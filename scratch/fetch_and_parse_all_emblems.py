import urllib.request
import ssl
import json
import re
from bs4 import BeautifulSoup
import os

dlc_emblems = ["edelgard", "tiki", "hector", "veronica", "soren", "camilla", "chrom"]
ctx = ssl._create_unverified_context()

os.makedirs("scratch/dlc_html", exist_ok=True)

parsed_dlc = {}

for emb_id in dlc_emblems:
    html_path = f"scratch/dlc_html/{emb_id}.html"
    if not os.path.exists(html_path):
        url = f"https://serenesforest.net/engage/emblems/{emb_id}/"
        print(f"Fetching {emb_id} from {url}...")
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=ctx) as resp:
            content = resp.read().decode('utf-8')
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(content)
    else:
        with open(html_path, "r", encoding="utf-8") as f:
            content = f.read()

    soup = BeautifulSoup(content, 'html.parser')
    tables = soup.find_all('table')
    print(f"{emb_id}: found {len(tables)} tables")

    # Table 0 is usually Stat Boosts, Table 1 is Skills and Weapons
    stat_table = None
    skill_table = None
    for tbl in tables:
        txt = tbl.get_text()
        if "Level" in txt and ("Str" in txt or "Mag" in txt or "Hp" in txt or "HP" in txt or "Def" in txt):
            stat_table = tbl
        elif "Bond" in txt and ("Sync" in txt or "Inheritable" in txt or "Engage" in txt):
            skill_table = tbl

    # Parse Stat table
    stat_boosts_by_level = {}
    if stat_table:
        rows = stat_table.find_all('tr')
        header_cells = [th.get_text().strip().lower() for th in rows[0].find_all(['th', 'td'])]
        # map headers to standard stat names
        header_map = {
            "str": "str", "mag": "mag", "dex": "dex", "spd": "spd",
            "def": "def", "res": "res", "lck": "lck", "luck": "lck",
            "bld": "bld", "hp": "hp", "mov": "mov"
        }
        stat_cols = [(idx, header_map[h]) for idx, h in enumerate(header_cells) if h in header_map]
        
        current_stats = {s: 0 for _, s in stat_cols}
        for r in rows[1:]:
            cells = [td.get_text().strip() for td in r.find_all(['td', 'th'])]
            if not cells or not cells[0].isdigit():
                continue
            lvl = int(cells[0])
            for idx, stat_name in stat_cols:
                if idx < len(cells):
                    val_str = cells[idx].replace('+', '').strip()
                    if val_str.isdigit():
                        current_stats[stat_name] = int(val_str)
            stat_boosts_by_level[lvl] = dict(current_stats)

    # Fill in all levels 1..20 with the accumulated stat boosts
    cum_stats = {}
    all_lvl_stats = {}
    for l in range(1, 21):
        if l in stat_boosts_by_level:
            cum_stats = dict(stat_boosts_by_level[l])
        all_lvl_stats[l] = dict(cum_stats)

    # Parse Skill table
    skills_by_level = {l: {"synchro_skills": [], "inheritance_skills": [], "engage_skills": [], "engage_items": [], "engage_attacks": []} for l in range(1, 21)}
    if skill_table:
        rows = skill_table.find_all('tr')
        for r in rows[1:]:
            cells = [td.get_text().strip() for td in r.find_all(['td', 'th'])]
            if len(cells) < 4:
                continue
            lvl_str = cells[0]
            if not lvl_str.isdigit():
                continue
            lvl = int(lvl_str)
            if lvl < 1 or lvl > 20:
                continue
            name = cells[1]
            desc = cells[2]
            stype = cells[3]
            sp = cells[4] if len(cells) > 4 else ""

            entry = {"nombre": name, "descripcion": desc, "tipo": stype, "sp": sp}
            stype_low = stype.lower()

            if "sync" in stype_low:
                skills_by_level[lvl]["synchro_skills"].append(entry)
            elif "engage weapon" in stype_low:
                skills_by_level[lvl]["engage_items"].append(entry)
            elif "engage attack" in stype_low:
                skills_by_level[lvl]["engage_attacks"].append(entry)
            elif "engage skill" in stype_low:
                skills_by_level[lvl]["engage_skills"].append(entry)
            elif "inheritable" in stype_low:
                skills_by_level[lvl]["inheritance_skills"].append(entry)

    parsed_dlc[emb_id] = {
        "id": f"GID_DLC_{emb_id.upper()}",
        "nombre": emb_id.capitalize() if emb_id != "edelgard" else "Edelgard / Dimitri / Claude",
        "stat_boosts": all_lvl_stats,
        "skills_by_level": skills_by_level
    }

with open("scratch/dlc_emblems_parsed.json", "w", encoding="utf-8") as f:
    json.dump(parsed_dlc, f, indent=2, ensure_ascii=False)

print("DLC Emblems parsed successfully and saved to scratch/dlc_emblems_parsed.json")
