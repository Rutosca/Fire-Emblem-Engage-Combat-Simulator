# -*- coding: utf-8 -*-
"""
Emblema Tiki (DLC). Desde la 2.0.0 todo sale del datamine extraído del propio juego
(`FE17_200`), que incluye el DLC: ya no hay ni un número escrito a mano. Lo único que
ponemos nosotros son los nombres (`json/nombres_dlc.json`), porque los textos del DLC
viven en un romfs aparte que no se ha podido extraer.

Estos tests fijan lo que DICE EL JUEGO. Parte del comportamiento todavía no lo ejecuta el
motor, porque el juego lo define en timings de la Fase 3 (12 reducción de daño, 18
posterior al golpe, 26-27 fuera del combate); esos casos están marcados y comprueban que
el dato está bien puesto, no que el motor lo aplique. Cuando llegue la Fase 3 se amplían.

Sincronías: Starsphere 1 · Geosphere 3 · Lifesphere 8 · Lightsphere 10 ·
            Lifesphere+ 14 · Geosphere+ 16 · Lifesphere++ 19
Fusión:     Draconic Form (Nv 1)
"""
import unittest

import catalogo_loader as cl
import pasivas
from motor_analisis import _armas_aliado
from motor_calculo import CalculadoraEngage, Terreno

GID_TIKI = "GID_チキ"

STATS = {"hp": 40, "fuerza": 20, "magia": 6, "destreza": 18, "velocidad": 18,
         "defensa": 14, "resistencia": 10, "suerte": 10, "complexion": 8}


def _con_tiki(vinculo=20, clase="Swordmaster", fusion=False, **kw):
    datos = {"nombre": "Portador", "es_aliado": True, "nivel": 15, "clase_nombre": clase,
             "stats": dict(STATS), "emblema_nombre": "Tiki", "nivel_vinculo": vinculo,
             "en_fusion": fusion,
             "inventario": [{"nombre": "Steel Sword", "equipada": True}], "x": 0, "y": 0}
    datos.update(kw)
    return cl.resolver_unidad_con_catalogo(datos, tablero=None)


def _armas(unidad):
    return {a.nombre.replace(" (Emblema)", ""): a for a, _, _ in _armas_aliado(unidad)}


def _emblema():
    return cl._catalogo["emblemas"][GID_TIKI]


def _arma_cruda(iid):
    return cl._catalogo["armas"][iid]


class TestDatosDelJuego(unittest.TestCase):
    """El Emblema sale de God.xml, no de un fichero nuestro."""

    def test_el_emblema_existe_con_su_gid_real(self):
        e = _emblema()
        self.assertEqual(e["nombre"], "Tiki")
        self.assertEqual(len(e["bond_levels"]), 20)

    def test_cada_sincronia_en_su_nivel(self):
        esperado = {1: "Starsphere", 3: "Geosphere", 8: "Lifesphere", 10: "Lightsphere",
                    14: "Lifesphere+", 16: "Geosphere+", 19: "Lifesphere++"}
        vistas = {}
        for lv in sorted(_emblema()["bond_levels"], key=int):
            for s in _emblema()["bond_levels"][lv]["synchro_skills"]:
                vistas.setdefault(s["nombre"], int(lv))
        for nivel, nombre in esperado.items():
            self.assertIn(nombre, vistas, f"falta {nombre}")
            self.assertEqual(vistas[nombre], nivel, nombre)

    def test_las_mejoras_sustituyen_a_la_version_base(self):
        """A vínculo 20 no puede seguir apareciendo la versión sin +."""
        nombres = [s["nombre"] for s in _emblema()["bond_levels"]["20"]["synchro_skills"]]
        self.assertIn("Lifesphere++", nombres)
        self.assertNotIn("Lifesphere", nombres)
        self.assertNotIn("Lifesphere+", nombres)
        self.assertIn("Geosphere+", nombres)
        self.assertNotIn("Geosphere", nombres)

    def test_la_fusion_da_draconic_form(self):
        eng = [s["nombre"] for s in _emblema()["bond_levels"]["1"]["engage_skills"]]
        self.assertIn("Draconic Form", eng)

    def test_todas_las_pasivas_existen_en_el_motor(self):
        for lv in _emblema()["bond_levels"].values():
            for campo in ("synchro_skills", "engage_skills"):
                for s in lv[campo]:
                    self.assertIn(s["sid"], pasivas.HABILIDADES, s["nombre"])


