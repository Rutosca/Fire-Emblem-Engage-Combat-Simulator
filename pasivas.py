"""
pasivas.py — Motor de habilidades data-driven (Skill.xml vía catalogo_engage.json).

Fase 0 (esta versión): recolección determinista de los SIDs que una unidad
tiene ACTIVOS en un instante dado. Es la entrada única que usará el motor
genérico (Fase 1) para evaluar Condition/Act* con condicion_dsl, y sustituye
las comprobaciones por nombre ('gentility' in h, 'eirika' in emblema…).

Fuentes de SIDs de una unidad (todas resueltas por catalogo_loader al construir
la Unidad, salvo las que dependen del estado en combate):
  - personales (Person.xml: common / hard / lunatic según dificultad)
  - de clase (Job.xml: innatas, LearningSkill, LunaticSkill según nivel)
  - sincronía del Emblema equipado según nivel de vínculo (God.xml)
  - de Fusión del Emblema (engage_skills): solo mientras `en_fusion`
  - heredadas / escritas a mano en el roster (nombres → SID por catálogo)
  - estados temporales (give_sids ya otorgados: ver pasivas_temporales.py)

Variantes por estilo de combate: el datamine define versiones de muchas
habilidades de Emblema con sufijo de estilo (SID_カウンター_竜族, SID_重唱_魔法…).
El juego aplica la variante del estilo de la unidad si existe; aquí se hace la
misma sustitución en `sids_activos`.
"""

from dataclasses import dataclass, field
from typing import Iterable, Optional

import condicion_dsl

HABILIDADES = condicion_dsl.HABILIDADES_CATALOGO

# id canónico de estilo (constants.ESTILOS_COMBATE_ALIASES) -> sufijo de SID en Skill.xml
SUFIJO_ESTILO = {
    "dragon": "竜族",
    "qi_adept": "気功",
    "mistico": "魔法",
    "encubierto": "隠密",
    "acorazado": "重装",
    "apoyo": "連携",
    "caballeria": "騎馬",
    "volador": "飛行",
}
_SUFIJO_HEREDADA = "_継承用"


# ── Nombre visible → SID ─────────────────────────────────────────────────────

def _construir_indice_nombres() -> dict:
    """{nombre normalizado: [SIDs candidatos]} excluyendo flags ocultos y SIDs
    de efecto (los que otro SID otorga por give_sids/sync_sids)."""
    hijos = set()
    for info in HABILIDADES.values():
        hijos.update(info.get("give_sids") or [])
        hijos.update(info.get("sync_sids") or [])
    indice = {}
    for sid, info in HABILIDADES.items():
        nombre = str(info.get("nombre") or "").strip()
        if not nombre or info.get("oculta") or sid in hijos:
            continue
        indice.setdefault(nombre.lower(), []).append(sid)
    return indice


_INDICE_NOMBRES = _construir_indice_nombres()


def _sufijo_de(sid: str) -> str:
    """Sufijo tras el último '_' si es una variante (estilo / heredada); '' si es el SID base."""
    for suf in list(SUFIJO_ESTILO.values()) + [_SUFIJO_HEREDADA.lstrip("_")]:
        if sid.endswith("_" + suf):
            return suf
    return ""


def resolver_nombre_a_sid(nombre: str, estilo_combate: str = "", heredada: Optional[bool] = None) -> Optional[str]:
    """
    SID canónico de una habilidad escrita por su nombre visible (roster, tests,
    datos a mano). Devuelve None si el nombre no está en el catálogo (DLC sin
    datamine, alias inventados…).

    Desambiguación entre SIDs con el mismo nombre:
      1. Se descartan las variantes de estilo (se aplican después en sids_activos).
      2. Si `heredada` es True se prefiere la variante _継承用 (versión de herencia
         del Emblema, sin bonos de vínculo); si es False o None, la base.
    """
    if not nombre:
        return None
    nombre = str(nombre).strip()
    if nombre.startswith("SID_"):
        return nombre if nombre in HABILIDADES else None
    candidatos = _INDICE_NOMBRES.get(nombre.lower())
    if not candidatos:
        return None
    base = [s for s in candidatos if not _sufijo_de(s)]
    heredadas = [s for s in candidatos if s.endswith(_SUFIJO_HEREDADA)]
    if heredada and heredadas:
        return heredadas[0]
    if base:
        return base[0]
    return candidatos[0]


