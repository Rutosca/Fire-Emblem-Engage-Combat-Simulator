"""
Informe "sombra": qué aportan las pasivas según el código a mano de
motor_calculo (bloques por nombre) frente a lo que aporta el motor genérico de
pasivas.py leyendo el datamine, combate a combate, sobre los escenarios golden.

Para cada combate:
  - aportación VIEJA = números con pasivas − números con las pasivas quitadas
    (habilidades, SIDs, emblema y estados temporales vaciados), en daño, precisión
    y crítico de ambos lados.
  - aportación NUEVA = lo que `motor_pasivas` (sombra) acumula: power / rival_power
    → daño; hit / avo / rival_hit / rival_avo → precisión; crit / ddg → crítico.

Las diferencias se agrupan por las pasivas implicadas: esa lista es el trabajo
de la Fase 2 (qué bloque a mano hace algo que el datamine no expresa, o al revés).

Uso:
    python tests/golden/sombra_pasivas.py            # notas/sombra_pasivas.md
    python tests/golden/sombra_pasivas.py --resumen
"""

import os
import sys
import copy
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import escenarios as E  # noqa: E402
from motor_calculo import CalculadoraEngage  # noqa: E402
from motor_analisis import obtener_aliados_backup, obtener_protector_chain_guard, _armas_aliado  # noqa: E402

RUTA_INFORME = os.path.join(E.RAIZ, "notas", "sombra_pasivas.md")
CAMPOS = ("dano_atk", "hit_atk", "crit_atk", "dano_def", "hit_def", "crit_def")


def _sin_pasivas(stats):
    """Copia de la Unidad con todas las fuentes de pasivas vaciadas."""
    c = copy.copy(stats)
    c.habilidades = []
    c.habilidades_sids = []
    c.habilidades_sids_fusion = []
    c.emblema_nombre = ""
    c.emblema = ""
    c.estados_temporales = []
    return c


def _numeros(res) -> dict:
    a, d = res["atacante"], res["defensor"]
    return {
        "dano_atk": a["daño_por_golpe"], "hit_atk": a["precision"], "crit_atk": a["prob_critico"],
        "dano_def": d["daño_por_golpe"], "hit_def": d["precision"], "crit_def": d["prob_critico"],
    }


def _esperado_nuevo(res) -> dict:
    """Δ que el motor genérico predice para cada campo a partir de la sombra."""
    ma = (res["atacante"].get("motor_pasivas") or {}).get("valores", {})
    md = (res["defensor"].get("motor_pasivas") or {}).get("valores", {})
    g = lambda m, k: float(m.get(k, 0) or 0)
    return {
        "dano_atk": g(ma, "power") + g(md, "rival_power"),
        "hit_atk": g(ma, "hit") + g(md, "rival_hit") - g(md, "avo") - g(ma, "rival_avo"),
        "crit_atk": g(ma, "crit") + g(md, "rival_crit") - g(md, "ddg"),
        "dano_def": g(md, "power") + g(ma, "rival_power"),
        "hit_def": g(md, "hit") + g(ma, "rival_hit") - g(ma, "avo") - g(md, "rival_avo"),
        "crit_def": g(md, "crit") + g(ma, "rival_crit") - g(ma, "ddg"),
    }


def _aliados(tablero, ficha, sin_pasivas):
    cercanos = E._aliados_cercanos(tablero, ficha)
    return [(_sin_pasivas(u), d) for u, d in cercanos] if sin_pasivas else cercanos


