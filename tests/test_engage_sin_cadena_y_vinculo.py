"""
Dos reglas comprobadas en juego:
  - Los Ataques de Emblema no admiten Chain Attacks (Houses Unite de Kagetsu, con Etie al
    lado, no encadena), salvo All for One de Lucina, que obliga a encadenar.
  - Subir a vínculo 11 en plena Fusión suma al momento el turno extra a la que está en
    curso: con 2 turnos restantes pasa a 3.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app, tablero  # noqa: E402
from catalogo_loader import resolver_unidad_con_catalogo  # noqa: E402
from motor_analisis import obtener_aliados_backup  # noqa: E402
from motor_calculo import CalculadoraEngage, Terreno  # noqa: E402


class TestAtaqueEmblemaSinChainAttack(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.client.post("/api/mapa/seleccionar", json={"capitulo": 7})

    def setUp(self):
        self.client.post("/api/mapa/seleccionar", json={"capitulo": 7})
        self.client.post("/api/preset/actual", json={})
        self.enemigo = next(f for f in tablero.obtener_enemigos() if f.viva and f.stats)
        self.enemigo.x, self.enemigo.y = 5, 4
        for nombre, clase, emblema, x, y in (
            ("Atacante", "Swordmaster", "Edelgard", 5, 5),
            ("LucinaTest", "Divine Dragon", "Lucina", 4, 4),
            ("Apoyo1", "Sword Fighter", "", 6, 4),
        ):
            f = resolver_unidad_con_catalogo({
                "nombre": nombre, "es_aliado": True, "nivel": 10, "clase_nombre": clase,
                "emblema_nombre": emblema, "en_fusion": bool(emblema), "nivel_vinculo": 5,
                "inventario": [{"nombre": "Iron Sword", "equipada": True}], "x": x, "y": y,
            }, tablero=tablero)
            tablero.registrar_unidad(f, resolver_colision=False)

    def test_houses_unite_no_encadena(self):
        atacante = tablero.obtener_ficha("Atacante")
        normal = [c.nombre for c in obtener_aliados_backup(atacante, self.enemigo, tablero=tablero)]
        self.assertIn("Apoyo1", normal, "en un ataque normal sí encadena")
        self.assertEqual(obtener_aliados_backup(atacante, self.enemigo, tablero=tablero,
                                                ataque_emblema="Houses Unite"), [])
        # y el motor de combate no los suma aunque se le pasen
        apoyo = tablero.obtener_ficha("Apoyo1")
        setattr(apoyo.stats, "arma", apoyo.arma)
        res = CalculadoraEngage.simular_combate(
            atacante.stats, self.enemigo.stats, atacante.arma, self.enemigo.arma, Terreno(), Terreno(), 1,
            aliados_apoyo_backup=[apoyo.stats], es_engage_attack=True, engage_attack_nombre="Houses Unite")
        self.assertEqual(res["resultado"]["chain_attacks"], [])

    def test_all_for_one_si_encadena(self):
        lucina = tablero.obtener_ficha("LucinaTest")
        apoyos = obtener_aliados_backup(lucina, self.enemigo, tablero=tablero,
                                        ataque_emblema="All for One (Todos para uno)")
        self.assertIn("Apoyo1", [c.nombre for c in apoyos])
        for a in apoyos:
            setattr(a.stats, "arma", a.arma)
        res = CalculadoraEngage.simular_combate(
            lucina.stats, self.enemigo.stats, lucina.arma, self.enemigo.arma, Terreno(), Terreno(), 1,
            aliados_apoyo_backup=[a.stats for a in apoyos], es_engage_attack=True,
            engage_attack_nombre="All for One (Todos para uno)")
        self.assertTrue(res["resultado"]["chain_attacks"])


class TestVinculo11EnFusion(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.client.post("/api/mapa/seleccionar", json={"capitulo": 7})

    def setUp(self):
        self.client.post("/api/mapa/seleccionar", json={"capitulo": 7})
        tablero.fichas.clear()

    def _guardar(self, **extra):
        d = {"nombre": "Kagetsu", "clase_nombre": "Swordmaster", "es_aliado": True, "x": 5, "y": 5,
             "nivel": 10, "emblema_nombre": "Edelgard", "arma_nombre": "Iron Sword",
             "inventario": [{"arma": "Iron Sword", "equipada": True}]}
        d.update(extra)
        r = self.client.post("/api/unidad/guardar", json=d)
        self.assertEqual(r.status_code, 200, r.get_json())
        return tablero.obtener_ficha("Kagetsu")

    def test_subir_a_11_alarga_la_fusion_en_curso(self):
        f = self._guardar(nivel_vinculo=10, en_fusion=True)
        self.assertEqual(f.turnos_fusion, 3)
        f.turnos_fusion = 2
        # el modal reenvía los turnos que tenía y el nuevo nivel de vínculo
        f = self._guardar(nivel_vinculo=11, en_fusion=True, turnos_fusion=2)
        self.assertEqual(f.turnos_fusion, 3)
        self.assertEqual(f.stats.turnos_fusion_restantes, 3)
        # volver a guardar sin cambiar el vínculo no suma más
        f = self._guardar(nivel_vinculo=11, en_fusion=True, turnos_fusion=3)
        self.assertEqual(f.turnos_fusion, 3)
        # corregir el nivel (volver a 10) lo deshace
        f = self._guardar(nivel_vinculo=10, en_fusion=True, turnos_fusion=3)
        self.assertEqual(f.turnos_fusion, 2)

    def test_fuera_de_fusion_solo_cambia_la_duracion_base(self):
        self._guardar(nivel_vinculo=10)
        f = self._guardar(nivel_vinculo=11, en_fusion=True)
        self.assertEqual(f.turnos_fusion, 4)


if __name__ == "__main__":
    unittest.main()
