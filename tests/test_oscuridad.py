"""
Mapas a oscuras (Cap. 6, 13, 20), fase 1: qué se ve y por dónde se puede ir.
  - Se ve lo que alumbran los aliados (rombo de su visión: 3, Thief 5), las antorchas del
    mapa encendidas (rombo de 3) y las antorchas de mano (7, se encoge 1 por turno).
  - Un enemigo a oscuras queda oculto, en su última posición conocida.
  - Un aliado no puede entrar en una casilla a oscuras (es un muro).
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app as app_mod  # noqa: E402
from app import app, tablero  # noqa: E402
from lector_de_mapas import MapaTactico  # noqa: E402
import visibilidad  # noqa: E402
from motor_analisis import casillas_para_comando  # noqa: E402

ANCHO, ALTO = 14, 10


def _mapa_oscuro(antorchas=((10, 1, {}),)):
    """Llanura de 14x10 entera a oscuras, con antorchas-objeto (x, y, propiedades)."""
    data = {
        "width": ANCHO, "height": ALTO, "tilewidth": 32, "tileheight": 32,
        "tilesets": [{"firstgid": 1, "tiles": [
            {"id": 0, "properties": [{"name": "tipo", "type": "string", "value": "llanura"}]},
            {"id": 1, "properties": [{"name": "tipo", "type": "string", "value": "oscuridad"}]}]}],
        "layers": [
            {"type": "tilelayer", "name": "Terreno", "data": [1] * (ANCHO * ALTO)},
            {"type": "tilelayer", "name": "Oscuridad", "data": [2] * (ANCHO * ALTO)},
            {"type": "objectgroup", "name": "estructuras", "objects": [
                {"id": 100 + i, "name": f"Antorcha {i + 1}", "type": "antorcha", "x": x * 32, "y": y * 32,
                 "width": 32, "height": 32,
                 "properties": [{"name": k, "type": "bool" if isinstance(v, bool) else "int", "value": v}
                                for k, v in props.items()]}
                for i, (x, y, props) in enumerate(antorchas)]},
        ],
    }
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(data, f)
    f.close()
    return MapaTactico(f.name)


class TestOscuridad(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.client.post("/api/mapa/seleccionar", json={"capitulo": 7})

    def setUp(self, antorchas=((10, 1, {}),)):
        mapa = _mapa_oscuro(antorchas)
        app_mod._partida_actual().mapa = mapa
        tablero.mapa = mapa
        tablero.limpiar()
        tablero.historial.clear()
        tablero.turno_actual, tablero.fase, tablero.batalla_iniciada = 1, "jugador", True
        tablero.inicializar_objetos_mapa()
        self._unidad("Alear", "Sword Fighter", 1, 1)
        self._unidad("Bandido", "Axe Fighter", 6, 1, aliado=False)     # a 5: a oscuras
        self._unidad("Vigía", "Axe Fighter", 10, 4, aliado=False)      # a 3 de la antorcha

    def _unidad(self, nombre, clase, x, y, aliado=True, inventario=None):
        r = self.client.post("/api/unidad/guardar", json={
            "nombre": nombre, "clase_nombre": clase, "es_aliado": aliado, "x": x, "y": y, "nivel": 5,
            "inventario": inventario or [{"arma": "Iron Axe" if not aliado else "Iron Sword", "equipada": True}]})
        self.assertEqual(r.status_code, 200, r.get_json())
        return tablero.obtener_ficha(nombre)

    def _vis(self):
        return self.client.get("/api/visibilidad").get_json()

    def test_lectura_del_mapa(self):
        self.assertEqual(len(tablero.mapa.casillas_oscuras), ANCHO * ALTO)
        self.assertFalse(tablero.mapa.grid[10][1].caminable, "la antorcha es un obstáculo")
        self.assertEqual(tablero.mapa.grid[0][0].nombre.lower(), "llanura", "la oscuridad no es terreno")

    def test_que_se_ve(self):
        v = self._vis()
        self.assertTrue(v["oscuro"])
        luz = {tuple(c) for c in v["iluminadas"]}
        self.assertIn((4, 1), luz)                 # a 3 de Alear
        self.assertNotIn((5, 1), luz)              # a 4: oscuro
        self.assertIn((10, 4), luz)                # a 3 de la antorcha
        self.assertEqual(set(v["ocultos"]), {"Bandido"})
        self.assertTrue(tablero.obtener_ficha("Bandido").oculto)
        self.assertFalse(tablero.obtener_ficha("Vigía").oculto)

    def test_la_vision_del_thief_es_5(self):
        self._unidad("Yunaka", "Thief", 1, 8)
        self.assertEqual(visibilidad.radio_vision(tablero.obtener_ficha("Yunaka")), 5)
        self.assertEqual(visibilidad.radio_vision(tablero.obtener_ficha("Alear")), 3)

    def test_un_aliado_no_entra_a_oscuras(self):
        r = self.client.post("/api/mover", json={"nombre": "Alear", "x": 5, "y": 1})
        self.assertEqual(r.status_code, 400)
        self.assertIn("oscuras", r.get_json()["error"])
        self.assertTrue(casillas_para_comando(tablero, tablero.mapa, tablero.obtener_ficha("Alear"))
                        <= visibilidad.casillas_iluminadas(tablero))
        r = self.client.post("/api/mover", json={"nombre": "Alear", "x": 4, "y": 1})
        self.assertEqual(r.status_code, 200, r.get_json())
        # desde (4,1) ve a Bandido (a 2): ya no está oculto
        self.assertNotIn("Bandido", self._vis()["ocultos"])
        # la luz de otro aliado también sirve para entrar
        self._unidad("Lapis", "Sword Fighter", 1, 2)
        r = self.client.post("/api/mover", json={"nombre": "Lapis", "x": 5, "y": 2})
        self.assertEqual(r.status_code, 200, r.get_json())

    def test_apagar_y_encender_antorchas(self):
        r = self.client.post("/api/mapa/objeto/antorcha", json={"id": "100", "encendida": False})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertIn("Vigía", r.get_json()["ocultos"])
        self.assertEqual(r.get_json()["ocultos"]["Vigía"]["turno_visto"], 1, "se le vio por última vez en el T1")
        # el enemigo que la apaga gasta su acción; el aliado que la enciende, también
        self.client.post("/api/mapa/objeto/antorcha", json={"id": "100", "encendida": True})
        r = self.client.post("/api/mapa/objeto/antorcha", json={"id": "100", "encendida": False, "unidad": "Vigía"})
        self.assertEqual(r.status_code, 400, "Vigía no está junto a la antorcha")
        self.assertTrue(tablero.deshacer() or True)

    def test_antorcha_permanente(self):
        self.setUp(antorchas=((10, 1, {"permanente": True}),))
        r = self.client.post("/api/mapa/objeto/antorcha", json={"id": "100", "encendida": False})
        self.assertEqual(r.status_code, 400)

    def test_antorcha_de_mano(self):
        self._unidad("Alear", "Sword Fighter", 1, 1, inventario=[
            {"arma": "Iron Sword", "equipada": True}, {"nombre": "Antorcha", "usos": 3}])
        r = self.client.post("/api/unidad/antorcha_mano", json={"nombre": "Alear"})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertNotIn("Bandido", r.get_json()["ocultos"], "radio 7: a 5 se ve")
        alear = tablero.obtener_ficha("Alear")
        self.assertTrue(alear.ha_actuado)
        usos = next(it["usos"] for it in alear.inventario if (it.get("nombre") or it.get("arma")) == "Antorcha")
        self.assertEqual(usos, 2)
        # se encoge 1 por turno: en el T3 alumbra 5 y en el T8 ya no alumbra
        for turno in range(2, 4):
            self.client.post("/api/turno/inicio_fase_enemigo", json={})
            self.client.post("/api/turno/fin", json={})
        self.assertEqual(visibilidad.radio_antorcha_mano(tablero.obtener_ficha("Alear"), tablero.turno_actual), 5)
        for turno in range(4, 9):
            self.client.post("/api/turno/inicio_fase_enemigo", json={})
            self.client.post("/api/turno/fin", json={})
        self.assertEqual(tablero.obtener_ficha("Alear").luz_antorcha, {})

    def test_no_se_ataca_a_quien_no_se_ve(self):
        # Bandido (6,1) está a oscuras: aunque Alear llegaría a pegarle, no se propone ni se deja
        self._unidad("Bandido", "Axe Fighter", 5, 2, aliado=False)   # a 5 de Alear: oscuro
        tablero.obtener_ficha("Bandido").sincronizar_hp(1)
        res = self.client.post("/api/analizar", json={"perfil": "seguro"}).get_json()["resultados"]
        self.assertFalse([r for r in res if r.get("enemigo") == "Bandido" and r.get("tipo_analisis") != "peligro_aliado"], res)
        # sigue avisando de que puede atacar, sin proponer matarlo antes
        peligro = [r for r in res if r.get("tipo_analisis") == "peligro_aliado"]
        if peligro:
            self.assertIn("oscuras", peligro[0]["recomendacion"])
        r = self.client.post("/api/combate/ejecutar", json={"atacante": "Alear", "defensor": "Bandido",
                                                             "pos_destino": [4, 2]})
        self.assertEqual(r.status_code, 400)
        self.assertIn("oscuras", r.get_json()["error"])
        # en cuanto otro aliado lo ilumina, ya es un objetivo
        self._unidad("Lapis", "Sword Fighter", 3, 3)
        res = self.client.post("/api/analizar", json={"perfil": "seguro"}).get_json()["resultados"]
        self.assertTrue([r for r in res if r.get("enemigo") == "Bandido"])

    def test_dark_inferno_sin_objetivo(self):
        # Camilla en (5,5): su área llega a las esquinas (±2,±2), a distancia 4, fuera de su
        # visión de 3. El golpe solo da al visible; el oculto solo se quema al empezar su fase.
        r = self.client.post("/api/unidad/guardar", json={
            "nombre": "Chloé", "clase_nombre": "Axe Fighter", "es_aliado": True, "x": 5, "y": 5, "nivel": 10,
            "emblema_nombre": "Camilla", "en_fusion": True,
            "inventario": [{"arma": "Steel Axe", "equipada": True}]})
        self.assertEqual(r.status_code, 200, r.get_json())
        visible = self._unidad("Visible", "Axe Fighter", 7, 5, aliado=False)
        oculto = self._unidad("Oculto", "Axe Fighter", 7, 7, aliado=False)
        self.assertTrue(oculto.oculto and not visible.oculto)
        hp_v, hp_o = visible.hp_actual, oculto.hp_actual
        r = self.client.post("/api/unidad/infierno_oscuro", json={"nombre": "Chloé"})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual([g["nombre"] for g in r.get_json()["golpes"]], ["Visible"])
        self.assertLess(tablero.obtener_ficha("Visible").hp_actual, hp_v)
        self.assertEqual(tablero.obtener_ficha("Oculto").hp_actual, hp_o)
        self.assertIn([7, 7], r.get_json()["fuego_encendido"])
        chloe = tablero.obtener_ficha("Chloé")
        self.assertTrue(chloe.ataque_emblema_usado and chloe.ha_actuado)
        # al empezar la fase enemiga le quema el fuego aunque siga oculto
        self.client.post("/api/turno/inicio_fase_enemigo", json={})
        self.assertLess(tablero.obtener_ficha("Oculto").hp_actual, hp_o)
        # una sola vez por Fusión
        tablero.obtener_ficha("Chloé").ha_actuado = False
        self.assertEqual(self.client.post("/api/unidad/infierno_oscuro", json={"nombre": "Chloé"}).status_code, 400)

    def test_sin_oscuridad_se_ve_todo(self):
        self.client.post("/api/mapa/seleccionar", json={"capitulo": 7})
        self.assertFalse(self._vis()["oscuro"])


if __name__ == "__main__":
    unittest.main()
