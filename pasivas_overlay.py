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
    # ── Tiki: Geosphere / Geosphere+ ──────────────────────────────────────────
    # Modelado como en la versión anterior del motor (aliados adyacentes reciben
    # 3 de daño menos, físico o mágico): aura de Def/Res +3 a distancia 1.
    # NO verificado en juego todavía; Geosphere+ se asume +5.
    "SID_OVERLAY_GEOSPHERE": _entrada(
        "SID_OVERLAY_GEOSPHERE", "Geosphere",
        timing=20, target=2, rango_efecto=[1, 1], give_sids=["SID_OVERLAY_GEOSPHERE_EFECTO"], priority=1,
    ),
    "SID_OVERLAY_GEOSPHERE_EFECTO": _entrada(
        "SID_OVERLAY_GEOSPHERE_EFECTO", "Geosphere",
        act_names=["守備", "魔防"], act_operations=["+", "+"], act_values=["3", "3"], timing=3, oculta=True,
    ),
    "SID_OVERLAY_GEOSPHERE_PLUS": _entrada(
        "SID_OVERLAY_GEOSPHERE_PLUS", "Geosphere+",
        timing=20, target=2, rango_efecto=[1, 1], give_sids=["SID_OVERLAY_GEOSPHERE_PLUS_EFECTO"], priority=4,
    ),
    "SID_OVERLAY_GEOSPHERE_PLUS_EFECTO": _entrada(
        "SID_OVERLAY_GEOSPHERE_PLUS_EFECTO", "Geosphere+",
        act_names=["守備", "魔防"], act_operations=["+", "+"], act_values=["5", "5"], timing=3, oculta=True,
    ),
}

for _sid, _info in OVERLAY.items():
    condicion_dsl.HABILIDADES_CATALOGO.setdefault(_sid, _info)
