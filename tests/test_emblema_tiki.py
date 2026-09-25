# -*- coding: utf-8 -*-
"""
Emblema Tiki (DLC). Los datos salen de https://serenesforest.net/engage/emblems/tiki/ y
viven en `json/dlc_emblems_canon.json` (qué se desbloquea a cada nivel de vínculo) y en
`pasivas_overlay.py` (qué hace cada pasiva), porque el DLC no está en el datamine.

Sincronías: Starsphere 1 · Geosphere 3 · Lifesphere 8 · Lightsphere 10 ·
            Lifesphere+ 14 · Geosphere+ 16 · Lifesphere++ 19
Fusión:     Draconic Form (Nv 1)
Heredables: HP/Lck +2/+4/+6/+8/+10 (2, 7, 12, 15, 18) ·
            Special Guard 1..5 (4, 9, 13, 17, 19)
"""
import json
import unittest

import catalogo_loader as cl
import pasivas
import pasivas_temporales as pt
from app import app, tablero
from motor_calculo import CalculadoraEngage, Terreno

STATS = {"hp": 40, "fuerza": 20, "magia": 6, "destreza": 18, "velocidad": 18,
         "defensa": 14, "resistencia": 10, "suerte": 10, "complexion": 8}


def _con_tiki(nombre, vinculo, **kw):
    datos = {"nombre": nombre, "es_aliado": True, "nivel": 15, "clase_nombre": "Swordmaster",
             "stats": dict(STATS), "emblema_nombre": "Tiki", "nivel_vinculo": vinculo,
             "inventario": [{"nombre": "Steel Sword", "equipada": True}], "x": 0, "y": 0}
    datos.update(kw)
    return cl.resolver_unidad_con_catalogo(datos, tablero=kw.get("_tablero"))


def _rival():
    return cl.resolver_unidad_con_catalogo({
        "nombre": "Bruto", "es_aliado": False, "nivel": 12, "clase_nombre": "Axe Fighter",
        "stats": {"hp": 55, "fuerza": 16, "magia": 0, "destreza": 14, "velocidad": 14,
                  "defensa": 12, "resistencia": 6, "suerte": 8, "complexion": 8},
        "inventario": [{"nombre": "Killer Axe", "equipada": True}], "x": 1, "y": 0}, tablero=None)


