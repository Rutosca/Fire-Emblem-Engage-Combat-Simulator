# Capítulo 11 — «Retreat» / イルシオン国境 (M011)

Volcado del datamine para montar el capítulo en la herramienta. **Todo lo que hay en las
tablas está LEÍDO** de `fe_assets_gamedata/dispos/M011.xml`, `Person.xml`, `Job.xml`,
`Item.xml`, `Skill.xml`, `fe_assets_scripts/M011.lua` y `il2cpp/dump.cs`. Lo que es
deducción mía va marcado con **(SUPOSICIÓN)**. Lo que no está en los datos se dice
explícitamente en vez de rellenarlo.

Traducciones tomadas de `json/catalogo_engage.json` (clases, armas, habilidades, emblemas)
y de `fe_assets_message/us/usen/csv/person.csv` para los nombres propios.

---

## 1. Ficha del capítulo

De `mapas/M011.json` (generado por `generar_mapas.py` desde `Chapter.xml`):

| campo | valor |
|---|---|
| `cid` | `CID_M011` |
| `dispos_id` | `M011` |
| `terrain_id` | `MapTerrain_M011` |
| `field_id` | `Fld_M011` |
| `script_bmap` | `M011.lua` |
| `script_encount` | `M011_Encount.lua` (refriega / 遭遇戦, usa `dispos/M011E.xml`) |
| nivel recomendado | 13 |
| nación | `NID_イルシオン` (Elusia) |
| BGM | `BGM_Field_P05` en ambas fases |
| `flag` | 177 = `Sally`(1) + `Hub`(16) + `Gmap`(32) + `Serious`(128) → **hay pantalla de preparativos** |
| siguiente | `CID_M012` |

**Condición de victoria** (`M011.lua > Startup`):

```lua
WinRuleSetEnemyNumberLessThanOrEqualTo(-1)
WinRuleSetMID( "MID_RULE_M011_WIN" )
```

`MID_RULE_M011_WIN` = `"escapes."` en inglés (`GameData.csv`), `"を離脱させる"` en japonés →
**"Que <Alear> escape"**. El `-1` del `WinRuleSetEnemyNumberLessThanOrEqualTo` hace la regla
de exterminio **inalcanzable a propósito**: el mapa solo se gana por el evento de huida.

> ⚠️ **Aviso para la herramienta**: `cargador_dispos.condicion_victoria("M011")` devuelve
> `"exterminio"` porque el regex solo busca la llamada, no su argumento. El test
> `tests/test_analisis_tactico.py::test_condicion_de_victoria_del_guion` lo da por bueno.
> Para el Cap. 11 eso es **falso**: hay que tratarlo como "escapar" (tercera categoría, `""`).
> No he tocado ni el módulo ni el test.

No existe `MID_RULE_M011_LOSE`: la derrota es la genérica (`MID_RULE_COMMON_LOSE`,
*"is defeated."*) → cae Alear.

---

## 2. Tamaño del mapa y coordenadas

`M011.lua` declara:

```lua
g_map_width   = 18
g_map_height  = 32
```

y los bucles del guion recorren `x = 1 .. g_map_width-1` y `z = 1 .. g_map_height-1`.
→ **casillas útiles: X 1..17, Z 1..31** en coordenadas del datamine (1-indexed, Y=1 abajo).
Coordenadas máximas que aparecen en el dispos: `AppearX` 17, `AppearY` 31, `DisposY` 30.

**(SUPOSICIÓN)** El mapa de Tiled debería ser **17 de ancho × 31 de alto**, y la llamada
al cargador `cargar_capitulo("M011", dif, mapa_ancho=17, mapa_alto=31)`. Es el mismo patrón
que el Cap. 10 (`CAP_10_Tiled.json` = 17×30), pero aquí el `g_map_height` es lo único que lo
respalda: **no hay fichero de rejilla en el datamine** que lo confirme.

Todas las tablas de abajo dan las dos coordenadas:
- **dm(x,y)** = tal cual está en el XML (1-indexed, Y=1 fila inferior).
- **tool(x,y)** = ya convertida por `cargador_dispos` con `mapa_alto=31`
  (`x = DisposX-1`, `y = 31 - DisposY`).

`Direction` (enum `DisposData.Directions` de `dump.cs`):
1 Arriba · 2 ArribaDcha · 3 Dcha · 4 AbajoDcha · 5 Abajo · 6 AbajoIzq · 7 Izq · 8 ArribaIzq.

---

## 3. Vocabulario del dispos: `Flag` y `AI_Flag`

Esto **no era conocido** en `notas/notas_cargador_dispos.md` más allá de los 3 bits de
dificultad y el bit 16. Sale del dump de il2cpp (`il2cpp/dump.cs`, `enum DisposData.Flags`):

| bit | nombre | significado |
|---|---|---|
| 1 | `Normal` | aparece en Normal |
| 2 | `Hard` | aparece en Difícil |
| 4 | `Lunatic` | aparece en Extremo |
| 8 | `Create` | la fila la crea el guion (`Dispos(grupo)`), no el arranque del mapa |
| 16 | `Leader` | **jefe del mapa** (lo que el cargador ya usaba) |
| 32 | `NotMove` | la unidad no se mueve |
| 64 | `Edge` | — |
| 128 | `Pos` | slot de despliegue con posición fija |
| 256 | `Must` | despliegue obligatorio |
| 512 | `Fix` | no se puede quitar del despliegue |
| 1024 | `Guest` | invitado |

(`MaskSortie = 896 = 128+256+512`, `MaskDifficulty = 7`.)

Y `enum DisposData.AIFlags`: 1 `NotActivateByAttacked` · 2 `Dummy` · 4 `ZeroAttack` ·
8 `Heal` · 16 `Break` · 32 `Chain` · 64 `EquipShortAfterLongRange` · 128 `MoveBreak` ·
256 `EngageAttackOnce`.

Los tres valores de `AI_Flag` que usa M011:

| valor | descomposición |
|---|---|
| 312 | `Heal` + `Break` + `Chain` + `EngageAttackOnce` (todos los corruptos genéricos) |
| 120 | `Heal` + `Break` + `Chain` + **`EquipShortAfterLongRange`** (los dos Corrupted Wyrm: tienen aliento 1-3 y Fireball a 4) |
| 56 | `Heal` + `Break` + `Chain` (Veyle y los cuatro Sabuesos) |

`AI_BattleRate`: `攻撃` = agresiva · `慎重` = cautelosa (Veyle, los Sabuesos y los dos
guardianes del punto de huida).

**Grupos del dispos M011** (58 filas, hoja `配置`):

