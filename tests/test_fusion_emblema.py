"""
Fusión (Engage) y Emblemas: duración, recargas, ataque de Emblema único por
Fusión, escalado por vínculo, armas de Emblema, secuencia contra Hortensia.

Origen: tests/test_fixes_tactical.py (partido por dominio el 2026-09-18).
"""

import os
import sys
import json
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from helpers import ruta_fixture  # noqa: E402
from app import app, tablero, resolver_unidad_con_catalogo  # noqa: E402
from motor_calculo import Unidad  # noqa: E402


class TestFusionEmblema(unittest.TestCase):

    def setUp(self):
        # resolver_unidad_con_catalogo lee app.tablero para heredar estado: empezar siempre limpio
        tablero.limpiar()

    def test_duracion_fusion_3_turnos_o_4_con_vinculo_11(self):
        """
        Todos tienen 3 turnos de emblema salvo que una unidad tenga nivel 11 de vínculo
        con dicho emblema, que gana 1 turno más. No se distingue entre tipos de unidades.
        """
        # 1. Alear (Dragón) con vínculo nivel 10 -> debe tener 3 turnos, NO 4
        alear_lv10 = resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 1, "y": 1, "es_aliado": True,
            "emblema_nombre": "Marth", "nivel_vinculo": 10, "en_fusion": True
        })
        self.assertEqual(alear_lv10.turnos_fusion, 3, "Alear con vínculo 10 debe tener 3 turnos de fusión base")

        # 2. Alfred (Caballería) con vínculo nivel 10 -> 3 turnos
        alfred_lv10 = resolver_unidad_con_catalogo({
            "nombre": "Alfred", "x": 1, "y": 2, "es_aliado": True,
            "emblema_nombre": "Sigurd", "nivel_vinculo": 10, "en_fusion": True
        })
        self.assertEqual(alfred_lv10.turnos_fusion, 3, "Caballería con vínculo 10 debe tener 3 turnos")

        # 3. Unidad con nivel de vínculo >= 11 gana 1 turno más (4 turnos)
        alear_lv11 = resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 1, "y": 3, "es_aliado": True,
            "emblema_nombre": "Marth", "nivel_vinculo": 11, "en_fusion": True
        })
        self.assertEqual(alear_lv11.turnos_fusion, 4, "Unidad con vínculo 11 gana +1 turno (4 en total)")

        alfred_lv11 = resolver_unidad_con_catalogo({
            "nombre": "Alfred", "x": 1, "y": 4, "es_aliado": True,
            "emblema_nombre": "Sigurd", "nivel_vinculo": 15, "en_fusion": True
        })
        self.assertEqual(alfred_lv11.turnos_fusion, 4, "Cualquier unidad con vínculo >= 11 tiene 4 turnos")

    def test_fusion_no_se_retira_y_decrementa_por_turno(self):
        """
        Una vez activada la fusión, no se puede retirar hasta que acabe.
        Al avanzar turno se decrementa en 1, y al llegar a 0 se apaga y energía queda en 0.
        """
        tablero.limpiar()
        chloe = resolver_unidad_con_catalogo({
            "nombre": "Chloé", "x": 3, "y": 3, "es_aliado": True,
            "emblema_nombre": "Edelgard", "nivel_vinculo": 5, "en_fusion": True
        })
        tablero.registrar_unidad(chloe)
        self.assertTrue(chloe.en_fusion)
        self.assertEqual(chloe.turnos_fusion, 3)

        # Intento de desmarcar fusión mientras turnos_fusion > 0 -> NO se retira
        chloe_mod = resolver_unidad_con_catalogo({
            "nombre": "Chloé", "x": 3, "y": 3, "es_aliado": True,
            "emblema_nombre": "Edelgard", "en_fusion": False
        }, tablero=tablero)
        tablero.registrar_unidad(chloe_mod)
        self.assertTrue(chloe_mod.en_fusion, "La fusión debe mantenerse bloqueada activa mientras turnos > 0")
        self.assertEqual(chloe_mod.turnos_fusion, 3)

        # Turno 1 -> Turno 2 (avanzar_turno resta 1 turno de fusión)
        tablero.avanzar_turno()
        f_chloe = tablero.obtener_ficha("Chloé")
        self.assertTrue(f_chloe.en_fusion)
        self.assertEqual(f_chloe.turnos_fusion, 2)

        # Turno 2 -> Turno 3
        tablero.avanzar_turno()
        f_chloe = tablero.obtener_ficha("Chloé")
        self.assertTrue(f_chloe.en_fusion)
        self.assertEqual(f_chloe.turnos_fusion, 1)

        # Turno 3 -> Turno 4 (expira la fusión)
        tablero.avanzar_turno()
        f_chloe = tablero.obtener_ficha("Chloé")
        self.assertFalse(f_chloe.en_fusion, "Al llegar a 0 turnos la fusión debe terminar")
        self.assertEqual(f_chloe.turnos_fusion, 0)
        self.assertEqual(f_chloe.energia_emblema, 0, "Al finalizar la fusión la energía se resetea a 0")
        self.assertFalse(f_chloe.ataque_emblema_usado, "El flag de ataque emblema se resetea para futuras fusiones")

    def test_recargas_de_emblema_solo_tras_agotar_fusion(self):
        """
        Las recargas de emblema (atacar +1, recibir +1, casilla recarga 100%)
        solo entran en vigor cuando se han agotado todos los turnos de fusión.
        """
        tablero.limpiar()
        # Aliado en fusión activa (HP alto para sobrevivir a varios contraataques
        # de EnemigoTest a lo largo del test y poder seguir contraatacando)
        tablero.registrar_unidad(resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 5, "y": 5, "es_aliado": True,
            "emblema_nombre": "Marth", "en_fusion": True, "energia_emblema": 0,
            "stats": {"hp": 40, "defensa": 12}
        }))
        # Arma sin ventaja de triángulo sobre la Espada de Alear (Liberation), para
        # que en el paso 4 su contraataque no quede anulado por Ruptura instantánea.
        tablero.registrar_unidad(resolver_unidad_con_catalogo({
            "nombre": "EnemigoTest", "x": 5, "y": 6, "es_aliado": False,
            "arma_nombre": "Iron Sword", "stats": {"hp": 30, "defensa": 5}
        }))

        client = app.test_client()
        # 1. Atacar estando en fusión NO recarga energía
        res = client.post("/api/combate/ejecutar", json={
            "atacante": "Alear", "defensor": "EnemigoTest", "arma_nombre": "Liberation"
        })
        self.assertEqual(res.status_code, 200)
        f_alear = tablero.obtener_ficha("Alear")
        self.assertEqual(f_alear.energia_emblema, 0, "En fusión no se acumula energía")

        # 2. Agotar la fusión completamente
        tablero.avanzar_turno() # 3 -> 2
        tablero.avanzar_turno() # 2 -> 1
        tablero.avanzar_turno() # 1 -> 0 (Fusión terminada, en_fusion=False, energia=0)
        self.assertFalse(f_alear.en_fusion)
        self.assertEqual(f_alear.energia_emblema, 0)

        # 3. Fuera de fusión: atacar da 1 recarga
        f_alear.ha_actuado = False
        res = client.post("/api/combate/ejecutar", json={
            "atacante": "Alear", "defensor": "EnemigoTest", "arma_nombre": "Liberation"
        })
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(f_alear.energia_emblema, 1, "Fuera de fusión, atacar da recarga")

        # 4. Fuera de fusión: defender da 1 recarga
        energia_previa = f_alear.energia_emblema
        res = client.post("/api/combate/ejecutar", json={
            "atacante": "EnemigoTest", "defensor": "Alear", "arma_nombre": "Iron Sword"
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(f_alear.energia_emblema, energia_previa + 1, "Recibir un ataque da otra recarga (+1)")

        # 5. Casilla de recarga de Emblema completa el medidor al 100% (6/6) cuando la
        # unidad TERMINA su acción encima (pisarla sin actuar no recarga)
        if tablero.mapa and hasattr(tablero.mapa, 'grid') and len(tablero.mapa.grid) > 13:
            tablero.mapa.grid[13][6].es_recarga_emblema = True
            tablero.mover_unidad("Alear", 13, 6)
            self.assertLess(f_alear.energia_emblema, f_alear.max_energia_emblema, "Pisar la casilla no recarga todavía")
            tablero.aplicar_recarga_emblema_en_casilla("Alear")
            self.assertEqual(f_alear.energia_emblema, f_alear.max_energia_emblema, "Terminar la acción en la casilla llena al 100%")

    def test_ataque_de_emblema_una_vez_por_fusion(self):
        """
        El ataque/habilidad especial del emblema se puede usar una sola vez durante la fusión.
        Una vez usado, el flag ataque_emblema_usado es True y no se vuelve a recomendar.
        """
        tablero.limpiar()
        marth_ali = resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 10, "y": 5, "es_aliado": True,
            "emblema_nombre": "Marth", "en_fusion": True, "nivel_vinculo": 10
        })
        tablero.registrar_unidad(marth_ali)

        jefe = resolver_unidad_con_catalogo({
            "nombre": "Hortensia (Boss)", "x": 10, "y": 6, "es_aliado": False,
            "arma_nombre": "Elfire", "stats": {"hp": 30, "defensa": 5}, "hp_stock": 2
        })
        tablero.registrar_unidad(jefe)

        self.assertFalse(marth_ali.ataque_emblema_usado)

        # Ejecutar Lodestar Rush (engage attack)
        client = app.test_client()
        res = client.post("/api/combate/ejecutar", json={
            "atacante": "Alear", "defensor": "Hortensia (Boss)",
            "arma_nombre": "Liberation", "es_engage_attack": True,
            "engage_attack_nombre": "Lodestar Rush"
        })
        self.assertEqual(res.status_code, 200)
        self.assertTrue(marth_ali.ataque_emblema_usado, "Ataque especial de emblema debe marcarse como usado")

        # El análisis táctico no debe recomendar usar Lodestar Rush de nuevo
        marth_ali.ha_actuado = False
        analisis = client.post("/api/analizar", json={"perfil": "seguro"}).get_json()
        op_alear = [r for r in analisis["resultados"] if r.get("aliado") == "Alear"]
        if op_alear:
            rec_txt = op_alear[0].get("recomendacion", "")
            self.assertIn("ya usada en esta fusión", rec_txt)

    def test_bonos_y_armas_de_engage_escalan_con_vinculo(self):
        """
        Verifica que los stats y armas de fusión se desbloqueen y escalen según el nivel de vínculo:
        - Marth Lv 1: Rapier (no Mercurius ni Falchion), Dex +1, Spd +1.
        - Marth Lv 10: Mercurius disponible en fusión.
        - Marth Lv 15+: Falchion disponible en fusión.
        - Marth Lv 20: Str +3, Dex +4, Spd +4.
        """
        # 1. Marth Lv 1
        alear_lv1 = resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 1, "y": 1, "es_aliado": True,
            "emblema_nombre": "Marth", "nivel_vinculo": 1, "en_fusion": True
        })
        nombres_inv_lv1 = [str(it.get("nombre", "")) for it in alear_lv1.inventario]
        self.assertTrue(any("rapier" in n.lower() for n in nombres_inv_lv1), "Rapier debe estar a Lv 1")
        self.assertFalse(any("mercurius" in n.lower() for n in nombres_inv_lv1), "Mercurius no debe estar a Lv 1")
        self.assertFalse(any("falchion" in n.lower() for n in nombres_inv_lv1), "Falchion no debe estar a Lv 1")

        # 2. Marth Lv 10
        alear_lv10 = resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 1, "y": 1, "es_aliado": True,
            "emblema_nombre": "Marth", "nivel_vinculo": 10, "en_fusion": True
        })
        nombres_inv_lv10 = [str(it.get("nombre", "")) for it in alear_lv10.inventario]
        self.assertTrue(any("mercurius" in n.lower() for n in nombres_inv_lv10), "Mercurius debe estar desbloqueado a Lv 10")
        self.assertFalse(any("falchion" in n.lower() for n in nombres_inv_lv10), "Falchion no debe estar a Lv 10")

        # 3. Marth Lv 15
        alear_lv15 = resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 1, "y": 1, "es_aliado": True,
            "emblema_nombre": "Marth", "nivel_vinculo": 15, "en_fusion": True
        })
        nombres_inv_lv15 = [str(it.get("nombre", "")) for it in alear_lv15.inventario]
        self.assertTrue(any("falchion" in n.lower() for n in nombres_inv_lv15), "Falchion debe estar desbloqueado a Lv 15")

        # 4. Progresión de Stats entre Lv 1 y Lv 20
        alear_lv20 = resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 1, "y": 1, "es_aliado": True,
            "emblema_nombre": "Marth", "nivel_vinculo": 20
        })
        # Marth da Str +1, Dex +1, Spd +1 a Lv 1 y Str +3, Dex +4, Spd +4 a Lv 20
        self.assertEqual(alear_lv20.stats.fuerza - alear_lv1.stats.fuerza, 2, "Delta Str entre Lv 1 y 20 debe ser +2 (1 -> 3)")
        self.assertEqual(alear_lv20.stats.destreza - alear_lv1.stats.destreza, 3, "Delta Dex entre Lv 1 y 20 debe ser +3 (1 -> 4)")
        self.assertEqual(alear_lv20.stats.velocidad - alear_lv1.stats.velocidad, 3, "Delta Spd entre Lv 1 y 20 debe ser +3 (1 -> 4)")

    def test_vinculo_20_reduce_medidor_a_5(self):
        """
        A nivel 20 de vínculo, el medidor de recarga máxima se reduce en 1, pasando de 6 a 5.
        Solo pasa únicamente a nivel 20:
        - Niveles 1..19: max_energia_emblema = 6
        - Nivel 20: max_energia_emblema = 5
        - Pisar casilla de recarga a nivel 20 llena exactamente a 5 (no 6).
        - Atacar o defender fuera de fusión a nivel 20 no excede de 5 cargas.
        """
        # Niveles 1, 10, 15, 19 tienen max_energia_emblema = 6
        for lvl in [1, 5, 10, 15, 19]:
            u = resolver_unidad_con_catalogo({
                "nombre": "Alear", "x": 1, "y": 1, "es_aliado": True,
                "emblema_nombre": "Marth", "nivel_vinculo": lvl
            })
            self.assertEqual(u.max_energia_emblema, 6, f"Nivel {lvl} debe tener max_energia_emblema = 6")
            self.assertEqual(u.stats.max_energia_emblema, 6)

        # Nivel 20 tiene max_energia_emblema = 5
        u20 = resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 1, "y": 1, "es_aliado": True,
            "emblema_nombre": "Marth", "nivel_vinculo": 20, "energia_emblema": 6
        })
        self.assertEqual(u20.max_energia_emblema, 5, "Nivel 20 debe tener max_energia_emblema = 5")
        self.assertEqual(u20.stats.max_energia_emblema, 5)
        self.assertEqual(u20.energia_emblema, 5, "Energía debe clampearse al máximo de 5")

        # Pisar casilla de recarga a Nivel 20 llena al 100% (5 cargas, no 6)
        tablero.limpiar()
        u20_cero = resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 2, "y": 2, "es_aliado": True,
            "emblema_nombre": "Marth", "nivel_vinculo": 20, "energia_emblema": 0
        })
        tablero.registrar_unidad(u20_cero)
        if tablero.mapa and hasattr(tablero.mapa, 'grid') and len(tablero.mapa.grid) > 13:
            tablero.mapa.grid[13][6].es_recarga_emblema = True
            tablero.mover_unidad("Alear", 13, 6)
            tablero.aplicar_recarga_emblema_en_casilla("Alear")
            f_alear = tablero.obtener_ficha("Alear")
            self.assertEqual(f_alear.energia_emblema, 5, "Casilla de recarga a Nivel 20 debe llenar a 5")
            self.assertEqual(f_alear.max_energia_emblema, 5)

        # Combate fuera de fusión a Nivel 20: no puede sobrepasar 5
        tablero.limpiar()
        u20_combate = resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 5, "y": 5, "es_aliado": True,
            "emblema_nombre": "Marth", "nivel_vinculo": 20, "energia_emblema": 4
        })
        ene_combate = resolver_unidad_con_catalogo({
            "nombre": "EnemigoDummy", "x": 5, "y": 6, "es_aliado": False,
            "arma_nombre": "Iron Lance", "stats": {"hp": 50, "defensa": 5}
        })
        tablero.registrar_unidad(u20_combate)
        tablero.registrar_unidad(ene_combate)

        client = app.test_client()
        res = client.post("/api/combate/ejecutar", json={
            "atacante": "Alear", "defensor": "EnemigoDummy", "arma_nombre": "Liberation"
        })
        self.assertEqual(res.status_code, 200)
        f_al = tablero.obtener_ficha("Alear")
        self.assertEqual(f_al.energia_emblema, 5, "Energía debe alcanzar el tope de 5 tras ganar carga")

        # Otro ataque no debe superar 5
        f_al.ha_actuado = False
        res2 = client.post("/api/combate/ejecutar", json={
            "atacante": "Alear", "defensor": "EnemigoDummy", "arma_nombre": "Liberation"
        })
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(f_al.energia_emblema, 5, "Energía no puede superar max_energia_emblema = 5")

    def test_habilidades_heredables_no_se_equipan_solas(self):
        """
        Las habilidades heredables (como Avoid +10, Sword Agility, etc.) NO deben
        equiparse automáticamente solo por sincronizar con el Emblema. Solo deben
        aplicarse las habilidades de sincronía (synchro_skills) auténticas.
        """
        alear = resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 1, "y": 1, "es_aliado": True,
            "emblema_nombre": "Marth", "nivel_vinculo": 20
        })
        habs_nombres = [str(h).lower() for h in alear.habilidades]
        # Avoid +10 y Sword Agility son heredables
        self.assertFalse(any("avoid +" in h for h in habs_nombres), "Habilidades de herencia como Avoid + no deben auto-equiparse")
        self.assertFalse(any("sword agility" in h for h in habs_nombres), "Sword Agility de herencia no debe auto-equiparse")
        # En cambio Perceptive y Break Defenses son pasivas de sincronía legítimas
        self.assertTrue(any("perceptive" in h for h in habs_nombres), "Perceptive debe estar en pasivas")

    def test_api_catalogo_emblemas_devuelve_los_21(self):
        """
        Verifica que el endpoint /api/catalogo/emblemas devuelva los 21 Emblemas
        (Base + DLC) con sus tablas de 20 niveles y la regla Lv20 max_energia=5.
        """
        client = app.test_client()
        res = client.get("/api/catalogo/emblemas")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("ok"))
        emblemas = data.get("emblemas", {})
        self.assertEqual(len(emblemas), 21, "Deben estar presentes los 21 Emblemas (14 base + 7 DLC)")

        for eid, einfo in emblemas.items():
            b_levels = einfo.get("bond_levels", {})
            self.assertEqual(len(b_levels), 20, f"Emblema {eid} debe tener exactamente 20 niveles")
            self.assertEqual(b_levels["19"]["max_energia_emblema"], 6, f"Emblema {eid} a Lv 19 debe tener max 6")
            self.assertEqual(b_levels["20"]["max_energia_emblema"], 5, f"Emblema {eid} a Lv 20 debe tener max 5")

    def test_edelgard_carga_houses_unite(self):
        """Verifica que el Emblema Edelgard cargue correctamente su ataque Houses Unite."""
        client = app.test_client()
        res = client.get("/api/catalogo/emblemas")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("ok"))
        emblemas = data.get("emblemas", {})
        self.assertIn("GID_DLC_EDELGARD", emblemas)
        ed = emblemas["GID_DLC_EDELGARD"]
        self.assertEqual(ed.get("engage_attack"), "Houses Unite (Unión de Casas)")

    def test_armas_de_emblema_usables_en_fusion(self):
        """Verifica que al fusionar, las armas desbloqueadas del Emblema sean utilizables."""
        from motor_analisis import _armas_aliado
        # Chloé con Edelgard a nivel de vínculo 10
        chloe_stats = Unidad(nombre="Chloé", hp=26, fuerza=9, magia=8, destreza=15, velocidad=13, defensa=9, resistencia=10, suerte=11, complexion=5)
        chloe_stats.emblema_nombre = "Edelgard"
        chloe_stats.nivel_vinculo = 10
        chloe_stats.en_fusion = True
        chloe_stats.inventario = [{"nombre": "Iron Lance"}]

        armas_fusion = _armas_aliado(chloe_stats)
        nombres_armas = [a.nombre for a, es_eng, _ in armas_fusion]
        # A nivel 10, Edelgard otorga Aymr y Areadbhar (con sufijo (Emblema) para diferenciarlas)
        self.assertTrue(any("Aymr" in n for n in nombres_armas), "Aymr debe estar disponible como arma usable en fusión")
        self.assertTrue(any("Areadbhar" in n for n in nombres_armas), "Areadbhar debe estar disponible como arma usable en fusión")
        self.assertIn("Iron Lance", nombres_armas, "El arma de inventario normal debe seguir presente")

        # Marth a nivel 15 con Alear
        alear_stats = Unidad(nombre="Alear", hp=24, fuerza=10, magia=2, destreza=12, velocidad=12, defensa=8, resistencia=5, suerte=9, complexion=6)
        alear_stats.emblema_nombre = "Marth"
        alear_stats.nivel_vinculo = 15
        alear_stats.en_fusion = True
        alear_stats.inventario = [{"nombre": "Libération"}]

        armas_marth = _armas_aliado(alear_stats)
        nombres_marth = [a.nombre for a, es_eng, _ in armas_marth]
        self.assertTrue(any("Rapier" in n for n in nombres_marth))
        self.assertTrue(any("Mercurius" in n for n in nombres_marth))
        self.assertTrue(any("Falchion" in n for n in nombres_marth))

    def test_hortensia_secuencia_de_3_pasos_con_engage(self):
        """
        Verifica el flujo canónico de 3 pasos para derrotar a Hortensia (Boss) en Capítulo 7:
        1. Recomendaciones simultáneas en el panel para Chloé, Alear y Céline con sus técnicas Engage.
        2. Paso 1: Chloé (Houses Unite) quiebra la 1ª barra, Hortensia consume la piedra resurrectora
           (hp_stock pasa de 1 a 0) y revive con 36/36 HP sin contraataque.
        3. Paso 2: Alear (Lodestar Rush con Fólkvangr) quita 9x3 = 27 dmg sin contraataque,
           dejando a Hortensia en 36 - 27 = 9 HP.
        4. Paso 3: Céline (Warp Ragnarök) se teletransporta a casilla adyacente libre y remata
           a Hortensia (18 dmg > 9 HP), dejándola en 0 HP y viva=False.
        """
        client = app.test_client()
        import os
        path_test = ruta_fixture("partida_hortensia_cap7.json")
        self.assertTrue(os.path.exists(path_test))
        with open(path_test, "r", encoding="utf-8") as f:
            d = json.load(f)

        for x in d["fichas"]:
            if "hortensia" in x["nombre"].lower():
                x["hp_stock"] = 1
                x["hp_actual"] = 25
                x["hp_max"] = 36

        res_imp = client.post("/api/partida/importar", json={"partida": d})
        self.assertEqual(res_imp.status_code, 200)

        # 1. Panel táctico debe recomendar simultáneamente a Alear, Chloé y Céline
        res_an = client.post("/api/analizar", json={})
        self.assertEqual(res_an.status_code, 200)
        recs = res_an.get_json().get("resultados", [])
        aliados_hortensia = [r.get("aliado") for r in recs if "hortensia" in str(r.get("enemigo")).lower()]

        self.assertTrue(any("chlo" in a.lower() for a in aliados_hortensia), "Chloé debe estar recomendada")
        self.assertTrue(any("alear" in a.lower() for a in aliados_hortensia), "Alear debe estar recomendada")
        self.assertTrue(any("line" in a.lower() for a in aliados_hortensia), "Céline debe estar recomendada")

        nom_chloe = [f.nombre for f in tablero.obtener_aliados() if "chlo" in f.nombre.lower()][0]
        nom_alear = [f.nombre for f in tablero.obtener_aliados() if "alear" in f.nombre.lower()][0]
        nom_celine = [f.nombre for f in tablero.obtener_aliados() if "line" in f.nombre.lower()][0]

        # 2. Paso 1: Chloé usa Houses Unite
        r1 = client.post("/api/combate/ejecutar", json={
            "atacante": nom_chloe,
            "defensor": "Hortensia (Boss)",
            "arma": "Houses Unite",
            "pos_destino": [16, 7]
        })
        self.assertEqual(r1.status_code, 200)
        hort = tablero.obtener_ficha("Hortensia (Boss)")
        self.assertEqual(hort.hp_actual, 36, "Hortensia debió revivir a 36 HP tras romper su 1ª barra")
        self.assertEqual(hort.hp_stock, 0, "Hortensia debió consumir su piedra resurrectora")

        # 3. Paso 2: Alear usa Lodestar Rush (Fólkvangr)
        r2 = client.post("/api/combate/ejecutar", json={
            "atacante": nom_alear,
            "defensor": "Hortensia (Boss)",
            "arma": "Lodestar Rush (Fólkvangr)",
            "pos_destino": [16, 9]
        })
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(hort.hp_actual, 9, "Hortensia debió quedar en 9 HP tras 9x3=27 de Lodestar Rush")

        # 4. Paso 3: Céline usa Warp Ragnarök al hueco adyacente libre
        libres_adj = []
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
            pos_adj = (16 + dx, 8 + dy)
            if not any(f.viva and (f.x, f.y) == pos_adj for f in tablero.fichas.values()):
                libres_adj.append(pos_adj)
        self.assertTrue(len(libres_adj) > 0, "Debe haber al menos 1 casilla adyacente libre")

        r3 = client.post("/api/combate/ejecutar", json={
            "atacante": nom_celine,
            "defensor": "Hortensia (Boss)",
            "arma": "Warp Ragnarök",
            "pos_destino": list(libres_adj[0])
        })
        self.assertEqual(r3.status_code, 200)
        self.assertEqual(hort.hp_actual, 0, "Hortensia debe quedar en 0 HP tras el remate")
        self.assertFalse(hort.viva, "Hortensia debe estar derrotada")

    def test_recarga_de_emblema_proporcional_a_golpes_reales(self):
        """
        La recarga de Fusión del defensor debe basarse en los contraataques que
        REALMENTE ocurrieron, no asumir siempre +1: si el defensor tiene
        follow-up (podría contraatacar 2 veces) pero su primer contraataque ya
        mata al atacante, el segundo golpe nunca ocurre y solo debe dar 1 carga.
        """
        tablero.limpiar()
        tablero.registrar_unidad(resolver_unidad_con_catalogo({
            "nombre": "Rapido", "x": 5, "y": 5, "es_aliado": True,
            "arma_nombre": "Iron Sword",
            "emblema_nombre": "Marth", "energia_emblema": 0,
            "stats": {"hp": 30, "fuerza": 10, "velocidad": 20, "defensa": 8}
        }))
        tablero.registrar_unidad(resolver_unidad_con_catalogo({
            "nombre": "Debil", "x": 5, "y": 6, "es_aliado": False,
            "arma_nombre": "Iron Sword",
            "hp_actual": 3, "hp_max": 3,
            "stats": {"hp": 3, "velocidad": 1, "defensa": 0}
        }))

        client = app.test_client()
        res = client.post("/api/combate/ejecutar", json={
            "atacante": "Debil", "defensor": "Rapido", "arma_nombre": "Iron Sword"
        })
        self.assertEqual(res.status_code, 200)
        secuencia = res.get_json()["combate"]["resultado"]["secuencia"]
        golpes_rapido = [s for s in secuencia if s["actor"] == "Rapido"]
        self.assertEqual(len(golpes_rapido), 1, "Rapido debe matar a Debil en su primer contraataque, sin llegar al follow-up")

        f_rapido = tablero.obtener_ficha("Rapido")
        self.assertEqual(f_rapido.energia_emblema, 1, "Solo debe recibir 1 carga por el único contraataque que ocurrió, no 2")

if __name__ == "__main__":
    unittest.main()
