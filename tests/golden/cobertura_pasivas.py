"""
Informe de cobertura del intérprete de pasivas (condicion_dsl) frente al datamine.

Responde a: de las habilidades que REALMENTE pueden llevar las unidades del
juego (personajes, clases, dificultad, emblemas por nivel de vínculo, enemigos
de todos los dispos, cadenas give_sids/sync_sids), ¿cuáles entiende hoy la DSL
por completo, cuáles a medias y qué vocabulario falta, ordenado por cuántas
habilidades desbloquea cada término?

Uso:
    python tests/golden/cobertura_pasivas.py            # informe en notas/cobertura_pasivas.md
    python tests/golden/cobertura_pasivas.py --resumen  # solo el resumen por consola
"""

import os
import re
import sys
import json
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import escenarios as E  # noqa: E402
import condicion_dsl as D  # noqa: E402
from cargador_dispos import CargadorDisposEngage, DISPOS_DIR  # noqa: E402
from catalogo_loader import resolver_unidad_con_catalogo  # noqa: E402

RAIZ = E.RAIZ
RUTA_INFORME = os.path.join(RAIZ, "notas", "cobertura_pasivas.md")
FUENTES_MOTOR = ["motor_calculo.py", "motor_analisis.py", "estado_tablero.py", "pasivas_temporales.py", "app.py", "catalogo_loader.py"]

# Operadores que el tokenizador/parser de la DSL no reconoce todavía.
_OPS_NO_SOPORTADOS = ()   # * / % ! ya los entiende el parser (Fase 1)
_RE_IDENT = re.compile(r'"[^"]*"|([^\s()><=+\-,"&|*/!%\d.][^\s()><=+\-,"&|*/!%]*)\s*(\()?')


def _catalogo():
    with open(os.path.join(RAIZ, "json", "catalogo_engage.json"), "r", encoding="utf-8") as f:
        return json.load(f)


# ── Universo de SIDs alcanzables ─────────────────────────────────────────────

def sids_en_escenarios() -> dict:
    """{sid: set(nombres de unidad)} de las fichas de los escenarios golden."""
    vistos = collections.defaultdict(set)
    for nombre, fn in E.escenarios_disponibles().items():
        _, tablero = fn()
        for f in tablero.fichas.values():
            for sid in (getattr(f.stats, "habilidades_sids", None) or []):
                vistos[sid].add(f"{nombre}:{f.nombre}")
    return vistos


def sids_en_todos_los_dispos() -> dict:
    """{sid: set(dispos_id)} de todas las unidades (incl. refuerzos) de M000..M026 en Extremo."""
    vistos = collections.defaultdict(set)
    if not os.path.isdir(DISPOS_DIR):
        return vistos
    cargador = CargadorDisposEngage()
    for fn in sorted(os.listdir(DISPOS_DIR)):
        m = re.fullmatch(r"(M\d{3})\.xml", fn)
        if not m:
            continue
        did = m.group(1)
        try:
            unidades = cargador.cargar_capitulo(did, "Extremo", incluir_refuerzos=True)
        except Exception:
            continue
        for u in unidades:
            try:
                ficha = resolver_unidad_con_catalogo(u)
            except Exception:
                continue
            for sid in (getattr(ficha.stats, "habilidades_sids", None) or []):
                vistos[sid].add(did)
    return vistos


def sids_del_catalogo(cat: dict) -> dict:
    """{sid: set(origen)} de personajes, clases y emblemas (todos los niveles de vínculo)."""
    vistos = collections.defaultdict(set)
    for pid, p in cat.get("personajes", {}).items():
        for campo in ("common_sids", "hard_sids", "lunatic_sids"):
            for sid in p.get(campo, []) or []:
                vistos[sid].add(f"personaje:{p.get('nombre', pid)}:{campo}")
    for jid, c in cat.get("clases", {}).items():
        for sid in list(c.get("skills_innatas") or c.get("skills") or []) + [c.get("learning_skill"), c.get("lunatic_skill")]:
            if sid:
                vistos[sid].add(f"clase:{c.get('nombre', jid)}")
    for gid, e in cat.get("emblemas", {}).items():
        nom = e.get("nombre", gid)
        if e.get("engage_attack"):
            vistos[e["engage_attack"]].add(f"emblema:{nom}:engage_attack")
        for sid in e.get("engage_skills", []) or []:
            vistos[sid].add(f"emblema:{nom}:engage")
        for sid in e.get("synchro_skills", []) or []:
            vistos[sid].add(f"emblema:{nom}:sync")
        for nivel, b in (e.get("bond_levels") or {}).items():
            for campo in ("synchro_skills", "engage_skills", "inheritance_skills"):
                for it in b.get(campo, []) or []:
                    sid = it.get("sid") if isinstance(it, dict) else it
                    if sid:
                        vistos[sid].add(f"emblema:{nom}:{campo}@{nivel}")
    return vistos