class TestArmas(unittest.TestCase):
    """Stats leídas de Item.xml. Coinciden con las que el jugador midió en partida."""

    ESPERADAS = {
        "IID_チキ_つめ": ("Eternal Claw", 10, 90, 30, 8),
        "IID_チキ_しっぽ": ("Tail Smash", 22, 85, 0, 13),
        "IID_チキ_ブレス": ("Fire Breath", 10, 75, 0, 15),
        "IID_チキ_ブレス_重装": ("Ice Breath", 10, 75, 0, 15),
        "IID_チキ_ブレス_飛行": ("Flame Breath", 10, 75, 0, 15),
        "IID_チキ_ブレス_魔法": ("Dark Breath", 10, 75, 0, 15),
        "IID_チキ_ブレス_竜族": ("Fog Breath", 10, 75, 0, 15),
    }

    def test_stats_de_cada_arma(self):
        for iid, (nombre, mt, hit, crit, wt) in self.ESPERADAS.items():
            a = _arma_cruda(iid)
            self.assertEqual((a["nombre"], a["mt"], a["hit"], a["crit"], a["wt"]),
                             (nombre, mt, hit, crit, wt), iid)

    def test_los_cinco_alientos_comparten_stats(self):
        alientos = [v for k, v in self.ESPERADAS.items() if "ブレス" in k]
        self.assertEqual(len({a[1:] for a in alientos}), 1, "solo cambian de efecto")

    def test_tail_smash_es_el_unico_smash(self):
        """`SID_スマッシュ` (empuja 1 casilla y no permite seguimiento) lo lleva solo la cola."""
        self.assertIn("SID_スマッシュ", _arma_cruda("IID_チキ_しっぽ")["equip_sids"])
        for iid in self.ESPERADAS:
            if iid != "IID_チキ_しっぽ":
                self.assertNotIn("SID_スマッシュ", _arma_cruda(iid)["equip_sids"], iid)

    def test_los_alientos_parten_la_defensa(self):
        """`SID_相手の防御力半減`: x0.5 a la Def si el golpe es físico, a la Res si es mágico."""
        for iid in self.ESPERADAS:
            sids = _arma_cruda(iid)["equip_sids"]
            if "ブレス" in iid:
                self.assertIn("SID_相手の防御力半減", sids, iid)
            else:
                self.assertNotIn("SID_相手の防御力半減", sids, iid)

    def test_solo_el_aliento_de_niebla_es_efectivo_contra_dragones(self):
        self.assertIn("SID_竜特効", _arma_cruda("IID_チキ_ブレス_竜族")["equip_sids"])
        self.assertIn("dragón", _arma_cruda("IID_チキ_ブレス_竜族")["efectividades"])
        for iid in self.ESPERADAS:
            if iid != "IID_チキ_ブレス_竜族":
                self.assertEqual(_arma_cruda(iid)["efectividades"], [], iid)

    def test_no_se_cuela_el_aliento_de_los_wyrms(self):
        """`IID_火のブレス` (Mt 12) es el aliento de los Corrupted Wyrm, no el de Tiki."""
        self.assertEqual(_arma_cruda("IID_火のブレス")["mt"], 12)
        self.assertEqual(_arma_cruda("IID_チキ_ブレス")["mt"], 10)


class TestArmasPorEstiloDeCombate(unittest.TestCase):
    """
    Cada estilo recibe un aliento distinto. No es una regla nuestra: God.xml tiene una
    columna por estilo en la tabla de vínculo (`EngageHeavys`, `EngageFlys`...).
    """

    POR_ESTILO = {"General": "Ice Breath",          # acorazado
                  "Wyvern Knight": "Flame Breath",  # volador
                  "Sage": "Dark Breath",            # místico
                  "Divine Dragon": "Fog Breath",    # dragón
                  "Swordmaster": "Fire Breath",     # el resto
                  "Paladin": "Fire Breath",
                  "Warrior": "Fire Breath"}

    def test_cada_estilo_recibe_el_suyo(self):
        for clase, aliento in self.POR_ESTILO.items():
            armas = _armas(_con_tiki(clase=clase, fusion=True))
            alientos = [n for n in armas if "Breath" in n]
            self.assertEqual(alientos, [aliento], clase)

    def test_la_zarpa_y_la_cola_son_para_todos(self):
        for clase in self.POR_ESTILO:
            armas = _armas(_con_tiki(clase=clase, fusion=True))
            self.assertIn("Eternal Claw", armas, clase)
            self.assertIn("Tail Smash", armas, clase)

    def test_sin_fusion_no_hay_armas_de_emblema(self):
        armas = _armas(_con_tiki(clase="General", fusion=False))
        self.assertEqual([n for n in armas if "Breath" in n], [])


