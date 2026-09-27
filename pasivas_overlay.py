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












    # ═══ Camilla (DLC) ═══════════════════════════════════════════════════════
    # Sincronías. Dragon Vein, Decisive Strike y Groundswell no son modificadores de
    # combate: son un comando y dos efectos posteriores al golpe. Se registran igual para
    # que aparezcan en la lista de pasivas de la unidad y para que el motor las conozca.

    # Dragon Vein NO va aquí: está en el datamine (SID_竜脈, con variante por estilo de
    # combate para las ocho venas). El catálogo de venas vive en `ataques_area.VENAS_DRAGON`.







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
