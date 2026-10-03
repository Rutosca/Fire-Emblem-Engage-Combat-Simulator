"""
Alear puede ser hombre o mujer (Person.xml trae sus variantes PID_青リュール_男性 / _女性).
El buscador ofrece "Alear (M)" y "Alear (F)"; la ficha conserva el sufijo y su género cuenta
para las pasivas: Fairy-Tale Folk de Chloé (SID_絵になる二人, "周囲の隣接男女数(2, 男性,
女性) > 0": un hombre y una mujer adyacentes entre sí a 2 casillas o menos de ella, +2 Mt).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app, tablero  # noqa: E402
from catalogo_loader import separar_genero, personajes_de_genero_elegible  # noqa: E402
from motor_calculo import CalculadoraEngage, Terreno, distancia_entre_unidades  # noqa: E402


class TestGeneroAlear(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.client.post("/api/mapa/seleccionar", json={"capitulo": 7})

    def setUp(self):
        self.client.post("/api/mapa/seleccionar", json={"capitulo": 12})
        tablero.fichas.clear()

    def _unidad(self, nombre, clase, x, y, aliado=True):
        r = self.client.post("/api/unidad/guardar", json={
            "nombre": nombre, "clase_nombre": clase, "es_aliado": aliado, "x": x, "y": y, "nivel": 10,
            "inventario": [{"arma": "Iron Sword" if aliado else "Iron Axe", "equipada": True}]})
        self.assertEqual(r.status_code, 200, r.get_json())
        return tablero.obtener_ficha(nombre)

    def test_solo_alear_tiene_genero_elegible(self):
        self.assertEqual(personajes_de_genero_elegible(), {"Alear"})
        self.assertEqual(separar_genero("Alear (F)"), ("Alear", 2))
        self.assertEqual(separar_genero("Alear (M)"), ("Alear", 1))
        self.assertEqual(separar_genero("Lapis (F)"), ("Lapis (F)", 0))

    def test_buscador(self):
        r = self.client.get("/api/catalogo/buscar", query_string={"q": "alear", "tipo": "personajes"}).get_json()
        nombres = [x["nombre"] for x in r["resultados"]]
        self.assertEqual(nombres[:2], ["Alear (M)", "Alear (F)"])
        self.assertNotIn("Alear", nombres)
        self.assertFalse([n for n in nombres if n.startswith("Title")])

    def test_ficha_y_vista_previa(self):
        f = self._unidad("Alear (F)", "Dragon Child", 6, 9)
        self.assertEqual((f.pid, f.stats.genero), ("PID_リュール", 2))
        p = self.client.post("/api/unidad/resolver_preview", json={"nombre": "Alear (F)", "es_aliado": True}).get_json()
        self.assertEqual((p["nombre"], p["clase_nombre"]), ("Alear (F)", "Dragon Child"))

    def _fairy_tale_folk(self, alear):
        chloe = self._unidad("Chloé", "Lance Flier", 6, 9)
        self._unidad(alear, "Dragon Child", 5, 9)
        self._unidad("Lapis", "Sword Fighter", 5, 10)       # adyacente a Alear, a 2 de Chloé
        ene = self._unidad("Bandido", "Axe Fighter", 7, 9, aliado=False)
        cercanos = [(a.stats, distancia_entre_unidades(a, chloe)) for a in tablero.fichas.values()
                    if a.es_aliado and a.nombre != "Chloé"]
        r = CalculadoraEngage.simular_combate(chloe.stats, ene.stats, chloe.arma, ene.arma, Terreno(), Terreno(), 1,
                                              aliados_cercanos_atk=cercanos)
        return any("Fairy-Tale Folk" in p for p in r["atacante"]["pasivas_activas"])

    def test_fairy_tale_folk_depende_del_genero_de_alear(self):
        self.assertTrue(self._fairy_tale_folk("Alear (M)"), "Alear hombre junto a Lapis: pareja")
        tablero.fichas.clear()
        self.assertFalse(self._fairy_tale_folk("Alear (F)"), "dos mujeres: no hay pareja")


if __name__ == "__main__":
    unittest.main()
