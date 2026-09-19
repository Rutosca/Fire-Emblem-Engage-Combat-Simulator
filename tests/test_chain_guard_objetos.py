"""
Guardia en Cadena (Qi Adept) y uso de objetos desde la API.

Origen: tests/test_fixes_tactical.py (partido por dominio el 2026-09-18).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import app, tablero, resolver_unidad_con_catalogo  # noqa: E402
from motor_calculo import Unidad, Arma  # noqa: E402
from estado_tablero import FichaUnidad  # noqa: E402


class TestChainGuardObjetos(unittest.TestCase):

    def setUp(self):
        # resolver_unidad_con_catalogo lee app.tablero para heredar estado: empezar siempre limpio
        tablero.limpiar()

    def test_chain_guard_activacion_y_toggle_en_fase_enemiga(self):
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

    def test_qi_adept_abarca_monk_master_dancer_y_custom(self):
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

    def test_usar_objeto_consume_uso_y_marca_actuado(self):
        """
        /api/unidad/usar_objeto debe: 1) descontar un uso del objeto indicado
        (eliminándolo del inventario al llegar a 0), y 2) marcar ha_actuado=True
        de forma definitiva (no alternable), a diferencia de alternar_actuado.
        """
        tablero.limpiar()
        yunaka = resolver_unidad_con_catalogo({
            "nombre": "Yunaka", "x": 5, "y": 5, "es_aliado": True,
            "inventario": [{"nombre": "Heal", "usos": 1, "usos_max": 3}],
            "stats": {"hp": 24, "magia": 8}
        })
        tablero.registrar_unidad(yunaka)

        client = app.test_client()
        res = client.post("/api/unidad/usar_objeto", json={"nombre": "Yunaka", "item_nombre": "Heal"})
        data = res.get_json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["ficha"]["ha_actuado"], "La unidad debe quedar marcada como actuada")
        nombres_inv = [it.get("nombre") for it in data["ficha"]["inventario"]]
        self.assertNotIn("Heal", nombres_inv, "El bastón debe eliminarse del inventario al agotar sus usos")

        # Llamar de nuevo (p.ej. tras curar a otro objetivo por error) NO debe
        # des-marcar ha_actuado, a diferencia de lo que haría alternar_actuado
        res2 = client.post("/api/unidad/usar_objeto", json={"nombre": "Yunaka", "item_nombre": "Heal"})
        data2 = res2.get_json()
        self.assertTrue(data2["ficha"]["ha_actuado"], "Una segunda llamada no debe des-marcar ha_actuado")

if __name__ == "__main__":
    unittest.main()
