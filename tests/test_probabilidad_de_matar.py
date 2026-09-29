"""
Probabilidad de matar y casillas mortales en la recomendación.

Partida del usuario (Cap. 11, turno 4): Diamant, en Fusión con Edelgard, puede matar con
Failnaught al Sword Fighter (9,23) (35 contra 32 HP) desde una casilla segura o al Martial
Monk (8,2) (100 % Hit) acabando al alcance del Axe Cavalier (10,1) y un Corrupted Wyrm,
que entre los dos le hacen 40 contra sus 30 HP. Con la Steel Sword el Sword Fighter tiene
33 de Evasión y el Hit baja al 88 %: el motor elegía la baja segura aunque Diamant muriera
en la fase enemiga, porque el peligro de la casilla restaba como mucho 120 puntos.
"""

import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from helpers import cargar_fixture  # noqa: E402
from motor_calculo import probabilidad_de_matar  # noqa: E402


class TestProbabilidadDeMatar(unittest.TestCase):

    def test_un_golpe_que_mata(self):
        self.assertEqual(probabilidad_de_matar(32, [(88, 35)]), 88.0)

    def test_con_doble_hay_dos_tiradas(self):
        """Fallar el primero no es fallar la baja si el segundo también mata."""
        self.assertEqual(probabilidad_de_matar(32, [(88, 35), (88, 35)]), 98.56)

    def test_si_hacen_falta_los_dos_golpes(self):
        self.assertEqual(probabilidad_de_matar(30, [(90, 15), (90, 15)]), 81.0)

    def test_brave_con_doble_son_cuatro_tiradas(self):
        """Brave y Artes: cada golpe del par tiene su propia tirada. Con 4 golpes de 10 y
        30 HP hacen falta 3 aciertos de 4 al 80 %: 0.8⁴ + 4·0.8³·0.2 = 81.92 %."""
        self.assertEqual(probabilidad_de_matar(30, [(80, 10)] * 4), 81.92)

    def test_sin_hp_que_quitar(self):
        self.assertEqual(probabilidad_de_matar(0, [(50, 1)]), 100.0)


class TestDiamantNoSeSuicida(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from app import app
        app.config["TESTING"] = True
        cls.client = app.test_client()
        cls.partida = cargar_fixture("partida_cap11_turno4.json")

    @classmethod
    def tearDownClass(cls):
        cls.client.post("/api/mapa/seleccionar", json={"capitulo": 7})

    def _analizar(self, arma_sword_fighter=None):
        p = copy.deepcopy(self.partida)
        if arma_sword_fighter:
            sf = next(f for f in p["fichas"] if f["nombre"] == "Sword Fighter (9,23)")
            for it in sf["inventario"]:
                it["equipada"] = it["nombre"] == arma_sword_fighter
        self.client.post("/api/mapa/seleccionar", json={"capitulo": 11})
        self.client.post("/api/partida/importar", json={"partida": p})
        res = self.client.post("/api/analizar", json={"perfil": "seguro"}).get_json()["resultados"]
        return next(r for r in res if r.get("aliado") == "Diamant" and r.get("enemigo"))

    def test_con_master_lance_mata_al_sword_fighter(self):
        r = self._analizar()
        self.assertEqual((r["enemigo"], r["pos_sugerida"]), ("Sword Fighter (9,23)", [10, 17]))
        self.assertTrue(r["veredicto"]["kill_seguro"])

    def test_con_steel_sword_prefiere_la_baja_probable_que_le_deja_vivo(self):
        r = self._analizar("Steel Sword")
        self.assertEqual(r["enemigo"], "Sword Fighter (9,23)")
        self.assertFalse(r["amenaza_letal_destino"])
        self.assertEqual(r["veredicto"]["prob_kill"], 88.0, "sin doble: una sola tirada al 88 %")

    def test_el_primer_golpe_ya_mata(self):
        """Diamant dobla con la Master Lance equipada (AS 7) pero el primer flechazo basta."""
        r = self._analizar()
        self.assertIn("2x35 = 70 dmg (First-hit kill)", r["recomendacion"])
        self.assertNotIn("Follow-up", r["recomendacion"])


if __name__ == "__main__":
    unittest.main()
