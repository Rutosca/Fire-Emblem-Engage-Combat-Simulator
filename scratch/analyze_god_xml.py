import xml.etree.ElementTree as ET
import json
import os

god_tree = ET.parse(r"FE17-DOC-main\FE17-DOC-main\fe_assets_gamedata\God.xml")
sheets = god_tree.getroot().findall("Sheet")
god_sheet = sheets[0].find("Data").findall("Param")
level_sheet = sheets[1].find("Data").findall("Param")

with open("traducciones_cache.json", "r", encoding="utf-8") as f:
    trans = json.load(f)

# Load skills for enhance stats
skill_tree = ET.parse(r"FE17-DOC-main\FE17-DOC-main\fe_assets_gamedata\Skill.xml")
skill_sheet = skill_tree.getroot().findall("Sheet")[0].find("Data").findall("Param")

skills_data = {}
for s in skill_sheet:
    sid = s.attrib.get("Sid")
    if not sid:
        continue
    # Check enhance stats
    enhances = {}
    for stat_field in ["Hp", "Str", "Magic", "Skill", "Quick", "Def", "Mdef", "Luck", "Special", "Move"]:
        val = s.attrib.get(f"Enhance.{stat_field}", "0")
        if val and val != "0":
            # map stat field to standard name
            stat_map = {
                "Hp": "hp", "Str": "str", "Magic": "mag", "Skill": "dex",
                "Quick": "spd", "Def": "def", "Mdef": "res", "Luck": "lck",
                "Special": "bld", "Move": "mov"
            }
            enhances[stat_map.get(stat_field, stat_field.lower())] = int(val)
    
    mid = s.attrib.get("Name", "")
    nom = trans.get(mid) or trans.get(f"MSID_{sid}") or trans.get(sid) or sid
    skills_data[sid] = {
        "sid": sid,
        "name": nom,
        "enhances": enhances,
        "help": trans.get(s.attrib.get("Help", ""), "")
    }

# Parse Level sheet
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

# Parse God sheet (emblems)
emblems = {}
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

    # Get bond progression
    prog = levels_by_ggid.get(grow, {})
    
    emblems[gid] = {
        "gid": gid,
        "nombre": nom,
        "ascii_name": ascii_name,
        "link_name": g.attrib.get("LinkName", ""),
        "grow_table": grow,
        "levels": prog
    }

with open("scratch/emblems_summary.json", "w", encoding="utf-8") as f:
    json.dump({
        "emblems_count": len(emblems),
        "emblem_names": [e["ascii_name"] for e in emblems.values()],
        "sample_marth": emblems.get("GID_マルス", {})
    }, f, indent=2, ensure_ascii=False)

print(f"Parsed {len(emblems)} emblems and saved summary!")
