import sys, os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')
from catalogo_loader import parsear_arma_string, _arma_desde_item, _catalogo, _canonico

test_names = [
    'Javelin', 'Jabalina', 'Hand Axe', 'Hacha de mano', 
    'Iron Bow', 'Arco de hierro', 'Steel Bow', 'Arco de acero', 'Silver Bow', 'Arco de plata', 'Longbow', 'Arco largo',
    'Fire', 'Fuego', 'Thunder', 'Trueno', 'Elfire', 'Elthunder', 'Wind', 'Viento', 
    'Slim Lance', 'Lanza fina', 'Silver Lance', 'Lanza de plata'
]

print("--- BUSQUEDA EN CANONICO ---")
targets = ['jabalina', 'javelin', 'arco', 'bow', 'fire', 'fuego', 'trueno', 'thunder', 'hacha de mano', 'hand axe']
for k, v in _canonico.get('armas', {}).items():
    nom = str(v.get('nombre', '')).lower()
    if any(t == nom or t in nom for t in targets):
        print(f"CANONICO: {k:15} | NOMBRE: {v.get('nombre'):16} | RANGO: {str(v.get('rango')):10} | TIPO: {v.get('tipo')}")


