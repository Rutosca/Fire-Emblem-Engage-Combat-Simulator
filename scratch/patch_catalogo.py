import re

path = r"c:\Rubén\Proyectos\Engage_tracker\catalogo_loader.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Part 1: Fix lines 606-612
target_bad = '''    # Si el usuario mandó stats explícitos, sobreescribir
    if "stats" in data and isinstance(data["stats"], dict):
        or any(w in c_nombre_c for w in ["flier", "pegas", "wyvern", "griffin", "grifo", "wing tamer", "sleipnir", "lindwurm", "melusine"])
        or any(w in c_jid_c for w in ["ペガサス", "ドラゴンナイト", "グリフォン", "スレイプニル", "リンドブルム", "メリュジーヌ", "flier", "wyvern", "pegas"])
        or bool(data.get("es_volador", False))
    )'''

replacement_good = '''    # Si el usuario mandó stats explícitos, sobreescribir
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

    nivel_vinculo = max(1, int(data.get("nivel_vinculo", getattr(unidad_previa, 'nivel_vinculo', 1) if unidad_previa else 1)))
    duracion_base = 4 if nivel_vinculo >= 11 else 3

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
    estilo_str_c = str(style).lower()

    es_volador = (
        estilo_str_c in ("flier", "volador", "飛行スタイル", "飛行", "flying")
        or tipo_mov_c in ("volador", "flier", "flying")
        or any(w in c_nombre_c for w in ["flier", "pegas", "wyvern", "griffin", "grifo", "wing tamer", "sleipnir", "lindwurm", "melusine"])
        or any(w in c_jid_c for w in ["ペガサス", "ドラゴンナイト", "グリフォン", "スレイプニル", "リンドブルム", "メリュジーヌ", "flier", "wyvern", "pegas"])
        or bool(data.get("es_volador", False))
    )'''

if target_bad in content:
    content = content.replace(target_bad, replacement_good)
    print("Part 1 replaced successfully!")
else:
    print("Warning: target_bad not found!")

# Part 2: Unidad stats_obj
content = content.replace(
    '''        turnos_fusion_restantes=3 if en_fusion else int(data.get("turnos_fusion", 0)),
        es_dragon=(style == "Dragon" or "alear" in nombre.lower()),''',
    '''        turnos_fusion_restantes=turnos_fusion if en_fusion else 0,
        es_dragon=(style == "Dragon" or "alear" in nombre.lower()),
        en_fusion=en_fusion,
        ataque_emblema_usado=ataque_emblema_usado,
        nivel_vinculo=nivel_vinculo,'''
)

# Part 3: stats_obj.turnos_fusion_restantes in engage items injection
content = content.replace(
    '''    if en_fusion and emblema_info:
        stats_obj.turnos_fusion_restantes = 3''',
    '''    if en_fusion and emblema_info:
        stats_obj.turnos_fusion_restantes = turnos_fusion'''
)

# Part 4: FichaUnidad instantiation
content = content.replace(
    '''        turnos_fusion=3 if en_fusion else int(data.get("turnos_fusion", 0)),
        en_fusion=en_fusion,''',
    '''        turnos_fusion=turnos_fusion,
        en_fusion=en_fusion,
        ataque_emblema_usado=ataque_emblema_usado,
        nivel_vinculo=nivel_vinculo,'''
)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Saved catalogo_loader.py successfully!")
