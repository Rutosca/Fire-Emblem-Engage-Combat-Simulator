"""
Módulo de carga y resolución de catálogos oficiales de Fire Emblem Engage.
Contiene:
- Búsqueda en catálogo y datos canónicos.
- Diccionario oficial de grabados de emblemas y refinamientos.
- Parser de armas con forja (+1..+5) y grabado.
- Resolución determinista de unidades completas (bases + crecimientos por nivel + clase + emblema).
"""

import os
import re
import json
import math
import unicodedata
from motor_calculo import Unidad, Arma
from estado_tablero import FichaUnidad

# Rutas de catálogos oficiales
_dir_actual = os.path.dirname(__file__)
_ruta_catalogo_json = os.path.join(_dir_actual, "json", "catalogo_engage.json")
_ruta_catalogo = _ruta_catalogo_json if os.path.exists(_ruta_catalogo_json) else os.path.join(_dir_actual, "catalogo_engage.json")

_ruta_canonico_json = os.path.join(_dir_actual, "json", "datos_canonicos_engage.json")
_ruta_canonico = _ruta_canonico_json if os.path.exists(_ruta_canonico_json) else os.path.join(_dir_actual, "datos_canonicos_engage.json")

_catalogo = {}
_canonico = {}

def normalizar_texto(texto):
    """Elimina tildes y caracteres diacríticos para búsquedas insensibles a acentos."""
    if not texto:
        return ""
    return unicodedata.normalize('NFKD', str(texto)).encode('ASCII', 'ignore').decode('utf-8').lower()

def round_half_up(val):
    """Redondeo aritmético estándar (Round Half Up) usado en el motor de FE Engage."""
    return math.floor(float(val) + 0.5)

def cargar_catalogo():
    """Carga catalogo_engage.json y datos_canonicos_engage.json in-place."""
    global _catalogo, _canonico
    if os.path.exists(_ruta_canonico):
        try:
            with open(_ruta_canonico, "r", encoding="utf-8") as f:
                _canonico.clear()
                _canonico.update(json.load(f))
            print(f"[OK] Datos Canónicos cargados: {len(_canonico.get('terrenos', {}))} terrenos, {len(_canonico.get('armas', {}))} armas, {len(_canonico.get('habilidades', {}))} habilidades, {len(_canonico.get('clases', {}))} clases")
        except Exception as e:
            print(f"Aviso al cargar datos_canonicos_engage.json: {e}")

    if os.path.exists(_ruta_catalogo):
        try:
            with open(_ruta_catalogo, "r", encoding="utf-8") as f:
                _catalogo.clear()
                _catalogo.update(json.load(f))
            print(f"[OK] Catálogo Engage cargado: {len(_catalogo.get('armas', {}))} armas, {len(_catalogo.get('clases', {}))} clases, {len(_catalogo.get('habilidades', {}))} habilidades, {len(_catalogo.get('emblemas', {}))} emblemas")
        except Exception as e:
            print(f"Aviso al cargar catalogo_engage.json: {e}")

# Carga inicial al importar el módulo
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

def _arma_desde_item(item_dict):
    """Convierte un dict de inventario en una instancia de Arma."""
    if not item_dict:
        return None
    if isinstance(item_dict, str):
        p = parsear_arma_string(item_dict)
        if p:
            item_dict = p
        else:
            item_dict = {"nombre": item_dict}

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

