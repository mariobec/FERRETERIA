#!/usr/bin/env python3
"""
Completar catálogo ERP al máximo desde Maestra compras + Consolidación materiales.

Objetivos:
  - codigo_barra / EAN → escaneo POS, enrolamiento, stock por almacén (filas en 0)
  - precio_compra + producto_codigo_proveedor → costo y cruce factura proveedor

Uso:
  .\\venv\\Scripts\\python.exe scripts\\maestra_completar_base_maxima.py
  .\\venv\\Scripts\\python.exe scripts\\maestra_completar_base_maxima.py --aplicar --dry-run
  .\\venv\\Scripts\\python.exe scripts\\maestra_completar_base_maxima.py --aplicar --limit-crear 200
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT_BASE = ROOT / "respaldos" / "maestra_completar"
USUARIO_ENRIQUECER = "maestra-completar-enriquecer"
USUARIO_CREAR = "maestra-completar-crear"
PREFIJO_INTERNO_PEND = "MAESTRA-PEND-"
PREFIJO_INTERNO_ACTIVO = "MAESTRA-"


def norm_prov(s) -> str:
    if pd.isna(s):
        return ""
    t = str(s).strip().upper()
    return re.sub(r"[^A-Z0-9 ]", "", re.sub(r"\s+", " ", t))


def norm_cod_factura(s) -> str:
    if pd.isna(s):
        return ""
    return str(s).strip().upper()


def precio_venta_sugerido(costo: float, margen: float) -> float:
    if costo <= 0:
        return 0.0
    return round(costo * (1 + margen), 0)


def elegir_codigo_barra(codigo_factura: str, ean: str, ocupados: set[str]) -> str | None:
    from services.maestra_unificado_loaders import norm_cod, norm_ean

    for candidato in (norm_ean(ean), norm_cod(codigo_factura)):
        if not candidato or len(candidato) < 4:
            continue
        if candidato in ocupados:
            continue
        return candidato[:50]
    cf = norm_cod(codigo_factura)
    if cf and len(cf) >= 4:
        alt = f"M-{cf}"[:50]
        if alt not in ocupados:
            return alt
    en = norm_ean(ean)
    if en:
        alt = f"EAN-{en}"[:50]
        if alt not in ocupados:
            return alt
    return None


def inicializar_stock_cero(producto) -> None:
    from app import fijar_stock_almacen, id_almacen_bodega, id_almacen_tienda

    aid_t = id_almacen_tienda()
    aid_b = id_almacen_bodega()
    if aid_t:
        fijar_stock_almacen(producto.id, aid_t, 0)
    if aid_b:
        fijar_stock_almacen(producto.id, aid_b, 0)
    producto.stock = 0


def build_plan(
    merged: pd.DataFrame,
    fase_a,
    pdf: pd.DataFrame,
    prv: pd.DataFrame,
    puente: pd.DataFrame,
    *,
    min_neto_activo: float,
) -> pd.DataFrame:
    indexes = fase_a.build_erp_indexes(pdf, prv, puente)
    rows = []
    for _, row in merged.iterrows():
        pid, prod, metodo, conf = fase_a.match_row(row, indexes, pdf)
        ean = str(row.get("ean_consolidacion") or "")
        from services.maestra_unificado_loaders import norm_ean

        ean_ok = bool(norm_ean(ean))
        neto = float(row.get("neto_f") or 0)
        ultimo = row.get("ultimo_costo_unitario")
        costo = float(ultimo) if ultimo is not None and pd.notna(ultimo) and float(ultimo) > 0 else 0.0

        if pid is not None:
            accion = "enriquecer"
            if conf < 72:
                accion = "revisar_enriquecer"
        else:
            if ean_ok and (neto >= min_neto_activo or costo > 0):
                accion = "crear_activo"
            elif neto > 0 or costo > 0:
                accion = "crear_pendiente"
            elif ean_ok:
                accion = "crear_activo"
            else:
                accion = "omitir_sin_prioridad"

        nombre = str(row.get("descripcion") or row.get("descripcion_consolidacion") or row.get("codigo_factura") or "")[:100]
        cat = str(row.get("grupo5") or row.get("familia_consolidacion") or "")[:50]
        sub = str(row.get("grupo4") or "")[:50]

        rows.append(
            {
                "accion": accion,
                "codigo_factura": row.get("codigo_factura"),
                "proveedor": row.get("proveedor"),
                "descripcion": nombre,
                "ean_consolidacion": ean,
                "en_consolidacion": bool(row.get("en_consolidacion")),
                "neto_acumulado": round(neto, 0),
                "ultimo_costo_unitario": round(costo, 2) if costo else "",
                "categoria_sugerida": cat,
                "subcategoria_sugerida": sub,
                "producto_id": pid or "",
                "match_metodo": metodo,
                "match_confianza": conf,
                "origen": row.get("origen", "maestra_compras"),
            }
        )

    return pd.DataFrame(rows)


def aplicar_enriquecer(
    df: pd.DataFrame,
    *,
    dry_run: bool,
    crear_proveedores: bool,
    actualizar_barra_ean: bool,
) -> tuple[list, list]:
    from scripts.maestra_fase_b_aplicar import get_or_create_proveedor_id, norm_codigo_factura, norm_proveedor

    import app as m
    from app import Producto, ProductoCodigoProveedor, _asegurar_tabla_producto_codigo_proveedor, db, guardar_producto_codigo_proveedor

    aplicados = []
    omitidos = []

    with m.app.app_context():
        _asegurar_tabla_producto_codigo_proveedor()
        from app import Proveedor

        proveedores = {norm_proveedor(p.nombre): p.id for p in Proveedor.query.all()}
        ocupados_barra = {
            norm_cod_factura(p.codigo_barra)
            for p in Producto.query.filter(Producto.codigo_barra.isnot(None)).all()
            if p.codigo_barra
        }
        puentes_existentes = {
            (int(r.proveedor_id), norm_codigo_factura(r.codigo_factura_proveedor))
            for r in ProductoCodigoProveedor.query.all()
        }

        for _, row in df.iterrows():
            try:
                pid = int(row["producto_id"])
            except (TypeError, ValueError):
                omitidos.append({"motivo": "sin_producto_id", "fila": row.to_dict()})
                continue

            cod = norm_codigo_factura(row.get("codigo_factura"))
            prov_nombre = row.get("proveedor") or ""
            prov_id = get_or_create_proveedor_id(
                prov_nombre, proveedores, [], crear=crear_proveedores, dry_run=dry_run
            )
            if not prov_id:
                omitidos.append({"producto_id": pid, "motivo": "proveedor_no_encontrado"})
                continue

            producto = Producto.query.get(pid)
            if not producto:
                omitidos.append({"producto_id": pid, "motivo": "producto_no_existe"})
                continue

            reg = {
                "producto_id": pid,
                "codigo_factura": cod,
                "accion": "enriquecer",
            }

            costo_maestra = pd.to_numeric(row.get("ultimo_costo_unitario"), errors="coerce")
            if pd.notna(costo_maestra) and float(costo_maestra) > 0:
                reg["precio_compra_nuevo"] = float(costo_maestra)
                if not dry_run:
                    producto.precio_compra = float(costo_maestra)

            cat = str(row.get("categoria_sugerida") or "").strip()[:50]
            sub = str(row.get("subcategoria_sugerida") or "").strip()[:50]
            if cat and not (producto.categoria or "").strip():
                reg["categoria"] = cat
                if not dry_run:
                    producto.categoria = cat
            if sub and not (producto.subcategoria or "").strip():
                reg["subcategoria"] = sub
                if not dry_run:
                    producto.subcategoria = sub

            ean = str(row.get("ean_consolidacion") or "")
            from services.maestra_unificado_loaders import norm_ean

            ean_n = norm_ean(ean)
            barra_actual = norm_cod_factura(producto.codigo_barra or "")
            if actualizar_barra_ean and ean_n and ean_n not in ocupados_barra and barra_actual != ean_n:
                reg["codigo_barra_nuevo"] = ean_n
                if not dry_run:
                    producto.codigo_barra = ean_n
                    ocupados_barra.add(ean_n)

            if cod and (int(prov_id), cod) not in puentes_existentes:
                if dry_run:
                    reg["puente"] = "dry_run"
                else:
                    ok, err = guardar_producto_codigo_proveedor(
                        prov_id, cod, pid, usuario=USUARIO_ENRIQUECER, commit=False
                    )
                    if not ok:
                        omitidos.append({"producto_id": pid, "motivo": err})
                        continue
                    puentes_existentes.add((int(prov_id), cod))
                    reg["puente"] = "creado"

            if not dry_run:
                db.session.flush()
            aplicados.append(reg)

        if not dry_run:
            db.session.commit()

    return aplicados, omitidos


def aplicar_crear(
    df: pd.DataFrame,
    *,
    dry_run: bool,
    margen: float,
    activo: bool,
) -> tuple[list, list]:
    import app as m
    from app import Producto, Proveedor, db, guardar_producto_codigo_proveedor

    creados = []
    omitidos = []

    with m.app.app_context():
        ocupados_barra = {
            norm_cod_factura(p.codigo_barra)
            for p in Producto.query.filter(Producto.codigo_barra.isnot(None)).all()
            if p.codigo_barra
        }
        prov_map = {norm_prov(p.nombre): p.id for p in Proveedor.query.all()}

        def get_prov_id(nombre):
            k = norm_prov(nombre)
            if k in prov_map:
                return prov_map[k]
            for pk, pid in prov_map.items():
                if pk and (pk in k or k in pk):
                    return pid
            if dry_run:
                return -1
            p = Proveedor(nombre=str(nombre).strip()[:100] or "PROVEEDOR MAESTRA")
            db.session.add(p)
            db.session.flush()
            prov_map[k] = p.id
            return p.id

        for _, row in df.iterrows():
            cod_f = norm_cod_factura(row.get("codigo_factura"))
            if not cod_f:
                omitidos.append({"motivo": "codigo_vacio"})
                continue

            prefijo = PREFIJO_INTERNO_ACTIVO if activo else PREFIJO_INTERNO_PEND
            interno = f"{prefijo}{cod_f}"[:32]
            if Producto.query.filter_by(codigo_interno=interno).first():
                omitidos.append({"codigo_factura": cod_f, "motivo": "ya_existe_interno"})
                continue

            ean = str(row.get("ean_consolidacion") or "")
            barra = elegir_codigo_barra(cod_f, ean, ocupados_barra)
            if not barra:
                omitidos.append({"codigo_factura": cod_f, "motivo": "sin_codigo_barra"})
                continue

            costo = pd.to_numeric(row.get("ultimo_costo_unitario"), errors="coerce")
            costo = float(costo) if pd.notna(costo) and float(costo) > 0 else 0.0
            nombre = str(row.get("descripcion") or cod_f)[:100]
            prov_nom = row.get("proveedor") or row.get("proveedor_consolidacion") or ""
            prov_id = get_prov_id(prov_nom)
            if not prov_id:
                omitidos.append({"codigo_factura": cod_f, "motivo": "sin_proveedor"})
                continue

            reg = {
                "codigo_factura": cod_f,
                "codigo_barra": barra,
                "codigo_interno": interno,
                "nombre": nombre,
                "precio_compra": costo,
                "precio_venta": precio_venta_sugerido(costo, margen),
                "activo": activo,
                "categoria": str(row.get("categoria_sugerida") or "")[:50],
            }

            if dry_run:
                reg["dry_run"] = True
                creados.append(reg)
                continue

            p = Producto(
                nombre=nombre,
                codigo_barra=barra,
                codigo_interno=interno,
                precio_compra=costo,
                precio_venta=reg["precio_venta"],
                categoria=reg["categoria"] or None,
                subcategoria=str(row.get("subcategoria_sugerida") or "")[:50] or None,
                stock=0,
                activo=activo,
            )
            db.session.add(p)
            db.session.flush()
            inicializar_stock_cero(p)
            ocupados_barra.add(norm_cod_factura(barra))

            ok, err = guardar_producto_codigo_proveedor(
                prov_id, cod_f, p.id, usuario=USUARIO_CREAR, commit=True
            )
            if not ok:
                db.session.rollback()
                omitidos.append({"codigo_factura": cod_f, "motivo": err})
                continue

            reg["producto_id"] = p.id
            creados.append(reg)

    return creados, omitidos


def main() -> int:
    ap = argparse.ArgumentParser(description="Completar base ERP desde maestros")
    ap.add_argument("--maestra", type=Path, default=None)
    ap.add_argument("--consolidacion", type=Path, default=None)
    ap.add_argument("--consolidacion-sample", type=int, default=0, help="Solo N filas (prueba)")
    ap.add_argument("--aplicar", action="store_true", help="Escribe en BD (con backups CSV)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--min-neto-activo", type=float, default=50_000)
    ap.add_argument("--limit-enriquecer", type=int, default=5000)
    ap.add_argument("--limit-crear-activo", type=int, default=300)
    ap.add_argument("--limit-crear-pendiente", type=int, default=500)
    ap.add_argument("--margen", type=float, default=0.35)
    ap.add_argument(
        "--incluir-solo-consolidacion",
        action="store_true",
        help="Incluye códigos solo en consolidación (con EAN), hasta --limit-solo-consolidacion",
    )
    ap.add_argument("--limit-solo-consolidacion", type=int, default=2000)
    ap.add_argument("--no-actualizar-barra-ean", action="store_false", dest="actualizar_barra_ean")
    args = ap.parse_args()

    from services.maestra_unificado_loaders import (
        consolidacion_sin_maestra,
        load_consolidacion,
        merge_maestra_consolidacion,
        resolve_consolidacion_path,
        resolve_maestra_path,
    )
    sys.path.insert(0, str(ROOT / "scripts"))
    import maestra_fase_a_enriquecer as fase_a

    maestra_path = resolve_maestra_path(args.maestra)
    cons_path = resolve_consolidacion_path(args.consolidacion)

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    out_dir = OUT_BASE / stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Maestra:", maestra_path)
    raw = fase_a.load_maestra(maestra_path)
    agg = fase_a.aggregate_por_codigo(raw)
    print("Claves compra:", len(agg))

    cons = None
    if cons_path:
        print("Consolidación:", cons_path)
        sample = args.consolidacion_sample if args.consolidacion_sample > 0 else None
        cons = load_consolidacion(cons_path, sample=sample)
        print("Códigos únicos consolidación:", len(cons))
    else:
        print("Sin consolidación (solo maestra compras).")

    merged = merge_maestra_consolidacion(agg, cons)
    merged["origen"] = "maestra_compras"

    if args.incluir_solo_consolidacion and cons is not None and not cons.empty:
        codigos_mae = set(merged["codigo_n"].astype(str))
        solo = consolidacion_sin_maestra(cons, codigos_mae)
        solo = solo[solo["ean_n"].astype(str).str.len() >= 8]
        solo = solo.head(max(1, args.limit_solo_consolidacion))
        if not solo.empty:
            extra = solo.copy()
            for c in ("grupo5", "grupo4", "grupo1", "familia_aa"):
                extra[c] = ""
            extra["neto_f"] = 0
            extra["cantidad_f"] = 0
            extra["ultimo_costo_unitario"] = None
            extra["codigo_factura_n"] = extra["codigo_n"]
            extra["proveedor_n"] = extra["proveedor"].map(fase_a.norm_proveedor)
            extra["descripcion_n"] = extra["descripcion"].map(fase_a.norm_text)
            extra["en_consolidacion"] = True
            merged = pd.concat([merged, extra], ignore_index=True, sort=False)

    pdf, prv, puente = fase_a.load_erp_catalog()
    plan = build_plan(
        merged,
        fase_a,
        pdf,
        prv,
        puente,
        min_neto_activo=args.min_neto_activo,
    )
    plan.sort_values(["neto_acumulado"], ascending=False, inplace=True)

    plan.to_csv(out_dir / "00_plan_completo.csv", index=False, encoding="utf-8-sig")
    for accion, fname in (
        ("enriquecer", "01_enriquecer.csv"),
        ("revisar_enriquecer", "02_revisar_enriquecer.csv"),
        ("crear_activo", "03_crear_activo.csv"),
        ("crear_pendiente", "04_crear_pendiente.csv"),
        ("omitir_sin_prioridad", "05_omitir.csv"),
    ):
        sub = plan[plan["accion"] == accion]
        sub.to_csv(out_dir / fname, index=False, encoding="utf-8-sig")

    conteos = plan["accion"].value_counts().to_dict()
    resumen = f"""# Completar base ERP — plan maestro

