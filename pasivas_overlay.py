"""
pasivas_overlay.py — Overlay escrito a mano sobre el catálogo de habilidades.

Aquí viven SOLO las habilidades que no están en el datamine (Emblemas DLC:
`json/dlc_emblems_canon.json` las nombra en inglés, sin SID) y las correcciones
verificadas en juego. Cada entrada usa el mismo esquema que `catalogo_engage.json`
(nombre / condition / act_* / timing / stand / give_sids…) y se registra en
`condicion_dsl.HABILIDADES_CATALOGO` con un pseudo-SID `SID_OVERLAY_*`, de modo que
`pasivas.recopilar` las trata exactamente igual que a las del datamine. La única
extensión es que `condition` puede ser una función Python `f(ctx) -> bool` cuando
la DSL no puede expresarla (p.ej. el líder activo de las Tres Casas).

Mantener esta lista corta: todo lo que tenga fila en Skill.xml va por el catálogo.
"""

import condicion_dsl

_CAMPOS_VACIOS = {
    "oculta": False, "icono": "", "stat_boosts": {}, "combat_mods": {}, "flag": 0, "priority": 0,
    "condition": "", "act_names": [], "act_operations": [], "act_values": [],
    "give_target": 0, "give_condition": "", "give_sids": [], "sync_sids": [], "sync_conditions": [],
    "timing": 3, "target": 0, "stand": 0, "action": 0, "life": 0, "cycle": 0, "variantes_estilo": {},
    "rango_efecto": [0, 0], "overlay": True,
}


def _entrada(sid: str, nombre: str, **campos) -> dict:
    info = dict(_CAMPOS_VACIOS, id=sid, nombre=nombre)
    info.update(campos)
    return info


def _en_fusion(u) -> bool:
    return bool(getattr(u, "en_fusion", False) or int(getattr(u, "turnos_fusion_restantes", 0) or 0) > 0)


def _elemento_del_arma(arma) -> str:
    """Elemento del tomo equipado ('fuego' / 'trueno' / 'viento'…); "" si no es tomo."""
    if arma is None:
        return ""
    elem = getattr(arma, "elemento", "") or ""
    if elem:
        return str(elem)
    from catalogo_loader import _catalogo, normalizar_texto
    armas = _catalogo.get("armas", {}) or {}
    info = armas.get(getattr(arma, "id", "") or "")
    if info is None:
        nom = normalizar_texto(getattr(arma, "nombre", ""))
        info = next((v for v in armas.values()
                     if v.get("elemento") and normalizar_texto(v.get("nombre", "")) == nom), None)
    return str((info or {}).get("elemento") or "")


def _con_tomo(ctx) -> bool:
    return str(getattr(ctx.arma, "tipo", "") or "").lower() in ("tomo", "tome")


def _flare(ctx) -> bool:
    """Flare solo actúa atacando con tomo (y solo existe en Fusión, que es quien la da)."""
    return _con_tomo(ctx)


def _usando_infierno_oscuro(ctx) -> bool:
    """True si el golpe en curso es el Ataque de Emblema Infierno Oscuro de Camilla."""
    arma = getattr(ctx, "arma", None)
    if arma is None or not getattr(arma, "es_engage_attack", False):
        return False
    nombre = str(getattr(arma, "engage_attack_nombre", "") or getattr(arma, "nombre", "")).lower()
    return "dark inferno" in nombre or "infierno oscuro" in nombre


def _infierno_oscuro_mistico(ctx) -> bool:
    if not _usando_infierno_oscuro(ctx):
        return False
    from motor_calculo import resolver_estilo_combate
    stats = getattr(ctx.unidad, "stats", None) or ctx.unidad
    return resolver_estilo_combate(getattr(stats, "estilo_combate", "")) == "mistico"


