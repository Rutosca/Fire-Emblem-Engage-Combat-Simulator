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

  • Dragon Vein (Camilla, sincronía a vínculo 1): comando que cubre un área con un
    efecto de suelo distinto según el estilo de combate del portador. Los efectos son
    terrenos reales del juego (Terrain.xml), así que sus números se leen del catálogo
    en vez de copiarse aquí. Duran un turno, como el fuego. El área apunta en una de las
    cuatro direcciones y cambia según la vena (geometría verificada por el jugador).

  • Infierno Oscuro (Dark Inferno, Ataque de Emblema de Camilla): daña a los enemigos de
    un área centrada en la unidad y prende fuego en esas casillas. Obliga a usar un hacha.
    [Dragón] amplía el área, [Qi Adept] deja luz curativa en las casillas adyacentes,
    [Místico] +20 % de daño.

  • Cataclysm (Soren, Ataque de Emblema): tres golpes de fuego, trueno y viento al 40 %
    del daño normal. Alcanza al objetivo y a las cuatro casillas en cruz a su alrededor.

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

# ── Terrenos temporales ───────────────────────────────────────────────────
# Cada uno es un terreno de Terrain.xml: sus números (Evasión, Defensa, curación,
# inmunidad a Ruptura) se leen del catálogo compilado por su TID, no se copian aquí.
# `coste_extra` sí va a mano: en el XML el fuego trae MoveCost 2, pero en el juego lo
# que hace es encarecer en 1 el coste de la casilla (verificado con Blazing Lion). La regla
# que cuadra con lo observado: MoveCost > 0 en el XML = +1 a lo que cueste la casilla, y se
# SUMA al terreno de debajo (bosque 2 + agua = 3: con Canter no se entra; Cap. 11). Agua,
# niebla, pilares y enredaderas traen MoveCost 1; miasma, brillo y el hielo, 0.
TERRENOS_TEMPORALES = {
    # tipo:            (TID de Terrain.xml, nombre a mostrar, coste de movimiento extra)
    "fuego":           ("TID_炎上", "Fuego", 1),        # Blazing Lion, Fire/Flame Breath, vena Mística
    "niebla":          ("TID_霧", "Niebla", 1),         # Fog Breath / vena de Corrin: frena +1 (visto en juego)
    "hielo":           (None, "Hielo", 0),              # Ice Breath: marca el área congelada, sin efecto de casilla
    # Venas de Dragón (Camilla)
    "pilares":         ("TID_土柱", "Pilares", 1),      # [Apoyo] pilares de piedra: +Def/Res
    "agua":            ("TID_水溜まり", "Agua", 1),      # [Caballería] agua: -Evasión
    "miasma":          ("TID_瘴気", "Miasma", 0),       # [Encubierto] humo: -Def/-Evasión
    "enredaderas":     ("TID_ツタ", "Enredaderas", 1),  # [Acorazado] inmunidad a Ruptura
    "brillo":          ("TID_アロマ", "Brillo", 0),     # [Volador] cura al empezar la fase encima
    "pista_hielo":     ("TID_氷の床", "Hielo resbaladizo", 0),  # [Qi Adept] suelo helado
}

# ── Áreas ────────────────────────────────────────────────────────────────
# Venas: (avance, lado) respecto del portador, con `avance` hacia la dirección elegida.
# `avance` 0 es la propia casilla del portador, que algunas venas cubren.
_VENA_DELANTE_3X3 = [(a, l) for a in (1, 2, 3) for l in (-1, 0, 1)]
# Flame y Water no apuntan a ningún lado: cubren todo lo que esté a 2 pasos o menos del
# portador, su casilla incluida. Al ser un rombo da igual hacia dónde se lance.
_VENA_ROMBO = [(a, l) for a in range(-2, 3) for l in range(-2, 3) if abs(a) + abs(l) <= 2]
_VENA_ABANICO = [(0, 0), (1, 0), (2, -1), (2, 0), (2, 1), (3, -2), (3, -1), (3, 0), (3, 1), (3, 2)]

AREA_VENA = {
    "pilares":     _VENA_DELANTE_3X3,   # Stone
    "miasma":      _VENA_DELANTE_3X3,   # Smoke
    "enredaderas": _VENA_DELANTE_3X3,   # Vines
    "pista_hielo": [(1, -1), (1, 0), (1, 1)],   # Frost: solo la fila de delante
    "fuego":       _VENA_ROMBO,         # Flame
    "agua":        _VENA_ROMBO,         # Water
    "brillo":      _VENA_ABANICO,       # Succor: se abre hacia delante y cubre al portador
}

