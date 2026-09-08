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
    fuerza: int        # STR - Fuerza física
    magia: int         # MAG - Poder mágico
    destreza: int      # DEX - Destreza / Habilidad
    velocidad: int     # SPD - Velocidad
    defensa: int       # DEF - Defensa física
    resistencia: int   # RES - Resistencia mágica
    suerte: int        # LCK - Suerte
    complexion: int    # BLD - Complexión (Build)
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
    estilo_combate: str = "Infantería"  # De apoyo (Backup), Acorazado (Armored), Espía (Covert), Místico (Mystical), etc.

    def __post_init__(self):
        if self.hp_max <= 0:
            self.hp_max = self.hp


@dataclass
class Arma:
    """Representa un arma con sus estadísticas y propiedades."""
    nombre: str
    mt: int             # Might - Potencia
    wt: int             # Weight - Peso
    hit: int            # Precisión base
    crit: int           # Crítico base
    es_magica: bool     # True = apunta a RES, False = apunta a DEF
    tipo: str           # Espada, Hacha, Lanza, Artes, Arco, Tomo, Daga
    rango: list = field(default_factory=lambda: [1])
    efectividades: list = field(default_factory=list)  # e.g. ["volador", "acorazado"]
    avo_bonus: int = 0  # Bonus de Evasión (ej. Grabados de Emblema)
    ddg_bonus: int = 0  # Bonus de Esquive de Crítico (Dodge)
    es_smash: bool = False  # True si es arma pesada (Smash): ataca de segundo, sin follow-up, empuja 1 casilla


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
    def _stats_de_golpe(cls, atacante, arma, defensor, arma_def, terreno, es_iniciador: bool = True):
        """
        Calcula las estadísticas de un golpe individual del atacante al defensor integrando
        efectividades (Mt × 3), pasivas (Resonancia, Pulsera Lunar, Gentileza) y estilos de combate.
        """
        habs_atk = [str(h).lower() for h in getattr(atacante, 'habilidades', [])]
        emblema_atk = str(getattr(atacante, 'emblema_nombre', '') or '').lower()
        estilo_atk = str(getattr(atacante, 'estilo_combate', '') or '').lower()

        habs_def = [str(h).lower() for h in getattr(defensor, 'habilidades', [])]
        emblema_def = str(getattr(defensor, 'emblema_nombre', '') or '').lower()
        estilo_def = str(getattr(defensor, 'estilo_combate', '') or '').lower()

        # Modificadores de terreno según estilo de clase del defensor
        terreno_avo = terreno.avo
        terreno_dfn = terreno.dfn

        # Estilo Espía (Covert): duplica bonos de terreno
        if estilo_def in ('espía', 'espia', 'covert'):
            terreno_avo *= 2
            terreno_dfn *= 2

        # Estilo Místico (Mystical): ataques mágicos ignoran la DFN de terreno del defensor
        if estilo_atk in ('místico', 'mistico', 'mystical') and arma.es_magica:
            terreno_dfn = 0

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
        mt_efectivo = arma.mt * mult_mt_efectividad

        atk_base = stat_ofensiva + mt_efectivo

        # Pasiva: Resonancia / Resonance (Celica): +2 ATK (+3 en Resonance+) si usa Tomo y HP >= 2
        recoil_hp = 0
        es_tomo_o_magia = (arma.tipo == 'Tomo' or arma.es_magica)
        tiene_resonance = any('resonance' in h or 'resonancia' in h or '共鳴' in h for h in habs_atk) or 'celica' in emblema_atk or 'セリカ' in emblema_atk
        if tiene_resonance and es_tomo_o_magia:
            if atacante.hp >= 2:
                bonus_res = 3 if any('+' in h for h in habs_atk if 'reson' in h) else 2
                atk_base += bonus_res
                recoil_hp = 1

        # Pasiva: Lunar Brace / Pulsera Lunar (Eirika): suma +20% (30% en +) de la DEF del enemigo
        tiene_lunar = any('lunar' in h or 'luna' in h or '月の腕輪' in h for h in habs_atk) or 'eirika' in emblema_atk or 'エイリーク' in emblema_atk
        if tiene_lunar and not arma.es_magica:
            pct_lunar = 0.30 if any('+' in h for h in habs_atk if 'lunar' in h) else 0.20
            atk_base += math.floor(defensor.defensa * pct_lunar)

        atk_efectivo = atk_base

        # Estadística defensiva (la magia ataca a RES e ignora los bonos de defensa física del terreno)
        if arma.es_magica:
            stat_defensiva = defensor.resistencia
        else:
            stat_defensiva = defensor.defensa + terreno_dfn

        # Daño por golpe base
        daño = max(0, atk_efectivo - stat_defensiva)

        # Pasiva: Gentility / Gentileza (Eirika) en el defensor: reduce daño recibido en 3 (o 5 con +)
        tiene_gentility = any('gentility' in h or 'gentileza' in h or '優風' in h for h in habs_def) or 'eirika' in emblema_def or 'エイリーク' in emblema_def
        if tiene_gentility and daño > 0:
            red_gent = 5 if any('+' in h for h in habs_def if 'gentil' in h) else 3
            daño = max(0, daño - red_gent)

        # Bonificaciones de evasión y esquive de crítico en el arma del defensor
        avo_bonus_arma = getattr(arma_def, 'avo_bonus', 0) if arma_def else 0
        ddg_bonus_arma = getattr(arma_def, 'ddg_bonus', 0) if arma_def else 0

        # Precisión (Hit vs Avoid)
        hit = cls.calcular_hit(atacante.destreza, atacante.suerte, arma.hit)
        avoid = cls.calcular_avoid(as_def, defensor.suerte, terreno_avo) + avo_bonus_arma
        precision = max(0, min(100, hit - avoid))

        # Críticos (Crit vs Dodge)
        crit = cls.calcular_crit(atacante.destreza, arma.crit)
        dodge = cls.calcular_dodge(defensor.suerte) + ddg_bonus_arma
        prob_critico = max(0, min(100, crit - dodge))

        # Triángulo de armas
        tipo_def_arma = arma_def.tipo if arma_def else None
        tiene_ventaja = cls.ventaja_triangulo(arma.tipo, tipo_def_arma)

        # Inmunidad a Break: si el defensor está en terreno antirruptura O es de clase Acorazada.
        # REGLA FUNDAMENTAL DE FE ENGAGE: Solo un ataque INICIADO con ventaja de armas puede causar Ruptura.
        # Un contraataque NUNCA puede infligir Ruptura (ni siquiera con ventaja de armas).
        es_antirruptura = getattr(terreno, 'es_antirruptura', False)
        es_acorazado = estilo_def in ('acorazado', 'armored') or getattr(defensor, 'tipo_movimiento', '') == 'acorazado'
        inflige_ruptura = es_iniciador and tiene_ventaja and daño > 0 and not es_antirruptura and not es_acorazado

        # Detección de pasivas adicionales
        tiene_canter = any('canter' in h or 'galopada' in h or '再移動' in h for h in habs_atk) or 'sigurd' in emblema_atk or 'シグルド' in emblema_atk
        tiene_alacrity = any('alacrity' in h or 'alacritad' in h or '攻め立て' in h for h in habs_atk) or 'lyn' in emblema_atk or 'リン' in emblema_atk
        # Velocidad Divina (Divine Speed) es la Habilidad de Fusión de Marth: solo activa en modo Engage
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
            "precision": precision,
            "prob_critico": prob_critico,
            "tiene_ventaja": tiene_ventaja,
            "inflige_ruptura": inflige_ruptura,
            "antirruptura_bloqueo_break": es_iniciador and tiene_ventaja and daño > 0 and (es_antirruptura or es_acorazado),
            "efectividad_activa": desc_efectividad,
            "multiplicador_efectividad": mult_mt_efectividad,
            "recoil_hp": recoil_hp,
            "tiene_canter": tiene_canter,
            "tiene_alacrity": tiene_alacrity,
            "tiene_divine_speed": tiene_divine_speed,
            "tiene_hold_out": tiene_hold_out,
        }

    # ── Simulación completa ─────────────────────────────────────────────

    @classmethod
    def simular_combate(cls, atacante, defensor, arma_atk, arma_def=None,
                        terreno_atk=None, terreno_def=None, distancia=1,
                        aliados_apoyo_backup=None,
                        pos_atk=None, pos_def=None, mapa=None, casillas_ocupadas=None,
                        defensor_en_ruptura: bool = False):
        """
        Simula el intercambio completo siguiendo la secuencia determinista de FE Engage:
          1. Chain Attacks de aliados de apoyo (Backup) cercanos (10% HP max c/u)
          2. Gestión de Armas Pesadas (Smash):
             - Si el atacante usa arma Smash y el defensor no, el defensor contraataca PRIMERO.
             - Las armas Smash NUNCA pueden realizar follow-up.
             - Si acierta un ataque Smash, empuja al rival 1 casilla. Si choca contra obstáculo o unidad,
               ¡provoca RUPTURA (Break) incluso a acorazados!
             - Un contraataque NUNCA inflige ruptura: el atacante ejecutará su golpe Smash siempre que sobreviva.
          3. Atacante golpea (y golpe extra de Divine Speed si activa) → Ruptura (si ventaja de armas)
          4. Si Alacrity activa y hay follow-up, el atacante hace follow-up ANTES del contraataque
          5. Defensor contraataca (si vivo, en rango y no roto)
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

        stats_atk = cls._stats_de_golpe(atacante, arma_atk, defensor, arma_def, terreno_def, es_iniciador=True)

        puede_contra = (not defensor_en_ruptura) and (arma_def is not None) and (distancia in arma_def.rango)
        stats_def = None
        if puede_contra:
            stats_def = cls._stats_de_golpe(defensor, arma_def, atacante, arma_atk, terreno_atk, es_iniciador=False)

        es_smash_atk = getattr(arma_atk, 'es_smash', False)
        es_smash_def = getattr(arma_def, 'es_smash', False) if arma_def else False

        diff_as_atk = stats_atk["as_atk"] - stats_atk["as_def"]
        follow_up_atk = (diff_as_atk >= 5) and (not es_smash_atk)
        follow_up_def = puede_contra and ((stats_atk["as_def"] - stats_atk["as_atk"]) >= 5) and (not es_smash_def)

        # Alacrity (Lyn): si AS >= rival + 9 (o +4), follow-up va antes del contraataque
        activa_alacrity = stats_atk.get("tiene_alacrity", False) and diff_as_atk >= 9 and follow_up_atk

        hp_atk = atacante.hp
        hp_def = defensor.hp
        hp_def_max = getattr(defensor, 'hp_max', defensor.hp) or defensor.hp
        defensor_roto = defensor_en_ruptura
        atacante_roto = False
        secuencia = []
        chain_dmg_total = 0

        def registrar(actor, tipo, daño, hp_obj):
            secuencia.append({
                "actor": actor, "tipo": tipo,
                "daño": daño, "hp_objetivo_tras": max(0, hp_obj),
            })

        # 1. Chain Attacks de aliados de apoyo (Backup)
        if aliados_apoyo_backup:
            for apoyo in aliados_apoyo_backup:
                if hp_def <= 0:
                    break
                dmg_chain = max(1, math.floor(hp_def_max * 0.10))
                hp_def -= dmg_chain
                chain_dmg_total += dmg_chain
                registrar(apoyo.nombre, "chain_attack", dmg_chain, hp_def)

        # 2. Secuencia según propiedad Smash:
        # En FE Engage, las armas Smash atacan de segundo ("strike second") si el rival puede contraatacar
        # y no usa también un arma Smash.
        if es_smash_atk and puede_contra and not es_smash_def:
            # ── Defensor contraataca PRIMERO (prioridad por arma Smash del rival) ──
            if hp_def > 0 and stats_def:
                hp_atk -= stats_def["daño"]
                # En FE Engage, un contraataque NUNCA inflige Ruptura al atacante
                registrar(defensor.nombre, "contraataque (prioridad sobre Smash)", stats_def["daño"], hp_atk)

            # ── Atacante ejecuta su golpe Smash (si sobrevive al contraataque) ──
            if hp_atk > 0 and hp_def > 0:
                hp_def -= stats_atk["daño"]
                if stats_atk["inflige_ruptura"]:
                    defensor_roto = True
                registrar(atacante.nombre, "ataque (smash)", stats_atk["daño"], hp_def)

                if stats_atk.get("tiene_divine_speed") and hp_def > 0:
                    dmg_divine = max(1, math.floor(stats_atk["daño"] * 0.50))
                    hp_def -= dmg_divine
                    registrar(atacante.nombre, "divine_speed", dmg_divine, hp_def)

            # ── Follow-up del defensor si doblaba, atacante sigue vivo y defensor no quedó roto ──
            if follow_up_def and hp_def > 0 and hp_atk > 0 and not defensor_roto and stats_def:
                hp_atk -= stats_def["daño"]
                registrar(defensor.nombre, "follow-up", stats_def["daño"], hp_atk)

        else:
            # ── Secuencia estándar (sin Smash del atacante, o ambos con Smash) ──
            # 2a. Ataque principal del atacante
            if hp_def > 0:
                tipo_atk_str = "ataque (smash)" if es_smash_atk else "ataque"
                hp_def -= stats_atk["daño"]
                if stats_atk["inflige_ruptura"]:
                    defensor_roto = True
                registrar(atacante.nombre, tipo_atk_str, stats_atk["daño"], hp_def)

                # Golpe extra de Divine Speed (Marth)
                if stats_atk.get("tiene_divine_speed") and hp_def > 0:
                    dmg_divine = max(1, math.floor(stats_atk["daño"] * 0.50))
                    hp_def -= dmg_divine
                    registrar(atacante.nombre, "divine_speed", dmg_divine, hp_def)

            # 2b. Follow-up anticipado por Alacrity
            if activa_alacrity and hp_atk > 0 and hp_def > 0:
                hp_def -= stats_atk["daño"]
                registrar(atacante.nombre, "follow-up (alacrity)", stats_atk["daño"], hp_def)

            # 2c. Contraataque del defensor (si vivo, en rango y no roto)
            if puede_contra and hp_def > 0 and not defensor_roto and stats_def:
                tipo_contra_str = "contraataque (smash)" if es_smash_def else "contraataque"
                hp_atk -= stats_def["daño"]
                # Un contraataque NUNCA inflige Ruptura
                registrar(defensor.nombre, tipo_contra_str, stats_def["daño"], hp_atk)

            # 2d. Follow-up regular del atacante (si no se ejecutó por Alacrity)
            if not activa_alacrity and follow_up_atk and hp_atk > 0 and hp_def > 0:
                hp_def -= stats_atk["daño"]
                registrar(atacante.nombre, "follow-up", stats_atk["daño"], hp_def)

            # 2e. Follow-up del defensor
            if follow_up_def and hp_def > 0 and hp_atk > 0 and not defensor_roto and stats_def:
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
                        es_vol = getattr(defensor, 'tipo_movimiento', '') == 'volador'
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

        return {
            "atacante": {
                "nombre": atacante.nombre,
                "hp_inicial": atacante.hp,
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
            },
            "defensor": {
                "nombre": defensor.nombre,
                "hp_inicial": defensor.hp,
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
            },
            "resultado": {
                "hp_atacante_final": hp_atk_final,
                "hp_defensor_final": hp_def_final,
                "atacante_mata": hp_def_final <= 0,
                "defensor_mata": hp_atk_final <= 0,
                "aplica_ruptura": bool(stats_atk.get("inflige_ruptura", False) or smash_info.get("rompio_por_choque", False)),
                "defensor_roto": defensor_roto,
                "sufre_ruptura": False,
                "antirruptura_bloqueo_break": stats_atk.get("antirruptura_bloqueo_break", False) and not smash_info["rompio_por_choque"],
                "chain_attacks_daño": chain_dmg_total,
                "puede_canter": stats_atk.get("tiene_canter", False),
                "recoil_hp": recoil,
                "secuencia": secuencia,
                "smash": smash_info,
            },
            "alertas_tacticas": {
                "peligro_letal": hp_atk_final <= 0,
                "kill_seguro": hp_def_final <= 0 and stats_atk["precision"] == 100,
                "kill_probable": hp_def_final <= 0 and stats_atk["precision"] < 100,
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
        if not isinstance(unidad, Unidad):
            raise TypeError(
                f"El {rol} debe ser una instancia de Unidad. "
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
                       contexto_mapa=None, defensor_en_ruptura: bool = False):
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
        """
        if perfil not in ("seguro", "agresivo"):
            raise ValueError(
                f"Perfil '{perfil}' no valido. Usa 'seguro' o 'agresivo'."
            )

        # Ejecutar simulación de combate completa
        combate = cls.simular_combate(
            atacante, defensor, arma_atk, arma_def,
            terreno_atk, terreno_def, distancia,
            defensor_en_ruptura=defensor_en_ruptura,
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
        if turnos_fusion <= 0:
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
                        f"¡FUSIÓN DE EMBLEMA LISTA! {atk['nombre']} obtiene +{ganancia} cargas "
                        f"({nueva_energia}/{max_energia}). Podrá fusionarse con su Emblema el próximo turno."
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