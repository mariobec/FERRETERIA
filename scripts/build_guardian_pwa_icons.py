# -*- coding: utf-8 -*-
"""Iconos PWA Guardián — núcleo login sobre fondo #0b0f19 (sin circuito blanco)."""
from __future__ import annotations

import os

from PIL import Image

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
IMG = os.path.join(ROOT, 'static', 'img')
OUT = os.path.join(ROOT, 'static', 'owner-pwa')
BG = (11, 15, 25)  # --login-bg


def _fit_center(im: Image.Image, canvas: int, scale: float = 0.72) -> Image.Image:
    side = int(canvas * scale)
    im = im.convert('RGBA')
    im.thumbnail((side, side), Image.Resampling.LANCZOS)
    out = Image.new('RGBA', (canvas, canvas), (*BG, 255))
    x = (canvas - im.width) // 2
    y = (canvas - im.height) // 2
    out.paste(im, (x, y), im)
    return out


def _maskable(im: Image.Image, canvas: int) -> Image.Image:
    """Icono maskable: arte ~62% del lienzo (zona segura Android)."""
    return _fit_center(im, canvas, scale=0.62)


def main() -> int:
    src = os.path.join(IMG, 'lhexia-core-reveal-square.png')
    if not os.path.isfile(src):
        src = os.path.join(IMG, 'lhexia-icon-approved.png')
    if not os.path.isfile(src):
        print('Falta lhexia-core-reveal-square.png o lhexia-icon-approved.png', flush=True)
        return 1

    os.makedirs(OUT, exist_ok=True)
    with Image.open(src) as raw:
        for size, name, fn in (
            (192, 'icon-192.png', _fit_center),
            (512, 'icon-512.png', _fit_center),
            (512, 'icon-512-maskable.png', _maskable),
            (180, 'apple-touch-icon.png', _fit_center),
        ):
            out = fn(raw, size)
            path = os.path.join(OUT, name)
            out.convert('RGB').save(path, 'PNG', optimize=True)
            print('OK', path)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
