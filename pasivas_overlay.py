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
