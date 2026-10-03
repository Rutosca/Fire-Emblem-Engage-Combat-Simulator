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


class TestAuraDeAlearCap13(unittest.TestCase):
    """Partida del jugador (Cap. 13, T3): Etie en (8,9) recibía el aura de otro aliado y la
    herramienta daba esa casilla por buena; junto a Alear (Divinely Inspiring, +1 por golpe
    de Astra Storm) mata al Ruffian (14,12): 5 x 9 = 45 contra 43 HP."""

    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.client.post("/api/mapa/seleccionar", json={"capitulo": 7})

    def test_astra_storm_junto_a_alear(self):
        import json
        if self.client.post("/api/mapa/seleccionar", json={"capitulo": 13}).status_code != 200:
            self.skipTest("sin mapa del capítulo 13")
        ruta = os.path.join(os.path.dirname(__file__), "fixtures", "partida_cap13_turno3.json")
        with open(ruta, encoding="utf-8") as f:
            self.assertEqual(self.client.post("/api/partida/importar", json=json.load(f)).status_code, 200)
        res = self.client.post("/api/analizar", json={"perfil": "seguro"}).get_json()["resultados"]
        etie = next(r for r in res if r.get("aliado") == "Etie" and r.get("enemigo") == "Ruffian (14,12)")
        self.assertTrue(etie["arma_recomendada"].startswith("Astra Storm"))
        self.assertEqual(etie["categoria"], "kill_seguro")
        alear = tablero.obtener_ficha("Alear")
        self.assertEqual(abs(etie["pos_sugerida"][0] - alear.x) + abs(etie["pos_sugerida"][1] - alear.y), 1)


if __name__ == "__main__":
    unittest.main()
