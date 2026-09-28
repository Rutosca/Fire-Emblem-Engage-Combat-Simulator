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


class TestEfectosDeTiming12PorGolpe(unittest.TestCase):
    """Timing 12 que solo se resuelve en el golpe: robo de vida, reducciones y "=" deterministas."""

    MAGA = {"hp": 40, "fuerza": 5, "magia": 22, "destreza": 16, "velocidad": 18, "defensa": 8,
            "resistencia": 18, "suerte": 10, "complexion": 5}

    def _unidad(self, nombre, emblema=None, fusion=False, hp=None, aliado=True, tomo="Elfire"):
        import catalogo_loader as cl
        datos = {"nombre": nombre, "es_aliado": aliado, "nivel": 15, "clase_nombre": "Sage",
                 "stats": dict(self.MAGA), "inventario": [{"nombre": tomo, "equipada": True}], "x": 0, "y": 0}
        if emblema:
            datos.update({"emblema_nombre": emblema, "nivel_vinculo": 10, "en_fusion": fusion})
        if hp is not None:
            datos["hp_actual"] = hp
        return cl.resolver_unidad_con_catalogo(datos, tablero=None)

    def _rival(self):
        import catalogo_loader as cl
        return cl.resolver_unidad_con_catalogo({
            "nombre": "Rival", "es_aliado": False, "nivel": 12, "clase_nombre": "General",
            "stats": {"hp": 60, "fuerza": 18, "magia": 0, "destreza": 12, "velocidad": 5, "defensa": 16,
                      "resistencia": 6, "suerte": 6, "complexion": 10},
            "inventario": [{"nombre": "Steel Lance", "equipada": True}], "x": 1, "y": 0}, tablero=None)

    def _armas(self, u):
        from motor_analisis import _armas_aliado
        return {a.nombre: a for a, _, _ in _armas_aliado(u)}

    def test_flare_roba_la_mitad_del_daño_hecho(self):
        """Renewal (SID_陽光_回復): "min(相手のダメージ, 相手のHP) × 0.5" tras cada golpe con tomo."""
        cel = self._unidad("Celine", "Soren", fusion=True, hp=25)
        rival = self._rival()
        r = CalculadoraEngage.simular_combate(cel.stats, rival.stats, self._armas(cel)["Elfire"], rival.arma,
                                              Terreno(), Terreno(), 2)
        sec = r["resultado"]["secuencia"]
        primero = next(s for s in sec if s["actor"] == "Celine" and s["tipo"] == "ataque")
        drenajes = [-s["daño"] for s in sec if s["tipo"] == "drenaje"]
        self.assertEqual(drenajes[0], primero["daño"] // 2)
        self.assertEqual(r["resultado"]["hp_atacante_final"], 40, "vuelve al máximo sin pasarse")
        self.assertEqual(r["atacante"]["golpes_en_ronda"], 2, "el robo de vida no cuenta como golpe")
        sin = self._unidad("Celine", "Soren", fusion=False, hp=25)
        r2 = CalculadoraEngage.simular_combate(sin.stats, rival.stats, self._armas(sin)["Elfire"], rival.arma,
                                               Terreno(), Terreno(), 2)
        self.assertEqual(r2["resultado"]["hp_atacante_final"], 25, "sin Fusión no hay Flare")

    def test_engage_attack_guard_solo_contra_ataques_de_emblema(self):
        """SID_敵エンゲージ技ダメージ軽減 (Flag bit 7): −20 % solo si le golpea un Ataque de Emblema."""
        guardian = self._unidad("Guardian", "Soren", fusion=True, aliado=False)
        normal = Arma("Silver Axe", tipo="Hacha", mt=15, wt=10, hit=100, rango=[1])
        emblema = Arma("Ataque", tipo="Hacha", mt=15, wt=10, hit=100, rango=[1])
        setattr(emblema, "es_engage_attack", True)
        bruto = Unidad("Bruto", hp=50, hp_max=50, fuerza=35, destreza=30, velocidad=30, defensa=10,
                       resistencia=5, suerte=5, complexion=12)
        r_n = CalculadoraEngage.simular_combate(bruto, guardian.stats, normal, None, Terreno(), Terreno(), 1)
        r_e = CalculadoraEngage.simular_combate(bruto, guardian.stats, emblema, None, Terreno(), Terreno(), 1)
        base_n = CalculadoraEngage._stats_de_golpe(bruto, normal, guardian.stats, None, Terreno())["daño"]
        self.assertEqual(r_n["atacante"]["daño_por_golpe"], base_n, "contra un ataque normal no reduce nada")
        base = CalculadoraEngage._stats_de_golpe(bruto, emblema, guardian.stats, None, Terreno(),
                                                 es_engage_attack=True)["daño"]
        # (la secuencia anota el daño aplicado, topado por el HP que le queda)
        self.assertEqual(r_e["resultado"]["secuencia"][0]["daño"], min(int(base - base * 0.2), 40))
        self.assertEqual(r_e["atacante"]["daño_por_golpe"], int(base - base * 0.2), "el pronóstico ya lo descuenta")

    def test_special_guard_resta_contra_ataques_especiales(self):
        """Special Guard N (overlay DLC de Tiki): −N al daño recibido de un arma de tipo Especial."""
        aliento = Arma("Fire Breath", tipo="Especial", mt=12, wt=0, hit=100, rango=[1, 2, 3], es_magica=True)
        hacha = Arma("Iron Axe", tipo="Hacha", mt=12, wt=0, hit=100, rango=[1])
        wyrm = Unidad("Wyrm", hp=60, hp_max=60, fuerza=25, magia=25, destreza=20, velocidad=5, defensa=10,
                      resistencia=10, suerte=0, complexion=15)

        def recibido(arma, habilidades):
            obj = Unidad("Tiki", hp=40, hp_max=40, fuerza=10, magia=10, destreza=10, velocidad=10, defensa=5,
                         resistencia=5, suerte=5, complexion=5, habilidades=habilidades)
            return CalculadoraEngage.simular_combate(wyrm, obj, arma, None, Terreno(), Terreno(), 1)["resultado"]["secuencia"][0]["daño"]

        self.assertEqual(recibido(aliento, []) - recibido(aliento, ["Special Guard 3"]), 3)
        self.assertEqual(recibido(hacha, []), recibido(hacha, ["Special Guard 3"]))

    def test_mercy_nunca_mata(self):
        """SID_慈悲 ("相手のHP <= 相手のダメージ → 相手のダメージ = max(相手のHP − 1, 0)"): por golpe."""
        hacha = Arma("Silver Axe", tipo="Hacha", mt=15, wt=0, hit=100, rango=[1])
        victima = Unidad("Victima", hp=20, hp_max=20, fuerza=5, destreza=5, velocidad=1, defensa=0,
                         resistencia=0, suerte=0, complexion=5)
        piadoso = Unidad("Piadoso", hp=40, hp_max=40, fuerza=30, destreza=20, velocidad=20, defensa=5,
                         resistencia=5, suerte=5, complexion=10, habilidades=["SID_慈悲"])
        r = CalculadoraEngage.simular_combate(piadoso, victima, hacha, None, Terreno(), Terreno(), 1)
        self.assertEqual(r["resultado"]["hp_defensor_final"], 1)
        self.assertEqual(r["atacante"]["daño_por_golpe"], 19, "el pronóstico ya enseña que no mata")

    def test_triangle_adept_dobla_al_rival_en_desventaja(self):
        """SID_相性激化 (Goldmary, Cap. 7): con desventaja de triángulo, 相手の手番回数 = 2."""
        espada = Arma("Steel Sword", tipo="Espada", mt=8, wt=5, hit=100, rango=[1])
        lanza = Arma("Iron Lance", tipo="Lanza", mt=7, wt=8, hit=100, rango=[1])
        lento = Unidad("Alfred", hp=40, hp_max=40, fuerza=12, destreza=10, velocidad=8, defensa=8,
                       resistencia=3, suerte=5, complexion=8)

        def golpes_alfred(habilidades):
            goldmary = Unidad("Goldmary", hp=60, hp_max=60, fuerza=15, destreza=15, velocidad=10, defensa=8,
                              resistencia=5, suerte=5, complexion=8, habilidades=habilidades)
            return CalculadoraEngage.simular_combate(lento, goldmary, lanza, espada, Terreno(), Terreno(), 1)["atacante"]["golpes_en_ronda"]

        self.assertEqual(golpes_alfred([]), 1, "sin la habilidad Alfred no dobla (Vel 8 vs 10)")
        self.assertEqual(golpes_alfred(["Triangle Adept"]), 2, "con desventaja de Goldmary, dobla Alfred")


class TestAurasSobreRivales(unittest.TestCase):
    """Timing 20 / Target 1: Racket of Solm (Timerra) — Crit −5 a los enemigos a 1-3 casillas."""

    ESPADA = Arma("Killing Edge", tipo="Espada", mt=9, wt=7, hit=100, crit=30, rango=[1])

    def _unidad(self, nombre, x, y, habilidades=()):
        u = Unidad(nombre, hp=60, hp_max=60, fuerza=20, destreza=20, velocidad=15, defensa=10,
                   resistencia=5, suerte=5, complexion=8, habilidades=list(habilidades))
        u.x, u.y = x, y
        return u

    def _crit(self, defensor, aliados_def=None, pos_atk=(0, 0)):
        atacante = self._unidad("Alfred", *pos_atk)
        r = CalculadoraEngage.simular_combate(atacante, defensor, self.ESPADA, None, Terreno(), Terreno(), 1,
                                              pos_atk=pos_atk, pos_def=(defensor.x, defensor.y),
                                              aliados_cercanos_def=aliados_def)
        return r["atacante"]["prob_critico"]

    def test_la_lleva_el_propio_rival(self):
        base = self._crit(self._unidad("Rival", 1, 0))
        self.assertEqual(self._crit(self._unidad("Timerra", 1, 0, ["SID_ソルムの騒音"])), base - 5)

    def test_la_lleva_un_rival_cercano_y_no_uno_lejano(self):
        rival = self._unidad("Rival", 1, 0)
        base = self._crit(rival)
        cerca = self._unidad("Timerra", 3, 0, ["SID_ソルムの騒音"])   # a 3 del atacante
        lejos = self._unidad("Timerra", 6, 0, ["SID_ソルムの騒音"])   # a 6
        self.assertEqual(self._crit(rival, [(cerca, 2)]), base - 5)
        self.assertEqual(self._crit(rival, [(lejos, 5)]), base)


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
