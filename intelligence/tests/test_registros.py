import _bootstrap  # noqa: F401

import json
import os
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from intelligence.cli import main
from intelligence.registros_chile.auth import code_challenge, guardar_token, leer_token, url_autorizacion
from intelligence.registros_chile.buscar import ejecutar
from intelligence.registros_chile.cliente import Cliente, ErrorFamilySearch
from intelligence.registros_chile.colecciones import colecciones_para
from intelligence.registros_chile.consulta import Consulta, parametros, partir_nombre
from intelligence.registros_chile.exportar import escribir
from intelligence.registros_chile.parser import interpretar


def _persona(persona_id, nombre, sexo, hecho, principal=False):
    return {
        "id": persona_id,
        "principal": principal,
        "gender": {"type": f"http://gedcomx.org/{sexo}"} if sexo else {},
        "names": [{"nameForms": [{"fullText": nombre}]}],
        "facts": [hecho] if hecho else [],
    }


def _entrada(persons, relationships, titulo="Chile, Bautismos, 1585-1932", score=0.9, ark="https://www.familysearch.org/ark:/61903/1:1:TEST-1"):
    if persons:
        persons[0].setdefault("identifiers", {"http://gedcomx.org/Persistent": [ark]})
    return {
        "id": "entrada",
        "score": score,
        "title": titulo,
        "content": {
            "gedcomx": {
                "persons": persons,
                "relationships": relationships,
                "sourceDescriptions": [{"titles": [{"value": titulo}], "about": ark}],
            }
        },
    }


class ParserTests(unittest.TestCase):
    def test_bautismo_con_padres(self):
        hecho = {
            "type": "http://gedcomx.org/Christening",
            "date": {"original": "12 de marzo de 1894", "formal": "+1894-03-12"},
            "place": {"original": "Santiago, Chile"},
        }
        entrada = _entrada(
            [
                _persona("hijo", "Juan Pérez", "Male", hecho, principal=True),
                _persona("padre", "Pedro Pérez", "Male", None),
                _persona("madre", "Ana Soto", "Female", None),
            ],
            [
                {"type": "http://gedcomx.org/ParentChild", "person1": {"resourceId": "padre"}, "person2": {"resourceId": "hijo"}},
                {"type": "http://gedcomx.org/ParentChild", "person1": {"resourceId": "madre"}, "person2": {"resourceId": "hijo"}},
            ],
        )
        registro = interpretar(entrada, "bautismo", "1520549", "Chile, Bautismos, 1585-1932", False)
        self.assertEqual(registro.nombre, "Juan Pérez")
        self.assertEqual(registro.sexo, "masculino")
        self.assertEqual(registro.fecha, "12 de marzo de 1894")
        self.assertEqual(registro.fecha_formal, "+1894-03-12")
        self.assertEqual(registro.lugar, "Santiago, Chile")
        self.assertEqual(registro.padre, "Pedro Pérez")
        self.assertEqual(registro.madre, "Ana Soto")
        self.assertEqual(registro.enlace, "https://www.familysearch.org/ark:/61903/1:1:TEST-1")

    def test_matrimonio_toma_la_fecha_de_la_relacion(self):
        entrada = _entrada(
            [
                _persona("esposa", "María González", "Female", None, principal=True),
                _persona("esposo", "Pedro Soto", "Male", None),
            ],
            [
                {
                    "type": "http://gedcomx.org/Couple",
                    "person1": {"resourceId": "esposa"},
                    "person2": {"resourceId": "esposo"},
                    "facts": [
                        {
                            "type": "http://gedcomx.org/Marriage",
                            "date": {"original": "1901", "formal": "+1901"},
                            "place": {"original": "Valparaíso, Chile"},
                        }
                    ],
                }
            ],
            titulo="Chile, Matrimonios, 1579-1930",
        )
        registro = interpretar(entrada, "matrimonio", "1520558", "Chile, Matrimonios, 1579-1930", False)
        self.assertEqual(registro.conyuge, "Pedro Soto")
        self.assertEqual(registro.fecha, "1901")
        self.assertEqual(registro.lugar, "Valparaíso, Chile")

    def test_defuncion_prefiere_muerte_antes_que_entierro(self):
        persona = _persona(
            "difunta",
            "Rosa Díaz",
            "Female",
            None,
            principal=True,
        )
        persona["facts"] = [
            {"type": "http://gedcomx.org/Burial", "date": {"original": "2 de mayo de 1910"}, "place": {"original": "Concepción, Chile"}},
            {"type": "http://gedcomx.org/Death", "date": {"original": "1 de mayo de 1910", "formal": "+1910-05-01"}, "place": {"original": "Concepción, Chile"}},
        ]
        entrada = _entrada([persona], [], titulo="Chile, Defunciones, 1700-1920")
        registro = interpretar(entrada, "defuncion", "1520559", "Chile, Defunciones, 1700-1920", False)
        self.assertEqual(registro.fecha, "1 de mayo de 1910")

    def test_coleccion_mixta_descarta_un_bautismo_si_se_piden_defunciones(self):
        hecho = {"type": "http://gedcomx.org/Christening", "date": {"original": "1890"}, "place": {"original": "Chile"}}
        entrada = _entrada(
            [_persona("hijo", "Juan Pérez", "Male", hecho, principal=True)],
            [],
            titulo="Chile, Catholic Church Records",
        )
        self.assertIsNone(interpretar(entrada, "defuncion", "3405096", "Chile, Catholic Church Records, 1633-2015", True))

    def test_nombre_por_partes_si_no_hay_texto_completo(self):
        persona = {
            "id": "p",
            "principal": True,
            "names": [{"nameForms": [{"parts": [{"type": "http://gedcomx.org/Given", "value": "Ana"}, {"type": "http://gedcomx.org/Surname", "value": "Soto"}]}]}],
            "facts": [],
        }
        entrada = _entrada([persona], [])
        registro = interpretar(entrada, "bautismo", "1520549", "Chile, Bautismos, 1585-1932", False)
        self.assertEqual(registro.nombre, "Ana Soto")


