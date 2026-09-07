# Compilar_catalogo.py
##
- Es el script constructor de base de datos estática del proyecto. Sin este archivo no existiría el catalogo_engage.json del que se nutren todos los cálculos del tracker y el simulador de combate.
- Transforma los XMLs crudos de datamining de FE Engage (FE17-DOC-main) y los mensajes de localización (fe_assets_message/ y translations/) en un único archivo JSON unificado y limpio: catalogo_engage.json.
- cargador_dispos.py, calculadora_combate.py, app.py y el frontend consumen directamente ese JSON resultante para no tener que parsear megabytes de XMLs en tiempo de ejecución.
- No necesita ejecutarse en cada inicio de la app; solo se corre cuando se quieren actualizar datos del juego o mejorar las traducciones/fórmulas maestras.

## constants.py — Módulo de constantes compartidas
###
- Las constantes de dominio del juego que antes vivían inline en compilar_catalogo.py se extrajeron a constants.py para que cualquier otro script pueda importarlas sin duplicar código.
- compilar_catalogo.py las importa con: from constants import JAPANESE_FALLBACK_TERMS, TIPO_ARMA_KIND, MOVE_TYPE_MAP, SID_A_EFECTIVIDAD
### JAPANESE_FALLBACK_TERMS
- Proveniente del código interno de Intelligent Systems, es un diccionario de fallback (~180 entradas).
- Si el sistema no encuentra un nombre en los CSV oficiales o solo existe como identificador japonés interno, lo busca aquí para obtener un equivalente en inglés.
- Ejemplos: "必殺" → "Crit", "追撃" → "Follow-Up", "飛行" → "Flying".
### TIPO_ARMA_KIND
- Mapea el entero del campo Kind de Item.xml a cadena legible: 1=Espada, 2=Lanza, 3=Hacha, 4=Arco, 5=Daga, 6=Tomo, 7=Bastón, 8=Artes, 9=Especial, 10=Objeto, 11=Accesorio.
### MOVE_TYPE_MAP
- Mapea el enum MoveType de Job.xml: 1=infantería, 2=caballería, 3=volador, 4=acorazado.
### SID_A_EFECTIVIDAD
- Mapea los SIDs internos de efectividad a tipo de movimiento legible: SID_飛行特効 → "volador", SID_鎧特効 → "acorazado", SID_馬特効 → "caballería", SID_竜特効 → "dragón", SID_異形特効 → "monstruo".

## Configuración de rutas y librerías (Líneas 1 a 19)
###
- Utiliza xml.etree.ElementTree, json, csv, os y re. Sin dependencias de terceros.
- Importa las cuatro constantes de dominio desde constants.py.
### Rutas del datamining
- DATAMINE_DIR: Apunta a fe_assets_gamedata/ (donde están Item.xml, Job.xml, Person.xml, Skill.xml, God.xml).
- USEN_DIR: Apunta a los CSV en inglés oficial (fe_assets_message/us/usen/csv/).
- TRANS_DIR: Diccionarios de traducción de la comunidad (translations/).

## Motor de carga de traducciones y sanitización (Líneas 20 a 210)
### to_int(val, default=0) (20-32):
- Convierte cadenas a entero de forma segura tolerando valores vacíos o nulos sin levantar excepciones.
### Caché de traducciones (_cache_valida, _CACHE_FILE)
- _CACHE_FILE apunta a traducciones_cache.json en la raíz del proyecto.
- _cache_valida() compara el timestamp del JSON de caché contra todos los archivos de USEN_DIR y TRANS_DIR con os.path.getmtime(). Si algún fuente es más nuevo, la caché se invalida.
- En la primera ejecución (o cuando cambian los CSV), cargar_traducciones() construye el diccionario completo y lo vuelca a traducciones_cache.json.
- En ejecuciones posteriores sin cambios, carga directamente el JSON de caché: el paso más costoso del script (parsear ~300 CSV) pasa de ~20s a menos de 1s.
### cargar_traducciones() (Líneas 54 a 145):
- Primero comprueba si la caché es válida; si lo es, devuelve el diccionario directamente del JSON.
- Si no, construye el diccionario con 4 capas de prioridad y lo guarda en caché al final:
- 1. Textos oficiales en inglés (USEN_DIR): Lee todos los CSVs y normaliza claves eliminando el BOM UTF-8 (\ufeff) y quitando prefijos de mensaje (MIID_, MJID_, MPID_, etc.) para indexar tanto por ID con prefijo como sin él.
- 2. fee-translations.csv: Cruza traducciones inglés-japonés con múltiples variantes de prefijos (PID_, JID_, IID_, etc.).
- 3. CSVs específicos (Item.csv, Job.csv, Person.csv, Skill.csv): Asigna nombres en inglés y genera alias cruzados con prefijos (MID_ITEM_*, MSID_*, SID_*, etc.).
- 4. Fallback japonés directo: Añade las constantes de JAPANESE_FALLBACK_TERMS importadas de constants.py.
### parsear_xml_generico(filepath) (Líneas 147 a 157):
- Itera todas las Sheet y dentro de cada una busca la etiqueta Data. Extrae cada elemento Param convirtiendo todos sus atributos XML en un diccionario Python.
### limpiar_nombre(ident, name_tag, trans) (Líneas 160 a 175):
- Pipeline en 5 pasos para resolver el nombre legible de cualquier entidad:
- 1. Búsqueda directa de name_tag o ident en el diccionario de traducciones.
- 2. Poda de prefijos de juego (MIID_, MJID_, IID_, etc.).
- 3. Partición por guion bajo (_) traduciendo token por token.
- 4. Reemplazo de residuales japoneses.
- 5. Expresión regular [\u3040-\u30ff...] para purgar cualquier carácter kanji/kana que haya quedado y dejar un identificador limpio.