def _simular(mapa, tablero, fichas, f_atk, f_def, arma, dist, sin_pasivas=False):
    atk, dfn = f_atk.stats, f_def.stats
    if sin_pasivas:
        atk, dfn = _sin_pasivas(atk), _sin_pasivas(dfn)
    apoyos = obtener_aliados_backup(f_atk, f_def, tablero=tablero)
    return CalculadoraEngage.simular_combate(
        atacante=atk, defensor=dfn, arma_atk=arma, arma_def=f_def.arma,
        terreno_atk=E._terreno_de(mapa, f_atk), terreno_def=E._terreno_de(mapa, f_def), distancia=dist,
        aliados_apoyo_backup=[ap.stats for ap in apoyos],
        pos_atk=(f_atk.x, f_atk.y), pos_def=(f_def.x, f_def.y), mapa=mapa,
        casillas_ocupadas={(f.x, f.y) for f in fichas if f.nombre not in (f_atk.nombre, f_def.nombre)},
        defensor_en_ruptura=bool(getattr(f_def, "en_ruptura", False)),
        # Los aliados cercanos se conservan (dan bonos de APOYO, que no son pasivas)
        # pero sin sus pasivas (auras como Guía Divina sí lo son).
        aliados_cercanos_atk=_aliados(tablero, f_atk, sin_pasivas),
        aliados_cercanos_def=_aliados(tablero, f_def, sin_pasivas),
        chain_guard_protector=obtener_protector_chain_guard(f_def, tablero),
    )


def analizar_escenario(nombre, mapa, tablero) -> list:
    """[{clave, viejo: {campo: Δ}, nuevo: {campo: Δ}, difiere: [campos], viejas: [...], nuevas: [...]}]"""
    filas = []
    fichas = [f for f in tablero.fichas.values() if f.viva and f.stats]
    for f_atk in fichas:
        for fusion in ([False, True] if (f_atk.es_aliado and getattr(f_atk, "emblema_nombre", "")) else [False]):
            E._con_fusion(f_atk, fusion)
            for arma, _eng, _n in _armas_aliado(f_atk):
                if getattr(arma, "es_engage_attack", False):
                    continue
                for f_def in fichas:
                    if f_def.es_aliado == f_atk.es_aliado or f_def.nombre == f_atk.nombre:
                        continue
                    for dist in sorted(set(int(r) for r in (arma.rango or [1]))):
                        E._sincronizar_hp(f_atk)
                        E._sincronizar_hp(f_def)
                        prev = f_atk.arma
                        f_atk.arma = arma
                        try:
                            con = _simular(mapa, tablero, fichas, f_atk, f_def, arma, dist)
                            sin = _simular(mapa, tablero, fichas, f_atk, f_def, arma, dist, sin_pasivas=True)
                        except Exception as e:
                            filas.append({"clave": f"{nombre}|{f_atk.nombre}|{arma.nombre}|{'F' if fusion else '-'}|d{dist}|{f_def.nombre}", "error": str(e)})
                            continue
                        finally:
                            f_atk.arma = prev
                        n_con, n_sin = _numeros(con), _numeros(sin)
                        viejo = {k: n_con[k] - n_sin[k] for k in CAMPOS}
                        nuevo = _esperado_nuevo(con)
                        # No comparar donde el viejo está saturado (0 % / 100 % / daño 0)
                        difiere = []
                        for k in CAMPOS:
                            saturado = (k.startswith("hit") and n_con[k] in (0, 100)) or (k.startswith("dano") and n_con[k] == 0) or (k.startswith("crit") and n_con[k] == 0)
                            if not saturado and abs(viejo[k] - nuevo[k]) >= 1:
                                difiere.append(k)
                        ma = con["atacante"].get("motor_pasivas") or {}
                        md = con["defensor"].get("motor_pasivas") or {}
                        filas.append({
                            "clave": f"{nombre}|{f_atk.nombre}|{arma.nombre}|{'F' if fusion else '-'}|d{dist}|{f_def.nombre}",
                            "viejo": viejo, "nuevo": nuevo, "difiere": difiere,
                            "viejas": sorted(set(str(p).split(" (")[0] for p in con["atacante"].get("pasivas_activas", []) + con["defensor"].get("pasivas_activas", []))),
                            "nuevas": sorted(set(a["nombre"] for a in ma.get("activas", []) + md.get("activas", []) if a.get("valores"))),
                            "procs": sorted(set(p["nombre"] for p in ma.get("procs", []) + md.get("procs", []))),
                            "ignoradas": sorted(set(i["sid"] for i in ma.get("ignoradas", []) + md.get("ignoradas", []))),
                        })
            E._con_fusion(f_atk, False)
    return filas