class ConsultaTests(unittest.TestCase):
    def test_bautismo_no_usa_el_registro_civil(self):
        ids = [coleccion.id for coleccion in colecciones_para("bautismo")]
        self.assertEqual(ids, ["1520549", "3405096"])

    def test_matrimonio_incluye_parroquia_e_indice_civil(self):
        ids = [coleccion.id for coleccion in colecciones_para("matrimonio")]
        self.assertIn("1520558", ids)
        self.assertIn("1630787", ids)

    def test_parametros_de_matrimonio(self):
        consulta = Consulta(
            tipo="matrimonio",
            nombre="María",
            apellido="González",
            lugar="Valparaíso, Chile",
            desde=1890,
            hasta=1910,
            conyuge_nombre="Pedro",
            conyuge_apellido="Soto",
        )
        pares = dict(parametros(consulta, "1520558", 20, 0))
        self.assertEqual(pares["q.marriageLikePlace"], "Valparaíso, Chile")
        self.assertEqual(pares["q.marriageLikeDate.from"], "+1890")
        self.assertEqual(pares["q.marriageLikeDate.to"], "+1910")
        self.assertEqual(pares["q.spouseSurname"], "Soto")
        self.assertEqual(pares["f.collectionId"], "1520558")

    def test_exige_nombre_o_apellido(self):
        with self.assertRaises(ValueError):
            Consulta(tipo="defuncion", nombre="", apellido="").validar()

    def test_un_solo_token_es_apellido(self):
        self.assertEqual(partir_nombre("Soto"), ("", "Soto"))
        self.assertEqual(partir_nombre("Pedro Soto"), ("Pedro", "Soto"))


class ClienteTests(unittest.TestCase):
    def test_reintenta_cuando_hay_demasiadas_consultas(self):
        llamadas = {"n": 0}

        def transport(url, headers):
            llamadas["n"] += 1
            self.assertIn("q.surname=P%C3%A9rez", url)
            self.assertTrue(headers["Authorization"].startswith("Bearer "))
            if llamadas["n"] == 1:
                return 429, None, {"Retry-After": "0"}
            return 200, {"entries": [], "results": 0}, {}

        dormidos = []
        cliente = Cliente("secreto", transport=transport, dormir=dormidos.append)
        pagina = cliente.buscar_pagina([("q.surname", "Pérez"), ("count", "1"), ("offset", "0")])
        self.assertEqual(pagina["results"], 0)
        self.assertEqual(llamadas["n"], 2)
        self.assertEqual(dormidos, [0.0])

    def test_sesion_rechazada_no_repite_el_token(self):
        def transport(url, headers):
            return 401, None, {}

        cliente = Cliente("secreto", transport=transport, dormir=lambda _s: None)
        with self.assertRaises(ErrorFamilySearch) as ctx:
            cliente.buscar_pagina([("count", "1"), ("offset", "0")])
        self.assertEqual(ctx.exception.estado, 401)
        self.assertNotIn("secreto", str(ctx.exception))

    def test_pagina_vacia(self):
        cliente = Cliente("tok", transport=lambda url, headers: (204, None, {}), dormir=lambda _s: None)
        self.assertEqual(cliente.buscar_pagina([("count", "1")]), {"entries": [], "results": 0})


