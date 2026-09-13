"""
compilar_catalogo.py — FE Engage Tactical Assistant
Parsea los XMLs oficiales del Datamining (FE17-DOC-main) y genera catalogo_engage.json.
"""

import xml.etree.ElementTree as ET
import os
import json
import csv
import re

from constants import JAPANESE_FALLBACK_TERMS, TIPO_ARMA_KIND, MOVE_TYPE_MAP, SID_A_EFECTIVIDAD

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATAMINE_DIR = os.path.join(BASE_DIR, "FE17-DOC-main", "FE17-DOC-main", "fe_assets_gamedata")
TRANS_DIR = os.path.join(BASE_DIR, "FE17-DOC-main", "FE17-DOC-main", "translations")

USEN_DIR = os.path.join(BASE_DIR, "FE17-DOC-main", "FE17-DOC-main", "fe_assets_message", "us", "usen", "csv")




def to_int(val, default=0):
    if val is None:
        return default
    val_str = str(val).strip()
    if not val_str:
        return default
    try:
        return int(val_str)
    except ValueError:
        return default

# Ficheros fuente cuyo timestamp se comprueba para invalidar la caché
_CACHE_SOURCES = [USEN_DIR, TRANS_DIR]
_CACHE_FILE = os.path.join(BASE_DIR, "traducciones_cache.json")


def _cache_valida() -> bool:
    """Devuelve True si la caché existe y es más reciente que todas las fuentes."""
    if not os.path.exists(_CACHE_FILE):
        return False
    cache_mtime = os.path.getmtime(_CACHE_FILE)
    for src in _CACHE_SOURCES:
        if not os.path.exists(src):
            continue
        for root, _, files in os.walk(src):
            for f in files:
                if os.path.getmtime(os.path.join(root, f)) > cache_mtime:
                    return False
    return True


