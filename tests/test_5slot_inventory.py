import unittest
from catalogo_loader import resolver_unidad_con_catalogo

class Test5SlotInventory(unittest.TestCase):
    def test_5slot_multiple_weapons_independent_forge_and_engraving(self):
        """Verifica que 5 ranuras guarden armas con forjas y grabados independientes."""
        data_unidad = {
            "nombre": "Louis",
            "clase_nombre": "Lance Armor",
            "nivel": 7,
            "es_aliado": True,
            "inventario": [
                {
                    "nombre": "Iron Lance",
                    "refine_lvl": 1,
                    "grabado": "",
                    "equipada": False
                },
                {
                    "nombre": "Iron Lance",
                    "refine_lvl": 2,
                    "grabado": "Marth",
                    "equipada": True
                },
                {
                    "nombre": "Javelin",
                    "refine_lvl": 0,
                    "grabado": "",
                    "equipada": False
                },
                {
                    "nombre": "Poción",
                    "usos": 2,
                    "usos_max": 3,
                    "equipada": False
                },
                {
                    "nombre": "Heal",
                    "usos": 20,
                    "usos_max": 25,
                    "equipada": False
                }
            ]
        }

        ficha = resolver_unidad_con_catalogo(data_unidad)
        self.assertEqual(len(ficha.inventario), 5)

        # Ranura 0: Iron Lance +1
        slot0 = ficha.inventario[0]
        self.assertEqual(slot0["refine_lvl"], 1)
        self.assertFalse(slot0["equipada"])
        self.assertIn("Iron Lance+1", slot0["arma"])

        # Ranura 1: Iron Lance +2 (Marth)
        slot1 = ficha.inventario[1]
        self.assertEqual(slot1["refine_lvl"], 2)
        self.assertEqual(slot1["grabado"], "Marth")
        self.assertTrue(slot1["equipada"])
        self.assertIn("Iron Lance+2 (Marth)", slot1["arma"])

        # El arma equipada debe ser la de la ranura 1
        self.assertIsNotNone(ficha.arma_equipada)
        self.assertIn("Iron Lance+2 (Marth)", ficha.arma_equipada.nombre)

        # Ranura 3: Poción (Objeto, usos = 2)
        slot3 = ficha.inventario[3]
        self.assertEqual(slot3["tipo"], "Objeto")
        self.assertEqual(slot3["usos"], 2)
        self.assertFalse(slot3["equipada"])

        # Ranura 4: Heal (Bastón, usos = 20)
        slot4 = ficha.inventario[4]
        self.assertEqual(slot4["tipo"], "Bastón")
        self.assertEqual(slot4["usos"], 20)
        self.assertFalse(slot4["equipada"])

    def test_staves_and_consumables_cannot_be_equipped(self):
        """Verifica que bastones y consumibles nunca se equipen como arma de combate."""
        data_unidad = {
            "nombre": "Framme",
            "clase_nombre": "Martial Monk",
            "nivel": 5,
            "es_aliado": True,
            "inventario": [
                {
                    "nombre": "Poción",
                    "usos": 3,
                    "equipada": True
                },
                {
                    "nombre": "Heal",
                    "usos": 25,
                    "equipada": True
                },
                {
                    "nombre": "Iron Shield",
                    "tipo": "Accesorio",
                    "equipada": True
                },
                {
                    "nombre": "Iron Arts",
                    "refine_lvl": 0,
                    "equipada": False
                }
            ]
        }

        ficha = resolver_unidad_con_catalogo(data_unidad)

        for it in ficha.inventario:
            if it["tipo"] in ("Objeto", "Bastón"):
                self.assertFalse(it["equipada"], f"{it['nombre']} no debe estar equipada")

        self.assertIsNotNone(ficha.arma_equipada)
        self.assertIn("Iron Arts", ficha.arma_equipada.nombre)
        self.assertNotIn("Poción", ficha.arma_equipada.nombre)
        self.assertNotIn("Heal", ficha.arma_equipada.nombre)

    def test_staves_and_consumables_separate_clean_name_and_uses(self):
        """Verifica que el nombre de bastones y objetos no contenga paréntesis sintéticos de usos."""
        data_unidad = {
            "nombre": "Alear",
            "clase_nombre": "Divine Dragon",
            "nivel": 10,
            "es_aliado": True,
            "inventario": [
                {"nombre": "Liberation", "equipada": True},
                {"nombre": "Poción", "usos": 1, "usos_max": 3},
                {"nombre": "Elixir", "usos": 2, "usos_max": 3}
            ]
        }

        ficha = resolver_unidad_con_catalogo(data_unidad)
        pocion = ficha.inventario[1]
        self.assertEqual(pocion["nombre"], "Poción")
        self.assertEqual(pocion["usos"], 1)

        pocion["usos"] -= 1
        self.assertEqual(pocion["usos"], 0)

if __name__ == "__main__":
    unittest.main()
