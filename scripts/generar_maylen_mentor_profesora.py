"""Maylén Mentor Academy — lentes de profesora integrados en el cutout."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "static" / "img" / "maylen_avatar_cutout.png"
OUT = ROOT / "static" / "img" / "maylen_avatar_mentor.png"


def _add_professor_glasses(im: Image.Image) -> Image.Image:
    """Dibuja montura sobre los ojos (coords calibradas 1024×682)."""
    out = im.copy().convert("RGBA")
    draw = ImageDraw.Draw(out)
    stroke = (45, 55, 72, 245)
    glare = (255, 255, 255, 165)
    lw = max(5, im.width // 170)

    left = (318, 172, 452, 252)
    right = (568, 172, 702, 252)
    bridge_y = 212

    for box in (left, right):
        draw.rounded_rectangle(box, radius=18, outline=stroke, width=lw)
        x0, y0, x1, y1 = box
        draw.line([(x0 + 22, y0 + 16), (x0 + 38, y0 + 32)], fill=glare, width=3)

    draw.line([(452, bridge_y), (568, bridge_y)], fill=stroke, width=lw)
    draw.line([(318, bridge_y), (248, 204)], fill=stroke, width=max(3, lw - 1))
    draw.line([(702, bridge_y), (772, 204)], fill=stroke, width=max(3, lw - 1))
    return out


def main() -> None:
    if not SRC.is_file():
        raise SystemExit(f"No existe {SRC}")
    out = _add_professor_glasses(Image.open(SRC))
    out.save(OUT)
    print(f"OK → {OUT} ({out.size[0]}x{out.size[1]})")


if __name__ == "__main__":
    main()
