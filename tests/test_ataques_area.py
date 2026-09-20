"""
Ataques de Emblema de área (ataques_area.py). Override (Sigurd), verificado en el
Cap. 9: atraviesa a TODOS los enemigos consecutivos de la fila/columna (5 en el
juego, sin tope), la casilla de llegada puede ser de evasión pero no muro/foso/bosque,
y los bonos de posición del atacante (Guía Divina de Alear adyacente) se aplican a
todos los objetivos, no solo al primero.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from ataques_area import resolver_ataque_area, es_casilla_llegada_override   # noqa: E402
from motor_calculo import Terreno                                              # noqa: E402
from app import app, tablero, _mapa, resolver_unidad_con_catalogo             # noqa: E402


def _enemigo(nombre, x, y, hp=30):
    return resolver_unidad_con_catalogo({
        "nombre": nombre, "x": x, "y": y, "es_aliado": False, "hp_actual": hp, "hp_max": hp,
        "arma_nombre": "Iron Axe", "stats": {"hp": hp, "defensa": 5, "resistencia": 5, "velocidad": 5, "fuerza": 8, "suerte": 3},
    })


class TestOverride(unittest.TestCase):

    def setUp(self):
        tablero.limpiar()
        # fila libre y transitable del mapa cargado (8 casillas seguidas)
        def libre(x, y):
            t = _mapa.grid[x][y]
            return getattr(t, "caminable", True) and getattr(t, "coste_mov", 1) == 1
        self.fila = next(((x, y) for y in range(_mapa.alto) for x in range(_mapa.ancho - 7)
                          if all(libre(x + k, y) for k in range(8))), None)
        self.assertIsNotNone(self.fila, "el mapa no tiene una fila libre de 8 casillas")

    def test_atraviesa_a_todos_los_enemigos_consecutivos(self):
        x0, y = self.fila
        sigurd = resolver_unidad_con_catalogo({
            "nombre": "Louis", "x": x0, "y": y, "es_aliado": True, "emblema_nombre": "Sigurd", "en_fusion": True,
            "inventario": [{"nombre": "Iron Lance"}], "stats": {"hp": 30, "fuerza": 14, "defensa": 12},
        })
        tablero.registrar_unidad(sigurd)
        enemigos = [_enemigo(f"E{k}", x0 + 1 + k, y) for k in range(5)]
        for e in enemigos:
            tablero.registrar_unidad(e)
        area = resolver_ataque_area("Override (Iron Lance)", (x0, y), enemigos[0], sigurd, tablero, _mapa)
        self.assertTrue(area["valido"], area["motivo"])
        self.assertEqual([o.nombre for o in area["objetivos"]], ["E0", "E1", "E2", "E3", "E4"])
        self.assertEqual(area["pos_final"], (x0 + 6, y))
        # un aliado en medio corta la cadena
        tablero.eliminar_unidad("E2")
        tablero.registrar_unidad(resolver_unidad_con_catalogo({"nombre": "Amigo", "x": x0 + 3, "y": y, "es_aliado": True, "stats": {"hp": 20}}))
        area2 = resolver_ataque_area("Override (Iron Lance)", (x0, y), enemigos[0], sigurd, tablero, _mapa)
        self.assertEqual([o.nombre for o in area2["objetivos"]], ["E0", "E1"])

    def test_casilla_de_llegada(self):
        self.assertTrue(es_casilla_llegada_override(Terreno(nombre="Llanura")))
        self.assertTrue(es_casilla_llegada_override(Terreno(nombre="evasion", avo=30, coste_mov=2)))
        self.assertFalse(es_casilla_llegada_override(Terreno(nombre="Muro", caminable=False)))
        self.assertFalse(es_casilla_llegada_override(Terreno(nombre="Foso", caminable=False, volable=True)))
        self.assertFalse(es_casilla_llegada_override(Terreno(nombre="Bosque", coste_mov=2)))
        # un volador sí puede acabar sobre un foso sobrevolable... pero no sobre un muro
        self.assertFalse(es_casilla_llegada_override(Terreno(nombre="Foso", caminable=False, volable=True), es_volador=True))
        self.assertTrue(es_casilla_llegada_override(Terreno(nombre="Río", caminable=False, volable=True), es_volador=True))

    def test_guia_divina_se_aplica_a_todos_los_objetivos(self):
        x0, y = self.fila
        louis = resolver_unidad_con_catalogo({
            "nombre": "Louis", "x": x0, "y": y, "es_aliado": True, "emblema_nombre": "Sigurd", "en_fusion": True,
            "energia_emblema": 0, "inventario": [{"nombre": "Iron Lance"}], "stats": {"hp": 30, "fuerza": 14, "defensa": 12},
        })
        tablero.registrar_unidad(louis)
        # Alear adyacente al atacante (detrás), lejos de los objetivos traseros
        tablero.registrar_unidad(resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": x0, "y": y + 1 if y + 1 < _mapa.alto else y - 1, "es_aliado": True,
            "habilidades": ["Divinely Inspiring"], "stats": {"hp": 30}}))
        for k in range(3):
            tablero.registrar_unidad(_enemigo(f"E{k}", x0 + 1 + k, y, hp=40))
        client = app.test_client()
        res = client.post("/api/combate/ejecutar", json={
            "atacante": "Louis", "defensor": "E0", "arma_nombre": "Override (Iron Lance)", "pos_destino": [x0, y],
        })
        self.assertEqual(res.status_code, 200, res.get_json())
        r = res.get_json()
        dmg_principal = r["combate"]["atacante"]["daño_total_ronda"]
        self.assertIn("Divinely Inspiring", " ".join(r["combate"]["atacante"]["pasivas_activas"]))
        extras = r.get("objetivos_extra") or r.get("area", {}).get("extras") or []
        self.assertEqual(len(extras), 2, r.keys())
        for ex in extras:
            self.assertEqual(ex["daño"], dmg_principal, ex)
        self.assertEqual((tablero.obtener_ficha("Louis").x, tablero.obtener_ficha("Louis").y), (x0 + 4, y))


if __name__ == "__main__":
    unittest.main()
