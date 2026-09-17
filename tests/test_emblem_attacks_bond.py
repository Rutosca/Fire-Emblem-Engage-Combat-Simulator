"""
Tests unitarios para las mecánicas de Emblemas:
1. Armas disponibles según nivel de vínculo (Louis y Sigurd).
2. Distinción explícita entre armas de Emblema vs normales (ej. Ridersbane vs Ridersbane (Emblema)).
3. Cálculo exacto del daño de Warp Ragnarök (18 de daño con Resonancia).
4. Clasificación de ataques de Emblema en arma fija vs arma variable.
"""

import unittest
from motor_calculo import CalculadoraEngage, Unidad, Arma, Terreno
from catalogo_loader import resolver_unidad_con_catalogo, ATAQUES_ENGAGE_CONFIG
from motor_analisis import _armas_aliado


class TestEmblemAttacksAndBond(unittest.TestCase):

    def test_01_louis_sigurd_bond_level_weapon_restriction(self):
        """Louis con Sigurd a nivel de vínculo 1 no debe tener Brave Lance."""
        louis_data = {
            "nombre": "Louis",
            "nivel": 7,
            "clase_nombre": "Lance Armor",
            "emblema_nombre": "Sigurd",
            "nivel_vinculo": 1,
            "energia_emblema": 6,
            "max_energia_emblema": 6,
            "en_fusion": False,
            "inventario": [
                {"arma": "Ridersbane", "equipada": True, "mt": 8, "tipo": "Lanza"},
                {"arma": "Poción", "equipada": False, "tipo": "Objeto"}
            ]
        }
        louis_ficha = resolver_unidad_con_catalogo(louis_data)
        armas_disponibles = _armas_aliado(louis_ficha)
        nombres = [a.nombre for a, _, _ in armas_disponibles]

        # Ridersbane normal y Ridersbane (Emblema) deben estar presentes
        self.assertIn("Ridersbane", nombres, "Louis debe tener su Ridersbane normal de inventario")
        self.assertIn("Ridersbane (Emblema)", nombres, "Louis a vínculo 1 debe desbloquear Ridersbane (Emblema)")

        # Brave Lance NO debe estar disponible a vínculo 1
        for n in nombres:
            self.assertNotIn("brave lance", n.lower(), f"Brave Lance no debe estar disponible a vínculo 1: {n}")
            self.assertNotIn("lanza del valor", n.lower())

        # Para Override, sólo deben generarse opciones para armas usables disponibles
        nombres_override = [a.nombre for a, _, _ in armas_disponibles if getattr(a, "es_engage_attack", False)]
        self.assertIn("Override (Ridersbane)", nombres_override)
        self.assertIn("Override (Ridersbane (Emblema))", nombres_override)
        for no in nombres_override:
            self.assertNotIn("brave", no.lower(), f"Override no debe usar Brave Lance a vínculo 1: {no}")

    def test_02_louis_sigurd_bond_level_10_unlocks_brave_lance(self):
        """Al alcanzar nivel de vínculo 10, Brave Lance (Emblema) sí debe estar disponible."""
        louis_data_lv10 = {
            "nombre": "Louis",
            "nivel": 10,
            "clase_nombre": "Lance Armor",
            "emblema_nombre": "Sigurd",
            "nivel_vinculo": 10,
            "energia_emblema": 6,
            "max_energia_emblema": 6,
            "en_fusion": True,
            "turnos_fusion": 3,
            "inventario": [
                {"arma": "Ridersbane", "equipada": True, "mt": 8, "tipo": "Lanza"}
            ]
        }
        louis_ficha = resolver_unidad_con_catalogo(louis_data_lv10)
        armas_disponibles = _armas_aliado(louis_ficha)
        nombres = [a.nombre for a, _, _ in armas_disponibles]

        self.assertTrue(any("Brave Lance" in n for n in nombres), "A vínculo 10 debe aparecer Brave Lance (Emblema)")
        nombres_override = [a.nombre for a, _, _ in armas_disponibles if getattr(a, "es_engage_attack", False)]
        self.assertTrue(any("Brave Lance" in n for n in nombres_override), "Override debe poder ejecutarse con Brave Lance a vínculo 10")

    def test_03_warp_ragnarok_exact_18_damage(self):
        """
        Céline (Noble Mística, Mag 16) con tomo Ragnarök (Mt 15) y pasiva Resonancia
        (+2 ATK) contra Hortensia (Res 18): 16 + 15 + 2 - 18 = 15, y el bono de estilo
        Místico de Warp Ragnarök (威力 * 1.2) lo eleva a 18, que es lo observado en el juego.
        """
        celine = Unidad(
            nombre="Céline",
            hp=21,
            magia=16,
            fuerza=11,
            velocidad=12,
            destreza=11,
            defensa=7,
            resistencia=12,
            suerte=15,
            complexion=4,
            habilidades=["Resonance", "Holy Stance", "Favorite Food"],
            emblema_nombre="Celica",
            estilo_combate="魔法スタイル",
        )
        hortensia = Unidad(
            nombre="Hortensia (Boss)",
            hp=25,
            resistencia=18,
            defensa=13,
            velocidad=18,
            habilidades=["Veteran+", "Big Personality"]
        )

        # Arma fija Warp Ragnarök generada canónicamente
        warp_ragnarok = Arma(
            nombre="Warp Ragnarök",
            mt=15,
            hit=100,
            crit=0,
            wt=5,
            tipo="Tomo",
            es_magica=True,
            rango=[1]
        )
        setattr(warp_ragnarok, "es_engage_attack", True)
        setattr(warp_ragnarok, "engage_attack_nombre", "Warp Ragnarök")

        res = CalculadoraEngage.simular_combate(
            atacante=celine,
            defensor=hortensia,
            arma_atk=warp_ragnarok,
            arma_def=None,
            terreno_atk=Terreno(),
            terreno_def=Terreno(),
            distancia=1
        )

        dano_por_golpe = res["atacante"]["daño_por_golpe"]
        self.assertEqual(dano_por_golpe, 18, f"El daño de Warp Ragnarök debe ser 18, pero fue {dano_por_golpe}")
        self.assertIn("Resonancia (+2 ATK, 1 recoil)", res["resultado"]["pasivas_activas"])
        self.assertIn("Ragnarök Fusión (Ataque de Emblema Celica)", res["resultado"]["pasivas_activas"])
        self.assertIn("Estilo Místico (Warp Ragnarök ×1.2 daño)", res["resultado"]["pasivas_activas"])

        # Sin estilo Místico (p.ej. Alear con Celica) no hay x1.2: se queda en 15
        celine.estilo_combate = "Infantería"
        res_no_mistico = CalculadoraEngage.simular_combate(
            atacante=celine, defensor=hortensia, arma_atk=warp_ragnarok, arma_def=None,
            terreno_atk=Terreno(), terreno_def=Terreno(), distancia=1
        )
        self.assertEqual(res_no_mistico["atacante"]["daño_por_golpe"], 15)

    def test_04_fixed_vs_variable_emblem_attacks(self):
        """Verifica la distinción entre técnicas de arma fija y arma variable."""
        self.assertTrue(ATAQUES_ENGAGE_CONFIG["Override"]["es_variable"])
        self.assertIn("Lanza", ATAQUES_ENGAGE_CONFIG["Override"]["tipos_permitidos"])
        self.assertIn("Espada", ATAQUES_ENGAGE_CONFIG["Override"]["tipos_permitidos"])

        self.assertTrue(ATAQUES_ENGAGE_CONFIG["Lodestar Rush"]["es_variable"])
        self.assertEqual(ATAQUES_ENGAGE_CONFIG["Lodestar Rush"]["tipos_permitidos"], ["Espada"])

        self.assertFalse(ATAQUES_ENGAGE_CONFIG["Warp Ragnarök"]["es_variable"])
        self.assertEqual(ATAQUES_ENGAGE_CONFIG["Warp Ragnarök"]["arma_fija"]["mt"], 15)
        self.assertEqual(ATAQUES_ENGAGE_CONFIG["Warp Ragnarök"]["arma_fija"]["tipo"], "Tomo")

        self.assertFalse(ATAQUES_ENGAGE_CONFIG["Houses Unite"]["es_variable"])
        self.assertEqual(ATAQUES_ENGAGE_CONFIG["Houses Unite"]["arma_fija"]["mt"], 19)

        self.assertFalse(ATAQUES_ENGAGE_CONFIG["Astra Storm"]["es_variable"])
        self.assertEqual(ATAQUES_ENGAGE_CONFIG["Astra Storm"]["arma_fija"]["mt"], 16)


if __name__ == "__main__":
    unittest.main()
