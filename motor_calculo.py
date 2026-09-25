"""
Motor de Cálculo — FE Engage Tactical Assistant
Motor matemático determinista que replica las fórmulas exactas de Fire Emblem: Engage.
"""

import copy
import math
import unicodedata
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING
from constants import ESTILOS_COMBATE_ALIASES, ESTILOS_COMBATE_REGLAS
import condicion_dsl
import pasivas

def normalizar_texto(texto):
    """Elimina tildes y caracteres diacríticos para comparaciones robustas."""
    if not texto:
        return ""
    return unicodedata.normalize('NFKD', str(texto)).encode('ASCII', 'ignore').decode('utf-8').lower()


def _es_texto_japones(texto: str) -> bool:
    return any('぀' <= c <= '鿿' for c in texto)


def resolver_estilo_combate(valor) -> str:
    """
    Normaliza estilo_combate (JP crudo del datamine, o alias EN/ES usados en
    tests y datos legacy) a uno de los ids canónicos de ESTILOS_COMBATE_ALIASES.
    Devuelve "infanteria" si no reconoce ningún alias.

    Los alias JP se comparan contra el string crudo (normalizar_texto() usa
    encode('ASCII','ignore') y borraría los caracteres japoneses); los alias
    EN/ES se comparan sin acentos/mayúsculas.
    """
    raw = str(valor or "")
    for canon, aliases in ESTILOS_COMBATE_ALIASES.items():
        if any(a in raw for a in aliases if _es_texto_japones(a)):
            return canon
    v = normalizar_texto(raw)
    if v:
        for canon, aliases in ESTILOS_COMBATE_ALIASES.items():
            if any(normalizar_texto(a) in v for a in aliases if not _es_texto_japones(a)):
                return canon
    return "infanteria"

if TYPE_CHECKING:
    from motor_de_movimiento_y_amenaza import ContextoMapaEnemigo


# =============================================================================
# Estructuras de Datos
# =============================================================================

@dataclass
class Unidad:
    """Representa una unidad con sus estadísticas de combate."""
    nombre: str
    hp: int
    fuerza: int = 0        # STR - Fuerza física
    magia: int = 0         # MAG - Poder mágico
    destreza: int = 0      # DEX - Destreza / Habilidad
    velocidad: int = 0     # SPD - Velocidad
    defensa: int = 0       # DEF - Defensa física
    resistencia: int = 0   # RES - Resistencia mágica
    suerte: int = 0        # LCK - Suerte
    complexion: int = 5    # BLD - Complexión (Build)
    es_lord: bool = False  # True si su muerte causa Game Over inmediato (ej. Alear)
    energia_emblema: int = 6         # Cargas actuales de Fusión de Emblema (0 a max)
    max_energia_emblema: int = 6     # Límite para activar la Fusión (normalmente 6)
    turnos_fusion_restantes: int = 0 # >0 si la Fusión está activa actualmente
    es_dragon: bool = False          # Bonificación tipo Dragón (Alear)
    tiene_liberation: bool = False   # Espada Libération (+1 carga extra al derrotar enemigos)
    tipo_movimiento: str = "infantería"  # Uno de: infantería, caballería, volador, acorazado, dragón, monstruo
    hp_max: int = 0
    habilidades: list = field(default_factory=list)
    habilidades_sids: list = field(default_factory=list)  # Sids crudos (SID_...) para lookups deterministas por Condition/Act*
    habilidades_sids_fusion: list = field(default_factory=list)  # Sids de Fusión del Emblema: activos solo con en_fusion (ver pasivas.sids_activos)
    emblema_nombre: str = ""
    emblema: str = ""
    estilo_combate: str = "Infantería"  # De apoyo (Backup), Acorazado (Armored), Espía (Covert), Místico (Mystical), etc.
    bando: str = "aliado"
    es_volador: bool = False
    es_jefe: bool = False
    en_fusion: bool = False
    clase_nombre: str = ""
    nivel_veneno: int = 0
    ataque_emblema_usado: bool = False # True si ya ejecutó el ataque o técnica especial de Engage
    nivel_vinculo: int = 1             # Nivel de vínculo con el Emblema (>=11 otorga +1 turno de Fusión)
    genero: int = 0                    # Género canónico (Person.xml Gender: 1=Hombre, 2=Mujer)
    pid: str = ""                      # ID de Person.xml (ej. PID_リュール)
    estados_temporales: list = field(default_factory=list)  # Buffs "de 1 turno" activos (ver pasivas_temporales.py)

    def __post_init__(self):
        if self.hp_max <= 0:
            self.hp_max = self.hp
        if self.emblema and not self.emblema_nombre:
            self.emblema_nombre = self.emblema
        elif self.emblema_nombre and not self.emblema:
            self.emblema = self.emblema_nombre
QI_ADEPT_CLASSES = {
    'martial monk', 'martial master', 'dancer',
    'monk', 'monje', 'monje marcial', 'maestro marcial',
    'bailarín', 'bailarin', 'bailarina'
}


def es_unidad_qi_adept(ficha_o_stats) -> bool:
    """
    Determina si una unidad es de estilo Qi Adept (Adepto de Qi / 気功スタイル) en Fire Emblem Engage.
    Incluye: Martial Monk, Martial Master, Dancer (Bailarín) y cualquier unidad con estilo de combate Qi Adept.
    """
    if not ficha_o_stats:
        return False
    stats = getattr(ficha_o_stats, 'stats', ficha_o_stats)
    clase = str(getattr(ficha_o_stats, 'clase_nombre', '') or getattr(stats, 'clase_nombre', '') or '').lower().strip()
    estilo = str(getattr(stats, 'estilo_combate', '') or getattr(ficha_o_stats, 'estilo_combate', '') or '')
    nombre = str(getattr(ficha_o_stats, 'nombre', '') or getattr(stats, 'nombre', '') or '').lower().strip()

    # 1. Estilo de combate explícito (StyleName de Job.xml): es la fuente canónica.
    # Si la unidad trae estilo y NO es 気功, no es Qi Adept aunque el nombre de la
    # clase engañe (p.ej. "Swordmaster" contiene "master" pero es 連携/Backup).
    # "Infantería"/"None" son el placeholder por defecto de la herramienta, no un estilo real.
    if estilo and normalizar_texto(estilo) not in ('infanteria', 'none', 'infantry'):
        return resolver_estilo_combate(estilo) == 'qi_adept'

    # 2. Sin estilo: clases canónicas Qi Adept (palabras completas, no "master" suelto)
    if clase in QI_ADEPT_CLASSES or any(k in clase for k in ('martial monk', 'martial master', 'monje', 'maestro marcial', 'dancer', 'bailar', 'qi adept', 'adepto')):
        return True

    # 3. Comprobar personajes canónicos si no tienen clase asignada
    if any(k in nombre for k in ('framme', 'seadall')):
        return True

    return False


def inferir_rango_arma(nombre: str, tipo: str, rango_existente=None) -> list:
    """
    Garantiza el rango canónico estricto de las armas en Fire Emblem Engage:
    - Arcos (Bows): estrictamente [2] (o [2, 3] si es Longbow/Arco largo, o [1] si es Mini Bow/Arco corto).
      NUNCA [1] para arcos estándar (no pueden atacar ni contraatacar a distancia 1).
    - Jabalinas, Hachas arrojadizas y armas 1-2: estrictamente [1, 2].
    - Tomos mágicos: estrictamente [1, 2] (o [1, 2, 3] para Trueno/Thunder/Thoron, [3..7] Meteor).
    - Dagas: estrictamente [1, 2].
    - Armas cuerpo a cuerpo estándar: [1].
    """
    nom_low = (nombre or "").lower()
    tipo_low = (tipo or "").lower()

    # Rango canónico del datamine si el arma está en el catálogo (Failnaught 2-3,
    # Master Bow 1-2, Kard 1…). Import perezoso: catalogo_loader importa este módulo.
    try:
        from catalogo_loader import _rango_canonico_catalogo
        rango_cat = _rango_canonico_catalogo(nom_low)
        if rango_cat:
            return list(rango_cat)
    except Exception:
        pass

    # Arcos
    if tipo_low in ("arco", "bow") or any(b in nom_low for b in ("arco", "bow")):
        if "longbow" in nom_low or "largo" in nom_low:
            return [2, 3]
        if "mini" in nom_low or "corto" in nom_low:
            return [1]
        return [2]

    # Armas arrojadizas 1-2
    if any(w in nom_low for w in (
        "javelin", "jabalina", "hand axe", "hacha de mano", "tomahawk",
        "spear", "pica", "short spear", "levin", "espada trueno",
        "flame lance", "lanza de fuego", "hurricane", "hacha huracan", "hacha huracán"
    )):
        return [1, 2]

    # Tomos
    if tipo_low in ("tomo", "tome", "magia") or any(w in nom_low for w in (
        "fire", "fuego", "thunder", "trueno", "wind", "viento", "elfire",
        "elthunder", "elwind", "bolganone", "thoron", "excalibur", "surge",
        "elsurge", "shine", "fulgor", "nosferatu", "seraphim", "meteor", "obscurite"
    )):
        if any(th in nom_low for th in ("thunder", "trueno", "elthunder", "thoron")):
            return [1, 2, 3]
        if "meteor" in nom_low:
            return [3, 4, 5, 6, 7]
        if "surge" in nom_low or "oleada" in nom_low:
            return [1]
        return [1, 2]

    # Dagas
    if tipo_low in ("daga", "dagger", "knife", "cuchillo") or any(w in nom_low for w in (
        "daga", "dagger", "knife", "cuchillo", "stiletto", "misericorde", "cinquedea", "peshkatz", "carnwenhan"
    )):
        return [1, 2]

    if isinstance(rango_existente, (list, tuple)) and len(rango_existente) > 0 and list(rango_existente) != [1]:
        return list(rango_existente)

    return [1]


@dataclass
class Arma:
    """Representa un arma con sus estadísticas y propiedades."""
    nombre: str
    mt: int             # Might - Potencia
    wt: int = 0         # Weight - Peso
    hit: int = 80       # Precisión base
    crit: int = 0       # Crítico base
    es_magica: bool = False  # True = apunta a RES, False = apunta a DEF
    es_fisica: bool = True
    tipo: str = "Espada"     # Espada, Hacha, Lanza, Artes, Arco, Tomo, Daga
    rango: list = field(default_factory=lambda: [1])
    efectividades: list = field(default_factory=list)  # e.g. ["volador", "acorazado"]
    efectivo_contra: list = field(default_factory=list)
    avo_bonus: int = 0  # Bonus de Evasión (ej. Grabados de Emblema)
    ddg_bonus: int = 0  # Bonus de Esquive de Crítico (Dodge)
    es_smash: bool = False  # True si es arma pesada (Smash): ataca de segundo, sin follow-up, empuja 1 casilla
    # Cede el primer golpe y no permite seguimiento, pero NO empuja ni rompe por empuje:
    # los alientos de Tiki ("cannot follow up, or strike first if initiating combat").
    cede_iniciativa: bool = False
    sids: list = field(default_factory=list)  # SIDs que otorga el arma (Item.xml EquipSids): SID_２回行動 Brave, SID_追撃不可…

    @property
    def es_brave(self) -> bool:
        """Arma Brave (SID_２回行動): cada ataque del INICIADOR son dos golpes (12x2 cuenta como un ataque)."""
        return "SID_２回行動" in (self.sids or [])

    def __post_init__(self):
        if self.efectivo_contra and not self.efectividades:
            self.efectividades = list(self.efectivo_contra)
        elif self.efectividades and not self.efectivo_contra:
            self.efectivo_contra = list(self.efectividades)
        self.rango = inferir_rango_arma(self.nombre, self.tipo, self.rango)


@dataclass
class Terreno:
    """Bonificaciones defensivas y propiedades especiales de una casilla del mapa."""
    avo: int = 0                  # Bonus a Evasión (Avoid)
    dfn: int = 0                  # Bonus a Defensa (aplica a DEF y RES por igual)
    curacion_turno: int = 0       # HP curados al inicio/fin de turno (ej. +10 HP en casillas de curación)
    es_antirruptura: bool = False  # Inmunidad a Ruptura (Break) al defender en esta casilla
    es_recarga_emblema: bool = False # Casilla de Emblema (recarga al 100% la energía de fusión)
    coste_mov: int = 1
    nombre: str = "Llanura"
    caminable: bool = True
    volable: bool = True


# Reliquias de Houses Unite (Unión de Casas, Emblema DLC de las Tres Casas). Sus datos
# son los del datamine (Item.xml, armas de Byleth DLC: IID_ベレト_アイムール Mt 24 efectiva
# contra dragón, IID_ベレト_アラドヴァル Mt 14 con SID_オフェンス時武器攻撃力上昇 (+50 % de Mt
# al iniciar) e IID_ベレト_フェイルノート Mt 13 efectiva contra dragón y volador). Cada
# entrada lleva el estilo de combate al que el texto oficial le da +10 % de daño.
def _reliquias_houses_unite():
    from catalogo_loader import _catalogo
    armas_cat = (_catalogo or {}).get("armas", {})
    plan = (
        ("IID_ベレト_アイムール", "Aymr", 24, "Hacha", ["dragón"], False, "acorazado"),
        ("IID_ベレト_アラドヴァル", "Areadbhar", 14, "Lanza", [], True, "caballeria"),
        ("IID_ベレト_フェイルノート", "Failnaught", 13, "Arco", ["dragón", "volador"], False, "encubierto"),
    )
    salida = []
    for iid, nombre, mt_def, tipo_def, ef_def, x15, estilo in plan:
        info = armas_cat.get(iid) or {}
        arma = Arma(
            nombre=info.get("nombre") or nombre,
            mt=int(info.get("mt", mt_def)),
            wt=int(info.get("wt", 9)),
            hit=int(info.get("hit", 75)),
            crit=int(info.get("crit", 0)),
            tipo=info.get("tipo", tipo_def),
            rango=[1],
            efectividades=list(info.get("efectividades") or ef_def),
        )
        setattr(arma, 'mt_x15_al_iniciar', x15 or "SID_オフェンス時武器攻撃力上昇" in (info.get("equip_sids") or []))
        salida.append((arma, estilo))
    return tuple(salida)


RELIQUIAS_HOUSES_UNITE = None   # se construye al primer uso (el catálogo se carga después)


# =============================================================================
# Constantes del sistema de combate
# =============================================================================

TIPOS_ARMA_VALIDOS = {'Espada', 'Hacha', 'Lanza', 'Artes', 'Arco', 'Tomo', 'Daga'}

TRIANGULO_ARMAS = {
    'Espada': ['Hacha'],
    'Hacha': ['Lanza'],
    'Lanza': ['Espada'],
    'Artes': ['Arco', 'Tomo', 'Daga'],
}


# =============================================================================
# Sistema Canónico de Apoyos de Fire Emblem Engage (SupportCalculator)
# =============================================================================

# Categorías de Apoyo oficiales (Serenes Forest / Datamine)
# RANGOS: C, B, A (Entre aliados estrictamente no hay rango S)
CATEGORIAS_APOYO = {
    # Equilibrado (Balanced)
    "alear": "balanced", "lueur": "balanced",
    "chloé": "balanced", "chloe": "balanced",
    "citrinne": "balanced", "citrinica": "balanced",
    "kagetsu": "balanced", "merrin": "balanced", "lindon": "balanced",

    # Enfocado en Acierto (Hit-focused)
    "framme": "hit", "alcryst": "hit", "staluke": "hit",
    "jade": "hit", "zelkov": "hit", "panette": "hit",
    "rosado": "hit", "anna": "hit",

    # Enfocado en Crítico (Critical-focused)
    "clanne": "critical", "boucheron": "critical",
    "louis": "critical", "diamant": "critical",
    "bunet": "critical", "timerra": "critical",
    "seadall": "critical", "jean": "critical",

    # Enfocado en Evasión (Avoid-focused)
    "vander": "avoid", "alfred": "avoid",
    "yunaka": "avoid", "amber": "avoid",
    "fogado": "avoid", "hortensia": "avoid", "saphir": "avoid",

    # Enfocado en Esquive de Crítico (Dodge-focused)
    "etie": "dodge", "céline": "dodge", "celine": "dodge",
    "lapis": "dodge", "ivy": "dodge", "pandreo": "dodge",
    "goldmary": "dodge", "veyle": "dodge",
}

TABLA_BONOS_APOYO = {
    "balanced": {
        "C": {"hit": 10, "avo": 5, "crit": 0, "ddg": 0},
        "B": {"hit": 10, "avo": 5, "crit": 3, "ddg": 0},
        "A": {"hit": 10, "avo": 5, "crit": 3, "ddg": 5},
    },
    "hit": {
        "C": {"hit": 15, "avo": 0, "crit": 0, "ddg": 0},
        "B": {"hit": 15, "avo": 5, "crit": 0, "ddg": 0},
        "A": {"hit": 20, "avo": 5, "crit": 0, "ddg": 0},
    },
    "critical": {
        "C": {"hit": 10, "avo": 0, "crit": 3, "ddg": 0},
        "B": {"hit": 10, "avo": 0, "crit": 3, "ddg": 5},
        "A": {"hit": 10, "avo": 0, "crit": 6, "ddg": 5},
    },
    "avoid": {
        "C": {"hit": 10, "avo": 5, "crit": 0, "ddg": 0},
        "B": {"hit": 10, "avo": 5, "crit": 3, "ddg": 0},
        "A": {"hit": 10, "avo": 10, "crit": 3, "ddg": 0},
    },
    "dodge": {
        "C": {"hit": 10, "avo": 0, "crit": 0, "ddg": 5},
        "B": {"hit": 15, "avo": 0, "crit": 0, "ddg": 5},
        "A": {"hit": 15, "avo": 0, "crit": 0, "ddg": 10},
    },
    "default": {
        "C": {"hit": 10, "avo": 0, "crit": 0, "ddg": 0},
        "B": {"hit": 10, "avo": 0, "crit": 0, "ddg": 0},
        "A": {"hit": 10, "avo": 0, "crit": 0, "ddg": 0},
    }
}

