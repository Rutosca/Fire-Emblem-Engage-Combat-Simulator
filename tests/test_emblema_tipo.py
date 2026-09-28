"""
Tipo de emblema del modal: "Normal" u "Oscuro".

  - Normal: el Emblema de siempre (vínculo, medidor y Fusión; sus bonos de vínculo los
    suma el propio modal a las stats).
  - Oscuro: la versión corrupta de ese Emblema en el capítulo activo (o la más reciente
    anterior: en el Cap. 22 los aliados pueden llevar anillos oscuros). Siempre fusionada,
    sin vínculo ni medidor; sus bonos, armas y habilidades los pone el servidor.

Los enemigos llevan Oscuro por defecto y los aliados Normal (lo decide el modal).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import app, tablero, _desplegar_capitulo  # noqa: E402
from catalogo_loader import _emblema_oscuro_de  # noqa: E402
from cargador_dispos import DISPOS_DIR  # noqa: E402


def _payload(f, emblema, tipo):
    """Lo que manda el modal al guardar: stats, habilidades e inventario tal como se ven."""
    d = f.como_dict()
    s = d["stats"]
    return {
        "nombre": f.nombre, "es_aliado": f.es_aliado, "pid": d["pid"], "x": f.x, "y": f.y,
        "nivel": f.nivel, "clase_nombre": f.clase_nombre, "arma_nombre": f.arma.nombre,
        "emblema_nombre": emblema, "emblema_tipo": tipo if emblema else "",
        "hp_actual": f.hp_actual, "hp_max": f.hp_max, "mov": f.mov,
        "stats": {k: s[k] for k in ("hp", "hp_max", "fuerza", "magia", "destreza", "velocidad",
                                    "defensa", "resistencia", "suerte", "complexion")},
        "habilidades": list(f.habilidades), "inventario": d["inventario"],
    }


@unittest.skipUnless(os.path.isdir(DISPOS_DIR), "sin datamine (dispos)")
class TestTipoDeEmblema(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()
        cls.client.post("/api/mapa/seleccionar", json={"capitulo": 11})

    @classmethod
    def tearDownClass(cls):
        app.test_client().post("/api/mapa/seleccionar", json={"capitulo": 7})

    def setUp(self):
        _desplegar_capitulo("M011", "Extremo")

    def _guardar(self, nombre, emblema, tipo):
        r = self.client.post("/api/unidad/guardar", json=_payload(tablero.obtener_ficha(nombre), emblema, tipo))
        self.assertEqual(r.status_code, 200, r.get_json())
        return tablero.obtener_ficha(nombre)

    def test_el_estado_dice_si_es_oscuro_y_su_emblema_base(self):
        d = tablero.obtener_ficha("Sword Flier (2,12)").como_dict()
        self.assertEqual((d["emblema_oscuro"], d["emblema_base"], d["emblema_nombre"]),
                         (True, "Marth", "Marth (Oscuro)"))

    def test_guardar_sin_cambios_no_suma_otra_vez_el_anillo(self):
        antes = tablero.obtener_ficha("Sword Flier (2,12)")
        vel, arma = antes.stats.velocidad, antes.arma.nombre
        f = self._guardar("Sword Flier (2,12)", "Marth", "oscuro")
        self.assertEqual((f.emblema_id, f.stats.velocidad, f.arma.nombre), ("GID_M011_敵マルス", vel, arma))

    def test_poner_un_anillo_oscuro_desde_el_modal(self):
        """Roy (Oscuro) del Cap. 11: +7 HP, +3 Fue, +2 Def, Lancereaver equipada, Hold Out+ y Sink Below."""
        antes = tablero.obtener_ficha("Sword Fighter (7,1)")
        hp, fue, dfn = antes.hp_max, antes.stats.fuerza, antes.stats.defensa
        f = self._guardar("Sword Fighter (7,1)", "Roy", "oscuro")
        self.assertEqual(f.emblema_id, "GID_M011_敵ロイ")
        self.assertTrue(f.emblema_oscuro)
        self.assertEqual((f.hp_max, f.stats.fuerza, f.stats.defensa), (hp + 7, fue + 3, dfn + 2))
        self.assertEqual(f.arma.nombre, "Lancereaver")
        self.assertTrue({"Hold Out+", "Sink Below"} <= set(f.habilidades))

    def test_quitar_el_anillo_lo_deja_como_sin_el(self):
        f = self._guardar("Sword Flier (2,12)", "", "")
        self.assertEqual(f.emblema_id, "")
        self.assertEqual((f.stats.fuerza, f.stats.destreza, f.stats.velocidad), (12, 16, 17))
        self.assertEqual(f.arma.nombre, "Steel Sword")
        self.assertEqual([i.get("nombre") for i in f.inventario], ["Steel Sword"])
        self.assertFalse({"Unyielding+", "Divine Speed"} & set(f.habilidades))

    def test_cambiar_un_anillo_oscuro_por_otro(self):
        f = self._guardar("Sword Flier (2,12)", "Roy", "oscuro")
        self.assertEqual(f.emblema_id, "GID_M011_敵ロイ")
        # Marth daba +2 Fue +3 Des +3 Vel; Roy da +7 HP +3 Fue +2 Def
        self.assertEqual((f.stats.fuerza, f.stats.destreza, f.stats.velocidad), (15, 16, 17))
        self.assertEqual(f.arma.nombre, "Lancereaver")
        self.assertNotIn("Rapier", [i.get("nombre") for i in f.inventario])

    def test_tipo_normal_es_el_emblema_de_siempre(self):
        f = self._guardar("Sword Fighter (7,1)", "Marth", "normal")
        self.assertEqual(f.emblema_id, "GID_マルス")
        self.assertFalse(f.emblema_oscuro)

    def test_oscuro_sin_version_en_el_capitulo_usa_la_anterior(self):
        """Cap. 22: no hay Marth oscuro propio; se usa el más reciente anterior (Cap. 21)."""
        self.assertEqual(_emblema_oscuro_de("Marth", "M022")[0], "GID_M021_敵マルス")
        self.assertEqual(_emblema_oscuro_de("Marth", "M011")[0], "GID_M011_敵マルス")
        self.assertEqual(_emblema_oscuro_de("Edelgard", "M011")[0], "GID_E006_敵エーデルガルト")
        self.assertEqual(_emblema_oscuro_de("Alear", "M011"), ("", None))


if __name__ == "__main__":
    unittest.main()
