"""Recorre las colecciones chilenas y devuelve registros ya normalizados."""

from __future__ import annotations

from intelligence.registros_chile.colecciones import colecciones_para
from intelligence.registros_chile.consulta import Consulta, parametros
from intelligence.registros_chile.parser import Registro, interpretar


def ejecutar(
    cliente,
    consulta: Consulta,
    *,
    max_resultados: int = 100,
    por_pagina: int = 20,
    pausa: float = 0.8,
    coleccion_ids: list[str] | None = None,
    dormir=None,
) -> list[Registro]:
    consulta.validar()
    por_pagina = max(1, min(100, por_pagina))
    max_resultados = max(1, min(5000, max_resultados))
    pausa = max(0.0, pausa)
    esperar = dormir or _dormir
    vistos: set[tuple[str, str, str, str, str]] = set()
    salida: list[Registro] = []

    for coleccion in colecciones_para(consulta.tipo, coleccion_ids):
        offset = 0
        while len(salida) < max_resultados and offset < 4999:
            count = min(por_pagina, max_resultados - len(salida), 4999 - offset)
            if count <= 0:
                break
            pagina = cliente.buscar_pagina(parametros(consulta, coleccion.id, count, offset))
            entradas = pagina.get("entries") or []
            if not entradas:
                break
            for entrada in entradas:
                registro = interpretar(
                    entrada,
                    consulta.tipo,
                    coleccion.id,
                    coleccion.titulo,
                    coleccion.mixta,
                )
                if registro is None:
                    continue
                clave = (registro.enlace, registro.tipo, registro.nombre, registro.fecha, registro.lugar)
                if clave in vistos:
                    continue
                vistos.add(clave)
                salida.append(registro)
                if len(salida) >= max_resultados:
                    break
            total = pagina.get("results")
            offset += len(entradas)
            if isinstance(total, int) and offset >= total:
                break
            if len(entradas) < count:
                break
            if len(salida) < max_resultados:
                esperar(pausa)
    return salida


def _dormir(segundos: float) -> None:
    import time

    time.sleep(segundos)
