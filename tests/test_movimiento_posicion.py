"""
Movimiento y posicionamiento: BFS con bloqueo enemigo, casilla de ataque
ocupada, elección de casilla segura y penalización de líneas de peligro.

Origen: tests/test_fixes_tactical.py (partido por dominio el 2026-09-18).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import app, tablero, _mapa, resolver_unidad_con_catalogo, encontrar_pos_ataque_optima  # noqa: E402


class TestMovimientoPosicion(unittest.TestCase):

    def setUp(self):
        # resolver_unidad_con_catalogo lee app.tablero para heredar estado: empezar siempre limpio
        tablero.limpiar()

    def test_casilla_de_ataque_ocupada_por_aliado_rechaza_ataque(self):
        """Si la casilla de ataque está ocupada por otro aliado, no puede atacar ni proponer la jugada."""
        tablero.limpiar()
        # Aliado 1 en (2, 2), mov 1, arma rango 1
        a1 = resolver_unidad_con_catalogo({
            "nombre": "TestAlly1", "x": 2, "y": 2, "mov": 1, "es_aliado": True,
            "arma_nombre": "Iron Sword", "stats": {"hp": 20, "fuerza": 10, "velocidad": 10}
        })
        tablero.registrar_unidad(a1)

        # Enemigo en (2, 4)
        ene = resolver_unidad_con_catalogo({
            "nombre": "TestEnemy", "x": 2, "y": 4, "mov": 4, "es_aliado": False,
            "arma_nombre": "Iron Lance", "stats": {"hp": 20, "defensa": 5}
        })
        tablero.registrar_unidad(ene)

        # Aliado 2 ocupando la única casilla desde la que A1 podría atacar a distancia 1: (2, 3)
        a2 = resolver_unidad_con_catalogo({
            "nombre": "TestAlly2", "x": 2, "y": 3, "mov": 4, "es_aliado": True,
            "arma_nombre": "Iron Sword", "stats": {"hp": 20}
        })
        tablero.registrar_unidad(a2)

        # Desde (2,2) con mov 1 y rango 1:
        # Casilla alcanzable (2,3) está ocupada por TestAlly2.
        # Por tanto, TestAlly1 NO tiene casilla física libre para atacar a TestEnemy.
        pos_sug = encontrar_pos_ataque_optima(a1, ene, a1.arma)
        self.assertIsNone(pos_sug, "Debe ser None porque la única casilla alcanzable (2,3) está ocupada")

        # Probar endpoint API /api/combate/ejecutar intentando atacar forzadamente
        client = app.test_client()

        # Intento A: pasar pos_destino (2,3) que está ocupada por TestAlly2
        res_occ = client.post("/api/combate/ejecutar", json={
            "atacante": "TestAlly1",
            "defensor": "TestEnemy",
            "arma_nombre": "Iron Sword",
            "pos_destino": [2, 3]
        })
        self.assertEqual(res_occ.status_code, 400, "Debe rechazar ataque hacia casilla ocupada")
        self.assertIn("ocupada", res_occ.get_json()["error"])

        # Intento B: atacar sin pos_destino quedando en (2,2) que está a distancia 2 con espada rango [1]
        res_range = client.post("/api/combate/ejecutar", json={
            "atacante": "TestAlly1",
            "defensor": "TestEnemy",
            "arma_nombre": "Iron Sword"
        })
        self.assertEqual(res_range.status_code, 400, "Debe rechazar ataque fuera de rango (ataque fantasma)")
        err_msg = res_range.get_json()["error"]
        self.assertTrue("no alcanza" in err_msg or "fuera de rango" in err_msg, f"Error inesperado: {err_msg}")

        # Verificar que el enemigo no recibió daño alguno
        self.assertEqual(tablero.obtener_ficha("TestEnemy").hp_actual, 20)

    def test_enemigo_bloquea_paso_en_bfs(self):
        """Un enemigo bloquea el paso físico (BFS) impidiendo rodearlo si no tiene espacio."""
        tablero.limpiar()
        # Aliado en (0, 0), mov 3, terreno transitable
        a = resolver_unidad_con_catalogo({
            "nombre": "Infanteria", "x": 0, "y": 0, "mov": 3, "es_aliado": True,
            "arma_nombre": "Iron Sword", "habilidades": []
        })
        tablero.registrar_unidad(a)

        # Enemigo bloqueando el único camino en (1, 0)
        e = resolver_unidad_con_catalogo({
            "nombre": "Bloqueador", "x": 1, "y": 0, "mov": 0, "es_aliado": False,
            "arma_nombre": "Iron Lance"
        })
        tablero.registrar_unidad(e)

        # Enemigo objetivo detrás en (2, 0)
        obj = resolver_unidad_con_catalogo({
            "nombre": "Objetivo", "x": 2, "y": 0, "mov": 0, "es_aliado": False,
            "arma_nombre": "Iron Lance"
        })
        tablero.registrar_unidad(obj)

        pos_sug = encontrar_pos_ataque_optima(a, obj, a.arma)
        if pos_sug is not None:
            self.assertNotEqual(pos_sug, [1, 0], "Jamás puede pisar o atacar desde la casilla del enemigo bloqueador")

    def test_posicion_optima_prefiere_rango_sin_contraataque(self):
        """
        Verifica que el optimizador de posiciones elija casillas seguras sin contraataque:
        1. Aliado con Javelin (1-2) ataca a enemigo con Espada (1):
           Si el aliado está en rango, prefiere casilla a distancia 2 para NO sufrir contraataque.
        2. Aliado con Espada (1) o Javelin (1-2) ataca a Arquero enemigo (2):
           Prefiere casilla a distancia 1 para que el arquero NO pueda contraatacar.
        """
        tablero.limpiar()

        # Aliado: Chloé con Javelin en (5, 4), mov 5
        chloe_ficha = resolver_unidad_con_catalogo({
            "nombre": "Chloé", "x": 5, "y": 4, "mov": 5, "es_aliado": True,
            "arma_nombre": "Javelin", "stats": {"hp": 28, "fuerza": 12, "velocidad": 15, "defensa": 8}
        })
        tablero.registrar_unidad(chloe_ficha)

        # Enemigo: Sword Fighter en (5, 5) con Iron Sword (rango 1)
        ene_sword = resolver_unidad_con_catalogo({
            "nombre": "Sword Fighter", "x": 5, "y": 5, "mov": 4, "es_aliado": False,
            "arma_nombre": "Iron Sword", "stats": {"hp": 25, "fuerza": 10, "velocidad": 12, "defensa": 6}
        })
        tablero.registrar_unidad(ene_sword)

        # Chloé está actualmente a distancia 1 (5,4) de (5,5).
        # Pero con Javelin puede atacar a distancia 2.
        # La posición óptima debe ser a distancia 2 (por ej. 5,3) para evitar el contragolpe de Iron Sword.
        pos_optima = encontrar_pos_ataque_optima(chloe_ficha, ene_sword, chloe_ficha.arma, mapa=_mapa, tablero=tablero)
        self.assertIsNotNone(pos_optima)
        dist_elegida = abs(pos_optima[0] - ene_sword.x) + abs(pos_optima[1] - ene_sword.y)
        self.assertEqual(dist_elegida, 2, f"Chloé con Javelin debería colocarse a distancia 2 para atacar sin recibir contraataque. Eligió {pos_optima} (dist {dist_elegida})")

        # Caso 2: Atacar a un Arquero enemigo con Iron Bow (rango 2)
        tablero.limpiar()
        ene_archer = resolver_unidad_con_catalogo({
            "nombre": "Bow Fighter", "x": 5, "y": 5, "mov": 4, "es_aliado": False,
            "arma_nombre": "Iron Bow", "stats": {"hp": 22, "fuerza": 11, "velocidad": 10, "defensa": 5}
        })
        tablero.registrar_unidad(ene_archer)
        tablero.registrar_unidad(chloe_ficha)

        # Chloé con Javelin atacando al arquero debe preferir distancia 1 (el arquero NO puede contraatacar a dist 1)
        pos_opt_archer = encontrar_pos_ataque_optima(chloe_ficha, ene_archer, chloe_ficha.arma, mapa=_mapa, tablero=tablero)
        self.assertIsNotNone(pos_opt_archer)
        dist_elegida_arc = abs(pos_opt_archer[0] - ene_archer.x) + abs(pos_opt_archer[1] - ene_archer.y)
        self.assertEqual(dist_elegida_arc, 1, f"Chloé debería colocarse a distancia 1 contra el arquero para que no pueda contraatacar. Eligió {pos_opt_archer} (dist {dist_elegida_arc})")

    def test_posicion_optima_evita_lineas_de_peligro(self):
        """
        Verifica que el optimizador de casillas de ataque penalice casillas en zona de peligro (Líneas de peligro de Engage):
        - Alear en (2, 8) con Iron Sword (rango 1, mov 4).
        - Objetivo: Lance Fighter en (4, 8) con Iron Lance.
        - Sin amenazas: Alear prefiere la casilla natural de menor coste de pasos: [3, 8].
        - Con zona de amenaza sobre [3, 8]: Alear se reubica automáticamente a una casilla segura libre de peligro: [4, 9].
        - En el análisis táctico global: la jugada reporta num_amenazas_destino y texto de casilla segura.
        """
        tablero.limpiar()

        alear = resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 2, "y": 8, "mov": 4, "es_aliado": True,
            "arma_nombre": "Iron Sword", "stats": {"hp": 25, "fuerza": 12, "velocidad": 12, "defensa": 8}
        })
        tablero.registrar_unidad(alear)

        lance_fighter = resolver_unidad_con_catalogo({
            "nombre": "Lance Fighter (4,8)", "x": 4, "y": 8, "mov": 0, "es_aliado": False,
            "arma_nombre": "Iron Lance", "stats": {"hp": 30, "fuerza": 10, "velocidad": 8, "defensa": 6}
        })
        tablero.registrar_unidad(lance_fighter)

        # 1. Sin peligro externo: debe elegir [3, 8]
        pos_sin_amenaza = encontrar_pos_ataque_optima(alear, lance_fighter, alear.arma, mapa=_mapa, tablero=tablero)
        self.assertEqual(pos_sin_amenaza, [3, 8], f"Sin amenazas debería elegir [3, 8], eligió: {pos_sin_amenaza}")

        # 2. Con zona de amenaza sobre [3, 8]: debe elegir una alternativa segura ([4, 9])
        amenazas_externas = {"MagoPeligroso": {(3, 8)}}
        pos_con_amenaza = encontrar_pos_ataque_optima(
            alear, lance_fighter, alear.arma, mapa=_mapa, tablero=tablero,
            zonas_amenaza_enemigos=amenazas_externas
        )
        self.assertNotEqual(pos_con_amenaza, [3, 8], "No debe elegir la casilla [3, 8] porque está en zona de amenaza")
        self.assertEqual(pos_con_amenaza, [4, 9], f"Debe elegir la casilla segura [4, 9], eligió: {pos_con_amenaza}")

        # 3. Verificación de metadata en el análisis táctico
        from motor_analisis import analizar_situacion_tactica
        recs = analizar_situacion_tactica(tablero=tablero, mapa=_mapa)
        ops_alear = [r for r in recs["resultados"] if r.get("tipo_analisis") == "oportunidad_jugador" and r.get("aliado") == "Alear"]
        self.assertTrue(len(ops_alear) > 0)
        # Como el enemigo sobrevive al combate, sigue representando 1 amenaza en la fase enemiga
        self.assertEqual(ops_alear[0]["num_amenazas_destino"], 1)
        self.assertIn("Lance Fighter (4,8)", ops_alear[0]["amenazas_en_destino"])
        self.assertNotIn("Al alcance de 1 enemigo", ops_alear[0]["recomendacion"])

        # 4. Verificación cuando el ataque es un CLEAN KILL (100% Hit y letal)
        # El enemigo muerto desaparece de las amenazas en la casilla de destino
        lance_fighter.stats.hp = 10
        lance_fighter.hp_actual = 10
        alear.stats.fuerza = 25
        alear.stats.destreza = 30
        recs_kill = analizar_situacion_tactica(tablero=tablero, mapa=_mapa)
        ops_kill = [r for r in recs_kill["resultados"] if r.get("tipo_analisis") == "oportunidad_jugador" and r.get("aliado") == "Alear"]
        self.assertTrue(len(ops_kill) > 0)
        self.assertEqual(ops_kill[0]["num_amenazas_destino"], 0)
        self.assertEqual(ops_kill[0]["amenazas_en_destino"], [])
        self.assertNotIn("Casilla segura (0 amenazas enemigas)", ops_kill[0]["recomendacion"])

    def test_ataque_expuesto_a_4_enemigos_se_descarta(self):
        """Un ataque que deja expuesta a la unidad ante 4 o más enemigos debe descartarse por suicida."""
        tablero.limpiar()
        target = resolver_unidad_con_catalogo({
            "nombre": "TargetEnemy", "x": 5, "y": 5, "mov": 4, "es_aliado": False,
            "arma_nombre": "Iron Lance", "stats": {"hp": 10, "hp_max": 10, "defensa": 0}
        })
        tablero.registrar_unidad(target)

        alear = resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 5, "y": 3, "mov": 4, "es_aliado": True,
            "arma_nombre": "Liberation", "stats": {"hp": 20, "fuerza": 15, "velocidad": 10, "estilo_combate": "Dragon"}
        })
        tablero.registrar_unidad(alear)

        # 4 enemigos adicionales cubren la casilla (5,4)
        for i, pos in enumerate([(4,4), (6,4), (5,5), (4,3)]):
            if pos != (5,5):
                e = resolver_unidad_con_catalogo({
                    "nombre": f"PackEnemy_{i}", "x": pos[0], "y": pos[1], "mov": 4, "es_aliado": False,
                    "arma_nombre": "Iron Lance", "stats": {"hp": 30, "fuerza": 12, "velocidad": 10, "defensa": 10}
                })
                tablero.registrar_unidad(e)

        client = app.test_client()
        res = client.post("/api/analizar", json={"perfil": "seguro"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        ops_alear = [r for r in data["resultados"] if r.get("aliado") == "Alear" and r.get("tipo_analisis") == "oportunidad_jugador"]
        self.assertEqual(len(ops_alear), 0, "No debe recomendar un ataque en una casilla expuesta a 4 o más enemigos")

if __name__ == "__main__":
    unittest.main()
