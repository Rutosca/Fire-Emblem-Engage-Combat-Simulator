"""
app.py — FE Engage Tactical Assistant
API REST Flask que conecta la UI del Gemelo con el motor de cálculo.
"""

from flask import Flask, jsonify, request, render_template, abort
from motor_calculo import CalculadoraEngage, Unidad, Arma, Terreno
from estado_tablero import EstadoTablero, FichaUnidad
from lector_de_mapas import MapaTactico
from motor_de_movimiento_y_amenaza import AnalizadorAmenaza, UnidadMock, ArmaMock

import os
import re
import math
import json
import unicodedata
from cargador_dispos import CargadorDisposEngage

def normalizar_texto(texto):
    """Elimina tildes y caracteres diacríticos para búsquedas insensibles a acentos."""
    if not texto:
        return ""
    return unicodedata.normalize('NFKD', str(texto)).encode('ASCII', 'ignore').decode('utf-8').lower()

app = Flask(__name__)

# =============================================================================
# Estado global del tablero (singleton por sesión Flask)
# =============================================================================

# Cargar el JSON de mapa del capítulo 7 (formato datamine, generado por generar_mapas.py)
_ruta_mapa = os.path.join(os.path.dirname(__file__), "mapas", "CAP_7_Tiled.json")

_mapa = MapaTactico(_ruta_mapa)
tablero = EstadoTablero(mapa=_mapa)

# Cargar catálogo maestro oficial de Fire Emblem Engage
_ruta_catalogo = os.path.join(os.path.dirname(__file__), "catalogo_engage.json")
_catalogo = {}

def cargar_catalogo():
    global _catalogo
    if os.path.exists(_ruta_catalogo):
        try:
            with open(_ruta_catalogo, "r", encoding="utf-8") as f:
                _catalogo = json.load(f)
            print(f"[OK] Catálogo Engage cargado: {len(_catalogo.get('armas', {}))} armas, {len(_catalogo.get('clases', {}))} clases, {len(_catalogo.get('habilidades', {}))} habilidades, {len(_catalogo.get('emblemas', {}))} emblemas")
        except Exception as e:
            print(f"Aviso al cargar catalogo_engage.json: {e}")

cargar_catalogo()

# =============================================================================
# Diccionario Oficial de Grabados de Emblema (Datamine God.xml) y Refinado
# =============================================================================

GRABADOS_EMBLEMA = {
    "marth": {"nombre": "Marth", "emblema": "Comienzos", "mt": 1, "wt": 0, "hit": 10, "crit": 10, "avo": 5, "ddg": 5},
    "sigurd": {"nombre": "Sigurd", "emblema": "Cruzada", "mt": 1, "wt": -1, "hit": 0, "crit": 0, "avo": 20, "ddg": 0},
    "celica": {"nombre": "Celica", "emblema": "Ecos", "mt": -1, "wt": -1, "hit": 0, "crit": 0, "avo": 0, "ddg": 50},
    "micaiah": {"nombre": "Micaiah", "emblema": "Aurora", "mt": -3, "wt": -1, "hit": 0, "crit": 0, "avo": 40, "ddg": 20},
    "roy": {"nombre": "Roy", "emblema": "León", "mt": 2, "wt": 8, "hit": 0, "crit": 0, "avo": -30, "ddg": 0},
    "leif": {"nombre": "Leif", "emblema": "Genealogía", "mt": 1, "wt": 1, "hit": 20, "crit": 0, "avo": 10, "ddg": 0},
    "lucina": {"nombre": "Lucina", "emblema": "Despertar", "mt": -1, "wt": -1, "hit": 30, "crit": 0, "avo": 30, "ddg": 0},
    "lyn": {"nombre": "Lyn", "emblema": "Llama", "mt": -3, "wt": -2, "hit": 40, "crit": 20, "avo": 0, "ddg": 0},
    "ike": {"nombre": "Ike", "emblema": "Fulgor", "mt": 3, "wt": 15, "hit": 0, "crit": 0, "avo": 0, "ddg": 0},
    "byleth": {"nombre": "Byleth", "emblema": "Academia", "mt": 0, "wt": 2, "hit": 30, "crit": 10, "avo": 10, "ddg": 30},
    "corrin": {"nombre": "Corrin", "emblema": "Destino", "mt": -2, "wt": 0, "hit": 0, "crit": 30, "avo": 10, "ddg": 30},
    "eirika": {"nombre": "Eirika", "emblema": "Sagrada", "mt": 0, "wt": 0, "hit": 40, "crit": 20, "avo": -20, "ddg": -20},
    "ephraim": {"nombre": "Ephraim", "emblema": "Sagrada", "mt": 0, "wt": 0, "hit": 40, "crit": 20, "avo": -20, "ddg": -20},
    "alear": {"nombre": "Alear", "emblema": "Dragón", "mt": -1, "wt": -1, "hit": 20, "crit": 20, "avo": 20, "ddg": 20},
}

REFINES_GENERICOS = {
    1: {"mt": 1, "hit": 5, "crit": 0, "wt": 0},
    2: {"mt": 2, "hit": 5, "crit": 5, "wt": 0},
    3: {"mt": 3, "hit": 10, "crit": 5, "wt": -1},
    4: {"mt": 4, "hit": 10, "crit": 10, "wt": -1},
    5: {"mt": 5, "hit": 15, "crit": 10, "wt": -2},
}

def parsear_arma_string(raw_str):
    """
    Parsea nombres de armas con nivel de forja (+1..+5) y grabado de emblema (Marth, Sigurd, etc.).
    """
    if not raw_str:
        return None
    raw_str = str(raw_str).strip()

    # 1. Detectar grabado de emblema entre paréntesis: (Marth), (Sigurd), etc.
    grabado_info = None
    m_grab = re.search(r'\(([^)]+)\)', raw_str)
    limpio = raw_str
    if m_grab:
        grab_nom = m_grab.group(1).lower().strip()
        grab_nom = grab_nom.replace("grabado de", "").replace("marca de", "").replace("engrave", "").strip()
        for k, v in GRABADOS_EMBLEMA.items():
            if k in grab_nom or grab_nom in k or v["emblema"].lower() in grab_nom:
                grabado_info = v
                break
        limpio = re.sub(r'\([^)]+\)', '', limpio).strip()

    # 2. Detectar nivel de refinamiento (+1..+5)
    refine_lvl = 0
    m_ref = re.search(r'\+(\d+)', limpio)
    if m_ref:
        refine_lvl = min(5, max(1, int(m_ref.group(1))))
        limpio = re.sub(r'\+\d+', '', limpio).strip()

    # 3. Buscar arma base en el catálogo
    base_aid, ainfo = _buscar_en_catalogo("armas", limpio)
    if not ainfo:
        return None

    base_mt = int(ainfo.get("mt", 5))
    base_wt = int(ainfo.get("wt", 5))
    base_hit = int(ainfo.get("hit", 80))
    base_crit = int(ainfo.get("crit", 0))

    # Aplicar refinamiento
    ref_mod = REFINES_GENERICOS.get(refine_lvl, {"mt": 0, "hit": 0, "crit": 0, "wt": 0})
    mt_calc = base_mt + ref_mod["mt"]
    wt_calc = max(0, base_wt + ref_mod["wt"])
    hit_calc = base_hit + ref_mod["hit"]
    crit_calc = base_crit + ref_mod["crit"]

    # Aplicar grabado
    avo_bonus = 0
    ddg_bonus = 0
    if grabado_info:
        mt_calc += grabado_info["mt"]
        wt_calc = max(0, wt_calc + grabado_info["wt"])
        hit_calc += grabado_info["hit"]
        crit_calc += grabado_info["crit"]
        avo_bonus += grabado_info["avo"]
        ddg_bonus += grabado_info["ddg"]

    nombre_base = ainfo.get("nombre", base_aid)
    nombre_formateado = nombre_base
    if refine_lvl > 0:
        nombre_formateado += f"+{refine_lvl}"
    if grabado_info:
        nombre_formateado += f" ({grabado_info['nombre']})"

    return {
        "id": ainfo.get("id", base_aid),
        "nombre": nombre_formateado,
        "nombre_base": nombre_base,
        "refine_lvl": refine_lvl,
        "grabado": grabado_info["nombre"] if grabado_info else None,
        "mt": max(0, mt_calc),
        "wt": max(0, wt_calc),
        "hit": hit_calc,
        "crit": max(0, crit_calc),
        "avo_bonus": avo_bonus,
        "ddg_bonus": ddg_bonus,
        "tipo": ainfo.get("tipo", "Espada"),
        "rango": ainfo.get("rango", [1]),
        "es_magica": ainfo.get("es_magica", False),
        "es_smash": bool(ainfo.get("es_smash", False)),
        "efectividades": ainfo.get("efectividades", ["volador"] if ainfo.get("tipo") == "Arco" else []),
        "usos_max": ainfo.get("usos_max"),
    }


def _buscar_en_catalogo(categoria: str, texto: str):
    """
    Búsqueda fuzzy en _catalogo[categoria] por ID exacto o nombre normalizado.
    Devuelve (key, item_dict) o (None, None) si no lo encuentra.
    """
    datos = _catalogo.get(categoria, {})
    if texto in datos:
        return texto, datos[texto]
    texto_norm = normalizar_texto(texto)
    for k, v in datos.items():
        if normalizar_texto(v.get("nombre", "")) == texto_norm or normalizar_texto(k) == texto_norm:
            return k, v
    return None, None



@app.route("/api/catalogo/recargar", methods=["POST", "GET"])
def recargar_catalogo_endpoint():
    cargar_catalogo()
    return jsonify({"ok": True, "armas": len(_catalogo.get('armas', {})), "emblemas": len(_catalogo.get('emblemas', {}))})


@app.route("/api/mapa/recargar", methods=["POST", "GET"])
def recargar_mapa_endpoint():
    """Recarga el JSON del mapa activo en caliente, sin reiniciar el servidor.
    Util durante el desarrollo: edita en Tiled, exporta, llama a este endpoint."""
    global _mapa, tablero
    try:
        _mapa = MapaTactico(_ruta_mapa)
        tablero.mapa = _mapa
        tipos = {}
        for x in range(_mapa.ancho):
            for y in range(_mapa.alto):
                t = _mapa.grid[x][y]
                tipos[t.nombre] = tipos.get(t.nombre, 0) + 1
        print(f"[Mapa recargado] {_mapa.ancho}x{_mapa.alto} | tipos: {tipos}")
        return jsonify({"ok": True, "ancho": _mapa.ancho, "alto": _mapa.alto, "tipos": tipos})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# =============================================================================
# API — Estado del tablero
# =============================================================================

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/estado", methods=["GET"])
def obtener_estado():
    """Devuelve el estado completo del tablero."""
    snap = tablero.snapshot()
    snap["mapa"] = {"ancho": _mapa.ancho, "alto": _mapa.alto} if _mapa else {"ancho": 24, "alto": 17}
    return jsonify(snap)

