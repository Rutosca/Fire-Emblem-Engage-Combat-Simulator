"""
buscador_maestro.py — FE Engage Data Mining & Canonical Engine Compiler
Recorre de forma robusta los XMLs y CSVs de datamine (FE17-DOC-main)
para extraer y consolidar todos los datos relevantes para combate, pasivas,
armas, estilos de combate, fórmulas y terrenos.

Genera: datos_canonicos_engage.json
Tolerante a fallos tipográficos, encodings y campos vacíos.
"""

import xml.etree.ElementTree as ET
import os
import json
import csv
import re
from typing import Dict, Any, List

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATAMINE_DIR = os.path.join(BASE_DIR, "FE17-DOC-main", "FE17-DOC-main", "fe_assets_gamedata")
TRANS_DIR = os.path.join(BASE_DIR, "FE17-DOC-main", "FE17-DOC-main", "translations")
USEN_CSV_DIR = os.path.join(BASE_DIR, "FE17-DOC-main", "FE17-DOC-main", "fe_assets_message", "us", "usen", "csv")
OUTPUT_FILE = os.path.join(BASE_DIR, "datos_canonicos_engage.json")
EXISTING_CATALOG_FILE = os.path.join(BASE_DIR, "catalogo_engage.json")


# =============================================================================
# Utilidades de Conversión y Normalización (Tolerantes a Fallos)
# =============================================================================

def safe_int(val: Any, default: int = 0) -> int:
    """Convierte de forma segura cualquier valor a entero."""
    if val is None:
        return default
    s = str(val).strip()
    if not s:
        return default
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return default


def safe_float(val: Any, default: float = 0.0) -> float:
    """Convierte de forma segura cualquier valor a flotante."""
    if val is None:
        return default
    s = str(val).strip()
    if not s:
        return default
    try:
        return float(s)
    except (ValueError, TypeError):
        return default


def safe_str(val: Any, default: str = "") -> str:
    """Convierte de forma segura a string limpio sin BOM."""
    if val is None:
        return default
    return str(val).strip().lstrip("\ufeff")


def normalizar_clave(texto: str) -> str:
    """Normaliza identificadores para búsquedas sin fallos tipográficos."""
    if not texto:
        return ""
    t = str(texto).lower().strip()
    for pfx in ["tid_", "mtid_", "sid_", "msid_", "jid_", "mjid_", "iid_", "miid_", "pid_", "mpid_", "gid_", "mgid_"]:
        if t.startswith(pfx):
            t = t[len(pfx):]
            break
    t = re.sub(r"[_\-\s]+", "", t)
    return t


def parsear_xml_seguro(filepath: str) -> List[Dict[str, str]]:
    """Parsea un XML del datamine devolviendo todos los Params de todas las Sheets."""
    if not os.path.exists(filepath):
        print(f"[Aviso] Archivo no encontrado: {filepath}")
        return []
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        filas = []
        for sheet in root.findall("Sheet"):
            data_elem = sheet.find("Data")
            if data_elem is None:
                continue
            for row in data_elem.findall("Param"):
                filas.append(dict(row.attrib))
        return filas
    except Exception as e:
        print(f"[Error XML] Error leyendo {filepath}: {e}")
        return []


# =============================================================================
# Ingestión de Traducciones y Mensajes
# =============================================================================

