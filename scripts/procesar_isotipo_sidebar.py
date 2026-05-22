# -*- coding: utf-8 -*-
"""Isotipo hex LhexIA (fondo negro) para sidebar y favicon."""
from __future__ import annotations

import os
import sys

from PIL import Image

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
IMG = os.path.join(ROOT, 'static', 'img')


def on_black(im: Image.Image) -> Image.Image:
    im = im.convert('RGBA')
    bg = Image.new('RGBA', im.size, (0, 0, 0, 255))
    bg.paste(im, (0, 0), im)
    return bg.convert('RGB')


def trim_content(im: Image.Image, thr: int = 24, pad: int = 4) -> Image.Image:
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
    side = max(max_x - min_x + 1, max_y - min_y + 1)
    cx = (min_x + max_x) // 2
    cy = (min_y + max_y) // 2
    half = side // 2 + pad
    return im.crop((
        max(0, cx - half),
        max(0, cy - half),
        min(w, cx + half),
        min(h, cy + half),
    ))


def square_fit(im: Image.Image, size: int) -> Image.Image:
    side = max(im.width, im.height)
    canvas = Image.new('RGB', (side, side), (0, 0, 0))
    ox = (side - im.width) // 2
    oy = (side - im.height) // 2
    canvas.paste(im, (ox, oy))
    return canvas.resize((size, size), Image.Resampling.LANCZOS)


def main() -> int:
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(IMG, 'lhexia_isotipo_definitivo_origen.png')
    if not os.path.isfile(src):
        print('No existe:', src, file=sys.stderr)
        return 1
    os.makedirs(IMG, exist_ok=True)
    with Image.open(src) as raw:
        base = on_black(raw)
        cropped = trim_content(base)
        square_fit(cropped, 256).save(os.path.join(IMG, 'lhexia-icon-approved.png'), 'PNG', optimize=True)
        square_fit(cropped, 128).save(os.path.join(IMG, 'lhexia-icon-login.png'), 'PNG', optimize=True)
        square_fit(cropped, 128).save(os.path.join(IMG, 'lhexia-icon-hex-login.png'), 'PNG', optimize=True)
        base.save(os.path.join(IMG, 'lhexia_isotipo_definitivo_origen.png'), 'PNG', optimize=True)
    print('OK isotipo sidebar 256+128 desde', os.path.basename(src))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
