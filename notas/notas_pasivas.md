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
| `pasivas.py` | motor de habilidades: `sids_activos(unidad)` (recolección), `recopilar(unidad, ctx)` → `Modificadores` (acumulador, activas, procs, ignoradas). |
| `pasivas_temporales.py` | disparadores de give_sids "de 1 turno"; se integrará en `pasivas.py` (Fase 3). |
| `tests/golden/` | red de seguridad: escenarios reales + golden de todos los combates. |
| `tests/test_golden_combates.py` | compara el motor actual contra el golden; falla listando cada combate que cambia. |
| `tests/golden/cobertura_pasivas.py` | informe `notas/cobertura_pasivas.md`: qué entiende la DSL y qué vocabulario falta, por frecuencia real. |
| `tests/golden/sombra_pasivas.py` | informe `notas/sombra_pasivas.md`: aportación de los bloques a mano vs la del motor genérico, combate a combate. |

## Comandos

```
python -m pytest tests -q                          # todo (incluye golden)
python tests/golden/generar_golden.py              # regenerar golden (solo cambios intencionados y revisados)
python tests/golden/cobertura_pasivas.py           # regenerar notas/cobertura_pasivas.md
python tests/golden/sombra_pasivas.py              # regenerar notas/sombra_pasivas.md
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
- **Fase 2 — sustitución bloque a bloque** de las comprobaciones por nombre en
  `_stats_de_golpe` (lista "Implementadas a mano" del informe de cobertura + grupos de
  `notas/sombra_pasivas.md`), un bloque por commit, golden en verde o diferencia
  justificada. Pasar el terreno propio del atacante al contexto (hoy Trained to Kill
  mira el terreno del rival, tanto en el viejo como en el nuevo).
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
- El motor viejo activa varias pasivas por el **nombre de la unidad** (`'lapis' in nombre`,
  `'louis' in nombre`): en el informe sombra aparecen con aportación vieja 0 aunque el
  bloque a mano sí actúe (porque también actúa sin habilidades). Son las primeras a migrar.
- `Hit１００` (SID de tutorial en el Lance Fighter (6,10) de M007): `相手の命中率 = 100`,
  el juego garantiza que se le acierta. El motor viejo no lo aplica.
- Terreno (2026-09-19): tipos de casilla `curacion` (+30 Avo, +10 HP/turno, antirruptura)
  y `evasion` (solo +30 Avo) en `lector_de_mapas`; los **voladores no reciben Avo/Def del
  terreno** (`CalculadoraEngage._es_volador` en `_stats_de_golpe`). Pendiente Fase 2: la
  variable `地形回避` de la DSL sigue leyendo el terreno crudo (también para voladores).
- Item.xml `EquipSids` (2026-09-19): las armas otorgan SIDs al portador; ya se compilan
  (`equip_sids`) y viajan en `Arma.sids` y en el contexto de la DSL. `SID_２回行動` = Brave
  (Brave Sword/Lance/Axe/Bow, Nova, y las Body Arts Iron/Steel/Silver-Body): el iniciador
  pega dos veces por ataque (Stand=1), el defensor no; los Ataques de Emblema no doblan.
  Pendiente (Fase 2): `SID_追撃不可` (Thunder/Thoron sin follow-up), `SID_必中`, `SID_攻撃速度＋５`…
  siguen por nombre en el motor viejo.
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
