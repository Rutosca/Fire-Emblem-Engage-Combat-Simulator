import sys
from app import resolver_unidad_con_catalogo
from motor_calculo import CalculadoraEngage, Terreno

def run_test():
    f_alear = resolver_unidad_con_catalogo({
        'nombre': 'Alear', 'clase_nombre': 'Dragon Child', 'nivel': 10,
        'es_aliado': True, 'x': 5, 'y': 5, 'arma': 'Libération'
    })
    f_e1 = resolver_unidad_con_catalogo({
        'nombre': 'Lance Fighter 1', 'clase_nombre': 'Lance Fighter', 'nivel': 10,
        'es_aliado': False, 'x': 6, 'y': 5, 'arma': 'Iron Lance'
    })
    f_e2 = resolver_unidad_con_catalogo({
        'nombre': 'Sword Fighter 2', 'clase_nombre': 'Sword Fighter', 'nivel': 10,
        'es_aliado': False, 'x': 4, 'y': 5, 'arma': 'Iron Sword'
    })
    f_e3 = resolver_unidad_con_catalogo({
        'nombre': 'Axe Fighter 3', 'clase_nombre': 'Axe Fighter', 'nivel': 10,
        'es_aliado': False, 'x': 5, 'y': 6, 'arma': 'Iron Axe'
    })

    print("=== TEST RUPTURA FE ENGAGE ===")
    print(f"Estado inicial Alear: cargas_ruptura={f_alear.cargas_ruptura}, en_ruptura={f_alear.cargas_ruptura > 0}")

    # Combate 1: Lance Fighter ataca a Alear con ventaja de armas
    print("\n--- Combate 1: Lance Fighter 1 ataca a Alear (Lanza vs Espada) ---")
    c1 = CalculadoraEngage.simular_combate(
        f_e1.stats, f_alear.stats, f_e1.arma, f_alear.arma, Terreno(), Terreno(),
        distancia=1, defensor_en_ruptura=(f_alear.cargas_ruptura > 0)
    )
    print("Secuencia:", [s['tipo'] for s in c1['resultado']['secuencia']])
    print("Ruptura infligida a Alear:", c1['resultado']['aplica_ruptura'])
    if c1['resultado']['aplica_ruptura']:
        f_alear.cargas_ruptura = 1
    elif f_alear.cargas_ruptura > 0:
        f_alear.cargas_ruptura -= 1
    print(f"Alear tras C1: cargas_ruptura={f_alear.cargas_ruptura}, en_ruptura={f_alear.cargas_ruptura > 0}")

    # Combate 2: Sword Fighter 2 ataca a Alear mientras Alear está en ruptura
    print("\n--- Combate 2: Sword Fighter 2 ataca a Alear mientras está en ruptura ---")
    c2 = CalculadoraEngage.simular_combate(
        f_e2.stats, f_alear.stats, f_e2.arma, f_alear.arma, Terreno(), Terreno(),
        distancia=1, defensor_en_ruptura=(f_alear.cargas_ruptura > 0)
    )
    print("Secuencia:", [s['tipo'] for s in c2['resultado']['secuencia']])
    pudo_contra_2 = any("contra" in s['tipo'] for s in c2['resultado']['secuencia'])
    print("¿Pudo contraatacar Alear?:", pudo_contra_2)
    assert not pudo_contra_2, "¡Alear NO debería poder contraatacar en el 2º combate!"
    if c2['resultado']['aplica_ruptura']:
        f_alear.cargas_ruptura = 1
    elif f_alear.cargas_ruptura > 0:
        f_alear.cargas_ruptura -= 1
    print(f"Alear tras C2: cargas_ruptura={f_alear.cargas_ruptura}, en_ruptura={f_alear.cargas_ruptura > 0}")

    # Combate 3: Axe Fighter 3 ataca a Alear. La ruptura ya expiró en el combate 2.
    print("\n--- Combate 3: Axe Fighter 3 ataca a Alear tras expirar la ruptura ---")
    c3 = CalculadoraEngage.simular_combate(
        f_e3.stats, f_alear.stats, f_e3.arma, f_alear.arma, Terreno(), Terreno(),
        distancia=1, defensor_en_ruptura=(f_alear.cargas_ruptura > 0)
    )
    print("Secuencia:", [s['tipo'] for s in c3['resultado']['secuencia']])
    pudo_contra_3 = any("contra" in s['tipo'] for s in c3['resultado']['secuencia'])
    print("¿Pudo contraatacar Alear?:", pudo_contra_3)
    assert pudo_contra_3, "¡Alear SÍ debería poder contraatacar en el 3º combate!"
    if c3['resultado']['aplica_ruptura']:
        f_alear.cargas_ruptura = 1
    elif f_alear.cargas_ruptura > 0:
        f_alear.cargas_ruptura -= 1
    print(f"Alear tras C3: cargas_ruptura={f_alear.cargas_ruptura}, en_ruptura={f_alear.cargas_ruptura > 0}")

    print("\n>>> ¡TODAS LAS ASERCIONES PASARON CON ÉXITO! <<<")

if __name__ == "__main__":
    run_test()