# ── SIDs activos ─────────────────────────────────────────────────────────────

def variante_por_estilo(sid: str, estilo_combate) -> str:
    """SID de la variante de estilo si el datamine la define; si no, el propio SID."""
    from motor_calculo import resolver_estilo_combate   # import diferido: motor_calculo importa este módulo
    canon = resolver_estilo_combate(estilo_combate)
    declarada = ((HABILIDADES.get(sid) or {}).get("variantes_estilo") or {}).get(canon)
    if declarada and declarada in HABILIDADES:
        return declarada
    suf = SUFIJO_ESTILO.get(canon)
    if not suf or _sufijo_de(sid):
        return sid
    candidato = f"{sid}_{suf}"
    return candidato if candidato in HABILIDADES else sid


def _dedup(sids: Iterable[str]) -> list:
    vistos, salida = set(), []
    for s in sids:
        if s and s not in vistos:
            vistos.add(s)
            salida.append(s)
    return salida


def sids_activos(unidad, incluir_variantes_estilo: bool = True) -> list:
    """
    Lista ordenada y sin duplicados de los SIDs que la unidad tiene activos
    ahora mismo: base (`habilidades_sids`) + de Fusión (`habilidades_sids_fusion`)
    si está en Fusión + estados temporales otorgados, con la variante de estilo
    de combate aplicada.

    `unidad` puede ser motor_calculo.Unidad (stats) o estado_tablero.FichaUnidad
    (se usa su `.stats` si existe).
    """
    stats = getattr(unidad, "stats", None) or unidad
    sids = list(getattr(stats, "habilidades_sids", None) or [])
    en_fusion = bool(getattr(stats, "en_fusion", False) or int(getattr(stats, "turnos_fusion_restantes", 0) or 0) > 0
                     or getattr(unidad, "en_fusion", False))
    lista_fusion = list(getattr(stats, "habilidades_sids_fusion", None) or [])
    solo_fusion = set(lista_fusion)
    # Nombres visibles (datos a mano, tests, roster sin pasar por catalogo_loader) → SID.
    # Las de Fusión guardadas por nombre ("Divine Speed") solo cuentan en Fusión.
    for nombre in (getattr(stats, "habilidades", None) or []):
        sid = resolver_nombre_a_sid(str(nombre))
        if sid and (en_fusion or sid not in solo_fusion):
            sids.append(sid)
    if en_fusion:
        sids += lista_fusion
    for estado in (getattr(stats, "estados_temporales", None) or getattr(unidad, "estados_temporales", None) or []):
        sid_est = estado.get("sid") if isinstance(estado, dict) else getattr(estado, "sid", None)
        if sid_est:
            sids.append(sid_est)
    if incluir_variantes_estilo:
        estilo = getattr(stats, "estilo_combate", "") or getattr(unidad, "estilo_combate", "")
        sids = [variante_por_estilo(s, estilo) for s in sids]
    return _dedup(sids)


def tiene_sid(unidad, *sids: str) -> bool:
    """True si alguno de los SIDs (o su variante de estilo) está activo en la unidad."""
    activos = set(sids_activos(unidad))
    for s in sids:
        if s in activos:
            return True
        estilo = getattr(getattr(unidad, "stats", None) or unidad, "estilo_combate", "")
        if variante_por_estilo(s, estilo) in activos:
            return True
    return False


# ── Motor genérico: Condition/Act* del catálogo sobre un acumulador ──────────

# Timing 20 / Target 2 (Skill.xml): aura. Los give_sids se otorgan a los aliados
# (y a uno mismo si rango_efecto empieza en 0) a distancia [RangeI, RangeO],
# evaluando Condition con 相手 = quien recibiría el efecto.
TIMING_AURA = 20
TARGET_ALIADOS = 2
# Bit 23 del Flag: el portador también recibe el efecto cuando algún aliado cumple
# la condición ("grants Avo+10 to both of them": Crimson Cheer, Alabaster Duty, Verdant Faith).
FLAG_AURA_TAMBIEN_PROPIO = 1 << 23

