# Emblemas de DLC — datos recopilados de serenesforest.net

Fecha de la consulta: **2026-09-26**. Los Emblemas de DLC no están en el datamine, así que
esta página es la única fuente para sus habilidades. Este documento es **solo recopilación
y comparación**: no se ha tocado ningún dato del proyecto.

## Método y fiabilidad

- Se descargaron las 7 páginas con `curl` y se extrajeron las tablas del HTML tal cual.
  Las siete respondieron **HTTP 200**; ninguna URL falló ni hizo falta el índice para
  localizarlas (el índice `https://serenesforest.net/engage/emblems/` las confirma todas):

  | Emblema | URL | estado |
  |---|---|---|
  | Edelgard / Dimitri / Claude | `/engage/emblems/edelgard/` | 200 |
  | Tiki | `/engage/emblems/tiki/` | 200 |
  | Hector | `/engage/emblems/hector/` | 200 |
  | Veronica | `/engage/emblems/veronica/` | 200 |
  | Soren | `/engage/emblems/soren/` | 200 |
  | Camilla | `/engage/emblems/camilla/` | 200 |
  | Chrom / Robin | `/engage/emblems/chrom/` | 200 |

- **LEÍDO** = copiado literal de la web (columnas *Bond*, *Name*, *Description*, *Type*, *SP*).
  Las descripciones se dejan en **inglés literal**, con los corchetes de estilo de combate
  tal cual; los `/` de la web (saltos `<br>`) se han convertido en viñetas dentro de la celda.
- **INTERPRETACIÓN (mía)** = todo lo marcado como tal: la clasificación por categoría de
  motor y cualquier deducción. Va siempre señalado.
- Lo que la web **no** da y por tanto no se rellena aquí: identificadores internos (SID/IID),
  Mt/Hit/Crit/Wt de las armas de Emblema, y los datos de grabado **no están en las páginas de
  Emblema** (están en otra página del mismo sitio, ver §10).

### Clasificación usada (INTERPRETACIÓN mía, no viene de la web)

| cat. | significado |
|---|---|
| (a) | modificador de estadística o de daño durante el combate |
| (b) | efecto POR GOLPE o POSTERIOR al golpe (daño tras combate, curación, romper, estados) |
| (c) | aura sobre aliados cercanos |
| (d) | comando que gasta la acción de la unidad |
| (e) | efecto fuera del combate (movimiento, terreno, experiencia, oro, crecimientos…) |

Cuando una habilidad cae en varias, se listan todas y se explica por qué.

### Nota de la web sobre Weapon Sync (LEÍDO, página de Edelgard)

> Note: For Weapon Sync(+), these are considered the Emblems’ weapon type:
> - Sword: Marth, Sigurd, Roy, Leif, Lucina, Ike, Byleth, Corrin, Eirika, 13th Emblem, Chrom
> - Lance: Ephraim, Dimitri
> - Axe: Edelgard, Hector, Camilla
> - Bow: Lyn, Claude
> - Tome: Celica, Micaiah, Veronica, Soren
> - Special: Tiki
> - None: Robin

---

## 1. Edelgard / Dimitri / Claude (Emblema Tres Casas)

### Sincronías (LEÍDO)

| Vínculo | Nombre | Descripción literal | Tipo (web) | SP | Cat. (mía) |
|---|---|---|---|---|---|
| 1 | Gambit | `Effects change based on synced Emblem.` | Sync Skill (Cannot Inherit) | — | (d) — habilita los tres comandos Gambit de abajo |
| 1 | Friendly Rivalry | `At start of player phase, the Emblem will randomly switch to Edelgard, Dimitri, or Claude.` | Sync Skill (Cannot Inherit) | — | (e) — cambia de Emblema al inicio de fase, fuera de combate |
| 3 | Lineage | `Increases unit’s earned experience by 20%.` | Sync Skill (Can Inherit) | 150 | (e) |
| 12 | Weapon Sync | `If unit initiates combat using same weapon type as the synced Emblem, grants Atk+5. If engaged, grants Atk+5 regardless of weapon type. [See note above.]` | Sync Skill (Can Inherit) | 3000 | (a) |
| 17 | Weapon Sync+ | `If unit initiates combat using same weapon type as the synced Emblem, grants Atk+7. If engaged, grants Atk+7 regardless of weapon type. [See note above.]` | Sync Skill (Can Inherit) | 5000 | (a) |

### Comandos ligados a Gambit y a Combat Arts (LEÍDO; tipo web = *Command Skill*, vínculo 1)

| Nombre | Descripción literal | Cat. (mía) |
|---|---|---|
| Flame Gambit | `Use when synced with Edelgard to attack a foe, then set the target foe’s space and nearby spaces on fire.` | (d) + (b) + (e) terreno |
| Shield Gambit | `Use when synced with Dimitri to negate damage from first attacks of ranged foes targeting unit in next enemy phase.` | (d) + (a) en la fase enemiga siguiente |
| Poison Gambit | `Use when synced with Claude to attack a foe, then poison target and all foes adjacent to it after combat.` | (d) + (b) |
| Raging Storm | `After combat, take another action. (Spend 3 turns.)` | (d) + (e) acción extra |
| Atrocity | `Attack at double weapon’s Mt. (Spend 1 turn.)` | (d) + (a) |
| Fallen Star | `Avoid foe’s attacks during next combat. (Spend 1 turn.)` | (d) + (a) |

