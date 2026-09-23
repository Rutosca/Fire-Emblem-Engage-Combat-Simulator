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
import xml.etree.ElementTree as ET
from motor_calculo import Unidad, Arma, inferir_rango_arma, resolver_estilo_combate
from estado_tablero import FichaUnidad
import pasivas

# Rutas de catálogos oficiales
_dir_actual = os.path.dirname(__file__)
_ruta_catalogo_json = os.path.join(_dir_actual, "json", "catalogo_engage.json")
_ruta_catalogo = _ruta_catalogo_json if os.path.exists(_ruta_catalogo_json) else os.path.join(_dir_actual, "catalogo_engage.json")

_catalogo = {}

def normalizar_texto(texto):
    """Elimina tildes y caracteres diacríticos para búsquedas insensibles a acentos."""
    if not texto:
        return ""
    return unicodedata.normalize('NFKD', str(texto)).encode('ASCII', 'ignore').decode('utf-8').lower()

def round_half_up(val):
    """Redondeo aritmético estándar (Round Half Up) usado en el motor de FE Engage."""
    return math.floor(float(val) + 0.5)

def _construir_grabados_desde_catalogo():
    """Construye el diccionario de grabados a partir de los datos oficiales de God.xml en el catálogo."""
    grabados = {}
    for eid, edata in (_catalogo.get("emblemas", {}) or {}).items():
        eng = edata.get("engrave")
        if eng:
            nom = edata.get("nombre", "")
            ascii_n = edata.get("ascii_name", "")
            # "nombre" (God.xml, nombre localizado oficial) es el que se usa para
            # mostrar y volver a guardar el grabado — "ascii_name" es una
            # transliteración interna del datamine con erratas conocidas
            # (Sigurd->Siglud, Leif->Leaf, Lyn->Lin, Corrin->Kamui, Eirika->Eirik,
            # Alear->Lueur) que rompía el guardado/reparseo del arma al no
            # coincidir con ninguna clave de GRABADOS_EMBLEMA.
            entry = {
                "nombre": nom or ascii_n,
                "emblema": nom,
                "mt": eng.get("power", 0),
                "wt": eng.get("weight", 0),
                "hit": eng.get("hit", 0),
                "crit": eng.get("critical", 0),
                "avo": eng.get("avoid", 0),
                "ddg": eng.get("secure", 0),
            }
            if ascii_n:
                grabados[normalizar_texto(ascii_n)] = entry
            if nom:
                grabados[normalizar_texto(nom)] = entry
    return grabados

GRABADOS_EMBLEMA = {}

def cargar_catalogo():
    """Carga catalogo_engage.json in-place."""
    global _catalogo
    if os.path.exists(_ruta_catalogo):
        try:
            with open(_ruta_catalogo, "r", encoding="utf-8") as f:
                _catalogo.clear()
                _catalogo.update(json.load(f))
            print(f"[OK] Catálogo Engage cargado: {len(_catalogo.get('armas', {}))} armas, {len(_catalogo.get('clases', {}))} clases, {len(_catalogo.get('habilidades', {}))} habilidades, {len(_catalogo.get('emblemas', {}))} emblemas")
        except Exception as e:
            print(f"Aviso al cargar catalogo_engage.json: {e}")

    # Los niveles internos (InternalLevel) de Job.xml y los grabados de God.xml
    # ya vienen compilados de origen en catalogo_engage.json vía compilar_catalogo.py.
    global GRABADOS_EMBLEMA
    GRABADOS_EMBLEMA = _construir_grabados_desde_catalogo()

    # Garantizar engage_attack canónico para los 21 Emblemas
    for eid, edata in _catalogo.get("emblemas", {}).items():
        if not edata.get("engage_attack"):
            atk = ATAQUES_ENGAGE_MAP.get(eid)
            if not atk:
                nom = normalizar_texto(edata.get("nombre", ""))
                ascii_n = normalizar_texto(edata.get("ascii_name", ""))
                for k_map, v_atk in ATAQUES_ENGAGE_MAP.items():
                    if normalizar_texto(k_map) in nom or normalizar_texto(k_map) in ascii_n:
                        atk = v_atk
                        break
            if atk:
                edata["engage_attack"] = atk

    return _catalogo

# =============================================================================
# Diccionario Canónico de Ataques de Emblema (Técnicas de Fusión Engage)
# =============================================================================

ATAQUES_ENGAGE_MAP = {
    "GID_マルス": "Lodestar Rush (Acometida estelar)",
    "GID_シグルド": "Override (Superación)",
    "GID_セリカ": "Warp Ragnarök (Tele-Ragnarök)",
    "GID_ミカヤ": "Great Sacrifice (Gran sacrificio)",
    "GID_ロイ": "Blazing Lion (León ardiente)",
    "GID_リーフ": "Quadruple Hit (Tétragolpe)",
    "GID_ルキナ": "All for One (Todos para uno)",
    "GID_リン": "Astra Storm (Tormenta astral)",
    "GID_アイク": "Great Aether (Gran Éter)",
    "GID_ベレト": "Goddess Dance (Danza de la Diosa)",
    "GID_カムイ": "Torrential Roar (Torrente rugiente)",
    "GID_エイリーク": "Twin Strike (Golpe gemelo)",
    "GID_エフラム": "Twin Strike (Golpe gemelo)",
    "GID_リュール": "Bond Blast (Ataque de Vínculo)",
    "GID_DLC_EDELGARD": "Houses Unite (Unión de Casas)",
    "GID_DLC_TIKI": "Divine Blessing (Bendición Divina)",
    "GID_DLC_HECTOR": "Storm's Eye (Ojo de la tormenta)",
    "GID_DLC_VERONICA": "Summon Hero (Invocar Héroe de FEH)",
    "GID_DLC_SOREN": "Cataclysm (Cataclismo)",
    "GID_DLC_CAMILLA": "Darkness (Torrente Sombrío)",
    "GID_DLC_CHROM": "Giga Levin Sword (Gigaespada Trueno)",
    "edelgard": "Houses Unite (Unión de Casas)",
    "three houses": "Houses Unite (Unión de Casas)",
    "marth": "Lodestar Rush (Acometida estelar)",
    "sigurd": "Override (Superación)",
    "celica": "Warp Ragnarök (Tele-Ragnarök)",
    "micaiah": "Great Sacrifice (Gran sacrificio)",
    "roy": "Blazing Lion (León ardiente)",
    "leif": "Quadruple Hit (Tétragolpe)",
    "lucina": "All for One (Todos para uno)",
    "lyn": "Astra Storm (Tormenta astral)",
    "ike": "Great Aether (Gran Éter)",
    "byleth": "Goddess Dance (Danza de la Diosa)",
    "corrin": "Torrential Roar (Torrente rugiente)",
    "eirika": "Twin Strike (Golpe gemelo)",
    "ephraim": "Twin Strike (Golpe gemelo)",
    "alear": "Bond Blast (Ataque de Vínculo)",
    "tiki": "Divine Blessing (Bendición Divina)",
    "hector": "Storm's Eye (Ojo de la tormenta)",
    "veronica": "Summon Hero (Invocar Héroe de FEH)",
    "soren": "Cataclysm (Cataclismo)",
    "camilla": "Darkness (Torrente Sombrío)",
    "chrom": "Giga Levin Sword (Gigaespada Trueno)",
}

# =============================================================================
# Configuración Canónica de Ataques de Emblema (Fijos vs Variables)
# =============================================================================

ATAQUES_ENGAGE_CONFIG = {
    # Ataques de arma variable: el atacante usa una de las armas disponibles en su inventario / emblema del tipo permitido
    "Lodestar Rush": {"es_variable": True, "tipos_permitidos": ["Espada"]},
    "Override": {"es_variable": True, "tipos_permitidos": ["Espada", "Lanza"]},
    "Blazing Lion": {"es_variable": True, "tipos_permitidos": ["Espada"]},
    "Great Aether": {"es_variable": True, "tipos_permitidos": ["Espada", "Hacha"]},
    "Twin Strike": {"es_variable": True, "tipos_permitidos": ["Espada", "Lanza"]},
    "All for One": {"es_variable": True, "tipos_permitidos": ["Espada", "Lanza", "Arco", "Daga"]},
    "Bond Blast": {"es_variable": True, "tipos_permitidos": ["Espada"]},

    # Ataques de arma fija: utilizan una técnica / arma predeterminada con estadísticas canónicas
    # Warp Ragnarök ataca con el tomo Ragnarok (IID_セリカ_ライナロック: Mt 15). El x1.2 de
    # Místico (SID_セリカエンゲージ技_魔法: 威力 * 1.2) se aplica al DAÑO en motor_calculo,
    # no al Mt — por eso ya no se usa el Mt 18 "fudge" que solo cuadraba con unidades Místicas.
    "Warp Ragnarök": {
        "es_variable": False,
        "arma_fija": {
            "nombre": "Warp Ragnarök", "mt": 15, "hit": 100, "crit": 0, "wt": 5, "tipo": "Tomo", "es_magica": True, "rango": [1]
        }
    },
    "Houses Unite": {
        "es_variable": False,
        "arma_fija": {
            "nombre": "Houses Unite", "mt": 19, "hit": 100, "crit": 0, "wt": 10, "tipo": "Lanza", "es_magica": False, "rango": [1]
        }
    },
    "Astra Storm": {"es_variable": True, "tipos_permitidos": ["Arco"]},
    "Torrential Roar": {
        "es_variable": False,
        "arma_fija": {
            "nombre": "Torrential Roar", "mt": 15, "hit": 100, "crit": 0, "wt": 7, "tipo": "Tomo", "es_magica": True, "rango": [1]
        }
    },
    "Quadruple Hit": {
        "es_variable": False,
        "arma_fija": {
            "nombre": "Quadruple Hit", "mt": 14, "hit": 100, "crit": 0, "wt": 8, "tipo": "Lanza", "es_magica": False, "rango": [1]
        }
    },
    "Cataclysm": {
        "es_variable": False,
        "arma_fija": {
            "nombre": "Cataclysm", "mt": 16, "hit": 100, "crit": 0, "wt": 6, "tipo": "Tomo", "es_magica": True, "rango": [1, 2]
        }
    },
    "Darkness": {
        "es_variable": False,
        "arma_fija": {
            "nombre": "Darkness", "mt": 15, "hit": 100, "crit": 0, "wt": 8, "tipo": "Hacha", "es_magica": True, "rango": [1]
        }
    },
    "Giga Levin Sword": {
        "es_variable": False,
        "arma_fija": {
            "nombre": "Giga Levin Sword", "mt": 17, "hit": 100, "crit": 0, "wt": 9, "tipo": "Espada", "es_magica": True, "rango": [1, 2]
        }
    },
}

