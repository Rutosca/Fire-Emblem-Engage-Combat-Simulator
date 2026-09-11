import sys, os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')

from cargador_dispos import CargadorDisposEngage
from catalogo_loader import resolver_unidad_con_catalogo

c = CargadorDisposEngage()
units = c.cargar_capitulo('M007', 'Extremo')
print("--- ENEMIGOS CAPÍTULO 7 ---")
for u in units:
    if not u.get('es_aliado'):
        ficha = resolver_unidad_con_catalogo(u)
        arma = ficha.arma
        rango = arma.rango if arma else None
        print(f"{ficha.nombre:25} | pos: ({ficha.x:2},{ficha.y:2}) | arma: {str(getattr(arma, 'nombre', 'None')):18} | tipo: {str(getattr(arma, 'tipo', 'None')):10} | rango: {rango}")
