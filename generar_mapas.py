"""
generar_mapas.py — FE Engage Tactical Assistant
Lee Chapter.xml del datamine y genera un JSON de metadata por cada capítulo
principal de la historia (CID_M000 a CID_M026) en la carpeta mapas/.

El motor de Engage usa '*' como comodín en los campos de Chapter.xml.
Este script resuelve esos comodines sustituyendo '*' por el identificador
numérico del capítulo (ej. CID_M007 → 'M007').
"""

import xml.etree.ElementTree as ET
import os
import json

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CHAPTER_XML = os.path.join(BASE_DIR, "FE17-DOC-main", "FE17-DOC-main",
                            "fe_assets_gamedata", "Chapter.xml")
MAPAS_DIR   = os.path.join(BASE_DIR, "mapas")

# Traducciones de los títulos de capítulo (Help field en Chapter.xml)
# al inglés, extraídas de los CSV de localización.
# Se usan como nombre legible en el JSON.
TITULOS_EN = {
    "CID_M000": "Prologue: Awake at Last",
    "CID_M001": "Chapter 1: Awake at Last",
    "CID_M002": "Chapter 2: Queen Lumera",
    "CID_M003": "Chapter 3: Hostilities",
    "CID_M004": "Chapter 4: A Land in Bloom",
    "CID_M005": "Chapter 5: Retaking the Castle",
    "CID_M006": "Chapter 6: The Stolen Ring",
    "CID_M007": "Chapter 7: Dark Emblem",
    "CID_M008": "Chapter 8: The Kingdom of Brodia",
    "CID_M009": "Chapter 9: A Clash of Forces",
    "CID_M010": "Chapter 10: The Fell Dragon Sombron",
    "CID_M011": "Chapter 11: Retreat",
    "CID_M012": "Chapter 12: The Desert War",
    "CID_M013": "Chapter 13: The Sentinels",
    "CID_M014": "Chapter 14: The Heroes of the Oasis",
    "CID_M015": "Chapter 15: Recursive Rings",
    "CID_M016": "Chapter 16: The Horrors of War",
    "CID_M017": "Chapter 17: Engaging the Commander",
    "CID_M018": "Chapter 18: The Cold Voyage",
    "CID_M019": "Chapter 19: The Dead Town",
    "CID_M020": "Chapter 20: The Fell & the Divine",
    "CID_M021": "Chapter 21: The Return",
    "CID_M022": "Chapter 22: The Fell-God War",
    "CID_M023": "Chapter 23: The Four Hounds",
    "CID_M024": "Chapter 24: Recollections",
    "CID_M025": "Chapter 25: The Final Guardian",
    "CID_M026": "Endgame: The Last Engage",
}


def resolver_comodin(valor: str, capitulo_id: str) -> str | None:
    """
    Sustituye '*' por el identificador corto del capítulo.
    'CID_M007' → 'M007', 'CID_M000' → 'M000'.
    Si el valor es vacío, devuelve None.
    """
    if not valor:
        return None
    # Identificador corto: 'M007' de 'CID_M007'
    short = capitulo_id.replace("CID_", "")
    return valor.replace("*", short) if "*" in valor else valor


def parsear_chapter_xml() -> list[dict]:
    """Parsea Chapter.xml y devuelve todas las filas como dicts."""
    if not os.path.exists(CHAPTER_XML):
        raise FileNotFoundError(f"No se encontró Chapter.xml en: {CHAPTER_XML}")
    tree = ET.parse(CHAPTER_XML)
    root = tree.getroot()
    filas = []
    for sheet in root.findall("Sheet"):
        data = sheet.find("Data")
        if data is None:
            continue
        for param in data.findall("Param"):
            filas.append(dict(param.attrib))
    return filas


def generar_json_capitulo(fila: dict) -> dict:
    """Convierte una fila de Chapter.xml en el JSON de mapa normalizado."""
    cid = fila["Cid"]

    def r(campo):
        return resolver_comodin(fila.get(campo, ""), cid)

    # Nivel recomendado
    try:
        nivel = int(fila.get("RecommendedLevel", "1"))
    except ValueError:
        nivel = 1

    return {
        "cid":               cid,
        "dispos_id":         r("Dispos"),
        "terrain_id":        r("Terrain"),
        "field_id":          r("Field"),
        "script_bmap":       r("ScriptBmap"),
        "script_encount":    r("ScriptEncount"),
        "script_kizuna":     r("ScriptKizuna"),
        "nivel_recomendado": nivel,
        "siguiente_capitulo": fila.get("NextChapter") or None,
        "nacion":            fila.get("Nation") or None,
        "entorno_sonido":    fila.get("SoundFieldSituation") or None,
        "bgm_jugador":       fila.get("PlayerPhaseBgm") or None,
        "bgm_enemigo":       fila.get("EnemyPhaseBgm") or None,
        "nombre_japones":    fila.get("Help") or None,
        "nombre_en":         TITULOS_EN.get(cid),
        "titulo_capitulo":   fila.get("ChapterTitle") or None,
        "flag":              int(fila.get("Flag", "0")),
        "gmap_spot":         fila.get("GmapSpot") or None,
    }


def generar_todos_los_mapas():
    os.makedirs(MAPAS_DIR, exist_ok=True)

    filas = parsear_chapter_xml()

    # Solo capítulos principales: CID_M000 … CID_M026
    capitulos_principales = [
        f for f in filas
        if f.get("Cid", "").startswith("CID_M")
    ]

    generados = []
    for fila in capitulos_principales:
        cid = fila["Cid"]
        # El número de capítulo (ej. 'M007')
        short = cid.replace("CID_", "")
        datos = generar_json_capitulo(fila)
        ruta = os.path.join(MAPAS_DIR, f"{short}.json")
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=2, ensure_ascii=False)
        generados.append(short)
        nombre_cap = datos.get('nombre_en') or datos.get('nombre_japones', '')
        print(f"  [OK] {short}.json  ->  {nombre_cap}")

    print(f"\n[DONE] {len(generados)} archivos generados en mapas/")
    return generados


if __name__ == "__main__":
    print("=== Generador de JSONs de mapa — FE Engage ===")
    generar_todos_los_mapas()