# Cataclysm: cruz centrada en el OBJETIVO (no en quien ataca), su casilla incluida.
AREA_CATACLYSM = [(0, 0), (0, -1), (0, 1), (-1, 0), (1, 0)]

# Infierno Oscuro: área fija centrada en la unidad, sin dirección. La casilla de la propia
# unidad no entra. `(dx, dy)` absolutos.
_DI_EXTERIOR = [(-2, -2), (0, -2), (2, -2), (-2, 0), (2, 0), (-2, 2), (0, 2), (2, 2)]
_DI_DIAGONALES = [(-1, -1), (1, -1), (-1, 1), (1, 1)]
_DI_ADYACENTES = [(0, -1), (0, 1), (-1, 0), (1, 0)]

AREA_DARK_INFERNO = {
    "base": _DI_EXTERIOR + _DI_DIAGONALES,
    # "[Dragon] Increases area of effect": entran también las cuatro adyacentes
    "dragon": _DI_EXTERIOR + _DI_DIAGONALES + _DI_ADYACENTES,
}
# "[Qi Adept] Adds Glow to adjacent spaces": las cuatro adyacentes quedan con luz curativa
# (el mismo terreno que la vena Succor: +10 HP a quien empiece su fase encima, un turno).
GLOW_DARK_INFERNO = _DI_ADYACENTES


def estilo_de_combate_de(unidad) -> str:
    """Estilo de combate canónico de la unidad ('volador', 'dragon', 'qi_adept'…)."""
    from motor_calculo import resolver_estilo_combate
    stats = getattr(unidad, "stats", None) or unidad
    crudo = getattr(unidad, "estilo_combate", "") or getattr(stats, "estilo_combate", "")
    return resolver_estilo_combate(crudo)


def rango_de_ataque_area(nombre_ataque: str) -> list:
    """
    Distancias a las que el ataque puede alcanzar a un enemigo. Override y Blazing Lion
    empiezan por el adyacente; Infierno Oscuro cubre un área alrededor de la unidad, así
    que llega hasta las esquinas del 5x5 (distancia 4 en pasos ortogonales).
    """
    if tipo_ataque_area(nombre_ataque) == "dark_inferno":
        distancias = {abs(dx) + abs(dy) for dx, dy in AREA_DARK_INFERNO["dragon"]}
        return sorted(distancias)
    if tipo_ataque_area(nombre_ataque) == "cataclysm":
        # Al objetivo hay que alcanzarlo (3 casillas); el área sale a su alrededor, así
        # que puede pillar a enemigos que estaban fuera de alcance.
        return [1, 2, 3]
    return [1]


def _girar(offsets, direccion):
    """Pasa una lista de (avance, lado) a desplazamientos (dx, dy) en esa dirección."""
    d = direccion
    p = (d[1], d[0])
    return [(d[0] * a + p[0] * l, d[1] * a + p[1] * l) for a, l in offsets]


def casillas_de_vena(vena: str, pos, direccion, mapa) -> list:
    """Casillas que cubre `vena` lanzada desde `pos` hacia `direccion` (vector unitario)."""
    salida = []
    for dx, dy in _girar(AREA_VENA.get(vena) or [], direccion):
        c = (int(pos[0]) + dx, int(pos[1]) + dy)
        if _dentro(mapa, *c) and admite_efecto_de_suelo(_terreno(mapa, *c), vena):
            salida.append(c)
    return salida


def casillas_de_infierno_oscuro(pos, estilo: str, mapa) -> tuple:
    """(casillas en llamas, casillas con luz) de Infierno Oscuro lanzado desde `pos`."""
    clave = "dragon" if estilo == "dragon" else "base"
    fuego, luz = [], []
    for dx, dy in AREA_DARK_INFERNO[clave]:
        c = (int(pos[0]) + dx, int(pos[1]) + dy)
        if _dentro(mapa, *c):
            fuego.append(c)
    if estilo == "qi_adept":
        for dx, dy in GLOW_DARK_INFERNO:
            c = (int(pos[0]) + dx, int(pos[1]) + dy)
            if _dentro(mapa, *c):
                luz.append(c)
    return fuego, luz


# Estilo de combate → vena que crea Dragon Vein. [Dragon] elige cualquiera.
VENAS_DRAGON = {
    "apoyo":      "pilares",
    "caballeria": "agua",
    "encubierto": "miasma",
    "acorazado":  "enredaderas",
    "volador":    "brillo",
    "mistico":    "fuego",
    "qi_adept":   "pista_hielo",
    "dragon":     None,   # elige el jugador
}


