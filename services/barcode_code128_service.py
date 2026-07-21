"""Genera Code128 (subset B) como SVG inline para PDF/impresión."""
from __future__ import annotations

# Patrones Code128 (11 módulos: 0=espacio, 1=barra) — índices 0..106
_CODE128_PATTERNS = (
    "11011001100", "11001101100", "11001100110", "10010011000", "10010001100",
    "10001001100", "10011001000", "10011000100", "10001100100", "11001001000",
    "11001000100", "11000100100", "10110011100", "10011011100", "10011001110",
    "10111001100", "10011101100", "10011100110", "11001110010", "11001011100",
    "11001001110", "11011100100", "11001110100", "11101101110", "11101001100",
    "11100101100", "11100100110", "11101100100", "11100110100", "11100110010",
    "11011011000", "11011000110", "11000110110", "10100011000", "10001011000",
    "10001000110", "10110001000", "10001101000", "10001100010", "11010001000",
    "11000101000", "11000100010", "10110111000", "10110001110", "10001101110",
    "10111011000", "10111000110", "10001110110", "11101110110", "11010001110",
    "11000101110", "11011101000", "11011100010", "11011101110", "11101011000",
    "11101000110", "11100010110", "11101101000", "11101100010", "11100011010",
    "11101111010", "11001000010", "11110001010", "10100110000", "10100001100",
    "10010110000", "10010000110", "10000101100", "10000100110", "10110010000",
    "10110000100", "10011010000", "10011000010", "10000110100", "10000110010",
    "11000010010", "11001010000", "11110111010", "11000010100", "10001111010",
    "10100111100", "10010111100", "10010011110", "10111100100", "10011110100",
    "10011110010", "11110100100", "11110010100", "11110010010", "11011011110",
    "11011110110", "11110110110", "10101111000", "10100011110", "10001011110",
    "10111101000", "10111100010", "11110101000", "11110100010", "10111011110",
    "10111101110", "11101011110", "11110101110", "11010000100", "11010010000",
    "11010011100", "1100011101011",
)

_START_B = 104
_STOP = 106


def _code128_values(text: str) -> list[int]:
    """Codifica texto ASCII imprimible (32..126) en valores Code128B."""
    raw = (text or "").strip()
    if not raw:
        raise ValueError("texto vacío para Code128")
    values = [_START_B]
    for ch in raw:
        code = ord(ch)
        if code < 32 or code > 126:
            raise ValueError(f"carácter no soportado en Code128B: {ch!r}")
        values.append(code - 32)
    checksum = values[0]
    for i, v in enumerate(values[1:], start=1):
        checksum += i * v
    values.append(checksum % 103)
    values.append(_STOP)
    return values


def code128_svg(
    text: str,
    *,
    height: int = 48,
    module_width: float = 1.4,
    quiet_zone: int = 10,
    show_text: bool = True,
    bar_color: str = "#0f172a",
    text_color: str = "#334155",
) -> str:
    """
    SVG Code128B listo para incrustar en HTML/PDF.
    Ideal para números de cotización (COT-000123).
    """
    label = (text or "").strip()
    values = _code128_values(label)
    modules = "".join(_CODE128_PATTERNS[v] for v in values)
    bar_h = height - (16 if show_text else 0)
    total_modules = quiet_zone * 2 + len(modules)
    width = total_modules * module_width
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.1f}" height="{height}" '
        f'viewBox="0 0 {width:.1f} {height}" role="img" aria-label="{_xml_escape(label)}">'
    ]
    x = quiet_zone * module_width
    for bit in modules:
        w = module_width
        if bit == "1":
            parts.append(
                f'<rect x="{x:.2f}" y="0" width="{w:.2f}" height="{bar_h}" fill="{bar_color}"/>'
            )
        x += w
    if show_text:
        parts.append(
            f'<text x="{width / 2:.1f}" y="{height - 3}" text-anchor="middle" '
            f'font-family="Segoe UI, Arial, Helvetica, sans-serif" font-size="11" '
            f'font-weight="700" fill="{text_color}" letter-spacing="0.06em">'
            f'{_xml_escape(label)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def _xml_escape(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
