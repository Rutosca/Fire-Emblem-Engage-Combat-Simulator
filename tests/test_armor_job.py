import json
import sys
sys.stdout.reconfigure(encoding='utf-8')
with open('catalogo_engage.json', 'r', encoding='utf-8') as f:
    cat = json.load(f)

for jid, j in cat.get('clases', {}).items():
    if 'Lance Armor' in j.get('nombre', '') or 'アーマー' in jid:
        print(f"{jid}: {j.get('nombre')}")
        print(f"  Bases: {j.get('base_stats')}")
        print(f"  Growths: {j.get('growths')}")
