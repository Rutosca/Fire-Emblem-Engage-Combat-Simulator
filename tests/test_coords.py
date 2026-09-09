from cargador_dispos import CargadorDisposEngage
c = CargadorDisposEngage()
fichas = c.cargar_capitulo('M007', 'extremo')

aliados = [f for f in fichas if f['es_aliado']]
enemigos_boss = [f for f in fichas if not f['es_aliado'] and f['nombre'] in ['Hortensia (Jefa)', 'Rosado', 'Goldmary']]

print("=== ALIADOS ===")
for a in aliados:
    nombre = a['nombre']
    x, y = a['x'], a['y']
    verde = a['es_verde']
    print(f"  {nombre:20} -> ({x}, {y}) | Verde: {verde}")

print()
print("=== JEFES ===")
for e in enemigos_boss:
    nombre = e['nombre']
    x, y = e['x'], e['y']
    print(f"  {nombre:20} -> ({x}, {y})")

print()
print("=== POSICIONES ESPECÍFICAS A VERIFICAR ===")
# Sword flier vanguardia (esperado: 7, 12)
vanguardia = [f for f in fichas if not f['es_aliado'] and f['x'] == 7]
for v in vanguardia:
    print(f"  Tropa en x=7: {v['nombre']} -> ({v['x']}, {v['y']})")
# Mages (esperado: 12, 11 y 12, 12)
mages = [f for f in fichas if not f['es_aliado'] and f['x'] == 12]
for m in mages:
    print(f"  Tropa en x=12: {m['nombre']} -> ({m['x']}, {m['y']})")
# Lance Fighters (esperado: 10, 5 y 10, 6)
lances = [f for f in fichas if not f['es_aliado'] and f['x'] == 10]
for l in lances:
    print(f"  Tropa en x=10: {l['nombre']} -> ({l['x']}, {l['y']})")
