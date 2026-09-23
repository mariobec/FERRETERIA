"""Pasa una entrada GEDCOM X Atom a una fila de registro civil o parroquial."""

from __future__ import annotations

from dataclasses import asdict, dataclass

HECHOS_POR_TIPO = {
    "bautismo": ("Baptism", "Christening"),
    "matrimonio": ("Marriage",),
    "defuncion": ("Death", "Burial"),
}

TITULOS_POR_TIPO = {
    "bautismo": ("bautis", "christen"),
    "matrimonio": ("matrimon", "marriage", "casamiento"),
    "defuncion": ("defun", "death", "burial", "sepel", "entierro", "fallec"),
}


@dataclass
class Registro:
    tipo: str
    coleccion_id: str
    coleccion: str
    persona_id: str
    nombre: str
    sexo: str
    fecha: str
    fecha_formal: str
    lugar: str
    padre: str
    madre: str
    conyuge: str
    puntaje: str
    enlace: str
    titulo: str

    def fila(self) -> dict[str, str]:
        return asdict(self)


COLUMNAS = list(Registro.__dataclass_fields__)


def interpretar(
    entry: dict,
    tipo: str,
    coleccion_id: str,
    coleccion_titulo: str,
    mixta: bool,
) -> Registro | None:
    if not isinstance(entry, dict):
        return None
    gx = gedcomx_de(entry)
    if mixta and not _aceptar_mixta(gx, entry, tipo):
        return None

    persons = _personas(gx)
    person = _principal(persons)
    hecho = _elegir_hecho(_hechos(gx, person), tipo)
    fecha, formal, lugar = _fecha_lugar(hecho)
    persona_id = str(person.get("id") or entry.get("id") or "")
    padre, madre = _padres(gx, person.get("id"), persons)
    puntaje = entry.get("score")
    return Registro(
        tipo=tipo,
        coleccion_id=coleccion_id,
        coleccion=coleccion_titulo,
        persona_id=persona_id,
        nombre=nombre_de(person),
        sexo=sexo_de(person),
        fecha=fecha,
        fecha_formal=formal,
        lugar=lugar,
        padre=padre,
        madre=madre,
        conyuge=_conyuges(gx, person.get("id"), persons),
        puntaje="" if puntaje is None else str(puntaje),
        enlace=enlace_de(entry, person, gx),
        titulo=_titulo(entry, gx),
    )


def gedcomx_de(entry: dict) -> dict:
    content = entry.get("content") or {}
    if isinstance(content, dict) and isinstance(content.get("gedcomx"), dict):
        return content["gedcomx"]
    if isinstance(content, dict) and "persons" in content:
        return content
    return {}


def nombre_de(person: dict) -> str:
    for name in person.get("names") or []:
        if not isinstance(name, dict):
            continue
        for form in name.get("nameForms") or []:
            if not isinstance(form, dict):
                continue
            completo = str(form.get("fullText") or "").strip()
            if completo:
                return completo
            partes = [
                str(parte.get("value") or "").strip()
                for parte in (form.get("parts") or [])
                if isinstance(parte, dict)
            ]
            unido = " ".join(parte for parte in partes if parte)
            if unido:
                return unido
    display = person.get("display") or {}
    if isinstance(display, dict):
        return str(display.get("name") or "").strip()
    return ""


def sexo_de(person: dict) -> str:
    tipo = str((person.get("gender") or {}).get("type") or "")
    if tipo.endswith("Female"):
        return "femenino"
    if tipo.endswith("Male"):
        return "masculino"
    return ""


def _personas(gx: dict) -> list[dict]:
    return [person for person in (gx.get("persons") or []) if isinstance(person, dict)]


def _principal(persons: list[dict]) -> dict:
    for person in persons:
        if person.get("principal") is True:
            return person
    return persons[0] if persons else {}


def _sufijo(uri: str) -> str:
    return str(uri or "").rstrip("/").rsplit("/", 1)[-1]


def _hechos(gx: dict, person: dict) -> list[dict]:
    encontrados: list[dict] = []
    for fact in person.get("facts") or []:
        if isinstance(fact, dict):
            encontrados.append(fact)
    persona_id = person.get("id")
    for relacion in gx.get("relationships") or []:
        if not isinstance(relacion, dict):
            continue
        participantes = {
            (relacion.get("person1") or {}).get("resourceId"),
            (relacion.get("person2") or {}).get("resourceId"),
        }
        if persona_id and persona_id not in participantes:
            continue
        for fact in relacion.get("facts") or []:
            if isinstance(fact, dict):
                encontrados.append(fact)
    return encontrados


