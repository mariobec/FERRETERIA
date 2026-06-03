"""
Genera máscaras de muro con GrabCut (OpenCV) o polígonos de respaldo.

Uso:
  pip install opencv-python-headless pillow numpy
  python scripts/generar_mascaras_ia.py
  python scripts/generar_mascaras_ia.py --solo living

Opcional: segmentación rembg (mejor contorno):
  python scripts/generar_mascaras_segmentacion.py --solo bano

Salida: static/img/fabrica-color/masks/{ambiente}.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from services.fabrica_color_service import AMBIENTES  # noqa: E402

PHOTOS = ROOT / 'static' / 'img' / 'fabrica-color' / 'ambientes'
MASKS = ROOT / 'static' / 'img' / 'fabrica-color' / 'masks'


def _poly_bounds(poly: list) -> tuple[int, int, int, int]:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def mask_from_polygons(size: tuple[int, int], amb: dict) -> Image.Image:
    import importlib.util

    path = ROOT / 'scripts' / 'generar_mascaras_ambientes.py'
    spec = importlib.util.spec_from_file_location('gm', path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod.build_mask(amb)


def mask_from_grabcut(photo: Path, amb: dict) -> Image.Image | None:
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None

    img = cv2.imread(str(photo))
    if img is None:
        return None

    h, w = img.shape[:2]
    polys = amb.get('wall_polygons') or []
    if not polys:
        return None

    x0 = min(_poly_bounds(p)[0] for p in polys)
    y0 = min(_poly_bounds(p)[1] for p in polys)
    x1 = max(_poly_bounds(p)[2] for p in polys)
    y1 = max(_poly_bounds(p)[3] for p in polys)

    rect = (
        int(x0 * w),
        int(y0 * h),
        max(1, int((x1 - x0) * w)),
        max(1, int((y1 - y0) * h)),
    )

    mask = np.zeros((h, w), np.uint8)
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    cv2.grabCut(img, mask, rect, bgd, fgd, 4, cv2.GC_INIT_WITH_RECT)

    bin_mask = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype('uint8')

    poly_mask = mask_from_polygons((w, h), amb)
    poly_arr = np.array(poly_mask.resize((w, h), Image.Resampling.LANCZOS))

    # Polígono = banda de muro completa. GrabCut solo resta objetos en primer plano
    # (intersección mínima dejaba huecos en espejos/ventanas del muro).
    y_cut = int(min(_poly_bounds(p)[3] for p in polys) * h * 0.72)
    fg_obj = (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD)
    result = poly_arr.copy()
    if y_cut < h:
        strip = np.zeros((h, w), dtype=bool)
        strip[y_cut:, :] = True
        result[strip & fg_obj] = 0
    return Image.fromarray(result, mode='L')


def process(ambiente_id: str | None = None, use_grabcut: bool = True) -> None:
    MASKS.mkdir(parents=True, exist_ok=True)
    items = AMBIENTES
    if ambiente_id:
        items = [a for a in AMBIENTES if a['id'] == ambiente_id]
        if not items:
            raise SystemExit(f'Ambiente desconocido: {ambiente_id}')

    for amb in items:
        aid = amb['id']
        photo = PHOTOS / f'{aid}.jpg'
        out = MASKS / f'{aid}.png'
        if not photo.exists():
            print(f'SKIP {aid}: falta {photo}')
            continue

        mask = None
        if use_grabcut:
            mask = mask_from_grabcut(photo, amb)
        if mask is None:
            mask = mask_from_polygons((1400, 933), amb)
            print(f'FALLBACK polígonos {aid}')
        else:
            print(f'GrabCut OK {aid}')

        mask.save(out, optimize=True)
        print(f'  -> {out} ({out.stat().st_size} bytes)')


def main() -> None:
    p = argparse.ArgumentParser(description='Máscaras de muro con IA/heurística')
    p.add_argument('--solo', help='Solo un ambiente (ej. living)')
    p.add_argument('--sin-grabcut', action='store_true', help='Solo polígonos')
    args = p.parse_args()
    process(args.solo, use_grabcut=not args.sin_grabcut)


if __name__ == '__main__':
    main()
