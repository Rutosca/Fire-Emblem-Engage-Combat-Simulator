"""
Invocaciones de Verónica: el aliado fusionado con ella puede invocar una unidad de clase
normal o un Emblema (Eirika, Edelgard…) que cuenta como UNIDAD aliada, no como Emblema. El
jugador la registra en el modal con su nombre, su clase y sus stats.

Person.xml tiene una ficha por invocación (PID_召喚_…, con SummonColor/SummonGod): las
habilidades del Emblema invocado y su clase "Emblem" (una por Emblema, con sus armas).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app, tablero  # noqa: E402

STATS = {"hp": 35, "hp_max": 35, "fuerza": 15, "magia": 2, "destreza": 14, "velocidad": 14,
         "defensa": 9, "resistencia": 6, "suerte": 8, "complexion": 7}


class TestInvocacionesDeVeronica(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()
        cls.client.post("/api/mapa/seleccionar", json={"capitulo": 11})

    @classmethod
    def tearDownClass(cls):
        cls.client.post("/api/mapa/seleccionar", json={"capitulo": 7})

    def _invocar(self, nombre, clase, arma, x=2, y=30):
        tablero.fichas.pop(nombre, None)
        r = self.client.post("/api/unidad/guardar", json={
            "nombre": nombre, "clase_nombre": clase, "es_aliado": True, "x": x, "y": y, "nivel": 1,
            "hp_max": 35, "hp_actual": 35, "mov": 5, "stats": STATS, "arma_nombre": arma,
            "inventario": [{"arma": arma, "equipada": True}], "emblema_nombre": ""})
        self.assertEqual(r.status_code, 200, r.get_json())
        return tablero.obtener_ficha(nombre)

    def test_un_emblema_invocado_es_una_unidad_aliada(self):
        f = self._invocar("Eirika", "Emblem", "Sieglinde")
        self.assertEqual(f.pid, "PID_召喚_エイリーク", "la ficha de la invocación, no la del paralogo")
        self.assertEqual((f.hp_max, f.stats.fuerza, f.mov), (35, 15, 5), "las stats son las del modal")
        self.assertEqual(f.arma.nombre, "Sieglinde")
        self.assertEqual(f.emblema_nombre, "", "no lleva Emblema: ES la unidad")
        self.assertFalse(getattr(f, "es_fijo", False))
        self.assertIn("Sacred Twins", f.habilidades)
        self.assertNotIn("Immobilized", f.habilidades)

    def test_la_clase_emblem_es_la_de_cada_uno(self):
        """Hay una clase "Emblem" por Emblema: Edelgard lleva hachas y Camilla vuela."""
        edelgard = self._invocar("Edelgard", "Emblem", "Aymr", x=3)
        self.assertEqual(edelgard.pid, "PID_召喚_エーデルガルト")
        camilla = self._invocar("Camilla", "Emblem", "Camilla's Axe", x=4)
        self.assertTrue(camilla.es_volador)

    def test_el_personaje_jugable_no_cambia(self):
        """Solo un aliado con el nombre de un Emblema que no es jugable es una invocación."""
        f = self._invocar("Framme", "Martial Monk", "Steel-Hand Art", x=5)
        self.assertEqual(f.pid, "PID_フラン")

    def test_el_analisis_la_mueve_y_la_usa(self):
        self._invocar("Eirika", "Emblem", "Sieglinde", x=6)
        r = self.client.post("/api/analizar", json={"perfil": "seguro"})
        self.assertEqual(r.status_code, 200)
        mov = self.client.get("/api/unidad/rango_movimiento", query_string={"nombre": "Eirika"})
        self.assertEqual(mov.status_code, 200)
        self.assertTrue(mov.get_json().get("casillas"))


if __name__ == "__main__":
    unittest.main()
