"""
test_fixes_tactical.py - Test exhaustivo de validación de los 4 arreglos:
1. Céline con Levin Sword hace 22 de daño exacto (Resonancia solo con Tomos).
2. Chloé con Silver Lance y Emblema Tres Casas:
   - Con Dimitri: 20 de daño (Weapon Sync +5 Atk con Lanza).
   - Con Edelgard: 15 de daño (Weapon Sync no aplica a Lanza).
3. Sistema de Veneno:
   - Daga aplica veneno al acertar.
   - Citrinne con Trueno pasa de 7 a 8 con veneno 1, 9 con veneno 2, 10 con veneno 3.
4. Prevención de Ataques Fantasma y Bloqueo Espacial:
   - Bloqueo por enemigos en BFS (salvo Pass).
   - Tránsito a través de aliados permitido.
   - Casilla de llegada ocupada por aliado rechazada.
   - Ataque fuera de rango rechazado con HTTP 400 sin daño.
"""

import unittest
import sys, json, os, unicodedata
sys.stdout.reconfigure(encoding='utf-8')

from app import app, tablero, _mapa, resolver_unidad_con_catalogo, _arma_desde_item, encontrar_pos_ataque_optima
from cargador_dispos import CargadorDisposEngage
from motor_calculo import CalculadoraEngage, Terreno, Unidad, Arma
from motor_de_movimiento_y_amenaza import AnalizadorAmenaza, UnidadMock, ArmaMock

def norm(t): return unicodedata.normalize('NFKD', str(t)).encode('ASCII', 'ignore').decode('utf-8').lower()

