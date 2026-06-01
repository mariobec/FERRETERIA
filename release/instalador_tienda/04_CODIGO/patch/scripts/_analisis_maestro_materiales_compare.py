#!/usr/bin/env python3
"""Compara Maestra compras vs Consolidacion materiales vs ERP (lectura)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
BASE = ROOT / 'docs' / 'Maestro Materiales'
OUT = ROOT / 'respaldos' / 'maestro_materiales_compare'
OUT.mkdir(parents=True, exist_ok=True)


def norm_cod(x) -> str:
    if pd.isna(x):
        return ''
    s = str(x).strip().upper()
    s = re.sub(r'\s+', '', s)
    if s.startswith('INT-'):
        s = s[4:]
    return s


def norm_bar(x) -> str:
    if pd.isna(x):
        return ''
    s = re.sub(r'\D', '', str(x))
    return s if len(s) >= 8 else ''


def col_match(cols, *parts):
    for c in cols:
        u = str(c).upper()
        if all(p.upper() in u for p in parts):
            return c
    return None


def main() -> int:
    cons_path = BASE / 'Consolidacion_Maestro_Materiales.xlsx'
    mae_path = BASE / 'Maestra_Ferreteria_Santo_Domingo.xlsx'
    if not cons_path.is_file() or not mae_path.is_file():
        print('Faltan archivos en', BASE)
        return 1

    print('Cargando Consolidacion...')
    cons = pd.read_excel(cons_path, sheet_name=0)
    print('Cargando Maestra Hoja1...')
    mae = pd.read_excel(mae_path, sheet_name='Hoja1')

    ccol = col_match(cons.columns, 'CODIGO', 'PRODUCTO') or cons.columns[3]
    bcol_c = col_match(cons.columns, 'BARRA') or col_match(cons.columns, 'EAN') or cons.columns[5]
    dcol_c = col_match(cons.columns, 'DESCRIPCION') or cons.columns[4]
    pcol = col_match(cons.columns, 'PROVEEDOR') or cons.columns[1]
    fcol = col_match(cons.columns, 'FAMILIA') or cons.columns[-1]

    m_cod = col_match(mae.columns, 'digo', 'Producto') or mae.columns[3]
    m_bar = col_match(mae.columns, 'Barra') or mae.columns[4]
    m_desc = col_match(mae.columns, 'Descripci') or mae.columns[5]

    cons['_cod'] = cons[ccol].map(norm_cod)
    cons['_bar'] = cons[bcol_c].map(norm_bar)
    mae['_cod'] = mae[m_cod].map(norm_cod)
    mae['_bar'] = mae[m_bar].map(norm_bar)

    cons_cod = set(cons.loc[cons['_cod'] != '', '_cod'])
    mae_cod = set(mae.loc[mae['_cod'] != '', '_cod'])
    cons_bar = set(cons.loc[cons['_bar'] != '', '_bar'])
    mae_bar = set(mae.loc[mae['_bar'] != '', '_bar'])

    lines = [
        '# Comparación maestro de materiales',
        '',
        '## Archivos',
        f'- **Consolidacion_Maestro_Materiales.xlsx**: {len(cons):,} filas, catálogo proveedores (códigos, EAN, dimensiones, familia).',
        f'- **Maestra_Ferreteria_Santo_Domingo.xlsx** (Hoja1): {len(mae):,} filas, historial compras 2024-2026 (cantidad, neto, grupos).',
        '',
        '## Códigos producto',
        f'| Métrica | Cantidad |',
        f'|--------|----------|',
        f'| Códigos únicos Consolidación | {len(cons_cod):,} |',
        f'| Códigos únicos Maestra compras | {len(mae_cod):,} |',
        f'| En ambos | {len(cons_cod & mae_cod):,} |',
        f'| Solo en maestra compras (compraron, no en consolidado) | {len(mae_cod - cons_cod):,} |',
        f'| Solo en consolidación (catálogo, sin línea en maestra compras) | {len(cons_cod - mae_cod):,} |',
        '',
        '## Código de barras / EAN',
        f'| Métrica | Cantidad |',
        f'|--------|----------|',
        f'| EAN únicos Consolidación | {len(cons_bar):,} |',
        f'| EAN únicos Maestra compras | {len(mae_bar):,} |',
        f'| EAN en ambos | {len(cons_bar & mae_bar):,} |',
        f'| EAN solo maestra compras | {len(mae_bar - cons_bar):,} |',
        f'| EAN solo consolidación | {len(cons_bar - mae_bar):,} |',
        '',
    ]

    # Muestras CSV
    solo_mae = sorted(mae_cod - cons_cod)[:500]
    pd.DataFrame({'codigo': solo_mae}).to_csv(OUT / 'codigos_solo_maestra_compras.csv', index=False)
    solo_cons = sorted(cons_cod - mae_cod)[:2000]
    pd.DataFrame({'codigo': solo_cons}).to_csv(OUT / 'codigos_solo_consolidacion_muestra.csv', index=False)

    # ERP
    erp_note = ''
    try:
        env_path = ROOT / '.env.local'
        if env_path.is_file():
            for raw in env_path.read_text(encoding='utf-8').splitlines():
                line = raw.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, _, v = line.partition('=')
                if k.strip() in ('DATABASE_URL', 'NEON_DATABASE_URL') and v.strip():
                    import os

                    os.environ['DATABASE_URL'] = v.strip().strip('"').strip("'")
                    break
        from app import app
        from app import Producto

        with app.app_context():
            prods = Producto.query.filter(Producto.activo.isnot(False)).all()
            erp_bar: set[str] = set()
            for p in prods:
                b = norm_bar(p.codigo_barra)
                if b:
                    erp_bar.add(b)
            mae_in_erp = len(mae_bar & erp_bar)
            cons_in_erp = len(cons_bar & erp_bar)
            lines.extend(
                [
                    '## ERP (productos activos)',
                    f'- Productos activos en BD: **{len(prods):,}**',
                    f'- Con código de barras: **{len(erp_bar):,}**',
                    f'- EAN maestra compras que ya están en ERP: **{mae_in_erp:,}** ({100 * mae_in_erp / max(1, len(mae_bar)):.1f}% de EAN maestra)',
                    f'- EAN consolidación que están en ERP: **{cons_in_erp:,}** ({100 * cons_in_erp / max(1, len(cons_bar)):.1f}% de EAN consolidación)',
                    '',
                ]
            )
            erp_note = 'ok'
    except Exception as ex:
        lines.extend(['## ERP', f'- No se pudo consultar BD: `{ex}`', ''])

    lines.extend(
        [
            '## Conclusión',
            '',
            '**Tu impresión es correcta:** `Consolidacion_Maestro_Materiales` es el **maestro de catálogo** '
            '(descripciones, EAN, medidas, marca, familia, proveedor) con ~213k filas.',
            '',
            '`Maestra_Ferreteria_Santo_Domingo` es el **historial de compras** (qué se compró, cuánto, a quién) '
            '— útil para costos, ranking y priorizar altas en ERP; no reemplaza el consolidado para fichas de producto.',
            '',
            '**Uso recomendado:**',
            '1. **Alta/homologación ERP + Chilemat:** Consolidación (código + EAN + descripción).',
            '2. **Costo y priorización:** Maestra compras (neto, cantidad, proveedor).',
            '3. Cruzar ambos por `Código Producto` / EAN antes de importar.',
            '',
        ]
    )

    md = '\n'.join(lines)
    (OUT / 'RESUMEN.md').write_text(md, encoding='utf-8')
    print(md)
    print('CSV y RESUMEN en', OUT)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
