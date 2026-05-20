# -*- coding: utf-8 -*-
"""Genera variantes PNG del logo hexIA en los tamaños usados por el ERP."""
from __future__ import annotations

import os
import sys

from PIL import Image

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
STATIC_IMG = os.path.join(ROOT, 'static', 'img')
# Origen wordmark horizontal oficial (hex + lhexIA + ERP inteligente)
DEFAULT_SOURCE = os.path.join(STATIC_IMG, 'lhexia_brand_wordmark_oficial.png')
# Isotipo núcleo hexagonal (login / sidebar / favicon)
ICON_SOURCE = os.path.join(STATIC_IMG, 'lhexia-core-reveal-square.png')

OUTPUTS = (
    ('lhexia-brand-approved.png', (799, 270)),
    ('lhexia-brand-navbar.png', (799, 270)),
    ('lhexia-brand-compact-nav.png', (476, 162)),
    ('lhexia_logo_transparent.png', (724, 294)),
    ('lhexia-brand-official.png', (1024, 682)),  # respaldo OG grande
)

ICON_OUT = ('lhexia-icon-approved.png', (256, 256))


def autocrop_rgba(im: Image.Image, padding: int = 4) -> Image.Image:
    im = im.convert('RGBA')
    bbox = im.split()[3].getbbox()
    if not bbox:
        raise ValueError('Sin contenido visible')
    l, u, r, d = bbox
    w, h = im.size
    return im.crop((
        max(0, l - padding),
        max(0, u - padding),
        min(w, r + padding),
        min(h, d + padding),
    ))


def fit_on_canvas(im: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Escala manteniendo proporción y centra en canvas transparente."""
    tw, th = size
    canvas = Image.new('RGBA', (tw, th), (0, 0, 0, 0))
    im = im.convert('RGBA')
    im.thumbnail((tw, th), Image.Resampling.LANCZOS)
    x = (tw - im.width) // 2
    y = (th - im.height) // 2
    canvas.paste(im, (x, y), im)
    return canvas


def crop_isotipo_hex(im: Image.Image) -> Image.Image:
    """Recorta el hexágono (lado izquierdo del wordmark)."""
    w, h = im.size
    side = min(w, h)
    # Isotipo ~42% del ancho en el arte original recortado
    hex_w = max(side, int(w * 0.44))
    hex_w = min(hex_w, w)
    box = (0, 0, hex_w, h)
    cropped = im.crop(box)
    side = min(cropped.size)
    top = max(0, (cropped.height - side) // 2)
    left = 0
    return cropped.crop((left, top, left + side, top + side))


def main() -> int:
    src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SOURCE
    if not os.path.isfile(src):
        print('No existe origen:', src, file=sys.stderr)
        return 1

    os.makedirs(STATIC_IMG, exist_ok=True)
    with Image.open(src) as raw:
        cropped = autocrop_rgba(raw)
    cropped.save(os.path.join(STATIC_IMG, 'lhexia_logo_origen_v2.png'), 'PNG', optimize=True)

    for name, size in OUTPUTS:
        out = fit_on_canvas(cropped, size)
        path = os.path.join(STATIC_IMG, name)
        out.save(path, 'PNG', optimize=True)
        print('OK', name, size, '->', out.size)

    # Isotipo cuadrado: NO regenerar desde wordmark (rompe el sidebar). Usar hex-login.
    icon_hex = os.path.join(STATIC_IMG, 'lhexia-icon-hex-login.png')
    if os.path.isfile(icon_hex):
        print('SKIP isotipo — conservar', icon_hex, '(regenerar con scripts/procesar_logo_nav_definitivo solo wordmark)')
    elif os.path.isfile(ICON_SOURCE):
        with Image.open(ICON_SOURCE) as raw_icon:
            iso = autocrop_rgba(raw_icon)
        fit_on_canvas(iso, ICON_OUT[1]).save(os.path.join(STATIC_IMG, ICON_OUT[0]), 'PNG', optimize=True)
        print('OK', ICON_OUT[0], 'from', os.path.basename(ICON_SOURCE))

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