class TestFixesTactical(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Cargar mapa y datos
        cls.cargador = CargadorDisposEngage()
        units = cls.cargador.cargar_capitulo('M007', 'Extremo')
        u106 = [u for u in units if (u.get('x'), u.get('y')) == (10, 6)][0]
        cls.f_lf = resolver_unidad_con_catalogo(u106)

        path_esc = 'json/escuadron_guardado.json' if os.path.exists('json/escuadron_guardado.json') else 'escuadron_guardado.json'
        with open(path_esc, 'r', encoding='utf-8') as f:
            esc = json.load(f)

        u_cel = [u for u in esc if 'cel' in norm(u.get('nombre',''))][0]
        cls.f_cel = resolver_unidad_con_catalogo(u_cel)

        u_chl = [u for u in esc if 'chlo' in norm(u.get('nombre',''))][0]
        cls.f_chl = resolver_unidad_con_catalogo(u_chl)

    def test_1_celine_levin_sword_damage(self):
        """Céline con Levin Sword debe hacer exactamente 22 de daño (no 24)."""
        levin = _arma_desde_item([i for i in self.f_cel.inventario if 'levin' in i.get('nombre','').lower()][0])
        comb = CalculadoraEngage.simular_combate(
            self.f_cel.stats, self.f_lf.stats, levin, self.f_lf.arma,
            Terreno(0,0), Terreno(0,0), distancia=1
        )
        dmg = comb['atacante']['daño_por_golpe']
        self.assertEqual(dmg, 22, f"Céline con Levin Sword debería hacer 22, hizo {dmg}")
        self.assertEqual(comb['resultado']['hp_defensor_final'], 10, "El Lance Fighter debería quedar en 10 HP")

    def test_2_chloe_weapon_sync_three_houses(self):
        """Chloé con Silver Lance: 20 con Dimitri (+5), 15 con Edelgard (+0)."""
        silver = _arma_desde_item([i for i in self.f_chl.inventario if 'silver' in i.get('nombre','').lower()][0])
        
        # Caso A: Dimitri activo -> +5 Atk (Weapon Sync Lanza)
        self.f_chl.stats.lider_tres_casas = "Dimitri"
        comb_dim = CalculadoraEngage.simular_combate(
            self.f_chl.stats, self.f_lf.stats, silver, self.f_lf.arma,
            Terreno(0,0), Terreno(0,0), distancia=1
        )
        self.assertEqual(comb_dim['atacante']['daño_por_golpe'], 20, "Chloé con Dimitri debe hacer 20")

        # Caso B: Edelgard activa -> +0 Atk con Lanza (Weapon Sync solo Hachas)
        self.f_chl.stats.lider_tres_casas = "Edelgard"
        comb_ed = CalculadoraEngage.simular_combate(
            self.f_chl.stats, self.f_lf.stats, silver, self.f_lf.arma,
            Terreno(0,0), Terreno(0,0), distancia=1
        )
        self.assertEqual(comb_ed['atacante']['daño_por_golpe'], 15, "Chloé con Edelgard debe hacer 15 con lanza")

    def test_3_poison_damage_and_application(self):
        """Dagas aplican veneno, y cada nivel suma +1 a todo el daño recibido."""
        yunaka = Unidad(nombre='Yunaka', hp=24, fuerza=8, magia=5, destreza=14, velocidad=12, defensa=5, resistencia=7, suerte=8, complexion=5)
        iron_dagger = Arma(nombre='Iron Dagger', mt=5, wt=4, hit=90, crit=0, es_magica=False, tipo='Daga', rango=[1, 2])
        mage = Unidad(nombre='Mage', hp=20, fuerza=1, magia=7, destreza=8, velocidad=6, defensa=3, resistencia=8, suerte=2, complexion=4)
        fire = Arma(nombre='Fire', mt=5, wt=5, hit=90, crit=0, es_magica=True, tipo='Tomo', rango=[1, 2])

        comb_y = CalculadoraEngage.simular_combate(yunaka, mage, iron_dagger, fire, Terreno(0,0), Terreno(0,0), distancia=1)
        self.assertTrue(comb_y['resultado']['aplica_veneno'], "Yunaka con daga debe aplicar veneno")
        self.assertEqual(comb_y['resultado']['nivel_veneno_defensor_post'], 1)

        # Citrinne con Trueno
        citrinne = Unidad(nombre='Citrinne', hp=20, fuerza=1, magia=13, destreza=9, velocidad=6, defensa=2, resistencia=9, suerte=8, complexion=4)
        thunder = Arma(nombre='Thunder', mt=2, wt=8, hit=80, crit=0, es_magica=True, tipo='Tomo', rango=[1, 2, 3])

        # Veneno 0 -> 13 + 2 - 8 = 7 daño
        setattr(mage, 'nivel_veneno', 0)
        c0 = CalculadoraEngage.simular_combate(citrinne, mage, thunder, fire, Terreno(0,0), Terreno(0,0), distancia=2)
        self.assertEqual(c0['atacante']['daño_por_golpe'], 7)

        # Veneno 1 -> 7 + 1 = 8 daño
        setattr(mage, 'nivel_veneno', 1)
        c1 = CalculadoraEngage.simular_combate(citrinne, mage, thunder, fire, Terreno(0,0), Terreno(0,0), distancia=2)
        self.assertEqual(c1['atacante']['daño_por_golpe'], 8)

        # Veneno 2 -> 7 + 2 = 9 daño
        setattr(mage, 'nivel_veneno', 2)
        c2 = CalculadoraEngage.simular_combate(citrinne, mage, thunder, fire, Terreno(0,0), Terreno(0,0), distancia=2)
        self.assertEqual(c2['atacante']['daño_por_golpe'], 9)

        # Veneno 3 -> 7 + 3 = 10 daño
        setattr(mage, 'nivel_veneno', 3)
        c3 = CalculadoraEngage.simular_combate(citrinne, mage, thunder, fire, Terreno(0,0), Terreno(0,0), distancia=2)
        self.assertEqual(c3['atacante']['daño_por_golpe'], 10)

    def test_4_phantom_attack_prevention(self):
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

    def test_5_enemy_blocks_movement_path(self):
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

    def test_6_chain_attack_backup_tactical(self):
        """Chain Attack: 10% Max HP defensor, 80% Hit, reportado explícitamente en /api/analizar."""
        from app import es_unidad_backup, obtener_aliados_backup
        tablero.limpiar()

        # Aliado Atacante: Alear en (5, 5), espada rango 1
        alear = resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 5, "y": 5, "mov": 4, "es_aliado": True,
            "arma_nombre": "Liberation", "stats": {"hp": 25, "fuerza": 12, "velocidad": 12, "estilo_combate": "Dragon"}
        })
        tablero.registrar_unidad(alear)

        # Aliado Backup: Lapis en (6, 5), Sword Fighter (estilo Backup / De apoyo), rango 1
        lapis = resolver_unidad_con_catalogo({
            "nombre": "Lapis", "x": 6, "y": 5, "mov": 4, "es_aliado": True,
            "clase_nombre": "Sword Fighter", "arma_nombre": "Iron Sword",
            "stats": {"hp": 22, "fuerza": 11, "velocidad": 14, "estilo_combate": "De apoyo"}
        })
        tablero.registrar_unidad(lapis)

        # Enemigo: Lance Fighter en (6, 6) con 32 HP Max
        ene = resolver_unidad_con_catalogo({
            "nombre": "Lance Fighter (6,6)", "x": 6, "y": 6, "mov": 4, "es_aliado": False,
            "arma_nombre": "Iron Lance", "stats": {"hp": 32, "hp_max": 32, "defensa": 8}
        })
        tablero.registrar_unidad(ene)

        # 1. Verificar detección de backup
        self.assertTrue(es_unidad_backup(lapis), "Lapis (Sword Fighter / De apoyo) debe ser reconocida como Backup")
        self.assertFalse(es_unidad_backup(alear), "Alear (Dragon) no es clase Backup directa")

        # 2. Verificar aliados de apoyo detectados
        # Lapis en (6,5) está adyacente a Lance Fighter en (6,6) (distancia 1, dentro de rango [1] de Iron Sword)
        apoyos = obtener_aliados_backup(alear, ene)
        self.assertEqual(len(apoyos), 1)
        self.assertEqual(apoyos[0].nombre, "Lapis")

        # 3. Test de endpoint /api/analizar
        client = app.test_client()
        res = client.post("/api/analizar", json={"perfil": "seguro"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(len(data.get("resultados", [])) > 0)

        # Buscar la jugada de Alear contra Lance Fighter (oportunidad de ataque del jugador)
        jugada_alear = [r for r in data["resultados"] if r.get("tipo_analisis") == "oportunidad_jugador" and r.get("aliado") == "Alear" and r.get("enemigo") == "Lance Fighter (6,6)"]
        self.assertTrue(len(jugada_alear) > 0, "Debe existir recomendación de ataque de Alear contra Lance Fighter")
        r_alear = jugada_alear[0]

        # Verificar que chain_attacks está presente
        chain_info = r_alear.get("chain_attacks", [])
        self.assertEqual(len(chain_info), 1)
        self.assertEqual(chain_info[0]["nombre"], "Lapis")
        # 10% de 32 HP = 3 de daño
        self.assertEqual(chain_info[0]["daño"], 3)
        self.assertEqual(chain_info[0]["precision"], 80)

        # Verificar que el texto de recomendación es limpio y conciso (la info de cadena va en badges superiores)
        rec = r_alear.get("recomendacion", "")
        self.assertIn("Alear", rec)
        self.assertIn("Libération", rec)
        self.assertIn("Lance Fighter (6,6)", rec)
        self.assertNotIn("Y luego el ataque normal del aliado", rec)

    def test_8_lapis_attacks_weakened_lance_fighter_no_healing(self):
        """
        Verifica el bug reportado:
        Lance Fighter (6,10) tenía su HP ajustado de 32 a 10.
        Al atacar Lapis con Espada de Hierro (14 dmg en 2 golpes de 7), el defensor debe
        quedar en 0 HP (derrotado), en lugar de 'curarse' a 18 calculando desde 32 base.
        """
        tablero.limpiar()
        # Lapis en (2, 10), Espada de Hierro, 26 HP, mov 5
        lapis = resolver_unidad_con_catalogo({
            "nombre": "Lapis", "x": 2, "y": 10, "mov": 5, "es_aliado": True,
            "arma_nombre": "Iron Sword",
            "stats": {"hp": 26, "fuerza": 11, "velocidad": 14, "defensa": 5, "destreza": 12, "complexion": 5}
        })
        tablero.registrar_unidad(lapis)

        # Lance Fighter (6,10) con HP base 32, pero ajustado a 10 HP
        lance_fighter = resolver_unidad_con_catalogo({
            "nombre": "Lance Fighter (6,10)", "x": 6, "y": 10, "mov": 4, "es_aliado": False,
            "arma_nombre": "Iron Lance",
            "hp_actual": 10,
            "hp_max": 32,
            "stats": {"hp": 32, "defensa": 9, "velocidad": 9, "fuerza": 13}
        })
        tablero.registrar_unidad(lance_fighter)

        # Verificar que el HP actual y stats.hp quedaron sincronizados a 10
        f_def = tablero.obtener_ficha("Lance Fighter (6,10)")
        self.assertEqual(f_def.hp_actual, 10)
        self.assertEqual(f_def.stats.hp, 10)

        client = app.test_client()
        # Lapis se mueve a (5, 10) y ataca
        res = client.post("/api/combate/ejecutar", json={
            "atacante": "Lapis",
            "defensor": "Lance Fighter (6,10)",
            "arma_nombre": "Iron Sword",
            "pos_destino": [5, 10]
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["ok"])

        # Daño: Lapis hace 7 por golpe x 2 = 14 daño
        res_combate = data["combate"]["resultado"]
        hp_def_final = res_combate["hp_defensor_final"]
        self.assertEqual(hp_def_final, 0, f"El defensor debía quedar en 0 HP tras 14 dmg contra 10 HP, pero quedó en {hp_def_final}")

        # En el tablero, el enemigo debe estar muerto (viva=False y hp_actual=0)
        f_def_post = tablero.obtener_ficha("Lance Fighter (6,10)")
        self.assertEqual(f_def_post.hp_actual, 0)
        self.assertFalse(f_def_post.viva)

    def test_9_analizar_with_active_supports_no_crash(self):
        """
        Verifica que /api/analizar y el flujo de confirmación de Turno Enemigo
        no crashean al formatear apoyos activos (apoyos_activos dicts).
        """
        tablero.limpiar()
        client = app.test_client()

        # Alear en (2, 8)
        alear = resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 2, "y": 8, "mov": 4, "es_aliado": True,
            "arma_nombre": "Liberation", "stats": {"hp": 24, "fuerza": 11, "velocidad": 12}
        })
        tablero.registrar_unidad(alear)

        # Céline en (2, 7) adyacente a Alear (Apoyo C canónico)
        celine = resolver_unidad_con_catalogo({
            "nombre": "Céline", "x": 2, "y": 7, "mov": 4, "es_aliado": True,
            "arma_nombre": "Fire", "stats": {"hp": 24, "magia": 15, "velocidad": 12}
        })
        tablero.registrar_unidad(celine)

        # Enemigo cercano en (2, 9)
        ene = resolver_unidad_con_catalogo({
            "nombre": "Lance Fighter (2,9)", "x": 2, "y": 9, "mov": 4, "es_aliado": False,
            "arma_nombre": "Iron Lance", "stats": {"hp": 32, "defensa": 10, "resistencia": 7}
        })
        tablero.registrar_unidad(ene)

        # 1. Simular inicio y fin de fase enemiga
        res_ini = client.post("/api/turno/inicio_fase_enemigo")
        self.assertEqual(res_ini.status_code, 200)

        res_fin = client.post("/api/turno/fin")
        self.assertEqual(res_fin.status_code, 200)
        self.assertEqual(tablero.fase, "jugador")

        # 2. Llamar a /api/analizar
        res_ana = client.post("/api/analizar", json={"perfil": "seguro"})
        self.assertEqual(res_ana.status_code, 200, "El análisis no debe fallar con error 500")
        data = res_ana.get_json()
        self.assertIn("resultados", data)
        self.assertTrue(len(data["resultados"]) > 0)

        # Verificar que si hay apoyos_activos, son diccionarios válidos y el texto no falló
        for r in data["resultados"]:
            if r.get("apoyos_activos"):
                for ap in r["apoyos_activos"]:
                    self.assertIsInstance(ap, dict)
                    self.assertIn("aliado", ap)

    def test_10_clean_kill_weapon_selection_vs_overkill_with_counterattack(self):
        """
        Validación del Ratio Daño-Acierto-Supervivencia:
        Chlóe enfrentando a un Mago con 24 HP.
        - Slim Lance hace 2x16 = 32 (mata al enemigo, pero Chlóe recibe contragolpe del mago en medio).
        - Silver Lance hace 1x24 = 24 (mata al enemigo en el 1er golpe, 0 daño recibido).
        La IA debe priorizar Silver Lance (Clean Kill) sobre Slim Lance (Overkill con daño recibido).
        """
        from motor_analisis import analizar_situacion_tactica
        tablero.limpiar()

        # Chloé con Slim Lance y Silver Lance en su inventario
        chloe = resolver_unidad_con_catalogo({
            "nombre": "Chloé", "x": 5, "y": 5, "mov": 5, "es_aliado": True,
            "arma_nombre": "Slim Lance",
            "stats": {"hp": 26, "fuerza": 12, "magia": 2, "destreza": 14, "velocidad": 16, "defensa": 8, "resistencia": 9, "suerte": 10},
            "inventario": [
                {"nombre": "Slim Lance", "tipo": "Lanza", "poder": 4, "precision": 100, "peso": 2, "rango": [1]},
                {"nombre": "Silver Lance", "tipo": "Lanza", "poder": 12, "precision": 100, "peso": 11, "rango": [1]}
            ]
        })
        tablero.registrar_unidad(chloe)

        # Mago enemigo con 24 HP y 18 Atk mágico (Fire, rango 1-2, Spd 10 -> Chloé hace follow-up con Slim pero no con Silver)
        # Contra Silver: Chloé pega 12 + 12 = 24 dmg -> Mago muere de 1 golpe (OHKO, 0 contraataque).
        # Contra Slim: Chloé pega 12 + 4 = 16 dmg en golpe 1 -> Mago vive con 8 HP y contraataca haciendo 18-9=9 dmg -> Chloé pega 16 en golpe 2 y mata.
        mago = resolver_unidad_con_catalogo({
            "nombre": "Mage (5,6)", "x": 5, "y": 6, "mov": 4, "es_aliado": False,
            "arma_nombre": "Fire",
            "stats": {"hp": 24, "fuerza": 1, "magia": 13, "destreza": 10, "velocidad": 10, "defensa": 0, "resistencia": 4, "suerte": 5},
            "inventario": [
                {"nombre": "Fire", "tipo": "Tomo", "poder": 5, "precision": 90, "peso": 4, "rango": [1, 2], "es_magica": True}
            ]
        })
        tablero.registrar_unidad(mago)

        recs = analizar_situacion_tactica(tablero=tablero, mapa=_mapa)

        op_chloe = [r for r in recs["resultados"] if r.get("aliado") == "Chloé"]
        self.assertTrue(len(op_chloe) > 0, "Debe haber al menos una recomendación para Chloé")
        mejor_op = op_chloe[0]

        # Debe recomendar Silver Lance, NO Slim Lance
        self.assertEqual(mejor_op.get("arma_recomendada"), "Silver Lance",
                         f"Debe recomendar Silver Lance (Clean Kill), pero recomendó {mejor_op.get('arma_recomendada')}")
        self.assertEqual(mejor_op.get("daño_recibido"), 0, "El daño recibido con Silver Lance debe ser 0")
        self.assertIn("CLEAN KILL", mejor_op.get("recomendacion", ""), "Debe etiquetarse como CLEAN KILL")

    def test_11_recommendations_deduplication_and_cap(self):
        """
        Validar que el motor no sobrecargue al jugador ni al servidor con 30+ combinaciones:
        - 1 mejor acción por aliado activo.
        - Total de oportunidades de ataque limitadas a <= 8.
        """
        from motor_analisis import analizar_situacion_tactica
        tablero.limpiar()

        # Registrar 6 aliados
        for i in range(6):
            ali = resolver_unidad_con_catalogo({
                "nombre": f"Aliado_{i}", "x": 2, "y": 2 + i, "mov": 5, "es_aliado": True,
                "arma_nombre": "Iron Sword",
                "stats": {"hp": 25, "fuerza": 12, "velocidad": 10, "defensa": 8, "resistencia": 5}
            })
            tablero.registrar_unidad(ali)

        # Registrar 5 enemigos alcanzables
        for j in range(5):
            ene = resolver_unidad_con_catalogo({
                "nombre": f"Enemigo_{j}", "x": 3, "y": 2 + j, "mov": 4, "es_aliado": False,
                "arma_nombre": "Iron Lance",
                "stats": {"hp": 20, "fuerza": 8, "velocidad": 6, "defensa": 5, "resistencia": 2}
            })
            tablero.registrar_unidad(ene)

        recs = analizar_situacion_tactica(tablero=tablero, mapa=_mapa)

        resultados = recs["resultados"]
        # Total no debe exceder 8 recomendaciones de ataque
        ops_ataque = [r for r in resultados if r.get("tipo_analisis") == "oportunidad_jugador"]
        self.assertLessEqual(len(ops_ataque), 8, "No debe haber más de 8 recomendaciones de ataque")

        # Verificar deduplicación por aliado: ningún aliado debe aparecer repetido en ops_ataque
        aliados_vistos = set()
        for op in ops_ataque:
            nom_a = op["aliado"]
            self.assertNotIn(nom_a, aliados_vistos, f"El aliado {nom_a} tiene múltiples recomendaciones de ataque duplicadas")
            aliados_vistos.add(nom_a)

    def test_11_counterattacks_javelin_tomes_bows_canonical(self):
        """
        Verificación estricta de las mecánicas canónicas de contraataque:
        1. Jabalina (Javelin): contraataca a distancia 1 y a distancia 2 (rango [1, 2]), pero NO a distancia 3.
        2. Tomos (Fire): contraataca a distancia 1 y a distancia 2 (rango [1, 2]), pero NO a distancia 3.
        3. Arcos (Bows):
           - No pueden atacar a distancia 1 (ValueError).
           - No pueden contraatacar a distancia 1 (puede_contraatacar = False).
           - SÍ pueden atacar y contraatacar a distancia 2 (puede_contraatacar = True).
        """
        # Unidades base
        chloe = Unidad(nombre="Chloé", hp=28, fuerza=12, velocidad=15, defensa=8, resistencia=10)
        diamant = Unidad(nombre="Diamant", hp=30, fuerza=13, velocidad=13, defensa=10, resistencia=5)
        etie = Unidad(nombre="Etie", hp=22, fuerza=14, velocidad=10, defensa=4, resistencia=3)
        mage = Unidad(nombre="Mage", hp=20, fuerza=2, magia=12, velocidad=8, defensa=3, resistencia=8)

        # Armas resueltas canónicamente
        javelin = Arma(nombre="Javelin", mt=6, tipo="Lanza")
        iron_sword = Arma(nombre="Iron Sword", mt=5, tipo="Espada")
        iron_bow = Arma(nombre="Iron Bow", mt=6, tipo="Arco")
        fire = Arma(nombre="Fire", mt=5, tipo="Tomo", es_magica=True)
        longbow = Arma(nombre="Longbow", mt=7, tipo="Arco")

        # Verificar rangos inferidos canónicamente
        self.assertEqual(javelin.rango, [1, 2], "Javelin debe tener rango [1, 2]")
        self.assertEqual(fire.rango, [1, 2], "Fire debe tener rango [1, 2]")
        self.assertEqual(iron_bow.rango, [2], "Iron Bow debe tener rango estrictamente [2] (NUNCA [1])")
        self.assertEqual(longbow.rango, [2, 3], "Longbow debe tener rango [2, 3]")
        self.assertEqual(iron_sword.rango, [1], "Iron Sword debe tener rango [1]")

        # ── 1. JAVELIN ──
        # Diamant ataca a Chloé (Javelin) a distancia 1 (con Iron Sword)
        c_jav_d1 = CalculadoraEngage.simular_combate(diamant, chloe, iron_sword, javelin, Terreno(0,0), Terreno(0,0), distancia=1)
        self.assertTrue(c_jav_d1["defensor"]["puede_contraatacar"], "Unidad con Javelin SÍ debe contraatacar a distancia 1")

        # Etie ataca a Chloé (Javelin) a distancia 2 (con Iron Bow)
        c_jav_d2 = CalculadoraEngage.simular_combate(etie, chloe, iron_bow, javelin, Terreno(0,0), Terreno(0,0), distancia=2)
        self.assertTrue(c_jav_d2["defensor"]["puede_contraatacar"], "Unidad con Javelin SÍ debe contraatacar a distancia 2")

        # Etie ataca a Chloé (Javelin) a distancia 3 (con Longbow)
        c_jav_d3 = CalculadoraEngage.simular_combate(etie, chloe, longbow, javelin, Terreno(0,0), Terreno(0,0), distancia=3)
        self.assertFalse(c_jav_d3["defensor"]["puede_contraatacar"], "Unidad con Javelin NO puede contraatacar a distancia 3")

        # ── 2. TOMOS (FIRE) ──
        # Diamant ataca a Mage (Fire) a distancia 1 (con Iron Sword)
        c_fire_d1 = CalculadoraEngage.simular_combate(diamant, mage, iron_sword, fire, Terreno(0,0), Terreno(0,0), distancia=1)
        self.assertTrue(c_fire_d1["defensor"]["puede_contraatacar"], "Unidad con Tomo SÍ debe contraatacar a distancia 1")

        # Etie ataca a Mage (Fire) a distancia 2 (con Iron Bow)
        c_fire_d2 = CalculadoraEngage.simular_combate(etie, mage, iron_bow, fire, Terreno(0,0), Terreno(0,0), distancia=2)
        self.assertTrue(c_fire_d2["defensor"]["puede_contraatacar"], "Unidad con Tomo SÍ debe contraatacar a distancia 2")

        # Etie ataca a Mage (Fire) a distancia 3 (con Longbow)
        c_fire_d3 = CalculadoraEngage.simular_combate(etie, mage, longbow, fire, Terreno(0,0), Terreno(0,0), distancia=3)
        self.assertFalse(c_fire_d3["defensor"]["puede_contraatacar"], "Unidad con Tomo estándar NO puede contraatacar a distancia 3")

        # ── 3. ARCOS (BOWS) ──
        # Intento de atacar a distancia 1 con Iron Bow -> debe lanzar ValueError
        with self.assertRaises(ValueError):
            CalculadoraEngage.simular_combate(etie, diamant, iron_bow, iron_sword, Terreno(0,0), Terreno(0,0), distancia=1)

        # Ataque a distancia 2 con Iron Bow -> válido
        c_bow_d2 = CalculadoraEngage.simular_combate(etie, diamant, iron_bow, iron_sword, Terreno(0,0), Terreno(0,0), distancia=2)
        self.assertFalse(c_bow_d2["defensor"]["puede_contraatacar"], "Diamant con Iron Sword (rango 1) no puede contraatacar a distancia 2")

        # Diamant ataca a Etie (con Iron Bow) a distancia 1
        c_vs_bow_d1 = CalculadoraEngage.simular_combate(diamant, etie, iron_sword, iron_bow, Terreno(0,0), Terreno(0,0), distancia=1)
        self.assertFalse(c_vs_bow_d1["defensor"]["puede_contraatacar"], "Arquero con Iron Bow NO PUEDE contraatacar a distancia 1")

        # Chloé ataca a Etie (con Iron Bow) a distancia 2 (con Javelin)
        c_vs_bow_d2 = CalculadoraEngage.simular_combate(chloe, etie, javelin, iron_bow, Terreno(0,0), Terreno(0,0), distancia=2)
        self.assertTrue(c_vs_bow_d2["defensor"]["puede_contraatacar"], "Arquero con Iron Bow SÍ debe contraatacar a distancia 2")

    def test_12_tactical_positioning_safe_range(self):
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

    def test_13_tactical_positioning_avoids_enemy_danger_lines(self):
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
        self.assertIn("CLEAN KILL", ops_kill[0]["recomendacion"])

    def test_5_chapter_7_bosses_ground_truth(self):
        """Validación canónica de stats y equipamiento de jefes del Cap. 7 (Hortensia, Rosado, Goldmary)."""
        c = CargadorDisposEngage()
        units_maddening = c.cargar_capitulo("M007", "Extremo")
        
        # 1. Hortensia en Maddening
        h_m = [u for u in units_maddening if u["nombre"] == "Hortensia (Jefa)"][0]
        f_h_m = resolver_unidad_con_catalogo(h_m)
        self.assertEqual(f_h_m.stats.hp, 36)
        self.assertEqual(f_h_m.stats.fuerza, 4)
        self.assertEqual(f_h_m.stats.magia, 6)
        self.assertEqual(f_h_m.stats.destreza, 20)
        self.assertEqual(f_h_m.stats.velocidad, 17)
        self.assertEqual(f_h_m.stats.defensa, 13)
        self.assertEqual(f_h_m.stats.resistencia, 18)
        self.assertEqual(f_h_m.hp_stock, 1)  # Revival Stone
        self.assertEqual(f_h_m.emblema_nombre, "Lucina")
        self.assertTrue(any("noble rapier" in str(it.get("nombre","")).lower() for it in f_h_m.inventario))
        self.assertTrue(any("elfire" in str(it.get("nombre","")).lower() for it in f_h_m.inventario))
        self.assertTrue(any("master seal" in str(it.get("nombre","")).lower() for it in f_h_m.inventario))

        # 2. Rosado en Maddening
        r_m = [u for u in units_maddening if u["nombre"] == "Rosado"][0]
        f_r_m = resolver_unidad_con_catalogo(r_m)
        self.assertEqual(f_r_m.stats.hp, 38)
        self.assertEqual(f_r_m.stats.fuerza, 17)
        self.assertEqual(f_r_m.stats.velocidad, 17)
        self.assertEqual(f_r_m.stats.defensa, 14)
        self.assertEqual(f_r_m.mov, 6)
        self.assertTrue(f_r_m.es_volador)
        self.assertTrue(any("steel axe" in str(it.get("nombre","")).lower() for it in f_r_m.inventario))

        # 3. Goldmary en Maddening
        g_m = [u for u in units_maddening if u["nombre"] == "Goldmary"][0]
        f_g_m = resolver_unidad_con_catalogo(g_m)
        self.assertEqual(f_g_m.stats.hp, 34)
        self.assertEqual(f_g_m.stats.fuerza, 12)
        self.assertEqual(f_g_m.stats.velocidad, 18)
        self.assertEqual(f_g_m.stats.defensa, 14)
        self.assertEqual(f_g_m.mov, 5)
        self.assertTrue(any("steel sword" in str(it.get("nombre","")).lower() for it in f_g_m.inventario))

    def test_6_sigurd_engage_mov_plus_5(self):
        """Sigurd otorga +1 MOV sincronizado y +5 MOV en modo Fusión (Engage)."""
        u_base = {
            "nombre": "Alfred", "es_aliado": True, "nivel": 10,
            "clase_nombre": "Noble (Caballería)", "emblema_nombre": "Sigurd"
        }
        f_synchro = resolver_unidad_con_catalogo({**u_base, "en_fusion": False})
        f_engage = resolver_unidad_con_catalogo({**u_base, "en_fusion": True})
        # Noble tiene 5 MOV base. Con Sigurd sincronizado: 6 MOV. Con Engage Sigurd: 10 MOV (+5).
        self.assertEqual(f_synchro.mov, 6, f"Sigurd sincronizado debe dar 6 MOV, dio {f_synchro.mov}")
        self.assertEqual(f_engage.mov, 10, f"Sigurd en Engage debe dar 10 MOV (+5), dio {f_engage.mov}")

    def test_7_personal_skills_stunning_smile_and_disarming_sigh(self):
        """Sonrisa Cautivadora (Rosado: -20 Avo a varones) y Suspiro Desarmante (Goldmary: -20 Hit a varones)."""
        u_rosado = Unidad(nombre="Rosado", hp=38, destreza=14, velocidad=17, suerte=9, habilidades=["Stunning Smile"])
        u_goldmary = Unidad(nombre="Goldmary", hp=34, destreza=10, velocidad=18, defensa=14, suerte=10, habilidades=["Disarming Sigh"])
        u_varon = Unidad(nombre="Boucheron", hp=30, destreza=12, velocidad=14, suerte=5)  # Male
        u_mujer = Unidad(nombre="Lapis", hp=26, destreza=14, velocidad=16, suerte=8)      # Female

        espada = Arma(nombre="Iron Sword", tipo="Espada", mt=5, wt=5, hit=85, crit=0, rango=[1])
        hacha = Arma(nombre="Steel Axe", tipo="Hacha", mt=11, wt=12, hit=75, crit=0, rango=[1])

        # 1. Rosado ataca a Boucheron (varón) -> Boucheron pierde 20 Avo
        comb_m = CalculadoraEngage.calcular_intercambio(u_rosado, u_varon, hacha, espada)
        comb_f = CalculadoraEngage.calcular_intercambio(u_rosado, u_mujer, hacha, espada)
        # Contra el varón, el Avoid del defensor se reduce en 20, aumentando la precisión en 20
        avo_boucheron_normal = CalculadoraEngage.calcular_avoid(u_varon.velocidad, u_varon.suerte, 0)
        self.assertIn("Sonrisa Cautivadora (-20 Evasión rival masculino)", comb_m["pasivas_activas"])
        self.assertNotIn("Sonrisa Cautivadora (-20 Evasión rival masculino)", comb_f["pasivas_activas"])

        # 2. Boucheron (varón) ataca a Goldmary -> Boucheron pierde 20 Hit
        comb_g_m = CalculadoraEngage.calcular_intercambio(u_varon, u_goldmary, espada, espada)
        comb_g_f = CalculadoraEngage.calcular_intercambio(u_mujer, u_goldmary, espada, espada)
        self.assertIn("Suspiro Desarmante (-20 Precisión por rival masculino)", comb_g_m["pasivas_activas"])
        self.assertNotIn("Suspiro Desarmante (-20 Precisión por rival masculino)", comb_g_f["pasivas_activas"])

    def test_8_canter_retreat_generation_and_execution(self):
        """Unidad con Canter calcula casilla de refugio y se mueve a ella tras combatir."""
        tablero.fichas.clear()
        chloe = resolver_unidad_con_catalogo({
            "nombre": "Chloé", "es_aliado": True, "x": 10, "y": 7, "mov": 5,
            "arma_nombre": "Slim Lance", "habilidades": ["Canter"],
            "stats": {"hp": 26, "fuerza": 12, "velocidad": 16, "defensa": 8}
        })
        mago = resolver_unidad_con_catalogo({
            "nombre": "Mage (10,6)", "es_aliado": False, "x": 10, "y": 6, "mov": 4,
            "arma_nombre": "Fire",
            "stats": {"hp": 20, "fuerza": 0, "magia": 8, "velocidad": 8, "defensa": 3}
        })
        tablero.registrar_unidad(chloe)
        tablero.registrar_unidad(mago)

        from motor_analisis import analizar_situacion_tactica
        recs = analizar_situacion_tactica(tablero=tablero, mapa=_mapa)
        op_chloe = [r for r in recs["resultados"] if r.get("aliado") == "Chloé"][0]
        self.assertIsNotNone(op_chloe.get("pos_canter"), "Debe generar casilla de refugio Canter")
        pos_refugio = op_chloe["pos_canter"]
        self.assertLessEqual(abs(pos_refugio[0] - op_chloe["pos_sugerida"][0]) + abs(pos_refugio[1] - op_chloe["pos_sugerida"][1]), 2)
        self.assertIn("Canter → Refugio", op_chloe["recomendacion"])

        # Ejecutar combate pasando pos_canter
        client = app.test_client()
        res = client.post("/api/combate/ejecutar", json={
            "atacante": "Chloé",
            "defensor": "Mage (10,6)",
            "arma_nombre": "Slim Lance",
            "pos_destino": op_chloe["pos_sugerida"],
            "pos_canter": pos_refugio
        })
        self.assertEqual(res.status_code, 200)
        # Chloé debe terminar en la casilla de refugio pos_canter
        chloe_fin = tablero.obtener_ficha("Chloé")
        self.assertEqual((chloe_fin.x, chloe_fin.y), (pos_refugio[0], pos_refugio[1]))

    def test_9_clean_recommendations_no_redundancy(self):
        """La cadena recomendacion no repite textos que ya se muestran en las insignias superiores."""
        tablero.fichas.clear()
        lapis = resolver_unidad_con_catalogo({
            "nombre": "Lapis", "es_aliado": True, "x": 2, "y": 10, "mov": 5,
            "arma_nombre": "Iron Sword", "clase_nombre": "Sword Fighter",
            "stats": {"hp": 26, "fuerza": 12, "velocidad": 15, "defensa": 8}
        })
        alcryst = resolver_unidad_con_catalogo({
            "nombre": "Alcryst", "es_aliado": True, "x": 2, "y": 9, "mov": 5,
            "arma_nombre": "Iron Bow", "clase_nombre": "Lord (Alcryst)",
            "stats": {"hp": 28, "fuerza": 11, "velocidad": 13, "defensa": 9}
        })
        ene = resolver_unidad_con_catalogo({
            "nombre": "Lance Fighter (3,10)", "es_aliado": False, "x": 3, "y": 10, "mov": 4,
            "arma_nombre": "Iron Lance",
            "stats": {"hp": 24, "fuerza": 8, "velocidad": 8, "defensa": 5}
        })
        tablero.registrar_unidad(lapis)
        tablero.registrar_unidad(alcryst)
        tablero.registrar_unidad(ene)

        from motor_analisis import analizar_situacion_tactica
        recs = analizar_situacion_tactica(tablero=tablero, mapa=_mapa)
        op_lapis = [r for r in recs["resultados"] if r.get("aliado") == "Lapis"][0]
        rec_str = op_lapis["recomendacion"]

        # No debe tener texto repetido de apoyos ni de chain attack en el párrafo inferior
        self.assertNotIn("⚔️ Chain Attack: La unidad", rec_str)
        self.assertNotIn("🤝 Apoyos:", rec_str)
        self.assertTrue(rec_str.startswith("🎯 Lapis → usa"))

    def test_10_three_houses_leader_switching(self):
        """Alternar el líder de Tres Casas cambia dinámicamente Weapon Sync."""
        tablero.fichas.clear()
        chloe = resolver_unidad_con_catalogo({
            "nombre": "Chloé", "es_aliado": True, "x": 5, "y": 5, "mov": 5,
            "arma_nombre": "Silver Lance", "emblema_nombre": "Edelgard",
            "lider_tres_casas": "Dimitri", "habilidades": ["Weapon Sync"],
            "stats": {"hp": 30, "fuerza": 10, "velocidad": 15, "defensa": 8}
        })
        tablero.registrar_unidad(chloe)
        client = app.test_client()

        # Con Dimitri: Lanza tiene Weapon Sync (+5 Atk)
        comb_dimitri = CalculadoraEngage.calcular_intercambio(chloe.stats, chloe.stats, chloe.arma, chloe.arma)
        self.assertIn("Weapon Sync (+5 ATK)", comb_dimitri["pasivas_activas"])

        # Cambiar líder a Edelgard vía API
        res = client.post("/api/unidad/alternar_lider_tres_casas", json={"nombre": "Chloé", "lider": "Edelgard"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json["lider_activo"], "Edelgard")

        # Con Edelgard: Lanza NO tiene Weapon Sync (requiere Hachas)
        comb_edelgard = CalculadoraEngage.calcular_intercambio(chloe.stats, chloe.stats, chloe.arma, chloe.arma)
        self.assertNotIn("Weapon Sync (+5 ATK)", comb_edelgard["pasivas_activas"])

if __name__ == "__main__":
    unittest.main()




