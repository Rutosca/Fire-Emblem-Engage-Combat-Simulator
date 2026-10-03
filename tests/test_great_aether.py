"""
Great Aether (SID_アイクエンゲージ技, Ataque de Emblema de Ike), verificado en juego:
  - No ataca a nadie al usarlo: la unidad se pone en guardia (Def/Res +5; Acorazado
    Def +10 / Res +5; Volador Def +5 / Res +10) y no contraataca en la fase enemiga.
  - Solo con espada o hacha (WeaponProhibit 1013).
  - Al empezar la siguiente fase de jugador, si sigue viva, golpea una vez a cada enemigo
    del rombo de radio 2 (Range.xml アイク我慢範囲_攻撃): Hit 100, sin crítico, y se cura el
    30 % de min(HP del enemigo, daño) por golpe. Si murió, o no hay nadie, no pasa nada.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app, tablero  # noqa: E402
import pasivas  # noqa: E402
from motor_calculo import CalculadoraEngage, Terreno  # noqa: E402

STATS = {"hp": 40, "hp_max": 40, "fuerza": 20, "magia": 2, "destreza": 18, "velocidad": 14,
         "defensa": 12, "resistencia": 8, "suerte": 8, "complexion": 9}


class _BaseGreatAether(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.client.post("/api/mapa/seleccionar", json={"capitulo": 7})

    def setUp(self):
        # Cap. 12: llanura libre en x 5..8, y 8..10
        self.client.post("/api/mapa/seleccionar", json={"capitulo": 12})
        tablero.fichas.clear()
        tablero.fase, tablero.turno_actual = "jugador", 2
        self._ike()

    def _ike(self, arma="Iron Sword", hp=40, **extra):
        d = {"nombre": "Timerra", "clase_nombre": "Swordmaster", "es_aliado": True, "x": 6, "y": 9, "nivel": 10,
             "hp_max": 40, "hp_actual": hp, "stats": STATS, "emblema_nombre": "Ike", "nivel_vinculo": 5,
             "en_fusion": True, "arma_nombre": arma, "inventario": [{"arma": arma, "equipada": True}]}
        d.update(extra)
        r = self.client.post("/api/unidad/guardar", json=d)
        self.assertEqual(r.status_code, 200, r.get_json())
        return tablero.obtener_ficha("Timerra")

    def _enemigo(self, nombre, x, y, arma="Iron Axe", hp=30, fuerza=None):
        d = {"nombre": nombre, "clase_nombre": "Axe Fighter", "es_aliado": False, "x": x, "y": y, "nivel": 5,
             "hp_max": hp, "hp_actual": hp, "arma_nombre": arma, "inventario": [{"arma": arma, "equipada": True}]}
        if fuerza:
            d["stats"] = {"hp": hp, "hp_max": hp, "fuerza": fuerza, "magia": 0, "destreza": 20, "velocidad": 10,
                          "defensa": 8, "resistencia": 2, "suerte": 4, "complexion": 10}
        r = self.client.post("/api/unidad/guardar", json=d)
        self.assertEqual(r.status_code, 200, r.get_json())
        return tablero.obtener_ficha(nombre)

    def _usar(self, **extra):
        return self.client.post("/api/unidad/postura_emblema", json={"nombre": "Timerra", **extra})


class TestGreatAether(_BaseGreatAether):

    def test_datos_del_datamine(self):
        p = pasivas.postura_de_emblema(tablero.obtener_ficha("Timerra"))
        self.assertEqual(p["nombre"], "Great Aether")
        self.assertEqual(p["stat_boosts"], {"def": 5, "res": 5})
        self.assertEqual(sorted(p["tipos_arma"]), ["Espada", "Hacha"])
        self.assertEqual(len(p["casillas"]), 12, "rombo de radio 2 sin la casilla propia")
        self.assertTrue(all(1 <= abs(dx) + abs(dy) <= 2 for dx, dy in p["casillas"]))

    def test_guardia_sin_contraataque_y_con_bonos(self):
        ene = self._enemigo("Axe Fighter A", 6, 10, arma="Silver Axe")
        ike = tablero.obtener_ficha("Timerra")
        antes = CalculadoraEngage.simular_combate(ene.stats, ike.stats, ene.arma, ike.arma, Terreno(), Terreno(), 1)
        r = self._usar()
        self.assertEqual(r.status_code, 200, r.get_json())
        ike = tablero.obtener_ficha("Timerra")
        self.assertTrue(ike.ha_actuado and ike.ataque_emblema_usado)
        self.assertEqual(ike.como_dict()["stats"]["defensa"], STATS["defensa"] + 5, "Def +5 a la vista, como en el juego")
        despues = CalculadoraEngage.simular_combate(ene.stats, ike.stats, ene.arma, ike.arma, Terreno(), Terreno(), 1)
        self.assertTrue(antes["defensor"]["puede_contraatacar"])
        self.assertFalse(despues["defensor"]["puede_contraatacar"])
        # Def +5 (y Laguz Friend, que en Fusión ya parte el daño a la mitad)
        self.assertLess(despues["atacante"]["daño_por_golpe"], antes["atacante"]["daño_por_golpe"])
        # y no se puede lanzar como un ataque contra un enemigo
        r = self.client.post("/api/combate/ejecutar", json={"atacante": "Timerra", "defensor": "Axe Fighter A",
                                                   "es_engage_attack": True, "engage_attack_nombre": "Great Aether"})
        self.assertEqual(r.status_code, 400)

    def test_demolish_no_mata_unidades_de_un_golpe(self):
        # SID_破壊 (Flag bit 9) es contra estructuras: "相手のダメージ = 相手のHP" no vale con unidades
        ene = self._enemigo("Axe Fighter A", 6, 10, hp=99)
        ike = tablero.obtener_ficha("Timerra")
        self.assertIn("SID_破壊", pasivas.sids_activos(ike))
        r = CalculadoraEngage.simular_combate(ike.stats, ene.stats, ike.arma, ene.arma, Terreno(), Terreno(), 1)
        self.assertLess(r["atacante"]["daño_por_golpe"], 40)

    def test_rechazos(self):
        self._ike(arma="Iron Lance")
        r = self._usar()
        self.assertEqual(r.status_code, 400)
        self.assertIn("espada o hacha", r.get_json()["error"])
        self._ike()
        self.assertEqual(self._usar().status_code, 200)
        tablero.obtener_ficha("Timerra").ha_actuado = False
        tablero.obtener_ficha("Timerra").accion_turno = ""
        r = self._usar()
        self.assertEqual(r.status_code, 400, "un Ataque de Emblema por Fusión")

    def test_golpe_al_empezar_el_turno_y_curacion(self):
        cerca = self._enemigo("Axe Fighter A", 6, 10)              # distancia 1
        a_dos = self._enemigo("Axe Fighter B", 7, 10)              # distancia 2
        lejos = self._enemigo("Axe Fighter C", 6, 12)              # distancia 3: fuera
        self.assertEqual(self._usar().status_code, 200)
        ike = tablero.obtener_ficha("Timerra")
        ike.sincronizar_hp(20)
        self.client.post("/api/turno/inicio_fase_enemigo", json={})
        r = self.client.post("/api/turno/fin", json={}).get_json()
        res = r["posturas_resueltas"]
        self.assertEqual(len(res), 1)
        golpeados = {g["enemigo"]: g for g in res[0]["golpes"]}
        self.assertEqual(set(golpeados), {"Axe Fighter A", "Axe Fighter B"})
        for g in golpeados.values():
            self.assertGreater(g["daño"], 0)
        self.assertEqual(lejos.hp_actual, 30)
        esperado = sum(int(min(30, g["daño"]) * 0.3) for g in golpeados.values())
        self.assertAlmostEqual(res[0]["curado"], esperado, delta=len(golpeados), msg="30 % de lo quitado por golpe")
        self.assertIsNone(pasivas.estado_de_postura(tablero.obtener_ficha("Timerra")), "la guardia se gasta")
        # todo se deshace con la Cronogema
        self.assertTrue(tablero.deshacer())
        self.assertEqual(tablero.obtener_ficha("Axe Fighter A").hp_actual, 30)

    def test_si_muere_no_hay_golpe(self):
        self._enemigo("Axe Fighter A", 6, 10)
        self.assertEqual(self._usar().status_code, 200)
        tablero.obtener_ficha("Timerra").sincronizar_hp(0)
        self.client.post("/api/turno/inicio_fase_enemigo", json={})
        r = self.client.post("/api/turno/fin", json={}).get_json()
        self.assertEqual(r["posturas_resueltas"], [])
        self.assertEqual(tablero.obtener_ficha("Axe Fighter A").hp_actual, 30)


class TestRecomendarGreatAether(_BaseGreatAether):
    """Solo se propone donde sobrevive al peor caso (todos los que llegan la atacan, con
    Chain Attacks) y donde los que la atacarían quedan en el área (armas de alcance <= 2)."""

    def _recs(self):
        res = self.client.post("/api/analizar", json={"perfil": "seguro"}).get_json()["resultados"]
        return [r for r in res if r.get("tipo_analisis") == "postura_emblema"]

    def test_se_propone_contra_varios_debiles(self):
        self._enemigo("Axe Fighter A", 6, 12)
        self._enemigo("Axe Fighter B", 8, 12)
        recs = self._recs()
        self.assertEqual(len(recs), 1, recs)
        self.assertEqual(sorted(recs[0]["objetivos"]), ["Axe Fighter A", "Axe Fighter B"])
        self.assertLess(recs[0]["daño_peor_caso"], 40)
        # ningún ataque normal ofrece "Great Aether" contra un enemigo
        res = self.client.post("/api/analizar", json={"perfil": "seguro"}).get_json()["resultados"]
        self.assertFalse([r for r in res if "great aether" in str(r.get("arma_recomendada", "")).lower()])
        # la recomendación se ejecuta con el mismo endpoint que el botón del modal
        x, y = recs[0]["pos_sugerida"]
        r = self.client.post("/api/unidad/postura_emblema", json={"nombre": "Timerra", "x": x, "y": y})
        self.assertEqual(r.status_code, 200, r.get_json())

    def test_no_si_puede_morir(self):
        self._ike(hp=25)
        self._enemigo("Axe Fighter A", 6, 12, arma="Silver Axe", fuerza=30)
        self._enemigo("Axe Fighter B", 8, 12, arma="Silver Axe", fuerza=30)
        self._enemigo("Axe Fighter C", 4, 11, arma="Silver Axe", fuerza=30)
        self.assertEqual(self._recs(), [])

    def test_no_con_uno_solo_que_no_muere(self):
        self._enemigo("Axe Fighter A", 6, 12, hp=60)
        self.assertEqual(self._recs(), [])


if __name__ == "__main__":
    unittest.main()
