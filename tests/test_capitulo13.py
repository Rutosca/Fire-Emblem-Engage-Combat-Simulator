"""
Capítulo 13 (oscuridad): lo que sale del guion M013.lua.
  - MapOpening: UnitCreateGodUnit("PID_ミスティラ", "GID_アイク") → Timerra llega con Ike.
  - Inicio del turno 1: UnitMovePos de Timerra, Panette y Merrin y luego UnitJoin → al
    pulsar "Empezar batalla" se recolocan donde los deja la conversación y ya son tuyos.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app, tablero  # noqa: E402
import cargador_dispos  # noqa: E402


class TestCapitulo13(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.client.post("/api/mapa/seleccionar", json={"capitulo": 7})

    def setUp(self):
        r = self.client.post("/api/mapa/seleccionar", json={"capitulo": 13})
        if r.status_code != 200:
            self.skipTest("sin mapa del capítulo 13")
        self.assertEqual(self.client.post("/api/preset/actual", json={}).status_code, 200)

    def test_guion(self):
        self.assertEqual(cargador_dispos.emblemas_del_guion("M013"), {"PID_ミスティラ": "GID_アイク"})
        self.assertEqual(cargador_dispos.movimientos_del_guion("M013"),
                         {"PID_ミスティラ": (10, 13), "PID_パネトネ": (12, 13), "PID_メリン": (11, 14)})

    def test_timerra_llega_con_ike(self):
        t = tablero.obtener_ficha("Timerra")
        self.assertEqual(t.emblema_nombre, "Ike")
        self.assertEqual(t.energia_emblema, t.max_energia_emblema, "puede fusionarse en el turno 1")

    def test_se_recolocan_al_empezar(self):
        alto = tablero.mapa.alto
        antes = {n: (tablero.obtener_ficha(n).x, tablero.obtener_ficha(n).y) for n in ("Timerra", "Panette", "Merrin")}
        self.assertEqual(self.client.post("/api/batalla/empezar", json={}).status_code, 200)
        esperado = {"Timerra": (9, alto - 13), "Panette": (11, alto - 13), "Merrin": (10, alto - 14)}
        for n, pos in esperado.items():
            f = tablero.obtener_ficha(n)
            self.assertEqual((f.x, f.y), pos)
            self.assertTrue(f.controlable and not f.es_verde)
        # la Cronogema los devuelve a la casilla de inicio
        self.assertTrue(tablero.deshacer())
        self.assertEqual({n: (tablero.obtener_ficha(n).x, tablero.obtener_ficha(n).y) for n in antes}, antes)


if __name__ == "__main__":
    unittest.main()
