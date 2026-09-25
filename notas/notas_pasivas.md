# Motor de pasivas data-driven — plan por fases y estado

Objetivo: que TODAS las habilidades del juego (804 en Skill.xml) funcionen leyendo
`Condition` / `Act*` / `give_sids` / `Around*` del catálogo (`json/catalogo_engage.json`),
sin bloques a mano por nombre en `motor_calculo._stats_de_golpe`. Lo único escrito a
mano será un overlay pequeño: Emblemas DLC (no están en el datamine) y correcciones
verificadas en juego, siempre con comentario del porqué.

## Piezas

| pieza | qué es |
|---|---|
| `condicion_dsl.py` | intérprete de la DSL de Skill.xml (VARIABLES / FUNCTIONS / LITERALS / ACT_STAT_MAP). Ampliar vocabulario aquí. |
| `pasivas.py` | motor de habilidades: `sids_activos(unidad)` (recolección: personales, clase, sincronía, Fusión, estados, nombres → SID, variantes de estilo, SIDs de estilo), `efectos_recibidos` (auras Timing 20), `expandir_sync` (SyncSids), `recopilar_combate(unidad, ctx, aliados)` → `Modificadores` (sumas / multiplicadores / asignaciones por act, activas con timing, procs, ignoradas). `motor_calculo._stats_de_golpe` solo suma lo que devuelve. |
| `pasivas_overlay.py` | pseudo-SIDs escritos a mano con el esquema del catálogo: Emblemas DLC (Weapon Sync/+, Geosphere/+). `condition` puede ser una función Python. |
| `pasivas_temporales.py` | disparadores de give_sids "de 1 turno" (al esperar, aliado dañado); se integrará en `pasivas.py` (Fase 3). |
| `tests/golden/` | red de seguridad: escenarios reales + golden de todos los combates. |
| `tests/test_golden_combates.py` | compara el motor actual contra el golden; falla listando cada combate que cambia. |
| `tests/golden/cobertura_pasivas.py` | informe `notas/cobertura_pasivas.md`: qué entiende la DSL y qué vocabulario falta, por frecuencia real. |

## Comandos

```
python -m pytest tests -q                          # todo (incluye golden)
python tests/golden/generar_golden.py              # regenerar golden (solo cambios intencionados y revisados)
python tests/golden/cobertura_pasivas.py           # regenerar notas/cobertura_pasivas.md
python compilar_catalogo.py                        # recompilar el catálogo desde el datamine
```

Los golden fijan el **comportamiento actual**, no la verdad del juego. Cuando un
cambio haga fallar el golden hay que decidir combate a combate: si el número nuevo
es el del juego (verificado), se regenera y se anota; si no, es una regresión.
La verdad del juego vive en `tests/test_ground_truth_cap7.py`.

Escenarios golden (se añaden solos al crear `mapas/CAP_<n>_Tiled.json` con dispos en
el datamine): `cap7_inicial`, `cap8_inicial` (mapa + dispos Extremo + roster
`json/escuadron_guardado.json`) y `cap7_turno10` (partida real exportada,
`tests/fixtures/`). Para fijar otra partida real: exportarla desde la app y copiar
el JSON a `tests/fixtures/`, registrándola en `escenarios.py`.

## Fases

- **Fase 0 — red y radiografía** (hecha, 2026-09-18)
  - Golden de combates (3 escenarios, ~5.800 combates, determinista).
  - Informe de cobertura DSL frente a los 573 SIDs alcanzables por unidades reales.
  - Recolección completa de SIDs: sincronía por vínculo y Fusión como SIDs, nombres del
    roster → SID, variante por estilo de combate, personales también sin `pid`.
    `ContextoCombate.habilidades_sids` = `pasivas.sids_activos`.
- **Fase 1 — motor genérico en modo sombra** (hecha, 2026-09-19)
  - DSL: operadores `* / % !` y unarios, `int()`, `cond()`, `スキル確率()` (procs),
    `相手のスキル所持()`, literales de tipo de arma / atributo / triángulo / rol / estilo,
    variables de stats propios y del rival, `MaxHP`, `生存`, `防御力`, `ダメージ`…
    `ACT_STAT_MAP` cubre todos los ActNames del datamine. Cobertura: 347 cubiertas,
    38 no cubiertas (antes 188 / 190).
  - Catálogo: se compilan ahora `timing`, `stand`, `action`, `target`, `life`, `cycle`,
    `variantes_estilo`, `sync_conditions`, `remove_sids`, `change_sids`, `engage_sid`…
    (ver "Campos de Skill.xml" abajo).
  - `pasivas.recopilar`: recorre los SIDs activos, aplica `stand`, resuelve `priority`
    entre versiones +, encadena `give_target = 1` (uno mismo), separa procs.
  - Sombra: `_stats_de_golpe` añade `motor_pasivas` (atk/def) al resultado sin tocar
    ningún número; `/api/analizar` lo expone como `sombra_pasivas` y la UI lo pinta
    bajo "Sombra datamine" (naranja = no la lista el motor actual). Golden intacto.
