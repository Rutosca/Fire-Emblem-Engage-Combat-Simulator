"""
Utilidades compartidas por los tests: rutas de fixtures versionadas, carga del
roster guardado y de los dispos del datamine, y una clase base con las
unidades del Capítulo 7 que usan varios tests de números reales.
"""

import os
import sys
import json
import unicodedata
import unittest

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

DIR_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
RUTA_ROSTER = os.path.join(RAIZ, "json", "escuadron_guardado.json")


def norm(texto) -> str:
    """Minúsculas sin acentos (para buscar por nombre sin depender de la tilde)."""
    return unicodedata.normalize("NFKD", str(texto)).encode("ASCII", "ignore").decode("utf-8").lower()


def ruta_fixture(nombre: str) -> str:
    return os.path.join(DIR_FIXTURES, nombre)


def cargar_fixture(nombre: str):
    with open(ruta_fixture(nombre), "r", encoding="utf-8") as f:
        return json.load(f)


def cargar_roster() -> list:
    """Roster de aliados guardado (json/escuadron_guardado.json), como dicts crudos."""
    with open(RUTA_ROSTER, "r", encoding="utf-8") as f:
        return json.load(f)


def unidad_roster(fragmento_nombre: str) -> dict:
    """Primer aliado del roster cuyo nombre contiene el fragmento (sin acentos)."""
    frag = norm(fragmento_nombre)
    return next(u for u in cargar_roster() if frag in norm(u.get("nombre", "")))


def cargar_dispos(dispos_id: str = "M007", dificultad: str = "Extremo") -> list:
    """Unidades del despliegue oficial del datamine, como dicts crudos."""
    from cargador_dispos import CargadorDisposEngage
    return CargadorDisposEngage().cargar_capitulo(dispos_id, dificultad)


def unidad_dispos_en(x: int, y: int, dispos_id: str = "M007", dificultad: str = "Extremo") -> dict:
    return next(u for u in cargar_dispos(dispos_id, dificultad) if (u.get("x"), u.get("y")) == (x, y))


class CasoCapitulo7(unittest.TestCase):
    """Fichas reales del Capítulo 7 resueltas por el catálogo: el Lance Fighter
    de (10, 6) en Extremo y Céline / Chloé del roster guardado."""

    @classmethod
    def setUpClass(cls):
        from catalogo_loader import resolver_unidad_con_catalogo
        cls.f_lf = resolver_unidad_con_catalogo(unidad_dispos_en(10, 6))
        cls.f_cel = resolver_unidad_con_catalogo(unidad_roster("cel"))
        cls.f_chl = resolver_unidad_con_catalogo(unidad_roster("chlo"))
