"""Arma los parámetros de búsqueda de la API de registros históricos."""

from __future__ import annotations

from dataclasses import dataclass

TIPOS = ("bautismo", "matrimonio", "defuncion")


@dataclass(frozen=True)
class Consulta:
    tipo: str
    nombre: str = ""
    apellido: str = ""
    lugar: str = "Chile"
    desde: int | None = None
    hasta: int | None = None
    sexo: str = ""
    padre_nombre: str = ""
    padre_apellido: str = ""
    madre_nombre: str = ""
    madre_apellido: str = ""
    conyuge_nombre: str = ""
    conyuge_apellido: str = ""

    def validar(self) -> None:
        if self.tipo not in TIPOS:
            raise ValueError("El tipo debe ser bautismo, matrimonio o defuncion.")
        if not self.nombre.strip() and not self.apellido.strip():
            raise ValueError("Indica al menos el nombre o el apellido.")
        if self.desde is not None and not 1500 <= self.desde <= 2100:
            raise ValueError("El año desde está fuera de rango.")
        if self.hasta is not None and not 1500 <= self.hasta <= 2100:
            raise ValueError("El año hasta está fuera de rango.")
        if self.desde is not None and self.hasta is not None and self.desde > self.hasta:
            raise ValueError("El año desde es posterior al año hasta.")
        if self.sexo and self.sexo not in {"Male", "Female"}:
            raise ValueError("El sexo debe ser Male o Female.")


def partir_nombre(texto: str) -> tuple[str, str]:
    """Separa 'Pedro Soto' en nombre y apellido. Un solo token queda como apellido."""
    partes = [parte for parte in (texto or "").split() if parte]
    if not partes:
        return "", ""
    if len(partes) == 1:
        return "", partes[0]
    return " ".join(partes[:-1]), partes[-1]


def parametros(consulta: Consulta, coleccion_id: str, count: int, offset: int) -> list[tuple[str, str]]:
    consulta.validar()
    pares: list[tuple[str, str]] = []

    def agregar(clave: str, valor: str) -> None:
        texto = (valor or "").strip()
        if texto:
            pares.append((clave, texto))

    agregar("q.givenName", consulta.nombre)
    agregar("q.surname", consulta.apellido)
    agregar("q.sex", consulta.sexo)
    agregar("q.fatherGivenName", consulta.padre_nombre)
    agregar("q.fatherSurname", consulta.padre_apellido)
    agregar("q.motherGivenName", consulta.madre_nombre)
    agregar("q.motherSurname", consulta.madre_apellido)

    if consulta.tipo == "bautismo":
        agregar("q.birthLikePlace", consulta.lugar)
        _rango(pares, "q.birthLikeDate", consulta.desde, consulta.hasta)
    elif consulta.tipo == "matrimonio":
        agregar("q.marriageLikePlace", consulta.lugar)
        _rango(pares, "q.marriageLikeDate", consulta.desde, consulta.hasta)
        agregar("q.spouseGivenName", consulta.conyuge_nombre)
        agregar("q.spouseSurname", consulta.conyuge_apellido)
    else:
        agregar("q.deathLikePlace", consulta.lugar)
        _rango(pares, "q.deathLikeDate", consulta.desde, consulta.hasta)

    pares.append(("f.collectionId", coleccion_id))
    pares.append(("count", str(count)))
    pares.append(("offset", str(offset)))
    return pares


def _rango(pares: list[tuple[str, str]], clave: str, desde: int | None, hasta: int | None) -> None:
    if desde is not None:
        pares.append((f"{clave}.from", f"+{desde}"))
    if hasta is not None:
        pares.append((f"{clave}.to", f"+{hasta}"))
