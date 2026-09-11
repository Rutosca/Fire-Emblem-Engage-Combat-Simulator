import sys, os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')

ALIAS_ARMAS_ESPANOL = {
    "jabalina": "Javelin",
    "pica": "Spear",
    "lanza de hierro": "Iron Lance",
    "lanza de acero": "Steel Lance",
    "lanza de plata": "Silver Lance",
    "lanza fina": "Slim Lance",
    "lanza asesina": "Killer Lance",
    "lanza del valor": "Brave Lance",
    "gran lanza de hierro": "Iron Greatlance",
    "gran lanza de acero": "Steel Greatlance",
    "gran lanza de plata": "Silver Greatlance",
    "lanza pesada": "Heavy Lance",
    "lanza jinete": "Ridersbane",
    "lanza de fuego": "Flame Lance",
    "espada de hierro": "Iron Sword",
    "espada de acero": "Steel Sword",
    "espada de plata": "Silver Sword",
    "espada fina": "Slim Sword",
    "espada asesina": "Killing Edge",
    "espada del valor": "Brave Sword",
    "gran espada de hierro": "Iron Blade",
    "gran espada de acero": "Steel Blade",
    "gran espada de plata": "Silver Blade",
    "espada trueno": "Levin Sword",
    "machacaarmaduras": "Armorslayer",
    "antijinetes": "Ridersbane",
    "estoque": "Rapier",
    "hacha de mano": "Hand Axe",
    "hacha de hierro": "Iron Axe",
    "hacha de acero": "Steel Axe",
    "hacha de plata": "Silver Axe",
    "hacha asesina": "Killer Axe",
    "hacha del valor": "Brave Axe",
    "gran hacha de hierro": "Iron Greataxe",
    "gran hacha de acero": "Steel Greataxe",
    "gran hacha de plata": "Silver Greataxe",
    "hacha huracan": "Hurricane Axe",
    "hacha huracán": "Hurricane Axe",
    "machacamartillo": "Hammer",
    "hacha polo": "Poleax",
    "arco de hierro": "Iron Bow",
    "arco de acero": "Steel Bow",
    "arco de plata": "Silver Bow",
    "arco asesino": "Killer Bow",
    "arco del valor": "Brave Bow",
    "arco largo": "Longbow",
    "miniarco": "Mini Bow",
    "arco corto": "Mini Bow",
    "arco radiante": "Radiant Bow",
    "fuego": "Fire",
    "elfire": "Elfire",
    "bolganon": "Bolganone",
    "bolganone": "Bolganone",
    "trueno": "Thunder",
    "elthunder": "Elthunder",
    "toron": "Thoron",
    "thoron": "Thoron",
    "viento": "Wind",
    "elwind": "Elwind",
    "excalibur": "Excalibur",
    "fulgor": "Shine",
    "nosferatu": "Nosferatu",
    "serafin": "Seraphim",
    "seraphim": "Seraphim",
    "oleada": "Surge",
    "eloleada": "Elsurge",
    "daga de hierro": "Iron Dagger",
    "daga de acero": "Steel Dagger",
    "daga de plata": "Silver Dagger",
    "cuchillo de hierro": "Iron Dagger",
    "cuchillo de acero": "Steel Dagger",
    "cuchillo de plata": "Silver Dagger",
}

def inferir_rango_arma(nombre: str, tipo: str, rango_existente=None) -> list:
    nom_low = (nombre or "").lower()
    tipo_low = (tipo or "").lower()

    # Arcos
    if tipo_low in ("arco", "bow") or any(b in nom_low for b in ("arco", "bow")):
        if "longbow" in nom_low or "largo" in nom_low:
            return [2, 3]
        if "mini" in nom_low or "corto" in nom_low:
            return [1]
        return [2]

    # Armas arrojadizas 1-2
    if any(w in nom_low for w in ("javelin", "jabalina", "hand axe", "hacha de mano", "tomahawk", "spear", "pica", "short spear", "levin", "espada trueno", "flame lance", "lanza de fuego", "hurricane", "hacha huracan", "hacha huracán")):
        return [1, 2]

    # Tomos
    if tipo_low in ("tomo", "tome", "magia") or any(w in nom_low for w in ("fire", "fuego", "thunder", "trueno", "wind", "viento", "elfire", "elthunder", "elwind", "bolganone", "thoron", "excalibur", "surge", "elsurge", "shine", "fulgor", "nosferatu", "seraphim")):
        if any(th in nom_low for th in ("thunder", "trueno", "elthunder", "thoron")):
            return [1, 2, 3]
        if "surge" in nom_low or "oleada" in nom_low:
            return [1]
        return [1, 2]

    # Dagas
    if tipo_low in ("daga", "dagger", "knife", "cuchillo") or any(w in nom_low for w in ("daga", "dagger", "knife", "cuchillo", "stiletto", "misericorde", "cinquedea", "peshkatz", "carnwenhan")):
        return [1, 2]

    if isinstance(rango_existente, (list, tuple)) and len(rango_existente) > 0:
        return list(rango_existente)

    return [1]

test_cases = [
    ("Javelin", "Lanza"), ("Jabalina", "Lanza"),
    ("Hand Axe", "Hacha"), ("Hacha de mano", "Hacha"),
    ("Iron Bow", "Arco"), ("Arco de hierro", "Arco"),
    ("Steel Bow", "Arco"), ("Arco de acero", "Arco"),
    ("Longbow", "Arco"), ("Arco largo", "Arco"),
    ("Mini Bow", "Arco"), ("Miniarco", "Arco"),
    ("Fire", "Tomo"), ("Fuego", "Tomo"),
    ("Thunder", "Tomo"), ("Trueno", "Tomo"),
    ("Iron Sword", "Espada"), ("Espada de hierro", "Espada"),
    ("Iron Dagger", "Daga"), ("Daga de hierro", "Daga"),
]

for nom, tipo in test_cases:
    r = inferir_rango_arma(nom, tipo)
    print(f"{nom:18} ({tipo:8}) -> Rango: {r}")
