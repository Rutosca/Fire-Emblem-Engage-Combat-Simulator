"""
Disparadores de pasivas que otorgan estados temporales (buffs "de 1 turno").

El juego modela estos buffs como habilidades-efecto otorgadas por `give_sids`
(p.ej. Self-Improver → SID_力＋２_１ターン, ¡Ponte detrás de mí! → SID_僕が守ります！効果),
cuyos `stat_boosts` ya están en el catálogo. Este módulo se limita a decidir
CUÁNDO se otorgan y HASTA CUÁNDO duran; el consumo lo hace motor_calculo al
sumar los `stat_boosts` de `estados_temporales` antes de simular.

Caducidad (fase, turno) = momento en que el estado deja de existir:
  - "Durante 1 turno" otorgado en fase enemiga N → caduca al entrar en fase
    enemiga N+1 (dura toda la fase de jugador N+1: ¡Ponte detrás de mí!).
  - "Durante ESE turno" otorgado en fase de jugador N → caduca al entrar en la
    fase enemiga N (solo vale si la unidad vuelve a actuar en el mismo turno:
    Self-Improver).
Disparos repetidos refrescan el estado sin acumularse.
"""

import condicion_dsl

SID_GET_BEHIND_ME = "SID_僕が守ります！"
SID_SELF_IMPROVER = "SID_自己研鑽"

# Self-Improver (Alfred): "si espera sin atacar ni usar objetos, +2 Fue durante
# ESE turno". Comprobado en el juego: el bono muere al acabar la fase de jugador
# en la que esperó, así que sin una forma de volver a actuar (Danza de Seadall,
# Danza de la Diosa de Byleth) no tiene efecto. Queda modelado pero apagado
# hasta que existan esas acciones de "refresco" en la herramienta; entonces el
# disparador correcto será la acción explícita "Esperar", no el fin de fase.
SELF_IMPROVER_ACTIVO = False

_ALIAS_TEXTO = {
    SID_GET_BEHIND_ME: ("僕が守ります", "get behind", "al rescate", "ponte detrás", "ponte detras"),
    SID_SELF_IMPROVER: ("自己研鑽", "self-improver", "self improver", "automejora", "superación personal", "superacion personal"),
}


def _tiene_pasiva(ficha, sid: str) -> bool:
    if sid in (getattr(ficha, 'habilidades_sids', None) or []):
        return True
    habs = [str(h).lower() for h in getattr(ficha, 'habilidades', [])]
    return any(alias in h for h in habs for alias in _ALIAS_TEXTO.get(sid, ()))


def _efecto_de(sid_pasiva: str):
    """Devuelve (sid_efecto, nombre, stat_boosts) del primer give_sid de la pasiva, según el catálogo."""
    info = condicion_dsl.HABILIDADES_CATALOGO.get(sid_pasiva) or {}
    for sid_ef in info.get("give_sids", []) or []:
        ef = condicion_dsl.HABILIDADES_CATALOGO.get(sid_ef)
        if ef:
            return sid_ef, info.get("nombre") or sid_pasiva, dict(ef.get("stat_boosts", {}) or {})
    return None


def _otorgar(ficha, sid_pasiva: str, tablero, expira_fase: str, expira_turno: int, origen: str) -> dict:
    efecto = _efecto_de(sid_pasiva)
    if not efecto:
        return None
    sid_ef, nombre, boosts = efecto
    return ficha.otorgar_estado_temporal(sid_ef, nombre, boosts, expira_fase, expira_turno, origen=origen)


# ── Disparadores ─────────────────────────────────────────────────────────────

def al_danar_aliado(tablero, ficha_danada) -> list:
    """
    Evento: un aliado ha perdido HP durante la fase enemiga (≈ "ha sido atacado").
    ¡Ponte detrás de mí!: todo portador vivo a distancia <= 2 del aliado dañado
    gana su efecto (+3 Fuerza) hasta el inicio de la siguiente fase enemiga.
    """
    otorgados = []
    if tablero.fase != "enemigo" or not getattr(ficha_danada, 'es_aliado', False):
        return otorgados
    for f in tablero.fichas.values():
        if not f.viva or not f.es_aliado or f.nombre == ficha_danada.nombre:
            continue
        if abs(f.x - ficha_danada.x) + abs(f.y - ficha_danada.y) > 2:
            continue
        if _tiene_pasiva(f, SID_GET_BEHIND_ME):
            # "Durante 1 turno": vale toda la fase de jugador N+1
            est = _otorgar(f, SID_GET_BEHIND_ME, tablero, "enemigo", tablero.turno_actual + 1,
                           origen=f"{ficha_danada.nombre} atacado")
            if est:
                otorgados.append((f.nombre, est))
    return otorgados


def al_esperar(tablero, ficha) -> list:
    """
    Evento: un aliado espera (termina su acción sin combatir ni usar objetos)
    durante la fase de jugador.
    Self-Improver: el portador gana +2 Fuerza hasta el final de ESA fase de
    jugador; solo aprovechable si vuelve a actuar en el mismo turno.
    Desactivado hasta que existan acciones de refresco (ver SELF_IMPROVER_ACTIVO).
    """
    otorgados = []
    if not SELF_IMPROVER_ACTIVO or tablero.fase != "jugador":
        return otorgados
    if getattr(ficha, 'es_aliado', False) and ficha.viva and not ficha.accion_turno:
        if _tiene_pasiva(ficha, SID_SELF_IMPROVER):
            est = _otorgar(ficha, SID_SELF_IMPROVER, tablero, "enemigo", tablero.turno_actual, origen="esperó")
            if est:
                otorgados.append((ficha.nombre, est))
    return otorgados


def al_terminar_fase_jugador(tablero) -> list:
    """
    Evento: el jugador cierra su fase. Toda unidad sin `accion_turno` ha esperado
    (el juego hace esperar automáticamente a quien no actuó). Hoy no otorga nada
    útil: lo que Self-Improver daría aquí caduca en ese mismo instante.
    """
    otorgados = []
    for f in tablero.fichas.values():
        if f.viva and f.es_aliado and not f.accion_turno:
            otorgados += al_esperar(tablero, f)
    return otorgados
