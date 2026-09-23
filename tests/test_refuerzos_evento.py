"""
Refuerzos por evento del guion (cargador_dispos.REFUERZOS_POR_EVENTO): en el
Cap. 9 los grupos Enemy_Kagetsu_Fort / Enemy_Zelkova_Fort no están en el
despliegue inicial; aparecen cuando Kagetsu llega a (14,1) y Zelkov a (14,15)
(M009.lua: 砦到着_カゲツ / 砦到着_ゼルコバ). Se disparan al mover, sobreviven al
deshacer y a exportar/importar la partida.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import app, tablero, _desplegar_capitulo, _cargador_dispos, resolver_unidad_con_catalogo  # noqa: E402
from cargador_dispos import DISPOS_DIR  # noqa: E402


@unittest.skipUnless(os.path.isdir(DISPOS_DIR), "sin datamine (dispos)")
class TestRefuerzosPorEvento(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        self.res = _desplegar_capitulo("M009", "Extremo")
        # el tablero global puede tener otro mapa cargado: solo importan las fichas y los eventos
        self.kagetsu = next(f for f in tablero.fichas.values() if getattr(f, "pid", "") == "PID_M009_カゲツ")

    def test_grupos_de_fuerte_no_estan_en_el_despliegue_inicial(self):
        nombres = set(tablero.fichas)
        self.assertNotIn("Sword Fighter (14,0)", nombres)
        self.assertNotIn("Thief (14,14)", nombres)
        eventos = tablero.refuerzos_por_evento_previstos()
        self.assertEqual({e["grupo"] for e in eventos}, {"Enemy_Kagetsu_Fort", "Enemy_Zelkova_Fort"})
        self.assertEqual(len(self.res["refuerzos_por_evento"]), 2)

    def test_se_disparan_al_llegar_la_unidad_y_solo_una_vez(self):
        tablero.fase = "enemigo"
        tablero.guardar_snapshot()
        tablero.mover_unidad(self.kagetsu.nombre, 14, 1)
        nombres = {f.nombre for f in tablero.fichas.values()}
        self.assertIn("Sword Fighter (14,0)", nombres)
        self.assertIn("Sword Fighter (14,2)", nombres)
        self.assertNotIn("Thief (14,14)", nombres)              # el evento de Zelkov sigue armado
        self.assertEqual([f["nombre"] for f in tablero.refuerzos_desplegados_ultimo], ["Sword Fighter (14,0)", "Sword Fighter (14,2)"])
        self.assertEqual([e["grupo"] for e in tablero.refuerzos_por_evento_previstos()], ["Enemy_Zelkova_Fort"])
        # salir y volver a entrar no los duplica
        tablero.mover_unidad(self.kagetsu.nombre, 15, 1)
        tablero.mover_unidad(self.kagetsu.nombre, 14, 1)
        self.assertEqual(sum(1 for n in tablero.fichas if n.startswith("Sword Fighter (14,0)")), 1)

    def test_deshacer_rearma_el_evento(self):
        tablero.fase = "enemigo"
        tablero.guardar_snapshot()
        tablero.mover_unidad(self.kagetsu.nombre, 14, 1)
        self.assertIn("Sword Fighter (14,0)", tablero.fichas)
        tablero.deshacer()
        self.assertNotIn("Sword Fighter (14,0)", tablero.fichas)
        self.assertIn("Enemy_Kagetsu_Fort", [e["grupo"] for e in tablero.refuerzos_por_evento_previstos()])

    def test_api_mover_devuelve_los_refuerzos(self):
        # El endpoint valida el alcance sobre el mapa activo: cargar el del Cap. 9 y restaurar después
        import app as _app
        cap_previo = _app._capitulo_actual
        self.assertEqual(self.client.post("/api/mapa/seleccionar", json={"capitulo": 9}).status_code, 200)
        try:
            _desplegar_capitulo("M009", "Extremo")
            kagetsu = next(f for f in tablero.fichas.values() if getattr(f, "pid", "") == "PID_M009_カゲツ")
            tablero.fase = "enemigo"
            tablero.mover_unidad(kagetsu.nombre, 15, 1)   # acercarlo: falta un paso hasta el fuerte
            r = self.client.post("/api/mover", json={"nombre": kagetsu.nombre, "x": 14, "y": 1})
            self.assertEqual(r.status_code, 200, r.get_json())
            self.assertEqual([f["nombre"] for f in r.get_json()["refuerzos_desplegados"]], ["Sword Fighter (14,0)", "Sword Fighter (14,2)"])
        finally:
            self.client.post("/api/mapa/seleccionar", json={"capitulo": cap_previo})

    def test_exportar_importar_conserva_el_estado_del_evento(self):
        tablero.fase = "enemigo"
        tablero.mover_unidad(self.kagetsu.nombre, 14, 1)
        exp = self.client.get("/api/partida/exportar").get_json()["partida"]
        self.assertEqual(sorted(e["grupo"] for e in exp["refuerzos_por_evento"] if e["disparado"]), ["Enemy_Kagetsu_Fort"])
        imp = self.client.post("/api/partida/importar", json={"partida": exp})
        self.assertEqual(imp.status_code, 200)
        self.assertEqual([e["grupo"] for e in tablero.refuerzos_por_evento_previstos()], ["Enemy_Zelkova_Fort"])
        self.assertIn("Sword Fighter (14,0)", tablero.fichas)

    def test_extremo_arma_a_los_refuerzos_como_en_el_juego(self):
        # Visto en juego (Extremo): Steel Sword + Armorslayer en los Sword Fighter, Kard + Stiletto en los Thief
        armas = {u["nombre"]: u["inventario"][0]["nombre"] for e in tablero.refuerzos_por_evento for u in e["unidades"]}
        self.assertEqual(armas, {"Sword Fighter (14,0)": "Steel Sword", "Sword Fighter (14,2)": "Armorslayer",
                                 "Thief (14,14)": "Kard", "Thief (14,16)": "Stiletto"})

    def test_importar_recupera_la_dificultad_y_regenera_eventos_obsoletos(self):
        # la regeneración lee el capítulo activo del servidor: asegurar que es el 9
        import app as _app
        cap_previo = _app._capitulo_actual
        self.client.post("/api/mapa/seleccionar", json={"capitulo": 9})
        self.addCleanup(lambda: self.client.post("/api/mapa/seleccionar", json={"capitulo": cap_previo}))
        _desplegar_capitulo("M009", "Extremo")
        exp = self.client.get("/api/partida/exportar").get_json()["partida"]
        self.assertEqual(exp["dificultad"], "Extremo")
        self.assertTrue(all(f["dificultad"] == "Extremo" for f in exp["fichas"] if not f["es_aliado"]))
        # Partida antigua: sin dificultad y con los eventos generados en Hard (servidor reiniciado)
        exp.pop("dificultad")
        exp["refuerzos_por_evento"] = _cargador_dispos.refuerzos_por_evento("M009", "Hard", mapa_ancho=24, mapa_alto=17)
        tablero.dificultad = "Hard"
        imp = self.client.post("/api/partida/importar", json={"partida": exp})
        self.assertEqual(imp.status_code, 200, imp.get_json())
        self.assertEqual(tablero.dificultad, "Extremo")   # inferida de las fichas
        armas = {u["nombre"]: u["inventario"][0]["nombre"] for e in tablero.refuerzos_por_evento for u in e["unidades"]}
        self.assertEqual(armas["Sword Fighter (14,2)"], "Armorslayer")
        self.assertTrue(all(u["dificultad"] == "Extremo" for e in tablero.refuerzos_por_evento for u in e["unidades"]))


@unittest.skipUnless(os.path.isdir(DISPOS_DIR), "sin datamine (dispos)")
class TestRefuerzosPorCombateYMuerte(unittest.TestCase):
    """M010: el guion despliega al ENTRAR EN COMBATE con Hortensia
    (condition_オルテンシア行動変化: g_flag_battle_holtencia) y al CAER Morion
    (condition_増援: muerte o conversación de combate)."""

    def setUp(self):
        self.client = app.test_client()
        self.client.post("/api/mapa/seleccionar", json={"capitulo": 10})
        _desplegar_capitulo("M010", "Extremo")
        tablero.fase = "jugador"

    @classmethod
    def tearDownClass(cls):
        app.test_client().post("/api/mapa/seleccionar", json={"capitulo": 7})

    def _por_pid(self, pid):
        return next(f for f in tablero.fichas.values() if getattr(f, "pid", "") == pid)

    def test_eventos_del_capitulo_10(self):
        eventos = {e["grupo"]: e for e in tablero.refuerzos_por_evento_previstos()}
        self.assertEqual(sorted(eventos), ["Enemy_Reinforcement1", "Enemy_Reinforcement2",
                                           "Enemy_Reinforcement3", "Enemy_Reinforcement4"])
        # Los arqueros salen cuando Hortensia HACE algo (atacar, bastón o recibir un
        # ataque), no por turno: verificado en juego que en el turno 6 no aparecen. Atacar
        # o curar pasa en fase enemiga, así que hay un disparo "accion" que marca el jugador.
        self.assertEqual([(d["tipo"], d.get("pid") or d.get("turno")) for d in eventos["Enemy_Reinforcement1"]["disparos"]],
                         [("accion", "PID_M010_オルテンシア"), ("combate", "PID_M010_オルテンシア")])
        # Los jinetes sí tienen dos condiciones (vale la primera que ocurra)
        self.assertEqual([(d["tipo"], d.get("pid") or d.get("objeto_tipo")) for d in eventos["Enemy_Reinforcement3"]["disparos"]],
                         [("muerte", "PID_M010_異形兵_モリオン"), ("objeto", "puerta")])
        # Aparecen donde dice el datamine: arqueros en la fila de Hortensia, jinetes en las escaleras de Hyacinth
        self.assertEqual([(u["x"], u["y"]) for u in eventos["Enemy_Reinforcement1"]["unidades"]], [(1, 18)])
        self.assertEqual([(u["x"], u["y"]) for u in eventos["Enemy_Reinforcement2"]["unidades"]], [(15, 18)])
        self.assertEqual([(u["x"], u["y"]) for u in eventos["Enemy_Reinforcement3"]["unidades"]], [(3, 4)])
        self.assertEqual([(u["x"], u["y"]) for u in eventos["Enemy_Reinforcement4"]["unidades"]], [(13, 4)])
        # ninguno está en el despliegue inicial
        nombres = set(tablero.fichas)
        for e in eventos.values():
            for u in e["unidades"]:
                self.assertNotIn(u["nombre"], nombres)

    def test_morion_cae_y_llegan_los_pegasos(self):
        morion = self._por_pid("PID_M010_異形兵_モリオン")
        vivos = len([f for f in tablero.fichas.values() if f.viva])
        r = self.client.post("/api/muerte", json={"nombre": morion.nombre}).get_json()
        self.assertEqual(len(r["refuerzos_desplegados"]), 2, r)
        self.assertEqual(len([f for f in tablero.fichas.values() if f.viva]), vivos - 1 + 2)
        restantes = [e["grupo"] for e in tablero.refuerzos_por_evento_previstos()]
        self.assertEqual(sorted(restantes), ["Enemy_Reinforcement1", "Enemy_Reinforcement2"])
        # no se repiten
        self.assertEqual(tablero.disparar_refuerzos_por_evento("muerte", morion), [])

    def test_bajar_el_hp_a_cero_a_mano_tambien_dispara(self):
        morion = self._por_pid("PID_M010_異形兵_モリオン")
        r = self.client.post("/api/unidad/ajustar_hp", json={"nombre": morion.nombre, "hp_actual": 0}).get_json()
        self.assertEqual(len(r["refuerzos_desplegados"]), 2, r)

    def test_combatir_con_hortensia_despliega_a_los_arqueros(self):
        hortensia = self._por_pid("PID_M010_オルテンシア")
        libre = next((c for c in ((hortensia.x, hortensia.y + 1), (hortensia.x + 1, hortensia.y), (hortensia.x - 1, hortensia.y))
                      if not any(f.viva and (f.x, f.y) == c for f in tablero.fichas.values())), None)
        self.assertIsNotNone(libre, "no hay casilla libre junto a Hortensia")
        aliado = resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": libre[0], "y": libre[1], "es_aliado": True,
            "clase_nombre": "Dragon Child", "nivel": 10, "inventario": [{"nombre": "Iron Sword"}],
            "stats": {"hp": 30, "fuerza": 12, "destreza": 12, "velocidad": 12, "defensa": 9, "resistencia": 6, "suerte": 8}})
        tablero.registrar_unidad(aliado)
        r = self.client.post("/api/combate/ejecutar", json={
            "atacante": "Alear", "defensor": hortensia.nombre, "arma_nombre": "Iron Sword"})
        self.assertEqual(r.status_code, 200, r.get_json())
        restantes = [e["grupo"] for e in tablero.refuerzos_por_evento_previstos()]
        self.assertEqual(sorted(restantes), ["Enemy_Reinforcement3", "Enemy_Reinforcement4"])
        self.assertEqual({f["nombre"] for f in r.get_json()["refuerzos_desplegados"]},
                         {"Archer (1,18)", "Archer (15,18)"})

    def test_el_jugador_registra_que_hortensia_ha_actuado(self):
        """Atacar o usar el bastón Freeze pasa en la fase enemiga y la herramienta no lo
        ve: el jugador lo marca desde el modal de la unidad."""
        eventos = tablero.eventos_por_accion()
        self.assertEqual([(e["nombre"], e["disparado"]) for e in eventos], [("Hortensia", False)])
        self.assertTrue(tablero.tiene_evento_por_accion("Hortensia"))
        r = self.client.post("/api/unidad/registrar_accion", json={"nombre": "Hortensia"})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(len(r.get_json()["refuerzos_desplegados"]), 2)
        # El botón se queda (en gris): el evento sigue listado, ya disparado
        self.assertEqual([(e["nombre"], e["disparado"]) for e in tablero.eventos_por_accion()],
                         [("Hortensia", True)])
        self.assertFalse(tablero.tiene_evento_por_accion("Hortensia"))
        # Una segunda vez ya no hace nada, y otras unidades no tienen el botón
        self.assertEqual(self.client.post("/api/unidad/registrar_accion", json={"nombre": "Hortensia"}).status_code, 400)
        self.assertEqual(self.client.post("/api/unidad/registrar_accion", json={"nombre": "Hyacinth"}).status_code, 400)

    def test_el_estado_del_tablero_dice_a_quien_ponerle_el_boton(self):
        """La UI lo saca de una lista del estado, no de un campo por ficha: así la ficha
        no necesita una referencia al tablero (que rompía el deepcopy de la Cronogema)."""
        estado = self.client.get("/api/estado").get_json()
        self.assertEqual([e["nombre"] for e in estado["eventos_por_accion"]], ["Hortensia"])
        self.assertFalse(estado["eventos_por_accion"][0]["disparado"])
        self.assertNotIn("evento_por_accion", estado["fichas"][0])
        self.client.post("/api/unidad/registrar_accion", json={"nombre": "Hortensia"})
        estado2 = self.client.get("/api/estado").get_json()
        self.assertTrue(estado2["eventos_por_accion"][0]["disparado"])

    def test_una_partida_empezada_se_pone_al_dia_con_los_disparadores_nuevos(self):
        """Los disparadores se guardan en la partida al cargar el capítulo. Si se corrige
        una condición después, una partida ya empezada se quedaría con la antigua: al pedir
        el estado se resincronizan, sin tocar el tablero ni lo que ya se disparó."""
        for ev in tablero.refuerzos_por_evento:
            if ev["grupo"] in ("Enemy_Reinforcement1", "Enemy_Reinforcement2"):
                ev["disparos"] = [{"tipo": "combate", "pid": "PID_M010_オルテンシア"},
                                  {"tipo": "turno", "turno": 6}]
        self.assertEqual(tablero.eventos_por_accion(), [], "partida vieja: sin disparo por acción")
        fichas_antes = set(tablero.fichas)

        estado = self.client.get("/api/estado").get_json()

        self.assertEqual([e["nombre"] for e in estado["eventos_por_accion"]], ["Hortensia"])
        self.assertEqual(set(tablero.fichas), fichas_antes, "resincronizar no despliega nada")
        disparos = next(e for e in tablero.refuerzos_por_evento
                        if e["grupo"] == "Enemy_Reinforcement1")["disparos"]
        self.assertEqual([d["tipo"] for d in disparos], ["accion", "combate"])

    def test_resincronizar_respeta_lo_ya_disparado(self):
        self.client.post("/api/unidad/registrar_accion", json={"nombre": "Hortensia"})
        n_fichas = len(tablero.fichas)
        self.client.get("/api/estado")
        self.assertEqual(len(tablero.fichas), n_fichas, "no se vuelven a desplegar")
        self.assertTrue(all(e["disparado"] for e in tablero.eventos_por_accion()))

    def test_la_apertura_recoloca_a_hortensia_y_hyacinth(self):
        """配置調整 del .lua: Hortensia baja al vestíbulo de los pozos y Hyacinth sube al trono."""
        self.assertEqual((self._por_pid("PID_M010_オルテンシア").x, self._por_pid("PID_M010_オルテンシア").y), (8, 18))
        self.assertEqual((self._por_pid("PID_M010_ハイアシンス").x, self._por_pid("PID_M010_ハイアシンス").y), (8, 0))

    def test_derribar_la_puerta_saca_a_los_jinetes_de_las_escaleras(self):
        puerta = next(o for o in tablero.objetos_como_lista() if o["propiedades"].get("tipo") == "puerta")
        r = self.client.post("/api/mapa/objeto/danar", json={"id": puerta["id"], "vida": 0}).get_json()
        nombres = {f["nombre"] for f in r["refuerzos_desplegados"]}
        self.assertEqual(nombres, {"Sword Flier (3,4)", "Axe Flier (13,4)"})
        self.assertEqual(sorted(e["grupo"] for e in tablero.refuerzos_por_evento_previstos()),
                         ["Enemy_Reinforcement1", "Enemy_Reinforcement2"])

    def test_los_arqueros_no_llegan_solos_por_pasar_los_turnos(self):
        """Verdad de juego: llegado el turno 6 sin combatir con Hortensia, los arqueros
        siguen sin aparecer — su único disparador es el combate con ella."""
        tablero.fase = "enemigo"
        for _ in range(6):
            tablero.avanzar_turno()
            tablero.fase = "enemigo"
        self.assertEqual(tablero.turno_actual, 7)
        self.assertEqual({f["nombre"] for f in tablero.refuerzos_desplegados_ultimo}, set())
        self.assertIn("Enemy_Reinforcement1", [e["grupo"] for e in tablero.refuerzos_por_evento_previstos()])

    def test_un_refuerzo_con_la_casilla_ocupada_aparece_al_lado(self):
        # (1,18) y (15,18) están ocupadas en el despliegue inicial: el refuerzo se coloca al lado
        ocupadas_antes = {(f.x, f.y) for f in tablero.fichas.values() if f.viva}
        self.assertIn((1, 18), ocupadas_antes)
        desplegados = tablero.disparar_refuerzos_por_evento("combate", self._por_pid("PID_M010_オルテンシア"))
        self.assertEqual(len(desplegados), 2, desplegados)
        for f in desplegados:
            self.assertNotIn((f["x"], f["y"]), ocupadas_antes)
            self.assertLessEqual(min(abs(f["x"] - 1) + abs(f["y"] - 18), abs(f["x"] - 15) + abs(f["y"] - 18)), 3)

    def test_el_grupo_thief_llega_en_el_turno_2_salvo_en_extremo(self):
        from cargador_dispos import CargadorDisposEngage
        c = CargadorDisposEngage()
        cal_extremo = c.calendario_refuerzos("M010", "Extremo", mapa_ancho=17, mapa_alto=30)
        cal_dificil = c.calendario_refuerzos("M010", "Hard", mapa_ancho=17, mapa_alto=30)
        self.assertEqual(cal_extremo, {}, "en Extremo el guion NO saca al ladrón")
        self.assertEqual(sorted(cal_dificil), [2])
        self.assertEqual([u["clase_nombre"] for u in cal_dificil[2]], ["Thief"])


if __name__ == "__main__":
    unittest.main()
