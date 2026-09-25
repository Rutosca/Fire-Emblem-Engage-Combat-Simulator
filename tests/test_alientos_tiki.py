# -*- coding: utf-8 -*-
"""
Alientos de Tiki: geometría del área, efecto de suelo y congelamiento.

Verdades de juego aportadas por el jugador (boceto):
  - Se inicia a rango 1, como una espada, pero el golpe barre un área por delante.
  - Ice / Dark / Fire / Fog: la casilla de delante + las tres del fondo (una "T").
    Flame llega una fila más lejos (7 casillas).
  - Efectos: Ice congela toda su área, Flame prende fuego en 2 casillas (la de delante
    y la del centro de la fila siguiente), Fire prende solo en la de delante, Fog deja
    niebla en su área y en 4 casillas de los flancos, Dark no deja nada.
  - El área se propaga en las 4 direcciones, no solo hacia arriba.
  - Congelado = 0 de movimiento durante su fase (aliado en fase de jugador, enemigo en
    la enemiga).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from ataques_area import (ALIENTOS, NIEBLA_AVO, admite_efecto_de_suelo,      # noqa: E402
                          resolver_ataque_area, sabor_aliento, tipo_ataque_area)
from lector_de_mapas import Terreno as TerrenoMapa                           # noqa: E402
from motor_calculo import Terreno                                             # noqa: E402
from app import app, tablero, _mapa, resolver_unidad_con_catalogo             # noqa: E402

# Radio del claro: los alientos llegan a 3 de fondo y 2 de lado, y el área gira con la
# dirección del ataque, así que hace falta un rombo de radio 4 alrededor del portador.
RADIO = 4


def _allanar(centro):
    """Deja llano el rombo alrededor de `centro` y devuelve el terreno original.

    Los mapas de capítulo no tienen un claro tan grande, y lo que se mide aquí es la
    geometría del área, no el terreno: se allana a propósito y se restaura después."""
    cx, cy = centro
    original = {}
    for dx in range(-RADIO, RADIO + 1):
        for dy in range(-RADIO, RADIO + 1):
            x, y = cx + dx, cy + dy
            if abs(dx) + abs(dy) > RADIO or not (0 <= x < _mapa.ancho and 0 <= y < _mapa.alto):
                continue
            original[(x, y)] = _mapa.grid[x][y]
            _mapa.grid[x][y] = TerrenoMapa()
    return original


def _restaurar(original):
    for (x, y), t in original.items():
        _mapa.grid[x][y] = t


def _centro_del_mapa():
    return (min(max(RADIO, _mapa.ancho // 2), _mapa.ancho - RADIO - 1),
            min(max(RADIO, _mapa.alto // 2), _mapa.alto - RADIO - 1))

ALIENTO_DE = {"hielo": "Ice Breath", "oscuro": "Dark Breath", "fuego": "Fire Breath",
              "llama": "Flame Breath", "niebla": "Fog Breath"}


def _enemigo(nombre, x, y, hp=30):
    return resolver_unidad_con_catalogo({
        "nombre": nombre, "x": x, "y": y, "es_aliado": False, "hp_actual": hp, "hp_max": hp,
        "arma_nombre": "Iron Axe",
        "stats": {"hp": hp, "defensa": 5, "resistencia": 5, "velocidad": 5, "fuerza": 8, "suerte": 3},
    })


class TestNombres(unittest.TestCase):

    def test_cada_arma_da_su_sabor(self):
        for sabor, nombre in ALIENTO_DE.items():
            self.assertEqual(sabor_aliento(f"{nombre} (Emblema)"), sabor, nombre)
            self.assertEqual(tipo_ataque_area(nombre), "aliento", nombre)

    def test_flame_no_se_confunde_con_fire(self):
        """Flame Breath se parece a Fire Breath pero su área es mayor."""
        self.assertEqual(sabor_aliento("Flame Breath"), "llama")
        self.assertEqual(sabor_aliento("Fire Breath"), "fuego")
        self.assertNotEqual(ALIENTOS["llama"][0], ALIENTOS["fuego"][0])

    def test_las_otras_armas_de_tiki_no_son_de_area(self):
        for n in ("Eternal Claw", "Tail Smash", "Iron Sword"):
            self.assertIsNone(sabor_aliento(n), n)


class TestGeometria(unittest.TestCase):
    """Se prueba sobre coordenadas puras: un hueco 7x7 libre del mapa cargado."""

    def setUp(self):
        tablero.limpiar()
        self.centro = _centro_del_mapa()
        self.original = _allanar(self.centro)
        self.addCleanup(_restaurar, self.original)
        self.dragon = resolver_unidad_con_catalogo({
            "nombre": "Tiki", "x": self.centro[0], "y": self.centro[1], "es_aliado": True,
            "emblema_nombre": "Tiki", "en_fusion": True,
            "inventario": [{"nombre": "Iron Sword"}], "stats": {"hp": 40, "fuerza": 20, "defensa": 12}})
        tablero.registrar_unidad(self.dragon)

    def _area(self, nombre_arma, d):
        """Resuelve el aliento contra un enemigo puesto en la dirección `d`."""
        cx, cy = self.centro
        obj = _enemigo("Blanco", cx + d[0], cy + d[1])
        tablero.registrar_unidad(obj)
        try:
            return resolver_ataque_area(nombre_arma, self.centro, obj, self.dragon, tablero, _mapa)
        finally:
            tablero.eliminar_unidad("Blanco")

    def _relativas(self, casillas, d):
        """Pasa coordenadas absolutas a (avance, lado) para comparar con la tabla."""
        cx, cy = self.centro
        p = (d[1], d[0])
        fuera = []
        for (x, y) in casillas:
            vx, vy = x - cx, y - cy
            fuera.append((vx * d[0] + vy * d[1], vx * p[0] + vy * p[1]))
        return sorted(fuera)

    def test_area_de_dano_en_las_cuatro_direcciones(self):
        for sabor, nombre in ALIENTO_DE.items():
            esperado = sorted(ALIENTOS[sabor][0])
            for d in ((0, -1), (0, 1), (1, 0), (-1, 0)):
                a = self._area(nombre, d)
                self.assertTrue(a["valido"], a["motivo"])
                self.assertEqual(self._relativas(a["casillas_dano"], d), esperado,
                                 f"{nombre} hacia {d}")

    def test_la_t_basica_son_cuatro_casillas_y_flame_siete(self):
        d = (0, -1)
        for nombre in ("Ice Breath", "Dark Breath", "Fire Breath", "Fog Breath"):
            self.assertEqual(len(self._area(nombre, d)["casillas_dano"]), 4, nombre)
        self.assertEqual(len(self._area("Flame Breath", d)["casillas_dano"]), 7)

    def test_efectos_de_suelo(self):
        d = (1, 0)
        hielo = self._area("Ice Breath", d)
        self.assertEqual(self._relativas(hielo["casillas_hielo"], d),
                         self._relativas(hielo["casillas_dano"], d), "Ice congela toda su área")

        llama = self._area("Flame Breath", d)
        self.assertEqual(self._relativas(llama["casillas_fuego"], d), [(1, 0), (2, 0)])

        fuego = self._area("Fire Breath", d)
        self.assertEqual(self._relativas(fuego["casillas_fuego"], d), [(1, 0)])

        niebla = self._area("Fog Breath", d)
        self.assertEqual(self._relativas(niebla["casillas_niebla"], d),
                         sorted([(1, 0), (2, -1), (2, 0), (2, 1), (1, -1), (1, 1), (2, -2), (2, 2)]),
                         "la niebla cubre el área y los flancos")

        oscuro = self._area("Dark Breath", d)
        self.assertEqual(oscuro["casillas_fuego"] + oscuro["casillas_niebla"] + oscuro["casillas_hielo"], [],
                         "Dark no deja nada en el suelo")

    def test_alcanza_a_los_enemigos_del_area_y_no_a_los_aliados(self):
        cx, cy = self.centro
        tablero.registrar_unidad(_enemigo("Fondo", cx - 1, cy - 2))
        tablero.registrar_unidad(resolver_unidad_con_catalogo({
            "nombre": "Amigo", "x": cx + 1, "y": cy - 2, "es_aliado": True, "stats": {"hp": 20}}))
        a = self._area("Ice Breath", (0, -1))
        self.assertEqual([o.nombre for o in a["objetivos"]], ["Blanco", "Fondo"])

    def test_el_area_existe_aunque_no_haya_nadie_dentro(self):
        a = self._area("Fog Breath", (0, 1))
        self.assertEqual(len(a["objetivos"]), 1)
        self.assertEqual(len(a["casillas_niebla"]), 8)


class TestTerrenoDelEfecto(unittest.TestCase):

    def test_el_fuego_solo_prende_en_llano(self):
        self.assertTrue(admite_efecto_de_suelo(Terreno(nombre="Llanura"), "fuego"))
        self.assertFalse(admite_efecto_de_suelo(Terreno(nombre="Bosque", coste_mov=2), "fuego"))
        self.assertFalse(admite_efecto_de_suelo(Terreno(nombre="Muro", caminable=False, volable=False), "fuego"))

    def test_niebla_y_hielo_cubren_tambien_terreno_dificil(self):
        bosque = Terreno(nombre="Bosque", coste_mov=2)
        muro = Terreno(nombre="Muro", caminable=False, volable=False)
        for efecto in ("niebla", "hielo"):
            self.assertTrue(admite_efecto_de_suelo(bosque, efecto), efecto)
            self.assertFalse(admite_efecto_de_suelo(muro, efecto), efecto)


class TestTerrenosTemporalesEnElTablero(unittest.TestCase):

    def setUp(self):
        tablero.limpiar()
        tablero.turno_actual = 1
        tablero.terrenos_temporales = {}
        tablero.sincronizar_terrenos_temporales()

    def tearDown(self):
        tablero.terrenos_temporales = {}
        tablero.sincronizar_terrenos_temporales()

    def test_la_niebla_da_evasion_y_caduca(self):
        c = (4, 4)
        avo_base = _mapa.grid[c[0]][c[1]].avo
        tablero.aplicar_terreno_temporal([c], "niebla")
        t = _mapa.grid[c[0]][c[1]]
        self.assertTrue(t.es_niebla)
        self.assertEqual(t.avo, avo_base + NIEBLA_AVO)
        tablero.turno_actual += 1
        self.assertEqual(tablero.caducar_terrenos_temporales(), [c])
        self.assertFalse(_mapa.grid[c[0]][c[1]].es_niebla)
        self.assertEqual(_mapa.grid[c[0]][c[1]].avo, avo_base)

    def test_el_fuego_sigue_funcionando_con_el_mecanismo_generico(self):
        tablero.encender_fuego([(5, 5)])
        self.assertEqual(list(tablero.casillas_fuego), [(5, 5)])
        self.assertTrue(_mapa.grid[5][5].es_fuego)
        self.assertEqual(tablero.casillas_fuego_lista(), [{"x": 5, "y": 5, "expira_turno": 2}])

    def test_el_ultimo_aliento_manda_en_la_casilla(self):
        tablero.encender_fuego([(6, 6)])
        tablero.aplicar_terreno_temporal([(6, 6)], "hielo")
        self.assertEqual(tablero.casillas_fuego, {})
        self.assertEqual(tablero.casillas_de_tipo("hielo"), [(6, 6)])
        self.assertTrue(_mapa.grid[6][6].es_hielo)
        self.assertFalse(_mapa.grid[6][6].es_fuego)


class TestCongelado(unittest.TestCase):

    def setUp(self):
        tablero.limpiar()
        tablero.turno_actual = 1
        tablero.fase = "jugador"
        self.aliado = resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 4, "y": 4, "es_aliado": True,
            "inventario": [{"nombre": "Iron Sword"}], "stats": {"hp": 30, "fuerza": 12}, "mov": 5})
        self.enemigo = _enemigo("Bruto", 6, 4)
        tablero.registrar_unidad(self.aliado)
        tablero.registrar_unidad(self.enemigo)

    def test_congelado_deja_el_movimiento_a_cero(self):
        self.assertEqual(self.enemigo.movimiento_disponible, self.enemigo.mov)
        tablero.congelar(["Bruto"])
        self.assertTrue(self.enemigo.congelado)
        self.assertEqual(self.enemigo.movimiento_disponible, 0)
        self.assertTrue(self.enemigo.como_dict()["congelado"])
        self.assertEqual(self.enemigo.como_dict()["mov_disponible"], 0)
        self.assertEqual(self.enemigo.como_dict()["mov"], self.enemigo.mov, "el Mov de la ficha no cambia")

    def test_el_enemigo_se_deshiela_al_acabar_la_fase_enemiga(self):
        tablero.congelar(["Bruto"])
        tablero.iniciar_fase_enemigo()
        self.assertTrue(self.enemigo.congelado, "sigue congelado DURANTE su fase")
        tablero.avanzar_turno()
        self.assertFalse(self.enemigo.congelado)

    def test_el_aliado_se_deshiela_al_acabar_la_fase_de_jugador(self):
        tablero.congelar(["Alear"])
        self.assertTrue(self.aliado.congelado, "sigue congelado DURANTE su fase")
        tablero.iniciar_fase_enemigo()
        self.assertFalse(self.aliado.congelado)

    def test_deshelar_solo_afecta_a_su_bando(self):
        tablero.congelar(["Alear", "Bruto"])
        tablero.deshelar(es_aliado=True)
        self.assertFalse(self.aliado.congelado)
        self.assertTrue(self.enemigo.congelado)


class TestEnPartida(unittest.TestCase):
    """El aliento se ejecuta como un ataque normal, no como Ataque de Emblema."""

    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()

    def setUp(self):
        tablero.limpiar()
        tablero.turno_actual = 1
        tablero.fase = "jugador"
        tablero.terrenos_temporales = {}
        tablero.sincronizar_terrenos_temporales()
        self.centro = _centro_del_mapa()
        self.original = _allanar(self.centro)
        self.addCleanup(_restaurar, self.original)
        cx, cy = self.centro
        self.dragon = resolver_unidad_con_catalogo({
            "nombre": "Dragona", "x": cx, "y": cy, "es_aliado": True, "clase_nombre": "General",
            "emblema_nombre": "Tiki", "nivel_vinculo": 1, "en_fusion": True,
            "inventario": [{"nombre": "Steel Sword", "equipada": True}],
            "stats": {"hp": 45, "fuerza": 24, "magia": 10, "destreza": 18, "velocidad": 14,
                      "defensa": 16, "resistencia": 10, "suerte": 8, "complexion": 10}})
        tablero.registrar_unidad(self.dragon)
        # Aguantan el golpe a propósito: un muerto no se congela ni bloquea su movimiento
        tablero.registrar_unidad(_enemigo("Blanco", cx, cy - 1, hp=90))
        tablero.registrar_unidad(_enemigo("Fondo", cx + 1, cy - 2, hp=90))

    def tearDown(self):
        tablero.terrenos_temporales = {}
        tablero.sincronizar_terrenos_temporales()

    def _atacar(self, arma):
        return self.client.post("/api/combate/ejecutar", json={
            "atacante": "Dragona", "defensor": "Blanco", "arma_nombre": arma}).get_json()

    def test_ice_breath_golpea_al_fondo_congela_y_deja_hielo(self):
        r = self._atacar("Ice Breath (Emblema)")
        self.assertTrue(r.get("ok"), r)
        self.assertEqual([e["nombre"] for e in r["objetivos_extra"]], ["Fondo"])
        self.assertGreater(r["objetivos_extra"][0]["daño"], 0)
        self.assertIn("Blanco", r["congelados"])
        self.assertIn("Fondo", r["congelados"])
        self.assertTrue(tablero.obtener_ficha("Fondo").congelado)
        self.assertEqual(tablero.obtener_ficha("Fondo").movimiento_disponible, 0)
        hielo = [c for c in r["terrenos_temporales"] if c["tipo"] == "hielo"]
        self.assertEqual(len(hielo), 4)

    def test_flame_breath_prende_dos_casillas(self):
        r = self._atacar("Flame Breath (Emblema)")
        self.assertTrue(r.get("ok"), r)
        cx, cy = self.centro
        self.assertEqual(sorted((c["x"], c["y"]) for c in r["casillas_fuego"]),
                         [(cx, cy - 2), (cx, cy - 1)])
        self.assertEqual(r["congelados"], [])

    def test_fog_breath_deja_niebla_y_no_fuego(self):
        r = self._atacar("Fog Breath (Emblema)")
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(r["casillas_fuego"], [])
        self.assertEqual(len([c for c in r["terrenos_temporales"] if c["tipo"] == "niebla"]), 8)

    def test_dark_breath_no_deja_nada_en_el_suelo(self):
        r = self._atacar("Dark Breath (Emblema)")
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(r["terrenos_temporales"], [])
        self.assertEqual([e["nombre"] for e in r["objetivos_extra"]], ["Fondo"])

    def test_eternal_claw_no_tiene_area(self):
        r = self._atacar("Eternal Claw (Emblema)")
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(r["objetivos_extra"], [])
        self.assertEqual(r["terrenos_temporales"], [])
        self.assertEqual(r["area_aliento"], [])

    def test_una_unidad_congelada_no_puede_moverse(self):
        self._atacar("Ice Breath (Emblema)")
        f = tablero.obtener_ficha("Fondo")
        r = self.client.post("/api/mover",
                             json={"nombre": "Fondo", "x": f.x + 1, "y": f.y})
        self.assertEqual(r.status_code, 400)
        self.assertIn("congelada", r.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
