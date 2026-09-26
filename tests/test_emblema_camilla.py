# -*- coding: utf-8 -*-
"""
Emblema Camilla (DLC). Datos de https://serenesforest.net/engage/emblems/camilla/ y stats
de las armas verificadas en juego por el jugador (Mt, Hit, Crit, Wt, Avo, Ddg, Rango):

    Bolt Axe:       14, 65, 0,  9, -20, 0, 1-2   (mágica)
    Lightning:       3, 75, 0, 10,   0, 0, 1-2   (mágica)
    Camilla's Axe:  19, 80, 0, 11,   0, 0, 1

Pendiente (a la espera del jugador): la geometría de Dragon Vein y de Dark Inferno, y los
números reales del miasma, que Terrain.xml guarda en campos que el catálogo no extrae.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import catalogo_loader as cl                                                  # noqa: E402
import pasivas                                                               # noqa: E402
from ataques_area import (AREA_DARK_INFERNO, GLOW_DARK_INFERNO,               # noqa: E402
                          TERRENOS_TEMPORALES, VENAS_DRAGON,
                          casillas_de_infierno_oscuro, casillas_de_vena,
                          efecto_de_terreno_temporal, rango_de_ataque_area)
from lector_de_mapas import Terreno as TerrenoMapa, defensa_de_terreno       # noqa: E402
from motor_analisis import _armas_aliado                                     # noqa: E402
from motor_calculo import CalculadoraEngage, Terreno                         # noqa: E402
from app import app, tablero, _mapa                                          # noqa: E402

STATS = {"hp": 50, "fuerza": 30, "magia": 20, "destreza": 20, "velocidad": 15,
         "defensa": 18, "resistencia": 10, "suerte": 10, "complexion": 10}


def _camilla(clase="Warrior", vinculo=20, fusion=True, **extra):
    datos = {"nombre": "Cam", "es_aliado": True, "nivel": 15, "clase_nombre": clase,
             "emblema_nombre": "Camilla", "nivel_vinculo": vinculo, "en_fusion": fusion,
             "stats": dict(STATS), "inventario": [{"nombre": "Steel Axe", "equipada": True}],
             "x": 0, "y": 0}
    datos.update(extra)
    return cl.resolver_unidad_con_catalogo(datos, tablero=None)


def _rival(defensa=15, resistencia=15, **extra):
    datos = {"nombre": "Rival", "es_aliado": False, "nivel": 12, "clase_nombre": "General",
             "stats": {"hp": 60, "fuerza": 16, "magia": 0, "destreza": 10, "velocidad": 5,
                       "defensa": defensa, "resistencia": resistencia, "suerte": 5, "complexion": 12},
             "inventario": [{"nombre": "Steel Lance", "equipada": True}], "x": 1, "y": 0}
    datos.update(extra)
    return cl.resolver_unidad_con_catalogo(datos, tablero=None)


def _armas(unidad):
    return {a.nombre: a for a, _, _ in _armas_aliado(unidad)}


class TestArmas(unittest.TestCase):

    def test_stats_de_las_tres_armas(self):
        armas = _armas(_camilla())
        bolt = armas["Bolt Axe (Emblema)"]
        self.assertEqual((bolt.mt, bolt.hit, bolt.crit, bolt.wt, bolt.avo_bonus, bolt.rango),
                         (14, 65, 0, 9, -20, [1, 2]))
        luz = armas["Lightning (Emblema)"]
        self.assertEqual((luz.mt, luz.hit, luz.crit, luz.wt, luz.rango), (3, 75, 0, 10, [1, 2]))
        hacha = armas["Camilla's Axe (Emblema)"]
        self.assertEqual((hacha.mt, hacha.hit, hacha.crit, hacha.wt, hacha.rango), (19, 80, 0, 11, [1]))

    def test_bolt_axe_y_lightning_son_magicas(self):
        armas = _armas(_camilla())
        self.assertTrue(armas["Bolt Axe (Emblema)"].es_magica, "es un hacha, pero pega contra Res")
        self.assertTrue(armas["Lightning (Emblema)"].es_magica)
        self.assertFalse(armas["Camilla's Axe (Emblema)"].es_magica)

    def test_bolt_axe_pega_contra_resistencia(self):
        """Mismo rival con Def y Res intercambiadas: el hacha mágica mira la Res."""
        cam = _camilla()
        bolt = _armas(cam)["Bolt Axe (Emblema)"]
        blando = CalculadoraEngage.simular_combate(
            cam.stats, _rival(defensa=30, resistencia=5).stats, bolt, None,
            Terreno(), Terreno(), 1)["atacante"]["daño_por_golpe"]
        duro = CalculadoraEngage.simular_combate(
            cam.stats, _rival(defensa=5, resistencia=30).stats, bolt, None,
            Terreno(), Terreno(), 1)["atacante"]["daño_por_golpe"]
        self.assertGreater(blando, duro)

    def test_lightning_ataca_dos_veces_al_iniciar(self):
        """Brave: cada ataque son dos golpes. Camilla dobla al rival, así que pega 4 veces
        con Lightning y 2 con un arma normal del mismo alcance."""
        cam = _camilla()
        armas = _armas(cam)
        self.assertTrue(armas["Lightning (Emblema)"].es_brave)
        self.assertFalse(armas["Bolt Axe (Emblema)"].es_brave)

        def golpes(arma):
            r = CalculadoraEngage.simular_combate(cam.stats, _rival().stats, arma, None,
                                                  Terreno(), Terreno(), 1)["resultado"]
            return len([x for x in r["secuencia"] if x["actor"] == "Cam"])

        self.assertEqual(golpes(armas["Bolt Axe (Emblema)"]), 2)
        self.assertEqual(golpes(armas["Lightning (Emblema)"]), 4)

    def test_camilla_axe_suma_la_diferencia_res_menos_def(self):
        cam = _camilla()
        hacha = _armas(cam)["Camilla's Axe (Emblema)"]

        def daño(defensa, resistencia):
            return CalculadoraEngage.simular_combate(
                cam.stats, _rival(defensa=defensa, resistencia=resistencia).stats, hacha, None,
                Terreno(), Terreno(), 1)["atacante"]["daño_por_golpe"]

        self.assertEqual(daño(10, 25) - daño(10, 10), 15, "+15 si la Res supera a la Def en 15")
        self.assertEqual(daño(10, 15) - daño(10, 10), 5)
        # Con más Def que Res no resta nada: el extra se queda en 0
        self.assertEqual(daño(25, 5), daño(25, 15))
        self.assertEqual(daño(25, 5), daño(25, 25))

    def test_camilla_axe_da_res_10(self):
        """Equipada aguanta mejor la magia: +10 de Resistencia."""
        cam = _camilla()
        armas = _armas(cam)
        mago = cl.resolver_unidad_con_catalogo({
            "nombre": "Mago", "es_aliado": False, "nivel": 15, "clase_nombre": "Sage",
            "stats": {"hp": 40, "fuerza": 5, "magia": 40, "destreza": 15, "velocidad": 10,
                      "defensa": 5, "resistencia": 10, "suerte": 5, "complexion": 5},
            "inventario": [{"nombre": "Elfire", "equipada": True}], "x": 1, "y": 0}, tablero=None)
        daños = {}
        for nombre in ("Steel Axe", "Camilla's Axe (Emblema)"):
            r = CalculadoraEngage.simular_combate(
                mago.stats, cam.stats, mago.arma, armas[nombre], Terreno(), Terreno(), 1)
            daños[nombre] = r["atacante"]["daño_por_golpe"]
        self.assertEqual(daños["Steel Axe"] - daños["Camilla's Axe (Emblema)"], 10)

    def test_las_armas_se_desbloquean_por_vinculo(self):
        self.assertIn("Bolt Axe (Emblema)", _armas(_camilla(vinculo=1)),
                      "el Bolt Axe entra ya a vínculo 1")
        self.assertNotIn("Lightning (Emblema)", _armas(_camilla(vinculo=9)))
        self.assertIn("Lightning (Emblema)", _armas(_camilla(vinculo=10)))
        self.assertNotIn("Camilla's Axe (Emblema)", _armas(_camilla(vinculo=14)))
        self.assertIn("Camilla's Axe (Emblema)", _armas(_camilla(vinculo=15)))


class TestSincronias(unittest.TestCase):

    def test_se_desbloquean_por_nivel_de_vinculo(self):
        def pasivas_de(vinculo):
            return list(getattr(_camilla(vinculo=vinculo, fusion=False).stats, "habilidades", []) or [])

        self.assertIn("Dragon Vein", pasivas_de(1))
        self.assertNotIn("Decisive Strike", pasivas_de(3))
        self.assertIn("Decisive Strike", pasivas_de(4))
        self.assertIn("Detoxify", pasivas_de(8))
        self.assertIn("Groundswell", pasivas_de(12))
        self.assertIn("Decisive Strike+", pasivas_de(18))
        self.assertNotIn("Decisive Strike", pasivas_de(18))

    def test_dragon_vein_es_la_del_datamine(self):
        """SID_竜脈 está en Skill.xml con variante para los ocho estilos: no se inventa."""
        sid = pasivas.resolver_nombre_a_sid("Dragon Vein")
        self.assertEqual(sid, "SID_竜脈")
        variantes = (pasivas.HABILIDADES[sid].get("variantes_estilo") or {})
        self.assertEqual(set(variantes), set(VENAS_DRAGON))

    def test_los_bonos_de_vinculo_se_aplican(self):
        """+7 HP / +5 Vel / +4 Res a vínculo 20, sobre stats calculadas por la herramienta."""
        def stats(**kw):
            return cl.resolver_unidad_con_catalogo(
                {"nombre": "U", "es_aliado": True, "nivel": 15, "clase_nombre": "Paladin",
                 "inventario": [{"nombre": "Steel Axe", "equipada": True}], **kw}, tablero=None).stats

        sin = stats()
        con = stats(emblema_nombre="Camilla", nivel_vinculo=20)
        self.assertEqual(con.hp_max - sin.hp_max, 7)
        self.assertEqual(con.velocidad - sin.velocidad, 5)
        self.assertEqual(con.resistencia - sin.resistencia, 4)


class TestSoar(unittest.TestCase):
    """Habilidad de Fusión: "Grants Mov+2. Unit can cross terrain as if flying.
    [Cavalry] extra Mov+2. [Flying] extra Mov+1"."""

    def _mov(self, clase, fusion):
        return _camilla(clase=clase, fusion=fusion).stats.mov

    def test_bono_de_movimiento_por_estilo(self):
        for clase, extra in (("Warrior", 2), ("Paladin", 4), ("Wyvern Knight", 3),
                             ("Sage", 2), ("General", 2)):
            self.assertEqual(self._mov(clase, True) - self._mov(clase, False), extra, clase)

    def test_solo_en_fusion(self):
        cam = _camilla(clase="Paladin", fusion=False)
        self.assertNotIn("Soar", getattr(cam.stats, "habilidades", []) or [])
        self.assertEqual(pasivas.bono_movimiento_fusion(cam), 0)

    def test_cruza_el_terreno_como_si_volara(self):
        self.assertTrue(pasivas.cruza_terreno_como_volador(_camilla(fusion=True)))
        self.assertFalse(pasivas.cruza_terreno_como_volador(_camilla(fusion=False)))


