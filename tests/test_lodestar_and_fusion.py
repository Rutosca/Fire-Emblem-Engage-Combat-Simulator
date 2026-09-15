import unittest
from motor_calculo import CalculadoraEngage, Unidad, Arma, Terreno
from catalogo_loader import resolver_unidad_con_catalogo
from estado_tablero import EstadoTablero, FichaUnidad
from motor_analisis import _armas_aliado


class TestLodestarAndFusion(unittest.TestCase):

    def test_lodestar_rush_zero_damage_against_lance_armor(self):
        """Contra un Lance Armor con defensa alta, Libération debe hacer 0x9 = 0 dmg, nunca 1x9."""
        alear = Unidad(
            nombre="Alear",
            hp=22, fuerza=12, magia=0, destreza=9, velocidad=11,
            defensa=8, resistencia=3, suerte=8, complexion=7,
            estilo_combate="Dragón", tipo_movimiento="Dragón",
            en_fusion=True, turnos_fusion_restantes=3
        )
        lance_armor = Unidad(
            nombre="Lance Armor",
            hp=28, fuerza=10, magia=0, destreza=7, velocidad=1,
            defensa=22, resistencia=0, suerte=2, complexion=9,
            estilo_combate="Acorazado", tipo_movimiento="Acorazado"
        )
        liberation = Arma(nombre="Libération", mt=7, hit=90, crit=0, wt=5, tipo="Espada", rango=[1])
        lance = Arma(nombre="Iron Lance", mt=7, hit=80, crit=0, wt=8, tipo="Lanza", rango=[1])

        # Simular Lodestar Rush con Libération
        combate = CalculadoraEngage.simular_combate(
            atacante=alear,
            defensor=lance_armor,
            arma_atk=liberation,
            arma_def=lance,
            terreno_atk=Terreno(),
            terreno_def=Terreno(),
            distancia=1,
            es_engage_attack=True,
            engage_attack_nombre="Lodestar Rush"
        )

        atk_res = combate["atacante"]
        num_g, dmg_g = atk_res.get("lodestar_hits", (0, 0))
        self.assertEqual(num_g, 9, "Alear es dragón, debe asestar 9 golpes en Lodestar Rush")
        self.assertEqual(dmg_g, 0, "Libération (Atk 19) no supera Def 22, cada golpe debe ser 0 dmg (no 1x9)")
        self.assertEqual(atk_res["daño_total_ronda"], 0, "El daño total debe ser exactamente 0")

    def test_lodestar_rush_with_rapier_effective_damage(self):
        """Con Rapier (Emblema), efectividad anti-acorazado (Mt 7*3=21) genera daño masivo redondeado hacia arriba."""
        alear = Unidad(
            nombre="Alear",
            hp=22, fuerza=12, magia=0, destreza=9, velocidad=11,
            defensa=8, resistencia=3, suerte=8, complexion=7,
            estilo_combate="Dragón", tipo_movimiento="Dragón",
            en_fusion=True, turnos_fusion_restantes=3
        )
        lance_armor = Unidad(
            nombre="Lance Armor",
            hp=40, fuerza=10, magia=0, destreza=7, velocidad=1,
            defensa=22, resistencia=0, suerte=2, complexion=9,
            estilo_combate="Acorazado", tipo_movimiento="Acorazado"
        )
        rapier = Arma(
            nombre="Rapier (Emblema)", mt=7, hit=95, crit=10, wt=5, tipo="Espada", rango=[1],
            efectividades=["acorazado", "caballeria"]
        )
        lance = Arma(nombre="Iron Lance", mt=7, hit=80, crit=0, wt=8, tipo="Lanza", rango=[1])

        combate = CalculadoraEngage.simular_combate(
            atacante=alear,
            defensor=lance_armor,
            arma_atk=rapier,
            arma_def=lance,
            terreno_atk=Terreno(),
            terreno_def=Terreno(),
            distancia=1,
            es_engage_attack=True,
            engage_attack_nombre="Lodestar Rush"
        )

        atk_res = combate["atacante"]
        num_g, dmg_g = atk_res.get("lodestar_hits", (0, 0))
        # Atk efectivo = 12 + (7 * 3) = 33
        # Daño neto = 33 - 22 = 11
        # Daño por golpe = ceil(11 * 0.3) = ceil(3.3) = 4
        # Daño total = 4 * 9 = 36
        self.assertEqual(num_g, 9)
        self.assertEqual(dmg_g, 4, "Rapier debe hacer 4 dmg por golpe con ceil(11 * 0.3)")
        self.assertEqual(atk_res["daño_total_ronda"], 36, "Daño total debe ser 36 (suficiente para derrotar los 28 HP del acorazado)")

    def test_lodestar_rush_hits_by_style(self):
        """Verifica que el número de golpes de Lodestar Rush sea 9 para Dragón, 8 para Apoyo y 7 para otros."""
        dragon = Unidad(nombre="Alear", hp=30, fuerza=15, estilo_combate="Dragón")
        backup = Unidad(nombre="Lapis", hp=30, fuerza=15, estilo_combate="Apoyo")
        cavalry = Unidad(nombre="Alfred", hp=30, fuerza=15, estilo_combate="Caballería")
        target = Unidad(nombre="Enemy", hp=40, defensa=5)
        sword = Arma(nombre="Iron Sword", mt=5, hit=90, tipo="Espada", rango=[1])

        c_d = CalculadoraEngage.simular_combate(dragon, target, sword, sword, Terreno(), Terreno(), 1, es_engage_attack=True, engage_attack_nombre="Lodestar Rush")
        c_b = CalculadoraEngage.simular_combate(backup, target, sword, sword, Terreno(), Terreno(), 1, es_engage_attack=True, engage_attack_nombre="Lodestar Rush")
        c_c = CalculadoraEngage.simular_combate(cavalry, target, sword, sword, Terreno(), Terreno(), 1, es_engage_attack=True, engage_attack_nombre="Lodestar Rush")

        self.assertEqual(c_d["atacante"]["lodestar_hits"][0], 9)
        self.assertEqual(c_b["atacante"]["lodestar_hits"][0], 8)
        self.assertEqual(c_c["atacante"]["lodestar_hits"][0], 7)

    def test_emblem_weapon_tagged_requiere_fusion_when_not_fused(self):
        """Si un aliado tiene 6/6 de energía pero NO está en fusión, las armas de emblema tienen requiere_fusion = True."""
        f_alear = resolver_unidad_con_catalogo({
            "nombre": "Alear",
            "es_aliado": True,
            "emblema_nombre": "Marth",
            "nivel_vinculo": 10,
            "en_fusion": False,
            "energia_emblema": 6,
            "max_energia_emblema": 6,
            "inventario": [{"nombre": "Libération", "equipada": True}]
        })

        armas = _armas_aliado(f_alear)
        armas_dict = {a.nombre: a for a, _, _ in armas}

        # Rapier (Emblema) debe estar disponible pero requerir Fusión
        self.assertIn("Rapier (Emblema)", armas_dict)
        self.assertTrue(getattr(armas_dict["Rapier (Emblema)"], "requiere_fusion", False))

        # Lodestar Rush debe estar disponible y requerir Fusión
        lodestar_keys = [k for k in armas_dict if "Lodestar Rush" in k]
        self.assertTrue(len(lodestar_keys) > 0)
        for k in lodestar_keys:
            self.assertTrue(getattr(armas_dict[k], "requiere_fusion", False))

    def test_end_of_fusion_recharge_gauge_zero(self):
        """Al expirar la Fusión, la energía queda en 0/6 y se persiste al guardar."""
        tablero = EstadoTablero(mapa=None, auto_cargar_spawns=False)
        f_alear = resolver_unidad_con_catalogo({
            "nombre": "Alear",
            "es_aliado": True,
            "emblema_nombre": "Marth",
            "nivel_vinculo": 10,
            "en_fusion": True,
            "turnos_fusion": 1,
            "energia_emblema": 0,
            "max_energia_emblema": 6,
            "x": 2, "y": 2
        })
        tablero.registrar_unidad(f_alear)

        # Iniciar siguiente fase jugador: turnos_fusion pasa de 1 a 0 -> Fin de fusión
        tablero.avanzar_turno()
        f_fin = tablero.obtener_ficha("Alear")
        self.assertFalse(f_fin.en_fusion, "La unidad debe dejar de estar en Fusión")
        self.assertEqual(f_fin.turnos_fusion, 0)
        self.assertEqual(f_fin.energia_emblema, 0, "La energía debe ser 0 tras el fin de fusión")

        # Al re-guardar la ficha enviando energia_emblema=0, debe mantenerse en 0
        f_actualizada = resolver_unidad_con_catalogo({
            "nombre": "Alear",
            "energia_emblema": 0,
            "max_energia_emblema": 6
        }, tablero=tablero)
        self.assertEqual(f_actualizada.energia_emblema, 0, "No debe resetearse a 6 al guardar")


if __name__ == "__main__":
    unittest.main()
