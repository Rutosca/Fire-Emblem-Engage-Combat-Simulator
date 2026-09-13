import sys, os
sys.path.insert(0, os.path.abspath('.'))
from app import tablero, _mapa, _desplegar_capitulo
from motor_analisis import analizar_situacion_tactica

_desplegar_capitulo('M007', 'Extremo')

hortensia = tablero.obtener_ficha("Hortensia (Boss)")
print("Hortensia:", hortensia.x, hortensia.y, hortensia.stats.hp, hortensia.arma)

# Move allies in range of Hortensia
alear = tablero.obtener_ficha("Alear")
alear.x, alear.y = 20, 8

alcryst = tablero.obtener_ficha("Alcryst")
alcryst.x, alcryst.y = 19, 8

citrinne = tablero.obtener_ficha("Citrinne")
citrinne.x, citrinne.y = 21, 9

lapis = tablero.obtener_ficha("Lapis")
lapis.x, lapis.y = 20, 9

try:
    res = analizar_situacion_tactica(tablero, _mapa)
    print("SUCCESS! Resultados:", res['total_analizados'])
    for r in res['resultados']:
        print(r.get('tipo_analisis'), r.get('aliado'), '->', r.get('enemigo'), '|', r.get('recomendacion'))
except Exception as e:
    import traceback
    print("CAUGHT ERROR:", type(e), e)
    traceback.print_exc()
