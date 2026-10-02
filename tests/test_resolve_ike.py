"""
Resolve (SID_勇将, sincronía de Ike): Def/Res +5 mientras HP <= 75 % (Resolve+: +7).
Es un bono de stats con condición (SyncCondition → SID_勇将_効果), y el juego lo enseña en
la pantalla de estado ("Emblem +5": Res 8 → 13 tras recibir daño). Por eso:
  - el modal envía los stats tal cual los muestra el juego, y se guardan sin el bono;
  - la ficha (como_dict) y el combate lo suman mientras se cumple la condición.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app, tablero  # noqa: E402
from motor_calculo import CalculadoraEngage, Terreno  # noqa: E402

STATS = {"hp": 40, "hp_max": 40, "fuerza": 15, "magia": 5, "destreza": 15, "velocidad": 12,
         "defensa": 10, "resistencia": 8, "suerte": 8, "complexion": 8}


class _BaseResolve(unittest.TestCase):

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
        r = self.client.post("/api/unidad/guardar", json={
            "nombre": "Bandido", "clase_nombre": "Barbarian", "es_aliado": False, "x": 6, "y": 10, "nivel": 10,
            "arma_nombre": "Steel Axe", "inventario": [{"arma": "Steel Axe", "equipada": True}]})
        self.assertEqual(r.status_code, 200, r.get_json())

    def _ike(self, hp, defensa, res, vinculo=1):
        stats = dict(STATS, defensa=defensa, resistencia=res)
        r = self.client.post("/api/unidad/guardar", json={
            "nombre": "Timerra", "clase_nombre": "Swordmaster", "es_aliado": True, "x": 6, "y": 9, "nivel": 10,
            "hp_max": 40, "hp_actual": hp, "stats": stats, "emblema_nombre": "Ike", "nivel_vinculo": vinculo,
            "arma_nombre": "Iron Sword", "inventario": [{"arma": "Iron Sword", "equipada": True}]})
        self.assertEqual(r.status_code, 200, r.get_json())
        return tablero.obtener_ficha("Timerra")

    def _daño_recibido(self):
        ike, ene = tablero.obtener_ficha("Timerra"), tablero.obtener_ficha("Bandido")
        r = CalculadoraEngage.simular_combate(ene.stats, ike.stats, ene.arma, ike.arma, Terreno(), Terreno(), 1)
        return r["atacante"]["daño_por_golpe"]



class TestResolve(_BaseResolve):

    def test_con_hp_alto_no_hay_bono(self):
        f = self._ike(40, 10, 8)
        d = f.como_dict()
        self.assertEqual((d["stats"]["defensa"], d["stats"]["resistencia"]), (10, 8))
        self.assertEqual([b["activo"] for b in d["bonos_condicionales"]], [False])
        self.assertEqual(max(d["bonos_condicionales"][0]["hp_activos"]), 30, "75 % de 40")

    def test_valores_del_juego_con_el_bono(self):
        # Con 30/40 el juego enseña Def 15 / Res 13 ("Emblem +5"): se guardan 10 / 8
        f = self._ike(30, 15, 13)
        self.assertEqual((f.stats.defensa, f.stats.resistencia), (10, 8))
        d = f.como_dict()
        self.assertEqual((d["stats"]["defensa"], d["stats"]["resistencia"]), (15, 13))
        self.assertTrue(d["bonos_condicionales"][0]["activo"])
        # y volver a guardar lo que enseña el modal no lo acumula
        f = self._ike(30, d["stats"]["defensa"], d["stats"]["resistencia"])
        self.assertEqual((f.stats.defensa, f.stats.resistencia), (10, 8))

    def test_el_combate_lo_suma_segun_el_hp(self):
        self._ike(40, 10, 8)
        sin_bono = self._daño_recibido()
        f = tablero.obtener_ficha("Timerra")
        f.sincronizar_hp(30)
        self.assertEqual(self._daño_recibido(), max(0, sin_bono - 5))

    def test_resolve_plus_sustituye_a_resolve(self):
        f = self._ike(30, 17, 15, vinculo=20)
        bonos = f.como_dict()["bonos_condicionales"]
        self.assertEqual([b["stat_boosts"] for b in bonos], [{"def": 7, "res": 7}])
        self.assertEqual((f.stats.defensa, f.stats.resistencia), (10, 8))


class TestEstadosTemporalesEnPantalla(_BaseResolve):
    """Self-Improver (Fue +2 al esperar, hasta el siguiente turno) se ve igual que Resolve
    en la pantalla de estado: sumado mientras dura (verificado en juego)."""

    def test_self_improver_se_ve_sumado_y_se_guarda_sin_el(self):
        import pasivas_temporales
        r = self.client.post("/api/unidad/guardar", json={
            "nombre": "Alfred", "clase_nombre": "Avenir", "es_aliado": True, "x": 5, "y": 9, "nivel": 10,
            "hp_max": 40, "hp_actual": 40, "stats": dict(STATS, fuerza=15),
            "arma_nombre": "Iron Lance", "inventario": [{"arma": "Iron Lance", "equipada": True}]})
        self.assertEqual(r.status_code, 200, r.get_json())
        alfred = tablero.obtener_ficha("Alfred")
        if not pasivas_temporales.al_esperar(tablero, alfred):
            self.skipTest("Alfred sin Self-Improver en el catálogo")
        d = alfred.como_dict()
        self.assertEqual(d["stats"]["fuerza"], 17)
        # el modal reenvía lo que enseña (17): se guarda 15, sin acumular
        r = self.client.post("/api/unidad/guardar", json={
            "nombre": "Alfred", "clase_nombre": "Avenir", "es_aliado": True, "x": 5, "y": 9, "nivel": 10,
            "hp_max": 40, "hp_actual": 40, "stats": dict(STATS, fuerza=d["stats"]["fuerza"]),
            "arma_nombre": "Iron Lance", "inventario": [{"arma": "Iron Lance", "equipada": True}]})
        alfred = tablero.obtener_ficha("Alfred")
        self.assertEqual(alfred.stats.fuerza, 15)
        self.assertEqual(alfred.como_dict()["stats"]["fuerza"], 17)
        # al acabar el estado vuelve a 15
        alfred.estados_temporales = []
        self.assertEqual(alfred.como_dict()["stats"]["fuerza"], 15)


if __name__ == "__main__":
    unittest.main()