- **Fase 2 — motor genérico en producción** (hecha, 2026-09-20)
  - `_stats_de_golpe` reescrito: `pasivas.recopilar_combate` para cada bando y suma de
    sus modificadores en el orden del juego (efectividad → Mt/Atk → 相手の威力 del defensor
    → Def/Res → multiplicadores de daño → Hit/Avo/Crit/Ddg → tasas impuestas). Cero
    comprobaciones por nombre de habilidad, unidad o Emblema en motor_calculo,
    motor_analisis, pasivas_temporales (Canter, Pass, Vantage, Rise Above, Sensitive… por SID).
  - Semántica nueva del acumulador: acts "+"/"-" (truncados a entero), "*" (multiplicadores:
    威力 × sobre el daño neto), "=" (asignaciones: 命中率 = 100, 相手の防御力 = 0, ユニット攻撃力…).
    Solo se consumen los timings estáticos del golpe (`TIMINGS_GOLPE_ESTATICO` = 1-5, 7, 8, 10)
    más las sumas de Timing 6 sobre golpes propios (Moved to Tears); 6/9/11/12/13/15 (por golpe)
    y ≥ 17 (eventos/comandos) esperan a la Fase 3. Los give_sids de comandos/eventos no se
    encadenan (Echo daba su ×0.6 a todos los ataques).
  - Auras (Timing 20 / Target 2 / `rango_efecto` = RangeI-RangeO del Skill.xml): el aliado a
    esa distancia recibe los give_sids si la Condition se cumple con 相手 = receptor
    (Guía Divina +3/-1 adyacentes, Spur Attack/Res de los anillos, Bond Forger, Knightly
    Escort con RangeI 0 = uno mismo). Flag bit 23 = también al portador (Crimson Cheer,
    Alabaster Duty, Verdant Faith: "a ambos"). Sustituye a las "auras recíprocas" a mano.
  - SyncSids con SyncConditions: sub-habilidades activas junto a la principal (Stalwart →
    _効果, Veteran+ → 特効無効, Sword Agility → Crit-10 solo con espada, Smash → 追撃不可,
    Gentility → Blue Skies con Sacred Twins…). Iterativo hasta punto fijo.
  - Ambos bandos de un mismo golpe: el defensor aporta 相手の威力 / 相手の命中値 / 相手の必殺値 /
    地形回避 del rival; el atacante 相手の回避値 / 相手の地形回避 / 相手の防御力. Fair Fight
    bonifica Hit a los dos (+15 al contraataque también).
  - Contexto de la DSL: `terreno_propio` es el del atacante (Trained to Kill mira su propio
    terreno; antes, el del rival), `rondas_rival` (相手の手番回数 = 0 si no puede contraatacar),
    `chain_attacks` (チェインアタック回数), identidad/género/Emblema (識別子, 性別, 神将レベル,
    個人判定 por pid). Los voladores presentan terreno Avo/Def 0 también a la DSL.
  - Reglas de estilo como SIDs (`pasivas.SIDS_ESTILO`): Encubierto SID_地形回避有利時２倍
    (**solo duplica el Avo del terreno**, no la Def: cambio justificado por el datamine),
    Místico SID_相手の地形回避有利時０ (**solo con tomo**: una Levin Sword no ignora el terreno),
    Acorazado SID_相性ブレイク無効.
  - Golden regenerado el 2026-09-20 con estas diferencias, todas del datamine: Perceptive
    (Avo +15 + 25 % Spd al iniciar), Spur Attack (+2 Atk a adyacentes del anillo de Alfonse),
    Fair Fight, Not *Quite*, Blinding Flash, Disarming Sigh, Stunning Smile, Certain Blow, Sure
    Strike, Hit１００, Stalwart, Areadbhar ×1.5 al atacar, Thunder/Elthunder/Thoron sin
    follow-up (SID_追撃不可), Share Spoils también al defender, Trained to Kill con terreno
    propio, Moved to Tears como +2 por golpe propio (antes un golpe extra de 2).
  - Advance (Roy, SID_踏み込み: comando Timing 21, MoveSelf 1, Range 1-1): "avanza 1 casilla
    hacia un enemigo a 2 y ataca". `motor_de_movimiento_y_amenaza.casillas_advance` da las
    casillas finales {Q: P}; `/api/unidad/rango_movimiento` las devuelve en `casillas_advance`
    (la UI las pinta en naranja), `/api/mover` las acepta, y `encontrar_pos_ataque_optima`
    las considera (a igualdad prefiere una casilla normal) anotando `advance_desde` en la
    recomendación ("Mover a (P) y ADVANCE a (Q)").
- **Fase 3 — secuencia y eventos**: acts de secuencia (`手番回数`, `攻撃回数`,
  `行動回数`, `攻撃結果`) en `simular_combate`; evaluación por golpe (`timing` 6-12,
  `action` 1/2) para `ダメージ` (Hold Out, Divine Speed 50 %); `give_target` 0/2/3/4 y
  `Around*` en `estado_tablero` (auras como Guía Divina, Get Behind Me, Savage Blow);
  procs como peor caso + esperado en `evaluar_riesgo`.
- **Fase 4 — especiales y limpieza**: registro `{SID: handler}` (Canter, Dance, Rise
  Above, overlay DLC: Weapon Sync…), eliminar aliases por nombre, tests a SIDs.

## Campos de Skill.xml (decodificados el 2026-09-19)

| campo | valores | significado |
|---|---|---|
| `Stand` | 0 / 1 / 2 | siempre / solo cuando la unidad **inicia** el combate (Perceptive, "Blow", Poison Strike) / solo cuando **defiende** ("Stance", Vantage, Engage Attack Guard). `recopilar` ya lo aplica. |
| `Action` | 0 / 1 / 2 | cualquier golpe / golpe **propio** (Hit0, DamageReduction On Attack) / golpe **recibido** (Poison, DamageNullify On Defense). Fase 3. |
| `Timing` | 0-27 | fase en que se evalúa: 1 boosts permanentes, 2 velocidad de ataque, 3 Hit/Avo/Crit, 4 inicio de combate (Divine Speed, Hold Out, Echo), 5 orden/forecast (Perceptive, Resonance, Vantage), 6 secuencia por golpe (Counter 50 %, Lodestar Rush), 7 daño (Momentum, Hit100), 8 procs (Ignis, Luna), 9 tras tirada (Divine Pulse), 10 modificador de daño (Poison, Magic 50 %), 11 tras impacto (Break, Hobble), 12 reducción de daño (Mercy, DamageNullify), 13 Break Defenses, 15 Alacrity, 17 exp/oro, 18 post-combate (Seal, Savage Blow, Poison Strike), 19 aliado atacado (Get Behind Me), 20 aura (Divinely Inspiring, Solar Brace), 21 tras actuar (Echo, Advance, Run Through), 22 comandos de mover aliados, 23 Dragon Vein, 24 Instruct, 25 al esperar (Self-Improver), 27 post-combate en área (Self-Destruct, Curious Dance). |
| `GiveTarget` | 0 / 1 / 2 / 3 / 4 | 0 depende de la habilidad (rival golpeado en Seal…, aliados adyacentes en Divinely Inspiring, uno mismo en Self-Improver), 1 uno mismo (cadenas de efecto propias), 2 aliados en cadena (All for One), 3 alrededor (Dreadful Aura, Attuned), 4 objetivo del comando (Special Dance). Solo 1 está resuelto. |
| `Priority` | 0-10 | entre versiones + de la misma familia aplica la mayor (Hold Out 1-4, Vantage 1-3). |
| `Life` / `Cycle` | turnos | duración de estados otorgados (Seal (Effect) 6, Silence 1…). |
| `*Skill` | SID | variante por estilo (DragonSkill, MagicSkill…) → `variantes_estilo` en el catálogo. |