def _elegir_hecho(hechos: list[dict], tipo: str) -> dict:
    preferidos = HECHOS_POR_TIPO[tipo]
    for nombre in preferidos:
        for hecho in hechos:
            if _sufijo(str(hecho.get("type") or "")) == nombre:
                return hecho
    return hechos[0] if hechos else {}


def _fecha_lugar(hecho: dict) -> tuple[str, str, str]:
    fecha = hecho.get("date") if isinstance(hecho.get("date"), dict) else {}
    lugar = hecho.get("place") if isinstance(hecho.get("place"), dict) else {}
    original = str(fecha.get("original") or "").strip()
    formal = str(fecha.get("formal") or "").strip()
    texto_lugar = str(lugar.get("original") or "").strip()
    return original or formal, formal, texto_lugar


def _padres(gx: dict, principal_id: str | None, persons: list[dict]) -> tuple[str, str]:
    por_id = {person.get("id"): person for person in persons if person.get("id")}
    padres: list[str] = []
    madres: list[str] = []
    sin_sexo: list[str] = []
    for relacion in gx.get("relationships") or []:
        if not isinstance(relacion, dict) or _sufijo(str(relacion.get("type") or "")) != "ParentChild":
            continue
        padre_id = (relacion.get("person1") or {}).get("resourceId")
        hijo_id = (relacion.get("person2") or {}).get("resourceId")
        if principal_id and hijo_id != principal_id:
            continue
        nombre = nombre_de(por_id.get(padre_id) or {})
        if not nombre:
            continue
        sexo = sexo_de(por_id.get(padre_id) or {})
        if sexo == "masculino":
            padres.append(nombre)
        elif sexo == "femenino":
            madres.append(nombre)
        else:
            sin_sexo.append(nombre)
    if not padres and sin_sexo:
        padres.append(sin_sexo.pop(0))
    if not madres and sin_sexo:
        madres.append(sin_sexo.pop(0))
    return " | ".join(padres), " | ".join(madres)


def _conyuges(gx: dict, principal_id: str | None, persons: list[dict]) -> str:
    por_id = {person.get("id"): person for person in persons if person.get("id")}
    nombres: list[str] = []
    for relacion in gx.get("relationships") or []:
        if not isinstance(relacion, dict) or _sufijo(str(relacion.get("type") or "")) != "Couple":
            continue
        ids = [
            (relacion.get("person1") or {}).get("resourceId"),
            (relacion.get("person2") or {}).get("resourceId"),
        ]
        if principal_id and principal_id not in ids:
            continue
        for persona_id in ids:
            if persona_id == principal_id:
                continue
            nombre = nombre_de(por_id.get(persona_id) or {})
            if nombre:
                nombres.append(nombre)
    return " | ".join(nombres)


def _titulo(entry: dict, gx: dict) -> str:
    for fuente in gx.get("sourceDescriptions") or []:
        if not isinstance(fuente, dict):
            continue
        for titulo in fuente.get("titles") or []:
            if isinstance(titulo, dict) and str(titulo.get("value") or "").strip():
                return str(titulo["value"]).strip()
            if isinstance(titulo, str) and titulo.strip():
                return titulo.strip()
    return str(entry.get("title") or "").strip()


def enlace_de(entry: dict, person: dict, gx: dict) -> str:
    identificadores = (person.get("identifiers") or {}).get("http://gedcomx.org/Persistent") or []
    for item in identificadores:
        if isinstance(item, str) and item.startswith("http"):
            return item
    for fuente in gx.get("sourceDescriptions") or []:
        if isinstance(fuente, dict):
            about = str(fuente.get("about") or "")
            if about.startswith("http"):
                return about
    links = entry.get("links") or {}
    for clave in ("persona", "record", "self"):
        href = str((links.get(clave) or {}).get("href") or "")
        if href.startswith("http"):
            return href
    return ""


def _aceptar_mixta(gx: dict, entry: dict, tipo: str) -> bool:
    person = _principal(_personas(gx))
    hechos = _hechos(gx, person)
    preferidos = set(HECHOS_POR_TIPO[tipo])
    if any(_sufijo(str(hecho.get("type") or "")) in preferidos for hecho in hechos):
        return True
    texto = f"{_titulo(entry, gx)} {entry.get('title') or ''}".lower()
    if any(pista in texto for pista in TITULOS_POR_TIPO[tipo]):
        return True
    return not hechos