def obtener_genero_unidad(u) -> int:
    """
    1: Masculino, 2: Femenino, 0: Indeterminado.
    Prioriza el valor canónico del datamine Person.xml ('Gender').
    """
    gen = getattr(u, 'genero', None) or getattr(getattr(u, 'stats', None), 'genero', None)
    if gen in (1, 2):
        return gen

    pid = getattr(u, 'pid', None) or getattr(getattr(u, 'stats', None), 'pid', None)
    if pid:
        try:
            from catalogo_loader import _catalogo
            p_cat = _catalogo.get("personajes", {}).get(pid)
            if p_cat and p_cat.get("genero") in (1, 2):
                return p_cat["genero"]
        except Exception:
            pass

    nom = (getattr(u, 'nombre', '') or '').lower()
    pid_str = (str(pid) or '').lower()
    females = {
        'céline', 'celine', 'chloé', 'chloe', 'yunaka', 'citrinne', 'citrinica',
        'lapis', 'framme', 'etie', 'ivy', 'hortensia', 'timerra', 'panette',
        'merrin', 'goldmary', 'veyle', 'anna', 'jade', 'saphir', 'lumera'
    }
    males = {
        'alfred', 'louis', 'boucheron', 'clanne', 'vander', 'alcryst', 'staluke',
        'diamant', 'amber', 'fogado', 'pandreo', 'bunet', 'seadall', 'kagetsu',
        'zelkov', 'lindon', 'mauvier', 'jean', 'rosado', 'morion', 'hyacinth'
    }
    if any(f in nom or f in pid_str for f in females):
        return 2
    if any(m in nom or m in pid_str for m in males):
        return 1
    if 'alear' in nom or 'lueur' in nom:
        return getattr(u, 'genero', 1)
    return 0

def distancia_entre_unidades(u1, u2) -> int:
    """Distancia Manhattan entre dos unidades u objetos con x, y."""
    x1, y1 = getattr(u1, 'x', 0), getattr(u1, 'y', 0)
    x2, y2 = getattr(u2, 'x', 0), getattr(u2, 'y', 0)
    return abs(x1 - x2) + abs(y1 - y2)

def obtener_rango_apoyo(u1, u2) -> str:
    """Devuelve 'C', 'B', 'A' o '' si no hay apoyo activo entre u1 y u2."""
    nom1 = (getattr(u1, 'nombre', '') or '').lower()
    nom2 = (getattr(u2, 'nombre', '') or '').lower()
    
    # Comprobar si hay apoyos explícitos definidos en el objeto u1 o u2
    apoyos1 = getattr(u1, 'apoyos', None) or {}
    if isinstance(apoyos1, dict):
        for k, v in apoyos1.items():
            if k.lower() in nom2 or nom2 in k.lower():
                r = str(v).upper()
                if r in ("C", "B", "A"):
                    return r

    apoyos2 = getattr(u2, 'apoyos', None) or {}
    if isinstance(apoyos2, dict):
        for k, v in apoyos2.items():
            if k.lower() in nom1 or nom1 in k.lower():
                r = str(v).upper()
                if r in ("C", "B", "A"):
                    return r

    # Apoyos canónicos activos iniciales (Rango C) en Chapter 7
    firene_vassals = {'alfred', 'céline', 'celine', 'chloé', 'chloe', 'louis', 'framme', 'clanne', 'vander', 'etie', 'boucheron'}
    if ('alear' in nom1 and any(v in nom2 for v in firene_vassals)) or ('alear' in nom2 and any(v in nom1 for v in firene_vassals)):
        return 'C'

    brodia_trio = {'alcryst', 'citrinne', 'citrinica', 'lapis'}
    if any(b in nom1 for b in brodia_trio) and any(b in nom2 for b in brodia_trio):
        return 'C'

    return ''

def normalizar_aliados_cercanos(aliados, pos_ref):
    """
    Convierte cualquier formato de lista de aliados a una lista normalizada de (unidad, distancia).
    Soporta tuplas (unidad, dist) o instancias de Ficha/Unidad con .x y .y.
    """
    res = []
    if not aliados:
        return res
    for item in aliados:
        if isinstance(item, (list, tuple)) and len(item) == 2 and isinstance(item[1], (int, float)):
            res.append((item[0], int(item[1])))
        elif hasattr(item, 'x') and hasattr(item, 'y') and pos_ref:
            d = abs(item.x - pos_ref[0]) + abs(item.y - pos_ref[1])
            res.append((item, d))
        else:
            res.append((item, 1))
    return res

def calcular_bonos_apoyo(unidad, aliados_cercanos):
    """
    Calcula la suma de bonos de apoyo de hasta 4 aliados adyacentes (distancia == 1).
    Solo rangos C, B, A (entre aliados no existe rango S).
    """
    total_hit = 0
    total_avo = 0
    total_crit = 0
    total_ddg = 0
    aliados_apoyo_contados = 0
    detalles = []

    if not aliados_cercanos:
        return total_hit, total_avo, total_crit, total_ddg, detalles

    nom_self = (getattr(unidad, 'nombre', '') or '').lower()

    for aliado, dist in aliados_cercanos:
        if dist != 1:
            continue
        nom_aliado = (getattr(aliado, 'nombre', '') or '').lower()
        if nom_aliado == nom_self:
            continue
        if aliados_apoyo_contados >= 4:
            break
            
        rango = obtener_rango_apoyo(unidad, aliado)
        if rango in ("C", "B", "A"):
            cat = "default"
            for k, c in CATEGORIAS_APOYO.items():
                if k in nom_aliado:
                    cat = c
                    break
            bono = TABLA_BONOS_APOYO.get(cat, TABLA_BONOS_APOYO["default"]).get(rango, {})
            b_hit = bono.get("hit", 0)
            b_avo = bono.get("avo", 0)
            b_crit = bono.get("crit", 0)
            b_ddg = bono.get("ddg", 0)
            
            total_hit += b_hit
            total_avo += b_avo
            total_crit += b_crit
            total_ddg += b_ddg
            aliados_apoyo_contados += 1
            detalles.append({
                "aliado": getattr(aliado, 'nombre', 'Aliado'),
                "rango": rango,
                "categoria": cat,
                "hit": b_hit, "avo": b_avo, "crit": b_crit, "ddg": b_ddg
            })

    return total_hit, total_avo, total_crit, total_ddg, detalles


# =============================================================================
# Motor de Cálculo
# =============================================================================

# Adaptable (SID_順応): habilidad de Fusión del Emblema de Leif. Skill.xml no la
# describe con Acts porque la resuelve el motor del juego; el texto oficial dice que
# al ser atacada la unidad contraataca con la mejor arma que tenga disponible.
SID_ADAPTABLE = "SID_順応"


def arma_de_respuesta(defensor, arma_def, distancia, atacante=None):
    """
    Arma con la que el DEFENSOR responde a `distancia`. Normalmente la que lleva
    equipada; con Adaptable (SID_順応, habilidad de Emblema de Leif: "If foe initiates
    combat, unit counters with the best weapon available (in terms of range, weapon
    advantage, effective bonus, etc.)") el juego elige la mejor de su inventario que
    alcance. Devuelve (arma, cambiada).
    """
    inventario = getattr(defensor, 'inventario', None) or []
    if not inventario or not pasivas.tiene_sid(defensor, SID_ADAPTABLE):
        return arma_def, False
    candidatas = []
    for item in inventario:
        if not isinstance(item, dict):
            continue
        if str(item.get("tipo", "")) in ("Bastón", "Objeto", "Accesorio"):
            continue
        a = _arma_desde_item_seguro(item)
        if a is None or a.mt <= 0 or distancia not in (a.rango or [1]):
            continue
        candidatas.append((_valor_de_respuesta(a, defensor, atacante), a.nombre == getattr(arma_def, 'nombre', ''), a))
    if not candidatas:
        return arma_def, False
    mejor = max(candidatas)[2]
    return mejor, mejor.nombre != getattr(arma_def, 'nombre', '')


def _valor_de_respuesta(arma, defensor, atacante) -> float:
    """Daño esperado aproximado (daño neto × precisión) con el que se compara qué arma
    es "la mejor disponible": cubre alcance, efectividad y triángulo de armas."""
    mult = 1.0
    if atacante is not None:
        mult, _ = CalculadoraEngage.calcular_efectividad(arma, atacante)
    ofensiva = getattr(defensor, 'magia', 0) if arma.es_magica else getattr(defensor, 'fuerza', 0)
    if atacante is None:
        return (ofensiva + arma.mt * mult) * max(0.01, arma.hit / 100.0)
    defensiva = getattr(atacante, 'resistencia', 0) if arma.es_magica else getattr(atacante, 'defensa', 0)
    arma_rival = getattr(atacante, 'arma', None)
    tipo_rival = getattr(arma_rival, 'tipo', None) if arma_rival else None
    # La ventaja de triángulo rompe al rival: pesa más que unos puntos de daño
    bono_tri = 3 if CalculadoraEngage.ventaja_triangulo(arma.tipo, tipo_rival) else 0
    daño = max(0.0, ofensiva + arma.mt * mult - defensiva) + bono_tri
    return daño * max(0.01, arma.hit / 100.0)


def _arma_desde_item_seguro(item):
    """Arma a partir de un dict de inventario ya resuelto, sin volver al catálogo."""
    try:
        return Arma(
            nombre=item.get("nombre") or item.get("arma") or "Arma",
            mt=int(item.get("mt", 0) or 0), wt=int(item.get("wt", 0) or 0),
            hit=int(item.get("hit", 0) or 0), crit=int(item.get("crit", 0) or 0),
            tipo=item.get("tipo", "Espada"), rango=list(item.get("rango") or [1]),
            es_magica=bool(item.get("es_magica", False)),
            efectividades=list(item.get("efectividades") or []),
            avo_bonus=int(item.get("avo_bonus", 0) or 0), ddg_bonus=int(item.get("ddg_bonus", 0) or 0),
        )
    except Exception:
        return None


