# Cargador_dispos.py
## 
- NO lee el JSON del mapa de Tiled
- Actúa como puente entre los datos de Nintendo y la herramienta
- Lee los XML originales y los archivos de la carpeta “dispos/”

## Configuración de rutas y librerías (Líneas 1 a 20)
- Usa xml.etree.ElementTree, la librería estándar de Python para parsear árboles XML sin instalar dependencias externas.
- Usa rutas absolutas (BASE_DIR, DATAMINE_DIR, DISPOS_DIR) para que pueda funcionar desde una terminal en otra carpeta
- Apunta a una carpeta llamada fe_assets_gamedata, que es la estructura de carpetas estándar que se obtiene al descompilar la ROM de Engage.

## Inicialización y carga de Person.xml (Líneas 22 a 83)
- Las líneas 23 a 28 intentan abrir el archivo “catálogo_engage.json”, un diccionario auxiliar creado en el proyecto que mappea IDs internos a texto legible
- _cargar_persons_xml() (Líneas 32-83): Lee Person.xml una sola vez al arrancar. Este archivo contiene la plantilla base de todos los personajes del juego.
- Las líneas 44 a 77 determinan la dificultad del juego (L, H, N) y para cada personaje, extrae: 
- Auto_grow_offset, niveles extra ficticios que se aplican a crecimientos automáticosdel enemigo para inflar sus stats
- Offset_l/h/n, modificadores fijos de cada dificultad, donde las estadísticas son abreviaturas inglesas (Tech, Phys, Quick)
- Valida con .lstrip("-").isdigit() para evitar que números negativos rompan el parseo a int.

## Los "Resolvers" de texto (Líneas 85 a 124)
- resolver_nombre_item (85 a 99) recibe un identificador de arma, devuelve nombre en español y sus usos (si está en el catálogo). Si no está, limpia prefijos del juego 
- resolver_nombre_personaje (101-124). Los enemigos genéricos no tienen nombre. Las líneas 103 a 112 tienen un diccionario con los nombres clave del Capítulo 7. En las líneas 122 a 124, si el enemigo no es un jefe con nombre, se filtran kanjis y se asignan identificadores únicos, tal como “Tipo-Unidad (X, Y)”

## Núcleo. cargar_capítulo (126 a 237)
- Aquí se procesa el archivo de despliegue (dispos/{dispos_id}.xml), donde cada etiqueta <Param> representa una entidad sobre el tablero.
- El filtro de dificultad por Máscara de Bits (Líneas 141-164):
   - Ingeniería pura del motor de juego: En Fire Emblem, algunos enemigos solo aparecen en ciertas dificultades. El juego usa una máscara de bits binaria en el atributo Flag:
   - 1 en binario es 001 (Normal)
   - 2 en binario es 010 (Difícil).
   - 4 en binario es 100 (Extremo).
   - Si un enemigo tiene Flag="6" (110 en binario), significa que aparece en Difícil ($2$) y Extremo ($4$), pero no en Normal.
   - Con la operación a nivel de bits (flag_val & mask) == 0, descartas de un plumazo a los enemigos que no tocan en la dificultad elegida.
- La inversión del eje Y (Líneas 166-177):
    - El motor de Engage indexa desde 1 y sitúa el origen (1, 1) en la esquina inferior izquierda (como en matemáticas).
    - Tiled, HTML5 Canvas y los navegadores indexan desde 0 y sitúan el origen (0, 0) en la esquina superior izquierda (el eje Y crece hacia abajo).
    - La fórmula mapa_alto_jueg - int(y_str) invierte verticalmente la posición para que las unidades no aparezcan del revés respecto a los tiles del mapa.
- C. Bandos y Tipos de Unidad (Líneas 179-183): Lee el campo "Force"
    - 0: Unidades del jugador (azul).
    - 1: Enemigos (rojo).
    - 2: Unidades neutrales / aliados temporales (verde).
- Extracción de inventario y estados (Líneas 207-228):
    - Itera de 1 a 6 (Item1.Iid a Item6.Iid) para extraer las armas.
    - Lee Item{i}.Drop: detecta si el objeto caerá como recompensa al derrotar al enemigo (el clásico icono verde de drop en el juego).
    - HpStockCount: Extrae las piedras de resurrección / barras de vida múltiples de los jefes (Hortensia en este mapa).
    - AI_MoveName y AI_BattleRate: Extrae la IA interna que dicta si la unidad carga directamente hacia ti o si se queda inmóvil esperando que entres en su rango.
- Empaquetado final (Líneas 230-252):
    - Devuelve una lista de diccionarios limpios con coordenadas cartesianas unificadas, inventarios legibles y modificadores de stats listos para que la UI los pinte o el motor de combate calcule los encuentros.
## Refuerzos por evento del guion (2026-09-19)

Además de `CALENDARIO_REFUERZOS` (grupos `Enemy_Reinforcement*` por turno, de
`EventEntryTurn` en el .lua), `REFUERZOS_POR_EVENTO` recoge los grupos que el guion
lanza con `Dispos(grupo)` dentro de una función condicionada por `判定_<evento>`
(una unidad `pid` está en la casilla (x, z) del datamine). Esos grupos se retiran del
despliegue inicial y `EstadoTablero.comprobar_refuerzos_por_evento` los coloca al
mover la unidad a la casilla (o al avanzar turno si ya está allí). Se disparan una
sola vez; la Cronogema y exportar/importar conservan su estado.

- M009: `Enemy_Kagetsu_Fort` (2 Sword Fighters) cuando Kagetsu llega a (14,1) y
  `Enemy_Zelkova_Fort` (2 Thieves) cuando Zelkov llega a (14,15): los fuertes de
  curación norte y sur (`砦到着_カゲツ` / `砦到着_ゼルコバ`). No dependen del turno.

## Inventario por defecto y unión por conversación (2026-09-19)

- Si la fila del dispos no lista objetos (`Item1..6` vacíos), el juego usa `Items` de
  Person.xml: el cargador hace lo mismo (`persons[pid]["items"]`). Antes caía en
  "Espada de Hierro" (Jade en M009 lleva Steel Axe + Poción).
- `UNION_POR_CONVERSACION`: verdes (Force=2) que no se unen al empezar, sino al hablar
  con ellos una unidad autorizada desde una casilla adyacente (`<pid>加入_<hablante>()` →
  `UnitJoin` en el .lua). Salen con `union_pendiente=True` y `habla_con=[pids]`.
  Hasta reclutarlos: no son `controlable` (`obtener_aliados` los excluye, no reciben
  recomendaciones ni dan apoyos/auras), se recolocan libremente sin gastar acción (los
  mueve la CPU) y editar su ficha en el modal conserva el estado. Reclutar:
  `EstadoTablero.hablar` / `POST /api/unidad/hablar` (gasta la acción del hablante);
  el análisis lo recomienda como `tipo_analisis = "conversacion"` con prioridad máxima.
- M009: Jade ↔ Alear o Diamant (`ジェーデ加入_リュール` / `ジェーデ加入_ディアマンド`).
