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

## Stats de aliados al unirse, dificultad y reclutar (2026-09-20)

- **Stats al unirse** (`join_stats` del catálogo, aliados/verdes de un dispos): base de
  clase + base personal (Base + OffsetN de Person.xml) + round-half-up(crecimiento
  PERSONAL × niveles / 100), contando el nivel interno de la clase. Los crecimientos de
  clase no intervienen. Verificado contra las tablas oficiales: exacto para todos los
  personajes de clase base (Jade 33/14/4/14/5/18/6/5/8, Amber, Louis, Ivy…), ±1 en
  algunos promocionados. Antes se truncaba (int) y se sumaba el crecimiento de clase
  (Jade salía 35/15/3/14/5/21).
- **Dificultad**: la campaña del usuario es Extremo → valor por defecto en tablero,
  selector y despliegue. Cada ficha recuerda su `dificultad` (se exporta); al importar
  una partida sin `dificultad` se infiere de las fichas, y las definiciones de refuerzos
  por evento aún no disparadas que se guardaron con otra dificultad se regeneran del
  datamine. Origen del fallo visto en el Cap. 9: un reinicio del servidor devolvía
  `tablero.dificultad` a "Hard" y los fuertes de Kagetsu/Zelkov salían con la fila
  Normal/Hard (Iron Sword/Kard) en vez de la de Extremo (Flag 4: Steel Sword +
  Armorslayer, Kard + Stiletto, con offsets de Lunatic).
- **Mover + hablar/curar = una acción**: `POST /api/unidad/hablar` acepta `x, y` (mueve
  al hablante validando alcance y recluta en la misma llamada; si falla, deshace);
  `POST /api/mover` acepta `accion_pendiente: true` para no marcar "ha actuado" cuando
  el movimiento es el primer paso de una acción (la UI lo usa al curar).
- **Jefe**: bit 16 del `Flag` del dispos (Ivy M008/M009, Hortensia M007, Hyacinth y Morion
  M010…), además de las piedras resurrectoras o "(Boss)" en el nombre. Editar la ficha en
  el modal (p.ej. quitarle las piedras) conserva `es_jefe`.

## Capítulo 10: cañón mágico, cofres y refuerzos por evento (2026-09-22)

- **Armas de mapa genéricas**: el objeto de Tiled declara `arma_permitida` ("Arco" en una
  ballesta, "Tomo" en el cañón mágico) y `distancia_min/max`. `catalogo_loader`:
  `tipo_arma_de_objeto`, `puede_usar_arma_de_mapa` (maestría de clase + llevar un arma de
  ese tipo) y `arma_de_mapa_desde` (arma propia + Hit +20, crítico 0, 1 golpe, sin
  contraataque, sin pasivas externas). El cañón mágico usa el tomo de la unidad, así que
  ataca a la RES. Datamine: SID_魔砲台 == SID_弓砲台 (命中値+20, 必殺率=0, 手番回数=1,
  相手の手番回数=0, RangeI 3 RangeO 7); el alcance real lo manda el objeto del mapa.
- **Cofres** (`tipo: cofre` en el tile): objeto de mapa que BLOQUEA su casilla, abierto o
  cerrado (es mobiliario). `POST /api/mapa/objeto/abrir_cofre {id, unidad}` gasta la acción
  de una unidad adyacente y lo marca abierto; el contenido lo anota el jugador. No genera
  recomendaciones.
- **Refuerzos por evento con varias condiciones**: cada entrada de `REFUERZOS_POR_EVENTO`
  lleva `disparos`, una lista de condiciones de las que basta UNA (la primera que ocurra):
  `casilla` (pid + casilla_datamine), `combate` (pid), `muerte` (pid), `turno` (nº) y
  `objeto` (objeto_tipo del mapa, p.ej. la puerta). M010:
  - `Enemy_Reinforcement1/2` (2 arqueros en (1,18) y (15,18), los extremos de la fila de
    Hortensia): al entrar en combate con Hortensia (`condition_オルテンシア行動変化`:
    g_flag_battle_holtencia) **o** al empezar el turno 6 (como lo anotan las guías).
  - `Enemy_Reinforcement3/4` (jinete con espada en (3,4) y con hacha en (13,4), las
    escaleras junto a Hyacinth): cuando cae Morion (`condition_増援`) **o** al derribar la
    puerta — Morion está pasada la puerta, por eso las guías lo describen así.
  - El grupo `Thief` llega en el turno 2 salvo en Extremo (Flag 3 de sus filas =
    Normal+Difícil, como `if not モードはルナティック()`), por CALENDARIO_REFUERZOS.
- **Apertura de M010** (`配置調整` del .lua): Hortensia baja al vestíbulo de los pozos de
  Emblema (8,18) y Hyacinth sube al fondo del trono (8,0). En RECOLOCACIONES_APERTURA.
- **Casilla de aparición ocupada**: el refuerzo ya no espera un turno entero; se coloca en
  la casilla transitable libre más cercana (radio 3) y solo se pospone si no hay ninguna.
- **Usos de las armas de mapa**: los enemigos también gastan la ballesta / el cañón, así que
  el jugador anota los que quedan: clic en su casilla (o **clic derecho**, que funciona
  aunque haya una unidad encima) → modal con "Usos restantes". `POST /api/mapa/objeto/usos
  {id, usos}`. Con 0 el arma queda **agotada**: sigue dibujada en el mapa (en gris) pero no
  se ofrece en las recomendaciones ni se puede disparar; con más de 0 vuelve a estar
  disponible. Si el tile no declaró `usos`, el número que escriba el jugador pasa a ser el
  máximo.

