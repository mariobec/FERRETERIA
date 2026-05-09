"""Recorta un PNG RGBA al bounding box del canal alpha (quita márgenes transparentes)."""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src", type=Path)
    ap.add_argument("-o", "--out", type=Path, help="Si se omite, sobrescribe src")
    ap.add_argument(
        "--pad",
        type=int,
        default=4,
        help="Padding en px alrededor del contenido (default 4)",
    )
    args = ap.parse_args()
    out = args.out or args.src

    im = Image.open(args.src).convert("RGBA")
    alpha = im.split()[-1]
    bbox = alpha.getbbox()
    if not bbox:
        raise SystemExit("Sin píxeles opacos: bbox vacío")

    x0, y0, x1, y1 = bbox
    p = max(0, args.pad)
    w, h = im.size
    x0 = max(0, x0 - p)
    y0 = max(0, y0 - p)
    x1 = min(w, x1 + p)
    y1 = min(h, y1 + p)

    cropped = im.crop((x0, y0, x1, y1))
    out.parent.mkdir(parents=True, exist_ok=True)
    cropped.save(out, "PNG", optimize=True)
    print(f"{args.src} -> {out}  ({im.size} -> {cropped.size})")


if __name__ == "__main__":
    main()
