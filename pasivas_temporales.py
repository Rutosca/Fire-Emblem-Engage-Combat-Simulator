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
from motor_calculo import distancia_entre_unidades

SID_ANIMA_FOCUS = "SID_理魔法＋"
# Elemento del tomo → efecto que Anima Focus (Soren) le cuelga al objetivo (datamine:
# Debuffs de 1 turno; fuego Def -3 y viento Mov -2 en stat_boosts, trueno act 命中値 -20).
EFECTOS_ANIMA_FOCUS = {
    "fuego":  "SID_理魔法＋_炎_効果",
    "trueno": "SID_理魔法＋_雷_効果",
    "viento": "SID_理魔法＋_風_効果",
}

SID_GET_BEHIND_ME = "SID_僕が守ります！"
SID_SELF_IMPROVER = "SID_自己研鑽"
SID_MEDITATION = "SID_瞑想"

# Timing de Skill.xml "al esperar" (la unidad termina su acción sin atacar ni usar objetos)
TIMING_AL_ESPERAR = 25
# Timing de Skill.xml "al empezar la fase de la unidad" (Geosphere, Fortify Def, Folkvangr…)
TIMING_INICIO_FASE = 27
# GiveTarget: 1 = uno mismo, 3 = alrededor (RangeI 0 incluye al portador)
GIVE_UNO_MISMO, GIVE_ALREDEDOR = 1, 3
# BadState 512 = categoría "Debuff" (SID_弱体化, Seal, Leg Strike…): el efecto va a los rivales
BAD_STATE_DEBUFF = 512


def anima_focus(tablero, atacante, objetivo, arma) -> list:
    """
    Anima Focus (Soren, sincronía a vínculo 4): "When using tomes, unit inflicts Def-3
    with fire, Hit-20 with thunder, or Mov-2 with wind magic for 1 turn".

    El lastre se queda en el OBJETIVO hasta su siguiente fase, así que lo aprovechan
    también los demás aliados que le peguen después, no solo quien lo puso. Se llama
    justo después de resolver el combate. Devuelve [(nombre_unidad, estado)].
    """
    if not tablero or atacante is None or objetivo is None or not getattr(objetivo, "viva", False):
        return []
    if not _tiene_pasiva(atacante, SID_ANIMA_FOCUS):
        return []
    if str(getattr(arma, "tipo", "") or "").lower() not in ("tomo", "tome"):
        return []
    from pasivas_overlay import _elemento_del_arma
    sid_efecto = EFECTOS_ANIMA_FOCUS.get(_elemento_del_arma(arma))
    if not sid_efecto:
        return []   # luz, oscuridad o un tomo sin elemento: la habilidad no dice nada
    info = condicion_dsl.HABILIDADES_CATALOGO.get(sid_efecto) or {}
    # "Durante 1 turno": caduca al entrar en la siguiente fase del objetivo
    fase = "jugador" if getattr(objetivo, "es_aliado", False) else "enemigo"
    elemento = next(e for e, s in EFECTOS_ANIMA_FOCUS.items() if s == sid_efecto)
    boosts = dict(info.get("stat_boosts") or {})
    # Verificado en juego (2026-09-28): el Mov-2 del viento NO se aplica — el enemigo sigue
    # con su movimiento normal aunque el texto y el datamine lo digan. El Def-3 del fuego sí.
    boosts.pop("mov", None)
    est = objetivo.otorgar_estado_temporal(
        sid_efecto, f"Anima Focus ({elemento})", boosts,
        fase, int(getattr(tablero, "turno_actual", 1)) + 1,
        origen=str(getattr(atacante, "nombre", "") or ""))
    return [(objetivo.nombre, est)] if est else []


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
        if distancia_entre_unidades(f, ficha_danada) > 2:
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