class CalculadoraEngage:
    """
    Motor matemático determinista.
    Replica las fórmulas exactas de Fire Emblem: Engage.
    """

    # ── Fórmulas base ───────────────────────────────────────────────────

    @staticmethod
    def calcular_velocidad_ataque(spd, bld, wt):
        """
        Calcula el Attack Speed (AS).
        El peso del arma (wt) resta velocidad solo si supera la Complexión (bld).
        """
        return spd - max(0, wt - bld)

    @staticmethod
    def calcular_hit(dex, lck, weapon_hit):
        """Calcula el Hit (Precisión máxima) del atacante."""
        return weapon_hit + (2 * dex) + math.floor(lck / 2)

    @staticmethod
    def calcular_avoid(as_val, lck, terreno_avo=0):
        """Calcula el Avoid (Evasión máxima) del defensor."""
        return (2 * as_val) + math.floor(lck / 2) + terreno_avo

    @staticmethod
    def calcular_crit(dex, weapon_crit):
        """Calcula la probabilidad de Crítico."""
        return weapon_crit + math.floor(dex / 2)

    @staticmethod
    def calcular_dodge(lck):
        """Calcula el Dodge (Evasión de críticos)."""
        return lck

    @staticmethod
    def ventaja_triangulo(tipo_atk, tipo_def):
        """
        Evalúa el Triángulo de Armas de Engage.
        Retorna True si el atacante tiene ventaja.
        """
        if not tipo_def:
            return False
        return tipo_def in TRIANGULO_ARMAS.get(tipo_atk, [])

    # ── Cálculos intermedios ────────────────────────────────────────────

    @staticmethod
    def calcular_efectividad(arma_atk: 'Arma', defensor: 'Unidad') -> tuple:
        """
        Calcula el multiplicador de efectividad del arma contra el defensor.
        En Fire Emblem Engage, la efectividad triplica el poder del arma (Weapon Mt × 3).
        Retorna (multiplicador_mt: int, descripción_str: Optional[str]).
        """
        if not arma_atk.efectividades:
            return 1, None

        tipo_mov = str(getattr(defensor, 'tipo_movimiento', 'infantería')).lower()
        estilo_canon = resolver_estilo_combate(getattr(defensor, 'estilo_combate', ''))
        es_dragon = getattr(defensor, 'es_dragon', False)

        # Debilidades canónicas de la clase (Job.xml Attrs → catálogo `debilidades`):
        # si están disponibles mandan sobre la heurística por tipo de movimiento.
        # P.ej. Lindwurm/Wyvern Knight (Attrs 8+16) es volador pero NO débil a arcos
        # (verificado en el juego con Ivy), solo a armas anti-dragón.
        debilidades = getattr(defensor, 'debilidades', None)
        if debilidades is not None and isinstance(debilidades, (list, tuple, set)) and getattr(defensor, 'debilidades_canonicas', False):
            deb = {str(d).lower() for d in debilidades}
            _ALIAS = {
                "volador": ("volador", "flier", "flying"),
                "acorazado": ("acorazado", "armored", "armor"),
                "caballería": ("caballería", "caballeria", "cavalry", "horse"),
                "dragón": ("dragón", "dragon"),
                "dragón caído": ("dragón caído", "dragon caido", "fell dragon", "邪竜"),
                "abominación": ("abominación", "abominacion", "corrupto", "monstruo", "corrupted", "異形"),
            }
            for eff in arma_atk.efectividades:
                eff_l = str(eff).lower()
                for canon, alias in _ALIAS.items():
                    if eff_l in alias and canon in deb:
                        return 3, f"Efectividad anti-{canon} (Mt ×3)"
            return 1, None

        for eff in arma_atk.efectividades:
            eff_l = str(eff).lower()
            if eff_l in ("volador", "flier", "flying"):
                if tipo_mov in ("volador", "flier", "flying") or estilo_canon == 'volador':
                    return 3, "Efectividad anti-volador (Mt ×3)"
            elif eff_l in ("acorazado", "armored", "armor"):
                if tipo_mov in ("acorazado", "armored", "armor") or estilo_canon == 'acorazado':
                    return 3, "Efectividad anti-acorazado (Mt ×3)"
            elif eff_l in ("caballería", "caballeria", "cavalry", "horse"):
                if tipo_mov in ("caballería", "caballeria", "cavalry", "horse") or estilo_canon == 'caballeria':
                    return 3, "Efectividad anti-caballería (Mt ×3)"
            elif eff_l in ("dragón", "dragon"):
                if es_dragon or tipo_mov in ("dragón", "dragon") or estilo_canon == 'dragon':
                    return 3, "Efectividad anti-dragón (Mt ×3)"
            elif eff_l in ("corrupto", "monstruo", "corrupted"):
                if tipo_mov in ("monstruo", "corrupto", "corrupted"):
                    return 3, "Efectividad anti-corrupto (Mt ×3)"
            elif eff_l == tipo_mov:
                return 3, f"Efectividad anti-{eff} (Mt ×3)"

        return 1, None

    _CAMPOS_STAT_BOOST = {
        "str": "fuerza", "mag": "magia", "dex": "destreza", "spd": "velocidad",
        "def": "defensa", "res": "resistencia", "lck": "suerte", "bld": "complexion",
    }

    @classmethod
    def _con_estados_temporales(cls, unidad):
        """
        Devuelve una copia superficial de `unidad` con los stat_boosts de sus
        estados temporales (buffs "de 1 turno") ya sumados, más una lista
        `_desc_estados_temporales` para documentarlos en pasivas_activas.
        Si no tiene estados activos devuelve la misma instancia sin tocar.
        """
        estados = list(getattr(unidad, 'estados_temporales', None) or [])
        # Rise Above (Roy, SID_超越): mientras la unidad está fusionada con Roy sube
        # 5 niveles → stats según sus crecimientos (personaje + clase). No se guarda
        # en la ficha: es un bono de fusión, como los estados de 1 turno.
        en_fusion_u = bool(getattr(unidad, 'en_fusion', False)) or int(getattr(unidad, 'turnos_fusion_restantes', 0) or 0) > 0
        tiene_rise_above = pasivas.tiene_sid(unidad, 'SID_超越')
        manuales = dict(getattr(unidad, 'boosts_fusion', None) or {})
        if en_fusion_u and not getattr(unidad, '_rise_above_aplicado', False):
            if manuales:
                # Bono de fusión anotado por el usuario (valores reales vistos en el juego)
                estados.append({"nombre": "Bono de Fusión (observado)", "stat_boosts": manuales, "_rise_above": True})
            elif tiene_rise_above:
                try:
                    from catalogo_loader import boosts_rise_above
                    b = boosts_rise_above(getattr(unidad, 'nombre', ''), getattr(unidad, 'clase_nombre', ''))
                except Exception:
                    b = {}
                if b:
                    estados.append({"nombre": "Superación (Roy, Nv+5, estimado)", "stat_boosts": b, "_rise_above": True})
        if not estados:
            return unidad
        u = copy.copy(unidad)
        u._rise_above_aplicado = True
        descs = []
        for est in estados:
            partes = []
            for k, v in (est.get("stat_boosts") or {}).items():
                if k == "hp" and est.get("_rise_above"):
                    # Rise Above también sube el HP máximo (y el actual en la misma cuantía)
                    u.hp_max = int(getattr(u, 'hp_max', 0) or 0) + int(v)
                    u.hp = int(getattr(u, 'hp', 0) or 0) + int(v)
                    if getattr(u, 'hp_actual', None) is not None:
                        u.hp_actual = int(u.hp_actual) + int(v)
                    partes.append(f"+{int(v)} HP")
                    continue
                campo = cls._CAMPOS_STAT_BOOST.get(k)
                if not campo or not v:
                    continue
                setattr(u, campo, getattr(u, campo, 0) + int(v))
                partes.append(f"{'+' if int(v) > 0 else ''}{int(v)} {campo.capitalize()}")
            if partes:
                descs.append(f"{est.get('nombre', est.get('sid', 'Estado temporal'))} ({', '.join(partes)})")
        u._desc_estados_temporales = descs
        return u

    @staticmethod
    def _es_volador(unidad) -> bool:
        return bool(
            getattr(unidad, 'es_volador', False)
            or str(getattr(unidad, 'tipo_movimiento', '') or '').lower() in ('volador', 'flier', 'flying')
            or resolver_estilo_combate(getattr(unidad, 'estilo_combate', '')) == 'volador'
        )

    @classmethod
    def _stats_de_golpe(
        cls,
        atacante,
        arma,
        defensor,
        arma_def,
        terreno,
        es_iniciador: bool = True,
        aliados_cercanos_atk=None,
        aliados_cercanos_def=None,
        distancia: int = 1,
        es_engage_attack: bool = False,
        engage_attack_nombre: str = "",
        defensor_en_ruptura: bool = False,
        terreno_atacante=None,
        rival_contraataca=None,
        chain_attacks: int = 0,
        ronda: int = 0,
    ):
        """
        Estadísticas de un golpe individual del atacante al defensor.

        Las pasivas salen del motor genérico (pasivas.recopilar_combate: Skill.xml
        Condition/Act* de los SIDs activos de cada bando, SyncSids, auras de los
        aliados cercanos y overlay DLC). Aquí solo se SUMAN sus modificadores en el
        orden del cálculo del juego; no hay comprobaciones por nombre de habilidad.
        Fuera del motor genérico quedan las reglas de estilo/terreno, la efectividad
        (Item.xml) y los Ataques de Emblema con geometría propia (Houses Unite,
        Lodestar Rush, Warp Ragnarök).

        `terreno`           terreno del DEFENSOR de este golpe (Avo/Def que recibe).
        `terreno_atacante`  terreno propio del atacante (Trained to Kill…); None = llano.
        `rival_contraataca` si el defensor puede devolver el golpe (相手の手番回数);
                            None = se deduce de arma_def/distancia.
        `chain_attacks`     Chain Attacks de apoyo que acompañan al atacante (チェインアタック回数).
        `ronda`             Rondas de ataque YA ejecutadas (総手番回数 / 総行動回数): 0 en el
                            primer golpe, 1 en el follow-up. Las pasivas cuya Condition lo
                            mira solo valen en la ronda que les toca — Momentum (SID_助走:
                            "移動距離 > 0 && 総行動回数 == 0") solo suma en el primer golpe.
        """
        estilo_atk_canon = resolver_estilo_combate(getattr(atacante, 'estilo_combate', ''))
        estilo_def_canon = resolver_estilo_combate(getattr(defensor, 'estilo_combate', ''))
        T = pasivas.TIMINGS_GOLPE_ESTATICO

        # Ballesta / cañón de mapa (verificado en el juego): las pasivas EXTERNAS de otras
        # unidades (Guía Divina de Alear, Gente de Cuento, apoyos, Solidaridad…) no se
        # aplican al disparo. Los bonos propios ya sumados a los stats (¡Ponte detrás
        # de mí!, potenciadores) sí cuentan. Se vacía la lista de aliados cercanos.
        if getattr(arma, 'es_ballesta', False):
            aliados_cercanos_atk = []

        # ── Terreno ─────────────────────────────────────────────────────────
        terreno_avo = terreno.avo
        terreno_dfn = terreno.dfn
        # Estilo Volador (飛行): no recibe bonos de Avo/Def del terreno (evasión, curación, bosque…)
        if cls._es_volador(defensor):
            terreno_avo = 0
            terreno_dfn = 0
        terreno_atacante = terreno_atacante or Terreno()
        terreno_propio_atk = Terreno(avo=0, dfn=0) if cls._es_volador(atacante) else terreno_atacante
        terreno_efectivo_def = Terreno(avo=terreno_avo, dfn=terreno_dfn,
                                       curacion_turno=getattr(terreno, 'curacion_turno', 0),
                                       es_antirruptura=getattr(terreno, 'es_antirruptura', False))

        if rival_contraataca is None:
            rival_contraataca = bool(arma_def is not None and distancia in getattr(arma_def, 'rango', [1])
                                     and not es_engage_attack and not defensor_en_ruptura
                                     and not getattr(arma, 'es_ballesta', False))

        # ── Contextos de la DSL (uno por bando) ─────────────────────────────
        ctx_atk = condicion_dsl.ContextoCombate(
            unidad=atacante, rival=defensor, es_iniciador=es_iniciador,
            arma=arma, arma_rival=arma_def,
            terreno_propio=terreno_propio_atk, terreno_rival=terreno_efectivo_def,
            aliados_cercanos=aliados_cercanos_atk or [],
            habilidades_sids=pasivas.sids_activos(atacante) + list(getattr(arma, 'sids', None) or []),
            turno_actual=1, turno_total=int(ronda or 0), rondas_rival=1 if rival_contraataca else 0,
            rol="atacante" if es_iniciador else "defensor", rol_rival="defensor" if es_iniciador else "atacante",
            chain_attacks=int(chain_attacks or 0),
        )
        ctx_def = condicion_dsl.ContextoCombate(
            unidad=defensor, rival=atacante, es_iniciador=not es_iniciador,
            arma=arma_def, arma_rival=arma,
            terreno_propio=terreno_efectivo_def, terreno_rival=terreno_propio_atk,
            aliados_cercanos=aliados_cercanos_def or [],
            habilidades_sids=pasivas.sids_activos(defensor) + list(getattr(arma_def, 'sids', None) or []),
            turno_actual=1 if rival_contraataca else 0, rondas_rival=1,
            rol="defensor" if es_iniciador else "atacante", rol_rival="atacante" if es_iniciador else "defensor",
        )

        # Efectividad (Item.xml): triplica el Mt. Se calcula antes para que el
        # defensor pueda reaccionar (Stalwart: 相手の武器特効 > 1 → = 2).
        mult_mt_efectividad, desc_efectividad = cls.calcular_efectividad(arma, defensor)
        ctx_def.mult_efectividad_rival = mult_mt_efectividad

        mods_atk = pasivas.recopilar_combate(atacante, ctx_atk, aliados_cercanos_atk)
        mods_def = pasivas.recopilar_combate(defensor, ctx_def, aliados_cercanos_def)

        # Veteran+ (SID_特効無効_効果): inmune a la efectividad; Stalwart / Veteran
        # (SID_特効耐性_効果: "相手の武器特効 = 2"): la reduce a ×2. Se aplica a cualquier
        # arma que golpee en este combate, incluidas las reliquias de Houses Unite.
        def _con_resistencias(mult, desc=None):
            if mods_def.presente('SID_特効無効_効果'):
                return 1, None
            if mods_def.asignado('rival_effectividad') is not None and mult > 1:
                m = int(mods_def.asignado('rival_effectividad'))
                return m, f"Efectividad reducida (Stalwart/Veteran, Mt ×{m})"
            return mult, desc

        mult_mt_efectividad, desc_efectividad = _con_resistencias(mult_mt_efectividad, desc_efectividad)

        # Velocidad de ataque de ambos bandos (+ acts 攻撃速度: Flashing Fist Art)
        as_atk = cls.calcular_velocidad_ataque(atacante.velocidad + mods_atk.suma('spd', T),
                                               atacante.complexion + mods_atk.suma('bld', T),
                                               arma.wt) + int(mods_atk.suma('as', T))
        as_def = (cls.calcular_velocidad_ataque(defensor.velocidad + mods_def.suma('spd', T),
                                                defensor.complexion + mods_def.suma('bld', T),
                                                arma_def.wt)
                  if arma_def else defensor.velocidad + mods_def.suma('spd', T)) + int(mods_def.suma('as', T))

        # ── Ataque ──────────────────────────────────────────────────────────
        # Estadística ofensiva (Artes usa la media de STR y MAG: SID_気功 "ユニット攻撃力 = (力+魔力)/2")
        fuerza = atacante.fuerza + mods_atk.suma('str', T)
        magia = atacante.magia + mods_atk.suma('mag', T)
        if arma.tipo == 'Artes':
            stat_ofensiva = math.floor((fuerza + magia) / 2)
        elif arma.es_magica:
            stat_ofensiva = magia
        else:
            stat_ofensiva = fuerza
        if mods_atk.asignado('unit_atk', T) is not None:
            stat_ofensiva = math.floor(mods_atk.asignado('unit_atk', T))

        mt_efectivo = math.floor(arma.mt * mult_mt_efectividad * mods_atk.producto('power_arma', T)) + mods_atk.suma('power_arma', T)
        atk_base = stat_ofensiva + mt_efectivo

        # Bonos propios (威力 / 攻撃力 / ユニット攻撃力 sumados: Resonance, Lunar Brace,
        # Momentum, Weapon Sync, Fairy-Tale Folk, aura de Guía Divina…) y del defensor
        # sobre el atacante (相手の威力: Admiration, Gentility, Arms Shield, Guía Divina).
        atk_base += mods_atk.suma('power', T) + mods_atk.suma('atk', T) + mods_atk.suma('unit_atk', T)
        atk_base += mods_def.suma('rival_power', T)
        # Sumas de Timing 6 (secuencia) sobre los golpes propios, ya decidibles antes de
        # golpear: Moved to Tears (Boucheron, "+2 daño si un aliado hace Chain Attack")
        golpe_propio_t6 = [a for a in mods_atk.activas_en({6}) if a["action"] != 2]
        atk_base += sum(a["valores"].get('power', 0) + a["valores"].get('atk', 0) for a in golpe_propio_t6)
        recoil_hp = -int(mods_atk.suma('hp', T))   # Resonance: "HP;-;1" = coste de 1 HP

        pasivas_activas = cls._textos_pasivas(mods_atk, mods_def, T)
        pasivas_activas += [f"{a['nombre']} (+{a['valores'].get('power', 0) + a['valores'].get('atk', 0):g} Atk)"
                            for a in golpe_propio_t6 if a["valores"].get('power', 0) + a["valores"].get('atk', 0)]
        # Estados temporales (¡Ponte detrás de mí!, Self-Improver, ...): sus stat_boosts
        # ya vienen sumados en `atacante` (simular_combate → _con_estados_temporales)
        for desc in getattr(atacante, '_desc_estados_temporales', []) or []:
            pasivas_activas.append(desc)

        # ── Ataques de Emblema (Engage Attacks) ──────────────────────────────
        eng_nom_norm = normalizar_texto(engage_attack_nombre) if engage_attack_nombre else ""
        es_houses_unite = es_engage_attack and any(t in eng_nom_norm for t in ('houses unite', 'union tres casas', 'union de casas'))
        # Ojo: "ragnarok" a secas es el nombre del TOMO de Celica (IID_セリカ_ライナロック),
        # un arma de Emblema que se usa en ataques normales. Solo el nombre completo del
        # Ataque de Emblema activa su ×1.2 Místico y su "ataca a RES sin contraataque".
        es_warp_ragnarok = es_engage_attack and any(t in eng_nom_norm for t in ('warp ragnarok', 'teleragnarok', 'tele ragnarok'))
        # Ataques de Emblema de varios golpes: los describe el propio Skill.xml
        # (pasivas.forma_ataque_emblema). Solo se tratan aquí los que pegan N veces a
        # una fracción del mismo daño; Quadruple Hit y Twin Strike usan un arma distinta
        # por golpe y siguen resolviéndose como un ataque normal.
        forma_multigolpe = None
        if es_engage_attack:
            _forma = pasivas.forma_ataque_emblema(atacante, nombre_ataque=engage_attack_nombre)
            if _forma and _forma.get("fraccion") and normalizar_texto(_forma["nombre"]) in eng_nom_norm:
                forma_multigolpe = _forma
        es_override = es_engage_attack and any(t in eng_nom_norm for t in ('override', 'superacion'))

        if es_warp_ragnarok:
            # Warp Ragnarok: ataca con el tomo Ragnarok (IID_セリカ_ライナロック, Mt 15).
            # Si el arma no traia Mt asignado, garantizar el aporte canonico de 15
            if getattr(arma, 'mt', 0) <= 0:
                atk_base += 15
            pasivas_activas.append("Ragnarök Fusión (Ataque de Emblema Celica)")
        elif es_override:
            pasivas_activas.append(f"Superación / Override ({arma.nombre})")

        atk_efectivo = atk_base

        # ── Defensa ─────────────────────────────────────────────────────────
        # (la magia ataca a RES e ignora los bonos de defensa física del terreno)
        if arma.es_magica or es_warp_ragnarok:
            stat_defensiva = defensor.resistencia + mods_def.suma('res', T)
        else:
            stat_defensiva = defensor.defensa + mods_def.suma('def', T) + terreno_dfn
        # 相手の防御力 = …: Ignore Def/Res (Fire Breath), Soulblade (media Def/Res)
        if mods_atk.asignado('rival_defensa_efectiva', T) is not None:
            stat_defensiva = math.floor(mods_atk.asignado('rival_defensa_efectiva', T)) + (0 if arma.es_magica else terreno_dfn)

        # Daño por golpe base (+ amplificación por Veneno acumulado en el defensor: +1 por cada nivel de veneno 1..3)
        nivel_veneno = max(0, min(3, int(getattr(defensor, 'nivel_veneno', 0) or 0)))
        daño = max(0, math.floor(atk_efectivo - stat_defensiva))
        if daño > 0:
            daño += nivel_veneno

        # Multiplicadores sobre el daño neto (威力 ×: Merciless, Great Thunder…;
        # 相手の威力 ×: Laguz Friend). El bono de estilo de un Ataque de Emblema
        # (Warp Ragnarök Místico ×1.2) viene de su propio SID, abajo.
        mult_dano = mods_atk.producto('power', T) * mods_def.producto('rival_power', T)
        if daño > 0 and mult_dano != 1:
            daño = math.floor(daño * mult_dano)

        # Bono de estilo Místico en Warp Ragnarök (SID_セリカエンゲージ技_魔法: Act "威力;*;1.2"):
        # multiplica el DAÑO (威力) por 1.2, truncando. Ground truth: Céline (Mística,
        # Mag 16 + Mt 15 + Resonancia 2) vs Hortensia (Res 18) = 15 → 18 en el juego.
        if es_warp_ragnarok and estilo_atk_canon == 'mistico' and daño > 0:
            info_wr_mistico = condicion_dsl.HABILIDADES_CATALOGO.get('SID_セリカエンゲージ技_魔法')
            mult_wr = 1.2
            if info_wr_mistico:
                acumulador_wr = {'power': daño}
                condicion_dsl.aplicar_acts(info_wr_mistico, acumulador_wr)
                mult_wr = acumulador_wr.get('power', daño) / daño if daño else 1.2
            daño = math.floor(daño * mult_wr)
            pasivas_activas.append(f"Estilo Místico (Warp Ragnarök ×{mult_wr:g} daño)")

        # ── Ataques de Emblema: Unión Tres Casas (Houses Unite) y Lodestar Rush ───────────────
        # Houses Unite (Edelgard / Tres Casas): tri-ataque con las reliquias del datamine
        # (Item.xml): Aymr Mt 24 (efectivo vs dragón), Areadbhar Mt 14 ×1.5 al atacar
        # (SID_オフェンス時武器攻撃力上昇 → 21), Failnaught Mt 13 (efectivo vs volador y
        # dragón). Cada golpe: (Fue + bonos de pasivas + Mt efectivo + 5 − DEF) × 0.5 (floor,
        # mín 1). Verificado en el Cap. 9 contra un Axe Flier (Chloé, Weapon Sync+ +7):
        # sin bonos 19/18/27, +2 Gente de Cuento 20/19/28, +3 Guía Divina 21/19/28, ambos 22/20/29.
        houses_unite_hits = None
        lodestar_hits = None
        if es_houses_unite:
            # Houses Unite: "Use to attack with Aymr, Areadbhar, and Failnaught at 50 %
            # damage". Cada golpe es el DAÑO NORMAL de esa reliquia partido por la mitad
            # (truncando), no una fórmula aparte: verificado con Chloé (Voladora, sin bono
            # de estilo) — Aymr 35 → 17, Areadbhar 32 → 16, Failnaught 24 → 12.
            # Bonos de estilo del texto oficial, +10 % de daño sobre el golpe ya reducido:
            #   [Dragon] a los tres · [Cavalry] Areadbhar · [Covert] Failnaught
            #   [Armored] Aymr · [Qi Adept] rompe al objetivo (sin daño extra)
            def_stat = defensor.defensa + mods_def.suma('def', T) + terreno_dfn
            bono_atk = atk_base - (stat_ofensiva + mt_efectivo)
            hits, detalles = [], []
            global RELIQUIAS_HOUSES_UNITE
            if RELIQUIAS_HOUSES_UNITE is None:
                RELIQUIAS_HOUSES_UNITE = _reliquias_houses_unite()
            for reliquia, estilo_bono in RELIQUIAS_HOUSES_UNITE:
                # Cada reliquia lleva su propia efectividad (Failnaught ×3 contra voladores
                # y dragones, Aymr ×3 contra dragones) y la resistencia del defensor se le
                # aplica igual que a un arma normal: contra Hortensia, que tiene Veteran+,
                # no hay efectividad; contra un Axe Flier normal sí.
                mult_r, _desc_r = _con_resistencias(*cls.calcular_efectividad(reliquia, defensor))
                mt_r = reliquia.mt * mult_r
                # Areadbhar (SID_オフェンス時武器攻撃力上昇): +50 % de Mt al iniciar combate,
                # y Houses Unite siempre inicia.
                if getattr(reliquia, 'mt_x15_al_iniciar', False):
                    mt_r = math.floor(mt_r * 1.5)
                dano_normal = max(0, math.floor(stat_ofensiva + bono_atk + mt_r - def_stat))
                if dano_normal > 0 and mult_dano != 1:
                    dano_normal = math.floor(dano_normal * mult_dano)
                fraccion_r = 0.50
                if estilo_atk_canon == 'dragon' or estilo_atk_canon == estilo_bono:
                    fraccion_r *= 1.10
                    detalles.append(reliquia.nombre)
                hits.append(math.floor(dano_normal * fraccion_r))
            d1, d2, d3 = hits
            daño = d1 + d2 + d3
            houses_unite_hits = [d1, d2, d3]
            extra = f" [+10% estilo: {', '.join(detalles)}]" if detalles else ""
            pasivas_activas.append(
                f"Unión Tres Casas (Tri-ataque Aymr/Areadbhar/Failnaught: {d1}, {d2}, {d3} dmg = {daño} dmg){extra}")
            if estilo_atk_canon == 'qi_adept':
                pasivas_activas.append("Unión Tres Casas: rompe al objetivo (estilo Qi Adept)")
        elif forma_multigolpe:
            # Ataque de Emblema de varios golpes a fracción del daño (Skill.xml:
            # `攻撃回数 = N` + SID_ダメージNN％). Lodestar Rush 7 golpes al 30 % (Apoyo 8,
            # Dragón 9, Místico ataca a RES con 魔力); Astra Storm 5 al 30 % (20 % en las
            # versiones oscuras). Cada golpe redondea hacia arriba.
            num_golpes_multi = int(forma_multigolpe["golpes"])
            stat_def_multi = (defensor.resistencia + terreno_dfn) if forma_multigolpe["usa_magia"] else (defensor.defensa + terreno_dfn)
            daño_neto_multi = max(0, atk_efectivo - stat_def_multi)
            d_hit = 0 if daño_neto_multi <= 0 else math.ceil(daño_neto_multi * forma_multigolpe["fraccion"])
            daño = d_hit * num_golpes_multi
            lodestar_hits = (num_golpes_multi, d_hit)
            pasivas_activas.append(
                f"{forma_multigolpe['nombre']} ({num_golpes_multi} golpes de {d_hit} dmg = {daño} dmg)")
            if forma_multigolpe["rompe"]:
                pasivas_activas.append(f"{forma_multigolpe['nombre']}: rompe al objetivo (estilo Qi Adept)")

        # ── Precisión, Evasión, Crítico y Esquive ───────────────────────────
        # Propios (命中値/回避値/必殺値/必殺回避) + los que el rival impone (相手の命中値:
        # Fair Fight bonifica a ambos; 相手の回避値…).
        hit_mod_pasivas = mods_atk.suma('hit', T) + mods_def.suma('rival_hit', T)
        avo_mod_pasivas = mods_def.suma('avo', T) + mods_atk.suma('rival_avo', T)
        crit_mod_pasivas = mods_atk.suma('crit', T) + mods_def.suma('rival_crit', T)
        ddg_mod_pasivas = mods_def.suma('ddg', T)

        # Terreno del defensor tras las pasivas: Estilo Encubierto (SID_地形回避有利時２倍:
        # 地形回避 ×2), Estilo Místico atacando con tomo (SID_相手の地形回避有利時０: 相手の地形回避 = 0)
        terreno_avo = terreno_avo * mods_def.producto('terreno_avo', T) + mods_def.suma('terreno_avo', T)
        if mods_atk.asignado('rival_terreno_avo', T) is not None:
            terreno_avo = mods_atk.asignado('rival_terreno_avo', T)
        terreno_avo = int(terreno_avo)

        # ── Bonificaciones oficiales de Apoyo (SupportCalculator) ───────────
        supp_hit_atk, supp_avo_atk, supp_crit_atk, supp_ddg_atk, det_apoyos_atk = calcular_bonos_apoyo(atacante, aliados_cercanos_atk)
        supp_hit_def, supp_avo_def, supp_crit_def, supp_ddg_def, det_apoyos_def = calcular_bonos_apoyo(defensor, aliados_cercanos_def)

        # Bonificaciones del arma del defensor
        avo_bonus_arma = getattr(arma_def, 'avo_bonus', 0) if arma_def else 0
        ddg_bonus_arma = getattr(arma_def, 'ddg_bonus', 0) if arma_def else 0

        # Precisión (Hit vs Avoid)
        hit = cls.calcular_hit(atacante.destreza + mods_atk.suma('dex', T),
                               atacante.suerte + mods_atk.suma('lck', T),
                               arma.hit) + hit_mod_pasivas + supp_hit_atk
        avoid = cls.calcular_avoid(as_def, defensor.suerte + mods_def.suma('lck', T),
                                   terreno_avo) + avo_bonus_arma + avo_mod_pasivas + supp_avo_def
        precision = max(0, min(100, int(hit - avoid)))
        # Tasa impuesta (命中率 = 100: Sure Strike, Howling Beam; 相手の命中率 = 100: Hit１００ del rival)
        tasa = mods_atk.asignado('hit_rate', T)
        if mods_def.asignado('rival_hit_rate', T) is not None:
            tasa = mods_def.asignado('rival_hit_rate', T)
        if tasa is not None:
            precision = max(0, min(100, int(tasa)))

        # Críticos (Crit vs Dodge)
        crit = cls.calcular_crit(atacante.destreza + mods_atk.suma('dex', T),
                                 arma.crit) + crit_mod_pasivas + supp_crit_atk
        dodge = cls.calcular_dodge(defensor.suerte + mods_def.suma('lck', T)) + ddg_bonus_arma + ddg_mod_pasivas + supp_ddg_def
        prob_critico = max(0, min(100, int(crit - dodge)))
        tasa_crit = mods_atk.asignado('crit_rate', T)
        if mods_def.asignado('rival_crit_rate', T) is not None:
            tasa_crit = mods_def.asignado('rival_crit_rate', T)
        if tasa_crit is not None:
            prob_critico = max(0, min(100, int(tasa_crit)))
        # 必殺率 ×: el defensor puede REDUCIR la tasa en vez de fijarla (Lightsphere de
        # Tiki la deja a la mitad). Se aplica tras el tope, sobre la probabilidad final.
        mult_crit = mods_atk.producto('crit_rate', T) * mods_def.producto('rival_crit_rate', T)
        if mult_crit != 1:
            prob_critico = max(0, min(100, int(prob_critico * mult_crit)))

        # Triángulo de armas
        tipo_def_arma = arma_def.tipo if arma_def else None
        tiene_ventaja = cls.ventaja_triangulo(arma.tipo, tipo_def_arma)

        # Inmunidad a Break: terreno, Estilo Acorazado (SID_相性ブレイク無効) o
        # Unbreakable (SID_ブレイク無効_効果: Veteran / Veteran+)
        es_antirruptura = getattr(terreno, 'es_antirruptura', False) or mods_def.presente('SID_ブレイク無効_効果', 'SID_相性ブレイク無効')
        es_acorazado = estilo_def_canon == 'acorazado' or getattr(defensor, 'tipo_movimiento', '') in ('acorazado', 'armored')
        inflige_ruptura = es_iniciador and tiene_ventaja and daño > 0 and not es_antirruptura and not es_acorazado and not defensor_en_ruptura

        # Break Defenses (Marth, SID_ブレイク時追撃): al romper, golpe extra al 50 %
        # (SID_ブレイク時追撃_ダメージ５０％: 威力 × 0.5). Su Condition (攻撃結果(ブレイク))
        # es por golpe: aquí se resuelve con `inflige_ruptura`.
        tiene_break_defenses = mods_atk.presente('SID_ブレイク時追撃')
        dmg_break_def = 0
        if tiene_break_defenses and inflige_ruptura and es_iniciador and daño > 0:
            dmg_break_def = max(1, math.floor(daño * 0.50))
            pasivas_activas.append(f"Rompedefensas (+{dmg_break_def} Daño golpe extra)")

        # ── Habilidades de secuencia (las consume simular_combate) ──────────
        # Canter (SID_再移動): sin Condition; su efecto vive en la capa de movimiento.
        tiene_canter = mods_atk.presente('SID_再移動', 'SID_再移動＋')
        # Alacrity (SID_攻め立て): su Condition ya incluye "AS - AS rival >= 9" y "sin 追撃不可"
        tiene_alacrity = mods_atk.tiene('SID_攻め立て', 'SID_攻め立て＋')
        # Velocidad Divina (Marth, SID_カウンター y variantes de estilo, solo en Fusión):
        # golpe extra al 50 % tras el primer ataque (SID_カウンター_ダメージ５０％, Timing 6)
        tiene_divine_speed = es_iniciador and not es_engage_attack and any(a["sid"].startswith('SID_カウンター') for a in mods_atk.activas)
        # Hold Out (Roy, SID_踏ん張り…): la Condition de la principal ("HP >= X %") se
        # evalúa aquí; el efecto (ダメージ = HP-1, Timing 12) lo aplica la secuencia.
        tiene_hold_out = any(a["sid"].startswith('SID_踏ん張り') and not a["sid"].endswith('効果') for a in mods_def.activas)
        # Vantage (SID_待ち伏せ…, Stand 2): "HP <= X % && puede contraatacar" → golpea primero
        vantage = next((a for a in mods_atk.activas if a["sid"].startswith('SID_待ち伏せ')), None) if not es_iniciador else None
        # Follow-Up prohibido (SID_追撃不可: Thunder, Thoron, Smash…)
        sin_follow_up = mods_atk.presente('SID_追撃不可')
        sin_follow_up_def = mods_def.presente('SID_追撃不可')

        return {
            "as_atk": as_atk,
            "as_def": as_def,
            "daño": daño,
            "daño_critico": daño * 3,
            "precision": 100 if es_engage_attack else precision,
            "prob_critico": 0 if es_engage_attack else prob_critico,
            "tiene_ventaja": tiene_ventaja,
            "inflige_ruptura": inflige_ruptura,
            "dmg_break_def": dmg_break_def,
            "antirruptura_bloqueo_break": es_iniciador and tiene_ventaja and daño > 0 and (es_antirruptura or es_acorazado),
            "efectividad_activa": desc_efectividad,
            "multiplicador_efectividad": mult_mt_efectividad,
            "recoil_hp": recoil_hp,
            "tiene_canter": tiene_canter,
            "tiene_alacrity": tiene_alacrity,
            "tiene_divine_speed": tiene_divine_speed,
            "tiene_hold_out": tiene_hold_out,
            "vantage": vantage["nombre"] if vantage else "",
            "sin_follow_up": sin_follow_up,
            "sin_follow_up_def": sin_follow_up_def,
            "es_houses_unite": es_houses_unite,
            "es_lodestar_rush": bool(forma_multigolpe),
            "nombre_multigolpe": forma_multigolpe["nombre"] if forma_multigolpe else "",
            "es_warp_ragnarok": es_warp_ragnarok,
            "es_override": es_override,
            "es_engage_attack": es_engage_attack,
            "houses_unite_hits": houses_unite_hits,
            "lodestar_hits": lodestar_hits,
            "concede_accion_extra": es_houses_unite,
            "pasivas_activas": pasivas_activas,
            "apoyos_activos": det_apoyos_atk,
            # Detalle del motor de pasivas (lo que ha aportado cada SID a este golpe)
            "motor_pasivas": {"atk": mods_atk.como_dict(), "def": mods_def.como_dict()},
        }

    # Claves que afectan al golpe PROPIO del atacante (las demás cuentan cuando defiende)
    _CLAVES_ATACANTE = frozenset({"power", "atk", "unit_atk", "power_arma", "hit", "crit", "rival_avo", "rival_terreno_avo",
                                  "as", "hp", "str", "mag", "dex", "spd", "bld", "hit_rate", "crit_rate",
                                  "rival_defensa_efectiva"})
    # Etiquetas de los acts del DEFENSOR vistos desde el golpe que recibe
    _ETIQUETAS_DEFENSOR = {
        "rival_power": "Daño", "rival_hit": "Hit rival", "rival_crit": "Crit rival",
        "avo": "Avo", "ddg": "Ddg", "def": "Def", "res": "Res", "as": "AS", "terreno_avo": "Avo terreno",
        "spd": "Vel", "lck": "Suerte", "bld": "Complexión",
        "rival_effectividad": "efectividad", "rival_hit_rate": "Hit% rival", "rival_crit_rate": "Crit% rival",
    }

    @classmethod
    def _textos_pasivas(cls, mods_atk, mods_def, timings) -> list:
        """Textos de `pasivas_activas` para la UI: aportaciones con efecto numérico de
        cada bando, con el aliado que otorga el efecto cuando es un aura."""
        textos = []
        for a in mods_atk.activas_en(timings):
            propias = {k: v for k, v in a["valores"].items() if k in cls._CLAVES_ATACANTE}
            partes = pasivas.Modificadores._partes({"valores": propias,
                                                     "mult": {k: v for k, v in a["mult"].items() if k in cls._CLAVES_ATACANTE},
                                                     "asig": {k: v for k, v in a["asig"].items() if k in cls._CLAVES_ATACANTE}})
            if partes:
                origen = f" (de {a['de']})" if a.get("de") else ""
                textos.append(f"{a['nombre'] or a['sid']}{origen} ({', '.join(partes)})")
        for a in mods_def.activas_en(timings):
            partes = [f"{pasivas._fmt_valor(v)} {cls._ETIQUETAS_DEFENSOR.get(k, k)}" for k, v in a["valores"].items() if v and k in cls._ETIQUETAS_DEFENSOR]
            partes += [f"×{v:g} {cls._ETIQUETAS_DEFENSOR.get(k, k)}" for k, v in a["mult"].items() if v != 1 and k in cls._ETIQUETAS_DEFENSOR]
            partes += [f"{cls._ETIQUETAS_DEFENSOR.get(k, k)} = {v:g}" for k, v in a["asig"].items() if isinstance(v, (int, float)) and k in cls._ETIQUETAS_DEFENSOR]
            if partes:
                origen = f" (de {a['de']})" if a.get("de") else ""
                textos.append(f"{a['nombre'] or a['sid']}{origen} del defensor ({', '.join(partes)})")
        return textos

    # ── Simulación completa ─────────────────────────────────────────────

    @classmethod
    def simular_combate(cls, atacante, defensor, arma_atk, arma_def=None,
                        terreno_atk=None, terreno_def=None, distancia=1,
                        aliados_apoyo_backup=None,
                        pos_atk=None, pos_def=None, mapa=None, casillas_ocupadas=None,
                        defensor_en_ruptura: bool = False,
                        aliados_cercanos_atk=None, aliados_cercanos_def=None,
                        es_engage_attack: bool = False, engage_attack_nombre: str = "",
                        chain_guard_protector=None):
        """
        Simula el intercambio completo siguiendo la secuencia determinista de FE Engage:
          1. Chain Attacks de aliados de apoyo (Backup) cercanos (10% HP max c/u, redondeo canónico)
          2. Gestión de Armas Pesadas (Smash):
             - Si el atacante usa arma Smash y el defensor no, el defensor contraataca PRIMERO.
             - Las armas Smash NUNCA pueden realizar follow-up.
             - Si acierta un ataque Smash, empuja al rival 1 casilla. Si choca contra obstáculo o unidad,
               ¡provoca RUPTURA (Break) incluso a acorazados!
             - Un contraataque NUNCA inflige ruptura: el atacante ejecutará su golpe Smash siempre que sobreviva.
          3. Atacante golpea (y golpe extra de Divine Speed si activa) → Ruptura (si ventaja de armas)
          4. Si Alacrity activa y hay follow-up, el atacante hace follow-up ANTES del contraataque
          5. Defensor contraataca (si vivo, en rango y no roto; NUNCA ante Ataques de Emblema)
          6. Follow-ups restantes
          7. Efectos de retroceso (Resonancia) y salvación letal (Hold Out)
        """
        terreno_atk = terreno_atk or Terreno()
        terreno_def = terreno_def or Terreno()

        cls._validar_unidad(atacante, "atacante")
        cls._validar_unidad(defensor, "defensor")
        cls._validar_arma(arma_atk)
        if arma_def:
            cls._validar_arma(arma_def)

        # Buffs temporales (¡Ponte detrás de mí!, Self-Improver, ...): se aplican
        # sobre copias para no mutar las stats persistentes de la ficha.
        atacante = cls._con_estados_temporales(atacante)
        defensor = cls._con_estados_temporales(defensor)

        if distancia not in arma_atk.rango:
            raise ValueError(
                f"'{arma_atk.nombre}' no alcanza a distancia {distancia}. "
                f"Rango válido: {arma_atk.rango}"
            )

        # Normalizar aliados cercanos con distancia si se pasó pos_atk / pos_def
        norm_atk = normalizar_aliados_cercanos(aliados_cercanos_atk, pos_atk)
        norm_def = normalizar_aliados_cercanos(aliados_cercanos_def, pos_def)

        if not es_engage_attack and getattr(arma_atk, 'es_engage_attack', False):
            es_engage_attack = True
        if not engage_attack_nombre and hasattr(arma_atk, 'engage_attack_nombre'):
            engage_attack_nombre = getattr(arma_atk, 'engage_attack_nombre', '')

        # Ballesta de mapa (arco de la unidad disparado desde el objeto): un solo
        # golpe, sin contraataque, sin follow-up ni Chain Attacks ni golpes extra.
        es_ballesta = bool(getattr(arma_atk, 'es_ballesta', False))
        # Los ataques de Emblema y las ballestas no permiten contraataque del defensor
        # Adaptable: el defensor responde con la mejor arma de su inventario que alcance
        arma_def, arma_def_cambiada = arma_de_respuesta(defensor, arma_def, distancia, atacante)
        puede_contra = (not es_engage_attack) and (not es_ballesta) and (not defensor_en_ruptura) and (arma_def is not None) and (distancia in arma_def.rango)
        n_chain_attacks = 0 if es_ballesta else len(aliados_apoyo_backup or [])

        stats_atk = cls._stats_de_golpe(
            atacante, arma_atk, defensor, arma_def, terreno_def,
            es_iniciador=True,
            aliados_cercanos_atk=norm_atk,
            aliados_cercanos_def=norm_def,
            distancia=distancia,
            es_engage_attack=es_engage_attack,
            engage_attack_nombre=engage_attack_nombre,
            defensor_en_ruptura=defensor_en_ruptura,
            terreno_atacante=terreno_atk,
            rival_contraataca=puede_contra,
            chain_attacks=n_chain_attacks,
        )
        if es_ballesta:
            aliados_apoyo_backup = None
            stats_atk["tiene_divine_speed"] = False
            stats_atk["dmg_break_def"] = 0
            stats_atk["tiene_alacrity"] = False

        stats_def = None
        if puede_contra:
            stats_def = cls._stats_de_golpe(
                defensor, arma_def, atacante, arma_atk, terreno_atk,
                es_iniciador=False,
                aliados_cercanos_atk=norm_def,
                aliados_cercanos_def=norm_atk,
                distancia=distancia,
                terreno_atacante=terreno_def,
                rival_contraataca=True,
            )

        es_smash_atk = getattr(arma_atk, 'es_smash', False)
        es_smash_def = getattr(arma_def, 'es_smash', False) if arma_def else False
        # "Cede la iniciativa": mismo orden de golpes y mismo veto al seguimiento que un
        # Smash, pero sin empujar. Para la SECUENCIA cuenta igual que un Smash.
        cede_atk = es_smash_atk or getattr(arma_atk, 'cede_iniciativa', False)
        cede_def = (es_smash_def or getattr(arma_def, 'cede_iniciativa', False)) if arma_def else False

        def _stats_ronda_siguiente(stats_base, es_atk: bool):
            """Golpe de la 2ª ronda (follow-up). Se recalcula solo si alguna pasiva del
            primer golpe dependía de que fuera el primero (Momentum y compañía); si no,
            se reutiliza el mismo resultado."""
            if not any(a.get("condicion_primera_ronda") for a in stats_base["motor_pasivas"]["atk"]["activas"]):
                return stats_base
            if es_atk:
                return cls._stats_de_golpe(
                    atacante, arma_atk, defensor, arma_def, terreno_def,
                    es_iniciador=True, aliados_cercanos_atk=norm_atk, aliados_cercanos_def=norm_def,
                    distancia=distancia, es_engage_attack=es_engage_attack,
                    engage_attack_nombre=engage_attack_nombre, defensor_en_ruptura=defensor_en_ruptura,
                    terreno_atacante=terreno_atk, rival_contraataca=puede_contra,
                    chain_attacks=n_chain_attacks, ronda=1)
            return cls._stats_de_golpe(
                defensor, arma_def, atacante, arma_atk, terreno_atk,
                es_iniciador=False, aliados_cercanos_atk=norm_def, aliados_cercanos_def=norm_atk,
                distancia=distancia, terreno_atacante=terreno_def, rival_contraataca=True, ronda=1)

        stats_atk_seguimiento = _stats_ronda_siguiente(stats_atk, True)
        stats_def_seguimiento = _stats_ronda_siguiente(stats_def, False) if stats_def else None

        diff_as_atk = stats_atk["as_atk"] - stats_atk["as_def"]
        follow_up_atk = (diff_as_atk >= 5) and (not cede_atk) and (not es_engage_attack) and (not es_ballesta) and not stats_atk.get("sin_follow_up")
        # Brave (SID_２回行動, Stand=1): solo cuando la unidad inicia el combate; el defensor con Brave contraataca normal
        es_brave_atk = bool(getattr(arma_atk, 'es_brave', False)) and not es_engage_attack and not es_ballesta
        follow_up_def = puede_contra and ((stats_atk["as_def"] - stats_atk["as_atk"]) >= 5) and (not cede_def) and not stats_atk.get("sin_follow_up_def")

        # Alacrity (Lyn, SID_攻め立て): su Condition ("AS - AS rival >= 9", sin 追撃不可) ya
        # está evaluada en _stats_de_golpe; con follow-up, este va antes del contraataque
        activa_alacrity = stats_atk.get("tiene_alacrity", False) and follow_up_atk

        hp_atk_inicial = getattr(atacante, 'hp_actual', atacante.hp)
        hp_def_inicial = getattr(defensor, 'hp_actual', defensor.hp)
        hp_atk = hp_atk_inicial
        hp_def = hp_def_inicial
        hp_def_max = getattr(defensor, 'hp_max', getattr(defensor, 'hp', 30)) or defensor.hp
        piedras_res = max(0, int(getattr(defensor, 'hp_stock', 0) or 0))
        barra_resucitada = False
        # Las piedras resurrectoras no son solo cosa de jefes: un aliado puede llevarlas
        # (Divine Blessing de Tiki se las da). Si el atacante cae por un contraataque y le
        # queda una, vuelve con la barra llena igual que el defensor.
        hp_atk_max = int(getattr(atacante, 'hp_max', 0) or getattr(atacante, 'hp', 0) or 0)
        piedras_atk = max(0, int(getattr(atacante, 'hp_stock', 0) or 0))
        barra_atk_resucitada = False
        dano_aplicado_ultimo = 0
        defensor_roto = defensor_en_ruptura
        atacante_roto = False
        secuencia = []
        chain_dmg_total = 0

        # Guardia en Cadena (Chain Guard) de estilo Qi Adept (Martial Monk / Martial Master / Dancer)
        chain_guard_info = {"activo": False, "protector": None, "daño_protector": 0}
        chain_guard_activo = False
        if chain_guard_protector:
            hp_p = getattr(chain_guard_protector, 'hp_actual', getattr(getattr(chain_guard_protector, 'stats', None), 'hp', 30))
            hp_max_p = getattr(chain_guard_protector, 'hp_max', getattr(getattr(chain_guard_protector, 'stats', None), 'hp_max', 30))
            es_qi = es_unidad_qi_adept(chain_guard_protector)
            cg_enabled = getattr(chain_guard_protector, 'chain_guard_activo', True) and not getattr(chain_guard_protector, 'chain_guard_usado', False)
            # Solo ante ataques normales: una técnica de Fusión (Ataque de Emblema) no se puede parar
            if es_qi and hp_p >= hp_max_p and cg_enabled and not es_engage_attack:
                chain_guard_activo = True

        curacion_divine_speed = 0
        veneno_divine_speed = False

        def registrar(actor, tipo, daño, hp_obj):
            secuencia.append({
                "actor": actor, "tipo": tipo,
                "daño": daño, "hp_objetivo_tras": max(0, hp_obj),
            })

        def golpear_defensor(actor, tipo, daño):
            """Aplica un golpe y corta la ronda al romper una barra con piedra."""
            nonlocal hp_def, piedras_res, barra_resucitada, dano_aplicado_ultimo, chain_guard_activo, chain_guard_info
            # Guardia en Cadena (Chain Guard): bloquea el 1er golpe directo del atacante principal
            if chain_guard_activo and "chain_attack" not in tipo and actor == atacante.nombre:
                hp_max_prot = getattr(chain_guard_protector, 'hp_max', getattr(getattr(chain_guard_protector, 'stats', None), 'hp_max', 30))
                dmg_recoil = max(1, math.floor(hp_max_prot * 0.20))
                chain_guard_info["activo"] = True
                chain_guard_info["protector"] = getattr(chain_guard_protector, 'nombre', 'Qi Adept')
                chain_guard_info["daño_protector"] = dmg_recoil
                chain_guard_activo = False
                dano_aplicado_ultimo = 0
                registrar(actor, f"{tipo} (bloqueado por Guardia en Cadena)", 0, hp_def)
                return False

            dano_aplicado_ultimo = min(max(0, daño), max(0, hp_def))
            hp_def -= daño
            registrar(actor, tipo, dano_aplicado_ultimo, hp_def)
            if hp_def <= 0 and piedras_res > 0:
                piedras_res -= 1
                barra_resucitada = True
                hp_def = hp_def_max
                secuencia.append({"actor": defensor.nombre, "tipo": "piedra_resurrectora", "daño": 0, "hp_objetivo_tras": hp_def})
                return True
            return False

        def revivir_atacante_si_procede() -> bool:
            """Gasta una piedra del atacante si acaba de caer. Se llama tras registrar el
            golpe recibido, para que la secuencia quede en orden."""
            nonlocal hp_atk, piedras_atk, barra_atk_resucitada
            if hp_atk > 0 or piedras_atk <= 0:
                return False
            piedras_atk -= 1
            barra_atk_resucitada = True
            hp_atk = hp_atk_max
            secuencia.append({"actor": atacante.nombre, "tipo": "piedra_resurrectora",
                              "daño": 0, "hp_objetivo_tras": hp_atk})
            return True

        # 1. Chain Attacks de aliados de apoyo (Backup)
        chain_attacks_info = []
        # "[Dragon] Ally chain attacks are guaranteed to hit" (All for One: GiveTarget 2
        # de SID_チェインアタック命中率１００％ → 命中率 = 100 para los aliados que encadenan)
        forzado_chain = pasivas.chain_attack_forzado(atacante, nombre_ataque=engage_attack_nombre) if es_engage_attack else None
        precision_chain = 100 if (forzado_chain and forzado_chain["hit_garantizado"]) else 80
        if aliados_apoyo_backup:
            for apoyo in aliados_apoyo_backup:
                if hp_def <= 0:
                    break
                dmg_chain = max(1, math.floor(hp_def_max * 0.10))
                apoyo_nom = getattr(apoyo, 'nombre', 'Aliado')
                barra_rota = golpear_defensor(apoyo_nom, "chain_attack", dmg_chain)
                chain_dmg_total += dano_aplicado_ultimo
                chain_attacks_info.append({
                    "nombre": apoyo_nom,
                    "daño": dano_aplicado_ultimo,
                    "precision": precision_chain,
                    "arma": getattr(getattr(apoyo, 'arma', None), 'nombre', 'Arma')
                })
                if barra_rota:
                    break

        # 1b. Vantage / Emboscada (Leif) — SID_待ち伏せ(＋/＋＋): si el DEFENSOR tiene
        # HP <= 25% / 50% / 75% de su máximo y puede contraatacar, su contraataque
        # ocurre ANTES del ataque del rival (una sola vez; sus follow-ups siguen igual).
        contra_ya_hecha = False
        if puede_contra and stats_def and not barra_resucitada and not barra_atk_resucitada and hp_def > 0:
            # Vantage / + / ++ (SID_待ち伏せ…, Stand 2): la Condition del datamine
            # ("HP <= 25/50/75 % && puede contraatacar") ya se evaluó al calcular el contraataque
            vantage = stats_def.get("vantage")
            if vantage:
                hp_atk -= stats_def["daño"]
                registrar(defensor.nombre, f"contraataque ({vantage})", stats_def["daño"], hp_atk)
                revivir_atacante_si_procede()
                contra_ya_hecha = True
                pasivas_def_extra = stats_def.setdefault("pasivas_activas", [])
                pasivas_def_extra.append(f"{vantage} (golpea primero)")
        if hp_atk <= 0:
            pass  # el atacante cae antes de golpear: la ronda termina aquí

        # 2. Secuencia según propiedad Smash:
        elif cede_atk and puede_contra and not cede_def and not barra_resucitada and not barra_atk_resucitada and not contra_ya_hecha:
            # ── Defensor contraataca PRIMERO (prioridad por arma Smash del rival) ──
            if hp_def > 0 and stats_def:
                hp_atk -= stats_def["daño"]
                etiqueta_primero = "prioridad sobre Smash" if es_smash_atk else "el aliento cede el primer golpe"
                registrar(defensor.nombre, f"contraataque ({etiqueta_primero})", stats_def["daño"], hp_atk)
                revivir_atacante_si_procede()

            # ── Atacante ejecuta su golpe (si sobrevive al contraataque) ──
            if hp_atk > 0 and hp_def > 0:
                etiqueta_golpe = "ataque (smash)" if es_smash_atk else "ataque (cede el primer golpe)"
                barra_rota = golpear_defensor(atacante.nombre, etiqueta_golpe, stats_atk["daño"])
                if stats_atk["inflige_ruptura"]:
                    defensor_roto = True

            # ── Follow-up del defensor si doblaba, atacante sigue vivo y defensor no quedó roto ──
            if follow_up_def and hp_def > 0 and hp_atk > 0 and not barra_resucitada and not barra_atk_resucitada and not defensor_roto and stats_def:
                hp_atk -= stats_def_seguimiento["daño"]
                registrar(defensor.nombre, "follow-up", stats_def_seguimiento["daño"], hp_atk)
                revivir_atacante_si_procede()

        elif not barra_resucitada and not barra_atk_resucitada:
            # ── Secuencia estándar o Ataques de Emblema (sin Smash del atacante, o ambos con Smash) ──
            if stats_atk.get("es_houses_unite"):
                h_hits = stats_atk.get("houses_unite_hits", [13, 12, 8])
                relic_names = ["Aymr", "Areadbhar", "Failnaught"]
                for i_h, dmg_h in enumerate(h_hits):
                    if hp_def <= 0 and not barra_resucitada and not barra_atk_resucitada:
                        break
                    nom_r = relic_names[i_h] if i_h < len(relic_names) else f"Relic {i_h+1}"
                    b_rota = golpear_defensor(atacante.nombre, f"ataque (Houses Unite - {nom_r})", dmg_h)
                    if b_rota:
                        break
            elif stats_atk.get("es_lodestar_rush"):
                # Ataque de Emblema de N golpes a fracción del daño (Lodestar Rush, Astra Storm)
                num_g, dmg_g = stats_atk.get("lodestar_hits", (9, 3))
                nom_multi = stats_atk.get("nombre_multigolpe") or "Lodestar Rush"
                for i_g in range(num_g):
                    if hp_def <= 0 and not barra_resucitada and not barra_atk_resucitada:
                        break
                    b_rota = golpear_defensor(atacante.nombre, f"ataque ({nom_multi} {i_g+1}/{num_g})", dmg_g)
                    if b_rota:
                        break
            else:
                # 2a. Ataque principal del atacante
                if hp_def > 0:
                    tipo_atk_str = "ataque (smash)" if es_smash_atk else ("ataque (cede el primer golpe)" if cede_atk else "ataque")
                    barra_rota = golpear_defensor(atacante.nombre, tipo_atk_str, stats_atk["daño"])
                    if stats_atk["inflige_ruptura"]:
                        defensor_roto = True
                    # Arma Brave (SID_２回行動): el iniciador golpea dos veces por ataque
                    if es_brave_atk and hp_def > 0 and not barra_rota and not barra_resucitada and not barra_atk_resucitada:
                        barra_rota = golpear_defensor(atacante.nombre, "ataque (Brave 2º golpe)", stats_atk["daño"])

                    # Golpe extra de Break Defenses (Marth - Rompedefensas): inmediatamente
                    # tras el golpe que rompe, al 50%, SIN curación (verificado en capturas
                    # del juego: "Break! 10 → 5" y luego el combate sigue con normalidad)
                    if stats_atk.get("dmg_break_def", 0) > 0 and hp_def > 0 and not barra_rota:
                        golpear_defensor(atacante.nombre, "ataque (Break Defenses)", stats_atk["dmg_break_def"])

            # 2b. Follow-up anticipado por Alacrity
            if activa_alacrity and hp_atk > 0 and hp_def > 0 and not barra_resucitada and not barra_atk_resucitada:
                golpear_defensor(atacante.nombre, "follow-up (alacrity)", stats_atk_seguimiento["daño"])
                if es_brave_atk and hp_def > 0 and not barra_resucitada and not barra_atk_resucitada:
                    golpear_defensor(atacante.nombre, "follow-up (alacrity, Brave 2º golpe)", stats_atk_seguimiento["daño"])

            # 2c. Contraataque del defensor (si vivo, en rango y no roto; no si ya golpeó por Vantage)
            if puede_contra and not contra_ya_hecha and hp_def > 0 and not barra_resucitada and not barra_atk_resucitada and not defensor_roto and stats_def:
                tipo_contra_str = "contraataque (smash)" if es_smash_def else "contraataque"
                hp_atk -= stats_def["daño"]
                # Un contraataque NUNCA inflige Ruptura
                registrar(defensor.nombre, tipo_contra_str, stats_def["daño"], hp_atk)
                revivir_atacante_si_procede()

            # 2d. Follow-up regular del atacante (si no se ejecutó por Alacrity)
            if not activa_alacrity and follow_up_atk and hp_atk > 0 and hp_def > 0 and not barra_resucitada and not barra_atk_resucitada:
                golpear_defensor(atacante.nombre, "follow-up", stats_atk_seguimiento["daño"])
                if es_brave_atk and hp_def > 0 and not barra_resucitada and not barra_atk_resucitada:
                    golpear_defensor(atacante.nombre, "follow-up (Brave 2º golpe)", stats_atk_seguimiento["daño"])

            # 2e. Follow-up del defensor
            if follow_up_def and hp_def > 0 and hp_atk > 0 and not barra_resucitada and not barra_atk_resucitada and not defensor_roto and stats_def:
                hp_atk -= stats_def_seguimiento["daño"]
                registrar(defensor.nombre, "follow-up", stats_def_seguimiento["daño"], hp_atk)
                revivir_atacante_si_procede()

        # 2f. Velocidad Divina (Marth): SIEMPRE el último golpe del combate, tras
        # todos los follow-ups, al 50% del daño truncado. Verificado en capturas
        # del juego: "11 → ←15 → 11 → (verde 5) 5".
        # La curación es el bono de estilo Dragón (SID_カウンター_竜族効果, que
        # concede SID_神速スタイル効果発動済み): cond "総手番回数 == 手番回数 - 1 &&
        # HP < MaxHP && HP > 0", act "回復 + min(相手のHP, 相手のダメージ)" — es
        # decir, cura el daño REAL (topado por los HP que le quedaban al rival).
        if (stats_atk.get("tiene_divine_speed") and hp_atk > 0 and hp_def > 0
                and not barra_resucitada and not barra_atk_resucitada and not stats_atk.get("es_engage_attack")):
            dmg_divine = max(1, math.floor(stats_atk["daño"] * 0.50))
            golpear_defensor(atacante.nombre, "divine_speed", dmg_divine)
            estilo_atk_ds = resolver_estilo_combate(getattr(atacante, 'estilo_combate', ''))
            if estilo_atk_ds == 'dragon' or getattr(atacante, 'es_dragon', False):
                curacion_divine_speed += dano_aplicado_ultimo
            # Bono de estilo Encubierto (SID_カウンター_隠密効果_発動チェック): el golpe
            # de Velocidad Divina envenena al rival (+1 nivel, como una daga).
            elif estilo_atk_ds == 'encubierto' and dano_aplicado_ultimo > 0:
                veneno_divine_speed = True

        # 3. Recoil de HP por Resonancia
        recoil = stats_atk.get("recoil_hp", 0)
        if recoil > 0 and hp_atk > 1:
            hp_atk = max(1, hp_atk - recoil)

        # 3b. Velocidad Divina: el atacante recupera el daño real del golpe extra
        hp_atk_max = getattr(atacante, 'hp_max', 0) or hp_atk_inicial
        if curacion_divine_speed > 0 and hp_atk > 0:
            curacion_divine_speed = min(curacion_divine_speed, max(0, hp_atk_max - hp_atk))
            hp_atk += curacion_divine_speed
        else:
            curacion_divine_speed = 0

        # 4. Hold Out (Roy, SID_踏ん張り…): si el defensor recibía daño letal, sobrevive con 1 HP.
        # El umbral de HP de cada versión (+, ++, +++) es la Condition del SID, ya evaluada.
        if stats_atk.get("tiene_hold_out") and hp_def <= 0:
            hp_def = 1

        # 5. Cálculo espacial de Smash (Knockback / Ruptura por impacto)
        smash_info = {
            "es_smash": es_smash_atk,
            "ocurrido": False,
            "empujado": False,
            "nueva_pos": None,
            "bloqueado": False,
            "rompio_por_choque": False,
        }

        # Ocurre si el atacante asestó su golpe Smash
        # Solo empuja el Smash de verdad: los alientos ceden la iniciativa pero no mueven
        if es_smash_atk and any(s["actor"] == atacante.nombre and "smash" in s["tipo"] for s in secuencia):
            smash_info["ocurrido"] = True
            if pos_atk is not None and pos_def is not None:
                dx = pos_def[0] - pos_atk[0]
                dy = pos_def[1] - pos_atk[1]
                step_x = 1 if dx > 0 else (-1 if dx < 0 else 0)
                step_y = 1 if dy > 0 else (-1 if dy < 0 else 0)
                dest_x = pos_def[0] + step_x
                dest_y = pos_def[1] + step_y

                bloqueado = False
                if mapa is not None:
                    if not (0 <= dest_x < mapa.ancho and 0 <= dest_y < mapa.alto):
                        bloqueado = True
                    else:
                        t = mapa.grid[dest_x][dest_y]
                        es_vol = (getattr(defensor, 'tipo_movimiento', '') == 'volador' or getattr(defensor, 'es_volador', False))
                        caminable = getattr(t, 'volable', True) if es_vol else getattr(t, 'caminable', True)
                        if not caminable:
                            bloqueado = True

                if casillas_ocupadas is not None and (dest_x, dest_y) in casillas_ocupadas:
                    bloqueado = True

                if bloqueado:
                    smash_info["bloqueado"] = True
                    smash_info["rompio_por_choque"] = True
                    defensor_roto = True  # ¡El choque contra obstáculo rompe guardia incondicionalmente!
                else:
                    smash_info["empujado"] = True
                    smash_info["nueva_pos"] = [dest_x, dest_y]
            else:
                smash_info["empujado"] = True

        hp_atk_final = max(0, hp_atk)
        hp_def_final = max(0, hp_def)

        golpes_atk = sum(1 for s in secuencia if s["actor"] == atacante.nombre)
        golpes_def = sum(1 for s in secuencia if s["actor"] == defensor.nombre)
        daño_total_atk = sum(s["daño"] for s in secuencia if s["actor"] == atacante.nombre) + chain_dmg_total

        # Efectos de Veneno (Dagas aplican Veneno si conectan al menos 1 golpe)
        es_daga_atk = bool(arma_atk and (getattr(arma_atk, 'tipo', '') in ('Daga', 'Dagger') or 'daga' in str(arma_atk.nombre).lower() or 'dagger' in str(arma_atk.nombre).lower() or 'knife' in str(arma_atk.nombre).lower()))
        aplica_veneno = bool((es_daga_atk and golpes_atk > 0 and stats_atk["precision"] > 0) or veneno_divine_speed)
        veneno_def_previo = max(0, min(3, int(getattr(defensor, 'nivel_veneno', 0) or 0)))
        veneno_def_post = min(3, veneno_def_previo + (1 if aplica_veneno else 0))

        daño_solo_atacante = sum(s["daño"] for s in secuencia if s["actor"] == atacante.nombre)
        mata_solo_atacante = (hp_def_final <= 0) and not barra_resucitada
        es_kill_seguro = (hp_def_final <= 0) and (stats_atk["precision"] == 100) and mata_solo_atacante
        es_kill_probable = (hp_def_final <= 0) and not es_kill_seguro

        return {
            "atacante": {
                "nombre": atacante.nombre,
                "hp_inicial": hp_atk_inicial,
                "daño_por_golpe": stats_atk["daño"],
                "daño_critico": stats_atk["daño_critico"],
                "precision": stats_atk["precision"],
                "prob_critico": stats_atk["prob_critico"],
                "golpes_en_ronda": golpes_atk,
                "daño_total_ronda": daño_total_atk,
                "tiene_follow_up": follow_up_atk,
                "es_brave": es_brave_atk,
                "recoil_hp": recoil,
                "tiene_divine_speed": stats_atk.get("tiene_divine_speed", False),
                "curacion_divine_speed": curacion_divine_speed,
                "puede_canter": stats_atk.get("tiene_canter", False),
                "es_smash": es_smash_atk,
                "efectividad_activa": stats_atk.get("efectividad_activa"),
                "multiplicador_efectividad": stats_atk.get("multiplicador_efectividad"),
                "pasivas_activas": stats_atk.get("pasivas_activas", []),
                "apoyos_activos": stats_atk.get("apoyos_activos", []),
                "motor_pasivas": (stats_atk.get("motor_pasivas") or {}).get("atk"),
                "es_houses_unite": stats_atk.get("es_houses_unite", False),
                "houses_unite_hits": stats_atk.get("houses_unite_hits", []),
                "es_lodestar_rush": stats_atk.get("es_lodestar_rush", False),
                "nombre_multigolpe": stats_atk.get("nombre_multigolpe", ""),
                "lodestar_hits": stats_atk.get("lodestar_hits", (0, 0)),
                "es_warp_ragnarok": stats_atk.get("es_warp_ragnarok", False),
                "es_engage_attack": stats_atk.get("es_engage_attack", False),
                "es_ballesta": es_ballesta,
            },
            "defensor": {
                "nombre": defensor.nombre,
                "hp_inicial": hp_def_inicial,
                "nivel_veneno": veneno_def_previo,
                "puede_contraatacar": puede_contra,
                "contraataque_anulado_por_ruptura": (defensor_en_ruptura or (defensor_roto and puede_contra)) and not (cede_atk and not cede_def),
                "daño_por_golpe": stats_def["daño"] if stats_def else 0,
                "daño_critico": stats_def["daño_critico"] if stats_def else 0,
                "precision": stats_def["precision"] if stats_def else 0,
                "prob_critico": stats_def["prob_critico"] if stats_def else 0,
                "golpes_en_ronda": golpes_def,
                "daño_total_ronda": (stats_def["daño"] * golpes_def) if stats_def else 0,
                "tiene_follow_up": follow_up_def,
                "es_smash": es_smash_def,
                "pasivas_activas": stats_def.get("pasivas_activas", []) if stats_def else [],
                "apoyos_activos": stats_def.get("apoyos_activos", []) if stats_def else [],
                # detalle del motor de pasivas del defensor (evaluado en el golpe del atacante)
                "motor_pasivas": (stats_atk.get("motor_pasivas") or {}).get("def"),
            },
            "resultado": {
                "hp_atacante_final": hp_atk_final,
                "hp_defensor_final": hp_def_final,
                "atacante_mata": hp_def_final <= 0 and not barra_resucitada,
                "piedra_resurrectora_consumida": barra_resucitada,
                "piedra_atacante_consumida": barra_atk_resucitada,
                "piedras_restantes": piedras_res,
                "defensor_mata": hp_atk_final <= 0,
                "aplica_ruptura": bool(stats_atk.get("inflige_ruptura", False) or smash_info.get("rompio_por_choque", False)),
                "defensor_roto": defensor_roto,
                "sufre_ruptura": False,
                "antirruptura_bloqueo_break": stats_atk.get("antirruptura_bloqueo_break", False) and not smash_info["rompio_por_choque"],
                "chain_attacks_daño": chain_dmg_total,
                "chain_attacks": chain_attacks_info,
                "puede_canter": stats_atk.get("tiene_canter", False),
                "recoil_hp": recoil,
                "aplica_veneno": aplica_veneno,
                "nivel_veneno_defensor_post": veneno_def_post,
                "secuencia": secuencia,
                "smash": smash_info,
                "chain_guard": chain_guard_info,
                "pasivas_activas": stats_atk.get("pasivas_activas", []),
                "apoyos_activos": stats_atk.get("apoyos_activos", []),
                "ataque_emblema_ejecutado": bool(es_engage_attack),
            },
            "alertas_tacticas": {
                "peligro_letal": hp_atk_final <= 0,
                "kill_seguro": es_kill_seguro,
                "kill_probable": es_kill_probable,
                "atacante_en_peligro": 0 < hp_atk_final <= atacante.hp * 0.25,
                "defensor_en_peligro": 0 < hp_def_final <= defensor.hp * 0.25,
                "daño_cero": stats_atk["daño"] == 0,
                "contraataque_bloqueado": defensor_roto or not puede_contra,
                "es_smash": es_smash_atk,
                "smash_empujado": smash_info["empujado"],
                "smash_rompio_por_choque": smash_info["rompio_por_choque"],
            },
        }

    # ── Validación ──────────────────────────────────────────────────────

    @classmethod
    def _validar_unidad(cls, unidad, rol: str) -> None:
        if not isinstance(unidad, Unidad) and not (hasattr(unidad, 'hp') and hasattr(unidad, 'fuerza')):
            raise TypeError(
                f"El {rol} debe ser una instancia de Unidad o FichaUnidad válida. "
                f"Recibido: {type(unidad).__name__}"
            )

    @classmethod
    def _validar_arma(cls, arma) -> None:
        if not isinstance(arma, Arma):
            raise TypeError(
                f"El arma debe ser una instancia de Arma. "
                f"Recibido: {type(arma).__name__}"
            )

    @classmethod
    def _determinar_distancia_optima_enemigo(cls, arma_enemigo, arma_jugador):
        """
        Determina a qué distancia atacará el enemigo en su turno (IA espacial):
        1. Prefiere una distancia dentro de su rango donde el jugador NO pueda contraatacar.
        2. Si en todas el jugador puede contraatacar (o en ninguna), escoge la primera distancia de su rango.
        3. Si no tiene arma o rango válido, retorna None.
        """
        if not arma_enemigo or not arma_enemigo.rango:
            return None

        rangos_seguros = [
            d for d in arma_enemigo.rango
            if not arma_jugador or d not in arma_jugador.rango
        ]
        if rangos_seguros:
            return rangos_seguros[0]

        return arma_enemigo.rango[0]

    # ── Evaluación de Riesgo (RNG Assessment) ────────────────────────────

    @classmethod
    def evaluar_riesgo(cls, atacante, defensor, arma_atk, arma_def=None,
                       terreno_atk=None, terreno_def=None, distancia=1,
                       perfil="seguro", cronogema_usada=False,
                       contexto_mapa=None, defensor_en_ruptura: bool = False,
                       aliados_apoyo_backup=None,
                       aliados_cercanos_atk=None, aliados_cercanos_def=None,
                       es_engage_attack: bool = False, engage_attack_nombre: str = "",
                       pos_atk=None, pos_def=None, chain_guard_protector=None):
        """
        Envuelve simular_combate() y genera un veredicto de riesgo
        con etiquetas semánticas para consumo del LLM.

        Args:
            (mismos que simular_combate)
            perfil: "seguro" (Iron-Man) o "agresivo" (Kamikaze/Speedrun).
                    Cambia los umbrales de riesgo aceptable.
            cronogema_usada: True si el usuario indica que acaba de rebobinar
                             tras haber fallado/muerto en esta tirada.
            contexto_mapa: instancia de ContextoMapaEnemigo (opcional).
                           Si se proporciona, la simulación del turno enemigo
                           usa el peor caso espacial real (posición óptima del
                           enemigo según su MOV y el terreno) en lugar de la
                           heurística de distancia interna.
            defensor_en_ruptura: True si el defensor ya está sufriendo Ruptura al iniciar.
            aliados_apoyo_backup: lista de unidades aliadas de apoyo (Backup) en rango.
        """
        if perfil not in ("seguro", "agresivo"):
            raise ValueError(
                f"Perfil '{perfil}' no valido. Usa 'seguro' o 'agresivo'."
            )

        # Ejecutar simulación de combate completa
        combate = cls.simular_combate(
            atacante, defensor, arma_atk, arma_def,
            terreno_atk, terreno_def, distancia,
            aliados_apoyo_backup=aliados_apoyo_backup,
            defensor_en_ruptura=defensor_en_ruptura,
            aliados_cercanos_atk=aliados_cercanos_atk,
            aliados_cercanos_def=aliados_cercanos_def,
            es_engage_attack=es_engage_attack,
            engage_attack_nombre=engage_attack_nombre,
            pos_atk=pos_atk,
            pos_def=pos_def,
            chain_guard_protector=chain_guard_protector,
        )

        atk = combate["atacante"]
        dfn = combate["defensor"]
        res = combate["resultado"]
        alertas = combate["alertas_tacticas"]

        # ── Regla 1: Kill Seguro vs Kill Probable ──
        kill_seguro = alertas["kill_seguro"]
        kill_probable = alertas["kill_probable"]

        # Podría matar con un crítico aunque el daño normal no mate?
        kill_con_critico = (
            not kill_seguro
            and not kill_probable
            and atk.get("prob_critico", 0) > 0
            and atk["daño_critico"] * atk["golpes_en_ronda"] >= dfn["hp_inicial"]
        )

        # ── Regla 2: Letalidad Inversa (Player Phase + Enemy Phase) ──
        # Evaluamos dos escenarios de muerte del atacante:
        # A) Muerte en contraataque inmediato (Player Phase)
        # B) Muerte en el turno enemigo posterior si el defensor sobrevive (Enemy Phase)
        
        atacante_muere_en_contra = False
        prob_muerte_contra = 0

        if dfn["puede_contraatacar"] and not alertas["contraataque_bloqueado"]:
            daño_contra_total = dfn["daño_total_ronda"]
            # Con piedras resurrectoras hay que agotar la barra actual Y las de repuesto:
            # perder una barra no es morir. Vale para aliados (Divine Blessing) y jefes.
            hp_a_agotar = atacante.hp + max(0, int(getattr(atacante, 'hp_stock', 0) or 0)) * int(
                getattr(atacante, 'hp_max', 0) or atacante.hp or 0)
            atacante_muere_en_contra = daño_contra_total >= hp_a_agotar

            # P(muerte) = P(no mato al enemigo) * P(enemigo acierta sus golpes)
            prob_no_matar = (100 - atk["precision"]) / 100

            if dfn["golpes_en_ronda"] > 0 and daño_contra_total >= hp_a_agotar:
                prob_contra_acierta = (dfn["precision"] / 100) ** dfn["golpes_en_ronda"]
                prob_muerte_contra = round(
                    prob_no_matar * prob_contra_acierta * 100, 1
                )

        # ── Simulación del Turno Enemigo (Enemy Phase) ──
        # Si el enemigo sobrevive a nuestro turno (no es kill seguro), asumimos que en su turno
        # se reposicionara a su distancia óptima para atacar. En su turno NO tiene Ruptura/Break (expiró).
        amenaza_turno_enemigo = None
        peor_caso_espacial = None         # relleno solo cuando hay contexto_mapa
        prob_muerte_turno_enemigo = 0
        atacante_muere_en_turno_enemigo = False

        if not kill_seguro and res["hp_defensor_final"] > 0:
            # ── Caso A: tenemos información espacial del mapa ──
            # Usamos AnalizadorAmenaza para encontrar la posición desde la que
            # el enemigo causará el máximo daño (peor caso real).
            if contexto_mapa is not None:
                # Importación en tiempo de ejecución para evitar dependencia circular
                from motor_de_movimiento_y_amenaza import ContextoMapaEnemigo  # noqa: F811
                peor = contexto_mapa.analizador.calcular_peor_caso_amenaza(
                    ficha_enemigo=contexto_mapa.ficha_enemigo,
                    pos_jugador=contexto_mapa.pos_jugador,
                    ficha_jugador=contexto_mapa.ficha_jugador,
                    calc=cls,
                )
                peor_caso_espacial = peor

                if not peor["enemigo_alcanza"]:
                    # El enemigo no puede llegar al jugador — turno enemigo sin amenaza
                    amenaza_turno_enemigo = {
                        "distancia_ataque": None,
                        "daño_enemigo_turno": 0,
                        "precision_enemigo": 0,
                        "hp_atacante_tras_turno_enemigo": res["hp_atacante_final"],
                        "mata_en_turno_enemigo": False,
                        "prob_muerte": 0,
                        "jugador_puede_contraatacar": False,
                        "pos_optima_enemigo": None,
                    }
                    # No hay simulación adicional — salimos del bloque
                    atacante_muere_en_turno_enemigo = False
                else:
                    # El enemigo alcanza — simulamos desde su posición óptima
                    distancia_enemigo = peor["distancia_ataque"]
                    arma_enemigo = arma_def if arma_def else None
                    # Sin arma que alcance esa distancia no hay segundo combate que simular
                    if arma_enemigo and distancia_enemigo not in (getattr(arma_enemigo, 'rango', None) or [1]):
                        arma_enemigo = None

                    if arma_enemigo:
                        defensor_post_combate = Unidad(
                            nombre=defensor.nombre, hp=res["hp_defensor_final"],
                            fuerza=defensor.fuerza, magia=defensor.magia,
                            destreza=defensor.destreza, velocidad=defensor.velocidad,
                            defensa=defensor.defensa, resistencia=defensor.resistencia,
                            suerte=defensor.suerte, complexion=defensor.complexion,
                            es_lord=defensor.es_lord
                        )
                        atacante_post_combate = Unidad(
                            nombre=atacante.nombre, hp=res["hp_atacante_final"],
                            fuerza=atacante.fuerza, magia=atacante.magia,
                            destreza=atacante.destreza, velocidad=atacante.velocidad,
                            defensa=atacante.defensa, resistencia=atacante.resistencia,
                            suerte=atacante.suerte, complexion=atacante.complexion,
                            es_lord=atacante.es_lord,
                            hp_max=getattr(atacante, 'hp_max', 0) or atacante.hp,
                        )
                        # Igual que en el otro escenario: las piedras que le queden
                        setattr(atacante_post_combate, 'hp_stock',
                                max(0, int(getattr(atacante, 'hp_stock', 0) or 0)
                                    - (1 if res.get("piedra_atacante_consumida") else 0)))
                        sim_enemigo = cls.simular_combate(
                            defensor_post_combate, atacante_post_combate,
                            arma_enemigo, arma_atk,
                            terreno_def, terreno_atk, distancia_enemigo
                        )
                        atk_ene = sim_enemigo["atacante"]
                        res_ene = sim_enemigo["resultado"]
                        dfn_ene = sim_enemigo["defensor"]

                        if res_ene["atacante_mata"]:
                            atacante_muere_en_turno_enemigo = True
                            prob_sobrevivir = (100 - (atk["precision"] if kill_probable else 0)) / 100
                            prob_hit = (atk_ene["precision"] / 100) ** atk_ene["golpes_en_ronda"]
                            prob_muerte_turno_enemigo = round(prob_sobrevivir * prob_hit * 100, 1)

                        amenaza_turno_enemigo = {
                            "distancia_ataque": distancia_enemigo,
                            "daño_enemigo_turno": atk_ene["daño_total_ronda"],
                            "precision_enemigo": atk_ene["precision"],
                            "hp_atacante_tras_turno_enemigo": res_ene["hp_defensor_final"],
                            "mata_en_turno_enemigo": res_ene["atacante_mata"],
                            "prob_muerte": prob_muerte_turno_enemigo,
                            "jugador_puede_contraatacar": dfn_ene["puede_contraatacar"],
                            "pos_optima_enemigo": list(peor["pos_optima"]),
                        }

            else:
                # ── Caso B (original): sin información de mapa ──
                # Heurística: el enemigo elige la distancia donde el jugador no puede contra.
                arma_enemigo = arma_def if arma_def else None
                distancia_enemigo = cls._determinar_distancia_optima_enemigo(arma_enemigo, arma_atk)

                if arma_enemigo and distancia_enemigo is not None:
                    defensor_post_combate = Unidad(
                        nombre=defensor.nombre, hp=res["hp_defensor_final"],
                        fuerza=defensor.fuerza, magia=defensor.magia,
                        destreza=defensor.destreza, velocidad=defensor.velocidad,
                        defensa=defensor.defensa, resistencia=defensor.resistencia,
                        suerte=defensor.suerte, complexion=defensor.complexion,
                        es_lord=defensor.es_lord
                    )
                    atacante_post_combate = Unidad(
                        nombre=atacante.nombre, hp=res["hp_atacante_final"],
                        fuerza=atacante.fuerza, magia=atacante.magia,
                        destreza=atacante.destreza, velocidad=atacante.velocidad,
                        defensa=atacante.defensa, resistencia=atacante.resistencia,
                        suerte=atacante.suerte, complexion=atacante.complexion,
                        es_lord=atacante.es_lord,
                        hp_max=getattr(atacante, 'hp_max', 0) or atacante.hp,
                    )
                    # Las piedras que le queden tras este combate: si en la fase enemiga
                    # le rematan, gasta una y sigue viva. Sin esto la herramienta daba por
                    # muerta a una unidad con barra de repuesto.
                    setattr(atacante_post_combate, 'hp_stock',
                            max(0, int(getattr(atacante, 'hp_stock', 0) or 0)
                                - (1 if res.get("piedra_atacante_consumida") else 0)))
                    sim_enemigo = cls.simular_combate(
                        defensor_post_combate, atacante_post_combate,
                        arma_enemigo, arma_atk,
                        terreno_def, terreno_atk, distancia_enemigo
                    )
                    atk_ene = sim_enemigo["atacante"]
                    res_ene = sim_enemigo["resultado"]
                    dfn_ene = sim_enemigo["defensor"]

                    if res_ene["atacante_mata"]:
                        atacante_muere_en_turno_enemigo = True
                        prob_sobrevivir_turno_jugador = (100 - (atk["precision"] if kill_probable else 0)) / 100
                        prob_hit_enemigo = (atk_ene["precision"] / 100) ** atk_ene["golpes_en_ronda"]
                        prob_muerte_turno_enemigo = round(prob_sobrevivir_turno_jugador * prob_hit_enemigo * 100, 1)

                    amenaza_turno_enemigo = {
                        "distancia_ataque": distancia_enemigo,
                        "daño_enemigo_turno": atk_ene["daño_total_ronda"],
                        "precision_enemigo": atk_ene["precision"],
                        "hp_atacante_tras_turno_enemigo": res_ene["hp_defensor_final"],
                        "mata_en_turno_enemigo": res_ene["atacante_mata"],
                        "prob_muerte": prob_muerte_turno_enemigo,
                        "jugador_puede_contraatacar": dfn_ene["puede_contraatacar"]
                    }

        prob_muerte_total = max(prob_muerte_contra, prob_muerte_turno_enemigo)
        atacante_muere_si_falla = atacante_muere_en_contra or atacante_muere_en_turno_enemigo

        # ── Clasificación de Riesgo ──
        if perfil == "seguro":
            # Iron-Man: >1% de muerte = inaceptable
            umbral_critico = 1
            umbral_alto = 0.5
            umbral_moderado = 0.1
        else:
            # Agresivo/Speedrun: acepta más riesgo
            umbral_critico = 40
            umbral_alto = 25
            umbral_moderado = 10

        # Si la unidad es Lord/Esencial (ej: Alear), elevar nivel de alerta por Game Over
        es_game_over_riesgo = atacante.es_lord and (atacante_muere_si_falla or prob_muerte_total > 0)

        if (atacante_muere_si_falla and prob_muerte_total > umbral_critico) or es_game_over_riesgo:
            nivel_riesgo = "critico"
        elif atacante_muere_si_falla and prob_muerte_total > umbral_alto:
            nivel_riesgo = "alto"
        elif (prob_muerte_total > umbral_moderado
              or (not kill_seguro and kill_probable)):
            nivel_riesgo = "moderado"
        elif alertas["daño_cero"]:
            nivel_riesgo = "inutil"
        else:
            nivel_riesgo = "bajo"

        # ── Construir motivos legibles ──
        motivos = []

        if kill_seguro:
            motivos.append(
                f"{atk['nombre']} mata a {dfn['nombre']} con certeza "
                f"({atk['precision']}% hit, {atk['daño_total_ronda']} "
                f"vs {dfn['hp_inicial']} HP)."
            )
        elif kill_probable:
            motivos.append(
                f"{atk['nombre']} puede matar a {dfn['nombre']}, "
                f"pero depende de acertar ({atk['precision']}% hit). "
                f"Para el plan B, {dfn['nombre']} sigue vivo."
            )
        elif kill_con_critico:
            motivos.append(
                f"{atk['nombre']} solo mata con critico "
                f"({atk['prob_critico']}% prob). "
                f"No planificar en base a esto."
            )
        else:
            motivos.append(
                f"{atk['nombre']} hace {atk['daño_total_ronda']} "
                f"({atk['golpes_en_ronda']}x{atk['daño_por_golpe']}). "
                f"{dfn['nombre']} queda en "
                f"{res['hp_defensor_final']}/{dfn['hp_inicial']} HP."
            )

        if atacante_muere_en_contra:
            motivos.append(
                f"PELIGRO (Contraataque): Si el {atk['precision']}% falla, "
                f"{dfn['nombre']} puede matar a {atk['nombre']} en la misma ronda "
                f"({prob_muerte_contra}% prob. muerte)."
            )

        if atacante_muere_en_turno_enemigo:
            motivos.append(
                f"PELIGRO (Turno Enemigo): Si {dfn['nombre']} sobrevive, en su turno "
                f"atacara a distancia {amenaza_turno_enemigo['distancia_ataque']} "
                f"haciéndole {amenaza_turno_enemigo['daño_enemigo_turno']} de daño "
                f"({prob_muerte_turno_enemigo}% prob. de morir en Turno Enemigo)."
            )

        if atacante.es_lord and (atacante_muere_si_falla or prob_muerte_total > 0):
            motivos.append(
                f"ALERTA GAME OVER: {atk['nombre']} es una unidad esencial (Lord). "
                f"Perder esta unidad provocara la derrota inmediata."
            )

        if alertas["contraataque_bloqueado"] and not alertas["daño_cero"]:
            if res["aplica_ruptura"]:
                motivos.append(
                    "Ruptura aplicada: contraataque inmediato anulado (nota: la Ruptura expira en el turno enemigo)."
                )
            elif not dfn["puede_contraatacar"]:
                motivos.append(
                    f"{dfn['nombre']} no puede contraatacar a esta distancia en esta ronda."
                )

        if res.get("antirruptura_bloqueo_break", False):
            motivos.append(
                f"ALERTA ANTIRRUPTURA: {dfn['nombre']} está en una casilla con inmunidad (Curación/Fortaleza). "
                f"No sufrirá Ruptura y contraatacará si está en rango."
            )

        if terreno_def and terreno_def.curacion_turno > 0 and not kill_seguro:
            motivos.append(
                f"TERRENO DE CURACIÓN: Si {dfn['nombre']} sobrevive, recuperará +{terreno_def.curacion_turno} HP "
                f"al inicio del turno enemigo."
            )

        # ── Cálculo de Recarga del Medidor de Emblema (Engage Gauge) ──
        # En FE Engage:
        # • Participar en combate: +1 carga
        # • Derrotar a un enemigo (KO): +1 carga adicional (+2 con espada Libération)
        # • Casilla de Emblema: Recarga instantánea al 100% (todas las cargas)
        recarga_emblema_info = None
        turnos_fusion = getattr(atacante, 'turnos_fusion_restantes', 0)
        esta_en_fusion = getattr(atacante, 'en_fusion', False) or (turnos_fusion > 0)
        if turnos_fusion <= 0 and not esta_en_fusion:
            energia_actual = getattr(atacante, 'energia_emblema', 6)
            max_energia = getattr(atacante, 'max_energia_emblema', 6)

            if energia_actual < max_energia or (terreno_atk and getattr(terreno_atk, 'es_recarga_emblema', False)):
                # +1 por cada ataque hecho o recibido en el combate (sin Chain Attacks);
                # derrotar al rival solo suma con Libération (SID_撃破時エンゲージカウント＋１)
                combatientes = {getattr(atacante, 'nombre', ''), getattr(defensor, 'nombre', '')}
                ganancia = sum(1 for s_ in res.get("secuencia", [])
                               if s_.get("actor") in combatientes and s_.get("tipo") not in ("piedra_resurrectora", "chain_attack")) or 1
                es_lib = 'SID_撃破時エンゲージカウント＋１' in (getattr(arma_atk, 'sids', None) or []) or getattr(atacante, 'tiene_liberation', False)
                if es_lib and (kill_seguro or (kill_probable and res["atacante_mata"])):
                    ganancia += 1

                if terreno_atk and getattr(terreno_atk, 'es_recarga_emblema', False):
                    nueva_energia = max_energia
                    ganancia = max_energia - energia_actual
                else:
                    nueva_energia = min(max_energia, energia_actual + ganancia)

                fusion_lista = (nueva_energia >= max_energia)
                recarga_emblema_info = {
                    "energia_previa": energia_actual,
                    "energia_ganada": ganancia,
                    "nueva_energia": nueva_energia,
                    "max_energia": max_energia,
                    "fusion_lista": fusion_lista,
                    "es_kill_bonus": (kill_seguro or res["atacante_mata"]),
                    "es_liberation": es_lib
                }

                if fusion_lista and energia_actual < max_energia:
                    motivos.append(
                        f"FUSION DE EMBLEMA LISTA: {atk['nombre']} obtiene +{ganancia} cargas "
                        f"({nueva_energia}/{max_energia}). Podra fusionarse con su Emblema el proximo turno."
                    )
                elif ganancia > 0 and energia_actual < max_energia:
                    motivo_kill = " (remate + bono baja)" if (kill_seguro or res["atacante_mata"]) else ""
                    motivos.append(
                        f"RECARGA DE EMBLEMA: {atk['nombre']} gana +{ganancia} carga(s){motivo_kill} "
                        f"(medidor: {nueva_energia}/{max_energia})."
                    )

        if terreno_atk and terreno_atk.es_recarga_emblema:
            motivos.append(
                "CASILLA DE EMBLEMA: Posición aliada recarga el medidor de Fusión al 100% (permite 2ª Fusión táctica)."
            )

        if cronogema_usada:
            motivos.append(
                "CRONOGEMA DETECTADA: El resultado de esta tirada especifica esta fijado por la semilla de RNG. "
                "Repetir exactamente esta misma accion producira el mismo fallo/resultado."
            )

        # ── Veredicto final ──
        veredicto = {
            "nivel_riesgo": "semilla_bloqueada" if cronogema_usada and not kill_seguro else nivel_riesgo,
            "perfil_aplicado": perfil,
            "cronogema_usada": cronogema_usada,
            "rng_semilla_bloqueada": cronogema_usada and not kill_seguro,
            "kill_seguro": kill_seguro,
            "kill_probable": kill_probable,
            "kill_con_critico": kill_con_critico,
            "atacante_muere_si_falla": atacante_muere_si_falla,
            "atacante_muere_en_contra": atacante_muere_en_contra,
            "atacante_muere_en_turno_enemigo": atacante_muere_en_turno_enemigo,
            "prob_muerte_atacante": prob_muerte_total,
            "amenaza_turno_enemigo": amenaza_turno_enemigo,
            "recarga_emblema": recarga_emblema_info,
            "peor_caso_espacial": peor_caso_espacial,   # None si no se usó contexto_mapa
            "es_lord_atacante": atacante.es_lord,
            "motivos": motivos,
        }

        # ── Recomendación táctica ──
        recomendacion = cls._generar_recomendacion(
            veredicto["nivel_riesgo"], perfil, kill_seguro, kill_probable,
            atacante_muere_si_falla, atk, dfn, res, alertas, atacante.es_lord,
            cronogema_usada=cronogema_usada
        )

        return {
            "combate": combate,
            "veredicto": veredicto,
            "recomendacion": recomendacion,
        }

    @staticmethod
    def _generar_recomendacion(nivel_riesgo, perfil, kill_seguro,
                               kill_probable, atacante_muere_si_falla,
                               atk, dfn, res, alertas, es_lord=False,
                               cronogema_usada=False):
        """
        Genera una recomendación táctica en texto legible.
        Esto es lo que el LLM usaría como base para su respuesta.
        """
        if cronogema_usada and not kill_seguro:
            return (
                f"MANIPULACION DE RNG REQUERIDA (Cronogema Usada): "
                f"El número aleatorio de esta acción específica está fijado por la semilla del juego. "
                f"NO repitas exactamente este ataque directo con {atk['nombre']}. "
                f"Sugerencia táctica: Haz que otro aliado realice primero una acción de combate o apoyo "
                f"para 'quemar' los números aleatorios malos (RNs). Después, vuelve a intentar el ataque con {atk['nombre']}."
            )

        prefix_lord = "ALERTA GAME OVER! " if es_lord and nivel_riesgo in ("critico", "alto") else ""

        if nivel_riesgo == "critico":
            return (
                f"{prefix_lord}RIESGO CRITICO. No se recomienda este ataque. "
                f"{atk['nombre']} corre riesgo letal (ya sea en contraataque o en el turno enemigo posterior). "
                f"Busca un enfoque alternativo: rematar con otra unidad para kill seguro, usar bastón Rescatar/Repetición, "
                f"o no dejar a {atk['nombre']} expuesto a alcance enemigo."
            )

        if nivel_riesgo == "alto":
            return (
                f"{prefix_lord}RIESGO ALTO. {atk['nombre']} puede atacar, pero si el enemigo sobrevive, "
                f"quedara expuesto a un contraataque o ataque enemigo letal. "
                f"Asegurate de tener plan de contingencia (Baston Rescatar, baile/refresco o Remate seguro)."
            )

        if nivel_riesgo == "inutil":
            return (
                f"Accion ineficaz. {atk['nombre']} no hace daño a {dfn['nombre']}. "
                f"Usa esta unidad en otro objetivo o como soporte."
            )

        if nivel_riesgo == "moderado":
            if kill_probable and not kill_seguro:
                return (
                    f"Riesgo moderado. {atk['nombre']} probablemente mata ({atk['precision']}% hit), "
                    f"pero si falla, {dfn['nombre']} contraatacara o podra actuar en su turno. "
                    f"Ten una segunda unidad lista para rematar."
                )
            return (
                "Riesgo moderado. La accion es viable pero no esta 100% libre de riesgo en turnos posteriores."
            )

        # Riesgo bajo
        if kill_seguro:
            return (
                f"Kill seguro. {atk['nombre']} elimina a {dfn['nombre']} con certeza. "
                f"No habra respuesta en el turno enemigo."
            )

        if alertas["contraataque_bloqueado"]:
            return (
                f"Ataque seguro en esta ronda. {atk['nombre']} golpea sin contraataque inmediato, "
                f"pero ten en cuenta la posicion final si {dfn['nombre']} sobrevive para su turno."
            )

        return (
            f"Riesgo bajo. {atk['nombre']} puede atacar con seguridad. "
            f"Resultado esperado: {dfn['nombre']} queda en {res['hp_defensor_final']}/{dfn['hp_inicial']} HP."
        )