# ── Edelgard / Dimitri / Claude (Tres Casas): Weapon Sync / Weapon Sync+ ──────
# Verificado en juego (Cap. 9, Chloé, vínculo 20 → +7 en Houses Unite y ataques normales).
# +5 Atk (+7 con "+") al iniciar combate si el arma equipada es la del líder activo
# (Edelgard hacha, Dimitri lanza, Claude arco); en Fusión valen las tres. Heredada
# sin el Emblema de las Tres Casas equipado no hay líder que la limite: aplica siempre.
_ARMA_DEL_LIDER = {"edelgard": ("hacha", "axe"), "dimitri": ("lanza", "lance"), "claude": ("arco", "bow")}


def _weapon_sync_aplica(ctx) -> bool:
    u = ctx.unidad
    if _en_fusion(u):
        return True
    emblema = str(getattr(u, "emblema_nombre", "") or getattr(u, "emblema", "") or "").lower()
    es_tres_casas = any(t in emblema for t in ("edelgard", "dimitri", "claude", "three houses", "tres casas", "brazalete"))
    if not es_tres_casas:
        return True
    lider = str(getattr(u, "lider_tres_casas", "") or "Dimitri").lower()
    tipo = str(getattr(ctx.arma, "tipo", "") or "").lower()
    for nombre_lider, tipos in _ARMA_DEL_LIDER.items():
        if nombre_lider in lider:
            return any(t in tipo for t in tipos)
    return any(t in tipo for tipos in _ARMA_DEL_LIDER.values() for t in tipos)


