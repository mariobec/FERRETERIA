"""Referencia al módulo principal sin `from app import` (evita re-ejecución parcial de app.py en carga circular)."""
import sys


def app_module():
    m = sys.modules.get('app')
    if m is not None:
        return m
    return sys.modules.get('__main__')
