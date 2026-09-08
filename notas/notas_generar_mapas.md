# Generar_mapas.py
##
- este script no genera la cuadrícula visual de Tiled (tiles 2D), sino el "manifiesto" o ficha técnica de cada capítulo.
## 1. Cabecera y Mapeo de Nombres (Líneas 1 a 50)
- Configura las rutas relativas para leer Chapter.xml y volcar la salida en la carpeta mapas/.  
- TITULOS_EN (Líneas 21-50): En el datamine original, muchos nombres de capítulos vienen en japonés o como códigos internos. Creaste este diccionario auxiliar que actúa como capa de localización para que en la interfaz web o en consola se lea "Chapter 7: Dark Emblem" en vez de solo CID_M007.
## 2. El truco del Comodín: resolver_comodin (Líneas 53-63)
- En Chapter.xml, para no repetir texto, usan el carácter * como comodín.
- Si estás en el capítulo CID_M007, y en el XML el campo Dispos vale "*", significa que el archivo real es M007.xml. Si pone "Field_*", el campo se llama Field_M007.
- short = capitulo_id.replace("CID_", "") extrae la raíz limpia (M007) y sustituye cualquier asterisco por ese identificador. Si el campo está vacío, devuelve None para evitar strings vacíos en el JSON final.
## 3. Parseo del XML: parsear_chapter_xml (Líneas 66-78)
- Los XMLs de datos de Engage están estructurados como hojas de cálculo de Excel exportadas: Root -> Sheet -> Data -> Param.  
- Cada etiqueta Param es una fila que tiene sus propiedades guardadas como atributos XML (attrib).  
- dict(param.attrib) convierte todos esos atributos de golpe en un diccionario estándar de Python {"Cid": "CID_M007", "RecommendedLevel": "11", ...}.
## 4. Normalización del Esquema: generar_json_capitulo (Líneas 81-112)
###
- Define el contrato de datos o esquema que consume la aplicación
### Enlaces a otros assets del datamine:
- "dispos_id": Apunta al XML de unidades en dispos/ (el que lee cargador_dispos.py).
- "terrain_id": Apunta a la tabla de terrenos que usará este escenario.  
- "field_id": Apunta a los modelos 3D y cuadrícula del escenario.
- "script_bmap", "script_encount", "script_kizuna": Nombres de los scripts de eventos de la misión (cinemáticas, refuerzos programados, diálogos).
### Metadatos jugables:
- "nivel_recomendado": Nivel del juego base, asegurando un fallback a 1 con un bloque try/except por si el campo viene vacío o corrupto
- "siguiente_capitulo": Permite al backend encadenar misiones automáticamente.
- "bgm_jugador" / "bgm_enemigo": Los identificadores de la música de fondo para cada fase.
## 5. El Generador y Filtro de Historia: generar_todos_los_mapas (Líneas 115-142)
- Chapter.xml no solo tiene los 26 capítulos principales; también contiene desvíos (Paralogues tipo CID_S001), capítulos del DLC (Fell Xenologue tipo CID_E001) y mapas de prueba.  
- El filtro startswith("CID_M") descarta todo lo secundario y se queda estrictamente con los 27 mapas de la historia principal (M000 a M026).
- Itera sobre cada uno, llama a generar_json_capitulo(), y escribe el archivo formateado (indent=2) en mapas/{short}.json.  