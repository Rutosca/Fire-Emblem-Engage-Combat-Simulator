"""
Resolución de unidades y armas por el catálogo (catalogo_loader): nivel
interno de clase, grabados de Emblema.

Origen: tests/test_fixes_tactical.py (partido por dominio el 2026-09-18).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from helpers import cargar_dispos  # noqa: E402
from app import tablero, resolver_unidad_con_catalogo, _arma_desde_item  # noqa: E402


class TestCatalogoLoader(unittest.TestCase):

    def setUp(self):
        # resolver_unidad_con_catalogo lee app.tablero para heredar estado: empezar siempre limpio
        tablero.limpiar()

    def test_armored_m007_usa_nivel_interno_de_clase_basica(self):
        """Un Armored de nivel 10 no debe recibir +9 niveles de clase avanzada."""
        armored = next(u for u in cargar_dispos("M007", "Extremo")
                       if "Armor" in u.get("clase_nombre", ""))
        ficha = resolver_unidad_con_catalogo(armored)
        self.assertEqual(getattr(ficha.stats, "nivel_interno_clase", None), 0)
        self.assertEqual(ficha.stats.hp, 36)

    def test_grabado_de_emblema_como_campo_separado_se_aplica(self):
        """
        _arma_desde_item no debe perder el grabado de Emblema cuando viene como
        campo separado del dict de inventario (no embebido en "nombre").
        """
        item = {"nombre": "Levin Sword", "nombre_base": "Levin Sword", "grabado": "Sigurd", "refine_lvl": 0}
        arma = _arma_desde_item(item)
        self.assertEqual(arma.mt, 14, "El grabado de Sigurd debe sumar +1 Mt (13 base + 1)")
        self.assertEqual(arma.avo_bonus, 20, "El grabado de Sigurd debe dar +20 Avoid")

    def test_grabado_sobrevive_reparseo_tras_mostrarse(self):
        """
        GRABADOS_EMBLEMA debe usar el nombre localizado oficial (God.xml "nombre"),
        no la transliteración interna "ascii_name" (que trae erratas: Sigurd-Siglud,
        Leif-Leaf, Lyn-Lin, Corrin-Kamui, Eirika-Eirik, Alear-Lueur). De lo contrario,
        el nombre formateado que se le muestra al jugador no coincide con ninguna
        clave al reparsearlo (p.ej. al reguardar la unidad), y el grabado desaparece.
        """
        from catalogo_loader import parsear_arma_string
        for emblema in ("Sigurd", "Leif", "Lyn", "Corrin", "Eirika", "Alear"):
            primera = parsear_arma_string(f"Iron Sword ({emblema})")
            self.assertIsNotNone(primera.get("grabado"), f"{emblema}: el grabado debe aplicarse en la primera pasada")
            segunda = parsear_arma_string(primera["nombre"])
            self.assertIsNotNone(segunda.get("grabado"), f"{emblema}: el grabado debe sobrevivir al reparsear el nombre ya formateado")
            self.assertEqual(primera["avo_bonus"], segunda["avo_bonus"], f"{emblema}: el bono debe mantenerse igual tras el reparseo")

if __name__ == "__main__":
    unittest.main()