> La web **no dice** a qué Emblema pertenece cada arte de combate (Raging Storm / Atrocity /
> Fallen Star); solo los marca como *Command Skill* de vínculo 1. INTERPRETACIÓN mía, por los
> juegos de origen: Atrocity ↔ Aymr (Edelgard), Raging Storm ↔ Areadbhar (Dimitri),
> Fallen Star ↔ Failnaught (Claude). **No verificado en la web.**

### Habilidad de Fusión (LEÍDO)

| Vínculo | Nombre | Descripción literal | Cat. (mía) |
|---|---|---|---|
| 1 | Combat Arts | `Enables use of Edelgard, Dimitri, or Claude’s Combat Art. Spends some remaining engage turns.` · `[Dragon] +10% damage.` · `[Covert] Avo+20.` | (d) habilita comandos + (a) los bonos de estilo |

### Ataques de Emblema (LEÍDO)

| Nombre | Descripción literal | Tipo (web) |
|---|---|---|
| Houses Unite | `Use to attack with Aymr, Areadbhar, and Failnaught at 50% damage.` · `[Dragon] +10% damage.` · `[Cavalry] +10% damage with Areadbhar.` · `[Covert] +10% damage with Failnaught.` · `[Armored] +10% damage with Aymr.` · `[Qi Adept] Breaks foe.` | Engage Attack (vínculo 1) |
| Houses Unite+ | `Use to attack with Aymr, Areadbhar, and Failnaught at 50% damage. After combat, take another action.` · `[Dragon] +10% damage.` · `[Cavalry] +10% damage with Areadbhar.` · `[Covert] +10% damage with Failnaught.` · `[Armored] +10% damage with Aymr.` · `[Qi Adept] Breaks foe.` | Engage Attack **(Requires adjacent Byleth)**, vínculo 1 |

Cat. (mía): (d) comando + (a) modificadores por estilo + (b) el Break de [Qi Adept] y la
acción extra de la variante +.

### Armas de Emblema (LEÍDO)

| Vínculo | Nombre | Descripción literal |
|---|---|---|
| 1 | Aymr (Edelgard) | `Axe of Emblem Edelgard. Smashes foes. Cannot follow up, or strike first if initiating combat. Eff: Dragon.` |
| 10 | Areadbhar (Dimitri) | `Lance wielded by Emblem Dimitri. If user initiates combat, grants Mt+50%.` |
| 15 | Failnaught (Claude) | `Bow wielded by Emblem Claude. If user initiates combat, grants Avo+20. Effective: Dragon, Flying.` |

### Heredables (LEÍDO)

| Vínculo | Nombre | SP | Descripción literal | Cat. (mía) |
|---|---|---|---|---|
| 2 | Assembly Gambit | 1500 | `Use to attack an adjacent foe, then move 1 space away after combat. Target foe moves to unit’s previous space.` | (d) + (e) movimiento |
| 3 | Str/Dex +1 | 700 | `Grants Str+1 and Dex+1.` | (a) |
| 4 | Bow Guard 1 | 200 | `If foe is equipped with a bow, unit takes 1 less damage during combat.` | (a) |
| 7 | Str/Dex +2 | 1600 | `Grants Str+2 and Dex+2.` | (a) |
| 8 | Bow Guard 2 | 400 | `…unit takes 2 less damage during combat.` | (a) |
| 12 | Str/Dex +3 | 4200 | `Grants Str+3 and Dex+3.` | (a) |
| 14 | Bow Guard 3 | 600 | `…3 less damage…` | (a) |
| 16 | Str/Dex +4 | 6000 | `Grants Str+4 and Dex+4.` | (a) |
| 17 | Bow Guard 4 | 800 | `…4 less damage…` | (a) |
| 18 | Str/Dex +5 | 8400 | `Grants Str+5 and Dex+5.` | (a) |
| 19 | Bow Guard 5 | 1000 | `…5 less damage…` | (a) |

Desbloqueos (*Unlock*, LEÍDO, sin efecto de combate): 5 Skill Inheritance, 6 Axe Prof.,
9 Lance Prof., 13 Bow Prof.

---

## 2. Tiki

### Sincronías (LEÍDO)

| Vínculo | Nombre | Descripción literal | SP | Cat. (mía) |
|---|---|---|---|---|
| 1 | Starsphere | `Grants unit enhanced stat growth when leveling up. [Adds +15% to final growth rates.]` | 1500 | (e) |
| 3 | Geosphere | `At start of player phase, if there are allies adjacent to unit, grants Def/Res+3 to unit and those allies for 1 turn.` | 500 | (c) + (a) — aura al inicio de fase, también al portador |
| 8 | Lifesphere | `If unit uses Wait without attacking or using items, restores 20 HP and heals status effects.` | 1000 | (e) — se dispara al Esperar, fuera de combate |
| 10 | Lightsphere | `If unit initiates combat, halves chance of receiving critical hit from foe.` | 900 | (a) |
| 14 | Lifesphere+ | `If unit uses Wait without attacking or using items, restores 30 HP and heals status effects.` | 2000 | (e) |
| 16 | Geosphere+ | `At start of player phase, if there are allies adjacent to unit, grants Def/Res+5 to unit and those allies for 1 turn.` | 1000 | (c) + (a) |
| 19 | Lifesphere++ | `If unit uses Wait without attacking or using items, restores 40 HP and heals status effects.` | 3000 | (e) |

Todas *Sync Skill (Can Inherit)*.

### Habilidad de Fusión (LEÍDO)

| Vínculo | Nombre | Descripción literal | Cat. (mía) |
|---|---|---|---|
| 1 | Draconic Form | `Unit transforms into and fights as a dragon while engaged. Grants +10 to max HP and +5 to Bld and all basic stats.` · `[Armored] Negates terrain damage.` · `[Mystical] Grants an extra Res+5.` | (a) + (e) el Armored anula daño de terreno |

