# -*- coding: utf-8 -*-
"""
Emblema Soren (DLC). Datos de https://serenesforest.net/engage/emblems/soren/ y stats de
las armas verificadas en juego por el jugador (Mt, Hit, Crit, Wt, Avo, Ddg, Rango):

    Bolting:     2,  50,  0, 15, 0, 0, 3-10   (no puede atacar a 1-2)
    Rexcalibur: 16, 105, 10, 12, 0, 0, 1-2    (efectivo contra voladores)

Pendiente: la geometría de Cataclysm y las stats del báculo Reflect.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import catalogo_loader as cl                                                  # noqa: E402
import pasivas                                                               # noqa: E402
import pasivas_temporales                                                    # noqa: E402
from motor_analisis import _armas_aliado                                     # noqa: E402
from motor_calculo import CalculadoraEngage, Terreno                         # noqa: E402
from ataques_area import resolver_ataque_area                                # noqa: E402
from app import app, tablero, _mapa                                          # noqa: E402

MAGA = {"hp": 40, "fuerza": 10, "magia": 26, "destreza": 18, "velocidad": 20,
        "defensa": 10, "resistencia": 18, "suerte": 10, "complexion": 5}


def _soren(vinculo=20, fusion=False, tomo="Elfire", **extra):
    datos = {"nombre": "Celine", "es_aliado": True, "nivel": 15, "clase_nombre": "Sage",
             "emblema_nombre": "Soren", "nivel_vinculo": vinculo, "en_fusion": fusion,
             "stats": dict(MAGA), "inventario": [{"nombre": tomo, "equipada": True}],
             "x": 0, "y": 0}
    datos.update(extra)
    return cl.resolver_unidad_con_catalogo(datos, tablero=None)


def _rival(clase="General", **extra):
    datos = {"nombre": "Rival", "es_aliado": False, "nivel": 12, "clase_nombre": clase,
             "stats": {"hp": 45, "fuerza": 18, "magia": 0, "destreza": 12, "velocidad": 12,
                       "defensa": 16, "resistencia": 10, "suerte": 6, "complexion": 10},
             "inventario": [{"nombre": "Steel Axe", "equipada": True}], "x": 1, "y": 0}
    datos.update(extra)
    return cl.resolver_unidad_con_catalogo(datos, tablero=None)


def _armas(u):
    return {a.nombre: a for a, _, _ in _armas_aliado(u)}


class TestArmas(unittest.TestCase):

    def test_stats(self):
        armas = _armas(_soren())
        bolting = armas["Bolting (Emblema)"]
        self.assertEqual((bolting.mt, bolting.hit, bolting.crit, bolting.wt), (2, 50, 0, 15))
        rex = armas["Rexcalibur (Emblema)"]
        self.assertEqual((rex.mt, rex.hit, rex.crit, rex.wt, rex.rango), (16, 105, 10, 12, [1, 2]))

    def test_bolting_no_alcanza_de_cerca(self):
        """3-10: no se puede atacar con ella a 1 ni a 2 casillas."""
        bolting = _armas(_soren())["Bolting (Emblema)"]
        self.assertEqual(bolting.rango, list(range(3, 11)))
        self.assertNotIn(1, bolting.rango)
        self.assertNotIn(2, bolting.rango)

    def test_bolting_no_persigue(self):
        """"Cannot follow up": un solo golpe aunque doble de velocidad."""
        celine, rival = _soren(), _rival()
        armas = _armas(celine)
        def golpes(arma, dist):
            r = CalculadoraEngage.simular_combate(celine.stats, rival.stats, arma, rival.arma,
                                                  Terreno(), Terreno(), dist)
            return r["atacante"]["golpes_en_ronda"]
        self.assertEqual(golpes(armas["Elfire"], 2), 2, "con un tomo normal sí dobla")
        self.assertEqual(golpes(armas["Bolting (Emblema)"], 3), 1)

    def test_rexcalibur_es_efectivo_contra_voladores(self):
        celine = _soren()
        rex = _armas(celine)["Rexcalibur (Emblema)"]
        contra_volador = CalculadoraEngage.simular_combate(
            celine.stats, _rival("Wyvern Knight").stats, rex, None, Terreno(), Terreno(), 1)
        contra_infante = CalculadoraEngage.simular_combate(
            celine.stats, _rival("General").stats, rex, None, Terreno(), Terreno(), 1)
        self.assertGreater(contra_volador["atacante"]["daño_por_golpe"],
                           contra_infante["atacante"]["daño_por_golpe"])

    def test_las_armas_se_desbloquean_por_vinculo(self):
        self.assertIn("Bolting (Emblema)", _armas(_soren(vinculo=1)),
                      "Bolting entra ya a vínculo 1")
        self.assertNotIn("Rexcalibur (Emblema)", _armas(_soren(vinculo=14)))
        self.assertIn("Rexcalibur (Emblema)", _armas(_soren(vinculo=15)))

    def test_el_elemento_de_los_tomos_sale_del_datamine(self):
        """Item.xml `WeaponAttr`. Anima Focus lo necesita para saber qué efecto aplica."""
        armas = (cl._catalogo.get("armas") or {})
        por_nombre = {v.get("nombre"): v.get("elemento") for v in armas.values()}
        self.assertEqual(por_nombre["Fire"], "fuego")
        self.assertEqual(por_nombre["Thunder"], "trueno")
        self.assertEqual(por_nombre["Excalibur"], "viento")
        self.assertEqual(por_nombre["Bolting"], "trueno")
        self.assertEqual(por_nombre["Rexcalibur"], "viento")
        self.assertIsNone(por_nombre["Steel Axe"], "solo los tomos tienen elemento")


class TestSincronias(unittest.TestCase):

    def test_se_desbloquean_por_nivel(self):
        def pasivas_de(v):
            return list(getattr(_soren(vinculo=v).stats, "habilidades", []) or [])
        self.assertIn("Assign Decoy", pasivas_de(1))
        self.assertNotIn("Anima Focus", pasivas_de(3))
        self.assertIn("Anima Focus", pasivas_de(4))
        self.assertIn("Keen Insight", pasivas_de(9))
        self.assertIn("Keen Insight+", pasivas_de(18))
        self.assertNotIn("Keen Insight", pasivas_de(18))

    def test_keen_insight_suma_solo_con_efectividad(self):
        celine = _soren(vinculo=9)
        rex = _armas(_soren(vinculo=20))["Rexcalibur (Emblema)"]
        sin_emblema = cl.resolver_unidad_con_catalogo({
            "nombre": "Otra", "es_aliado": True, "nivel": 15, "clase_nombre": "Sage",
            "stats": dict(MAGA), "inventario": [{"nombre": "Elfire", "equipada": True}],
            "x": 0, "y": 0}, tablero=None)

        def daño(unidad, clase):
            return CalculadoraEngage.simular_combate(
                unidad.stats, _rival(clase).stats, rex, None, Terreno(), Terreno(), 1
            )["atacante"]["daño_por_golpe"]

        self.assertEqual(daño(celine, "Wyvern Knight") - daño(sin_emblema, "Wyvern Knight"), 5)
        self.assertEqual(daño(celine, "General"), daño(sin_emblema, "General"),
                         "sin efectividad no suma nada")

    def test_keen_insight_plus_suma_7(self):
        rex = _armas(_soren(vinculo=18))["Rexcalibur (Emblema)"]
        def daño(v):
            return CalculadoraEngage.simular_combate(
                _soren(vinculo=v).stats, _rival("Wyvern Knight").stats, rex, None,
                Terreno(), Terreno(), 1)["atacante"]["daño_por_golpe"]
        self.assertEqual(daño(18) - daño(9), 2, "de +5 a +7")


class TestFlare(unittest.TestCase):
    """Habilidad de Fusión: con tomos, Res del rival -20 % y cura el 50 % del daño."""

    def _daño(self, fusion, arma="Elfire", dist=2):
        celine = _soren(fusion=fusion)
        r = CalculadoraEngage.simular_combate(
            celine.stats, _rival().stats, _armas(celine)[arma], _rival().arma,
            Terreno(), Terreno(), dist)["atacante"]
        return r["daño_por_golpe"], r["golpes_en_ronda"]

    def test_baja_la_resistencia_del_rival(self):
        """
        Ground truth (Céline, Mística): contra un Lance Flier de Res 14, con Elfire pasa de
        19 a 24 al fusionarse y con un Elwind forjado de Mt 7 de 34 a 39. Los dos son +5,
        porque la Res que aplica cae de 14 a floor(14 * 0.7) = 9.

        El 0.7 es "Res-20%" más el "[Mystical] Extra -10% to foe's Res" del propio Flare.
        El cambio va en la estadística del rival, así que entra en los dos golpes si dobla.
        """
        # La unidad del helper es Sage, o sea Mística: -30 %
        sin, golpes_sin = self._daño(False)
        con, golpes_con = self._daño(True)
        self.assertEqual(con - sin, 3, "Res 10 -> floor(10 * 0.7) = 7")
        self.assertEqual(golpes_sin, golpes_con, "sigue doblando: el bono va en los dos golpes")

    def test_la_medida_del_lance_flier(self):
        volador = cl.resolver_unidad_con_catalogo({
            "nombre": "Lance Flier", "es_aliado": False, "nivel": 10, "clase_nombre": "Lance Flier",
            "stats": {"hp": 30, "fuerza": 14, "magia": 0, "destreza": 10, "velocidad": 10,
                      "defensa": 8, "resistencia": 14, "suerte": 4, "complexion": 7},
            "inventario": [{"nombre": "Steel Lance", "equipada": True}], "x": 1, "y": 0}, tablero=None)

        def daño(fusion, arma):
            celine = cl.resolver_unidad_con_catalogo({
                "nombre": "Celine", "es_aliado": True, "nivel": 15, "clase_nombre": "Sage",
                "emblema_nombre": "Soren", "nivel_vinculo": 10, "en_fusion": fusion,
                "stats": dict(MAGA, magia=22), "x": 0, "y": 0,
                "inventario": [{"nombre": "Elfire", "equipada": True}, {"nombre": "Elwind"}]}, tablero=None)
            return CalculadoraEngage.simular_combate(
                celine.stats, volador.stats, _armas(celine)[arma], volador.arma,
                Terreno(), Terreno(), 1)["atacante"]["daño_por_golpe"]

        self.assertEqual(daño(False, "Elfire"), 19, "22 + 11 - 14")
        self.assertEqual(daño(False, "Elwind"), 34, "22 + 7x3 - 14, +5 de Keen Insight")
        self.assertEqual(daño(True, "Elfire"), 24, "Flare: Res 14 -> 9")
        self.assertEqual(daño(True, "Elwind"), 39)

    def test_sin_estilo_mistico_el_recorte_es_menor(self):
        """Sin el extra de Místico, Flare es -20 %: Res 10 -> 8, o sea +2 en vez de +3."""
        def daño(clase, fusion):
            u = cl.resolver_unidad_con_catalogo({
                "nombre": "Otra", "es_aliado": True, "nivel": 15, "clase_nombre": clase,
                "emblema_nombre": "Soren", "nivel_vinculo": 10, "en_fusion": fusion,
                "stats": dict(MAGA), "inventario": [{"nombre": "Elfire", "equipada": True}],
                "x": 0, "y": 0}, tablero=None)
            return CalculadoraEngage.simular_combate(
                u.stats, _rival().stats, _armas(u)["Elfire"], _rival().arma,
                Terreno(), Terreno(), 2)["atacante"]["daño_por_golpe"]

        self.assertEqual(daño("Mage Knight", True) - daño("Mage Knight", False), 2)

    def test_solo_con_tomos(self):
        celine = _soren(fusion=True, tomo="Steel Sword", clase_nombre="Hero")
        r = CalculadoraEngage.simular_combate(
            celine.stats, _rival().stats, _armas(celine)["Steel Sword"], None,
            Terreno(), Terreno(), 1)["atacante"]
        self.assertFalse([x for x in r["pasivas_activas"] if "Flare" in x])

    def test_solo_en_fusion(self):
        self.assertNotIn("Flare", getattr(_soren(fusion=False).stats, "habilidades", []) or [])
        self.assertIn("Flare", getattr(_soren(fusion=True).stats, "habilidades", []) or [])


class TestAnimaFocus(unittest.TestCase):
    """
    "When using tomes, unit inflicts Def-3 with fire, Hit-20 with thunder, or Mov-2 with
    wind magic for 1 turn". El lastre se queda en el objetivo hasta su siguiente fase, así
    que lo aprovechan también los demás aliados que le peguen después.
    """

    def setUp(self):
        tablero.limpiar()
        tablero.turno_actual = 1
        tablero.fase = "jugador"
        self.rival = _rival()
        self.rival.x, self.rival.y = 5, 5
        tablero.registrar_unidad(self.rival, resolver_colision=False)

    def _atacar_con(self, tomo):
        celine = _soren(vinculo=20, tomo=tomo)
        celine.x, celine.y = 5, 4
        tablero.registrar_unidad(celine, resolver_colision=False)
        return pasivas_temporales.anima_focus(tablero, celine, self.rival, celine.arma)

    def test_fuego_baja_la_defensa(self):
        self.assertTrue(self._atacar_con("Elfire"))
        self.assertTrue(self.rival.tiene_estado_temporal("SID_理魔法＋_炎_効果"))
        celine = _soren()
        armas = _armas(celine)
        r = CalculadoraEngage.simular_combate(
            celine.stats, self.rival.stats, armas["Elfire"], None, Terreno(), Terreno(), 2)
        self.assertIn("Anima Focus (fuego) del defensor (-3 Defensa)", str(r["defensor"]["pasivas_activas"])
                      + str(r["atacante"]["pasivas_activas"]))

    def test_trueno_baja_la_precision(self):
        celine = _soren()
        arma_celine = _armas(celine)["Elfire"]
        def hit_del_rival():
            r = CalculadoraEngage.simular_combate(
                self.rival.stats, celine.stats, self.rival.arma, arma_celine, Terreno(), Terreno(), 1)
            return r["atacante"]["precision"]
        antes = hit_del_rival()
        self.assertTrue(self._atacar_con("Thunder"))
        self.assertTrue(self.rival.tiene_estado_temporal("SID_理魔法＋_雷_効果"))
        self.assertEqual(hit_del_rival(), antes - 20)

    def test_viento_no_quita_movimiento(self):
        """El texto dice Mov-2, pero en el juego el enemigo conserva su movimiento
        (verificado por el jugador): el estado se marca, sin tocar el Mov."""
        base = self.rival.movimiento_disponible
        self.assertTrue(self._atacar_con("Wind"))
        self.assertTrue(self.rival.tiene_estado_temporal("SID_理魔法＋_風_効果"))
        self.assertEqual(self.rival.movimiento_disponible, base)

    def test_caduca_en_la_siguiente_fase_del_objetivo(self):
        self._atacar_con("Elfire")
        efecto = "SID_理魔法＋_炎_効果"
        self.assertTrue(self.rival.tiene_estado_temporal(efecto))
        tablero.iniciar_fase_enemigo()
        self.assertTrue(self.rival.tiene_estado_temporal(efecto), "dura toda su fase")
        tablero.avanzar_turno()
        tablero.iniciar_fase_enemigo()
        self.assertFalse(self.rival.tiene_estado_temporal(efecto))

    def test_sin_tomo_no_hace_nada(self):
        celine = _soren(vinculo=20, tomo="Steel Sword", clase_nombre="Hero")
        self.assertEqual(pasivas_temporales.anima_focus(tablero, celine, self.rival, celine.arma), [])

    def test_sin_la_sincronia_no_hace_nada(self):
        otra = _soren(vinculo=3, tomo="Elfire")
        self.assertEqual(pasivas_temporales.anima_focus(tablero, otra, self.rival, otra.arma), [])


class TestCataclysm(unittest.TestCase):
    """
    "Use to attack foes in an area with fire, thunder and wind magic at 40% damage.
    Wind is effective: Flying. [Mystical] +10% damage."

    No usa ninguna arma del inventario: pega con una magia propia de Mt 12, tres veces, y
    cada golpe es el daño normal truncado al 40 %, o al 44 % si quien lo lanza es Místico.

    Cuatro medidas en partida, todas contra el mismo Lance Flier de Res 14 salvo la
    primera, y las cuatro las reproduce el motor:

        Céline   Magia 22, Keen Insight   vs Mage Res 17     ->  7/7/7   (25 HP -> 4)
        Céline   Magia 22, Keen Insight   vs Flier Res 14    ->  8/8/15
        la misma con +3 de ataque                            -> 10/10/16
        Citrinne Magia 21, SIN Keen Insight, vs Flier Res 14 ->  8/8/12

    De las dos últimas salen las dos cosas que no se podían deducir de una sola unidad:
    que el golpe de viento efectivo aporta Mt 22 (no el x3 = 36 de las armas normales) y
    que Keen Insight suma su bono al daño BASE, antes del reparto.
    """

    def _maga(self, magia, vinculo=10, clase="Sage"):
        return cl.resolver_unidad_con_catalogo({
            "nombre": "Maga", "es_aliado": True, "nivel": 15, "clase_nombre": clase,
            "emblema_nombre": "Soren", "nivel_vinculo": vinculo, "en_fusion": True,
            "stats": dict(MAGA, magia=magia, fuerza=13, destreza=16),
            "inventario": [{"nombre": "Elfire", "equipada": True}], "x": 0, "y": 0}, tablero=None)

    def _blanco(self, clase, res, hp=30):
        return cl.resolver_unidad_con_catalogo({
            "nombre": "Blanco", "es_aliado": False, "nivel": 10, "clase_nombre": clase,
            "stats": {"hp": hp, "fuerza": 8, "magia": 14, "destreza": 10, "velocidad": 10,
                      "defensa": 8, "resistencia": res, "suerte": 4, "complexion": 5},
            "inventario": [{"nombre": "Steel Lance", "equipada": True}], "x": 1, "y": 0}, tablero=None)

    def _golpes(self, blanco, magia=22, vinculo=10, clase="Sage"):
        maga = self._maga(magia, vinculo, clase)
        r = CalculadoraEngage.simular_combate(
            maga.stats, blanco.stats, _armas(maga)["Cataclysm"], blanco.arma,
            Terreno(), Terreno(), 1, es_engage_attack=True, engage_attack_nombre="Cataclysm")
        return r["atacante"]["houses_unite_hits"]

    def test_celine_contra_el_mage(self):
        blanco = self._blanco("Mage", 17, hp=25)
        golpes = self._golpes(blanco)
        self.assertEqual(golpes, [7, 7, 7])
        self.assertEqual(25 - sum(golpes), 4, "de 25 HP a 4")

    def test_celine_contra_el_lance_flier(self):
        self.assertEqual(self._golpes(self._blanco("Lance Flier", 14)), [8, 8, 15])

    def test_celine_con_bono_de_ataque(self):
        self.assertEqual(self._golpes(self._blanco("Lance Flier", 14), magia=25), [10, 10, 16])

    def test_keen_insight_entra_antes_del_reparto(self):
        """
        Si entrara después del reparto, el golpe de viento se llevaría los +5 enteros;
        entrando antes se queda en floor(0.44 x 5) = 2.

        Es lo que se ve comparando a Céline (15) con Citrinne (12), que no la tiene. Lo
        que ese par NO permite todavía es fijar el resto: con Magia 18 los 8/8 de Citrinne
        no salen con ningún Mt compatible con Céline (ver el comentario de MT_VIENTO_EFECTIVO
        en motor_calculo), así que aquí solo se fija la diferencia, no sus números.
        """
        con = self._golpes(self._blanco("Lance Flier", 14), magia=22, vinculo=10)[2]
        sin = self._golpes(self._blanco("Lance Flier", 14), magia=22, vinculo=1)[2]
        self.assertEqual(con - sin, 2, "floor de 0.44 x 5, no 5")

    def test_los_tres_golpes_son_iguales_sin_efectividad(self):
        for res in (10, 15, 20):
            golpes = self._golpes(self._blanco("Mage", res))
            self.assertEqual(len(set(golpes)), 1, f"Res {res}: {golpes}")

    def test_el_bono_mistico_del_ataque(self):
        """"[Mystical] +10% damage": la misma unidad sin ese estilo pega menos."""
        blanco = self._blanco("Mage", 17)
        self.assertLess(self._golpes(blanco, clase="Warrior")[0], self._golpes(blanco)[0])

    def test_no_usa_ningun_arma_del_inventario(self):
        armas = _armas(self._maga(22))
        self.assertIn("Cataclysm", armas)
        self.assertNotIn("Cataclysm (Elfire)", armas, "no es un ataque de arma variable")
        self.assertEqual(armas["Cataclysm"].tipo, "Tomo")


class TestGeometriaDeCataclysm(unittest.TestCase):
    """Cruz centrada en el OBJETIVO: él y las cuatro casillas de su alrededor."""

    def setUp(self):
        tablero.limpiar()
        self.celine = _soren(vinculo=20, fusion=True)
        self.celine.x, self.celine.y = 5, 7
        tablero.registrar_unidad(self.celine, resolver_colision=False)

    def _enemigo(self, nombre, x, y):
        e = _rival()
        e.nombre, e.x, e.y = nombre, x, y
        tablero.registrar_unidad(e, resolver_colision=False)
        return e

    def test_alcanza_al_objetivo_y_a_sus_cuatro_vecinos(self):
        centro = self._enemigo("Centro", 5, 6)
        self._enemigo("Arriba", 5, 5)
        self._enemigo("Izquierda", 4, 6)
        self._enemigo("Derecha", 6, 6)
        self._enemigo("Lejos", 7, 4)
        area = resolver_ataque_area("Cataclysm", (self.celine.x, self.celine.y),
                                    centro, self.celine, tablero, _mapa)
        self.assertTrue(area["valido"], area["motivo"])
        self.assertEqual(sorted(o.nombre for o in area["objetivos"]),
                         ["Arriba", "Centro", "Derecha", "Izquierda"])
        self.assertEqual(len(area["casillas_dano"]), 5)

    def test_las_diagonales_no_entran(self):
        centro = self._enemigo("Centro", 5, 6)
        self._enemigo("Diagonal", 6, 5)
        area = resolver_ataque_area("Cataclysm", (self.celine.x, self.celine.y),
                                    centro, self.celine, tablero, _mapa)
        self.assertEqual([o.nombre for o in area["objetivos"]], ["Centro"])

    def test_no_alcanza_a_los_aliados(self):
        centro = self._enemigo("Centro", 5, 6)
        amigo = _soren()
        amigo.nombre, amigo.x, amigo.y = "Amigo", 4, 6
        tablero.registrar_unidad(amigo, resolver_colision=False)
        area = resolver_ataque_area("Cataclysm", (self.celine.x, self.celine.y),
                                    centro, self.celine, tablero, _mapa)
        self.assertEqual([o.nombre for o in area["objetivos"]], ["Centro"])


if __name__ == "__main__":
    unittest.main()
