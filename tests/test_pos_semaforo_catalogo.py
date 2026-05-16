"""Coherencia del catálogo pruebas/pos_semaforo/productos.json (sin BD)."""
from __future__ import annotations

import json
from pathlib import Path

from services.pos_busqueda_service import clasificar_semaforo

ROOT = Path(__file__).resolve().parents[1]
CATALOGO = ROOT / "pruebas" / "pos_semaforo" / "productos.json"


def _items():
    data = json.loads(CATALOGO.read_text(encoding="utf-8"))
    return data.get("items") or []


def test_catalogo_existe_y_tiene_ocho_casos():
    assert CATALOGO.is_file()
    items = _items()
    assert len(items) >= 8
    codigos = {it["codigo_barra"] for it in items}
    assert "POS-SEM-V1" in codigos
    assert "POS-SEM-Z1" in codigos


def test_semaforo_esperado_coincide_con_stock():
    for it in _items():
        st_t = int(it.get("stock_tienda") or 0)
        st_b = int(it.get("stock_bodega") or 0)
        esperado = str(it.get("semaforo_esperado") or "").lower()
        assert clasificar_semaforo(st_t, st_b) == esperado, it.get("codigo_barra")
