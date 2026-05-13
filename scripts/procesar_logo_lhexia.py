# -*- coding: utf-8 -*-
"""
Procesa el logotipo **LhexIA**: fondo oscuro → transparente, autocrop, PNG optimizado.

Marca (ortografía): **L** (isotipo) + **hexIA** — la palabra lleva **h** («hex»), no «Lex».
Útil con fondo negro o tablero negro/gris muy oscuro.

Dependencia: Pillow (requirements.txt).

Uso:
    python scripts/procesar_logo_lhexia.py
    python scripts/procesar_logo_lhexia.py --input static/img/mi_logo.png
    python scripts/procesar_logo_lhexia.py --umbral 65 --padding 2

Por defecto busca (en orden) en la raíz del proyecto:
    static/img/lhexia_logo_origen.png
    static/img/lhexia_logo.png
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from PIL import Image

DEFAULT_CANDIDATES = (
    'static/img/lhexia_logo_origen.png',
    'static/img/lhexia_logo.png',
    'static/img/lhexia_logo_orig.png',
)
DEFAULT_OUTPUT = 'static/img/lhexia_logo_transparent.png'


def _raiz() -> str:
    return os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))


def _resolver(ruta: str) -> str:
    if os.path.isabs(ruta):
        return os.path.normpath(ruta)
    return os.path.normpath(os.path.join(_raiz(), ruta))


def aplicar_fondo_transparente(img: Image.Image, umbral_max_rgb: int) -> Image.Image:
    """
    Pasa a RGBA y pone alpha=0 en píxeles de fondo oscuro (negro puro o gris muy oscuro).
    Criterio: max(R,G,B) <= umbral — conserva blanco y naranjas del logo (L + hexIA).
    """
    rgba = img.convert('RGBA')
    px = rgba.load()
    w, h = rgba.size
    t = int(umbral_max_rgb)
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if max(r, g, b) <= t:
                px[x, y] = (0, 0, 0, 0)
    return rgba


def autocrop_por_alpha(img: Image.Image, padding: int = 0) -> Image.Image:
    """Recorta al bbox del canal alfa > 0 (equivalente a contenido visible)."""
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    alpha = img.split()[3]
    bbox = alpha.getbbox()
    if bbox is None:
        raise ValueError('No quedó contenido visible tras la transparencia (¿umbral demasiado alto?).')
    if padding > 0:
        l, u, r, d = bbox
        w, h = img.size
        bbox = (
            max(0, l - padding),
            max(0, u - padding),
            min(w, r + padding),
            min(h, d + padding),
        )
    return img.crop(bbox)


def main() -> int:
    ap = argparse.ArgumentParser(description='Limpia y recorta logo LhexIA → PNG transparente.')
    ap.add_argument(
        '--input',
        '-i',
        default='',
        help='Ruta a la imagen origen (relativa al proyecto o absoluta). Si se omite, se prueban rutas por defecto.',
    )
    ap.add_argument(
        '--output',
        '-o',
        default=DEFAULT_OUTPUT,
        help='Ruta del PNG de salida (default: static/img/lhexia_logo_transparent.png).',
    )
    ap.add_argument(
        '--umbral',
        type=int,
        default=64,
        help='Máx(R,G,B) considerado fondo oscuro (default 64). Subir (p.ej. 72) si queda tablero gris; bajar si se comen bordes del logo.',
    )
    ap.add_argument('--padding', type=int, default=0, help='Píxeles de margen alrededor del bbox (default 0).')
    args = ap.parse_args()

    entrada = (args.input or '').strip()
    if not entrada:
        for cand in DEFAULT_CANDIDATES:
            p = _resolver(cand)
            if os.path.isfile(p):
                entrada = p
                print('[LhexIA] Entrada por defecto:', cand)
                break
        if not entrada:
            print(
                '[LhexIA] No se encontró imagen origen. Coloque el archivo en una de:\n  '
                + '\n  '.join(DEFAULT_CANDIDATES)
                + '\n  o use: python scripts/procesar_logo_lhexia.py --input ruta/al/logo.png',
                file=sys.stderr,
            )
            return 1
    else:
        entrada = _resolver(entrada)

    if not os.path.isfile(entrada):
        print('[LhexIA] No existe el archivo:', entrada, file=sys.stderr)
        return 1

    salida = _resolver(args.output)
    os.makedirs(os.path.dirname(salida), exist_ok=True)

    with Image.open(entrada) as src:
        im = src.convert('RGBA')
    procesada = aplicar_fondo_transparente(im, args.umbral)
    recortada = autocrop_por_alpha(procesada, padding=args.padding)

    recortada.save(salida, format='PNG', optimize=True)
    print('[LhexIA] Guardado:', salida, '| tamaño:', recortada.size)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
