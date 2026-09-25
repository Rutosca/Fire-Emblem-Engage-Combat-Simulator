# -*- coding: utf-8 -*-
"""
Piedras resurrectoras en ALIADOS. La lógica ya existía para los jefes; lo que faltaba es
que valiera para el bando propio, porque el Ataque de Emblema de Tiki (Divine Blessing)
le da una piedra a un aliado que elijas.

Una piedra es una barra de vida extra: al quedarse a 0 se gasta una, se vuelve con la vida
llena y se sigue peleando. Toda la lógica de combate (ruptura, contraataques, seguimiento)
es igual. Lo que cambia es que el motor tiene que dejar de dar por muerta a la unidad.
"""
import unittest

import catalogo_loader as cl
from app import app, tablero
from motor_calculo import CalculadoraEngage, Terreno

FRAGIL = {"hp": 20, "fuerza": 4, "magia": 12, "destreza": 10, "velocidad": 8,
          "defensa": 4, "resistencia": 6, "suerte": 5, "complexion": 4}
BRUTO = {"hp": 50, "fuerza": 26, "magia": 0, "destreza": 14, "velocidad": 10,
         "defensa": 12, "resistencia": 2, "suerte": 5, "complexion": 9}


def _aliado(piedras, tab=None):
    return cl.resolver_unidad_con_catalogo({
        "nombre": "Fragil", "es_aliado": True, "nivel": 5, "clase_nombre": "Mage",
        "hp_stock": piedras, "stats": dict(FRAGIL),
        "inventario": [{"nombre": "Fire", "equipada": True}], "x": 0, "y": 0}, tablero=tab)


def _enemigo(arma="Steel Bow"):
    return cl.resolver_unidad_con_catalogo({
        "nombre": "Bruto", "es_aliado": False, "nivel": 15, "clase_nombre": "Warrior",
        "stats": dict(BRUTO), "inventario": [{"nombre": arma, "equipada": True}],
        "x": 2, "y": 0}, tablero=None)


class TestAliadoDefendiendo(unittest.TestCase):
    """Ya funcionaba: se comprueba que sigue funcionando para el bando propio."""

    def test_la_piedra_salva_al_aliado_atacado(self):
        bruto = _enemigo("Silver Axe")
        for piedras, muere in ((0, True), (1, False)):
            a = _aliado(piedras)
            r = CalculadoraEngage.simular_combate(
                bruto.stats, a.stats, bruto.arma, a.arma, Terreno(), Terreno(), 1)["resultado"]
            self.assertEqual(r["atacante_mata"], muere, f"{piedras} piedra(s)")
            if not muere:
                self.assertEqual(r["hp_defensor_final"], a.stats.hp_max)
                self.assertIn("piedra_resurrectora", [s["tipo"] for s in r["secuencia"]])


class TestAliadoAtacando(unittest.TestCase):
    """Esto NO estaba: el atacante no gastaba piedras, así que un aliado con barra de
    repuesto figuraba como muerto por el contraataque."""

    def _riesgo(self, piedras):
        a, bruto = _aliado(piedras), _enemigo()
        return CalculadoraEngage.evaluar_riesgo(
            atacante=a.stats, defensor=bruto.stats, arma_atk=a.arma, arma_def=bruto.arma,
            terreno_atk=Terreno(), terreno_def=Terreno(), distancia=2)["veredicto"]

    def test_la_piedra_se_gasta_en_el_contraataque(self):
        a, bruto = _aliado(1), _enemigo()
        r = CalculadoraEngage.simular_combate(
            a.stats, bruto.stats, a.arma, bruto.arma, Terreno(), Terreno(), 2)["resultado"]
        self.assertTrue(r["piedra_atacante_consumida"])
        self.assertEqual(r["hp_atacante_final"], a.stats.hp_max)
        self.assertIn("piedra_resurrectora", [s["tipo"] for s in r["secuencia"]])

    def test_sin_piedra_si_muere(self):
        a, bruto = _aliado(0), _enemigo()
        r = CalculadoraEngage.simular_combate(
            a.stats, bruto.stats, a.arma, bruto.arma, Terreno(), Terreno(), 2)["resultado"]
        self.assertFalse(r["piedra_atacante_consumida"])
        self.assertEqual(r["hp_atacante_final"], 0)

    def test_el_veredicto_deja_de_darla_por_muerta(self):
        self.assertTrue(self._riesgo(0)["atacante_muere_en_contra"])
        self.assertFalse(self._riesgo(1)["atacante_muere_en_contra"], "una barra de repuesto lo salva")

    def test_con_piedras_de_sobra_el_riesgo_baja(self):
        """Con 2 piedras sobrevive al contraataque Y a la fase enemiga."""
        sin = self._riesgo(0)
        con = self._riesgo(2)
        self.assertEqual(sin["nivel_riesgo"], "critico")
        self.assertGreater(sin["prob_muerte_atacante"], con["prob_muerte_atacante"])
        self.assertFalse(con["atacante_muere_en_turno_enemigo"])


