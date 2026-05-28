#!/usr/bin/env python3
"""Diagnóstico Liz / Ollama vitrina (local o variables VITRINA_OLLAMA_* como Render)."""
from __future__ import annotations

import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def main() -> int:
    from services.ollama_client import generar_chat_vitrina, vitrina_ollama_status

    st = vitrina_ollama_status()
    print(json.dumps(st, indent=2, ensure_ascii=False))
    if not st.get('habilitado'):
        print("\n→ Active VITRINA_OLLAMA_ENABLED=1 y VITRINA_OLLAMA_BASE_URL (túnel).")
        return 1
    if not st.get('disponible'):
        print("\n→ Ollama no responde en esa URL. Revise túnel y modelo.")
        return 1
    chat = generar_chat_vitrina(
        system='Respondes en una sola frase en español.',
        user='Di solo: Liz OK',
    )
    if chat.get('ok'):
        print(f"\nChat prueba: {(chat.get('texto') or '')[:200]}")
        return 0
    print(f"\nChat falló: {chat.get('error')}")
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
