"""
Disparadores de pasivas que otorgan estados temporales (buffs "de 1 turno").

El juego modela estos buffs como habilidades-efecto otorgadas por `give_sids`
(p.ej. Self-Improver → SID_力＋２_１ターン, Meditation → SID_瞑想効果,
¡Ponte detrás de mí! → SID_僕が守ります！効果), cuyos `stat_boosts` ya están en el
catálogo. Este módulo se limita a decidir CUÁNDO se otorgan y HASTA CUÁNDO duran;
el consumo lo hace motor_calculo al sumar los `stat_boosts` de
`estados_temporales` antes de simular.

Caducidad (fase, turno) = momento en que el estado deja de existir:
  - "Durante 1 turno" otorgado en fase enemiga N → caduca al entrar en fase
    enemiga N+1 (dura toda la fase de jugador N+1: ¡Ponte detrás de mí!).
  - "Al esperar" (Skill.xml Timing 25: Self-Improver, Meditation) otorgado en la
    fase de jugador N → caduca al entrar en la fase de jugador N+1: cubre la fase
    enemiga N (Res+2 de Meditación contra los ataques enemigos, Fue+2 de
    Self-Improver en los contraataques de Alfred) y, si la unidad vuelve a actuar
    en el mismo turno (Danza de Seadall, Danza de la Diosa de Byleth), también esa
    acción. Ambas comparten Life/Cycle en el datamine (1/2), así que se tratan igual.
Disparos repetidos refrescan el estado sin acumularse.
"""

import condicion_dsl
import pasivas

SID_GET_BEHIND_ME = "SID_僕が守ります！"
SID_SELF_IMPROVER = "SID_自己研鑽"
SID_MEDITATION = "SID_瞑想"

# Timing de Skill.xml "al esperar" (la unidad termina su acción sin atacar ni usar objetos)
TIMING_AL_ESPERAR = 25


def _tiene_pasiva(ficha, sid: str) -> bool:
    return sid in pasivas.sids_activos(ficha)


def _efectos_de(sid_pasiva: str):
    """[(sid_efecto, nombre, stat_boosts)] de los give_sids con boosts de la pasiva, según el catálogo."""
    info = condicion_dsl.HABILIDADES_CATALOGO.get(sid_pasiva) or {}
    salida = []
    for sid_ef in info.get("give_sids", []) or []:
        ef = condicion_dsl.HABILIDADES_CATALOGO.get(sid_ef)
        if ef and any(ef.get("stat_boosts", {}).values()):
            salida.append((sid_ef, info.get("nombre") or sid_pasiva, dict(ef.get("stat_boosts", {}) or {})))
    return salida


def _otorgar(ficha, sid_pasiva: str, tablero, expira_fase: str, expira_turno: int, origen: str) -> list:
    otorgados = []
    for sid_ef, nombre, boosts in _efectos_de(sid_pasiva):
        est = ficha.otorgar_estado_temporal(sid_ef, nombre, boosts, expira_fase, expira_turno, origen=origen)
        if est:
            otorgados.append(est)
    return otorgados


def _pasivas_al_esperar(ficha) -> list:
    """SIDs activos de la unidad con Timing 25 (al esperar) que otorgan boosts."""
    salida = []
    for sid in pasivas.sids_activos(ficha):
        info = condicion_dsl.HABILIDADES_CATALOGO.get(sid) or {}
        if int(info.get("timing") or 0) == TIMING_AL_ESPERAR and _efectos_de(sid):
            salida.append(sid)
    return salida


def _curaciones_al_esperar(ficha) -> list:
    """
    [(sid, nombre, HP)] de las pasivas de Timing 25 que curan en vez de dar stats
    (Lifesphere de Tiki: 回復 +20 / +30 / +40 y quita los estados alterados).
    Si hay varias del mismo tipo (Lifesphere y Lifesphere+ a la vez) vale la mayor.
    """
    salida = []
    for sid in pasivas.sids_activos(ficha):
        info = condicion_dsl.HABILIDADES_CATALOGO.get(sid) or {}
        if int(info.get("timing") or 0) != TIMING_AL_ESPERAR:
            continue
        for nombre_act, op, valor in zip(info.get("act_names") or [],
                                         info.get("act_operations") or [],
                                         info.get("act_values") or []):
            if nombre_act != "回復" or op != "+":
                continue
            try:
                salida.append((sid, info.get("nombre") or sid, int(float(valor))))
            except (TypeError, ValueError):
                pass
    return salida


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
            for est in _otorgar(f, SID_GET_BEHIND_ME, tablero, "enemigo", tablero.turno_actual + 1,
                                origen=f"{ficha_danada.nombre} atacado"):
                otorgados.append((f.nombre, est))
    return otorgados


def al_esperar(tablero, ficha) -> list:
    """
    Evento: un aliado espera (termina su acción sin combatir ni usar objetos)
    durante la fase de jugador. Pasivas de Timing 25 (Self-Improver +2 Fue,
    Meditation +2 Res): el efecto dura hasta el inicio de la siguiente fase de
    jugador, es decir, toda la fase enemiga de este turno.
    """
    otorgados = []
    if tablero.fase != "jugador":
        return otorgados
    if not (getattr(ficha, 'es_aliado', False) and ficha.viva and not ficha.accion_turno):
        return otorgados
    for sid in _pasivas_al_esperar(ficha):
        for est in _otorgar(ficha, sid, tablero, "jugador", tablero.turno_actual + 1, origen="esperó"):
            otorgados.append((ficha.nombre, est))
    # Curación al esperar (Lifesphere): cura HP y limpia los estados alterados
    curaciones = _curaciones_al_esperar(ficha)
    if curaciones:
        sid, nombre, hp = max(curaciones, key=lambda c: c[2])
        antes = ficha.hp_actual
        ficha.sincronizar_hp(min(ficha.hp_max, ficha.hp_actual + hp))
        ficha.nivel_veneno = 0
        if ficha.stats:
            setattr(ficha.stats, "nivel_veneno", 0)
        otorgados.append((ficha.nombre, {
            "sid": sid, "nombre": nombre, "curacion": ficha.hp_actual - antes,
            "stat_boosts": {}, "origen": "esperó",
        }))
    return otorgados


def al_terminar_fase_jugador(tablero) -> list:
    """
    Evento: el jugador cierra su fase. Toda unidad sin `accion_turno` ha esperado
    (el juego hace esperar automáticamente a quien no actuó).
    """
    otorgados = []
    for f in tablero.fichas.values():
        if f.viva and f.es_aliado and not f.accion_turno:
            otorgados += al_esperar(tablero, f)
    return otorgados
