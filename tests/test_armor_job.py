import json
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
path_cat = 'json/catalogo_engage.json' if os.path.exists('json/catalogo_engage.json') else 'catalogo_engage.json'
if os.path.exists(path_cat):
    with open(path_cat, 'r', encoding='utf-8') as f:
        cat = json.load(f)
else:
    cat = {}

for jid, j in cat.get('clases', {}).items():
    if 'Lance Armor' in j.get('nombre', '') or 'アーマー' in jid:
        print(f"{jid}: {j.get('nombre')}")
        print(f"  Bases: {j.get('base_stats')}")
        print(f"  Growths: {j.get('growths')}")
