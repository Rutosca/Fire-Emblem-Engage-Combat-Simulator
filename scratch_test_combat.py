from app import resolver_unidad_con_catalogo, _cargador_dispos
from motor_calculo import CalculadoraEngage, Terreno

dispos = _cargador_dispos.cargar_capitulo("M007", "Extremo")
fichas = {}
for u in dispos:
    f = resolver_unidad_con_catalogo(u)
    fichas[f.nombre] = f
    if any(n in f.nombre for n in ["Lapis", "Alear", "Lance Fighter", "Lance Armor"]):
        arma_nom = f.arma.nombre if f.arma else "Ninguna"
        mt = getattr(f.arma, "mt", 0) if f.arma else 0
        tipo = getattr(f.arma, "tipo", "Desconocido") if f.arma else ""
        st = f.stats
        bando = 'aliado' if f.es_aliado else 'enemigo'
        print(f"{f.nombre} ({bando}) | Clase: {f.clase_nombre} | STR: {getattr(st, 'fuerza', 0)} | DEF: {getattr(st, 'defensa', 0)} | SPD: {getattr(st, 'velocidad', 0)} | BLD: {getattr(st, 'complexion', 0)} | Arma: {arma_nom} (Mt: {mt}, Tipo: {tipo})")

print("\n--- SIMULACIONES DE COMBATE ---")
lapis = fichas.get("Lapis")
alear = fichas.get("Alear")

lance_fighters = [f for n, f in fichas.items() if "Lance Fighter" in n]
lance_armors = [f for n, f in fichas.items() if "Lance Armor" in n]

terreno_llano = Terreno(nombre="Llanura", avo=0, dfn=0)

if lapis and lance_fighters:
    lf = lance_fighters[0]
    res = CalculadoraEngage.simular_combate(lapis.stats, lf.stats, lapis.arma, lf.arma, terreno_llano, terreno_llano)
    print(f"\n[Lapis -> Lance Fighter]")
    print(f"Lapis arma: {lapis.arma.nombre} (Mt={lapis.arma.mt}, Wt={lapis.arma.wt})")
    print(f"Lance Fighter arma: {lf.arma.nombre} (Mt={lf.arma.mt}, Wt={lf.arma.wt})")
    print("Atacante:", res["atacante"])
    print("Defensor:", res["defensor"])
    print("Secuencia:", res.get("secuencia", []))

if alear and lance_armors:
    la = lance_armors[0]
    res2 = CalculadoraEngage.simular_combate(alear.stats, la.stats, alear.arma, la.arma, terreno_llano, terreno_llano)
    print(f"\n[Alear -> Lance Armor]")
    print(f"Alear arma: {alear.arma.nombre} (Mt={alear.arma.mt}, Wt={alear.arma.wt})")
    print(f"Lance Armor arma: {la.arma.nombre} (Mt={la.arma.mt}, Wt={la.arma.wt})")
    print("Atacante:", res2["atacante"])
    print("Defensor:", res2["defensor"])
    print("Secuencia:", res2.get("secuencia", []))
