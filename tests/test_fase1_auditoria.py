# -*- coding: utf-8 -*-
"""
Pruebas unitarias para las correcciones de la Fase 1 de la auditoría:
- Grabados de emblema dinámicos desde God.xml / catalogo_engage.json
- Género dinámico desde Person.xml (Gender: 1=M, 2=F)
- InternalLevel de clases desde Job.xml
- Detección canónica de jefes sin strings de nombres hardcodeados
- Dimensiones de mapa dinámicas en cargador_dispos
- Activación de pasivas personales por SID canónico
"""
import unittest
from catalogo_loader import GRABADOS_EMBLEMA, cargar_catalogo
from motor_calculo import (
    obtener_genero_unidad,
    CalculadoraEngage,
    Unidad,
    Arma,
    Terreno,
)
from estado_tablero import FichaUnidad
from motor_analisis import _es_jefe
from cargador_dispos import CargadorDisposEngage


class TestFase1Auditoria(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogo = cargar_catalogo()

    def test_grabados_emblema_cargados_desde_catalogo(self):
        """Verifica que los grabados base de Emblemas provengan del catálogo y tengan stats exactos."""
        self.assertGreaterEqual(len(GRABADOS_EMBLEMA), 12)
        self.assertIn("marth", GRABADOS_EMBLEMA)
        self.assertIn("sigurd", GRABADOS_EMBLEMA)
        self.assertIn("micaiah", GRABADOS_EMBLEMA)

        # Datamine God.xml Marth: EngravePower=1, EngraveWeight=0, EngraveHit=10, EngraveCritical=5, EngraveAvoid=5, EngraveSecure=0
        marth = GRABADOS_EMBLEMA["marth"]
        self.assertEqual(marth["mt"], 1)
        self.assertEqual(marth["hit"], 10)
        self.assertEqual(marth["crit"], 10)
        self.assertEqual(marth["avo"], 5)

        # Datamine God.xml Sigurd: EngravePower=1, EngraveWeight=1, EngraveHit=0, EngraveCritical=0, EngraveAvoid=0, EngraveSecure=0
        sigurd = GRABADOS_EMBLEMA["sigurd"]
        self.assertEqual(sigurd["mt"], 1)
        self.assertEqual(sigurd["wt"], -1)

    def test_genero_unidad_desde_datamine(self):
        """Verifica que el género se obtenga de Person.xml (1=Hombre, 2=Mujer) y se propague."""
        personajes = self.catalogo.get("personajes", {})
        p_alear_f = personajes.get("PID_リュール_女")
        if p_alear_f:
            self.assertEqual(p_alear_f.get("genero"), 2)

        unidad_m = Unidad(
            nombre="Caballero Desconocido",
            hp=30, fuerza=10, magia=0, destreza=10, velocidad=10, defensa=5, resistencia=5, suerte=5,
            genero=1
        )
        self.assertEqual(obtener_genero_unidad(unidad_m), 1)

        unidad_f = Unidad(
            nombre="Guerrera Desconocida",
            hp=30, fuerza=10, magia=0, destreza=10, velocidad=10, defensa=5, resistencia=5, suerte=5,
            genero=2
        )
        self.assertEqual(obtener_genero_unidad(unidad_f), 2)

    def test_internal_level_clases_desde_job_xml(self):
        """Verifica que las clases avanzadas tengan internal_level=20 y básicas 0."""
        clases = self.catalogo.get("clases", {})
        paladin = clases.get("JID_パラディン", {})
        self.assertEqual(paladin.get("internal_level"), 20)

        sword_fighter = clases.get("JID_ソードファイター", {})
        self.assertEqual(sword_fighter.get("internal_level"), 0)

    def test_es_jefe_canonico(self):
        """Verifica que Hortensia jugable no sea considerada jefe y los jefes legítimos sí."""
        hortensia_aliada = FichaUnidad(
            nombre="Hortensia",
            es_aliado=True,
            x=5, y=5,
            hp_stock=0,
            es_jefe=False
        )
        self.assertFalse(_es_jefe(hortensia_aliada))

        hortensia_boss = FichaUnidad(
            nombre="Hortensia (Boss)",
            es_aliado=False,
            x=10, y=10,
            hp_stock=1,
            es_jefe=True
        )
        self.assertTrue(_es_jefe(hortensia_boss))

    def test_dimensiones_mapa_dinamicas(self):
        """Verifica que el cargador de dispos acepte límites de mapa variables."""
        cargador = CargadorDisposEngage()
        unidades = cargador.cargar_capitulo("M007", "Extremo", mapa_ancho=24, mapa_alto=17)
        self.assertGreater(len(unidades), 0)
        for u in unidades:
            self.assertGreaterEqual(u["x"], 0)
            self.assertLess(u["x"], 24)
            self.assertGreaterEqual(u["y"], 0)
            self.assertLess(u["y"], 17)

    def test_activacion_pasivas_por_sid(self):
        """Verifica que una unidad active su habilidad personal mediante su SID canónico."""
        # Unidad adyacente otorgando Guía Divina por SID_神竜の結束
        alear = Unidad(
            nombre="Heroe Desconocido",
            hp=30, fuerza=15, magia=5, destreza=15, velocidad=15, defensa=10, resistencia=8, suerte=10,
            habilidades=["SID_神竜の結束"]
        )
        atacante = Unidad(
            nombre="Soldado Aliado",
            hp=30, fuerza=10, magia=0, destreza=10, velocidad=10, defensa=10, resistencia=5, suerte=5,
        )
        defensor = Unidad(
            nombre="Enemigo",
            hp=30, fuerza=10, magia=0, destreza=10, velocidad=10, defensa=5, resistencia=5, suerte=5,
        )
        arma_atk = Arma("Espada de Hierro", mt=5, wt=5, hit=90, crit=0, tipo="Espada", rango=[1])
        arma_def = Arma("Espada de Hierro", mt=5, wt=5, hit=90, crit=0, tipo="Espada", rango=[1])
        terreno = Terreno(nombre="Llano", avo=0, dfn=0)

        resultado = CalculadoraEngage.simular_combate(
            atacante=atacante,
            defensor=defensor,
            arma_atk=arma_atk,
            arma_def=arma_def,
            terreno_atk=terreno,
            terreno_def=terreno,
            aliados_cercanos_atk=[(alear, 1)],
            aliados_cercanos_def=[]
        )
        # ATK base: 10 STR + 5 Mt + 3 (Guía Divina) = 18 ATK. Daño = 18 - 5 DEF = 13.
        self.assertEqual(resultado["atacante"]["daño_por_golpe"], 13)
        self.assertTrue(any("Divinely Inspiring" in p for p in resultado["atacante"]["pasivas_activas"]))


if __name__ == "__main__":
    unittest.main()
