# -*- coding: utf-8 -*-
"""
Habilidades de Emblema de los jefes con Emblema Oscuro y su regla general (no se fusionan:
sus armas y habilidades de Emblema están siempre activas).

  Lyn    (GID_M010_敵リン, Hyacinth en el Cap. 10): Call Doubles + Astra Storm
  Leif   (GID_M008_敵リーフ, Ivy en el Cap. 8):      Adaptable (+ Vantage+ / Weapon Sync+)
  Lucina (GID_M007_敵ルキナ, Hortensia en el Cap. 7): Dual Strike + All for One

Fuentes del datamine:
  Skill.xml   SID_残像 VisionCount 4 (_竜族 5, _飛行 +10 Avo vía SID_残像_飛行_効果)
              SID_リンエンゲージ技 攻撃回数 = 5 + SID_ダメージ３０％, RangeI/O 1-10
              SID_リンエンゲージ技_隠密 1-20 · _竜族 1-15 · _気功 rompe · _闇_気功 20 % + rompe
  Person.xml  PID_残像 ("Illusory Double", JID_村人, Items IID_残像_マーニ・カティ,
              CommonSids SID_相手の取得経験値０)
  Params.xml  残像能力倍率 (Doubles stats multiplier) = 1
  Skill.csv   "Creates four illusory doubles that can make chain attacks with unit"
              "自分のみチェインアタック可能な残像" → solo encadenan con quien los invocó
"""
import unittest

import pasivas
from app import app, tablero
from motor_analisis import obtener_aliados_backup


class TestHabilidadesDeLyn(unittest.TestCase):
    """Lectura de las habilidades del Emblema directamente del catálogo compilado."""

    def test_call_doubles_copias_por_estilo(self):
        base = pasivas.HABILIDADES["SID_残像"]
        self.assertEqual(base["vision_count"], 4)
        self.assertEqual(pasivas.HABILIDADES["SID_残像_竜族"]["vision_count"], 5)
        # El estilo Volador no da una copia más: da +10 de Evasión a los dobles
        self.assertEqual(pasivas.HABILIDADES["SID_残像_飛行"]["vision_count"], 4)
        self.assertIn("SID_残像_飛行_効果", pasivas.HABILIDADES["SID_残像_飛行"]["give_sids"])
        efecto = pasivas.HABILIDADES["SID_残像_飛行_効果"]
        self.assertEqual((efecto["act_names"], efecto["act_values"]), (["回避値"], ["10"]))

    def test_astra_storm_golpes_fraccion_y_alcance(self):
        normal = pasivas.forma_ataque_emblema(None, "SID_リンエンゲージ技")
        self.assertEqual((normal["golpes"], normal["fraccion"], normal["rompe"]), (5, 0.3, False))
        self.assertEqual((normal["rango"][0], normal["rango"][-1]), (1, 10))
        # Bonos de estilo declarados en el propio Skill.xml
        encubierto = pasivas.forma_ataque_emblema(None, "SID_リンエンゲージ技_隠密")
        dragon = pasivas.forma_ataque_emblema(None, "SID_リンエンゲージ技_竜族")
        qi = pasivas.forma_ataque_emblema(None, "SID_リンエンゲージ技_気功")
        self.assertEqual(encubierto["rango"][-1], 20)   # Encubierto: alcance +10
        self.assertEqual(dragon["rango"][-1], 15)       # Dragón: alcance +5
        self.assertTrue(qi["rompe"])                    # Qi Adept: rompe al objetivo
        self.assertEqual(qi["rango"][-1], 10)           # ...y no gana alcance
        # La versión que lleva Hyacinth: oscura + Qi Adept (20 % y ruptura)
        oscura = pasivas.forma_ataque_emblema(None, "SID_リンエンゲージ技_闇_気功")
        self.assertEqual((oscura["golpes"], oscura["fraccion"], oscura["rompe"]), (5, 0.2, True))

    def test_lodestar_rush_sigue_saliendo_del_mismo_lector(self):
        """El lector genérico reproduce los 7/8/9 golpes al 30 % de Lodestar Rush."""
        self.assertEqual(pasivas.forma_ataque_emblema(None, "SID_マルスエンゲージ技")["golpes"], 7)
        self.assertEqual(pasivas.forma_ataque_emblema(None, "SID_マルスエンゲージ技_連携")["golpes"], 8)
        self.assertEqual(pasivas.forma_ataque_emblema(None, "SID_マルスエンゲージ技_竜族")["golpes"], 9)
        self.assertEqual(pasivas.forma_ataque_emblema(None, "SID_マルスエンゲージ技")["fraccion"], 0.3)


