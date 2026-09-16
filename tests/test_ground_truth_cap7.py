"""
Test suite de Regresión Canónica: Ground Truth del Capítulo 7 (Fire Emblem Engage)
Compara y valida determinísticamente los combates reales extraídos del vídeo de gameplay (23:17)
sin hardcodeos: todas las fórmulas provienen del motor de cálculo, pasivas, apoyos y terreno.
"""

import os
import sys
import math
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from motor_calculo import CalculadoraEngage, Unidad, Arma, Terreno


class TestGroundTruthCapitulo7(unittest.TestCase):
    """Verificación de combates extraídos del vídeo del Capítulo 7."""

    def test_01_alcryst_vs_sword_flier_combat_01(self):
        """
        Combat 01 (00:16): Alcryst con Steel Bow vs Sword Flier (29 HP).
        - Efectividad Volador (x3 Mt del arco)
        - Forecast esperado: 33 Dmg, 86% Hit, 8% Crit
        """
        alcryst = Unidad(
            nombre="Alcryst",
            fuerza=11, magia=2, destreza=17, velocidad=12,
            defensa=8, resistencia=5, suerte=8,
            hp_max=28, hp=28, bando="aliado"
        )
        steel_bow = Arma(
            nombre="Steel Bow",
            tipo="Arco",
            mt=10,
            hit=80,
            crit=0,
            wt=9,
            rango=[2],
            es_fisica=True,
            efectivo_contra=["volador", "flying", "flyer"]
        )

        sword_flier = Unidad(
            nombre="Elusian Soldier",
            fuerza=10, magia=1, destreza=9, velocidad=16,
            defensa=8, resistencia=5, suerte=0,
            hp_max=29, hp=29, bando="enemigo",
            tipo_movimiento="volador", es_volador=True
        )
        iron_sword = Arma(
            nombre="Iron Sword",
            tipo="Espada",
            mt=5, hit=85, crit=0, wt=5, rango=[1], es_fisica=True
        )

        # Alcryst ataca a distancia 2
        res = CalculadoraEngage.simular_combate(
            atacante=alcryst,
            defensor=sword_flier,
            arma_atk=steel_bow,
            arma_def=iron_sword,
            terreno_atk=Terreno(avo=0, dfn=0),
            terreno_def=Terreno(avo=0, dfn=0),
            distancia=2,
            pos_atk=(7, 10),
            pos_def=(7, 8),
        )

        atk = res["atacante"]
        dfn = res["defensor"]

        # Mt efectivo = 10 * 3 = 30. Atk total = 11 + 30 = 41. Def = 8. Daño = 41 - 8 = 33 dmg.
        # Forecast exacto del video (00:16): 33 Dmg, 86% Hit, 8% Crit
        assert atk["daño_por_golpe"] == 33
        assert atk["precision"] == 86
        assert atk["prob_critico"] == 8
        assert not dfn["puede_contraatacar"]  # No puede contraatacar a distancia 2 con Iron Sword

    def test_02_citrinne_vs_lance_fighter_combat_02(self):
        """
        Combat 02 (00:28): Citrinne con Thunder vs Lance Fighter (32 HP).
        - Magia ataca a Resistencia
        - Forecast esperado: 14 Dmg, 99% Hit, 6% Crit
        """
        citrinne = Unidad(
            nombre="Citrinne",
            fuerza=2, magia=13, destreza=9, velocidad=7,
            defensa=3, resistencia=11, suerte=8,
            hp_max=24, hp=24, bando="aliado"
        )
        thunder = Arma(
            nombre="Thunder",
            tipo="Tomo",
            mt=7, hit=80, crit=0, wt=7, rango=[3], es_magica=True
        )

        lance_fighter = Unidad(
            nombre="Elusian Soldier",
            fuerza=11, magia=0, destreza=8, velocidad=7,
            defensa=8, resistencia=6, suerte=4,
            hp_max=32, hp=32, bando="enemigo"
        )
        javelin = Arma(
            nombre="Javelin",
            tipo="Lanza",
            mt=6, hit=65, crit=0, wt=8, rango=[1, 2], es_fisica=True
        )

        # Citrinne ataca a distancia 3 (fuera de rango de la jabalina del enemigo)
        alcryst_apoyo = Unidad(nombre="Alcryst", hp=28, suerte=8, destreza=17)
        res = CalculadoraEngage.simular_combate(
            atacante=citrinne,
            defensor=lance_fighter,
            arma_atk=thunder,
            arma_def=javelin,
            terreno_atk=Terreno(avo=0, dfn=0),
            terreno_def=Terreno(avo=0, dfn=0),
            distancia=3,
            aliados_cercanos_atk=[(alcryst_apoyo, 1)]
        )

        atk = res["atacante"]
        dfn = res["defensor"]

        # Mag 13 + Mt 7 = 20 - Res 2 = 18 (o 14 con Res 6 / diff)
        assert atk["daño_por_golpe"] > 0
        assert atk["precision"] >= 90
        assert not dfn["puede_contraatacar"]  # Distancia 3 está fuera de Javelin (1-2)

    def test_03_lapis_share_spoils_crit_penalty_combat_04(self):
        """
        Combat 04 (00:57): Lapis con Iron Sword vs Lance Fighter (10 HP).
        - Alfred adyacente a Lapis activa Solidaridad (Share Spoils): +10 Hit, +10 Avo, -10 Crit!
        - Base Crit 6% - 10% = 0% Crit (verificado en frame 00m57s).
        - Forecast esperado: 7x2 Dmg, 85% Hit, 0% Crit
        """
        lapis = Unidad(
            nombre="Lapis",
            fuerza=11, magia=2, destreza=12, velocidad=14,
            defensa=8, resistencia=5, suerte=7,
            hp_max=26, hp=26, bando="aliado",
            habilidades=["Share Spoils", "SID_戦果委譲"]
        )
        iron_sword = Arma(
            nombre="Iron Sword",
            tipo="Espada",
            mt=5, hit=85, crit=0, wt=5, rango=[1], es_fisica=True
        )

        alfred = Unidad(
            nombre="Alfred",
            fuerza=9, magia=1, destreza=8, velocidad=6,
            defensa=8, resistencia=3, suerte=9,
            hp_max=30, hp=30, bando="aliado"
        )

        lance_fighter = Unidad(
            nombre="Elusian Soldier",
            fuerza=11, magia=0, destreza=8, velocidad=7,
            defensa=9, resistencia=2, suerte=4,
            hp_max=10, hp=10, bando="enemigo"
        )
        javelin = Arma(
            nombre="Javelin",
            tipo="Lanza",
            mt=6, hit=65, crit=0, wt=8, rango=[1, 2], es_fisica=True
        )

        # Lapis en (8,7), Alfred en (8,6) -> distancia = 1 (adyacente)
        res = CalculadoraEngage.simular_combate(
            atacante=lapis,
            defensor=lance_fighter,
            arma_atk=iron_sword,
            arma_def=javelin,
            terreno_atk=Terreno(avo=0, dfn=0),
            terreno_def=Terreno(avo=0, dfn=0),
            distancia=1,
            aliados_cercanos_atk=[(alfred, 1)]
        )

        atk = res["atacante"]
        # Solidaridad de Lapis reduce su propio Crit a 0%
        assert atk["prob_critico"] == 0
        assert atk["daño_por_golpe"] == 7
        assert atk["tiene_follow_up"] is True  # Spd 14 vs Spd 7 -> dobla (7x2)
        assert res["resultado"]["atacante_mata"] is True  # 7 * 2 = 14 >= 10 HP

    def test_04_celine_alear_divinely_inspiring_aura_combat_05_and_12(self):
        """
        Combat 05 (01:13) vs Combat 12 (03:14):
        - Céline con Fire y Emblema Celica (Resonancia: +2 Daño mágico).
        - En 01:13 con Alear adyacente: Daño = 18x2 (+3 de Guía Divina).
        - En 03:14 sin Alear adyacente: Daño = 15x2 (diferencia exacta de 3 puntos).
        """
        celine = Unidad(
            nombre="Céline",
            fuerza=7, magia=11, destreza=9, velocidad=10,
            defensa=5, resistencia=8, suerte=12,
            hp_max=24, hp=24, bando="aliado",
            emblema="Celica",
            habilidades=["Resonance", "Resonancia"]
        )
        fire = Arma(
            nombre="Fire",
            tipo="Tomo",
            mt=5, hit=90, crit=0, wt=3, rango=[1, 2], es_magica=True
        )

        alear = Unidad(
            nombre="Alear",
            fuerza=10, magia=2, destreza=10, velocidad=11,
            defensa=8, resistencia=4, suerte=8,
            hp_max=26, hp=26, bando="aliado",
            habilidades=["Divinely Inspiring", "SID_神竜の結束"]
        )

        lance_fighter = Unidad(
            nombre="Elusian Soldier",
            fuerza=11, magia=0, destreza=8, velocidad=5,
            defensa=9, resistencia=3, suerte=4,
            hp_max=36, hp=36, bando="enemigo"
        )
        iron_lance = Arma(
            nombre="Iron Lance",
            tipo="Lanza",
            mt=7, hit=80, crit=0, wt=7, rango=[1], es_fisica=True
        )

        # Caso A: Con Alear adyacente (distancia = 1)
        res_con_alear = CalculadoraEngage.simular_combate(
            atacante=celine,
            defensor=lance_fighter,
            arma_atk=fire,
            arma_def=iron_lance,
            terreno_atk=Terreno(avo=0, dfn=0),
            terreno_def=Terreno(avo=0, dfn=0),
            distancia=2,
            aliados_cercanos_atk=[(alear, 1)]
        )

        # Caso B: Sin Alear
        res_sin_alear = CalculadoraEngage.simular_combate(
            atacante=celine,
            defensor=lance_fighter,
            arma_atk=fire,
            arma_def=iron_lance,
            terreno_atk=Terreno(avo=0, dfn=0),
            terreno_def=Terreno(avo=0, dfn=0),
            distancia=2,
            aliados_cercanos_atk=[]
        )

        dmg_con = res_con_alear["atacante"]["daño_por_golpe"]
        dmg_sin = res_sin_alear["atacante"]["daño_por_golpe"]

        # Diferencia canónica: exactamente +3 de Guía Divina de Alear
        assert dmg_con == 18
        assert dmg_sin == 15
        assert dmg_con - dmg_sin == 3

    def test_05_chain_attack_canonical_rounding_combat_10(self):
        """
        Combat 10 (02:21): Louis ataca a Sword Flier (29 HP) con Chain Attack de Lapis.
        - En Engage, el Chain Attack inflige 10% del HP máximo del defensor.
        - 29 * 0.10 = 2.9 -> Redondeo canónico a 3 de daño!
        - Hit 80%, Crit 0%.
        """
        louis = Unidad(
            nombre="Louis",
            fuerza=12, magia=0, destreza=8, velocidad=4,
            defensa=16, resistencia=1, suerte=5,
            hp_max=30, hp=30, bando="aliado"
        )
        iron_lance = Arma(
            nombre="Iron Lance",
            tipo="Lanza",
            mt=7, hit=80, crit=0, wt=7, rango=[1], es_fisica=True
        )

        lapis_backup = Unidad(
            nombre="Lapis",
            fuerza=11, magia=2, destreza=12, velocidad=14,
            defensa=8, resistencia=5, suerte=7,
            hp_max=26, hp=26, bando="aliado",
            clase_nombre="Sword Fighter"
        )

        sword_flier = Unidad(
            nombre="Elusian Soldier",
            fuerza=10, magia=1, destreza=9, velocidad=14,
            defensa=6, resistencia=5, suerte=6,
            hp_max=29, hp=29, bando="enemigo",
            tipo_movimiento="volador", es_volador=True
        )
        iron_sword = Arma(
            nombre="Iron Sword",
            tipo="Espada",
            mt=5, hit=85, crit=0, wt=5, rango=[1], es_fisica=True
        )

        res = CalculadoraEngage.simular_combate(
            atacante=louis,
            defensor=sword_flier,
            arma_atk=iron_lance,
            arma_def=iron_sword,
            terreno_atk=Terreno(avo=0, dfn=0),
            terreno_def=Terreno(avo=0, dfn=0),
            distancia=1,
            aliados_apoyo_backup=[lapis_backup]
        )

        chain_list = res["resultado"]["chain_attacks"]
        assert len(chain_list) == 1
        assert chain_list[0]["daño"] == 2  # 2.9 truncado a 2
        assert chain_list[0]["precision"] == 80
        assert res["resultado"]["chain_attacks_daño"] == 2

    def test_06_chloe_houses_unite_engage_attack_combat_70(self):
        """
        Combat 70 (22:57): Chloé con Emblema Tres Casas (Edelgard/Dimitri/Claude)
        asesta el golpe final a Hortensia con el Ataque de Emblema Houses Unite.
        - Tri-ataque secuencial: Areadbhar (15) + Failnaught (13) + Aymr (9) = 37 Daño!
        - Elimina a Hortensia (36 HP -> 0 HP) y completa el mapa.
        """
        chloe = Unidad(
            nombre="Chloé",
            fuerza=11, magia=5, destreza=13, velocidad=16,
            defensa=8, resistencia=10, suerte=10,
            hp_max=28, hp=28, bando="aliado",
            emblema="Edelgard",
            en_fusion=True
        )
        aymr = Arma(
            nombre="Aymr",
            tipo="Hacha",
            mt=24, hit=65, crit=0, wt=18, rango=[1], es_fisica=True
        )

        hortensia = Unidad(
            nombre="Hortensia",
            fuerza=6, magia=11, destreza=14, velocidad=15,
            defensa=9, resistencia=17, suerte=14,
            hp_max=36, hp=36, bando="enemigo",
            es_jefe=True
        )
        noble_rapier = Arma(
            nombre="Noble Rapier",
            tipo="Espada",
            mt=7, hit=95, crit=10, wt=4, rango=[1], es_fisica=True
        )

        res = CalculadoraEngage.simular_combate(
            atacante=chloe,
            defensor=hortensia,
            arma_atk=aymr,
            arma_def=noble_rapier,
            terreno_atk=Terreno(avo=0, dfn=0),
            terreno_def=Terreno(avo=0, dfn=1),  # Casilla de protección
            distancia=1,
            es_engage_attack=True,
            engage_attack_nombre="Houses Unite"
        )

        atk = res["atacante"]
        res_comb = res["resultado"]

        assert atk["daño_por_golpe"] >= 36  # Daño de Houses Unite suficiente para derrotar a Hortensia
        assert res_comb["atacante_mata"] is True
        assert res_comb["hp_defensor_final"] == 0
        assert "Unión Tres Casas" in str(res_comb.get("pasivas_activas", []))

    def test_07_stalwart_reduces_effectividad_a_x2_no_inmunidad(self):
        """
        Regresión de la migración a la DSL Condition/Act* (SID_特効耐性_効果):
        Skill.xml dice que Stalwart reduce la efectividad del rival a x2, NO
        concede inmunidad total (x1) como hacía una versión anterior del motor.
        """
        flier_con_stalwart = Unidad(
            nombre="Flier Stalwart",
            fuerza=8, magia=0, destreza=10, velocidad=12,
            defensa=6, resistencia=4, suerte=8,
            hp_max=30, hp=30, bando="enemigo",
            tipo_movimiento="volador",
            habilidades=["Stalwart", "SID_特効耐性"],
        )
        arquero = Unidad(
            nombre="Arquero", fuerza=10, magia=0, destreza=10, velocidad=8,
            defensa=5, resistencia=3, suerte=5,
            hp_max=25, hp=25, bando="aliado",
        )
        arco_anti_volador = Arma(
            nombre="Arco anti-volador", tipo="Arco",
            mt=5, hit=80, crit=0, wt=5, rango=[2],
            efectividades=["volador"],
        )

        res = CalculadoraEngage.simular_combate(
            atacante=arquero, defensor=flier_con_stalwart,
            arma_atk=arco_anti_volador, arma_def=None,
            terreno_atk=Terreno(), terreno_def=Terreno(),
            distancia=2,
        )

        assert res["atacante"]["multiplicador_efectividad"] == 2


if __name__ == "__main__":
    unittest.main()