# Carga inicial al importar el módulo
cargar_catalogo()

# GRABADOS_EMBLEMA se construye dinámicamente desde los datos de God.xml en el catálogo cargado.
if not GRABADOS_EMBLEMA:
    GRABADOS_EMBLEMA = _construir_grabados_desde_catalogo()

REFINES_GENERICOS = {
    1: {"mt": 1, "hit": 5, "crit": 0, "wt": 0},
    2: {"mt": 2, "hit": 5, "crit": 5, "wt": 0},
    3: {"mt": 3, "hit": 10, "crit": 5, "wt": -1},
    4: {"mt": 4, "hit": 10, "crit": 10, "wt": -1},
    5: {"mt": 5, "hit": 15, "crit": 10, "wt": -2},
}

ALIAS_ARMAS_ESPANOL = {
    # Lanzas
    "jabalina": "Javelin",
    "pica": "Spear",
    "lanza de hierro": "Iron Lance",
    "lanza de acero": "Steel Lance",
    "lanza de plata": "Silver Lance",
    "lanza fina": "Slim Lance",
    "lanza asesina": "Killer Lance",
    "lanza del valor": "Brave Lance",
    "gran lanza de hierro": "Iron Greatlance",
    "gran lanza de acero": "Steel Greatlance",
    "gran lanza de plata": "Silver Greatlance",
    "lanza pesada": "Heavy Lance",
    "lanza jinete": "Ridersbane",
    "lanza de fuego": "Flame Lance",
    # Espadas
    "espada de hierro": "Iron Sword",
    "espada de acero": "Steel Sword",
    "espada de plata": "Silver Sword",
    "espada fina": "Slim Sword",
    "espada asesina": "Killing Edge",
    "espada del valor": "Brave Sword",
    "gran espada de hierro": "Iron Blade",
    "gran espada de acero": "Steel Blade",
    "gran espada de plata": "Silver Blade",
    "espada trueno": "Levin Sword",
    "machacaarmaduras": "Armorslayer",
    "antijinetes": "Ridersbane",
    "estoque": "Rapier",
    # Hachas
    "hacha de mano": "Hand Axe",
    "hacha de hierro": "Iron Axe",
    "hacha de acero": "Steel Axe",
    "hacha de plata": "Silver Axe",
    "hacha asesina": "Killer Axe",
    "hacha del valor": "Brave Axe",
    "gran hacha de hierro": "Iron Greataxe",
    "gran hacha de acero": "Steel Greataxe",
    "gran hacha de plata": "Silver Greataxe",
    "hacha huracan": "Hurricane Axe",
    "hacha huracán": "Hurricane Axe",
    "machacamartillo": "Hammer",
    "hacha polo": "Poleax",
    # Arcos
    "arco de hierro": "Iron Bow",
    "arco de acero": "Steel Bow",
    "arco de plata": "Silver Bow",
    "arco asesino": "Killer Bow",
    "arco del valor": "Brave Bow",
    "arco largo": "Longbow",
    "miniarco": "Mini Bow",
    "arco corto": "Mini Bow",
    "arco radiante": "Radiant Bow",
    # Tomos
    "fuego": "Fire",
    "elfire": "Elfire",
    "bolganon": "Bolganone",
    "bolganone": "Bolganone",
    "trueno": "Thunder",
    "elthunder": "Elthunder",
    "toron": "Thoron",
    "thoron": "Thoron",
    "viento": "Wind",
    "elwind": "Elwind",
    "excalibur": "Excalibur",
    "fulgor": "Shine",
    "nosferatu": "Nosferatu",
    "serafin": "Seraphim",
    "seraphim": "Seraphim",
    "oleada": "Surge",
    "eloleada": "Elsurge",
    # Dagas
    "daga de hierro": "Iron Dagger",
    "daga de acero": "Steel Dagger",
    "daga de plata": "Silver Dagger",
    "cuchillo de hierro": "Iron Dagger",
    "cuchillo de acero": "Steel Dagger",
    "cuchillo de plata": "Silver Dagger",
}

_RANGOS_CATALOGO_CACHE = {}


def _rango_canonico_catalogo(nom_low: str):
    """Rango del catálogo para el nombre base del arma (sin forja ni paréntesis),
    por coincidencia exacta del nombre normalizado. None si no está o no es válido."""
    base = re.sub(r'\([^)]*\)', '', nom_low or '')
    base = re.sub(r'\+\d+', '', base).strip()
    if not base:
        return None
    clave = normalizar_texto(base)
    if not _RANGOS_CATALOGO_CACHE or _RANGOS_CATALOGO_CACHE.get('_n') != len(_catalogo.get("armas", {})):
        _RANGOS_CATALOGO_CACHE.clear()
        for v in _catalogo.get("armas", {}).values():
            r = v.get("rango")
            if isinstance(r, list) and r and all(isinstance(x, int) and x > 0 for x in r):
                _RANGOS_CATALOGO_CACHE.setdefault(normalizar_texto(v.get("nombre", "")), tuple(sorted(set(r))))
        _RANGOS_CATALOGO_CACHE['_n'] = len(_catalogo.get("armas", {}))
    return _RANGOS_CATALOGO_CACHE.get(clave)


def inferir_rango_arma(nombre: str, tipo: str, rango_existente=None) -> list:
    """
    Garantiza el rango canónico estricto de las armas en Fire Emblem Engage:
    - Arcos (Bows): estrictamente [2] (o [2, 3] si es Longbow/Arco largo, o [1] si es Mini Bow/Arco corto).
      NUNCA [1] para arcos estándar (no pueden atacar ni contraatacar a distancia 1).
    - Jabalinas, Hachas arrojadizas y armas 1-2: estrictamente [1, 2].
    - Tomos mágicos: estrictamente [1, 2] (o [1, 2, 3] para Trueno/Thunder/Thoron).
    - Dagas: estrictamente [1, 2].
    - Armas cuerpo a cuerpo estándar: [1].
    """
    nom_low = (nombre or "").lower()
    tipo_low = (tipo or "").lower()

    # Rango canónico del datamine si el arma existe en el catálogo (Failnaught 2-3,
    # Master Bow 1-2, Kard 1, Meteor 3-7…): la heurística solo cubre lo que falta.
    rango_cat = _rango_canonico_catalogo(nom_low)
    if rango_cat:
        return list(rango_cat)

    # Arcos
    if tipo_low in ("arco", "bow") or any(b in nom_low for b in ("arco", "bow")):
        if "longbow" in nom_low or "largo" in nom_low:
            return [2, 3]
        if "mini" in nom_low or "corto" in nom_low:
            return [1]
        return [2]

    # Armas arrojadizas 1-2
    if any(w in nom_low for w in ("javelin", "jabalina", "hand axe", "hacha de mano", "tomahawk", "spear", "pica", "short spear", "levin", "espada trueno", "flame lance", "lanza de fuego", "hurricane", "hacha huracan", "hacha huracán")):
        return [1, 2]

    # Tomos
    if tipo_low in ("tomo", "tome", "magia") or any(w in nom_low for w in ("fire", "fuego", "thunder", "trueno", "wind", "viento", "elfire", "elthunder", "elwind", "bolganone", "thoron", "excalibur", "surge", "elsurge", "shine", "fulgor", "nosferatu", "seraphim")):
        if any(th in nom_low for th in ("thunder", "trueno", "elthunder", "thoron")):
            return [1, 2, 3]
        if "surge" in nom_low or "oleada" in nom_low:
            return [1]
        return [1, 2]

    # Dagas
    if tipo_low in ("daga", "dagger", "knife", "cuchillo") or any(w in nom_low for w in ("daga", "dagger", "knife", "cuchillo", "stiletto", "misericorde", "cinquedea", "peshkatz", "carnwenhan")):
        return [1, 2]

    if isinstance(rango_existente, (list, tuple)) and len(rango_existente) > 0:
        return list(rango_existente)

    return [1]