class TestVenasDeDragon(unittest.TestCase):
    """Los efectos de suelo salen de Terrain.xml, no de números escritos a mano."""

    def test_cada_estilo_tiene_su_vena(self):
        self.assertEqual(VENAS_DRAGON["apoyo"], "pilares")
        self.assertEqual(VENAS_DRAGON["mistico"], "fuego")
        self.assertIsNone(VENAS_DRAGON["dragon"], "[Dragon] elige cualquiera")
        for estilo, vena in VENAS_DRAGON.items():
            if vena is not None:
                self.assertIn(vena, TERRENOS_TEMPORALES, estilo)

    def test_efectos_leidos_del_catalogo(self):
        self.assertEqual(efecto_de_terreno_temporal("pilares")["dfn"], 3)
        self.assertEqual(efecto_de_terreno_temporal("agua")["avo"], -30)
        self.assertEqual(efecto_de_terreno_temporal("pista_hielo")["avo"], -30)
        self.assertEqual(efecto_de_terreno_temporal("brillo")["curacion_turno"], 10)
        self.assertTrue(efecto_de_terreno_temporal("enredaderas")["es_antirruptura"])
        self.assertEqual(efecto_de_terreno_temporal("fuego")["coste_extra"], 1)
        self.assertEqual(efecto_de_terreno_temporal("fuego")["curacion_turno"], 0,
                         "el daño del fuego lo aplica el tablero, no la curación del terreno")