class TestEmblemaOscuroDeHyacinth(unittest.TestCase):
    """El Emblema Oscuro no se fusiona: sus armas y habilidades están siempre puestas."""

    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()

    def setUp(self):
        self.client.post("/api/mapa/seleccionar", json={"capitulo": 10})
        self.client.post("/api/preset/actual", json={})
        self.hyacinth = tablero.obtener_ficha("Hyacinth")

    @classmethod
    def tearDownClass(cls):
        cls.client.post("/api/mapa/seleccionar", json={"capitulo": 7})

    def test_lleva_las_armas_del_emblema_lyn(self):
        h = self.hyacinth
        self.assertEqual(h.emblema_id, "GID_M010_敵リン")
        self.assertFalse(h.en_fusion, "un Emblema Oscuro nunca entra en Fusión")
        por_id = {i["id"]: i for i in h.inventario}
        self.assertIn("IID_リン_キラーボウ_M010", por_id)
        self.assertIn("IID_リン_マーニ・カティ_M010", por_id)
        # Las versiones de evento no son las genéricas: distinto Mt y distinto crítico
        self.assertEqual((por_id["IID_リン_キラーボウ_M010"]["mt"], por_id["IID_リン_キラーボウ_M010"]["crit"]), (9, 10))
        self.assertEqual((por_id["IID_リン_マーニ・カティ_M010"]["mt"], por_id["IID_リン_マーニ・カティ_M010"]["crit"]), (6, 5))

    def test_tiene_call_doubles_y_astra_storm_sin_fusionarse(self):
        h = self.hyacinth
        self.assertIn("Call Doubles", h.habilidades)
        self.assertTrue(h.como_dict()["puede_call_doubles"])
        forma = pasivas.forma_ataque_emblema(h)
        self.assertEqual((forma["nombre"], forma["golpes"], forma["fraccion"], forma["rompe"]),
                         ("Astra Storm", 5, 0.2, True))


