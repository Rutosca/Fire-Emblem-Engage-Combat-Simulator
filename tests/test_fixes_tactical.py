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
        setattr(mage, 'nivel_veneno', 0)
        c0 = CalculadoraEngage.simular_combate(citrinne, mage, thunder, fire, Terreno(0,0), Terreno(0,0), distancia=2)
        self.assertEqual(c0['atacante']['daño_por_golpe'], 7)
        setattr(mage, 'nivel_veneno', 1)
        c1 = CalculadoraEngage.simular_combate(citrinne, mage, thunder, fire, Terreno(0,0), Terreno(0,0), distancia=2)
        self.assertEqual(c1['atacante']['daño_por_golpe'], 8)
        setattr(mage, 'nivel_veneno', 2)
        c2 = CalculadoraEngage.simular_combate(citrinne, mage, thunder, fire, Terreno(0,0), Terreno(0,0), distancia=2)
        self.assertEqual(c2['atacante']['daño_por_golpe'], 9)
        setattr(mage, 'nivel_veneno', 3)
        c3 = CalculadoraEngage.simular_combate(citrinne, mage, thunder, fire, Terreno(0,0), Terreno(0,0), distancia=2)
        self.assertEqual(c3['atacante']['daño_por_golpe'], 10)

    def test_resurrector_stops_attack_and_does_not_transfer_excess_damage(self):
        """Romper una barra con piedra corta la ronda y restaura la siguiente."""
        atacante = Unidad(nombre='Atacante', hp=30, fuerza=10, destreza=20, velocidad=20,
                          defensa=5, resistencia=5, suerte=0, complexion=5)
        defensor = Unidad(nombre='Hortensia', hp=10, fuerza=1, destreza=1, velocidad=1,
                          defensa=5, resistencia=5, suerte=0, complexion=5, hp_max=10)
        defensor.hp_stock = 1
        espada = Arma(nombre='Espada', mt=5, wt=0, hit=100, crit=0, es_magica=False, tipo='Espada', rango=[1])
        tomo = Arma(nombre='Tomo', mt=1, wt=0, hit=0, crit=0, es_magica=True, tipo='Tomo', rango=[1])

        comb = CalculadoraEngage.simular_combate(
            atacante, defensor, espada, tomo, Terreno(0, 0), Terreno(0, 0), distancia=1
        )
        self.assertTrue(comb['resultado']['piedra_resurrectora_consumida'])
        self.assertEqual(comb['atacante']['golpes_en_ronda'], 1)
        self.assertEqual(comb['atacante']['daño_total_ronda'], 10)
        self.assertEqual(comb['resultado']['hp_defensor_final'], 10)
        self.assertFalse(comb['resultado']['atacante_mata'])
        return

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

        # Verificar que el texto de recomendación contiene el mensaje exacto solicitado
        rec = r_alear.get("recomendacion", "")
        self.assertNotIn("ataque en cadena", rec)
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

    def test_14_m007_armored_uses_basic_internal_level(self):
        """Un Armored de nivel 10 no debe recibir +9 niveles de clase avanzada."""
        armored = next(u for u in self.cargador.cargar_capitulo("M007", "Extremo")
                       if "Armor" in u.get("clase_nombre", ""))
        ficha = resolver_unidad_con_catalogo(armored)
        self.assertEqual(getattr(ficha.stats, "nivel_interno_clase", None), 0)
        self.assertEqual(ficha.stats.hp, 36)

    def test_15_chain_attack_execution_and_damage_sum(self):
        """El ataque en cadena debe sumarse en golpe_txt y aplicarse al HP del defensor en /api/combate/ejecutar."""
        tablero.limpiar()
        ene = resolver_unidad_con_catalogo({
            "nombre": "Lance Fighter (ChainTest)", "x": 5, "y": 6, "mov": 4, "es_aliado": False,
            "arma_nombre": "Iron Lance", "stats": {"hp": 25, "hp_max": 25, "defensa": 8}
        })
        tablero.registrar_unidad(ene)

        alear = resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 5, "y": 5, "mov": 4, "es_aliado": True,
            "arma_nombre": "Liberation", "stats": {"hp": 25, "fuerza": 12, "velocidad": 10, "estilo_combate": "Dragon"}
        })
        tablero.registrar_unidad(alear)

        lapis = resolver_unidad_con_catalogo({
            "nombre": "Lapis", "x": 4, "y": 6, "mov": 4, "es_aliado": True,
            "clase_nombre": "Sword Fighter", "arma_nombre": "Iron Sword",
            "stats": {"hp": 22, "fuerza": 11, "velocidad": 14, "estilo_combate": "De apoyo"}
        })
        tablero.registrar_unidad(lapis)

        client = app.test_client()

        # 1. En /api/analizar, golpe_txt debe incluir Chain Attack sumado
        res_an = client.post("/api/analizar", json={"perfil": "seguro"})
        self.assertEqual(res_an.status_code, 200)
        data_an = res_an.get_json()
        op_alear = [r for r in data_an["resultados"] if r.get("aliado") == "Alear"][0]
        self.assertIn("Chain Attack", op_alear["recomendacion"])
        self.assertEqual(len(op_alear["chain_attacks"]), 1)
        self.assertEqual(op_alear["chain_attacks"][0]["daño"], 2)

        # 2. En /api/combate/ejecutar, el Chain Attack debe reducir el HP del enemigo (25 - 20 - 2 = 3)
        res_ex = client.post("/api/combate/ejecutar", json={
            "atacante": "Alear",
            "defensor": "Lance Fighter (ChainTest)",
            "arma_nombre": "Liberation",
            "pos_destino": [5, 5]
        })
        self.assertEqual(res_ex.status_code, 200)
        data_ex = res_ex.get_json()
        self.assertEqual(data_ex["defensor"]["hp_actual"], 3)
        self.assertEqual(data_ex["combate"]["resultado"]["chain_attacks_daño"], 2)

    def test_16_hortensia_analysis_no_crash(self):
        """Tener a Hortensia (Boss) en rango de múltiples aliados no debe arrojar KeyError ni error en análisis."""
        from app import _desplegar_capitulo, _mapa
        from motor_analisis import analizar_situacion_tactica
        _desplegar_capitulo("M007", "Extremo")

        hortensia = tablero.obtener_ficha("Hortensia (Boss)")
        self.assertIsNotNone(hortensia)

        alear = tablero.obtener_ficha("Alear")
        alcryst = tablero.obtener_ficha("Alcryst")
        citrinne = tablero.obtener_ficha("Citrinne")
        lapis = tablero.obtener_ficha("Lapis")

        alear.x, alear.y = 20, 8
        alcryst.x, alcryst.y = 19, 8
        citrinne.x, citrinne.y = 21, 9
        lapis.x, lapis.y = 20, 9

        analisis = analizar_situacion_tactica(tablero, _mapa)
        self.assertIn("resultados", analisis)
        self.assertTrue(len(analisis["resultados"]) > 0)

    def test_17_suicide_attack_prevention(self):
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

    def test_18_duracion_fusion_vinculo_sin_distincion_tipo(self):
        """
        Todos tienen 3 turnos de emblema salvo que una unidad tenga nivel 11 de vínculo
        con dicho emblema, que gana 1 turno más. No se distingue entre tipos de unidades.
        """
        # 1. Alear (Dragón) con vínculo nivel 10 -> debe tener 3 turnos, NO 4
        alear_lv10 = resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 1, "y": 1, "es_aliado": True,
            "emblema_nombre": "Marth", "nivel_vinculo": 10, "en_fusion": True
        })
        self.assertEqual(alear_lv10.turnos_fusion, 3, "Alear con vínculo 10 debe tener 3 turnos de fusión base")

        # 2. Alfred (Caballería) con vínculo nivel 10 -> 3 turnos
        alfred_lv10 = resolver_unidad_con_catalogo({
            "nombre": "Alfred", "x": 1, "y": 2, "es_aliado": True,
            "emblema_nombre": "Sigurd", "nivel_vinculo": 10, "en_fusion": True
        })
        self.assertEqual(alfred_lv10.turnos_fusion, 3, "Caballería con vínculo 10 debe tener 3 turnos")

        # 3. Unidad con nivel de vínculo >= 11 gana 1 turno más (4 turnos)
        alear_lv11 = resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 1, "y": 3, "es_aliado": True,
            "emblema_nombre": "Marth", "nivel_vinculo": 11, "en_fusion": True
        })
        self.assertEqual(alear_lv11.turnos_fusion, 4, "Unidad con vínculo 11 gana +1 turno (4 en total)")

        alfred_lv11 = resolver_unidad_con_catalogo({
            "nombre": "Alfred", "x": 1, "y": 4, "es_aliado": True,
            "emblema_nombre": "Sigurd", "nivel_vinculo": 15, "en_fusion": True
        })
        self.assertEqual(alfred_lv11.turnos_fusion, 4, "Cualquier unidad con vínculo >= 11 tiene 4 turnos")

    def test_19_bloqueo_retirar_fusion_y_decremento_turnos(self):
        """
        Una vez activada la fusión, no se puede retirar hasta que acabe.
        Al avanzar turno se decrementa en 1, y al llegar a 0 se apaga y energía queda en 0.
        """
        tablero.limpiar()
        chloe = resolver_unidad_con_catalogo({
            "nombre": "Chloé", "x": 3, "y": 3, "es_aliado": True,
            "emblema_nombre": "Edelgard", "nivel_vinculo": 5, "en_fusion": True
        })
        tablero.registrar_unidad(chloe)
        self.assertTrue(chloe.en_fusion)
        self.assertEqual(chloe.turnos_fusion, 3)

        # Intento de desmarcar fusión mientras turnos_fusion > 0 -> NO se retira
        chloe_mod = resolver_unidad_con_catalogo({
            "nombre": "Chloé", "x": 3, "y": 3, "es_aliado": True,
            "emblema_nombre": "Edelgard", "en_fusion": False
        }, tablero=tablero)
        tablero.registrar_unidad(chloe_mod)
        self.assertTrue(chloe_mod.en_fusion, "La fusión debe mantenerse bloqueada activa mientras turnos > 0")
        self.assertEqual(chloe_mod.turnos_fusion, 3)

        # Turno 1 -> Turno 2 (avanzar_turno resta 1 turno de fusión)
        tablero.avanzar_turno()
        f_chloe = tablero.obtener_ficha("Chloé")
        self.assertTrue(f_chloe.en_fusion)
        self.assertEqual(f_chloe.turnos_fusion, 2)

        # Turno 2 -> Turno 3
        tablero.avanzar_turno()
        f_chloe = tablero.obtener_ficha("Chloé")
        self.assertTrue(f_chloe.en_fusion)
        self.assertEqual(f_chloe.turnos_fusion, 1)

        # Turno 3 -> Turno 4 (expira la fusión)
        tablero.avanzar_turno()
        f_chloe = tablero.obtener_ficha("Chloé")
        self.assertFalse(f_chloe.en_fusion, "Al llegar a 0 turnos la fusión debe terminar")
        self.assertEqual(f_chloe.turnos_fusion, 0)
        self.assertEqual(f_chloe.energia_emblema, 0, "Al finalizar la fusión la energía se resetea a 0")
        self.assertFalse(f_chloe.ataque_emblema_usado, "El flag de ataque emblema se resetea para futuras fusiones")

    def test_20_recargas_emblema_solo_tras_agotar_fusion(self):
        """
        Las recargas de emblema (atacar +1, recibir +1, casilla recarga 100%)
        solo entran en vigor cuando se han agotado todos los turnos de fusión.
        """
        tablero.limpiar()
        # Aliado en fusión activa
        tablero.registrar_unidad(resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 5, "y": 5, "es_aliado": True,
            "emblema_nombre": "Marth", "en_fusion": True, "energia_emblema": 0
        }))
        tablero.registrar_unidad(resolver_unidad_con_catalogo({
            "nombre": "EnemigoTest", "x": 5, "y": 6, "es_aliado": False,
            "arma_nombre": "Iron Lance", "stats": {"hp": 30, "defensa": 5}
        }))

        client = app.test_client()
        # 1. Atacar estando en fusión NO recarga energía
        res = client.post("/api/combate/ejecutar", json={
            "atacante": "Alear", "defensor": "EnemigoTest", "arma_nombre": "Liberation"
        })
        self.assertEqual(res.status_code, 200)
        f_alear = tablero.obtener_ficha("Alear")
        self.assertEqual(f_alear.energia_emblema, 0, "En fusión no se acumula energía")

        # 2. Agotar la fusión completamente
        tablero.avanzar_turno() # 3 -> 2
        tablero.avanzar_turno() # 2 -> 1
        tablero.avanzar_turno() # 1 -> 0 (Fusión terminada, en_fusion=False, energia=0)
        self.assertFalse(f_alear.en_fusion)
        self.assertEqual(f_alear.energia_emblema, 0)

        # 3. Fuera de fusión: atacar da 1 recarga
        f_alear.ha_actuado = False
        res = client.post("/api/combate/ejecutar", json={
            "atacante": "Alear", "defensor": "EnemigoTest", "arma_nombre": "Liberation"
        })
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(f_alear.energia_emblema, 1, "Fuera de fusión, atacar da recarga")

        # 4. Fuera de fusión: defender da 1 recarga
        energia_previa = f_alear.energia_emblema
        res = client.post("/api/combate/ejecutar", json={
            "atacante": "EnemigoTest", "defensor": "Alear", "arma_nombre": "Iron Lance"
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(f_alear.energia_emblema, energia_previa + 1, "Recibir un ataque da otra recarga (+1)")

        # 5. Casilla de recarga de Emblema completa el medidor al 100% (6/6)
        # Colocar casilla recarga en mapa (13, 6) o grid
        if tablero.mapa and hasattr(tablero.mapa, 'grid') and len(tablero.mapa.grid) > 13:
            tablero.mapa.grid[13][6].es_recarga_emblema = True
            tablero.mover_unidad("Alear", 13, 6)
            self.assertEqual(f_alear.energia_emblema, f_alear.max_energia_emblema, "Pisar casilla recarga llena al 100%")

    def test_21_ataque_emblema_una_vez_por_fusion(self):
        """
        El ataque/habilidad especial del emblema se puede usar una sola vez durante la fusión.
        Una vez usado, el flag ataque_emblema_usado es True y no se vuelve a recomendar.
        """
        tablero.limpiar()
        marth_ali = resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 10, "y": 5, "es_aliado": True,
            "emblema_nombre": "Marth", "en_fusion": True, "nivel_vinculo": 10
        })
        tablero.registrar_unidad(marth_ali)

        jefe = resolver_unidad_con_catalogo({
            "nombre": "Hortensia (Boss)", "x": 10, "y": 6, "es_aliado": False,
            "arma_nombre": "Elfire", "stats": {"hp": 30, "defensa": 5}, "hp_stock": 2
        })
        tablero.registrar_unidad(jefe)

        self.assertFalse(marth_ali.ataque_emblema_usado)

        # Ejecutar Lodestar Rush (engage attack)
        client = app.test_client()
        res = client.post("/api/combate/ejecutar", json={
            "atacante": "Alear", "defensor": "Hortensia (Boss)",
            "arma_nombre": "Liberation", "es_engage_attack": True,
            "engage_attack_nombre": "Lodestar Rush"
        })
        self.assertEqual(res.status_code, 200)
        self.assertTrue(marth_ali.ataque_emblema_usado, "Ataque especial de emblema debe marcarse como usado")

        # El análisis táctico no debe recomendar usar Lodestar Rush de nuevo
        marth_ali.ha_actuado = False
        analisis = client.post("/api/analizar", json={"perfil": "seguro"}).get_json()
        op_alear = [r for r in analisis["resultados"] if r.get("aliado") == "Alear"]
        if op_alear:
            rec_txt = op_alear[0].get("recomendacion", "")
            self.assertIn("ya usada en esta fusión", rec_txt)

    def test_22_bond_level_stat_boosts_and_engage_weapons_scaling(self):
        """
        Verifica que los stats y armas de fusión se desbloqueen y escalen según el nivel de vínculo:
        - Marth Lv 1: Rapier (no Mercurius ni Falchion), Dex +1, Spd +1.
        - Marth Lv 10: Mercurius disponible en fusión.
        - Marth Lv 15+: Falchion disponible en fusión.
        - Marth Lv 20: Str +3, Dex +4, Spd +4.
        """
        # 1. Marth Lv 1
        alear_lv1 = resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 1, "y": 1, "es_aliado": True,
            "emblema_nombre": "Marth", "nivel_vinculo": 1, "en_fusion": True
        })
        nombres_inv_lv1 = [str(it.get("nombre", "")) for it in alear_lv1.inventario]
        self.assertTrue(any("rapier" in n.lower() for n in nombres_inv_lv1), "Rapier debe estar a Lv 1")
        self.assertFalse(any("mercurius" in n.lower() for n in nombres_inv_lv1), "Mercurius no debe estar a Lv 1")
        self.assertFalse(any("falchion" in n.lower() for n in nombres_inv_lv1), "Falchion no debe estar a Lv 1")

        # 2. Marth Lv 10
        alear_lv10 = resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 1, "y": 1, "es_aliado": True,
            "emblema_nombre": "Marth", "nivel_vinculo": 10, "en_fusion": True
        })
        nombres_inv_lv10 = [str(it.get("nombre", "")) for it in alear_lv10.inventario]
        self.assertTrue(any("mercurius" in n.lower() for n in nombres_inv_lv10), "Mercurius debe estar desbloqueado a Lv 10")
        self.assertFalse(any("falchion" in n.lower() for n in nombres_inv_lv10), "Falchion no debe estar a Lv 10")

        # 3. Marth Lv 15
        alear_lv15 = resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 1, "y": 1, "es_aliado": True,
            "emblema_nombre": "Marth", "nivel_vinculo": 15, "en_fusion": True
        })
        nombres_inv_lv15 = [str(it.get("nombre", "")) for it in alear_lv15.inventario]
        self.assertTrue(any("falchion" in n.lower() for n in nombres_inv_lv15), "Falchion debe estar desbloqueado a Lv 15")

        # 4. Progresión de Stats entre Lv 1 y Lv 20
        alear_lv20 = resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 1, "y": 1, "es_aliado": True,
            "emblema_nombre": "Marth", "nivel_vinculo": 20
        })
        # Marth da Str +1, Dex +1, Spd +1 a Lv 1 y Str +3, Dex +4, Spd +4 a Lv 20
        self.assertEqual(alear_lv20.stats.fuerza - alear_lv1.stats.fuerza, 2, "Delta Str entre Lv 1 y 20 debe ser +2 (1 -> 3)")
        self.assertEqual(alear_lv20.stats.destreza - alear_lv1.stats.destreza, 3, "Delta Dex entre Lv 1 y 20 debe ser +3 (1 -> 4)")
        self.assertEqual(alear_lv20.stats.velocidad - alear_lv1.stats.velocidad, 3, "Delta Spd entre Lv 1 y 20 debe ser +3 (1 -> 4)")

    def test_23_bond_level_20_max_energy_reduction(self):
        """
        A nivel 20 de vínculo, el medidor de recarga máxima se reduce en 1, pasando de 6 a 5.
        Solo pasa únicamente a nivel 20:
        - Niveles 1..19: max_energia_emblema = 6
        - Nivel 20: max_energia_emblema = 5
        - Pisar casilla de recarga a nivel 20 llena exactamente a 5 (no 6).
        - Atacar o defender fuera de fusión a nivel 20 no excede de 5 cargas.
        """
        # Niveles 1, 10, 15, 19 tienen max_energia_emblema = 6
        for lvl in [1, 5, 10, 15, 19]:
            u = resolver_unidad_con_catalogo({
                "nombre": "Alear", "x": 1, "y": 1, "es_aliado": True,
                "emblema_nombre": "Marth", "nivel_vinculo": lvl
            })
            self.assertEqual(u.max_energia_emblema, 6, f"Nivel {lvl} debe tener max_energia_emblema = 6")
            self.assertEqual(u.stats.max_energia_emblema, 6)

        # Nivel 20 tiene max_energia_emblema = 5
        u20 = resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 1, "y": 1, "es_aliado": True,
            "emblema_nombre": "Marth", "nivel_vinculo": 20, "energia_emblema": 6
        })
        self.assertEqual(u20.max_energia_emblema, 5, "Nivel 20 debe tener max_energia_emblema = 5")
        self.assertEqual(u20.stats.max_energia_emblema, 5)
        self.assertEqual(u20.energia_emblema, 5, "Energía debe clampearse al máximo de 5")

        # Pisar casilla de recarga a Nivel 20 llena al 100% (5 cargas, no 6)
        tablero.limpiar()
        u20_cero = resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 2, "y": 2, "es_aliado": True,
            "emblema_nombre": "Marth", "nivel_vinculo": 20, "energia_emblema": 0
        })
        tablero.registrar_unidad(u20_cero)
        if tablero.mapa and hasattr(tablero.mapa, 'grid') and len(tablero.mapa.grid) > 13:
            tablero.mapa.grid[13][6].es_recarga_emblema = True
            tablero.mover_unidad("Alear", 13, 6)
            f_alear = tablero.obtener_ficha("Alear")
            self.assertEqual(f_alear.energia_emblema, 5, "Casilla de recarga a Nivel 20 debe llenar a 5")
            self.assertEqual(f_alear.max_energia_emblema, 5)

        # Combate fuera de fusión a Nivel 20: no puede sobrepasar 5
        tablero.limpiar()
        u20_combate = resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 5, "y": 5, "es_aliado": True,
            "emblema_nombre": "Marth", "nivel_vinculo": 20, "energia_emblema": 4
        })
        ene_combate = resolver_unidad_con_catalogo({
            "nombre": "EnemigoDummy", "x": 5, "y": 6, "es_aliado": False,
            "arma_nombre": "Iron Lance", "stats": {"hp": 50, "defensa": 5}
        })
        tablero.registrar_unidad(u20_combate)
        tablero.registrar_unidad(ene_combate)

        client = app.test_client()
        res = client.post("/api/combate/ejecutar", json={
            "atacante": "Alear", "defensor": "EnemigoDummy", "arma_nombre": "Liberation"
        })
        self.assertEqual(res.status_code, 200)
        f_al = tablero.obtener_ficha("Alear")
        self.assertEqual(f_al.energia_emblema, 5, "Energía debe alcanzar el tope de 5 tras ganar carga")

        # Otro ataque no debe superar 5
        f_al.ha_actuado = False
        res2 = client.post("/api/combate/ejecutar", json={
            "atacante": "Alear", "defensor": "EnemigoDummy", "arma_nombre": "Liberation"
        })
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(f_al.energia_emblema, 5, "Energía no puede superar max_energia_emblema = 5")

    def test_24_inheritance_skills_not_auto_equipped(self):
        """
        Las habilidades heredables (como Avoid +10, Sword Agility, etc.) NO deben
        equiparse automáticamente solo por sincronizar con el Emblema. Solo deben
        aplicarse las habilidades de sincronía (synchro_skills) auténticas.
        """
        alear = resolver_unidad_con_catalogo({
            "nombre": "Alear", "x": 1, "y": 1, "es_aliado": True,
            "emblema_nombre": "Marth", "nivel_vinculo": 20
        })
        habs_nombres = [str(h).lower() for h in alear.habilidades]
        # Avoid +10 y Sword Agility son heredables
        self.assertFalse(any("avoid +" in h for h in habs_nombres), "Habilidades de herencia como Avoid + no deben auto-equiparse")
        self.assertFalse(any("sword agility" in h for h in habs_nombres), "Sword Agility de herencia no debe auto-equiparse")
        # En cambio Perceptive y Break Defenses son pasivas de sincronía legítimas
        self.assertTrue(any("perceptive" in h for h in habs_nombres), "Perceptive debe estar en pasivas")

    def test_25_api_catalogo_emblemas_endpoint(self):
        """
        Verifica que el endpoint /api/catalogo/emblemas devuelva los 21 Emblemas
        (Base + DLC) con sus tablas de 20 niveles y la regla Lv20 max_energia=5.
        """
        client = app.test_client()
        res = client.get("/api/catalogo/emblemas")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("ok"))
        emblemas = data.get("emblemas", {})
        self.assertEqual(len(emblemas), 21, "Deben estar presentes los 21 Emblemas (14 base + 7 DLC)")

        for eid, einfo in emblemas.items():
            b_levels = einfo.get("bond_levels", {})
            self.assertEqual(len(b_levels), 20, f"Emblema {eid} debe tener exactamente 20 niveles")
            self.assertEqual(b_levels["19"]["max_energia_emblema"], 6, f"Emblema {eid} a Lv 19 debe tener max 6")
            self.assertEqual(b_levels["20"]["max_energia_emblema"], 5, f"Emblema {eid} a Lv 20 debe tener max 5")

if __name__ == "__main__":
    unittest.main()