def _buscar_en_catalogo(categoria: str, texto: str):
    """
    Búsqueda fuzzy en _catalogo[categoria] por ID exacto o nombre normalizado.
    Soporta mapeo automático de nombres canónicos en español sin recursión circular.
    Devuelve (key, item_dict) o (None, None) si no lo encuentra.
    """
    datos = _catalogo.get(categoria, {})
    if texto in datos:
        return texto, datos[texto]
    texto_norm = normalizar_texto(texto)

    # 1. Búsqueda directa por nombre o key en el catálogo
    for k, v in datos.items():
        if normalizar_texto(v.get("nombre", "")) == texto_norm or normalizar_texto(k) == texto_norm:
            return k, v

    # 2. Comprobar alias en español si busca armas (evitando recursión circular)
    if categoria == "armas" and texto_norm in ALIAS_ARMAS_ESPANOL:
        alias_en = ALIAS_ARMAS_ESPANOL[texto_norm]
        alias_norm = normalizar_texto(alias_en)
        if alias_norm != texto_norm:
            alias_k, alias_v = _buscar_en_catalogo("armas", alias_en)
            if alias_v:
                return alias_k, alias_v

    # 3. Búsqueda por contención
    for k, v in datos.items():
        v_nom = normalizar_texto(v.get("nombre", ""))
        if v_nom and (texto_norm in v_nom or v_nom in texto_norm):
            return k, v

    return None, None

_ALIAS_TIPO_ARMA = {
    "espada": "Espada", "sword": "Espada",
    "lanza": "Lanza", "lance": "Lanza",
    "hacha": "Hacha", "axe": "Hacha",
    "arco": "Arco", "bow": "Arco",
    "daga": "Daga", "dagger": "Daga", "knife": "Daga",
    "tomo": "Tomo", "tome": "Tomo", "magia": "Tomo", "magic": "Tomo",
    "baston": "Bastón", "bastón": "Bastón", "staff": "Bastón", "rod": "Bastón",
    "artes": "Artes", "arts": "Artes", "fist": "Artes", "puño": "Artes",
    "especial": "Especial", "special": "Especial",
}


def normalizar_tipo_arma(tipo) -> str:
    """'bow' / 'Arco' / 'arco' → 'Arco' (clave canónica de armas_permitidas)."""
    return _ALIAS_TIPO_ARMA.get(normalizar_texto(tipo), str(tipo or "").capitalize())


def armas_permitidas_clase(clase_id: str = "", clase_nombre: str = "") -> list:
    """Tipos de arma en que la clase tiene maestría (Job.xml WeaponBow="1", etc.)."""
    info = _catalogo.get("clases", {}).get(clase_id) if clase_id else None
    if not info and clase_nombre:
        _, info = _buscar_en_catalogo("clases", clase_nombre)
    return list((info or {}).get("armas_permitidas", []))


def puede_usar_tipo_arma(ficha, tipo) -> bool:
    """True si la clase de la ficha tiene maestría en ese tipo de arma."""
    tipo_c = normalizar_tipo_arma(tipo)
    return tipo_c in armas_permitidas_clase(getattr(ficha, 'clase_id', ''), getattr(ficha, 'clase_nombre', ''))


def tiene_arma_de_tipo(ficha, tipo) -> bool:
    """True si la ficha lleva en el inventario (o equipada) un arma de ese tipo."""
    tipo_c = normalizar_tipo_arma(tipo)
    if getattr(ficha, 'arma', None) and normalizar_tipo_arma(getattr(ficha.arma, 'tipo', '')) == tipo_c:
        return True
    for it in getattr(ficha, 'inventario', []) or []:
        t_it = it.get("tipo")
        if not t_it:
            a_obj = _arma_desde_item(it)
            t_it = getattr(a_obj, 'tipo', '') if a_obj else ''
        if normalizar_tipo_arma(t_it) == tipo_c:
            return True
    return False


# Tipo de arma que exige cada arma de mapa. El objeto de Tiled lo declara en
# `arma_permitida` ("Arco" en una ballesta, "Tomo" en un cañón mágico); si no lo
# trae, se deduce de su `tipo` y, en última instancia, es una ballesta de arco.
_ARMA_MAPA_POR_TIPO = {
    "ballesta": "Arco", "canon": "Arco", "cañon": "Arco",
    "canon_magico": "Tomo", "cañon_magico": "Tomo", "magico": "Tomo",
}


# Nombre bonito por `tipo` del tile, para no depender de cómo se llame en Tiled
_NOMBRE_ARMA_MAPA = {
    "ballesta": "Ballesta", "canon": "Cañón", "cañon": "Cañón",
    "canon_magico": "Cañón mágico", "cañon_magico": "Cañón mágico",
}


def nombre_arma_de_mapa(props_objeto: dict, nombre_objeto: str = "") -> str:
    """Etiqueta legible del arma de mapa: la del catálogo por `tipo`, o el nombre del
    objeto de Tiled con los guiones bajos convertidos en espacios."""
    props_objeto = props_objeto or {}
    por_tipo = _NOMBRE_ARMA_MAPA.get(normalizar_texto(str(props_objeto.get("tipo", ""))))
    if por_tipo:
        return por_tipo
    limpio = str(nombre_objeto or "").replace("_", " ").strip()
    return limpio or ("Cañón mágico" if tipo_arma_de_objeto(props_objeto) == "Tomo" else "Ballesta")


def tipo_arma_de_objeto(props_objeto: dict) -> str:
    """Tipo de arma que hay que llevar para usar esta arma de mapa ("Arco", "Tomo"…)."""
    props_objeto = props_objeto or {}
    declarado = str(props_objeto.get("arma_permitida", "") or "").strip()
    if declarado:
        return normalizar_tipo_arma(declarado) or declarado
    return _ARMA_MAPA_POR_TIPO.get(normalizar_texto(str(props_objeto.get("tipo", ""))), "Arco")


def puede_usar_arma_de_mapa(ficha, props_objeto: dict = None) -> bool:
    """
    Armas de mapa (ballesta del Cap. 8, cañón mágico del Cap. 10): solo unidades cuya
    clase tiene maestría en el tipo que pide el objeto Y que llevan un arma de ese tipo.
    """
    tipo = tipo_arma_de_objeto(props_objeto)
    return puede_usar_tipo_arma(ficha, tipo) and tiene_arma_de_tipo(ficha, tipo)


def puede_usar_ballesta(ficha) -> bool:
    """Compatibilidad: arma de mapa de tipo Arco (ballesta)."""
    return puede_usar_arma_de_mapa(ficha, {"arma_permitida": "Arco"})


def info_curacion_item(nombre_item: str, sanador=None) -> Optional[dict]:
    """
    Curación de un bastón u objeto según el datamine (Item.xml → catálogo `armas`):
      • Bastón de curación (Heal 10, Mend 20, Physic 8, Recover 40, Fortify 7…):
        HP = Mt del bastón + Mag del sanador // 2  (fórmula de Engage), rango del catálogo.
      • Objeto consumible (Poción 15, Elixir 30, Antídoto 15): HP = Mt del objeto, sin
        rango. El Antídoto (Item.xml AddType=18) además quita el veneno → `cura_veneno`.
    Devuelve {"nombre", "tipo", "mt", "curacion", "rango", "cura_veneno"} o None si no cura.
    """
    if not nombre_item:
        return None
    # Nombres ingleses de los consumibles (el catálogo los guarda en español)
    _ALIAS_CONSUMIBLES = {"vulnerary": "Poción", "medicine": "Elixir", "antidote": "Antídoto"}
    clave = _ALIAS_CONSUMIBLES.get(normalizar_texto(str(nombre_item)), str(nombre_item))
    _aid, ainfo = _buscar_en_catalogo("armas", clave)
    if not ainfo:
        return None
    tipo = str(ainfo.get("tipo", "") or "")
    mt = int(ainfo.get("mt", 0) or 0)
    nombre = ainfo.get("nombre", str(nombre_item))
    n_low = normalizar_texto(nombre)
    if tipo in ("Bastón", "Baston", "Staff"):
        # Bastones de estado (Freeze, Silence, Rescue, Warp…) tienen Mt 0; Sacrifice (255) es especial
        if mt <= 0 or mt >= 200 or "sacrifice" in n_low:
            return None
        mag = int(getattr(getattr(sanador, 'stats', sanador), 'magia', 0) or 0) if sanador is not None else 0
        return {"nombre": nombre, "tipo": "Bastón", "mt": mt, "curacion": mt + mag // 2,
                "rango": list(ainfo.get("rango") or [1]), "cura_veneno": False}
    if tipo in ("Objeto", "Item", "Consumible"):
        # Consumibles de HP: Poción, Elixir y Antídoto (que además cura el veneno).
        # Libros de habilidad y bentos también tienen Mt pero no curan HP.
        es_antidoto = any(k in n_low for k in ("antidoto", "antidote"))
        if mt <= 0 or not (es_antidoto or any(k in n_low for k in ("pocion", "vulnerary", "elixir", "medicine", "brebaje"))):
            return None
        return {"nombre": nombre, "tipo": "Objeto", "mt": mt, "curacion": mt, "rango": [0], "cura_veneno": es_antidoto}
    return None


def growths_totales(nombre_personaje: str, clase_nombre: str) -> dict:
    """
    Crecimientos personaje + clase (%) por stat, como los usa el juego para subir
    de nivel. Claves: hp, str, mag, dex, spd, def, res, lck, bld. Vacío si no
    hay datos del personaje ni de la clase.
    """
    total = {}
    _pid, p_info = _buscar_en_catalogo("personajes", nombre_personaje or "")
    _jid, j_info = _buscar_en_catalogo("clases", clase_nombre or "")
    for fuente in ((p_info or {}).get("growths") or {}, (j_info or {}).get("growths") or {}):
        for k, v in fuente.items():
            total[k] = total.get(k, 0) + int(v or 0)
    return total


