"""
Ruptura (Break) a lo largo de varios combates, con la contabilidad real de
`cargas_ruptura` que hace /api/combate/ejecutar:

  1. Lanza vs Espada (ventaja): Alear recibe Ruptura → cargas_ruptura = 1.
  2. Mientras está rota, el siguiente atacante no recibe contraataque y la
     Ruptura se consume (cargas_ruptura = 0).
  3. Ya sin Ruptura (y sin ventaja del atacante), Alear vuelve a contraatacar.

Sustituye al antiguo script tests/test_ruptura_secuencia.py, que hacía esta
contabilidad a mano y nunca se ejecutaba en la suite.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import app, tablero, resolver_unidad_con_catalogo  # noqa: E402


def _ficha(nombre, clase, arma, es_aliado, x, y):
    return resolver_unidad_con_catalogo({
        "nombre": nombre, "clase_nombre": clase, "nivel": 10,
        "es_aliado": es_aliado, "x": x, "y": y, "arma": arma,
        "hp_actual": 80, "hp_max": 80,   # que nadie muera: se prueba la Ruptura, no el daño
    })


class TestRuptura(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        tablero.limpiar()
        tablero.turno_actual = 1
        tablero.fase = "enemigo"
        for f in (
            _ficha("Alear", "Dragon Child", "Libération", True, 5, 5),
            # Caballeros (estilo Caballería): sin Chain Attacks, que ensuciarían la secuencia
            _ficha("Lance Cavalier 1", "Lance Cavalier", "Iron Lance", False, 6, 5),
            _ficha("Sword Cavalier 2", "Sword Cavalier", "Iron Sword", False, 4, 5),
            _ficha("Axe Cavalier 3", "Axe Cavalier", "Iron Axe", False, 5, 6),
        ):
            tablero.registrar_unidad(f, resolver_colision=False)
        self.alear = tablero.obtener_ficha("Alear")

    def _ataca(self, atacante):
        res = self.client.post("/api/combate/ejecutar", json={
            "atacante": atacante, "defensor": "Alear",
            "pos_destino": list(tablero.posicion_de(atacante)),
        })
        self.assertEqual(res.status_code, 200, res.get_json())
        return res.get_json()

    @staticmethod
    def _contraataco(res) -> bool:
        secuencia = res["combate"]["resultado"].get("secuencia", [])
        return any(s.get("actor") == "Alear" for s in secuencia)

    def test_secuencia_recibe_ruptura_no_contraataca_y_recupera(self):
        # 1. Lanza (ventaja sobre Espada) rompe a Alear
        r1 = self._ataca("Lance Cavalier 1")
        self.assertTrue(self._resultado(r1)["aplica_ruptura"], "Lanza vs Espada debe infligir Ruptura")
        self.assertEqual(self.alear.cargas_ruptura, 1)

        # 2. Rota: no contraataca al siguiente atacante y la Ruptura se consume
        r2 = self._ataca("Sword Cavalier 2")
        self.assertFalse(self._contraataco(r2), "Alear no debe contraatacar mientras está rota")
        self.assertTrue(r2["combate"]["alertas_tacticas"]["contraataque_bloqueado"])
        self.assertEqual(self.alear.cargas_ruptura, 0, "La Ruptura se consume tras un combate")

        # 3. Recuperada: contraataca (Hacha vs Espada = desventaja del atacante, no rompe)
        r3 = self._ataca("Axe Cavalier 3")
        self.assertTrue(self._contraataco(r3), "Alear debe volver a contraatacar sin Ruptura")
        self.assertFalse(self._resultado(r3)["aplica_ruptura"])
        self.assertEqual(self.alear.cargas_ruptura, 0)

    @staticmethod
    def _resultado(res) -> dict:
        return res["combate"]["resultado"]


if __name__ == "__main__":
    unittest.main()
