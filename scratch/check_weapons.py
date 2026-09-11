import sys, json
sys.stdout.reconfigure(encoding='utf-8')

with open('json/catalogo_engage.json', 'r', encoding='utf-8') as f:
    cat = json.load(f)

targets = ['javelin', 'jabalina', 'hand axe', 'fire', 'thunder', 'trueno', 'elfire', 'iron bow', 'steel bow', 'silver bow', 'longbow']

for k, v in cat.get('armas', {}).items():
    nom = str(v.get('nombre', '')).lower()
    if any(t in nom or t in k.lower() for t in targets):
        print(f"KEY: {k} | NOMBRE: {v.get('nombre')} | TIPO: {v.get('tipo')} | RANGO: {v.get('rango')}")