class TestCallDoublesEnElTablero(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()

    def setUp(self):
        self.client.post("/api/mapa/seleccionar", json={"capitulo": 10})
        self.client.post("/api/preset/actual", json={})
        tablero.fase = "jugador"
        self.hyacinth = tablero.obtener_ficha("Hyacinth")

    @classmethod
    def tearDownClass(cls):
        cls.client.post("/api/mapa/seleccionar", json={"capitulo": 7})

    def _dobles(self):
        return [f for f in tablero.fichas.values() if f.invocador == "Hyacinth"]

    def test_invoca_copias_con_1_hp_y_las_mismas_stats(self):
        r = self.client.post("/api/unidad/invocar_dobles", json={"nombre": "Hyacinth"})
        self.assertEqual(r.status_code, 200, r.get_json())
        dobles = self._dobles()
        self.assertEqual(len(dobles), 4)
        h = self.hyacinth
        for d in dobles:
            self.assertEqual((d.hp_actual, d.hp_max), (1, 1))
            self.assertEqual(d.es_aliado, h.es_aliado)
            self.assertEqual(abs(d.x - h.x) + abs(d.y - h.y) <= 2, True)
            # Mismas stats que el invocador (Params.xml: multiplicador 1)
            for stat in ("fuerza", "magia", "destreza", "velocidad", "defensa", "resistencia"):
                self.assertEqual(getattr(d.stats, stat), getattr(h.stats, stat), stat)
            self.assertEqual(d.arma.nombre, "Mani Katti")
            self.assertFalse(d.es_jefe)
            self.assertIn("SID_相手の取得経験値０", getattr(d.stats, "habilidades_sids", []))

    def test_no_se_pueden_invocar_dos_veces(self):
        self.client.post("/api/unidad/invocar_dobles", json={"nombre": "Hyacinth"})
        r = self.client.post("/api/unidad/invocar_dobles", json={"nombre": "Hyacinth"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(len(self._dobles()), 4)

    def test_sin_la_habilidad_no_hay_dobles(self):
        r = self.client.post("/api/unidad/invocar_dobles", json={"nombre": "Hortensia"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Call Doubles", r.get_json()["error"])

    def test_solo_encadenan_con_quien_los_invoco(self):
        h = self.hyacinth
        victima = tablero.obtener_aliados()[0]
        victima.x, victima.y = h.x, h.y + 2          # adyacente a un doble, no a Hyacinth
        self.client.post("/api/unidad/invocar_dobles", json={"nombre": "Hyacinth"})
        con_hyacinth = obtener_aliados_backup(h, victima, tablero=tablero)
        self.assertTrue(con_hyacinth, "el doble adyacente debe encadenar con Hyacinth")
        self.assertTrue(all(f.invocador == "Hyacinth" for f in con_hyacinth))
        otro = next(f for f in tablero.obtener_enemigos()
                    if f.nombre != "Hyacinth" and not f.invocador and f.viva)
        otro.x, otro.y = victima.x + 1, victima.y
        self.assertEqual(obtener_aliados_backup(otro, victima, tablero=tablero), [],
                         "los dobles no encadenan con el resto del ejército")

    def test_se_disipan_al_caer_el_invocador(self):
        self.client.post("/api/unidad/invocar_dobles", json={"nombre": "Hyacinth"})
        r = self.client.post("/api/muerte", json={"nombre": "Hyacinth"})
        self.assertEqual(len(r.get_json()["dobles_disipados"]), 4)
        self.assertEqual(self._dobles(), [])

    def test_comando_de_disipar(self):
        self.client.post("/api/unidad/invocar_dobles", json={"nombre": "Hyacinth"})
        r = self.client.post("/api/unidad/disipar_dobles", json={"nombre": "Hyacinth"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self._dobles(), [])
        # Y se pueden volver a invocar
        self.assertEqual(self.client.post("/api/unidad/invocar_dobles",
                                          json={"nombre": "Hyacinth"}).status_code, 200)


class TestAstraStormDeAliado(unittest.TestCase):
    """Cuando Lyn esté entre los aliados: dispara el arco equipado 5 veces al 30 %."""

    def _etie_con_lyn(self):
        from catalogo_loader import resolver_unidad_con_catalogo
        return resolver_unidad_con_catalogo({
            "nombre": "Etie", "es_aliado": True, "nivel": 12, "clase_nombre": "Sniper",
            "emblema_nombre": "Lyn", "en_fusion": True, "nivel_vinculo": 5,
            "inventario": [{"nombre": "Steel Bow", "equipada": True}], "x": 0, "y": 0,
        }, tablero=None)

    def test_el_ataque_usa_el_arco_y_el_alcance_del_sid(self):
        from motor_analisis import _armas_aliado
        f = self._etie_con_lyn()
        ataques = [a for a, _, _ in _armas_aliado(f) if getattr(a, "es_engage_attack", False)]
        self.assertTrue(ataques, "Astra Storm debe aparecer como Ataque de Emblema")
        for a in ataques:
            self.assertEqual(a.tipo, "Arco", "Astra Storm es 弓限定 (solo arcos)")
            # Sniper es Encubierto: alcance 1-20 (el arco normal llegaría solo a 2)
            self.assertEqual((a.rango[0], a.rango[-1]), (1, 20))

    def test_cinco_golpes_al_30_por_ciento_sin_contraataque(self):
        from catalogo_loader import resolver_unidad_con_catalogo
        from motor_analisis import _armas_aliado
        from motor_calculo import CalculadoraEngage, Terreno
        f = self._etie_con_lyn()
        enemigo = resolver_unidad_con_catalogo({
            "nombre": "Bruto", "es_aliado": False, "nivel": 10, "clase_nombre": "Axe Fighter",
            "inventario": [{"nombre": "Iron Axe", "equipada": True}], "x": 8, "y": 0}, tablero=None)
        arma = next(a for a, _, _ in _armas_aliado(f) if getattr(a, "es_engage_attack", False))
        c = CalculadoraEngage.simular_combate(
            f.stats, enemigo.stats, arma, enemigo.arma, Terreno(), Terreno(), 8,
            es_engage_attack=True, engage_attack_nombre="Astra Storm (Tormenta astral)")
        golpes, dmg = c["atacante"]["lodestar_hits"]
        self.assertEqual(golpes, 5)
        self.assertGreater(dmg, 0)
        self.assertIn("Astra Storm (5 golpes", " ".join(c["atacante"]["pasivas_activas"]))
        # Un Ataque de Emblema no permite respuesta (SID_エンゲージ技_汎用設定: 相手の手番回数 = 0)
        self.assertNotIn("contraataque", " ".join(s["tipo"] for s in c["resultado"]["secuencia"]))


class TestAdaptableDelEmblemaOscuroDeLeif(unittest.TestCase):
    """SID_順応 (Adaptable): al ser atacada, la unidad responde con la mejor arma que
    tenga disponible, no con la equipada. Ivy la lleva en el Cap. 8 (GID_M008_敵リーフ)."""

    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()

    def setUp(self):
        self.client.post("/api/mapa/seleccionar", json={"capitulo": 8})
        self.client.post("/api/preset/actual", json={})
        self.ivy = tablero.obtener_ficha("Ivy")

    @classmethod
    def tearDownClass(cls):
        cls.client.post("/api/mapa/seleccionar", json={"capitulo": 7})

    def test_ivy_lleva_las_armas_y_la_habilidad_del_emblema_oscuro(self):
        ids = {i["id"] for i in self.ivy.inventario}
        self.assertIn("IID_リーフ_キラーアクス_M008", ids)
        self.assertIn("IID_リーフ_マスターランス_M008", ids)
        self.assertIn("Adaptable", self.ivy.habilidades)

    def test_responde_a_distancia_2_aunque_lleve_equipada_un_arma_de_alcance_1(self):
        from motor_calculo import arma_de_respuesta
        self.assertEqual(self.ivy.arma.rango, [1], "lleva equipada el Killer Axe (alcance 1)")
        arma, cambiada = arma_de_respuesta(self.ivy.stats, self.ivy.arma, 2)
        self.assertTrue(cambiada, "Adaptable debe cambiar a un arma que alcance a distancia 2")
        self.assertIn(2, arma.rango)

    def test_sin_adaptable_se_responde_con_la_equipada(self):
        from motor_calculo import arma_de_respuesta
        otro = next(f for f in tablero.obtener_enemigos()
                    if f.viva and f.nombre != "Ivy" and f.arma and f.stats)
        arma, cambiada = arma_de_respuesta(otro.stats, otro.arma, 2)
        self.assertFalse(cambiada)
        self.assertIs(arma, otro.arma)



class TestDualStrikeDelEmblemaOscuroDeLucina(unittest.TestCase):
    """Dual Strike (SID_絆の力, sincronía de Lucina): "Unit participates in chain attacks
    as if it were a backup unit" — lo concede el SID oculto SID_チェインアタック許可.
    Hortensia lo lleva en el Cap. 7 (GID_M007_敵ルキナ), junto con All for One."""

    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()

    def setUp(self):
        self.client.post("/api/mapa/seleccionar", json={"capitulo": 7})
        self.client.post("/api/preset/actual", json={})
        self.hortensia = next(f for f in tablero.obtener_enemigos() if "Hortensia" in f.nombre)

    def test_hortensia_tiene_dual_strike_y_all_for_one(self):
        h = self.hortensia
        self.assertIn("Dual Strike", h.habilidades)
        self.assertEqual(h.arma.nombre, "Noble Rapier")
        self.assertEqual(
            pasivas.HABILIDADES[getattr(h.stats, "sid_ataque_emblema")]["nombre"], "All for One")

    def test_encadena_sin_ser_de_apoyo(self):
        from motor_analisis import es_unidad_backup
        h = self.hortensia
        self.assertFalse(es_unidad_backup(h), "una Wing Tamer no es de estilo Apoyo")
        self.assertTrue(pasivas.permite_chain_attack(h))
        # Con un aliado adyacente atacando, Hortensia entra como Chain Attack
        victima = tablero.obtener_aliados()[0]
        victima.x, victima.y = h.x, h.y + 1
        otro = next(f for f in tablero.obtener_enemigos()
                    if f.viva and f is not h and f.arma and f.stats)
        otro.x, otro.y = victima.x + 1, victima.y
        apoyos = obtener_aliados_backup(otro, victima, tablero=tablero)
        self.assertIn(h.nombre, [a.nombre for a in apoyos])

    def test_una_unidad_sin_la_habilidad_no_encadena(self):
        otro = next(f for f in tablero.obtener_enemigos()
                    if f.viva and "Hortensia" not in f.nombre and f.stats)
        from motor_analisis import es_unidad_backup
        if not es_unidad_backup(otro):
            self.assertFalse(pasivas.permite_chain_attack(otro))



class TestAllForOneYBondedShield(unittest.TestCase):
    """Las otras dos habilidades de Lucina, leídas del datamine.

    All for One (`SID_ルキナエンゲージ技`): "All allies within 2 spaces chain attack.
    [Dragon] Ally chain attacks are guaranteed to hit. [Backup] Range +1" — el radio es el
    RangeO del SID_強制チェインアタックNマス sincronizado y el Hit 100 % es el GiveSids de la
    variante de Dragón.
    Bonded Shield (`SID_絆盾`): el % de activación es el スキル確率(N) de su Condition.
    """

    def test_all_for_one_radio_y_hit_por_estilo(self):
        base = pasivas.chain_attack_forzado(None, "SID_ルキナエンゲージ技")
        apoyo = pasivas.chain_attack_forzado(None, "SID_ルキナエンゲージ技_連携")
        dragon = pasivas.chain_attack_forzado(None, "SID_ルキナエンゲージ技_竜族")
        self.assertEqual((base["rango"], base["hit_garantizado"]), (2, False))
        self.assertEqual(apoyo["rango"], 3)                 # [Backup] Range +1
        self.assertTrue(dragon["hit_garantizado"])          # [Dragon] chain attacks aciertan
        self.assertEqual(dragon["rango"], 2)
        # Un Ataque de Emblema que no fuerza Chain Attacks no devuelve nada
        self.assertIsNone(pasivas.chain_attack_forzado(None, "SID_リンエンゲージ技"))

    def test_bonded_shield_probabilidades_del_datamine(self):
        esperado = {
            "SID_絆盾": (80, ""),            # base
            "SID_絆盾_竜族": (90, ""),        # [Dragon] +10 % — NO es 100 %
            "SID_絆盾_気功": (100, ""),       # [Qi Adept] Trigger %=100
            "SID_絆盾_騎馬": (80, "caballeria"),
            "SID_絆盾_重装": (80, "acorazado"),
            "SID_絆盾_飛行": (80, "volador"),
        }
        for sid, (prob, estilo) in esperado.items():
            leido = pasivas._leer_probabilidades(pasivas.HABILIDADES[sid]["condition"])
            self.assertEqual(leido, (prob, estilo), sid)

    def test_hortensia_tiene_registrado_all_for_one(self):
        """En el Cap. 7 el jugador solo anota el daño, pero el dato debe estar."""
        client = app.test_client()
        client.post("/api/mapa/seleccionar", json={"capitulo": 7})
        client.post("/api/preset/actual", json={})
        h = next(f for f in tablero.obtener_enemigos() if "Hortensia" in f.nombre)
        forzado = pasivas.chain_attack_forzado(h)
        self.assertEqual((forzado["nombre"], forzado["rango"]), ("All for One", 2))
        # El Emblema Oscuro de Lucina no trae Bonded Shield (su GGID solo declara SID_絆の力)
        self.assertFalse(h.como_dict()["puede_escudo_vinculo"])


class TestAllForOneYBondedShieldEnAliado(unittest.TestCase):
    """Para cuando Lucina esté entre los aliados."""

    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()

    def setUp(self):
        from catalogo_loader import resolver_unidad_con_catalogo
        self.client.post("/api/mapa/seleccionar", json={"capitulo": 7})
        self.client.post("/api/preset/actual", json={})
        self.enemigo = next(f for f in tablero.obtener_enemigos() if f.viva and f.stats)
        self.enemigo.x, self.enemigo.y = 5, 4
        for nombre, clase, arma, x, y in (
            ("LucinaTest", "Divine Dragon", "Iron Sword", 5, 5),
            ("Apoyo1", "Sword Fighter", "Iron Sword", 6, 5),
            ("Mago1", "Mage", "Fire", 5, 6),
            ("Lejos", "Sword Fighter", "Iron Sword", 5, 9),
        ):
            f = resolver_unidad_con_catalogo({
                "nombre": nombre, "es_aliado": True, "nivel": 10, "clase_nombre": clase,
                "emblema_nombre": "Lucina" if nombre == "LucinaTest" else "",
                "en_fusion": nombre == "LucinaTest", "nivel_vinculo": 5,
                "inventario": [{"nombre": arma, "equipada": True}], "x": x, "y": y,
            }, tablero=tablero)
            tablero.registrar_unidad(f, resolver_colision=False)
        self.lucina = tablero.obtener_ficha("LucinaTest")

    @classmethod
    def tearDownClass(cls):
        cls.client.post("/api/mapa/seleccionar", json={"capitulo": 7})

    def test_all_for_one_encadena_a_todos_los_cercanos(self):
        from motor_analisis import obtener_aliados_backup
        sin_ataque = [c.nombre for c in obtener_aliados_backup(self.lucina, self.enemigo, tablero=tablero)]
        con_ataque = [c.nombre for c in obtener_aliados_backup(
            self.lucina, self.enemigo, tablero=tablero, ataque_emblema="All for One (Todos para uno)")]
        self.assertNotIn("Mago1", sin_ataque, "un Místico no encadena en un ataque normal")
        self.assertIn("Apoyo1", con_ataque)
        self.assertIn("Mago1", con_ataque, "All for One fuerza a encadenar sea cual sea el estilo")
        self.assertNotIn("Lejos", con_ataque, "a 4 casillas queda fuera del radio 2")

    def test_bonded_shield_marca_a_los_adyacentes(self):
        r = self.client.post("/api/unidad/escudo_vinculo", json={"nombre": "LucinaTest"})
        self.assertEqual(r.status_code, 200, r.get_json())
        protegidos = {p["aliado"]: p["probabilidad"] for p in r.get_json()["protegidos"]}
        self.assertEqual(set(protegidos), {"Apoyo1", "Mago1"}, "solo los adyacentes")
        # LucinaTest es Dragón: 90 %, no 100 %
        self.assertEqual(set(protegidos.values()), {90})
        estados = tablero.obtener_ficha("Apoyo1").estados_temporales
        self.assertTrue(any(e["sid"] == "SID_絆盾" for e in estados))

    def test_sin_la_habilidad_el_comando_falla(self):
        r = self.client.post("/api/unidad/escudo_vinculo", json={"nombre": "Apoyo1"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Bonded Shield", r.get_json()["error"])



class TestRoundTripDelModal(unittest.TestCase):
    """Abrir el modal de un jefe con Emblema Oscuro, guardar y volver a entrar no debe
    duplicar sus armas de Emblema ni cambiarlas por las genéricas del mismo nombre."""

    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()

    def setUp(self):
        self.client.post("/api/mapa/seleccionar", json={"capitulo": 10})
        self.client.post("/api/preset/actual", json={})

    @classmethod
    def tearDownClass(cls):
        cls.client.post("/api/mapa/seleccionar", json={"capitulo": 7})

    def _payload_como_el_modal(self, f, con_id=True, es_aliado=None):
        """El modal reconstruye el inventario desde sus 5 ranuras de texto: sin marca de
        Emblema y, en la versión antigua, sin el IID."""
        return {
            "nombre": f.nombre, "es_aliado": f.es_aliado if es_aliado is None else es_aliado,
            "x": f.x, "y": f.y, "nivel": f.nivel, "clase_nombre": f.clase_nombre,
            "emblema_nombre": f.emblema_nombre, "emblema_id": f.emblema_id,
            "hp_actual": f.hp_actual, "hp_max": f.hp_max,
            "inventario": [{"id": i.get("id") if con_id else None, "arma": i["nombre"],
                            "nombre": i["nombre"], "nombre_base": i["nombre"],
                            "equipada": i["equipada"], "tipo": "Arma",
                            "refine_lvl": 0, "grabado": None} for i in f.inventario],
        }

    def test_guardar_dos_veces_no_duplica(self):
        for nombre in ("Hyacinth", "Hortensia"):
            f = tablero.obtener_ficha(nombre)
            original = [i["id"] for i in f.inventario]
            payload = self._payload_como_el_modal(f)
            for _ in range(2):
                self.client.post("/api/unidad/guardar", json=payload)
            self.assertEqual([i["id"] for i in tablero.obtener_ficha(nombre).inventario], original, nombre)

    def test_el_iid_conserva_el_arma_de_evento(self):
        f = tablero.obtener_ficha("Hyacinth")
        self.client.post("/api/unidad/guardar", json=self._payload_como_el_modal(f))
        bow = next(i for i in tablero.obtener_ficha("Hyacinth").inventario if i["nombre"] == "Killer Bow")
        # La de Lyn (Mt 9, crit 10), no la genérica IID_キラーボウ (Mt 7, crit 30)
        self.assertEqual((bow["id"], bow["mt"], bow["crit"]), ("IID_リン_キラーボウ_M010", 9, 10))

    def test_un_payload_antiguo_sin_iid_tampoco_duplica(self):
        f = tablero.obtener_ficha("Hyacinth")
        self.client.post("/api/unidad/guardar", json=self._payload_como_el_modal(f, con_id=False))
        nombres = [i["nombre"] for i in tablero.obtener_ficha("Hyacinth").inventario]
        self.assertEqual(len(nombres), len(set(nombres)), nombres)

    def test_convertir_el_jefe_en_aliado_no_rompe_el_estado(self):
        """El bug: /api/estado devolvía 500 en el Cap. 10 porque los refuerzos por evento
        de combate/muerte no tienen casilla y snapshot() la serializaba a ciegas."""
        f = tablero.obtener_ficha("Hyacinth")
        r = self.client.post("/api/unidad/guardar", json=self._payload_como_el_modal(f, es_aliado=True))
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(self.client.get("/api/estado").status_code, 200)
        h = tablero.obtener_ficha("Hyacinth")
        self.assertTrue(h.es_aliado)
        self.assertTrue(h.como_dict()["puede_call_doubles"], "sigue llevando el Emblema de Lyn")

    def test_snapshot_serializa_eventos_sin_casilla(self):
        import json as _json
        snap = tablero.snapshot()
        _json.dumps(snap)   # no debe lanzar
        eventos = snap["refuerzos_por_evento"]
        self.assertTrue(eventos, "el Cap. 10 tiene refuerzos por evento")
        self.assertTrue(any(e["casilla"] is None for e in eventos),
                        "los de combate/muerte/objeto no tienen casilla")



if __name__ == "__main__":
    unittest.main()