def boosts_rise_above(nombre_personaje: str, clase_nombre: str, niveles: int = 5) -> dict:
    """
    Rise Above (Roy, SID_超越, EnhanceLevel=5): Nv +5 durante la Fusión. El juego
    resuelve esas 5 subidas con su acumulador de crecimientos (no reproducible),
    así que esto es una ESTIMACIÓN: ceil(crecimiento personaje+clase × 5 / 100)
    por stat (contrastado con Diamant/Lord: acierta 7 de 9 stats; falla Sue y Com).
    Si la ficha trae `boosts_fusion` (valores vistos en el juego) se usan esos.
    """
    import math
    g = growths_totales(nombre_personaje, clase_nombre)
    out = {}
    for k, v in g.items():
        b = int(math.ceil(int(v) * niveles / 100.0))
        if b > 0:
            out[k] = b
    return out


def arma_de_tipo_de_ficha(ficha, tipo):
    """El arma equipada de ese tipo o, si no, la de más Mt del inventario — None si no lleva."""
    tipo_c = normalizar_tipo_arma(tipo)
    if getattr(ficha, 'arma', None) and normalizar_tipo_arma(getattr(ficha.arma, 'tipo', '')) == tipo_c:
        return ficha.arma
    candidatas = []
    for it in getattr(ficha, 'inventario', []) or []:
        a_obj = _arma_desde_item(it)
        if a_obj and normalizar_tipo_arma(getattr(a_obj, 'tipo', '')) == tipo_c:
            candidatas.append(a_obj)
    return max(candidatas, key=lambda a: int(getattr(a, 'mt', 0) or 0)) if candidatas else None


def arco_de_ficha(ficha):
    """El arco equipado o, si no, el mejor arco del inventario (objeto Arma) — None si no hay."""
    return arma_de_tipo_de_ficha(ficha, "Arco")


def arma_de_mapa_desde(ficha, props_objeto: dict, nombre_objeto: str = ""):
    """
    Arma efectiva al disparar un arma de mapa (ballesta de arco, cañón mágico) con el
    arma propia del tipo que pide el objeto: su Mt, Hit +20, sin crítico, alcance
    `distancia_min`..`distancia_max` (3–7 en el datamine), UN solo golpe y sin
    contraataque (Skill.xml SID_弓砲台 / SID_魔砲台: 命中値+20, 必殺率=0, 手番回数=1,
    相手の手番回数=0, RangeI=3 RangeO=7). Conserva el tipo del arma base, así que un
    cañón mágico ataca a la RES, y su efectividad (el arco x3 contra pegasos/grifos;
    NO contra jinetes de wyvern como Ivy: ver `debilidades` de la clase).
    """
    import copy
    props_objeto = props_objeto or {}
    tipo = tipo_arma_de_objeto(props_objeto)
    base = arma_de_tipo_de_ficha(ficha, tipo)
    if not base:
        return None
    arma = copy.copy(base)
    d_min = int(props_objeto.get("distancia_min", 3))
    d_max = int(props_objeto.get("distancia_max", 7))
    arma.nombre = f"{nombre_arma_de_mapa(props_objeto, nombre_objeto)} ({base.nombre})"
    arma.rango = list(range(d_min, d_max + 1))
    arma.hit = int(getattr(base, 'hit', 0) or 0) + int(props_objeto.get("hit_bonus", 20))
    arma.crit = 0
    setattr(arma, 'es_ballesta', True)          # comportamiento: 1 golpe, sin contra, sin pasivas externas
    setattr(arma, 'es_arma_mapa', True)
    setattr(arma, 'tipo_arma_mapa', tipo)
    setattr(arma, 'arma_base_nombre', base.nombre)
    return arma


def arma_ballesta_desde(ficha, props_objeto: dict):
    """Compatibilidad: `arma_de_mapa_desde` para ballestas de arco."""
    return arma_de_mapa_desde(ficha, props_objeto)


_NOMBRES_ARMAS_EMBLEMA_CACHE = {}


def _es_nombre_arma_emblema(raw: str) -> bool:
    """True si `raw` (sin sufijo "(Emblema)") es exactamente un engage_item del catálogo
    de emblemas, p.ej. "Failnaught (Claude)" o "Levin Sword (Robin)"."""
    n_emb = len(_catalogo.get("emblemas", {}))
    if _NOMBRES_ARMAS_EMBLEMA_CACHE.get('_n') != n_emb:
        _NOMBRES_ARMAS_EMBLEMA_CACHE.clear()
        for e in _catalogo.get("emblemas", {}).values():
            for b in (e.get("bond_levels") or {}).values():
                for it in b.get("engage_items") or []:
                    nom = (it.get("nombre") or it.get("iid")) if isinstance(it, dict) else str(it)
                    if nom:
                        _NOMBRES_ARMAS_EMBLEMA_CACHE[normalizar_texto(nom)] = True
        _NOMBRES_ARMAS_EMBLEMA_CACHE['_n'] = n_emb
    limpio = re.sub(r'\(\s*emblema\s*\)', '', str(raw or ''), flags=re.IGNORECASE).strip()
    return bool(_NOMBRES_ARMAS_EMBLEMA_CACHE.get(normalizar_texto(limpio)))