def efecto_de_terreno_temporal(tipo: str) -> dict:
    """
    Qué le hace a una casilla el terreno temporal `tipo`, tal como lo define Terrain.xml:
    {"nombre", "avo", "dfn", "curacion_turno", "es_antirruptura", "coste_extra"}.
    Un tipo desconocido, o sin TID (el hielo de Ice Breath), no altera nada.
    """
    tid, nombre, coste_extra = TERRENOS_TEMPORALES.get(tipo, (None, tipo.capitalize(), 0))
    base = {"nombre": nombre, "avo": 0, "dfn": 0, "curacion_turno": 0,
            "es_antirruptura": False, "coste_extra": int(coste_extra),
            # Asimetría del Miasma (-20 al jugador, +20 al enemigo). Se publica para que
            # se vea en la casilla, pero el motor NO la aplica: falta saber en qué unidad
            # está esa cifra (ningún otro terreno usa estos campos).
            "defensa_aliado": 0, "defensa_enemigo": 0}
    if not tid:
        return base
    from catalogo_loader import _catalogo   # diferido: el catálogo se carga al importar
    info = (_catalogo.get("terrenos", {}) or {}).get(tid)
    if not info:
        return base
    base.update(defensa_aliado=int(info.get("defensa_aliado") or 0),
                defensa_enemigo=int(info.get("defensa_enemigo") or 0),
                avo=int(info.get("avoid") or 0),
                dfn=int(info.get("defense") or 0),
                # El Heal negativo del fuego (-10) no es "curación negativa": el daño por
                # fase lo aplica EstadoTablero.quemar_unidades_en_fuego, con sus reglas
                # (nunca mata, los voladores no se queman).
                curacion_turno=max(0, int(info.get("heal_turno") or 0)),
                es_antirruptura=bool(info.get("es_antirruptura")))
    return base

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
    if "dark inferno" in n or "infierno oscuro" in n:
        return "dark_inferno"
    if "cataclysm" in n or "cataclismo" in n:
        return "cataclysm"
    if sabor_aliento(n):
        return "aliento"
    return None


def _dentro(mapa, x: int, y: int) -> bool:
    return 0 <= x < mapa.ancho and 0 <= y < mapa.alto


def _terreno(mapa, x: int, y: int):
    return mapa.grid[x][y] if _dentro(mapa, x, y) else None


def _unidad_en(tablero, x: int, y: int):
    from motor_calculo import casillas_de_unidad   # diferido, como el resto de este módulo
    for f in tablero.fichas.values():
        if f.viva and (x, y) in casillas_de_unidad(f):
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
        "casillas_luz": [...],          # Infierno Oscuro en Qi Adept: luz curativa
      }
    Para un ataque que no es de área devuelve tipo None y valido True (no aplica).
    """
    tipo = tipo_ataque_area(nombre_ataque)
    base = {"tipo": tipo, "valido": True, "motivo": "", "direccion": None,
            "objetivos": [objetivo] if objetivo is not None else [], "pos_final": None, "casillas_fuego": [],
            "sabor": "", "casillas_dano": [], "casillas_niebla": [], "casillas_hielo": [],
            "casillas_luz": []}
    if tipo is None or objetivo is None or mapa is None:
        return base

    pos_atk = (int(pos_atk[0]), int(pos_atk[1]))
    pos_obj = (int(objetivo.x), int(objetivo.y))
    es_aliado_atk_di = bool(getattr(atacante, "es_aliado", True))

    if tipo == "cataclysm":
        dentro = [(pos_obj[0] + dx, pos_obj[1] + dy) for dx, dy in AREA_CATACLYSM]
        dentro = [c for c in dentro if _dentro(mapa, *c)]
        objetivos = [objetivo] + [
            u for c in dentro if c != pos_obj
            for u in [_unidad_en(tablero, *c)]
            if u is not None and u.viva and bool(getattr(u, "es_aliado", False)) != es_aliado_atk_di
        ]
        base.update(objetivos=objetivos, casillas_dano=dentro)
        return base

    if tipo == "dark_inferno":
        # Área fija centrada en la unidad: no hay dirección ni casilla de ataque adyacente.
        estilo = estilo_de_combate_de(atacante)
        fuego, luz = casillas_de_infierno_oscuro(pos_atk, estilo, mapa)
        dentro = set(fuego)
        if pos_obj not in dentro:
            base.update(valido=False, motivo="el objetivo no está en el área de Infierno Oscuro")
            return base
        objetivos = [objetivo] + [
            u for c in sorted(dentro) if c != pos_obj
            for u in [_unidad_en(tablero, *c)]
            if u is not None and u.viva and bool(getattr(u, "es_aliado", False)) != es_aliado_atk_di
        ]
        base.update(objetivos=objetivos, casillas_dano=fuego, casillas_luz=luz,
                    casillas_fuego=[c for c in fuego if es_terreno_llano(_terreno(mapa, *c))])
        return base

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