### Ataques de Emblema (LEÍDO)

| Nombre | Descripción literal | Tipo (web) |
|---|---|---|
| Divine Blessing | `Use to grant 1 ally a Revival Stone.` · `[Dragon] Restore 20 HP to ally.` · `[Qi Adept] Heal their status effects.` | Engage Attack (vínculo 1) |
| Divine Blessing+ | `Use to grant 1 ally a Revival Stone. If ally is not synced, fully restore HP. If ally is synced, +3 to engage meter. If ally is engaged, restore engage turns.` · `[Dragon] Restore 20 HP to ally.` · `[Qi Adept] Heal their status effects.` | Engage Attack **(Requires adjacent Marth)**, vínculo 1 |

Cat. (mía): (d) comando de apoyo, sin combate; sus efectos son (e) (piedra resurrectora,
medidor de Fusión) y (b) curación/estados sobre el aliado.

### Armas de Emblema (LEÍDO) — **todas a vínculo 1**, cada aliento restringido por estilo

| Nombre | Descripción literal | Tipo (web) = restricción de estilo |
|---|---|---|
| Eternal Claw | `Claw attack used by Emblem Tiki. Easily inflicts fatal wounds.` | Engage Weapon (sin restricción) |
| Tail Smash | `Smash attack used by Emblem Tiki. Smashes foes. Cannot follow up, or strike first if initiating combat.` | Engage Weapon (sin restricción) |
| Fire Breath | `A scorching breath attack. Ignores foe’s Def/Res.` | Engage Weapon **(Backup, Cavalry, Covert and Qi Adept)** |
| Ice Breath | `Strikes foes in area at half Def. Freezes foes. Cannot follow up, or strike first if initiating combat.` | Engage Weapon **(Armor)** |
| Flame Breath | `Sets area on fire. Strikes foes at 70% damage and half Def. Cannot follow up, or strike first if initiating combat.` | Engage Weapon **(Flying)** |
| Dark Breath | `Magically strikes foes in area at half Res. Cannot follow up, or strike first if initiating combat.` | Engage Weapon **(Mystical)** |
| Fog Breath | `Strikes foes in area at half Def. Eff: Dragon. Creates fog. Cannot follow up, or strike first if initiating combat.` | Engage Weapon **(Dragon)** |

### Heredables (LEÍDO)

| Vínculo | Nombre | SP | Descripción literal |
|---|---|---|---|
| 2 / 7 / 12 / 15 / 18 | HP/Lck +2 / +4 / +6 / +8 / +10 | 200 / 600 / 1100 / 1900 / 3600 | `Grants HP+N and Lck+N.` |
| 4 / 9 / 13 / 17 / 19 | Special Guard 1…5 | 200 / 400 / 600 / 800 / 1000 | `If foe is equipped with a special attack, unit takes N less damage during combat.` |

Cat. (mía): las dos familias son (a). Desbloqueos: 5 Skill Inheritance, 6 Arts Prof.

---

## 3. Hector

### Sincronías (LEÍDO)

| Vínculo | Nombre | Descripción literal | Tipo (web) | SP | Cat. (mía) |
|---|---|---|---|---|---|
| 1 | Quick Riposte | `If unit’s HP is 80% or more and foe initiates combat, unit will always follow up (if weapon allows).` | Sync (Can Inherit) | 2000 | (a) — altera la secuencia del combate |
| 3 | Adaptability | `When hit by a foe’s attack, grants Def+2 for a physical attack or Res+2 for a magical attack after combat. Lasts until end of battle, or until activated again.` | Sync (Can Inherit) | 350 | (b) + (a) — se concede TRAS el combate y persiste |
| 8 | Heavy Attack | `When making a physical attack, if an equipped weapon’s Wt exceeds unit’s Bld, adds excess as damage. (Max +5)` | Sync (Can Inherit) | 3000 | (a) |
| 12 | Piercing Glare | `Use when HP is full to consume 20% of max HP and prevent foes from entering the 4 spaces diagonally adjacent to unit for 1 turn.` | Sync Skill (**Cannot Inherit**) | — | (d) + (e) control de casillas |
| 16 | Quick Riposte+ | `If unit’s HP is 60% or more and foe initiates combat, unit will always follow up (if weapon allows).` | Sync (Can Inherit) | 3000 | (a) |
| 19 | Adaptability+ | `When hit by a foe’s attack, grants Def+3 for a physical attack or Res+3 for a magical attack after combat. Lasts until end of battle, or until activated again.` | Sync (Can Inherit) | 700 | (b) + (a) |

### Habilidad de Fusión (LEÍDO)

| Vínculo | Nombre | Descripción literal | Cat. (mía) |
|---|---|---|---|
| 1 | Impenetrable | `If foe initiates combat, grants Def/Res+30% during combat.` · `[Dragon] Ddg+50%.` · `[Cavalry] Grants immunity to freeze.` · `[Armored] Grants Def+50% instead of +30%.` · `[Flying] Grants Res+50% instead of +30%.` | (a), salvo la inmunidad a congelación de [Cavalry] que es (e)/estado |

### Ataques de Emblema (LEÍDO)