Generado: {datetime.now().isoformat(timespec="seconds")}
Maestra: {maestra_path}
Consolidación: {cons_path or '—'}
Salida: {out_dir}

## Conteos plan
| Acción | Cantidad |
|--------|--------:|
"""
    for k, v in sorted(conteos.items(), key=lambda x: -x[1]):
        resumen += f"| {k} | {v:,} |\n"
    resumen += f"""
## ERP actual
| Productos | {len(pdf):,} |
| Proveedores | {len(prv):,} |
| Puentes factura | {len(puente):,} |

## Siguiente paso
1. Revisar `02_revisar_enriquecer.csv` manualmente si hay dudas.
2. `python scripts/maestra_completar_base_maxima.py --aplicar --dry-run`
3. Sin dry-run: `python scripts/maestra_completar_base_maxima.py --aplicar`

Límites aplicación: enriquecer={args.limit_enriquecer}, activo={args.limit_crear_activo}, pendiente={args.limit_crear_pendiente}
"""
    (out_dir / "RESUMEN.md").write_text(resumen, encoding="utf-8")
    print(resumen)

    if not args.aplicar:
        print("Solo plan (sin BD). Use --aplicar para escribir.")
        return 0

    enr = plan[plan["accion"].isin(["enriquecer", "revisar_enriquecer"])].head(args.limit_enriquecer)
    act = plan[plan["accion"] == "crear_activo"].head(args.limit_crear_activo)
    pend = plan[plan["accion"] == "crear_pendiente"].head(args.limit_crear_pendiente)

    meta = {"dry_run": args.dry_run, "stamp": stamp}
    if not enr.empty:
        aplicados, omitidos = aplicar_enriquecer(
            enr,
            dry_run=args.dry_run,
            crear_proveedores=True,
            actualizar_barra_ean=args.actualizar_barra_ean,
        )
        pd.DataFrame(aplicados).to_csv(out_dir / "aplicados_enriquecer.csv", index=False, encoding="utf-8-sig")
        pd.DataFrame(omitidos).to_csv(out_dir / "omitidos_enriquecer.csv", index=False, encoding="utf-8-sig")
        meta["enriquecidos"] = len(aplicados)
        meta["omitidos_enriquecer"] = len(omitidos)

    if not act.empty:
        creados, omit = aplicar_crear(act, dry_run=args.dry_run, margen=args.margen, activo=True)
        pd.DataFrame(creados).to_csv(out_dir / "creados_activo.csv", index=False, encoding="utf-8-sig")
        pd.DataFrame(omit).to_csv(out_dir / "omitidos_activo.csv", index=False, encoding="utf-8-sig")
        meta["creados_activo"] = len(creados)

    if not pend.empty:
        creados, omit = aplicar_crear(pend, dry_run=args.dry_run, margen=args.margen, activo=False)
        pd.DataFrame(creados).to_csv(out_dir / "creados_pendiente.csv", index=False, encoding="utf-8-sig")
        pd.DataFrame(omit).to_csv(out_dir / "omitidos_pendiente.csv", index=False, encoding="utf-8-sig")
        meta["creados_pendiente"] = len(creados)

    (out_dir / "meta_aplicacion.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
