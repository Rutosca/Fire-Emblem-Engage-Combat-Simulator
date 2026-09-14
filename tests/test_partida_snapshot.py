"""
Test de importación y exportación de partida como fotografía exacta del estado actual.
Verifica que las unidades muertas y restos de presets no resuciten ni se mezclen en el tablero.
"""

import json
import os
import unittest
from app import app, tablero, _mapa


class TestPartidaSnapshot(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        path_partida = os.path.join("scratch", "partida_usuario.json")
        self.assertTrue(os.path.exists(path_partida), f"No se encontró {path_partida}")
        with open(path_partida, "r", encoding="utf-8") as f:
            self.data_raw = json.load(f)

    def _importar_partida_usuario(self):
        return self.client.post("/api/partida/importar", json={"partida": self.data_raw})

    def test_1_importar_partida_usuario_fotografia(self):
        """
        Verifica que al importar una partida real del turno 10:
        1. Se limpian todos los presets y unidades anteriores.
        2. No resucitan las 23 unidades derrotadas en turnos previos.
        3. Se colocan exactamente las 15 unidades vivas en sus casillas exactas.
        4. No hay sobreescritura destructiva por colisiones con unidades muertas.
        5. El turno y fase se restauran fielmente (Turno 10, Fase Jugador).
        """
        # 1. Importar la partida a través del endpoint REST
        res = self._importar_partida_usuario()
        self.assertEqual(res.status_code, 200)
        res_json = res.get_json()
        self.assertTrue(res_json.get("ok"))

        # 2. Comprobar que en el tablero y en la respuesta hay EXACTAMENTE 15 unidades
        fichas_resp = res_json.get("fichas", [])
        self.assertEqual(len(fichas_resp), 15, f"Debían haber 15 unidades vivas, pero hay {len(fichas_resp)}")
        self.assertEqual(len(tablero.fichas), 15, f"En tablero.fichas debían haber 15, pero hay {len(tablero.fichas)}")

        # 3. Comprobar que todas las fichas en el tablero están vivas y con HP > 0
        for nombre, ficha in tablero.fichas.items():
            self.assertTrue(ficha.viva, f"La ficha {nombre} debería tener viva=True")
            self.assertGreater(ficha.hp_actual, 0, f"La ficha {nombre} debería tener HP > 0")

        # 4. Comprobar que unidades muertas específicas del capítulo NO están en el tablero
        muertas_esperadas = [
            "Lance Armor (6,6)", "Lance Fighter (10,6)", "Lance Fighter (10,5)",
            "Lance Fighter (6,10)", "Sword Flier (7,12)", "Mage (12,11)",
            "Mage (12,12)", "Sword Armor (16,7)", "Martial Monk (16,8)",
            "Archer (18,5)", "Axe Cavalier (14,7)"
        ]
        for nom_m in muertas_esperadas:
            self.assertNotIn(nom_m, tablero.fichas, f"La unidad derrotada {nom_m} no debería estar en el tablero")

        # 5. Comprobar unidades vivas clave y casillas donde antes había colisión con muertas
        # Céline en (12,7) — coincidía con Sword Armor (16,7)
        celine = tablero.obtener_ficha("Céline")
        self.assertIsNotNone(celine, "Céline debe existir en el tablero")
        self.assertEqual((celine.x, celine.y), (12, 7))
        self.assertEqual(celine.hp_actual, 22)
        self.assertEqual(celine.hp_max, 25)

        # Lapis en (13,9) — coincidía con Martial Monk (16,8)
        lapis = tablero.obtener_ficha("Lapis")
        self.assertIsNotNone(lapis, "Lapis debe existir en el tablero")
        self.assertEqual((lapis.x, lapis.y), (13, 9))
        self.assertEqual(lapis.hp_actual, 26)

        # Chloé en (13,8) — coincidía con Archer (18,5)
        chloe = tablero.obtener_ficha("Chloé")
        self.assertIsNotNone(chloe, "Chloé debe existir en el tablero")
        self.assertEqual((chloe.x, chloe.y), (13, 8))
        self.assertEqual(chloe.hp_actual, 27)
        self.assertEqual(chloe.hp_max, 29)

        # Louis herido en (15,8)
        louis = tablero.obtener_ficha("Louis")
        self.assertIsNotNone(louis, "Louis debe existir en el tablero")
        self.assertEqual((louis.x, louis.y), (15, 8))
        self.assertEqual(louis.hp_actual, 10)
        self.assertEqual(louis.hp_max, 31)

        # Hortensia y jefes
        hortensia = tablero.obtener_ficha("Hortensia (Boss)")
        self.assertIsNotNone(hortensia, "Hortensia debe existir en el tablero")
        self.assertEqual((hortensia.x, hortensia.y), (16, 8))
        self.assertEqual(hortensia.hp_actual, 36)

        rosado = tablero.obtener_ficha("Rosado")
        self.assertIsNotNone(rosado, "Rosado debe existir en el tablero")
        self.assertEqual((rosado.x, rosado.y), (16, 6))

        goldmary = tablero.obtener_ficha("Goldmary")
        self.assertIsNotNone(goldmary, "Goldmary debe existir en el tablero")
        self.assertEqual((goldmary.x, goldmary.y), (18, 9))

        # 6. Turno y fase
        self.assertEqual(tablero.turno_actual, 10)
        self.assertEqual(tablero.fase, "jugador")

    def test_2_exportar_partida_fotografia_limpia(self):
        """
        Verifica que /api/partida/exportar produzca una fotografía limpia
        sin fichas derrotadas ni datos obsoletos.
        """
        self._importar_partida_usuario()
        res_exp = self.client.get("/api/partida/exportar")
        self.assertEqual(res_exp.status_code, 200)
        exp_json = res_exp.get_json()
        self.assertTrue(exp_json.get("ok"))
        partida = exp_json.get("partida", {})

        self.assertEqual(partida.get("turno_actual"), 10)
        self.assertEqual(partida.get("fase"), "jugador")
        fichas_exp = partida.get("fichas", [])
        self.assertEqual(len(fichas_exp), 15)

        for f in fichas_exp:
            self.assertTrue(f.get("viva"))
            self.assertGreater(f.get("hp_actual", 0), 0)

    def test_3_analisis_tactico_en_partida_importada(self):
        """
        Verifica que /api/analizar opere con total normalidad sobre la situación
        real importada del turno 10.
        """
        self._importar_partida_usuario()
        res_an = self.client.post("/api/analizar", json={"perfil": "seguro"})
        self.assertEqual(res_an.status_code, 200)
        an_json = res_an.get_json()
        resultados = an_json.get("resultados", [])
        self.assertGreater(len(resultados), 0, "Debe haber recomendaciones tácticas disponibles")

        # Debe sugerir curar a Louis (que tiene solo 10 HP)
        sugiere_curar = any(
            r.get("tipo_analisis") in ("apoyo_curacion", "sanacion", "uso_pocion") and (r.get("objetivo") == "Louis" or r.get("aliado") == "Louis")
            for r in resultados
        )
        self.assertTrue(sugiere_curar, "El análisis táctico debe identificar que Louis necesita curación")


if __name__ == "__main__":
    unittest.main()
