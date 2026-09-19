"""
Mecánicas del motor de combate (motor_calculo.simular_combate / evaluar_riesgo)
que no son números observados en el juego: piedras resurrectoras, contraataque
por rango, kill con crítico, suma de chain attacks en /api/combate/ejecutar.
Los números verificados en partida viven en test_ground_truth_cap7.py.

Origen: tests/test_fixes_tactical.py (partido por dominio el 2026-09-18).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import app, tablero, resolver_unidad_con_catalogo  # noqa: E402
from motor_calculo import CalculadoraEngage, Terreno, Unidad, Arma  # noqa: E402


class TestCombateMecanicas(unittest.TestCase):

    def setUp(self):
        # resolver_unidad_con_catalogo lee app.tablero para heredar estado: empezar siempre limpio
        tablero.limpiar()

    def test_piedra_resurrectora_corta_ronda_y_no_transfiere_exceso(self):
        """Romper una barra con piedra corta la ronda y restaura la siguiente."""
        atacante = Unidad(nombre='Atacante', hp=30, fuerza=10, destreza=20, velocidad=20,
                          defensa=5, resistencia=5, suerte=0, complexion=5)
        defensor = Unidad(nombre='Hortensia', hp=10, fuerza=1, destreza=1, velocidad=1,
                          defensa=5, resistencia=5, suerte=0, complexion=5, hp_max=10)
        defensor.hp_stock = 1
        espada = Arma(nombre='Espada', mt=5, wt=0, hit=100, crit=0, es_magica=False, tipo='Espada', rango=[1])
        tomo = Arma(nombre='Tomo', mt=1, wt=0, hit=0, crit=0, es_magica=True, tipo='Tomo', rango=[1])

        comb = CalculadoraEngage.simular_combate(
            atacante, defensor, espada, tomo, Terreno(0, 0), Terreno(0, 0), distancia=1
        )
        self.assertTrue(comb['resultado']['piedra_resurrectora_consumida'])
        self.assertEqual(comb['atacante']['golpes_en_ronda'], 1)
        self.assertEqual(comb['atacante']['daño_total_ronda'], 10)
        self.assertEqual(comb['resultado']['hp_defensor_final'], 10)
        self.assertFalse(comb['resultado']['atacante_mata'])
    def test_contraataque_por_rango_jabalina_tomos_arcos(self):
        """
        Verificación estricta de las mecánicas canónicas de contraataque:
        1. Jabalina (Javelin): contraataca a distancia 1 y a distancia 2 (rango [1, 2]), pero NO a distancia 3.
        2. Tomos (Fire): contraataca a distancia 1 y a distancia 2 (rango [1, 2]), pero NO a distancia 3.
        3. Arcos (Bows):
           - No pueden atacar a distancia 1 (ValueError).
           - No pueden contraatacar a distancia 1 (puede_contraatacar = False).
           - SÍ pueden atacar y contraatacar a distancia 2 (puede_contraatacar = True).
        """
        # Unidades base
        chloe = Unidad(nombre="Chloé", hp=28, fuerza=12, velocidad=15, defensa=8, resistencia=10)
        diamant = Unidad(nombre="Diamant", hp=30, fuerza=13, velocidad=13, defensa=10, resistencia=5)
        etie = Unidad(nombre="Etie", hp=22, fuerza=14, velocidad=10, defensa=4, resistencia=3)
        mage = Unidad(nombre="Mage", hp=20, fuerza=2, magia=12, velocidad=8, defensa=3, resistencia=8)

        # Armas resueltas canónicamente
        javelin = Arma(nombre="Javelin", mt=6, tipo="Lanza")
        iron_sword = Arma(nombre="Iron Sword", mt=5, tipo="Espada")
        iron_bow = Arma(nombre="Iron Bow", mt=6, tipo="Arco")
        fire = Arma(nombre="Fire", mt=5, tipo="Tomo", es_magica=True)
        longbow = Arma(nombre="Longbow", mt=7, tipo="Arco")

        # Verificar rangos inferidos canónicamente
        self.assertEqual(javelin.rango, [1, 2], "Javelin debe tener rango [1, 2]")
        self.assertEqual(fire.rango, [1, 2], "Fire debe tener rango [1, 2]")
        self.assertEqual(iron_bow.rango, [2], "Iron Bow debe tener rango estrictamente [2] (NUNCA [1])")
        self.assertEqual(longbow.rango, [2, 3], "Longbow debe tener rango [2, 3]")
        self.assertEqual(iron_sword.rango, [1], "Iron Sword debe tener rango [1]")

        # ── 1. JAVELIN ──
        # Diamant ataca a Chloé (Javelin) a distancia 1 (con Iron Sword)
        c_jav_d1 = CalculadoraEngage.simular_combate(diamant, chloe, iron_sword, javelin, Terreno(0,0), Terreno(0,0), distancia=1)
        self.assertTrue(c_jav_d1["defensor"]["puede_contraatacar"], "Unidad con Javelin SÍ debe contraatacar a distancia 1")

        # Etie ataca a Chloé (Javelin) a distancia 2 (con Iron Bow)
        c_jav_d2 = CalculadoraEngage.simular_combate(etie, chloe, iron_bow, javelin, Terreno(0,0), Terreno(0,0), distancia=2)
        self.assertTrue(c_jav_d2["defensor"]["puede_contraatacar"], "Unidad con Javelin SÍ debe contraatacar a distancia 2")

        # Etie ataca a Chloé (Javelin) a distancia 3 (con Longbow)
        c_jav_d3 = CalculadoraEngage.simular_combate(etie, chloe, longbow, javelin, Terreno(0,0), Terreno(0,0), distancia=3)
        self.assertFalse(c_jav_d3["defensor"]["puede_contraatacar"], "Unidad con Javelin NO puede contraatacar a distancia 3")

        # ── 2. TOMOS (FIRE) ──
        # Diamant ataca a Mage (Fire) a distancia 1 (con Iron Sword)
        c_fire_d1 = CalculadoraEngage.simular_combate(diamant, mage, iron_sword, fire, Terreno(0,0), Terreno(0,0), distancia=1)
        self.assertTrue(c_fire_d1["defensor"]["puede_contraatacar"], "Unidad con Tomo SÍ debe contraatacar a distancia 1")

        # Etie ataca a Mage (Fire) a distancia 2 (con Iron Bow)
        c_fire_d2 = CalculadoraEngage.simular_combate(etie, mage, iron_bow, fire, Terreno(0,0), Terreno(0,0), distancia=2)
        self.assertTrue(c_fire_d2["defensor"]["puede_contraatacar"], "Unidad con Tomo SÍ debe contraatacar a distancia 2")

        # Etie ataca a Mage (Fire) a distancia 3 (con Longbow)
        c_fire_d3 = CalculadoraEngage.simular_combate(etie, mage, longbow, fire, Terreno(0,0), Terreno(0,0), distancia=3)
        self.assertFalse(c_fire_d3["defensor"]["puede_contraatacar"], "Unidad con Tomo estándar NO puede contraatacar a distancia 3")

        # ── 3. ARCOS (BOWS) ──
        # Intento de atacar a distancia 1 con Iron Bow -> debe lanzar ValueError
        with self.assertRaises(ValueError):
            CalculadoraEngage.simular_combate(etie, diamant, iron_bow, iron_sword, Terreno(0,0), Terreno(0,0), distancia=1)

        # Ataque a distancia 2 con Iron Bow -> válido
        c_bow_d2 = CalculadoraEngage.simular_combate(etie, diamant, iron_bow, iron_sword, Terreno(0,0), Terreno(0,0), distancia=2)
        self.assertFalse(c_bow_d2["defensor"]["puede_contraatacar"], "Diamant con Iron Sword (rango 1) no puede contraatacar a distancia 2")

        # Diamant ataca a Etie (con Iron Bow) a distancia 1
        c_vs_bow_d1 = CalculadoraEngage.simular_combate(diamant, etie, iron_sword, iron_bow, Terreno(0,0), Terreno(0,0), distancia=1)
        self.assertFalse(c_vs_bow_d1["defensor"]["puede_contraatacar"], "Arquero con Iron Bow NO PUEDE contraatacar a distancia 1")

        # Chloé ataca a Etie (con Iron Bow) a distancia 2 (con Javelin)
        c_vs_bow_d2 = CalculadoraEngage.simular_combate(chloe, etie, javelin, iron_bow, Terreno(0,0), Terreno(0,0), distancia=2)
        self.assertTrue(c_vs_bow_d2["defensor"]["puede_contraatacar"], "Arquero con Iron Bow SÍ debe contraatacar a distancia 2")

    def test_kill_con_critico_requiere_prob_critico_positiva(self):
        """
        CalculadoraEngage.evaluar_riesgo solo debe marcar kill_con_critico=True
        si la probabilidad de crítico es estrictamente mayor a 0%.
        """
        chloe = Unidad("Chloé", hp=22, fuerza=12, magia=0, destreza=12, velocidad=14, defensa=6, resistencia=8, suerte=10, complexion=5, tipo_movimiento="volador")
        archer = Unidad("Archer", hp=24, fuerza=9, magia=0, destreza=10, velocidad=9, defensa=6, resistencia=2, suerte=6, complexion=6, tipo_movimiento="infanteria")
        arma_atk = Arma("Lanza", mt=5, wt=5, hit=100, crit=0, tipo="Lanza", rango=[1])
        arma_def = Arma("Arco", mt=6, wt=5, hit=80, crit=0, tipo="Arco", rango=[2])

        v = CalculadoraEngage.evaluar_riesgo(chloe, archer, arma_atk, arma_def, Terreno(), Terreno(), distancia=1, perfil="seguro")
        self.assertFalse(v["veredicto"]["kill_con_critico"], "Con 0% crit, kill_con_critico debe ser False")

    def test_chain_attack_se_suma_y_aplica_en_api_combate(self):
        """El ataque en cadena debe sumarse en golpe_txt y aplicarse al HP del defensor en /api/combate/ejecutar."""
        tablero.limpiar()
        ene = resolver_unidad_con_catalogo({
            "nombre": "Lance Fighter (ChainTest)", "x": 5, "y": 6, "mov": 4, "es_aliado": False,
            "arma_nombre": "Iron Lance", "stats": {"hp": 25, "hp_max": 25, "defensa": 8}
        })
        tablero.registrar_unidad(ene)

        alear = resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 5, "y": 5, "mov": 4, "es_aliado": True,
            "arma_nombre": "Liberation", "stats": {"hp": 25, "fuerza": 12, "velocidad": 10, "estilo_combate": "Dragon"}
        })
        tablero.registrar_unidad(alear)

        lapis = resolver_unidad_con_catalogo({
            "nombre": "Lapis", "x": 4, "y": 6, "mov": 4, "es_aliado": True,
            "clase_nombre": "Sword Fighter", "arma_nombre": "Iron Sword",
            "stats": {"hp": 22, "fuerza": 11, "velocidad": 14, "estilo_combate": "De apoyo"}
        })
        tablero.registrar_unidad(lapis)

        client = app.test_client()

        # 1. En /api/analizar, golpe_txt debe incluir Chain Attack sumado
        res_an = client.post("/api/analizar", json={"perfil": "seguro"})
        self.assertEqual(res_an.status_code, 200)
        data_an = res_an.get_json()
        op_alear = [r for r in data_an["resultados"] if r.get("aliado") == "Alear"][0]
        self.assertIn("Chain Attack", op_alear["recomendacion"])
        self.assertEqual(len(op_alear["chain_attacks"]), 1)
        self.assertEqual(op_alear["chain_attacks"][0]["daño"], 2)

        # 2. En /api/combate/ejecutar, el Chain Attack debe reducir el HP del enemigo (25 - 20 - 2 = 3)
        res_ex = client.post("/api/combate/ejecutar", json={
            "atacante": "Alear",
            "defensor": "Lance Fighter (ChainTest)",
            "arma_nombre": "Liberation",
            "pos_destino": [5, 5]
        })
        self.assertEqual(res_ex.status_code, 200)
        data_ex = res_ex.get_json()
        self.assertEqual(data_ex["defensor"]["hp_actual"], 3)
        self.assertEqual(data_ex["combate"]["resultado"]["chain_attacks_daño"], 2)

if __name__ == "__main__":
    unittest.main()
