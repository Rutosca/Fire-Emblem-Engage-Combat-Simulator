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

        # Buscar la jugada de Alear contra Lance Fighter
        jugada_alear = [r for r in data["resultados"] if r.get("aliado") == "Alear" and r.get("enemigo") == "Lance Fighter (6,6)"]
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
        self.assertIn("ataque en cadena", rec)
        self.assertIn("Lapis", rec)
        self.assertIn("80% Hit", rec)
        self.assertIn("3 de daño", rec)
        self.assertIn("Y luego el ataque normal del aliado", rec)

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

if __name__ == "__main__":
    unittest.main()