class TestVenasEnElTablero(unittest.TestCase):

    def setUp(self):
        tablero.limpiar()
        tablero.turno_actual = 1
        tablero.fase = "jugador"
        tablero.terrenos_temporales = {}
        tablero.sincronizar_terrenos_temporales()

    def tearDown(self):
        tablero.terrenos_temporales = {}
        tablero.sincronizar_terrenos_temporales()

    def test_los_pilares_dan_defensa_y_caducan(self):
        c = (4, 4)
        base = _mapa.grid[c[0]][c[1]].dfn
        tablero.aplicar_terreno_temporal([c], "pilares")
        self.assertEqual(_mapa.grid[c[0]][c[1]].dfn, base + 3)
        self.assertEqual(_mapa.grid[c[0]][c[1]].nombre, "Pilares")
        tablero.turno_actual += 1
        tablero.caducar_terrenos_temporales()
        self.assertEqual(_mapa.grid[c[0]][c[1]].dfn, base)

    def test_las_enredaderas_dan_inmunidad_a_ruptura(self):
        c = (5, 5)
        tablero.aplicar_terreno_temporal([c], "enredaderas")
        self.assertTrue(_mapa.grid[5][5].es_antirruptura)
        tablero.turno_actual += 1
        tablero.caducar_terrenos_temporales()
        self.assertFalse(_mapa.grid[5][5].es_antirruptura)

    def test_el_brillo_cura_al_empezar_la_fase_encima(self):
        c = (6, 6)
        base = _mapa.grid[c[0]][c[1]].curacion_turno   # la casilla puede curar ya de por sí
        cam = _camilla(fusion=False)
        cam.x, cam.y = c
        cam.sincronizar_hp(cam.hp_max - 30)
        tablero.registrar_unidad(cam, resolver_colision=False)
        self.assertEqual(tablero.curar_unidades_en_terreno(es_aliado=True),
                         [("Cam", base)] if base else [])
        tablero.aplicar_terreno_temporal([c], "brillo")
        self.assertEqual(tablero.curar_unidades_en_terreno(es_aliado=True), [("Cam", base + 10)])


