"""
Partida del usuario (Cap. 12, turno 1): Etie, fusionada con Lyn, tiene Astra Storm (5
golpes al 30 %, efectivo contra voladores con su arco) y Alear está cerca con Divinely
Inspiring (+3 de daño a los adyacentes).
  - El análisis la mandaba a (17,9), lejos de Alear: 5 golpes de 6 contra un Sword Fighter
    y una baja conjunta con Bunet. Junto a Alear son 5 de 7.
  - El Ataque de Emblema contra enemigos normales tenía un tope de puntuación ("reservar
    la Fusión para jefes"), aunque Etie ya estaba fusionada y el mapa no tiene jefe: matar al
    Lance Flier con Astra Storm (5 de 14) no se proponía. Ahora sí, y el Sword Fighter queda
    para una baja conjunta de Bunet y Pandreo.
  - El texto decía "Etie hace 30 (5x30)"; ahora "hace 30 de daño (5 golpes de 6)".
"""

import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from helpers import cargar_fixture  # noqa: E402


class TestAstraStormDeEtie(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from app import app
        app.config["TESTING"] = True
        cls.client = app.test_client()
        cls.partida = cargar_fixture("partida_cap12_turno1.json")

    @classmethod
    def tearDownClass(cls):
        cls.client.post("/api/mapa/seleccionar", json={"capitulo": 7})

    def setUp(self):
        self.client.post("/api/mapa/seleccionar", json={"capitulo": 12})
        self.client.post("/api/partida/importar", json={"partida": copy.deepcopy(self.partida)})

    def _astra_contra(self, enemigo, pos):
        from app import tablero
        from motor_analisis import _armas_aliado
        from motor_calculo import CalculadoraEngage, Terreno, distancia_a_unidad
        etie, e = tablero.obtener_ficha("Etie"), tablero.obtener_ficha(enemigo)
        astra = next(a for a, _, _ in _armas_aliado(etie) if a.nombre == "Astra Storm (Steel Bow)")
        cercanos = [(a.stats, distancia_a_unidad(a, *pos)) for a in tablero.obtener_aliados() if a.nombre != "Etie"]
        return CalculadoraEngage.evaluar_riesgo(
            atacante=etie.stats, defensor=e.stats, arma_atk=astra, arma_def=e.arma, terreno_atk=Terreno(),
            terreno_def=Terreno(), distancia=distancia_a_unidad(e, *pos), es_engage_attack=True,
            engage_attack_nombre="Astra Storm", aliados_cercanos_atk=cercanos)

    def test_texto_del_daño(self):
        v = self._astra_contra("Sword Fighter (11,5)", (17, 9))
        self.assertIn("Etie hace 30 de daño (5 golpes de 6).", v["veredicto"]["motivos"][0])

    def test_junto_a_alear_pega_mas(self):
        lejos = self._astra_contra("Sword Fighter (11,5)", (17, 9))["combate"]["atacante"]["lodestar_hits"]
        cerca = self._astra_contra("Sword Fighter (11,5)", (16, 7))["combate"]["atacante"]["lodestar_hits"]
        self.assertEqual((tuple(lejos), tuple(cerca)), ((5, 6), (5, 7)))

    def test_mata_al_volador_y_los_demas_al_sword_fighter(self):
        res = self.client.post("/api/analizar", json={"perfil": "seguro"}).get_json()["resultados"]
        por_aliado = {r.get("aliado"): r for r in res if r.get("tipo_analisis") == "oportunidad_jugador"}
        etie = por_aliado["Etie"]
        self.assertEqual((etie["enemigo"], etie["arma_recomendada"], etie["categoria"]),
                         ("Lance Flier (6,7)", "Astra Storm (Steel Bow)", "kill_seguro"))
        self.assertEqual(etie["pos_sugerida"], [16, 7], "junto a Alear (Divinely Inspiring)")
        plan = {n for n, r in por_aliado.items() if r.get("plan_baja") and r["enemigo"] == "Sword Fighter (11,5)"}
        self.assertEqual(plan, {"Bunet", "Pandreo"})


if __name__ == "__main__":
    unittest.main()
