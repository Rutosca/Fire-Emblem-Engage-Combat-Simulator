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
from app import app, tablero, _desplegar_capitulo, _cargador_dispos  # noqa: E402
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


if __name__ == "__main__":
    unittest.main()