## Hallazgos del datamine (para no redescubrirlos)

- `Around*` (8 SIDs) son efectos post-combate en área (Savage Blow, Self-Destruct,
  Curious Dance…), no auras. Las auras van por `give_sids` + `give_target` + `timing 20`.
- Hold Out y Divine Speed son puro datamine: `give_sids` → `_効果` con
  `cond: HP <= ダメージ`, `act: ダメージ = max(HP-1, 0)`. Exigen evaluar acts por golpe.
- Variantes por estilo: sufijos `_竜族 _気功 _魔法 _隠密 _重装 _連携 _騎馬 _飛行`;
  `_継承用` = versión heredada (sin bonos de vínculo). El catálogo ya trae el mapa explícito.
- Emblemas DLC (`json/dlc_emblems_canon.json`) referencian habilidades por nombre
  inglés (116), sin SID: territorio del overlay.
- Cuentas del combate en la DSL (deducidas de los Act*): 手番回数 = rondas de ataque de la
  unidad (Dragon Blast "= 2", Follow-Up "= min(手番回数, 1)"), 総手番回数 = rondas ya
  ejecutadas, 相手の手番回数 = rondas del rival (0 = no contraataca), 行動回数 / 攻撃回数 =
  golpes por ronda / por ataque (Brave "行動回数 × 2", Lodestar "攻撃回数 = 7").
- Timing 21 = comandos de ataque (Echo, Advance, Run Through, Paraselene), 22 = comandos de
  mover aliados (Reposition, Swap, Pivot, Draw Back, Shove). Sus give_sids solo valen al usar
  el comando. `move_self` y `rango_efecto` se compilan para ellos.
- Los `Around*` siguen sin motor; `SID_双聖` (Sacred Twins, RangeO 99) exige todos los aliados
  del mapa: `aliados_cercanos` ya trae todo el bando, así que funciona.
- `Hit１００` (SID de tutorial en el Lance Fighter (6,10) de M007): `相手の命中率 = 100`,
  el juego garantiza que se le acierta. El motor viejo no lo aplica.
- Terreno (2026-09-19): tipos de casilla `curacion` (+30 Avo, +10 HP/turno, antirruptura)
  y `evasion` (solo +30 Avo) en `lector_de_mapas`; los **voladores no reciben Avo/Def del
  terreno** (`CalculadoraEngage._es_volador` en `_stats_de_golpe`); la DSL ve ese terreno
  efectivo (地形回避 = 0 para un volador).
- Item.xml `EquipSids` (2026-09-19): las armas otorgan SIDs al portador; ya se compilan
  (`equip_sids`) y viajan en `Arma.sids` y en el contexto de la DSL. `SID_２回行動` = Brave
  (Brave Sword/Lance/Axe/Bow, Nova, y las Body Arts Iron/Steel/Silver-Body): el iniciador
  pega dos veces por ataque (Stand=1), el defensor no; los Ataques de Emblema no doblan.
  `SID_追撃不可` (Thunder/Thoron/Smash sin follow-up), `SID_必中` (Surge: Hit 100 %),
  `SID_攻撃速度＋５`, `SID_オフェンス時武器攻撃力上昇` (Areadbhar ×1.5 al atacar) ya los aplica el motor.
- Guardia en Cadena solo para ataques normales: no bloquea Ataques de Emblema.
- Houses Unite (verificado en el Cap. 9, 2026-09-20, `tests/test_ground_truth_cap9.py`): cada
  golpe = (Fue + bonos de pasivas + Mt efectivo de la reliquia + 5 − DEF) × 0.5, floor, mín 1.
  Reliquias del datamine: Aymr 24 (efectivo vs dragón), Areadbhar 14 ×1.5 al atacar
  (`SID_オフェンス時武器攻撃力上昇`), Failnaught 13 (efectivo vs volador y dragón, Mt ×3).
  Weapon Sync/+ (+5/+7), Guía Divina (+3) y Gente de Cuento (+2) entran como bonos.
- Confirmado en juego (2026-09-20): un pozo de Emblema no hace nada con una unidad en Fusión
  (rellena lo que falte del medidor y desaparece); las armas Brave no doblan en Ataques de
  Emblema (ni en los que permiten elegir espada); Self-Improver / Meditación duran la fase
  enemiga y caducan al empezar la siguiente fase de jugador.
- Pasivas "al esperar" (Timing 25: Self-Improver, Meditación): otorgan su efecto hasta el
  inicio de la siguiente fase de jugador (cubre la fase enemiga). Datamine: mismo Life/Cycle
  (1/2) para ambas. Sustituye la nota anterior de que Self-Improver moría al cerrar la fase.

## Armas de Emblema e inventario (2026-09-20)

- Las armas de Emblema solo existen en el inventario DURANTE la Fusión: el loader las
  inyecta al fusionar y las descarta si la ficha no está en Fusión (aunque vengan en
  una partida guardada); `FichaUnidad.terminar_fusion()` las purga al acabar y reequipa
  la primera ARMA normal (nunca una poción). Antes se quedaban (Failnaught (Emblema)
  equipada con el medidor a 0) y el análisis las recomendaba como ataques normales
  mientras `/api/combate/ejecutar` fusionaba por su cuenta.
- `motor_analisis._armas_aliado`: cualquier arma con `es_engage` (del catálogo o del
  inventario) lleva `requiere_fusion` si la unidad no está fusionada → prefijo
  "⚡ [FUSIÓN]" y botón "Fusionar y Atacar" coherentes con lo que hará el servidor.