# Claves del acumulador que son modificadores numéricos de combate. Cualquier
# otra clave de ACT_STAT_MAP se acumula igual pero el motor la ignora hasta que
# la consuma (Fase 3).
CLAVES_COMBATE = (
    "power", "atk", "unit_atk", "power_arma", "hit", "avo", "crit", "ddg", "hit_rate", "crit_rate",
    "rival_power", "rival_hit", "rival_avo", "rival_crit", "rival_hit_rate", "rival_crit_rate",
    "rival_effectividad", "rival_defensa_efectiva",
    "terreno_avo", "rival_terreno_avo", "as", "str", "dex", "def", "res",
    "dano", "rival_dano", "golpes", "turno_extra", "rival_turno_extra", "acciones",
    "curacion", "rival_curacion", "hp", "rival_hp",
)

# Etiquetas para los textos de pasivas_activas (UI)
_ETIQUETAS = {
    "power": "Atk", "atk": "Atk", "unit_atk": "Atk", "power_arma": "Mt", "rival_power": "Atk rival",
    "hit": "Hit", "avo": "Avo", "crit": "Crit", "ddg": "Ddg", "rival_hit": "Hit rival", "rival_avo": "Avo rival",
    "rival_crit": "Crit rival", "as": "AS", "hp": "HP", "str": "Fue", "dex": "Des", "def": "Def", "res": "Res",
    "dano": "Daño", "rival_dano": "Daño rival", "terreno_avo": "Avo terreno", "rival_terreno_avo": "Avo terreno rival",
    "hit_rate": "Hit%", "crit_rate": "Crit%", "rival_hit_rate": "Hit% rival", "rival_crit_rate": "Crit% rival",
    "rival_effectividad": "efectividad rival", "rival_defensa_efectiva": "Def rival", "turno_extra": "rondas",
    "rival_turno_extra": "rondas rival", "acciones": "golpes/ronda", "golpes": "golpes",
}


def _fmt_valor(v) -> str:
    return f"{'+' if v > 0 else ''}{v:g}"


@dataclass
class Modificadores:
    """Resultado de `recopilar`: lo que las pasivas activas de una unidad aportan
    a un combate, listo para que el motor lo sume.

    valores:         {clave: Δ} sumas/restas acumuladas ("+"/"-") (claves de condicion_dsl.ACT_STAT_MAP)
    multiplicadores: {clave: producto} de los acts "*" (威力 ×1.2: sobre el daño neto)
    asignaciones:    {clave: valor} de los acts "=" (命中率 = 100, 相手の防御力 = 0…); gana el último
    textos:          {clave: texto} para acts de texto (攻撃結果, 攻撃属性)
    activas:         [{sid, nombre, valores, mult, asig, timing, stand, action, de}] en orden de
                     aplicación (`de` = nombre del aliado que otorga el efecto en un aura, o "")
    procs:           [{sid, nombre, prob, valores, mult, asig}] habilidades con スキル確率: NO están en
                     `valores`; el análisis de riesgo decide (peor caso / esperado)
    ignoradas:       [(sid, motivo)] habilidades activas que no se han podido aplicar
    sids:            todos los SIDs considerados (activos + sync + recibidos), cumplan o no su Condition
    """
    valores: dict = field(default_factory=dict)
    multiplicadores: dict = field(default_factory=dict)
    asignaciones: dict = field(default_factory=dict)
    textos: dict = field(default_factory=dict)
    activas: list = field(default_factory=list)
    procs: list = field(default_factory=list)
    ignoradas: list = field(default_factory=list)
    sids: list = field(default_factory=list)

    def get(self, clave: str, defecto: float = 0) -> float:
        return self.valores.get(clave, defecto)

    def mult(self, clave: str) -> float:
        return self.multiplicadores.get(clave, 1.0)

    def asig(self, clave: str, defecto=None):
        return self.asignaciones.get(clave, defecto)

    def tiene(self, *sids: str) -> bool:
        """True si alguno de los SIDs se ha aplicado (Condition cumplida) en este combate."""
        aplicados = {a["sid"] for a in self.activas}
        return any(s in aplicados for s in sids)

    def presente(self, *sids: str) -> bool:
        """True si alguno de los SIDs está en la lista considerada (cumpla o no su Condition)."""
        return any(s in self.sids for s in sids)

    def nombres(self) -> list:
        return _dedup(a["nombre"] for a in self.activas if a["nombre"])

    def como_dict(self) -> dict:
        return {
            "valores": {k: v for k, v in self.valores.items() if v},
            "multiplicadores": {k: v for k, v in self.multiplicadores.items() if v != 1},
            "asignaciones": dict(self.asignaciones),
            "textos": dict(self.textos),
            "activas": [dict(a, valores={k: v for k, v in a["valores"].items() if v}) for a in self.activas],
            "procs": [dict(p) for p in self.procs],
            "ignoradas": [{"sid": s, "motivo": m} for s, m in self.ignoradas],
        }

    @staticmethod
    def _partes(entrada: dict) -> list:
        partes = [f"{_fmt_valor(v)} {_ETIQUETAS.get(k, k)}" for k, v in entrada["valores"].items() if v]
        partes += [f"×{v:g} {_ETIQUETAS.get(k, k)}" for k, v in entrada.get("mult", {}).items() if v != 1]
        partes += [f"{_ETIQUETAS.get(k, k)} = {v:g}" for k, v in entrada.get("asig", {}).items() if isinstance(v, (int, float))]
        return partes

    def resumen(self, solo_con_efecto: bool = True) -> list:
        """['Nombre (+3 Atk, -1 Atk rival)', 'Aura (de Alear) (+3 Atk)', ...] para la UI.
        Con `solo_con_efecto` se omiten las activas sin modificador numérico
        (flags, comandos, efectos por golpe aún no evaluados)."""
        out = []
        for a in self.activas:
            partes = self._partes(a)
            if solo_con_efecto and not partes:
                continue
            origen = f" (de {a['de']})" if a.get("de") else ""
            out.append(f"{a['nombre'] or a['sid']}{origen}" + (f" ({', '.join(partes)})" if partes else ""))
        for p in self.procs:
            partes = self._partes(p)
            out.append(f"{p['nombre'] or p['sid']} [{p['prob']:g}%]" + (f" ({', '.join(partes)})" if partes else ""))
        return out


