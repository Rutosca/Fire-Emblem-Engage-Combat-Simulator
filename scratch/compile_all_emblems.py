import xml.etree.ElementTree as ET
import json
import os
import re
from bs4 import BeautifulSoup

BASE_DIR = r"c:\Rubén\Proyectos\Engage_tracker"
DATAMINE_DIR = os.path.join(BASE_DIR, "FE17-DOC-main", "FE17-DOC-main", "fe_assets_gamedata")

with open(os.path.join(BASE_DIR, "traducciones_cache.json"), "r", encoding="utf-8") as f:
    trans = json.load(f)

# 1. Base Game Emblems from XML
god_tree = ET.parse(os.path.join(DATAMINE_DIR, "God.xml"))
god_sheet = god_tree.getroot().findall("Sheet")[0].find("Data").findall("Param")
level_sheet = god_tree.getroot().findall("Sheet")[1].find("Data").findall("Param")

skill_tree = ET.parse(os.path.join(DATAMINE_DIR, "Skill.xml"))
skill_sheet = skill_tree.getroot().findall("Sheet")[0].find("Data").findall("Param")

item_tree = ET.parse(os.path.join(DATAMINE_DIR, "Item.xml"))
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

all_emblems = {}

# Build Base Emblems
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
    
    bond_levels = {}
    active_stats = {s: 0 for s in ["hp", "str", "mag", "dex", "spd", "def", "res", "lck", "bld", "mov"]}
    active_passives = {}
    active_items = []
    active_engage_skills = []

    for l in range(1, 21):
        lvl_data = raw_levels.get(l, {"synchro_skills": [], "inheritance_skills": [], "engage_skills": [], "engage_items": []})
        
        # Engage items
        for iid in lvl_data["engage_items"]:
            if iid not in [it["iid"] for it in active_items]:
                it_nom = items_dict.get(iid, {}).get("nombre", iid)
                active_items.append({"iid": iid, "nombre": it_nom})

        # Engage skills
        for sid in lvl_data["engage_skills"]:
            if sid not in [es["sid"] for es in active_engage_skills]:
                s_info = skills_dict.get(sid, {})
                active_engage_skills.append({"sid": sid, "nombre": s_info.get("nombre", sid)})

        # Synchro skills
        for sid in lvl_data["synchro_skills"]:
            s_info = skills_dict.get(sid, {})
            enh = s_info.get("enhances", {})
            if enh:
                for stat_k, val in enh.items():
                    active_stats[stat_k] = max(active_stats.get(stat_k, 0), val)
            else:
                # Filter out internal boss flags
                if "特効" in sid:
                    continue
                base_key = sid.rstrip("＋+0123456789")
                active_passives[base_key] = {"sid": sid, "nombre": s_info.get("nombre", sid)}

        # Inheritance skills
        inh_at_level = []
        for sid in lvl_data["inheritance_skills"]:
            s_info = skills_dict.get(sid, {})
            inh_at_level.append({"sid": sid, "nombre": s_info.get("nombre", sid)})

        cur_boosts = {k: v for k, v in active_stats.items() if v > 0}

        bond_levels[str(l)] = {
            "level": l,
            "stat_boosts": dict(cur_boosts),
            "synchro_skills": list(active_passives.values()),
            "engage_items": list(active_items),
            "engage_skills": list(active_engage_skills),
            "inheritance_skills": inh_at_level,
            "max_energia_emblema": 5 if l >= 20 else 6
        }

    # Top-level legacy fallbacks (Level 10)
    fb10 = bond_levels.get("10", bond_levels.get("1", {}))
    all_emblems[gid] = {
        "id": gid,
        "nombre": nom,
        "ascii_name": ascii_name,
        "link_name": g.attrib.get("LinkName", ""),
        "grow_table": grow,
        "engage_items": [it["iid"] for it in fb10.get("engage_items", [])],
        "engage_skills": [sk["sid"] for sk in fb10.get("engage_skills", [])],
        "synchro_skills": [sk["sid"] for sk in fb10.get("synchro_skills", [])],
        "bond_levels": bond_levels
    }

print(f"Loaded {len(all_emblems)} base emblems from XML.")

# 2. Parse DLC Emblems from HTML files
dlc_meta = [
    ("edelgard", "GID_DLC_EDELGARD", "Edelgard / Dimitri / Claude", "Edelgard"),
    ("tiki", "GID_DLC_TIKI", "Tiki", "Tiki"),
    ("hector", "GID_DLC_HECTOR", "Hector", "Hector"),
    ("veronica", "GID_DLC_VERONICA", "Veronica", "Veronica"),
    ("soren", "GID_DLC_SOREN", "Soren", "Soren"),
    ("camilla", "GID_DLC_CAMILLA", "Camilla", "Camilla"),
    ("chrom", "GID_DLC_CHROM", "Chrom / Robin", "Chrom"),
]

stat_header_map = {
    "str": "str", "mag": "mag", "dex": "dex", "spd": "spd",
    "def": "def", "res": "res", "lck": "lck", "luck": "lck",
    "bld": "bld", "hp": "hp", "mov": "mov"
}