class TestDetoxifyYGroundswell(unittest.TestCase):

    def setUp(self):
        tablero.limpiar()
        tablero.turno_actual = 1
        tablero.fase = "jugador"
        tablero.terrenos_temporales = {}
        tablero.sincronizar_terrenos_temporales()
        self.cam = _camilla(vinculo=20, fusion=False)
        self.cam.x, self.cam.y = 4, 4
        tablero.registrar_unidad(self.cam, resolver_colision=False)

    def tearDown(self):
        tablero.terrenos_temporales = {}
        tablero.sincronizar_terrenos_temporales()

    def test_detoxify_cura_el_veneno_al_empezar_su_fase(self):
        tablero.ajustar_nivel_veneno("Cam", 3)
        tablero.fase = "enemigo"
        tablero.avanzar_turno()
        self.assertEqual(tablero.obtener_ficha("Cam").nivel_veneno, 0)
        self.assertEqual(tablero.venenos_curados_ultimo, [("Cam", 3)])

    def test_sin_detoxify_el_veneno_sigue(self):
        tablero.limpiar()
        otra = _camilla(vinculo=1, fusion=False)
        otra.x, otra.y = 4, 4
        tablero.registrar_unidad(otra, resolver_colision=False)
        tablero.ajustar_nivel_veneno("Cam", 2)
        tablero.avanzar_turno()
        self.assertEqual(tablero.obtener_ficha("Cam").nivel_veneno, 2)

    def test_groundswell_limpia_el_terreno_dañino_y_cura_10(self):
        self.cam.sincronizar_hp(self.cam.hp_max - 25)
        tablero.aplicar_terreno_temporal([(4, 4)], "fuego")
        r = tablero.aplicar_groundswell("Cam")
        self.assertEqual((r["terreno"], r["curacion"]), ("fuego", 10))
        self.assertEqual(tablero.terrenos_temporales, {})

    def test_absorbe_cualquier_terreno_temporal(self):
        """Verificado en juego: se lleva también los buenos, no solo fuego y miasma."""
        for tipo in TERRENOS_TEMPORALES:
            tablero.terrenos_temporales = {}
            self.cam.sincronizar_hp(self.cam.hp_max - 25)
            tablero.aplicar_terreno_temporal([(4, 4)], tipo)
            r = tablero.aplicar_groundswell("Cam")
            self.assertIsNotNone(r, tipo)
            self.assertEqual((r["terreno"], r["curacion"]), (tipo, 10), tipo)
            self.assertEqual(tablero.terrenos_temporales, {}, tipo)

    def test_sin_terreno_temporal_no_hace_nada(self):
        self.assertIsNone(tablero.aplicar_groundswell("Cam"))

    def test_no_cura_por_encima_del_maximo(self):
        tablero.aplicar_terreno_temporal([(4, 4)], "fuego")
        self.assertEqual(tablero.aplicar_groundswell("Cam")["curacion"], 0, "estaba a tope")


class TestAtaqueDeEmblema(unittest.TestCase):
    """Infierno Oscuro: área fija centrada en la unidad y obligado a llevar hacha."""

    def test_pega_con_el_hacha_equipada(self):
        """"Estás obligado a usar un hacha": no tiene arma propia, usa una de las tuyas."""
        armas = _armas(_camilla())
        variantes = [n for n in armas if n.startswith("Dark Inferno")]
        self.assertTrue(variantes, "debería ofrecer Infierno Oscuro")
        self.assertNotIn("Darkness", armas, "era un nombre provisional")
        for n in variantes:
            self.assertEqual(armas[n].tipo, "Hacha", n)
            self.assertEqual(armas[n].hit, 100, "los Ataques de Emblema no fallan")
        self.assertEqual(armas["Dark Inferno (Steel Axe)"].mt, armas["Steel Axe"].mt)

    def test_mistico_multiplica_el_dano_por_1_2(self):
        """
        Ground truth: Céline (Mística) con Camilla le quita 28 a un Lance Armor con el
        Bolt Axe (x2 porque dobla) y exactamente 33 con Infierno Oscuro, que no dobla.
        floor(28 x 1.2) = 33. Las stats están reconstruidas para dar ese 28 de partida.
        """
        armadura = cl.resolver_unidad_con_catalogo({
            "nombre": "Lance Armor", "es_aliado": False, "nivel": 10, "clase_nombre": "Lance Armor",
            "stats": {"hp": 40, "fuerza": 14, "magia": 0, "destreza": 8, "velocidad": 4,
                      "defensa": 16, "resistencia": 6, "suerte": 4, "complexion": 12},
            "inventario": [{"nombre": "Steel Lance", "equipada": True}], "x": 1, "y": 0}, tablero=None)

        def golpe(clase, arma):
            celine = _camilla(clase=clase, vinculo=20, fusion=True, nombre="Celine",
                              stats={"hp": 40, "fuerza": 20, "magia": 20, "destreza": 18,
                                     "velocidad": 20, "defensa": 12, "resistencia": 18,
                                     "suerte": 10, "complexion": 6})
            r = CalculadoraEngage.simular_combate(
                celine.stats, armadura.stats, _armas(celine)[arma], armadura.arma,
                Terreno(), Terreno(), 1)["atacante"]
            return r["daño_por_golpe"], r["golpes_en_ronda"]

        self.assertEqual(golpe("Sage", "Bolt Axe (Emblema)"), (28, 2), "dobla por velocidad")
        self.assertEqual(golpe("Sage", "Dark Inferno (Bolt Axe (Emblema))"), (33, 1),
                         "+20% truncado y sin doblar")
        self.assertEqual(golpe("Warrior", "Dark Inferno (Bolt Axe (Emblema))"), (28, 1),
                         "sin el bono si no es Mística")

    def test_no_ofrece_variante_con_tomo(self):
        armas = _armas(_camilla())
        self.assertNotIn("Dark Inferno (Lightning (Emblema))", armas)