| Nombre | Descripción literal | Tipo (web) |
|---|---|---|
| Storm’s Eye | `Grants immunity to break. Foe cannot follow up. Unit follows up. Lasts 1 turn. Sword/axe only.` · `[Dragon] Prevent one critical hit.` · `[Backup] Crit+20.` · `[Covert] Avo+30.` | Engage Attack (vínculo 1) |
| Storm’s Eye+ | `Grants immunity to break. Foe cannot follow up. Unit counters before foe’s first attack and follows up. Lasts 1 turn. Sword/axe only.` · `[Dragon] Prevent one critical hit.` · `[Backup] Crit+20.` · `[Covert] Avo+30.` | Engage Attack **(Requires adjacent Lyn)**, vínculo 1 |

Cat. (mía): (d) comando que deja un buff de 1 turno, con efectos (a) sobre la secuencia y
los stats del combate.

### Armas de Emblema (LEÍDO)

| Vínculo | Nombre | Descripción literal |
|---|---|---|
| 1 | Wolf Beil | `Axe wielded by Emblem Hector. Effective: Cavalry, Armored.` |
| 10 | Runesword | `Magic sword of Emblem Hector. Can strike close or at range. Restore HP equal to 50% of damage dealt.` |
| 15 | Armads | `Lightning-charged axe wielded by Emblem Hector. Grants Def+5. Effective: Dragon.` |

### Heredables (LEÍDO)

| Vínculo | Nombre | SP | Descripción literal |
|---|---|---|---|
| 2 / 7 / 12 / 14 / 18 | Str/Def +1…+5 | 700 / 1600 / 4200 / 6000 / 8400 | `Grants Str+N and Def+N.` |
| 4 / 9 / 13 / 17 / 19 | Axe Guard 1…5 | 200 / 400 / 600 / 800 / 1000 | `If foe is equipped with an axe, unit takes N less damage during combat.` |

Cat. (mía): ambas (a). Desbloqueos: 6 Axe Prof. **La página de Hector NO lista
“Skill Inheritance” a vínculo 5** (salta del 4 al 6); en los otros seis sí aparece.
No es un dato del JSON, solo una laguna de la web.

---

## 4. Veronica

### Sincronías (LEÍDO)

| Vínculo | Nombre | Descripción literal | SP | Cat. (mía) |
|---|---|---|---|---|
| 1 | Reprisal | `If unit’s HP is not full, adds 30% of lost HP to Atk.` | 5000 | (a) |
| 3 | Book of Worlds | `Book of Worlds advances 1 stage (to max 5) for each consecutive round that unit uses Wait. Reverts to base stage if unit triggers the effect.` · `[Book I: Seal] If unit initiates combat, freezes foe after combat.` · `[Book II: Flame] If unit initiates combat, freezes foe and sets foe’s space on fire after combat.` · `[Book III: Death] If unit initiates combat, deals 10 damage, freezes foe, and sets foe’s space on fire after combat.` · `[Book IV: Dream] If unit initiates combat, restores HP equal to damage dealt during combat, then deals 10 damage, freezes foe, and sets foe’s space on fire after combat.` · `[Book V: Science] If unit initiates combat, restores HP to self and adjacent allies equal to damage dealt during combat, then deals 10 damage, freezes foe, and sets foe’s space on fire after combat.` | 300 | (b) puro (todo es “after combat”) + (e) terreno en llamas + (c) la curación a adyacentes del Libro V. Necesita **estado propio** (fase 1-5) que sube al Esperar |
| 8 | Level Boost | `When unit defeats a foe of a higher level, grants Lvl+1 until the end of battle. (Max +3)` | 300 | (b) → (a) indirecto: el nivel efectivo sube tras matar |
| 13 | SP Conversion | `Grants +20 SP for each defeated foe. Triggers even without a ring or bracelet equipped.` | 300 | (e) |
| 18 | Reprisal+ | `If unit’s HP is not full, adds 50% of lost HP to Atk.` | 6000 | (a) |

Todas *Sync Skill (Can Inherit)*. Ojo: los corchetes `[Book I…V]` **no** son estilos de
combate, son las fases del Libro (INTERPRETACIÓN mía, evidente por el texto).

### Habilidad de Fusión (LEÍDO)

| Vínculo | Nombre | Descripción literal | Cat. (mía) |
|---|---|---|---|
| 1 | Contract | `Use to grant another action to an adjacent ally who has already acted. (Ally cannot move.)` · `[Dragon] Grants Str/Mag/Def/Res+2 to ally during action.` · `[Backup] Unit participates in chain attack during ally action.` · `[Covert] Grants Hit/Avo+30 to ally during action.` | (d) comando + (e) acción extra a un aliado + (a) sobre el aliado durante esa acción |

### Ataque de Emblema (LEÍDO)

| Nombre | Descripción literal | Tipo (web) |
|---|---|---|
| Summon Hero | `Use to summon a random unit.` · `[Dragon] Summons a powerful unit. [Removes 3-stars from pool. The 3-star rate is added to 4-star rate.]` · `[Backup] Summoned unit has the “Dual Strike” skill.` · `[Cavalry] Summoned unit gets Mov+1.` | Engage Attack (vínculo 1) |

Cat. (mía): (d) + (e). La web **no lista variante “+”** para Veronica: es el único de los
siete sin Engage Attack `+`. El listado de invocables está en otra página del sitio
(*Veronica’s Summons*), no consultada aquí.

### Armas de Emblema (LEÍDO)

| Vínculo | Nombre | Descripción literal |
|---|---|---|
| 1 | Hliðskjálf | `A staff wielded by Emblem Veronica. If user initiates combat, foe cannot counterattack.` |
| 10 | Fortify+ | `A staff wielded by Emblem Veronica. Heals HP and status effects for all allies within a 7-space radius.` |
| 15 | Élivágar | `Powerful magic wielded by Emblem Veronica. Nullifies basic stat bonuses on target for 1 turn after combat.` |

