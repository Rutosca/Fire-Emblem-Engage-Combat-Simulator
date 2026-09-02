import json
import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('catalogo_engage.json', 'r', encoding='utf-8') as f:
    cat = json.load(f)

personas = cat.get('personajes', {})
print("--- BUSCANDO LANCE ARMOR ---")
for pid, p in personas.items():
    if 'アーマー' in pid or 'Lance Armor' in p.get('nombre', '') or 'armor' in pid.lower():
        print(f"{pid}: {p.get('nombre')}")
        print(f"  Bases: {p.get('base_stats')}")
        print(f"  Growths: {p.get('growths')}")
        break

print("\n--- BUSCANDO GENERIC ENEMIES EN GENERAL ---")
for pid, p in list(personas.items())[:20]:
    if 'PID_M007' in pid or '異形兵' in p.get('nombre', ''):
        print(f"{pid}: {p.get('nombre')}")
        print(f"  Bases: {p.get('base_stats')}")
        break
