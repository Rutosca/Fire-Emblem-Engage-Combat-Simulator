"""
ataques_area.py — Geometría de los Ataques de Emblema que afectan a más de una
casilla:

  • Override / Superación (Sigurd): con una lanza, ataca al objetivo adyacente y
    ATRAVIESA en línea recta a los enemigos consecutivos (hasta 3) en esa fila o
    columna, acabando en la casilla inmediatamente después del último.
    Un solo golpe a cada uno, Hit 100, sin contraataque. Después puede usar
    Canter como tras un ataque normal. La casilla de llegada debe ser terreno
    LLANO y estar libre (verificado en el juego); si no, el ataque no puede usarse.

  • Blazing Lion / León ardiente (Roy): con una espada, golpea al objetivo
    adyacente y a los enemigos a su izquierda y derecha (perpendicular a la
    dirección del ataque), y prende fuego a un área de 3x3: esa fila y las dos
    de detrás. El fuego solo prende en terreno llano (caminable, coste 1), dura
    hasta el siguiente turno, hace 10 de daño a quien empiece su fase encima
    (aliado o enemigo, NUNCA a voladores, y nunca mata: deja a 1 HP) y encarece
    el movimiento: entrar en la casilla cuesta 1 punto más (coste +1).

Los cálculos de daño no viven aquí: este módulo solo dice a QUIÉN se golpea,
DÓNDE acaba el atacante y QUÉ casillas arden. Lo usan motor_analisis (para
puntuar y describir la jugada) y app.py (para ejecutarla).
"""
from __future__ import annotations

from typing import Optional

OVERRIDE_MAX_OBJETIVOS = 3
FUEGO_DANO_POR_FASE = 10
FUEGO_COSTE_EXTRA = 1


def tipo_ataque_area(nombre_ataque: str) -> Optional[str]:
    """'override' | 'blazing_lion' | None según el nombre del Ataque de Emblema."""
    n = (nombre_ataque or "").lower()
    if "override" in n or "superaci" in n:
        return "override"
    if "blazing" in n or "león ardiente" in n or "leon ardiente" in n:
        return "blazing_lion"
    return None


def _dentro(mapa, x: int, y: int) -> bool:
    return 0 <= x < mapa.ancho and 0 <= y < mapa.alto


def _terreno(mapa, x: int, y: int):
    return mapa.grid[x][y] if _dentro(mapa, x, y) else None


def _unidad_en(tablero, x: int, y: int):
    for f in tablero.fichas.values():
        if f.viva and (f.x, f.y) == (x, y):
            return f
    return None


def _direccion(pos_atk, pos_obj):
    """Vector unitario ortogonal desde el atacante al objetivo; None si no son adyacentes en cruz."""
    dx, dy = pos_obj[0] - pos_atk[0], pos_obj[1] - pos_atk[1]
    if abs(dx) + abs(dy) != 1:
        return None
    return (dx, dy)


def es_terreno_llano(terreno) -> bool:
    """Casilla en la que puede prender el fuego de Blazing Lion: llano transitable de coste 1."""
    if terreno is None:
        return False
    if not getattr(terreno, "caminable", False):
        return False
    if int(getattr(terreno, "coste_mov", 1) or 1) != 1:
        return False
    nombre = str(getattr(terreno, "nombre", "") or "").lower()
    return not any(k in nombre for k in ("muro", "foso", "agua", "pilar", "trono", "puerta", "cofre"))


def resolver_ataque_area(nombre_ataque: str, pos_atk, objetivo, atacante, tablero, mapa) -> dict:
    """
    Resuelve el área de un Ataque de Emblema desde `pos_atk` contra `objetivo`.

    Devuelve:
      {
        "tipo": "override" | "blazing_lion" | None,
        "valido": bool,                 # False → el ataque no puede ejecutarse desde ahí
        "motivo": str,                  # por qué no es válido
        "direccion": (dx, dy) | None,
        "objetivos": [FichaUnidad, ...],   # el principal primero
        "pos_final": (x, y) | None,     # Override: casilla de llegada del atacante
        "casillas_fuego": [(x, y), ...] # Blazing Lion: casillas que arden
      }
    Para un ataque que no es de área devuelve tipo None y valido True (no aplica).
    """
    tipo = tipo_ataque_area(nombre_ataque)
    base = {"tipo": tipo, "valido": True, "motivo": "", "direccion": None,
            "objetivos": [objetivo] if objetivo is not None else [], "pos_final": None, "casillas_fuego": []}
    if tipo is None or objetivo is None or mapa is None:
        return base

    pos_atk = (int(pos_atk[0]), int(pos_atk[1]))
    pos_obj = (int(objetivo.x), int(objetivo.y))
    d = _direccion(pos_atk, pos_obj)
    if d is None:
        base.update(valido=False, motivo="el objetivo debe estar adyacente en línea recta")
        return base
    base["direccion"] = d
    es_aliado_atk = bool(getattr(atacante, "es_aliado", True))

    def es_enemigo(u) -> bool:
        return u is not None and u.viva and bool(getattr(u, "es_aliado", False)) != es_aliado_atk

    if tipo == "override":
        objetivos = []
        cx, cy = pos_obj
        while len(objetivos) < OVERRIDE_MAX_OBJETIVOS:
            u = _unidad_en(tablero, cx, cy)
            if not es_enemigo(u):
                break
            objetivos.append(u)
            cx, cy = cx + d[0], cy + d[1]
        if not objetivos:
            base.update(valido=False, motivo="no hay enemigo en la casilla objetivo")
            return base
        # Casilla de llegada: la siguiente al último enemigo atravesado. Debe ser
        # terreno llano (verificado en el juego: ni bosque, ni muro, ni foso…).
        lx, ly = objetivos[-1].x + d[0], objetivos[-1].y + d[1]
        t = _terreno(mapa, lx, ly)
        if not es_terreno_llano(t):
            base.update(objetivos=objetivos, valido=False, motivo=f"la casilla de llegada ({lx},{ly}) no es terreno llano")
            return base
        if _unidad_en(tablero, lx, ly) is not None:
            base.update(objetivos=objetivos, valido=False, motivo=f"la casilla de llegada ({lx},{ly}) está ocupada")
            return base
        base.update(objetivos=objetivos, pos_final=(lx, ly))
        return base

    # blazing_lion
    p = (d[1], d[0])  # perpendicular (izquierda/derecha del objetivo)
    frente = [pos_obj, (pos_obj[0] + p[0], pos_obj[1] + p[1]), (pos_obj[0] - p[0], pos_obj[1] - p[1])]
    objetivos = [objetivo]
    for (fx, fy) in frente[1:]:
        u = _unidad_en(tablero, fx, fy)
        if es_enemigo(u):
            objetivos.append(u)
    fuego = []
    for fila in range(3):
        for lado in (-1, 0, 1):
            fx = pos_obj[0] + d[0] * fila + p[0] * lado
            fy = pos_obj[1] + d[1] * fila + p[1] * lado
            if _dentro(mapa, fx, fy) and es_terreno_llano(_terreno(mapa, fx, fy)):
                fuego.append((fx, fy))
    base.update(objetivos=objetivos, casillas_fuego=fuego)
    return base