### Heredables (LEÍDO)

| Vínculo | Nombre | SP | Descripción literal |
|---|---|---|---|
| 2 / 7 / 12 / 14 / 18 | Mag/Dex +1…+5 | 700 / 1600 / 4200 / 6000 / 8400 | `Grants Mag+N and Dex+N.` |
| 4 / 9 / 13 / 17 / 19 | Knife Guard 1…5 | 200 / 400 / 600 / 800 / 1000 | `If foe is equipped with a knife, unit takes N less damage during combat.` |

Cat. (mía): ambas (a). Desbloqueos: 5 Skill Inheritance, 6 Staff Prof., 16 Tome Prof.

---

## 5. Soren

### Sincronías (LEÍDO)

| Vínculo | Nombre | Descripción literal | SP | Cat. (mía) |
|---|---|---|---|---|
| 1 | Assign Decoy | `Use to make one chosen ally more likely to be targeted by enemies for 1 turn. Effect is removed after ally is targeted by or otherwise damaged by foes 3 times.` | 1500 | (d) + (e) — toca la IA de selección de objetivo, no el combate |
| 4 | Anima Focus | `When using tomes, unit inflicts Def-3 with fire, Hit-20 with thunder, or Mov-2 with wind magic for 1 turn.` | 800 | (b) debuff al rival tras golpear (el Mov-2 además es (e)) |
| 9 | Keen Insight | `When unit deals Effective damage, deal +5 damage.` | 1500 | (a) |
| 13 | Block Recovery | `When attacking a broken foe with a tome, grants a chance the foe will remain broken. Chance increases with high Spd. [Trigger% = (Spd – foe’s Spd) x 5, max 50]` | 1500 | (b) |
| 18 | Keen Insight+ | `When unit deals Effective damage, deal +7 damage.` | 3000 | (a) |

Todas *Sync Skill (Can Inherit)*.

### Habilidad de Fusión (LEÍDO)

| Vínculo | Nombre | Descripción literal | Cat. (mía) |
|---|---|---|---|
| 1 | Flare | `When attacking with tomes, inflicts Res-20% on foe, and unit recovers 50% of damage dealt.` · `[Dragon] Critical rate is doubled.` · `[Mystical] Extra -10% to foe’s Res.` · `[Qi Adept] Unit recovers 100% of damage dealt instead.` | (a) el Res-% y el crítico + (b) la recuperación por daño hecho |

### Ataques de Emblema (LEÍDO)

| Nombre | Descripción literal | Tipo (web) |
|---|---|---|
| Cataclysm | `Use to attack foes in an area with fire, thunder and wind magic at 40% damage. Wind is effective: Flying.` · `[Dragon] Sets terrain on fire.` · `[Mystical] +10% damage.` · `[Qi Adept] 20% chance of breaking target.` | Engage Attack (vínculo 1) |
| Cataclysm+ | **texto idéntico al anterior en la web** (no describe ninguna mejora) | Engage Attack **(Requires adjacent Ike)**, vínculo 1 |

Cat. (mía): (d) + (a) + (b) (romper). **La web no dice en qué mejora Cataclysm+**: repite
literalmente la descripción base. Dato ausente, no rellenado.

### Armas de Emblema (LEÍDO)

| Vínculo | Nombre | Descripción literal |
|---|---|---|
| **1** | Bolting | `Long-range thunder magic wielded by Emblem Soren. Cannot follow up.` |
| 10 | Reflect | `Staff of Emblem Soren. Allies within 2 spaces gain “deals 50% of magic damage taken back to foe” for 1 turn.` |
| 15 | Rexcalibur | `Powerful wind magic wielded by Emblem Soren. Effective: Flying.` |

Reflect es (c) + (b) según mi clasificación: reparte un efecto de contragolpe a los aliados
a 2 casillas.

### Heredables (LEÍDO)

| Vínculo | Nombre | SP | Descripción literal |
|---|---|---|---|
| 2 / 7 / 12 / 14 / 18 | Mag/Res +1…+5 | 700 / 1600 / 4200 / 6000 / 8400 | `Grants Mag+N and Res+N.` |
| 3 / 8 / 13 / 17 / 19 | Magic Guard 1…5 | 200 / 400 / 600 / 800 / 1000 | `If foe is equipped with a tome, unit takes N less damage during combat.` |

Cat. (mía): ambas (a). Desbloqueos: 5 Skill Inheritance, 6 Knife Prof., 12 Staff Prof.,
16 Tome Prof.

---

## 6. Camilla

### Sincronías (LEÍDO)

| Vínculo | Nombre | Descripción literal | Tipo (web) | SP | Cat. (mía) |
|---|---|---|---|---|---|
| 1 | Dragon Vein | `Use to add a special effect to certain spaces.` · `[Dragon] Choose any Vein effect.` · `[Backup] Creates stone pillars that increase Def/Res.` · `[Cavalry] Creates water that decreases Avo.` · `[Covert] Creates smoke that decreases Def/Avo.` · `[Armored] Creates vines that grant immunity to break.` · `[Flying] Creates healing glow that restores HP.` · `[Mystical] Creates flames that inflict damage.` · `[Qi Adept] Creates ice floor that increases movement.` | Sync Skill (**Cannot Inherit**) | — | (d) + (e) terreno |
| 4 | Decisive Strike | `If unit initiates combat and lands a critical, deals 5 damage to foe after combat.` | Sync (Can Inherit) | 500 | (b) |
| 8 | Detoxify | `Cures poison at start of turn.` | Sync (Can Inherit) | 250 | (e) |
| 12 | Groundswell | `After unit acts or waits in flames, miasma, or similar terrain effect, unit clears effect and recovers 10 HP.` | Sync (Can Inherit) | 500 | (e) |
| 18 | Decisive Strike+ | `If unit initiates combat and lands a critical, deals 10 damage to foe after combat.` | Sync (Can Inherit) | 1000 | (b) |

