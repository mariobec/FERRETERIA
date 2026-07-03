"""Exporta el manual KB JSON a Markdown legible para operadores."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KB_PATH = ROOT / 'data' / 'mentor' / 'manual_operacion_ollama.json'
OUT_PATH = ROOT / 'docs' / 'mentor' / 'MANUAL_OPERACION_OLLAMA.md'


def main() -> None:
    kb = json.loads(KB_PATH.read_text(encoding='utf-8'))
    lines: list[str] = [
        '# Manual operativo LhexIA — base Ollama / Mentor Coach',
        '',
        f'> Versión KB: **{kb.get("version", "")}** · Producto: {kb.get("producto", "")}',
        '',
        'Documento fuente para **Ollama** y el **Mentor Coach** en `/academy`.',
        'No editar el Markdown a mano: regenerar con `python scripts/export_mentor_kb_md.py`.',
        '',
        '---',
        '',
        '## Invariantes de negocio',
        '',
    ]
    for inv in kb.get('invariantes') or []:
        lines.append(f'- **{inv.get("id", "")}:** {inv.get("texto", "")}')
    lines.extend(['', '---', '', '## Procedimientos por módulo', ''])
    for mod in kb.get('modulos') or []:
        lines.append(f'### {mod.get("nombre", "")} (`{mod.get("id", "")}`)')
        lines.append(f'- Ruta base: `{mod.get("ruta", "")}`')
        lines.append('')
        for proc in mod.get('procedimientos') or []:
            lines.append(f'#### {proc.get("titulo", "")}')
            for i, paso in enumerate(proc.get('pasos') or [], 1):
                lines.append(f'{i}. {paso}')
            if proc.get('errores_comunes'):
                lines.append('')
                lines.append('**Errores frecuentes:**')
                for err in proc['errores_comunes']:
                    lines.append(f'- {err}')
            lines.append('')
    lines.extend(['---', '', '## Preguntas y respuestas (FAQ)', ''])
    for faq in kb.get('faq') or []:
        lines.append(f'### {faq.get("pregunta", "")}')
        lines.append(f'- **Módulo:** {faq.get("modulo", "")} · **Ruta:** `{faq.get("ruta", "")}`')
        lines.append('')
        lines.append(faq.get('respuesta', ''))
        lines.append('')
        if faq.get('pasos'):
            lines.append('**Pasos:**')
            for i, p in enumerate(faq['pasos'], 1):
                lines.append(f'{i}. {p}')
            lines.append('')
        if faq.get('variantes'):
            lines.append(f'*También preguntan:* {", ".join(faq["variantes"][:8])}')
            lines.append('')
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text('\n'.join(lines), encoding='utf-8')
    print(f'OK -> {OUT_PATH} ({len(lines)} lineas)')


if __name__ == '__main__':
    main()
