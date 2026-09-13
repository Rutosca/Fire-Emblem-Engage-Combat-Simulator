import xml.etree.ElementTree as ET
import json
import os

god_tree = ET.parse(r"FE17-DOC-main\FE17-DOC-main\fe_assets_gamedata\God.xml")
sheets = god_tree.getroot().findall("Sheet")
god_sheet = sheets[0].find("Data").findall("Param")
level_sheet = sheets[1].find("Data").findall("Param")

with open("traducciones_cache.json", "r", encoding="utf-8") as f:
    trans = json.load(f)

# Load skills and items
skill_tree = ET.parse(r"FE17-DOC-main\FE17-DOC-main\fe_assets_gamedata\Skill.xml")
skill_sheet = skill_tree.getroot().findall("Sheet")[0].find("Data").findall("Param")

item_tree = ET.parse(r"FE17-DOC-main\FE17-DOC-main\fe_assets_gamedata\Item.xml")
item_sheet = item_tree.getroot().findall("Sheet")[0].find("Data").findall("Param")

items_dict = {}
for i in item_sheet:
    iid = i.attrib.get("Iid")
    if iid:
        mid = i.attrib.get("Name", "")
        nom = trans.get(mid) or trans.get(f"MIID_{iid}") or trans.get(iid) or iid
        items_dict[iid] = {"iid": iid, "nombre": nom}

skills_dict = {}
stat_map = {
    "Hp": "hp", "Str": "str", "Magic": "mag", "Tech": "dex",
    "Quick": "spd", "Def": "def", "Mdef": "res", "Luck": "lck",
    "Phys": "bld", "Move": "mov"
}

for s in skill_sheet:
    sid = s.attrib.get("Sid")
    if not sid:
        continue
    enhances = {}
    for fld, stat_key in stat_map.items():
        v = s.attrib.get(f"EnhanceValue.{fld}", "0")
        if v and v != "0":
            try:
                enhances[stat_key] = int(v)
            except ValueError:
                pass
    mid = s.attrib.get("Name", "")
    nom = trans.get(mid) or trans.get(f"MSID_{sid}") or trans.get(sid) or sid
    skills_dict[sid] = {
        "sid": sid,
        "nombre": nom,
        "enhances": enhances,
        "help": trans.get(s.attrib.get("Help", ""), "")
    }

# Parse Sheet_1 levels grouped by Ggid
current_ggid = None
levels_by_ggid = {}
for r in level_sheet:
    ggid = r.attrib.get("Ggid", "").strip()
    if ggid:
        current_ggid = ggid
    if not current_ggid:
        continue
    lvl_str = r.attrib.get("Level", "").strip()
    if not lvl_str or not lvl_str.isdigit():
        continue
    lvl = int(lvl_str)
    if current_ggid not in levels_by_ggid:
        levels_by_ggid[current_ggid] = {}
    
    sync_skills = [s.strip() for s in r.attrib.get("SynchroSkills", "").split(";") if s.strip()]
    inh_skills = [s.strip() for s in r.attrib.get("InheritanceSkills", "").split(";") if s.strip()]
    eng_skills = [s.strip() for s in r.attrib.get("EngageSkills", "").split(";") if s.strip()]
    eng_items = [s.strip() for s in r.attrib.get("EngageItems", "").split(";") if s.strip()]

    levels_by_ggid[current_ggid][lvl] = {
        "synchro_skills": sync_skills,
        "inheritance_skills": inh_skills,
        "engage_skills": eng_skills,
        "engage_items": eng_items
    }

# Build full 1..20 progression for each base emblem
base_emblems = {}
for g in god_sheet:
    gid = g.attrib.get("Gid")
    if not gid or gid.startswith("GID_M0") or "相手" in gid or "敵" in gid:
        continue
    grow = g.attrib.get("GrowTable")
    ascii_name = g.attrib.get("AsciiName")
    mid = g.attrib.get("Mid", "")
    nom = trans.get(mid) or ascii_name or gid
    if not nom or nom == "???":
        continue

    raw_levels = levels_by_ggid.get(grow, {})
    
    # Calculate cumulative progression for levels 1 to 20
    bond_levels = {}
    active_stats = {s: 0 for s in ["hp", "str", "mag", "dex", "spd", "def", "res", "lck", "bld", "mov"]}
    active_passives = {} # sid_base: {sid, nombre}
    active_items = []
    active_engage_skills = []

    for l in range(1, 21):
        lvl_data = raw_levels.get(l, {"synchro_skills": [], "inheritance_skills": [], "engage_skills": [], "engage_items": []})
        
        # 1. Engage items unlocked
        for iid in lvl_data["engage_items"]:
            if iid not in [it["iid"] for it in active_items]:
                it_nom = items_dict.get(iid, {}).get("nombre", iid)
                active_items.append({"iid": iid, "nombre": it_nom})

        # 2. Engage skills unlocked
        for sid in lvl_data["engage_skills"]:
            if sid not in [es["sid"] for es in active_engage_skills]:
                s_info = skills_dict.get(sid, {})
                active_engage_skills.append({"sid": sid, "nombre": s_info.get("nombre", sid)})

        # 3. Synchro skills: stat boosts vs passives
        for sid in lvl_data["synchro_skills"]:
            s_info = skills_dict.get(sid, {})
            enh = s_info.get("enhances", {})
            if enh:
                # Stat booster
                for stat_k, val in enh.items():
                    active_stats[stat_k] = max(active_stats.get(stat_k, 0), val)
            else:
                # Combat passive
                # Check for upgraded version replacing base (e.g. Canter+ replaces Canter)
                base_key = sid.rstrip("＋+0123456789")
                active_passives[base_key] = {"sid": sid, "nombre": s_info.get("nombre", sid)}

        # 4. Inheritable skills unlocked at this level
        inh_at_level = []
        for sid in lvl_data["inheritance_skills"]:
            s_info = skills_dict.get(sid, {})
            inh_at_level.append({"sid": sid, "nombre": s_info.get("nombre", sid)})

        # Filter out 0 stats
        cur_boosts = {k: v for k, v in active_stats.items() if v > 0}

        bond_levels[str(l)] = {
            "level": l,
            "stat_boosts": dict(cur_boosts),
            "synchro_skills": list(active_passives.values()),
            "engage_items": list(active_items),
            "engage_skills": list(active_engage_skills),
            "inheritance_skills": inh_at_level
        }

    base_emblems[gid] = {
        "id": gid,
        "nombre": nom,
        "ascii_name": ascii_name,
        "link_name": g.attrib.get("LinkName", ""),
        "grow_table": grow,
        "bond_levels": bond_levels
    }

with open("scratch/base_emblems_compiled.json", "w", encoding="utf-8") as f:
    json.dump(base_emblems, f, indent=2, ensure_ascii=False)

print(f"Compiled {len(base_emblems)} base emblems with full 1..20 progression to scratch/base_emblems_compiled.json")
