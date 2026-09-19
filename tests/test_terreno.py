"""
Terreno: tipos de casilla del mapa Tiled y cómo los aplica el motor.
  - `evasion`: +30 Avo, sin curación ni antirruptura (Cap. 9).
  - `curacion`: +30 Avo, +10 HP/turno, antirruptura.
  - Los voladores no reciben bonos de Avo/Def del terreno.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from lector_de_mapas import MapaTactico
from motor_calculo import CalculadoraEngage, Unidad, Arma, Terreno

RUTA_CAP9 = os.path.join(os.path.dirname(__file__), "..", "mapas", "CAP_9_Tiled.json")


def _u(nombre, **kw):
    base = dict(hp=30, fuerza=10, magia=0, destreza=10, velocidad=10, defensa=5, resistencia=3, suerte=6, complexion=5)
    base.update(kw)
    return Unidad(nombre, **base)


ESPADA = Arma("Iron Sword", tipo="Espada", mt=5, wt=5, hit=90, crit=0, rango=[1])


class TestTiposDeCasilla(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not os.path.exists(RUTA_CAP9):
            raise unittest.SkipTest("No existe mapas/CAP_9_Tiled.json")
        cls.mapa = MapaTactico(RUTA_CAP9)

    def _primera(self, nombre):
        for x in range(self.mapa.ancho):
            for y in range(self.mapa.alto):
                if self.mapa.grid[x][y].nombre.lower() == nombre:
                    return self.mapa.grid[x][y]
        self.fail(f"El mapa no tiene casillas '{nombre}'")

    def test_evasion_solo_da_avo(self):
        t = self._primera("evasion")
        self.assertEqual(t.avo, 30)
        self.assertEqual(t.dfn, 0)
        self.assertEqual(t.curacion_turno, 0)
        self.assertFalse(t.es_antirruptura)
        self.assertTrue(t.caminable)

    def test_curacion_da_avo_curacion_y_antirruptura(self):
        t = self._primera("curacion")
        self.assertEqual(t.avo, 30)
        self.assertEqual(t.curacion_turno, 10)
        self.assertTrue(t.es_antirruptura)


class TestBonosDeTerrenoEnCombate(unittest.TestCase):

    def _precision_contra(self, defensor, terreno_def):
        res = CalculadoraEngage.simular_combate(_u("Atacante"), defensor, ESPADA, ESPADA, Terreno(), terreno_def, distancia=1)
        return res["atacante"]["precision"]

    def test_terrestre_gana_30_avo_en_evasion(self):
        llano = self._precision_contra(_u("Infante"), Terreno())
        evasion = self._precision_contra(_u("Infante"), Terreno(nombre="evasion", avo=30))
        self.assertEqual(llano - evasion, 30)

    def test_volador_no_recibe_bonos_de_terreno(self):
        volador = _u("Pegaso", es_volador=True, tipo_movimiento="volador", estilo_combate="飛行スタイル")
        llano = self._precision_contra(volador, Terreno())
        evasion = self._precision_contra(volador, Terreno(nombre="evasion", avo=30))
        self.assertEqual(llano, evasion)
        # tampoco la Def de un trono
        res_llano = CalculadoraEngage.simular_combate(_u("A"), volador, ESPADA, ESPADA, Terreno(), Terreno(), distancia=1)
        res_trono = CalculadoraEngage.simular_combate(_u("A"), volador, ESPADA, ESPADA, Terreno(), Terreno(nombre="trono", avo=30, dfn=2), distancia=1)
        self.assertEqual(res_llano["atacante"]["daño_por_golpe"], res_trono["atacante"]["daño_por_golpe"])


if __name__ == "__main__":
    unittest.main()