- Prioridad del jefe en el análisis (2026-09-20): +300 solo si la jugada mata / quiebra una
  barra (antes siempre +300 y +1000 más por Ataque de Emblema, que arrastraba a todo el
  ejército y obligaba a gastar la Fusión). Desgaste al jefe: +60; Ataque de Emblema contra
  el jefe: +100 sobre sus números. Las armas/Ataques de Emblema solo se enumeran si la unidad
  está en Fusión o con el medidor lleno (mismo criterio que el servidor al ejecutar).
- Medidor de Emblema (verificado en juego, Cap. 9): +1 por cada ataque que la unidad hace
  o recibe en el combate (acierte o falle; Brave/Artes cuentan cada golpe), sin Chain
  Attacks; matar NO suma salvo Libération (SID_撃破時エンゲージカウント＋１, +1). Antes se
  sumaba +1 por baja y no se contaban los ataques recibidos al defender.
- Elección de arma (2026-09-20): entre kills igual de seguros y sin daño recibido
  desempata la que mata en menos golpes y con más margen sobre los HP del rival. Activar la
  Fusión por un arma de Emblema contra un enemigo normal tiene el mismo tope (40) que un
  Ataque de Emblema; ya fusionada, sus armas de Emblema compiten en igualdad.
- Override (verificado en el Cap. 9, 2026-09-20): atraviesa a TODOS los enemigos consecutivos
  de la fila/columna (5 en el juego; antes tope de 3); la casilla de llegada puede ser de
  evasión (coste 2) pero no muro, foso ni bosque (`ataques_area.es_casilla_llegada_override`);
  los bonos de posición del atacante (Guía Divina de Alear adyacente, Momentum, Gente de
  Cuento…) se aplican a todos los objetivos porque golpea a todos desde su casilla de
  ataque; cada objetivo conserva sus propias auras y terreno. Igual en el análisis
  (`_evaluar_objetivos_extra`) y al ejecutar (`/api/combate/ejecutar`).
- Condición de victoria del capítulo (2026-09-20): `cargador_dispos.condicion_victoria(M0xx)`
  lee el `WinRuleSet*` del .lua ("jefe" = derrotar al jefe, "exterminio", "" otras) y
  `pids_jefe` los PIDs con bit 16 del Flag. En el análisis, una kill SEGURA que cumple la
  condición (`termina_mapa`) no se descarta por las amenazas de la fase enemiga (no la hay)
  y va la primera ("GANA EL MAPA"). Antes, Céline mataba a Ivy con Levin Sword pero se
  descartaba porque quedaba rodeada de hachas. Al importar/guardar, el jefe del dispos se
  marca aunque el guardado venga sin `es_jefe`.
- `motor_analisis.ERRORES_ANALISIS`: las opciones descartadas por excepción ya no se pierden
  en silencio (se registran y se loguean). Con ello se vio y corrigió `evaluar_riesgo`: el
  segundo combate (fase enemiga) intentaba simular con un arma que no alcanzaba esa
  distancia y tumbaba la evaluación de amenaza.
- La Cronogema (`/api/tablero/deshacer`) devuelve `casillas_fuego`; la UI lo repinta (el fuego
  apagado se quedaba dibujado tras deshacer).
- Gallop (Sigurd, SID_迅走): bono de Mov de la FUSIÓN, del datamine (stat_boosts.mov con
  variante de estilo): +5 general, **+7 caballería** (_騎馬), +6 dragón (_竜族), +5 volador
  / encubierto, +3 la versión oscura. El +1 de llevar a Sigurd equipado sigue saliendo de
  los stat_boosts del nivel de vínculo. `FichaUnidad.mov_base` guarda el Mov sin Fusión y
  `actualizar_movimiento_fusion()` recalcula `mov = mov_base + bono` al fusionar, al cargar
  una ficha y al terminar la Fusión. El campo Mov del modal es el TOTAL que ve el jugador:
  al guardar se le descuenta el bono para no acumularlo.
- Gallop en el análisis (2026-09-22): si una unidad puede fusionar (Emblema + medidor lleno)
  y la Fusión le daría Mov extra, se calcula también su alcance FUSIONADO
  (`casillas_mov_fusion`); las casillas de ataque que solo se alcanzan así marcan la jugada
  como `requiere_fusion` ("⚡ [FUSIÓN] … | Solo llega fusionándose (+N Mov del Emblema)") y,
  contra enemigos normales, tienen el mismo tope de score que un Ataque de Emblema (no se
  gasta la Fusión por un soldado). `/api/combate/ejecutar` con `requiere_fusion` activa la
  Fusión ANTES de mover (`_activar_fusion`), porque la casilla propuesta depende de ese Mov.

## Emblema de Lyn (2026-09-22)

Registrado entero desde el datamine; en el Cap. 10 lo lleva Hyacinth como Emblema
Oscuro (`GID_M010_敵リン`).

- **Call Doubles** (`SID_残像`, comando de Emblema). Skill.xml lo describe con
  `VisionCount`: **4 copias**, **5 en estilo Dragón** (`SID_残像_竜族`); en estilo Volador
  siguen siendo 4 pero reciben `SID_残像_飛行_効果` (**+10 Evasión**). El doble es una
  unidad propia del datamine: `PID_残像` ("Illusory Double", clase Villager) con
  `IID_残像_マーニ・カティ` (Mani Katti Mt 6 / Hit 80 / Crit 20, efectiva contra caballería
  y acorazados) y `SID_相手の取得経験値０` (no da experiencia). Params.xml
  `残像能力倍率` ("Doubles stats multiplier") = **1**: mismas stats que el invocador,
  con **1 HP**.
  El texto japonés ("自分のみチェインアタック可能な残像") aclara que **solo hacen Chain
  Attack cuando ataca quien los invocó**, no con el resto del ejército — por eso
  `obtener_aliados_backup` los filtra por `invocador` en vez de tratarlos como Backup.
  En el tablero: `EstadoTablero.invocar_dobles` / `disipar_dobles` /
  `purgar_dobles_huerfanos` (se disipan solos al caer el invocador), endpoints
  `POST /api/unidad/invocar_dobles` y `/api/unidad/disipar_dobles`, y botón
  "Invocar dobles" en el modal de la unidad (solo si `puede_call_doubles`).
  `pasivas.call_doubles(unidad)` devuelve {sid, copias, give_sids, pid, arma_iid}.