| grupo | cuándo entra | qué es |
|---|---|---|
| `Player` | al empezar | 10 slots de despliegue |
| `Enemy` | al cargar el mapa | enemigos iniciales repartidos por la ruta |
| `Enemy_OP1` | `MapOpening`, `Dispos("Enemy_OP1")` | la columna que te persigue por el norte (incluye los 2 wyrms) |
| `Enemy_OP2` | `MapOpening`, `Dispos("Enemy_OP2")` | Veyle |
| `Enemy_4dogs` | evento `四狗とアイビー登場` | los cuatro Sabuesos |
| `Enemy_EV1` | mismo evento | 4 corruptos que te cortan la salida por el sur |
| `Ally_Add0` / `Ally_Add1` | mismo evento | Ivy + Kagetsu / Zelkov |

**No hay ningún grupo `Enemy_Reinforcement*` y no hay ni un solo `EventEntryTurn` de
refuerzos**: en este capítulo **nada aparece por número de turno** (ver §6).

---

## 4. Unidades aliadas desplegables

Grupo `Player`, 10 filas. El dispos **no** lleva `Jid`, `Level` ni objetos en estos slots:
son huecos de la pantalla de preparativos.

| # | PID | Flag | dm(x,y) | tool(x,y) | notas |
|---|---|---|---|---|---|
| 1 | `PID_リュール` (Alear) | 775 = NHL+`Must`+`Fix` | (11,19) | (10,12) | obligatorio y fijo |
| 2 | — | 135 = NHL+`Pos` | (10,20) | (9,11) | libre |
| 3 | — | 135 | (12,20) | (11,11) | libre |
| 4 | — | 135 | (13,20) | (12,11) | libre |
| 5 | — | 135 | (9,21) | (8,10) | libre |
| 6 | — | 135 | (10,21) | (9,10) | libre |
| 7 | — | 135 | (11,21) | (10,10) | libre |
| 8 | — | 135 | (13,21) | (12,10) | libre |
| 9 | — | 135 | (10,22) | (9,9) | libre |
| 10 | — | 135 | (12,22) | (11,9) | libre |

**10 unidades desplegables** (Alear + 9), idéntico en las tres dificultades.

La cinemática de apertura (`自軍入場演出`) mete a cada slot desde la fila 30 y **deja a
Alear en su casilla del dispos** (`UnitSetPos(9,30)` → `UnitMovePos(9,27)` → `UnitMovePos(11,19)`).
→ **No hace falta añadir nada a `RECOLOCACIONES_APERTURA`**: la posición del dispos ya es la
final.

> ⚠️ **Emblemas del jugador**: ninguna fila `Player` tiene atributo `Gid`. Es coherente con
> el guion (Alear ha perdido los anillos) y con que el propio mapa le entregue **Lucina** a
> mitad de capítulo. Ojo: `cargador_dispos` pone `emblema_nombre = "Marth"` por defecto
> cuando el PID es Alear y no hay `Gid` (líneas 503-504), lo que en este capítulo es **falso**.

---

## 5. Enemigos iniciales

### 5.1 `Enemy_OP1` — la columna del norte (desplegada en la cinemática)

Todos con `Sid = SID_必殺０_オフェンス時` (*Crit０ Offense*, `必殺率 = 0`: **no pueden hacer
crítico**, hasta que el evento de los Sabuesos se lo quita — ver §7).

| PID (sin `PID_M011_`) | Clase | Nv | dm(x,y) | tool(x,y) | Aparece en | Arma(s) | Dif. | IA |
|---|---|---|---|---|---|---|---|---|
| `異形兵_ソードペガサス` | Sword Flier | 13 | (3,29) | (2,2) | (3,31) | Armorslayer | NHL | `TurnAttackRange 3,100` |
| `異形兵_アクスナイト` | Axe Cavalier | 14 | (7,29) | (6,2) | (7,31) | Steel Axe | NHL | `Everytime` |
| `異形兵_ソードファイター` | Sword Fighter | 14 | (8,29) | (7,2) | (8,31) | Steel Sword | NHL | `TurnAttackRange 3,100` |
| `異形兵_モンク` | Martial Monk | 12 | (9,28) | (8,3) | (9,31) | Steel-Hand Art + **Fracture** + Physic | **solo N** | `Everytime` |
| `異形兵_モンク` | Martial Monk | 12 | (9,28) | (8,3) | (9,31) | Steel-Hand Art + **Freeze** + Physic | **H y L** | `Everytime` |
| `異形兵_アクスファイター` | Axe Fighter | 13 | (10,29) | (9,2) | (10,31) | Iron Greataxe | NHL | `TurnAttackRange 3,100` |
| `異形兵_アクスナイト` | Axe Cavalier | 14 | (11,29) | (10,2) | (11,31) | Hand Axe | NHL | `Everytime` |
| `異形兵_ソードペガサス` | Sword Flier | 13 | (15,29) | (14,2) | (15,31) | Steel Sword | NHL | `TurnAttackRange 3,100` |
| **`異形竜`** | **Corrupted Wyrm** | 23 | (11,26) | (10,5) | (11,29) | Fire Breath + Fireball | NHL | `FlagTrue FLAG_四狗とアイビー登場_済` |
| **`異形竜`** | **Corrupted Wyrm** | 23 | (8,25) | (7,6) | (8,28) | Fire Breath + Fireball | NHL | `FlagTrue FLAG_四狗とアイビー登場_済` |

**9 unidades en cualquier dificultad** (el monje es la misma unidad con inventario distinto).
La diferencia real por dificultad aquí es solo **Fracture (Normal) vs Freeze (Difícil/Extremo)**.

### 5.2 `Enemy_OP2` — Veyle (jefe)

| PID | Clase | Nv | dm(x,y) | tool(x,y) | Flag | Armas | HpStock | IA |
|---|---|---|---|---|---|---|---|---|
| `PID_M011_ヴェイル` (Veyle) | Fell Child (`JID_邪竜ノ娘_敵`) | 25 | (9,30) | (8,1) | 55 = NHL + **`Leader`** + `NotMove` | Obscurité, Misericorde | **3** | `Everytime`, rate `慎重` |

- Es **el único** con el bit 16: `cargador_dispos.pids_jefe("M011")` → `{"PID_M011_ヴェイル"}`.
- `NotMove`: **no se mueve de (9,30)**. Está literalmente en la fila más al norte, detrás de
  todo, y solo hay diálogo con ella (`MID_BT7`). No hay que matarla.
