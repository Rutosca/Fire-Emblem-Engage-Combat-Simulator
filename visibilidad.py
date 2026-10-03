"""
Oscuridad (capítulos 6, 13 y 20): qué casillas ve el jugador.

El mapa de Tiled trae una capa "Oscuridad" con las casillas que empiezan a oscuras (en el
Cap. 13, todo el mapa). Sobre ellas, se ve lo que alumbra:
  - cada aliado: un rombo del radio de visión de su clase (Job.xml Base.Sight: 3, Thief 5);
  - cada antorcha del mapa encendida: un rombo del radio de su terreno (Terrain.xml Sight:
    TID_篝火 3; las casas con farol, TID_建物灯, también 3 y no se apagan);
  - la antorcha de mano de un aliado: rombo de 7 (Item.xml Distance) que le sigue y se
    encoge una casilla por turno.

Reglas del juego (verificadas por el jugador):
  - Un aliado no puede entrar en una casilla a oscuras: es un muro que la luz quita.
  - Un enemigo a oscuras no se ve ni se puede atacar; su ficha se queda en su última posición
    conocida (`turno_visto`), porque se mueve sin que se vea.
  - Los enemigos no llevan luz: van a apagar las antorchas del mapa (IA AI_MI_Torch).
"""

from typing import Optional

TID_ANTORCHA = "TID_篝火"          # antorcha del mapa encendida (Sight 3)
TID_ANTORCHA_PERMANENTE = "TID_篝火常"
RADIO_POR_DEFECTO = 3              # si el catálogo no trae el dato


def es_mapa_oscuro(mapa) -> bool:
    return bool(getattr(mapa, "casillas_oscuras", None))


def rombo(cx: int, cy: int, radio: int, ancho: int, alto: int) -> set:
    """Casillas a distancia Manhattan <= radio de (cx, cy), dentro del mapa."""
    if radio < 0:
        return set()
    return {(x, y) for x in range(max(0, cx - radio), min(ancho, cx + radio + 1))
            for y in range(max(0, cy - radio), min(alto, cy + radio + 1))
            if abs(x - cx) + abs(y - cy) <= radio}


def radio_vision(ficha) -> int:
    """Visión de la clase (Job.xml Base.Sight): 3; Thief 5."""
    from catalogo_loader import _catalogo, _buscar_en_catalogo
    info = (_catalogo.get("clases", {}) or {}).get(getattr(ficha, "clase_id", "") or "")
    if not info and getattr(ficha, "clase_nombre", ""):
        _, info = _buscar_en_catalogo("clases", ficha.clase_nombre)
    return int((info or {}).get("vision") or RADIO_POR_DEFECTO)


def radio_de_terreno(tid: str) -> int:
    from catalogo_loader import _catalogo
    return int(((_catalogo.get("terrenos", {}) or {}).get(tid) or {}).get("vision") or RADIO_POR_DEFECTO)


def radio_antorcha_mano(ficha, turno_actual: int) -> int:
    """Radio que alumbra ahora la antorcha de mano de `ficha` (0 si no tiene o se apagó)."""
    luz = getattr(ficha, "luz_antorcha", None) or {}
    if not luz:
        return 0
    return max(0, int(luz.get("radio", 0)) - (int(turno_actual) - int(luz.get("turno", turno_actual))))


def antorchas_del_mapa(tablero) -> list:
    """[(entidad, estado)] de las antorchas de la capa de objetos."""
    mapa = getattr(tablero, "mapa", None)
    if not mapa or not hasattr(mapa, "objetos_mapa"):
        return []
    return [(e, tablero.objetos.get(e.id_entidad, {})) for e in mapa.objetos_mapa()
            if str(e.tipo).lower() == "antorcha"]


def radio_de_antorcha(entidad) -> int:
    """Radio de una antorcha del mapa: el de su propiedad `radio` o el del terreno del juego."""
    props = entidad.propiedades or {}
    if props.get("radio") is not None:
        return int(props["radio"])
    return radio_de_terreno(TID_ANTORCHA_PERMANENTE if props.get("permanente") else TID_ANTORCHA)