### Habilidad de Fusión (LEÍDO)

| Vínculo | Nombre | Descripción literal | Cat. (mía) |
|---|---|---|---|
| 1 | Soar | `Grants Mov+2. Unit can cross terrain as if flying.` · `[Dragon] If unit initiates combat, deals damage to foes within 2 spaces equal to 10% of their max HP after combat.` · `[Cavalry] Grants an extra Mov+2.` · `[Flying] Grants an extra Mov+1.` | (e) movimiento/terreno + (b) el daño en área de [Dragon] |

### Ataques de Emblema (LEÍDO)

| Nombre | Descripción literal | Tipo (web) |
|---|---|---|
| Dark Inferno | `Use to deal damage to foes on certain spaces near unit and set those spaces on fire.` · `[Dragon] Increases area of effect.` · `[Mystical] +20% damage.` · `[Qi Adept] Adds Glow to adjacent spaces.` | Engage Attack (vínculo 1) |
| Dark Inferno+ | **texto idéntico al anterior en la web** | Engage Attack **(Requires adjacent Corrin)**, vínculo 1 |

Cat. (mía): (d) + (b) daño en área + (e) terreno. Igual que con Cataclysm+, **la web no
dice qué añade la variante +**.

### Armas de Emblema (LEÍDO)

| Vínculo | Nombre | Descripción literal |
|---|---|---|
| **1** | Bolt Axe | `Magic axe wielded by Emblem Camilla. Can strike close or at range.` |
| 10 | Lightning | `Magic wielded by Emblem Camilla. If user initiates combat, attacks twice.` |
| 15 | Camilla’s Axe | `Axe wielded by Emblem Camilla. Grants Res+10 and deals extra damage = foe’s Res-Def.` |

### Heredables (LEÍDO)

| Vínculo | Nombre | SP | Descripción literal |
|---|---|---|---|
| **1** / 3 / 9 / 14 / 18 | Spd/Res +1…+5 | 250 / 700 / 1200 / 2400 / 4800 | `Grants Spd+N and Res+N.` |
| 2 / 7 / 13 / 16 / 19 | Lance Guard 1…5 | 200 / 400 / 600 / 800 / 1000 | `If foe is equipped with a lance, unit takes N less damage during combat.` |

Camilla es el único de los siete cuyo primer heredable sale ya a vínculo **1**.
Desbloqueos: 5 Skill Inheritance, 6 Axe Prof., 17 Tome Prof.

---

## 7. Chrom / Robin

### Sincronías (LEÍDO)

| Vínculo | Nombre | Descripción literal | SP | Cat. (mía) |
|---|---|---|---|---|
| 1 | Surprise Attack | `If unit initiates combat from terrain that provides an Avo bonus, foe cannot counterattack.` | 3000 | (a) — condición de terreno propio, efecto en combate |
| 4 | Rally Spectrum | `Use to grant adjacent allies +3 to all seven basic stats for 1 turn.` | 1500 | (d) + (c) |
| 8 | Brute Force | `While making a physical attack, critical hits deal increased damage. [Damage increased by one third.]` | 1500 | (a) |
| 13 | Charm | `If unit’s attack triggers a chain attack, increases chain attack accuracy to 90%.` | 800 | (a) sobre el ataque en cadena |
| 18 | Rally Spectrum+ | `Use to grant allies within 2 spaces +3 to all seven basic stats for 1 turn.` | 2000 | (d) + (c) |

Todas *Sync Skill (Can Inherit)*.

### Habilidad de Fusión (LEÍDO)

| Vínculo | Nombre | Descripción literal | Cat. (mía) |
|---|---|---|---|
| 1 | Other Half | `If unit initiates combat, Robin chain attacks. Grants Mag+10 while engaged.` · `[Dragon] Robin chain attacks 2 times.` · `[Backup] Guaranteed hit with chain attack.` · `[Covert] Grants Mov+1 while engaged.` | (a) + golpes extra por combate (b) + (e) el Mov de [Covert] |

### Ataques de Emblema (LEÍDO)

| Nombre | Descripción literal | Tipo (web) |
|---|---|---|
| Giga Levin Sword | `Use to attack with a magic sword. Magic attack that uses physical attack power. Swords only.` · `[Dragon] Deals extra damage = half of Str.` · `[Flying] Deals extra damage = Bld.` · `[Mystical] Deals extra damage = half of Mag.` | Engage Attack (vínculo 1) |
| Giga Levin Sword+ | `Use to attack with a magic sword. Magic attack that uses physical attack power. Swords only. Adjacent allies chain attack.` · `[Dragon] Deals extra damage = half of Str.` · `[Flying] Deals extra damage = Bld.` · `[Mystical] Deals extra damage = half of Mag.` | Engage Attack **(requires adjacent Lucina)**, vínculo 1 |

Cat. (mía): (d) + (a).

### Armas de Emblema (LEÍDO)

