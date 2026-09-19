"""
Regenera los ficheros golden de combates (tests/golden/combates_<escenario>.json).

Uso:
    python tests/golden/generar_golden.py            # todos los escenarios
    python tests/golden/generar_golden.py cap7_inicial

Los golden fijan el COMPORTAMIENTO ACTUAL del motor, no la verdad del juego
(esa está en tests/test_ground_truth_cap7.py y en las observaciones anotadas
en notas/). Regenerar solo cuando un cambio de números sea intencionado y esté
revisado; el diff del JSON es la lista exacta de combates que cambian.
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import escenarios as E  # noqa: E402

DIR_GOLDEN = os.path.dirname(os.path.abspath(__file__))


def ruta_golden(nombre: str) -> str:
    return os.path.join(DIR_GOLDEN, f"combates_{nombre}.json")


def escribir_golden(nombre: str, datos: dict) -> str:
    """Una entrada por línea (claves ordenadas) para que `git diff` sea legible."""
    ruta = ruta_golden(nombre)
    with open(ruta, "w", encoding="utf-8", newline="\n") as f:
        f.write("{\n")
        claves = sorted(datos)
        for i, k in enumerate(claves):
            coma = "," if i < len(claves) - 1 else ""
            f.write(f"  {json.dumps(k, ensure_ascii=False)}: {json.dumps(datos[k], ensure_ascii=False, sort_keys=True)}{coma}\n")
        f.write("}\n")
    return ruta


def generar(nombre: str) -> dict:
    mapa, tablero = E.escenarios_disponibles()[nombre]()
    return E.enumerar_combates(mapa, tablero)


if __name__ == "__main__":
    disponibles = E.escenarios_disponibles()
    pedidos = sys.argv[1:] or sorted(disponibles)
    for nom in pedidos:
        if nom not in disponibles:
            print(f"[golden] escenario desconocido: {nom} (disponibles: {', '.join(sorted(disponibles))})")
            continue
        datos = generar(nom)
        ruta = escribir_golden(nom, datos)
        print(f"[golden] {nom}: {len(datos)} combates -> {os.path.relpath(ruta)}")