@app.route("/api/terreno/<int:x>/<int:y>", methods=["GET"])
def obtener_info_terreno(x, y):
    """Devuelve información táctica de una casilla."""
    mapa_actual = tablero.mapa if (tablero and tablero.mapa) else _mapa
    t = mapa_actual.obtener_terreno(x, y) if mapa_actual else None
    if t is None:
        return jsonify({"error": "Casilla fuera del mapa"}), 404
    return jsonify({
        "x": x, "y": y,
        "nombre": t.nombre,
        "caminable": t.caminable,
        "volable": t.volable,
        "avo": t.avo,
        "dfn": t.dfn,
        "coste_mov": t.coste_mov,
        "curacion_turno": getattr(t, 'curacion_turno', 0),
        "es_antirruptura": getattr(t, 'es_antirruptura', False),
        "es_recarga_emblema": getattr(t, 'es_recarga_emblema', False),
    })

@app.route("/api/catalogo/buscar", methods=["GET"])
def buscar_catalogo():
    """
    Buscador rápido autocompletable en el catálogo maestro de Engage.
    Query params:
        q: término de búsqueda (ej: 'Iron Sword', 'Marth', 'Canto', 'Poción')
        tipo: 'armas' | 'clases' | 'habilidades' | 'emblemas' | 'personajes' | 'todos'
    """
    q = request.args.get("q", "").strip()
    tipo = request.args.get("tipo", "todos").strip().lower()

    if not q:
        return jsonify({"resultados": []})

    q_norm = normalizar_texto(q)
    resultados = []
    categorias = [tipo] if tipo in _catalogo else ["armas", "clases", "habilidades", "emblemas", "personajes"]
    vistos = set()

    for cat in categorias:
        if cat not in _catalogo:
            continue
        for key, item in _catalogo[cat].items():
            nombre = item.get("nombre", "")
            nombre_norm = normalizar_texto(nombre)
            key_norm = normalizar_texto(key)
            ascii_norm = normalizar_texto(item.get("ascii_name", ""))

            # Filtrar duplicados de scripts de eventos / enemigos para emblemas
            if cat == "emblemas" and (key.startswith("GID_M0") or "相手" in key or "敵" in key or nombre == "???"):
                continue

            if q_norm in nombre_norm or q_norm in key_norm or (ascii_norm and q_norm in ascii_norm):
                display_nombre = nombre

                # Deduplicar en la lista devuelta
                dedup_key = (cat, display_nombre)
                if dedup_key in vistos:
                    continue
                vistos.add(dedup_key)

                # Si es un objeto consumible con usos múltiples (ej: Poción de 3 usos), ofrecer desglose
                usos_max = item.get("usos_max")
                if cat == "armas" and usos_max and usos_max > 1:
                    for u in range(usos_max, 0, -1):
                        resultados.append({
                            "categoria": cat,
                            "id": key,
                            "nombre": f"{display_nombre} ({u})",
                            "nombre_base": display_nombre,
                            "usos": u,
                            "usos_max": usos_max,
                            "datos": item
                        })
                else:
                    resultados.append({
                        "categoria": cat,
                        "id": key,
                        "nombre": display_nombre,
                        "datos": item
                    })

                    # Sugerir variantes de forja (+1..+5) y grabado si la búsqueda encaja
                    if cat == "armas" and item.get("tipo") in {'Espada', 'Hacha', 'Lanza', 'Artes', 'Arco', 'Tomo', 'Daga'}:
                        if "+" in q or any(k in q_norm for k in GRABADOS_EMBLEMA):
                            parsed_exact = parsear_arma_string(q)
                            if parsed_exact and parsed_exact["nombre_base"] == display_nombre:
                                resultados.insert(0, {
                                    "categoria": cat,
                                    "id": key,
                                    "nombre": parsed_exact["nombre"],
                                    "nombre_base": display_nombre,
                                    "datos": parsed_exact
                                })

                if len(resultados) >= 40:
                    break

    # Si la búsqueda es directamente un arma con + o grabado (ej: 'Libération+2 (Marth)')
    if (tipo == "todos" or tipo == "armas") and not any(r["nombre"] == q for r in resultados):
        parsed_q = parsear_arma_string(q)
        if parsed_q:
            resultados.insert(0, {
                "categoria": "armas",
                "id": parsed_q["id"],
                "nombre": parsed_q["nombre"],
                "nombre_base": parsed_q["nombre_base"],
                "datos": parsed_q
            })

    return jsonify({"query": q, "total": len(resultados), "resultados": resultados})


# =============================================================================
# API — Gestión de fichas
# =============================================================================