# =============================================================================
# Ejemplo de uso
# =============================================================================

if __name__ == "__main__":
    import json

    # ── Definir unidades ──
    alear = Unidad(
        nombre="Alear", hp=35,
        fuerza=15, magia=5, destreza=12, velocidad=16,
        defensa=10, resistencia=8, suerte=10, complexion=7,
    )
    espada_hierro = Arma(
        nombre="Espada de Hierro", mt=5, wt=5, hit=90, crit=0,
        es_magica=False, tipo="Espada", rango=[1],
    )

    mago = Unidad(
        nombre="Mago Enemigo", hp=25,
        fuerza=2, magia=14, destreza=10, velocidad=10,
        defensa=4, resistencia=12, suerte=8, complexion=4,
    )
    tomo_fuego = Arma(
        nombre="Tomo de Fuego", mt=6, wt=4, hit=85, crit=0,
        es_magica=True, tipo="Tomo", rango=[1, 2],
    )

    # Jefe fuerte para escenario de riesgo
    jefe = Unidad(
        nombre="Jefe Enemigo", hp=45,
        fuerza=20, magia=3, destreza=14, velocidad=12,
        defensa=18, resistencia=6, suerte=5, complexion=12,
    )
    hacha_plata = Arma(
        nombre="Hacha de Plata", mt=14, wt=11, hit=75, crit=5,
        es_magica=False, tipo="Hacha", rango=[1],
    )

    # ── Terreno del defensor (ej. bosque) ──
    bosque = Terreno(avo=15, dfn=1)

    # =================================================================
    # TEST 1: Combate seguro — Alear mata al Mago
    # =================================================================
    print("=" * 60)
    print("TEST 1: Alear (Espada) vs Mago (Tomo) — Distancia 1")
    print("=" * 60)

    riesgo_1 = CalculadoraEngage.evaluar_riesgo(
        alear, mago, espada_hierro, tomo_fuego,
        terreno_def=bosque, distancia=1, perfil="seguro",
    )
    print("VEREDICTO:", json.dumps(riesgo_1["veredicto"], indent=2, ensure_ascii=False))
    print("RECOMENDACION:", riesgo_1["recomendacion"])

    # =================================================================
    # TEST 2: Riesgo critico — Alear vs Jefe (Espada vs Hacha)
    # Alear tiene ventaja de triangulo pero el Jefe pega muy fuerte
    # =================================================================
    print("\n" + "=" * 60)
    print("TEST 2: Alear (Espada) vs Jefe (Hacha) — Riesgo alto")
    print("  Alear tiene ventaja de armas pero el Jefe es letal")
    print("=" * 60)

    riesgo_2 = CalculadoraEngage.evaluar_riesgo(
        alear, jefe, espada_hierro, hacha_plata,
        distancia=1, perfil="seguro",
    )
    print("VEREDICTO:", json.dumps(riesgo_2["veredicto"], indent=2, ensure_ascii=False))
    print("RECOMENDACION:", riesgo_2["recomendacion"])

    # =================================================================
    # TEST 3: Mismo combate pero con perfil Agresivo
    # =================================================================
    print("\n" + "=" * 60)
    print("TEST 3: Mismo combate (Alear vs Jefe) — Perfil AGRESIVO")
    print("=" * 60)

    riesgo_3 = CalculadoraEngage.evaluar_riesgo(
        alear, jefe, espada_hierro, hacha_plata,
        distancia=1, perfil="agresivo",
    )
    print("VEREDICTO:", json.dumps(riesgo_3["veredicto"], indent=2, ensure_ascii=False))
    print("RECOMENDACION:", riesgo_3["recomendacion"])

    # =================================================================
    # TEST 4: Ataque a distancia sin represalia
    # =================================================================
    print("\n" + "=" * 60)
    print("TEST 4: Mago ataca a Alear a distancia 2 (sin contra)")
    print("=" * 60)

    riesgo_4 = CalculadoraEngage.evaluar_riesgo(
        mago, alear, tomo_fuego, espada_hierro,
        distancia=2, perfil="seguro",
    )
    print("VEREDICTO:", json.dumps(riesgo_4["veredicto"], indent=2, ensure_ascii=False))
    print("RECOMENDACION:", riesgo_4["recomendacion"])

    # =================================================================
    # TEST 5: Letalidad Inversa — Lancero vs Jefe (sin ventaja de armas)
    # El Lancero no rompe al Jefe, y el Jefe pega letal
    # =================================================================
    print("\n" + "=" * 60)
    print("TEST 5: Lancero vs Jefe (Lanza vs Hacha) — Perfil SEGURO")
    print("  Lancero NO tiene ventaja (Lanza pierde vs nada aqui)")
    print("  El Jefe es letal en contraataque")
    print("=" * 60)

    lancero = Unidad(
        nombre="Lancero", hp=22,
        fuerza=13, magia=2, destreza=11, velocidad=14,
        defensa=9, resistencia=5, suerte=7, complexion=6,
    )
    lanza_hierro = Arma(
        nombre="Lanza de Hierro", mt=6, wt=6, hit=80, crit=0,
        es_magica=False, tipo="Lanza", rango=[1],
    )

    riesgo_5 = CalculadoraEngage.evaluar_riesgo(
        lancero, jefe, lanza_hierro, hacha_plata,
        distancia=1, perfil="seguro",
    )
    print("VEREDICTO:", json.dumps(riesgo_5["veredicto"], indent=2, ensure_ascii=False))
    print("RECOMENDACION:", riesgo_5["recomendacion"])

    # =================================================================
    # TEST 7: Caso del usuario — Alear (Lord, 25 HP) vs Bandido (20 HP, da 25 en su turno)
    # Alear rompe al Bandido (no hay contraataque en Player Phase), pero el Bandido sobrevive con 5 HP.
    # En el Turno Enemigo, el Break expiró y el Bandido ataca matando a Alear -> ALERTA GAME OVER!
    # =================================================================
    print("\n" + "=" * 60)
    print("TEST 7: Alear (Lord 25HP) vs Bandido (Hacha 20HP) — Ruptura + Muerte en Turno Enemigo")
    print("=" * 60)

    alear_25hp = Unidad(
        nombre="Alear", hp=25,
        fuerza=10, magia=0, destreza=12, velocidad=15,
        defensa=5, resistencia=5, suerte=10, complexion=7,
        es_lord=True  # Lord esencial
    )
    espada_test = Arma(
        nombre="Espada de Hierro", mt=5, wt=5, hit=90, crit=0,
        es_magica=False, tipo="Espada", rango=[1]
    )

    bandido = Unidad(
        nombre="Bandido", hp=30,
        fuerza=25, magia=0, destreza=8, velocidad=14,
        defensa=0, resistencia=0, suerte=0, complexion=10,
        es_lord=False
    )
    hacha_gran_peso = Arma(
        nombre="Hacha Gran", mt=12, wt=8, hit=80, crit=0,
        es_magica=False, tipo="Hacha", rango=[1]
    )

    riesgo_7 = CalculadoraEngage.evaluar_riesgo(
        alear_25hp, bandido, espada_test, hacha_gran_peso,
        distancia=1, perfil="seguro", cronogema_usada=False
    )
    print("VEREDICTO:", json.dumps(riesgo_7["veredicto"], indent=2, ensure_ascii=False))
    print("RECOMENDACION:", riesgo_7["recomendacion"])

    # =================================================================
    # TEST 8: Rebobinado con Cronogema (Manipulación de RNG / Quemar RNs)
    # =================================================================
    print("\n" + "=" * 60)
    print("TEST 8: Rebobinado con Cronogema tras un fallo previo (Quemar RNs)")
    print("=" * 60)

    riesgo_8 = CalculadoraEngage.evaluar_riesgo(
        alear_25hp, bandido, espada_test, hacha_gran_peso,
        distancia=1, perfil="seguro", cronogema_usada=True
    )
    print("VEREDICTO:", json.dumps(riesgo_8["veredicto"], indent=2, ensure_ascii=False))
    print("RECOMENDACION:", riesgo_8["recomendacion"])

    # =================================================================
    # TEST 9: IA Espacial / Rango en Turno Enemigo
    # Alear ataca a distancia 1 a un Arquero (Arco rango [2]).
    # En turno del jugador: Arquero no contraataca (rango 2 != 1).
    # En turno enemigo: Arquero da un paso atrás (distancia 2), ataca sin contraataque y mata a Alear.
    # =================================================================
    print("\n" + "=" * 60)
    print("TEST 9: IA Espacial — Alear (Espada R1) vs Arquero (Arco R2) a Distancia 1")
    print("  En Player Phase no hay contraataque, pero el Arquero se aleja a R2 en Enemy Phase")
    print("=" * 60)

    alear_espada_corta = Unidad(
        nombre="Alear", hp=18,
        fuerza=11, magia=0, destreza=12, velocidad=14,
        defensa=4, resistencia=3, suerte=8, complexion=7,
        es_lord=True
    )
    espada_r1 = Arma(
        nombre="Espada de Hierro", mt=5, wt=5, hit=90, crit=0,
        es_magica=False, tipo="Espada", rango=[1]
    )

    arquero_enemigo = Unidad(
        nombre="Arquero", hp=28,
        fuerza=18, magia=0, destreza=14, velocidad=12,
        defensa=6, resistencia=2, suerte=5, complexion=6,
        es_lord=False
    )
    arco_r2 = Arma(
        nombre="Arco de Hierro", mt=6, wt=5, hit=85, crit=0,
        es_magica=False, tipo="Arco", rango=[2]
    )

    riesgo_9 = CalculadoraEngage.evaluar_riesgo(
        alear_espada_corta, arquero_enemigo, espada_r1, arco_r2,
        distancia=1, perfil="seguro"
    )
    print("VEREDICTO:", json.dumps(riesgo_9["veredicto"], indent=2, ensure_ascii=False))
    print("RECOMENDACION:", riesgo_9["recomendacion"])

    # =================================================================
    # TEST 10: Recarga de Medidor de Emblema al Derrotar Enemigos + Libération
    # Alear (4/6 cargas) remata a un Ladrón (10 HP) con Libération -> gana +3 cargas (1 combate + 2 kill Libération)
    # Resultado: ¡Fusión al 100% (6/6 cargas) lista para el próximo turno!
    # =================================================================
    print("\n" + "=" * 60)
    print("TEST 10: Recarga de Medidor de Emblema al Derrotar Enemigo (Libération)")
    print("  Alear tiene 4/6 cargas. Remata a un enemigo débil con Libération")
    print("=" * 60)

    alear_medidor = Unidad(
        nombre="Alear", hp=30,
        fuerza=18, magia=4, destreza=16, velocidad=18,
        defensa=12, resistencia=8, suerte=12, complexion=8,
        es_lord=True,
        energia_emblema=4,
        max_energia_emblema=6,
        turnos_fusion_restantes=0,
        es_dragon=True,
    )
    liberation = Arma(
        nombre="Libération", mt=8, wt=6, hit=95, crit=5,
        es_magica=False, tipo="Espada", rango=[1]
    )
    ladron = Unidad(
        nombre="Ladrón", hp=10,
        fuerza=8, magia=0, destreza=10, velocidad=12,
        defensa=4, resistencia=2, suerte=5, complexion=5,
        es_lord=False
    )
    daga_bronce = Arma(
        nombre="Daga de Bronce", mt=2, wt=2, hit=90, crit=0,
        es_magica=False, tipo="Daga", rango=[1, 2]
    )

    riesgo_10 = CalculadoraEngage.evaluar_riesgo(
        alear_medidor, ladron, liberation, daga_bronce,
        distancia=1, perfil="seguro"
    )
    print("VEREDICTO:", json.dumps(riesgo_10["veredicto"], indent=2, ensure_ascii=False))
    print("RECOMENDACION:", riesgo_10["recomendacion"])
