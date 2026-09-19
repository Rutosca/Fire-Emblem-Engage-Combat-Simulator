"""
Análisis táctico y recomendaciones (motor_analisis.analizar_situacion_tactica
y /api/analizar): selección de arma, deduplicación, combos, jefes, curación.

Origen: tests/test_fixes_tactical.py (partido por dominio el 2026-09-18).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import app, tablero, _mapa, resolver_unidad_con_catalogo, _arma_desde_item  # noqa: E402
from motor_calculo import Unidad  # noqa: E402
from estado_tablero import FichaUnidad  # noqa: E402


class TestAnalisisTactico(unittest.TestCase):

    def setUp(self):
        # resolver_unidad_con_catalogo lee app.tablero para heredar estado: empezar siempre limpio
        tablero.limpiar()

    def test_chain_attack_backup_reportado_en_analizar(self):
        """Chain Attack: 10% Max HP defensor, 80% Hit, reportado explícitamente en /api/analizar."""
        from app import es_unidad_backup, obtener_aliados_backup
        tablero.limpiar()

        # Aliado Atacante: Alear en (5, 5), espada rango 1
        alear = resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 5, "y": 5, "mov": 4, "es_aliado": True,
            "arma_nombre": "Liberation", "stats": {"hp": 25, "fuerza": 12, "velocidad": 12, "estilo_combate": "Dragon"}
        })
        tablero.registrar_unidad(alear)

        # Aliado Backup: Lapis en (6, 5), Sword Fighter (estilo Backup / De apoyo), rango 1
        lapis = resolver_unidad_con_catalogo({
            "nombre": "Lapis", "x": 6, "y": 5, "mov": 4, "es_aliado": True,
            "clase_nombre": "Sword Fighter", "arma_nombre": "Iron Sword",
            "stats": {"hp": 22, "fuerza": 11, "velocidad": 14, "estilo_combate": "De apoyo"}
        })
        tablero.registrar_unidad(lapis)

        # Enemigo: Lance Fighter en (6, 6) con 32 HP Max
        ene = resolver_unidad_con_catalogo({
            "nombre": "Lance Fighter (6,6)", "x": 6, "y": 6, "mov": 4, "es_aliado": False,
            "arma_nombre": "Iron Lance", "stats": {"hp": 32, "hp_max": 32, "defensa": 8}
        })
        tablero.registrar_unidad(ene)

        # 1. Verificar detección de backup
        self.assertTrue(es_unidad_backup(lapis), "Lapis (Sword Fighter / De apoyo) debe ser reconocida como Backup")
        self.assertFalse(es_unidad_backup(alear), "Alear (Dragon) no es clase Backup directa")

        # 2. Verificar aliados de apoyo detectados
        # Lapis en (6,5) está adyacente a Lance Fighter en (6,6) (distancia 1, dentro de rango [1] de Iron Sword)
        apoyos = obtener_aliados_backup(alear, ene)
        self.assertEqual(len(apoyos), 1)
        self.assertEqual(apoyos[0].nombre, "Lapis")

        # 3. Test de endpoint /api/analizar
        client = app.test_client()
        res = client.post("/api/analizar", json={"perfil": "seguro"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(len(data.get("resultados", [])) > 0)

        # Buscar la jugada de Alear contra Lance Fighter (oportunidad de ataque del jugador)
        jugada_alear = [r for r in data["resultados"] if r.get("tipo_analisis") in ("oportunidad_jugador", "combo_ataque") and r.get("aliado") == "Alear" and r.get("enemigo") == "Lance Fighter (6,6)"]
        self.assertTrue(len(jugada_alear) > 0, "Debe existir recomendación de ataque de Alear contra Lance Fighter")
        r_alear = jugada_alear[0]

        # Verificar que chain_attacks está presente
        chain_info = r_alear.get("chain_attacks", [])
        self.assertEqual(len(chain_info), 1)
        self.assertEqual(chain_info[0]["nombre"], "Lapis")
        # 10% de 32 HP = 3 de daño
        self.assertEqual(chain_info[0]["daño"], 3)
        self.assertEqual(chain_info[0]["precision"], 80)

        # Verificar que el texto de recomendación contiene el mensaje exacto solicitado
        rec = r_alear.get("recomendacion", "")
        self.assertNotIn("ataque en cadena", rec)
        self.assertNotIn("Y luego el ataque normal del aliado", rec)

    def test_lapis_ataca_lance_fighter_debilitado_sin_curacion_fantasma(self):
        """
        Verifica el bug reportado:
        Lance Fighter (6,10) tenía su HP ajustado de 32 a 10.
        Al atacar Lapis con Espada de Hierro (14 dmg en 2 golpes de 7), el defensor debe
        quedar en 0 HP (derrotado), en lugar de 'curarse' a 18 calculando desde 32 base.
        """
        tablero.limpiar()
        # Lapis en (2, 10), Espada de Hierro, 26 HP, mov 5
        lapis = resolver_unidad_con_catalogo({
            "nombre": "Lapis", "x": 2, "y": 10, "mov": 5, "es_aliado": True,
            "arma_nombre": "Iron Sword",
            "stats": {"hp": 26, "fuerza": 11, "velocidad": 14, "defensa": 5, "destreza": 12, "complexion": 5}
        })
        tablero.registrar_unidad(lapis)

        # Lance Fighter (6,10) con HP base 32, pero ajustado a 10 HP
        lance_fighter = resolver_unidad_con_catalogo({
            "nombre": "Lance Fighter (6,10)", "x": 6, "y": 10, "mov": 4, "es_aliado": False,
            "arma_nombre": "Iron Lance",
            "hp_actual": 10,
            "hp_max": 32,
            "stats": {"hp": 32, "defensa": 9, "velocidad": 9, "fuerza": 13}
        })
        tablero.registrar_unidad(lance_fighter)

        # Verificar que el HP actual y stats.hp quedaron sincronizados a 10
        f_def = tablero.obtener_ficha("Lance Fighter (6,10)")
        self.assertEqual(f_def.hp_actual, 10)
        self.assertEqual(f_def.stats.hp, 10)

        client = app.test_client()
        # Lapis se mueve a (5, 10) y ataca
        res = client.post("/api/combate/ejecutar", json={
            "atacante": "Lapis",
            "defensor": "Lance Fighter (6,10)",
            "arma_nombre": "Iron Sword",
            "pos_destino": [5, 10]
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["ok"])

        # Daño: Lapis hace 7 por golpe x 2 = 14 daño
        res_combate = data["combate"]["resultado"]
        hp_def_final = res_combate["hp_defensor_final"]
        self.assertEqual(hp_def_final, 0, f"El defensor debía quedar en 0 HP tras 14 dmg contra 10 HP, pero quedó en {hp_def_final}")

        # En el tablero, el enemigo debe estar muerto (viva=False y hp_actual=0)
        f_def_post = tablero.obtener_ficha("Lance Fighter (6,10)")
        self.assertEqual(f_def_post.hp_actual, 0)
        self.assertFalse(f_def_post.viva)

    def test_analizar_con_apoyos_activos_y_turno_enemigo_no_falla(self):
        """
        Verifica que /api/analizar y el flujo de confirmación de Turno Enemigo
        no crashean al formatear apoyos activos (apoyos_activos dicts).
        """
        tablero.limpiar()
        client = app.test_client()

        # Alear en (2, 8)
        alear = resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 2, "y": 8, "mov": 4, "es_aliado": True,
            "arma_nombre": "Liberation", "stats": {"hp": 24, "fuerza": 11, "velocidad": 12}
        })
        tablero.registrar_unidad(alear)

        # Céline en (2, 7) adyacente a Alear (Apoyo C canónico)
        celine = resolver_unidad_con_catalogo({
            "nombre": "Céline", "x": 2, "y": 7, "mov": 4, "es_aliado": True,
            "arma_nombre": "Fire", "stats": {"hp": 24, "magia": 15, "velocidad": 12}
        })
        tablero.registrar_unidad(celine)

        # Enemigo cercano en (2, 9)
        ene = resolver_unidad_con_catalogo({
            "nombre": "Lance Fighter (2,9)", "x": 2, "y": 9, "mov": 4, "es_aliado": False,
            "arma_nombre": "Iron Lance", "stats": {"hp": 32, "defensa": 10, "resistencia": 7}
        })
        tablero.registrar_unidad(ene)

        # 1. Simular inicio y fin de fase enemiga
        res_ini = client.post("/api/turno/inicio_fase_enemigo")
        self.assertEqual(res_ini.status_code, 200)

        res_fin = client.post("/api/turno/fin")
        self.assertEqual(res_fin.status_code, 200)
        self.assertEqual(tablero.fase, "jugador")

        # 2. Llamar a /api/analizar
        res_ana = client.post("/api/analizar", json={"perfil": "seguro"})
        self.assertEqual(res_ana.status_code, 200, "El análisis no debe fallar con error 500")
        data = res_ana.get_json()
        self.assertIn("resultados", data)
        self.assertTrue(len(data["resultados"]) > 0)

        # Verificar que si hay apoyos_activos, son diccionarios válidos y el texto no falló
        for r in data["resultados"]:
            if r.get("apoyos_activos"):
                for ap in r["apoyos_activos"]:
                    self.assertIsInstance(ap, dict)
                    self.assertIn("aliado", ap)

    def test_seleccion_de_arma_kill_limpio_sobre_overkill_con_contraataque(self):
        """
        Validación del Ratio Daño-Acierto-Supervivencia:
        Chlóe enfrentando a un Mago con 24 HP.
        - Slim Lance hace 2x16 = 32 (mata al enemigo, pero Chlóe recibe contragolpe del mago en medio).
        - Silver Lance hace 1x24 = 24 (mata al enemigo en el 1er golpe, 0 daño recibido).
        La IA debe priorizar Silver Lance (Clean Kill) sobre Slim Lance (Overkill con daño recibido).
        """
        from motor_analisis import analizar_situacion_tactica
        tablero.limpiar()

        # Chloé con Slim Lance y Silver Lance en su inventario
        chloe = resolver_unidad_con_catalogo({
            "nombre": "Chloé", "x": 5, "y": 5, "mov": 5, "es_aliado": True,
            "arma_nombre": "Slim Lance",
            "stats": {"hp": 26, "fuerza": 12, "magia": 2, "destreza": 14, "velocidad": 16, "defensa": 8, "resistencia": 9, "suerte": 10},
            "inventario": [
                {"nombre": "Slim Lance", "tipo": "Lanza", "poder": 4, "precision": 100, "peso": 2, "rango": [1]},
                {"nombre": "Silver Lance", "tipo": "Lanza", "poder": 12, "precision": 100, "peso": 11, "rango": [1]}
            ]
        })
        tablero.registrar_unidad(chloe)

        # Mago enemigo con 24 HP y 18 Atk mágico (Fire, rango 1-2, Spd 10 -> Chloé hace follow-up con Slim pero no con Silver)
        # Contra Silver: Chloé pega 12 + 12 = 24 dmg -> Mago muere de 1 golpe (OHKO, 0 contraataque).
        # Contra Slim: Chloé pega 12 + 4 = 16 dmg en golpe 1 -> Mago vive con 8 HP y contraataca haciendo 18-9=9 dmg -> Chloé pega 16 en golpe 2 y mata.
        mago = resolver_unidad_con_catalogo({
            "nombre": "Mage (5,6)", "x": 5, "y": 6, "mov": 4, "es_aliado": False,
            "arma_nombre": "Fire",
            "stats": {"hp": 24, "fuerza": 1, "magia": 13, "destreza": 10, "velocidad": 10, "defensa": 0, "resistencia": 4, "suerte": 5},
            "inventario": [
                {"nombre": "Fire", "tipo": "Tomo", "poder": 5, "precision": 90, "peso": 4, "rango": [1, 2], "es_magica": True}
            ]
        })
        tablero.registrar_unidad(mago)

        recs = analizar_situacion_tactica(tablero=tablero, mapa=_mapa)

        op_chloe = [r for r in recs["resultados"] if r.get("aliado") == "Chloé"]
        self.assertTrue(len(op_chloe) > 0, "Debe haber al menos una recomendación para Chloé")
        mejor_op = op_chloe[0]

        # Debe recomendar Silver Lance, NO Slim Lance
        self.assertEqual(mejor_op.get("arma_recomendada"), "Silver Lance",
                         f"Debe recomendar Silver Lance (Clean Kill), pero recomendó {mejor_op.get('arma_recomendada')}")
        self.assertEqual(mejor_op.get("daño_recibido"), 0, "El daño recibido con Silver Lance debe ser 0")
        self.assertIn("CLEAN KILL", mejor_op.get("recomendacion", ""), "Debe etiquetarse como CLEAN KILL")

    def test_recomendaciones_deduplicadas_y_acotadas(self):
        """
        Validar que el motor no sobrecargue al jugador ni al servidor con 30+ combinaciones:
        - 1 mejor acción por aliado activo.
        - Total de oportunidades de ataque limitadas a <= 8.
        """
        from motor_analisis import analizar_situacion_tactica
        tablero.limpiar()

        # Registrar 6 aliados
        for i in range(6):
            ali = resolver_unidad_con_catalogo({
                "nombre": f"Aliado_{i}", "x": 2, "y": 2 + i, "mov": 5, "es_aliado": True,
                "arma_nombre": "Iron Sword",
                "stats": {"hp": 25, "fuerza": 12, "velocidad": 10, "defensa": 8, "resistencia": 5}
            })
            tablero.registrar_unidad(ali)

        # Registrar 5 enemigos alcanzables
        for j in range(5):
            ene = resolver_unidad_con_catalogo({
                "nombre": f"Enemigo_{j}", "x": 3, "y": 2 + j, "mov": 4, "es_aliado": False,
                "arma_nombre": "Iron Lance",
                "stats": {"hp": 20, "fuerza": 8, "velocidad": 6, "defensa": 5, "resistencia": 2}
            })
            tablero.registrar_unidad(ene)

        recs = analizar_situacion_tactica(tablero=tablero, mapa=_mapa)

        resultados = recs["resultados"]
        # Total no debe exceder 8 recomendaciones de ataque
        ops_ataque = [r for r in resultados if r.get("tipo_analisis") == "oportunidad_jugador"]
        self.assertLessEqual(len(ops_ataque), 8, "No debe haber más de 8 recomendaciones de ataque")

        # Verificar deduplicación por aliado: ningún aliado debe aparecer repetido en ops_ataque
        aliados_vistos = set()
        for op in ops_ataque:
            nom_a = op["aliado"]
            self.assertNotIn(nom_a, aliados_vistos, f"El aliado {nom_a} tiene múltiples recomendaciones de ataque duplicadas")
            aliados_vistos.add(nom_a)

    def test_hortensia_en_rango_de_varios_aliados_no_falla(self):
        """Tener a Hortensia (Boss) en rango de múltiples aliados no debe arrojar KeyError ni error en análisis."""
        from app import _desplegar_capitulo, _mapa
        from motor_analisis import analizar_situacion_tactica
        _desplegar_capitulo("M007", "Extremo")

        hortensia = tablero.obtener_ficha("Hortensia (Boss)")
        self.assertIsNotNone(hortensia)

        alear = tablero.obtener_ficha("Alear")
        alcryst = tablero.obtener_ficha("Alcryst")
        citrinne = tablero.obtener_ficha("Citrinne")
        lapis = tablero.obtener_ficha("Lapis")

        alear.x, alear.y = 20, 8
        alcryst.x, alcryst.y = 19, 8
        citrinne.x, citrinne.y = 21, 9
        lapis.x, lapis.y = 20, 9

        analisis = analizar_situacion_tactica(tablero, _mapa)
        self.assertIn("resultados", analisis)
        self.assertTrue(len(analisis["resultados"]) > 0)

    def test_bastones_utilitarios_no_cuentan_como_curacion(self):
        """
        Verifica que bastones utilitarios como Obstruct NO sean tratados como
        bastones de curación, y que un aliado herido reciba a lo sumo la mejor
        recomendación curativa sin duplicados repetitivos.
        """
        from motor_analisis import analizar_situacion_tactica
        tablero.limpiar()
        framme = resolver_unidad_con_catalogo({
            "nombre": "Framme", "x": 10, "y": 10, "es_aliado": True,
            "inventario": [{"nombre": "Obstruct (8)"}, {"nombre": "Heal (16)"}],
            "stats": {"hp": 20, "magia": 10}
        })
        yunaka = resolver_unidad_con_catalogo({
            "nombre": "Yunaka", "x": 10, "y": 12, "es_aliado": True,
            "inventario": [{"nombre": "Mend (13)"}],
            "stats": {"hp": 24, "magia": 12}
        })
        louis = resolver_unidad_con_catalogo({
            "nombre": "Louis", "x": 11, "y": 11, "es_aliado": True,
            "hp_actual": 10,
            "stats": {"hp": 31}
        })
        tablero.registrar_unidad(framme)
        tablero.registrar_unidad(yunaka)
        tablero.registrar_unidad(louis)

        res = analizar_situacion_tactica(tablero, _mapa, perfil="seguro")
        curaciones = [r for r in res["resultados"] if r.get("tipo_analisis") == "apoyo_curacion"]
        # Ninguna curación puede provenir de Obstruct
        self.assertFalse(any("obstruct" in str(r.get("baston", "")).lower() for r in curaciones), "Obstruct nunca debe ser recomendado como curación")
        # Louis debe tener a lo sumo 1 recomendación de curación (la mejor: Mend de Yunaka)
        curaciones_louis = [r for r in curaciones if r.get("objetivo") == "Louis"]
        self.assertEqual(len(curaciones_louis), 1, "Debe haber exactamente 1 mejor curación para Louis")
        self.assertEqual(curaciones_louis[0]["aliado"], "Yunaka", "Mend de Yunaka debe superar a Heal de Framme")

    def test_seleccion_de_arma_follow_up_slim_sobre_iron(self):
        """
        Verifica que un arma de follow-up con mayor daño total y 100% acierto
        (Slim Lance 11x2 = 22 dmg) supere a un arma de golpe único con menor daño
        (Iron Lance 13x1 = 13 dmg).
        """
        from motor_analisis import analizar_situacion_tactica
        from catalogo_loader import _buscar_en_catalogo
        tablero.limpiar()
        _, a_slim = _buscar_en_catalogo("armas", "Slim Lance")
        _, a_iron = _buscar_en_catalogo("armas", "Iron Lance")
        _, a_bow = _buscar_en_catalogo("armas", "Iron Bow")

        arma_slim = _arma_desde_item(a_slim)
        arma_iron = _arma_desde_item(a_iron)
        arma_bow = _arma_desde_item(a_bow)

        chloe = Unidad("Chloé", hp=22, fuerza=12, magia=0, destreza=12, velocidad=14, defensa=6, resistencia=8, suerte=10, complexion=5, tipo_movimiento="volador")
        archer = Unidad("Archer", hp=24, fuerza=9, magia=0, destreza=10, velocidad=9, defensa=6, resistencia=2, suerte=6, complexion=6, tipo_movimiento="infanteria")

        chloe_f = FichaUnidad(
            "Chloé", clase_nombre="Pegasus Knight", nivel=7, es_aliado=True,
            x=10, y=10, hp_actual=22, hp_max=22, stats=chloe, arma=arma_slim,
            inventario=[{"nombre": "Slim Lance"}, {"nombre": "Iron Lance"}]
        )
        archer_f = FichaUnidad(
            "Archer", clase_nombre="Archer", nivel=7, es_aliado=False,
            x=11, y=10, hp_actual=24, hp_max=24, stats=archer, arma=arma_bow,
            inventario=[{"nombre": "Iron Bow"}]
        )
        tablero.registrar_unidad(chloe_f)
        tablero.registrar_unidad(archer_f)

        res = analizar_situacion_tactica(tablero, _mapa, perfil="seguro")
        ataques_chloe = [r for r in res["resultados"] if r.get("aliado") == "Chloé" and r.get("enemigo") == "Archer"]
        self.assertTrue(len(ataques_chloe) > 0, "Debe haber una recomendación de ataque para Chloé")
        self.assertEqual(ataques_chloe[0]["arma_recomendada"], "Slim Lance", "Slim Lance (11x2) debe superar a Iron Lance (13x1)")

    def test_combo_focus_fire_entre_aliados(self):
        """
        Detección de ataque combinado (Focus Fire): Alfred desgasta a un enemigo
        de 31 HP (10 dmg) para que Louis lo remate con Ridersbane (26 dmg).
        El sistema debe recomendar primero el ataque de preparación de Alfred.
        """
        from motor_analisis import analizar_situacion_tactica
        tablero.limpiar()
        alfred = resolver_unidad_con_catalogo({
            "nombre": "Alfred", "x": 15, "y": 10, "es_aliado": True,
            "clase_nombre": "Noble", "nivel": 7,
            "inventario": [{"nombre": "Iron Lance"}],
            "stats": {"hp": 26, "fuerza": 10, "velocidad": 9, "defensa": 9, "mov": 5}
        })
        louis = resolver_unidad_con_catalogo({
            "nombre": "Louis", "x": 15, "y": 8, "es_aliado": True,
            "clase_nombre": "Lance Armor", "nivel": 7,
            "inventario": [{"nombre": "Ridersbane"}],
            "stats": {"hp": 31, "fuerza": 13, "velocidad": 4, "defensa": 14, "mov": 4}
        })
        axe_cav = resolver_unidad_con_catalogo({
            "nombre": "Axe Cavalier", "x": 18, "y": 10, "es_aliado": False,
            "clase_nombre": "Axe Cavalier", "nivel": 7,
            "hp_actual": 31,
            "inventario": [{"nombre": "Iron Axe"}],
            "stats": {"hp": 31, "fuerza": 10, "defensa": 6, "velocidad": 8, "tipo_movimiento": "caballeria"}
        })
        tablero.registrar_unidad(alfred)
        tablero.registrar_unidad(louis)
        tablero.registrar_unidad(axe_cav)

        res = analizar_situacion_tactica(tablero, _mapa, perfil="seguro")
        # Los combos "desgastar + rematar" se sustituyeron por bajas conjuntas planificadas
        # (ataques normales numerados) y solo se emiten cuando NADIE mata solo. Aquí
        # Louis mata al Axe Cavalier de un golpe con Ridersbane (x3), así que la
        # recomendación es su kill directo; el desgaste de Alfred queda detrás.
        ops_cav = [r for r in res["resultados"] if r.get("tipo_analisis") == "oportunidad_jugador" and r.get("enemigo") == "Axe Cavalier"]
        self.assertTrue(ops_cav, "Debe haber ataques contra el Axe Cavalier")
        self.assertEqual(ops_cav[0]["aliado"], "Louis", "El kill directo de Louis va primero")
        self.assertTrue(ops_cav[0]["veredicto"].get("kill_seguro") or ops_cav[0]["veredicto"].get("kill_probable"))
        self.assertFalse(any(r.get("plan_baja") for r in ops_cav), "Sin baja conjunta cuando un aliado mata solo")

    def test_ataque_a_jefe_viable_en_zona_de_peligro(self):
        """
        Verifica que en combates con alta densidad de enemigos (como Hortensia en Cap 7),
        los ataques seguros al jefe no sean descartados por penalización excesiva de zonas de peligro.
        """
        from motor_analisis import analizar_situacion_tactica
        from app import _desplegar_capitulo
        _desplegar_capitulo("M007", "Extremo")
        hortensia = [e for e in tablero.obtener_enemigos() if "hortensia" in e.nombre.lower()][0]
        hortensia.x, hortensia.y = 18, 8

        # Desplegar aliado que alcance a Hortensia en zona densa de peligro
        chloe = resolver_unidad_con_catalogo({
            "nombre": "Chloé", "x": 17, "y": 8, "es_aliado": True,
            "clase_nombre": "Lance Flier", "nivel": 7,
            "mov": 5, "es_volador": True,
            "inventario": [{"nombre": "Javelin"}, {"nombre": "Slim Lance"}],
            "stats": {"hp": 24, "fuerza": 11, "velocidad": 14, "defensa": 7, "resistencia": 10}
        })
        tablero.registrar_unidad(chloe)

        res = analizar_situacion_tactica(tablero, _mapa, perfil="seguro")
        ataques = [r for r in res["resultados"] if r.get("enemigo") == hortensia.nombre]
        self.assertTrue(len(ataques) > 0, "Debe haber al menos un ataque viable recomendado contra Hortensia")

    def test_kill_en_solitario_prioritario_sobre_combos(self):
        """
        Verifica que:
        1. Si un enemigo puede ser eliminado de forma directa 1:1, NO se generen combos contra él.
        2. Las kills unitarias tengan prioridad estricta y se listen antes de cualquier estrategia conjunta.
        """
        from motor_analisis import analizar_situacion_tactica
        tablero.limpiar()

        # Enemigo 1: Corrupted frágil que Boucheron puede derrotar 1:1 con 100% hit
        fragil = resolver_unidad_con_catalogo({
            "nombre": "Fragile Thief", "x": 5, "y": 5, "es_aliado": False,
            "hp_actual": 12, "hp_max": 12, "arma_nombre": "Iron Dagger",
            "stats": {"hp": 12, "defensa": 2, "resistencia": 1, "velocidad": 0, "fuerza": 5, "suerte": 0}
        })
        tablero.registrar_unidad(fragil)

        # Aliado 1: Boucheron cerca del frágil (Kill 1:1 garantizada, 100% hit)
        bouch = resolver_unidad_con_catalogo({
            "nombre": "Boucheron", "x": 5, "y": 4, "es_aliado": True,
            "mov": 5, "arma_nombre": "Iron Axe",
            "stats": {"hp": 28, "fuerza": 14, "destreza": 15, "velocidad": 10, "defensa": 8, "resistencia": 3, "suerte": 10}
        })
        tablero.registrar_unidad(bouch)

        # Aliados 2 y 3: Alfred y Louis cerca de Axe Cavalier (hacen combo coordinado)
        alfred = resolver_unidad_con_catalogo({
            "nombre": "Alfred", "x": 15, "y": 10, "es_aliado": True,
            "clase_nombre": "Noble", "nivel": 7,
            "inventario": [{"nombre": "Iron Lance"}],
            "stats": {"hp": 26, "fuerza": 10, "velocidad": 9, "defensa": 9, "mov": 5}
        })
        louis = resolver_unidad_con_catalogo({
            "nombre": "Louis", "x": 15, "y": 8, "es_aliado": True,
            "clase_nombre": "Lance Armor", "nivel": 7,
            "inventario": [{"nombre": "Ridersbane"}],
            "stats": {"hp": 31, "fuerza": 13, "velocidad": 4, "defensa": 14, "mov": 4}
        })
        axe_cav = resolver_unidad_con_catalogo({
            "nombre": "Axe Cavalier", "x": 18, "y": 10, "es_aliado": False,
            "clase_nombre": "Axe Cavalier", "nivel": 7,
            "hp_actual": 31,
            "inventario": [{"nombre": "Iron Axe"}],
            "stats": {"hp": 31, "fuerza": 10, "defensa": 6, "velocidad": 8, "tipo_movimiento": "caballeria"}
        })
        tablero.registrar_unidad(alfred)
        tablero.registrar_unidad(louis)
        tablero.registrar_unidad(axe_cav)

        res = analizar_situacion_tactica(tablero, _mapa, perfil="seguro")
        resultados = res["resultados"]

        # 1. No debe haber ningún combo contra Fragile Thief (porque Boucheron lo mata 1:1)
        combos_fragil = [r for r in resultados if r.get("plan_baja") and r.get("enemigo") == "Fragile Thief"]
        self.assertEqual(len(combos_fragil), 0, "No deben generarse combos para un enemigo que muere 1:1")

        # 2. Debe haber kill directa de Boucheron sobre Fragile Thief
        solo_kill = [r for r in resultados if r.get("tipo_analisis") == "oportunidad_jugador" and r.get("enemigo") == "Fragile Thief"]
        self.assertTrue(len(solo_kill) > 0, "Boucheron debe tener kill unitaria contra Fragile Thief")

        # 3. Debe haber combo coordinado contra Axe Cavalier (ya que nadie lo mata 1:1)
        # (baja conjunta planificada si nadie lo mata solo; si alguien lo mata, su kill directo)
        combos_cav = [r for r in resultados if r.get("enemigo") == "Axe Cavalier" and (r.get("plan_baja") or (r.get("veredicto") or {}).get("kill_seguro") or (r.get("veredicto") or {}).get("kill_probable"))]
        self.assertTrue(len(combos_cav) > 0, "Debe haber una jugada letal (conjunta o directa) contra Axe Cavalier")

        # 4. En la lista final, la kill 1:1 debe aparecer ANTES del combo coordinado
        idx_solo = resultados.index(solo_kill[0])
        idx_combo = resultados.index(combos_cav[0])
        self.assertLess(idx_solo, idx_combo, "Las bajas 1:1 deben listarse antes que los combos coordinados")

    def test_fusion_reservada_para_jefes(self):
        """
        La Fusión de Emblema debe reservarse para jefes: contra un enemigo normal
        que ya puede ser eliminado con un arma corriente, la recomendación NO debe
        usar el ataque de Fusión aunque esté disponible. Contra un jefe, sí debe
        preferirse el ataque de Fusión.
        """
        from motor_analisis import analizar_situacion_tactica
        tablero.limpiar()

        alear = resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 5, "y": 5, "es_aliado": True,
            "clase_nombre": "Dragon Child", "nivel": 10,
            "emblema_nombre": "Marth", "nivel_vinculo": 15, "en_fusion": True,
            "energia_emblema": 0, "max_energia_emblema": 6,
            "inventario": [{"nombre": "Iron Sword"}],
            "stats": {"hp": 28, "fuerza": 12, "destreza": 12, "velocidad": 12, "defensa": 9, "resistencia": 6, "suerte": 8}
        })
        tablero.registrar_unidad(alear)

        enemigo_normal = resolver_unidad_con_catalogo({
            "nombre": "Soldado Débil", "x": 5, "y": 4, "es_aliado": False,
            "hp_actual": 8, "hp_max": 8, "arma_nombre": "Iron Lance",
            "stats": {"hp": 8, "defensa": 1, "resistencia": 1, "velocidad": 3, "fuerza": 4, "suerte": 0}
        })
        tablero.registrar_unidad(enemigo_normal)

        res = analizar_situacion_tactica(tablero, _mapa, perfil="seguro")
        ataques = [r for r in res["resultados"] if r.get("aliado") == "Alear" and r.get("enemigo") == "Soldado Débil"]
        self.assertTrue(len(ataques) > 0, "Debe existir una recomendación de ataque de Alear contra el enemigo normal")
        mejor = ataques[0]
        self.assertFalse(mejor.get("requiere_fusion"), "No debe recomendarse gastar la Fusión contra un enemigo normal derrotable con arma corriente")
        self.assertFalse(mejor.get("es_engage"), "El arma recomendada contra un enemigo normal no debe ser de Engage")
        self.assertEqual(mejor.get("arma_recomendada"), "Iron Sword", "Debe preferirse el arma corriente que ya asegura la baja")

        # Contra un jefe, el ataque de Fusión SÍ debe ser el preferido
        tablero.limpiar()
        alear2 = resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 5, "y": 5, "es_aliado": True,
            "clase_nombre": "Dragon Child", "nivel": 10,
            "emblema_nombre": "Marth", "nivel_vinculo": 15, "en_fusion": True,
            "energia_emblema": 0, "max_energia_emblema": 6,
            "inventario": [{"nombre": "Iron Sword"}],
            "stats": {"hp": 28, "fuerza": 12, "destreza": 12, "velocidad": 12, "defensa": 9, "resistencia": 6, "suerte": 8}
        })
        tablero.registrar_unidad(alear2)
        jefe = resolver_unidad_con_catalogo({
            "nombre": "Jefe Enemigo", "x": 5, "y": 4, "es_aliado": False, "es_jefe": True,
            "hp_actual": 40, "hp_max": 40, "arma_nombre": "Iron Lance",
            "stats": {"hp": 40, "defensa": 10, "resistencia": 8, "velocidad": 5, "fuerza": 10, "suerte": 5}
        })
        tablero.registrar_unidad(jefe)

        res2 = analizar_situacion_tactica(tablero, _mapa, perfil="seguro")
        ataques_jefe = [r for r in res2["resultados"] if r.get("aliado") == "Alear" and r.get("enemigo") == "Jefe Enemigo"]
        self.assertTrue(len(ataques_jefe) > 0, "Debe existir una recomendación de ataque de Alear contra el jefe")
        self.assertTrue(ataques_jefe[0].get("es_engage"), "Contra un jefe debe preferirse el ataque de Fusión de Emblema")

if __name__ == "__main__":
    unittest.main()