def generar_informe(escribir=True) -> str:
    todas = []
    for nombre, fn in sorted(E.escenarios_disponibles().items()):
        mapa, tablero = fn()
        todas += analizar_escenario(nombre, mapa, tablero)
    filas = [f for f in todas if "error" not in f]
    errores = [f for f in todas if "error" in f]
    coinciden = [f for f in filas if not f["difiere"]]
    difieren = [f for f in filas if f["difiere"]]

    grupos = collections.defaultdict(list)
    for f in difieren:
        clave = ("viejas=" + (", ".join(f["viejas"]) or "—") + " | nuevas=" + (", ".join(f["nuevas"]) or "—"))
        grupos[clave].append(f)

    procs = collections.Counter(p for f in filas for p in f["procs"])
    ignoradas = collections.Counter(i for f in filas for i in f["ignoradas"])

    L = ["# Sombra: pasivas a mano (motor_calculo) vs motor genérico (pasivas.py)\n",
         "Generado por `tests/golden/sombra_pasivas.py`. No editar a mano.\n",
         f"- Combates analizados: **{len(filas)}** (errores: {len(errores)})",
         f"- Coinciden (misma aportación en daño/precisión/crítico de ambos lados): **{len(coinciden)}**",
         f"- Difieren: **{len(difieren)}**\n",
         "## Diferencias agrupadas por pasivas implicadas\n",
         "`viejo` = aportación del código a mano (con − sin pasivas); `nuevo` = lo que predice el datamine.",
         "Cada grupo es un caso a decidir en la Fase 2: o falta vocabulario/evento en el motor nuevo, o el bloque a mano inventaba.\n",
         "| pasivas | combates | campos | ejemplo | viejo | nuevo |", "|---|---:|---|---|---|---|"]
    for clave, fs in sorted(grupos.items(), key=lambda kv: -len(kv[1])):
        campos = collections.Counter(c for f in fs for c in f["difiere"])
        ej = fs[0]
        v = {k: ej["viejo"][k] for k in ej["difiere"]}
        n = {k: round(ej["nuevo"][k], 1) for k in ej["difiere"]}
        L.append(f"| {clave} | {len(fs)} | {', '.join(f'{c}×{k}' for c, k in campos.most_common())} | `{ej['clave']}` | {v} | {n} |")

    L += ["\n## Procs (スキル確率) vistos: no entran en los números, los decide el análisis de riesgo\n"]
    L += [f"- {p}: {n} combates" for p, n in procs.most_common()] or ["- ninguno"]
    L += ["\n## Habilidades activas que el motor nuevo aún no aplica (eventos give_target ≠ 1, Fase 3)\n"]
    L += [f"- `{s}`: {n} combates" for s, n in ignoradas.most_common()] or ["- ninguna"]
    if errores:
        L += ["\n## Errores\n"] + [f"- `{f['clave']}`: {f['error']}" for f in errores[:30]]
    texto = "\n".join(L) + "\n"
    if escribir:
        with open(RUTA_INFORME, "w", encoding="utf-8", newline="\n") as f:
            f.write(texto)
    resumen = f"[sombra] combates={len(filas)} coinciden={len(coinciden)} difieren={len(difieren)} grupos={len(grupos)} errores={len(errores)}\n"
    resumen += "\n".join(f"  {len(fs):5d}  {clave}" for clave, fs in sorted(grupos.items(), key=lambda kv: -len(kv[1]))[:20])
    return resumen


if __name__ == "__main__":
    print(generar_informe(escribir="--resumen" not in sys.argv))