- **Astra Storm** (`SID_リンエンゲージ技`): NO es un arma fija. Dispara el **arco
  equipado** (`WeaponProhibit` 1007 = solo Kind 4) **5 veces** (`攻撃回数 = 5`) a una
  **fracción del daño** (`SID_ダメージ３０％` → techo(daño × 0.3)), alcance **1-10**
  (`RangeI/O`), Hit 100, sin respuesta del rival. Bonos de estilo del propio Skill.xml:
  **Encubierto alcance +10** (1-20), **Dragón +5** (1-15), **Qi Adept rompe** al objetivo
  sin ganar alcance. Las versiones oscuras / debilitadas pegan al **20 %**: la de Hyacinth
  es `SID_リンエンゲージ技_闇_気功` (20 % + ruptura).
  *(Ojo: el bono de Encubierto es +10, no +5; el +5 es el de Dragón.)*

### Ataques de Emblema de varios golpes, genéricos

`pasivas.forma_ataque_emblema(unidad, sid, nombre)` lee la forma del ataque del propio
Skill.xml: `攻撃回数 = N` + el `SID_ダメージNN％` sincronizado (más `SID_エンゲージ技_汎用設定`,
que es lo que fija Hit 100 / Crit 0 / rival sin turno). `motor_calculo._stats_de_golpe` ya
no tiene el bloque hardcodeado de Lodestar Rush con sus 9/8/7: los golpes y la fracción
salen del SID con la variante de estilo, así que Lodestar Rush (7, Apoyo 8, Dragón 9, al
30 %) y Astra Storm (5 al 30 %/20 %) comparten camino. El SID del ataque viaja en la
Unidad (`sid_ataque_emblema`, de God.xml `EngageAttack`) y, si falta, se resuelve por el
nombre del ataque que se simula.
**Pendiente**: Quadruple Hit (4 golpes) y Twin Strike (2) NO pasan por aquí porque cada
golpe usa un arma distinta (espada/lanza/hacha/arco; Eirika + lanza de Ephraim); siguen
resolviéndose como un ataque normal. El filtro es `fraccion is not None`, no una lista de
nombres.

### Adaptable (`SID_順応`, Emblema de Leif)

El datamine no la describe con Acts (la resuelve el motor del juego); el texto oficial
dice "If foe initiates combat, unit counters with the best weapon available (in terms of
range, weapon advantage, effective bonus, etc.)". Implementada en
`motor_calculo.arma_de_respuesta`: al DEFENDER, la unidad elige de su inventario el arma
que alcanza esa distancia y maximiza el daño esperado (daño neto × precisión, con
efectividad y ventaja de triángulo). Para eso la Unidad de combate ahora lleva su
`inventario` resuelto. Las variantes de estilo sí traen Acts normales: la de Volador
(`SID_順応_飛行`, la que tiene Ivy) da **+5 Res en combate**.

### Emblemas Oscuros: no se fusionan, así que lo llevan todo puesto

Un `es_oscuro` tiene `EngageCount 0`: nunca entra en Fusión, pero en la batalla lleva las
armas del Emblema y usa sus habilidades y su Ataque de Emblema. Por eso, cuando el Emblema
es oscuro, `catalogo_loader` trata la inyección de Fusión como **permanente**
(`engage_permanente`): sus `engage_items` entran en el inventario (y no se retiran fuera de
Fusión) y sus `engage_skills` van a las pasivas siempre activas en vez de a
`habilidades_sids_fusion`. Esto sustituye al caso especial que había para Hortensia en el
Cap. 7 y arregla a Hyacinth (Mani Katti + Killer Bow + Call Doubles + Astra Storm) y a Ivy
en el Cap. 8 (Killer Axe + Master Lance + Adaptable, `GID_M008_敵リーフ`).

**Golden cap8 regenerado** por este cambio: 66 combates nuevos (Ivy atacando con sus dos
armas de Leif) y 93 modificados, todos "aliado → Ivy" y todos por Adaptable — +5 Res en
combate (25 combates pierden daño mágico) y la respuesta con la mejor arma disponible (15).
Ninguno desaparece.

### Dual Strike (`SID_絆の力`, sincronía de Lucina)

"Unit participates in chain attacks as if it were a backup unit": lo concede el SID oculto
`SID_チェインアタック許可` que sincroniza. `pasivas.permite_chain_attack(unidad)` lo detecta y
`obtener_aliados_backup` ya no exige estilo Apoyo. En el Cap. 7 eso significa que
**Hortensia encadena ataques** con los enemigos que la rodean (verificado en el juego junto
con All for One y la Noble Rapier): el golden `cap7_turno10` cambió en 4 combates, todos
"alguien ataca a Louis" con un `chain_attack` de 3 de Hortensia por delante. `cap7_inicial`
no se movió (al desplegar no llega a nadie).

**Pendiente**: All for One (`SID_ルキナエンゲージ技`) sincroniza
`SID_強制チェインアタック２マス` — fuerza el Chain Attack de TODOS los aliados a 2 casillas,
no solo de los de Apoyo. El motor aún lo trata como un ataque normal de arma variable.

### All for One (`SID_ルキナエンゲージ技`) y Bonded Shield (`SID_絆盾`)

