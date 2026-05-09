"""
Quita fondo casi negro de un PNG del logo y guarda RGBA transparente.
Uso:
  python scripts/remove_logo_black_bg.py entrada.png -o static/img/salida.png
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src", type=Path, help="PNG de entrada (fondo oscuro)")
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument(
        "--cutoff",
        type=int,
        default=42,
        help="Si max(R,G,B) <= cutoff se considera fondo (0–255). Default 42.",
    )
    ap.add_argument(
        "--feather",
        type=int,
        default=36,
        help="Ancho de transición suave anti-alias junto al corte. Default 36.",
    )
    args = ap.parse_args()

    img = Image.open(args.src).convert("RGBA")
    px = img.load()
    w, h = img.size
    c0 = max(0, min(255, args.cutoff))
    fe = max(1, min(128, args.feather))

    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            m = max(r, g, b)
            if m <= c0:
                px[x, y] = (r, g, b, 0)
            elif m < c0 + fe:
                # Suaviza borde: fondo oscuro antialiasing
                t = (m - c0) / float(fe)
                px[x, y] = (r, g, b, int(round(a * t)))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    img.save(args.out, "PNG", optimize=True)
    print(f"Guardado: {args.out.resolve()}")


if __name__ == "__main__":
    main()
