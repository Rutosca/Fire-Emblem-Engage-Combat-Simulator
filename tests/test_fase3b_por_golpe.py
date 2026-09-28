"""
Fase 3b — evaluación por golpe.

- Reprisal / Reprisal+ (Verónica, SID_血讐 / SID_血讐＋, Timing 10): Atk + floor((MaxHP − HP) ×
  0.3 / 0.5) en cada golpe PROPIO, con el HP del momento. Tras recibir un contraataque, el
  siguiente golpe pega más (pedido expreso del usuario: puede cambiar a mitad de combate).
- Timing 12 sobre el daño infligido (相手のダメージ): Keen Insight, Camilla's Axe, Infierno
  Oscuro Místico (sus casos verificados en juego están en test_emblema_soren/camilla).
- Bonos de stats del arma equipada (Item.xml Enhance.*).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import pasivas                                                    # noqa: E402
from motor_calculo import CalculadoraEngage, Unidad, Arma, Terreno  # noqa: E402

LANZA = Arma("Iron Lance", tipo="Lanza", mt=6, wt=6, hit=100, crit=0, rango=[1])


def _veronica(hp, habilidad="Reprisal"):
    return Unidad("Veronica", hp=hp, hp_max=40, fuerza=15, magia=4, destreza=20, velocidad=12,
                  defensa=6, resistencia=5, suerte=5, complexion=6,
                  habilidades=[habilidad] if habilidad else [])


def _bruto():
    return Unidad("Bruto", hp=60, hp_max=60, fuerza=22, magia=0, destreza=30, velocidad=3,
                  defensa=8, resistencia=0, suerte=0, complexion=10)


def _golpes(r, actor):
    return [s["daño"] for s in r["resultado"]["secuencia"] if s["actor"] == actor and s["tipo"] != "drenaje"]


class TestReprisal(unittest.TestCase):

    def test_el_follow_up_sube_tras_recibir_el_contraataque(self):
        r = CalculadoraEngage.simular_combate(_veronica(40), _bruto(), LANZA, LANZA, Terreno(), Terreno(), 1)
        base = r["atacante"]["daño_por_golpe"]
        contra = _golpes(r, "Bruto")[0]
        # 1.er golpe a HP lleno (sin bono); el follow-up, con el HP perdido en el contraataque
        self.assertEqual(_golpes(r, "Veronica"), [base, base + int(contra * 0.3)])

    def test_herida_desde_el_principio_ya_suma(self):
        sin = CalculadoraEngage.simular_combate(_veronica(20, None), _bruto(), LANZA, LANZA,
                                                Terreno(), Terreno(), 1)["atacante"]["daño_por_golpe"]
        con = CalculadoraEngage.simular_combate(_veronica(20), _bruto(), LANZA, LANZA,
                                                Terreno(), Terreno(), 1)["atacante"]["daño_por_golpe"]
        self.assertEqual(con - sin, 6, "perdió 20 HP: floor(20 × 0.3)")

    def test_defendiendo_el_contraataque_ya_lleva_el_bono(self):
        r = CalculadoraEngage.simular_combate(_bruto(), _veronica(40), LANZA, LANZA, Terreno(), Terreno(), 1)
        recibido = _golpes(r, "Bruto")[0]
        base = r["defensor"]["daño_por_golpe"]
        bono = int(recibido * 0.3)
        self.assertEqual(_golpes(r, "Veronica"), [base + bono, base + bono])
        self.assertEqual(r["defensor"]["daño_total_ronda"], 2 * (base + bono))

    def test_reprisal_plus_es_la_mitad_del_hp_perdido(self):
        r = CalculadoraEngage.simular_combate(_veronica(20, "Reprisal+"), _bruto(), LANZA, LANZA, Terreno(), Terreno(), 1)
        sin = CalculadoraEngage.simular_combate(_veronica(20, None), _bruto(), LANZA, LANZA, Terreno(), Terreno(), 1)
        self.assertEqual(r["atacante"]["daño_por_golpe"] - sin["atacante"]["daño_por_golpe"], 10)

    def test_sin_reprisal_los_golpes_no_cambian(self):
        r = CalculadoraEngage.simular_combate(_veronica(40, None), _bruto(), LANZA, LANZA, Terreno(), Terreno(), 1)
        base = r["atacante"]["daño_por_golpe"]
        self.assertEqual(_golpes(r, "Veronica"), [base, base])

    def test_se_detecta_como_dependiente_del_hp(self):
        self.assertTrue(pasivas.depende_del_hp_propio(["SID_血讐"]))
        self.assertTrue(pasivas.depende_del_hp_propio(["SID_血讐＋"]))
        self.assertFalse(pasivas.depende_del_hp_propio(["SID_慧眼"]), "Keen Insight no mira el HP")


class TestBonosDelArmaEquipada(unittest.TestCase):
    """Item.xml Enhance.*: bonos de stats mientras el arma está equipada."""

    def test_el_bono_se_aplica_solo_con_el_arma_en_la_mano(self):
        protegido = Arma("Guardian Lance", tipo="Lanza", mt=6, wt=6, hit=100, crit=0, rango=[1], enhance={"def": 5})
        r_con = CalculadoraEngage.simular_combate(_bruto(), _veronica(40, None), LANZA, protegido, Terreno(), Terreno(), 1)
        r_sin = CalculadoraEngage.simular_combate(_bruto(), _veronica(40, None), LANZA, LANZA, Terreno(), Terreno(), 1)
        self.assertEqual(r_sin["atacante"]["daño_por_golpe"] - r_con["atacante"]["daño_por_golpe"], 5)
        self.assertIn("Guardian Lance del defensor (+5 Defensa)", r_con["atacante"]["pasivas_activas"])

    def test_el_catalogo_trae_los_bonos_de_las_armas_de_emblema(self):
        import catalogo_loader as cl
        armas = cl._catalogo["armas"]
        self.assertEqual(armas["IID_カミラ_カミラの艶斧"]["enhance"], {"res": 10})
        self.assertEqual(armas["IID_ロイ_封印の剣"]["enhance"], {"def": 5, "res": 5})
        self.assertEqual(armas["IID_護身の法"]["enhance"], {"def": 5}, "Shielding Art")
        self.assertEqual(armas["IID_力のしずく"].get("enhance"), {}, "los consumibles no son bono de equipo")


class TestPeligroDeLasAmenazas(unittest.TestCase):
    """
    Cada enemigo pesa según su peor combate real contra ESE aliado (no todos igual): no es
    lo mismo que Louis esté al alcance de Lance Fighters que no le hacen nada que de dos
    magos que lo revientan. Y una baja no renta si al turno siguiente muere la unidad.
    """

    def _ficha(self, nombre, es_aliado, arma, x=0, y=0, **stats):
        from catalogo_loader import resolver_unidad_con_catalogo
        return resolver_unidad_con_catalogo({"nombre": nombre, "x": x, "y": y, "es_aliado": es_aliado,
                                             "arma_nombre": arma, "stats": stats}, tablero=None)

    def test_inofensivo_pesa_casi_nada_y_letal_mucho(self):
        import motor_analisis as MA
        tanque = self._ficha("Louis", True, "Iron Lance", hp=40, defensa=30, resistencia=5, velocidad=3)
        flojo = self._ficha("Lance Fighter", False, "Iron Lance", hp=20, fuerza=8, velocidad=5)
        mago = self._ficha("Mago", False, "Elfire", hp=20, magia=30, velocidad=10, destreza=15)
        p_flojo = MA.peligro_de_enemigo(flojo, tanque)
        p_mago = MA.peligro_de_enemigo(mago, tanque)
        self.assertEqual((p_flojo["daño"], p_flojo["peso"]), (0, MA.PESO_AMENAZA_INOFENSIVA))
        self.assertTrue(p_mago["letal"])
        self.assertEqual(p_mago["peso"], MA.PESO_AMENAZA_LETAL)

    def test_letal_entre_varios_aunque_ninguno_mate_solo(self):
        import motor_analisis as MA
        aliado = self._ficha("Etie", True, "Iron Bow", hp=30)
        peligros = {"A": {"daño": 12, "letal": False, "peso": 84}, "B": {"daño": 12, "letal": False, "peso": 84},
                    "C": {"daño": 12, "letal": False, "peso": 84}}
        zonas = {n: {(5, 5)} for n in peligros}
        expo = MA.exposicion_en((5, 5), aliado, zonas, lambda e, a: peligros[e])
        self.assertTrue(expo["letal"], "36 de daño contra 30 HP")
        self.assertEqual(expo["peso"], 3 * 84 + MA.EXTRA_LETAL_COMBINADA)
        # Fuera de la casilla de A no cuenta
        self.assertEqual(MA.exposicion_en((5, 5), aliado, zonas, lambda e, a: peligros[e], excluir={"A"})["daño"], 24)

    def test_en_el_cap8_ninguna_jugada_deja_a_la_unidad_para_morir(self):
        """Mapa real (Cap. 8 inicial, Extremo): las jugadas que se recomiendan no acaban en una
        casilla letal, y los aliados que morirían si se quedan donde están tienen su aviso."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "golden"))
        import escenarios as E
        import cargador_dispos
        from motor_analisis import analizar_situacion_tactica
        mapa, tab = E.escenarios_disponibles()["cap8_inicial"]()
        res = analizar_situacion_tactica(tab, mapa, "seguro", False,
                                         condicion_victoria=cargador_dispos.condicion_victoria("M008"))
        ataques = [r for r in res["resultados"] if r["tipo_analisis"] == "oportunidad_jugador"]
        self.assertFalse([r["aliado"] for r in ataques if r.get("amenaza_letal_destino")])
        avisos = [r for r in res["resultados"] if r["tipo_analisis"] == "peligro_aliado"]
        self.assertTrue(avisos)
        self.assertTrue(all("hasta" in r["veredicto"]["motivos"][0] for r in avisos))

    def test_un_enemigo_congelado_no_tiene_zona_de_movimiento(self):
        """Ice Breath: congelado en la fase de jugador, sigue congelado en la suya."""
        ene = self._ficha("Bandido", False, "Iron Axe")
        base = ene.movimiento_disponible
        ene.congelado = True
        self.assertGreater(base, 0)
        self.assertEqual(ene.movimiento_disponible, 0)


if __name__ == "__main__":
    unittest.main()
