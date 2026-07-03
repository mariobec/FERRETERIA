"""Diagnóstico rápido OC vs recepción (factura 5005433 / OC 47332341)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import app, db, RecepcionCompra, OrdenCompra, Producto  # noqa: E402

CODIGO_GENERICO = 'COMPRA-HIST-MAESTRA'


def main():
    with app.app_context():
        recs = RecepcionCompra.query.filter(
            db.or_(
                RecepcionCompra.documento_numero.ilike('%5005433%'),
                RecepcionCompra.guia_despacho_numero.ilike('%2112449%'),
            )
        ).all()
        print('=== Recepciones factura 5005433 / guía 2112449 ===')
        if not recs:
            print('(ninguna encontrada)')
        for r in recs:
            oc = r.orden_compra
            n_oc = len(oc.detalles) if oc else 0
            n_rec = len(r.detalles or [])
            print(
                f'Rec #{r.id} estado={r.estado} factura={r.documento_numero} '
                f'guia={r.guia_despacho_numero} oc_id={r.orden_compra_id} '
                f'oc_num={oc.numero if oc else None} lineas_oc={n_oc} lineas_rec={n_rec}'
            )
            if oc:
                n_gen = sum(
                    1 for d in oc.detalles
                    if d.producto and (d.producto.codigo_interno or '') == CODIGO_GENERICO
                )
                print(f'  OC genéricos COMPRA-HIST-MAESTRA: {n_gen}/{n_oc}')
                for i, d in enumerate(oc.detalles, 1):
                    p = d.producto
                    cod = (p.codigo_barra or p.codigo_interno or p.codigo_chilemat or '') if p else ''
                    gen = (p.codigo_interno or '') == CODIGO_GENERICO if p else False
                    print(
                        f'  OC[{i:02d}] pid={d.producto_id} cant={d.cantidad} gen={gen} '
                        f'cod={cod[:30]} nom={(p.nombre[:45] if p else None)}'
                    )
            print('  --- líneas recepción ---')
            for d in r.detalles or []:
                p = d.producto
                print(
                    f'  REC pid={d.producto_id} cant={d.cantidad_recibida} '
                    f'dest={d.almacen_destino} nom={(p.nombre[:45] if p else None)}'
                )

        ocs = OrdenCompra.query.filter(OrdenCompra.numero.ilike('%47332341%')).all()
        print('\n=== OCs número 47332341 ===')
        if not ocs:
            print('(ninguna encontrada)')
        for oc in ocs:
            print(f'OC #{oc.id} num={oc.numero} estado={oc.estado} lineas={len(oc.detalles)}')
            for i, d in enumerate(oc.detalles, 1):
                p = d.producto
                cod = (p.codigo_barra or p.codigo_interno or p.codigo_chilemat or '') if p else ''
                print(
                    f'  [{i:02d}] pid={d.producto_id} cant={d.cantidad} '
                    f'cod={cod[:25]} nom={(p.nombre[:40] if p else None)}'
                )


if __name__ == '__main__':
    main()