**All for One**: ataque de espada al adyacente + Chain Attack **forzado de todos los
aliados** a 2 casillas del atacante, sean o no de estilo Apoyo. El radio no está en el
nombre sino en el `RangeO` del SID sincronizado (`SID_強制チェインアタック２マス` → 2;
la variante de Apoyo sincroniza la de **3 casillas**, que es el "[Backup] Range +1") y el
"[Dragon] Ally chain attacks are guaranteed to hit" es el `GiveSids`
`SID_チェインアタック命中率１００％` (`命中率 = 100`, GiveTarget 2) de la variante de Dragón.
`pasivas.chain_attack_forzado()` lo lee; `obtener_aliados_backup(..., ataque_emblema=...)`
devuelve entonces a todos los cercanos y los Chain Attacks pasan de 80 % a 100 % de Hit.
En el Cap. 7 queda **registrado** en Hortensia (su `EngageAttack` es este SID): el jugador
anota el daño si llega a usarlo, no lo simula la IA.

**Bonded Shield**: comando que anula el primer ataque contra los aliados **adyacentes**
hasta el turno siguiente. El porcentaje está en la `Condition` de la variante de estilo:

| Estilo | Condition | % |
|---|---|---|
| base | `スキル確率(80)` | 80 |
| Dragón | `スキル確率(90)` | **90**, no 100 (coincide con "[Dragon] +10 % to trigger rate") |
| Qi Adept | `スキル確率(100)` | 100 |
| Caballería / Acorazado / Volador | `スキル確率(80) \|\| 相手の戦闘スタイル == Xスタイル` | 80, y **100 para los aliados de ese mismo estilo** |

`pasivas.probabilidad_bonded_shield(unidad, aliado)` resuelve el % que toca.
`EstadoTablero.activar_escudo_vinculo` / `POST /api/unidad/escudo_vinculo` marcan a los
adyacentes con un estado temporal "Bonded Shield (N %)" que caduca en el turno siguiente;
la herramienta **no** anula el golpe (el jugador registra el daño real), solo avisa.
El Emblema Oscuro de Lucina del Cap. 7 **no** trae Bonded Shield: su `GGID_M007_敵ルキナ`
solo declara `SID_絆の力`.

### Houses Unite (Unión de Casas, Emblema DLC de las Tres Casas)

"Use to attack with Aymr, Areadbhar, and Failnaught at 50 % damage."
Cada golpe es el **daño normal de esa reliquia partido por la mitad, truncando** — no una
fórmula aparte. El motor ya no lleva el "+5" fijo que tenía: era un parche que compensaba
una Fue mal reconstruida en un test, y hacía que los tres golpes salieran ~2-3 de más.

Reliquias, con sus datos del datamine (Item.xml, armas DLC de Byleth):

| Reliquia | IID | Mt | Notas |
|---|---|---|---|
| Aymr | `IID_ベレト_アイムール` | 24 | Hacha |
| Areadbhar | `IID_ベレト_アラドヴァル` | 14 → **21** | `SID_オフェンス時武器攻撃力上昇`: +50 % de Mt al iniciar, y Houses Unite siempre inicia |
| Failnaught | `IID_ベレト_フェイルノート` | 13 | Arco |

Bonos de estilo del texto oficial, **+10 % sobre el golpe ya reducido**:
Dragón a los tres · Caballería a Areadbhar · Encubierto a Failnaught · Acorazado a Aymr ·
Qi Adept rompe al objetivo (sin daño extra).

**La efectividad sí se aplica**, con la resistencia del defensor como en cualquier otro
ataque. Lo que parecía una excepción era el **Veteran+ de Hortensia** (`SID_熟練者＋` →
`SID_特効無効_効果`), que anula la efectividad: por eso Failnaught no la triplica contra
ella y sí contra un volador corriente. El bloque de Houses Unite se saltaba esa regla
llamando directo a `calcular_efectividad`; ahora pasa por el mismo `_con_resistencias` que
el arma principal, así que Veteran/Veteran+/Stalwart valen también para las reliquias.

Las tres observaciones en juego cuadran a la vez:

| Observación | Defensor | Golpes | Failnaught |
|---|---|---|---|
| Cap. 7 combate 70 (Chloé Fue 15) | Hortensia (voladora **con Veteran+**) | 15 / 13 / 9 = **37** | ×1 |
| Cap. 9 (Chloé Fue 20, Weapon Sync+ +7) | Axe Flier (volador normal) | 19 / 18 / **27** | ×3 |
| Cap. 10 (Chloé, sin bonos) | Hortensia | **17 / 16 / 12** | ×1 |

De paso: la Fue de las dos reconstrucciones de test estaba 5 por debajo de la real, que es
justo lo que tapaba el "+5". Y Hortensia es voladora, así que el +1 de defensa de la casilla
de protección del Cap. 7 no cuenta.

### "Ragnarok" el tomo vs "Warp Ragnarök" el Ataque de Emblema (2026-09-23)

`es_warp_ragnarok` se detectaba con el fragmento `"ragnarok"` a secas, que también es el
nombre del **tomo** de Celica (`IID_セリカ_ライナロック`), un arma de Emblema con la que se
hacen ataques normales. Y la UI marcaba `es_engage_attack` mirando el nombre del arma
recomendada (`...includes("ragnarok")`), así que atacar con el tomo se enviaba como Ataque
de Emblema y se llevaba el ×1.2 de estilo Místico, el atacar a RES y el "sin contraataque".
Ahora: el motor solo reconoce el nombre completo del ataque, el análisis publica
`es_engage_attack` / `engage_attack_nombre` en cada jugada y la UI los reenvía tal cual en
vez de deducirlos del nombre del arma.

### Pasivas de "solo el primer golpe" (2026-09-23)

Momentum (`SID_助走`) suma `min(移動距離, 10)` al ataque, pero su Condition es
`移動距離 > 0 && 総行動回数 == 0`: **solo el primer golpe del combate**. Verificado en un
vídeo (unidad con Sigurd que dobla: 16 y 10 de daño, los +6 solo en el primero).

El motor evaluaba todas las pasivas de Timing "estático" con un contexto fijo
(`総行動回数 = 0`), así que el bono se colaba también en el follow-up. Ahora:
- `_stats_de_golpe` acepta `ronda` (rondas ya ejecutadas) y la pone en el contexto.
- `pasivas` marca cada habilidad activa con `condicion_primera_ronda` cuando su Condition
  compara `総行動回数` o `総手番回数` con 0.
