"""Exporta una instantánea auditable de las estadísticas de los despliegues.

No contiene estadísticas escritas a mano: lee cada dispos/*.xml, aplica la
dificultad y pasa cada unidad por el mismo resolver que usa la aplicación.
Sirve para comparar una partida real con el tracker y detectar diferencias de
HP, nivel interno, clase, armas o habilidades.

Uso:
    python scratch/extract_unit_stats.py --chapter M007 --difficulty Extremo
    python scratch/extract_unit_stats.py --all --output scratch/stats_snapshot.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Cuando se ejecuta como ``python scratch/...`` Python toma ``scratch`` como
# primer directorio de importación; añadir la raíz permite reutilizar los
# módulos de la aplicación sin instalar el proyecto como paquete.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from cargador_dispos import CargadorDisposEngage, DISPOS_DIR
from catalogo_loader import resolver_unidad_con_catalogo


STAT_KEYS = (
    "hp", "fuerza", "magia", "destreza", "velocidad", "defensa",
    "resistencia", "suerte", "complexion",
)


def snapshot_unit(raw: dict, ficha) -> dict:
    stats = ficha.stats
    return {
        "nombre": ficha.nombre,
        "pid": raw.get("pid", ""),
        "clase_id": ficha.clase_id,
        "clase": ficha.clase_nombre,
        "nivel_interno_clase": int(getattr(getattr(ficha, "stats", None), "nivel_interno_clase", 0)),
        "nivel": ficha.nivel,
        "aliado": ficha.es_aliado,
        "jefe": bool(getattr(stats, "es_jefe", False)),
        "emblema": ficha.emblema_nombre,
        "arma": getattr(ficha.arma, "nombre", "") if ficha.arma else "",
        "habilidades": list(ficha.habilidades),
        "stats": {key: int(getattr(stats, key)) for key in STAT_KEYS},
    }


def extract(chapter: str, difficulty: str, loader: CargadorDisposEngage) -> dict:
    rows = []
    for raw in loader.cargar_capitulo(chapter, difficulty):
        ficha = resolver_unidad_con_catalogo(raw)
        rows.append(snapshot_unit(raw, ficha))
    return {"chapter": chapter, "difficulty": difficulty, "units": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--chapter", help="Identificador, por ejemplo M007")
    group.add_argument("--all", action="store_true", help="Extrae todos los capítulos disponibles")
    parser.add_argument("--difficulty", default="Extremo", choices=("Normal", "Dificil", "Difícil", "Extremo"))
    parser.add_argument("--output", type=Path, help="Ruta JSON de salida; por defecto imprime en stdout")
    args = parser.parse_args()

    loader = CargadorDisposEngage()
    if args.all:
        chapters = sorted(Path(DISPOS_DIR).glob("M*.xml"))
        result = [extract(path.stem, args.difficulty, loader) for path in chapters]
    else:
        result = extract(args.chapter.upper(), args.difficulty, loader)

    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
        print(f"[OK] Estadísticas exportadas a {args.output}")
    else:
        print(payload)


if __name__ == "__main__":
    main()