- Habilidades (`Person.xml`): `SID_邪竜の救済` (*Fell Protection*, aura Timing 20),
  `SID_ダメージ無効化` (*DamageNullify*), `SID_死亡回避` (*Avo*: si el daño la mataría,
  `ダメージ = 0` y el ataque cuenta como fallo), `SID_オヴスキュリテ装備可能`,
  `SID_ミセリコルデ装備可能`. En Difícil añade `SID_特効耐性` (*Stalwart*) y en Extremo
  `SID_熟練者＋` (*Veteran+*).
- Sin `Sid` en la fila del dispos → **sí puede hacer críticos desde el turno 1**.

### 5.3 `Enemy` — el recorrido (los que ya están al cargar el mapa)

Todos con `Sid = SID_必殺０_オフェンス時`. Ordenados de norte a sur (según el camino que
recorres bajando).

| PID (sin `PID_M011_`) | Clase | Nv | dm(x,y) | tool(x,y) | Flag → dif. | Arma(s) | IA (`AI_ActionName` / val) |
|---|---|---|---|---|---|---|---|
| `異形兵_ソードペガサス` | Sword Flier | 13 | (3,18) | (2,13) | 7 → NHL | Steel Sword | `TurnAttackRange 2,100` |
| `異形兵_アクスファイター` | Axe Fighter | 13 | (11,16) | (10,15) | 7 → NHL | Steel Axe | `Everytime` |
| `異形兵_アーチャー` | Archer | 12 | (13,12) | (12,19) | 7 → NHL | Steel Bow | `TurnAttackRange 2,100` |
| `異形兵_ランスファイター` | Lance Fighter | 14 | (7,12) | (6,19) | 7 → NHL | Steel Lance | `TurnAttackRange 3,100` |
| `異形兵_ランスファイター` | Lance Fighter | 14 | (6,10) | (5,21) | **4 → solo L** | Steel Lance | `TurnAttackRange 3,100` |
| `異形兵_アクスファイター_トマホーク` | Axe Fighter | 13 | (3,10) | (2,21) | 7 → NHL | **Tomahawk (DROP)** | `Null` (nunca se activa) |
| `異形兵_マージ` | Mage | 13 | (9,8) | (8,23) | 7 → NHL | Thunder | `TurnAttackRange 5,100` |
| `異形兵_ソードファイター` | Sword Fighter | 14 | (9,7) | (8,24) | **4 → solo L** | Steel Sword | `TurnAttackRange 5,100` |
| `異形兵_ソードファイター` | Sword Fighter | 14 | (10,7) | (9,24) | 7 → NHL | Steel Sword | `TurnAttackRange 5,100` |
| `異形兵_ランスファイター` | Lance Fighter | 14 | (5,7) | (4,24) | **6 → H y L** | Iron Greatlance | `TurnAttackRange 6,100` |
| `異形兵_シーフ` | Thief | 13 | (2,5) | (1,26) | 7 → NHL | Steel Dagger | `TurnAttackRange 7,100` |
| `異形兵_マージ` | Mage | 13 | (3,2) | (2,29) | **4 → solo L** | Fire | `TurnAttackRange 7,100` |
| `異形兵_アクスアーマー` | Axe Armor | 15 | (8,5) | (7,26) | 7 → NHL | Hammer | `TurnAttackRange 7,100` |
| `異形兵_ランスファイター` | Lance Fighter | 14 | (7,4) | (6,27) | **4 → solo L** | Steel Lance | `TurnAttackRange 7,100` |
| `異形兵_モンク` | Martial Monk | 12 | (13,5) | (12,26) | 7 → NHL | Steel-Hand Art + Physic | `TurnAttackRange 7,100` |
| `異形兵_ソードファイター` | Sword Fighter | 14 | (12,2) | (11,29) | **4 → solo L** | Steel Sword | `TurnAttackRange 7,100` |
| **`異形兵_ランスナイト_離脱`** | Lance Cavalier | 14 | **(7,1)** | **(6,30)** | 39 → NHL + `NotMove` | Iron Greatlance | `Everytime`, rate `慎重` |
| **`異形兵_アーチャー_離脱`** | Archer | 12 | **(8,1)** | **(7,30)** | 39 → NHL + `NotMove` | Steel Bow + **Master Seal (DROP)** | `Everytime`, rate `慎重` |

Las dos últimas (`_離脱` = "huida") **están plantadas encima de las dos casillas de escape**
y con `NotMove`: son el tapón. La arquera suelta un **Sello Maestro**.

**(SUPOSICIÓN, interpretación de la IA)** `AI_AC_TurnAttackRange "N, 100"` = la unidad se
activa al llegar el turno **N** o si entras en su rango de ataque, con probabilidad 100.
`AI.xml` solo lista los nombres, sin documentar los argumentos, y `dump.cs` no trae la
implementación. Aun así el patrón encaja con el diseño (los de la salida, con `7, 100`, son
los más lejanos). `AI_AC_Null` = nunca se activa por sí sola (el del Tomahawk se queda quieto
hasta que le pegas). `AI_AC_FlagTrue <flag>` = se activa cuando el guion pone esa flag a 1.

### 5.4 Recuento de enemigos iniciales

| dificultad | `Enemy_OP1` | `Enemy_OP2` | `Enemy` | **total inicial** |
|---|---|---|---|---|
| Normal | 9 | 1 | 12 | **22** |
| Difícil | 9 | 1 | 13 | **23** |
| Extremo | 9 | 1 | 18 | **28** |

### 5.5 Stats resueltos por arquetipo

Calculado con el resolver del propio proyecto
(`catalogo_loader.resolver_unidad_con_catalogo` sobre la salida de
`cargador_dispos.cargar_capitulo`), o sea: bases de clase + crecimientos de enemigo por
dificultad + `AutoGrowOffset*` + `Offset*` de `Person.xml`. **Son los números del motor de la
herramienta, no verificados en juego.**

Orden: **HP / Fue / Mag / Des / Vel / Def / Res / Suerte / Complexión**

