import sys
sys.stdout.reconfigure(encoding='utf-8')

from motor_calculo import CalculadoraEngage, Unidad, Arma, Terreno

u_flier = Unidad('Sword Flier', hp=25, fuerza=11, magia=0, destreza=12,
                  velocidad=14, defensa=9, resistencia=7, suerte=8, complexion=7,
                  tipo_movimiento='volador')
u_alcryst = Unidad('Alcryst', hp=30, fuerza=12, magia=0, destreza=12,
                    velocidad=11, defensa=8, resistencia=7, suerte=9, complexion=7,
                    tipo_movimiento='infanteria')
steel_bow = Arma('Steel Bow', mt=9, wt=7, hit=75, crit=0, es_magica=False,
                  tipo='Arco', rango=[2], efectividades=['volador'])

# Verificar efectividad
mult, desc = CalculadoraEngage.calcular_efectividad(steel_bow, u_flier)
print(f"Efectividad vs volador: x{mult} -- {desc}")

# Simular golpe
terreno = Terreno()
golpe = CalculadoraEngage._stats_de_golpe(u_alcryst, steel_bow, u_flier, None, terreno)
atk_base = u_alcryst.fuerza + steel_bow.mt
print(f"ATK base: {atk_base} (STR {u_alcryst.fuerza} + Mt {steel_bow.mt})")
print(f"ATK efectivo: {atk_base * mult}")
print(f"Danio calculado: {golpe['daño']} (ATK_eff {atk_base * mult} - DEF {u_flier.defensa})")
print(f"Efectividad activa: {golpe['efectividad_activa']}")
print(f"Esperado segun juego: 33 HP (Lv10 Alcryst con STR~12, Steel Bow Mt9, DEF flier = 9 en Extremo)")
print(f"(42 - 9 = 33)")

