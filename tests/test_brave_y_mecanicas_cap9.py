"""
Mecánicas incorporadas con el Cap. 9:
  - Armas Brave (Item.xml EquipSids SID_２回行動: Brave Sword/Lance/Axe/Bow, Nova,
    Body Arts): el INICIADOR pega dos veces por ataque; con follow-up: 2, contra, 2.
    Al defender no dobla; los Ataques de Emblema no doblan.
  - Guardia en Cadena no para un Ataque de Emblema.
  - Casillas de evasión: coste de movimiento +1 para terrestres, 1 para voladores.
  - Houses Unite: los bonos de Atk de las pasivas entran en cada golpe (×0.5).
  - Meditación / Self-Improver: al esperar, +2 Res / +2 Fue hasta la siguiente fase de jugador.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from motor_calculo import CalculadoraEngage, Unidad, Arma, Terreno
from catalogo_loader import _arma_desde_item
from motor_de_movimiento_y_amenaza import AnalizadorAmenaza, UnidadMock, ArmaMock
from estado_tablero import EstadoTablero, FichaUnidad
import pasivas_temporales


def _u(nombre, **kw):
    base = dict(hp=40, hp_max=40, fuerza=14, magia=2, destreza=10, velocidad=10, defensa=5, resistencia=3, suerte=5, complexion=5)
    base.update(kw)
    return Unidad(nombre, **base)


BRAVE = Arma("Brave Sword", tipo="Espada", mt=4, wt=13, hit=80, crit=0, rango=[1], sids=["SID_２回行動"])
ESPADA = Arma("Iron Sword", tipo="Espada", mt=5, wt=5, hit=90, crit=0, rango=[1])


def _tipos(res, actor):
    return [s["tipo"] for s in res["resultado"]["secuencia"] if s["actor"] == actor]


class TestBrave(unittest.TestCase):

    def test_catalogo_marca_brave_y_body_arts(self):
        for nombre in ("Brave Sword", "Brave Lance", "Brave Axe", "Iron-Body Art"):
            a = _arma_desde_item({"arma": nombre})
            self.assertIsNotNone(a, nombre)
            self.assertTrue(a.es_brave, nombre)
        self.assertFalse(_arma_desde_item({"arma": "Silver Sword"}).es_brave)

    def test_iniciador_brave_dos_golpes_por_ataque_con_follow_up(self):
        atk = _u("Kagetsu", velocidad=20, complexion=10)   # AS 17 vs 10: dobla
        dfn = _u("Rival", velocidad=10)
        res = CalculadoraEngage.simular_combate(atk, dfn, BRAVE, ESPADA, Terreno(), Terreno(), distancia=1)
        self.assertEqual(_tipos(res, "Kagetsu"), ["ataque", "ataque (Brave 2º golpe)", "follow-up", "follow-up (Brave 2º golpe)"])
        secuencia = [s["actor"] for s in res["resultado"]["secuencia"]]
        self.assertEqual(secuencia, ["Kagetsu", "Kagetsu", "Rival", "Kagetsu", "Kagetsu"])   # 12x2, contra, 12x2
        self.assertEqual(res["atacante"]["golpes_en_ronda"], 4)
        self.assertTrue(res["atacante"]["es_brave"])

    def test_defensor_con_brave_no_dobla(self):
        atk = _u("Atacante", velocidad=10)
        dfn = _u("Defensor", velocidad=10)
        res = CalculadoraEngage.simular_combate(atk, dfn, ESPADA, BRAVE, Terreno(), Terreno(), distancia=1)
        self.assertEqual(_tipos(res, "Defensor"), ["contraataque"])

    def test_ataque_de_emblema_no_dobla(self):
        atk = _u("Céline", magia=16)
        dfn = _u("Rival")
        tomo = Arma("Warp Ragnarök", tipo="Tomo", mt=15, wt=0, hit=100, crit=0, rango=[1], es_magica=True, sids=["SID_２回行動"])
        res = CalculadoraEngage.simular_combate(atk, dfn, tomo, ESPADA, Terreno(), Terreno(), distancia=1,
                                                es_engage_attack=True, engage_attack_nombre="Warp Ragnarök")
        self.assertEqual(res["atacante"]["golpes_en_ronda"], 1)


class TestChainGuardYEmblema(unittest.TestCase):

    def _qi(self):
        f = FichaUnidad(nombre="Framme", es_aliado=False, x=1, y=1, stats=_u("Framme", hp=30, hp_max=30), clase_nombre="Martial Monk", estilo_combate="気功スタイル")
        f.hp_actual, f.hp_max = 30, 30
        return f

    def test_chain_guard_bloquea_ataque_normal_pero_no_ataque_de_emblema(self):
        atk, dfn = _u("Alear", fuerza=20), _u("Rival")
        normal = CalculadoraEngage.simular_combate(atk, dfn, ESPADA, ESPADA, Terreno(), Terreno(), distancia=1, chain_guard_protector=self._qi())
        self.assertTrue(normal["resultado"]["chain_guard"]["activo"])
        self.assertIn("bloqueado por Guardia en Cadena", normal["resultado"]["secuencia"][0]["tipo"])
        eng = CalculadoraEngage.simular_combate(atk, dfn, ESPADA, ESPADA, Terreno(), Terreno(), distancia=1, chain_guard_protector=self._qi(),
                                                es_engage_attack=True, engage_attack_nombre="Lodestar Rush")
        self.assertFalse(eng["resultado"]["chain_guard"]["activo"])
        self.assertFalse(any("Guardia en Cadena" in s["tipo"] for s in eng["resultado"]["secuencia"]))

    def test_houses_unite_incluye_bonos_de_atk(self):
        chloe = _u("Chloé", fuerza=12, hp=29, hp_max=29)
        rival = _u("Rival", defensa=5, hp=60, hp_max=60)
        lanza = Arma("Houses Unite", tipo="Lanza", mt=0, wt=0, hit=100, crit=0, rango=[1])
        sin = CalculadoraEngage.simular_combate(chloe, rival, lanza, None, Terreno(), Terreno(), distancia=1,
                                                es_engage_attack=True, engage_attack_nombre="Houses Unite")
        # Guía Divina: Alear adyacente (+3 Atk) → cada golpe sube antes del ×0.5
        alear = _u("Alear", habilidades=["SID_神竜の結束"], habilidades_sids=["SID_神竜の結束"])
        con = CalculadoraEngage.simular_combate(chloe, rival, lanza, None, Terreno(), Terreno(), distancia=1,
                                                es_engage_attack=True, engage_attack_nombre="Houses Unite",
                                                aliados_cercanos_atk=[(alear, 1)])
        h_sin, h_con = sin["atacante"]["houses_unite_hits"], con["atacante"]["houses_unite_hits"]
        # Fue 12 + Mt (24 / 21 / 13) − Def 5 = 31/28/20, a la mitad truncando
        self.assertEqual(h_sin, [15, 14, 10])
        self.assertTrue(all(c > s for c, s in zip(h_con, h_sin)), (h_sin, h_con))


class TestEvasionCoste(unittest.TestCase):

    def test_terrestre_paga_2_y_volador_1(self):
        t_llano = Terreno()
        t_ev = Terreno(nombre="evasion", avo=30, coste_mov=2)
        grid = [[t_llano for _ in range(5)] for _ in range(5)]
        grid[1][0] = t_ev
        grid[2][0] = t_ev
        an = AnalizadorAmenaza(grid, 5, 5)
        terr = an.calcular_casillas_alcanzables(UnidadMock(0, 0, 2, False, ArmaMock([1])))
        vol = an.calcular_casillas_alcanzables(UnidadMock(0, 0, 2, True, ArmaMock([1])))
        self.assertIn((1, 0), terr)
        self.assertNotIn((2, 0), terr)   # 2 + 2 > mov 2
        self.assertIn((2, 0), vol)


class TestPasivasAlEsperar(unittest.TestCase):

    def _tablero(self, nombre, sid):
        t = EstadoTablero(mapa=None, auto_cargar_spawns=False)
        t.fase, t.turno_actual = "jugador", 3
        f = FichaUnidad(nombre=nombre, es_aliado=True, x=1, y=1, stats=_u(nombre, habilidades_sids=[sid]), hp_actual=40, hp_max=40, viva=True)
        t.registrar_unidad(f)
        return t, f

    def test_meditacion_da_res2_durante_la_fase_enemiga(self):
        t, jade = self._tablero("Jade", "SID_瞑想")
        otorgados = pasivas_temporales.al_terminar_fase_jugador(t)
        self.assertEqual([n for n, _ in otorgados], ["Jade"])
        self.assertEqual(otorgados[0][1]["stat_boosts"].get("res"), 2)
        t.iniciar_fase_enemigo()
        self.assertTrue(jade.tiene_estado_temporal("SID_瞑想効果"))
        t.avanzar_turno()   # entra la fase de jugador 4: caduca
        self.assertFalse(jade.tiene_estado_temporal("SID_瞑想効果"))

    def test_self_improver_misma_duracion(self):
        t, alfred = self._tablero("Alfred", "SID_自己研鑽")
        otorgados = pasivas_temporales.al_esperar(t, alfred)
        self.assertEqual(otorgados[0][1]["stat_boosts"].get("str"), 2)
        alfred.accion_turno = "atacar"
        self.assertEqual(pasivas_temporales.al_esperar(t, alfred), [])   # si atacó, no espera


if __name__ == "__main__":
    unittest.main()