| PID | Clase | Nv | Normal | Difícil | Extremo | Mov |
|---|---|---|---|---|---|---|
| `異形兵_ソードペガサス` | Sword Flier | 13 | 28/8/6/12/16/6/10/5/5 | 30/11/7/15/16/7/13/6/5 | 32/12/9/16/17/10/14/7/5 | 5 |
| `異形兵_アクスナイト` | Axe Cavalier | 14 | 32/10/3/14/13/8/5/4/8 | 34/13/3/16/14/11/8/5/8 | 36/14/5/17/15/12/10/5/8 | 5 |
| `異形兵_ソードファイター` | Sword Fighter | 14 | 28/9/1/13/13/6/5/4/6 | 30/12/1/15/15/8/9/6/6 | 32/13/3/16/15/11/10/6/6 | 4 |
| `異形兵_ランスファイター` | Lance Fighter | 14 | 32/11/5/14/11/8/5/3/6 | 34/14/6/18/11/11/7/3/6 | 36/15/8/18/13/12/9/4/6 | 4 |
| `異形兵_アクスファイター` (y el del Tomahawk) | Axe Fighter | 13 | 35/12/0/8/10/7/1/0/8 | 40/16/1/9/11/9/3/1/9 | 40/16/2/10/12/11/5/2/9 | 4 |
| `異形兵_アーチャー` (y `_離脱`) | Archer | 12 | 25/9/1/14/9/4/3/3/5 | 28/13/1/18/10/6/5/4/6 | 29/13/3/17/11/8/7/4/6 | 4 |
| `異形兵_マージ` | Mage | 13 | 21/2/7/14/13/3/11/2/4 | 22/3/10/15/12/4/16/3/4 | 24/5/10/17/15/7/17/4/4 | 4 |
| `異形兵_モンク` | Martial Monk | 12 | 23/5/5/9/9/5/11/4/4 | 25/8/8/10/9/8/15/5/4 | 27/9/8/12/11/9/16/5/4 | 4 |
| `異形兵_シーフ` | Thief | 13 | 28/8/2/14/15/5/4/4/5 | 30/12/2/18/16/9/6/6/6 | 32/14/4/18/16/10/9/6/6 | 5 |
| `異形兵_アクスアーマー` | Axe Armor | 15 | 35/13/1/12/5/18/2/3/9 | 40/16/1/14/4/24/3/3/10 | 40/17/3/15/7/25/6/4/10 | 4 |
| `異形兵_ランスナイト_離脱` | Lance Cavalier | 14 | 32/10/3/14/13/8/5/4/8 | 34/13/3/16/14/11/8/5/8 | 36/14/5/17/15/12/10/5/8 | 5 |
| **`異形竜`** | **Corrupted Wyrm** | 23 | 47/0/23/9/2/25/25/3/17 | 46/0/19/8/2/18/18/3/16 | 50/3/24/12/6/24/24/3/17 | **2** |
| `ヴェイル` (Veyle) | Fell Child | 25 | 42/15/28/20/20/14/23/13/6 | 42/15/28/20/20/14/23/13/6 | 44/16/31/22/22/16/26/15/6 | 5 |
| `セピア` (Zephia) | Melusine | 23 | 36/14/15/15/21/12/16/7/8 | 39/17/18/16/21/15/19/8/8 | 41/19/21/18/23/18/21/11/8 | 6 |
| `グリ` (Griss) | Sage | 3 | 33/7/11/13/13/9/18/8/7 | 35/9/15/13/13/12/22/9/7 | 37/10/18/15/15/14/25/12/7 | 5 |
| `モーヴ` (Mauvier) | Royal Knight | 3 | 38/15/15/18/17/14/12/9/10 | 41/19/18/20/17/18/16/9/10 | 43/21/21/22/19/21/18/13/10 | 6 |
| `マロン` (Marni) | General | 3 | 44/20/5/13/6/24/8/8/13 | 47/24/6/13/6/28/11/9/13 | 49/26/7/15/7/31/12/11/13 | 4 |

> **Rareza a vigilar**: el Corrupted Wyrm sale **más duro en Normal que en Difícil**
> (47 HP / 25 Def / 25 Res vs 46 / 18 / 18). Viene de que `Person.xml` de `PID_M011_異形竜`
> solo define `OffsetN.Def +6`, `OffsetN.Magic +4`, `OffsetN.Mdef +6` (sin equivalente en
> H/L) y `Job.xml` le pone `DiffGrowNormal.Def -25` etc. **(SUPOSICIÓN)**: puede ser una
> peculiaridad real del juego o un artefacto del resolver; habría que verificarlo en partida
> antes de dar los números de Normal por buenos.

Aliados que se unen (las tres dificultades dan lo mismo, son aliados):
Ivy `32/7/17/15/13/12/15/4/7` (mov 5) · Kagetsu `36/17/5/22/22/14/10/17/9` (mov 5) ·
Zelkov `35/15/3/19/19/14/5/7/9` (mov 5).

---

## 6. Refuerzos: **cero por turno, todo por evento**

No hay `CALENDARIO_REFUERZOS` que añadir para M011: en `イベント登録()` los únicos
`EventEntryTurn` son `進撃開始直後` (turno 1: cambia el BGM), `勝利条件` (turno 1: cartel de
la condición de victoria) y `青軍ターン直前イベント` (turno `-1, -1` = **cada** fase de
jugador, condicionado). Ninguno despliega nada por número de turno.

Los tres despliegues por guion salen todos del **mismo evento**, `四狗とアイビー登場()`:

| grupo | unidades | dm(x,y) → tool(x,y) | casilla de entrada (`AppearX/Y`) |
|---|---|---|---|
| `Enemy_4dogs` | Zephia (Melusine, Nv23, Levin Sword, HpStock 2) | (7,28) → (6,3) | (7,30) |
| | Griss (Sage, Nv3, Elwind, HpStock 2) | (8,28) → (7,3) | (8,31) |
| | Mauvier (Royal Knight, Nv3, Flame Lance, HpStock 2) | (10,28) → (9,3) | (10,31) |
| | Marni (General, Nv3, Hurricane Axe, HpStock 2) | (11,28) → (10,3) | (11,30) |
| `Enemy_EV1` | Martial Monk Nv12 (Steel-Hand Art + Physic) | (5,1) → (4,30) | (5, **0** = borde sur) |
| | Lance Fighter Nv14 (Steel Lance) | (6,2) → (5,29) | (6,0) |
| | Lance Fighter Nv14 (Steel Lance) | (9,2) → (8,29) | (9,0) |
| | Mage Nv13 (Thunder) | (10,1) → (9,30) | (10,0) |
| `Ally_Add0` | **Ivy** (Wing Tamer, Nv17) — verde | (14,10) → (13,21) | (17,10) = borde este |
| | **Kagetsu** (Swordmaster, Nv1/int.15) — verde | (15,10) → (14,21) | (17,10) |
| `Ally_Add1` | **Zelkov** (Thief, Nv17) — verde | (14,9) → (13,22) | (17,9) |

`Enemy_EV1` es el detalle importante para el tablero: **aparece pegado a la salida**
(filas 1 y 2 del sur), o sea entre tú y las casillas de escape, y con
`AI_ActionName = AI_AC_AttackRange` (se activan al entrar en su rango).
Sus filas **no llevan `Sid`** → estos cuatro sí pueden hacer críticos.