def resolver_unidad_con_catalogo(data):
    """
    Toma los datos enviados desde la UI (o Tiled) y resuelve stats, clase, arma e inventario
    utilizando el catálogo oficial compilado (catalogo_engage.json).
    """
    nombre = data.get("nombre", "Unidad").strip()
    es_aliado = data.get("es_aliado", True)
    x = int(data.get("x", 0))
    y = int(data.get("y", 0))
    nivel = max(1, int(data.get("nivel", 1)))
    # Dificultad: viene del preset via cargador_dispos, o por defecto Extremo
    dificultad = data.get("dificultad", "Extremo").lower()
    # Level-ups extras para crecimientos (AutoGrowOffset del Person.xml por dificultad)
    auto_grow_extra = int(data.get("auto_grow_extra", 0))
    # Offsets de stats por dificultad (OffsetL/H/N del Person.xml)
    p_offset_diff = data.get("p_offset", {})

    clase_id = data.get("clase_id", "")
    clase_info = _catalogo.get("clases", {}).get(clase_id) if clase_id else None

    # Si no viene por ID, buscar por nombre
    if not clase_info and data.get("clase_nombre"):
        cn = normalizar_texto(data.get("clase_nombre"))
        for cid, cdata in _catalogo.get("clases", {}).items():
            if normalizar_texto(cdata.get("nombre", "")) == cn or normalizar_texto(cid) == cn:
                clase_info = cdata
                clase_id = cid
                break

    # 1. Buscar si es un personaje con datos propios (Alear, Alcryst, Citrinne, Lapis, etc.)
    p_info = None
    pid = data.get("pid", "")
    if pid and pid in _catalogo.get("personajes", {}):
        p_info = _catalogo["personajes"][pid]
    else:
        n_norm = normalizar_texto(nombre)
        for cpid, cperson in _catalogo.get("personajes", {}).items():
            if normalizar_texto(cperson.get("nombre", "")) == n_norm or normalizar_texto(cpid) == n_norm:
                p_info = cperson
                break

    # Bonos de Emblema (si aplica)
    emblema_id = data.get("emblema_id", "")
    emblema_info = _catalogo.get("emblemas", {}).get(emblema_id) if emblema_id else None

    # Si no viene por ID, buscar por nombre
    if not emblema_info and data.get("emblema_nombre"):
        en_raw = data.get("emblema_nombre", "").strip()
        en_norm = normalizar_texto(en_raw)
        for eid, edata in _catalogo.get("emblemas", {}).items():
            nom = normalizar_texto(edata.get("nombre", ""))
            ascii_n = normalizar_texto(edata.get("ascii_name", ""))
            link_n = normalizar_texto(edata.get("link_name", ""))
            eid_n = normalizar_texto(eid)
            if en_norm == nom or en_norm == ascii_n or en_norm == link_n or en_norm == eid_n or (en_norm in nom and len(en_norm) >= 3):
                emblema_info = edata
                emblema_id = eid
                break

    es_sigurd = bool(emblema_info and ("siglud" in str(emblema_id).lower() or "sigurd" in str(emblema_info.get("nombre", "")).lower())) or ("sigurd" in str(data.get("emblema_nombre", "")).lower())
    tiene_botas = any("bota" in str(p).lower() for p in data.get("potenciadores_usados", []))

    # Stats base de la clase y Movimiento
    c_bases = clase_info.get("base_stats", {}) if clase_info else {}
    style = clase_info.get("estilo_combate", "") if clase_info else ""
    mov_base = clase_info.get("mov", 4) if clase_info else 4

    if "mov" in data and data["mov"] is not None and str(data["mov"]).strip() != "":
        mov = int(data["mov"])
    else:
        mov = mov_base + (1 if es_sigurd else 0) + (1 if tiene_botas else 0)

    if p_info and es_aliado:
        # Personaje único aliado con estadísticas canónicas de Serenes Forest
        p_bases = p_info.get("base_stats", {})
        p_growths = p_info.get("growths", {})
        c_growths = clase_info.get("growths", {}) if clase_info else {}
        join_lvl = p_info.get("nivel_base", 1)
        join_stats = p_info.get("join_stats", {})

        if nivel == join_lvl and join_stats:
            calc_hp  = join_stats.get("hp", 20)
            calc_str = join_stats.get("str", 6)
            calc_mag = join_stats.get("mag", 0)
            calc_dex = join_stats.get("dex", 5)
            calc_spd = join_stats.get("spd", 6)
            calc_def = join_stats.get("def", 5)
            calc_res = join_stats.get("res", 2)
            calc_lck = join_stats.get("lck", 4)
            calc_bld = join_stats.get("bld", 5)
        else:
            lvl_diff = max(0, nivel - 1)
            calc_hp  = c_bases.get("hp", 0)  + p_bases.get("hp", 20)  + round((c_growths.get("hp", 0)  + p_growths.get("hp", 45)) * lvl_diff / 100.0)
            calc_str = c_bases.get("str", 0) + p_bases.get("str", 6)  + round((c_growths.get("str", 0) + p_growths.get("str", 30)) * lvl_diff / 100.0)
            calc_mag = c_bases.get("mag", 0) + p_bases.get("mag", 0)  + round((c_growths.get("mag", 0) + p_growths.get("mag", 15)) * lvl_diff / 100.0)
            calc_dex = c_bases.get("dex", 0) + p_bases.get("dex", 5)  + round((c_growths.get("dex", 0) + p_growths.get("dex", 35)) * lvl_diff / 100.0)
            calc_spd = c_bases.get("spd", 0) + p_bases.get("spd", 6)  + round((c_growths.get("spd", 0) + p_growths.get("spd", 35)) * lvl_diff / 100.0)
            calc_def = c_bases.get("def", 0) + p_bases.get("def", 5)  + round((c_growths.get("def", 0) + p_growths.get("def", 25)) * lvl_diff / 100.0)
            calc_res = c_bases.get("res", 0) + p_bases.get("res", 2)  + round((c_growths.get("res", 0) + p_growths.get("res", 20)) * lvl_diff / 100.0)
            calc_lck = c_bases.get("lck", 0) + p_bases.get("lck", 4)  + round((c_growths.get("lck", 0) + p_growths.get("lck", 25)) * lvl_diff / 100.0)
            calc_bld = c_bases.get("bld", 0) + p_bases.get("bld", 5)  + round((c_growths.get("bld", 0) + p_growths.get("bld", 5))  * lvl_diff / 100.0)
    else:
        # Enemigo o unidad genérica
        p_bases = p_info.get("base_stats", {}) if p_info else {}
        p_growths = p_info.get("growths", {}) if p_info else {}

        if es_aliado:
            c_growths = clase_info.get("growths", {}) if clase_info else {}
        else:
            e_growths = clase_info.get("enemy_growths", {}) if clase_info else {}
            base_g = e_growths.get("base", {})
            hard_g = e_growths.get("hard", {})
            lunatic_g = e_growths.get("lunatic", {})
            if dificultad in ("extremo", "lunatic", "maddening"):
                c_growths = {stat: base_g.get(stat, 0) + lunatic_g.get(stat, 0)
                             for stat in ["hp", "str", "mag", "dex", "spd", "def", "res", "lck", "bld"]}
            elif dificultad in ("dificil", "hard"):
                c_growths = {stat: base_g.get(stat, 0) + hard_g.get(stat, 0)
                             for stat in ["hp", "str", "mag", "dex", "spd", "def", "res", "lck", "bld"]}
            else:  # Normal
                normal_g = clase_info.get("enemy_growths_normal", e_growths.get("normal", {}))
                c_growths = {stat: max(0, base_g.get(stat, 0) + normal_g.get(stat, 0))
                             for stat in ["hp", "str", "mag", "dex", "spd", "def", "res", "lck", "bld"]}

        lvl_ups = max(0, nivel - 1 + auto_grow_extra)
        lvl_factor = lvl_ups / 100.0

        calc_hp  = c_bases.get("hp", 20)  + p_offset_diff.get("hp",  0) + int((c_growths.get("hp",  45) + p_growths.get("hp",  0)) * lvl_factor)
        calc_str = c_bases.get("str", 6)  + p_offset_diff.get("str", 0) + int((c_growths.get("str", 30) + p_growths.get("str", 0)) * lvl_factor)
        calc_mag = c_bases.get("mag", 0)  + p_offset_diff.get("mag", 0) + int((c_growths.get("mag", 15) + p_growths.get("mag", 0)) * lvl_factor)
        calc_dex = c_bases.get("dex", 5)  + p_offset_diff.get("dex", 0) + int((c_growths.get("dex", 35) + p_growths.get("dex", 0)) * lvl_factor)
        calc_spd = c_bases.get("spd", 6)  + p_offset_diff.get("spd", 0) + int((c_growths.get("spd", 35) + p_growths.get("spd", 0)) * lvl_factor)
        calc_def = c_bases.get("def", 5)  + p_offset_diff.get("def", 0) + int((c_growths.get("def", 25) + p_growths.get("def", 0)) * lvl_factor)
        calc_res = c_bases.get("res", 2)  + p_offset_diff.get("res", 0) + int((c_growths.get("res", 20) + p_growths.get("res", 0)) * lvl_factor)
        calc_lck = c_bases.get("lck", 4)  + p_offset_diff.get("lck", 0) + int((c_growths.get("lck", 25) + p_growths.get("lck", 0)) * lvl_factor)
        calc_bld = c_bases.get("bld", 5)  + p_offset_diff.get("bld", 0) + int((c_growths.get("bld",  5) + p_growths.get("bld", 0)) * lvl_factor)

    # Clamping de estadísticas a valores válidos no negativos
    calc_hp  = max(1, calc_hp)
    calc_str = max(0, calc_str)
    calc_mag = max(0, calc_mag)
    calc_dex = max(0, calc_dex)
    calc_spd = max(0, calc_spd)
    calc_def = max(0, calc_def)
    calc_res = max(0, calc_res)
    calc_lck = max(0, calc_lck)
    calc_bld = max(1, calc_bld)

    # Si el usuario mandó stats explícitos, sobreescribir
    if "stats" in data and isinstance(data["stats"], dict):
        s = data["stats"]
        calc_hp  = max(1, int(s.get("hp", calc_hp)))
        calc_str = max(0, int(s.get("fuerza", s.get("str", calc_str))))
        calc_mag = max(0, int(s.get("magia", s.get("mag", calc_mag))))
        calc_dex = max(0, int(s.get("destreza", s.get("dex", calc_dex))))
        calc_spd = max(0, int(s.get("velocidad", s.get("spd", calc_spd))))
        calc_def = max(0, int(s.get("defensa", s.get("def", calc_def))))
        calc_res = max(0, int(s.get("resistencia", s.get("res", calc_res))))
        calc_lck = max(0, int(s.get("suerte", s.get("lck", calc_lck))))
        calc_bld = max(1, int(s.get("complexion", s.get("bld", calc_bld))))

    en_fusion = bool(data.get("en_fusion", False)) or int(data.get("turnos_fusion", 0)) > 0
    es_lord = data.get("es_lord", False) or "alear" in nombre.lower()
    es_volador = (style == "Flier" or "wyvern" in str(clase_info).lower() or "pegasus" in str(clase_info).lower() or data.get("es_volador", False))

    # tipo_movimiento y estilo_combate vienen de la clase del personaje
    tipo_movimiento = clase_info.get("tipo_movimiento", "infantería") if clase_info else data.get("tipo_movimiento", "infantería")
    estilo_combate = clase_info.get("estilo_combate") or clase_info.get("style", "Infantería") if clase_info else data.get("estilo_combate", "Infantería")
    emb_nom = emblema_info.get("nombre", "") if emblema_info else data.get("emblema_nombre", "")
    habs_lista = list(data.get("habilidades", []))
    if isinstance(habs_lista, str):
        habs_lista = [habs_lista]

    if emblema_info:
        for sid in emblema_info.get("synchro_skills", []):
            sk_info = _catalogo.get("habilidades", {}).get(sid)
            s_nom = sk_info.get("nombre", sid) if sk_info else sid
            if s_nom and s_nom not in habs_lista and not any(s_nom.startswith(pfx) for pfx in ["HP +", "Strength +", "Magic +", "Dexterity +", "Speed +", "Defense +", "Resistance +", "Res ", "Phy "]):
                habs_lista.append(s_nom)

    if es_sigurd:
        for sig_hab in ["Canter", "Galopada", "Momentum", "助走", "再移動"]:
            if sig_hab not in habs_lista and sig_hab in ["Canter", "Momentum"]:
                habs_lista.append(sig_hab)

    stats_obj = Unidad(
        nombre=nombre,
        hp=calc_hp,
        fuerza=calc_str,
        magia=calc_mag,
        destreza=calc_dex,
        velocidad=calc_spd,
        defensa=calc_def,
        resistencia=calc_res,
        suerte=calc_lck,
        complexion=calc_bld,
        es_lord=es_lord,
        energia_emblema=int(data.get("energia_emblema", 6)),
        max_energia_emblema=6,
        turnos_fusion_restantes=3 if en_fusion else int(data.get("turnos_fusion", 0)),
        es_dragon=(style == "Dragon" or "alear" in nombre.lower()),
        tipo_movimiento=tipo_movimiento,
        hp_max=calc_hp,
        habilidades=habs_lista,
        emblema_nombre=emb_nom,
        estilo_combate=estilo_combate,
    )

    # Resolver arma principal / inventario
    inventario_raw = list(data.get("inventario", []))
    inventario_resuelto = []
    arma_equipada = None

    arma_id_directa = data.get("arma_id") or data.get("arma_nombre") or data.get("arma")
    if arma_id_directa and not inventario_raw:
        inventario_raw = [{"arma": arma_id_directa, "equipada": True}]

    # Inyección de Fusión (Engage Mode)
    if en_fusion and emblema_info:
        stats_obj.turnos_fusion_restantes = 3
        # Añadir armas de Engage al inventario temporal
        for iid in emblema_info.get("engage_items", []):
            ya_esta = any(
                (isinstance(it, dict) and (it.get("id") == iid or it.get("arma") == iid or it.get("nombre") == iid))
                or (isinstance(it, str) and (it == iid or iid in it))
                for it in inventario_raw
            )
            if not ya_esta:
                inventario_raw.append({"arma": iid, "id": iid, "equipada": False, "es_engage": True})

        # Añadir habilidades de Engage
        habilidades_existentes = list(data.get("habilidades", []))
        if isinstance(habilidades_existentes, str):
            habilidades_existentes = [habilidades_existentes]

        for sid in emblema_info.get("engage_skills", []):
            skill_info = _catalogo.get("habilidades", {}).get(sid)
            s_nom = skill_info.get("nombre", sid) if skill_info else sid
            if s_nom not in habilidades_existentes:
                habilidades_existentes.append(s_nom)

        data["habilidades"] = habilidades_existentes

    re_usos = re.compile(r"^(.*?)(?:\s*(?:\((\d+)(?:\/\d+)?\)|x(\d+)))?\s*$")

    for item in inventario_raw:
        if isinstance(item, dict):
            aid = item.get("arma") or item.get("id") or item.get("nombre") or ""
            es_eq = item.get("equipada", False)
            es_eng = item.get("es_engage", False)
            usos_override = item.get("usos")
        else:
            aid = str(item)
            es_eq = False
            es_eng = False
            usos_override = None

        m = re_usos.match(str(aid).strip())
        if m:
            base_aid = m.group(1).strip()
            usos_str = m.group(2) or m.group(3)
            if usos_str and usos_override is None:
                try:
                    usos_override = int(usos_str)
                except ValueError:
                    pass
        else:
            base_aid = str(aid).strip()

        parsed_w = parsear_arma_string(aid if aid else base_aid)
        if parsed_w:
            usos_max = parsed_w.get("usos_max")
            usos_actual = usos_override if (usos_override is not None) else usos_max
            display_nombre = f"{parsed_w['nombre']} ({usos_actual})" if (usos_max and usos_max > 1) else parsed_w['nombre']

            item_dict = {
                "id": parsed_w["id"],
                "nombre": display_nombre,
                "arma": display_nombre,
                "nombre_base": parsed_w["nombre_base"],
                "refine_lvl": parsed_w.get("refine_lvl", 0),
                "grabado": parsed_w.get("grabado"),
                "tipo": parsed_w["tipo"],
                "mt": parsed_w["mt"],
                "wt": parsed_w["wt"],
                "hit": parsed_w["hit"],
                "crit": parsed_w["crit"],
                "avo_bonus": parsed_w.get("avo_bonus", 0),
                "ddg_bonus": parsed_w.get("ddg_bonus", 0),
                "rango": parsed_w["rango"],
                "es_magica": parsed_w["es_magica"],
                "efectividades": parsed_w["efectividades"],
                "usos": usos_actual,
                "usos_max": usos_max,
                "es_engage": es_eng,
                "es_smash": parsed_w.get("es_smash", False),
                "equipada": es_eq,
            }
            inventario_resuelto.append(item_dict)

            if es_eq or arma_equipada is None:
                arma_equipada = Arma(
                    nombre=display_nombre,
                    mt=parsed_w["mt"],
                    wt=parsed_w["wt"],
                    hit=parsed_w["hit"],
                    crit=parsed_w["crit"],
                    es_magica=parsed_w["es_magica"],
                    tipo=parsed_w["tipo"],
                    rango=parsed_w["rango"],
                    efectividades=parsed_w["efectividades"],
                    avo_bonus=parsed_w.get("avo_bonus", 0),
                    ddg_bonus=parsed_w.get("ddg_bonus", 0),
                    es_smash=parsed_w.get("es_smash", False),
                )
        else:
            base_aid_k, ainfo = _buscar_en_catalogo("armas", base_aid) if base_aid else (None, None)
            if base_aid_k:
                base_aid = base_aid_k

            if ainfo:
                nombre_final = ainfo.get("nombre", "Arma")
                usos_max = ainfo.get("usos_max")
                usos_actual = usos_override if (usos_override is not None) else usos_max
                display_nombre = f"{nombre_final} ({usos_actual})" if (usos_max and usos_max > 1) else nombre_final

                es_smash_val = bool(ainfo.get("es_smash", False))
                if not es_smash_val:
                    n_low = (nombre_final or "").lower()
                    if any(w in n_low for w in ("blade", "gran espada", "greatlance", "gran lanza", "greataxe", "gran hacha", "georgios", "venomous", "ukonvasara", "carnwenhan", "aymr")):
                        es_smash_val = True

                item_dict = {
                    "id": ainfo.get("id", base_aid),
                    "nombre": display_nombre,
                    "arma": display_nombre,
                    "nombre_base": nombre_final,
                    "tipo": ainfo.get("tipo", "Espada"),
                    "mt": ainfo.get("mt", 5),
                    "wt": ainfo.get("wt", 5),
                    "hit": ainfo.get("hit", 80),
                    "crit": ainfo.get("crit", 0),
                    "rango": ainfo.get("rango", [1]),
                    "es_magica": ainfo.get("es_magica", False),
                    "es_smash": es_smash_val,
                    "efectividades": ainfo.get("efectividades", ["volador"] if ainfo.get("tipo") == "Arco" else []),
                    "usos": usos_actual,
                    "usos_max": usos_max,
                    "es_engage": es_eng,
                    "equipada": es_eq,
                }
                inventario_resuelto.append(item_dict)

                if es_eq or arma_equipada is None:
                    arma_equipada = Arma(
                        nombre=display_nombre,
                        mt=ainfo.get("mt", 5),
                        wt=ainfo.get("wt", 5),
                        hit=ainfo.get("hit", 80),
                        crit=ainfo.get("crit", 0),
                        es_magica=ainfo.get("es_magica", False),
                        tipo=ainfo.get("tipo", "Espada"),
                        rango=ainfo.get("rango", [1]),
                        efectividades=ainfo.get("efectividades", []),
                        es_smash=es_smash_val,
                    )
            else:
                inventario_resuelto.append({
                    "nombre": aid,
                    "arma": aid,
                    "equipada": es_eq,
                    "es_engage": es_eng,
                })

    if arma_equipada is None:
        arma_equipada = Arma("Espada de Hierro", mt=5, wt=5, hit=90, crit=0, es_magica=False, tipo="Espada", rango=[1], efectividades=[])

    es_verde = data.get("es_verde", False)
    es_fijo = data.get("es_fijo", False) or es_verde or ("alear" in nombre.lower())

    hp_m = int(data.get("hp_max", calc_hp))
    hp_a = int(data.get("hp_actual", hp_m))
    if hp_a > hp_m:
        hp_a = hp_m

    ficha = FichaUnidad(
        nombre=nombre,
        es_aliado=es_aliado,
        es_verde=es_verde,
        es_fijo=es_fijo,
        x=x,
        y=y,
        stats=stats_obj,
        arma=arma_equipada,
        mov=mov,
        es_volador=es_volador,
        hp_max=hp_m,
        hp_actual=hp_a,
        energia_emblema=int(data.get("energia_emblema", 6)),
        max_energia_emblema=6,
        turnos_fusion=3 if en_fusion else int(data.get("turnos_fusion", 0)),
        en_fusion=en_fusion,
        clase_id=clase_id,
        clase_nombre=clase_info.get("nombre", "") if clase_info else data.get("clase_nombre", ""),
        nivel=nivel,
        emblema_id=emblema_id,
        emblema_nombre=emblema_info.get("nombre", "") if emblema_info else data.get("emblema_nombre", ""),
        habilidades=data.get("habilidades", []),
        inventario=inventario_resuelto,
        potenciadores_usados=list(data.get("potenciadores_usados", [])),
    )
    return ficha

