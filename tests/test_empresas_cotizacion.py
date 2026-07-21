"""Perfiles multi-empresa para cotizaciones."""
from types import SimpleNamespace

from services.empresas_cotizacion_service import (
    aplicar_marker_empresa_notas,
    extraer_empresa_slug_cot,
    listar_empresas_cotizacion,
    normalizar_empresa_cotizacion_id,
    notas_cotizacion_visibles,
    resolver_empresa_cotizacion,
    resolver_empresa_cotizacion_cot,
)


def test_listar_incluye_transportes(app_ctx):
    ids = {e["id"] for e in listar_empresas_cotizacion()}
    assert "santo-domingo" in ids
    assert "transportes-st-julliet" in ids


def test_resolver_transportes(app_ctx):
    emp = resolver_empresa_cotizacion("transportes-st-julliet")
    assert emp["plantilla"] == "transportes"
    assert emp["razon_social"] == "JULIO IVAN RIVERA PEREZ EIRL"
    assert emp["rut_emisor"] == "76.873.527-1"
    assert "51270010532" in (emp.get("cuenta_banco") or "")


def test_normalizar_slug_invalido(app_ctx):
    assert normalizar_empresa_cotizacion_id("no-existe") == "santo-domingo"


def test_marker_notas_resuelve_transportes(app_ctx):
    cot = SimpleNamespace(
        empresa_cotizacion=None,
        notas="[[empresa_cot:transportes-st-julliet]]\nPlazo 15 dias",
    )
    assert extraer_empresa_slug_cot(cot) == "transportes-st-julliet"
    emp = resolver_empresa_cotizacion_cot(cot)
    assert emp["plantilla"] == "transportes"
    assert notas_cotizacion_visibles(cot.notas) == "Plazo 15 dias"


def test_marker_notas_gana_sobre_columna_chilemat(app_ctx):
    """Si el marker dice Transportes, no usar Chilemat aunque la columna diga otra cosa."""
    cot = SimpleNamespace(
        empresa_cotizacion="santo-domingo",
        notas="[[empresa_cot:transportes-st-julliet]]\nNota",
    )
    assert extraer_empresa_slug_cot(cot) == "transportes-st-julliet"
    emp = resolver_empresa_cotizacion_cot(cot)
    assert emp["plantilla"] == "transportes"
    assert emp["razon_social"] == "JULIO IVAN RIVERA PEREZ EIRL"