Los cuatro Sabuesos y `Enemy_EV1` son iguales en las tres dificultades (`Flag 7`);
los aliados llevan `Flag 15` = NHL + `Create`.

### 6.1 Disparadores del evento (los dos, el primero que ocurra)

`EventEntryTurn(青軍ターン直前イベント, -1, -1, FORCE_PLAYER, condition_青軍ターン直前イベント)`:

1. **Por zona** — `EventEntryArea(EmptyFunction, 1, 1, 16, 7, FORCE_PLAYER, "エリア進入_済")`.
   Cuando **cualquier unidad del jugador** pisa el rectángulo **X 1..16 · Y 1..7** (la franja
   de las 7 filas del sur, es decir al acercarte a la salida), se pone la flag `エリア進入_済`.
   El evento se dispara **al principio de la siguiente fase de jugador**.
2. **Por muerte de los tapones** — `EventEntryFixed(離脱地点が空いた, "", FORCE_PLAYER, condition_離脱地点が空いた)`,
   cuya condición es `指定座標上に敵がいない(7,1) or 指定座標上に敵がいない(8,1)`: en cuanto
   **una de las dos casillas de escape deja de tener un enemigo encima** (o sea, matas al
   Lance Cavalier o a la Archer), salta **inmediatamente** (no espera al turno).

Ambas vías ponen `四狗とアイビー登場_済 = 1` al terminar; la condición comprueba ese flag
para no repetirse.

En el vocabulario de `cargador_dispos.REFUERZOS_POR_EVENTO` esto se modelaría así
**(propuesta, no implementada)**:

```python
"M011": [
    {"grupo": "Enemy_4dogs", "descripcion": "Los cuatro Sabuesos y Veyle te cortan la retirada",
     "disparos": [{"tipo": "zona", "x1": 1, "y1": 1, "x2": 16, "y2": 7},   # tipo NUEVO
                  {"tipo": "muerte", "pid": "PID_M011_異形兵_ランスナイト_離脱"},
                  {"tipo": "muerte", "pid": "PID_M011_異形兵_アーチャー_離脱"}]},
    {"grupo": "Enemy_EV1",  ...mismos disparos...},
    {"grupo": "Ally_Add0",  ...mismos disparos...},
    {"grupo": "Ally_Add1",  ...mismos disparos...},
]
```

Hace falta **un tipo de disparo nuevo, `"zona"`** (rectángulo, cualquier aliado): los tipos
actuales (`casilla`, `combate`, `muerte`, `turno`, `objeto`, `accion`) no lo cubren. Y el
disparo por zona **se resuelve al empezar la fase de jugador siguiente**, no al pisarla.

---

## 7. Qué hace exactamente el evento `四狗とアイビー登場()`

En orden (útil para guionizarlo en la herramienta):

1. `Talk(MID_EV1)` con la cámara en Veyle.
2. `Dispos("Enemy_4dogs")` → aparecen los cuatro Sabuesos.
3. **`強者に指輪付与()`** → reparto de Emblemas Oscuros (ver §8).
4. `Talk(MID_EV2)`, `Talk(MID_EV3)`.
5. `Dispos("Enemy_EV1")` → los 4 corruptos que te bloquean la salida.
6. `Talk(MID_EV4)` (Alear desesperando).
7. `Dispos("Ally_Add0")` → Ivy + Kagetsu; `Talk(MID_EV5)`.
8. `Dispos("Ally_Add1")` → Zelkov; `Talk(MID_EV6)`.
9. Los tres se mueven junto a Alear (`UnitMovePos(..., g_pid_lueur)`), `Talk(MID_EV7)`.
10. `Movie("Kengen06")` → `Talk(MID_EV8)` → **`UnitCreateGodUnit("PID_アイビー", "GID_リン")`**
    con `UnitSetEngageCount(7)` → **Ivy recibe el Emblema de Lyn** (tutorial `TUTID_紋章士リン`).
11. `Movie("Kengen07")` → **`UnitCreateGodUnit("PID_リュール", "GID_ルキナ")`** con
    `UnitSetEngageCount(7)` → **Alear recibe el Emblema de Lucina** (tutorial `TUTID_紋章士ルキナ`).
12. `Talk(MID_EV11)` → **`アイビー隊仲間入り()`**: `UnitJoin("PID_アイビー","PID_ゼルコバ","PID_カゲツ")`
    (pasan de verdes a controlables, **sin hablar con nadie**) y se les **quita
    `SID_死亡回避`** (*Avo*, la habilidad que impide que mueran). Es decir: **mientras son
    verdes son inmortales; al unirse dejan de serlo**.
    (El datamine no dice dónde se les concede ese `SID_死亡回避`: no está en su `Person.xml`
    ni en su fila del dispos. **(SUPOSICIÓN)**: lo pone el motor a los NPC del bando verde.)
13. `SetFieldBgmWarSituation("B_BGM_Field_P05")` → cambia la música.
14. **`MapHistoryRewindEnable()`** → a partir de aquí se puede usar la **Cronogema**
    (antes no).
15. **`敵の必殺０を解除()`** → **recorre TODOS los enemigos y les quita
    `SID_必殺０_オフェンス時`**: desde este momento los corruptos **sí pueden hacer críticos**.
16. `VariableSet("四狗とアイビー登場_済", 1)` → con esto **se activan los dos Corrupted
    Wyrm** (su `AI_AC_FlagTrue FLAG_四狗とアイビー登場_済`), que hasta entonces estaban
    inertes.

Red de seguridad: en `MapEnding()`, si el evento no se llegó a reproducir, el guion une a
Ivy/Kagetsu/Zelkov y crea `GID_リン` y `GID_ルキナ` de todos modos.

---

## 8. Emblemas Oscuros: quién los lleva y cómo rotan

Los seis `GID_M011_敵*` **ya están compilados** en `json/catalogo_engage.json` con
`es_oscuro: true`, así que `cargador_dispos` les mete las armas del Emblema en el inventario
real (como con Hortensia en el Cap. 7 o Hyacinth en el Cap. 10):

| GID | Emblema | Armas (`engage_items`) | `engage_skills` | `synchro_skills` |
|---|---|---|---|---|
| `GID_M011_敵マルス` | Marth (Oscuro) | Rapier | Divine Speed (`SID_カウンター`) | Unyielding+ |
| `GID_M011_敵シグルド` | Sigurd (Oscuro) | Ridersbane, Brave Lance | Dark Gallop | Canter |
| `GID_M011_敵セリカ` | Celica (Oscuro) | Seraphim | — (ataque: `SID_セリカエンゲージ技_闇`) | Resonance+ |
| `GID_M011_敵ミカヤ` | Micaiah (Oscuro) | Shine | Dark Augment | Cleric+ |
| `GID_M011_敵ロイ` | Roy (Oscuro) | Lancereaver | Sink Below | Hold Out+ |
| `GID_M011_敵リーフ` | Leif (Oscuro) | Killer Axe (Evento), Master Lance | Adaptable | Arms Shield+, Vantage+ |

