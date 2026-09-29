"""
Cap. 11 (Retreat): Corrupted Wyrm de 2x2, el evento de la fila 23 y los anillos oscuros.

  - Los Corrupted Wyrm ocupan 2x2 (Person.xml BmapSize=2), anclados en la esquina inferior
    izquierda (la casilla del dispos + la de su derecha + las dos de encima). Verificado
    en juego con una captura del mapa.
  - Son de movimiento dragón (Job.xml MoveType 4): el bosque no les frena.
  - Atacan con Fire Breath (1-3) o Fireball (4): la zona de peligro cuenta las dos.
  - Al llegar una unidad del jugador a la fila 23 aparecen Ivy/Kagetsu/Zelkov, los Cuatro
    Sabuesos con sus anillos y cuatro Corrupted por el sur (observado en juego).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import app, tablero, _desplegar_capitulo, resolver_unidad_con_catalogo  # noqa: E402
from cargador_dispos import DISPOS_DIR  # noqa: E402
from lector_de_mapas import Terreno  # noqa: E402
from motor_calculo import casillas_de_unidad, casillas_ocupadas_por, distancia_entre_unidades, distancia_a_unidad  # noqa: E402
from motor_de_movimiento_y_amenaza import AnalizadorAmenaza, ArmaMock, UnidadMock  # noqa: E402
from motor_analisis import rangos_de_ataque, peligro_de_enemigo  # noqa: E402

WYRM = "Corrupted Wyrm (7,5)"


@unittest.skipUnless(os.path.isdir(DISPOS_DIR), "sin datamine (dispos)")
class TestCapitulo11(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()
        cls.client.post("/api/mapa/seleccionar", json={"capitulo": 11})

    @classmethod
    def tearDownClass(cls):
        app.test_client().post("/api/mapa/seleccionar", json={"capitulo": 7})

    def setUp(self):
        _desplegar_capitulo("M011", "Extremo")

    def _ficha(self, nombre):
        return tablero.obtener_ficha(nombre)

    # ── Wyrms 2x2 ──────────────────────────────────────────────────────────

    def test_los_wyrms_ocupan_2x2_desde_la_esquina_inferior_izquierda(self):
        w = self._ficha(WYRM)
        self.assertEqual(w.tamano, 2)
        self.assertEqual(set(casillas_de_unidad(w)), {(7, 5), (8, 5), (7, 4), (8, 4)})
        self.assertEqual(set(casillas_de_unidad(self._ficha("Corrupted Wyrm (10,4)"))),
                         {(10, 4), (11, 4), (10, 3), (11, 3)})
        self.assertIn((8, 4), casillas_ocupadas_por(f for f in tablero.fichas.values() if f.viva))

    def test_no_se_puede_mover_a_ninguna_de_sus_casillas(self):
        r = self.client.post("/api/mover", json={"nombre": "Alear", "x": 8, "y": 4})
        self.assertEqual(r.status_code, 400)
        self.assertIn(WYRM, r.get_json()["error"])

    def test_distancias_a_su_casilla_mas_cercana(self):
        w = self._ficha(WYRM)
        self.assertEqual(distancia_a_unidad(w, 9, 4), 1, "a la derecha de su casilla (8,4)")
        self.assertEqual(distancia_a_unidad(w, 7, 3), 1, "encima de (7,4)")
        self.assertEqual(distancia_a_unidad(w, 9, 3), 2)
        self.assertEqual(distancia_entre_unidades(w, self._ficha("Corrupted Wyrm (10,4)")), 2)

    def test_la_zona_cuenta_fire_breath_y_fireball(self):
        w = self._ficha(WYRM)
        self.assertEqual(w.arma.nombre, "Fire Breath")
        self.assertEqual(rangos_de_ataque(w), [1, 2, 3, 4])
        alear = self._ficha("Alear")
        self.assertIsNotNone(peligro_de_enemigo(w, alear)["daño"])

    def test_su_movimiento_ilumina_todo_lo_que_cubre(self):
        """Se mueve como una unidad normal (Mov 2), pero su avance cubre 2 filas y 2
        columnas: se ilumina todo lo que puede cubrir su cuerpo, como en el juego."""
        r = self.client.get("/api/unidad/rango_movimiento", query_string={"nombre": WYRM}).get_json()
        cubre = {tuple(c) for c in r["casillas"]}
        self.assertTrue({(7, 5), (8, 5), (7, 4), (8, 4)} <= cubre, "su sitio actual")
        self.assertIn((7, 3), cubre, "subiendo 1 cubre la fila 3")
        self.assertIn((7, 7), cubre, "bajando 2 cubre la fila 7")
        self.assertNotIn((7, 8), cubre, "la fila 8 ya queda a 3")
        otros = casillas_ocupadas_por(f for f in tablero.fichas.values() if f.viva and f.nombre != WYRM)
        self.assertFalse(otros & cubre, "no ilumina casillas de otras unidades")

    def test_soltarlo_en_cualquier_casilla_de_su_area(self):
        """(8,7) no puede ser su esquina, pero la cubre bajando 2: acaba con la esquina en (7,7)."""
        from app import tablero as t
        t.fase = "enemigo"
        r = self.client.post("/api/mover", json={"nombre": WYRM, "x": 8, "y": 7})
        self.assertEqual(r.status_code, 200, r.get_json())
        w = self._ficha(WYRM)
        self.assertEqual((w.x, w.y), (7, 7))
        self.assertIn((8, 7), casillas_de_unidad(w))
        self.assertEqual(self.client.post("/api/mover", json={"nombre": WYRM, "x": 8, "y": 11}).status_code, 400)

    # ── Evento de la fila 23 ──────────────────────────────────────────────

    def test_ivy_los_sabuesos_y_el_sur_esperan_al_evento(self):
        nombres = set(tablero.fichas)
        for n in ("Ivy", "Kagetsu", "Zelkov", "Zephia", "Griss", "Mauvier", "Marni"):
            self.assertNotIn(n, nombres)
        self.assertEqual(len([e for e in tablero.refuerzos_por_evento if not e.get("disparado")]), 4)

    def test_llegar_a_la_fila_23_los_trae(self):
        alear = self._ficha("Alear")
        alear.x, alear.y = 10, 22
        self.assertEqual(tablero.comprobar_refuerzos_por_evento(), [], "la fila 22 aún no")
        alear.y = 23
        nuevos = {f["nombre"]: f for f in tablero.comprobar_refuerzos_por_evento()}
        for n in ("Ivy", "Kagetsu", "Zelkov", "Zephia", "Griss", "Mauvier", "Marni"):
            self.assertIn(n, nuevos)
        for n in ("Ivy", "Kagetsu", "Zelkov"):   # se unen como aliados azules normales
            self.assertTrue(nuevos[n]["es_aliado"] and nuevos[n]["controlable"], n)
            self.assertFalse(nuevos[n]["es_verde"] or nuevos[n]["es_fijo"] or nuevos[n]["union_pendiente"], n)
        self.assertEqual(nuevos["Ivy"]["emblema_nombre"], "Lyn", "Ivy llega con Lyn")
        self.assertEqual({n: nuevos[n]["emblema_nombre"] for n in ("Zephia", "Griss", "Mauvier", "Marni")},
                         {"Zephia": "Marth (Oscuro)", "Griss": "Celica (Oscuro)",
                          "Mauvier": "Micaiah (Oscuro)", "Marni": "Sigurd (Oscuro)"})
        self.assertEqual(len(nuevos), 7 + 4, "más los cuatro Corrupted del sur")

    def test_solo_lo_dispara_alear(self):
        otro = self._ficha("Aliado 2")
        otro.x, otro.y = 10, 24
        self.assertEqual(tablero.comprobar_refuerzos_por_evento(), [])

    def test_ivy_kagetsu_y_zelkov_salen_junto_a_alear(self):
        """En el juego salen algo al azar según por dónde cruce Alear: se ponen en las libres
        más cercanas a él y el jugador los ajusta en su modal."""
        alear = self._ficha("Alear")
        alear.x, alear.y = 4, 24
        tablero.comprobar_refuerzos_por_evento()
        for n in ("Ivy", "Kagetsu", "Zelkov"):
            self.assertLessEqual(distancia_entre_unidades(alear, self._ficha(n)), 4, n)

    def test_los_sabuesos_se_llevan_los_anillos(self):
        """El Corrupted que tenía el anillo lo pierde: sin sus armas, sus habilidades ni
        sus bonos, pero conservando su casilla y el daño que llevaba."""
        flier = self._ficha("Sword Flier (2,12)")
        self.assertEqual((flier.arma.nombre, flier.stats.velocidad), ("Rapier", 20))
        flier.x, flier.y = 3, 13
        flier.hp_actual -= 10
        alear = self._ficha("Alear")
        alear.y = 23
        tablero.comprobar_refuerzos_por_evento()
        flier = self._ficha("Sword Flier (2,12)")
        self.assertEqual(flier.emblema_id, "")
        self.assertEqual((flier.x, flier.y), (3, 13))
        self.assertEqual(flier.arma.nombre, "Steel Sword")
        self.assertEqual(flier.stats.velocidad, 17, "sin los +3 de Vel del anillo")
        self.assertNotIn("Divine Speed", flier.habilidades)
        self.assertEqual(flier.hp_actual, flier.hp_max - 10)
        portadores = {f.nombre: f.emblema_nombre for f in tablero.fichas.values()
                      if f.viva and not f.es_aliado and f.emblema_nombre}
        self.assertEqual(portadores, {
            "Zephia": "Marth (Oscuro)", "Griss": "Celica (Oscuro)", "Mauvier": "Micaiah (Oscuro)",
            "Marni": "Sigurd (Oscuro)",
            # Roy y Leif no los reclama ningún Sabueso: siguen donde estaban
            "Axe Fighter (10,14)": "Roy (Oscuro)", "Lance Fighter (6,18)": "Leif (Oscuro)"})

    def test_la_partida_guardada_conserva_el_evento(self):
        exp = self.client.get("/api/partida/exportar").get_json()["partida"]
        self.assertEqual(self.client.post("/api/partida/importar", json={"partida": exp}).status_code, 200)
        self.assertEqual(len([e for e in tablero.refuerzos_por_evento if e.get("sin_emblema")]), 1)
        self._ficha("Alear").y = 23
        tablero.comprobar_refuerzos_por_evento()
        self.assertEqual(self._ficha("Sword Flier (2,12)").emblema_id, "")

    # ── Anillos oscuros ────────────────────────────────────────────────────

    def test_los_seis_anillos_iniciales(self):
        portadores = {f.nombre: f.emblema_nombre for f in tablero.fichas.values()
                      if f.viva and not f.es_aliado and f.emblema_nombre}
        self.assertEqual(portadores, {
            "Axe Cavalier (6,1)": "Sigurd (Oscuro)", "Martial Monk (8,2)": "Micaiah (Oscuro)",
            "Sword Flier (2,12)": "Marth (Oscuro)", "Axe Fighter (10,14)": "Roy (Oscuro)",
            "Lance Fighter (6,18)": "Leif (Oscuro)", "Mage (8,22)": "Celica (Oscuro)"})

    def test_axe_fighter_con_roy_como_en_el_juego(self):
        """Ficha del juego (Extremo, captura del Cap. 11): Corrupted & Roy, Axe Fighter Nv 16
        (13 + los 3 de Sink Below, EnhanceLevel 3 de Skill.xml). HP 51, Fue 21, Mag 2,
        Des 11, Vel 10 (13 menos 3 por el peso de la Steel Axe: 12 − Com 9, así lo enseña
        el juego), Def 14, Res 5, Sue 2, Com 9. Habilidades: solo Hold Out+ y Sink Below."""
        f = self._ficha("Axe Fighter (10,14)")
        s = f.stats
        self.assertEqual((f.hp_max, s.fuerza, s.magia, s.destreza, s.velocidad, s.defensa, s.resistencia,
                          s.suerte, s.complexion), (51, 21, 2, 11, 13, 14, 5, 2, 9))
        self.assertEqual(f.habilidades, ["Hold Out+", "Sink Below"])

    def test_de_una_misma_familia_solo_cuenta_la_mejor(self):
        """Una partida guardada con Hold Out y Hold Out+ a la vez: se queda Hold Out+."""
        d = self._ficha("Axe Fighter (10,14)").como_dict()
        d["habilidades"] = ["Hold Out", "Hold Out+", "Sink Below"]
        f = resolver_unidad_con_catalogo(d)
        self.assertEqual(f.habilidades, ["Hold Out+", "Sink Below"])
        self.assertNotIn("SID_踏ん張り", f.habilidades_sids)

    def test_el_fuego_se_come_el_agua_para_siempre(self):
        """Visto en el juego (Dark Inferno sobre el agua fija): el fuego sustituye al agua y,
        cuando se apaga, la casilla queda como llanura. Se guarda en la partida (sobrevive a
        exportar/importar y a otro efecto encima); Groundswell no la devuelve; el Preset sí."""
        c = (4, 28)
        grid = tablero.mapa.grid
        self.assertEqual(grid[c[0]][c[1]].superpuesto, "agua")
        tablero.aplicar_terreno_temporal([c], "fuego")
        self.assertEqual((grid[c[0]][c[1]].nombre, grid[c[0]][c[1]].avo), ("llanura + Fuego", 0))
        tablero.turno_actual += 1
        tablero.caducar_terrenos_temporales()
        t = grid[c[0]][c[1]]
        self.assertEqual((t.nombre, t.avo, t.coste_mov, t.superpuesto), ("llanura", 0, 1, ""))
        # exportar / importar
        exp = self.client.get("/api/partida/exportar").get_json()["partida"]
        self.client.post("/api/partida/importar", json={"partida": exp})
        self.assertEqual(tablero.mapa.grid[c[0]][c[1]].nombre, "llanura")
        # otro efecto encima y otra vez fuera: sigue sin agua
        tablero.aplicar_terreno_temporal([c], "niebla")
        tablero.turno_actual += 1
        tablero.caducar_terrenos_temporales()
        self.assertEqual(tablero.mapa.grid[c[0]][c[1]].nombre, "llanura")
        self.assertEqual(tablero.terrenos_temporales_lista(),
                         [{"x": 4, "y": 28, "tipo": "sin_capa", "expira_turno": 10 ** 9}])
        # un Preset empieza con el mapa tal cual: el agua vuelve
        _desplegar_capitulo("M011", "Extremo")
        self.assertEqual(tablero.mapa.grid[c[0]][c[1]].nombre, "agua")
        self.assertEqual(tablero.terrenos_temporales, {})

    def test_dark_inferno_prende_el_bosque_y_el_agua(self):
        """La partida del usuario: Chloé con Camilla en (12,16) y el área base alrededor.
        El juego enseña "Woods + Flames" en el bosque y el fuego sobre el agua fija; antes
        solo ardían las casillas de llano."""
        from types import SimpleNamespace
        from ataques_area import resolver_ataque_area, es_terreno_llano, _terreno_natural
        grid = tablero.mapa.grid
        chloe = SimpleNamespace(es_aliado=True, estilo_combate="飛行スタイル")
        area = resolver_ataque_area("Dark Inferno (Steel Axe)", (12, 16), self._ficha("Axe Fighter (10,14)"),
                                    chloe, tablero, tablero.mapa)
        self.assertTrue(area["valido"], area["motivo"])
        self.assertEqual(grid[14][18].nombre, "foso")
        self.assertEqual(sorted(area["casillas_fuego"]), sorted(c for c in area["casillas_dano"] if c != (14, 18)),
                         "arden las doce casillas del área menos el foso")
        tablero.encender_fuego(area["casillas_fuego"])
        self.addCleanup(lambda: (tablero.terrenos_temporales.clear(), tablero.sincronizar_terrenos_temporales()))
        self.assertEqual((grid[12][14].nombre, grid[12][14].avo, grid[12][14].coste_mov), ("evasion + Fuego", 30, 3))
        # el agua fija también arde (la sustituye); da igual que ya tenga otro efecto encima
        self.assertEqual(grid[12][15].superpuesto, "agua")
        self.assertTrue(es_terreno_llano(_terreno_natural(tablero.mapa, 12, 15)))
        tablero.aplicar_terreno_temporal([(12, 15)], "pilares")
        self.assertTrue(es_terreno_llano(_terreno_natural(tablero.mapa, 12, 15)))

    def test_poner_un_anillo_a_mano_usa_el_del_capitulo(self):
        """"Marth (Oscuro)" existe en los Cap. 11, 17, 21 y 24: se elige el del mapa activo."""
        f = resolver_unidad_con_catalogo({
            "nombre": "Portador", "es_aliado": False, "x": 3, "y": 3, "clase_nombre": "Sword Fighter",
            "nivel": 14, "emblema_nombre": "Marth (Oscuro)"}, tablero=tablero)
        self.assertEqual(f.emblema_id, "GID_M011_敵マルス")
        self.assertTrue(f.emblema_oscuro)


class TestMovimientoDeDragonY2x2(unittest.TestCase):
    """El analizador con un grid sintético: bosque (coste 2) y un muro."""

    def _grid(self, ancho=8, alto=8, muros=()):
        grid = [[Terreno(nombre="evasion", avo=30, coste_mov=2) for _ in range(alto)] for _ in range(ancho)]
        for (x, y) in muros:
            grid[x][y] = Terreno(nombre="muro", caminable=False, volable=False)
        return grid

    def test_el_bosque_no_frena_al_dragon(self):
        an = AnalizadorAmenaza(self._grid(), 8, 8)
        a_pie = an.calcular_casillas_alcanzables(UnidadMock(4, 4, 2, False, ArmaMock([1])))
        dragon = an.calcular_casillas_alcanzables(UnidadMock(4, 4, 2, False, ArmaMock([1]), es_dragon=True))
        self.assertNotIn((4, 2), a_pie)
        self.assertIn((4, 2), dragon)

    def test_la_huella_2x2_tiene_que_caber(self):
        """Un muro en (6,4) impide que el Wyrm de (4,4) se desplace a la derecha."""
        an = AnalizadorAmenaza(self._grid(muros=[(6, 4)]), 8, 8)
        wyrm = UnidadMock(4, 4, 1, False, ArmaMock([1]), tamano=2, es_dragon=True)
        self.assertNotIn((5, 4), an.calcular_anclas_alcanzables(wyrm))
        self.assertIn((3, 4), an.calcular_anclas_alcanzables(wyrm))
        cubre = an.calcular_casillas_alcanzables(wyrm)
        self.assertIn((3, 3), cubre, "la huella movida a la izquierda cubre (3,3)")
        self.assertNotIn((6, 4), cubre)


if __name__ == "__main__":
    unittest.main()
