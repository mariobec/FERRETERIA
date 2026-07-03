"""
Genera GIF animado de Maylén saludando (breathing + gesto de saludo + asentir).

Uso:
  python scripts/generar_maylen_saludo_gif.py

Salida:
  static/img/maylen_saludo.gif
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "static" / "img" / "maylen_avatar_cutout.png"
OUT = ROOT / "static" / "img" / "maylen_saludo.gif"

# Tamaño final del GIF (ancho; alto proporcional)
TARGET_W = 320
FPS = 12
DURATION_MS = int(1000 / FPS)


def load_base() -> Image.Image:
    if not SRC.is_file():
        raise SystemExit(f"No existe {SRC}")
    im = Image.open(SRC).convert("RGBA")
    ratio = TARGET_W / im.width
    target_h = int(im.height * ratio)
    return im.resize((TARGET_W, target_h), Image.LANCZOS)


def paste_centered(canvas: Image.Image, sprite: Image.Image, ox: int = 0, oy: int = 0) -> Image.Image:
    out = canvas.copy()
    cw, ch = canvas.size
    sw, sh = sprite.size
    x = (cw - sw) // 2 + ox
    y = ch - sh + oy
    out.alpha_composite(sprite, (x, y))
    return out


def rotate_around_bottom(im: Image.Image, degrees: float) -> Image.Image:
    w, h = im.size
    return im.rotate(degrees, resample=Image.BICUBIC, center=(w // 2, h - 8), expand=False)


def scale_from_bottom(im: Image.Image, scale: float) -> Image.Image:
    w, h = im.size
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    scaled = im.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    x = (w - nw) // 2
    y = h - nh
    canvas.alpha_composite(scaled, (x, y))
    return canvas


def fade_in(im: Image.Image, alpha: float) -> Image.Image:
    out = im.copy()
    r, g, b, a = out.split()
    a = a.point(lambda p: int(p * max(0.0, min(1.0, alpha))))
    out.putalpha(a)
    return out


def build_frames(base: Image.Image) -> list[Image.Image]:
    w, h = base.size
    canvas_h = h + 24
    canvas = Image.new("RGBA", (w, canvas_h), (0, 0, 0, 0))
    frames: list[Image.Image] = []

    # 1) Entrada: sube + fade (18 frames)
    for i in range(18):
        t = i / 17
        ease = 1 - (1 - t) ** 3
        oy = int(28 * (1 - ease))
        alpha = 0.15 + 0.85 * ease
        sprite = fade_in(base, alpha)
        frames.append(paste_centered(canvas, sprite, oy=oy))

    # 2) Saludo: balanceo mano — 24 frames (más marcado)
    for i in range(24):
        t = i / 23
        wave = math.sin(t * math.pi * 3.5) * 11.0
        bounce = abs(math.sin(t * math.pi * 3.5)) * 8
        sprite = rotate_around_bottom(base, wave)
        sprite = scale_from_bottom(sprite, 1.0 + bounce * 0.006)
        frames.append(paste_centered(canvas, sprite, oy=-int(bounce)))

    # 3) Respiración idle — 16 frames
    for i in range(16):
        t = i / 15
        breath = math.sin(t * 2 * math.pi) * 0.018
        sprite = scale_from_bottom(base, 1.0 + breath)
        frames.append(paste_centered(canvas, sprite))

    # 4) Asentir (sí) — 14 frames
    for i in range(14):
        t = i / 13
        nod = math.sin(t * math.pi) * 7
        squash = 1.0 - abs(math.sin(t * math.pi)) * 0.025
        sprite = scale_from_bottom(base, squash)
        frames.append(paste_centered(canvas, sprite, oy=int(nod)))

    # 5) Guiño amistoso: inclinación lateral — 16 frames
    for i in range(16):
        t = i / 15
        tilt = math.sin(t * 2 * math.pi) * 3.2
        sprite = rotate_around_bottom(base, tilt)
        frames.append(paste_centered(canvas, sprite))

    # 6) Despedida mini-bounce — 12 frames
    for i in range(12):
        t = i / 11
        bounce = math.sin(t * math.pi) * 10
        sprite = scale_from_bottom(base, 1.0 + 0.02 * math.sin(t * math.pi))
        frames.append(paste_centered(canvas, sprite, oy=-int(bounce)))

    return frames


def save_gif(frames: list[Image.Image]) -> None:
    if not frames:
        raise SystemExit("Sin frames")
    # Paleta global para que el navegador interpole bien entre frames
    sample = Image.new("RGBA", frames[0].size, (0, 0, 0, 0))
    for fr in frames[::4]:
        sample.alpha_composite(fr)
    palette_ref = sample.convert("RGB").quantize(colors=128, method=Image.MEDIANCUT)

    rgb_frames = []
    for fr in frames:
        bg = Image.new("RGBA", fr.size, (0, 0, 0, 0))
        bg.alpha_composite(fr)
        q = bg.convert("RGB").quantize(palette=palette_ref)
        rgb_frames.append(q)

    rgb_frames[0].save(
        OUT,
        save_all=True,
        append_images=rgb_frames[1:],
        duration=DURATION_MS,
        loop=0,
        disposal=2,
        optimize=False,
    )


def main() -> None:
    base = load_base()
    frames = build_frames(base)
    save_gif(frames)
    print(f"OK {OUT} ({len(frames)} frames, {TARGET_W}px)")


if __name__ == "__main__":
    main()