class TestDatosPorNivelDeVinculo(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open("json/dlc_emblems_canon.json", encoding="utf-8") as f:
            cls.tiki = json.load(f)["GID_DLC_TIKI"]

    def _sync(self, lvl):
        return [s["nombre"] for s in self.tiki["bond_levels"][str(lvl)]["synchro_skills"]]

    def test_cada_sincronia_en_su_nivel(self):
        esperado = {1: "Starsphere", 3: "Geosphere", 8: "Lifesphere", 10: "Lightsphere",
                    14: "Lifesphere+", 16: "Geosphere+", 19: "Lifesphere++"}
        for lvl, nombre in esperado.items():
            self.assertIn(nombre, self._sync(lvl), f"{nombre} debe estar al vínculo {lvl}")
            if lvl > 1:
                self.assertNotIn(nombre, self._sync(lvl - 1), f"{nombre} no debe estar al {lvl - 1}")

    def test_las_mejoras_sustituyen_a_la_version_base(self):
        self.assertIn("Lifesphere", self._sync(13))
        self.assertNotIn("Lifesphere", self._sync(14))     # la sustituye Lifesphere+
        self.assertIn("Geosphere", self._sync(15))
        self.assertNotIn("Geosphere", self._sync(16))      # la sustituye Geosphere+

    def test_bonos_de_stats_por_nivel(self):
        # Tabla de Serenes Forest: solo cambian en estos niveles
        esperado = {1: (5, 1, 2), 2: (5, 1, 4), 4: (5, 2, 4), 7: (7, 2, 4), 9: (7, 2, 6),
                    12: (7, 3, 6), 13: (10, 3, 6), 15: (10, 3, 8), 17: (10, 4, 8), 18: (10, 4, 10)}
        for lvl, (hp, df, lck) in esperado.items():
            b = self.tiki["bond_levels"][str(lvl)]["stat_boosts"]
            self.assertEqual((b.get("hp"), b.get("def"), b.get("lck")), (hp, df, lck), f"vínculo {lvl}")

    def test_heredables_con_su_coste_de_sp(self):
        esperado = {2: ("HP/Lck +2", "200"), 4: ("Special Guard 1", "200"), 7: ("HP/Lck +4", "600"),
                    9: ("Special Guard 2", "400"), 12: ("HP/Lck +6", "1100"), 13: ("Special Guard 3", "600"),
                    15: ("HP/Lck +8", "1900"), 17: ("Special Guard 4", "800"), 18: ("HP/Lck +10", "3600"),
                    19: ("Special Guard 5", "1000")}
        for lvl, (nombre, sp) in esperado.items():
            heredables = self.tiki["bond_levels"][str(lvl)]["inheritance_skills"]
            self.assertIn((nombre, sp), [(h["nombre"], str(h.get("sp"))) for h in heredables], f"vínculo {lvl}")

    def test_todas_las_pasivas_existen_en_el_motor(self):
        """Ninguna puede quedarse en un nombre suelto que el motor no sepa resolver."""
        nombres = set(self.tiki["synchro_skills"]) | {"Draconic Form"}
        for n in nombres:
            sid = pasivas.resolver_nombre_a_sid(n)
            self.assertIsNotNone(sid, f"{n} no resuelve a ningún SID")
            self.assertIn(sid, pasivas.HABILIDADES, n)


class TestPasivasEnCombate(unittest.TestCase):

    def _combate(self, unidad, rival=None):
        rival = rival or _rival()
        return CalculadoraEngage.simular_combate(
            unidad.stats, rival.stats, unidad.arma, rival.arma, Terreno(), Terreno(), distancia=1)

    def test_draconic_form_solo_en_fusion(self):
        """+10 HP y +5 a Complexión y a todas las stats básicas, solo fusionado."""
        sin = self._combate(_con_tiki("Sin", 1))["atacante"]
        con = self._combate(_con_tiki("Con", 1, en_fusion=True))["atacante"]
        self.assertEqual(con["daño_por_golpe"] - sin["daño_por_golpe"], 5, "+5 Fue")
        self.assertGreater(con["prob_critico"], sin["prob_critico"], "+5 Des sube el crítico")
        self.assertTrue(any("Draconic Form" in p for p in con["pasivas_activas"]))
        self.assertFalse(any("Draconic Form" in p for p in sin["pasivas_activas"]))

    def test_lightsphere_reduce_a_la_mitad_el_critico_del_rival(self):
        antes = self._combate(_con_tiki("Nueve", 9))["defensor"]["prob_critico"]
        despues = self._combate(_con_tiki("Diez", 10))["defensor"]["prob_critico"]
        self.assertEqual(despues, antes // 2, f"{antes}% debería quedarse en la mitad")

    def test_geosphere_protege_al_portador_y_a_los_adyacentes(self):
        """+3 Def/Res (+5 con Geosphere+) si hay algún aliado adyacente."""
        rival = _rival()
        for vinculo, bono in ((3, 3), (16, 5)):
            portador = _con_tiki("Portador", vinculo)
            amigo = _con_tiki("Amigo", 1)
            solo = CalculadoraEngage.simular_combate(
                rival.stats, portador.stats, rival.arma, portador.arma,
                Terreno(), Terreno(), 1, aliados_cercanos_def=[])
            acompanado = CalculadoraEngage.simular_combate(
                rival.stats, portador.stats, rival.arma, portador.arma,
                Terreno(), Terreno(), 1, aliados_cercanos_def=[(amigo.stats, 1)])
            self.assertEqual(
                solo["atacante"]["daño_por_golpe"] - acompanado["atacante"]["daño_por_golpe"], bono,
                f"vínculo {vinculo}: debería recibir {bono} de daño menos")

    def test_sin_aliados_alrededor_geosphere_no_hace_nada(self):
        portador = _con_tiki("Solo", 3)
        pasivas_act = self._combate(portador)["atacante"]["pasivas_activas"]
        self.assertFalse([p for p in pasivas_act if "Geosphere" in p])


class TestLifesphereAlEsperar(unittest.TestCase):
    """"If unit uses Wait without attacking or using items, restores 20/30/40 HP and
    heals status effects"."""

    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()

    def setUp(self):
        self.client.post("/api/mapa/seleccionar", json={"capitulo": 10})
        for n in list(tablero.fichas):
            tablero.fichas.pop(n)
        tablero.fase = "jugador"

    @classmethod
    def tearDownClass(cls):
        cls.client.post("/api/mapa/seleccionar", json={"capitulo": 7})

    def _esperar_con(self, vinculo, hp_inicial=5, veneno=2):
        u = _con_tiki(f"Kagetsu{vinculo}", vinculo, x=vinculo % 10, y=5, _tablero=tablero)
        tablero.registrar_unidad(u, resolver_colision=False)
        u.sincronizar_hp(hp_inicial)
        u.nivel_veneno = veneno
        otorgados = pt.al_esperar(tablero, u)
        return u, [e for _, e in otorgados if e.get("curacion")]

    def test_cura_lo_que_toca_a_cada_nivel(self):
        for vinculo, curacion in ((8, 20), (14, 30), (19, 40)):
            u, curas = self._esperar_con(vinculo, hp_inicial=1)
            self.assertEqual(len(curas), 1, f"vínculo {vinculo}")
            self.assertEqual(u.hp_actual, min(u.hp_max, 1 + curacion), f"vínculo {vinculo}")

    def test_tambien_limpia_los_estados_alterados(self):
        u, curas = self._esperar_con(8)
        self.assertEqual(u.nivel_veneno, 0)
        self.assertTrue(curas)

    def test_por_debajo_del_vinculo_8_no_cura(self):
        u, curas = self._esperar_con(7)
        self.assertEqual((u.hp_actual, u.nivel_veneno), (5, 2))
        self.assertEqual(curas, [])

    def test_no_cura_si_la_unidad_actuo(self):
        u = _con_tiki("Actuo", 19, x=3, y=5, _tablero=tablero)
        tablero.registrar_unidad(u, resolver_colision=False)
        u.sincronizar_hp(5)
        u.accion_turno = "combate"
        self.assertEqual(pt.al_esperar(tablero, u), [])
        self.assertEqual(u.hp_actual, 5)


class TestDragonYAtaquesEspeciales(unittest.TestCase):
    """
    En Fusión, Draconic Form convierte a la unidad en un dragón que **solo** usa ataques
    especiales: no puede usar sus propias armas mientras dure.

    Un "ataque especial" es un arma de tipo `Especial` (Item.xml Kind 9): los alientos de
    los Corrupted Wyrm / Phantom Dragon (JID_異形竜 / JID_幻影竜, las tropas 2×2 que salen
    a partir del Cap. 11), los ataques de Sombron, el Dragon Fang de Corrin... y los del
    propio Emblema. Es también la condición de Special Guard.
    """

    def _con_espada(self, **kw):
        datos = {"nombre": "Kagetsu", "es_aliado": True, "nivel": 15, "clase_nombre": "Swordmaster",
                 "stats": dict(STATS), "emblema_nombre": "Tiki", "nivel_vinculo": 1,
                 "inventario": [{"nombre": "Steel Sword", "equipada": True}], "x": 0, "y": 0}
        datos.update(kw)
        return cl.resolver_unidad_con_catalogo(datos, tablero=None)

    def _wyrm(self):
        return cl.resolver_unidad_con_catalogo({
            "nombre": "Corrupted Wyrm", "es_aliado": False, "nivel": 20,
            "clase_nombre": "Corrupted Wyrm", "dificultad": "Extremo",
            "inventario": [{"id": "IID_火のブレス", "nombre": "Fire Breath", "equipada": True}],
            "x": 1, "y": 0}, tablero=None)

    def test_el_aliento_del_wyrm_es_un_arma_especial(self):
        arma = self._wyrm().arma
        self.assertEqual(arma.tipo, "Especial")
        self.assertEqual((arma.mt, arma.rango), (12, [1, 2, 3]))

    def test_fusionado_no_puede_usar_sus_propias_armas(self):
        from motor_analisis import _armas_aliado
        sin = [a.nombre for a, _, _ in _armas_aliado(self._con_espada())]
        con = [a.nombre for a, _, _ in _armas_aliado(self._con_espada(en_fusion=True))]
        self.assertIn("Steel Sword", sin, "sin fusionar sí usa su espada")
        self.assertNotIn("Steel Sword", con, "transformado en dragón no puede usarla")
        self.assertTrue(con, "algo tiene que poder usar")
        for nombre in con:
            self.assertIn("Emblema", nombre, f"{nombre} debería ser un ataque del Emblema")

    def test_special_guard_solo_contra_ataques_especiales(self):
        wyrm = self._wyrm()
        hacha = cl.resolver_unidad_con_catalogo({
            "nombre": "Bruto", "es_aliado": False, "nivel": 12, "clase_nombre": "Axe Fighter",
            "inventario": [{"nombre": "Steel Axe", "equipada": True}], "x": 1, "y": 0}, tablero=None)

        def dano_recibido(rival, habilidades):
            defensor = cl.resolver_unidad_con_catalogo({
                "nombre": "Def", "es_aliado": True, "nivel": 15, "clase_nombre": "Swordmaster",
                "stats": dict(STATS), "habilidades": habilidades,
                "inventario": [{"nombre": "Steel Sword", "equipada": True}], "x": 0, "y": 0}, tablero=None)
            return CalculadoraEngage.simular_combate(
                rival.stats, defensor.stats, rival.arma, defensor.arma,
                Terreno(), Terreno(), 1)["atacante"]["daño_por_golpe"]

        base_wyrm = dano_recibido(wyrm, [])
        for n in (1, 3, 5):
            self.assertEqual(dano_recibido(wyrm, [f"Special Guard {n}"]), base_wyrm - n,
                             f"Special Guard {n} contra un aliento")
        base_hacha = dano_recibido(hacha, [])
        self.assertEqual(dano_recibido(hacha, ["Special Guard 5"]), base_hacha,
                         "un hacha normal no es un ataque especial")

    def test_las_tropas_2x2_del_cap_11_estan_en_el_datamine(self):
        """Comprobación de que el dato sigue ahí: el Cap. 11 trae dos Corrupted Wyrm."""
        import xml.etree.ElementTree as ET
        import os
        ruta = os.path.join("FE17-DOC-main", "FE17-DOC-main", "fe_assets_gamedata", "Dispos", "M011.xml")
        if not os.path.exists(ruta):
            self.skipTest("datamine no disponible")
        filas = [g for g in ET.parse(ruta).getroot()[0][1]
                 if "異形竜" in (g.attrib.get("Pid") or "")]
        self.assertEqual(len(filas), 2)
        for g in filas:
            items = [g.attrib.get(f"Item{i}.Iid") for i in range(1, 7) if g.attrib.get(f"Item{i}.Iid")]
            self.assertEqual(items, ["IID_火のブレス", "IID_炎塊"])



class TestArmasDeFusionDeTiki(unittest.TestCase):
    """
    Stats verificadas en juego por el jugador (Mt, Hit, Crit, Wt). No están en el datamine,
    así que viven en `json/dlc_armas_canon.json` y el compilador las integra en `armas`.

    Cada unidad dispone de tres: Eternal Claw y Tail Smash, que son de todos, más **un solo
    aliento según su estilo de combate**.
    """

    ESPERADO = {
        "Eternal Claw": (10, 90, 30, 8),
        "Tail Smash": (22, 85, 0, 13),
        "Fire Breath": (10, 75, 0, 15),
        "Ice Breath": (10, 75, 0, 15),
        "Flame Breath": (10, 75, 0, 15),
        "Dark Breath": (10, 75, 0, 15),
        "Fog Breath": (10, 75, 0, 15),
    }
    POR_ESTILO = {"General": "Ice Breath", "Griffin Knight": "Flame Breath",
                  "Sage": "Dark Breath", "Divine Dragon": "Fog Breath",
                  "Swordmaster": "Fire Breath"}

    def _dragon(self, clase):
        return cl.resolver_unidad_con_catalogo({
            "nombre": f"T{clase}", "es_aliado": True, "nivel": 15, "clase_nombre": clase,
            "stats": dict(STATS), "emblema_nombre": "Tiki", "nivel_vinculo": 1, "en_fusion": True,
            "inventario": [{"nombre": "Steel Sword", "equipada": True}], "x": 0, "y": 0}, tablero=None)

    def _armas(self, clase):
        from motor_analisis import _armas_aliado
        return {a.nombre.replace(" (Emblema)", ""): a for a, _, _ in _armas_aliado(self._dragon(clase))}

    def test_stats_de_cada_arma(self):
        armas = {}
        for clase in self.POR_ESTILO:
            armas.update(self._armas(clase))
        for nombre, (mt, hit, crit, wt) in self.ESPERADO.items():
            a = armas.get(nombre)
            self.assertIsNotNone(a, f"{nombre} no aparece en ninguna clase")
            self.assertEqual((a.mt, a.hit, a.crit, a.wt), (mt, hit, crit, wt), nombre)

    def test_cada_estilo_solo_tiene_su_aliento(self):
        for clase, aliento in self.POR_ESTILO.items():
            nombres = set(self._armas(clase))
            self.assertEqual(nombres, {"Eternal Claw", "Tail Smash", aliento},
                             f"{clase} debería llevar solo {aliento}")

    def test_no_se_cuela_el_aliento_de_los_wyrms(self):
        """`IID_火のブレス` (Mt 12) es el aliento de los Corrupted Wyrm, no el de Tiki."""
        fire = self._armas("Swordmaster")["Fire Breath"]
        self.assertEqual(fire.mt, 10, "es el de Tiki, no el del wyrm (Mt 12)")

    def test_solo_tail_smash_es_smash(self):
        """Verdad de juego: los alientos ceden el primer golpe y no permiten seguimiento,
        pero NO empujan. El empuje es exclusivo de Tail Smash."""
        armas = self._armas("General")
        self.assertFalse(armas["Eternal Claw"].es_smash, "la zarpa sí permite seguimiento")
        self.assertFalse(armas["Eternal Claw"].cede_iniciativa)
        self.assertTrue(armas["Tail Smash"].es_smash)
        self.assertFalse(armas["Ice Breath"].es_smash, "el aliento no empuja")
        self.assertTrue(armas["Ice Breath"].cede_iniciativa)

    def test_el_aliento_cede_el_primer_golpe_pero_no_empuja(self):
        lento = cl.resolver_unidad_con_catalogo({
            "nombre": "Lento", "es_aliado": False, "nivel": 10, "clase_nombre": "General",
            "stats": {"hp": 60, "fuerza": 16, "magia": 0, "destreza": 10, "velocidad": 4,
                      "defensa": 20, "resistencia": 8, "suerte": 5, "complexion": 12},
            "inventario": [{"nombre": "Steel Lance", "equipada": True}], "x": 1, "y": 0}, tablero=None)
        dragon = self._dragon("General")

        def combate(arma_nombre):
            return CalculadoraEngage.simular_combate(
                dragon.stats, lento.stats, self._armas("General")[arma_nombre], lento.arma,
                Terreno(), Terreno(), 1, pos_atk=(0, 0), pos_def=(1, 0))["resultado"]

        aliento = combate("Ice Breath")
        actores = [s["actor"] for s in aliento["secuencia"]]
        self.assertEqual(actores[0], "Lento", "el aliento cede la iniciativa: contraataca primero")
        self.assertEqual(len(actores), 2, "sin seguimiento aunque el dragón doble")
        self.assertFalse(aliento["smash"]["empujado"], "el aliento no mueve al rival")
        self.assertIsNone(aliento["smash"]["nueva_pos"])

        cola = combate("Tail Smash")
        self.assertEqual(cola["secuencia"][0]["actor"], "Lento")
        self.assertTrue(cola["smash"]["empujado"], "Tail Smash sí empuja")
        self.assertEqual(cola["smash"]["nueva_pos"], [2, 0])

        zarpa = combate("Eternal Claw")
        self.assertEqual(zarpa["secuencia"][0]["actor"], dragon.nombre, "la zarpa golpea primero")
        self.assertIn("follow-up", [s["tipo"] for s in zarpa["secuencia"]])

    def test_efectos_sobre_la_defensa_del_rival(self):
        muro = cl.resolver_unidad_con_catalogo({
            "nombre": "Muro", "es_aliado": False, "nivel": 12, "clase_nombre": "General",
            "stats": {"hp": 60, "fuerza": 18, "magia": 0, "destreza": 10, "velocidad": 6,
                      "defensa": 24, "resistencia": 8, "suerte": 5, "complexion": 12},
            "inventario": [{"nombre": "Steel Lance", "equipada": True}], "x": 1, "y": 0}, tablero=None)

        def pasivas_de(clase, arma_nombre):
            u = self._dragon(clase)
            a = self._armas(clase)[arma_nombre]
            return CalculadoraEngage.simular_combate(
                u.stats, muro.stats, a, muro.arma, Terreno(), Terreno(), 1)["atacante"]["pasivas_activas"]

        # Media Def (24 -> 12) en Ice / Flame / Fog; media Res (8 -> 4) en Dark
        self.assertIn("Media defensa (Def rival = 12)", pasivas_de("General", "Ice Breath"))
        self.assertIn("Media defensa (Def rival = 4)", pasivas_de("Sage", "Dark Breath"))
        self.assertIn("Media defensa (Def rival = 12)", pasivas_de("Divine Dragon", "Fog Breath"))
        # Fire Breath ignora la defensa del todo
        self.assertIn("Ignora la defensa (Def rival = 0)", pasivas_de("Swordmaster", "Fire Breath"))
        # Flame Breath además pega al 70 %
        flame = pasivas_de("Griffin Knight", "Flame Breath")
        self.assertIn("Media defensa (Def rival = 12)", flame)
        self.assertTrue([p for p in flame if "70" in p], flame)

    def test_fog_breath_es_efectiva_contra_dragones(self):
        self.assertIn("dragón", self._armas("Divine Dragon")["Fog Breath"].efectividades)


class TestArmasDeLasTresCasas(unittest.TestCase):
    """Las reliquias de Edelgard/Dimitri/Claude son las de Byleth del datamine: el jugador
    confirmó los números en partida."""

    def test_las_tres_reliquias_con_sus_stats_del_datamine(self):
        esperado = {
            "Aymr (Edelgard)": ("IID_ベレト_アイムール", 24, 60, 20, 11),
            "Areadbhar (Dimitri)": ("IID_ベレト_アラドヴァル", 14, 75, 10, 9),
            "Failnaught (Claude)": ("IID_ベレト_フェイルノート", 13, 75, 20, 9),
        }
        for nombre, (iid, mt, hit, crit, wt) in esperado.items():
            p = cl.parsear_arma_string({"nombre": nombre})
            self.assertIsNotNone(p, nombre)
            self.assertEqual((p["id"], p["mt"], p["hit"], p["crit"], p["wt"]),
                             (iid, mt, hit, crit, wt), nombre)

    def test_el_emblema_lista_las_tres(self):
        with open("json/dlc_emblems_canon.json", encoding="utf-8") as f:
            e = json.load(f)["GID_DLC_EDELGARD"]
        self.assertEqual(len(e["engage_items"]), 3, e["engage_items"])
        self.assertTrue(any("Failnaught" in x for x in e["engage_items"]))



if __name__ == "__main__":
    unittest.main()
