# Oscuridad (capítulos 6, 13 y 20): reglas y diseño

Complementa `plan_oscuridad.md` (la filosofía: la herramienta lo sabe todo, pero solo
propone lo que el juego permite con lo que el jugador ve).

## Reglas (verificadas por el jugador o del datamine)

- **Mapas con oscuridad**: Chapter.xml Flag bit 2 (M006, M013, M020: Flag 63).
- **Casillas iluminadas** = rombos alrededor de:
  - cada aliado: `Sight` de su clase (Job.xml): 3, Thief 5;
  - cada antorcha del mapa encendida: radio 3 (Terrain.xml `TID_篝火` Sight 3; `TID_篝火消`
    apagada = 0; `TID_篝火常` permanente). Es obstáculo. Las casas NO dan luz;
  - antorcha de mano (`IID_たいまつ`, 3 usos) y bastón Illume (`IID_トーチ`, 5 usos): radio 7,
    que se encoge 1 por turno.
- **Un aliado no puede entrar en una casilla oscura**: es un muro, no un coste. La luz de otro
  aliado sí cuenta (así se avanza: uno ilumina y los demás entran).
- **Antorcha de mano**: alumbra alrededor de quien la usa y le sigue; el radio baja 1 por turno,
  así que una casilla iluminada puede volver a quedar a oscuras al turno siguiente.
- **Antorchas del mapa**: objeto de tipo "antorcha" en la capa de objetos "estructuras" de Tiled,
  obstáculo, con estado encendida/apagada. Encender o apagar gasta la acción de quien lo hace
  (enemigos: el jugador lo refleja en el modal de la antorcha; aliados: modal o recomendación).
- **Tiled**: el mapa entero va oscurecido; la luz de aliados y antorchas lo va descubriendo.
- **Un enemigo en casilla oscura no se ve y no se puede atacar**, aunque se descubra al moverse:
  hace falta que ya esté iluminado (por un aliado o una antorcha) al elegir la acción.
- **Los enemigos se mueven a oscuras sin que se vea**: solo se sabe dónde están cuando acaban en
  una casilla iluminada. Los voladores (y otros) van a apagar las antorchas del mapa al empezar
  su fase (IA `AI_MI_Torch`); empiezan todas encendidas.
- **Refuerzos**: el juego no los enseña (no hay cámara). Si existen, no se puede saber.
- **Efectos de área sobre ocultos**: el fuego de Dark Inferno quema al empezar la fase enemiga a
  un enemigo que sigue oculto (verificado en el Cap. 13). Dark Inferno se puede lanzar sin
  apuntar a un enemigo. Sin verificar: si el golpe directo de Override, Blazing Lion o los
  alientos de Tiki alcanza a un oculto (probar en el Cap. 20). La herramienta, de momento,
  los cuenta como alcanzados.

## Capítulo 13 en el datamine (dificultad Extremo, coordenadas de la herramienta)

El mapa de Tiled mide 30 x 23; la herramienta convierte las del datamine con x = X − 1,
y = 23 − Y (lo hace el cargador con el alto del mapa).

- 42 enemigos iniciales; jefes Totchie (28,20, Brave Axe) y Tetchie (27,21, Tomahawk). Los
  Ruffian con IA de saqueo (`AI_MI_Village`) cerca de los jefes están en (21,21), (23,22) y
  (29,22); la casa imposible de salvar es la de (21,17) (`奥民家破壊`, Lua 22,6).
- Aliados verdes: empiezan en (5,2) Merrin, (5,3) Timerra, (6,3) Panette; la conversación del
  turno 1 los mueve a (10,9) Merrin, (9,10) Timerra, (11,10) Panette (Lua `UnitMovePos`) y
  luego `UnitJoin`.

## Modelo

Por enemigo: `visible` (calculado), `ultima_pos_conocida`, `turno_visto`. La ficha se queda en su
última posición conocida; el jugador solo mueve a los que ve.

- **Estado real** = lo que el jugador ha introducido + el preset del datamine en el turno 1.
- **Visible** = en casilla iluminada ahora (se recalcula con cada movimiento / antorcha).
- **Acciones válidas** = movimiento solo por casillas iluminadas; atacar solo a visibles.
- **Amenaza de un oculto** = zona desde su última posición conocida, marcada como incierta y
  ampliada con su Mov por cada turno sin verlo.

## Fases propuestas

1. **Visibilidad** (hecha, 2026-10-03: `visibilidad.py`, capa `oscuridad`, objetos `antorcha`,
   `/api/visibilidad`, `/api/mapa/objeto/antorcha`, `/api/unidad/antorcha_mano`): capa "Oscuridad" de Tiled (qué casillas son oscuras) + objetos
   "antorcha" (encendida / apagada, se cambian en su modal) + visión de aliados y antorchas de
   mano → conjunto de casillas iluminadas; la UI oscurece el resto y marca a los ocultos.
2. **Acciones válidas**: movimiento bloqueado por la oscuridad; el análisis no ataca a ocultos;
   peligro incierto de los ocultos; preset del Cap. 13 (enemigos iniciales, casillas de los
   aliados tras la conversación: `UnitMovePos` del guion, ver arriba).
3. **Planificador "revelar → atacar"**: mover un explorador (o encender una antorcha, usar una
   antorcha de mano) para iluminar a un enemigo, y después atacarlo con otros.