# ── Geometrías (boceto del jugador) ─────────────────────────────────────────
# Se dibujan como rejillas con la unidad en el centro: '#' es casilla cubierta,
# 'o' luz curativa, '*' la unidad. Así el test se lee igual que el boceto.

RADIO_CLARO = 5


def _allanar(centro):
    """Deja llano el entorno de `centro` y devuelve el terreno original, para que lo que
    se mida sea la geometría y no qué casillas del capítulo son transitables."""
    original = {}
    for dx in range(-RADIO_CLARO, RADIO_CLARO + 1):
        for dy in range(-RADIO_CLARO, RADIO_CLARO + 1):
            x, y = centro[0] + dx, centro[1] + dy
            if 0 <= x < _mapa.ancho and 0 <= y < _mapa.alto:
                original[(x, y)] = _mapa.grid[x][y]
                _mapa.grid[x][y] = TerrenoMapa()
    return original


def _restaurar(original):
    for (x, y), t in original.items():
        _mapa.grid[x][y] = t


def _pintar(centro, casillas, radio, luz=()):
    casillas, luz = set(casillas), set(luz)
    filas = []
    for dy in range(-radio, radio + 1):
        fila = ""
        for dx in range(-radio, radio + 1):
            c = (centro[0] + dx, centro[1] + dy)
            fila += "*" if (dx, dy) == (0, 0) else ("o" if c in luz else ("#" if c in casillas else "."))
        filas.append(fila)
    return filas


