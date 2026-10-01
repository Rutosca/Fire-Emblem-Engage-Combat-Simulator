"""
Devolver la acción a un aliado que ya actuó:
  - Dance (SID_踊り, clase Dancer: Seadall): a uno adyacente, que vuelve a moverse y actuar.
  - Goddess Dance (Ataque de Emblema de Byleth en Fusión): a todos los adyacentes en cruz
    que ya actuaron, igual que Dance; gasta el Ataque de Emblema.
  - Contract (SID_契約, Verónica en Fusión): a uno adyacente, que vuelve a actuar SIN
    moverse (ataca o cura desde su casilla).
La cadena típica (atacar → Dance → atacar → Goddess Dance a ese aliado y a Seadall →
atacar → Dance → atacar) da hasta cuatro acciones a una misma unidad en un turno.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app, tablero  # noqa: E402

STATS = {"hp": 40, "hp_max": 40, "fuerza": 15, "magia": 5, "destreza": 15, "velocidad": 15,
         "defensa": 10, "resistencia": 8, "suerte": 8, "complexion": 8}


class TestReactivarAcciones(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.client.post("/api/mapa/seleccionar", json={"capitulo": 7})

    def setUp(self):
        # Cap. 12: llanura libre en x 5..8, y 8..10 (sin arenas ni rocas)
        self.client.post("/api/mapa/seleccionar", json={"capitulo": 12})
        tablero.fichas.clear()
        tablero.fase = "jugador"
        self._unidad("Diamant", "Swordmaster", 6, 9)
        self._unidad("Seadall", "Dancer", 8, 9)
        self._unidad("Byleth", "Swordmaster", 5, 8, emblema="Byleth", en_fusion=True)
        self._unidad("Veronica", "Swordmaster", 8, 10, emblema="Veronica", en_fusion=True)

    def _unidad(self, nombre, clase, x, y, **extra):
        d = {"nombre": nombre, "clase_nombre": clase, "es_aliado": True, "x": x, "y": y, "nivel": 10,
             "hp_max": 40, "hp_actual": 40, "mov": 5, "stats": STATS, "arma_nombre": "Iron Sword",
             "inventario": [{"arma": "Iron Sword", "equipada": True}]}
        if extra.get("emblema"):
            d.update(emblema_nombre=extra["emblema"], en_fusion=extra.get("en_fusion", False), turnos_fusion=3)
        r = self.client.post("/api/unidad/guardar", json=d)
        self.assertEqual(r.status_code, 200, r.get_json())

    def _f(self, n):
        return tablero.obtener_ficha(n)

    def _actuar(self, nombre, accion="combate"):
        self._f(nombre).ha_actuado = True
        self._f(nombre).accion_turno = accion

    def _opciones(self, nombre):
        return self.client.get("/api/unidad/opciones_reactivar", query_string={"nombre": nombre}).get_json()["opciones"]

    def _reactivar(self, actor, op):
        payload = {"actor": actor, "tipo": op["tipo"], "x": op["pos"][0], "y": op["pos"][1]}
        if op["tipo"] != "danza_diosa":
            payload["objetivo"] = op["objetivos"][0]
        return self.client.post("/api/unidad/reactivar", json=payload)

    def test_quien_tiene_cada_comando(self):
        self.assertEqual(self._f("Seadall").tipos_reactivacion(), ["baile"])
        self.assertIn("danza_diosa", self._f("Byleth").tipos_reactivacion())
        self.assertIn("contrato", self._f("Veronica").tipos_reactivacion())
        self.assertEqual(self._f("Diamant").tipos_reactivacion(), [])

    def test_cadena_de_cuatro_acciones(self):
        # 1. Diamant ataca; Seadall se acerca y baila (mover + bailar es una acción)
        self._actuar("Diamant")
        op = next(o for o in self._opciones("Seadall") if o["objetivos"] == ["Diamant"])
        r = self._reactivar("Seadall", op)
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertFalse(self._f("Diamant").ha_actuado)
        self.assertTrue(self._f("Seadall").ha_actuado)
        self.assertEqual(self._f("Diamant").movimiento_disponible, 5, "Dance: vuelve a moverse")
        # 2. Diamant se mueve y vuelve a atacar
        r = self.client.post("/api/mover", json={"nombre": "Diamant", "x": 6, "y": 10})
        self.assertEqual(r.status_code, 200, r.get_json())
        self._actuar("Diamant")
        # 3. Goddess Dance: Byleth va a la casilla junto a los dos y los reactiva a ambos
        op = next(o for o in self._opciones("Byleth") if o["tipo"] == "danza_diosa")
        self.assertEqual(sorted(op["objetivos"]), ["Diamant", "Seadall"])
        r = self._reactivar("Byleth", op)
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertFalse(self._f("Diamant").ha_actuado)
        self.assertFalse(self._f("Seadall").ha_actuado)
        self.assertTrue(self._f("Byleth").ataque_emblema_usado)
        self.assertNotIn("danza_diosa", self._f("Byleth").tipos_reactivacion(), "una por Fusión")
        # 4. Diamant ataca otra vez y Seadall vuelve a bailarle
        self._actuar("Diamant")
        op = next(o for o in self._opciones("Seadall") if o["objetivos"] == ["Diamant"])
        self.assertEqual(self._reactivar("Seadall", op).status_code, 200)
        self.assertFalse(self._f("Diamant").ha_actuado)
        # todo se deshace paso a paso con la Cronogema
        self.assertTrue(tablero.deshacer())
        self.assertTrue(self._f("Diamant").ha_actuado)

    def test_contract_actua_sin_moverse(self):
        self._actuar("Diamant")
        tablero.mover_unidad("Veronica", 7, 9)
        op = next(o for o in self._opciones("Veronica") if o["tipo"] == "contrato")
        self.assertEqual((op["objetivos"], op["pos"]), (["Diamant"], [7, 9]))
        r = self._reactivar("Veronica", op)
        self.assertEqual(r.status_code, 200, r.get_json())
        d = self._f("Diamant")
        self.assertFalse(d.ha_actuado)
        self.assertEqual(d.movimiento_disponible, 0)
        r = self.client.post("/api/mover", json={"nombre": "Diamant", "x": 6, "y": 10})
        self.assertEqual(r.status_code, 400, "no puede moverse")
        # al empezar el siguiente turno vuelve a moverse con normalidad
        tablero.reiniciar_acciones_turno()
        self.assertEqual(self._f("Diamant").movimiento_disponible, 5)

    def test_rechazos(self):
        # nadie ha actuado: no hay a quién bailar
        self.assertEqual(self._opciones("Seadall"), [])
        r = self.client.post("/api/unidad/reactivar", json={"actor": "Seadall", "tipo": "baile", "objetivo": "Diamant"})
        self.assertEqual(r.status_code, 400)
        # quien ya hizo algo (no solo moverse) no puede bailar
        self._actuar("Diamant")
        self._actuar("Seadall", "combate")
        self.assertEqual(self._opciones("Seadall"), [])
        # quien solo se movió (arrastró la ficha) sí: en el juego se mueve y luego baila
        self._f("Seadall").accion_turno = ""
        tablero.mover_unidad("Seadall", 7, 9)
        self.assertTrue(self._opciones("Seadall"))
        # sin el comando no se puede
        r = self.client.post("/api/unidad/reactivar", json={"actor": "Byleth", "tipo": "baile", "objetivo": "Diamant"})
        self.assertEqual(r.status_code, 400)


class TestRecomendarReactivar(TestReactivarAcciones):
    """El análisis solo propone devolver la acción cuando rinde: Dance si el bailado remata;
    Contract si remata desde su casilla (o se cura con una poción); Goddess Dance (gasta el
    Ataque de Emblema) si reactiva a dos o más que matan o si eso gana el mapa."""

    def _enemigo(self, nombre, x, y, hp=4):
        r = self.client.post("/api/unidad/guardar", json={
            "nombre": nombre, "clase_nombre": "Axe Fighter", "es_aliado": False, "x": x, "y": y, "nivel": 1,
            "hp_max": 30, "hp_actual": hp, "mov": 4, "arma_nombre": "Iron Axe",
            "inventario": [{"arma": "Iron Axe", "equipada": True}]})
        self.assertEqual(r.status_code, 200, r.get_json())

    def _recs(self):
        res = self.client.post("/api/analizar", json={"perfil": "seguro"}).get_json()["resultados"]
        return [r for r in res if r.get("tipo_analisis") == "reactivacion"]

    def test_seadall_baila_para_rematar(self):
        self._enemigo("Axe Fighter A", 6, 12)
        self._actuar("Diamant")
        recs = self._recs()
        baile = [r for r in recs if r["tipo"] == "baile"]
        self.assertEqual(len(baile), 1, recs)
        self.assertEqual((baile[0]["aliado"], baile[0]["objetivos"]), ("Seadall", ["Diamant"]))
        self.assertEqual(baile[0]["jugadas_siguientes"][0]["enemigo"], "Axe Fighter A")
        # el enemigo queda lejos de su casilla: Contract (sin moverse) no remata, no se propone
        self.assertFalse([r for r in recs if r["tipo"] == "contrato"])
        # la recomendación se ejecuta con el mismo endpoint que el botón del modal
        r = self.client.post("/api/unidad/reactivar", json={"actor": "Seadall", "tipo": "baile", "objetivo": "Diamant",
                                                            "x": baile[0]["pos_sugerida"][0], "y": baile[0]["pos_sugerida"][1]})
        self.assertEqual(r.status_code, 200, r.get_json())

    def test_sin_nadie_que_rematar_no_se_propone(self):
        self._enemigo("Axe Fighter A", 1, 1, hp=30)
        self._actuar("Diamant")
        self.assertEqual(self._recs(), [])

    def test_contract_si_remata_desde_su_casilla(self):
        self._enemigo("Axe Fighter A", 5, 9)
        self._actuar("Diamant")
        recs = {r["tipo"]: r for r in self._recs()}
        self.assertIn("contrato", recs)
        self.assertEqual(recs["contrato"]["objetivos"], ["Diamant"])

    def test_goddess_dance_solo_si_varias_bajas(self):
        self._enemigo("Axe Fighter A", 5, 9)
        self._enemigo("Axe Fighter B", 7, 12)
        self._unidad("Lapis", "Swordmaster", 6, 11)
        self._actuar("Diamant")
        self.assertFalse([r for r in self._recs() if r["tipo"] == "danza_diosa"], "una sola baja: no compensa")
        self._actuar("Lapis")
        gd = [r for r in self._recs() if r["tipo"] == "danza_diosa"]
        self.assertEqual(len(gd), 1)
        self.assertEqual(sorted(gd[0]["objetivos"]), ["Diamant", "Lapis"])
        self.assertEqual(sorted(j["enemigo"] for j in gd[0]["jugadas_siguientes"]), ["Axe Fighter A", "Axe Fighter B"])


if __name__ == "__main__":
    unittest.main()
