"""
Fase 2 del motor de pasivas: los bloques a mano de motor_calculo._stats_de_golpe
sustituidos por pasivas.recopilar_combate (Skill.xml vía catálogo) + overlay DLC.

Cubre lo que el motor genérico tiene que reproducir para que el golden siga en
verde: auras (Timing 20), SyncSids, ambos bandos de un mismo golpe (Fair Fight),
Stand 1/2 (Perceptive, Vantage), armas con SID (Thunder sin follow-up), reglas de
estilo como SIDs, Trained to Kill con el terreno propio, Moved to Tears con Chain
Attack, el overlay (Weapon Sync, Geosphere) y el comando Advance (Roy).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import pasivas                                                        # noqa: E402
import condicion_dsl                                                  # noqa: E402
from motor_calculo import CalculadoraEngage, Unidad, Arma, Terreno   # noqa: E402
from motor_de_movimiento_y_amenaza import casillas_advance            # noqa: E402


def _u(nombre="U", **kw):
    base = dict(hp=40, hp_max=40, fuerza=14, magia=4, destreza=10, velocidad=10, defensa=5, resistencia=3, suerte=5, complexion=5)
    base.update(kw)
    pos = base.pop("pos", None)
    u = Unidad(nombre, **base)
    if pos:
        setattr(u, "x", pos[0])
        setattr(u, "y", pos[1])
    return u


ESPADA = Arma("Iron Sword", tipo="Espada", mt=5, wt=5, hit=90, crit=0, rango=[1])
HACHA = Arma("Iron Axe", tipo="Hacha", mt=7, wt=7, hit=80, crit=0, rango=[1])
LANZA = Arma("Iron Lance", tipo="Lanza", mt=6, wt=6, hit=85, crit=0, rango=[1])
TOMO = Arma("Fire", tipo="Tomo", mt=5, wt=4, hit=95, crit=0, rango=[1, 2], es_magica=True)
THUNDER = Arma("Thunder", tipo="Tomo", mt=5, wt=10, hit=80, crit=0, rango=[1, 2, 3], es_magica=True, sids=["SID_追撃不可"])


def _combate(atk, dfn, arma_atk=ESPADA, arma_def=HACHA, **kw):
    kw.setdefault("distancia", 1)
    return CalculadoraEngage.simular_combate(atk, dfn, arma_atk, arma_def, kw.pop("terreno_atk", Terreno()), kw.pop("terreno_def", Terreno()), **kw)


class TestAuras(unittest.TestCase):

    def test_divinely_inspiring_solo_a_adyacentes(self):
        alear = _u("Alear", habilidades=["Divinely Inspiring"], pid="PID_リュール", pos=(5, 5))
        rival = _u("Rival", defensa=5)
        base = _combate(_u("Louis"), rival)["atacante"]["daño_por_golpe"]
        ady = _combate(_u("Louis"), rival, aliados_cercanos_atk=[(alear, 1)])
        lejos = _combate(_u("Louis"), rival, aliados_cercanos_atk=[(alear, 2)])
        self.assertEqual(ady["atacante"]["daño_por_golpe"], base + 3)
        self.assertEqual(lejos["atacante"]["daño_por_golpe"], base)
        self.assertIn("Divinely Inspiring (Damage Boost) (de Alear) (+3 Atk)", ady["atacante"]["pasivas_activas"])
        # y el aliado adyacente recibe 1 de daño menos
        golpe = _combate(rival, _u("Louis"), HACHA, ESPADA, aliados_cercanos_def=[(alear, 1)])
        golpe_sin = _combate(rival, _u("Louis"), HACHA, ESPADA)
        self.assertEqual(golpe["atacante"]["daño_por_golpe"], golpe_sin["atacante"]["daño_por_golpe"] - 1)

    def test_crimson_cheer_es_reciproco(self):
        # "If unit is adjacent to the Divine Dragon, grants Avo+10 during combat to both of them" (bit 23 del Flag)
        framme = _u("Framme", habilidades=["Crimson Cheer"], pos=(5, 5))
        alear = _u("Alear", pid="PID_リュール", pos=(5, 6))
        otro = _u("Otro", pos=(5, 6))
        ctx_f = condicion_dsl.ContextoCombate(unidad=framme, rival=_u("E"), arma=ESPADA)
        self.assertEqual(pasivas.recopilar_combate(framme, ctx_f, [(alear, 1)]).get("avo"), 10)
        self.assertEqual(pasivas.recopilar_combate(framme, condicion_dsl.ContextoCombate(unidad=framme, rival=_u("E"), arma=ESPADA), [(otro, 1)]).get("avo"), 0)
        ctx_a = condicion_dsl.ContextoCombate(unidad=alear, rival=_u("E"), arma=ESPADA)
        self.assertEqual(pasivas.recopilar_combate(alear, ctx_a, [(framme, 1)]).get("avo"), 10)
        ctx_o = condicion_dsl.ContextoCombate(unidad=otro, rival=_u("E"), arma=ESPADA)
        self.assertEqual(pasivas.recopilar_combate(otro, ctx_o, [(framme, 1)]).get("avo"), 0)

    def test_spur_attack_anillo_de_vinculo(self):
        etie = _u("Etie", habilidades_sids=["SID_絆の指輪_アルフォンス"], pos=(1, 7))
        con = _combate(_u("Chloé"), _u("Rival"), aliados_cercanos_atk=[(etie, 1)])
        sin = _combate(_u("Chloé"), _u("Rival"), aliados_cercanos_atk=[(etie, 2)])
        self.assertEqual(con["atacante"]["daño_por_golpe"], sin["atacante"]["daño_por_golpe"] + 2)


class TestSyncYAmbosBandos(unittest.TestCase):

    def test_stalwart_reduce_efectividad_y_veteran_plus_la_anula(self):
        arco = Arma("Iron Bow", tipo="Arco", mt=6, wt=5, hit=85, crit=0, rango=[2], efectividades=["volador"])
        flier = _u("Flier", es_volador=True, tipo_movimiento="volador")
        stalwart = _u("Flier", es_volador=True, tipo_movimiento="volador", habilidades=["Stalwart"])
        veteran = _u("Flier", es_volador=True, tipo_movimiento="volador", habilidades=["Veteran+"])
        r0 = _combate(_u("Arquero"), flier, arco, None, distancia=2)
        r1 = _combate(_u("Arquero"), stalwart, arco, None, distancia=2)
        r2 = _combate(_u("Arquero"), veteran, arco, None, distancia=2)
        self.assertEqual(r0["atacante"]["daño_por_golpe"], 14 + 18 - 5)
        self.assertEqual(r1["atacante"]["daño_por_golpe"], 14 + 12 - 5)
        self.assertEqual(r2["atacante"]["daño_por_golpe"], 14 + 6 - 5)

    def test_sword_agility_solo_con_espada(self):
        u = _u("Espadachín", habilidades=["Sword Agility 1"])
        ctx = condicion_dsl.ContextoCombate(unidad=u, rival=_u("E"), arma=ESPADA)
        m = pasivas.recopilar_combate(u, ctx)
        self.assertEqual((m.get("avo"), m.get("crit")), (10, -10))   # SyncSid Crit-10 solo con espada
        m2 = pasivas.recopilar_combate(u, condicion_dsl.ContextoCombate(unidad=u, rival=_u("E"), arma=LANZA))
        self.assertEqual((m2.get("avo"), m2.get("crit")), (0, 0))

    def test_fair_fight_bonifica_a_ambos(self):
        diamant = _u("Diamant", habilidades=["Fair Fight"])
        rival = _u("Rival")
        con = _combate(diamant, rival)
        sin = _combate(_u("Diamant"), rival)
        self.assertEqual(con["atacante"]["precision"], min(100, sin["atacante"]["precision"] + 15))
        self.assertEqual(con["defensor"]["precision"], min(100, sin["defensor"]["precision"] + 15))
        # sin contraataque posible (相手の手番回数 == 0) no se activa
        lejos = _combate(diamant, rival, TOMO, HACHA, distancia=2)
        self.assertEqual(lejos["atacante"]["precision"], _combate(_u("Diamant"), rival, TOMO, HACHA, distancia=2)["atacante"]["precision"])

    def test_perceptive_solo_al_iniciar_y_truncado(self):
        alear = _u("Alear", velocidad=14, habilidades=["Perceptive"])
        rival = _u("Rival")
        ini = _combate(alear, rival)
        sin = _combate(_u("Alear", velocidad=14), rival)
        self.assertEqual(ini["defensor"]["precision"], sin["defensor"]["precision"] - 18)   # 15 + floor(14 * 0.25)
        dfn = _combate(rival, alear, HACHA, ESPADA)
        self.assertEqual(dfn["atacante"]["precision"], _combate(rival, _u("Alear", velocidad=14), HACHA, ESPADA)["atacante"]["precision"])

    def test_vantage_por_sid_y_umbral(self):
        leif = _u("Defensor", hp=10, hp_max=40, habilidades=["Vantage+"])   # 25 % <= 50 %
        res = _combate(_u("Atacante"), leif)
        self.assertEqual(res["resultado"]["secuencia"][0]["actor"], "Defensor")
        self.assertIn("Vantage+", res["resultado"]["secuencia"][0]["tipo"])
        sano = _u("Defensor", hp=30, hp_max=40, habilidades=["Vantage+"])   # 75 % > 50 %
        self.assertEqual(_combate(_u("Atacante"), sano)["resultado"]["secuencia"][0]["actor"], "Atacante")
        self.assertEqual(pasivas.umbral_vantage(leif), 50)
        self.assertEqual(pasivas.umbral_vantage(_u("X", habilidades=["Vantage++"])), 75)

    def test_thunder_no_hace_follow_up(self):
        mago = _u("Mago", magia=15, velocidad=20)
        lento = _u("Lento", velocidad=5)
        self.assertTrue(_combate(mago, lento, TOMO, HACHA)["atacante"]["tiene_follow_up"])
        self.assertFalse(_combate(mago, lento, THUNDER, HACHA)["atacante"]["tiene_follow_up"])
        # y tampoco al contraatacar con Thunder
        self.assertFalse(_combate(lento, mago, HACHA, THUNDER)["defensor"]["tiene_follow_up"])

    def test_trained_to_kill_usa_el_terreno_propio(self):
        yunaka = _u("Yunaka", habilidades=["Trained to Kill"])
        bosque = Terreno(avo=30, dfn=0)
        propio = _combate(yunaka, _u("Rival"), terreno_atk=bosque)
        ajeno = _combate(yunaka, _u("Rival"), terreno_def=bosque)
        self.assertEqual(propio["atacante"]["prob_critico"], ajeno["atacante"]["prob_critico"] + 15)
        self.assertIn("Trained to Kill (+15 Crit)", propio["atacante"]["pasivas_activas"])

    def test_moved_to_tears_suma_2_por_golpe_con_chain_attack(self):
        boucheron = _u("Boucheron", habilidades=["Moved to Tears"])
        apoyo = _u("Apoyo", estilo_combate="連携スタイル")
        setattr(apoyo, "arma", ESPADA)
        rival = _u("Rival", hp=60, hp_max=60)
        sin = _combate(boucheron, rival)
        con = _combate(boucheron, rival, aliados_apoyo_backup=[apoyo])
        self.assertEqual(con["atacante"]["daño_por_golpe"], sin["atacante"]["daño_por_golpe"] + 2)
        self.assertIn("Moved to Tears (+2 Atk)", con["atacante"]["pasivas_activas"])
        self.assertFalse(any("Sensible" in s["tipo"] for s in con["resultado"]["secuencia"]))


class TestEstilosComoSids(unittest.TestCase):

    def test_encubierto_duplica_solo_el_avo_del_terreno(self):
        fuerte = Terreno(avo=30, dfn=3)
        yunaka = _u("Yunaka", estilo_combate="隠密スタイル")
        normal = _u("Normal")
        r_y = _combate(_u("Atacante"), yunaka, terreno_def=fuerte)
        r_n = _combate(_u("Atacante"), normal, terreno_def=fuerte)
        self.assertEqual(r_y["atacante"]["precision"], r_n["atacante"]["precision"] - 30)   # 60 vs 30 de Avo
        self.assertEqual(r_y["atacante"]["daño_por_golpe"], r_n["atacante"]["daño_por_golpe"])   # Def del terreno: igual (datamine: solo 地形回避)

    def test_mistico_ignora_el_avo_del_terreno_solo_con_tomo(self):
        fuerte = Terreno(avo=30, dfn=0)
        mago = _u("Céline", estilo_combate="魔法スタイル", magia=12)
        con_tomo = _combate(mago, _u("Rival"), TOMO, HACHA, terreno_def=fuerte)
        con_tomo_llano = _combate(mago, _u("Rival"), TOMO, HACHA)
        self.assertEqual(con_tomo["atacante"]["precision"], con_tomo_llano["atacante"]["precision"])
        levin = Arma("Levin Sword", tipo="Espada", mt=8, wt=9, hit=80, crit=0, rango=[1, 2], es_magica=True)
        con_levin = _combate(mago, _u("Rival"), levin, HACHA, terreno_def=fuerte)
        self.assertEqual(con_levin["atacante"]["precision"], _combate(mago, _u("Rival"), levin, HACHA)["atacante"]["precision"] - 30)

    def test_acorazado_no_sufre_ruptura(self):
        armor = _u("Armor", estilo_combate="重装スタイル")
        res = _combate(_u("Espadachín"), armor, ESPADA, HACHA)   # espada > hacha
        self.assertFalse(res["resultado"]["aplica_ruptura"])
        self.assertTrue(_combate(_u("Espadachín"), _u("Normal"), ESPADA, HACHA)["resultado"]["aplica_ruptura"])


class TestOverlayDLC(unittest.TestCase):

    def test_weapon_sync_segun_lider_y_en_fusion(self):
        rival = _u("Rival")
        chloe = _u("Chloé", habilidades=["Weapon Sync"], emblema_nombre="Edelgard / Dimitri / Claude")
        setattr(chloe, "lider_tres_casas", "Dimitri")
        base = _combate(_u("Chloé"), rival, LANZA, HACHA)["atacante"]["daño_por_golpe"]
        self.assertEqual(_combate(chloe, rival, LANZA, HACHA)["atacante"]["daño_por_golpe"], base + 5)
        self.assertEqual(_combate(chloe, rival, ESPADA, HACHA)["atacante"]["daño_por_golpe"], _combate(_u("Chloé"), rival, ESPADA, HACHA)["atacante"]["daño_por_golpe"])
        chloe.en_fusion = True
        self.assertEqual(_combate(chloe, rival, ESPADA, HACHA)["atacante"]["daño_por_golpe"], _combate(_u("Chloé"), rival, ESPADA, HACHA)["atacante"]["daño_por_golpe"] + 5)
        plus = _u("Chloé", habilidades=["Weapon Sync+"], emblema_nombre="Edelgard / Dimitri / Claude", en_fusion=True)
        self.assertEqual(_combate(plus, rival, LANZA, HACHA)["atacante"]["daño_por_golpe"], base + 7)
        # solo al iniciar
        self.assertEqual(_combate(rival, plus, HACHA, LANZA)["defensor"]["daño_por_golpe"], _combate(rival, _u("Chloé"), HACHA, LANZA)["defensor"]["daño_por_golpe"])

    def test_geosphere_aura_de_def_res(self):
        tiki = _u("Portador", habilidades=["Geosphere"], pos=(3, 3))
        rival = _u("Rival", fuerza=20)
        con = _combate(rival, _u("Aliado"), HACHA, ESPADA, aliados_cercanos_def=[(tiki, 1)])
        sin = _combate(rival, _u("Aliado"), HACHA, ESPADA)
        self.assertEqual(con["atacante"]["daño_por_golpe"], sin["atacante"]["daño_por_golpe"] - 3)
        con_m = _combate(_u("Mago", magia=20), _u("Aliado"), TOMO, ESPADA, aliados_cercanos_def=[(tiki, 1)])
        sin_m = _combate(_u("Mago", magia=20), _u("Aliado"), TOMO, ESPADA)
        self.assertEqual(con_m["atacante"]["daño_por_golpe"], sin_m["atacante"]["daño_por_golpe"] - 3)


class _T:
    def __init__(self, caminable=True, volable=True):
        self.caminable, self.volable, self.coste_mov = caminable, volable, 1


class TestAdvance(unittest.TestCase):

    def test_casillas_advance_geometria(self):
        grid = [[_T() for _ in range(6)] for _ in range(6)]
        grid[2][4] = _T(caminable=False)   # muro
        alcanzables = {(2, 0), (2, 1), (2, 2), (1, 2), (3, 2)}
        enemigos = {(2, 4), (5, 2)}
        ocupadas = {(3, 3)}
        adv = casillas_advance(alcanzables, enemigos, ocupadas | enemigos, grid, 6, 6, es_volador=False)
        # Enemigo (5,2): desde (3,2) (distancia 2) se avanza a (4,2)
        self.assertEqual(adv.get((4, 2)), (3, 2))
        # Enemigo (2,4) (sobre muro, da igual): desde (2,2) se avanzaría a (2,3) o (1,3)/(3,3): (3,3) ocupada
        self.assertEqual(adv.get((2, 3)), (2, 2))
        self.assertNotIn((3, 3), adv)
        # una casilla ya alcanzable no cuenta como Advance
        self.assertNotIn((2, 2), adv)

    def test_sid_advance_por_nombre(self):
        roy = _u("Alfred", habilidades=["Advance"])
        self.assertTrue(pasivas.tiene_advance(roy))
        self.assertFalse(pasivas.tiene_advance(_u("Alfred")))


class TestAdvanceEnTablero(unittest.TestCase):

    def setUp(self):
        from app import tablero
        tablero.limpiar()

    def test_recomendacion_y_mover_con_advance(self):
        from app import app, tablero, _mapa, resolver_unidad_con_catalogo, encontrar_pos_ataque_optima
        # Columna de 4 casillas transitables del mapa cargado: Alfred (mov 1) en la
        # primera, enemigo en la cuarta: sin Advance no llega (la 3ª está a 2 pasos)
        def _libre(x, y):
            t = _mapa.grid[x][y]
            return getattr(t, "caminable", True) and getattr(t, "coste_mov", 1) == 1
        col = next(((x, y) for x in range(_mapa.ancho) for y in range(_mapa.alto - 3)
                    if all(_libre(x, y + k) for k in range(4))), None)
        self.assertIsNotNone(col)
        x0, y0 = col
        alfred = resolver_unidad_con_catalogo({
            "nombre": "Alfred", "x": x0, "y": y0, "mov": 1, "es_aliado": True,
            "arma_nombre": "Iron Lance", "habilidades": ["Advance"], "stats": {"hp": 30, "fuerza": 12, "velocidad": 10}
        })
        tablero.registrar_unidad(alfred)
        ene = resolver_unidad_con_catalogo({
            "nombre": "Bandit", "x": x0, "y": y0 + 3, "mov": 4, "es_aliado": False,
            "arma_nombre": "Iron Axe", "stats": {"hp": 20, "defensa": 3}
        })
        tablero.registrar_unidad(ene)
        self.assertTrue(pasivas.tiene_advance(alfred))
        detalle = {}
        pos = encontrar_pos_ataque_optima(alfred, ene, alfred.arma, detalle=detalle)
        self.assertIsNotNone(pos)
        self.assertEqual(abs(pos[0] - ene.x) + abs(pos[1] - ene.y), 1)
        self.assertIsNotNone(detalle["advance_desde"])
        self.assertEqual(abs(detalle["advance_desde"][0] - x0) + abs(detalle["advance_desde"][1] - y0), 1)

        client = app.test_client()
        rango = client.get("/api/unidad/rango_movimiento?nombre=Alfred").get_json()
        self.assertIn(list(pos), rango["casillas_advance"])
        self.assertNotIn(list(pos), rango["casillas"])
        res = client.post("/api/mover", json={"nombre": "Alfred", "x": pos[0], "y": pos[1]}).get_json()
        self.assertTrue(res.get("ok"), res)
        self.assertEqual(res["advance_desde"], detalle["advance_desde"])
        # sin la habilidad, la misma casilla se rechaza
        tablero.limpiar()
        sin = resolver_unidad_con_catalogo({
            "nombre": "Alfred", "x": x0, "y": y0, "mov": 1, "es_aliado": True,
            "arma_nombre": "Iron Lance", "stats": {"hp": 30, "fuerza": 12, "velocidad": 10}
        })
        tablero.registrar_unidad(sin)
        tablero.registrar_unidad(ene)
        res2 = client.post("/api/mover", json={"nombre": "Alfred", "x": pos[0], "y": pos[1]})
        self.assertEqual(res2.status_code, 400)


if __name__ == "__main__":
    unittest.main()