class TestGeometriaDeLasVenas(unittest.TestCase):
    """La estrella del boceto es el portador; la vena apunta hacia donde se lanza."""

    ESPERADO = {
        # Stone, Smoke, Vines: un 3x3 delante
        "pilares": ["...........",
                    "...........",
                    "....###....",
                    "....###....",
                    "....###....",
                    ".....*.....",
                    "...........",
                    "...........",
                    "...........",
                    "...........",
                    "..........."],
        # Frost: solo la fila de delante
        "pista_hielo": ["...........",
                        "...........",
                        "...........",
                        "...........",
                        "....###....",
                        ".....*.....",
                        "...........",
                        "...........",
                        "...........",
                        "...........",
                        "..........."],
        # Flame, Water: rombo alrededor del portador, sin apuntar a ningún lado
        "fuego": ["...........",
                  "...........",
                  "...........",
                  ".....#.....",
                  "....###....",
                  "...##*##...",
                  "....###....",
                  ".....#.....",
                  "...........",
                  "...........",
                  "..........."],
        # Succor: abanico hacia delante, cubriendo la casilla del portador
        "brillo": ["...........",
                   "...........",
                   "...#####...",
                   "....###....",
                   ".....#.....",
                   ".....*.....",
                   "...........",
                   "...........",
                   "...........",
                   "...........",
                   "..........."],
    }

    def setUp(self):
        self.centro = (_mapa.ancho // 2, _mapa.alto // 2)
        self.addCleanup(_restaurar, _allanar(self.centro))

    def test_cada_vena_dibuja_su_area(self):
        for vena, esperado in self.ESPERADO.items():
            casillas = casillas_de_vena(vena, self.centro, (0, -1), _mapa)
            self.assertEqual(_pintar(self.centro, casillas, 5), esperado, vena)

    def test_las_que_comparten_forma_la_comparten_de_verdad(self):
        def forma(v):
            return sorted(casillas_de_vena(v, self.centro, (0, -1), _mapa))
        self.assertEqual(forma("pilares"), forma("miasma"))
        self.assertEqual(forma("pilares"), forma("enredaderas"))
        self.assertEqual(forma("fuego"), forma("agua"))

    def test_flame_y_water_no_apuntan_a_ningun_lado(self):
        """Rodean al portador: sale lo mismo se lance hacia donde se lance."""
        formas = {d: sorted(casillas_de_vena("fuego", self.centro, d, _mapa))
                  for d in ((0, -1), (0, 1), (1, 0), (-1, 0))}
        primera = formas[(0, -1)]
        for d, forma in formas.items():
            self.assertEqual(forma, primera, d)
        self.assertEqual(len(primera), 13)

    def test_el_area_gira_con_la_direccion(self):
        cx, cy = self.centro
        for d, esquina in (((0, -1), (cx - 1, cy - 3)), ((0, 1), (cx + 1, cy + 3)),
                           ((1, 0), (cx + 3, cy + 1)), ((-1, 0), (cx - 3, cy - 1))):
            casillas = casillas_de_vena("pilares", self.centro, d, _mapa)
            self.assertEqual(len(casillas), 9, d)
            self.assertIn(esquina, casillas, d)

    def test_succor_cubre_al_portador_y_las_demas_no(self):
        for vena in ("brillo", "fuego", "agua"):
            self.assertIn(self.centro, casillas_de_vena(vena, self.centro, (0, -1), _mapa), vena)
        for vena in ("pilares", "miasma", "enredaderas", "pista_hielo"):
            self.assertNotIn(self.centro, casillas_de_vena(vena, self.centro, (0, -1), _mapa), vena)


class TestGeometriaDeInfiernoOscuro(unittest.TestCase):

    BASE = ["#.#.#",
            ".#.#.",
            "#.*.#",
            ".#.#.",
            "#.#.#"]
    DRAGON = ["#.#.#",
              ".###.",
              "##*##",
              ".###.",
              "#.#.#"]
    QI_ADEPT = ["#.#.#",
                ".#o#.",
                "#o*o#",
                ".#o#.",
                "#.#.#"]

    def setUp(self):
        self.centro = (_mapa.ancho // 2, _mapa.alto // 2)
        self.addCleanup(_restaurar, _allanar(self.centro))

    def _dibujo(self, estilo):
        fuego, luz = casillas_de_infierno_oscuro(self.centro, estilo, _mapa)
        return _pintar(self.centro, fuego, 2, luz)

    def test_area_base(self):
        self.assertEqual(self._dibujo("volador"), self.BASE)
        self.assertEqual(len(AREA_DARK_INFERNO["base"]), 12)

    def test_el_estilo_dragon_amplia_el_area(self):
        self.assertEqual(self._dibujo("dragon"), self.DRAGON)
        self.assertEqual(len(AREA_DARK_INFERNO["dragon"]), 16)
        self.assertTrue(set(AREA_DARK_INFERNO["base"]) < set(AREA_DARK_INFERNO["dragon"]))

    def test_qi_adept_deja_luz_en_las_adyacentes(self):
        self.assertEqual(self._dibujo("qi_adept"), self.QI_ADEPT)
        self.assertEqual(sorted(GLOW_DARK_INFERNO), [(-1, 0), (0, -1), (0, 1), (1, 0)])

    def test_nunca_cubre_la_casilla_de_la_propia_unidad(self):
        for estilo in ("volador", "dragon", "qi_adept"):
            fuego, _ = casillas_de_infierno_oscuro(self.centro, estilo, _mapa)
            self.assertNotIn(self.centro, fuego, estilo)

    def test_alcanza_mas_alla_del_adyacente(self):
        """Por eso no se ofrece solo a rango 1 como Override."""
        self.assertEqual(rango_de_ataque_area("Dark Inferno (Steel Axe)"), [1, 2, 4])
        self.assertEqual(rango_de_ataque_area("Override (Iron Lance)"), [1])


class TestComandoVenaDeDragon(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()

    def setUp(self):
        tablero.limpiar()
        tablero.turno_actual = 1
        tablero.fase = "jugador"
        tablero.terrenos_temporales = {}
        tablero.sincronizar_terrenos_temporales()
        self.centro = (_mapa.ancho // 2, _mapa.alto // 2)
        self.addCleanup(_restaurar, _allanar(self.centro))

    def tearDown(self):
        tablero.terrenos_temporales = {}
        tablero.sincronizar_terrenos_temporales()

    def _poner(self, clase, vinculo=20):
        u = _camilla(clase=clase, vinculo=vinculo, fusion=False)
        u.x, u.y = self.centro
        tablero.registrar_unidad(u, resolver_colision=False)
        return u

    def _lanzar(self, **cuerpo):
        return self.client.post("/api/unidad/vena_dragon",
                                json={"nombre": "Cam", "direccion": [0, -1], **cuerpo})

    def test_cada_estilo_crea_la_vena_que_le_toca(self):
        for clase, vena in (("Warrior", "pilares"), ("Paladin", "agua"), ("Thief", "miasma"),
                            ("General", "enredaderas"), ("Wyvern Knight", "brillo"),
                            ("Sage", "fuego"), ("Martial Master", "pista_hielo")):
            tablero.limpiar()
            tablero.terrenos_temporales = {}
            self._poner(clase)
            r = self._lanzar().get_json()
            self.assertTrue(r.get("ok"), (clase, r))
            self.assertEqual(r["vena"]["vena"], vena, clase)
            self.assertEqual(sorted(tablero.casillas_de_tipo(vena)),
                             sorted(tuple(c) for c in r["vena"]["casillas"]))

    def test_gasta_la_accion(self):
        self._poner("Warrior")
        self.assertTrue(self._lanzar().get_json()["ok"])
        self.assertTrue(tablero.obtener_ficha("Cam").ha_actuado)

    def test_solo_el_estilo_dragon_elige_vena(self):
        self._poner("Warrior")
        self.assertEqual(self._lanzar(vena="fuego").status_code, 400)
        tablero.limpiar()
        self._poner("Divine Dragon")
        r = self._lanzar(vena="fuego").get_json()
        self.assertEqual(r["vena"]["vena"], "fuego")

    def test_sin_la_habilidad_no_puede(self):
        otra = cl.resolver_unidad_con_catalogo({
            "nombre": "Cam", "es_aliado": True, "nivel": 15, "clase_nombre": "Warrior",
            "stats": dict(STATS), "inventario": [{"nombre": "Steel Axe", "equipada": True}],
            "x": self.centro[0], "y": self.centro[1]}, tablero=None)
        tablero.registrar_unidad(otra, resolver_colision=False)
        self.assertEqual(self._lanzar().status_code, 400)

    def test_la_direccion_tiene_que_ser_ortogonal(self):
        self._poner("Warrior")
        self.assertEqual(self._lanzar(direccion=[1, 1]).status_code, 400)


class TestHieloDeslizante(unittest.TestCase):
    """
    [Qi Adept] +2 de movimiento a quien esté sobre el hielo y todavía no se haya movido.
    No hace falta haber empezado la fase encima: si Alear crea la vena debajo de un
    aliado que aún no ha actuado, ese aliado ya la aprovecha. Vale para los dos bandos.
    """

    def setUp(self):
        tablero.limpiar()
        tablero.turno_actual = 1
        tablero.fase = "jugador"
        tablero.terrenos_temporales = {}
        tablero.sincronizar_terrenos_temporales()
        self.u = _camilla(clase="Warrior", fusion=False)
        self.u.x, self.u.y = 4, 4
        tablero.registrar_unidad(self.u, resolver_colision=False)

    def tearDown(self):
        tablero.terrenos_temporales = {}
        tablero.sincronizar_terrenos_temporales()

    def test_crearlo_debajo_de_un_aliado_ya_le_sirve(self):
        base = self.u.movimiento_disponible
        tablero.aplicar_terreno_temporal([(4, 4)], "pista_hielo")
        self.assertEqual(self.u.movimiento_disponible, base + 2)
        self.assertEqual(tablero.hielo_deslizante_ultimo, [("Cam", 2)])

    def test_tambien_a_los_enemigos(self):
        enemigo = _rival()
        enemigo.x, enemigo.y = 6, 6
        tablero.registrar_unidad(enemigo, resolver_colision=False)
        base = enemigo.movimiento_disponible
        tablero.aplicar_terreno_temporal([(6, 6)], "pista_hielo")
        self.assertEqual(enemigo.movimiento_disponible, base + 2,
                         "el efecto no distingue bando aunque no compense usarlo así")

    def test_se_pierde_al_salir_de_la_casilla(self):
        tablero.aplicar_terreno_temporal([(4, 4)], "pista_hielo", turnos=5)
        base = int(self.u.mov)
        self.assertEqual(self.u.movimiento_disponible, base + 2)
        tablero.mover_unidad("Cam", 5, 4)
        self.assertEqual(self.u.movimiento_disponible, base)

    def test_se_pierde_cuando_el_hielo_se_desvanece(self):
        tablero.aplicar_terreno_temporal([(4, 4)], "pista_hielo")
        base = int(self.u.mov)
        self.assertEqual(self.u.movimiento_disponible, base + 2)
        tablero.turno_actual += 1
        tablero.caducar_terrenos_temporales()
        self.assertEqual(self.u.movimiento_disponible, base)

    def test_el_bono_se_pierde_al_turno_siguiente(self):
        tablero.aplicar_terreno_temporal([(4, 4)], "pista_hielo", turnos=5)
        tablero.fase = "enemigo"
        tablero.avanzar_turno()
        base = int(self.u.mov)
        self.assertEqual(self.u.movimiento_disponible, base + 2)
        tablero.mover_unidad("Cam", 5, 4)      # se baja del hielo
        tablero.fase = "enemigo"
        tablero.avanzar_turno()
        self.assertEqual(self.u.movimiento_disponible, base)

    def test_congelada_manda_sobre_el_bono(self):
        tablero.aplicar_terreno_temporal([(4, 4)], "pista_hielo")
        tablero.fase = "enemigo"
        tablero.avanzar_turno()
        tablero.congelar(["Cam"])
        self.assertEqual(self.u.movimiento_disponible, 0)


class TestInfiernoOscuroEnPartida(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()

    def setUp(self):
        tablero.limpiar()
        tablero.turno_actual = 1
        tablero.fase = "jugador"
        tablero.terrenos_temporales = {}
        tablero.sincronizar_terrenos_temporales()
        self.centro = (_mapa.ancho // 2, _mapa.alto // 2)
        self.addCleanup(_restaurar, _allanar(self.centro))

    def tearDown(self):
        tablero.terrenos_temporales = {}
        tablero.sincronizar_terrenos_temporales()

    def _montar(self, clase):
        cx, cy = self.centro
        cam = _camilla(clase=clase, vinculo=20, fusion=True)
        cam.x, cam.y = cx, cy
        tablero.registrar_unidad(cam, resolver_colision=False)
        for nombre, (dx, dy) in (("Cerca", (1, 1)), ("Lejos", (2, 0)), ("Fuera", (3, 3))):
            e = _rival()
            e.nombre, e.x, e.y = nombre, cx + dx, cy + dy
            e.sincronizar_hp(e.hp_max)
            tablero.registrar_unidad(e, resolver_colision=False)
        return cam

    def _atacar(self, objetivo="Cerca"):
        return self.client.post("/api/combate/ejecutar", json={
            "atacante": "Cam", "defensor": objetivo, "arma_nombre": "Dark Inferno (Steel Axe)",
            "es_engage_attack": True, "engage_attack_nombre": "Dark Inferno"}).get_json()

    def test_golpea_a_todo_el_area_y_prende_fuego(self):
        self._montar("Warrior")
        r = self._atacar()
        self.assertTrue(r.get("ok"), r)
        self.assertEqual([e["nombre"] for e in r["objetivos_extra"]], ["Lejos"],
                         "Fuera está a 6 casillas: no entra")
        self.assertEqual(len(r["casillas_fuego"]), 12)

    def test_qi_adept_deja_luz_curativa(self):
        self._montar("Martial Master")
        r = self._atacar()
        self.assertTrue(r.get("ok"), r)
        luz = [c for c in r["terrenos_temporales"] if c["tipo"] == "brillo"]
        self.assertEqual(len(luz), 4)
        self.assertEqual(len([c for c in r["terrenos_temporales"] if c["tipo"] == "fuego"]), 12)

    def test_el_adyacente_ortogonal_no_entra_salvo_en_dragon(self):
        cam = self._montar("Warrior")
        pegado = _rival()
        pegado.nombre, pegado.x, pegado.y = "Pegado", cam.x, cam.y - 1
        tablero.registrar_unidad(pegado, resolver_colision=False)
        self.assertIn("no está en el área", self._atacar("Pegado").get("error", ""))


class TestMiasma(unittest.TestCase):
    """20 puntos PLANOS de Defensa, con el signo cambiado según el bando (verificado en
    juego): -20 a las unidades del jugador, +20 a las enemigas."""

    def setUp(self):
        tablero.limpiar()
        tablero.turno_actual = 1
        tablero.terrenos_temporales = {}
        tablero.sincronizar_terrenos_temporales()

    def tearDown(self):
        tablero.terrenos_temporales = {}
        tablero.sincronizar_terrenos_temporales()

    def test_los_valores_salen_del_datamine(self):
        m = efecto_de_terreno_temporal("miasma")
        self.assertEqual((m["defensa_aliado"], m["defensa_enemigo"]), (-20, 20))
        self.assertEqual(efecto_de_terreno_temporal("pilares")["defensa_aliado"], 0)

    def test_la_casilla_reparte_defensa_segun_el_bando(self):
        c = (4, 4)
        base = _mapa.grid[c[0]][c[1]].dfn
        tablero.aplicar_terreno_temporal([c], "miasma")
        t = _mapa.grid[c[0]][c[1]]
        self.assertEqual(defensa_de_terreno(t, es_aliado=True), base - 20)
        self.assertEqual(defensa_de_terreno(t, es_aliado=False), base + 20)
        tablero.turno_actual += 1
        tablero.caducar_terrenos_temporales()
        t = _mapa.grid[c[0]][c[1]]
        self.assertEqual(defensa_de_terreno(t, es_aliado=True), base)
        self.assertEqual(defensa_de_terreno(t, es_aliado=False), base)

    def test_en_combate_el_aliado_encaja_20_mas_y_el_enemigo_20_menos(self):
        """Mismo golpe, misma casilla: cambia quién está encima."""
        c = (4, 4)
        atacante = _rival(defensa=10, resistencia=10)
        defensor = _camilla(clase="Warrior", vinculo=1, fusion=False)

        def daño(en_miasma, defensor_es_aliado):
            t = TerrenoMapa()
            if en_miasma:
                t.dfn_aliado, t.dfn_enemigo = -20, 20
            return CalculadoraEngage.simular_combate(
                atacante.stats, defensor.stats, atacante.arma, None,
                Terreno(), Terreno(dfn=defensa_de_terreno(t, defensor_es_aliado)),
                1)["atacante"]["daño_por_golpe"]

        limpio = daño(False, True)
        self.assertEqual(daño(True, defensor_es_aliado=True), limpio + 20, "el aliado sufre")
        self.assertEqual(daño(True, defensor_es_aliado=False), max(0, limpio - 20), "el enemigo aguanta")

    def test_los_demas_terrenos_tratan_igual_a_los_dos_bandos(self):
        c = (5, 5)
        for tipo in ("pilares", "fuego", "brillo", "agua"):
            tablero.terrenos_temporales = {}
            tablero.aplicar_terreno_temporal([c], tipo)
            t = _mapa.grid[c[0]][c[1]]
            self.assertEqual(defensa_de_terreno(t, True), defensa_de_terreno(t, False), tipo)


if __name__ == "__main__":
    unittest.main()