- `simular_combate` recalcula el golpe de seguimiento con `ronda=1` **solo si** alguna
  pasiva del primer golpe llevaba esa marca; si no, reutiliza el mismo resultado y no
  paga el cálculo.

Es un primer trozo de la Fase 3 (evaluación por golpe) y vale para cualquier otra
habilidad con esa forma, no solo Momentum y Momentum+.

## Emblema Tiki (DLC) — 2026-09-24

Fuente: https://serenesforest.net/engage/emblems/tiki/ (el DLC no está en el datamine).
Los **datos por nivel** ya estaban bien en `json/dlc_emblems_canon.json` y coinciden uno a
uno con Serenes; lo que faltaba es que las pasivas **hicieran algo**: solo Geosphere existía
como habilidad. Ahora están las siete sincronías más la de Fusión en `pasivas_overlay.py`,
y se activan solas según el vínculo que elija el jugador, porque quien decide es la lista
`synchro_skills` de cada `bond_levels` que ya aplicaba `catalogo_loader`.

| Nv | Pasiva | Qué hace y cómo está modelada |
|---|---|---|
| 1 | Starsphere | +15 % a los crecimientos al subir de nivel. Fuera de combate: se registra para que salga en la ficha, sin acts. |
| 3 / 16 | Geosphere / + | Def/Res **+3 / +5** al portador **y a los adyacentes**, si hay alguno. Aura Timing 20 con el **bit 23 del Flag** (`FLAG_AURA_TAMBIEN_PROPIO`), que es lo que hace que el portador también la reciba — antes no. |
| 8 / 14 / 19 | Lifesphere / + / ++ | Al **esperar** (sin atacar ni usar objetos): cura **20 / 30 / 40** HP y limpia los estados alterados. Timing 25 con un act `回復`. |
| 10 | Lightsphere | Al **iniciar** combate, el rival critica a la **mitad**. Act `相手の必殺率 × 0.5`, Stand 1. |
| Fusión | Draconic Form | **+10 HP** y **+5** a Complexión y a todas las stats básicas mientras dure la Fusión. Vive en `habilidades_sids_fusion`, así que se apaga sola al terminar. `[Mystical] +5 Res extra` va como SyncSid con Condition de estilo; el `[Armored] anula daño de terreno` no es de combate y no se modela. |
| 4/9/13/17/19 | Special Guard 1-5 | Heredables: **-1 a -5** de daño recibido. **La condición no está verificada**: el juego dice "si el rival lleva un ataque especial" y no se sabe con qué lo marca, así que de momento se aplica cuando el rival es quien ataca. Revisar si se ve en juego. |

### Lo que hubo que abrir en el motor para esto

- **`condicion_dsl`**: `速さ`, `幸運` y `体格` se podían LEER en las Condition pero no
  escribir en los Act. Ahora son destinos válidos (`spd`, `lck`, `bld`). Ninguna habilidad
  del datamine las usa como destino (comprobado), así que no movió ningún número existente.
- **`motor_calculo`**: esos canales entran ahora por su fórmula, no como bono plano —
  Velocidad y Complexión en la Velocidad de Ataque, Destreza y Suerte en Hit/Crit/Avo/Ddg.
  +5 de Destreza no es +5 de Hit.
- **Tasa de crítico multiplicable**: solo se podía *fijar* (`必殺率 =`), no reducir.
  Lightsphere necesita multiplicarla, así que `prob_critico` aplica ahora
  `producto('crit_rate') × producto('rival_crit_rate')` sobre la probabilidad final.

### La Fusión de Tiki convierte en dragón, y qué es un "ataque especial"

**Un ataque especial es un arma de tipo `Especial`** (Item.xml, **Kind 9**). El compilador
ya las clasificaba así (`constants.TIPO_ARMA_KIND["9"] = "Especial"`) y la DSL ya traducía
el literal `特殊`, pero nada las usaba. Son:

- Los alientos de los **Corrupted Wyrm** (`JID_異形竜`) y **Phantom Dragon** (`JID_幻影竜`),
  las tropas que ocupan **2×2** (`BmapSize = 2`). Su clase tiene `MaxWeaponLevelSpecial = S`
  y **N en todo lo demás**: solo saben usar ataques especiales.
- Los ataques de Sombron, el Dragon Fang de Corrin, el rayo de Alear, los cañones de fuego.
- Y los del propio Emblema Tiki.

**Cap. 11**: trae dos `PID_M011_異形竜`, cada uno con `IID_火のブレス` (Fire Breath, Mt 12,
alcance **1-3**, mágico) e `IID_炎塊` (Fireball, Mt 7, alcance **4**), más
`SID_必殺０_オフェンス時` (no critica al iniciar). Ojo al alcance: pegan a 1-3 y a 4.

Con eso, dos cosas quedan resueltas:

- **Special Guard 1-5** ya no tiene la condición a medias: es `相手の武器の種類 == 特殊`.
  Verificado: -1 a -5 contra el aliento del wyrm, 0 contra un hacha normal. (Va en Timing 7
  en vez del 12 del juego, que es Fase 3; al ser una resta fija el número es el mismo.)
- **Draconic Form prohíbe las armas propias**: mientras dura la Fusión la unidad pelea como
  dragón y solo puede usar los ataques del Emblema. Lo marca `solo_armas_emblema` en el
  overlay y lo aplica `motor_analisis._armas_aliado`.

**Pendientes de este emblema:**

- De las **7 armas de Fusión de Tiki solo existe Fire Breath** en el catálogo. Eternal Claw,
  Tail Smash, Ice/Flame/Dark/Fog Breath son exclusivas del DLC y no tienen fila en Item.xml,
  así que no hay Mt, alcance ni efectos. Habría que anotarlas a mano en
  `json/dlc_emblems_canon.json` cuando se tengan (Serenes solo da la descripción, no las
  stats). Las descripciones sí dicen cosas aprovechables: varias son de área, golpean a
  media Def/Res y no permiten seguimiento.
- Las tropas **2×2 se tratan como una casilla**. Para el Cap. 11 habrá que decidir cómo se
  modelan (ocupan 4 casillas, bloquean el paso y se las puede atacar desde más sitios).
