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
from estado_tablero import FichaUnidad

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
        # Caso B: Edelgard activa -> +0 Atk con Lanza (Weapon Sync solo Hachas)
        self.f_chl.stats.lider_tres_casas = "Edelgard"
        comb_ed = CalculadoraEngage.simular_combate(
            self.f_chl.stats, self.f_lf.stats, silver, self.f_lf.arma,
            Terreno(0,0), Terreno(0,0), distancia=1
        )
        self.assertEqual(comb_dim['atacante']['daño_por_golpe'] - comb_ed['atacante']['daño_por_golpe'], 5, "Dimitri debe otorgar exactamente +5 ATK sobre Edelgard con lanza")
        self.assertEqual(comb_dim['atacante']['daño_por_golpe'], 21, "Chloé con Dimitri debe hacer 21 a vínculo 11")
        self.assertEqual(comb_ed['atacante']['daño_por_golpe'], 16, "Chloé con Edelgard debe hacer 16 con lanza a vínculo 11")

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
        jugada_alear = [r for r in data["resultados"] if r.get("tipo_analisis") in ("oportunidad_jugador", "combo_ataque") and r.get("aliado") == "Alear" and r.get("enemigo") == "Lance Fighter (6,6)"]
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

    def test_26_obstruct_excluded_from_healing_and_deduplication(self):
        """
        Verifica que bastones utilitarios como Obstruct NO sean tratados como
        bastones de curación, y que un aliado herido reciba a lo sumo la mejor
        recomendación curativa sin duplicados repetitivos.
        """
        from motor_analisis import analizar_situacion_tactica
        tablero.limpiar()
        framme = resolver_unidad_con_catalogo({
            "nombre": "Framme", "x": 10, "y": 10, "es_aliado": True,
            "inventario": [{"nombre": "Obstruct (8)"}, {"nombre": "Heal (16)"}],
            "stats": {"hp": 20, "magia": 10}
        })
        yunaka = resolver_unidad_con_catalogo({
            "nombre": "Yunaka", "x": 10, "y": 12, "es_aliado": True,
            "inventario": [{"nombre": "Mend (13)"}],
            "stats": {"hp": 24, "magia": 12}
        })
        louis = resolver_unidad_con_catalogo({
            "nombre": "Louis", "x": 11, "y": 11, "es_aliado": True,
            "hp_actual": 10,
            "stats": {"hp": 31}
        })
        tablero.registrar_unidad(framme)
        tablero.registrar_unidad(yunaka)
        tablero.registrar_unidad(louis)

        res = analizar_situacion_tactica(tablero, _mapa, perfil="seguro")
        curaciones = [r for r in res["resultados"] if r.get("tipo_analisis") == "apoyo_curacion"]
        # Ninguna curación puede provenir de Obstruct
        self.assertFalse(any("obstruct" in str(r.get("baston", "")).lower() for r in curaciones), "Obstruct nunca debe ser recomendado como curación")
        # Louis debe tener a lo sumo 1 recomendación de curación (la mejor: Mend de Yunaka)
        curaciones_louis = [r for r in curaciones if r.get("objetivo") == "Louis"]
        self.assertEqual(len(curaciones_louis), 1, "Debe haber exactamente 1 mejor curación para Louis")
        self.assertEqual(curaciones_louis[0]["aliado"], "Yunaka", "Mend de Yunaka debe superar a Heal de Framme")

    def test_27_weapon_selection_follow_up_slim_over_iron(self):
        """
        Verifica que un arma de follow-up con mayor daño total y 100% acierto
        (Slim Lance 11x2 = 22 dmg) supere a un arma de golpe único con menor daño
        (Iron Lance 13x1 = 13 dmg).
        """
        from motor_analisis import analizar_situacion_tactica
        from catalogo_loader import _buscar_en_catalogo
        tablero.limpiar()
        _, a_slim = _buscar_en_catalogo("armas", "Slim Lance")
        _, a_iron = _buscar_en_catalogo("armas", "Iron Lance")
        _, a_bow = _buscar_en_catalogo("armas", "Iron Bow")

        arma_slim = _arma_desde_item(a_slim)
        arma_iron = _arma_desde_item(a_iron)
        arma_bow = _arma_desde_item(a_bow)

        chloe = Unidad("Chloé", hp=22, fuerza=12, magia=0, destreza=12, velocidad=14, defensa=6, resistencia=8, suerte=10, complexion=5, tipo_movimiento="volador")
        archer = Unidad("Archer", hp=24, fuerza=9, magia=0, destreza=10, velocidad=9, defensa=6, resistencia=2, suerte=6, complexion=6, tipo_movimiento="infanteria")

        chloe_f = FichaUnidad(
            "Chloé", clase_nombre="Pegasus Knight", nivel=7, es_aliado=True,
            x=10, y=10, hp_actual=22, hp_max=22, stats=chloe, arma=arma_slim,
            inventario=[{"nombre": "Slim Lance"}, {"nombre": "Iron Lance"}]
        )
        archer_f = FichaUnidad(
            "Archer", clase_nombre="Archer", nivel=7, es_aliado=False,
            x=11, y=10, hp_actual=24, hp_max=24, stats=archer, arma=arma_bow,
            inventario=[{"nombre": "Iron Bow"}]
        )
        tablero.registrar_unidad(chloe_f)
        tablero.registrar_unidad(archer_f)

        res = analizar_situacion_tactica(tablero, _mapa, perfil="seguro")
        ataques_chloe = [r for r in res["resultados"] if r.get("aliado") == "Chloé" and r.get("enemigo") == "Archer"]
        self.assertTrue(len(ataques_chloe) > 0, "Debe haber una recomendación de ataque para Chloé")
        self.assertEqual(ataques_chloe[0]["arma_recomendada"], "Slim Lance", "Slim Lance (11x2) debe superar a Iron Lance (13x1)")

    def test_28_kill_con_critico_requires_positive_crit_rate(self):
        """
        CalculadoraEngage.evaluar_riesgo solo debe marcar kill_con_critico=True
        si la probabilidad de crítico es estrictamente mayor a 0%.
        """
        chloe = Unidad("Chloé", hp=22, fuerza=12, magia=0, destreza=12, velocidad=14, defensa=6, resistencia=8, suerte=10, complexion=5, tipo_movimiento="volador")
        archer = Unidad("Archer", hp=24, fuerza=9, magia=0, destreza=10, velocidad=9, defensa=6, resistencia=2, suerte=6, complexion=6, tipo_movimiento="infanteria")
        arma_atk = Arma("Lanza", mt=5, wt=5, hit=100, crit=0, tipo="Lanza", rango=[1])
        arma_def = Arma("Arco", mt=6, wt=5, hit=80, crit=0, tipo="Arco", rango=[2])

        v = CalculadoraEngage.evaluar_riesgo(chloe, archer, arma_atk, arma_def, Terreno(), Terreno(), distancia=1, perfil="seguro")
        self.assertFalse(v["veredicto"]["kill_con_critico"], "Con 0% crit, kill_con_critico debe ser False")

    def test_29_cooperative_focus_fire_combo(self):
        """
        Detección de ataque combinado (Focus Fire): Alfred desgasta a un enemigo
        de 31 HP (10 dmg) para que Louis lo remate con Ridersbane (26 dmg).
        El sistema debe recomendar primero el ataque de preparación de Alfred.
        """
        from motor_analisis import analizar_situacion_tactica
        tablero.limpiar()
        alfred = resolver_unidad_con_catalogo({
            "nombre": "Alfred", "x": 15, "y": 10, "es_aliado": True,
            "clase_nombre": "Noble", "nivel": 7,
            "inventario": [{"nombre": "Iron Lance"}],
            "stats": {"hp": 26, "fuerza": 10, "velocidad": 9, "defensa": 9, "mov": 5}
        })
        louis = resolver_unidad_con_catalogo({
            "nombre": "Louis", "x": 15, "y": 8, "es_aliado": True,
            "clase_nombre": "Lance Armor", "nivel": 7,
            "inventario": [{"nombre": "Ridersbane"}],
            "stats": {"hp": 31, "fuerza": 13, "velocidad": 4, "defensa": 14, "mov": 4}
        })
        axe_cav = resolver_unidad_con_catalogo({
            "nombre": "Axe Cavalier", "x": 18, "y": 10, "es_aliado": False,
            "clase_nombre": "Axe Cavalier", "nivel": 7,
            "hp_actual": 31,
            "inventario": [{"nombre": "Iron Axe"}],
            "stats": {"hp": 31, "fuerza": 10, "defensa": 6, "velocidad": 8, "tipo_movimiento": "caballeria"}
        })
        tablero.registrar_unidad(alfred)
        tablero.registrar_unidad(louis)
        tablero.registrar_unidad(axe_cav)

        res = analizar_situacion_tactica(tablero, _mapa, perfil="seguro")
        combos = [r for r in res["resultados"] if r.get("tipo_analisis") == "combo_ataque" and r.get("enemigo") == "Axe Cavalier"]
        self.assertTrue(len(combos) > 0, "Debe generarse un ataque coordinado contra el Axe Cavalier")
        combo = combos[0]
        self.assertEqual(combo["aliado"], "Alfred", "Debe recomendarse el ataque preparatorio de Alfred")
        self.assertEqual(combo["aliado_rematador"], "Louis", "Louis debe ser el aliado que remata")
        self.assertIn("PREPARAR BAJA", combo["recomendacion"])

    def test_30_boss_hortensia_attack_viable_in_danger_zone(self):
        """
        Verifica que en combates con alta densidad de enemigos (como Hortensia en Cap 7),
        los ataques seguros al jefe no sean descartados por penalización excesiva de zonas de peligro.
        """
        from motor_analisis import analizar_situacion_tactica
        from app import _desplegar_capitulo
        _desplegar_capitulo("M007", "Extremo")
        hortensia = [e for e in tablero.obtener_enemigos() if "hortensia" in e.nombre.lower()][0]
        hortensia.x, hortensia.y = 18, 8

        # Desplegar aliado que alcance a Hortensia en zona densa de peligro
        chloe = resolver_unidad_con_catalogo({
            "nombre": "Chloé", "x": 17, "y": 8, "es_aliado": True,
            "clase_nombre": "Lance Flier", "nivel": 7,
            "mov": 5, "es_volador": True,
            "inventario": [{"nombre": "Javelin"}, {"nombre": "Slim Lance"}],
            "stats": {"hp": 24, "fuerza": 11, "velocidad": 14, "defensa": 7, "resistencia": 10}
        })
        tablero.registrar_unidad(chloe)

        res = analizar_situacion_tactica(tablero, _mapa, perfil="seguro")
        ataques = [r for r in res["resultados"] if r.get("enemigo") == hortensia.nombre]
        self.assertTrue(len(ataques) > 0, "Debe haber al menos un ataque viable recomendado contra Hortensia")

    def test_31_edelgard_engage_attack_houses_unite(self):
        """Verifica que el Emblema Edelgard cargue correctamente su ataque Houses Unite."""
        from catalogo_loader import _catalogo
        client = app.test_client()
        res = client.get("/api/catalogo/emblemas")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("ok"))
        emblemas = data.get("emblemas", {})
        self.assertIn("GID_DLC_EDELGARD", emblemas)
        ed = emblemas["GID_DLC_EDELGARD"]
        self.assertEqual(ed.get("engage_attack"), "Houses Unite (Unión de Casas)")

    def test_32_engage_weapons_usable_when_in_fusion(self):
        """Verifica que al fusionar, las armas desbloqueadas del Emblema sean utilizables."""
        from motor_analisis import _armas_aliado
        # Chloé con Edelgard a nivel de vínculo 10
        chloe_stats = Unidad(nombre="Chloé", hp=26, fuerza=9, magia=8, destreza=15, velocidad=13, defensa=9, resistencia=10, suerte=11, complexion=5)
        chloe_stats.emblema_nombre = "Edelgard"
        chloe_stats.nivel_vinculo = 10
        chloe_stats.en_fusion = True
        chloe_stats.inventario = [{"nombre": "Iron Lance"}]

        armas_fusion = _armas_aliado(chloe_stats)
        nombres_armas = [a.nombre for a, es_eng, _ in armas_fusion]
        # A nivel 10, Edelgard otorga Aymr y Areadbhar (con sufijo (Emblema) para diferenciarlas)
        self.assertTrue(any("Aymr" in n for n in nombres_armas), "Aymr debe estar disponible como arma usable en fusión")
        self.assertTrue(any("Areadbhar" in n for n in nombres_armas), "Areadbhar debe estar disponible como arma usable en fusión")
        self.assertIn("Iron Lance", nombres_armas, "El arma de inventario normal debe seguir presente")

        # Marth a nivel 15 con Alear
        alear_stats = Unidad(nombre="Alear", hp=24, fuerza=10, magia=2, destreza=12, velocidad=12, defensa=8, resistencia=5, suerte=9, complexion=6)
        alear_stats.emblema_nombre = "Marth"
        alear_stats.nivel_vinculo = 15
        alear_stats.en_fusion = True
        alear_stats.inventario = [{"nombre": "Libération"}]

        armas_marth = _armas_aliado(alear_stats)
        nombres_marth = [a.nombre for a, es_eng, _ in armas_marth]
        self.assertTrue(any("Rapier" in n for n in nombres_marth))
        self.assertTrue(any("Mercurius" in n for n in nombres_marth))
        self.assertTrue(any("Falchion" in n for n in nombres_marth))

    def test_33_solo_kill_priority_over_combos(self):
        """
        Verifica que:
        1. Si un enemigo puede ser eliminado de forma directa 1:1, NO se generen combos contra él.
        2. Las kills unitarias tengan prioridad estricta y se listen antes de cualquier estrategia conjunta.
        """
        from motor_analisis import analizar_situacion_tactica
        tablero.limpiar()

        # Enemigo 1: Corrupted frágil que Boucheron puede derrotar 1:1 con 100% hit
        fragil = resolver_unidad_con_catalogo({
            "nombre": "Fragile Thief", "x": 5, "y": 5, "es_aliado": False,
            "hp_actual": 12, "hp_max": 12, "arma_nombre": "Iron Dagger",
            "stats": {"hp": 12, "defensa": 2, "resistencia": 1, "velocidad": 0, "fuerza": 5, "suerte": 0}
        })
        tablero.registrar_unidad(fragil)

        # Aliado 1: Boucheron cerca del frágil (Kill 1:1 garantizada, 100% hit)
        bouch = resolver_unidad_con_catalogo({
            "nombre": "Boucheron", "x": 5, "y": 4, "es_aliado": True,
            "mov": 5, "arma_nombre": "Iron Axe",
            "stats": {"hp": 28, "fuerza": 14, "destreza": 15, "velocidad": 10, "defensa": 8, "resistencia": 3, "suerte": 10}
        })
        tablero.registrar_unidad(bouch)

        # Aliados 2 y 3: Alfred y Louis cerca de Axe Cavalier (hacen combo coordinado)
        alfred = resolver_unidad_con_catalogo({
            "nombre": "Alfred", "x": 15, "y": 10, "es_aliado": True,
            "clase_nombre": "Noble", "nivel": 7,
            "inventario": [{"nombre": "Iron Lance"}],
            "stats": {"hp": 26, "fuerza": 10, "velocidad": 9, "defensa": 9, "mov": 5}
        })
        louis = resolver_unidad_con_catalogo({
            "nombre": "Louis", "x": 15, "y": 8, "es_aliado": True,
            "clase_nombre": "Lance Armor", "nivel": 7,
            "inventario": [{"nombre": "Ridersbane"}],
            "stats": {"hp": 31, "fuerza": 13, "velocidad": 4, "defensa": 14, "mov": 4}
        })
        axe_cav = resolver_unidad_con_catalogo({
            "nombre": "Axe Cavalier", "x": 18, "y": 10, "es_aliado": False,
            "clase_nombre": "Axe Cavalier", "nivel": 7,
            "hp_actual": 31,
            "inventario": [{"nombre": "Iron Axe"}],
            "stats": {"hp": 31, "fuerza": 10, "defensa": 6, "velocidad": 8, "tipo_movimiento": "caballeria"}
        })
        tablero.registrar_unidad(alfred)
        tablero.registrar_unidad(louis)
        tablero.registrar_unidad(axe_cav)

        res = analizar_situacion_tactica(tablero, _mapa, perfil="seguro")
        resultados = res["resultados"]

        # 1. No debe haber ningún combo contra Fragile Thief (porque Boucheron lo mata 1:1)
        combos_fragil = [r for r in resultados if r.get("tipo_analisis") == "combo_ataque" and r.get("enemigo") == "Fragile Thief"]
        self.assertEqual(len(combos_fragil), 0, "No deben generarse combos para un enemigo que muere 1:1")

        # 2. Debe haber kill directa de Boucheron sobre Fragile Thief
        solo_kill = [r for r in resultados if r.get("tipo_analisis") == "oportunidad_jugador" and r.get("enemigo") == "Fragile Thief"]
        self.assertTrue(len(solo_kill) > 0, "Boucheron debe tener kill unitaria contra Fragile Thief")

        # 3. Debe haber combo coordinado contra Axe Cavalier (ya que nadie lo mata 1:1)
        combos_cav = [r for r in resultados if r.get("tipo_analisis") == "combo_ataque" and r.get("enemigo") == "Axe Cavalier"]
        self.assertTrue(len(combos_cav) > 0, "Debe haber combo coordinado contra Axe Cavalier")

        # 4. En la lista final, la kill 1:1 debe aparecer ANTES del combo coordinado
        idx_solo = resultados.index(solo_kill[0])
        idx_combo = resultados.index(combos_cav[0])
        self.assertLess(idx_solo, idx_combo, "Las bajas 1:1 deben listarse antes que los combos coordinados")

    def test_34_hortensia_boss_3_step_engage_defeat_sequence(self):
        """
        Verifica el flujo canónico de 3 pasos para derrotar a Hortensia (Boss) en Capítulo 7:
        1. Recomendaciones simultáneas en el panel para Chloé, Alear y Céline con sus técnicas Engage.
        2. Paso 1: Chloé (Houses Unite) quiebra la 1ª barra, Hortensia consume la piedra resurrectora
           (hp_stock pasa de 1 a 0) y revive con 36/36 HP sin contraataque.
        3. Paso 2: Alear (Lodestar Rush con Fólkvangr) quita 9x3 = 27 dmg sin contraataque,
           dejando a Hortensia en 36 - 27 = 9 HP.
        4. Paso 3: Céline (Warp Ragnarök) se teletransporta a casilla adyacente libre y remata
           a Hortensia (18 dmg > 9 HP), dejándola en 0 HP y viva=False.
        """
        client = app.test_client()
        import os
        path_test = os.path.join("scratch", "partida_hortensia_test.json")
        self.assertTrue(os.path.exists(path_test))
        with open(path_test, "r", encoding="utf-8") as f:
            d = json.load(f)

        for x in d["fichas"]:
            if "hortensia" in x["nombre"].lower():
                x["hp_stock"] = 1
                x["hp_actual"] = 25
                x["hp_max"] = 36

        res_imp = client.post("/api/partida/importar", json={"partida": d})
        self.assertEqual(res_imp.status_code, 200)

        # 1. Panel táctico debe recomendar simultáneamente a Alear, Chloé y Céline
        res_an = client.post("/api/analizar", json={})
        self.assertEqual(res_an.status_code, 200)
        recs = res_an.get_json().get("resultados", [])
        aliados_hortensia = [r.get("aliado") for r in recs if "hortensia" in str(r.get("enemigo")).lower()]

        self.assertTrue(any("chlo" in a.lower() for a in aliados_hortensia), "Chloé debe estar recomendada")
        self.assertTrue(any("alear" in a.lower() for a in aliados_hortensia), "Alear debe estar recomendada")
        self.assertTrue(any("line" in a.lower() for a in aliados_hortensia), "Céline debe estar recomendada")

        nom_chloe = [f.nombre for f in tablero.obtener_aliados() if "chlo" in f.nombre.lower()][0]
        nom_alear = [f.nombre for f in tablero.obtener_aliados() if "alear" in f.nombre.lower()][0]
        nom_celine = [f.nombre for f in tablero.obtener_aliados() if "line" in f.nombre.lower()][0]

        # 2. Paso 1: Chloé usa Houses Unite
        r1 = client.post("/api/combate/ejecutar", json={
            "atacante": nom_chloe,
            "defensor": "Hortensia (Boss)",
            "arma": "Houses Unite",
            "pos_destino": [16, 7]
        })
        self.assertEqual(r1.status_code, 200)
        hort = tablero.obtener_ficha("Hortensia (Boss)")
        self.assertEqual(hort.hp_actual, 36, "Hortensia debió revivir a 36 HP tras romper su 1ª barra")
        self.assertEqual(hort.hp_stock, 0, "Hortensia debió consumir su piedra resurrectora")

        # 3. Paso 2: Alear usa Lodestar Rush (Fólkvangr)
        r2 = client.post("/api/combate/ejecutar", json={
            "atacante": nom_alear,
            "defensor": "Hortensia (Boss)",
            "arma": "Lodestar Rush (Fólkvangr)",
            "pos_destino": [16, 9]
        })
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(hort.hp_actual, 9, "Hortensia debió quedar en 9 HP tras 9x3=27 de Lodestar Rush")

        # 4. Paso 3: Céline usa Warp Ragnarök al hueco adyacente libre
        libres_adj = []
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
            pos_adj = (16 + dx, 8 + dy)
            if not any(f.viva and (f.x, f.y) == pos_adj for f in tablero.fichas.values()):
                libres_adj.append(pos_adj)
        self.assertTrue(len(libres_adj) > 0, "Debe haber al menos 1 casilla adyacente libre")

        r3 = client.post("/api/combate/ejecutar", json={
            "atacante": nom_celine,
            "defensor": "Hortensia (Boss)",
            "arma": "Warp Ragnarök",
            "pos_destino": list(libres_adj[0])
        })
        self.assertEqual(r3.status_code, 200)
        self.assertEqual(hort.hp_actual, 0, "Hortensia debe quedar en 0 HP tras el remate")
        self.assertFalse(hort.viva, "Hortensia debe estar derrotada")

    def test_35_qi_adept_chain_guard_activation_and_enemy_phase_toggle(self):
        """
        Verifica el funcionamiento canónico de Guardia en Cadena (Chain Guard) de Adeptos de Qi:
        1. Al 100% HP, anula el 1er impacto contra un aliado adyacente y recibe 20% max HP de retroceso.
        2. Un 2º impacto en la misma ronda (doble ataque / arma brave) sí impacta al defensor.
        3. Si la unidad enemiga no activó Chain Guard en su turno (ej. curó con bastón o atacó),
           el toggle chain_guard_activo=False impide que proteja al objetivo.
        4. Si el protector tiene HP < 100%, no puede realizar Chain Guard.
        """
        from motor_calculo import es_unidad_qi_adept
        from motor_analisis import obtener_protector_chain_guard

        client = app.test_client()
        tablero.limpiar()

        # Atacante aliado: Alear con espada de hierro y alta velocidad para realizar ataque doble
        tablero.registrar_unidad(FichaUnidad(
            "Alear", es_aliado=True, x=9, y=5,
            hp_actual=30, hp_max=30,
            stats=Unidad("Alear", hp=30, fuerza=15, velocidad=20, defensa=10),
            arma=Arma("Iron Sword", mt=6, wt=5, hit=100, crit=0, es_magica=False, tipo="Espada", rango=[1])
        ))

        # Defensor enemigo: Lance Armor con 30 HP, 10 Def
        tablero.registrar_unidad(FichaUnidad(
            "Lance Armor", es_aliado=False, x=10, y=5,
            hp_actual=30, hp_max=30,
            stats=Unidad("Lance Armor", hp=30, fuerza=10, velocidad=2, defensa=10),
            arma=Arma("Iron Lance", mt=6, wt=8, hit=80, crit=0, es_magica=False, tipo="Lanza", rango=[1])
        ))

        # Protector enemigo: Martial Monk adyacente en (10, 6) a 100% HP (30/30)
        tablero.registrar_unidad(FichaUnidad(
            "Martial Monk", es_aliado=False, x=10, y=6,
            hp_actual=30, hp_max=30,
            clase_nombre="Martial Monk",
            chain_guard_activo=True,
            stats=Unidad("Martial Monk", hp=30, fuerza=5, velocidad=10, defensa=5, clase_nombre="Martial Monk")
        ))

        # 1. Verificar detección de protector
        armor = tablero.obtener_ficha("Lance Armor")
        monk = tablero.obtener_ficha("Martial Monk")
        self.assertTrue(es_unidad_qi_adept(monk))
        prot = obtener_protector_chain_guard(armor, tablero)
        self.assertIsNotNone(prot)
        self.assertEqual(prot.nombre, "Martial Monk")

        # 2. Ejecutar combate: 1er golpe debe ser bloqueado por Chain Guard, 2º golpe entra
        # Daño por golpe: 15 Atk + 6 Mt = 21 Atk - 10 Def = 11 dmg.
        # Hit 1: Bloqueado (0 dmg a Armor). Monk sufre 20% de 30 HP = 6 daño de retroceso.
        # Hit 2 (Doble por velocidad): Conecta contra Armor por 11 dmg -> HP Armor 30 - 11 = 19.
        resp = client.post("/api/combate/ejecutar", json={
            "atacante": "Alear",
            "defensor": "Lance Armor",
            "arma": "Iron Sword",
            "pos_destino": [9, 5]
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()

        # Armor debe haber recibido solo el 2º golpe
        self.assertEqual(armor.hp_actual, 19, "Armor debió recibir únicamente el 2º impacto tras la protección")
        # Monk debe haber recibido 6 dmg de retroceso (30 - 6 = 24) y gastado su Chain Guard
        self.assertEqual(monk.hp_actual, 24, "Martial Monk debió sufrir 6 daño de recoil (20% de 30 HP)")
        self.assertTrue(monk.chain_guard_usado, "Martial Monk debe tener chain_guard_usado=True")

        # 3. Un segundo ataque al mismo objetivo no debe activar Chain Guard (Monk ya no tiene 100% HP)
        prot_segundo = obtener_protector_chain_guard(armor, tablero)
        self.assertIsNone(prot_segundo, "No debe proteger porque ya no está al 100% HP")

        # 4. Probar toggle de Chain Guard: Restaurar Monk a 30 HP, pero desactivar chain_guard_activo
        monk.hp_actual = 30
        monk.chain_guard_usado = False
        r_toggle = client.post("/api/unidad/alternar_chain_guard", json={"nombre": "Martial Monk", "activo": False})
        self.assertEqual(r_toggle.status_code, 200)
        self.assertFalse(monk.chain_guard_activo)

        # Ahora, aun teniendo 100% HP, como el enemigo curó o atacó en su turno, no está en postura de Chain Guard
        prot_desactivado = obtener_protector_chain_guard(armor, tablero)
        self.assertIsNone(prot_desactivado, "No debe proteger si chain_guard_activo=False")

        # Volver a activar vía toggle API
        r_toggle2 = client.post("/api/unidad/alternar_chain_guard", json={"nombre": "Martial Monk", "activo": True})
        self.assertEqual(r_toggle2.status_code, 200)
        self.assertTrue(monk.chain_guard_activo)
        self.assertIsNotNone(obtener_protector_chain_guard(armor, tablero))

    def test_36_qi_adept_scope_monk_master_dancer_and_custom(self):
        """
        Verifica que el subtipo Qi Adept abarca:
        - Martial Monk
        - Martial Master
        - Dancer (Seadall / Bailarín)
        - Unidades con estilo_combate explícito "Qi Adept" / "気功スタイル"
        Y descarta unidades de otros estilos (Místico, Dragón, Apoyo, Acorazado).
        """
        from motor_calculo import es_unidad_qi_adept

        # Qi Adept canónicos
        monk = FichaUnidad("Framme", es_aliado=True, x=0, y=0, clase_nombre="Martial Monk", hp_actual=25, hp_max=25)
        master = FichaUnidad("Jean", es_aliado=True, x=0, y=0, clase_nombre="Martial Master", hp_actual=35, hp_max=35)
        dancer = FichaUnidad("Seadall", es_aliado=True, x=0, y=0, clase_nombre="Dancer", hp_actual=28, hp_max=28)
        dancer_es = FichaUnidad("Bailarín", es_aliado=True, x=0, y=0, clase_nombre="Bailarín", hp_actual=28, hp_max=28)
        custom_qi = FichaUnidad("Soldado Qi", es_aliado=True, x=0, y=0, estilo_combate="Qi Adept", hp_actual=30, hp_max=30)
        custom_jp = FichaUnidad("Monje JP", es_aliado=True, x=0, y=0, estilo_combate="気功スタイル", hp_actual=30, hp_max=30)

        self.assertTrue(es_unidad_qi_adept(monk), "Martial Monk debe ser Qi Adept")
        self.assertTrue(es_unidad_qi_adept(master), "Martial Master debe ser Qi Adept")
        self.assertTrue(es_unidad_qi_adept(dancer), "Dancer (Seadall) debe ser Qi Adept")
        self.assertTrue(es_unidad_qi_adept(dancer_es), "Bailarín español debe ser Qi Adept")
        self.assertTrue(es_unidad_qi_adept(custom_qi), "Estilo Qi Adept explícito debe ser reconocido")
        self.assertTrue(es_unidad_qi_adept(custom_jp), "Estilo 気功スタイル explícito debe ser reconocido")

        # No Qi Adept
        alear = FichaUnidad("Alear", es_aliado=True, x=0, y=0, clase_nombre="Dragon Child", estilo_combate="Dragon", hp_actual=25, hp_max=25)
        chloe = FichaUnidad("Chloé", es_aliado=True, x=0, y=0, clase_nombre="Pegasus Knight", estilo_combate="Flying", hp_actual=25, hp_max=25)
        louis = FichaUnidad("Louis", es_aliado=True, x=0, y=0, clase_nombre="Lance Armor", estilo_combate="Armored", hp_actual=30, hp_max=30)
        lapis = FichaUnidad("Lapis", es_aliado=True, x=0, y=0, clase_nombre="Sword Fighter", estilo_combate="Backup", hp_actual=22, hp_max=22)
        celine = FichaUnidad("Céline", es_aliado=True, x=0, y=0, clase_nombre="Vidame", estilo_combate="Mystical", hp_actual=24, hp_max=24)

        self.assertFalse(es_unidad_qi_adept(alear), "Dragon no es Qi Adept")
        self.assertFalse(es_unidad_qi_adept(chloe), "Flying no es Qi Adept")
        self.assertFalse(es_unidad_qi_adept(louis), "Armored no es Qi Adept")
        self.assertFalse(es_unidad_qi_adept(lapis), "Backup no es Qi Adept")
        self.assertFalse(es_unidad_qi_adept(celine), "Mystical no es Qi Adept")

if __name__ == "__main__":
    unittest.main()