def parsear_arma_string(raw_str, es_arma_emblema: bool = False):
    """
    Parsea nombres de armas con nivel de forja (+1..+5) y grabado de emblema (Marth, Sigurd, etc.).
    Acepta string o diccionario con campos 'nombre', 'refine_lvl', 'grabado'.
    `es_arma_emblema` (o el sufijo "(Emblema)" / el campo es_engage del dict) marca
    un arma de Emblema: no se le aplica grabado.
    """
    if not raw_str:
        return None
    iid_explicito = ""
    if isinstance(raw_str, dict):
        es_arma_emblema = es_arma_emblema or bool(raw_str.get("es_engage"))
        iid_explicito = str(raw_str.get("id") or "")
        base = raw_str.get("nombre_base") or raw_str.get("nombre") or raw_str.get("arma") or ""
        ref = raw_str.get("refine_lvl", 0)
        grab = raw_str.get("grabado", "")
        raw_str = str(base)
        if ref and f"+{ref}" not in raw_str:
            raw_str += f"+{ref}"
        if grab and f"({grab})" not in raw_str:
            raw_str += f" ({grab})"
    raw_str = str(raw_str).strip()
    es_arma_emblema = bool(es_arma_emblema) or "(emblema)" in raw_str.lower() or _es_nombre_arma_emblema(raw_str)

    # 1. Detectar grabado de emblema entre paréntesis: (Marth), (Sigurd), etc.
    # Las armas de Emblema (Failnaught (Claude), Levin Sword (Robin), Aymr…) no
    # admiten grabado: su paréntesis nombra al emblema dueño y se descarta.
    grabado_info = None
    m_grab = re.search(r'\(([^)]+)\)', raw_str)
    limpio = raw_str
    if m_grab:
        if not es_arma_emblema:
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
    if iid_explicito and iid_explicito in (_catalogo.get("armas") or {}):
        candidata = _catalogo["armas"][iid_explicito]
        nom_sin_etiqueta = re.sub(r"\([^)]+\)", "", str(candidata.get("nombre", ""))).strip()
        if normalizar_texto(nom_sin_etiqueta) == normalizar_texto(limpio):
            base_aid, ainfo = iid_explicito, candidata
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

    nombre_base = re.sub(r"\s*\((?:Evento|Prólogo)\)\s*$", "", str(ainfo.get("nombre", base_aid))).strip()
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
        "rango": inferir_rango_arma(ainfo.get("nombre", base_aid), ainfo.get("tipo", "Espada"), ainfo.get("rango")),
        "es_magica": ainfo.get("es_magica", False),
        "es_smash": bool(ainfo.get("es_smash", False)),
        "efectividades": ainfo.get("efectividades", ["volador"] if ainfo.get("tipo") == "Arco" else []),
        "usos_max": ainfo.get("usos_max"),
        "sids": list(ainfo.get("equip_sids", []) or []),
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
    # Pasar el dict completo (no solo el nombre): si el grabado/refine_lvl viene
    # como campo separado y no embebido en "nombre" (p.ej. {"nombre": "Levin
    # Sword", "grabado": "Sigurd"}), parsear_arma_string solo lo detecta a
    # partir del dict — con solo el string se pierde el grabado en silencio.
    parsed = parsear_arma_string(item_dict)
    arma_obj = None
    if parsed:
        arma_obj = Arma(
            nombre=parsed["nombre"],
            mt=parsed["mt"],
            wt=parsed["wt"],
            hit=parsed["hit"],
            crit=parsed["crit"],
            es_magica=parsed["es_magica"],
            tipo=parsed["tipo"],
            rango=inferir_rango_arma(parsed["nombre"], parsed["tipo"], parsed["rango"]),
            efectividades=parsed["efectividades"],
            avo_bonus=parsed["avo_bonus"],
            ddg_bonus=parsed["ddg_bonus"],
            es_smash=parsed.get("es_smash", False),
            sids=parsed.get("sids", []),
        )
    else:
        tipo_raw = item_dict.get("tipo", "Espada")
        TIPOS_VALIDOS = {'Espada', 'Hacha', 'Lanza', 'Artes', 'Arco', 'Tomo', 'Daga'}
        if tipo_raw in ("Bastón", "Objeto", "Accesorio", "Especial") or tipo_raw not in TIPOS_VALIDOS:
            return None

        es_smash = bool(item_dict.get("es_smash", False))
        if not es_smash:
            n_low = nombre_raw.lower()
            if any(w in n_low for w in ("blade", "gran espada", "greatlance", "gran lanza", "greataxe", "gran hacha", "georgios", "venomous", "ukonvasara", "carnwenhan", "aymr")):
                es_smash = True

        arma_obj = Arma(
            nombre=nombre_raw,
            mt=int(item_dict.get("mt", 0)),
            wt=int(item_dict.get("wt", 5)),
            hit=int(item_dict.get("hit", 80)),
            crit=int(item_dict.get("crit", 0)),
            es_magica=bool(item_dict.get("es_magica", False)),
            tipo=tipo_raw,
            rango=inferir_rango_arma(nombre_raw, tipo_raw, item_dict.get("rango")),
            efectividades=item_dict.get("efectividades", []),
            avo_bonus=int(item_dict.get("avo_bonus", 0)),
            ddg_bonus=int(item_dict.get("ddg_bonus", 0)),
            es_smash=es_smash,
            sids=list(item_dict.get("sids", []) or []),
        )

    if arma_obj:
        if item_dict.get("es_engage") or "(emblema)" in nombre_raw.lower():
            setattr(arma_obj, 'es_engage', True)
            if not arma_obj.nombre.endswith("(Emblema)"):
                arma_obj.nombre = f"{arma_obj.nombre} (Emblema)"

    return arma_obj

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
    # Las pasivas extra por dificultad (HardSids/LunaticSids, LunaticSkill de clase)
    # son solo de enemigos: un aliado nunca las recibe.
    dificultad = normalizar_texto(data.get("dificultad", "Extremo")).replace("?", "i") if not es_aliado else "normal"
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

    # Nivel de vínculo (1..20) y progresión canónica del Emblema
    nivel_vinculo = max(1, min(20, int(data.get("nivel_vinculo", getattr(unidad_previa, 'nivel_vinculo', 1) if unidad_previa else 1))))
    duracion_base = 4 if nivel_vinculo >= 11 else 3
    max_energia_emblema = 5 if nivel_vinculo >= 20 else 6
    if data.get("energia_emblema") is not None:
        energia_emblema_val = min(int(data["energia_emblema"]), max_energia_emblema)
    elif unidad_previa and getattr(unidad_previa, "energia_emblema", None) is not None:
        energia_emblema_val = min(int(unidad_previa.energia_emblema), max_energia_emblema)
    else:
        energia_emblema_val = max_energia_emblema
    # Emblema Oscuro (jefes): nivel de vínculo fijo 1 y sin fusión posible (EngageCount 0 en God.xml)
    es_emblema_oscuro = bool(emblema_info and emblema_info.get("es_oscuro"))
    if es_emblema_oscuro:
        nivel_vinculo = 1
        energia_emblema_val = 0
    # Como nunca entra en Fusión, lo que el juego le da "de Fusión" (armas de Emblema,
    # engage_skills y Ataque de Emblema) lo tiene puesto de forma permanente: Hyacinth
    # lleva la Mani Katti y la Killer Bow de Lyn y usa Call Doubles sin fusionarse.
    engage_permanente = es_emblema_oscuro
    bond_data = emblema_info.get("bond_levels", {}).get(str(nivel_vinculo)) if emblema_info else None
    emblem_mov = bond_data.get("stat_boosts", {}).get("mov", 0) if bond_data else (1 if es_sigurd else 0)

    # Stats base de la clase y Movimiento
    c_bases = clase_info.get("base_stats", {}) if clase_info else {}
    style = clase_info.get("estilo_combate", "") if clase_info else ""
    mov_base = clase_info.get("mov", 4) if clase_info else 4

    # Mov SIN Fusión: el guardado (`mov_base`), el TOTAL que trae el payload menos el
    # bono de Fusión (el modal muestra y reenvía el total), o el calculado. El bono de
    # las habilidades de Fusión (Gallop de Sigurd) se suma al final, cuando ya se sabe
    # si la unidad está fusionada y con qué estilo de combate.
    mov_total_explicito = None
    if data.get("mov_base") not in (None, "", 0):
        mov_sin_fusion = int(data["mov_base"])
    elif "mov" in data and data["mov"] is not None and str(data["mov"]).strip() != "":
        mov_sin_fusion = mov_total_explicito = int(data["mov"])
    else:
        mov_sin_fusion = mov_base + emblem_mov + (1 if tiene_botas else 0)
    mov = mov_sin_fusion

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
            # Misma regla que join_stats del catálogo (verificada contra las tablas
            # oficiales): base de clase + base personal + round-half-up(crecimiento
            # PERSONAL × niveles / 100), contando el nivel interno de la clase.
            lvl_diff = max(0, nivel - 1) + int(clase_info.get("internal_level", 0) if clase_info else 0)
            calc_hp  = c_bases.get("hp", 0)  + p_bases.get("hp", 20)  + round_half_up(p_growths.get("hp", 45) * lvl_diff / 100.0)
            calc_str = c_bases.get("str", 0) + p_bases.get("str", 6)  + round_half_up(p_growths.get("str", 30) * lvl_diff / 100.0)
            calc_mag = c_bases.get("mag", 0) + p_bases.get("mag", 0)  + round_half_up(p_growths.get("mag", 15) * lvl_diff / 100.0)
            calc_dex = c_bases.get("dex", 0) + p_bases.get("dex", 5)  + round_half_up(p_growths.get("dex", 35) * lvl_diff / 100.0)
            calc_spd = c_bases.get("spd", 0) + p_bases.get("spd", 6)  + round_half_up(p_growths.get("spd", 35) * lvl_diff / 100.0)
            calc_def = c_bases.get("def", 0) + p_bases.get("def", 5)  + round_half_up(p_growths.get("def", 25) * lvl_diff / 100.0)
            calc_res = c_bases.get("res", 0) + p_bases.get("res", 2)  + round_half_up(p_growths.get("res", 20) * lvl_diff / 100.0)
            calc_lck = c_bases.get("lck", 0) + p_bases.get("lck", 4)  + round_half_up(p_growths.get("lck", 25) * lvl_diff / 100.0)
            calc_bld = c_bases.get("bld", 0) + p_bases.get("bld", 5)  + round_half_up(p_growths.get("bld", 5)  * lvl_diff / 100.0)
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

        # En enemigos, los crecimientos de Person.xml son los de la unidad
        # jugable y no se aplican al cálculo de despliegues. El juego usa los
        # crecimientos de enemigo de la clase y el nivel interno de la clase.
        # Una clase avanzada de nivel 1 equivale a una básica de nivel 10;
        # el catálogo permite detectarlo sin una tabla de mapas hardcodeada.
        # Los personajes con nombre propio traen en Person.xml su tabla de
        # crecimientos completa. Los genéricos no tienen crecimientos
        # personales útiles y usan los de enemigo de Job.xml.
        usar_personales_enemigo = bool(not es_aliado and p_growths and any(v > 0 for v in p_growths.values()))
        if usar_personales_enemigo:
            final_growths = dict(p_growths)
        else:
            final_growths = {stat: c_growths.get(stat, 0) + (p_growths.get(stat, 0) if es_aliado else 0)
                             for stat in ["hp", "str", "mag", "dex", "spd", "def", "res", "lck", "bld"]}

        clase_internal = int(clase_info.get("internal_level", 0) if clase_info else 0)
        # El nivel interno de Job.xml ya expresa la equivalencia de clase
        # (una clase avanzada de nivel 1 tiene InternalLevel=20). No se debe
        # aproximar con los límites máximos de HP ni sumar 9 manualmente.
        # Las clases con InternalLevel usan su nivel interno como referencia
        # (nivel 1 avanzado equivale a nivel 20), mientras que las básicas
        # conservan la progresión normal del nivel mostrado.
        if clase_internal > 0:
            lvl_ups = max(0, nivel + clase_internal + auto_grow_extra - 2)
        else:
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

    # Bonos de estadísticas de Emblema según nivel de vínculo (o sobreescritura manual)
    emblem_stats = bond_data.get("stat_boosts", {}) if bond_data else {}
    bonos_a_aplicar = data.get("emblema_bonos") if data.get("emblema_bonos") is not None else emblem_stats
    for stat, bonus in (bonos_a_aplicar or {}).items():
        b_val = int(bonus)
        if stat == "hp": calc_hp += b_val
        elif stat in ("str", "fuerza"): calc_str += b_val
        elif stat in ("mag", "magia"): calc_mag += b_val
        elif stat in ("dex", "destreza"): calc_dex += b_val
        elif stat in ("spd", "velocidad"): calc_spd += b_val
        elif stat in ("def", "defensa"): calc_def += b_val
        elif stat in ("res", "resistencia"): calc_res += b_val
        elif stat in ("lck", "suerte"): calc_lck += b_val
        elif stat in ("bld", "complexion"): calc_bld += b_val

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

    # Comprobar si la unidad ya estaba en fusion activa previa
    estaba_en_fusion = bool(unidad_previa and (unidad_previa.en_fusion or getattr(unidad_previa, 'turnos_fusion', 0) > 0) and getattr(unidad_previa, 'turnos_fusion', 0) > 0)
    if estaba_en_fusion:
        # Una vez activada la fusion, no se puede retirar hasta que acaben los turnos
        en_fusion = True
        turnos_fusion = int(data.get("turnos_fusion", unidad_previa.turnos_fusion))
        if turnos_fusion <= 0:
            turnos_fusion = unidad_previa.turnos_fusion
        ataque_emblema_usado = getattr(unidad_previa, 'ataque_emblema_usado', False)
    else:
        en_fusion = bool(data.get("en_fusion", False)) or int(data.get("turnos_fusion", 0)) > 0
        if en_fusion:
            t_solicitados = int(data.get("turnos_fusion", 0))
            turnos_fusion = t_solicitados if t_solicitados > 0 else duracion_base
        else:
            turnos_fusion = 0
        ataque_emblema_usado = bool(data.get("ataque_emblema_usado", False))

    es_lord = data.get("es_lord", False) or "alear" in nombre.lower()

    tipo_mov_c = str(clase_info.get("tipo_movimiento", "")).lower() if clase_info else ""
    c_nombre_c = str(clase_info.get("nombre", "")).lower() if clase_info else ""
    c_jid_c = str(clase_id).lower()

    es_volador = (
        resolver_estilo_combate(style) == 'volador'
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

    # SIDs del Emblema para el motor de pasivas (pasivas.sids_activos): sincronía
    # según nivel de vínculo (siempre activa) y de Fusión (solo en Fusión).
    sids_emblema_sync = []
    sids_emblema_fusion = []
    if emblema_info:
        sync_passives = []
        if bond_data and "synchro_skills" in bond_data:
            for sk_item in bond_data["synchro_skills"]:
                if isinstance(sk_item, dict):
                    s_nom = sk_item.get("nombre") or sk_item.get("sid")
                    s_sid = sk_item.get("sid")
                else:
                    s_nom = str(sk_item)
                    s_sid = s_nom
                if s_nom and s_nom not in sync_passives:
                    sync_passives.append(s_nom)
                if s_sid and str(s_sid).startswith("SID_") and s_sid not in sids_emblema_sync:
                    sids_emblema_sync.append(s_sid)
        else:
            for sid in emblema_info.get("synchro_skills", []):
                sk_info = _catalogo.get("habilidades", {}).get(sid)
                s_nom = sk_info.get("nombre", sid) if sk_info else sid
                if s_nom and s_nom not in sync_passives:
                    sync_passives.append(s_nom)
                if str(sid).startswith("SID_") and sid not in sids_emblema_sync:
                    sids_emblema_sync.append(sid)

        for s_nom in sync_passives:
            if s_nom and s_nom not in habs_lista and not any(s_nom.startswith(pfx) for pfx in ["HP +", "Strength +", "Magic +", "Dexterity +", "Speed +", "Defense +", "Resistance +", "Res ", "Phy "]):
                habs_lista.append(s_nom)

        engage_items_bond = bond_data.get("engage_skills") if bond_data and "engage_skills" in bond_data else emblema_info.get("engage_skills", [])
        destino_engage = sids_emblema_sync if engage_permanente else sids_emblema_fusion
        for sk_item in engage_items_bond or []:
            s_sid = sk_item.get("sid") if isinstance(sk_item, dict) else sk_item
            if s_sid and str(s_sid).startswith("SID_") and s_sid not in destino_engage:
                destino_engage.append(s_sid)

    # Enriquecer habilidades personales y de clase desde el catálogo compilado
    sids_solo_motor = []   # SIDs que el motor necesita pero que el juego no muestra como pasivas
    if _catalogo:
        # p_info ya se resolvió arriba por pid o por nombre (las claves son PIDs, no nombres)
        p_canon = _catalogo.get("personajes", {}).get(pid) or p_info
        if p_canon:
            for sid in p_canon.get("common_sids", []):
                if sid not in habs_lista:
                    habs_lista.append(sid)
                s_nom = _catalogo.get("habilidades", {}).get(sid, {}).get("nombre")
                if s_nom and s_nom not in habs_lista:
                    habs_lista.append(s_nom)
            if dificultad in ("difícil", "dificil", "hard", "extremo", "lunatic", "maddening"):
                for sid in p_canon.get("hard_sids", []):
                    if sid not in habs_lista:
                        habs_lista.append(sid)
                    s_nom = _catalogo.get("habilidades", {}).get(sid, {}).get("nombre")
                    if s_nom and s_nom not in habs_lista:
                        habs_lista.append(s_nom)
            if dificultad in ("extremo", "lunatic", "maddening"):
                for sid in p_canon.get("lunatic_sids", []):
                    if sid not in habs_lista:
                        habs_lista.append(sid)
                    s_nom = _catalogo.get("habilidades", {}).get(sid, {}).get("nombre")
                    if s_nom and s_nom not in habs_lista:
                        habs_lista.append(s_nom)

        c_canon = _catalogo.get("clases", {}).get(clase_id) or _catalogo.get("clases", {}).get(normalizar_texto(clase_info.get("nombre", "") if clase_info else ""))
        if c_canon:
            if not estilo_combate or estilo_combate in ("Infantería", "infantería", "None", ""):
                estilo_combate = c_canon.get("estilo_combate", estilo_combate)
            # Innatas de la clase (Job.xml Skills) siempre; la habilidad de clase
            # (LearningSkill, p.ej. Run Through / Pass) y la extra de Extremo
            # (LunaticSkill) solo a partir del nivel en que la clase la aprende:
            # Nv 5 en clases base/avanzadas (MaxLevel 20) y Nv 25 en las especiales
            # (MaxLevel 40: Thief, Dancer, Fell Child…). Kagetsu Nv 1 no tiene Run
            # Through; Zelkov Thief Nv 11 no tiene Pass.
            if "skills_innatas" in c_canon:
                innatas = list(c_canon.get("skills_innatas") or [])
                aprendida = c_canon.get("learning_skill") or ""
            else:  # catálogo antiguo sin desglose
                innatas = list(c_canon.get("skills") or [])
                aprendida = ""
            nivel_hab_clase = int(c_canon.get("nivel_habilidad_clase", 5) or 5)
            # Las innatas de clase (Job.xml Skills: 鍵開け Lockpick, 踊り Dance) son
            # comandos, no pasivas: el juego no las lista en la unidad. Se guardan
            # solo como SID para el motor (habilidades_sids), no en la lista visible.
            for sid in innatas:
                if sid not in sids_solo_motor:
                    sids_solo_motor.append(sid)
            if aprendida and nivel >= nivel_hab_clase and aprendida not in habs_lista:
                habs_lista.append(aprendida)
            if dificultad in ("extremo", "lunatic", "maddening") and c_canon.get("lunatic_skill") and nivel >= nivel_hab_clase:
                ls = c_canon.get("lunatic_skill")
                if ls not in habs_lista:
                    habs_lista.append(ls)

    # Los SID se conservan internamente en los XML, pero la UI debe mostrar
    # el nombre traducido. Si existe traducción, no expongas el identificador
    # japonés como una segunda pasiva duplicada.
    # Se guarda una copia de los Sids crudos ANTES de traducir/filtrar: el
    # motor de combate (intérprete de Condition/Act*) necesita identificadores
    # deterministas, no los nombres mostrados en la UI.
    habs_sids_crudos = [str(h) for h in habs_lista if str(h).startswith("SID_")] + [s_ for s_ in sids_solo_motor if s_ not in habs_lista]
    # Sincronías del Emblema y habilidades escritas por nombre (heredadas,
    # roster, tests): también como SID, para que el motor de pasivas vea la
    # misma lista que el juego. Los nombres sin SID (DLC sin datamine) se
    # quedan solo en la lista visible.
    for s_sid in sids_emblema_sync:
        if s_sid not in habs_sids_crudos:
            habs_sids_crudos.append(s_sid)
    for habilidad in habs_lista:
        if str(habilidad).startswith("SID_"):
            continue
        s_sid = pasivas.resolver_nombre_a_sid(str(habilidad))
        # Las de Fusión del Emblema (p.ej. "Divine Speed" guardado en el roster
        # durante una Fusión) solo se activan en Fusión: van en la lista aparte.
        if s_sid and s_sid not in habs_sids_crudos and s_sid not in sids_emblema_fusion:
            habs_sids_crudos.append(s_sid)
    habilidades_limpias = []
    nombres_ocultos = {str(i.get("nombre")) for i in _catalogo.get("habilidades", {}).values() if i.get("oculta") and i.get("nombre")}
    for habilidad in habs_lista:
        valor = str(habilidad)
        if valor in nombres_ocultos:
            continue
        era_sid = valor.startswith("SID_")
        if valor.startswith("SID_"):
            info = _catalogo.get("habilidades", {}).get(valor)
            # Flags internos del datamine (sin nombre en Skill.xml): no son pasivas visibles
            if info and info.get("oculta"):
                continue
            traducida = info.get("nombre") if info else None
            valor = traducida or valor
        # Algunos registros canónicos no tienen traducción inglesa y dejan
        # el nombre japonés. No lo mostramos como si fuera una pasiva nueva.
        if re.search(r"[\u3040-\u30ff\u3400-\u9fff]", valor):
            continue
        if valor and valor not in habilidades_limpias:
            habilidades_limpias.append(valor)
    # Si la unidad tiene la versión + de una habilidad (p.ej. Weapon Sync+ a vínculo 18+),
    # la base sobra (suele venir arrastrada de un roster guardado con menos vínculo).
    con_plus = {v.rstrip("+＋") for v in habilidades_limpias if v.endswith(("+", "＋"))}
    habilidades_limpias = [v for v in habilidades_limpias if not (v in con_plus)]
    habs_lista = habilidades_limpias

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
        energia_emblema=energia_emblema_val,
        max_energia_emblema=max_energia_emblema,
        turnos_fusion_restantes=turnos_fusion if en_fusion else 0,
        es_dragon=(style == "Dragon" or "alear" in nombre.lower()),
        en_fusion=en_fusion,
        ataque_emblema_usado=ataque_emblema_usado,
        nivel_vinculo=nivel_vinculo,
        tipo_movimiento=tipo_movimiento,
        hp_max=calc_hp,
        habilidades=habs_lista,
        habilidades_sids=habs_sids_crudos,
        habilidades_sids_fusion=sids_emblema_fusion,
        emblema_nombre=emb_nom,
        estilo_combate=estilo_combate,
    )
    # SID del Ataque de Emblema (God.xml EngageAttack): pasivas.forma_ataque_emblema lo
    # lee para saber cuántos golpes da y a qué fracción de daño (Astra Storm, Lodestar…).
    setattr(stats_obj, 'sid_ataque_emblema', (emblema_info or {}).get("engage_attack", "") or "")
    genero_val = int(data.get("genero", 0) or (p_info.get("genero", p_info.get("gender", 0)) if p_info else 0) or 0)
    setattr(stats_obj, 'genero', genero_val)
    if not getattr(stats_obj, 'clase_nombre', ''):
        setattr(stats_obj, 'clase_nombre', clase_info.get("nombre", "") if clase_info else (data.get("clase_nombre") or ""))
    # Debilidades canónicas de la clase (Job.xml Attrs); si la clase no está en el
    # catálogo se deja sin marcar y calcular_efectividad usa la heurística por movimiento.
    if clase_info and "debilidades" in clase_info:
        setattr(stats_obj, 'debilidades', list(clase_info.get("debilidades") or []))
        setattr(stats_obj, 'debilidades_canonicas', True)
    setattr(stats_obj, 'pid', pid or (getattr(unidad_previa, 'pid', '') if unidad_previa else '') or (p_info.get("id", "") if p_info else ""))
    val_veneno = int(data.get("nivel_veneno", getattr(unidad_previa, 'nivel_veneno', 0) if unidad_previa else 0))
    # Jefe: flag del dispos (bit 16), nombre "(Boss)" o piedras resurrectoras; y si la
    # ficha ya era jefe, lo sigue siendo aunque el usuario le quite las piedras en el modal
    es_jefe_val = (
        bool(data.get("es_jefe", False))
        or nombre.lower().endswith("(boss)")
        or (int(data.get("hp_stock", 0)) > 0 and not bool(data.get("es_aliado", False)))
        or ("es_jefe" not in data and unidad_previa is not None and bool(getattr(unidad_previa, 'es_jefe', False)))
    )
    val_lider_3h = data.get("lider_tres_casas") or (getattr(unidad_previa, 'lider_tres_casas', None) if unidad_previa else "Dimitri") or "Dimitri"
    if val_lider_3h not in ("Edelgard", "Dimitri", "Claude"):
        val_lider_3h = "Dimitri"
    setattr(stats_obj, 'nivel_veneno', val_veneno)
    setattr(stats_obj, 'lider_tres_casas', val_lider_3h)
    setattr(stats_obj, 'es_jefe', es_jefe_val)
    setattr(stats_obj, 'nivel_interno_clase', int(clase_info.get('internal_level', 0) if clase_info else 0))

    # Resolver arma principal / inventario
    inventario_raw = list(data.get("inventario", []))
    inventario_resuelto = []
    arma_equipada = None

    arma_id_directa = data.get("arma_id") or data.get("arma_nombre") or data.get("arma")
    if arma_id_directa and not inventario_raw:
        inventario_raw = [{"arma": arma_id_directa, "equipada": True}]

    # Las armas de Emblema solo existen en el inventario DURANTE la Fusión (se
    # inyectan abajo). Fuera de ella se descartan aunque vengan en una partida
    # guardada: si no, el análisis las trataría como armas normales.
    if not en_fusion and not engage_permanente:
        inventario_raw = [
            it for it in inventario_raw
            if not ((isinstance(it, dict) and it.get("es_engage")) or (isinstance(it, str) and "(emblema)" in it.lower()))
        ]

    # Inyección de Fusión (Engage Mode) — y del Emblema Oscuro, que la tiene permanente
    if (en_fusion or engage_permanente) and emblema_info:
        if en_fusion:
            stats_obj.turnos_fusion_restantes = turnos_fusion
        
        # Armas y habilidades de Engage específicas para este nivel de vínculo
        b_items = None
        if bond_data and "engage_items" in bond_data:
            b_items = bond_data["engage_items"]
        elif emblema_info and "bond_levels" in emblema_info:
            disp = sorted([int(k) for k in emblema_info["bond_levels"].keys() if k.isdigit() and int(k) <= nivel_vinculo])
            if disp:
                b_items = emblema_info["bond_levels"][str(disp[-1])].get("engage_items")
        if b_items is not None:
            armas_engage_a_anadir = [it.get("iid") or it.get("nombre") if isinstance(it, dict) else it for it in b_items]
        else:
            armas_engage_a_anadir = []

        if bond_data and "engage_skills" in bond_data:
            skills_engage_a_anadir = [sk.get("nombre") or sk.get("sid") if isinstance(sk, dict) else sk for sk in bond_data["engage_skills"]]
        else:
            skills_engage_a_anadir = emblema_info.get("engage_skills", [])

        # Colapsar armas de Emblema repetidas ya presentes (p.ej. partidas guardadas con
        # "Failnaught (Claude) (Emblema)" y "Failnaught (Emblema)" a la vez)
        vistas_eng = set()
        inventario_dedup = []
        for it in inventario_raw:
            es_eng_it = (isinstance(it, dict) and it.get("es_engage")) or (isinstance(it, str) and "(emblema)" in it.lower())
            if es_eng_it:
                nom_it = (it.get("nombre_base") or it.get("nombre") or it.get("arma") or "") if isinstance(it, dict) else str(it)
                p_it = parsear_arma_string({"nombre": nom_it, "es_engage": True})
                clave_it = normalizar_texto(p_it["nombre_base"]) if p_it else normalizar_texto(nom_it)
                if clave_it in vistas_eng:
                    continue
                vistas_eng.add(clave_it)
            inventario_dedup.append(it)
        inventario_raw[:] = inventario_dedup

        # Añadir armas de Engage al inventario temporal distinguidas con (Emblema)
        for it_raw in armas_engage_a_anadir:
            iid = str(it_raw)
            w_info = (_catalogo.get("armas", {}) or {}).get(iid, {})
            nombre_base = w_info.get("nombre", iid)
            nombre_eng = nombre_base if nombre_base.endswith("(Emblema)") else f"{nombre_base} (Emblema)"
            # Deduplicar por arma base resuelta: el mismo Failnaught puede venir del
            # navegador como "Failnaught (Claude) (Emblema)", "Failnaught (Emblema)"…
            p_eng = parsear_arma_string({"nombre": nombre_base, "es_engage": True})
            base_eng_norm = normalizar_texto(p_eng["nombre_base"]) if p_eng else normalizar_texto(nombre_base)

            def _misma_arma_emblema(it):
                if isinstance(it, dict):
                    if it.get("id") == iid:
                        return True
                    nom_it = it.get("nombre_base") or it.get("nombre") or it.get("arma") or ""
                else:
                    nom_it = str(it)
                if nom_it in (iid, nombre_eng, nombre_base):
                    return True
                p_it = parsear_arma_string({"nombre": nom_it, "es_engage": True})
                return bool(p_it) and normalizar_texto(p_it["nombre_base"]) == base_eng_norm

            ya_esta = any(isinstance(it, dict) and it.get("id") == iid for it in inventario_raw) or any(
                _misma_arma_emblema(it)
                for it in inventario_raw
                if engage_permanente
                or (isinstance(it, dict) and it.get("es_engage"))
                or (isinstance(it, str) and "(emblema)" in it.lower())
            )
            if not ya_esta:
                inventario_raw.append({"arma": nombre_eng, "id": iid, "nombre": nombre_eng, "equipada": False, "es_engage": True})

        # Añadir habilidades de Engage
        habilidades_existentes = list(habs_lista)
        for sid in skills_engage_a_anadir:
            skill_info = _catalogo.get("habilidades", {}).get(sid)
            s_nom = skill_info.get("nombre", sid) if skill_info else sid
            if s_nom not in habilidades_existentes:
                habilidades_existentes.append(s_nom)

        habs_lista = habilidades_existentes
        data["habilidades"] = habilidades_existentes
        stats_obj.habilidades = list(habs_lista)

    re_usos = re.compile(r"^(.*?)(?:\s*(?:\((\d+)(?:\/\d+)?\)|x(\d+)))?\s*$")

    for item in inventario_raw:
        if isinstance(item, dict):
            aid = item.get("arma") or item.get("nombre") or item.get("id") or ""
            ref_i = item.get("refine_lvl", 0)
            grab_i = item.get("grabado", "")
            es_eq = bool(item.get("equipada", False))
            es_eng = bool(item.get("es_engage", False))
            usos_override = item.get("usos")
            # Si el dict trae forja o grabado pero no están en el string, anexarlos para el parseo
            if ref_i and f"+{ref_i}" not in str(aid):
                aid = f"{aid}+{ref_i}"
            if grab_i and f"({grab_i})" not in str(aid):
                aid = f"{aid} ({grab_i})"
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

        iid_item = item.get("id") if isinstance(item, dict) else None
        parsed_w = parsear_arma_string({"nombre": aid if aid else base_aid, "id": iid_item, "es_engage": es_eng}
                                       if iid_item else (aid if aid else base_aid))
        if parsed_w:
            tipo_w = parsed_w.get("tipo", "Espada")
            es_staff_o_item = str(tipo_w).lower() in ("bastón", "baston", "staff", "objeto", "accesorio", "item")
            usos_max = parsed_w.get("usos_max")
            usos_actual = usos_override if (usos_override is not None) else usos_max

            if es_staff_o_item:
                display_nombre = parsed_w["nombre_base"]
                es_eq = False  # Bastones y consumibles nunca se equipan como arma de combate
            else:
                display_nombre = parsed_w["nombre"]

            if es_eng and not display_nombre.endswith("(Emblema)"):
                display_nombre = f"{display_nombre} (Emblema)"

            item_dict = {
                "id": parsed_w["id"],
                "nombre": display_nombre,
                "arma": display_nombre,
                "nombre_base": parsed_w["nombre_base"],
                "refine_lvl": 0 if es_staff_o_item else parsed_w.get("refine_lvl", 0),
                "grabado": None if es_staff_o_item else parsed_w.get("grabado"),
                "tipo": tipo_w,
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

            if not es_staff_o_item and (es_eq or arma_equipada is None):
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
                tipo_w = ainfo.get("tipo", "Espada")
                es_staff_o_item = str(tipo_w).lower() in ("bastón", "baston", "staff", "objeto", "accesorio", "item")
                nombre_final = ainfo.get("nombre", "Arma")
                usos_max = ainfo.get("usos_max")
                usos_actual = usos_override if (usos_override is not None) else usos_max

                if es_staff_o_item:
                    display_nombre = nombre_final
                    es_eq = False
                else:
                    display_nombre = nombre_final

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
                    "tipo": tipo_w,
                    "mt": ainfo.get("mt", 5),
                    "wt": ainfo.get("wt", 5),
                    "hit": ainfo.get("hit", 80),
                    "crit": ainfo.get("crit", 0),
                    "rango": inferir_rango_arma(nombre_final, tipo_w, ainfo.get("rango")),
                    "es_magica": ainfo.get("es_magica", False),
                    "es_smash": es_smash_val,
                    "efectividades": ainfo.get("efectividades", ["volador"] if tipo_w == "Arco" else []),
                    "usos": usos_actual,
                    "usos_max": usos_max,
                    "es_engage": es_eng,
                    "equipada": es_eq,
                    "sids": list(ainfo.get("equip_sids", []) or []),
                }
                inventario_resuelto.append(item_dict)

                if not es_staff_o_item and (es_eq or arma_equipada is None):
                    arma_equipada = Arma(
                        nombre=display_nombre,
                        mt=ainfo.get("mt", 5),
                        wt=ainfo.get("wt", 5),
                        hit=ainfo.get("hit", 80),
                        crit=ainfo.get("crit", 0),
                        es_magica=ainfo.get("es_magica", False),
                        tipo=tipo_w,
                        rango=inferir_rango_arma(nombre_final, tipo_w, ainfo.get("rango")),
                        efectividades=ainfo.get("efectividades", []),
                        es_smash=es_smash_val,
                        sids=list(ainfo.get("equip_sids", []) or []),
                    )
            else:
                raw_tipo = item.get("tipo") if isinstance(item, dict) else None
                item_tipo = raw_tipo if raw_tipo else ("Objeto" if any(w in str(aid).lower() for w in ("pocion", "poción", "elixir", "antidoto", "antídoto", "objeto", "item")) else "Espada")
                es_staff_o_item = str(item_tipo).lower() in ("bastón", "baston", "staff", "objeto", "accesorio", "item")
                es_eq_val = False if es_staff_o_item else es_eq
                inventario_resuelto.append({
                    "nombre": aid,
                    "arma": aid,
                    "nombre_base": aid,
                    "tipo": item_tipo,
                    "usos": item.get("usos") if isinstance(item, dict) else None,
                    "usos_max": item.get("usos_max") if isinstance(item, dict) else None,
                    "equipada": es_eq_val,
                    "es_engage": es_eng,
                })
                if not es_staff_o_item and (es_eq_val or arma_equipada is None):
                    arma_equipada = Arma(
                        nombre=aid,
                        mt=5,
                        wt=5,
                        hit=80,
                        crit=0,
                        es_magica=False,
                        tipo=item_tipo,
                        rango=[1],
                        efectividades=[]
                    )

    if arma_equipada is None:
        arma_equipada = Arma("Espada de Hierro", mt=5, wt=5, hit=90, crit=0, es_magica=False, tipo="Espada", rango=[1], efectividades=[])

    # El inventario resuelto viaja con la Unidad: Adaptable (SID_順応) contraataca con
    # la mejor arma disponible, no con la equipada (ver motor_calculo.arma_de_respuesta).
    setattr(stats_obj, 'inventario', list(inventario_resuelto))

    # Identidad de la ficha (verde, fija, pendiente de unión): si el dato no viene
    # explícito (el modal solo envía stats/equipo), se conserva de la ficha previa.
    def _dato_o_previo(clave, defecto):
        if clave in data:
            return data[clave]
        return getattr(unidad_previa, clave, defecto) if unidad_previa else defecto
    es_verde = bool(_dato_o_previo("es_verde", False))
    union_pendiente = bool(_dato_o_previo("union_pendiente", False)) and bool(data.get("es_aliado", True))
    habla_con = list(_dato_o_previo("habla_con", []) or [])
    es_fijo = bool(_dato_o_previo("es_fijo", False)) or (es_verde and union_pendiente) or ("alear" in nombre.lower())

    hp_m = int(data.get("hp_max", calc_hp))
    hp_a = int(data.get("hp_actual", hp_m))
    if hp_a > hp_m:
        hp_a = hp_m

    es_viva = bool(data.get("viva", True)) and (hp_a > 0)
    if not es_viva:
        hp_a = 0

    if stats_obj:
        stats_obj.hp = hp_a
        stats_obj.hp_max = hp_m
        setattr(stats_obj, 'hp_actual', hp_a)

    ficha = FichaUnidad(
        nombre=nombre,
        es_aliado=es_aliado,
        es_verde=es_verde,
        union_pendiente=union_pendiente,
        habla_con=habla_con,
        es_fijo=es_fijo,
        x=x,
        y=y,
        stats=stats_obj,
        arma=arma_equipada,
        mov=mov,
        mov_base=mov_sin_fusion,
        es_volador=es_volador,
        viva=es_viva,
        hp_max=hp_m,
        hp_actual=hp_a,
        hp_stock=int(data.get("hp_stock", getattr(unidad_previa, 'hp_stock', 0) if unidad_previa else 0)),
        chain_guard_activo=bool(data.get("chain_guard_activo", getattr(unidad_previa, 'chain_guard_activo', True) if unidad_previa else True)),
        chain_guard_usado=bool(data.get("chain_guard_usado", getattr(unidad_previa, 'chain_guard_usado', False) if unidad_previa else False)),
        ha_actuado=ha_actuado,
        cargas_ruptura=cargas_ruptura,
        energia_emblema=energia_emblema_val,
        max_energia_emblema=max_energia_emblema,
        turnos_fusion=turnos_fusion,
        en_fusion=en_fusion,
        ataque_emblema_usado=ataque_emblema_usado,
        nivel_vinculo=nivel_vinculo,
        clase_id=clase_id,
        clase_nombre=clase_info.get("nombre", "") if clase_info else data.get("clase_nombre", ""),
        nivel=nivel,
        emblema_id=emblema_id,
        emblema_nombre=emblema_info.get("nombre", "") if emblema_info else data.get("emblema_nombre", ""),
        habilidades=habs_lista,
        habilidades_sids=habs_sids_crudos,
        inventario=inventario_resuelto,
        potenciadores_usados=list(data.get("potenciadores_usados", [])),
        boosts_fusion={k: int(v) for k, v in (data.get("boosts_fusion") or {}).items() if str(v).lstrip("-").isdigit() and int(v) != 0},
        nivel_veneno=val_veneno,
        lider_tres_casas=val_lider_3h,
        estilo_combate=estilo_combate,
        accion_turno=str(data.get("accion_turno", getattr(unidad_previa, 'accion_turno', "") if unidad_previa else "") or ""),
        dificultad=str(data.get("dificultad") or (getattr(unidad_previa, 'dificultad', "") if unidad_previa else "") or ""),
        estados_temporales=list(data.get("estados_temporales", getattr(unidad_previa, 'estados_temporales', []) if unidad_previa else []) or []),
    )
    setattr(ficha, 'genero', genero_val)
    setattr(ficha, 'emblema_oscuro', es_emblema_oscuro)
    setattr(ficha, 'pid', getattr(stats_obj, 'pid', '') or pid)
    if unidad_previa is not None and getattr(unidad_previa, 'es_refuerzo', False):
        ficha.es_refuerzo = True
    setattr(ficha, 'es_jefe', es_jefe_val)
    setattr(ficha, '_lider_tres_casas_explicito', 'lider_tres_casas' in data)
    setattr(ficha, '_chain_guard_activo_explicito', 'chain_guard_activo' in data)
    setattr(ficha, '_hp_stock_explicito', 'hp_stock' in data)
    setattr(ficha, '_energia_emblema_explicito', 'energia_emblema' in data)
    # Gallop (Sigurd) y cualquier otra habilidad de Fusión con bono de Mov: el Mov del
    # payload es el total que ve el jugador, así que el bono se descuenta de la base.
    if mov_total_explicito is not None:
        ficha.mov_base = max(1, mov_total_explicito - pasivas.bono_movimiento_fusion(ficha))
    ficha.actualizar_movimiento_fusion()
    return ficha