def cargar_diccionario_traducciones() -> Dict[str, str]:
    """Carga traducciones de mensajes desde US/EN y tablas de traducción."""
    traducciones = {}
    if os.path.exists(USEN_CSV_DIR):
        for fname in os.listdir(USEN_CSV_DIR):
            if fname.endswith(".csv"):
                fpath = os.path.join(USEN_CSV_DIR, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        reader = csv.reader(f)
                        for row in reader:
                            if len(row) >= 2 and row[0]:
                                k = safe_str(row[0])
                                v = safe_str(row[1])
                                traducciones[k] = v
                                for pfx in ["MIID_", "MJID_", "MPID_", "MSID_", "MGID_", "MTID_", "MID_"]:
                                    if k.startswith(pfx):
                                        traducciones[k[len(pfx):]] = v
                except Exception as e:
                    print(f"[Aviso CSV] Error al leer {fname}: {e}")

    # Translations secundarias
    trans_fee = os.path.join(TRANS_DIR, "fee-translations.csv")
    if os.path.exists(trans_fee):
        try:
            with open(trans_fee, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 3 and row[0] and row[2]:
                        en = safe_str(row[0])
                        jp = safe_str(row[2])
                        traducciones[jp] = en
                        traducciones[en] = en
                        for pfx in ["PID_", "JID_", "IID_", "SID_", "GID_", "TID_"]:
                            traducciones[f"{pfx}{jp}"] = en
                            traducciones[f"{pfx}{en}"] = en
        except Exception as e:
            print(f"[Aviso Translations] Error al leer fee-translations.csv: {e}")

    return traducciones


# =============================================================================
# 0. Fórmulas Maestras y Estilos de Combate (Calculator.xml & BattleStyle)
# =============================================================================

def extraer_formulas_y_estilos(trans: Dict[str, str]) -> Dict[str, Any]:
    print("[0/6] Extrayendo fórmulas maestras y estilos de combate...")
    calc_path = os.path.join(DATAMINE_DIR, "Calculator.xml")
    formulas = {}
    if os.path.exists(calc_path):
        try:
            tree = ET.parse(calc_path)
            root = tree.getroot()
            for sheet in root.findall("Sheet"):
                if sheet.get("Name") == "共通":
                    data = sheet.find("Data")
                    if data is not None:
                        for p in data.findall("Param"):
                            nombre = p.get("名前", "")
                            cond = p.get("条件式", "")
                            func = p.get("計算式", "")
                            formulas[nombre] = {
                                "condicion": cond,
                                "formula": func
                            }
        except Exception as e:
            print(f"[Aviso Calculator] Error parseando Calculator.xml: {e}")

    # Estilos de combate canónicos de FE Engage y sus reglas
    estilos_combate = {
        "Mystical": {
            "nombre_jp": "魔道スタイル",
            "aliases": ["mystical", "místico", "mistico", "magic", "魔道"],
            "regla_combate": "Ignora bonos de evasión (Avoid) del terreno al atacar con magia.",
            "ignora_terreno_avo": True,
            "duplica_terreno": False,
            "inmune_ruptura": False,
            "chain_attack": False
        },
        "Covert": {
            "nombre_jp": "隠密スタイル",
            "aliases": ["covert", "espía", "espia", "stealth", "隠密"],
            "regla_combate": "Duplica los bonos de evasión (Avoid) y defensa otorgados por el terreno.",
            "ignora_terreno_avo": False,
            "duplica_terreno": True,
            "inmune_ruptura": False,
            "chain_attack": False
        },
        "Armored": {
            "nombre_jp": "重装スタイル",
            "aliases": ["armored", "acorazado", "armor", "重装"],
            "regla_combate": "Inmunidad total a sufrir Ruptura (Break) en combate.",
            "ignora_terreno_avo": False,
            "duplica_terreno": False,
            "inmune_ruptura": True,
            "chain_attack": False
        },
        "Backup": {
            "nombre_jp": "連携スタイル",
            "aliases": ["backup", "alianza", "cooperación", "backup", "連携"],
            "regla_combate": "Participa en ataques en cadena (Chain Attacks) a rango de arma (Hit fijo 80%, 10% Max HP).",
            "ignora_terreno_avo": False,
            "duplica_terreno": False,
            "inmune_ruptura": False,
            "chain_attack": True
        },
        "Dragon": {
            "nombre_jp": "竜族スタイル",
            "aliases": ["dragon", "dragón", "dragon lord", "竜族"],
            "regla_combate": "Potenciadores de Engage máximos en habilidades y sincronías de Emblemas.",
            "ignora_terreno_avo": False,
            "duplica_terreno": False,
            "inmune_ruptura": False,
            "chain_attack": False
        },
        "Cavalry": {
            "nombre_jp": "騎馬スタイル",
            "aliases": ["cavalry", "caballería", "caballeria", "horse", "騎馬"],
            "regla_combate": "Mayor movilidad base en el mapa.",
            "ignora_terreno_avo": False,
            "duplica_terreno": False,
            "inmune_ruptura": False,
            "chain_attack": False
        },
        "Flying": {
            "nombre_jp": "飛行スタイル",
            "aliases": ["flying", "volador", "flier", "飛行"],
            "regla_combate": "Ignora costes de movimiento del terreno y sobrevuela obstáculos transitables.",
            "ignora_terreno_avo": False,
            "duplica_terreno": False,
            "inmune_ruptura": False,
            "chain_attack": False
        },
        "Qi Adept": {
            "nombre_jp": "気功スタイル",
            "aliases": ["qi adept", "artes", "qiadep", "guardián", "気功"],
            "regla_combate": "Capacidad de activar Guardia en Cadena (Chain Guard) a aliados adyacentes.",
            "ignora_terreno_avo": False,
            "duplica_terreno": False,
            "inmune_ruptura": False,
            "chain_attack": False
        }
    }

    return {
        "formulas": formulas,
        "estilos_combate": estilos_combate
    }


# =============================================================================
# 1. Terrenos Canónicos (Terrain.xml)
# =============================================================================

def extraer_terrenos(trans: Dict[str, str]) -> Dict[str, Any]:
    print("[1/6] Extrayendo catálogo canónico de terrenos (Terrain.xml)...")
    filas = parsear_xml_seguro(os.path.join(DATAMINE_DIR, "Terrain.xml"))
    terrenos = {}
    for row in filas:
        tid = row.get("Tid")
        if not tid:
            continue
        mtid = row.get("Name", "")
        nombre = trans.get(mtid) or trans.get(tid) or mtid.replace("MTID_", "")
        
        avo = safe_int(row.get("Avoid"))
        dfn = safe_int(row.get("Defense"))
        heal = safe_int(row.get("Heal"))
        flag = safe_int(row.get("Flag"))
        
        # En Engage el flag 4096 indica tile defensivo con inmunidad a Break (Antirruptura)
        es_antirruptura = bool(flag & 4096)
        prohibition = safe_int(row.get("Prohibition"))
        coste_mov = safe_int(row.get("MoveCost"), 1)
        
        info = {
            "tid": tid,
            "mtid": mtid,
            "nombre": nombre,
            "avoid": avo,
            "defense": dfn,
            "heal_turno": heal,
            "flag": flag,
            "es_antirruptura": es_antirruptura,
            "combate_prohibido": prohibition > 0,
            "coste_mov": coste_mov,
            "color_rgb": [
                safe_int(row.get("ColorR")),
                safe_int(row.get("ColorG")),
                safe_int(row.get("ColorB"))
            ]
        }
        terrenos[tid] = info
        if mtid and mtid not in terrenos:
            terrenos[mtid] = info
        # Normalizado para búsqueda tolerante
        terrenos[normalizar_clave(tid)] = info
        if mtid:
            terrenos[normalizar_clave(mtid)] = info

    print(f"      Terrenos indexados: {len(terrenos)}")
    return terrenos


# =============================================================================
# 2. Armas e Ítems Canónicos (Item.xml)
# =============================================================================

def extraer_armas(trans: Dict[str, str]) -> Dict[str, Any]:
    print("[2/6] Extrayendo armas e ítems canónicos (Item.xml)...")
    filas = parsear_xml_seguro(os.path.join(DATAMINE_DIR, "Item.xml"))
    armas = {}
    
    TIPO_ARMA_KIND = {
        "0": "Espada", "1": "Lanza", "2": "Hacha", "3": "Arco",
        "4": "Daga", "5": "Tomo", "6": "Bastón", "7": "Artes",
        "8": "Objeto", "9": "Objeto"
    }
    
    SID_A_EFECTIVIDAD = {
        "SID_飛行特効": "volador",
        "SID_鎧特効": "acorazado",
        "SID_馬特効": "caballería",
        "SID_竜特効": "dragón",
        "SID_異形特効": "monstruo",
    }

    for it in filas:
        iid = it.get("Iid")
        if not iid or iid.startswith("IID_None"):
            continue
            
        name_tag = it.get("Name", "")
        nombre = trans.get(name_tag) or trans.get(iid) or name_tag.replace("MIID_", "") or iid.replace("IID_", "")
        
        kind = str(it.get("Kind", "0"))
        tipo = TIPO_ARMA_KIND.get(kind, "Espada")
        
        mt = safe_int(it.get("Power"))
        wt = safe_int(it.get("Weight"))
        hit = safe_int(it.get("Hit"))
        crit = safe_int(it.get("Critical"))
        avo = safe_int(it.get("Avoid"))
        ddg = safe_int(it.get("Secure"))
        
        range_i = safe_int(it.get("RangeI"), 1)
        range_o = safe_int(it.get("RangeO"), 1)
        rango = list(range(range_i, range_o + 1)) if range_o > range_i else [range_i]
        
        attr = it.get("WeaponAttr", "0")
        flag_val = safe_int(it.get("Flag", 0))
        es_magica = (tipo == "Tomo" or str(attr) in ("2", "3") or bool(flag_val & 65536) or 
                     iid in ("IID_いかづちの剣", "IID_ほのおの槍", "IID_かぜの大斧", "IID_光の弓"))
        
        equip_sids = it.get("EquipSids", "")
        es_smash = ("SID_スマッシュ" in equip_sids or "smash" in equip_sids.lower())
        efectividades = []
        for sid in equip_sids.split(";"):
            sid = sid.strip()
            if sid in SID_A_EFECTIVIDAD:
                efectividades.append(SID_A_EFECTIVIDAD[sid])
                
        info = {
            "id": iid,
            "nombre": nombre,
            "tipo": tipo,
            "mt": mt,
            "wt": wt,
            "hit": hit,
            "crit": crit,
            "avo": avo,
            "ddg": ddg,
            "rango": rango,
            "es_magica": es_magica,
            "es_smash": es_smash,
            "efectividades": efectividades,
            "equip_sids": [s.strip() for s in equip_sids.split(";") if s.strip()]
        }
        armas[iid] = info
        armas[normalizar_clave(iid)] = info
        if nombre:
            armas[normalizar_clave(nombre)] = info

    print(f"      Armas e ítems indexados: {len(armas)}")
    return armas


# =============================================================================
# 3. Habilidades y Pasivas Canónicas (Skill.xml)
# =============================================================================

def extraer_habilidades(trans: Dict[str, str]) -> Dict[str, Any]:
    print("[3/6] Extrayendo habilidades y pasivas (Skill.xml)...")
    filas = parsear_xml_seguro(os.path.join(DATAMINE_DIR, "Skill.xml"))
    habilidades = {}
    
    for s in filas:
        sid = s.get("Sid")
        if not sid or sid.startswith("SID_None"):
            continue
            
        name_tag = s.get("Name", "")
        nombre = trans.get(name_tag) or trans.get(sid) or name_tag.replace("MSID_", "") or sid.replace("SID_", "")
        help_tag = s.get("Help", "")
        descripcion = trans.get(help_tag, "")
        
        info = {
            "id": sid,
            "nombre": nombre,
            "descripcion": descripcion,
            "icono": s.get("IconName", ""),
            "stat_boosts": {
                "hp": safe_int(s.get("Enhance.Hp")),
                "str": safe_int(s.get("Enhance.Str")),
                "mag": safe_int(s.get("Enhance.Magic")),
                "dex": safe_int(s.get("Enhance.Tech")),
                "spd": safe_int(s.get("Enhance.Quick")),
                "def": safe_int(s.get("Enhance.Def")),
                "res": safe_int(s.get("Enhance.Mdef")),
                "lck": safe_int(s.get("Enhance.Luck")),
                "bld": safe_int(s.get("Enhance.Phys")),
                "mov": safe_int(s.get("Enhance.Move")),
            },
            "combat_mods": {
                "power": safe_int(s.get("Power")),
                "hit": safe_int(s.get("Hit")),
                "crit": safe_int(s.get("Critical")),
                "avo": safe_int(s.get("Avoid")),
                "ddg": safe_int(s.get("Secure")),
            },
            "flags": safe_int(s.get("Flag")),
            "priority": safe_int(s.get("Priority"))
        }
        habilidades[sid] = info
        habilidades[normalizar_clave(sid)] = info
        if nombre:
            habilidades[normalizar_clave(nombre)] = info

    print(f"      Habilidades indexadas: {len(habilidades)}")
    return habilidades


# =============================================================================
# 4. Clases y Arquetipos (Job.xml)
# =============================================================================

def extraer_clases(trans: Dict[str, str]) -> Dict[str, Any]:
    print("[4/6] Extrayendo clases canónicas (Job.xml)...")
    filas = parsear_xml_seguro(os.path.join(DATAMINE_DIR, "Job.xml"))
    clases = {}
    
    MOVE_TYPE_MAP = {
        "1": "infantería",
        "2": "caballería",
        "3": "volador",
        "4": "acorazado",
    }

    for j in filas:
        jid = j.get("Jid")
        if not jid:
            continue
            
        name_tag = j.get("Name", "")
        nombre = trans.get(name_tag) or trans.get(jid) or name_tag.replace("MJID_", "") or jid.replace("JID_", "")
        
        style = j.get("StyleName", "None")
        mov = safe_int(j.get("Base.Move"), 4)
        tipo_mov = MOVE_TYPE_MAP.get(str(j.get("MoveType", "1")), "infantería")
        
        skills_raw = j.get("Skills", "")
        learning_skill = j.get("LearningSkill", "")
        lunatic_skill = j.get("LunaticSkill", "")
        
        info = {
            "id": jid,
            "nombre": nombre,
            "estilo_combate": style,
            "mov": mov,
            "tipo_movimiento": tipo_mov,
            "skills": [s.strip() for s in skills_raw.split(";") if s.strip()],
            "learning_skill": learning_skill,
            "lunatic_skill": lunatic_skill,
            "base_stats": {
                "hp": safe_int(j.get("Base.Hp")),
                "str": safe_int(j.get("Base.Str")),
                "mag": safe_int(j.get("Base.Magic")),
                "dex": safe_int(j.get("Base.Tech")),
                "spd": safe_int(j.get("Base.Quick")),
                "def": safe_int(j.get("Base.Def")),
                "res": safe_int(j.get("Base.Mdef")),
                "lck": safe_int(j.get("Base.Luck")),
                "bld": safe_int(j.get("Base.Phys")),
            },
            "enemy_growths": {
                "normal": {
                    "hp": safe_int(j.get("BaseGrow.Hp")),
                    "str": safe_int(j.get("BaseGrow.Str")),
                    "mag": safe_int(j.get("BaseGrow.Magic")),
                    "dex": safe_int(j.get("BaseGrow.Tech")),
                    "spd": safe_int(j.get("BaseGrow.Quick")),
                    "def": safe_int(j.get("BaseGrow.Def")),
                    "res": safe_int(j.get("BaseGrow.Mdef")),
                    "lck": safe_int(j.get("BaseGrow.Luck")),
                    "bld": safe_int(j.get("BaseGrow.Phys")),
                },
                "hard": {
                    "hp": safe_int(j.get("DiffGrow.Hp")),
                    "str": safe_int(j.get("DiffGrow.Str")),
                    "mag": safe_int(j.get("DiffGrow.Magic")),
                    "dex": safe_int(j.get("DiffGrow.Tech")),
                    "spd": safe_int(j.get("DiffGrow.Quick")),
                    "def": safe_int(j.get("DiffGrow.Def")),
                    "res": safe_int(j.get("DiffGrow.Mdef")),
                    "lck": safe_int(j.get("DiffGrow.Luck")),
                    "bld": safe_int(j.get("DiffGrow.Phys")),
                },
                "lunatic": {
                    "hp": safe_int(j.get("DiffGrowLunatic.Hp")),
                    "str": safe_int(j.get("DiffGrowLunatic.Str")),
                    "mag": safe_int(j.get("DiffGrowLunatic.Magic")),
                    "dex": safe_int(j.get("DiffGrowLunatic.Tech")),
                    "spd": safe_int(j.get("DiffGrowLunatic.Quick")),
                    "def": safe_int(j.get("DiffGrowLunatic.Def")),
                    "res": safe_int(j.get("DiffGrowLunatic.Mdef")),
                    "lck": safe_int(j.get("DiffGrowLunatic.Luck")),
                    "bld": safe_int(j.get("DiffGrowLunatic.Phys")),
                }
            }
        }
        clases[jid] = info
        clases[normalizar_clave(jid)] = info
        if nombre:
            clases[normalizar_clave(nombre)] = info

    print(f"      Clases indexadas: {len(clases)}")
    return clases


# =============================================================================
# 5. Emblemas y Personajes (God.xml & Person.xml)
# =============================================================================

def extraer_emblemas_y_personajes(trans: Dict[str, str]) -> Dict[str, Any]:
    print("[5/6] Extrayendo Emblemas y Personajes...")
    gods_raw = parsear_xml_seguro(os.path.join(DATAMINE_DIR, "God.xml"))
    emblemas = {}
    for g in gods_raw:
        gid = g.get("Gid")
        if not gid or gid.startswith("GID_M0") or "相手" in gid or "敵" in gid:
            continue
        nombre = trans.get(g.get("Mid", "")) or g.get("AsciiName", "") or gid.replace("GID_", "")
        if not nombre or nombre.startswith("GID_") or nombre == "???":
            continue
        info = {
            "id": gid,
            "nombre": nombre,
            "ascii_name": g.get("AsciiName", ""),
            "link_name": g.get("LinkName", ""),
            "grow_table": g.get("GrowTable", "")
        }
        emblemas[gid] = info
        emblemas[normalizar_clave(gid)] = info
        if nombre:
            emblemas[normalizar_clave(nombre)] = info

    persons_raw = parsear_xml_seguro(os.path.join(DATAMINE_DIR, "Person.xml"))
    personajes = {}
    for p in persons_raw:
        pid = p.get("Pid")
        if not pid or pid.startswith("PID_None"):
            continue
        name_tag = p.get("Name", "")
        nombre = trans.get(name_tag) or trans.get(pid) or name_tag.replace("MPID_", "") or pid.replace("PID_", "")
        
        info = {
            "id": pid,
            "nombre": nombre,
            "jid_default": p.get("Jid", ""),
            "nivel_base": safe_int(p.get("Level"), 1),
            "base_stats": {
                "hp": safe_int(p.get("Base.Hp")) + safe_int(p.get("OffsetN.Hp")),
                "str": safe_int(p.get("Base.Str")) + safe_int(p.get("OffsetN.Str")),
                "mag": safe_int(p.get("Base.Magic")) + safe_int(p.get("OffsetN.Magic")),
                "dex": safe_int(p.get("Base.Tech")) + safe_int(p.get("OffsetN.Tech")),
                "spd": safe_int(p.get("Base.Quick")) + safe_int(p.get("OffsetN.Quick")),
                "def": safe_int(p.get("Base.Def")) + safe_int(p.get("OffsetN.Def")),
                "res": safe_int(p.get("Base.Mdef")) + safe_int(p.get("OffsetN.Mdef")),
                "lck": safe_int(p.get("Base.Luck")) + safe_int(p.get("OffsetN.Luck")),
                "bld": safe_int(p.get("Base.Phys")) + safe_int(p.get("OffsetN.Phys")),
            },
            "growths": {
                "hp": safe_int(p.get("Grow.Hp")),
                "str": safe_int(p.get("Grow.Str")),
                "mag": safe_int(p.get("Grow.Magic")),
                "dex": safe_int(p.get("Grow.Tech")),
                "spd": safe_int(p.get("Grow.Quick")),
                "def": safe_int(p.get("Grow.Def")),
                "res": safe_int(p.get("Grow.Mdef")),
                "lck": safe_int(p.get("Grow.Luck")),
                "bld": safe_int(p.get("Grow.Phys")),
            },
            "common_sids": [s.strip() for s in (p.get("CommonSids") or "").split(";") if s.strip()],
            "normal_sids": [s.strip() for s in (p.get("NormalSids") or "").split(";") if s.strip()],
            "hard_sids": [s.strip() for s in (p.get("HardSids") or "").split(";") if s.strip()],
            "lunatic_sids": [s.strip() for s in (p.get("LunaticSids") or "").split(";") if s.strip()],
            "engage_sid": p.get("EngageSid", "")
        }
        personajes[pid] = info
        personajes[normalizar_clave(pid)] = info
        if nombre:
            personajes[normalizar_clave(nombre)] = info

    print(f"      Emblemas: {len(emblemas)}, Personajes: {len(personajes)}")
    return {"emblemas": emblemas, "personajes": personajes}


# =============================================================================
# Compilación y Fusión Maestra
# =============================================================================

def ejecutar_buscador_maestro():
    print("=================================================================")
    print("Iniciando Buscador Maestro (Extracción Canónica de FE Engage)...")
    print("=================================================================")

    trans = cargar_diccionario_traducciones()
    print(f"Diccionario de traducciones cargado: {len(trans)} entradas.")

    c0 = extraer_formulas_y_estilos(trans)
    c1_terrenos = extraer_terrenos(trans)
    c1_armas = extraer_armas(trans)
    c1_skills = extraer_habilidades(trans)
    c2_clases = extraer_clases(trans)
    c3_emblemas_personajes = extraer_emblemas_y_personajes(trans)

    # Catálogo canónico consolidado
    datos_canonicos = {
        "version": "1.0-canonico",
        "formulas": c0["formulas"],
        "estilos_combate": c0["estilos_combate"],
        "terrenos": c1_terrenos,
        "armas": c1_armas,
        "habilidades": c1_skills,
        "clases": c2_clases,
        "emblemas": c3_emblemas_personajes["emblemas"],
        "personajes": c3_emblemas_personajes["personajes"],
    }

    # Guardar en archivo JSON de salida
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(datos_canonicos, f, indent=2, ensure_ascii=False)

    print("\n=================================================================")
    print(f"[EXITO] Archivo generado: {OUTPUT_FILE}")
    print(f"Tamano: {os.path.getsize(OUTPUT_FILE) / 1024:.1f} KB")
    print("=================================================================")


if __name__ == "__main__":
    ejecutar_buscador_maestro()