def _familia(sid: str, info: dict) -> str:
    """Clave para resolver prioridades: Hold Out / Hold Out+ / Hold Out++ comparten
    familia y solo aplica la de mayor `priority` (así codifica el datamine las
    versiones + de una misma habilidad)."""
    nombre = str(info.get("nombre") or "").rstrip("+＋ ").strip().lower()
    return nombre or sid


def _resolver_prioridades(sids: list) -> list:
    """Entre SIDs activos de la misma familia con priority > 0, conserva el de
    mayor prioridad. Devuelve la lista filtrada en el orden original."""
    mejor = {}
    for sid in sids:
        info = HABILIDADES.get(sid) or {}
        prio = int(info.get("priority") or 0)
        if prio <= 0:
            continue
        fam = _familia(sid, info)
        if fam not in mejor or prio > mejor[fam][0]:
            mejor[fam] = (prio, sid)
    ganadores = {s for _, s in mejor.values()}
    salida = []
    for sid in sids:
        info = HABILIDADES.get(sid) or {}
        prio = int(info.get("priority") or 0)
        if prio > 0 and sid not in ganadores:
            continue
        salida.append(sid)
    return salida


def _condicion_cumplida(info: dict, ctx) -> bool:
    cond = info.get("condition") or ""
    if callable(cond):          # overlay escrito a mano (DLC): condición en Python
        try:
            return bool(cond(ctx))
        except Exception:
            return False
    return condicion_dsl.evaluar_condicion(cond, ctx)


def expandir_sync(sids: list, ctx) -> list:
    """SyncSids (Skill.xml): sub-habilidades activas mientras lo está la principal,
    cada una con su SyncCondition (Stalwart → _効果; Sword Agility → Crit-10 solo con
    espada; Gentility → Blue Skies solo con Sacred Twins…). Iterativo: una condición
    puede depender de otro SID expandido (スキル所持)."""
    lista = _dedup(sids)
    for _ in range(6):
        ctx.habilidades_sids = lista
        nuevos = []
        for sid in lista:
            info = HABILIDADES.get(sid) or {}
            hijos = info.get("sync_sids") or []
            conds = list(info.get("sync_conditions") or [])
            for i, hijo in enumerate(hijos):
                if hijo in lista or hijo in nuevos or hijo not in HABILIDADES:
                    continue
                cond = conds[i] if i < len(conds) else ""
                if not cond or condicion_dsl.evaluar_condicion(cond, ctx):
                    nuevos.append(hijo)
        if not nuevos:
            break
        lista = lista + nuevos
    ctx.habilidades_sids = lista
    return lista


