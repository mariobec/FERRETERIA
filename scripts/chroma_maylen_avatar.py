"""Recorta verde croma de maylen_avatar.png → maylen_avatar_cutout.png."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "static" / "img" / "maylen_avatar.png"
OUT = ROOT / "static" / "img" / "maylen_avatar_cutout.png"


def chroma_key_green(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if g > 100 and g > r + 25 and g > b + 25:
                px[x, y] = (r, g, b, 0)
            elif g > 80 and g > r + 15 and g > b + 15 and r < 120:
                px[x, y] = (r, g, b, min(a, 80))
    return im


def main() -> None:
    if not SRC.is_file():
        raise SystemExit(f"No existe {SRC}")
    out = chroma_key_green(Image.open(SRC))
    out.save(OUT)
    print(f"OK → {OUT} ({out.size[0]}x{out.size[1]})")


if __name__ == "__main__":
    main()
