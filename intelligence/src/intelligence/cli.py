"""Línea de comandos del extractor de registros chilenos."""

from __future__ import annotations

import argparse
import os
import sys
import webbrowser
from pathlib import Path

from intelligence.registros_chile.auth import (
    code_challenge,
    esperar_codigo,
    guardar_token,
    leer_token,
    nuevo_verifier,
    pedir_token,
    redirect_uri,
    url_autorizacion,
)
from intelligence.registros_chile.buscar import ejecutar
from intelligence.registros_chile.cliente import Cliente, ErrorFamilySearch
from intelligence.registros_chile.consulta import Consulta, partir_nombre
from intelligence.registros_chile.exportar import escribir


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        return args.funcion(args)
    except (ErrorFamilySearch, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="registros.py",
        description=(
            "Busca bautismos, matrimonios y defunciones de Chile en FamilySearch "
            "y los exporta a CSV o JSON. Trabajo aparte del ERP."
        ),
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    login = sub.add_parser("login", help="Abre FamilySearch en el navegador y guarda la sesión.")
    login.add_argument("--client-id", default="", help="App key de https://www.familysearch.org/developers/")
    login.add_argument("--puerto", type=int, default=8765, help="Puerto local del retorno OAuth.")
    login.set_defaults(funcion=cmd_login)

    buscar = sub.add_parser("buscar", help="Consulta una colección y escribe el resultado.")
    buscar.add_argument("--tipo", required=True, choices=("bautismo", "matrimonio", "defuncion"))
    buscar.add_argument("--nombre", default="")
    buscar.add_argument("--apellido", default="")
    buscar.add_argument("--lugar", default="Chile")
    buscar.add_argument("--desde", type=int, default=None, help="Año inicial, inclusive.")
    buscar.add_argument("--hasta", type=int, default=None, help="Año final, inclusive.")
    buscar.add_argument("--sexo", default="", choices=("", "masculino", "femenino"))
    buscar.add_argument("--padre", default="", help="Nombre y apellido del padre, si los conoces.")
    buscar.add_argument("--madre", default="")
    buscar.add_argument("--conyuge", default="", help="Nombre y apellido del cónyuge.")
    buscar.add_argument("--coleccion", action="append", default=None, help="Id de colección. Se puede repetir.")
    buscar.add_argument("--max", type=int, default=100, help="Tope de filas. Máximo de la API: 5000.")
    buscar.add_argument("--por-pagina", type=int, default=20)
    buscar.add_argument("--pausa", type=float, default=0.8, help="Segundos entre páginas.")
    buscar.add_argument("--salida", default="", help="Ruta .csv o .json. Por defecto, intelligence/salidas/.")
    buscar.add_argument("--formato", default="", choices=("", "csv", "json"))
    buscar.add_argument("--token", default="", help="Token ya obtenido. Si falta, usa la sesión guardada.")
    buscar.set_defaults(funcion=cmd_buscar)

    colecciones = sub.add_parser("colecciones", help="Lista las colecciones chilenas que consulta la herramienta.")
    colecciones.set_defaults(funcion=cmd_colecciones)
    return parser


def cmd_login(args: argparse.Namespace) -> int:
    client_id = (args.client_id or os.environ.get("FAMILYSEARCH_CLIENT_ID") or "").strip()
    if not client_id:
        print(
            "Falta la app key. Créala en https://www.familysearch.org/developers/ "
            "y pásala con --client-id o con FAMILYSEARCH_CLIENT_ID.",
            file=sys.stderr,
        )
        return 2
    if not 1024 < args.puerto < 65536:
        print("El puerto debe estar entre 1025 y 65535.", file=sys.stderr)
        return 2
    retorno = redirect_uri(args.puerto)
    verifier = nuevo_verifier()
    state = nuevo_verifier()
    enlace = url_autorizacion(client_id, retorno, state, code_challenge(verifier))
    print("Registra esta redirect URI en la app key, si todavía no está:")
    print(retorno)
    print("Abriendo FamilySearch en el navegador. La contraseña no pasa por esta herramienta.")
    print(enlace)
    webbrowser.open(enlace)
    code = esperar_codigo(args.puerto, state)
    data = pedir_token(client_id, retorno, code, verifier)
    destino = guardar_token(data)
    print(f"Sesión guardada en {destino}")
    return 0


def cmd_buscar(args: argparse.Namespace) -> int:
    padre_nombre, padre_apellido = partir_nombre(args.padre)
    madre_nombre, madre_apellido = partir_nombre(args.madre)
    conyuge_nombre, conyuge_apellido = partir_nombre(args.conyuge)
    sexo = {"masculino": "Male", "femenino": "Female"}.get(args.sexo, "")
    consulta = Consulta(
        tipo=args.tipo,
        nombre=args.nombre,
        apellido=args.apellido,
        lugar=args.lugar,
        desde=args.desde,
        hasta=args.hasta,
        sexo=sexo,
        padre_nombre=padre_nombre,
        padre_apellido=padre_apellido,
        madre_nombre=madre_nombre,
        madre_apellido=madre_apellido,
        conyuge_nombre=conyuge_nombre,
        conyuge_apellido=conyuge_apellido,
    )
    consulta.validar()
    token = (args.token or leer_token()).strip()
    cliente = Cliente(token)
    registros = ejecutar(
        cliente,
        consulta,
        max_resultados=args.max,
        por_pagina=args.por_pagina,
        pausa=args.pausa,
        coleccion_ids=args.coleccion,
    )
    destino = Path(args.salida) if args.salida else _salida_por_defecto(args.tipo, args.formato or "csv")
    escribir(registros, destino, args.formato or None)
    print(f"{len(registros)} registros en {destino}")
    return 0


def cmd_colecciones(_args: argparse.Namespace) -> int:
    from intelligence.registros_chile.colecciones import COLECCIONES

    for coleccion in COLECCIONES:
        tipos = ", ".join(sorted(coleccion.tipos))
        print(f"{coleccion.id}\t{tipos}\t{coleccion.titulo}")
        print(f"  {coleccion.ficha}")
    return 0


def _salida_por_defecto(tipo: str, formato: str) -> Path:
    raiz = Path(__file__).resolve().parents[2]
    return raiz / "salidas" / f"{tipo}.{formato}"