def casillas_iluminadas(tablero) -> Optional[set]:
    """
    Casillas que el jugador ve ahora: las que no son oscuras en el mapa y las que alumbran
    aliados, antorchas encendidas y antorchas de mano. None si el mapa no tiene oscuridad
    (se ve todo).
    """
    mapa = getattr(tablero, "mapa", None)
    if not es_mapa_oscuro(mapa):
        return None
    # El análisis lo pide miles de veces por turno: se cachea por lo único que lo cambia
    aliados = tuple(sorted((f.nombre, f.clase_nombre, f.x, f.y, tuple(sorted((f.luz_antorcha or {}).items())))
                           for f in tablero.fichas.values() if f.viva and f.es_aliado))
    antorchas = tuple(sorted((e.id_entidad, bool(est.get("encendida", True))) for e, est in antorchas_del_mapa(tablero)))
    clave = (id(mapa), int(tablero.turno_actual), aliados, antorchas)
    if _CACHE.get("clave") == clave:
        return set(_CACHE["luz"])
    ancho, alto = mapa.ancho, mapa.alto
    luz = set()
    for f in tablero.fichas.values():
        if not f.viva or not f.es_aliado:
            continue
        luz |= rombo(f.x, f.y, radio_vision(f), ancho, alto)
        r_mano = radio_antorcha_mano(f, tablero.turno_actual)
        if r_mano:
            luz |= rombo(f.x, f.y, r_mano, ancho, alto)
    for ent, est in antorchas_del_mapa(tablero):
        if est.get("encendida", True) or (ent.propiedades or {}).get("permanente"):
            r = radio_de_antorcha(ent)
            for (cx, cy) in ent.casillas:
                luz |= rombo(cx, cy, r, ancho, alto)
    claras = {(x, y) for x in range(ancho) for y in range(alto)} - set(mapa.casillas_oscuras)
    _CACHE.clear()
    _CACHE.update(clave=clave, luz=frozenset(claras | luz))
    return claras | luz


_CACHE: dict = {}


def casillas_vetadas(tablero, ficha) -> set:
    """Casillas a oscuras a las que `ficha` no puede entrar (solo aliados; vacío sin
    oscuridad). Se calculan con la luz de antes de moverse, como en el juego."""
    if not getattr(ficha, "es_aliado", False):
        return set()
    luz = casillas_iluminadas(tablero)
    if luz is None:
        return set()
    return set(tablero.mapa.casillas_oscuras) - luz


def marcar_ocultos(tablero, luz=None) -> Optional[set]:
    """
    Marca a cada enemigo como oculto o visible (`oculto`) y apunta el turno en que se le ve
    (`turno_visto`). El tablero lo llama tras todo lo que cambia la luz (mover, registrar,
    antorchas, cambio de fase), así el último turno visto queda guardado antes de perderlo.
    """
    if luz is None:
        luz = casillas_iluminadas(tablero)
    from motor_calculo import casillas_de_unidad
    for f in tablero.fichas.values():
        if f.es_aliado or not f.viva:
            f.oculto = False
            continue
        visible = luz is None or any(c in luz for c in casillas_de_unidad(f))
        f.oculto = not visible
        if visible:
            f.turno_visto = int(tablero.turno_actual)
    return luz


def actualizar_visibilidad(tablero) -> dict:
    """{"oscuro", "iluminadas", "ocultos": {nombre: {turno_visto}}} para la interfaz."""
    luz = marcar_ocultos(tablero)
    ocultos = {f.nombre: {"turno_visto": int(f.turno_visto or 0)}
               for f in tablero.fichas.values() if f.viva and not f.es_aliado and f.oculto}
    return {"oscuro": luz is not None, "iluminadas": sorted(luz) if luz is not None else [], "ocultos": ocultos}