def resolver_unidad_con_catalogo(data, tablero=None):
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

    # Preservar el estado de acción del turno (ha_actuado) y ruptura si la unidad ya está en el tablero
    unidad_previa = None
    if tablero is None:
        try:
            import app as _app_mod
            tablero = getattr(_app_mod, 'tablero', None)
        except Exception:
            tablero = None

    if tablero and hasattr(tablero, 'fichas'):
        unidad_previa = tablero.fichas.get(nombre)

    if "ha_actuado" in data and data["ha_actuado"] is not None:
        ha_actuado = bool(data["ha_actuado"])
    elif unidad_previa is not None:
        ha_actuado = bool(unidad_previa.ha_actuado)
    else:
        ha_actuado = False

    cargas_ruptura = int(data.get("cargas_ruptura", unidad_previa.cargas_ruptura if unidad_previa else 0))

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
            calc_hp  = c_bases.get("hp", 0)  + p_bases.get("hp", 20)  + round_half_up((c_growths.get("hp", 0)  + p_growths.get("hp", 45)) * lvl_diff / 100.0)
            calc_str = c_bases.get("str", 0) + p_bases.get("str", 6)  + round_half_up((c_growths.get("str", 0) + p_growths.get("str", 30)) * lvl_diff / 100.0)
            calc_mag = c_bases.get("mag", 0) + p_bases.get("mag", 0)  + round_half_up((c_growths.get("mag", 0) + p_growths.get("mag", 15)) * lvl_diff / 100.0)
            calc_dex = c_bases.get("dex", 0) + p_bases.get("dex", 5)  + round_half_up((c_growths.get("dex", 0) + p_growths.get("dex", 35)) * lvl_diff / 100.0)
            calc_spd = c_bases.get("spd", 0) + p_bases.get("spd", 6)  + round_half_up((c_growths.get("spd", 0) + p_growths.get("spd", 35)) * lvl_diff / 100.0)
            calc_def = c_bases.get("def", 0) + p_bases.get("def", 5)  + round_half_up((c_growths.get("def", 0) + p_growths.get("def", 25)) * lvl_diff / 100.0)
            calc_res = c_bases.get("res", 0) + p_bases.get("res", 2)  + round_half_up((c_growths.get("res", 0) + p_growths.get("res", 20)) * lvl_diff / 100.0)
            calc_lck = c_bases.get("lck", 0) + p_bases.get("lck", 4)  + round_half_up((c_growths.get("lck", 0) + p_growths.get("lck", 25)) * lvl_diff / 100.0)
            calc_bld = c_bases.get("bld", 0) + p_bases.get("bld", 5)  + round_half_up((c_growths.get("bld", 0) + p_growths.get("bld", 5))  * lvl_diff / 100.0)
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

        # Si es enemigo y tiene crecimientos personales únicos (ej. jefes con nombre propio como Hortensia),
        # sus crecimientos en el datamine ya son completos (no se suman a los crecimientos genéricos de clase)
        if not es_aliado and p_growths and any(v > 0 for v in p_growths.values()):
            final_growths = p_growths
        else:
            final_growths = {stat: c_growths.get(stat, 0) + (p_growths.get(stat, 0) if es_aliado else 0)
                             for stat in ["hp", "str", "mag", "dex", "spd", "def", "res", "lck", "bld"]}

        lvl_ups = max(0, nivel - 1 + auto_grow_extra)
        lvl_factor = lvl_ups / 100.0

        calc_hp  = c_bases.get("hp", 20)  + p_offset_diff.get("hp",  0) + round_half_up(final_growths.get("hp",  45) * lvl_factor)
        calc_str = c_bases.get("str", 6)  + p_offset_diff.get("str", 0) + round_half_up(final_growths.get("str", 30) * lvl_factor)
        calc_mag = c_bases.get("mag", 0)  + p_offset_diff.get("mag", 0) + round_half_up(final_growths.get("mag", 15) * lvl_factor)
        calc_dex = c_bases.get("dex", 5)  + p_offset_diff.get("dex", 0) + round_half_up(final_growths.get("dex", 35) * lvl_factor)
        calc_spd = c_bases.get("spd", 6)  + p_offset_diff.get("spd", 0) + round_half_up(final_growths.get("spd", 35) * lvl_factor)
        calc_def = c_bases.get("def", 5)  + p_offset_diff.get("def", 0) + round_half_up(final_growths.get("def", 25) * lvl_factor)
        calc_res = c_bases.get("res", 2)  + p_offset_diff.get("res", 0) + round_half_up(final_growths.get("res", 20) * lvl_factor)
        calc_lck = c_bases.get("lck", 4)  + p_offset_diff.get("lck", 0) + round_half_up(final_growths.get("lck", 25) * lvl_factor)
        calc_bld = c_bases.get("bld", 5)  + p_offset_diff.get("bld", 0) + round_half_up(final_growths.get("bld",  5) * lvl_factor)

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

    tipo_mov_c = str(clase_info.get("tipo_movimiento", "")).lower() if clase_info else ""
    c_nombre_c = str(clase_info.get("nombre", "")).lower() if clase_info else ""
    c_jid_c = str(clase_id).lower()
    estilo_str_c = str(style).lower()

    es_volador = (
        estilo_str_c in ("flier", "volador", "飛行スタイル", "飛行", "flying")
        or tipo_mov_c in ("volador", "flier", "flying")
        or any(w in c_nombre_c for w in ["flier", "pegas", "wyvern", "griffin", "grifo", "wing tamer", "sleipnir", "lindwurm", "melusine"])
        or any(w in c_jid_c for w in ["ペガサス", "ドラゴンナイト", "グリフォン", "スレイプニル", "リンドブルム", "メリュジーヌ", "flier", "wyvern", "pegas"])
        or bool(data.get("es_volador", False))
    )

    # tipo_movimiento y estilo_combate vienen de la clase del personaje
    tipo_movimiento = "volador" if es_volador else (clase_info.get("tipo_movimiento", "infantería") if clase_info else data.get("tipo_movimiento", "infantería"))
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

    # Enriquecer habilidades personales y de clase desde datos canónicos
    if _canonico:
        p_canon = _canonico.get("personajes", {}).get(pid) or _canonico.get("personajes", {}).get(normalizar_texto(nombre))
        if p_canon:
            for sid in p_canon.get("common_sids", []):
                if sid not in habs_lista:
                    habs_lista.append(sid)
                s_nom = _canonico.get("habilidades", {}).get(sid, {}).get("nombre")
                if s_nom and s_nom not in habs_lista:
                    habs_lista.append(s_nom)
            if dificultad in ("difícil", "dificil", "hard", "extremo", "lunatic", "maddening"):
                for sid in p_canon.get("hard_sids", []):
                    if sid not in habs_lista:
                        habs_lista.append(sid)
                    s_nom = _canonico.get("habilidades", {}).get(sid, {}).get("nombre")
                    if s_nom and s_nom not in habs_lista:
                        habs_lista.append(s_nom)
            if dificultad in ("extremo", "lunatic", "maddening"):
                for sid in p_canon.get("lunatic_sids", []):
                    if sid not in habs_lista:
                        habs_lista.append(sid)
                    s_nom = _canonico.get("habilidades", {}).get(sid, {}).get("nombre")
                    if s_nom and s_nom not in habs_lista:
                        habs_lista.append(s_nom)

        c_canon = _canonico.get("clases", {}).get(clase_id) or _canonico.get("clases", {}).get(normalizar_texto(clase_info.get("nombre", "") if clase_info else ""))
        if c_canon:
            if not estilo_combate or estilo_combate in ("Infantería", "infantería", "None", ""):
                estilo_combate = c_canon.get("estilo_combate", estilo_combate)
            for sid in c_canon.get("skills", []):
                if sid not in habs_lista:
                    habs_lista.append(sid)
            if dificultad in ("extremo", "lunatic", "maddening") and c_canon.get("lunatic_skill"):
                ls = c_canon.get("lunatic_skill")
                if ls not in habs_lista:
                    habs_lista.append(ls)

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
    val_veneno = int(data.get("nivel_veneno", getattr(unidad_previa, 'nivel_veneno', 0) if unidad_previa else 0))
    val_lider_3h = data.get("lider_tres_casas") or (getattr(unidad_previa, 'lider_tres_casas', None) if unidad_previa else "Dimitri") or "Dimitri"
    setattr(stats_obj, 'nivel_veneno', val_veneno)
    setattr(stats_obj, 'lider_tres_casas', val_lider_3h)

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
        hp_stock=int(data.get("hp_stock", 0)),
        ha_actuado=ha_actuado,
        cargas_ruptura=cargas_ruptura,
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
        nivel_veneno=val_veneno,
        lider_tres_casas=val_lider_3h,
    )
    return ficha