- **Emblema Oscuro del jefe** (2026-09-22): el `Gid` del dispos ya trae el Emblema
  (`GID_M010_敵リン` en Hyacinth, `GID_M008_敵リーフ` en Ivy, `GID_M010_敵ベレト` en la
  Hortensia del Cap. 10). Sus **armas de Emblema pasan al inventario real del jefe**, con
  la primera equipada, porque un Emblema Oscuro no se fusiona y las lleva toda la batalla.
  El único que el guion entrega por evento (y no aparece en el Gid) es el de Lucina para
  Hortensia en M007: está en `EMBLEMA_POR_EVENTO`, no como caso especial en el código.
- **Las armas "(Evento)" no son las genéricas**: `IID_リン_キラーボウ_M010` es Mt 9 / crit 10
  y la genérica `IID_キラーボウ` es Mt 7 / crit 30; la Mani Katti del Cap. 10 tiene crit 5 y
  la normal 20. Resolverlas por nombre daba el arma equivocada, así que
  `parsear_arma_string` respeta el **IID** del ítem cuando nombra la misma arma, y el
  nombre visible se queda sin la etiqueta "(Evento)"/"(Prólogo)" del compilador.
- **Bugs del Cap. 10 (2026-09-22)**:
  - `/api/estado` daba **500** en cualquier mapa con refuerzos por evento de tipo
    combate / muerte / objeto: `snapshot()` hacía `list(e["casilla"])` y esos eventos no
    tienen casilla. Arreglado (y los `disparos` también se serializan). El efecto colateral
    eran los 404 de `/api/terreno`: sin estado, la UI se quedaba con el mapa anterior y
    pedía casillas fuera de los 17×30 del Cap. 10.
  - **Armas de Emblema duplicadas al guardar desde el modal**: el modal reconstruye el
    inventario desde sus 5 ranuras de texto, sin marca de Emblema y (antes) sin el IID, así
    que la inyección del Emblema no reconocía el arma y la añadía otra vez. Ahora la ranura
    guarda el `IID` en `dataset.iid` y lo reenvía (se borra al reescribir el nombre), y la
    inyección, cuando el Emblema es Oscuro, deduplica también por arma base. Sin el IID ya
    no duplica, pero el arma pasa a ser la genérica del mismo nombre.
- **Arqueros del Cap. 10 (verificado en juego, 2026-09-23)**: `Enemy_Reinforcement1/2` NO
  llegan por turno. Se jugó hasta el turno 6 sin combatir con Hortensia y no aparecieron,
  así que su único disparador es el combate con ella (`g_flag_battle_holtencia`). Las guías
  lo cuentan como "turno 6" porque es cuando se suele llegar hasta ella. Los jinetes de las
  escaleras (`Enemy_Reinforcement3/4`) sí conservan sus dos condiciones (Morion cae **o**
  se derriba la puerta).
- **Disparo por acción de una unidad (`accion`)**, 2026-09-23: algunos eventos del guion
  dependen de que una unidad ENEMIGA haga algo que la herramienta no puede observar
  porque pasa en la fase enemiga (atacar, usar un bastón). Los arqueros del Cap. 10 son
  el primer caso: no llegan por turno ni solo por combate, sino en cuanto **Hortensia
  actúa** — ataca, congela con Freeze o recibe un ataque.
  Cómo funciona:
  - En `REFUERZOS_POR_EVENTO`, `{"tipo": "accion", "pid": ...}` junto a los demás disparos
    (basta el primero que ocurra; el de `combate` sigue estando para cuando la ataques tú).
  - `EstadoTablero.acciones_pendientes_de_registrar()` lista las unidades vivas con un
    evento así sin disparar, y `como_dict` publica `evento_por_accion` por ficha.
  - En el modal de esa unidad aparece el botón **"Ha actuado → refuerzos"**
    (`POST /api/unidad/registrar_accion`), y al pulsar "Turno Enemigo" la respuesta trae
    `acciones_pendientes` para que la UI lo recuerde con un aviso.
  - Los refuerzos se colocan como siempre: su casilla del guion, o la libre más cercana
    (radio 3) si está ocupada.
  La lista va en el **estado del tablero** (`eventos_por_accion`), no como un campo por
  ficha. El primer intento se lo preguntaba a la ficha, y para eso le colgó una referencia
  al tablero: el `deepcopy` de `guardar_snapshot` pasó a copiar el tablero entero con su
  historial en cada snapshot y la suite se colgaba. La ficha no sabe nada de esto.
  El botón es de **acción única**: una vez disparado sigue visible pero en gris
  ("Refuerzos ya llamados"), para que se vea que está hecho.
- **Los disparadores viven en la partida, no en el código**: `programar_refuerzos_por_evento`
  solo se llama al seleccionar capítulo y al cargar el preset, así que una partida empezada
  se queda con las condiciones que tuviera ese día. Al corregir los arqueros del Cap. 10 el
  botón no aparecía en la sesión en curso por eso. `GET /api/estado` llama ahora a
  `resincronizar_refuerzos_por_evento`: actualiza los `disparos` y la descripción de los
  grupos que ya estaban, **conservando `disparado`** y sin desplegar ni mover nada. Los
  grupos que no estaban en la partida no se añaden a mitad de mapa.

