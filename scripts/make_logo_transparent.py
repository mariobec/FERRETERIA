"""Convierte un PNG con fondo simulado (patron tablero / blanco) a PNG con
transparencia real haciendo flood fill desde las esquinas.

Uso:
    python scripts/make_logo_transparent.py <input.png> <output.png> [threshold]

threshold por defecto: 80 (tolerancia de color para el flood fill).
"""
import sys
from PIL import Image, ImageDraw


def hacer_transparente(src_path: str, dst_path: str, thresh: int = 35) -> None:
    """Hace transparente solo el fondo conectado a los bordes.

    Usa flood fill desde multiples puntos del borde con threshold bajo
    para no afectar colores claros (texto blanco) ni naranjos del logo.
    """
    img = Image.open(src_path).convert("RGBA")
    w, h = img.size
    transparente = (0, 0, 0, 0)

    puntos_borde = [
        (0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1),
        (w // 4, 0), (w // 2, 0), (3 * w // 4, 0),
        (w // 4, h - 1), (w // 2, h - 1), (3 * w // 4, h - 1),
        (0, h // 4), (0, h // 2), (0, 3 * h // 4),
        (w - 1, h // 4), (w - 1, h // 2), (w - 1, 3 * h // 4),
    ]
    aplicados = 0
    for punto in puntos_borde:
        try:
            ImageDraw.floodfill(img, punto, transparente, thresh=thresh)
            aplicados += 1
        except Exception as e:
            print(f"  ! flood fill skip {punto}: {e}")
    print(f"  flood fill aplicado en {aplicados} puntos del borde (threshold={thresh})")

    # Auto-crop al bounding box del contenido visible (alpha > 0)
    bbox = img.getbbox()
    if bbox:
        # Padding pequenio para no recortar demasiado pegado
        pad = 8
        left = max(0, bbox[0] - pad)
        top = max(0, bbox[1] - pad)
        right = min(w, bbox[2] + pad)
        bottom = min(h, bbox[3] + pad)
        img = img.crop((left, top, right, bottom))
        print(f"  recortado a bbox: {bbox} -> {(left, top, right, bottom)} (final {right-left}x{bottom-top})")

    img.save(dst_path, "PNG")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    src = sys.argv[1]
    dst = sys.argv[2]
    thresh = int(sys.argv[3]) if len(sys.argv) > 3 else 80
    print(f"Procesando {src} -> {dst} (threshold={thresh})")
    hacer_transparente(src, dst, thresh)
    print("OK")