## Sección 1 del catálogo: Armas e Ítems
###
- Lee Item.xml.
- Tipo de arma (TIPO_ARMA_KIND): importado de constants.py. Convierte el entero del motor a cadena (1=Espada, 2=Lanza... 6=Tomo, 7=Bastón, 8=Artes, 10=Objeto).
- Extracción de atributos de combate:
Mt (Power), Wt (Weight), Hit, Crit, Avo (Avoid), Ddg/Esquive de crítico (Secure).
Rango: Lee RangeI (mínimo) y RangeO (máximo) y genera una lista de enteros (ej: [1, 2]).
- Magia vs. Físico:
Comprueba si el tipo es Tomo, si WeaponAttr es 2 o 3, si el bit flag 65536 está activo (usado en espadas/lanzas mágicas), o si coincide con armas mágicas fijas (IID_いかづちの剣 = Levin Sword, etc.).
- Efectividades contra clases:
Parsea el atributo EquipSids separando por ";" y mapea usando SID_A_EFECTIVIDAD importado de constants.py.
- Durabilidad y Alíases:
Calcula usos máximos según Endurance (ignora valores infinitos/dummy como 255).
Renombra consumibles populares al español (IID_傷薬 -> "Poción").

## Sección 2 del catálogo: Clases / Jobs
###
- Lee Job.xml.
- Desambiguación: Corrige nombres genéricos duplicados en las traducciones para darles contexto real (ej. JID_ティラユール下級 -> "Lord (Alcryst)").
- Tipo de movimiento: Traduce el enum MoveType usando MOVE_TYPE_MAP importado de constants.py.
### Extracción de 4 bloques estadísticos clave:
- base_stats: Estadísticas base de la clase (HP, Str, Mag, Dex/Tech, Spd/Quick, Def, Res/Mdef, Lck, Bld/Phys).
- growths: Crecimientos de clase para el jugador (DiffGrow o GrowRatio).
- max_stats: Topes máximos de estadísticas (Limit.*).
- enemy_growths: Crecimientos usados exclusivamente por la IA enemiga divididos por dificultad (base, hard, lunatic).

## Sección 3 del catálogo: Personajes / Person
###
- Lee Person.xml.
- Bases personales: Extrae las bases (Base.* + OffsetN.*), permitiendo aislar lo que aporta el personaje de lo que aporta la clase.
- Crecimientos personales: Lee Grow.* o BaseGrow.*.
### Cálculo de estadísticas iniciales canónicas (join_stats):
- Aplica la fórmula de subida de nivel de Engage: Stat = (Base Clase + Base Personaje) + floor((Crecimiento Clase + Crecimiento Personaje) × (Nivel - 1) / 100)
- Esto genera las estadísticas exactas de reclutamiento de cada unidad coincidiendo al 100% con guías oficiales como Serenes Forest.

## Sección 4 del catálogo: Habilidades / Skills
###
- Lee Skill.xml.
- Extrae el ID, nombre limpio e icono (IconName).
- stat_boosts: Bonificaciones pasivas a los atributos (Enhance.*), incluyendo bono de movimiento (Enhance.Move).
- combat_mods: Bonificaciones directas al combate activo: daño (Power), golpe (Hit), crítico (Critical), evasión (Avoid), y esquiva de crítico (Secure).

## Sección 5 del catálogo: Emblemas / God
###
- Lee God.xml mediante una estrategia de doble pasada.
### Pasada 1 (Tablas de crecimiento):
- Agrupa por Ggid los niveles del 1 al 10 para recopilar las armas del emblema (EngageItems), habilidades activadas por engage (EngageSkills) y habilidades de sincronización (SynchroSkills).
### Pasada 2 (Emblemas):
- Registra el emblema maestro (Marth, Sigurd, Roy, etc.), filtrando versiones dummy o de cinemáticas (GID_M0..., 相手, 敵), e indexa las armas y habilidades que desbloquea a lo largo de su tabla de progresión.

## Exportación y persistencia
- Agrupa las cinco colecciones en el diccionario catalogo_final:
"armas", "clases", "personajes", "habilidades", "emblemas".
- Escribe el archivo en disco como catalogo_engage.json (con codificación UTF-8 e indentación legible de 2 espacios).
