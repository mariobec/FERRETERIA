"""
Máscaras de muro con segmentación IA (rembg) + recorte por polígono ERP.

rembg clasifica muebles como primer plano; el fondo (muros) queda con alpha bajo.
Se intersecta con wall_polygons de fabrica_color_service para la banda de muro.

Uso:
  pip install rembg pillow numpy opencv-python-headless
  python scripts/generar_mascaras_segmentacion.py
  python scripts/generar_mascaras_segmentacion.py --solo bano
  python scripts/generar_mascaras_segmentacion.py --metodo grabcut

Salida: static/img/fabrica-color/masks/{ambiente}.png
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from services.fabrica_color_service import AMBIENTES  # noqa: E402

PHOTOS = ROOT / 'static' / 'img' / 'fabrica-color' / 'ambientes'
MASKS = ROOT / 'static' / 'img' / 'fabrica-color' / 'masks'


def _load_polygon_builder():
    import importlib.util

    path = ROOT / 'scripts' / 'generar_mascaras_ambientes.py'
    spec = importlib.util.spec_from_file_location('gm', path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod.build_mask


def mask_from_polygons(size: tuple[int, int], amb: dict) -> Image.Image:
    build = _load_polygon_builder()
    return build(amb)


def mask_from_rembg(photo: Path, amb: dict) -> Image.Image | None:
    try:
        from rembg import remove
        import numpy as np
    except ImportError:
        return None

    data = photo.read_bytes()
    rgba = Image.open(io.BytesIO(remove(data))).convert('RGBA')
    w, h = rgba.size
    alpha = np.array(rgba.split()[3])

    # Alpha bajo ≈ fondo removido (muros en fotos de ambiente).
    wall = np.where(alpha < 110, 255, 0).astype('uint8')

    poly = np.array(mask_from_polygons((w, h), amb).resize((w, h), Image.Resampling.LANCZOS))
    result = np.minimum(wall, poly)

    try:
        import cv2

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        result = cv2.morphologyEx(result, cv2.MORPH_CLOSE, kernel, iterations=2)
        result = cv2.morphologyEx(result, cv2.MORPH_OPEN, kernel, iterations=1)
    except ImportError:
        pass

    return Image.fromarray(result, mode='L')


def mask_from_grabcut(photo: Path, amb: dict) -> Image.Image | None:
    path = ROOT / 'scripts' / 'generar_mascaras_ia.py'
    import importlib.util

    spec = importlib.util.spec_from_file_location('gmi', path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod.mask_from_grabcut(photo, amb)


def process(
    ambiente_id: str | None = None,
    metodo: str = 'rembg',
) -> None:
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

        mask: Image.Image | None = None
        if metodo == 'rembg':
            mask = mask_from_rembg(photo, amb)
        elif metodo == 'grabcut':
            mask = mask_from_grabcut(photo, amb)

        if mask is None:
            mask = mask_from_polygons((1400, 933), amb)
            print(f'FALLBACK polígonos {aid}')
        else:
            print(f'{metodo.upper()} OK {aid}')

        mask.save(out, optimize=True)
        print(f'  -> {out} ({out.stat().st_size} bytes)')


def main() -> None:
    p = argparse.ArgumentParser(description='Máscaras de muro con segmentación IA')
    p.add_argument('--solo', help='Solo un ambiente (ej. bano)')
    p.add_argument(
        '--metodo',
        choices=('rembg', 'grabcut', 'polygon'),
        default='rembg',
        help='rembg (IA), grabcut (OpenCV) o polygon (manual)',
    )
    args = p.parse_args()
    if args.metodo == 'polygon':
        build = _load_polygon_builder()
        MASKS.mkdir(parents=True, exist_ok=True)
        poly_items = AMBIENTES
        if args.solo:
            poly_items = [a for a in AMBIENTES if a['id'] == args.solo]
            if not poly_items:
                raise SystemExit(f'Ambiente desconocido: {args.solo}')
        for amb in poly_items:
            out = MASKS / f"{amb['id']}.png"
            build(amb).save(out, optimize=True)
            print(f'OK {amb["id"]} -> {out}')
        return
    process(args.solo, metodo=args.metodo)


if __name__ == '__main__':
    main()
