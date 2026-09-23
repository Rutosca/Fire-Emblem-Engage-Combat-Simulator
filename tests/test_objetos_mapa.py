"""
Objetos de la capa de Tiled: armas de mapa (ballesta de arco del Cap. 8, cañón
mágico del Cap. 10) y cofres.

Cañón mágico (Cap. 10): mismo comportamiento que la ballesta (Skill.xml SID_魔砲台 =
SID_弓砲台: Hit +20, sin crítico, 1 golpe, sin contraataque) pero pide Tomo y maestría
en magia, y ataca a la RES con el tomo de la unidad.
Cofres: obstáculo que bloquea su casilla; abrirlo gasta la acción de una unidad
adyacente y no genera recomendaciones (el contenido lo anota el jugador).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import app, tablero, resolver_unidad_con_catalogo   # noqa: E402
import app as A                                              # noqa: E402
from motor_analisis import _armas_ballesta                   # noqa: E402
from catalogo_loader import (puede_usar_arma_de_mapa, arma_de_mapa_desde,   # noqa: E402
                             tipo_arma_de_objeto, nombre_arma_de_mapa)


def _mago(nombre="Céline", x=8, y=19, **kw):
    d = {"nombre": nombre, "x": x, "y": y, "es_aliado": True, "clase_nombre": "Mage", "nivel": 10,
         "inventario": [{"nombre": "Fire"}],
         "stats": {"hp": 26, "magia": 16, "destreza": 14, "velocidad": 12, "defensa": 5, "resistencia": 9, "suerte": 10}}
    d.update(kw)
    return resolver_unidad_con_catalogo(d)


class TestArmasDeMapa(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()

    def setUp(self):
        self.client.post("/api/mapa/seleccionar", json={"capitulo": 10})
        tablero.fase = "jugador"

    @classmethod
    def tearDownClass(cls):
        cls.client.post("/api/mapa/seleccionar", json={"capitulo": 7})

    def _canon(self):
        return next(e for e in A._mapa.objetos_mapa() if str(e.tipo).lower() == "arma_usable")

    def test_el_mapa_del_cap10_trae_canon_cofres_y_puerta(self):
        tipos = sorted(str(e.tipo).lower() for e in A._mapa.objetos_mapa())
        self.assertEqual(tipos.count("cofre"), 2)
        self.assertEqual(tipos.count("arma_usable"), 1)
        self.assertIn("destructible", tipos)
        canon = self._canon()
        self.assertEqual(tipo_arma_de_objeto(canon.propiedades), "Tomo")
        self.assertEqual(nombre_arma_de_mapa(canon.propiedades, canon.nombre), "Cañón mágico")

    def test_solo_las_unidades_magicas_pueden_usar_el_canon(self):
        canon = self._canon()
        mago = _mago()
        arquero = resolver_unidad_con_catalogo({"nombre": "Alcryst", "x": 9, "y": 19, "es_aliado": True,
                                                "clase_nombre": "Lord (Alcryst)", "nivel": 10,
                                                "inventario": [{"nombre": "Steel Bow"}], "stats": {"hp": 29, "fuerza": 13}})
        self.assertTrue(puede_usar_arma_de_mapa(mago, canon.propiedades))
        self.assertFalse(puede_usar_arma_de_mapa(arquero, canon.propiedades))
        # un mago sin tomo en el inventario tampoco
        sin_tomo = _mago("Sin Tomo", inventario=[{"nombre": "Poción"}])
        self.assertFalse(puede_usar_arma_de_mapa(sin_tomo, canon.propiedades))

    def test_arma_del_canon_usa_el_tomo_propio_hit20_sin_critico(self):
        canon = self._canon()
        mago = _mago()
        arma = arma_de_mapa_desde(mago, canon.propiedades, canon.nombre)
        base = next(a for a in [mago.arma] if a)
        self.assertEqual(arma.nombre, f"Cañón mágico ({base.nombre})")
        self.assertTrue(arma.es_magica)
        self.assertEqual(arma.mt, base.mt)
        self.assertEqual(arma.hit, base.hit + 20)
        self.assertEqual(arma.crit, 0)
        self.assertEqual(arma.rango, list(range(1, 8)))
        self.assertTrue(getattr(arma, "es_ballesta", False) and getattr(arma, "es_arma_mapa", False))

    def test_el_analisis_ofrece_el_canon_y_el_combate_gasta_turno_sin_contraataque(self):
        canon = self._canon()
        mago = _mago()
        tablero.registrar_unidad(mago)
        enemigo = resolver_unidad_con_catalogo({
            "nombre": "Bruto", "x": canon.x, "y": canon.y + 5, "es_aliado": False, "hp_actual": 30, "hp_max": 30,
            "arma_nombre": "Iron Axe", "stats": {"hp": 30, "defensa": 8, "resistencia": 3, "velocidad": 6, "fuerza": 12, "suerte": 3}})
        tablero.registrar_unidad(enemigo)
        armas = _armas_ballesta(mago, tablero, A._mapa)
        self.assertEqual([a.nombre for a, _, _ in armas], ["Cañón mágico (Fire)"])
        arma, _, nota = armas[0]
        self.assertEqual(getattr(arma, "pos_forzada"), (canon.x, canon.y))
        self.assertIn("sin contraataque", nota)

        r = self.client.post("/api/combate/ejecutar", json={
            "atacante": "Céline", "defensor": "Bruto", "objeto_id": canon.id_entidad})
        self.assertEqual(r.status_code, 200, r.get_json())
        d = r.get_json()
        self.assertEqual((tablero.obtener_ficha("Céline").x, tablero.obtener_ficha("Céline").y), (canon.x, canon.y))
        self.assertEqual(d["combate"]["atacante"]["golpes_en_ronda"], 1)
        self.assertFalse(d["combate"]["defensor"]["puede_contraatacar"])
        self.assertTrue(tablero.obtener_ficha("Céline").ha_actuado)
        # daño = Mag + Mt del tomo − RES del rival
        self.assertEqual(d["combate"]["atacante"]["daño_por_golpe"], 16 + 5 - 3)

    def test_un_arquero_no_puede_disparar_el_canon_magico(self):
        canon = self._canon()
        tablero.registrar_unidad(resolver_unidad_con_catalogo({
            "nombre": "Alcryst", "x": 9, "y": 19, "es_aliado": True, "clase_nombre": "Lord (Alcryst)", "nivel": 10,
            "inventario": [{"nombre": "Steel Bow"}], "stats": {"hp": 29, "fuerza": 13}}))
        tablero.registrar_unidad(resolver_unidad_con_catalogo({
            "nombre": "Bruto", "x": canon.x, "y": canon.y + 5, "es_aliado": False, "hp_actual": 30, "hp_max": 30,
            "arma_nombre": "Iron Axe", "stats": {"hp": 30, "defensa": 8}}))
        r = self.client.post("/api/combate/ejecutar", json={
            "atacante": "Alcryst", "defensor": "Bruto", "objeto_id": canon.id_entidad})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Tomo", r.get_json()["error"])


class TestUsosDeArmasDeMapa(unittest.TestCase):
    """Los enemigos también gastan la ballesta / el cañón: el jugador anota los usos que
    quedan (`POST /api/mapa/objeto/usos`). Con 0 el arma sigue en el mapa pero ya no se
    ofrece en las recomendaciones."""

    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()

    def setUp(self):
        self.client.post("/api/mapa/seleccionar", json={"capitulo": 10})
        tablero.fase = "jugador"
        self.canon = next(e for e in A._mapa.objetos_mapa() if str(e.tipo).lower() == "arma_usable")

    @classmethod
    def tearDownClass(cls):
        cls.client.post("/api/mapa/seleccionar", json={"capitulo": 7})

    def _estado(self):
        return next(o for o in tablero.objetos_como_lista() if str(o["id"]) == str(self.canon.id_entidad))

    def test_fijar_usos_y_agotar(self):
        # El tile del Cap. 10 declara `usos`: ese es el tope y el estado inicial
        tope = int(self.canon.propiedades["usos"])
        self.assertEqual((self._estado()["usos"], self._estado()["usos_max"]), (tope, tope))
        r = self.client.post("/api/mapa/objeto/usos", json={"id": self.canon.id_entidad, "usos": 3})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual((self._estado()["usos"], self._estado()["usos_max"]), (3, tope))
        # no se puede pasar del máximo que declara el mapa
        self.client.post("/api/mapa/objeto/usos", json={"id": self.canon.id_entidad, "usos": tope + 4})
        self.assertEqual(self._estado()["usos"], tope)
        # gastados por los enemigos
        self.client.post("/api/mapa/objeto/usos", json={"id": self.canon.id_entidad, "usos": 1})
        self.assertEqual(self._estado()["usos"], 1)
        self.client.post("/api/mapa/objeto/usos", json={"id": self.canon.id_entidad, "usos": 0})
        self.assertFalse(self._estado()["activo"])
        # sigue existiendo como objeto del mapa (mobiliario), pero no se puede usar
        self.assertIn(str(self.canon.id_entidad), [str(o["id"]) for o in tablero.objetos_como_lista()])
        # y si se le devuelven usos vuelve a estar activa (el mapa la repinta sin el gris)
        self.client.post("/api/mapa/objeto/usos", json={"id": self.canon.id_entidad, "usos": 2})
        self.assertEqual((self._estado()["usos"], self._estado()["activo"]), (2, True))

    def test_disparar_gasta_un_uso(self):
        mago = _mago()
        tablero.registrar_unidad(mago)
        tablero.registrar_unidad(resolver_unidad_con_catalogo({
            "nombre": "Bruto", "x": self.canon.x, "y": self.canon.y + 5, "es_aliado": False,
            "hp_actual": 30, "hp_max": 30, "arma_nombre": "Iron Axe",
            "stats": {"hp": 30, "defensa": 8, "resistencia": 3}}))
        antes = self._estado()["usos"]
        r = self.client.post("/api/combate/ejecutar", json={
            "atacante": "Céline", "defensor": "Bruto", "objeto_id": self.canon.id_entidad})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(self._estado()["usos"], antes - 1)

    def test_agotada_no_aparece_en_las_recomendaciones(self):
        mago = _mago()
        tablero.registrar_unidad(mago)
        self.assertTrue(_armas_ballesta(mago, tablero, A._mapa))
        self.client.post("/api/mapa/objeto/usos", json={"id": self.canon.id_entidad, "usos": 0})
        self.assertEqual(_armas_ballesta(mago, tablero, A._mapa), [])
        self.client.post("/api/mapa/objeto/usos", json={"id": self.canon.id_entidad, "usos": 2})
        self.assertTrue(_armas_ballesta(mago, tablero, A._mapa))

    def test_solo_vale_para_armas_de_mapa(self):
        puerta = next(o for o in tablero.objetos_como_lista() if o["propiedades"].get("tipo") == "puerta")
        r = self.client.post("/api/mapa/objeto/usos", json={"id": puerta["id"], "usos": 1})
        self.assertEqual(r.status_code, 400)


class TestCofres(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()

    def setUp(self):
        self.client.post("/api/mapa/seleccionar", json={"capitulo": 10})
        tablero.fase = "jugador"
        self.cofre = next(e for e in A._mapa.objetos_mapa() if str(e.tipo).lower() == "cofre")

    @classmethod
    def tearDownClass(cls):
        cls.client.post("/api/mapa/seleccionar", json={"capitulo": 7})

    def test_el_cofre_bloquea_su_casilla_antes_y_despues_de_abrirse(self):
        t = A._mapa.grid[self.cofre.x][self.cofre.y]
        self.assertFalse(t.caminable)
        self.assertFalse(t.volable)
        ok = tablero.abrir_cofre(self.cofre.id_entidad)
        self.assertIsNotNone(ok)
        t = A._mapa.grid[self.cofre.x][self.cofre.y]
        self.assertFalse(t.caminable, "un cofre abierto sigue siendo mobiliario del mapa")
        self.assertEqual(t.nombre, "Cofre abierto")

    def test_abrir_gasta_la_accion_de_una_unidad_adyacente(self):
        yunaka = resolver_unidad_con_catalogo({
            "nombre": "Yunaka", "x": self.cofre.x, "y": self.cofre.y - 1, "es_aliado": True,
            "clase_nombre": "Thief", "inventario": [{"nombre": "Iron Dagger"}], "stats": {"hp": 25}})
        tablero.registrar_unidad(yunaka)
        lejos = resolver_unidad_con_catalogo({
            "nombre": "Louis", "x": self.cofre.x, "y": max(0, self.cofre.y - 5), "es_aliado": True,
            "clase_nombre": "Lance Armor", "inventario": [{"nombre": "Iron Lance"}], "stats": {"hp": 30}})
        tablero.registrar_unidad(lejos)

        r = self.client.post("/api/mapa/objeto/abrir_cofre", json={"id": self.cofre.id_entidad, "unidad": "Louis"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("adyacente", r.get_json()["error"])

        r = self.client.post("/api/mapa/objeto/abrir_cofre", json={"id": self.cofre.id_entidad, "unidad": "Yunaka"})
        self.assertEqual(r.status_code, 200, r.get_json())
        f = tablero.obtener_ficha("Yunaka")
        self.assertTrue(f.ha_actuado)
        self.assertEqual(f.accion_turno, "cofre")
        self.assertFalse(next(o for o in tablero.objetos_como_lista() if o["id"] == self.cofre.id_entidad)["activo"])

        r = self.client.post("/api/mapa/objeto/abrir_cofre", json={"id": self.cofre.id_entidad, "unidad": "Yunaka"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("ya está abierto", r.get_json()["error"])

    def test_los_cofres_no_generan_recomendaciones(self):
        from motor_analisis import analizar_situacion_tactica
        tablero.registrar_unidad(resolver_unidad_con_catalogo({
            "nombre": "Yunaka", "x": self.cofre.x, "y": self.cofre.y - 1, "es_aliado": True,
            "clase_nombre": "Thief", "inventario": [{"nombre": "Iron Dagger"}], "stats": {"hp": 25}}))
        res = analizar_situacion_tactica(tablero, A._mapa, perfil="seguro")
        textos = " ".join(str(r.get("recomendacion", "")) for r in res["resultados"]).lower()
        self.assertNotIn("cofre", textos)


if __name__ == "__main__":
    unittest.main()