for emb_key, gid, full_name, ascii_name in dlc_meta:
    html_file = os.path.join(BASE_DIR, "scratch", "dlc_html", f"{emb_key}.html")
    if not os.path.exists(html_file):
        continue
    with open(html_file, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    stat_table = None
    skill_table = None
    for tbl in soup.find_all("table"):
        rows = tbl.find_all("tr")
        if not rows:
            continue
        hdr = [th.get_text().strip().lower() for th in rows[0].find_all(["th", "td"])]
        if "bond" in hdr:
            skill_table = tbl
        elif "level" in hdr:
            stat_table = tbl

    # Parse stat table
    raw_stats_by_level = {}
    if stat_table:
        rows = stat_table.find_all("tr")
        header_cells = [th.get_text().strip().lower() for th in rows[0].find_all(["th", "td"])]
        stat_cols = [(idx, stat_header_map[h]) for idx, h in enumerate(header_cells) if h in stat_header_map]
        
        cur = {s: 0 for _, s in stat_cols}
        for r in rows[1:]:
            cells = [td.get_text().strip() for td in r.find_all(["td", "th"])]
            if not cells or not cells[0].isdigit():
                continue
            lvl = int(cells[0])
            for idx, sname in stat_cols:
                if idx < len(cells):
                    vstr = cells[idx].replace("+", "").strip()
                    if vstr.isdigit():
                        cur[sname] = int(vstr)
            raw_stats_by_level[lvl] = dict(cur)

    # Accumulate stats 1..20
    cum_stats = {}
    stats_1_to_20 = {}
    for l in range(1, 21):
        if l in raw_stats_by_level:
            cum_stats = dict(raw_stats_by_level[l])
        stats_1_to_20[l] = {k: v for k, v in cum_stats.items() if v > 0}

    # Parse skill table
    skills_by_level = {l: {"synchro_skills": [], "inheritance_skills": [], "engage_skills": [], "engage_items": []} for l in range(1, 21)}
    if skill_table:
        rows = skill_table.find_all("tr")
        for r in rows[1:]:
            cells = [td.get_text().strip() for td in r.find_all(["td", "th"])]
            if len(cells) < 4:
                continue
            if not cells[0].isdigit():
                continue
            lvl = int(cells[0])
            if lvl < 1 or lvl > 20:
                continue
            name = cells[1]
            desc = cells[2]
            stype = cells[3].lower()
            sp = cells[4] if len(cells) > 4 else ""

            entry = {"nombre": name, "descripcion": desc, "sp": sp}
            if "sync" in stype:
                skills_by_level[lvl]["synchro_skills"].append(entry)
            elif "engage weapon" in stype:
                skills_by_level[lvl]["engage_items"].append(entry)
            elif "engage skill" in stype:
                skills_by_level[lvl]["engage_skills"].append(entry)
            elif "inheritable" in stype:
                skills_by_level[lvl]["inheritance_skills"].append(entry)

    # Accumulate 1..20 progression
    dlc_bond_levels = {}
    active_dlc_passives = {}
    active_dlc_items = []
    active_dlc_skills = []

    for l in range(1, 21):
        lvl_sk = skills_by_level[l]
        for it in lvl_sk["engage_items"]:
            if it["nombre"] not in [x["nombre"] for x in active_dlc_items]:
                active_dlc_items.append({"iid": it["nombre"], "nombre": it["nombre"]})

        for sk in lvl_sk["engage_skills"]:
            if sk["nombre"] not in [x["nombre"] for x in active_dlc_skills]:
                active_dlc_skills.append({"sid": sk["nombre"], "nombre": sk["nombre"]})

        for sy in lvl_sk["synchro_skills"]:
            base_key = sy["nombre"].rstrip("+123456789 ")
            active_dlc_passives[base_key] = {"sid": sy["nombre"], "nombre": sy["nombre"]}

        inh_list = [{"sid": inh["nombre"], "nombre": inh["nombre"], "sp": inh.get("sp", "")} for inh in lvl_sk["inheritance_skills"]]

        dlc_bond_levels[str(l)] = {
            "level": l,
            "stat_boosts": dict(stats_1_to_20[l]),
            "synchro_skills": list(active_dlc_passives.values()),
            "engage_items": list(active_dlc_items),
            "engage_skills": list(active_dlc_skills),
            "inheritance_skills": inh_list,
            "max_energia_emblema": 5 if l >= 20 else 6
        }

    fb10 = dlc_bond_levels.get("10", dlc_bond_levels.get("1", {}))
    all_emblems[gid] = {
        "id": gid,
        "nombre": full_name,
        "ascii_name": ascii_name,
        "link_name": ascii_name,
        "grow_table": f"GGID_{emb_key.upper()}",
        "engage_items": [it["iid"] for it in fb10.get("engage_items", [])],
        "engage_skills": [sk["sid"] for sk in fb10.get("engage_skills", [])],
        "synchro_skills": [sk["sid"] for sk in fb10.get("synchro_skills", [])],
        "bond_levels": dlc_bond_levels
    }

print(f"Total compiled emblems (Base + DLC): {len(all_emblems)}")

with open("scratch/all_emblems_verified.json", "w", encoding="utf-8") as f:
    json.dump(all_emblems, f, indent=2, ensure_ascii=False)

print("Saved verification JSON to scratch/all_emblems_verified.json")