def al_empezar_fase(tablero, es_aliado: bool) -> list:
    """
    Evento: empieza la fase de un bando (Skill.xml Timing 27). Cada portador vivo cuya
    Condition se cumple (周囲の味方数 > 0 = "si tiene aliados adyacentes") otorga sus
    give_sids como estado temporal:
      - GiveTarget 1: a sí mismo (Folkvangr / Nóatún con HP bajo).
      - GiveTarget 3: a las unidades a distancia RangeI..RangeO; RangeI 0 incluye al
        portador (Geosphere: "grants Def/Res+3 to unit and those allies"). Van a los
        aliados, o a los rivales si el efecto es un Debuff (BadState 512: Fensalir).
    "For 1 turn" (Life 1 / Cycle 2, como Self-Improver): dura hasta el inicio de la
    siguiente fase del mismo bando. Las armas cuentan (sus EquipSids). Entre versiones
    de una familia (Geosphere / Geosphere+) solo vale la de mayor Priority, también si
    llegan de portadores distintos. Devuelve [(nombre_unidad, estado)].
    """
    fase = "jugador" if es_aliado else "enemigo"
    turno = int(getattr(tablero, "turno_actual", 1))
    vivas = [f for f in tablero.fichas.values() if f.viva and f.stats]
    mejor = {}   # (receptor, familia) -> (priority, orden, receptor, info, sid, efectos, portador)
    for portador in [f for f in vivas if f.es_aliado == es_aliado]:
        # Los verdes pendientes de unión no comparten auras con el ejército (ni al revés)
        aliados = [f for f in vivas if f is not portador and f.es_aliado == es_aliado
                   and f.union_pendiente == portador.union_pendiente]
        rivales = [f for f in vivas if f.es_aliado != es_aliado]
        sids = pasivas.sids_activos(portador) + [s for s in (getattr(portador.arma, "sids", None) or []) if s]
        for sid in pasivas._resolver_prioridades(list(dict.fromkeys(sids))):
            info = condicion_dsl.HABILIDADES_CATALOGO.get(sid) or {}
            gt = int(info.get("give_target") or 0)
            if int(info.get("timing") or 0) != TIMING_INICIO_FASE or not info.get("give_sids")                     or gt not in (GIVE_UNO_MISMO, GIVE_ALREDEDOR):
                continue
            ctx = condicion_dsl.ContextoCombate(
                unidad=portador.stats, rival=portador.stats, es_iniciador=True,
                aliados_cercanos=[(f.stats, _distancia(portador, f)) for f in aliados],
                habilidades_sids=list(sids), arma=portador.arma)
            if not pasivas._condicion_cumplida(info, ctx):
                continue
            efectos = [(h, condicion_dsl.HABILIDADES_CATALOGO.get(h) or {}) for h in info["give_sids"]]
            if gt == GIVE_UNO_MISMO:
                receptores = [portador]
            else:
                ri, ro = pasivas._rango_aura(info)
                es_debuff = all(int(ef.get("bad_state") or 0) & BAD_STATE_DEBUFF for _, ef in efectos)
                candidatos = rivales if es_debuff else aliados
                receptores = ([portador] if ri == 0 and not es_debuff else []) +                              [f for f in candidatos if max(ri, 1) <= _distancia(portador, f) <= ro]
            prio = int(info.get("priority") or 0)
            for receptor in receptores:
                clave = (receptor.nombre, pasivas._familia(sid, info))
                if clave not in mejor or prio > mejor[clave][0]:
                    mejor[clave] = (prio, len(mejor), receptor, info, sid, efectos, portador)
    otorgados = []
    for _, _, receptor, info, sid, efectos, portador in sorted(mejor.values(), key=lambda m: m[1]):
        for sid_ef, ef in efectos:
            est = receptor.otorgar_estado_temporal(
                sid_ef, info.get("nombre") or sid, dict(ef.get("stat_boosts") or {}),
                fase, turno + 1, origen=portador.nombre)
            if est:
                otorgados.append((receptor.nombre, est))
    return otorgados


def _distancia(a, b) -> int:
    return distancia_entre_unidades(a, b)


def al_terminar_fase_jugador(tablero) -> list:
    """
    Evento: el jugador cierra su fase. Toda unidad sin `accion_turno` ha esperado
    (el juego hace esperar automáticamente a quien no actuó).
    """
    otorgados = []
    for f in tablero.fichas.values():
        # Los dobles de Call Doubles no tienen turno: no "esperan"
        if f.viva and f.es_aliado and not f.accion_turno and not f.invocador:
            otorgados += al_esperar(tablero, f)
    return otorgados