def cargar_traducciones():
    """Carga mapeo completo de identificadores a nombres oficiales en inglés.

    En la primera ejecución construye el diccionario leyendo todos los CSV y lo
    guarda en traducciones_cache.json.  En ejecuciones posteriores, si ninguno
    de los archivos fuente ha cambiado, carga directamente la caché (mucho más
    rápido).
    """
    # — Caché rápida -------------------------------------------------------
    if _cache_valida():
        print("[caché] Traducciones cargadas desde traducciones_cache.json")
        with open(_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    traducciones = {}

    # 1. Cargar todas las traducciones oficiales en inglés (fe_assets_message/us/usen/csv)
    if os.path.exists(USEN_DIR):
        for fname in os.listdir(USEN_DIR):
            if fname.endswith(".csv"):
                fpath = os.path.join(USEN_DIR, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    for row in reader:
                        if len(row) >= 2 and row[0]:
                            k = row[0].strip().lstrip("\ufeff")
                            v = row[1].strip()
                            traducciones[k] = v
                            for pfx in ["MIID_", "MJID_", "MPID_", "MSID_", "MGID_", "MID_"]:
                                if k.startswith(pfx):
                                    traducciones[k[len(pfx):]] = v

    # 2. Cargar traducciones desde translations/fee-translations.csv
    trans_file = os.path.join(TRANS_DIR, "fee-translations.csv")
    if os.path.exists(trans_file):
        with open(trans_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 3 and row[0] and row[2]:
                    en = row[0].strip()
                    jp = row[2].strip()
                    traducciones[jp] = en
                    traducciones[en] = en
                    for pfx in ["PID_", "JID_", "IID_", "SID_", "GID_", "MID_", "MSID_", "MJID_", "MIID_", "MPID_", "MGID_"]:
                        traducciones[f"{pfx}{jp}"] = en
                        traducciones[f"{pfx}{en}"] = en

    # 3. Cargar traducciones específicas de Item, Job, Person, Skill
    for fname in ["Item.csv", "Job.csv", "Person.csv", "Skill.csv"]:
        fpath = os.path.join(TRANS_DIR, fname)
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                for row in reader:
                    if len(row) >= 2 and row[0]:
                        key = row[0].strip().lstrip("\ufeff")
                        name_en = row[1].strip() if row[1] else key
                        jp = row[2].strip() if len(row) > 2 and row[2] else ""
                        traducciones[key] = name_en
                        traducciones[f"MID_{key}"] = name_en
                        traducciones[f"MID_JOB_{key}"] = name_en
                        traducciones[f"MID_ITEM_{key}"] = name_en
                        traducciones[f"MID_PERSON_{key}"] = name_en
                        traducciones[f"MID_SKILL_{key}"] = name_en
                        traducciones[f"MSID_{key}"] = name_en
                        traducciones[f"SID_{key}"] = name_en
                        traducciones[f"IID_{key}"] = name_en
                        traducciones[f"JID_{key}"] = name_en
                        traducciones[f"PID_{key}"] = name_en
                        if jp:
                            traducciones[jp] = name_en
                            traducciones[f"SID_{jp}"] = name_en
                            traducciones[f"IID_{jp}"] = name_en
                            traducciones[f"JID_{jp}"] = name_en
                            traducciones[f"PID_{jp}"] = name_en

    # 4. Añadir términos japoneses directos del fallback
    for jp_term, en_term in JAPANESE_FALLBACK_TERMS.items():
        traducciones[jp_term] = en_term
        for pfx in ["PID_", "JID_", "IID_", "SID_", "GID_", "MID_"]:
            traducciones[f"{pfx}{jp_term}"] = en_term

    # — Guardar caché para próximas ejecuciones ------------------------------
    with open(_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(traducciones, f, ensure_ascii=False)
    print(f"[caché] Traducciones compiladas y guardadas ({len(traducciones)} entradas)")

    return traducciones

def parsear_xml_generico(filepath):
    """Parsea un archivo XML del datamine y devuelve una lista de diccionarios de filas de todas las Sheets."""
    if not os.path.exists(filepath):
        print(f"Aviso: {filepath} no encontrado.")
        return []

    tree = ET.parse(filepath)
    root = tree.getroot()
    
    filas = []
    for sheet in root.findall("Sheet"):
        data_elem = sheet.find("Data")
        if data_elem is None:
            continue
        for row in data_elem.findall("Param"):
            d = {}
            for k, v in row.attrib.items():
                d[k] = v
            filas.append(d)

    return filas

# TIPO_ARMA_KIND importado de constants.py

def limpiar_nombre(ident, name_tag, trans):
    """Obtiene un nombre legible en inglés a partir del identificador de mensaje."""
    # 1. Intentar con name_tag directo
    if name_tag and name_tag in trans:
        return trans[name_tag]
    if ident in trans:
        return trans[ident]

    # 2. Desglosar prefijos
    raw_str = name_tag or ident
    for pfix in ["MIID_H_", "MIID_HE_", "MIID_", "MJID_", "MPID_", "MSID_", "MGID_", "MRID_", "MID_", "IID_", "JID_", "PID_", "SID_", "GID_", "RID_"]:
        if raw_str.startswith(pfix):
            raw_str = raw_str[len(pfix):]
            break

    if raw_str in trans:
        return trans[raw_str]

    # 3. Separar por guiones bajos y traducir componentes
    parts = []
    for p in raw_str.split("_"):
        t = trans.get(p, trans.get(f"MID_{p}", JAPANESE_FALLBACK_TERMS.get(p, p)))
        parts.append(t)
    res = " ".join(parts)

    # 4. Reemplazos finales de términos japoneses residuales
    for jp_k, en_v in JAPANESE_FALLBACK_TERMS.items():
        if jp_k in res:
            res = res.replace(jp_k, en_v)

    # 5. Limpieza de caracteres japoneses residuales en scripts internos
    jp_re = re.compile(r'[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]+')
    if jp_re.search(res):
        res = jp_re.sub('', res).strip()
        res = re.sub(r'\s+', ' ', res).strip()

    return res if res else ident.replace("SID_", "").replace("IID_", "").replace("PID_", "").replace("JID_", "")

def compilar():
    print("=== Iniciando compilación de catálogo FE Engage desde Datamine ===")
    trans = cargar_traducciones()
    print(f"Traducciones cargadas: {len(trans)}")

    # 1. Armas e Ítems
    items_raw = parsear_xml_generico(os.path.join(DATAMINE_DIR, "Item.xml"))
    armas = {}
    for it in items_raw:
        iid = it.get("Iid")
        if not iid or iid.startswith("IID_None"):
            continue

        name_tag = it.get("Name")
        if iid in armas and not name_tag:
            continue

        kind_code = str(it.get("Kind", "0"))
        tipo_str = TIPO_ARMA_KIND.get(kind_code, "Espada")
        nombre = limpiar_nombre(iid, name_tag, trans)
        
        # Atributos de combate
        mt = to_int(it.get("Power"))
        wt = to_int(it.get("Weight"))
        hit = to_int(it.get("Hit"))
        crit = to_int(it.get("Critical"))
        avo = to_int(it.get("Avoid"))
        ddg = to_int(it.get("Secure"))
        
        range_i = to_int(it.get("RangeI"), 1)
        range_o = to_int(it.get("RangeO"), 1)
        if range_i == range_o:
            rango = [range_i]
        else:
            rango = list(range(range_i, range_o + 1))

        # Magia / Física (WeaponAttr: 2 suele ser Mágica, o Flag con bit 65536 para Levin Sword, Flame Lance, Hurricane Axe, Radiant Bow)
        attr = it.get("WeaponAttr", "0")
        flag_val = to_int(it.get("Flag", 0))
        es_magica = (tipo_str == "Tomo" or str(attr) in ("2", "3") or bool(flag_val & 65536) or iid in ("IID_いかづちの剣", "IID_ほのおの槍", "IID_かぜの大斧", "IID_光の弓"))

        # Efectividades — vienen en EquipSids separadas por ;
        # Mapeamos los SIDs a tipos de movimiento legibles
        SID_A_EFECTIVIDAD = {
            "SID_飛行特効": "volador",
            "SID_鎧特効":   "acorazado",
            "SID_馬特効":   "caballería",
            "SID_竜特効":   "dragón",
            "SID_異形特効": "monstruo",
        }
        equip_sids_raw = it.get("EquipSids", "")
        es_smash = ("SID_スマッシュ" in equip_sids_raw or "smash" in equip_sids_raw.lower())
        efectividades = []
        for sid in equip_sids_raw.split(";"):
            sid = sid.strip()
            if sid in SID_A_EFECTIVIDAD:
                efectividades.append(SID_A_EFECTIVIDAD[sid])

        # Durabilidad / Usos máximos (Endurance)
        endurance_val = it.get("Endurance", "1")
        endurance_int = to_int(endurance_val, 1)
        usos_max = endurance_int if (1 < endurance_int < 255) else (1 if tipo_str == "Objeto" else None)

        # Mapeo de nombres en español comunes para consumibles
        ALIASES_ESPANOL = {
            "IID_傷薬": "Poción",
            "IID_特効薬": "Elixir",
            "IID_聖水": "Agua pura",
            "IID_毒消し": "Antídoto",
            "IID_たいまつ": "Antorcha",
        }
        if iid in ALIASES_ESPANOL:
            nombre = ALIASES_ESPANOL[iid]

        # Distinguir versiones de tutorial/prólogo o eventos especiales
        if iid.endswith("_M000"):
            nombre = f"{nombre} (Prólogo)"
        elif "_M0" in iid or "_敵" in iid:
            nombre = f"{nombre} (Evento)"

        armas[iid] = {
            "id": iid,
            "nombre": nombre,
            "tipo": tipo_str,
            "mt": mt,
            "wt": wt,
            "hit": hit,
            "crit": crit,
            "avo": avo,
            "ddg": ddg,
            "rango": rango,
            "es_magica": es_magica,
            "es_smash": es_smash,
            "precio": to_int(it.get("Price")),
            "usos_max": usos_max,
            "efectividades": efectividades,  # e.g. ["volador"], ["acorazado", "caballería"]
        }

    print(f"Armas e ítems procesados: {len(armas)}")

    # 2. Clases (Jobs)
    jobs_raw = parsear_xml_generico(os.path.join(DATAMINE_DIR, "Job.xml"))
    clases = {}
    for j in jobs_raw:
        jid = j.get("Jid")
        if not jid:
            continue

        name_tag = j.get("Name")
        if jid in clases and not name_tag:
            continue

        nombre = limpiar_nombre(jid, name_tag, trans)
        
        # Distinción de clases reales compartidas con el mismo nombre en la traducción
        CLASES_DISAMBIGUATION = {
            "JID_アヴニール下級": "Noble (Caballería)",
            "JID_フロラージュ下級": "Noble (Mística)",
            "JID_スュクセサール下級": "Lord (Diamant)",
            "JID_ティラユール下級": "Lord (Alcryst)",
            "JID_リンドブルム下級": "Wing Tamer (Ivy)",
            "JID_スレイプニル下級": "Wing Tamer (Hortensia)",
            "JID_ピッチフォーク下級": "Sentinel (Timerra)",
            "JID_クピードー下級": "Sentinel (Fogado)",
        }
        if jid in CLASES_DISAMBIGUATION:
            nombre = CLASES_DISAMBIGUATION[jid]

        style = j.get("StyleName", "None")
        mov = to_int(j.get("Base.Move"), 5)

        # Tipo de movimiento (MoveType del datamine)
        MOVE_TYPE_MAP = {
            "1": "infantería",
            "2": "caballería",
            "3": "volador",
            "4": "acorazado",
        }
        move_type_raw = j.get("MoveType", "1")
        tipo_movimiento = MOVE_TYPE_MAP.get(str(move_type_raw), "infantería")

        clases[jid] = {
            "id": jid,
            "nombre": nombre,
            "estilo_combate": style,
            "mov": mov,
            "tipo_movimiento": tipo_movimiento,
            "base_stats": {
                "hp": to_int(j.get("Base.Hp")),
                "str": to_int(j.get("Base.Str")),
                "mag": to_int(j.get("Base.Magic")),
                "dex": to_int(j.get("Base.Tech")),
                "spd": to_int(j.get("Base.Quick")),
                "def": to_int(j.get("Base.Def")),
                "res": to_int(j.get("Base.Mdef")),
                "lck": to_int(j.get("Base.Luck")),
                "bld": to_int(j.get("Base.Phys")),
            },
            "growths": {
                "hp": to_int(j.get("DiffGrow.Hp")) or to_int(j.get("GrowRatio.Hp")),
                "str": to_int(j.get("DiffGrow.Str")) or to_int(j.get("GrowRatio.Str")),
                "mag": to_int(j.get("DiffGrow.Magic")) or to_int(j.get("GrowRatio.Magic")),
                "dex": to_int(j.get("DiffGrow.Tech")) or to_int(j.get("GrowRatio.Tech")),
                "spd": to_int(j.get("DiffGrow.Quick")) or to_int(j.get("GrowRatio.Quick")),
                "def": to_int(j.get("DiffGrow.Def")) or to_int(j.get("GrowRatio.Def")),
                "res": to_int(j.get("DiffGrow.Mdef")) or to_int(j.get("GrowRatio.Mdef")),
                "lck": to_int(j.get("DiffGrow.Luck")) or to_int(j.get("GrowRatio.Luck")),
                "bld": to_int(j.get("DiffGrow.Phys")) or to_int(j.get("GrowRatio.Phys")),
            },
            "max_stats": {
                "hp": to_int(j.get("Limit.Hp")),
                "str": to_int(j.get("Limit.Str")),
                "mag": to_int(j.get("Limit.Magic")),
                "dex": to_int(j.get("Limit.Tech")),
                "spd": to_int(j.get("Limit.Quick")),
                "def": to_int(j.get("Limit.Def")),
                "res": to_int(j.get("Limit.Mdef")),
                "lck": to_int(j.get("Limit.Luck")),
                "bld": to_int(j.get("Limit.Phys")),
            },
            "enemy_growths": {
                "base": {
                    "hp": to_int(j.get("BaseGrow.Hp")),
                    "str": to_int(j.get("BaseGrow.Str")),
                    "mag": to_int(j.get("BaseGrow.Magic")),
                    "dex": to_int(j.get("BaseGrow.Tech")),
                    "spd": to_int(j.get("BaseGrow.Quick")),
                    "def": to_int(j.get("BaseGrow.Def")),
                    "res": to_int(j.get("BaseGrow.Mdef")),
                    "lck": to_int(j.get("BaseGrow.Luck")),
                    "bld": to_int(j.get("BaseGrow.Phys")),
                },
                "hard": {
                    "hp": to_int(j.get("DiffGrow.Hp")),
                    "str": to_int(j.get("DiffGrow.Str")),
                    "mag": to_int(j.get("DiffGrow.Magic")),
                    "dex": to_int(j.get("DiffGrow.Tech")),
                    "spd": to_int(j.get("DiffGrow.Quick")),
                    "def": to_int(j.get("DiffGrow.Def")),
                    "res": to_int(j.get("DiffGrow.Mdef")),
                    "lck": to_int(j.get("DiffGrow.Luck")),
                    "bld": to_int(j.get("DiffGrow.Phys")),
                },
                "lunatic": {
                    "hp": to_int(j.get("DiffGrowLunatic.Hp")),
                    "str": to_int(j.get("DiffGrowLunatic.Str")),
                    "mag": to_int(j.get("DiffGrowLunatic.Magic")),
                    "dex": to_int(j.get("DiffGrowLunatic.Tech")),
                    "spd": to_int(j.get("DiffGrowLunatic.Quick")),
                    "def": to_int(j.get("DiffGrowLunatic.Def")),
                    "res": to_int(j.get("DiffGrowLunatic.Mdef")),
                    "lck": to_int(j.get("DiffGrowLunatic.Luck")),
                    "bld": to_int(j.get("DiffGrowLunatic.Phys")),
                }
            }
        }

    print(f"Clases procesadas: {len(clases)}")

    # 3. Personajes (Person)
    persons_raw = parsear_xml_generico(os.path.join(DATAMINE_DIR, "Person.xml"))
    personajes = {}
    for p in persons_raw:
        pid = p.get("Pid")
        if not pid or pid.startswith("PID_None"):
            continue

        name_tag = p.get("Name")
        if pid in personajes and not name_tag:
            continue

        nombre = limpiar_nombre(pid, name_tag, trans)
        
        # Stats base personales (Base + OffsetN)
        p_bases = {
            "hp": to_int(p.get("Base.Hp")) + to_int(p.get("OffsetN.Hp")),
            "str": to_int(p.get("Base.Str")) + to_int(p.get("OffsetN.Str")),
            "mag": to_int(p.get("Base.Magic")) + to_int(p.get("OffsetN.Magic")),
            "dex": to_int(p.get("Base.Tech")) + to_int(p.get("OffsetN.Tech")),
            "spd": to_int(p.get("Base.Quick")) + to_int(p.get("OffsetN.Quick")),
            "def": to_int(p.get("Base.Def")) + to_int(p.get("OffsetN.Def")),
            "res": to_int(p.get("Base.Mdef")) + to_int(p.get("OffsetN.Mdef")),
            "lck": to_int(p.get("Base.Luck")) + to_int(p.get("OffsetN.Luck")),
            "bld": to_int(p.get("Base.Phys")) + to_int(p.get("OffsetN.Phys")),
        }

        # Crecimientos personales
        p_growths = {
            "hp": to_int(p.get("Grow.Hp")) or to_int(p.get("BaseGrow.Hp")),
            "str": to_int(p.get("Grow.Str")) or to_int(p.get("BaseGrow.Str")),
            "mag": to_int(p.get("Grow.Magic")) or to_int(p.get("BaseGrow.Magic")),
            "dex": to_int(p.get("Grow.Tech")) or to_int(p.get("BaseGrow.Tech")),
            "spd": to_int(p.get("Grow.Quick")) or to_int(p.get("BaseGrow.Quick")),
            "def": to_int(p.get("Grow.Def")) or to_int(p.get("BaseGrow.Def")),
            "res": to_int(p.get("Grow.Mdef")) or to_int(p.get("BaseGrow.Mdef")),
            "lck": to_int(p.get("Grow.Luck")) or to_int(p.get("BaseGrow.Luck")),
            "bld": to_int(p.get("Grow.Phys")) or to_int(p.get("BaseGrow.Phys")),
        }

        default_jid = p.get("Jid", "")
        join_lvl = to_int(p.get("Level"), 1)
        clase_def = clases.get(default_jid, {})
        c_bases = clase_def.get("base_stats", {})
        c_growths = clase_def.get("growths", {})

        # Estadísticas canónicas exactas al unirse (Serenes Forest / Juego oficial)
        join_stats = {}
        serenes_path = os.path.join(BASE_DIR, "scratch_canonical_serenes_bases.json")
        serenes_data = {}
        if os.path.exists(serenes_path):
            try:
                with open(serenes_path, "r", encoding="utf-8") as sf:
                    serenes_data = json.load(sf)
            except Exception:
                pass

        if nombre in serenes_data and not any(pid.startswith(pfx) for pfx in ['PID_M0', 'PID_M1', 'PID_M2', 'PID_S0']):
            s_data = serenes_data[nombre]
            join_stats = {
                'hp': s_data['hp'], 'str': s_data['str'], 'mag': s_data['mag'],
                'dex': s_data['dex'], 'spd': s_data['spd'], 'def': s_data['def'],
                'res': s_data['res'], 'lck': s_data['lck'], 'bld': s_data['bld']
            }
        else:
            lvl_diff = max(0, join_lvl - 1)
            for stat in ["hp", "str", "mag", "dex", "spd", "def", "res", "lck", "bld"]:
                b = c_bases.get(stat, 0) + p_bases.get(stat, 0)
                g = c_growths.get(stat, 0) + p_growths.get(stat, 0)
                join_stats[stat] = b + int(g * lvl_diff / 100.0)
        
        personajes[pid] = {
            "id": pid,
            "nombre": nombre,
            "jid_default": default_jid,
            "clase_default": clase_def.get("nombre", ""),
            "nivel_base": join_lvl,
            "base_stats": p_bases,
            "growths": p_growths,
            "join_stats": join_stats,
        }

    print(f"Personajes procesados: {len(personajes)}")

    # 4. Habilidades (Skill)
    skills_raw = parsear_xml_generico(os.path.join(DATAMINE_DIR, "Skill.xml"))
    habilidades = {}
    for s in skills_raw:
        sid = s.get("Sid")
        if not sid or sid.startswith("SID_None"):
            continue

        name_tag = s.get("Name")
        if sid in habilidades and not name_tag:
            continue

        nombre = limpiar_nombre(sid, name_tag, trans)

        habilidades[sid] = {
            "id": sid,
            "nombre": nombre,
            "icono": s.get("IconName", ""),
            "stat_boosts": {
                "hp": to_int(s.get("EnhanceValue.Hp") or s.get("Enhance.Hp")),
                "str": to_int(s.get("EnhanceValue.Str") or s.get("Enhance.Str")),
                "mag": to_int(s.get("EnhanceValue.Magic") or s.get("Enhance.Magic")),
                "dex": to_int(s.get("EnhanceValue.Tech") or s.get("Enhance.Tech")),
                "spd": to_int(s.get("EnhanceValue.Quick") or s.get("Enhance.Quick")),
                "def": to_int(s.get("EnhanceValue.Def") or s.get("Enhance.Def")),
                "res": to_int(s.get("EnhanceValue.Mdef") or s.get("Enhance.Mdef")),
                "lck": to_int(s.get("EnhanceValue.Luck") or s.get("Enhance.Luck")),
                "bld": to_int(s.get("EnhanceValue.Phys") or s.get("Enhance.Phys")),
                "mov": to_int(s.get("EnhanceValue.Move") or s.get("Enhance.Move")),
            },
            "combat_mods": {
                "power": to_int(s.get("Power")),
                "hit": to_int(s.get("Hit")),
                "crit": to_int(s.get("Critical")),
                "avo": to_int(s.get("Avoid")),
                "ddg": to_int(s.get("Secure")),
            }
        }

    print(f"Habilidades procesadas: {len(habilidades)}")

    # 5. Emblemas (God) — Extracción canónica de niveles de vínculo (1 a 20)
    god_tree = ET.parse(os.path.join(DATAMINE_DIR, "God.xml"))
    god_sheets = god_tree.getroot().findall("Sheet")
    god_sheet_0 = god_sheets[0].find("Data").findall("Param")
    god_sheet_1 = god_sheets[1].find("Data").findall("Param")

    # Mapeo de niveles por tabla de crecimiento (Ggid)
    current_ggid = None
    levels_by_ggid = {}
    for r in god_sheet_1:
        ggid = r.attrib.get("Ggid", "").strip()
        if ggid:
            current_ggid = ggid
        if not current_ggid:
            continue
        lvl_str = r.attrib.get("Level", "").strip()
        if not lvl_str or not lvl_str.isdigit():
            continue
        lvl = int(lvl_str)
        if current_ggid not in levels_by_ggid:
            levels_by_ggid[current_ggid] = {}
        
        sync_skills = [s.strip() for s in r.attrib.get("SynchroSkills", "").split(";") if s.strip()]
        inh_skills = [s.strip() for s in r.attrib.get("InheritanceSkills", "").split(";") if s.strip()]
        eng_skills = [s.strip() for s in r.attrib.get("EngageSkills", "").split(";") if s.strip()]
        eng_items = [s.strip() for s in r.attrib.get("EngageItems", "").split(";") if s.strip()]

        levels_by_ggid[current_ggid][lvl] = {
            "synchro_skills": sync_skills,
            "inheritance_skills": inh_skills,
            "engage_skills": eng_skills,
            "engage_items": eng_items
        }

    emblemas = {}

    for g in god_sheet_0:
        gid = g.attrib.get("Gid")
        if not gid or gid.startswith("GID_M0") or "相手" in gid or "敵" in gid:
            continue

        mid = g.attrib.get("Mid", "")
        ascii_name = g.attrib.get("AsciiName", "")
        nombre = trans.get(mid) or ascii_name or limpiar_nombre(gid, g.attrib.get("Name"), trans)
        if not nombre or nombre.startswith("GID_") or nombre == "???":
            continue

        gt = g.attrib.get("GrowTable", "")
        raw_levels = levels_by_ggid.get(gt, {})

        bond_levels = {}
        active_stats = {s: 0 for s in ["hp", "str", "mag", "dex", "spd", "def", "res", "lck", "bld", "mov"]}
        active_passives = {}
        active_items = []
        active_engage_skills = []

        for l in range(1, 21):
            lvl_data = raw_levels.get(l, {"synchro_skills": [], "inheritance_skills": [], "engage_skills": [], "engage_items": []})

            # Armas Engage desbloqueadas en este nivel o previos
            for iid in lvl_data["engage_items"]:
                if iid not in [it["iid"] for it in active_items]:
                    it_nom = armas.get(iid, {}).get("nombre") or trans.get(f"MIID_{iid}") or trans.get(iid) or iid
                    active_items.append({"iid": iid, "nombre": it_nom})

            # Habilidades Engage desbloqueadas
            for sid in lvl_data["engage_skills"]:
                if sid not in [es["sid"] for es in active_engage_skills]:
                    s_nom = habilidades.get(sid, {}).get("nombre") or trans.get(f"MSID_{sid}") or trans.get(sid) or sid
                    active_engage_skills.append({"sid": sid, "nombre": s_nom})

            # Habilidades de Sincronía (distinguiendo entre potenciadores de stat y pasivas de combate)
            for sid in lvl_data["synchro_skills"]:
                sk_info = habilidades.get(sid)
                enh = sk_info.get("stat_boosts", {}) if sk_info else {}
                has_enh = any(v > 0 for v in enh.values())
                if has_enh:
                    for stat_k, val in enh.items():
                        if val > 0:
                            active_stats[stat_k] = max(active_stats.get(stat_k, 0), val)
                else:
                    if "特効" in sid:
                        continue
                    s_nom = sk_info.get("nombre") if sk_info else (trans.get(f"MSID_{sid}") or trans.get(sid) or sid)
                    base_key = sid.rstrip("＋+0123456789")
                    active_passives[base_key] = {"sid": sid, "nombre": s_nom}

            # Habilidades heredables desbloqueadas en este nivel (se guardan para referencia pero no se auto-equipan)
            inh_at_level = []
            for sid in lvl_data["inheritance_skills"]:
                s_nom = habilidades.get(sid, {}).get("nombre") or trans.get(f"MSID_{sid}") or trans.get(sid) or sid
                inh_at_level.append({"sid": sid, "nombre": s_nom})

            cur_boosts = {k: v for k, v in active_stats.items() if v > 0}

            bond_levels[str(l)] = {
                "level": l,
                "stat_boosts": dict(cur_boosts),
                "synchro_skills": list(active_passives.values()),
                "engage_items": list(active_items),
                "engage_skills": list(active_engage_skills),
                "inheritance_skills": inh_at_level,
                "max_energia_emblema": 5 if l >= 20 else 6
            }

        fb10 = bond_levels.get("10", bond_levels.get("1", {}))
        emblemas[gid] = {
            "id": gid,
            "nombre": nombre,
            "ascii_name": ascii_name,
            "link_name": g.attrib.get("LinkName", ""),
            "grow_table": gt,
            "engage_items": [it["iid"] for it in fb10.get("engage_items", [])],
            "engage_skills": [sk["sid"] for sk in fb10.get("engage_skills", [])],
            "synchro_skills": [sk["sid"] for sk in fb10.get("synchro_skills", [])],
            "bond_levels": bond_levels
        }

    # Integrar Emblemas de DLC (Edelgard/3H, Tiki, Hector, Veronica, Soren, Camilla, Chrom/Robin)
    dlc_canon_path = os.path.join(BASE_DIR, "json", "dlc_emblems_canon.json")
    if os.path.exists(dlc_canon_path):
        with open(dlc_canon_path, "r", encoding="utf-8") as f:
            dlc_data = json.load(f)
        for dlc_gid, dlc_info in dlc_data.items():
            emblemas[dlc_gid] = dlc_info
        print(f"Emblemas DLC integrados: {len(dlc_data)}")

    print(f"Total Emblemas procesados (Base + DLC): {len(emblemas)}")

    # Guardar catálogo maestro compilado
    catalogo_final = {
        "armas": armas,
        "clases": clases,
        "personajes": personajes,
        "habilidades": habilidades,
        "emblemas": emblemas,
    }

    output_path = os.path.join(BASE_DIR, "catalogo_engage.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(catalogo_final, f, indent=2, ensure_ascii=False)

    json_dir = os.path.join(BASE_DIR, "json")
    if os.path.exists(json_dir):
        json_output = os.path.join(json_dir, "catalogo_engage.json")
        with open(json_output, "w", encoding="utf-8") as f:
            json.dump(catalogo_final, f, indent=2, ensure_ascii=False)

    print(f"\n[OK] Catalogo maestro compilado con exito: {output_path}")
    print(f"Tamano total: {os.path.getsize(output_path) / 1024:.1f} KB")

if __name__ == "__main__":
    compilar()