def _aplicar_sid(sid: str, ctx, mods: Modificadores, profundidad: int = 0, de: str = "") -> None:
    info = HABILIDADES.get(sid)
    if info is None:
        mods.ignoradas.append((sid, "no está en el catálogo"))
        return
    # Stand (Skill.xml): 1 = solo cuando la unidad inicia el combate, 2 = solo cuando defiende
    stand = int(info.get("stand") or 0)
    if (stand == 1 and not ctx.es_iniciador) or (stand == 2 and ctx.es_iniciador):
        return
    ctx.proc_prob = None
    if not _condicion_cumplida(info, ctx):
        return
    prob = ctx.proc_prob
    ctx.proc_prob = None
    nombre = str(info.get("nombre") or "")
    sumas, mult, asig, textos = {}, {}, {}, {}
    for clave, op, valor in condicion_dsl.leer_acts(info, ctx):
        if isinstance(valor, str):
            textos[clave] = valor
        elif op == "+":
            sumas[clave] = sumas.get(clave, 0) + valor
        elif op == "-":
            sumas[clave] = sumas.get(clave, 0) - valor
        elif op == "*":
            mult[clave] = mult.get(clave, 1.0) * valor
        elif op == "=":
            asig[clave] = valor
    entrada = {
        "sid": sid, "nombre": nombre, "valores": sumas, "mult": mult, "asig": asig,
        "timing": int(info.get("timing") or 0), "stand": stand, "action": int(info.get("action") or 0), "de": de,
    }
    if prob is not None:
        mods.procs.append(dict(entrada, prob=prob))
    else:
        for k, v in sumas.items():
            mods.valores[k] = mods.valores.get(k, 0) + v
        for k, v in mult.items():
            mods.multiplicadores[k] = mods.multiplicadores.get(k, 1.0) * v
        mods.asignaciones.update(asig)
        mods.textos.update(textos)
        mods.activas.append(entrada)
    # give_target 1 = otorgado a uno mismo: la cadena de efectos se evalúa aquí
    # con su propia Condition (Hold Out → _効果 con "HP <= ダメージ", Divine Speed →
    # ダメージ 50 %...). Auras (Timing 20) se resuelven en efectos_recibidos; el resto
    # de give_target (rival golpeado, alrededor tras combate) son eventos: Fase 3.
    gt = int(info.get("give_target") or 0)
    if profundidad < 4 and info.get("give_sids") and gt == 1:
        for hijo in info["give_sids"]:
            if hijo != sid:
                _aplicar_sid(hijo, ctx, mods, profundidad + 1, de)
    elif info.get("give_sids") and gt != 1 and int(info.get("timing") or 0) != TIMING_AURA:
        mods.ignoradas.append((sid, f"give_target={gt} (evento, Fase 3)"))


def _es_aura(info: dict) -> bool:
    return bool(info) and int(info.get("timing") or 0) == TIMING_AURA and int(info.get("target") or 0) == TARGET_ALIADOS and bool(info.get("give_sids"))


def _rango_aura(info: dict):
    r = info.get("rango_efecto") or [0, 0]
    return int(r[0] or 0), int(r[1] or 0)


def _pos(u):
    x, y = getattr(u, "x", None), getattr(u, "y", None)
    return (x, y) if isinstance(x, (int, float)) and isinstance(y, (int, float)) else None


def _alrededor_de(dador, receptor, dist_receptor, aliados_receptor) -> list:
    """[(unidad, distancia)] vistos desde `dador`, reconstruidos a partir de la lista
    de aliados del receptor (posiciones x/y cuando existen)."""
    p0 = _pos(dador)
    salida = [(receptor, dist_receptor)]
    for v, d in aliados_receptor:
        if v is dador:
            continue
        pv = _pos(v)
        if p0 and pv:
            salida.append((v, abs(p0[0] - pv[0]) + abs(p0[1] - pv[1])))
    return salida


