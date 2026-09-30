"""
Cap. 12 (Solm, "La guerra del desierto"): arenas movedizas y refuerzos por turno.

- Arenas movedizas (TID_流砂, MoveFirst −3 en Terrain.xml): quien empieza su fase encima
  tiene 3 de Mov menos, también los enemigos que aparecen sobre ellas. Funciona como el hielo
  de la vena de Camilla (según la casilla en la que está antes de moverse). Los voladores no
  reciben ni bonos ni penalizaciones del suelo.
- Refuerzos (M012.lua): en Difícil/Extremo, EventEntryTurn(増援N, 3/4/6, FORCE_ALLY), en la
  fase aliada, tras la enemiga: el jugador los ve al empezar los turnos 4, 5 y 7 (la guía).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app, tablero, _desplegar_capitulo  # noqa: E402

RUTA_CAP12 = os.path.join(os.path.dirname(__file__), "..", "mapas", "CAP_12_Tiled.json")


@unittest.skipUnless(os.path.exists(RUTA_CAP12), "No existe mapas/CAP_12_Tiled.json")
class TestCapitulo12(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()
        cls.client.post("/api/mapa/seleccionar", json={"capitulo": 12})

    @classmethod
    def tearDownClass(cls):
        cls.client.post("/api/mapa/seleccionar", json={"capitulo": 7})

    def setUp(self):
        _desplegar_capitulo("M012", "Extremo")

    def _ficha(self, nombre):
        f = tablero.obtener_ficha(nombre)
        self.assertIsNotNone(f, nombre)
        return f

    def test_el_mapa_trae_las_arenas_del_datamine(self):
        t = tablero.mapa.grid[7][1]
        self.assertEqual((t.nombre, t.mov_inicial, t.coste_mov), ("arena_movediza", -3, 1))

    def test_quien_empieza_en_arenas_tiene_menos_mov(self):
        self.assertEqual(self._ficha("Sword Fighter (7,1)").movimiento_disponible, 1)
        self.assertEqual(self._ficha("Wolf Knight (8,11)").movimiento_disponible, 3)
        self.assertEqual(self._ficha("Warrior (6,3)").movimiento_disponible, 5, "en llano, sin cambios")

    def test_al_salir_de_las_arenas_recupera_el_mov(self):
        tablero.mover_unidad("Sword Fighter (7,1)", 4, 1)
        self.assertEqual(self._ficha("Sword Fighter (7,1)").movimiento_disponible, 4)

    def test_los_voladores_no_notan_las_arenas(self):
        flier = self._ficha("Lance Flier (6,7)")
        tablero.mover_unidad(flier.nombre, 7, 1)
        self.assertEqual(flier.movimiento_disponible, flier.mov)

    def test_los_refuerzos_llegan_en_los_turnos_4_5_y_7(self):
        enemigos = [f for f in tablero.fichas.values() if not f.es_aliado]
        self.assertEqual(len(enemigos), 13, "los refuerzos no salen en el despliegue inicial")
        self.assertIn("Martial Monk (1,1)", tablero.fichas)
        pendientes = {t: sorted(u["nombre"] for u in us) for t, us in tablero.refuerzos_pendientes.items()}
        self.assertEqual(sorted(pendientes), [4, 5, 7])
        self.assertEqual(len(pendientes[4]), 6)
        self.assertEqual(pendientes[5], ["Mage (17,1)", "Martial Monk (19,10)"])
        self.assertEqual(len(pendientes[7]), 5)

    # ── Aliados verdes ─────────────────────────────────────────────────────
    # M012.lua: UnitJoin("PID_フォガート", "PID_パンドロ", "PID_ボネ") al empezar el turno 1.
    # Los aldeanos de Solm (PID_M012_村人Ａ/Ｂ/Ｃ) no se unen nunca: los mueve la CPU (Retreat),
    # no tienen armas y su muerte no es condición de derrota.

    def _aldeanos(self):
        return [f for f in tablero.fichas.values() if getattr(f, "pid", "").startswith("PID_M012_村人")]

    def test_los_aldeanos_no_son_controlables(self):
        aldeanos = self._aldeanos()
        self.assertEqual(len(aldeanos), 3)
        for f in aldeanos:
            self.assertTrue(f.es_verde and f.nunca_se_une and not f.controlable, f.nombre)
        self.assertFalse({f.nombre for f in tablero.obtener_aliados()} & {f.nombre for f in aldeanos})

    def test_el_analisis_no_recomienda_nada_a_los_aldeanos(self):
        res = self.client.post("/api/analizar", json={"perfil": "seguro"}).get_json()["resultados"]
        nombres = {f.nombre for f in self._aldeanos()}
        self.assertFalse([r for r in res if r.get("aliado") in nombres])

    def test_fogado_pandreo_y_bunet_son_azules_desde_el_preset(self):
        """Aliados de tipo "inmediato": azules y controlables desde el Preset, en su casilla
        fija (no se recolocan en la formación)."""
        for n in ("Fogado", "Pandreo", "Bunet"):
            f = self._ficha(n)
            self.assertFalse(f.es_verde, n)
            self.assertTrue(f.controlable and f.es_fijo, n)
        self.assertTrue(all(f.es_verde for f in self._aldeanos()), "los aldeanos siguen verdes")
        # y se conserva al exportar/importar
        exp = self.client.get("/api/partida/exportar").get_json()["partida"]
        self.client.post("/api/partida/importar", json={"partida": exp})
        self.assertFalse(self._ficha("Fogado").es_verde)
        self.assertTrue(all(f.nunca_se_une for f in self._aldeanos()))

if __name__ == "__main__":
    unittest.main()
