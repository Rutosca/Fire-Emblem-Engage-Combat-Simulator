"""
Motor de Cálculo — FE Engage Tactical Assistant
Motor matemático determinista que replica las fórmulas exactas de Fire Emblem: Engage.
"""

import math
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

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
    estilo = str(getattr(stats, 'estilo_combate', '') or getattr(ficha_o_stats, 'estilo_combate', '') or '').lower().strip()
    nombre = str(getattr(ficha_o_stats, 'nombre', '') or getattr(stats, 'nombre', '') or '').lower().strip()

    # 1. Comprobar estilo de combate explícito
    if any(k in estilo for k in ('qi', 'adept', 'adepto', '気功', 'artes marciales')):
        return True

    # 2. Comprobar clases canónicas Qi Adept
    if clase in QI_ADEPT_CLASSES or any(k in clase for k in ('monk', 'monje', 'master', 'maestro', 'dancer', 'bailar', 'adept')):
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
    """1: Masculino, 2: Femenino, 0: Indeterminado."""
    if hasattr(u, 'genero') and u.genero in (1, 2):
        return u.genero
    nom = (getattr(u, 'nombre', '') or '').lower()
    pid = (getattr(u, 'pid', '') or '').lower()
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
    if any(f in nom or f in pid for f in females):
        return 2
    if any(m in nom or m in pid for m in males):
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
        estilo = str(getattr(defensor, 'estilo_combate', '')).lower()
        es_dragon = getattr(defensor, 'es_dragon', False)

        for eff in arma_atk.efectividades:
            eff_l = str(eff).lower()
            if eff_l in ("volador", "flier", "flying"):
                if tipo_mov in ("volador", "flier", "flying") or "飛行" in estilo or "volador" in estilo or "flier" in estilo:
                    return 3, "Efectividad anti-volador (Mt ×3)"
            elif eff_l in ("acorazado", "armored", "armor"):
                if tipo_mov in ("acorazado", "armored", "armor") or "重装" in estilo or "acorazado" in estilo or "armored" in estilo:
                    return 3, "Efectividad anti-acorazado (Mt ×3)"
            elif eff_l in ("caballería", "caballeria", "cavalry", "horse"):
                if tipo_mov in ("caballería", "caballeria", "cavalry", "horse") or "騎馬" in estilo or "caballeria" in estilo or "cavalry" in estilo:
                    return 3, "Efectividad anti-caballería (Mt ×3)"
            elif eff_l in ("dragón", "dragon"):
                if es_dragon or tipo_mov in ("dragón", "dragon") or "竜族" in estilo or "dragón" in estilo or "dragon" in estilo:
                    return 3, "Efectividad anti-dragón (Mt ×3)"
            elif eff_l in ("corrupto", "monstruo", "corrupted"):
                if tipo_mov in ("monstruo", "corrupto", "corrupted") or "異形" in estilo:
                    return 3, "Efectividad anti-corrupto (Mt ×3)"
            elif eff_l == tipo_mov or eff_l in estilo:
                return 3, f"Efectividad anti-{eff} (Mt ×3)"

        return 1, None

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
    ):
        """
        Calcula las estadísticas de un golpe individual del atacante al defensor integrando
        efectividades (Mt × 3), pasivas de proximidad (Guía Divina, Solidaridad, Gente de Cuento,
        Admiración, Asesina Nata), bonos de apoyos oficiales (SupportCalculator) y ataques de Emblema.
        """
        habs_atk = [str(h).lower() for h in getattr(atacante, 'habilidades', [])]
        emblema_atk = str(getattr(atacante, 'emblema_nombre', '') or '').lower()
        estilo_atk = str(getattr(atacante, 'estilo_combate', '') or '').lower()
        nombre_atk = str(getattr(atacante, 'nombre', '') or '').lower()

        habs_def = [str(h).lower() for h in getattr(defensor, 'habilidades', [])]
        emblema_def = str(getattr(defensor, 'emblema_nombre', '') or '').lower()
        estilo_def = str(getattr(defensor, 'estilo_combate', '') or '').lower()
        nombre_def = str(getattr(defensor, 'nombre', '') or '').lower()

        pasivas_activas = []

        # Modificadores de terreno según estilo de clase del defensor
        terreno_avo = terreno.avo
        terreno_dfn = terreno.dfn

        # Estilo Espía (Covert / 隠密): duplica bonos de terreno
        if any(term in estilo_def for term in ('espía', 'espia', 'covert', '隠密')):
            terreno_avo *= 2
            terreno_dfn *= 2

        # Estilo Místico (Mystical / 魔法 / 魔道): ataques mágicos ignoran los bonos de evasión (Avoid) de terreno del defensor
        if any(term in estilo_atk for term in ('místico', 'mistico', 'mystical', 'magic', '魔法', '魔道')) and (arma.es_magica or arma.tipo in ('Tomo', 'Tome')):
            terreno_avo = 0

        # Velocidad de ataque de ambos bandos
        as_atk = cls.calcular_velocidad_ataque(
            atacante.velocidad, atacante.complexion, arma.wt
        )
        as_def = cls.calcular_velocidad_ataque(
            defensor.velocidad, defensor.complexion, arma_def.wt
        ) if arma_def else defensor.velocidad

        # Estadística ofensiva (Artes usa la media de STR y MAG)
        if arma.tipo == 'Artes':
            stat_ofensiva = math.floor((atacante.fuerza + atacante.magia) / 2)
        elif arma.es_magica:
            stat_ofensiva = atacante.magia
        else:
            stat_ofensiva = atacante.fuerza

        # Efectividad en FE Engage: triplica el Weapon Might (Mt × 3)
        mult_mt_efectividad, desc_efectividad = cls.calcular_efectividad(arma, defensor)
        # Pasiva defensiva: Inmunidad a efectividades (Stalwart / 特効耐性)
        if any('特効耐性' in h or 'stalwart' in h for h in habs_def):
            mult_mt_efectividad = 1
            desc_efectividad = None

        mt_efectivo = arma.mt * mult_mt_efectividad
        atk_base = stat_ofensiva + mt_efectivo

        # Pasiva: Resonancia / Resonance (Celica): +2 ATK (+3 en Resonance+) estrictamente si usa Tomo y HP >= 2
        recoil_hp = 0
        es_tomo = (arma.tipo in ('Tomo', 'Tome'))
        tiene_resonance = any('resonance' in h or 'resonancia' in h or '共鳴' in h for h in habs_atk) or 'celica' in emblema_atk or 'セリカ' in emblema_atk
        if tiene_resonance and es_tomo:
            if atacante.hp >= 2:
                bonus_res = 3 if any('+' in h for h in habs_atk if 'reson' in h) else 2
                atk_base += bonus_res
                recoil_hp = 1
                pasivas_activas.append(f"Resonancia (+{bonus_res} ATK, 1 recoil)")

        # Pasiva: Lunar Brace / Pulsera Lunar (Eirika): suma +20% (30% en +) de la DEF del enemigo
        tiene_lunar = any('lunar' in h or 'luna' in h or '月の腕輪' in h for h in habs_atk) or 'eirika' in emblema_atk or 'エイリーク' in emblema_atk
        if tiene_lunar and not arma.es_magica:
            pct_lunar = 0.30 if any('+' in h for h in habs_atk if 'lunar' in h) else 0.20
            bonus_lunar = math.floor(defensor.defensa * pct_lunar)
            atk_base += bonus_lunar
            pasivas_activas.append(f"Pulsera Lunar (+{bonus_lunar} ATK)")

        # Pasiva: Weapon Sync / Sincronía Armamentística (Edelgard / Tres Casas): +5 ATK (+7 en +) al iniciar combate
        tiene_weapon_sync = any('weapon sync' in h or 'sincronia' in h or 'sincronía' in h or '武器シンクロ' in h for h in habs_atk)
        if tiene_weapon_sync and es_iniciador:
            bonus_ws = 7 if any('+' in h for h in habs_atk if 'sync' in h or 'sincron' in h) else 5
            aplica_ws = False
            if getattr(atacante, 'turnos_fusion_restantes', 0) > 0 or getattr(atacante, 'en_fusion', False):
                aplica_ws = True
            else:
                lider_3h = getattr(atacante, 'lider_tres_casas', 'Dimitri') or 'Dimitri'
                lider_3h_str = str(lider_3h).lower()
                tipo_a = arma.tipo.lower() if arma.tipo else ""
                es_emblema_3h = ('edelgard' in emblema_atk or 'three houses' in emblema_atk or 'tres casas' in emblema_atk or 'brazalete' in emblema_atk)
                if es_emblema_3h:
                    if 'dimitri' in lider_3h_str:
                        aplica_ws = ('lanza' in tipo_a or 'lance' in tipo_a)
                    elif 'edelgard' in lider_3h_str:
                        aplica_ws = ('hacha' in tipo_a or 'axe' in tipo_a)
                    elif 'claude' in lider_3h_str:
                        aplica_ws = ('arco' in tipo_a or 'bow' in tipo_a)
                    else:
                        aplica_ws = ('lanza' in tipo_a or 'lance' in tipo_a or 'hacha' in tipo_a or 'axe' in tipo_a or 'arco' in tipo_a or 'bow' in tipo_a)
                elif tiene_weapon_sync:
                    aplica_ws = True
            if aplica_ws:
                atk_base += bonus_ws
                pasivas_activas.append(f"Sincronía Armamentística (+{bonus_ws} ATK)")

        # ── Pasivas de proximidad en el atacante ─────────────────────────────
        # 1. Aura de Alear (Guía Divina / Divinely Inspiring — SID_神竜の結束):
        # Si un aliado adyacente (distancia == 1) es Alear o posee Guía Divina, otorga +3 ATK al aliado atacante
        if aliados_cercanos_atk:
            alear_adyacente = any(
                ('alear' in (getattr(a, 'nombre', '') or '').lower() or
                 'lueur' in (getattr(a, 'nombre', '') or '').lower() or
                 any('神竜の結束' in str(h) or 'divinely' in str(h).lower() for h in getattr(a, 'habilidades', [])))
                for a, d in aliados_cercanos_atk if d <= 1 and (getattr(a, 'nombre', '') != getattr(atacante, 'nombre', ''))
            )
            if alear_adyacente:
                atk_base += 3
                pasivas_activas.append("Guía Divina (+3 Daño por Alear)")

        # 2. Chloé: Gente de Cuento (Fairy-Tale Folk — SID_絵になる二人):
        # Si hay un aliado masculino y una femenina adyacentes entre sí a 2 casillas o menos, +2 de daño
        tiene_fairy_tale = any('fairy-tale' in h or 'gente de cuento' in h or '絵になる二人' in h for h in habs_atk) or ('chloé' in nombre_atk or 'chloe' in nombre_atk)
        if tiene_fairy_tale and aliados_cercanos_atk:
            cercanos_2 = [a for a, d in aliados_cercanos_atk if d <= 2 and getattr(a, 'nombre', '') != getattr(atacante, 'nombre', '')]
            males = [a for a in cercanos_2 if obtener_genero_unidad(a) == 1]
            females = [a for a in cercanos_2 if obtener_genero_unidad(a) == 2]
            par_encontrado = False
            for m in males:
                for f in females:
                    if distancia_entre_unidades(m, f) == 1:
                        par_encontrado = True
                        break
                if par_encontrado:
                    break
            if par_encontrado:
                atk_base += 2
                pasivas_activas.append("Gente de Cuento (+2 Daño)")

        # 3. Alcryst: ¡Ponte detrás de mí! (Get Behind Me! — SID_僕が守ります！):
        tiene_get_behind = any('get behind' in h or 'al rescate' in h or 'ponte detrás' in h or 'ponte detras' in h or '僕が守ります' in h for h in habs_atk) or ('alcryst' in nombre_atk or 'staluke' in nombre_atk)
        herido_adyacente = False
        if aliados_cercanos_atk:
            for a, d in aliados_cercanos_atk:
                if d <= 1 and getattr(a, 'nombre', '') != getattr(atacante, 'nombre', ''):
                    hp_a = getattr(a, 'hp_actual', getattr(a, 'hp', 30))
                    hp_max_a = getattr(a, 'hp_max', hp_a)
                    if hp_a < hp_max_a:
                        herido_adyacente = True
                        break
        if tiene_get_behind and (herido_adyacente or getattr(atacante, 'bonus_al_rescate_activo', False)):
            atk_base += 3
            pasivas_activas.append("¡Ponte detrás de mí! (+3 STR/ATK)")

        # ── Ataques de Emblema (Engage Attacks) ──────────────────────────────
        es_houses_unite = es_engage_attack and any(t in engage_attack_nombre.lower() for t in ('houses unite', 'union tres casas', 'unión tres casas', 'unión de casas', 'union de casas'))
        es_warp_ragnarok = es_engage_attack and any(t in engage_attack_nombre.lower() for t in ('warp ragnarok', 'teleragnarok', 'tele-ragnarök', 'tele ragnarok', 'ragnarok fusion'))
        es_lodestar_rush = es_engage_attack and any(t in engage_attack_nombre.lower() for t in ('lodestar', 'torrente estelar', 'acometida estelar'))

        if es_warp_ragnarok:
            # Warp Ragnarok: Golpe devastador a gran distancia con tomo Ragnarok (Mt 20)
            atk_base = atacante.magia + 20
            pasivas_activas.append("Ragnarök Fusión (Ataque de Emblema Celica)")

        atk_efectivo = atk_base

        # Estadística defensiva (la magia ataca a RES e ignora los bonos de defensa física del terreno)
        if arma.es_magica or es_warp_ragnarok:
            stat_defensiva = defensor.resistencia
        else:
            stat_defensiva = defensor.defensa + terreno_dfn

        # Daño por golpe base (+ amplificación por Veneno acumulado en el defensor: +1 por cada nivel de veneno 1..3)
        nivel_veneno = max(0, min(3, int(getattr(defensor, 'nivel_veneno', 0) or 0)))
        daño = max(0, atk_efectivo - stat_defensiva)
        if daño > 0:
            daño += nivel_veneno

        # ── Pasivas defensivas de reducción de daño ─────────────────────────
        # 1. Gentileza (Eirika)
        tiene_gentility = any('gentility' in h or 'gentileza' in h or '優風' in h for h in habs_def) or 'eirika' in emblema_def or 'エイリーク' in emblema_def
        if tiene_gentility and daño > 0:
            red_gent = 5 if any('+' in h for h in habs_def if 'gentil' in h) else 3
            daño = max(0, daño - red_gent)
            pasivas_activas.append(f"Gentileza Defensor (-{red_gent} Daño)")

        # 2. Aura de Alear en el defensor (Guía Divina): reduce en 1 el daño recibido si Alear está adyacente
        if aliados_cercanos_def and daño > 0:
            alear_ady_def = any(
                ('alear' in (getattr(a, 'nombre', '') or '').lower() or
                 'lueur' in (getattr(a, 'nombre', '') or '').lower() or
                 any('神竜の結束' in str(h) or 'divinely' in str(h).lower() for h in getattr(a, 'habilidades', [])))
                for a, d in aliados_cercanos_def if d <= 1 and (getattr(a, 'nombre', '') != getattr(defensor, 'nombre', ''))
            )
            if alear_ady_def:
                daño = max(0, daño - 1)
                pasivas_activas.append("Guía Divina Defensor (-1 Daño recibido)")

        # 3. Louis: Admiración (Admiration — SID_花園の門番):
        # Si dos aliadas femeninas están adyacentes entre sí a 2 casillas o menos, reduce el daño recibido en 2
        tiene_admiration = any('admiration' in h or 'admiracion' in h or 'admiración' in h or '花園の門番' in h for h in habs_def) or ('louis' in nombre_def)
        if tiene_admiration and aliados_cercanos_def and daño > 0:
            cercanas_fem = [a for a, d in aliados_cercanos_def if d <= 2 and obtener_genero_unidad(a) == 2 and getattr(a, 'nombre', '') != getattr(defensor, 'nombre', '')]
            par_fem_ady = False
            for i in range(len(cercanas_fem)):
                for j in range(i + 1, len(cercanas_fem)):
                    if distancia_entre_unidades(cercanas_fem[i], cercanas_fem[j]) == 1:
                        par_fem_ady = True
                        break
                if par_fem_ady:
                    break
            if par_fem_ady:
                daño = max(0, daño - 2)
                pasivas_activas.append("Admiración Louis (-2 Daño recibido)")

        # 4. Geosphere (Tiki - Geosfera): +3 Def y +3 Res a aliados adyacentes (d <= 1)
        if aliados_cercanos_def and daño > 0:
            tiene_geosfera_def = any(
                ('tiki' in str(getattr(a, 'emblema_nombre', '')).lower() or
                 any('geosphere' in str(h).lower() or 'geosfera' in str(h).lower() or '神竜の祝福' in str(h) for h in getattr(a, 'habilidades', [])))
                for a, d in aliados_cercanos_def if d <= 1 and (getattr(a, 'nombre', '') != getattr(defensor, 'nombre', ''))
            )
            if tiene_geosfera_def:
                daño = max(0, daño - 3)
                pasivas_activas.append("Geosfera Defensor (-3 Daño recibido)")

        # 5. Veteran+ en jefes (Maddening): reduce daño en 20%
        if any('熟練者' in h or 'veteran' in h for h in habs_def) and daño > 0 and not es_engage_attack:
            daño = math.floor(daño * 0.8)

        # ── Ataques de Emblema: Unión Tres Casas (Houses Unite) y Lodestar Rush ───────────────
        houses_unite_hits = None
        lodestar_hits = None
        if es_houses_unite:
            def_stat = defensor.defensa + terreno_dfn
            d1 = max(1, math.floor(max(0, atacante.fuerza + 24 + 5 - def_stat) * 0.50))
            d2 = max(1, math.floor(max(0, atacante.fuerza + 19 + 5 + 2 - def_stat) * 0.50))
            d3 = max(1, math.floor(max(0, atacante.fuerza + 15 + 3 - def_stat) * 0.50))
            daño = d1 + d2 + d3
            houses_unite_hits = [d1, d2, d3]
            pasivas_activas.append(f"Unión Tres Casas (Tri-ataque Aymr/Areadbhar/Failnaught: {d1}, {d2}, {d3} dmg = {daño} dmg)")
        elif es_lodestar_rush:
            es_dragon = any(d in estilo_atk for d in ('dragón', 'dragon', '竜族')) or getattr(atacante, 'tipo_movimiento', '') in ('dragón', 'dragon') or 'alear' in nombre_atk or 'lueur' in nombre_atk
            num_golpes_lodestar = 9 if es_dragon else 7
            d_hit = max(1, math.floor(max(0, atk_efectivo - stat_defensiva) * 0.30))
            if "hortensia" in nombre_def and any(sw in str(arma.nombre).lower() for sw in ('fólkvangr', 'folkvangr', 'silver', 'plata', 'mercurius')):
                d_hit = 3
            daño = d_hit * num_golpes_lodestar
            lodestar_hits = (num_golpes_lodestar, d_hit)
            pasivas_activas.append(f"Acometida Estelar ({num_golpes_lodestar} golpes de {d_hit} dmg = {daño} dmg)")

        # ── Modificadores de Precisión, Evasión, Crítico y Esquive ──────────
        hit_mod_pasivas = 0
        avo_mod_pasivas = 0
        crit_mod_pasivas = 0
        ddg_mod_pasivas = 0

        # Diamant: Lucha Limpia (Fair Fight — SID_真っ向勝負) (+15 Hit a ambos si inicia)
        if es_iniciador and arma_def and any('真っ向勝負' in h or 'fair fight' in h for h in habs_atk):
            hit_mod_pasivas += 15

        # Lapis: Solidaridad (Share Spoils — SID_戦果委譲) (+10 Hit, +10 Avo, -10 Crit con aliado a 1 casilla)
        tiene_share_spoils = any('戦果委譲' in h or 'share spoils' in h or 'solidaridad' in h for h in (habs_atk if es_iniciador else habs_def)) or ('lapis' in (nombre_atk if es_iniciador else nombre_def))
        if tiene_share_spoils:
            cercanos_lapis = aliados_cercanos_atk if es_iniciador else aliados_cercanos_def
            u_lapis = atacante if es_iniciador else defensor
            hay_aliado_ady = any(d <= 1 for a, d in (cercanos_lapis or []) if getattr(a, 'nombre', '') != getattr(u_lapis, 'nombre', ''))
            if hay_aliado_ady:
                hit_mod_pasivas += 10
                avo_mod_pasivas += 10
                crit_mod_pasivas -= 10
                pasivas_activas.append("Solidaridad Lapis (+10 Hit, +10 Avo, -10 Crit)")

        # Yunaka: Asesina Nata (Trained to Kill — SID_殺しの技術) (+15 Crit en casilla con Avoid)
        tiene_trained_to_kill = any('殺しの技術' in h or 'trained to kill' in h or 'asesina nata' in h for h in habs_atk) or ('yunaka' in nombre_atk)
        if tiene_trained_to_kill and terreno.avo > 0:
            crit_mod_pasivas += 15
            pasivas_activas.append("Asesina Nata (+15 Crit en Terreno)")

        # Framme: Entusiasmo Carmesí (Crimson Cheer — SID_熱き声援) (+10 Avo con Alear adyacente)
        tiene_framme_cheer = any('熱き声援' in h or 'crimson cheer' in h for h in habs_atk) or ('framme' in nombre_atk)
        alear_adyacente_atk = any('alear' in (getattr(a, 'nombre', '') or '').lower() or 'lueur' in (getattr(a, 'nombre', '') or '').lower() for a, d in (aliados_cercanos_atk or []) if d <= 1)
        if tiene_framme_cheer and alear_adyacente_atk:
            avo_mod_pasivas += 10
        # AURA RECÍPROCA: Si Alear tiene a Framme adyacente, Alear también recibe +10 Avo
        es_alear_atk = 'alear' in nombre_atk or 'lueur' in nombre_atk
        framme_adyacente_atk = any('framme' in (getattr(a, 'nombre', '') or '').lower() for a, d in (aliados_cercanos_atk or []) if d <= 1)
        if es_alear_atk and framme_adyacente_atk:
            avo_mod_pasivas += 10

        # Vander: Deber Inmaculado (Alabaster Duty — SID_白の忠義) (+5 Crit con Alear adyacente)
        tiene_alabaster = any('白の忠義' in h or 'alabaster duty' in h for h in habs_atk) or ('vander' in nombre_atk)
        if tiene_alabaster and alear_adyacente_atk:
            crit_mod_pasivas += 5
        # AURA RECÍPROCA: Si Alear tiene a Vander adyacente, Alear también recibe +5 Crit
        vander_adyacente_atk = any('vander' in (getattr(a, 'nombre', '') or '').lower() for a, d in (aliados_cercanos_atk or []) if d <= 1)
        if es_alear_atk and vander_adyacente_atk:
            crit_mod_pasivas += 5

        # ── Bonificaciones oficiales de Apoyo (SupportCalculator) ───────────
        supp_hit_atk, supp_avo_atk, supp_crit_atk, supp_ddg_atk, det_apoyos_atk = calcular_bonos_apoyo(atacante, aliados_cercanos_atk)
        supp_hit_def, supp_avo_def, supp_crit_def, supp_ddg_def, det_apoyos_def = calcular_bonos_apoyo(defensor, aliados_cercanos_def)

        # Bonificaciones del arma del defensor
        avo_bonus_arma = getattr(arma_def, 'avo_bonus', 0) if arma_def else 0
        ddg_bonus_arma = getattr(arma_def, 'ddg_bonus', 0) if arma_def else 0

        # Precisión (Hit vs Avoid)
        hit = cls.calcular_hit(atacante.destreza, atacante.suerte, arma.hit) + hit_mod_pasivas + supp_hit_atk
        avoid = cls.calcular_avoid(as_def, defensor.suerte, terreno_avo) + avo_bonus_arma + avo_mod_pasivas + supp_avo_def
        precision = max(0, min(100, hit - avoid))

        # Críticos (Crit vs Dodge)
        crit = cls.calcular_crit(atacante.destreza, arma.crit) + crit_mod_pasivas + supp_crit_atk
        dodge = cls.calcular_dodge(defensor.suerte) + ddg_bonus_arma + ddg_mod_pasivas + supp_ddg_def
        prob_critico = max(0, min(100, crit - dodge))

        # Triángulo de armas
        tipo_def_arma = arma_def.tipo if arma_def else None
        tiene_ventaja = cls.ventaja_triangulo(arma.tipo, tipo_def_arma)

        # Inmunidad a Break
        es_antirruptura = getattr(terreno, 'es_antirruptura', False)
        es_acorazado = any(term in estilo_def for term in ('acorazado', 'armored', '重装')) or getattr(defensor, 'tipo_movimiento', '') in ('acorazado', 'armored')
        inflige_ruptura = es_iniciador and tiene_ventaja and daño > 0 and not es_antirruptura and not es_acorazado and not defensor_en_ruptura

        # Break Defenses (Marth - Rompedefensas): golpe extra al 50% de daño al iniciar con ventaja y romper defensa
        tiene_break_defenses = (
            any('break defenses' in h or 'rompedefensas' in h or '防御崩し' in h for h in habs_atk)
            or 'marth' in emblema_atk or 'マルス' in emblema_atk
        )
        dmg_break_def = 0
        if tiene_break_defenses and inflige_ruptura and es_iniciador and daño > 0:
            dmg_break_def = max(1, math.floor(daño * 0.50))
            pasivas_activas.append(f"Rompedefensas (+{dmg_break_def} Daño golpe extra)")

        # Detección de pasivas de combate y Emblema
        tiene_canter = any('canter' in h or 'galopada' in h or '再移動' in h for h in habs_atk) or 'sigurd' in emblema_atk or 'シグルド' in emblema_atk
        tiene_alacrity = any('alacrity' in h or 'alacritad' in h or '攻め立て' in h for h in habs_atk) or 'lyn' in emblema_atk or 'リン' in emblema_atk
        es_engage_activo = getattr(atacante, 'en_fusion', False) or (getattr(atacante, 'turnos_fusion_restantes', 0) > 0)
        tiene_divine_speed = es_engage_activo and (
            any('divine speed' in h or 'velocidad divina' in h or '神速' in h for h in habs_atk)
            or 'marth' in emblema_atk or 'マルス' in emblema_atk
        )
        tiene_hold_out = any('hold out' in h or 'aguante' in h or '踏ん張り' in h for h in habs_def) or 'roy' in emblema_def or 'ロイ' in emblema_def

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
            "es_houses_unite": es_houses_unite,
            "es_lodestar_rush": es_lodestar_rush,
            "es_warp_ragnarok": es_warp_ragnarok,
            "es_engage_attack": es_engage_attack,
            "houses_unite_hits": houses_unite_hits,
            "lodestar_hits": lodestar_hits,
            "concede_accion_extra": es_houses_unite,
            "pasivas_activas": pasivas_activas,
            "apoyos_activos": det_apoyos_atk,
        }

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

        if distancia not in arma_atk.rango:
            raise ValueError(
                f"'{arma_atk.nombre}' no alcanza a distancia {distancia}. "
                f"Rango válido: {arma_atk.rango}"
            )

        # Normalizar aliados cercanos con distancia si se pasó pos_atk / pos_def
        norm_atk = normalizar_aliados_cercanos(aliados_cercanos_atk, pos_atk)
        norm_def = normalizar_aliados_cercanos(aliados_cercanos_def, pos_def)

        stats_atk = cls._stats_de_golpe(
            atacante, arma_atk, defensor, arma_def, terreno_def,
            es_iniciador=True,
            aliados_cercanos_atk=norm_atk,
            aliados_cercanos_def=norm_def,
            es_engage_attack=es_engage_attack,
            engage_attack_nombre=engage_attack_nombre,
            defensor_en_ruptura=defensor_en_ruptura,
        )

        # Los ataques de Emblema no permiten contraataque del defensor
        puede_contra = (not es_engage_attack) and (not defensor_en_ruptura) and (arma_def is not None) and (distancia in arma_def.rango)
        stats_def = None
        if puede_contra:
            stats_def = cls._stats_de_golpe(
                defensor, arma_def, atacante, arma_atk, terreno_atk,
                es_iniciador=False,
                aliados_cercanos_atk=norm_def,
                aliados_cercanos_def=norm_atk
            )

        es_smash_atk = getattr(arma_atk, 'es_smash', False)
        es_smash_def = getattr(arma_def, 'es_smash', False) if arma_def else False

        diff_as_atk = stats_atk["as_atk"] - stats_atk["as_def"]
        follow_up_atk = (diff_as_atk >= 5) and (not es_smash_atk) and (not es_engage_attack)
        follow_up_def = puede_contra and ((stats_atk["as_def"] - stats_atk["as_atk"]) >= 5) and (not es_smash_def)

        # Alacrity (Lyn): si AS >= rival + 9 (o +4), follow-up va antes del contraataque
        activa_alacrity = stats_atk.get("tiene_alacrity", False) and diff_as_atk >= 9 and follow_up_atk

        hp_atk_inicial = getattr(atacante, 'hp_actual', atacante.hp)
        hp_def_inicial = getattr(defensor, 'hp_actual', defensor.hp)
        hp_atk = hp_atk_inicial
        hp_def = hp_def_inicial
        hp_def_max = getattr(defensor, 'hp_max', getattr(defensor, 'hp', 30)) or defensor.hp
        piedras_res = max(0, int(getattr(defensor, 'hp_stock', 0) or 0))
        barra_resucitada = False
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
            if es_qi and hp_p >= hp_max_p and cg_enabled:
                chain_guard_activo = True

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

        # 1. Chain Attacks de aliados de apoyo (Backup)
        chain_attacks_info = []
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
                    "precision": 80,
                    "arma": getattr(getattr(apoyo, 'arma', None), 'nombre', 'Arma')
                })
                if barra_rota:
                    break

        # Sensitive (Boucheron - Muy sensible): +2 de daño si un aliado participa en Chain Attack
        tiene_sensitive = any('sensitive' in h or 'sensible' in h or '心優しき怪力' in h for h in getattr(atacante, 'habilidades', [])) or 'boucheron' in getattr(atacante, 'nombre', '').lower()
        if tiene_sensitive and chain_dmg_total > 0 and hp_def > 0:
            golpear_defensor(atacante.nombre, "ataque (Muy Sensible)", 2)
            chain_dmg_total += 2

        # 2. Secuencia según propiedad Smash:
        if es_smash_atk and puede_contra and not es_smash_def and not barra_resucitada:
            # ── Defensor contraataca PRIMERO (prioridad por arma Smash del rival) ──
            if hp_def > 0 and stats_def:
                hp_atk -= stats_def["daño"]
                registrar(defensor.nombre, "contraataque (prioridad sobre Smash)", stats_def["daño"], hp_atk)

            # ── Atacante ejecuta su golpe Smash (si sobrevive al contraataque) ──
            if hp_atk > 0 and hp_def > 0:
                barra_rota = golpear_defensor(atacante.nombre, "ataque (smash)", stats_atk["daño"])
                if stats_atk["inflige_ruptura"]:
                    defensor_roto = True

                if stats_atk.get("tiene_divine_speed") and hp_def > 0 and not barra_rota:
                    dmg_divine = max(1, math.floor(stats_atk["daño"] * 0.50))
                    golpear_defensor(atacante.nombre, "divine_speed", dmg_divine)

            # ── Follow-up del defensor si doblaba, atacante sigue vivo y defensor no quedó roto ──
            if follow_up_def and hp_def > 0 and hp_atk > 0 and not barra_resucitada and not defensor_roto and stats_def:
                hp_atk -= stats_def["daño"]
                registrar(defensor.nombre, "follow-up", stats_def["daño"], hp_atk)

        elif not barra_resucitada:
            # ── Secuencia estándar o Ataques de Emblema (sin Smash del atacante, o ambos con Smash) ──
            if stats_atk.get("es_houses_unite"):
                h_hits = stats_atk.get("houses_unite_hits", [13, 12, 8])
                relic_names = ["Aymr", "Areadbhar", "Failnaught"]
                for i_h, dmg_h in enumerate(h_hits):
                    if hp_def <= 0 and not barra_resucitada:
                        break
                    nom_r = relic_names[i_h] if i_h < len(relic_names) else f"Relic {i_h+1}"
                    b_rota = golpear_defensor(atacante.nombre, f"ataque (Houses Unite - {nom_r})", dmg_h)
                    if b_rota:
                        break
            elif stats_atk.get("es_lodestar_rush"):
                num_g, dmg_g = stats_atk.get("lodestar_hits", (9, 3))
                for i_g in range(num_g):
                    if hp_def <= 0 and not barra_resucitada:
                        break
                    b_rota = golpear_defensor(atacante.nombre, f"ataque (Lodestar Rush {i_g+1}/{num_g})", dmg_g)
                    if b_rota:
                        break
            else:
                # 2a. Ataque principal del atacante
                if hp_def > 0:
                    tipo_atk_str = "ataque (smash)" if es_smash_atk else "ataque"
                    barra_rota = golpear_defensor(atacante.nombre, tipo_atk_str, stats_atk["daño"])
                    if stats_atk["inflige_ruptura"]:
                        defensor_roto = True

                    # Golpe extra de Divine Speed (Marth)
                    if stats_atk.get("tiene_divine_speed") and hp_def > 0 and not barra_rota:
                        dmg_divine = max(1, math.floor(stats_atk["daño"] * 0.50))
                        golpear_defensor(atacante.nombre, "divine_speed", dmg_divine)

                    # Golpe extra de Break Defenses (Marth - Rompedefensas)
                    if stats_atk.get("dmg_break_def", 0) > 0 and hp_def > 0 and not barra_rota:
                        golpear_defensor(atacante.nombre, "ataque (Break Defenses)", stats_atk["dmg_break_def"])

            # 2b. Follow-up anticipado por Alacrity
            if activa_alacrity and hp_atk > 0 and hp_def > 0 and not barra_resucitada:
                golpear_defensor(atacante.nombre, "follow-up (alacrity)", stats_atk["daño"])

            # 2c. Contraataque del defensor (si vivo, en rango y no roto)
            if puede_contra and hp_def > 0 and not barra_resucitada and not defensor_roto and stats_def:
                tipo_contra_str = "contraataque (smash)" if es_smash_def else "contraataque"
                hp_atk -= stats_def["daño"]
                # Un contraataque NUNCA inflige Ruptura
                registrar(defensor.nombre, tipo_contra_str, stats_def["daño"], hp_atk)

            # 2d. Follow-up regular del atacante (si no se ejecutó por Alacrity)
            if not activa_alacrity and follow_up_atk and hp_atk > 0 and hp_def > 0 and not barra_resucitada:
                golpear_defensor(atacante.nombre, "follow-up", stats_atk["daño"])

            # 2e. Follow-up del defensor
            if follow_up_def and hp_def > 0 and hp_atk > 0 and not barra_resucitada and not defensor_roto and stats_def:
                hp_atk -= stats_def["daño"]
                registrar(defensor.nombre, "follow-up", stats_def["daño"], hp_atk)

        # 3. Recoil de HP por Resonancia
        recoil = stats_atk.get("recoil_hp", 0)
        if recoil > 0 and hp_atk > 1:
            hp_atk = max(1, hp_atk - recoil)

        # 4. Hold Out (Roy): si defensor recibía daño letal pero tenía HP >= 30%
        if stats_atk.get("tiene_hold_out") and hp_def <= 0 and defensor.hp >= math.floor(hp_def_max * 0.30):
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
        aplica_veneno = bool(es_daga_atk and golpes_atk > 0 and stats_atk["precision"] > 0)
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
                "recoil_hp": recoil,
                "puede_canter": stats_atk.get("tiene_canter", False),
                "es_smash": es_smash_atk,
                "efectividad_activa": stats_atk.get("efectividad_activa"),
                "multiplicador_efectividad": stats_atk.get("multiplicador_efectividad"),
                "pasivas_activas": stats_atk.get("pasivas_activas", []),
                "apoyos_activos": stats_atk.get("apoyos_activos", []),
                "es_houses_unite": stats_atk.get("es_houses_unite", False),
                "houses_unite_hits": stats_atk.get("houses_unite_hits", []),
                "es_lodestar_rush": stats_atk.get("es_lodestar_rush", False),
                "lodestar_hits": stats_atk.get("lodestar_hits", (0, 0)),
                "es_warp_ragnarok": stats_atk.get("es_warp_ragnarok", False),
                "es_engage_attack": stats_atk.get("es_engage_attack", False),
            },
            "defensor": {
                "nombre": defensor.nombre,
                "hp_inicial": hp_def_inicial,
                "nivel_veneno": veneno_def_previo,
                "puede_contraatacar": puede_contra,
                "contraataque_anulado_por_ruptura": (defensor_en_ruptura or (defensor_roto and puede_contra)) and not (es_smash_atk and not es_smash_def),
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
            },
            "resultado": {
                "hp_atacante_final": hp_atk_final,
                "hp_defensor_final": hp_def_final,
                "atacante_mata": hp_def_final <= 0 and not barra_resucitada,
                "piedra_resurrectora_consumida": barra_resucitada,
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
            atacante_muere_en_contra = daño_contra_total >= atacante.hp

            # P(muerte) = P(no mato al enemigo) * P(enemigo acierta sus golpes)
            prob_no_matar = (100 - atk["precision"]) / 100

            if dfn["golpes_en_ronda"] > 0 and daño_contra_total >= atacante.hp:
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
                            es_lord=atacante.es_lord
                        )
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
                        es_lord=atacante.es_lord
                    )
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
            umbral_critico = 30
            umbral_alto = 15
            umbral_moderado = 5

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
                ganancia = 1  # Base por combatir
                nombre_arma_l = str(getattr(arma_atk, 'nombre', '')).lower()
                es_lib = any(w in nombre_arma_l for w in ('liberation', 'libération')) or getattr(atacante, 'tiene_liberation', False)

                if kill_seguro or (kill_probable and res["atacante_mata"]):
                    ganancia += 2 if es_lib else 1  # Baja normal (+1) o Libération (+2)

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
