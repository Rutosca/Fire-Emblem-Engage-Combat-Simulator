"""
ataques_area.py — Geometría de los Ataques de Emblema que afectan a más de una
casilla:

  • Override / Superación (Sigurd): con una lanza o una espada, ataca al objetivo adyacente y
    ATRAVIESA en línea recta a TODOS los enemigos consecutivos en esa fila o
    columna (verificado con 5 en el juego; no hay tope), acabando en la casilla
    inmediatamente después del último. Un solo golpe a cada uno, Hit 100, sin
    contraataque, con los mismos bonos de posición del atacante para todos (Guía
    Divina de Alear adyacente, Momentum…). Después puede usar Canter como tras un
    ataque normal. La casilla de llegada debe estar libre y ser transitable (sirve una
    casilla de evasión; no un muro, un foso ni un bosque); si no, no puede usarse.

  • Blazing Lion / León ardiente (Roy): con una espada, golpea al objetivo
    adyacente y a los enemigos a su izquierda y derecha (perpendicular a la
    dirección del ataque), y prende fuego a un área de 3x3: esa fila y las dos
    de detrás. El fuego solo prende en terreno llano (caminable, coste 1), dura
    hasta el siguiente turno, hace 10 de daño a quien empiece su fase encima
    (aliado o enemigo, NUNCA a voladores, y nunca mata: deja a 1 HP) y encarece
    el movimiento: entrar en la casilla cuesta 1 punto más (coste +1).

  • Alientos de Tiki (Fusión): el dragón inicia el combate a rango 1 como una espada
    cualquiera, pero el golpe barre un área por delante. El objetivo principal es el
    adyacente (combate normal, con su contraataque); a los demás enemigos del área les
    llega un único golpe. Además cada aliento deja un efecto en el suelo. Geometría
    verificada por el jugador con un boceto; se propaga en las 4 direcciones.

Los cálculos de daño no viven aquí: este módulo solo dice a QUIÉN se golpea,
DÓNDE acaba el atacante y QUÉ casillas arden, se congelan o se llenan de niebla.
Lo usan motor_analisis (para puntuar y describir la jugada) y app.py (para ejecutarla).
"""
from __future__ import annotations

from typing import Optional

FUEGO_DANO_POR_FASE = 10
FUEGO_COSTE_EXTRA = 1
# Niebla (Terrain.xml `TID_霧`): +30 Evasión a quien esté encima, dura un turno.
NIEBLA_AVO = 30

# ── Alientos de Tiki ──────────────────────────────────────────────────────
# Las casillas van como (avance, lado) respecto del portador: `avance` cuenta hacia el
# objetivo (1 = la casilla adyacente que ataca) y `lado` hacia la perpendicular. Así la
# misma tabla vale para las 4 direcciones.
_T = [(1, 0), (2, -1), (2, 0), (2, 1)]                       # la T básica: 1 delante + 3 al fondo
_T_LARGA = _T + [(3, -1), (3, 0), (3, 1)]                    # Flame llega una fila más lejos

ALIENTOS = {
    # sabor: (casillas de daño, efecto de suelo, casillas del efecto)
    "hielo":  (_T,       "hielo",  _T),
    "oscuro": (_T,       None,     []),
    "fuego":  (_T,       "fuego",  [(1, 0)]),
    "llama":  (_T_LARGA, "fuego",  [(1, 0), (2, 0)]),
    "niebla": (_T,       "niebla", _T + [(1, -1), (1, 1), (2, -2), (2, 2)]),
}

# Nombre del arma → sabor. "Fire" va el último: "Flame Breath" no debe caer aquí.
_ALIENTO_POR_NOMBRE = (
    ("ice breath", "hielo"), ("aliento de hielo", "hielo"),
    ("dark breath", "oscuro"), ("aliento oscuro", "oscuro"),
    ("flame breath", "llama"), ("aliento llameante", "llama"), ("aliento de llamas", "llama"),
    ("fog breath", "niebla"), ("aliento de niebla", "niebla"),
    ("fire breath", "fuego"), ("aliento de fuego", "fuego"),
)


def sabor_aliento(nombre_arma: str) -> Optional[str]:
    """'hielo' | 'oscuro' | 'fuego' | 'llama' | 'niebla' según el arma; None si no es un aliento."""
    n = (nombre_arma or "").lower()
    for clave, sabor in _ALIENTO_POR_NOMBRE:
        if clave in n:
            return sabor
    return None


def tipo_ataque_area(nombre_ataque: str) -> Optional[str]:
    """'override' | 'blazing_lion' | 'aliento' | None según el nombre del ataque o arma."""
    n = (nombre_ataque or "").lower()
    if "override" in n or "superaci" in n:
        return "override"
    if "blazing" in n or "león ardiente" in n or "leon ardiente" in n:
        return "blazing_lion"
    if sabor_aliento(n):
        return "aliento"
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