class TestEnPartida(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()

    def setUp(self):
        self.client.post("/api/mapa/seleccionar", json={"capitulo": 10})
        for n in list(tablero.fichas):
            tablero.fichas.pop(n)
        self.aliado = _aliado(1, tab=tablero)
        self.aliado.x, self.aliado.y = 3, 3
        tablero.registrar_unidad(self.aliado, resolver_colision=False)

    @classmethod
    def tearDownClass(cls):
        cls.client.post("/api/mapa/seleccionar", json={"capitulo": 7})

    def test_registrar_el_daño_a_mano_gasta_la_piedra(self):
        """En la fase enemiga el jugador apunta el daño recibido: quedarse a 0 con piedra
        no es morir."""
        r = self.client.post("/api/unidad/ajustar_hp",
                             json={"nombre": "Fragil", "hp_actual": 0}).get_json()
        self.assertTrue(r["piedra_resurrectora_gastada"])
        f = tablero.obtener_ficha("Fragil")
        self.assertTrue(f.viva)
        self.assertEqual((f.hp_actual, f.hp_stock), (f.hp_max, 0))

    def test_agotadas_las_piedras_sí_cae(self):
        self.client.post("/api/unidad/ajustar_hp", json={"nombre": "Fragil", "hp_actual": 0})
        r = self.client.post("/api/unidad/ajustar_hp",
                             json={"nombre": "Fragil", "hp_actual": 0}).get_json()
        self.assertFalse(r["piedra_resurrectora_gastada"])
        f = tablero.obtener_ficha("Fragil")
        self.assertFalse(f.viva)
        self.assertEqual(f.hp_actual, 0)

    def test_un_aliado_con_piedras_no_se_confunde_con_un_jefe(self):
        self.assertFalse(self.aliado.como_dict()["es_jefe"])
        self.assertEqual(self.aliado.como_dict()["hp_stock"], 1)


class TestPerderUnaBarraParaElCombate(unittest.TestCase):
    """
    Verdad de juego: **nunca caen dos barras en el mismo combate**. En cuanto la unidad con
    piedras se queda a 0, el combate se para en seco — no hay seguimiento aunque el rival
    doble, ni se toca la barra siguiente.
    """

    def _duelo(self, piedras, jefe_ataca):
        jefe = cl.resolver_unidad_con_catalogo({
            "nombre": "Jefe", "es_aliado": False, "nivel": 10, "clase_nombre": "Axe Fighter",
            "hp_stock": piedras,
            "stats": {"hp": 18, "fuerza": 10, "magia": 0, "destreza": 8, "velocidad": 6,
                      "defensa": 5, "resistencia": 3, "suerte": 4, "complexion": 7},
            "inventario": [{"nombre": "Iron Axe", "equipada": True}], "x": 0, "y": 0}, tablero=None)
        heroe = cl.resolver_unidad_con_catalogo({
            "nombre": "Heroe", "es_aliado": True, "nivel": 20, "clase_nombre": "Swordmaster",
            "stats": {"hp": 45, "fuerza": 30, "magia": 0, "destreza": 25, "velocidad": 25,
                      "defensa": 18, "resistencia": 12, "suerte": 15, "complexion": 8},
            "inventario": [{"nombre": "Silver Sword", "equipada": True}], "x": 1, "y": 0}, tablero=None)
        a, d = (jefe, heroe) if jefe_ataca else (heroe, jefe)
        return jefe, CalculadoraEngage.simular_combate(
            a.stats, d.stats, a.arma, d.arma, Terreno(), Terreno(), 1)["resultado"]

    def test_el_heroe_no_da_seguimiento_tras_quitarle_la_barra(self):
        """Ataca el héroe, que dobla: le quita la barra al jefe y ahí se acaba."""
        jefe, r = self._duelo(1, jefe_ataca=False)
        self.assertEqual([s["tipo"] for s in r["secuencia"]], ["ataque", "piedra_resurrectora"])
        self.assertFalse(r["atacante_mata"], "perder una barra no es morir")
        self.assertEqual(r["hp_defensor_final"], jefe.stats.hp_max, "vuelve con la barra llena")

    def test_tampoco_al_caer_por_el_contraataque(self):
        """Ataca el jefe, el héroe le contraataca y le quita la barra: sin seguimiento."""
        jefe, r = self._duelo(1, jefe_ataca=True)
        self.assertEqual([s["tipo"] for s in r["secuencia"]],
                         ["ataque", "contraataque", "piedra_resurrectora"])
        self.assertEqual(r["hp_atacante_final"], jefe.stats.hp_max)

    def test_sin_piedras_el_combate_sigue_su_curso(self):
        _, r = self._duelo(0, jefe_ataca=False)
        self.assertNotIn("piedra_resurrectora", [s["tipo"] for s in r["secuencia"]])
        self.assertTrue(r["atacante_mata"])



if __name__ == "__main__":
    unittest.main()
