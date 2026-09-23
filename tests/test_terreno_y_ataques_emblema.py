# -*- coding: utf-8 -*-
"""
Dos regresiones vistas jugando el Cap. 10:

1. El bono de Evasión del terreno tiene que aplicarse al DEFENSOR sea aliado o enemigo,
   en las tres vías (motor, recomendaciones y ejecución del combate). Solo los voladores
   lo ignoran.
2. "Ragnarok" a secas es el nombre del TOMO de Celica (IID_セリカ_ライナロック), un arma de
   Emblema que se usa en ataques normales. No debe activar nada del Ataque de Emblema
   Warp Ragnarök (el ×1.2 de estilo Místico, atacar a RES, anular el contraataque).
"""
import unittest

import catalogo_loader as cl
from app import app, tablero, _mapa
from motor_calculo import CalculadoraEngage, Terreno
from motor_analisis import _armas_aliado


def _lanza(nombre="Steel Lance"):
    return {"nombre": nombre, "equipada": True}


class TestEvasionDelTerreno(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()

    def setUp(self):
        self.client.post("/api/mapa/seleccionar", json={"capitulo": 10})
        for n in list(tablero.fichas):
            tablero.fichas.pop(n)
        tablero.fase = "jugador"
        # Una casilla de evasión con sitio libre justo debajo para plantar al atacante
        self.evasion = next(
            (x, y) for x in range(_mapa.ancho) for y in range(_mapa.alto - 2)
            if _mapa.grid[x][y].avo
            and _mapa.grid[x][y + 1].caminable and _mapa.grid[x][y + 2].caminable)

    @classmethod
    def tearDownClass(cls):
        cls.client.post("/api/mapa/seleccionar", json={"capitulo": 7})

    def _colocar(self, clase_enemigo="Lance Cavalier", volador=False):
        ex, ey = self.evasion
        enemigo = cl.resolver_unidad_con_catalogo({
            "nombre": "Rival", "es_aliado": False, "nivel": 12, "clase_nombre": clase_enemigo,
            "dificultad": "Extremo", "inventario": [_lanza()], "x": ex, "y": ey}, tablero=tablero)
        tablero.registrar_unidad(enemigo, resolver_colision=False)
        louis = cl.resolver_unidad_con_catalogo({
            "nombre": "Louis", "es_aliado": True, "nivel": 12, "clase_nombre": "General",
            "inventario": [_lanza()], "x": ex, "y": ey + 2}, tablero=tablero)
        tablero.registrar_unidad(louis, resolver_colision=False)
        return louis, enemigo

    def test_la_casilla_del_mapa_declara_evasion(self):
        ex, ey = self.evasion
        t = self.client.get(f"/api/terreno/{ex}/{ey}").get_json()
        self.assertEqual((t["nombre"], t["avo"]), ("evasion", 30))

    def test_el_motor_resta_la_evasion_del_enemigo_defensor(self):
        louis, enemigo = self._colocar()
        t_ev = _mapa.grid[self.evasion[0]][self.evasion[1]]
        llano = CalculadoraEngage.simular_combate(
            louis.stats, enemigo.stats, louis.arma, enemigo.arma, Terreno(), Terreno(), 1)
        sobre_ev = CalculadoraEngage.simular_combate(
            louis.stats, enemigo.stats, louis.arma, enemigo.arma, Terreno(),
            Terreno(avo=t_ev.avo, dfn=t_ev.dfn, nombre="evasion"), 1)
        self.assertEqual(llano["atacante"]["precision"] - sobre_ev["atacante"]["precision"], t_ev.avo)

    def test_la_recomendacion_ya_lleva_la_evasion_descontada(self):
        louis, enemigo = self._colocar()
        res = self.client.post("/api/analizar", json={}).get_json()["resultados"]
        fila = next(r for r in res if r.get("aliado") == "Louis" and r.get("enemigo") == "Rival"
                    and r.get("tipo_analisis") != "zona_segura")
        t_ev = _mapa.grid[self.evasion[0]][self.evasion[1]]
        sin_terreno = CalculadoraEngage.simular_combate(
            louis.stats, enemigo.stats, louis.arma, enemigo.arma, Terreno(), Terreno(), 1)
        esperado = sin_terreno["atacante"]["precision"] - t_ev.avo
        self.assertIn(f"Hit {esperado}%", fila["recomendacion"])

    def test_un_enemigo_volador_sí_la_ignora(self):
        louis, enemigo = self._colocar(clase_enemigo="Lance Flier")
        self.assertTrue(enemigo.es_volador)
        t_ev = _mapa.grid[self.evasion[0]][self.evasion[1]]
        sobre_ev = CalculadoraEngage.simular_combate(
            louis.stats, enemigo.stats, louis.arma, enemigo.arma, Terreno(),
            Terreno(avo=t_ev.avo, dfn=t_ev.dfn, nombre="evasion"), 1)
        llano = CalculadoraEngage.simular_combate(
            louis.stats, enemigo.stats, louis.arma, enemigo.arma, Terreno(), Terreno(), 1)
        self.assertEqual(sobre_ev["atacante"]["precision"], llano["atacante"]["precision"])


class TestTomoRagnarokNoEsWarpRagnarok(unittest.TestCase):

    def _celine_mistica(self):
        return cl.resolver_unidad_con_catalogo({
            "nombre": "Céline", "es_aliado": True, "nivel": 15, "clase_nombre": "Sage",
            "emblema_nombre": "Celica", "en_fusion": True, "nivel_vinculo": 20,
            "inventario": [{"nombre": "Elfire", "equipada": True}], "x": 0, "y": 0}, tablero=None)

    def _rival(self):
        return cl.resolver_unidad_con_catalogo({
            "nombre": "Bruto", "es_aliado": False, "nivel": 10, "clase_nombre": "Axe Fighter",
            "stats": {"hp": 80, "fuerza": 12, "magia": 0, "destreza": 10, "velocidad": 10,
                      "defensa": 10, "resistencia": 10, "suerte": 5, "complexion": 7},
            "inventario": [{"nombre": "Iron Axe", "equipada": True}], "x": 3, "y": 0}, tablero=None)

    def _combate(self, arma, celine, rival):
        return CalculadoraEngage.simular_combate(
            celine.stats, rival.stats, arma, rival.arma, Terreno(), Terreno(),
            distancia=arma.rango[0],
            es_engage_attack=getattr(arma, "es_engage_attack", False),
            engage_attack_nombre=getattr(arma, "engage_attack_nombre", ""))

    def test_el_tomo_de_emblema_no_recibe_el_x12_mistico(self):
        celine, rival = self._celine_mistica(), self._rival()
        armas = {a.nombre: a for a, _, _ in _armas_aliado(celine)}
        tomo = next(a for n, a in armas.items() if n.lower().startswith("ragnarok"))
        self.assertFalse(getattr(tomo, "es_engage_attack", False), "es un arma, no el Ataque de Emblema")
        pasivas_tomo = self._combate(tomo, celine, rival)["atacante"]["pasivas_activas"]
        self.assertFalse([p for p in pasivas_tomo if "Warp Ragnar" in p or "Ragnarök Fusión" in p], pasivas_tomo)
        # Y el rival sí responde, porque es un ataque normal
        secuencia = self._combate(tomo, celine, rival)["resultado"]["secuencia"]
        self.assertTrue(any("contraataque" in s["tipo"] for s in secuencia), secuencia)

    def test_el_ataque_de_emblema_si_lo_recibe(self):
        celine, rival = self._celine_mistica(), self._rival()
        ataque = next(a for a, _, _ in _armas_aliado(celine) if getattr(a, "es_engage_attack", False))
        pasivas_atk = self._combate(ataque, celine, rival)["atacante"]["pasivas_activas"]
        self.assertTrue([p for p in pasivas_atk if "×1.2" in p], pasivas_atk)

    def test_el_analisis_dice_si_la_jugada_es_ataque_de_emblema(self):
        """La UI no debe deducirlo del nombre del arma: el análisis lo publica."""
        from motor_analisis import analizar_situacion_tactica  # noqa: F401  (import comprobado)
        celine = self._celine_mistica()
        for a, _, _ in _armas_aliado(celine):
            es_atk = getattr(a, "es_engage_attack", False)
            if "ragnarok" in a.nombre.lower():
                # el tomo no lo es; el Ataque de Emblema (Warp Ragnarök) sí
                self.assertEqual(es_atk, a.nombre.lower().startswith("warp"), a.nombre)


class TestMomentumSoloEnElPrimerGolpe(unittest.TestCase):
    """Verdad de juego (vídeo, 2026-09-23): una unidad con Sigurd que dobla aplica Momentum
    solo al PRIMER ataque — 16 y 10 de daño, +6 del primero. El datamine lo dice en la
    Condition de SID_助走: "移動距離 > 0 && 総行動回数 == 0"."""

    def _jinete(self, movidas):
        u = cl.resolver_unidad_con_catalogo({
            "nombre": "Jinete", "es_aliado": True, "nivel": 15, "clase_nombre": "Paladin",
            "emblema_nombre": "Sigurd", "en_fusion": True, "nivel_vinculo": 5,
            "stats": {"hp": 40, "fuerza": 20, "magia": 0, "destreza": 18, "velocidad": 24,
                      "defensa": 14, "resistencia": 8, "suerte": 10, "complexion": 8},
            "inventario": [_lanza()], "x": 0, "y": 0}, tablero=None)
        setattr(u.stats, "distancia_movida", movidas)
        return u

    def _lento(self):
        return cl.resolver_unidad_con_catalogo({
            "nombre": "Bruto", "es_aliado": False, "nivel": 8, "clase_nombre": "Axe Fighter",
            "stats": {"hp": 60, "fuerza": 12, "magia": 0, "destreza": 8, "velocidad": 6,
                      "defensa": 10, "resistencia": 4, "suerte": 3, "complexion": 7},
            "inventario": [{"nombre": "Iron Axe", "equipada": True}], "x": 2, "y": 0}, tablero=None)

    def _golpes(self, movidas):
        atk, rival = self._jinete(movidas), self._lento()
        c = CalculadoraEngage.simular_combate(atk.stats, rival.stats, atk.arma, rival.arma,
                                              Terreno(), Terreno(), distancia=1)
        return [(s["tipo"], s["daño"]) for s in c["resultado"]["secuencia"] if s["actor"] == "Jinete"]

    def test_el_follow_up_no_lleva_el_bono(self):
        quieto = self._golpes(0)
        movido = self._golpes(6)
        self.assertEqual(len(quieto), 2, quieto)   # ataque + follow-up
        self.assertEqual(quieto[0][1], quieto[1][1], "sin moverse los dos golpes son iguales")
        self.assertEqual(movido[0][1] - quieto[0][1], 6, "Momentum suma las casillas recorridas")
        self.assertEqual(movido[1][1], quieto[1][1], "el follow-up NO lleva Momentum")

    def test_el_motor_marca_la_condicion_de_primera_ronda(self):
        import pasivas
        self.assertTrue(pasivas._mira_la_primera_ronda(pasivas.HABILIDADES["SID_助走"]["condition"]))
        self.assertTrue(pasivas._mira_la_primera_ronda(pasivas.HABILIDADES["SID_助走＋"]["condition"]))
        self.assertFalse(pasivas._mira_la_primera_ronda(pasivas.HABILIDADES["SID_狙撃"]["condition"]))



if __name__ == "__main__":
    unittest.main()
