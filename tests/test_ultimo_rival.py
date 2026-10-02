"""
Single-Minded (SID_執着, personal de Ivy): +20 Hit "si se enfrenta a su oponente más
reciente" (Skill.xml: 最終戦闘相手 == 相手の識別子). Cada ficha recuerda su último rival
(ultimo_rival, por nombre en el tablero: los genéricos comparten pid) y se actualiza con
cada combate ejecutado, en las dos fases. Visto en el juego (Cap. 12): un Wolf Knight ataca a
Ivy en la fase enemiga; cuando ella le ataca después tiene 98 % de Hit, no 78 %.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app, tablero  # noqa: E402
from motor_calculo import CalculadoraEngage, Terreno  # noqa: E402

ENEMIGO = {"clase_nombre": "Wolf Knight", "es_aliado": False, "nivel": 1, "hp_max": 38, "hp_actual": 38,
           "stats": {"hp": 38, "hp_max": 38, "fuerza": 16, "magia": 9, "destreza": 20, "velocidad": 22,
                     "defensa": 12, "resistencia": 14, "suerte": 8, "complexion": 8},
           "arma_nombre": "Steel Dagger", "inventario": [{"arma": "Steel Dagger", "equipada": True}]}


class TestUltimoRival(unittest.TestCase):

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
        self._guardar({"nombre": "Ivy", "clase_nombre": "Lindwurm", "es_aliado": True, "x": 6, "y": 9, "nivel": 5,
                       "arma_nombre": "Elfire", "inventario": [{"arma": "Elfire", "equipada": True}]})
        self._guardar(dict(ENEMIGO, nombre="Wolf Knight A", x=6, y=10))
        self._guardar(dict(ENEMIGO, nombre="Wolf Knight B", x=7, y=9))

    def _guardar(self, d):
        r = self.client.post("/api/unidad/guardar", json=d)
        self.assertEqual(r.status_code, 200, r.get_json())

    def _hit(self, enemigo):
        ivy, e = tablero.obtener_ficha("Ivy"), tablero.obtener_ficha(enemigo)
        r = CalculadoraEngage.simular_combate(ivy.stats, e.stats, ivy.arma, e.arma, Terreno(), Terreno(), 1)
        return r["atacante"]["precision"]

    def test_bono_solo_contra_el_ultimo_rival(self):
        self.assertTrue(tablero.obtener_ficha("Ivy").usa_ultimo_rival())
        sin = (self._hit("Wolf Knight A"), self._hit("Wolf Knight B"))
        self.assertEqual(sin[0], sin[1], "los dos Wolf Knight son iguales")
        # Wolf Knight A ataca a Ivy en la fase enemiga
        tablero.fase = "enemigo"
        r = self.client.post("/api/combate/ejecutar", json={"atacante": "Wolf Knight A", "defensor": "Ivy",
                                                            "arma_nombre": "Steel Dagger", "pos_destino": [6, 10]})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(tablero.obtener_ficha("Ivy").ultimo_rival, "Wolf Knight A")
        self.assertEqual(tablero.obtener_ficha("Wolf Knight A").ultimo_rival, "Ivy")
        self.assertEqual(self._hit("Wolf Knight A"), min(100, sin[0] + 20))
        self.assertEqual(self._hit("Wolf Knight B"), sin[1], "mismo pid, otra unidad: sin bono")

    def test_se_fija_a_mano_y_se_conserva(self):
        d = tablero.obtener_ficha("Ivy").como_dict()
        self.assertTrue(d["usa_ultimo_rival"])
        d["ultimo_rival"] = "Wolf Knight B"
        self._guardar(d)
        self.assertEqual(tablero.obtener_ficha("Ivy").ultimo_rival, "Wolf Knight B")
        exp = self.client.get("/api/partida/exportar").get_json()["partida"]
        self.client.post("/api/partida/importar", json={"partida": exp})
        self.assertEqual(tablero.obtener_ficha("Ivy").ultimo_rival, "Wolf Knight B")
        self.assertGreater(self._hit("Wolf Knight B"), self._hit("Wolf Knight A") - 1)


if __name__ == "__main__":
    unittest.main()
