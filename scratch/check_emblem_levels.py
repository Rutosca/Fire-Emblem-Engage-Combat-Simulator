import json
import xml.etree.ElementTree as ET
import os

tree = ET.parse(r"FE17-DOC-main\FE17-DOC-main\fe_assets_gamedata\God.xml")
root = tree.getroot()

sheets = root.findall("Sheet")
god_sheet = sheets[0].find("Data").findall("Param")
level_sheet = sheets[1].find("Data").findall("Param")

with open("traducciones_cache.json", "r", encoding="utf-8") as f:
    trans = json.load(f)

# Group level_sheet by Ggid
ggids = {}
for r in level_sheet:
    ggid = r.attrib.get("Ggid")
    if not ggid:
        continue
    if ggid not in ggids:
        ggids[ggid] = []
    lvl_raw = r.attrib.get("Level", "")
    if not lvl_raw or not lvl_raw.isdigit():
        continue
    lvl = int(lvl_raw)
    ggids[ggid].append({
        "level": lvl,
        "inheritance_skills": [s.strip() for s in r.attrib.get("InheritanceSkills", "").split(";") if s.strip()],
        "synchro_skills": [s.strip() for s in r.attrib.get("SynchroSkills", "").split(";") if s.strip()],
        "engage_skills": [s.strip() for s in r.attrib.get("EngageSkills", "").split(";") if s.strip()],
        "engage_items": [s.strip() for s in r.attrib.get("EngageItems", "").split(";") if s.strip()],
    })

# Now build detailed emblem profiles
emblems_by_gid = {}
for g in god_sheet:
    gid = g.attrib.get("Gid")
    if not gid or gid.startswith("GID_M0") or "相手" in gid or "敵" in gid:
        continue
    grow = g.attrib.get("GrowTable")
    ascii_name = g.attrib.get("AsciiName")
    mid = g.attrib.get("Mid", "")
    nombre = trans.get(mid) or ascii_name or gid
    if not nombre or nombre == "???":
        continue

    levels = ggids.get(grow, [])
    # Translate skill and item names
    translated_levels = []
    for l in sorted(levels, key=lambda x: x["level"]):
        translated_levels.append({
            "level": l["level"],
            "synchro_skills": [{"sid": s, "nombre": trans.get(s, trans.get(f"MSID_{s}", s))} for s in l["synchro_skills"]],
            "inheritance_skills": [{"sid": s, "nombre": trans.get(s, trans.get(f"MSID_{s}", s))} for s in l["inheritance_skills"]],
            "engage_skills": [{"sid": s, "nombre": trans.get(s, trans.get(f"MSID_{s}", s))} for s in l["engage_skills"]],
            "engage_items": [{"iid": i, "nombre": trans.get(i, trans.get(f"MIID_{i}", i))} for i in l["engage_items"]],
        })

    emblems_by_gid[gid] = {
        "gid": gid,
        "nombre": nombre,
        "grow_table": grow,
        "levels": translated_levels
    }

with open(r"scratch\emblem_bond_levels_analyzed.json", "w", encoding="utf-8") as f:
    json.dump(emblems_by_gid, f, ensure_ascii=False, indent=2)

print(f"Processed {len(emblems_by_gid)} emblems and saved to scratch/emblem_bond_levels_analyzed.json")
