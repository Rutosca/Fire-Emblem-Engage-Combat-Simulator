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


def _mapa_tiled(capas, ancho):
    """Mapa Tiled mínimo con tileset incrustado: gid 1 llanura, 2 evasion (bosque), 3 agua."""
    import json
    import tempfile
    data = {
        "width": ancho, "height": 1,
        "tilesets": [{"firstgid": 1, "tiles": [
            {"id": i, "properties": [{"name": "tipo", "type": "string", "value": tipo}]}
            for i, tipo in enumerate(("llanura", "evasion", "agua"))]}],
        "layers": [{"type": "tilelayer", "name": nombre, "data": datos} for nombre, datos in capas],
    }
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(data, f)
    f.close()
    try:
        return MapaTactico(f.name)
    finally:
        os.unlink(f.name)


class TestAguaSuperpuesta(unittest.TestCase):
    """Cap. 11: el agua (TID_水溜まり_永続, −30 Avo, +1 de coste) va encima del terreno de
    base. Sobre un bosque la evasión se anula (0 Avo) y el coste se suma: 2 + 1 = 3, así que
    con Canter (2) no se entra en la arboleda con agua (observado en juego)."""

    BASE = ("terreno", [1, 2, 1])
    AGUA = ("superpuestos", [0, 3, 3])

    def _comprobar(self, mapa):
        llano, bosque_agua, agua = (mapa.grid[x][0] for x in range(3))
        self.assertEqual((llano.nombre, llano.avo, llano.coste_mov), ("llanura", 0, 1))
        self.assertEqual((bosque_agua.nombre, bosque_agua.avo, bosque_agua.coste_mov), ("evasion + agua", 0, 3))
        self.assertEqual((agua.nombre, agua.avo, agua.coste_mov), ("agua", -30, 2))

    def test_agua_encima_de_bosque_y_de_llano(self):
        self._comprobar(_mapa_tiled([self.BASE, self.AGUA], 3))

    def test_da_igual_el_orden_de_las_capas(self):
        self._comprobar(_mapa_tiled([self.AGUA, self.BASE], 3))

    def test_dos_capas_de_agua_no_acumulan(self):
        self._comprobar(_mapa_tiled([self.BASE, self.AGUA, self.AGUA], 3))

    def test_la_vena_de_agua_de_camilla_no_se_suma_al_agua_fija(self):
        mapa = _mapa_tiled([self.BASE, self.AGUA], 3)
        mapa.aplicar_terrenos_temporales({"agua": [(0, 0), (1, 0), (2, 0)]})
        self.assertEqual((mapa.grid[0][0].avo, mapa.grid[0][0].coste_mov), (-30, 2), "la vena sobre llano resta y frena")
        self.assertEqual((mapa.grid[2][0].avo, mapa.grid[2][0].coste_mov), (-30, 2), "sobre agua fija no se repite")
        self.assertEqual(mapa.grid[1][0].coste_mov, 3, "bosque con agua fija y vena: sigue en 3")
        mapa.limpiar_terrenos_temporales()
        self._comprobar(mapa)
