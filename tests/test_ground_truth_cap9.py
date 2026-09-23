"""
Verdad de juego del Capítulo 9 (observaciones en partida, Extremo).

Houses Unite de Chloé (vínculo 20 con las Tres Casas → Weapon Sync+ +7) contra un
Axe Flier: las cuatro combinaciones de Guía Divina (+3, Alear adyacente) y Gente de
Cuento (+2, pareja hombre-mujer adyacentes entre sí a ≤2 casillas):
  sin bonos 19/18/27 · solo Gente de Cuento 20/19/28 · solo Guía Divina 21/19/28 · ambos 22/20/29.
El tercer golpe (Failnaught) es efectivo contra voladores (Mt ×3).

Cada golpe es el DAÑO NORMAL de esa reliquia partido por la mitad (truncando):
Fue 20 + Weapon Sync+ 7 + Mt (24 · 14×1.5 = 21 · 13×3 = 39) − Def 12 = 39/36/54 → 19/18/27.
La Fue de esta reconstrucción era 15 y el motor llevaba un "+5" fijo que la compensaba;
con la Fue real las cuatro combinaciones salen sin ningún término suelto.

El ×3 de Failnaught se aplica aquí porque el Axe Flier es un volador corriente. Contra
Hortensia no se aplica, pero no por el ataque: es su Veteran+ el que anula la efectividad.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from motor_calculo import CalculadoraEngage, Unidad, Arma, Terreno


class TestGroundTruthCapitulo9(unittest.TestCase):

    def _houses_unite(self, aliados, defensor=None):
        chloe = Unidad("Chloé", hp=30, fuerza=20, destreza=10, velocidad=10, defensa=8, resistencia=5, suerte=5, complexion=5,
                       habilidades=["Weapon Sync+", "Fairy-Tale Folk"], emblema_nombre="Edelgard / Dimitri / Claude", en_fusion=True,
                       estilo_combate="飛行スタイル")
        setattr(chloe, "genero", 2)
        setattr(chloe, "lider_tres_casas", "Dimitri")
        flier = Unidad("Axe Flier", hp=40, fuerza=12, destreza=8, velocidad=9, defensa=12, resistencia=6, suerte=3, complexion=6,
                       tipo_movimiento="volador", es_volador=True)
        lanza = Arma("Houses Unite", tipo="Lanza", mt=0, wt=0, hit=100, crit=0, rango=[1])
        res = CalculadoraEngage.simular_combate(chloe, defensor or flier, lanza, None, Terreno(), Terreno(), distancia=1,
                                                es_engage_attack=True, engage_attack_nombre="Houses Unite",
                                                aliados_cercanos_atk=aliados)
        return res["atacante"]["houses_unite_hits"]

    @staticmethod
    def _aliados():
        alear = Unidad("Alear", hp=30, habilidades=["SID_神竜の結束"], habilidades_sids=["SID_神竜の結束"])
        celine = Unidad("Céline", hp=30)
        louis = Unidad("Louis", hp=30)
        for u, g, (x, y) in ((alear, 1, (5, 6)), (celine, 2, (6, 5)), (louis, 1, (7, 5))):
            setattr(u, "genero", g)
            setattr(u, "x", x)
            setattr(u, "y", y)
        return alear, celine, louis

    def test_01_houses_unite_vs_axe_flier_cuatro_combinaciones(self):
        alear, celine, louis = self._aliados()
        self.assertEqual(self._houses_unite([]), [19, 18, 27])
        self.assertEqual(self._houses_unite([(celine, 1), (louis, 2)]), [20, 19, 28])          # Gente de Cuento
        self.assertEqual(self._houses_unite([(alear, 1)]), [21, 19, 28])                       # Guía Divina
        self.assertEqual(self._houses_unite([(alear, 1), (celine, 1), (louis, 2)]), [22, 20, 29])

    def test_02_veteran_mas_del_defensor_anula_la_efectividad(self):
        """El mismo golpe contra un volador CON Veteran+ (SID_熟練者＋, que sincroniza
        SID_特効無効_効果) pierde el ×3: es lo que pasa con Hortensia en los Cap. 7 y 10."""
        from motor_calculo import Unidad as _U
        flier_veterano = _U("Axe Flier", hp=40, fuerza=12, destreza=8, velocidad=9, defensa=12,
                            resistencia=6, suerte=3, complexion=6,
                            tipo_movimiento="volador", es_volador=True,
                            habilidades=["Veteran+"], habilidades_sids=["SID_熟練者＋"])
        self.assertEqual(self._houses_unite([], defensor=flier_veterano), [19, 18, 14])


if __name__ == "__main__":
    unittest.main()
