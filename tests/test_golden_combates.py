"""
Tests de caracterización del motor de combate (golden).

Para cada escenario real (mapa + dispos del datamine + roster, o una partida
guardada) se simulan todos los combates posibles y se comparan, campo a campo,
con tests/golden/combates_<escenario>.json. Cualquier cambio de daño, precisión,
secuencia o pasivas activas hace fallar el test y lista los combates afectados.

Regenerar (solo con cambios intencionados y revisados):
    python tests/golden/generar_golden.py
"""

import os
import sys
import json
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "golden"))

import escenarios as E  # noqa: E402
from generar_golden import ruta_golden  # noqa: E402

MAX_DIFERENCIAS_MOSTRADAS = 25


def _diferencias(esperado: dict, obtenido: dict) -> list:
    """Lista legible de diferencias entre dos golden ({clave: resultado_compacto})."""
    difs = []
    for k in sorted(set(esperado) | set(obtenido)):
        if k not in obtenido:
            difs.append(f"- {k}: combate desaparecido")
            continue
        if k not in esperado:
            difs.append(f"+ {k}: combate nuevo (no está en el golden)")
            continue
        e, o = esperado[k], obtenido[k]
        if e == o:
            continue
        campos = []
        for seccion in sorted(set(e) | set(o)):
            se, so = e.get(seccion), o.get(seccion)
            if isinstance(se, dict) and isinstance(so, dict):
                for campo in sorted(set(se) | set(so)):
                    if se.get(campo) != so.get(campo):
                        campos.append(f"{seccion}.{campo}: {se.get(campo)!r} -> {so.get(campo)!r}")
            elif se != so:
                campos.append(f"{seccion}: {se!r} -> {so!r}")
        difs.append(f"~ {k}\n      " + "\n      ".join(campos))
    return difs


class TestGoldenCombates(unittest.TestCase):

    def _comprobar(self, nombre: str):
        ruta = ruta_golden(nombre)
        if not os.path.exists(ruta):
            self.skipTest(f"No existe {os.path.relpath(ruta)}; genera el golden con tests/golden/generar_golden.py")
        with open(ruta, "r", encoding="utf-8") as f:
            esperado = json.load(f)
        mapa, tablero = E.escenarios_disponibles()[nombre]()
        obtenido = E.enumerar_combates(mapa, tablero)
        difs = _diferencias(esperado, obtenido)
        if difs:
            resumen = "\n".join(difs[:MAX_DIFERENCIAS_MOSTRADAS])
            extra = f"\n... y {len(difs) - MAX_DIFERENCIAS_MOSTRADAS} más" if len(difs) > MAX_DIFERENCIAS_MOSTRADAS else ""
            self.fail(f"{len(difs)} combates de '{nombre}' difieren del golden:\n{resumen}{extra}")


def _crear_tests():
    for nombre in sorted(E.escenarios_disponibles()):
        def _t(self, n=nombre):
            self._comprobar(n)
        _t.__doc__ = f"Golden de combates del escenario {nombre}"
        setattr(TestGoldenCombates, f"test_golden_{nombre}", _t)


_crear_tests()


if __name__ == "__main__":
    unittest.main()
