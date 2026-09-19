# Sombra: pasivas a mano (motor_calculo) vs motor genérico (pasivas.py)

Generado por `tests/golden/sombra_pasivas.py`. No editar a mano.

- Combates analizados: **9104** (errores: 0)
- Coinciden (misma aportación en daño/precisión/crítico de ambos lados): **6053**
- Difieren: **3051**

## Diferencias agrupadas por pasivas implicadas

`viejo` = aportación del código a mano (con − sin pasivas); `nuevo` = lo que predice el datamine.
Cada grupo es un caso a decidir en la Fase 2: o falta vocabulario/evento en el motor nuevo, o el bloque a mano inventaba.

| pasivas | combates | campos | ejemplo | viejo | nuevo |
|---|---:|---|---|---|---|
| viejas=Gente de Cuento, Sincronía Armamentística | nuevas=Fairy-Tale Folk | 1079 | dano_atk×1079 | `cap7_inicial|Chloé|Javelin|-|d1|Hortensia (Boss)` | {'dano_atk': 5} | {'dano_atk': 2.0} |
| viejas=Admiración Louis | nuevas=Admiration | 372 | dano_def×306, dano_atk×66 | `cap7_inicial|Hortensia (Boss)|Noble Rapier|-|d1|Louis` | {'dano_atk': 0.0} | {'dano_atk': -2.0} |
| viejas=— | nuevas=Perceptive | 302 | hit_def×302 | `cap7_inicial|Alear|Libération (Marth)|-|d1|Hortensia (Boss)` | {'hit_def': 0} | {'hit_def': -18.5} |
| viejas=— | nuevas=Divine Speed, Perceptive | 302 | hit_def×302 | `cap7_inicial|Alear|Libération (Marth)|F|d1|Hortensia (Boss)` | {'hit_def': 0} | {'hit_def': -18.5} |
| viejas=Gente de Cuento | nuevas=Fairy-Tale Folk | 197 | dano_atk×107, dano_def×90 | `cap7_inicial|Hortensia (Boss)|Noble Rapier|-|d1|Chloé` | {'dano_def': 0} | {'dano_def': 2.0} |
| viejas=Solidaridad Lapis | nuevas=Share Spoils | 166 | hit_def×159, hit_atk×29 | `cap7_inicial|Lapis|Iron Blade|-|d1|Hortensia (Boss)` | {'hit_atk': 0.0} | {'hit_atk': 10.0} |
| viejas=— | nuevas=Share Spoils | 103 | hit_atk×96, crit_def×65, hit_def×24 | `cap7_inicial|Hortensia (Boss)|Noble Rapier|-|d1|Lapis` | {'hit_def': 0} | {'hit_def': 10.0} |
| viejas=Rompedefensas | nuevas=Perceptive | 83 | hit_def×83 | `cap7_inicial|Alear|Libération (Marth)|-|d1|Axe Cavalier (14,7)` | {'hit_def': 0} | {'hit_def': -18.5} |
| viejas=Rompedefensas | nuevas=Divine Speed, Perceptive | 83 | hit_def×83 | `cap7_inicial|Alear|Libération (Marth)|F|d1|Axe Cavalier (14,7)` | {'hit_def': 0} | {'hit_def': -18.5} |
| viejas=— | nuevas=Not *Quite* | 65 | hit_atk×65 | `cap8_inicial|Aliado 2|Iron Sword|-|d1|Zelkov` | {'hit_atk': 0} | {'hit_atk': -10.0} |
| viejas=Superación | nuevas=— | 60 | dano_atk×60, dano_def×60, hit_def×60, crit_atk×56, hit_atk×8, crit_def×3 | `cap8_inicial|Diamant|Iron Sword|F|d1|Ivy` | {'dano_atk': 3, 'dano_def': -2, 'hit_def': -6} | {'dano_atk': 0.0, 'dano_def': 0.0, 'hit_def': 0.0} |
| viejas=— | nuevas=— | 49 | dano_atk×28, hit_atk×14, dano_def×7 | `cap7_inicial|Hortensia (Boss)|Elfire|-|d2|Alcryst` | {'dano_def': -20} | {'dano_def': 0.0} |
| viejas=Gente de Cuento, Sincronía Armamentística | nuevas=Fairy-Tale Folk, Not *Quite* | 26 | dano_atk×26, hit_atk×24 | `cap8_inicial|Chloé|Javelin|-|d1|Zelkov` | {'dano_atk': 5, 'hit_atk': 0} | {'dano_atk': 2.0, 'hit_atk': -10.0} |
| viejas=Asesina Nata | nuevas=Trained to Kill | 24 | crit_atk×24 | `cap7_inicial|Yunaka|Iron Dagger|-|d1|Lance Armor (6,6)` | {'crit_atk': 0.0} | {'crit_atk': 15.0} |
| viejas=Guía Divina, Guía Divina Defensor, Resonancia | nuevas=Not *Quite*, Resonance | 24 | hit_atk×24 | `cap8_inicial|Céline|Fire|-|d1|Zelkov` | {'hit_atk': 0} | {'hit_atk': -10.0} |
| viejas=Gente de Cuento, Sincronía Armamentística | nuevas=Fairy-Tale Folk, Hit１００ | 13 | dano_atk×13 | `cap7_inicial|Chloé|Javelin|-|d1|Lance Fighter (6,10)` | {'dano_atk': 5} | {'dano_atk': 2.0} |
| viejas=— | nuevas=Not *Quite*, Perceptive | 12 | hit_atk×11, hit_def×5 | `cap8_inicial|Alear|Libération (Marth)|-|d1|Zelkov` | {'hit_def': 0} | {'hit_def': -18.5} |
| viejas=— | nuevas=Divine Speed, Not *Quite*, Perceptive | 12 | hit_atk×11, hit_def×5 | `cap8_inicial|Alear|Libération (Marth)|F|d1|Zelkov` | {'hit_def': 0} | {'hit_def': -18.5} |
| viejas=Guía Divina, Guía Divina Defensor | nuevas=Not *Quite* | 12 | hit_atk×12 | `cap8_inicial|Céline|Levin Sword (Sigurd)|-|d1|Zelkov` | {'hit_atk': 0} | {'hit_atk': -10.0} |
| viejas=Admiración Louis | nuevas=Admiration, Not *Quite* | 12 | hit_atk×12, dano_def×6 | `cap8_inicial|Louis|Steel Lance|-|d1|Zelkov` | {'hit_atk': 0} | {'hit_atk': -10.0} |
| viejas=Asesina Nata | nuevas=Hit１００, Trained to Kill | 8 | crit_atk×8 | `cap7_inicial|Yunaka|Iron Dagger|-|d1|Lance Fighter (6,10)` | {'crit_atk': 0.0} | {'crit_atk': 15.0} |
| viejas=— | nuevas=Certain Blow | 7 | hit_atk×7 | `cap7_turno10|Rosado|Steel Axe|-|d1|Alear` | {'hit_atk': 0} | {'hit_atk': 40.0} |
| viejas=— | nuevas=Hit１００, Perceptive | 6 | hit_def×6 | `cap7_inicial|Alear|Libération (Marth)|-|d1|Lance Fighter (6,10)` | {'hit_def': 0} | {'hit_def': -18.5} |
| viejas=— | nuevas=Divine Speed, Hit１００, Perceptive | 6 | hit_def×6 | `cap7_inicial|Alear|Libération (Marth)|F|d1|Lance Fighter (6,10)` | {'hit_def': 0} | {'hit_def': -18.5} |
| viejas=Gente de Cuento | nuevas=Fairy-Tale Folk, Hit１００ | 3 | dano_def×2, dano_atk×1 | `cap7_inicial|Lance Fighter (6,10)|Javelin|-|d1|Chloé` | {'dano_def': 0} | {'dano_def': 2.0} |
| viejas=Superación | nuevas=Not *Quite* | 3 | dano_atk×3, crit_atk×3, dano_def×3, hit_def×3, crit_def×3, hit_atk×1 | `cap8_inicial|Diamant|Iron Sword|F|d1|Zelkov` | {'dano_atk': 3, 'crit_atk': 1, 'dano_def': -3, 'hit_def': -7, 'crit_def': -2} | {'dano_atk': 0.0, 'crit_atk': 0.0, 'dano_def': 0.0, 'hit_def': 0.0, 'crit_def': 0.0} |
| viejas=Solidaridad Lapis | nuevas=Not *Quite*, Share Spoils | 3 | hit_def×3 | `cap8_inicial|Lapis|Iron Blade|-|d1|Zelkov` | {'hit_def': 0.0} | {'hit_def': -10.0} |
| viejas=— | nuevas=Hit１００, Share Spoils | 2 | hit_atk×2, hit_def×1, crit_def×1 | `cap7_inicial|Lance Fighter (6,10)|Javelin|-|d1|Lapis` | {'hit_atk': 0, 'hit_def': 0, 'crit_def': 0} | {'hit_atk': -10.0, 'hit_def': 10.0, 'crit_def': -10.0} |
| viejas=Solidaridad Lapis | nuevas=Hit１００, Share Spoils | 2 | hit_def×2, hit_atk×1 | `cap7_inicial|Lapis|Iron Blade|-|d1|Lance Fighter (6,10)` | {'hit_atk': 0.0, 'hit_def': 0.0} | {'hit_atk': 10.0, 'hit_def': -10.0} |
| viejas=Gente de Cuento, Sincronía Armamentística | nuevas=Fairy-Tale Folk, Triangle Adept | 2 | dano_atk×2 | `cap7_turno10|Chloé|Aymr (Emblema)|-|d1|Goldmary` | {'dano_atk': 5} | {'dano_atk': 2.0} |
| viejas=— | nuevas=Blinding Flash, Share Spoils | 2 | hit_def×2 | `cap8_inicial|Kagetsu|Wo Dao|-|d1|Lapis` | {'hit_def': 0} | {'hit_def': 10.0} |
| viejas=Guía Divina, Guía Divina Defensor | nuevas=Blinding Flash | 2 | hit_atk×2 | `cap8_inicial|Kagetsu|Wo Dao|-|d1|Céline` | {'hit_atk': 0} | {'hit_atk': 10.0} |
| viejas=Gente de Cuento | nuevas=Blinding Flash, Fairy-Tale Folk | 2 | dano_def×2 | `cap8_inicial|Kagetsu|Wo Dao|-|d1|Chloé` | {'dano_def': 0} | {'dano_def': 2.0} |
| viejas=Admiración Louis | nuevas=Admiration, Blinding Flash | 2 | dano_atk×2 | `cap8_inicial|Kagetsu|Wo Dao|-|d1|Louis` | {'dano_atk': 0.0} | {'dano_atk': -2.0} |
| viejas=Gente de Cuento | nuevas=Fairy-Tale Folk, Not *Quite* | 2 | dano_atk×2, hit_atk×2 | `cap8_inicial|Chloé|Aymr (Emblema)|-|d1|Zelkov` | {'dano_atk': 0, 'hit_atk': 0} | {'dano_atk': 2.0, 'hit_atk': -10.0} |
| viejas=Guía Divina, Guía Divina Defensor | nuevas=Certain Blow | 1 | hit_atk×1 | `cap7_turno10|Rosado|Steel Axe|-|d1|Citrinne` | {'hit_atk': 0} | {'hit_atk': 40.0} |
| viejas=— | nuevas=Certain Blow, Share Spoils | 1 | hit_atk×1, hit_def×1 | `cap7_turno10|Rosado|Steel Axe|-|d1|Lapis` | {'hit_atk': 0, 'hit_def': 0} | {'hit_atk': 30.0, 'hit_def': 10.0} |
| viejas=Gente de Cuento | nuevas=Certain Blow, Fairy-Tale Folk | 1 | hit_atk×1, dano_def×1 | `cap7_turno10|Rosado|Steel Axe|-|d1|Chloé` | {'hit_atk': 0, 'dano_def': 0} | {'hit_atk': 40.0, 'dano_def': 2.0} |

## Procs (スキル確率) vistos: no entran en los números, los decide el análisis de riesgo

- ninguno

## Habilidades activas que el motor nuevo aún no aplica (eventos give_target ≠ 1, Fase 3)

- `SID_平和の花`: 1712 combates
- `SID_神竜の結束`: 1192 combates
- `SID_自己研鑽`: 472 combates
- `SID_筋肉増強剤`: 444 combates
- `SID_絆の指輪_アルフォンス`: 444 combates
- `SID_絆の指輪_アンナ`: 202 combates
- `SID_瞑想`: 74 combates