_ruta_squad_file = os.path.join(os.path.dirname(__file__), "escuadron_guardado.json")

@app.route("/api/unidad/guardar", methods=["POST"])
@app.route("/api/registrar", methods=["POST"])
def guardar_unidad():
    """
    Crea o actualiza una unidad resolviendo sus stats con catalogo_engage.json.
    """
    data = request.get_json(force=True)
    if not data or "nombre" not in data:
        return jsonify({"error": "Falta campo 'nombre'"}), 400

    ficha = resolver_unidad_con_catalogo(data)
    tablero.registrar_unidad(ficha)
    return jsonify({"ok": True, "ficha": ficha.como_dict()})

@app.route("/api/escuadron/guardar", methods=["POST"])
def guardar_escuadron():
    """Guarda la plantilla actual de unidades aliadas activas en el servidor."""
    aliados = [f.como_dict() for f in tablero.fichas.values() if f.es_aliado and f.viva]
    # Deduplicar por nombre y por posición (priorizando nombres de personajes reales)
    aliados_dedup = []
    vistos_nombres = set()
    vistos_pos = set()
    
    # Primero añadir personajes con nombre propio
    for a in sorted(aliados, key=lambda x: 1 if "Aliado" in x.get("nombre", "") else 0):
        nom = a.get("nombre")
        pos = (a.get("x"), a.get("y"))
        if nom not in vistos_nombres and pos not in vistos_pos:
            vistos_nombres.add(nom)
            vistos_pos.add(pos)
            aliados_dedup.append(a)

    try:
        with open(_ruta_squad_file, "w", encoding="utf-8") as f:
            json.dump(aliados_dedup, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error al guardar escuadrón: {e}")

    return jsonify({
        "ok": True,
        "mensaje": f"Escuadrón guardado con éxito ({len(aliados_dedup)} aliados)",
        "escuadron": aliados_dedup
    })

@app.route("/api/escuadron/cargar", methods=["GET"])
def cargar_escuadron():
    """Devuelve la plantilla guardada de aliados."""
    if os.path.exists(_ruta_squad_file):
        try:
            with open(_ruta_squad_file, "r", encoding="utf-8") as f:
                aliados = json.load(f)
                return jsonify({"ok": True, "escuadron": aliados})
        except Exception:
            pass
    return jsonify({"ok": True, "escuadron": []})

@app.route("/api/escuadron/desplegar", methods=["POST"])
def desplegar_escuadron():
    """
    Despliega la plantilla del escuadrón en el mapa actual.
    Sustituye limpiamente a los aliados existentes / genéricos sin solapamientos ni duplicados.
    """
    if not os.path.exists(_ruta_squad_file):
        return jsonify({"error": "No hay ningún escuadrón guardado previamente."}), 404

    try:
        with open(_ruta_squad_file, "r", encoding="utf-8") as f:
            squad_guardado = json.load(f)
    except Exception as e:
        return jsonify({"error": f"Error al leer plantilla de escuadrón: {e}"}), 500

    if not squad_guardado:
        return jsonify({"error": "La plantilla de escuadrón está vacía."}), 400

    tablero.guardar_snapshot()

    # Eliminar todos los aliados existentes para evitar solapamientos con el escuadrón guardado
    aliados_actuales = [nom for nom, f in list(tablero.fichas.items()) if f.es_aliado]
    for nom in aliados_actuales:
        del tablero.fichas[nom]

    # Registrar cada aliado del escuadrón
    for s_data in squad_guardado:
        f_res = resolver_unidad_con_catalogo(s_data)
        tablero.registrar_unidad(f_res, resolver_colision=True)

    return jsonify({
        "ok": True,
        "mensaje": f"Escuadrón desplegado con éxito ({len(squad_guardado)} aliados)",
        "fichas": [f.como_dict() for f in tablero.fichas.values()]
    })

@app.route("/api/partida/exportar", methods=["GET"])
def exportar_partida():
    """Exporta el estado completo de la partida en formato JSON."""
    estado = {
        "turno_actual": tablero.turno_actual,
        "fase": tablero.fase,
        "fichas": [f.como_dict() for f in tablero.fichas.values()]
    }
    return jsonify({"ok": True, "partida": estado})

@app.route("/api/partida/importar", methods=["POST"])
def importar_partida():
    """Importa el estado completo de la partida desde un JSON."""
    data = request.get_json(force=True)
    partida = data.get("partida") or data
    fichas_raw = partida.get("fichas", [])
    if not fichas_raw:
        return jsonify({"error": "No se encontraron fichas en el archivo de partida"}), 400

    tablero.guardar_snapshot()
    tablero.limpiar()
    tablero.turno_actual = int(partida.get("turno_actual", 1))
    tablero.fase = partida.get("fase", "jugador")

    for f_data in fichas_raw:
        f_res = resolver_unidad_con_catalogo(f_data)
        tablero.registrar_unidad(f_res)

    return jsonify({
        "ok": True,
        "mensaje": f"Partida importada con éxito ({len(fichas_raw)} unidades)",
        "fichas": [f.como_dict() for f in tablero.fichas.values()]
    })

@app.route("/api/unidad/eliminar", methods=["POST"])
def eliminar_unidad():
    """Elimina permanentemente una unidad del tablero."""
    data = request.get_json(force=True)
    nombre = data.get("nombre")
    if not nombre:
        return jsonify({"error": "Falta campo 'nombre'"}), 400
    ok = tablero.eliminar_unidad(nombre)
    return jsonify({"ok": ok, "nombre": nombre})

_cargador_dispos = CargadorDisposEngage()


def _desplegar_capitulo(capitulo_id: str, dificultad: str = "Hard") -> dict:
    """
    Nucleo reutilizable de despliegue: limpia el tablero y carga las unidades
    del capitulo indicado desde los XMLs de dispos/ del datamine.
    Devuelve un dict con el resultado listo para jsonify.
    """
    tablero.fichas.clear()
    tablero.turno_actual = 1
    tablero.fase = "jugador"

    unidades_dispos = _cargador_dispos.cargar_capitulo(capitulo_id, dificultad)
    if not unidades_dispos:
        num = tablero.cargar_spawns_desde_mapa()
        return {
            "ok": True,
            "mensaje": f"Sin dispos para {capitulo_id}; cargados {num} spawns del mapa",
            "fichas": [f.como_dict() for f in tablero.fichas.values()]
        }

    for u in unidades_dispos:
        ficha = resolver_unidad_con_catalogo(u)
        tablero.registrar_unidad(ficha)

    return {
        "ok": True,
        "mensaje": f"Despliegue de {capitulo_id} ({len(unidades_dispos)} unidades) en {dificultad}",
        "fichas": [f.como_dict() for f in tablero.fichas.values()]
    }


def _auto_despliegue_inicial():
    """
    Si el mapa cargado al arranque es formato datamine, despliega automaticamente
    las unidades del capitulo correspondiente en dificultad Hard (Difícil).
    """
    if not getattr(_mapa, "es_datamine", False):
        return
    dispos_id = getattr(_mapa, "dispos_id", None)
    if not dispos_id:
        return
    try:
        resultado = _desplegar_capitulo(dispos_id, "Hard")
        print(f"[Auto-despliegue] {len(tablero.fichas)} unidades cargadas para {dispos_id} (Hard)")
    except Exception as e:
        print(f"[Auto-despliegue] Error al cargar {dispos_id}: {e}")


# Auto-despliegue de unidades en el arranque si el mapa es de datamine
_auto_despliegue_inicial()


@app.route("/api/preset/<capitulo_id>", methods=["POST"])
@app.route("/api/preset/capitulo7", methods=["POST"])
def cargar_preset_capitulo(capitulo_id=None):
    """
    Carga el despliegue oficial desde dispos/ del datamine de Engage para el capitulo solicitado.
    Si no se especifica capitulo_id, usa el del mapa activo o por defecto M007.
    """
    data = request.get_json(silent=True) or {}
    dificultad = data.get("dificultad", "Hard")
    if not capitulo_id:
        capitulo_id = getattr(_mapa, "dispos_id", None) or "M007"
    return jsonify(_desplegar_capitulo(capitulo_id, dificultad))

@app.route("/api/unidad/rango_movimiento", methods=["GET"])
def obtener_rango_movimiento():
    """
    Calcula y devuelve las casillas que puede alcanzar una unidad específica
    según su MOV, tipo de movimiento y costes reales del terreno del mapa.
    """
    nombre = request.args.get("nombre")
    if not nombre:
        return jsonify({"error": "Falta parametro nombre"}), 400

    ficha = tablero.obtener_ficha(nombre)
    if not ficha:
        for f in tablero.fichas.values():
            if normalizar_texto(f.nombre) == normalizar_texto(nombre):
                ficha = f
                nombre = f.nombre
                break

    if not ficha:
        return jsonify({"error": f"Unidad '{nombre}' no encontrada"}), 404

    # Analizador de movimiento y amenazas
    analizador = AnalizadorAmenaza(_mapa.grid, _mapa.ancho, _mapa.alto)
    
    # Construir objeto para el analizador
    umock = UnidadMock(
        x=ficha.x,
        y=ficha.y,
        mov=ficha.mov or 4,
        es_volador=ficha.es_volador,
        arma=ArmaMock(ficha.arma.rango if ficha.arma else [1])
    )
    casillas_mov = analizador.calcular_casillas_alcanzables(umock)
    
    # Ocupantes: no se puede terminar el movimiento en una casilla ocupada por otra unidad viva
    ocupadas = {(f.x, f.y) for f in tablero.fichas.values() if f.viva and f.nombre != nombre}
    casillas_validas = [[x, y] for (x, y) in casillas_mov if (x, y) not in ocupadas or (x == ficha.x and y == ficha.y)]

    return jsonify({
        "ok": True,
        "nombre": nombre,
        "mov": ficha.mov or 4,
        "es_volador": ficha.es_volador,
        "casillas": casillas_validas
    })

@app.route("/api/mover", methods=["POST"])
def mover_unidad():
    """
    Actualiza la posición de una unidad respetando las reglas de movimiento táctico.
    Llamado por la UI cuando el jugador arrastra un token.
    Body JSON: {nombre, x, y}
    """
    data = request.get_json(force=True)
    nombre = data.get("nombre")
    x = data.get("x")
    y = data.get("y")

    if nombre is None or x is None or y is None:
        return jsonify({"error": "Faltan campos: nombre, x, y"}), 400

    if not _mapa.obtener_terreno(x, y):
        return jsonify({"error": f"Coordenada ({x},{y}) fuera del mapa"}), 400

    ficha = tablero.obtener_ficha(nombre)
    if not ficha:
        for f in tablero.fichas.values():
            if normalizar_texto(f.nombre) == normalizar_texto(nombre):
                ficha = f
                nombre = f.nombre
                break

    if not ficha:
        return jsonify({"error": f"Unidad '{nombre}' no encontrada"}), 404

    # En fase de jugador, si el aliado ya actuó, no se le permite volver a mover
    if tablero.fase == "jugador" and ficha.es_aliado and ficha.ha_actuado:
        return jsonify({"error": f"{nombre} ya ha actuado este turno. Usa la Cronogema (Deshacer) para cambiar la elección."}), 400

    # 1. Casilla ocupada por otra unidad viva?
    otra_unidad = next((f for f in tablero.fichas.values() if f.viva and f.nombre != nombre and f.x == x and f.y == y), None)
    if otra_unidad:
        return jsonify({"error": f"La casilla ({x},{y}) ya está ocupada por {otra_unidad.nombre}."}), 400

    # 2. Validar alcance de movimiento táctico para la unidad (aliada o enemiga)
    analizador = AnalizadorAmenaza(_mapa.grid, _mapa.ancho, _mapa.alto)
    umock = UnidadMock(
        x=ficha.x,
        y=ficha.y,
        mov=ficha.mov or 4,
        es_volador=ficha.es_volador,
        arma=ArmaMock(ficha.arma.rango if ficha.arma else [1])
    )
    alcanzables = analizador.calcular_casillas_alcanzables(umock)
    if (x, y) not in alcanzables:
        return jsonify({"error": f"{nombre} solo puede moverse {ficha.mov or 4} casillas. La casilla ({x},{y}) está fuera de su alcance o es intransitable."}), 400

    tablero.guardar_snapshot()
    ok = tablero.mover_unidad(nombre, x, y)
    if not ok:
        return jsonify({"error": f"Unidad '{nombre}' no encontrada"}), 404

    # Si un aliado se mueve en la fase de jugador, consume su acción del turno
    if tablero.fase == "jugador" and ficha.es_aliado:
        ficha.ha_actuado = True
    elif tablero.fase == "enemigo" and not ficha.es_aliado:
        ficha.ha_actuado = True

    return jsonify({
        "ok": True,
        "nombre": nombre,
        "x": x,
        "y": y,
        "ficha": ficha.como_dict(),
        "fichas": [f.como_dict() for f in tablero.fichas.values()]
    })

@app.route("/api/muerte", methods=["POST"])
def registrar_muerte():
    """Marca una unidad como muerta. Body JSON: {nombre}"""
    data = request.get_json(force=True)
    nombre = data.get("nombre")
    if not nombre:
        return jsonify({"error": "Falta campo 'nombre'"}), 400
    tablero.guardar_snapshot()
    tablero.registrar_muerte(nombre)
    return jsonify({"ok": True, "nombre": nombre})




# ── Helper global: construir Arma desde datos de catálogo / inventario ──────
def _arma_desde_item(item_dict):
    """Convierte un dict de inventario o string en instancia de Arma con soporte para Forja y Grabados."""
    if not isinstance(item_dict, dict):
        if isinstance(item_dict, str):
            item_dict = {"nombre": item_dict}
        else:
            return None

    nombre_raw = item_dict.get("nombre", item_dict.get("arma", "Arma"))
    parsed = parsear_arma_string(nombre_raw)
    if parsed:
        return Arma(
            nombre=parsed["nombre"],
            mt=parsed["mt"],
            wt=parsed["wt"],
            hit=parsed["hit"],
            crit=parsed["crit"],
            es_magica=parsed["es_magica"],
            tipo=parsed["tipo"],
            rango=parsed["rango"],
            efectividades=parsed["efectividades"],
            avo_bonus=parsed["avo_bonus"],
            ddg_bonus=parsed["ddg_bonus"],
            es_smash=parsed.get("es_smash", False),
        )

    tipo_raw = item_dict.get("tipo", "Espada")
    TIPOS_VALIDOS = {'Espada', 'Hacha', 'Lanza', 'Artes', 'Arco', 'Tomo', 'Daga'}
    if tipo_raw in ("Bastón", "Objeto", "Accesorio", "Especial") or tipo_raw not in TIPOS_VALIDOS:
        return None

    es_smash = bool(item_dict.get("es_smash", False))
    if not es_smash:
        n_low = nombre_raw.lower()
        if any(w in n_low for w in ("blade", "gran espada", "greatlance", "gran lanza", "greataxe", "gran hacha", "georgios", "venomous", "ukonvasara", "carnwenhan", "aymr")):
            es_smash = True

    return Arma(
        nombre=nombre_raw,
        mt=int(item_dict.get("mt", 0)),
        wt=int(item_dict.get("wt", 5)),
        hit=int(item_dict.get("hit", 80)),
        crit=int(item_dict.get("crit", 0)),
        es_magica=bool(item_dict.get("es_magica", False)),
        tipo=tipo_raw,
        rango=item_dict.get("rango", [1]),
        efectividades=item_dict.get("efectividades", []),
        avo_bonus=int(item_dict.get("avo_bonus", 0)),
        ddg_bonus=int(item_dict.get("ddg_bonus", 0)),
        es_smash=es_smash,
    )

def encontrar_pos_ataque_optima(aliado, enemigo, arma):
    """
    Encuentra la mejor casilla (x, y) a la que puede moverse el aliado para atacar al enemigo con el arma dada.
    Prioriza:
    1. Si la posición actual ya está en rango válido del arma -> quedarse en (aliado.x, aliado.y).
    2. Casillas dentro de su rango de MOV donde la distancia al enemigo esté en arma.rango.
    3. Mayor bonificación de terreno (DFN/AVO) y menor distancia recorrida.
    """
    dist_actual = abs(aliado.x - enemigo.x) + abs(aliado.y - enemigo.y)
    r_arma = arma.rango if (arma and arma.rango) else [1]
    if dist_actual in r_arma:
        return [aliado.x, aliado.y]

    mejores = []
    ancho = _mapa.ancho
    alto = _mapa.alto

    ocupadas = {(f.x, f.y) for f in tablero.fichas.values() if f.viva and f.nombre != aliado.nombre}

    for dx in range(-aliado.mov, aliado.mov + 1):
        for dy in range(-aliado.mov, aliado.mov + 1):
            coste_pasos = abs(dx) + abs(dy)
            if coste_pasos > aliado.mov:
                continue
            nx = aliado.x + dx
            ny = aliado.y + dy
            if 0 <= nx < ancho and 0 <= ny < alto:
                if (nx, ny) in ocupadas:
                    continue
                t = _mapa.grid[nx][ny]
                if not (t.volable if getattr(aliado, 'es_volador', False) else t.caminable):
                    continue
                d_ene = abs(nx - enemigo.x) + abs(ny - enemigo.y)
                if d_ene in r_arma:
                    score = (t.dfn * 15) + t.avo - coste_pasos
                    mejores.append((score, [nx, ny]))

    if mejores:
        mejores.sort(key=lambda x: x[0], reverse=True)
        return mejores[0][1]

    return [aliado.x, aliado.y]


# =============================================================================
# API — Cronogema (Deshacer) y Gestión de Acciones
# =============================================================================

@app.route("/api/tablero/deshacer", methods=["POST"])
def deshacer_accion():
    """Restaura el estado anterior de la Cronogema (Time Crystal)."""
    ok = tablero.deshacer()
    return jsonify({
        "ok": ok,
        "mensaje": "⏱️ Cronogema activada: Acción deshecha." if ok else "No hay más acciones previas para deshacer.",
        "turno": tablero.turno_actual,
        "fase": tablero.fase,
        "fichas": [f.como_dict() for f in tablero.fichas.values()]
    })

@app.route("/api/turno/reiniciar_acciones", methods=["POST"])
def reiniciar_acciones_turno():
    """Reactiva las acciones de todos los aliados para el turno actual."""
    tablero.guardar_snapshot()
    tablero.reiniciar_acciones_turno()
    return jsonify({
        "ok": True,
        "mensaje": "✓ Acciones de turno reactivadas para todos los aliados.",
        "fichas": [f.como_dict() for f in tablero.fichas.values()]
    })

@app.route("/api/unidad/alternar_actuado", methods=["POST"])
def alternar_actuado():
    """Alterna el estado ha_actuado de una unidad."""
    data = request.get_json(force=True) or {}
    nombre = data.get("nombre")
    if not nombre:
        return jsonify({"error": "Falta campo nombre"}), 400
    tablero.guardar_snapshot()
    ok = tablero.alternar_actuado(nombre)
    f = tablero.obtener_ficha(nombre)
    return jsonify({
        "ok": ok,
        "ficha": f.como_dict() if f else None,
        "fichas": [x.como_dict() for x in tablero.fichas.values()]
    })


# =============================================================================
# API — Combate Interactivo y Ajustes en Tiempo Real
# =============================================================================

@app.route("/api/combate/ejecutar", methods=["POST"])
def ejecutar_combate():
    """
    Ejecuta un ataque táctico en el tablero:
    1. Si se provee pos_destino (o se calcula), mueve al atacante a la casilla.
    2. Equipa el arma seleccionada en el atacante.
    3. Simula el combate determinista exacto de Engage con pasivas y chain attacks.
    4. Resta HP real al defensor, contraataque y recoil al atacante.
    5. Marca al atacante como ha_actuado = True.
    6. Otorga cargas de energía de Emblema (+1 combate, +1 kill).
    """
    data = request.get_json(force=True) or {}
    nombre_atk = data.get("atacante")
    nombre_def = data.get("defensor")
    nombre_arma = data.get("arma_nombre")
    pos_destino = data.get("pos_destino")

    f_atk = tablero.obtener_ficha(nombre_atk)
    f_def = tablero.obtener_ficha(nombre_def)

    if not f_atk or not f_def:
        return jsonify({"error": "No se encontraron las unidades especificadas"}), 400

    # Guardar snapshot antes de la acción para la Cronogema
    tablero.guardar_snapshot()

    # 1. Posición de ataque: si viene pos_destino válida, mover al atacante
    if pos_destino and isinstance(pos_destino, (list, tuple)) and len(pos_destino) == 2:
        nx, ny = int(pos_destino[0]), int(pos_destino[1])
        tablero.mover_unidad(nombre_atk, nx, ny)

    # 2. Equipar arma
    if nombre_arma:
        for item in f_atk.inventario:
            if item.get("nombre") == nombre_arma or item.get("arma") == nombre_arma or item.get("id") == nombre_arma:
                for it in f_atk.inventario:
                    it["equipada"] = (it == item)
                a_obj = _arma_desde_item(item)
                if a_obj:
                    f_atk.arma = a_obj
                break

    # 3. Detectar aliados de apoyo (Backup) cercanos al enemigo para Chain Attacks
    aliados_backup = []
    for a in tablero.obtener_aliados():
        if a.viva and a.nombre != f_atk.nombre and a.stats and a.arma:
            st = getattr(a.stats, 'estilo_combate', '') or ''
            if st in ('De apoyo', 'Backup') or a.clase_nombre in ('Sword Fighter', 'Hero', 'Berserker', 'Warrior', 'Halberdier') or 'lapis' in a.nombre.lower():
                d_a = abs(a.x - f_def.x) + abs(a.y - f_def.y)
                r_a = a.arma.rango if (a.arma and a.arma.rango) else [1]
                if d_a in r_a:
                    aliados_backup.append(a.stats)

    # 4. Distancia y terrenos
    dist = abs(f_atk.x - f_def.x) + abs(f_atk.y - f_def.y)
    r_arma = f_atk.arma.rango if (f_atk.arma and f_atk.arma.rango) else [1]
    dist_combate = dist if dist in r_arma else r_arma[0]

    t_atk = _mapa.grid[f_atk.x][f_atk.y]
    t_def = _mapa.grid[f_def.x][f_def.y]

    casillas_ocupadas = {(f.x, f.y) for f in tablero.fichas.values() if f.viva and f.nombre not in (f_atk.nombre, f_def.nombre)}

    combate = CalculadoraEngage.simular_combate(
        atacante=f_atk.stats,
        defensor=f_def.stats,
        arma_atk=f_atk.arma,
        arma_def=f_def.arma,
        terreno_atk=Terreno(avo=t_atk.avo, dfn=t_atk.dfn,
            curacion_turno=getattr(t_atk, 'curacion_turno', 0),
            es_antirruptura=getattr(t_atk, 'es_antirruptura', False)),
        terreno_def=Terreno(avo=t_def.avo, dfn=t_def.dfn,
            curacion_turno=getattr(t_def, 'curacion_turno', 0),
            es_antirruptura=getattr(t_def, 'es_antirruptura', False)),
        distancia=dist_combate,
        aliados_apoyo_backup=aliados_backup,
        pos_atk=(f_atk.x, f_atk.y),
        pos_def=(f_def.x, f_def.y),
        mapa=_mapa,
        casillas_ocupadas=casillas_ocupadas,
        defensor_en_ruptura=(getattr(f_def, 'cargas_ruptura', 0) > 0),
    )

    res = combate["resultado"]
    hp_def_final = res["hp_defensor_final"]
    hp_atk_final = res["hp_atacante_final"]

    # Aplicar HP resultante en el estado mutable del tablero
    tablero.modificar_hp(nombre_def, hp_def_final)
    tablero.modificar_hp(nombre_atk, hp_atk_final)

    # Efecto Smash: empuje físico de 1 casilla o ruptura si choca contra obstáculo
    smash_res = res.get("smash", {})
    if smash_res.get("empujado") and smash_res.get("nueva_pos") and hp_def_final > 0:
        nueva_x, nueva_y = smash_res["nueva_pos"]
        tablero.mover_unidad(nombre_def, nueva_x, nueva_y)

    # Gestión canónica de Ruptura (Break) en FE Engage:
    # 1. Si en este combate sufre ruptura (por ventaja de armas o choque contra obstáculo):
    #    f_def.cargas_ruptura = 1 (no podrá contraatacar en el siguiente combate en que sea atacado).
    # 2. Si ya estaba en ruptura previa y sobrevivió a este combate sin nueva ruptura:
    #    consume la carga de ruptura (f_def.cargas_ruptura = max(0, f_def.cargas_ruptura - 1)),
    #    de modo que en un 3er combate ya podrá contraatacar con normalidad.
    if hp_def_final > 0:
        if res.get("aplica_ruptura") or smash_res.get("rompio_por_choque"):
            f_def.cargas_ruptura = 1
        elif getattr(f_def, 'cargas_ruptura', 0) > 0:
            f_def.cargas_ruptura = max(0, f_def.cargas_ruptura - 1)

    # Marcar atacante como que ha actuado este turno si es aliado
    if f_atk.es_aliado:
        f_atk.ha_actuado = True

    # Medidor de Emblema (si aliado combate)
    if f_atk.es_aliado and f_atk.energia_emblema < f_atk.max_energia_emblema and not f_atk.en_fusion:
        ganancia = 1
        if hp_def_final <= 0:
            ganancia += 1
        f_atk.energia_emblema = min(f_atk.max_energia_emblema, f_atk.energia_emblema + ganancia)

    return jsonify({
        "ok": True,
        "combate": combate,
        "atacante": f_atk.como_dict(),
        "defensor": f_def.como_dict(),
        "fichas": [f.como_dict() for f in tablero.fichas.values()]
    })

@app.route("/api/unidad/ajustar_hp", methods=["POST"])
def ajustar_hp():
    """Modifica directamente el HP actual de una unidad."""
    data = request.get_json(force=True) or {}
    nombre = data.get("nombre")
    hp = data.get("hp_actual")
    if not nombre or hp is None:
        return jsonify({"error": "Faltan campos nombre y hp_actual"}), 400
    tablero.guardar_snapshot()
    ok = tablero.modificar_hp(nombre, int(hp))
    f = tablero.obtener_ficha(nombre)
    return jsonify({
        "ok": ok,
        "ficha": f.como_dict() if f else None,
        "fichas": [x.como_dict() for x in tablero.fichas.values()]
    })

@app.route("/api/unidad/ajustar_nivel", methods=["POST"])
def ajustar_nivel():
    """Recalcula las estadísticas de una unidad según un nuevo nivel."""
    data = request.get_json(force=True) or {}
    nombre = data.get("nombre")
    nuevo_nivel = int(data.get("nivel", 1))
    if not nombre:
        return jsonify({"error": "Falta campo nombre"}), 400
    f = tablero.obtener_ficha(nombre)
    if not f:
        return jsonify({"error": "Unidad no encontrada"}), 404
    tablero.guardar_snapshot()
    f_dict = f.como_dict()
    f_dict["nivel"] = nuevo_nivel
    nueva_ficha = resolver_unidad_con_catalogo(f_dict)
    tablero.registrar_unidad(nueva_ficha)
    return jsonify({
        "ok": True,
        "ficha": nueva_ficha.como_dict(),
        "fichas": [x.como_dict() for x in tablero.fichas.values()]
    })

@app.route("/api/unidad/resolver_preview", methods=["POST"])
def resolver_unidad_preview():
    """
    Recibe nombre, clase (opcional), nivel (opcional), es_aliado, etc. y devuelve
    las estadísticas exactas resueltas del catálogo junto con clase_default, nivel_base y stats.
    """
    data = request.get_json(force=True) or {}
    nombre = data.get("nombre", "").strip()
    if not nombre:
        return jsonify({"error": "Falta nombre"}), 400

    # Buscar si existe el personaje en el catálogo para rellenar clase_default y nivel_base
    p_info = None
    n_norm = normalizar_texto(nombre)
    for cpid, cperson in _catalogo.get("personajes", {}).items():
        if normalizar_texto(cperson.get("nombre", "")) == n_norm or normalizar_texto(cpid) == n_norm:
            p_info = cperson
            break

    clase_nombre = data.get("clase_nombre", "").strip()
    if not clase_nombre and p_info:
        clase_nombre = p_info.get("clase_default", "")

    nivel_raw = data.get("nivel")
    if nivel_raw is None or str(nivel_raw).strip() == "" or str(nivel_raw) == "0":
        nivel = p_info.get("nivel_base", 1) if p_info else 10
    else:
        nivel = max(1, int(nivel_raw))

    payload = dict(data)
    payload["nombre"] = p_info.get("nombre", nombre) if p_info else nombre
    payload["clase_nombre"] = clase_nombre
    payload["nivel"] = nivel

    ficha = resolver_unidad_con_catalogo(payload)
    f_dict = ficha.como_dict()

    return jsonify({
        "ok": True,
        "nombre": ficha.nombre,
        "clase_nombre": ficha.clase_nombre,
        "nivel": ficha.nivel,
        "hp_max": ficha.hp_max,
        "hp_actual": ficha.hp_actual,
        "mov": ficha.mov,
        "stats": f_dict.get("stats", {}),
        "es_aliado": ficha.es_aliado,
        "arma_nombre": ficha.arma.nombre if ficha.arma else "",
        "ficha": f_dict
    })


# =============================================================================
# API — Turnos
# =============================================================================

@app.route("/api/turno/inicio_fase_enemigo", methods=["POST"])
def iniciar_fase_enemigo():
    """Marca que el jugador está arrastrando fichas del turno enemigo."""
    tablero.iniciar_fase_enemigo()
    return jsonify({"ok": True, "fase": tablero.fase, "turno": tablero.turno_actual, "fichas": [f.como_dict() for f in tablero.fichas.values()]})

@app.route("/api/turno/fin", methods=["POST"])
def fin_turno():
    """
    El jugador ha terminado de actualizar las posiciones enemigas.
    Avanza al siguiente turno y vuelve a la fase del jugador, reactivando aliados.
    """
    tablero.avanzar_turno()
    return jsonify({"ok": True, "fase": tablero.fase, "turno": tablero.turno_actual, "fichas": [f.como_dict() for f in tablero.fichas.values()]})


# =============================================================================
# API — Análisis (el botón [Analizar])
# =============================================================================

@app.route("/api/analizar", methods=["POST"])
def analizar():
    """
    Análisis táctico completo por turno.
    Para cada aliado × enemigo alcanzable:
      - Evalúa TODAS las armas del inventario (incluyendo armas de Engage si está en fusión).
      - Selecciona la MEJOR opción (kill seguro > mayor daño > menor riesgo).
      - Calcula la casilla óptima de ataque pos_sugerida: [x, y].
      - Genera recomendación accionable: qué mover, adónde, con qué arma y resultado esperado.
    También evalúa amenazas enemigas inminentes sobre los aliados.
    """
    data = request.get_json(force=True) or {}
    perfil = data.get("perfil", "seguro")
    cronogema = data.get("cronogema_usada", False)

    from motor_de_movimiento_y_amenaza import AnalizadorAmenaza, ContextoMapaEnemigo

    class _TerrenoAdapter:
        def __init__(self, t):
            self.caminable = t.caminable
            self.volable = t.volable
            self.coste = t.coste_mov

    grid_adapted = [
        [_TerrenoAdapter(_mapa.grid[x][y])
         for y in range(_mapa.alto)]
        for x in range(_mapa.ancho)
    ]
    analizador = AnalizadorAmenaza(grid_adapted, _mapa.ancho, _mapa.alto)

    aliados_activos = [a for a in tablero.obtener_aliados() if a.stats and a.arma and a.viva and not a.ha_actuado]
    enemigos_activos = [e for e in tablero.obtener_enemigos() if e.stats and e.arma and e.viva]

    amenazas_inminentes = []
    oportunidades_jugador = []
    distancias_frente = []

    # ── Helper: obtener todas las armas usables de un aliado ─────────────
    def _armas_aliado(aliado):
        armas = []
        for item in (aliado.inventario or []):
            if not isinstance(item, dict):
                continue
            tipo = item.get("tipo", "")
            if tipo in ("Bastón", "Objeto", "Accesorio"):
                continue
            a = _arma_desde_item(item)
            if a and a.mt > 0:
                es_engage = item.get("es_engage", False)
                nota = ""
                if "ragnarok" in a.nombre.lower() or "teleragna" in a.nombre.lower():
                    nota = "⚠️ TeleRagnarok: expone al aliado (solo si kill seguro)"
                elif es_engage:
                    nota = "⚡ Arma de Engage"
                armas.append((a, es_engage, nota))

        if not armas and aliado.arma:
            armas.append((aliado.arma, False, ""))

        return armas

    # ── 1. Evaluar amenazas enemigas sobre aliados ────────────────────────
    for enemigo in enemigos_activos:
        rango_max_enemigo = max(enemigo.arma.rango) if enemigo.arma.rango else 1
        alcance_enemigo = enemigo.mov + rango_max_enemigo

        for aliado in aliados_activos:
            dist = abs(aliado.x - enemigo.x) + abs(aliado.y - enemigo.y)
            distancias_frente.append((dist, enemigo, aliado))

            if dist <= alcance_enemigo + 1:
                try:
                    contexto = ContextoMapaEnemigo(
                        analizador=analizador,
                        ficha_enemigo=enemigo,
                        pos_jugador=(aliado.x, aliado.y),
                        ficha_jugador=aliado,
                    )
                    peor_caso = analizador.calcular_peor_caso_amenaza(enemigo, (aliado.x, aliado.y), aliado)

                    if peor_caso and peor_caso.get("puede_atacar", False):
                        dist_combate = peor_caso.get("distancia_ataque", 1)
                        t_def = _mapa.grid[aliado.x][aliado.y]
                        t_atk = _mapa.grid[enemigo.x][enemigo.y]

                        veredicto = CalculadoraEngage.evaluar_riesgo(
                            atacante=enemigo.stats,
                            defensor=aliado.stats,
                            arma_atk=enemigo.arma,
                            arma_def=aliado.arma,
                            terreno_def=Terreno(avo=t_def.avo, dfn=t_def.dfn,
                                curacion_turno=getattr(t_def, 'curacion_turno', 0),
                                es_antirruptura=getattr(t_def, 'es_antirruptura', False),
                                es_recarga_emblema=getattr(t_def, 'es_recarga_emblema', False)),
                            terreno_atk=Terreno(avo=t_atk.avo, dfn=t_atk.dfn,
                                curacion_turno=getattr(t_atk, 'curacion_turno', 0),
                                es_antirruptura=getattr(t_atk, 'es_antirruptura', False),
                                es_recarga_emblema=getattr(t_atk, 'es_recarga_emblema', False)),
                            distancia=dist_combate,
                            perfil=perfil,
                            cronogema_usada=cronogema,
                            contexto_mapa=contexto,
                            defensor_en_ruptura=(getattr(aliado, 'cargas_ruptura', 0) > 0),
                        )

                        mult_eff, desc_eff = CalculadoraEngage.calcular_efectividad(enemigo.arma, aliado.stats)
                        eff_tag = f" [✨ {desc_eff}]" if desc_eff else ""
                        if enemigo.arma.es_magica and aliado.stats.tipo_movimiento == 'acorazado':
                            eff_tag += " [✨ Magia penetra Armadura]"

                        verd = veredicto["veredicto"]
                        daño_e = verd.get("combate", veredicto.get("combate", {}))
                        combate_e = veredicto.get("combate", {})
                        atk_e = combate_e.get("atacante", {})
                        hp_aliado_tras = combate_e.get("resultado", {}).get("hp_defensor_final", aliado.stats.hp)

                        rec_texto = (
                            f"⚠️ AMENAZA: {enemigo.nombre} → {aliado.nombre}{eff_tag} | "
                            f"Daño: {atk_e.get('daño_total_ronda', '?')} ({atk_e.get('golpes_en_ronda','?')}x{atk_e.get('daño_por_golpe','?')}) | "
                            f"Hit: {atk_e.get('precision','?')}% | "
                            f"{aliado.nombre} quedaría en {hp_aliado_tras}/{aliado.stats.hp} HP. "
                        )
                        if verd.get("kill_seguro") or hp_aliado_tras <= 0:
                            rec_texto += f"💀 LETAL — mueve a {aliado.nombre} fuera de alcance o interpón otra unidad."
                        elif hp_aliado_tras <= aliado.stats.hp * 0.3:
                            rec_texto += f"🔴 CRÍTICO — {aliado.nombre} quedaría muy débil. Considera retroceder o usar Rescatar."

                        amenazas_inminentes.append({
                            "tipo_analisis": "amenaza_enemiga",
                            "aliado": aliado.nombre,
                            "enemigo": enemigo.nombre,
                            "distancia_combate": dist_combate,
                            "veredicto": verd,
                            "recomendacion": rec_texto,
                        })
                except Exception:
                    pass

    # ── 2. Evaluar oportunidades de ataque del jugador (multi-arma) ───────
    for aliado in aliados_activos:
        todas_armas = _armas_aliado(aliado)

        # Para cada enemigo alcanzable con cualquier arma del inventario
        for enemigo in enemigos_activos:
            dist = abs(aliado.x - enemigo.x) + abs(aliado.y - enemigo.y)

            mejor_veredicto = None
            mejor_arma = None
            mejor_nota = ""
            mejor_score = -1  # kill_seguro=3, kill_probable=2, daño_alto=1, daño_cero=-1

            for (arma_candidata, es_engage, nota_arma) in todas_armas:
                rango_max = max(arma_candidata.rango) if arma_candidata.rango else 1
                alcance = aliado.mov + rango_max
                if dist > alcance:
                    continue  # Fuera de alcance con esta arma

                # Distancia de combate óptima para esta arma
                dist_combate = min(
                    (d for d in arma_candidata.rango if d <= dist),
                    default=None
                )
                if dist_combate is None:
                    continue

                # TeleRagnarok: solo si kill seguro (demasiado riesgo)
                is_tele = "ragnarok" in arma_candidata.nombre.lower()

                try:
                    t_def = _mapa.grid[enemigo.x][enemigo.y]
                    t_atk = _mapa.grid[aliado.x][aliado.y]

                    v = CalculadoraEngage.evaluar_riesgo(
                        atacante=aliado.stats,
                        defensor=enemigo.stats,
                        arma_atk=arma_candidata,
                        arma_def=enemigo.arma,
                        terreno_def=Terreno(avo=t_def.avo, dfn=t_def.dfn,
                            curacion_turno=getattr(t_def, 'curacion_turno', 0),
                            es_antirruptura=getattr(t_def, 'es_antirruptura', False),
                            es_recarga_emblema=getattr(t_def, 'es_recarga_emblema', False)),
                        terreno_atk=Terreno(avo=t_atk.avo, dfn=t_atk.dfn,
                            curacion_turno=getattr(t_atk, 'curacion_turno', 0),
                            es_antirruptura=getattr(t_atk, 'es_antirruptura', False),
                            es_recarga_emblema=getattr(t_atk, 'es_recarga_emblema', False)),
                        distancia=dist_combate,
                        perfil=perfil,
                        cronogema_usada=cronogema,
                        defensor_en_ruptura=(getattr(enemigo, 'cargas_ruptura', 0) > 0),
                    )

                    verd = v["veredicto"]
                    combate_info = v.get("combate", {})
                    atk_info = combate_info.get("atacante", {})
                    daño_total = atk_info.get("daño_total_ronda", 0)

                    # Score para elegir la mejor arma:
                    if verd.get("kill_seguro"):
                        score = 300 + daño_total
                    elif verd.get("kill_probable"):
                        score = 200 + daño_total
                    elif verd.get("kill_con_critico"):
                        score = 100 + daño_total
                    elif daño_total == 0:
                        score = -1
                    else:
                        score = daño_total

                    # TeleRagnarok: reducir prioridad si no es kill
                    if is_tele and not verd.get("kill_seguro"):
                        score -= 150

                    # No preferir armas que nos dejan con riesgo crítico
                    if verd.get("nivel_riesgo") == "critico" and not verd.get("kill_seguro"):
                        score -= 100

                    if score > mejor_score:
                        mejor_score = score
                        mejor_veredicto = v
                        mejor_arma = arma_candidata
                        mejor_nota = nota_arma

                except Exception:
                    continue

            if mejor_veredicto is None or mejor_score < 0:
                continue  # No hay ataque viable

            # ── Generar recomendación accionable ──────────────────────────
            verd = mejor_veredicto["veredicto"]
            combate_final = mejor_veredicto.get("combate", {})
            atk_f = combate_final.get("atacante", {})
            res_f = combate_final.get("resultado", {})

            golpes = atk_f.get("golpes_en_ronda", 1)
            dpp = atk_f.get("daño_por_golpe", 0)
            dtotal = atk_f.get("daño_total_ronda", 0)
            precision = atk_f.get("precision", 0)
            hp_enemigo_ini = enemigo.stats.hp
            hp_enemigo_tras = res_f.get("hp_defensor_final", hp_enemigo_ini)
            follow_up = atk_f.get("tiene_follow_up", False)
            ruptura = res_f.get("aplica_ruptura", False)

            # Efectividad
            mult_eff, desc_eff = CalculadoraEngage.calcular_efectividad(mejor_arma, enemigo.stats)
            eff_tag = f" [✨ {desc_eff}]" if desc_eff else ""
            if mejor_arma.es_magica and enemigo.stats.tipo_movimiento == 'acorazado':
                eff_tag += " [✨ Magia penetra Armadura]"

            # Resultado principal
            if verd.get("kill_seguro"):
                resultado_tag = f"✅ KILL SEGURO ({precision}% hit)"
            elif verd.get("kill_probable"):
                resultado_tag = f"🎯 Kill probable ({precision}% hit)"
            elif verd.get("kill_con_critico"):
                resultado_tag = f"⚡ Solo mata con crítico ({atk_f.get('prob_critico',0)}%)"
            else:
                resultado_tag = f"→ {enemigo.nombre} queda en {hp_enemigo_tras}/{hp_enemigo_ini} HP"

            # Datos del golpe con desglose matemático exacto
            tiene_ds = atk_f.get("tiene_divine_speed", False)
            if follow_up and tiene_ds:
                dmg_ds = max(1, math.floor(dpp * 0.50))
                golpe_txt = f"2x{dpp} + {dmg_ds} (Velocidad Divina) = {dpp * 2 + dmg_ds} dmg"
            elif follow_up:
                golpe_txt = f"2x{dpp} = {dpp * 2} dmg (Follow-up)"
            elif tiene_ds:
                dmg_ds = max(1, math.floor(dpp * 0.50))
                golpe_txt = f"1x{dpp} + {dmg_ds} (Velocidad Divina) = {dpp + dmg_ds} dmg"
            else:
                golpe_txt = f"1x{dpp} = {dpp} dmg"

            # Riesgo para el aliado
            nivel_riesgo = verd.get("nivel_riesgo", "bajo")
            riesgo_txt = ""
            if nivel_riesgo == "critico":
                riesgo_txt = f" | 🔴 RIESGO CRÍTICO"
            elif nivel_riesgo == "alto":
                riesgo_txt = f" | 🟠 Riesgo alto"
            elif nivel_riesgo == "moderado":
                riesgo_txt = f" | 🟡 Riesgo moderado"

            # Ruptura, engage y pasivas
            bonus_txt = ""
            if ruptura:
                bonus_txt += " | 💥 Aplica Ruptura"
            if combate_info.get("resultado", {}).get("chain_attacks_daño", 0) > 0:
                cdmg = combate_info["resultado"]["chain_attacks_daño"]
                bonus_txt += f" | ⚔️ Chain Attack (+{cdmg} dmg)"
            if combate_info.get("atacante", {}).get("recoil_hp", 0) > 0:
                bonus_txt += " | 🩸 Resonancia (-1 HP)"
            if combate_info.get("atacante", {}).get("puede_canter", False):
                bonus_txt += " | 🏃 Canter (mueve 2 tras atacar)"
            if mejor_nota:
                bonus_txt += f" | {mejor_nota}"

            pos_sug = encontrar_pos_ataque_optima(aliado, enemigo, mejor_arma)
            pos_txt = f"📍 Mover a ({pos_sug[0]},{pos_sug[1]}) · " if (pos_sug[0] != aliado.x or pos_sug[1] != aliado.y) else "📍 En rango directo · "

            # Recomendación final
            rec_texto = (
                f"🎯 {aliado.nombre} → usa {mejor_arma.nombre}{eff_tag} contra {enemigo.nombre} | "
                f"{pos_txt}{golpe_txt} | Hit {precision}% | {resultado_tag}{riesgo_txt}{bonus_txt}"
            )

            oportunidades_jugador.append({
                "tipo_analisis": "oportunidad_jugador",
                "aliado": aliado.nombre,
                "enemigo": enemigo.nombre,
                "distancia_combate": dist,
                "arma_recomendada": mejor_arma.nombre,
                "pos_sugerida": pos_sug,
                "veredicto": verd,
                "recomendacion": rec_texto,
            })

    # Ordenar oportunidades: kill seguro primero, luego por daño
    def _score_oportunidad(r):
        v = r.get("veredicto", {})
        if v.get("kill_seguro"):
            return 300
        if v.get("kill_probable"):
            return 200
        if v.get("kill_con_critico"):
            return 100
        return 0

    oportunidades_jugador.sort(key=_score_oportunidad, reverse=True)

    # Combinar: amenazas primero, luego oportunidades
    resultados = amenazas_inminentes + oportunidades_jugador

    # ── 3. Fallback: zona segura / avance recomendado ─────────────────────
    if not resultados and distancias_frente:
        distancias_frente.sort(key=lambda x: x[0])
        dist_min, e_cercano, a_cercano = distancias_frente[0]
        alcance_e = e_cercano.mov + (max(e_cercano.arma.rango) if e_cercano.arma else 1)
        col_segura = e_cercano.x - alcance_e - 1

        resultados.append({
            "tipo_analisis": "vanguardia_segura",
            "aliado": a_cercano.nombre,
            "enemigo": e_cercano.nombre,
            "distancia_combate": dist_min,
            "veredicto": {
                "nivel_riesgo": "bajo",
                "motivos": [
                    f"Frente seguro: ningún enemigo alcanza este turno (distancia mínima: {dist_min} casillas).",
                    f"Enemigo más próximo: {e_cercano.nombre} en ({e_cercano.x}, {e_cercano.y}), alcance {alcance_e} casillas.",
                ]
            },
            "recomendacion": (
                f"🛡️ ZONA SEGURA: Puedes avanzar. No te expongas más allá de la columna X={max(0, col_segura)} "
                f"para no entrar en rango de {e_cercano.nombre} este turno."
            )
        })

    return jsonify({"turno": tablero.turno_actual, "total_analizados": len(resultados), "resultados": resultados})


# =============================================================================
# API — Reset y Limpieza
# =============================================================================

@app.route("/api/tablero/limpiar", methods=["POST"])
def limpiar_tablero():
    """Elimina absolutamente todas las fichas del tablero."""
    tablero.guardar_snapshot()
    tablero.limpiar()
    return jsonify({
        "ok": True,
        "mensaje": "Tablero limpio: todas las fichas eliminadas.",
        "fichas": []
    })

@app.route("/api/reset", methods=["POST"])
def reset():
    """
    Reinicia el tablero al estado inicial (Turno 1, Fase Jugador, Spawns del capitulo activo).
    - Mapa Datamine: recarga dispos desde el XML del capitulo.
    - Mapa Tiled: limpia el tablero y carga los spawns de la capa de objetos del mapa.
    """
    tablero.guardar_snapshot()
    cap_id = getattr(_mapa, "dispos_id", None)
    if cap_id:
        # Mapa Datamine: despliegue normal desde XML de dispos
        resultado = _desplegar_capitulo(cap_id, "Extremo")
        nombre_cap = getattr(_mapa, "nombre_en", cap_id)
        fichas_result = resultado["fichas"]
    else:
        # Mapa Tiled (o cualquier mapa sin dispos_id)
        tablero.fichas.clear()
        tablero.turno_actual = 1
        tablero.fase = "jugador"
        num = tablero.cargar_spawns_desde_mapa()
        nombre_cap = getattr(_mapa, "filepath", "Mapa Tiled").split("/")[-1].split("\\")[-1]
        fichas_result = [f.como_dict() for f in tablero.fichas.values()]
    return jsonify({
        "ok": True,
        "mensaje": f"Tablero reiniciado al Turno 1 con {nombre_cap} ({len(tablero.fichas)} unidades).",
        "fase": tablero.fase,
        "turno": tablero.turno_actual,
        "fichas": fichas_result
    })


# =============================================================================
# Entrada
# =============================================================================

if __name__ == "__main__":
    print("=== FE Engage Tactical Assistant ===")
    capitulo_info = getattr(_mapa, 'nombre_en', None) or getattr(_mapa, 'cid', 'Tiled')
    print(f"Mapa cargado: {_mapa.ancho}x{_mapa.alto} | {capitulo_info}")
    print("Servidor en http://localhost:5000")
    app.run(debug=True, port=5000)