class TestDraconicForm(unittest.TestCase):

    def test_sube_las_estadisticas_al_fusionarse(self):
        """HP+10 y +5 al resto, leído de los stat_boosts de SID_竜化."""
        d = pasivas.HABILIDADES["SID_竜化"]["stat_boosts"]
        self.assertEqual(d["hp"], 10)
        for k in ("str", "mag", "dex", "spd", "def", "res", "lck", "bld"):
            self.assertEqual(d[k], 5, k)

    def test_la_variante_mistica_da_res_extra(self):
        """"[Mystical] Grants an extra Res+5": 5 + 5 = 10."""
        self.assertEqual(pasivas.HABILIDADES["SID_竜化_魔法"]["stat_boosts"]["res"], 10)

    def test_la_variante_acorazada_ignora_el_dano_del_terreno(self):
        self.assertIn("SID_地形ダメージ無効", pasivas.HABILIDADES["SID_竜化_重装"]["sync_sids"])

    def test_solo_cuenta_en_fusion(self):
        self.assertNotIn("Draconic Form", getattr(_con_tiki(fusion=False).stats, "habilidades", []) or [])
        self.assertIn("Draconic Form", getattr(_con_tiki(fusion=True).stats, "habilidades", []) or [])


class TestPendienteDeFase3(unittest.TestCase):
    """
    Lo que el juego define en timings que el motor todavía no consume. Aquí se comprueba
    que el DATO está donde debe; que se aplique es cosa de la Fase 3.
    """

    def test_el_aliento_llameante_pega_al_70_por_ciento(self):
        d = pasivas.HABILIDADES["SID_チキ_ブレス_飛行_威力減"]
        self.assertEqual(d["timing"], 12, "reducción de daño")
        self.assertEqual((d["act_names"], d["act_operations"], d["act_values"]),
                         (["相手のダメージ"], ["*"], ["0.7"]))

    def test_el_area_del_aliento_es_un_ataque_posterior(self):
        """Timing 18: el área no va en el golpe, es un ataque extra después del combate."""
        for sid in ("SID_チキ_ブレス_通常", "SID_チキ_ブレス_重装", "SID_チキ_ブレス_飛行",
                    "SID_チキ_ブレス_魔法", "SID_チキ_ブレス_竜族"):
            d = pasivas.HABILIDADES[sid]
            self.assertEqual(d["timing"], 18, sid)
            self.assertIn("SID_追撃不可", d["sync_sids"], sid)

    def test_geosphere_es_un_aura_posterior_al_combate(self):
        d = pasivas.HABILIDADES["SID_地玉の加護"]
        self.assertEqual(d["timing"], 27)
        self.assertEqual(d["give_target"], 3, "a los de alrededor")
        self.assertTrue(d["give_sids"])


class TestTropas2x2(unittest.TestCase):
    """
    Los Corrupted Wyrm ocupan 2x2. El tamaño está en Person.xml (`BmapSize`), por PID,
    no en Job.xml: es de la unidad concreta, no de la clase.
    """

    def test_el_aliento_del_wyrm_es_un_arma_especial(self):
        a = _arma_cruda("IID_火のブレス")
        self.assertEqual(a["tipo"], "Especial")
        self.assertEqual((a["mt"], a["rango"]), (12, [1, 2, 3]))

    def test_las_clases_de_los_wyrms_estan_en_el_catalogo(self):
        clases = cl._catalogo["clases"]
        self.assertIn("JID_異形竜", clases)
        self.assertIn("JID_幻影竜", clases)
        self.assertEqual(clases["JID_異形竜"]["estilo_combate"], "竜族スタイル")

    def test_debilidades_de_cada_uno(self):
        """El Corrupted Wyrm NO recibe la efectividad a dragón; el Phantom sí."""
        clases = cl._catalogo["clases"]
        self.assertIn("dragón caído", clases["JID_異形竜"]["debilidades"])
        self.assertNotIn("dragón", clases["JID_異形竜"]["debilidades"])
        self.assertIn("dragón", clases["JID_幻影竜"]["debilidades"])


class TestReliquiasDeLasTresCasas(unittest.TestCase):
    """Ahora hay dos juegos de reliquias: las de Byleth y las del Emblema Tres Casas."""

    def test_las_tres_del_emblema_tres_casas(self):
        for iid, (nombre, mt, hit, crit, wt) in {
                "IID_三級長_アイムール": ("Aymr", 24, 60, 20, 11),
                "IID_三級長_アラドヴァル": ("Areadbhar", 14, 75, 10, 9),
                "IID_三級長_フェイルノート": ("Failnaught", 13, 75, 20, 9)}.items():
            a = _arma_cruda(iid)
            self.assertEqual((a["nombre"], a["mt"], a["hit"], a["crit"], a["wt"]),
                             (nombre, mt, hit, crit, wt), iid)

    def test_byleth_tiene_las_suyas_aparte(self):
        """Byleth reparte una Reliquia distinta a cada estilo; su Aymr es otra entrada."""
        self.assertEqual(_arma_cruda("IID_ベレト_アイムール")["mt"], 24)
        por_estilo = cl._catalogo["emblemas"]["GID_ベレト"]["bond_levels"]["20"]["engage_items_por_estilo"]
        self.assertEqual([i["nombre"] for i in por_estilo["dragon"]], ["Aymr"])
        self.assertEqual([i["nombre"] for i in por_estilo["apoyo"]], ["Blutgang"])


if __name__ == "__main__":
    unittest.main()
