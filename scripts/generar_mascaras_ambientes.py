"""Genera máscaras PNG de muro para el visualizador Colores en tienda."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw  # noqa: E402

from services.fabrica_color_service import AMBIENTES  # noqa: E402

OUT = ROOT / 'static' / 'img' / 'fabrica-color' / 'masks'
SIZE = (1400, 933)


def _scale(poly: list, w: int, h: int) -> list[tuple[int, int]]:
    return [(int(p[0] * w), int(p[1] * h)) for p in poly]


def _ellipse_box(ex: list, w: int, h: int) -> tuple[int, int, int, int]:
    cx, cy, rx, ry = ex
    x0 = int((cx - rx) * w)
    y0 = int((cy - ry) * h)
    x1 = int((cx + rx) * w)
    y1 = int((cy + ry) * h)
    return x0, y0, x1, y1


def build_mask(amb: dict) -> Image.Image:
    w, h = SIZE
    img = Image.new('L', (w, h), 0)
    draw = ImageDraw.Draw(img)
    polys = amb.get('wall_polygons') or []
    if not polys and amb.get('wall_polygon'):
        polys = [amb['wall_polygon']]
    for poly in polys:
        draw.polygon(_scale(poly, w, h), fill=255)
    for ex in amb.get('wall_exclusions') or []:
        draw.ellipse(_ellipse_box(ex, w, h), fill=0)
    # Sin blur: el difuminado filtraba alpha al mueble y teñía toda la foto.
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for amb in AMBIENTES:
        aid = amb['id']
        mask = build_mask(amb)
        path = OUT / f'{aid}.png'
        mask.save(path, optimize=True)
        print(f'OK {aid} -> {path} ({path.stat().st_size} bytes)')


if __name__ == '__main__':
    main()
