#!/usr/bin/env python3
"""Genera isotipo PNG con fondo transparente (PWA, sidebar claro, login)."""
from __future__ import annotations

import os
import sys

from PIL import Image

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
IMG = os.path.join(ROOT, 'static', 'img')
PWA = os.path.join(ROOT, 'static', 'owner-pwa')


def _alpha_trim(im: Image.Image, thr: int = 28) -> Image.Image:
    im = im.convert('RGBA')
    w, h = im.size
    px = im.load()
    min_x, min_y, max_x, max_y = w, h, 0, 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 10:
                continue
            if r <= thr and g <= thr and b <= thr:
                px[x, y] = (r, g, b, 0)
                continue
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)
    if max_x <= min_x:
        return im
    pad = 4
    return im.crop((
        max(0, min_x - pad),
        max(0, min_y - pad),
        min(w, max_x + pad + 1),
        min(h, max_y + pad + 1),
    ))


def _fit_square(im: Image.Image, size: int) -> Image.Image:
    side = max(im.width, im.height)
    canvas = Image.new('RGBA', (side, side), (0, 0, 0, 0))
    ox = (side - im.width) // 2
    oy = (side - im.height) // 2
    canvas.paste(im, (ox, oy), im)
    return canvas.resize((size, size), Image.Resampling.LANCZOS)


def main() -> int:
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(IMG, 'lhexia_isotipo_definitivo_origen.png')
    if not os.path.isfile(src):
        src = os.path.join(IMG, 'lhexia-icon-approved.png')
    if not os.path.isfile(src):
        print('No hay imagen origen', file=sys.stderr)
        return 1
    os.makedirs(PWA, exist_ok=True)
    with Image.open(src) as raw:
        trimmed = _alpha_trim(raw)
        for size, name in ((256, 'lhexia-icon-transparent.png'), (512, 'icon-512.png')):
            out = _fit_square(trimmed, size)
            path = os.path.join(IMG if size == 256 else PWA, name)
            out.save(path, 'PNG', optimize=True)
            print('OK', path, size)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