### 8.1 Reparto inicial (cinemática de apertura, `OPイベント_異形兵がエンゲージ`)

**Ninguna fila del dispos tiene atributo `Gid`**: los anillos se asignan **por coordenadas**
en el guion (`闇シンクロ_座標(x, z, gid)`), a quien esté en esa casilla, si es enemigo:

| casilla dm | tool(x,y) | Emblema | a quién le toca (según el dispos) |
|---|---|---|---|
| (7,29) | (6,2) | **Sigurd Oscuro** | `Enemy_OP1` Axe Cavalier (Steel Axe) |
| (9,28) | (8,3) | **Micaiah Oscuro** | `Enemy_OP1` Martial Monk |
| (3,18) | (2,13) | **Marth Oscuro** | `Enemy` Sword Flier (Steel Sword) |
| (11,16) | (10,15) | **Roy Oscuro** | `Enemy` Axe Fighter (Steel Axe) |
| (7,12) | (6,19) | **Leif Oscuro** | `Enemy` Lance Fighter (Steel Lance) |
| (9,8) | (8,23) | **Celica Oscuro** | `Enemy` Mage (Thunder) |

Cada uno recibe además un ajuste de IA:
`敵セリカ` → `AI_AT_EngageAttack "1, 1"`; `敵ミカヤ` → `AI_AT_Interference` en Normal y
`AI_AT_InterferenceFrequency "3, 3"` en Difícil/Extremo; el resto solo `AiSetActive(true)`.

Esto implica que **estos 6 enemigos "genéricos" son, de hecho, mini-jefes con armas de
Emblema y sincronías**, aunque su `Flag` no tenga el bit `Leader`. Para el tablero habría que
inyectarles el `Gid` (igual que `EMBLEMA_POR_EVENTO` hace con Hortensia en M007), pero aquí
la clave es **la casilla, no el PID** (varios comparten PID).

### 8.2 Redistribución al aparecer los Sabuesos (`強者に指輪付与`)

1. Recorre el mapa entero, **le quita el anillo a todo el que lo tenga**, le reequipa su arma
   propia (`UnitSetItemEquip`), le resetea la IA a `AI_AT_Attack` y marca ese Emblema como
   "en espera" (`エンゲージ待ち_<gid> = 1`).
2. Reparte **por PID**:
   - Zephia (`セピア`) ← **Marth Oscuro**
   - Griss (`グリ`) ← **Celica Oscuro**
   - Mauvier (`モーヴ`) ← **Micaiah Oscuro**
   - Marni (`マロン`) ← **Sigurd Oscuro**
3. Y **por casilla**, a los dos que tapan la salida:
   - (7,1) → **Roy Oscuro** (el Lance Cavalier `_離脱`)
   - (8,1) → **Leif Oscuro** (la Archer `_離脱`)
   (con `cameraAct = false`, sin animación).

### 8.3 Reciclaje de anillos cada turno (rama `else` de `青軍ターン直前イベント`)

Si ya pasó el evento de los Sabuesos y quedan Emblemas "en espera" (porque murió su
portador), **cada fase de jugador se reasignan hasta `g_SynchroNumMax = 2` anillos** a
enemigos vivos que no lleven ninguno:

- Orden de prioridad: por tiempo de espera (`エンゲージ待ち_*`, que sube cada vez que muere
  otro portador); Micaiah se cuela primera si su espera supera a la del tercero de la lista.
- **Micaiah** intenta ir a un `JID_モンク` (usuario de bastón); si no hay, va por distancia.
- **Sigurd o Celica** (solo uno de los dos por turno) van **al enemigo vivo más al norte**;
  para Celica se excluyen los guardianes de la salida y los `JID_アクスアーマー`.
- El resto, por **distancia al centro de gravedad del ejército del jugador**: primero los que
  están a distancia 10-15, luego los más cercanos, luego los demás.
- **Nunca pueden llevar anillo**: Veyle, el `異形兵_アクスファイター_トマホーク` (el del drop)
  y los **dos Corrupted Wyrm**.
- La primera reasignación dispara `初回シンクロ時イベント` → `Talk(MID_EV14)` con la cámara
  en Veyle.

Y al **matar al primer portador de anillo** salta
`EventEntryDie(指輪の待機状態を更新, ...)` + `指輪持ちの敵を初撃破` → cámara a esa casilla,
`Talk(MID_EV12)`, efecto `ワープアウト_闇`, `Talk(MID_EV13)`.

---

## 9. Corrupted Wyrms (y Phantom Wyrms)

### 9.1 En M011 hay **dos Corrupted Wyrm y ningún Phantom Wyrm**

`PID_M011_異形竜` ×2, grupo `Enemy_OP1`, en **dm(11,26)** y **dm(8,25)** → tool **(10,5)** y
**(7,6)**. En las tres dificultades. `Phantom Wyrm` (`JID_幻影竜`) **no aparece en M011**: sus
PID están en S006, S008, S012, S013, N004-N006 y `PID_やり込み_幻影竜`.

Corrupted Wyrm sí aparece además en M016, M017, M019, M021, M022 (uno es `PID_M022_ボス`),
M023, M024, M025.

### 9.2 Tamaño 2×2 — corrección de dónde está el dato

**`BmapSize` no está en `Job.xml`** (0 apariciones): está en **`Person.xml`**, por PID.
`PID_M011_異形竜` → `BmapSize = 2`. Todos los PID con `JID_異形竜` / `JID_幻影竜` lo llevan a 2;
el único con 5 es `PID_M026_ソンブル_竜型` (`JID_邪竜`).

**(SUPOSICIÓN)**: el `DisposX/DisposY` de una unidad 2×2 es la casilla de anclaje, pero **el
datamine no dice qué esquina** (¿inferior-izquierda, superior-izquierda?). Hay que
determinarlo en juego antes de pintarlas. Pista: el wyrm de dm(11,26) tiene `AppearY = 29` y
el de dm(8,25) `AppearY = 28`, o sea entran 3 filas por encima de su destino.

### 9.3 `JID_異形竜` (Corrupted Wyrm) — ficha completa

De `Job.xml` + `json/catalogo_engage.json`:

