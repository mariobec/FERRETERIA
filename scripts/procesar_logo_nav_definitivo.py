# -*- coding: utf-8 -*-
"""Recorta logo LhexIA fondo negro para navbar."""
from __future__ import annotations

import os
import sys

from PIL import Image

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
IMG = os.path.join(ROOT, 'static', 'img')
DEFAULT_SRC = os.path.join(
    ROOT,
    'assets',
    'lhexia_brand_nav_definitivo_copilot.png',
)


def trim_black(im: Image.Image, thr: int = 22, pad: int = 10) -> Image.Image:
    im = im.convert('RGB')
    w, h = im.size
    px = im.load()
    min_x, min_y, max_x, max_y = w, h, 0, 0
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            if r > thr or g > thr or b > thr:
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    if max_x <= min_x:
        return im
    return im.crop((max(0, min_x - pad), max(0, min_y - pad), min(w, max_x + pad + 1), min(h, max_y + pad + 1)))


def fit_h(im: Image.Image, h: int) -> Image.Image:
    r = h / im.height
    return im.resize((max(1, int(im.width * r)), h), Image.Resampling.LANCZOS)


def main() -> int:
    src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SRC
    if not os.path.isfile(src):
        print('No existe:', src, file=sys.stderr)
        return 1
    os.makedirs(IMG, exist_ok=True)
    with Image.open(src) as raw:
        cropped = trim_black(raw)
        cropped.save(os.path.join(IMG, 'lhexia_brand_nav_definitivo_origen.png'), 'PNG', optimize=True)
        fit_h(cropped, 96).save(os.path.join(IMG, 'lhexia-brand-navbar.png'), 'PNG', optimize=True)
        fit_h(cropped, 80).save(os.path.join(IMG, 'lhexia-brand-compact-nav.png'), 'PNG', optimize=True)
        fit_h(cropped, 120).save(os.path.join(IMG, 'lhexia-brand-approved.png'), 'PNG', optimize=True)
        cropped.save(os.path.join(IMG, 'lhexia_brand_wordmark_oficial.png'), 'PNG', optimize=True)
    print('OK recorte', cropped.size)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