OVERLAY = {
    "SID_OVERLAY_WEAPON_SYNC": _entrada(
        "SID_OVERLAY_WEAPON_SYNC", "Weapon Sync",
        condition=_weapon_sync_aplica, act_names=["攻撃力"], act_operations=["+"], act_values=["5"],
        timing=3, stand=1, priority=1,
    ),
    "SID_OVERLAY_WEAPON_SYNC_PLUS": _entrada(
        "SID_OVERLAY_WEAPON_SYNC_PLUS", "Weapon Sync+",
        condition=_weapon_sync_aplica, act_names=["攻撃力"], act_operations=["+"], act_values=["7"],
        timing=3, stand=1, priority=4,
    ),
    # ══ Emblema Tiki (DLC) ═══════════════════════════════════════════════════
    # Fuente: https://serenesforest.net/engage/emblems/tiki/ — los niveles de vínculo a
    # los que se desbloquea cada una están en json/dlc_emblems_canon.json, que es lo que
    # decide cuáles están activas según el vínculo que elija el jugador.

    # Nv 1 · "Grants unit enhanced stat growth when leveling up (+15% a los crecimientos)".
    # Fuera de combate: se registra para que aparezca en la ficha, no modifica el combate.
    "SID_OVERLAY_STARSPHERE": _entrada(
        "SID_OVERLAY_STARSPHERE", "Starsphere", timing=1,
    ),

    # Nv 3 / 16 · "At start of player phase, if there are allies adjacent to unit, grants
    # Def/Res+3 (+5) to unit and those allies for 1 turn". El portador también lo recibe:
    # por eso el Flag con el bit 23 (FLAG_AURA_TAMBIEN_PROPIO).
    "SID_OVERLAY_GEOSPHERE": _entrada(
        "SID_OVERLAY_GEOSPHERE", "Geosphere",
        timing=20, target=2, rango_efecto=[1, 1], flag=1 << 23,
        give_sids=["SID_OVERLAY_GEOSPHERE_EFECTO"], priority=1,
    ),
    "SID_OVERLAY_GEOSPHERE_EFECTO": _entrada(
        "SID_OVERLAY_GEOSPHERE_EFECTO", "Geosphere",
        act_names=["守備", "魔防"], act_operations=["+", "+"], act_values=["3", "3"], timing=3, oculta=True,
    ),
    "SID_OVERLAY_GEOSPHERE_PLUS": _entrada(
        "SID_OVERLAY_GEOSPHERE_PLUS", "Geosphere+",
        timing=20, target=2, rango_efecto=[1, 1], flag=1 << 23,
        give_sids=["SID_OVERLAY_GEOSPHERE_PLUS_EFECTO"], priority=4,
    ),
    "SID_OVERLAY_GEOSPHERE_PLUS_EFECTO": _entrada(
        "SID_OVERLAY_GEOSPHERE_PLUS_EFECTO", "Geosphere+",
        act_names=["守備", "魔防"], act_operations=["+", "+"], act_values=["5", "5"], timing=3, oculta=True,
    ),

    # Nv 8 / 14 / 19 · "If unit uses Wait without attacking or using items, restores
    # 20/30/40 HP and heals status effects". Timing 25 = al esperar, como Self-Improver y
    # Meditation; el acto 回復 (curación) lo aplica pasivas_temporales.al_esperar.
    "SID_OVERLAY_LIFESPHERE": _entrada(
        "SID_OVERLAY_LIFESPHERE", "Lifesphere",
        timing=25, act_names=["回復"], act_operations=["+"], act_values=["20"], priority=1,
    ),
    "SID_OVERLAY_LIFESPHERE_PLUS": _entrada(
        "SID_OVERLAY_LIFESPHERE_PLUS", "Lifesphere+",
        timing=25, act_names=["回復"], act_operations=["+"], act_values=["30"], priority=2,
    ),
    "SID_OVERLAY_LIFESPHERE_PLUSPLUS": _entrada(
        "SID_OVERLAY_LIFESPHERE_PLUSPLUS", "Lifesphere++",
        timing=25, act_names=["回復"], act_operations=["+"], act_values=["40"], priority=3,
    ),

    # Nv 10 · "If unit initiates combat, halves chance of receiving critical hit from foe".
    # Stand 1 = solo al iniciar; reduce a la mitad la tasa de crítico DEL RIVAL.
    "SID_OVERLAY_LIGHTSPHERE": _entrada(
        "SID_OVERLAY_LIGHTSPHERE", "Lightsphere",
        act_names=["相手の必殺率"], act_operations=["*"], act_values=["0.5"], timing=3, stand=1,
    ),

    # Habilidad de Fusión (Nv 1) · "Unit transforms into and fights as a dragon while
    # engaged. Grants +10 to max HP and +5 to Bld and all basic stats."
    # Solo se aplica en Fusión porque vive en `habilidades_sids_fusion` (catalogo_loader).
    # Mientras dura la Fusión la unidad ES un dragón: solo pelea con ataques especiales
    # (los alientos y zarpazos del Emblema) y NO puede usar sus propias armas.
    # `solo_armas_emblema` lo lee motor_analisis._armas_aliado.
    "SID_OVERLAY_DRACONIC_FORM": _entrada(
        "SID_OVERLAY_DRACONIC_FORM", "Draconic Form",
        act_names=["HP", "力", "魔力", "技", "速さ", "守備", "魔防", "幸運", "体格"],
        act_operations=["+"] * 9,
        act_values=["10", "5", "5", "5", "5", "5", "5", "5", "5"],
        timing=1, sync_sids=["SID_OVERLAY_DRACONIC_FORM_MAGICO"],
        solo_armas_emblema=True,
    ),
    # "[Mystical] Grants an extra Res+5"  ([Armored] anula el daño de terreno: no es de combate)
    "SID_OVERLAY_DRACONIC_FORM_MAGICO": _entrada(
        "SID_OVERLAY_DRACONIC_FORM_MAGICO", "Draconic Form",
        condition="戦闘スタイル == 魔法スタイル",
        act_names=["魔防"], act_operations=["+"], act_values=["5"], timing=1, oculta=True,
    ),

    # ── Efectos de las armas de Fusión de Tiki (equip_sids) ──────────────────
    # "Strikes foes at half Def / half Res": la mitad de la defensa que aplica al golpe.
    "SID_OVERLAY_MEDIA_DEFENSA": _entrada(
        "SID_OVERLAY_MEDIA_DEFENSA", "Media defensa",
        act_names=["相手の防御力"], act_operations=["="], act_values=["相手の防御力 * 0.5"],
        timing=7,
    ),
    # Fire Breath: "Ignores foe's Def/Res".
    "SID_OVERLAY_IGNORA_DEFENSA": _entrada(
        "SID_OVERLAY_IGNORA_DEFENSA", "Ignora la defensa",
        act_names=["相手の防御力"], act_operations=["="], act_values=["0"], timing=7,
    ),
    # Flame Breath: "Strikes foes at 70% damage".
    "SID_OVERLAY_DANO_70": _entrada(
        "SID_OVERLAY_DANO_70", "Daño 70%",
        act_names=["威力"], act_operations=["*"], act_values=["0.7"], timing=7,
    ),

    # ═══ Soren (DLC) ═════════════════════════════════════════════════════════
    # Nv 1 · "Use to make one chosen ally more likely to be targeted by enemies for 1
    # turn". Es un COMANDO que cambia a quién ataca la IA; la herramienta no simula la
    # decisión del enemigo (la toma el jugador), así que solo se declara.
    "SID_OVERLAY_ASSIGN_DECOY": _entrada(
        "SID_OVERLAY_ASSIGN_DECOY", "Assign Decoy", timing=21,
    ),

    # Nv 4 · "When using tomes, unit inflicts Def-3 with fire, Hit-20 with thunder, or
    # Mov-2 with wind magic for 1 turn". El efecto NO es del golpe: es un lastre que se
    # queda pegado al objetivo durante el turno siguiente, así que lo aprovechan también
    # los demás aliados. Lo otorga pasivas_temporales tras el combate.
    "SID_OVERLAY_ANIMA_FOCUS": _entrada(
        "SID_OVERLAY_ANIMA_FOCUS", "Anima Focus", timing=1,
    ),
    "SID_OVERLAY_ANIMA_FOCUS_FUEGO": _entrada(
        "SID_OVERLAY_ANIMA_FOCUS_FUEGO", "Anima Focus (fuego): Def -3",
        act_names=["守備"], act_operations=["-"], act_values=["3"], timing=3,
    ),
    "SID_OVERLAY_ANIMA_FOCUS_TRUENO": _entrada(
        "SID_OVERLAY_ANIMA_FOCUS_TRUENO", "Anima Focus (trueno): Precisión -20",
        act_names=["命中値"], act_operations=["-"], act_values=["20"], timing=3,
    ),
    # El de viento no es de combate: le quita movimiento, y eso vive en la ficha.
    "SID_OVERLAY_ANIMA_FOCUS_VIENTO": _entrada(
        "SID_OVERLAY_ANIMA_FOCUS_VIENTO", "Anima Focus (viento): Mov -2",
        stat_boosts={"mov": -2}, timing=1,
    ),

    # Nv 9 / 18 · "When unit deals Effective damage, deal +5 (+7) damage".
    "SID_OVERLAY_KEEN_INSIGHT": _entrada(
        "SID_OVERLAY_KEEN_INSIGHT", "Keen Insight",
        condition="武器特効 > 1",
        act_names=["威力"], act_operations=["+"], act_values=["5"], timing=7,
    ),
    "SID_OVERLAY_KEEN_INSIGHT_PLUS": _entrada(
        "SID_OVERLAY_KEEN_INSIGHT_PLUS", "Keen Insight+",
        condition="武器特効 > 1",
        act_names=["威力"], act_operations=["+"], act_values=["7"], timing=7,
    ),

    # Efecto que reparte el báculo Reflect a los aliados a 2 casillas: "deals 50% of magic
    # damage taken back to foe" durante 1 turno. El motor no devuelve ese daño todavía
    # (es un efecto POSTERIOR al golpe recibido, de la Fase 3): se deja marcado en la
    # ficha para que el análisis lo avise y el jugador anote el daño.
    "SID_OVERLAY_REFLECT": _entrada(
        "SID_OVERLAY_REFLECT", "Reflect (devuelve el 50 % del daño mágico)", timing=1,
    ),

    # Habilidad de Fusión · "When attacking with tomes, inflicts Res-20% on foe, and unit
    # recovers 50% of damage dealt". El -20 % va sobre la Res que aplica a ESE golpe, así
    # que vale para los dos golpes si la unidad dobla (verificado: Céline pasa de 28 a 30).
    "SID_OVERLAY_FLARE": _entrada(
        "SID_OVERLAY_FLARE", "Flare",
        condition=_flare,
        act_names=["相手の防御力", "回復"], act_operations=["=", "*"],
        act_values=["相手の魔防 * 0.8", "0.5"],
        timing=7, variantes_estilo={"mistico": "SID_OVERLAY_FLARE_魔法",
                                    "qi_adept": "SID_OVERLAY_FLARE_気功"},
    ),
    # "[Mystical] Extra -10% to foe's Res": -30 % en total. Verificado con Céline contra un
    # Lance Flier de Res 14 -> la Res que aplica queda en 9 (floor(14 * 0.7)).
    "SID_OVERLAY_FLARE_魔法": _entrada(
        "SID_OVERLAY_FLARE_魔法", "Flare",
        condition=_flare,
        act_names=["相手の防御力", "回復"], act_operations=["=", "*"],
        act_values=["相手の魔防 * 0.7", "0.5"],
        timing=7,
    ),
    # "[Qi Adept] Unit recovers 100% of damage dealt instead."
    "SID_OVERLAY_FLARE_気功": _entrada(
        "SID_OVERLAY_FLARE_気功", "Flare",
        condition=_flare,
        act_names=["相手の防御力", "回復"], act_operations=["=", "*"],
        act_values=["相手の魔防 * 0.8", "1.0"],
        timing=7,
    ),

    # ═══ Camilla (DLC) ═══════════════════════════════════════════════════════
    # Sincronías. Dragon Vein, Decisive Strike y Groundswell no son modificadores de
    # combate: son un comando y dos efectos posteriores al golpe. Se registran igual para
    # que aparezcan en la lista de pasivas de la unidad y para que el motor las conozca.

    # Dragon Vein NO va aquí: está en el datamine (SID_竜脈, con variante por estilo de
    # combate para las ocho venas). El catálogo de venas vive en `ataques_area.VENAS_DRAGON`.

    # Nv 4 / 18 · "If unit initiates combat and lands a critical, deals 5 (10) damage to
    # foe after combat". El motor es determinista y no tira el crítico: publica su
    # probabilidad. El daño posterior al combate es un evento por golpe (Fase 3), así que
    # de momento la habilidad solo se declara.
    "SID_OVERLAY_DECISIVE_STRIKE": _entrada(
        "SID_OVERLAY_DECISIVE_STRIKE", "Decisive Strike", stand=1, timing=1,
    ),
    "SID_OVERLAY_DECISIVE_STRIKE_PLUS": _entrada(
        "SID_OVERLAY_DECISIVE_STRIKE_PLUS", "Decisive Strike+", stand=1, timing=1,
    ),

    # Nv 8 · "Cures poison at start of turn". Lo aplica EstadoTablero al entrar en la fase
    # de la unidad, no el cálculo de combate.
    "SID_OVERLAY_DETOXIFY": _entrada(
        "SID_OVERLAY_DETOXIFY", "Detoxify", timing=1,
    ),

    # Nv 12 · "After unit acts or waits in flames, miasma, or similar terrain effect, unit
    # clears effect and recovers 10 HP". También lo aplica EstadoTablero: limpia el
    # terreno temporal de su casilla y cura 10. Se lleva cualquiera, no solo los dañinos
    # (verificado en juego con la luz curativa de Succor).
    "SID_OVERLAY_GROUNDSWELL": _entrada(
        "SID_OVERLAY_GROUNDSWELL", "Groundswell", timing=1,
    ),

    # Habilidad de Fusión · "Grants Mov+2. Unit can cross terrain as if flying.
    # [Cavalry] Grants an extra Mov+2. [Flying] Grants an extra Mov+1."
    # El Mov sale de stat_boosts, igual que Gallop de Sigurd (pasivas.bono_movimiento_fusion).
    "SID_OVERLAY_SOAR": _entrada(
        "SID_OVERLAY_SOAR", "Soar", timing=1, stat_boosts={"mov": 2}, cruza_como_volador=True,
        sync_sids=["SID_OVERLAY_INFIERNO_OSCURO_MISTICO"],
    ),
    "SID_OVERLAY_SOAR_騎馬": _entrada(
        "SID_OVERLAY_SOAR_騎馬", "Soar", timing=1, stat_boosts={"mov": 4}, cruza_como_volador=True,
        sync_sids=["SID_OVERLAY_INFIERNO_OSCURO_MISTICO"],
    ),
    "SID_OVERLAY_SOAR_飛行": _entrada(
        "SID_OVERLAY_SOAR_飛行", "Soar", timing=1, stat_boosts={"mov": 3}, cruza_como_volador=True,
        sync_sids=["SID_OVERLAY_INFIERNO_OSCURO_MISTICO"],
    ),
    # "[Dragon] If unit initiates combat, deals damage to foes within 2 spaces equal to
    # 10% of their max HP after combat" — daño posterior al combate: Fase 3.
    "SID_OVERLAY_SOAR_竜族": _entrada(
        "SID_OVERLAY_SOAR_竜族", "Soar", timing=1, stat_boosts={"mov": 2}, cruza_como_volador=True,
        sync_sids=["SID_OVERLAY_INFIERNO_OSCURO_MISTICO"],
    ),

    # "[Mystical] +20% damage" de Infierno Oscuro: multiplica el DAÑO ya calculado por
    # 1.2 y trunca, igual que el bono Místico de Warp Ragnarök. Ground truth: Céline con
    # el Bolt Axe hace 28 de daño a un Lance Armor y con Infierno Oscuro hace 33.
    "SID_OVERLAY_INFIERNO_OSCURO_MISTICO": _entrada(
        "SID_OVERLAY_INFIERNO_OSCURO_MISTICO", "Infierno Oscuro (Místico)",
        condition=_infierno_oscuro_mistico,
        act_names=["威力"], act_operations=["*"], act_values=["1.2"], timing=7, oculta=True,
    ),

    # ── Efectos de las armas de Camilla (equip_sids) ─────────────────────────
    # Camilla's Axe: "Grants Res+10 and deals extra damage = foe's Res-Def".
    "SID_OVERLAY_CAMILLA_RES_10": _entrada(
        "SID_OVERLAY_CAMILLA_RES_10", "Camilla's Axe: Res+10",
        act_names=["魔防"], act_operations=["+"], act_values=["10"], timing=1,
    ),
    # El extra es la diferencia Res-Def del rival; si su Def es mayor, no resta nada.
    "SID_OVERLAY_DANO_RES_MENOS_DEF": _entrada(
        "SID_OVERLAY_DANO_RES_MENOS_DEF", "Camilla's Axe: daño extra = Res-Def del rival",
        act_names=["威力"], act_operations=["+"],
        act_values=["max( 相手の魔防 - 相手の守備 , 0 )"], timing=7,
    ),

    # Heredables por SP · "If foe is equipped with a special attack, unit takes N less
    # damage during combat" (Nv 4/9/13/17/19, 1..5 de reducción).
    # Un "ataque especial" es un arma de tipo Especial (Item.xml Kind 9): los alientos y
    # zarpazos de los Corrupted Wyrm y Phantom Dragon (JID_異形竜 / JID_幻影竜, las tropas
    # 2×2), los ataques de Sombron, el Dragon Fang de Corrin... y los de Draconic Form.
    **{
        f"SID_OVERLAY_SPECIAL_GUARD_{n}": _entrada(
            f"SID_OVERLAY_SPECIAL_GUARD_{n}", f"Special Guard {n}",
            condition="相手の武器の種類 == 特殊",
            act_names=["相手の威力"], act_operations=["-"], act_values=[str(n)],
            # En el juego es una reducción de daño (Timing 12), que es Fase 3. Como es una
            # resta fija se expresa en el Timing 7 (daño), que el motor ya aplica, y da el
            # mismo número; cuando llegue la Fase 3 puede volver a su timing real.
            timing=7, priority=n,
        )
        for n in range(1, 6)
    },
}

for _sid, _info in OVERLAY.items():
    condicion_dsl.HABILIDADES_CATALOGO.setdefault(_sid, _info)
