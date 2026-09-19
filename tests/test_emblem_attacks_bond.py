"""
Tests unitarios para las mecánicas de Emblemas:
1. Armas disponibles según nivel de vínculo (Louis y Sigurd).
2. Distinción explícita entre armas de Emblema vs normales (ej. Ridersbane vs Ridersbane (Emblema)).
3. Clasificación de ataques de Emblema en arma fija vs arma variable.
"""

import unittest
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