class BuscarTests(unittest.TestCase):
    def test_pagina_y_descarta_la_coleccion_mixta_que_no_coincide(self):
        bautismo = _entrada(
            [_persona("hijo", "Juan Pérez", "Male", {"type": "http://gedcomx.org/Christening", "date": {"original": "1894"}, "place": {"original": "Chile"}}, True)],
            [],
        )
        otro = _entrada(
            [_persona("otro", "Luis Pérez", "Male", {"type": "http://gedcomx.org/Death", "date": {"original": "1920"}, "place": {"original": "Chile"}}, True)],
            [],
            titulo="Defunción",
            ark="https://www.familysearch.org/ark:/61903/1:1:OTRO-1",
        )

        class Falso:
            def __init__(self):
                self.llamadas = []

            def buscar_pagina(self, params):
                datos = dict(params)
                self.llamadas.append(datos)
                if datos["f.collectionId"] == "1520549" and datos["offset"] == "0":
                    return {"entries": [bautismo, bautismo], "results": 2}
                if datos["f.collectionId"] == "3405096":
                    return {"entries": [otro], "results": 1}
                return {"entries": [], "results": 0}

        falso = Falso()
        registros = ejecutar(
            falso,
            Consulta(tipo="bautismo", apellido="Pérez"),
            max_resultados=10,
            por_pagina=1,
            pausa=0,
            dormir=lambda _s: None,
        )
        self.assertEqual([registro.nombre for registro in registros], ["Juan Pérez"])
        self.assertTrue(any(item["f.collectionId"] == "3405096" for item in falso.llamadas))


class ExportarTests(unittest.TestCase):
    def test_csv_con_bom_para_excel(self):
        registro = interpretar(
            _entrada([_persona("hijo", "Juan Pérez", "Male", {"type": "http://gedcomx.org/Baptism", "date": {"original": "1894"}}, True)], []),
            "bautismo",
            "1520549",
            "Chile, Bautismos, 1585-1932",
            False,
        )
        with tempfile.TemporaryDirectory() as carpeta:
            destino = Path(carpeta) / "bautismos.csv"
            escribir([registro], destino)
            self.assertTrue(destino.read_bytes().startswith(b"\xef\xbb\xbf"))
            texto = destino.read_text(encoding="utf-8-sig")
            self.assertIn("Juan Pérez", texto)
            self.assertTrue(texto.startswith("tipo,coleccion_id"))


class AuthTests(unittest.TestCase):
    def test_pkce_del_rfc(self):
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        self.assertEqual(code_challenge(verifier), "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM")

    def test_la_autorizacion_apunta_a_familysearch(self):
        url = url_autorizacion("app", "http://127.0.0.1:8765/callback", "estado", "reto")
        parsed = urlparse(url)
        self.assertEqual(parsed.netloc, "ident.familysearch.org")
        query = parse_qs(parsed.query)
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertEqual(query["redirect_uri"], ["http://127.0.0.1:8765/callback"])

    def test_guarda_la_sesion_sin_imprimirla_en_el_archivo_publico(self):
        anterior = os.environ.get("INTELLIGENCE_TOKEN_DIR")
        token_env = os.environ.pop("FAMILYSEARCH_ACCESS_TOKEN", None)
        with tempfile.TemporaryDirectory() as carpeta:
            os.environ["INTELLIGENCE_TOKEN_DIR"] = carpeta
            try:
                destino = guardar_token({"access_token": "abc", "expires_in": 3600})
                self.assertEqual(json.loads(destino.read_text(encoding="utf-8"))["access_token"], "abc")
                self.assertEqual(leer_token(), "abc")
                os.environ["FAMILYSEARCH_ACCESS_TOKEN"] = "desde-env"
                self.assertEqual(leer_token(), "desde-env")
            finally:
                if anterior is None:
                    os.environ.pop("INTELLIGENCE_TOKEN_DIR", None)
                else:
                    os.environ["INTELLIGENCE_TOKEN_DIR"] = anterior
                if token_env is None:
                    os.environ.pop("FAMILYSEARCH_ACCESS_TOKEN", None)
                else:
                    os.environ["FAMILYSEARCH_ACCESS_TOKEN"] = token_env


class CliTests(unittest.TestCase):
    def test_sin_apellido_no_consulta(self):
        codigo = main(["buscar", "--tipo", "bautismo"])
        self.assertEqual(codigo, 1)

    def test_lista_colecciones(self):
        self.assertEqual(main(["colecciones"]), 0)


if __name__ == "__main__":
    unittest.main()
