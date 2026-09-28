"""
Resolución de unidades y armas por el catálogo (catalogo_loader): nivel
interno de clase, grabados de Emblema.

Origen: tests/test_fixes_tactical.py (partido por dominio el 2026-09-18).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from helpers import cargar_dispos  # noqa: E402
from app import tablero, resolver_unidad_con_catalogo, _arma_desde_item  # noqa: E402


class TestCatalogoLoader(unittest.TestCase):

    def setUp(self):
        # resolver_unidad_con_catalogo lee app.tablero para heredar estado: empezar siempre limpio
        tablero.limpiar()

    def test_armored_m007_usa_nivel_interno_de_clase_basica(self):
        """Un Armored de nivel 10 no debe recibir +9 niveles de clase avanzada."""
        armored = next(u for u in cargar_dispos("M007", "Extremo")
                       if "Armor" in u.get("clase_nombre", ""))
        ficha = resolver_unidad_con_catalogo(armored)
        self.assertEqual(getattr(ficha.stats, "nivel_interno_clase", None), 0)
        self.assertEqual(ficha.stats.hp, 36)

    def test_grabado_de_emblema_como_campo_separado_se_aplica(self):
        """
        _arma_desde_item no debe perder el grabado de Emblema cuando viene como
        campo separado del dict de inventario (no embebido en "nombre").
        """
        item = {"nombre": "Levin Sword", "nombre_base": "Levin Sword", "grabado": "Sigurd", "refine_lvl": 0}
        arma = _arma_desde_item(item)
        self.assertEqual(arma.mt, 14, "El grabado de Sigurd debe sumar +1 Mt (13 base + 1)")
        self.assertEqual(arma.avo_bonus, 20, "El grabado de Sigurd debe dar +20 Avoid")

    def test_grabado_sobrevive_reparseo_tras_mostrarse(self):
        """
        GRABADOS_EMBLEMA debe usar el nombre localizado oficial (God.xml "nombre"),
        no la transliteración interna "ascii_name" (que trae erratas: Sigurd-Siglud,
        Leif-Leaf, Lyn-Lin, Corrin-Kamui, Eirika-Eirik, Alear-Lueur). De lo contrario,
        el nombre formateado que se le muestra al jugador no coincide con ninguna
        clave al reparsearlo (p.ej. al reguardar la unidad), y el grabado desaparece.
        """
        from catalogo_loader import parsear_arma_string
        for emblema in ("Sigurd", "Leif", "Lyn", "Corrin", "Eirika", "Alear"):
            primera = parsear_arma_string(f"Iron Sword ({emblema})")
            self.assertIsNotNone(primera.get("grabado"), f"{emblema}: el grabado debe aplicarse en la primera pasada")
            segunda = parsear_arma_string(primera["nombre"])
            self.assertIsNotNone(segunda.get("grabado"), f"{emblema}: el grabado debe sobrevivir al reparsear el nombre ya formateado")
            self.assertEqual(primera["avo_bonus"], segunda["avo_bonus"], f"{emblema}: el bono debe mantenerse igual tras el reparseo")

class TestArmasDelDLC(unittest.TestCase):
    """El juego base no trae los textos del DLC: sus nombres van en json/nombres_dlc.json."""

    def test_armas_personales_del_fell_xenologue(self):
        """Nel (Représailles, MIID_Trahison) y Rafal (Revanche, MIID_Levanche)."""
        for nombre, tipo, mt in (("Représailles", "Lanza", 13), ("Represailles", "Lanza", 13), ("Revanche", "Hacha", 10)):
            f = resolver_unidad_con_catalogo({"nombre": "Prueba", "es_aliado": True, "clase_nombre": "Lance Fighter",
                                              "nivel": 10, "inventario": [{"nombre": nombre, "equipada": True}]})
            self.assertEqual((f.arma.nombre, f.arma.tipo, f.arma.mt), (nombre.replace("Represailles", "Représailles"), tipo, mt))

    def test_la_busqueda_del_modal_no_repite_armas(self):
        """Lo escrito a medias ("Repr") se interpretaba además como arma y salía dos veces."""
        from app import app
        c = app.test_client()
        for q, esperado in (("Repr", ["Représailles"]), ("iron s", ["Iron Sword"])):
            r = c.get("/api/catalogo/buscar", query_string={"tipo": "armas", "q": q}).get_json()
            self.assertEqual([x["nombre"] for x in r["resultados"]], esperado, q)

    def test_los_objetos_con_usos_salen_una_sola_vez(self):
        """Los usos restantes/máximos se ponen en la ranura del inventario: ya no se
        ofrece "Poción (3)", "(2)", "(1)"; los usos máximos van en los datos."""
        from app import app
        r = app.test_client().get("/api/catalogo/buscar", query_string={"tipo": "armas", "q": "poci"}).get_json()
        nombres = [x["nombre"] for x in r["resultados"]]
        self.assertTrue(nombres)
        self.assertFalse([n for n in nombres if n.rstrip().endswith(")")], nombres)
        self.assertEqual(len(nombres), len(set(nombres)))
        self.assertTrue(all(x["datos"].get("usos_max") for x in r["resultados"]))

    def test_una_partida_antigua_con_usos_entre_parentesis_se_sigue_leyendo(self):
        f = resolver_unidad_con_catalogo({"nombre": "Prueba", "es_aliado": True, "clase_nombre": "Sword Fighter",
                                          "nivel": 10, "inventario": ["Iron Sword", "Poción (2)"]})
        pocion = next(i for i in f.inventario if "Poción" in str(i.get("nombre", "")))
        self.assertEqual((pocion["nombre"], pocion["usos"]), ("Poción", 2))


class TestAtaqueDeEmblemaEnElModal(unittest.TestCase):
    """El catálogo guarda en `engage_attack` el SID (lo usa el motor); al modal le llega el
    nombre, que es el chip que añade al fusionar. Antes salía SID_マルスエンゲージ技."""

    def test_todos_los_emblemas_llegan_con_nombre_legible(self):
        from app import app
        emblemas = app.test_client().get("/api/catalogo/emblemas").get_json()["emblemas"]
        for gid, e in emblemas.items():
            self.assertFalse(e["engage_attack"].startswith("SID_"), (gid, e["engage_attack"]))
            self.assertTrue(e["engage_attack_sid"].startswith("SID_"), gid)
        por_nombre = {e["nombre"]: e["engage_attack"] for e in emblemas.values()}
        self.assertEqual(por_nombre["Marth"], "Lodestar Rush (Acometida estelar)")
        self.assertEqual(por_nombre["Dimitri"], "Houses Unite (Unión de Casas)")
        self.assertEqual(por_nombre["Robin"], "Giga Levin Sword (Gigaespada Trueno)")

    def test_el_motor_sigue_teniendo_el_sid(self):
        from catalogo_loader import _catalogo
        self.assertEqual(_catalogo["emblemas"]["GID_マルス"]["engage_attack"], "SID_マルスエンゲージ技")


if __name__ == "__main__":
    unittest.main()