| campo | valor |
|---|---|
| Nombre | **Corrupted Wyrm** (`MJID_MorphDragon`) |
| Estilo de combate | `竜族スタイル` = **Dragon** → "Potenciadores de Engage máximos en habilidades y sincronías de Emblemas" |
| `MoveType` | 4 → `tipo_movimiento` **acorazado** (armored) |
| Mov base | **2** |
| Vista (`Base.Sight`) | 3 |
| Nivel máximo | 40 · `nivel_habilidad_clase` 25 · `es_especial` **true** |
| Armas | **solo `Especial`** (rango máx. **S**); todos los demás tipos a `N` · `WeaponTool = 1` |
| `LunaticSkill` | **`SID_狂乱の一撃`** (*Spirit Strike*): en Extremo, si sobreviven ambos y el rival tiene Engage, `相手のエンゲージカウント = max(0, ...-5)` → **le quita 5 de contador de Emblema al rival** |
| `Attrs` | **96** (32 + 64) → `debilidades`: **dragón caído** y **abominación** |

**Bases de clase** (`Base.*`): HP 30 · Fue 0 · Mag 7 · Des 0 · Vel 0 · Def 9 · Res 9 · Suerte 0 · Complexión 10.

**Topes** (`Limit.*`): HP 74 · Fue 0 · Mag 42 · Des 24 · **Vel 6** · Def 36 · Res 36 · Suerte 19 · Compl. 28.

**Crecimientos de enemigo** (`BaseGrow.*`, el bloque `enemy_growths.base` del catálogo):
HP 75 · Fue 0 · Mag 55 · Des 40 · **Vel 10** · Def 45 · Res 45 · Suerte 15 · Compl. 30.

Modificadores por dificultad, en la propia clase:

| | HP | Fue | Des | Vel | Def | Mag | Res |
|---|---|---|---|---|---|---|---|
| `DiffGrowNormal` | — | **-15** | — | — | **-25** | **-20** | **-25** |
| `DiffGrowLunatic` | **+15** | **+15** | **+15** | **+15** | **+25** | **+20** | **+25** |

(No hay `DiffGrowHard`: Difícil usa `BaseGrow` a pelo.)

`JID_幻影竜` (**Phantom Wyrm**) es **idéntico en todo** (mismas bases, topes, crecimientos,
mov 2, estilo Dragon, `LunaticSkill`) salvo `Attrs = 16` → su única debilidad es **dragón**
(el Corrupted Wyrm, con 96, es débil a *dragón caído* y *abominación*).

### 9.4 El ejemplar concreto de M011

`Person.xml` → `PID_M011_異形竜`:

| campo | valor |
|---|---|
| `Jid` | `JID_異形竜` · `BmapSize` **2** · `Belong` `BID_異形` |
| `Level` | **23** |
| `AutoGrowOffset` | N 0 · **H -1** · L 0 |
| `Offset` | solo Normal: **Def +6, Mag +4, Res +6** |
| `NormalSids` | `SID_命中回避－２０` (*HitAvo−20*: `命中値 -20`, `回避値 -20`, solo en Normal) |
| `HardSids` / `LunaticSids` | **vacíos** (o sea: en Extremo **no** trae `SID_狂乱の一撃` por PID — le llega por el `LunaticSkill` de la clase; los de M016/M022/M023… sí lo traen también por PID) |
| `Items` | vacío → usa lo que dice la fila del dispos |
| Sid de la fila del dispos | `SID_必殺０_オフェンス時` (**no puede criticar** hasta el evento de §7) |

**Armas (de la fila del dispos)** — tipo `Especial` (Kind 9):

| IID | Nombre | Mt | Wt | Hit | Crit | Rango | Mágica | `equip_sids` |
|---|---|---|---|---|---|---|---|---|
| `IID_火のブレス` | **Fire Breath** | 12 | 5 | 100 | 0 | **1-3** | sí | `SID_ブレス` (*Dragon Breath*), **`SID_相手の防御力無視`** (`相手の防御力 = 0` → **ignora Def/Res**) |
| `IID_炎塊` | **Fireball** | 7 | 5 | 80 | 0 | **4** | sí | mismos dos |

> Nota de coherencia con `notas/notas_pasivas.md`: ahí ya se dejó escrito que el
> `IID_火のブレス` del datamine (12/100/0/5) **es el aliento de los wyrms**, distinto del
> "Fire Breath" del Emblema Tiki del DLC. Se confirma: es exactamente el arma que llevan
> estos dos.

Como `AI_Flag = 120` incluye `EquipShortAfterLongRange`, la IA **cambia a Fire Breath tras
usar el Fireball de rango 4** (o al revés según el objetivo).

**Efectividades que RECIBEN** (`debilidades` del catálogo, `Attrs = 96`): *dragón caído* y
*abominación*. En la práctica, las armas de este mapa que les pegan efectivo:
**Seraphim** (`IID_セリカ_エンジェル`, `SID_異形特効` / *Effective: Corrupted*) — que en este
capítulo la lleva el enemigo con el Emblema Oscuro de Celica, no tú.

**Efectividades que NO reciben**: no son voladores ni acorazados a efectos de *Slayer*
(`tipo_movimiento` acorazado es de movimiento, pero sus `debilidades` son las de `Attrs`);
el Armorslayer/Hammer/Steel Bow del mapa **no** les hace efectivo.

---

## 10. Eventos de guion: casillas de escape y lo demás

### 10.1 Las casillas de escape (lo más importante del capítulo)

```lua
-- 離脱関係のイベント
EventEntryEscape(離脱イベント, 7, 1, "PID_リュール", condition_true)
EventEntryEscape(離脱イベント, 8, 1, "PID_リュール", condition_true)
```

→ **Dos casillas: dm(7,1) y dm(8,1)** = **tool(6,30) y (7,30)** con `mapa_alto=31`
(las dos del centro de la fila inferior del mapa).
**Solo `PID_リュール` (Alear)** las activa: el cuarto argumento es el PID.

`離脱イベント()` → gira a Alear, `Talk(MID_EV15)`, **`VariableSet("勝利", 1)`** → victoria
inmediata. Nada más cuenta: no hay que matar a nadie.

La apertura las señala en pantalla (`離脱マス点灯`):
`CursorAnimeCreate_DistanceModeNear(7, 1, "W2H1")` = marco de **2 de ancho × 1 de alto**
empezando en (7,1) → confirma que las casillas son (7,1) y (8,1).

Y **están tapadas al empezar** por `異形兵_ランスナイト_離脱` en (7,1) y
`異形兵_アーチャー_離脱` en (8,1), ambos con `NotMove`. Matar a cualquiera de los dos libera
la salida **pero dispara de inmediato la llegada de los Sabuesos** (§6.1).

### 10.2 Diálogos y sus disparadores