def efectos_recibidos(unidad, aliados_cercanos, ctx_unidad=None) -> list:
    """
    [(sid_efecto, nombre_dador)] que `unidad` recibe ahora mismo de las auras
    (Timing 20 / Target 2) de sus aliados cercanos y de las suyas propias:
      - un aliado a distancia d ∈ [RangeI, RangeO] cuya Condition se cumple con
        相手 = unidad otorga sus give_sids (Guía Divina +3/-1 a adyacentes, Bond Forger…)
      - RangeI = 0 incluye al propio portador (Knightly Escort: 相手の識別子 == 識別子)
      - Flag bit 23: el portador también recibe el efecto si algún aliado en rango
        cumple la Condition (Crimson Cheer / Alabaster Duty "a ambos")
    `aliados_cercanos`: [(unidad, distancia)] del mismo bando, sin `unidad`.
    """
    salida = []
    aliados = [(u, int(d)) for u, d in (aliados_cercanos or []) if u is not unidad]
    nombre_propio = str(getattr(unidad, "nombre", "") or "")

    def _ctx(dador, receptor, dist):
        return condicion_dsl.ContextoCombate(
            unidad=dador, rival=receptor, es_iniciador=True,
            aliados_cercanos=_alrededor_de(dador, receptor, dist, aliados) if dador is not receptor else aliados,
            habilidades_sids=sids_activos(dador),
        )

    for dador, d in aliados:
        for sid in sids_activos(dador):
            info = HABILIDADES.get(sid)
            if not _es_aura(info):
                continue
            ri, ro = _rango_aura(info)
            if not (ri <= d <= ro):
                continue
            if _condicion_cumplida(info, _ctx(dador, unidad, d)):
                salida += [(h, str(getattr(dador, "nombre", "") or "")) for h in info["give_sids"]]
    for sid in sids_activos(unidad):
        info = HABILIDADES.get(sid)
        if not _es_aura(info):
            continue
        ri, ro = _rango_aura(info)
        if ri == 0 and _condicion_cumplida(info, _ctx(unidad, unidad, 0)):
            salida += [(h, "") for h in info["give_sids"]]
            continue
        if int(info.get("flag") or 0) & FLAG_AURA_TAMBIEN_PROPIO:
            if any(ri <= d <= ro and _condicion_cumplida(info, _ctx(unidad, v, d)) for v, d in aliados):
                salida += [(h, nombre_propio) for h in info["give_sids"]]
    vistos, unicos = set(), []
    for h, de in salida:
        if h not in vistos:
            vistos.add(h)
            unicos.append((h, de))
    return unicos


def recopilar(unidad, ctx, sids: Optional[list] = None, recibidos: Optional[list] = None) -> Modificadores:
    """
    Evalúa TODAS las habilidades activas de `unidad` contra `ctx`
    (condicion_dsl.ContextoCombate, ya construido desde su punto de vista) y
    devuelve sus modificadores acumulados. No toca la unidad; en el contexto
    actualiza `habilidades_sids` (con los SyncSids expandidos) y usa `proc_prob`
    como scratch.

    `sids`: lista explícita (por defecto `sids_activos(unidad)` + los del arma de `ctx`).
    `recibidos`: [(sid_efecto, nombre_dador)] de `efectos_recibidos` (auras).
    """
    mods = Modificadores()
    if sids is None:
        lista = sids_activos(unidad) + [s for s in list(getattr(ctx.arma, "sids", None) or []) if s]
    else:
        lista = list(sids)
    recibidos = list(recibidos or [])
    lista = expandir_sync(lista + [h for h, _ in recibidos], ctx)
    mods.sids = list(lista)
    origen = {h: de for h, de in recibidos}
    for sid in _resolver_prioridades(lista):
        try:
            _aplicar_sid(sid, ctx, mods, de=origen.get(sid, ""))
        except Exception as e:   # una habilidad rota nunca debe tumbar un combate
            mods.ignoradas.append((sid, f"error: {type(e).__name__}: {e}"))
    return mods


def recopilar_combate(unidad, ctx, aliados_cercanos=None) -> Modificadores:
    """`recopilar` + auras de los aliados cercanos: la entrada única de motor_calculo."""
    sids = list(ctx.habilidades_sids) if ctx.habilidades_sids else None
    return recopilar(unidad, ctx, sids=sids, recibidos=efectos_recibidos(unidad, aliados_cercanos, ctx))


# Overlay escrito a mano (Emblemas DLC sin datamine, correcciones verificadas):
# registra pseudo-SIDs con el mismo esquema del catálogo. Se importa al final para
# que pueda usar las utilidades de este módulo.
import pasivas_overlay  # noqa: E402,F401
_INDICE_NOMBRES = _construir_indice_nombres()
