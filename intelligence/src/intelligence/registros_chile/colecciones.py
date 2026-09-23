"""Colecciones chilenas publicadas en FamilySearch.

Los identificadores son los de las fichas públicas del portal
(https://www.familysearch.org/search/collection/<id>).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Coleccion:
    id: str
    titulo: str
    tipos: frozenset[str]
    mixta: bool
    ficha: str


COLECCIONES: tuple[Coleccion, ...] = (
    Coleccion(
        id="1520549",
        titulo="Chile, Bautismos, 1585-1932",
        tipos=frozenset({"bautismo"}),
        mixta=False,
        ficha="https://www.familysearch.org/search/collection/1520549",
    ),
    Coleccion(
        id="1520558",
        titulo="Chile, Matrimonios, 1579-1930",
        tipos=frozenset({"matrimonio"}),
        mixta=False,
        ficha="https://www.familysearch.org/search/collection/1520558",
    ),
    Coleccion(
        id="1520559",
        titulo="Chile, Defunciones, 1700-1920",
        tipos=frozenset({"defuncion"}),
        mixta=False,
        ficha="https://www.familysearch.org/search/collection/1520559",
    ),
    Coleccion(
        id="3405096",
        titulo="Chile, Catholic Church Records, 1633-2015",
        tipos=frozenset({"bautismo", "matrimonio", "defuncion"}),
        mixta=True,
        ficha="https://www.familysearch.org/search/collection/3405096",
    ),
    Coleccion(
        id="1630787",
        titulo="Chile, Registro Civil, 1885-1932",
        tipos=frozenset({"matrimonio", "defuncion"}),
        mixta=True,
        ficha="https://www.familysearch.org/search/collection/1630787",
    ),
)

_POR_ID = {coleccion.id: coleccion for coleccion in COLECCIONES}


def colecciones_para(tipo: str, solo_ids: list[str] | None = None) -> list[Coleccion]:
    if solo_ids:
        desconocidas = [item for item in solo_ids if item not in _POR_ID]
        if desconocidas:
            raise ValueError(
                "Colección desconocida: " + ", ".join(desconocidas) + ". "
                "Revisa los identificadores del portal de FamilySearch."
            )
        elegidas = [_POR_ID[item] for item in solo_ids]
    else:
        elegidas = [coleccion for coleccion in COLECCIONES if tipo in coleccion.tipos]
    incompatibles = [coleccion.id for coleccion in elegidas if tipo not in coleccion.tipos]
    if incompatibles:
        raise ValueError(
            f"La colección {', '.join(incompatibles)} no está definida para {tipo}."
        )
    return elegidas
