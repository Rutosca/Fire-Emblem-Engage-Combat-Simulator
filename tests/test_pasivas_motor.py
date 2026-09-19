"""
Motor genérico de pasivas (Fase 1): DSL ampliada + pasivas.recopilar en modo
sombra. Los números del combate NO cambian en esta fase (lo fija el golden);
aquí se prueba que el motor lee bien el datamine.
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pasivas
import condicion_dsl as D
from motor_calculo import CalculadoraEngage, Unidad, Arma, Terreno


def _u(nombre="U", **kw):
    base = dict(hp=30, hp_max=30, fuerza=10, magia=5, destreza=12, velocidad=14, defensa=6, resistencia=4, suerte=8, complexion=5)
    base.update(kw)
    return Unidad(nombre, **base)


ESPADA = Arma("Iron Sword", tipo="Espada", mt=5, wt=5, hit=90, crit=0, rango=[1])
HACHA = Arma("Iron Axe", tipo="Hacha", mt=8, wt=10, hit=70, crit=0, rango=[1])
TOMO = Arma("Fire", tipo="Tomo", mt=5, wt=5, hit=90, crit=0, rango=[1, 2], es_magica=True)


def _ctx(u, r, arma=ESPADA, arma_rival=HACHA, es_iniciador=True, aliados=None):
    return D.ContextoCombate(unidad=u, rival=r, es_iniciador=es_iniciador, arma=arma, arma_rival=arma_rival,
                             aliados_cercanos=aliados or [])


class TestDSLAmpliada(unittest.TestCase):

    def test_operadores_aritmeticos_y_unarios(self):
        ctx = _ctx(_u(hp=30, hp_max=40), _u())
        self.assertTrue(D.evaluar_condicion("HP*100 >= (MaxHP * 30)", ctx))      # Hold Out
        self.assertFalse(D.evaluar_condicion("HP*100 <= MaxHP * 25", ctx))       # Vantage
        self.assertTrue(D.evaluar_condicion("!(生存 == 0)", ctx))
        self.assertEqual(D._eval(D._parsear("max(HP-1, 0)"), ctx), 29)
        self.assertEqual(D._eval(D._parsear("int(MaxHP*0.5)"), ctx), 20)
        self.assertEqual(D._eval(D._parsear("cond(1 == 1, 2, 1)"), ctx), 2)
        self.assertEqual(D._eval(D._parsear("-3 + 5"), ctx), 2)

    def test_literales_de_arma_atributo_y_triangulo(self):
        ctx = _ctx(_u(), _u(), arma=ESPADA, arma_rival=HACHA)
        self.assertTrue(D.evaluar_condicion("武器の種類 == 剣", ctx))
        self.assertTrue(D.evaluar_condicion("相手の武器の種類 == 斧", ctx))
        self.assertTrue(D.evaluar_condicion("攻撃属性 == 物理属性", ctx))
        self.assertTrue(D.evaluar_condicion("武器相性 == 有利", ctx))
        ctx2 = _ctx(_u(), _u(), arma=HACHA, arma_rival=ESPADA)
        self.assertTrue(D.evaluar_condicion("武器相性 == 不利", ctx2))
        ctx3 = _ctx(_u(), _u(), arma=TOMO, arma_rival=ESPADA)
        self.assertTrue(D.evaluar_condicion("武器の種類 == 魔道書 && 攻撃属性 == 魔法属性", ctx3))

    def test_stats_del_rival_y_defensa_efectiva(self):
        ctx = _ctx(_u(), _u(defensa=8, resistencia=2), arma=ESPADA)
        self.assertEqual(D._eval(D._parsear("相手の守備 * 0.2"), ctx), 1.6)   # Lunar Brace
        self.assertEqual(D._eval(D._parsear("相手の防御力"), ctx), 8)
        ctx_m = _ctx(_u(), _u(defensa=8, resistencia=2), arma=TOMO)
        self.assertEqual(D._eval(D._parsear("相手の防御力"), ctx_m), 2)

    def test_proc_registra_probabilidad(self):
        ctx = _ctx(_u(destreza=12), _u())
        self.assertTrue(D.evaluar_condicion("スキル確率( 技 )", ctx))
        self.assertEqual(ctx.proc_prob, 12)

    def test_acts_de_texto_no_rompen(self):
        info = {"act_names": ["攻撃結果", "威力"], "act_operations": ["=", "+"], "act_values": ["ブレイク", "3"]}
        acum = D.aplicar_acts(info, {}, _ctx(_u(), _u()))
        self.assertEqual(acum["resultado"], "break")
        self.assertEqual(acum["power"], 3)


class TestRecopilar(unittest.TestCase):

    def test_share_spoils_requiere_aliado_adyacente(self):
        lapis = _u("Lapis", habilidades_sids=["SID_戦果委譲"])
        solo = pasivas.recopilar(lapis, _ctx(lapis, _u()))
        self.assertEqual(solo.get("hit"), 0)
        con = pasivas.recopilar(lapis, _ctx(lapis, _u(), aliados=[(_u("Amiga"), 1)]))
        self.assertEqual(con.get("hit"), 10)
        self.assertEqual(con.get("avo"), 10)
        self.assertEqual(con.get("crit"), -10)
        self.assertEqual(con.nombres(), ["Share Spoils"])

    def test_stand_perceptive_solo_al_iniciar(self):
        alear = _u("Alear", velocidad=14, habilidades_sids=["SID_見切り"])
        ini = pasivas.recopilar(alear, _ctx(alear, _u(), es_iniciador=True))
        self.assertEqual(ini.get("avo"), 15 + math.floor(14 * 0.25))   # el juego trunca
        dfn = pasivas.recopilar(alear, _ctx(alear, _u(), es_iniciador=False))
        self.assertEqual(dfn.get("avo"), 0)
        self.assertEqual(dfn.activas, [])

    def test_stand_vantage_solo_al_defender(self):
        u = _u(hp=5, hp_max=30, habilidades_sids=["SID_待ち伏せ"])
        self.assertEqual(pasivas.recopilar(u, _ctx(u, _u(), es_iniciador=True)).activas, [])
        activas = pasivas.recopilar(u, _ctx(u, _u(), es_iniciador=False)).activas
        self.assertEqual([a["sid"] for a in activas], ["SID_待ち伏せ"])

    def test_prioridad_entre_versiones_plus(self):
        u = _u(hp=30, hp_max=30, habilidades_sids=["SID_踏ん張り", "SID_踏ん張り＋＋"])
        m = pasivas.recopilar(u, _ctx(u, _u(), es_iniciador=False))
        sids = [a["sid"] for a in m.activas]
        self.assertIn("SID_踏ん張り＋＋", sids)
        self.assertNotIn("SID_踏ん張り", sids)

    def test_proc_va_a_procs_no_a_valores(self):
        u = _u(destreza=20, habilidades_sids=["SID_月光"])   # Luna: スキル確率(技)
        m = pasivas.recopilar(u, _ctx(u, _u(defensa=10)))
        self.assertEqual(m.valores.get("rival_defensa_efectiva", 0), 0)
        self.assertEqual(len(m.procs), 1)
        self.assertEqual(m.procs[0]["nombre"], "Luna")
        self.assertEqual(m.procs[0]["prob"], 20)
        self.assertEqual(m.procs[0]["valores"]["rival_defensa_efectiva"], -5)

    def test_cadena_give_a_uno_mismo(self):
        # Divine Speed (Fusión de Marth): +1 golpe y cadena de efectos propios
        u = _u("Alear", habilidades_sids=["SID_カウンター"])
        m = pasivas.recopilar(u, _ctx(u, _u(), es_iniciador=True))
        self.assertEqual(m.get("turno_extra"), 1)
        self.assertIn("Divine Speed", m.nombres())

    def test_variante_de_estilo_declarada_en_skill_xml(self):
        info = pasivas.HABILIDADES["SID_カウンター"]
        self.assertEqual(info["variantes_estilo"].get("dragon"), "SID_カウンター_竜族")
        self.assertEqual(pasivas.variante_por_estilo("SID_カウンター", "竜族スタイル"), "SID_カウンター_竜族")

    def test_sid_desconocido_no_rompe(self):
        u = _u(habilidades_sids=["SID_inventado", "SID_戦果委譲"])
        m = pasivas.recopilar(u, _ctx(u, _u(), aliados=[(_u("A"), 1)]))
        self.assertEqual(m.get("hit"), 10)
        self.assertEqual(m.ignoradas, [("SID_inventado", "no está en el catálogo")])


class TestMotorEnCombate(unittest.TestCase):

    def test_simular_combate_aplica_el_motor_y_lo_documenta(self):
        lapis = _u("Lapis", habilidades_sids=["SID_戦果委譲"], habilidades=["Share Spoils"])
        rival = _u("Enemigo")
        # Sin el SID no hay Solidaridad aunque la unidad se llame Lapis (nada por nombre)
        base = CalculadoraEngage.simular_combate(_u("Lapis"), rival, ESPADA, HACHA, Terreno(), Terreno(),
                                                 aliados_cercanos_atk=[(_u("Amiga"), 1)])
        con = CalculadoraEngage.simular_combate(lapis, rival, ESPADA, HACHA, Terreno(), Terreno(),
                                                aliados_cercanos_atk=[(_u("Amiga"), 1)])
        detalle = con["atacante"]["motor_pasivas"]
        self.assertEqual(detalle["valores"].get("hit"), 10)
        self.assertEqual([a["nombre"] for a in detalle["activas"]], ["Share Spoils"])
        self.assertIsNotNone(con["defensor"]["motor_pasivas"])
        self.assertEqual(con["atacante"]["precision"], min(100, base["atacante"]["precision"] + 10))
        self.assertEqual(con["atacante"]["daño_por_golpe"], base["atacante"]["daño_por_golpe"])
        self.assertIn("Share Spoils (+10 Hit, -10 Crit)", con["atacante"]["pasivas_activas"])   # el Avo cuenta al defender
        self.assertEqual(base["atacante"]["pasivas_activas"], [])


if __name__ == "__main__":
    unittest.main()
