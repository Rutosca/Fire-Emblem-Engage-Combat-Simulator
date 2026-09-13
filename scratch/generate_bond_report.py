import json

with open(r"scratch\emblem_bond_levels_analyzed.json", "r", encoding="utf-8") as f:
    data = json.load(f)

lines = ["# Reporte de Desglose de Niveles de Vínculo de Emblemas (1 a 20)\n"]

for gid, emb in data.items():
    lines.append(f"## Emblema: {emb['nombre']} (`{gid}`, Tabla: `{emb['grow_table']}`)\n")
    for lvl_info in emb["levels"]:
        l = lvl_info["level"]
        sync_sk = [s["nombre"] for s in lvl_info["synchro_skills"]]
        inh_sk = [s["nombre"] for s in lvl_info["inheritance_skills"]]
        eng_sk = [s["nombre"] for s in lvl_info["engage_skills"]]
        eng_it = [i["nombre"] for i in lvl_info["engage_items"]]
        
        parts = []
        if sync_sk:
            parts.append(f"**Sincronía (Inmediatas):** {', '.join(sync_sk)}")
        if eng_sk:
            parts.append(f"**Habilidades Engage:** {', '.join(eng_sk)}")
        if eng_it:
            parts.append(f"**Armas Engage:** {', '.join(eng_it)}")
        if inh_sk:
            parts.append(f"*Heredables:* {', '.join(inh_sk)}")

        desc = " | ".join(parts) if parts else "(Sin cambios o solo aumento de stats)"
        lines.append(f"- **Nivel {l:2d}**: {desc}")
    lines.append("\n" + "-"*60 + "\n")

with open(r"scratch\emblem_levels_report.md", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print("emblem_levels_report.md created successfully!")