| MID | cuándo |
|---|---|
| `MID_OP1`…`MID_OP3` | apertura (con el reparto de Emblemas Oscuros entre `OP1` y `OP2`) |
| `MID_BT7` | conversación antes de combate con **Veyle** |
| `MID_BT8` / `MID_BT9` | antes de combate / al morir **Zephia** |
| `MID_BT10` / `MID_BT11` | antes / al morir **Griss** |
| `MID_BT12` / `MID_BT13` | antes / al morir **Marni** |
| `MID_BT14` / `MID_BT15` | antes / al morir **Mauvier** |
| `MID_BT1`…`MID_BT6` | conversación de Alear contra un portador de Emblema Oscuro: BT1 Marth, BT2 Sigurd, BT3 Celica, BT4 Micaiah, **BT5 Leif, BT6 Roy** (ojo al cruce). Solo si **Alear** es uno de los dos combatientes y ese Emblema no se ha comentado aún |
| `MID_EV1`…`MID_EV11` | el evento de los Sabuesos + Ivy (§7) |
| `MID_EV12` / `MID_EV13` | al matar al **primer** portador de Emblema Oscuro |
| `MID_EV14` | primera **reasignación** de un Emblema Oscuro |
| `MID_EV15` | **Alear escapa** (victoria) |
| `MID_ED1`…`MID_ED3` | cierre (`PuppetDemo`) |

`E_BattleTalkEntry_Sepia/Gris/Marron` (de `Common_E.lua`) están **vacías** en el datamine:
son ganchos del DLC sin contenido aquí.

### 10.3 Unidades que huyen

**Ninguna.** No hay `AI_MI_Escape` ni `AI_MV_Escape` en `M011.lua` ni en el dispos; los únicos
`Escape` son los del jugador (`EventEntryEscape`) y los de `M011_Encount.lua`
(los enemigos raros de la refriega huyen a (9,1) / (9,30), pero eso es la refriega, no el
capítulo).

### 10.4 Otros efectos de guion que afectan a los números

- **Nadie enemigo puede hacer críticos al principio**, salvo Veyle, los 4 Sabuesos y
  `Enemy_EV1`: el resto lleva `SID_必殺０_オフェンス時` en su fila del dispos, y el guion solo
  lo quita en el evento de §7 (`敵の必殺０を解除`).
- **La Cronogema está desactivada** hasta ese mismo evento (`MapHistoryRewindEnable`).
- **Los dos wyrms están inertes** hasta ese mismo evento (`AI_AC_FlagTrue`).
- `Ivy`, `Kagetsu` y `Zelkov` son **verdes inmortales** (`SID_死亡回避`, *Avo*)
  mientras no se unan, y **se unen solos** en el evento (`UnitJoin`): **no hay que hablar con
  ellos** → nada que añadir a `UNION_POR_CONVERSACION`.
- Al unirse, Ivy trae ya el **Emblema de Lyn** y Alear el de **Lucina**, ambos con
  `EngageCount = 7`.

---

## 11. Terrenos

- **El dispos de M011 no menciona ningún terreno**: no hay filas `PID_紋章氣` (casillas de
  energía de Emblema) — 0 apariciones, frente a 3 en M010 — ni ninguna otra fila de objeto,
  puerta, cofre o pared.
- `Terrain.xml` **no tiene entradas específicas de M011** (a diferencia de, p.ej.,
  `TID_進入不可_M026`): son los 142 terrenos genéricos (hoja `地形`) más 6 costes (`地形コスト`).
- La rejilla por casilla del capítulo vive en `MapTerrain_M011` / `Fld_M011`, y **esos
  ficheros no están en el dump** (`find -iname "*MapTerrain*"` → nada). Igual que en los
  capítulos anteriores, **el terreno hay que pintarlo a mano en el Tiled**; el datamine no
  aporta nada aquí.

---

## 12. `M011E.xml` — no es el capítulo

`dispos/M011E.xml` es el despliegue de la **refriega** (`script_encount = M011_Encount`) sobre
el mismo mapa: 12 slots `Player0` y 28 filas `Mob00`, **todas con `PID_ダミー`** (dummy), sin
clase, nivel ni armas — el juego las rellena por procedimiento. No aporta nada al capítulo de
la historia; solo confirma el tamaño del mapa (coordenadas hasta X 16, Y 30).

---

## 13. Resumen para montar el capítulo

| pregunta | respuesta |
|---|---|
| Tipo de mapa | **Huida**: Alear llega a **tool(6,30)** o **tool(7,30)** y se gana. Nada más cuenta |
| Tamaño | 17 × 31 **(SUPOSICIÓN** a partir de `g_map_width/height`**)** |
| Aliados desplegables | **10** (Alear fijo y obligatorio en tool(10,12) + 9 libres) |
| Enemigos iniciales | **22** (Normal) / **23** (Difícil) / **28** (Extremo) |
| Jefes | Veyle (bit `Leader`, `NotMove`, 3 piedras). Los 4 Sabuesos tienen 2 piedras cada uno pero **no** el bit `Leader` (el cargador ya los marca como jefes por `hp_stock > 0`) |
| Refuerzos por turno | **ninguno** |
| Refuerzos por evento | **4 grupos**, todos con el **mismo par de disparadores** (entrar en la franja sur Y 1..7, o liberar una casilla de escape) |
| Wyrms 2×2 | **2 Corrupted Wyrm**, inertes hasta el evento. Ningún Phantom Wyrm |
| Terreno | nada en el datamine |

### Pendiente / cabos sueltos

1. **`condicion_victoria("M011")` devuelve `"exterminio"`** y debería ser "escapar"
   (el `-1` la hace inalcanzable). Hay un test que fija el valor actual.
2. Falta un **tipo de disparo `"zona"`** en `REFUERZOS_POR_EVENTO` (rectángulo + "al empezar
   la siguiente fase de jugador").
3. Falta poder **asignar `Gid` por casilla**, no por PID: los 6 Emblemas Oscuros iniciales se
   reparten por coordenadas y varios candidatos comparten PID. Y la **rotación de anillos**
   entre enemigos vivos (hasta 2 por turno) no tiene equivalente en la herramienta.
4. Alear **no debe salir con Marth** en este capítulo (el fallback de `cargador_dispos`
   se lo pone); recibe **Lucina** a mitad de mapa, e Ivy **Lyn**.
5. Hay que modelar dos interruptores globales que cambian el evento: **críticos enemigos
   deshabilitados** y **Cronogema deshabilitada** hasta el evento de los Sabuesos.
6. Verificar en juego: la **esquina de anclaje** de las unidades 2×2 y los **stats del wyrm
   en Normal** (salen mejores que en Difícil).
