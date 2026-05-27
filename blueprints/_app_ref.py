"""Referencia al módulo principal sin `from app import` (evita re-ejecución parcial de app.py en carga circular)."""
import sys


def app_module():
    m = sys.modules.get('app')
    if m is not None and getattr(m, 'app', None) is not None:
        return m
    main = sys.modules.get('__main__')
    if main is not None and getattr(main, 'app', None) is not None:
        return main
    return m or main
