"""
Recolección de SIDs activos (pasivas.sids_activos): la lista que el motor de
pasivas ve debe ser la misma que aplica el juego — personales, de clase,
sincronía por nivel de vínculo, de Fusión solo en Fusión, nombres del roster
resueltos a SID y variante por estilo de combate.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pasivas
from catalogo_loader import resolver_unidad_con_catalogo


def _alear(**extra):
    data = {
        "nombre": "Alear", "es_aliado": True, "x": 3, "y": 7,
        "clase_id": "JID_神竜ノ子", "nivel": 9,
        "emblema_id": "GID_マルス", "nivel_vinculo": 10,
        "habilidades": ["Canter"],
        "inventario": [{"arma": "Libération", "equipada": True}],
        "dificultad": "Extremo",
    }
    data.update(extra)
    return resolver_unidad_con_catalogo(data)


class TestResolverNombre(unittest.TestCase):

    def test_nombre_visible_a_sid_base(self):
        self.assertEqual(pasivas.resolver_nombre_a_sid("Canter"), "SID_再移動")
        self.assertEqual(pasivas.resolver_nombre_a_sid("canter+"), "SID_再移動＋")
        self.assertEqual(pasivas.resolver_nombre_a_sid("Momentum"), "SID_助走")

    def test_sid_directo_y_desconocidos(self):
        self.assertEqual(pasivas.resolver_nombre_a_sid("SID_見切り"), "SID_見切り")
        self.assertIsNone(pasivas.resolver_nombre_a_sid("SID_inventado"))
        self.assertIsNone(pasivas.resolver_nombre_a_sid("Weapon Sync"))   # DLC sin datamine
        self.assertIsNone(pasivas.resolver_nombre_a_sid(""))

    def test_variantes_de_estilo_no_se_eligen_por_nombre(self):
        # "Divine Speed" tiene SID base y variantes _隠密 / _竜族: por nombre, la base.
        self.assertEqual(pasivas.resolver_nombre_a_sid("Divine Speed"), "SID_カウンター")

    def test_heredada_prefiere_variante_de_herencia(self):
        base = pasivas.resolver_nombre_a_sid("Luck +2")
        her = pasivas.resolver_nombre_a_sid("Luck +2", heredada=True)
        self.assertEqual(base, "SID_幸運＋２")
        self.assertEqual(her, "SID_幸運＋２_継承用")


class TestSidsActivos(unittest.TestCase):

    def test_sincronia_por_vinculo_y_personal_y_roster(self):
        f = _alear()
        activos = pasivas.sids_activos(f)
        # Sincronía de Marth a vínculo 10: Perceptive, Break Defenses, Unyielding
        for sid in ("SID_見切り", "SID_ブレイク時追撃", "SID_不屈"):
            self.assertIn(sid, activos, sid)
        self.assertIn("SID_神竜の結束", activos)   # personal (Divinely Inspiring)
        self.assertIn("SID_再移動", activos)       # "Canter" del roster, resuelto por nombre

    def test_vinculo_bajo_no_da_sincronias_altas(self):
        f = _alear(nivel_vinculo=1)
        activos = pasivas.sids_activos(f)
        self.assertIn("SID_見切り", activos)
        self.assertNotIn("SID_ブレイク時追撃", activos)
        self.assertNotIn("SID_不屈", activos)

    def test_habilidades_de_fusion_solo_en_fusion(self):
        f = _alear(habilidades=["Canter", "Divine Speed", "Engage Attack Guard"])
        self.assertIn("SID_カウンター", f.stats.habilidades_sids_fusion)
        sin = pasivas.sids_activos(f)
        self.assertFalse(any(s.startswith("SID_カウンター") for s in sin), sin)
        self.assertNotIn("SID_敵エンゲージ技ダメージ軽減", sin)
        f.stats.en_fusion = True
        con = pasivas.sids_activos(f)
        self.assertIn("SID_敵エンゲージ技ダメージ軽減", con)
        self.assertTrue(any(s.startswith("SID_カウンター") for s in con), con)

    def test_variante_por_estilo_de_combate(self):
        f = _alear()
        f.stats.en_fusion = True
        # Alear (Dragon Child, 竜族スタイル): Divine Speed en su variante de estilo
        self.assertIn("SID_カウンター_竜族", pasivas.sids_activos(f))
        self.assertNotIn("SID_カウンター", pasivas.sids_activos(f))
        self.assertIn("SID_カウンター", pasivas.sids_activos(f, incluir_variantes_estilo=False))
        self.assertEqual(pasivas.variante_por_estilo("SID_カウンター", "隠密スタイル"), "SID_カウンター_隠密")
        self.assertEqual(pasivas.variante_por_estilo("SID_カウンター", "騎馬スタイル"), "SID_カウンター")   # sin variante
        self.assertEqual(pasivas.variante_por_estilo("SID_見切り", "竜族スタイル"), "SID_見切り")

    def test_estados_temporales_cuentan_como_activos(self):
        f = _alear()
        f.otorgar_estado_temporal("SID_僕が守ります！効果", "Get Behind Me!", {"str": 3}, "enemigo", 2)
        self.assertIn("SID_僕が守ります！効果", pasivas.sids_activos(f))
        self.assertTrue(pasivas.tiene_sid(f, "SID_僕が守ります！効果"))

    def test_sin_duplicados_y_acepta_stats_o_ficha(self):
        f = _alear(habilidades=["Canter", "Perceptive", "SID_見切り"])
        activos = pasivas.sids_activos(f)
        self.assertEqual(len(activos), len(set(activos)))
        self.assertEqual(activos, pasivas.sids_activos(f.stats))


if __name__ == "__main__":
    unittest.main()
