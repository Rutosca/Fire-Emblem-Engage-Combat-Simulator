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