def expandir_cadenas(sids: set, hab: dict) -> dict:
    """Añade los SIDs de efecto a los que llegan give_sids / sync_sids. {sid: padre}."""
    padres = {s: None for s in sids}
    pendientes = list(sids)
    while pendientes:
        s = pendientes.pop()
        info = hab.get(s) or {}
        for hijo in (info.get("give_sids") or []) + (info.get("sync_sids") or []):
            if hijo not in padres:
                padres[hijo] = s
                pendientes.append(hijo)
    return padres


# ── Análisis de una habilidad ────────────────────────────────────────────────

def _identificadores(expr: str):
    """(identificadores, funciones, operadores_no_soportados) de una expresión de la DSL."""
    idents, funcs, ops = set(), set(), set()
    if not expr:
        return idents, funcs, ops
    for m in _RE_IDENT.finditer(expr):
        nombre, es_llamada = m.group(1), m.group(2)
        if not nombre:
            continue   # literal de cadena
        (funcs if es_llamada else idents).add(nombre)
    for op in _OPS_NO_SOPORTADOS:
        if op in expr and not (op == "!" and "!=" in expr and expr.count("!") == expr.count("!=")):
            ops.add(op)
    return idents, funcs, ops


def analizar(sid: str, info: dict, fuentes_motor: str) -> dict:
    cond = info.get("condition") or ""
    idents, funcs, ops = _identificadores(cond)
    faltan_vars = sorted(i for i in idents if i not in D.VARIABLES and i not in D.LITERALS)
    faltan_funcs = sorted(f for f in funcs if f not in D.FUNCTIONS)
    faltan_acts, faltan_en_valores = [], set()
    for nombre_jp, val in zip(info.get("act_names") or [], info.get("act_values") or []):
        if nombre_jp not in D.ACT_STAT_MAP:
            faltan_acts.append(nombre_jp)
        try:
            float(val)
        except (TypeError, ValueError):
            vi, vf, vo = _identificadores(str(val))
            faltan_en_valores |= {i for i in vi if i not in D.VARIABLES and i not in D.LITERALS}
            faltan_en_valores |= {f + "()" for f in vf if f not in D.FUNCTIONS}
            ops |= vo
    tiene_boosts = any(v for v in (info.get("stat_boosts") or {}).values()) or any(v for v in (info.get("combat_mods") or {}).values())
    tiene_acts = bool(info.get("act_names"))
    tiene_around = bool(info.get("around_condition") or info.get("around_name"))
    tiene_give = bool(info.get("give_sids"))
    tiene_sync = bool(info.get("sync_sids"))
    sin_efecto = not (tiene_boosts or tiene_acts or tiene_around or tiene_give or tiene_sync or cond)

    nombre = str(info.get("nombre") or "")
    a_mano = (sid in fuentes_motor) or (len(nombre) >= 4 and nombre.lower() in fuentes_motor)

    if sin_efecto:
        estado = "sin_efecto_codificado"
    elif tiene_around:
        estado = "evento_around"
    elif faltan_vars or faltan_funcs or faltan_acts or faltan_en_valores or ops:
        estado = "parcial" if (tiene_boosts or (tiene_acts and not faltan_acts and not faltan_vars and not faltan_funcs and not ops)) else "no_cubierta"
    else:
        estado = "cubierta"
    return {
        "sid": sid, "nombre": nombre, "estado": estado, "a_mano": a_mano,
        "condition": cond, "acts": list(zip(info.get("act_names") or [], info.get("act_operations") or [], info.get("act_values") or [])),
        "faltan_vars": faltan_vars, "faltan_funcs": faltan_funcs, "faltan_acts": faltan_acts,
        "faltan_en_valores": sorted(faltan_en_valores), "ops": sorted(ops),
        "give_target": info.get("give_target"), "give_sids": info.get("give_sids") or [], "sync_sids": info.get("sync_sids") or [],
        "around": (info.get("around_condition"), info.get("around_name"), info.get("around_operation"), info.get("around_value")) if tiene_around else None,
        "priority": info.get("priority"), "oculta": bool(info.get("oculta")),
    }