- **Divine Blessing** (Ataque de Emblema) da una **piedra resurrectora** a un aliado
  elegido; con Marth adyacente, Divine Blessing+ además cura o recarga el medidor. El
  análisis ya lo excluye de las opciones de ataque (no es un ataque), pero no existe como
  comando: la herramienta ya sabe de `hp_stock`, así que sería un botón como los demás.

### Piedras resurrectoras en ALIADOS (2026-09-24)

`Divine Blessing`, el Ataque de Emblema de Tiki, le da una piedra a un aliado. La lógica
existía para los jefes, pero el bando propio estaba a medias. Lo que faltaba:

- **El ATACANTE no gastaba piedras.** `simular_combate` solo las miraba en el defensor, así
  que un aliado con barra de repuesto figuraba muerto por el contraataque. Ahora hay
  `revivir_atacante_si_procede()` en los cinco puntos donde recibe daño, y el resultado
  expone `piedra_atacante_consumida` (que `app.py` descuenta al ejecutar el combate).
- **El veredicto de riesgo daba por muerta a la unidad.** `atacante_muere_en_contra`
  comparaba el daño con `atacante.hp` a secas; ahora cuenta la barra actual **más** las de
  repuesto. Y las dos reconstrucciones de `atacante_post_combate` que simulan la fase
  enemiga no arrastraban ni `hp_max` ni `hp_stock`: por eso la unidad "moría" igualmente
  después. Verificado: 0 piedras → riesgo crítico 100 %; 1 → sobrevive al contraataque pero
  cae en la fase enemiga (92 %); 2 → riesgo bajo, 0 %.
- **Registrar el daño a mano mataba a la unidad.** En la fase enemiga el jugador apunta el
  daño recibido con `/api/unidad/ajustar_hp`; quedarse a 0 con piedra ahora gasta una barra
  y devuelve la vida llena (`FichaUnidad.gastar_piedra_si_cae`), y solo se dispara el evento
  de muerte del guion cuando cae de verdad. Esto cambia también a los JEFES: a Morion hay
  que tumbarlo dos veces para que lleguen sus refuerzos, que es lo que hace el juego.
- **Objetivos extra y planes de kill**: `_evaluar_objetivos_extra` marcaba `muere` con
  `hp <= 0` a secas (ahora distingue `pierde_barra`), y el plan de kill descartaba a un
  aliado si el contraataque le bajaba de su HP actual sin contar las barras de repuesto.

**Nunca caen dos barras en el mismo combate** (verdad de juego): en cuanto la unidad con
piedras se queda a 0, el combate se para en seco — no hay seguimiento aunque el rival doble,
ni se toca la barra siguiente. Para el defensor ya funcionaba así (`barra_resucitada` era el
guardia de toda la secuencia); al añadir las piedras del atacante **se rompió**, porque
`barra_atk_resucitada` no guardaba nada y el rival seguía pegando. Ahora los 14 guardias de
la secuencia miran las dos. Los del RESULTADO (`atacante_mata`, `mata_solo_atacante`) siguen
mirando solo la del defensor, que es lo que significan.

El campo del modal ya existía y no estaba limitado a enemigos, así que no hubo que tocar la
UI. Un aliado con piedras **no** se confunde con un jefe: `es_jefe` ya exigía `not es_aliado`.

### Armas de Fusión de Tiki (2026-09-24)

Stats **verificadas en juego por el jugador**. No están en el datamine, así que viven en
`json/dlc_armas_canon.json` y `compilar_catalogo.py` las integra en `armas` igual que ya
hacía con los Emblemas de `dlc_emblems_canon.json` (sobreviven a la recompilación).

| Arma | Mt | Hit | Crit | Wt | Estilo que la usa | Efecto |
|---|---|---|---|---|---|---|
| Eternal Claw | 10 | 90 | **30** | 8 | todos | — (el crítico alto es el "fatal wounds") |
| Tail Smash | **22** | 85 | 0 | 13 | todos | Smash |
| Fire Breath | 10 | 75 | 0 | 15 | Apoyo · Caballería · Encubierto · Qi Adept | **ignora** Def/Res |
| Ice Breath | 10 | 75 | 0 | 15 | Acorazado | media Def · congela |
| Flame Breath | 10 | 75 | 0 | 15 | Volador | media Def · **70 % de daño** · prende el área |
| Dark Breath | 10 | 75 | 0 | 15 | Místico | media **Res** (mágica) |
| Fog Breath | 10 | 75 | 0 | 15 | Dragón | media Def · efectiva contra dragón · niebla |

Cada unidad dispone de **tres**: las dos primeras más el aliento de su estilo, tal y como se
ve en el juego. Lo aplica `motor_analisis._arma_permitida_por_estilo` leyendo el campo
`_estilos` del arma. Todas menos Eternal Claw son Smash ("cannot follow up, or strike first
if initiating combat"), que el motor ya sabía manejar.

**Pendiente**: los **alcances** no están confirmados (se asume 1) y las partes de **área**
—prender fuego, congelar, crear niebla— necesitan el módulo `ataques_area`, como Blazing
Lion. El Fire Breath de Tiki se asume igual que sus hermanos (10/75/0/15): el
`IID_火のブレス` del datamine (12/100/0/5) es el aliento de los **wyrms**, otra arma.

### Las armas de Emblema se resolvían por nombre y cogían la genérica

Al pasar las armas de Emblema por su IID salió un fallo que llevaba tiempo ahí: el análisis
las buscaba **por nombre**, y varias comparten nombre con un arma normal. La Ridersbane de
Sigurd (`IID_シグルド_ナイトキラー`, Mt 10 / Hit 75 / Wt 6) se resolvía a la genérica
(`IID_ナイトキラー`, Mt 8 / Hit 70 / Wt 13): Louis pegaba 2 menos, acertaba 5 menos y cargaba
7 de peso de más. Los cuatro golden se regeneraron por esto — **172 combates, todos de
"Ridersbane (Emblema)"**, sin ninguno nuevo ni desaparecido.