| Vínculo | Nombre | Descripción literal |
|---|---|---|
| 1 | Levin Sword (Robin) | `Magic sword wielded by Emblem Robin. Can hit foes with magic lightning from a distance.` |
| 10 | Thoron (Robin) | `Powerful lightning magic wielded by Emblem Robin.` |
| 15 | Falchion (Chrom) | `A legendary sword wielded by Emblem Chrom. Effective: Dragon.` |

### Heredables (LEÍDO)

| Vínculo | Nombre | SP | Descripción literal |
|---|---|---|---|
| 2 / 7 / 12 / 14 / 18 | Spd/Dex +1…+5 | 250 / 700 / 1200 / 2400 / 4800 | `Grants Spd+N and Dex+N.` |
| 3 / 9 / 13 / 17 / 19 | Sword Guard 1…5 | 200 / 400 / 600 / 800 / 1000 | `If foe is equipped with a sword, unit takes N less damage during combat.` |

Cat. (mía): ambas (a). Desbloqueos: 5 Skill Inheritance, 6 Sword Prof., 16 Tome Prof.

---

## 8. Comparación contra `json/dlc_emblems_canon.json`

Comparación hecha a máquina: para cada fila de la web se buscó el primer nivel de vínculo en
que el JSON expone ese nombre, por categoría (*Sync Skill* → `synchro_skills`,
*Engage Skill* → `engage_skills`, *Engage Weapon* → `engage_items`,
*Inheritable Skill* → `inheritance_skills`), comparando además el SP.

### 8.1 Discrepancias reales (LEÍDO vs JSON)

| # | Emblema | Qué | Serenes | JSON | gravedad |
|---|---|---|---|---|---|
| 1 | Soren | Arma de Emblema **Bolting** | vínculo **1** | vínculo **2** | el arma se desbloquea un nivel más tarde en el proyecto |
| 2 | Camilla | Arma de Emblema **Bolt Axe** | vínculo **1** | vínculo **2** | ídem |

Verificado sobre el HTML crudo, no sobre el texto convertido: la fila de `Bolting` en
`soren.html` y la de `Bolt Axe` en `camilla.html` tienen ambas `1` en la columna *Bond*.
**Ojo con la dirección del error**: el encargo decía que estas dos figuraban a vínculo 1 en
el JSON y que Serenes decía 2; es al revés. Hoy el JSON dice 2 y Serenes dice 1. Si alguien
ya "corrigió" el JSON a 2, esa corrección contradice a Serenes (y a las demás armas: en los
siete Emblemas el patrón de la web es **1 / 10 / 15**, sin excepción).

**Nada más difiere.** Concretamente coinciden al 100 %:

- Nombres y niveles de **todas** las sincronías, incluidas las variantes `+`
  (Weapon Sync 12 / Weapon Sync+ 17, Quick Riposte+ 16, Adaptability+ 19, Lifesphere+ 14,
  Lifesphere++ 19, Geosphere+ 16, Reprisal+ 18, Keen Insight+ 18, Decisive Strike+ 18,
  Rally Spectrum+ 18) y las no heredables (Gambit, Friendly Rivalry, Piercing Glare 12,
  Dragon Vein).
- Las 7 habilidades de Fusión, todas a vínculo 1.
- Las demás armas de Emblema: vínculos 1 / 10 / 15 en los siete (incluidas las 7 armas de
  Tiki a vínculo 1).
- Las 10 heredables de cada Emblema: **nombre, vínculo y coste en SP**, uno por uno
  (incluido el caso raro de Camilla, con Spd/Res +1 a vínculo 1 por 250 SP).
- Los bonos de estadística por nivel: comparadas las tres columnas de cada Emblema nivel a
  nivel (1-20, rellenando los niveles que la web omite). **Cero diferencias** en los siete.
- Los grabados (ver §10): los seis valores de los siete Emblemas coinciden con la web.

### 8.2 Datos de la web que el JSON no modela (no son errores, pero faltan para implementar)

1. **Ataques de Emblema**: `dlc_emblems_canon.json` no tiene ningún campo para ellos
   (`grep` de los siete nombres en el JSON → 0 coincidencias). Viven a mano en
   `catalogo_loader.py` (`ATAQUES_ENGAGE_MAP` / `ATAQUES_ENGAGE_CONFIG`). Según la web todos
   se desbloquean a **vínculo 1**.
2. **Las variantes `+` de los Ataques de Emblema no existen en el código** (búsqueda de
   `Houses Unite+`, `Storm's Eye+`, `Cataclysm+`, `Dark Inferno+`, `Divine Blessing+`,
   `Giga Levin Sword+` fuera de `scratch/` → 0 coincidencias). La web da para cada una el
   Emblema que hay que tener adyacente: Byleth (Edelgard), Marth (Tiki), Lyn (Hector),
   Ike (Soren), Corrin (Camilla), Lucina (Chrom); Veronica no tiene variante `+`.
   De las seis, solo tres describen la mejora (Houses Unite+ = acción extra;
   Storm’s Eye+ = contraataca antes del primer golpe rival; Divine Blessing+ = cura /
   medidor / turnos de Fusión; Giga Levin Sword+ = ataque en cadena de los adyacentes);
   Cataclysm+ y Dark Inferno+ repiten el texto base en la web.
3. **Comandos (Command Skill) de Edelgard**: Flame / Shield / Poison Gambit, Raging Storm,
   Atrocity, Fallen Star, todos a vínculo 1, no están en el JSON.