# ── Informe ──────────────────────────────────────────────────────────────────

def generar_informe(escribir: bool = True) -> str:
    cat = _catalogo()
    hab = cat.get("habilidades", {})
    fuentes = ""
    for fn in FUENTES_MOTOR:
        try:
            with open(os.path.join(RAIZ, fn), "r", encoding="utf-8") as f:
                fuentes += f.read().lower() + "\n"
        except OSError:
            pass

    origen = collections.defaultdict(set)
    for sid, quien in sids_en_escenarios().items():
        origen[sid] |= {"tablero"}
    for sid, quien in sids_en_todos_los_dispos().items():
        origen[sid] |= {"dispos"}
    for sid, quien in sids_del_catalogo(cat).items():
        origen[sid] |= {q.split(":")[0] for q in quien}
    padres = expandir_cadenas(set(origen), hab)
    for hijo, padre in padres.items():
        if padre:
            origen[hijo] |= {"cadena"}

    analisis = {}
    for sid in padres:
        info = hab.get(sid)
        if info is None:
            # Nombres sin SID: habilidades de Emblemas DLC (no están en Skill.xml) → overlay a mano
            estado_falta = "dlc_sin_datamine" if not str(sid).startswith("SID_") else "no_en_catalogo"
            analisis[sid] = {"sid": sid, "nombre": "", "estado": estado_falta, "a_mano": False, "faltan_vars": [], "faltan_funcs": [], "faltan_acts": [], "faltan_en_valores": [], "ops": [], "condition": "", "acts": [], "give_sids": [], "sync_sids": [], "around": None, "priority": None, "oculta": False, "give_target": None}
        else:
            analisis[sid] = analizar(sid, info, fuentes)

    por_estado = collections.Counter(a["estado"] for a in analisis.values())
    a_mano = [a for a in analisis.values() if a["a_mano"]]

    # Vocabulario que falta, ponderado por nº de habilidades que desbloquea
    faltas = collections.defaultdict(set)
    for a in analisis.values():
        for v in a["faltan_vars"]:
            faltas[("variable", v)].add(a["sid"])
        for f in a["faltan_funcs"]:
            faltas[("función", f + "()")].add(a["sid"])
        for x in a["faltan_acts"]:
            faltas[("act", x)].add(a["sid"])
        for x in a["faltan_en_valores"]:
            faltas[("valor", x)].add(a["sid"])
        for o in a["ops"]:
            faltas[("operador", o)].add(a["sid"])
    ranking = sorted(faltas.items(), key=lambda kv: (-len(kv[1]), kv[0]))

    L = []
    L.append("# Cobertura del intérprete de pasivas (condicion_dsl) frente al datamine\n")
    L.append("Generado por `tests/golden/cobertura_pasivas.py`. No editar a mano.\n")
    L.append(f"- Habilidades en el catálogo: **{len(hab)}**")
    L.append(f"- Alcanzables por unidades reales (personajes, clases, emblemas, dispos M000–M026 con refuerzos, cadenas give/sync): **{len(analisis)}**")
    L.append(f"- Vistas en los escenarios golden actuales: **{sum(1 for s in analisis if 'tablero' in origen[s])}**\n")
    L.append("## Estado\n")
    L.append("| estado | nº | significado |")
    L.append("|---|---:|---|")
    descr = {
        "cubierta": "Condition y Act* íntegramente en el vocabulario actual de la DSL",
        "parcial": "stat_boosts/combat_mods o parte de los acts se leen; falta vocabulario para el resto",
        "no_cubierta": "tiene Condition/Act* pero la DSL no los entiende",
        "evento_around": "efecto post-combate en área (Around*): sin motor todavía",
        "sin_efecto_codificado": "sin Condition/Act*/boosts/give: comando o flag que el motor debe tratar aparte (Canter, Vantage, Dance…)",
        "dlc_sin_datamine": "habilidad de Emblema DLC identificada solo por nombre (no está en Skill.xml): overlay a mano",
        "no_en_catalogo": "SID referenciado pero ausente del catálogo",
    }
    for est in ("cubierta", "parcial", "no_cubierta", "evento_around", "sin_efecto_codificado", "dlc_sin_datamine", "no_en_catalogo"):
        L.append(f"| {est} | {por_estado.get(est, 0)} | {descr[est]} |")
    L.append(f"\nCitadas en el código del motor (SID o nombre en {', '.join(FUENTES_MOTOR)}, comentarios incluidos): **{len(a_mano)}** (lista al final).\n")

    L.append("## Vocabulario que falta, por habilidades que desbloquea\n")
    L.append("| tipo | término | habilidades | ejemplos |")
    L.append("|---|---|---:|---|")
    for (tipo, termino), sids in ranking:
        ejemplos = ", ".join(sorted({analisis[s]['nombre'] or s for s in sids})[:4])
        L.append(f"| {tipo} | `{termino}` | {len(sids)} | {ejemplos} |")

    def _fila(a):
        faltas_txt = ", ".join(a["faltan_vars"] + [f + "()" for f in a["faltan_funcs"]] + [f"act:{x}" for x in a["faltan_acts"]] + [f"val:{x}" for x in a["faltan_en_valores"]] + [f"op:{o}" for o in a["ops"]])
        acts_txt = "; ".join(f"{n} {o} {v}" for n, o, v in a["acts"])
        return f"| `{a['sid']}` | {a['nombre']} | {'/'.join(sorted(origen[a['sid']]))} | `{a['condition']}` | {acts_txt} | {faltas_txt} |"

    for est, titulo in (("no_cubierta", "No cubiertas"), ("parcial", "Parciales"), ("evento_around", "Eventos Around*"), ("sin_efecto_codificado", "Sin efecto codificado (comandos/flags)"), ("dlc_sin_datamine", "DLC sin datamine (overlay a mano)")):
        filas = sorted((a for a in analisis.values() if a["estado"] == est), key=lambda a: a["sid"])
        L.append(f"\n## {titulo} ({len(filas)})\n")
        L.append("| SID | nombre | origen | Condition | Act* | falta |")
        L.append("|---|---|---|---|---|---|")
        for a in filas:
            L.append(_fila(a))

    L.append(f"\n## Citadas en el código del motor ({len(a_mano)})\n")
    L.append("Tras la Fase 2 el motor genérico (pasivas.recopilar_combate) aplica todas las de `estado` cubierta; las que "
             "siguen nombradas en el código son las de secuencia/eventos (Fase 3), comandos (Canter, Advance), Ataques de "
             "Emblema con geometría propia o simples menciones en comentarios.\n")
    L.append("| SID | nombre | estado DSL | Condition | Act* |")
    L.append("|---|---|---|---|---|")
    for a in sorted(a_mano, key=lambda a: (a["estado"], a["sid"])):
        acts_txt = "; ".join(f"{n} {o} {v}" for n, o, v in a["acts"])
        L.append(f"| `{a['sid']}` | {a['nombre']} | {a['estado']} | `{a['condition']}` | {acts_txt} |")

    L.append("\n## Cubiertas\n")
    L.append(", ".join(f"{a['nombre'] or a['sid']}" for a in sorted(analisis.values(), key=lambda a: a["sid"]) if a["estado"] == "cubierta"))
    texto = "\n".join(L) + "\n"
    if escribir:
        os.makedirs(os.path.dirname(RUTA_INFORME), exist_ok=True)
        with open(RUTA_INFORME, "w", encoding="utf-8", newline="\n") as f:
            f.write(texto)
    resumen = (
        f"[cobertura] alcanzables={len(analisis)} " + " ".join(f"{k}={v}" for k, v in sorted(por_estado.items()))
        + f" a_mano={len(a_mano)}\n" + "\n".join(f"  {len(s):4d}  {t}: {x}" for (t, x), s in ranking[:25])
    )
    return resumen


if __name__ == "__main__":
    print(generar_informe(escribir="--resumen" not in sys.argv))