def admite_efecto_de_suelo(terreno, efecto: str) -> bool:
    """
    Si el efecto de un aliento puede quedarse en la casilla. El fuego solo prende en llano
    (igual que el de Blazing Lion, verificado); la niebla y el hielo cubren cualquier
    casilla por la que se pueda pasar o volar, pero no un muro.
    """
    if terreno is None:
        return False
    if efecto == "fuego":
        return es_terreno_llano(terreno)
    return bool(getattr(terreno, "caminable", False) or getattr(terreno, "volable", False))


def es_casilla_llegada_override(terreno, es_volador: bool = False) -> bool:
    """Casilla en la que puede acabar Override: transitable para el atacante y sin
    obstáculo. Verificado en el juego: vale una casilla de evasión (coste 2); no vale
    un muro, un foso ni un bosque."""
    if terreno is None:
        return False
    if not (getattr(terreno, "volable", True) if es_volador else getattr(terreno, "caminable", False)):
        return False
    nombre = str(getattr(terreno, "nombre", "") or "").lower()
    return not any(k in nombre for k in ("muro", "foso", "agua", "pilar", "trono", "puerta", "cofre", "bosque", "forest", "arbol", "árbol"))


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
        "casillas_fuego": [(x, y), ...],  # Blazing Lion / Fire y Flame Breath: casillas que arden
        "sabor": str,                   # alientos: 'hielo' | 'oscuro' | 'fuego' | 'llama' | 'niebla'
        "casillas_dano": [(x, y), ...], # alientos: el área barrida, haya o no enemigo dentro
        "casillas_niebla": [...],       # Fog Breath
        "casillas_hielo": [...],        # Ice Breath
      }
    Para un ataque que no es de área devuelve tipo None y valido True (no aplica).
    """
    tipo = tipo_ataque_area(nombre_ataque)
    base = {"tipo": tipo, "valido": True, "motivo": "", "direccion": None,
            "objetivos": [objetivo] if objetivo is not None else [], "pos_final": None, "casillas_fuego": [],
            "sabor": "", "casillas_dano": [], "casillas_niebla": [], "casillas_hielo": []}
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
        while _dentro(mapa, cx, cy):
            u = _unidad_en(tablero, cx, cy)
            if not es_enemigo(u):
                break
            objetivos.append(u)
            cx, cy = cx + d[0], cy + d[1]
        if not objetivos:
            base.update(valido=False, motivo="no hay enemigo en la casilla objetivo")
            return base
        # Casilla de llegada: la siguiente al último enemigo atravesado.
        lx, ly = objetivos[-1].x + d[0], objetivos[-1].y + d[1]
        t = _terreno(mapa, lx, ly)
        if not es_casilla_llegada_override(t, bool(getattr(atacante, "es_volador", False))):
            base.update(objetivos=objetivos, valido=False, motivo=f"la casilla de llegada ({lx},{ly}) no es transitable")
            return base
        if _unidad_en(tablero, lx, ly) is not None:
            base.update(objetivos=objetivos, valido=False, motivo=f"la casilla de llegada ({lx},{ly}) está ocupada")
            return base
        base.update(objetivos=objetivos, pos_final=(lx, ly))
        return base

    p = (d[1], d[0])  # perpendicular (izquierda/derecha del objetivo)

    if tipo == "aliento":
        sabor = sabor_aliento(nombre_ataque)
        casillas_dano, efecto, casillas_efecto = ALIENTOS[sabor]

        def casilla(off):
            avance, lado = off
            return (pos_atk[0] + d[0] * avance + p[0] * lado,
                    pos_atk[1] + d[1] * avance + p[1] * lado)

        dano = [casilla(o) for o in casillas_dano if _dentro(mapa, *casilla(o))]
        objetivos = [objetivo]
        for c in dano:
            if c == pos_obj:
                continue
            u = _unidad_en(tablero, *c)
            if es_enemigo(u):
                objetivos.append(u)
        suelo = [c for c in (casilla(o) for o in casillas_efecto)
                 if _dentro(mapa, *c) and admite_efecto_de_suelo(_terreno(mapa, *c), efecto)]
        base.update(sabor=sabor, objetivos=objetivos, casillas_dano=dano)
        if efecto == "fuego":
            base["casillas_fuego"] = suelo
        elif efecto == "niebla":
            base["casillas_niebla"] = suelo
        elif efecto == "hielo":
            base["casillas_hielo"] = suelo
        return base

    # blazing_lion
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
