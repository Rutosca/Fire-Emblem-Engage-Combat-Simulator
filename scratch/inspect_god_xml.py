import xml.etree.ElementTree as ET
import json

tree = ET.parse(r"FE17-DOC-main\FE17-DOC-main\fe_assets_gamedata\God.xml")
root = tree.getroot()

sheets_data = []
for idx, sheet in enumerate(root.findall("Sheet")):
    sname = sheet.attrib.get("name") or f"Sheet_{idx}"
    data = sheet.find("Data")
    rows = [p.attrib for p in data.findall("Param")] if data is not None else []
    sheets_data.append({
        "index": idx,
        "name": sname,
        "row_count": len(rows),
        "keys": list(rows[0].keys()) if rows else [],
        "sample_rows": rows[:3]
    })

# Also search for GGID / Gid rows for Marth across all sheets
marth_findings = {}
for idx, sheet in enumerate(root.findall("Sheet")):
    data = sheet.find("Data")
    if data is not None:
        for p in data.findall("Param"):
            vals = list(p.attrib.values())
            if any("Marth" in v or "GGID_M001" in v or "GID_M001" in v for v in vals):
                k = f"Sheet_{idx}"
                if k not in marth_findings:
                    marth_findings[k] = []
                marth_findings[k].append(p.attrib)

with open(r"scratch\god_dump.json", "w", encoding="utf-8") as f:
    json.dump({"sheets": sheets_data, "marth_findings": marth_findings}, f, ensure_ascii=False, indent=2)

print("God dump saved to scratch/god_dump.json successfully!")