4. **Restricción por estilo de los alientos de Tiki**: la web pone el estilo en la columna
   *Type* (Fire Breath → Backup/Cavalry/Covert/Qi Adept; Ice Breath → Armor;
   Flame Breath → Flying; Dark Breath → Mystical; Fog Breath → Dragon). El JSON da las 7
   armas a todo el mundo desde vínculo 1 y no encontré filtro por estilo en el código
   (`grep` de `FOG_BREATH` / `ICE_BREATH` + estilo → 0). INTERPRETACIÓN mía: la unidad solo
   debería poder equipar el aliento de su estilo, más Eternal Claw y Tail Smash.
5. **Desbloqueos (*Unlock*)**: Skill Inheritance (vínculo 5) y las competencias de arma
   (Axe/Lance/Bow/Tome/Staff/Knife/Sword/Arts Prof.) no están en el JSON. Afectan a cambios
   de clase, no al combate.

### 8.3 Incoherencias internas del propio JSON (no contra la web)

Las listas resumen de nivel superior (`synchro_skills`, `engage_items`) están incompletas
frente a lo que sí guarda `bond_levels`, que es lo que de verdad usa `catalogo_loader.py`
(para sincronías lee `bond_data["synchro_skills"]` y solo cae a la lista superior si no hay
`bond_data`). Aun así conviene cuadrarlas, porque `cargador_dispos.py:512` sí lee
`emblema_info["engage_items"]` de nivel superior:

| Emblema | Lista superior | No incluye |
|---|---|---|
| Edelgard | `synchro_skills` | Weapon Sync, Weapon Sync+ |
| Hector | `synchro_skills` | Piercing Glare, Quick Riposte+, Adaptability+ |
| Hector | `engage_items` | **Armads** |
| Veronica | `synchro_skills` | SP Conversion, Reprisal+ |
| Veronica | `engage_items` | **Élivágar** |
| Soren | `synchro_skills` | Block Recovery |
| Chrom | `synchro_skills` | Charm, Rally Spectrum+ |
| Chrom | `engage_items` | **Falchion (Chrom)** |

(Tiki y Camilla las tienen completas.)

---

## 9. Resumen de clasificación para el motor (INTERPRETACIÓN mía)

Habilidades que el motor de combate actual debería poder resolver con lo que ya hay
(categoría (a), sumas/multiplicadores dentro del golpe):

> Weapon Sync/+, Heavy Attack, Quick Riposte/+, Impenetrable, Reprisal/+, Keen Insight/+,
> Lightsphere, Surprise Attack, Brute Force, Charm, Draconic Form, Flare (la parte Res-%),
> Other Half (Mag+10), y las 70 heredables Str/Dex, HP/Lck, Str/Def, Mag/Dex, Mag/Res,
> Spd/Res, Spd/Dex y las cinco familias *Guard*.

Habilidades que necesitan **efecto por golpe / posterior al golpe** (Fase 3 del plan de
pasivas, categoría (b)):

> Book of Worlds (los cinco libros), Decisive Strike/+, Anima Focus, Block Recovery,
> Adaptability/+ (se concede tras el combate), Level Boost, Flare (recuperación por daño),
> Runesword, Soar [Dragon], Élivágar, Poison Gambit, Houses Unite [Qi Adept].

Auras sobre aliados cercanos, categoría (c):

> Geosphere / Geosphere+, Rally Spectrum / Rally Spectrum+, Reflect, Fortify+,
> Book of Worlds [Book V] (curación a adyacentes).

Comandos que gastan la acción, categoría (d):

> los 7 Ataques de Emblema (+ sus 6 variantes `+`), Contract, Assign Decoy, Dragon Vein,
> Piercing Glare, Rally Spectrum/+, Assembly Gambit y los 6 Command Skill de Edelgard.

Fuera del combate, categoría (e):

> Lineage, Starsphere, Lifesphere/+/++, SP Conversion, Detoxify, Groundswell,
> Friendly Rivalry, Soar (Mov y terreno), Summon Hero, Divine Blessing/+.

---

## 10. Grabados (engrave)

**Las páginas de Emblema NO dan datos de grabado.** Sí los da otra página del mismo sitio,
`https://serenesforest.net/engage/somniel/engraving/` (HTTP 200; la ruta
`/engage/somniel/forging-engraving/` que aparece como título en el índice da 404, la buena es
`/engraving/`). Extracto literal de esa tabla para los siete de DLC, con el mapeo al JSON:

| Emblema | Engraving | Mt+ | Hit+ | Crit+ | Wt+ | Avo+ | Ddg+ | ¿coincide con el JSON? |
|---|---|---|---|---|---|---|---|---|
| Edelgard | Rivals | 1 | 10 | 10 | 1 | 10 | — | sí (`power 1, hit 10, critical 10, weight 1, avoid 10, secure 0`) |
| Tiki | Dragons | 2 | — | — | — | -20 | -20 | sí |
| Hector | Strength | 3 | — | — | 3 | -30 | -30 | sí |
| Veronica | Heroes | 1 | -20 | -20 | -2 | 20 | 20 | sí |
| Soren | Acumen | 2 | — | — | — | -10 | -20 | sí |
| Camilla | Revelation | 1 | — | 30 | 1 | -20 | -20 | sí |
| Chrom | Bonds | 1 | — | — | -1 | 20 | 20 | sí |

El campo `secure` del JSON es el **Ddg+** de la web (INTERPRETACIÓN mía, confirmada porque
los 7 cuadran con esa lectura y ninguna otra).

---

## Fuente y crédito

Todos los textos en inglés de este documento provienen de serenesforest.net
(*Content not otherwise credited copyright 2005-2020 to Aveyn Knight/VincentASM*). Se citan
aquí como fuente de datos para implementar el motor, igual que el resto de créditos del
proyecto.
