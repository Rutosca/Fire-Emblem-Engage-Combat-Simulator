"""
Aliados verdes que se unen por conversación (Cap. 9: Jade). Hasta hablar con
ellos desde una casilla adyacente con una unidad autorizada (Alear o Diamant,
M009.lua ジェーデ加入_*), no son controlables: no reciben recomendaciones, no
dan apoyos, se pueden recolocar sin gastar acción (los mueve la CPU) y editar su
ficha en el modal no los convierte en aliados.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import app, tablero, _desplegar_capitulo  # noqa: E402
from cargador_dispos import DISPOS_DIR  # noqa: E402


@unittest.skipUnless(os.path.isdir(DISPOS_DIR), "sin datamine (dispos)")
class TestUnionPorConversacion(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        _desplegar_capitulo("M009", "Extremo")
        tablero.fase = "jugador"
        self.jade = tablero.obtener_ficha("Jade")
        self.alear = next(f for f in tablero.fichas.values() if getattr(f, "pid", "") == "PID_リュール")
        self.assertIsNotNone(self.jade)

    def test_preset_jade_pendiente_con_steel_axe_y_pocion(self):
        self.assertTrue(self.jade.es_aliado)
        self.assertTrue(self.jade.union_pendiente)
        self.assertFalse(self.jade.controlable)
        self.assertEqual(self.jade.habla_con, ["PID_リュール", "PID_ディアマンド"])
        self.assertEqual([i["nombre"] for i in self.jade.inventario], ["Steel Axe", "Poción"])
        self.assertEqual(self.jade.arma.nombre, "Steel Axe")
        self.assertNotIn("Jade", [f.nombre for f in tablero.obtener_aliados()])
        self.assertEqual([f.nombre for f in tablero.obtener_npcs_pendientes()], ["Jade"])
        # Los verdes del Cap. 7 siguen siendo controlables desde el turno 1
        _desplegar_capitulo("M007", "Extremo")
        self.assertTrue(all(f.controlable for f in tablero.fichas.values() if f.es_verde))

    def test_hablar_requiere_adyacencia_autorizacion_y_accion(self):
        x, y = self.jade.x, self.jade.y
        ok, msg = tablero.hablar(self.alear.nombre, "Jade")
        self.assertFalse(ok, msg)                                   # no adyacente
        tablero.mover_unidad(self.alear.nombre, x + 1, y)
        otro = next(f for f in tablero.obtener_aliados() if f.nombre != self.alear.nombre and getattr(f, "pid", "") != "PID_ディアマンド")
        tablero.mover_unidad(otro.nombre, x - 1, y)
        ok, msg = tablero.hablar(otro.nombre, "Jade")
        self.assertFalse(ok, msg)                                   # no autorizado
        self.alear.ha_actuado = True
        ok, msg = tablero.hablar(self.alear.nombre, "Jade")
        self.assertFalse(ok, msg)                                   # sin acción
        self.alear.ha_actuado = False
        ok, msg = tablero.hablar(self.alear.nombre, "Jade")
        self.assertTrue(ok, msg)
        self.assertTrue(self.jade.controlable)
        self.assertTrue(self.alear.ha_actuado)
        self.assertEqual(self.alear.accion_turno, "hablar")
        self.assertIn("Jade", [f.nombre for f in tablero.obtener_aliados()])
        ok, _ = tablero.hablar(self.alear.nombre, "Jade")
        self.assertFalse(ok)                                        # ya reclutada

    def test_api_hablar_y_deshacer(self):
        tablero.mover_unidad(self.alear.nombre, self.jade.x, self.jade.y + 1)
        r = self.client.post("/api/unidad/hablar", json={"hablante": self.alear.nombre, "objetivo": "Jade"})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertFalse(r.get_json()["objetivo"]["union_pendiente"])
        self.assertTrue(tablero.deshacer())
        self.assertTrue(tablero.obtener_ficha("Jade").union_pendiente)
        r = self.client.post("/api/unidad/hablar", json={"hablante": self.alear.nombre, "objetivo": "Jade"})
        self.assertEqual(r.status_code, 200)   # el intento fallido de antes no dejó snapshot huérfano

    def test_mover_npc_no_gasta_accion_y_editar_ficha_no_lo_recluta(self):
        r = self.client.post("/api/mover", json={"nombre": "Jade", "x": self.jade.x, "y": self.jade.y - 1})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertFalse(tablero.obtener_ficha("Jade").ha_actuado)
        r = self.client.post("/api/mover", json={"nombre": "Jade", "x": self.jade.x, "y": self.jade.y})
        self.assertEqual(r.status_code, 200, r.get_json())          # puede volver a moverse (CPU)
        datos = tablero.obtener_ficha("Jade").como_dict()
        datos["hp_actual"] = datos["hp_max"] - 5
        r = self.client.post("/api/unidad/guardar", json=datos)
        self.assertEqual(r.status_code, 200, r.get_json())
        jade = tablero.obtener_ficha("Jade")
        self.assertTrue(jade.union_pendiente)
        self.assertFalse(jade.controlable)
        self.assertEqual(jade.hp_actual, datos["hp_max"] - 5)
        # El modal solo envía stats/equipo (sin es_verde, es_fijo, pid...): la identidad se conserva
        minimo = {"nombre": "Jade", "es_aliado": True, "x": jade.x, "y": jade.y, "nivel": jade.nivel,
                  "clase_nombre": jade.clase_nombre, "hp_actual": datos["hp_max"] - 7, "hp_max": datos["hp_max"],
                  "inventario": datos["inventario"]}
        r = self.client.post("/api/unidad/guardar", json=minimo)
        self.assertEqual(r.status_code, 200, r.get_json())
        jade = tablero.obtener_ficha("Jade")
        self.assertTrue(jade.es_verde)
        self.assertTrue(jade.union_pendiente)
        self.assertEqual(jade.habla_con, ["PID_リュール", "PID_ディアマンド"])
        self.assertEqual(getattr(jade, "pid", ""), "PID_ジェーデ")
        # y un enemigo genérico conserva su pid de dispos al reeditarlo
        kag = next(f for f in tablero.fichas.values() if getattr(f, "pid", "") == "PID_M009_カゲツ")
        r = self.client.post("/api/unidad/guardar", json={"nombre": kag.nombre, "es_aliado": False, "x": kag.x, "y": kag.y,
                                                          "nivel": kag.nivel, "clase_nombre": kag.clase_nombre, "inventario": kag.como_dict()["inventario"]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(getattr(tablero.obtener_ficha(kag.nombre), "pid", ""), "PID_M009_カゲツ")

    def test_analisis_recomienda_reclutar(self):
        tablero.mover_unidad(self.alear.nombre, self.jade.x + 2, self.jade.y)
        res = self.client.post("/api/analizar", json={"perfil": "seguro"}).get_json()
        recs = [r for r in res["resultados"] if r.get("tipo_analisis") == "conversacion"]
        self.assertTrue(recs, "debe recomendar hablar con Jade")
        self.assertEqual(recs[0]["aliado"], self.alear.nombre)
        self.assertEqual(recs[0]["objetivo"], "Jade")
        px, py = recs[0]["pos_sugerida"]
        self.assertEqual(abs(px - self.jade.x) + abs(py - self.jade.y), 1)
        self.assertFalse(any(r.get("aliado") == "Jade" for r in res["resultados"]), "Jade no recibe recomendaciones propias")
        # Ejecutar la recomendación: mover + hablar es UNA acción (la UI manda la casilla al endpoint de hablar)
        r = self.client.post("/api/unidad/hablar", json={"hablante": self.alear.nombre, "objetivo": "Jade", "x": px, "y": py})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual((self.alear.x, self.alear.y), (px, py))
        self.assertTrue(self.alear.ha_actuado)
        self.assertTrue(tablero.obtener_ficha("Jade").controlable)

    def test_hablar_con_movimiento_valida_alcance_y_deshace_si_falla(self):
        lejos = (self.jade.x + 1, self.jade.y)
        # una casilla fuera del alcance de movimiento: error y el hablante no se mueve
        self.alear.mov = 0
        r = self.client.post("/api/unidad/hablar", json={"hablante": self.alear.nombre, "objetivo": "Jade", "x": lejos[0], "y": lejos[1]})
        self.assertEqual(r.status_code, 400)
        self.assertNotEqual((self.alear.x, self.alear.y), lejos)
        self.assertFalse(self.alear.ha_actuado)
        # con alcance pero sin autorización (otro aliado): tampoco se queda movido ni gastado
        otro = next(f for f in tablero.obtener_aliados() if getattr(f, "pid", "") not in ("PID_リュール", "PID_ディアマンド"))
        tablero.mover_unidad(otro.nombre, self.jade.x + 2, self.jade.y)
        otro.ha_actuado = False
        r = self.client.post("/api/unidad/hablar", json={"hablante": otro.nombre, "objetivo": "Jade", "x": lejos[0], "y": lejos[1]})
        self.assertEqual(r.status_code, 400)
        f_otro = tablero.obtener_ficha(otro.nombre)
        self.assertEqual((f_otro.x, f_otro.y), (self.jade.x + 2, self.jade.y))
        self.assertFalse(f_otro.ha_actuado)

    def test_mover_con_accion_pendiente_no_gasta_el_turno(self):
        r = self.client.post("/api/mover", json={"nombre": self.alear.nombre, "x": self.alear.x + 1, "y": self.alear.y, "accion_pendiente": True})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertFalse(tablero.obtener_ficha(self.alear.nombre).ha_actuado)
        r = self.client.post("/api/mover", json={"nombre": self.alear.nombre, "x": self.alear.x + 1, "y": self.alear.y})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertTrue(tablero.obtener_ficha(self.alear.nombre).ha_actuado)

    def test_jade_tiene_sus_stats_oficiales(self):
        # Base de clase + base personal + round-half-up(crecimiento personal × 11 / 100)
        s = self.jade.stats
        self.assertEqual((s.hp_max or s.hp, s.fuerza, s.magia, s.destreza, s.velocidad, s.defensa, s.resistencia, s.suerte, s.complexion),
                         (33, 14, 4, 14, 5, 18, 6, 5, 8))


if __name__ == "__main__":
    unittest.main()
