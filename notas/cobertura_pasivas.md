# Cobertura del intérprete de pasivas (condicion_dsl) frente al datamine

Generado por `tests/golden/cobertura_pasivas.py`. No editar a mano.

- Habilidades en el catálogo: **804**
- Alcanzables por unidades reales (personajes, clases, emblemas, dispos M000–M026 con refuerzos, cadenas give/sync): **573**
- Vistas en los escenarios golden actuales: **56**

## Estado

| estado | nº | significado |
|---|---:|---|
| cubierta | 347 | Condition y Act* íntegramente en el vocabulario actual de la DSL |
| parcial | 4 | stat_boosts/combat_mods o parte de los acts se leen; falta vocabulario para el resto |
| no_cubierta | 38 | tiene Condition/Act* pero la DSL no los entiende |
| evento_around | 7 | efecto post-combate en área (Around*): sin motor todavía |
| sin_efecto_codificado | 61 | sin Condition/Act*/boosts/give: comando o flag que el motor debe tratar aparte (Canter, Vantage, Dance…) |
| dlc_sin_datamine | 116 | habilidad de Emblema DLC identificada solo por nombre (no está en Skill.xml): overlay a mano |
| no_en_catalogo | 0 | SID referenciado pero ausente del catálogo |

Implementadas a mano en el motor (SID o nombre citado en motor_calculo.py, motor_analisis.py, estado_tablero.py, pasivas_temporales.py, app.py, catalogo_loader.py): **54** (lista al final).

## Vocabulario que falta, por habilidades que desbloquea

| tipo | término | habilidades | ejemplos |
|---|---|---:|---|
| valor | `相手の回復` | 6 | Healing Light, Staff Mastery 1, Staff Mastery 2, Staff Mastery 3 |
| variable | `相手の回復` | 6 | Healing Light, Staff Mastery 1, Staff Mastery 2, Staff Mastery 3 |
| variable | `妨害杖` | 5 | Staff Mastery 1, Staff Mastery 2, Staff Mastery 3, Staff Mastery 4 |
| variable | `杖の種類` | 5 | Staff Mastery 1, Staff Mastery 2, Staff Mastery 3, Staff Mastery 4 |
| función | `相手のユニット属性()` | 3 | Holy Stance, Holy Stance+, Holy Stance++ |
| variable | `異形属性` | 3 | Holy Stance, Holy Stance+, Holy Stance++ |
| variable | `相手の性別` | 3 | Disarming Sigh, Knightly Escort, Stunning Smile |
| variable | `相手の識別子` | 3 | Charmer, Knightly Escort, Single-Minded |
| función | `神将スキル確率()` | 2 | Divine Pulse, Divine Pulse+ |
| valor | `ヒット` | 2 | Divine Pulse, Divine Pulse+ |
| variable | `チェインアタック回数` | 2 | Moved to Tears |
| variable | `ミス` | 2 | Divine Pulse, Divine Pulse+ |
| variable | `一時変数` | 2 | Back at You, Diffuse Healer |
| variable | `攻撃結果` | 2 | Divine Pulse, Divine Pulse+ |
| variable | `最終戦闘相手` | 2 | Charmer, Single-Minded |
| variable | `相手の神将レベル` | 2 | Bond Forger, Bond Forger+ |
| función | `周囲のユニット数()` | 1 | Party Animal |
| función | `周囲の味方数()` | 1 | Spell Harmony |
| función | `周囲の性別数()` | 1 | Knightly Escort |
| función | `移動コスト()` | 1 | Air Raid |
| valor | `アイテム()` | 1 | Gold Acquisition 500G |
| valor | `ミス` | 1 | Avo |
| valor | `一時変数` | 1 | Back at You |
| valor | `周囲のユニット数()` | 1 | Party Animal |
| valor | `周囲の味方数()` | 1 | Spell Harmony |
| valor | `回復` | 1 | Diffuse Healer |
| valor | `相手のエンゲージカウント` | 1 | Spirit Strike |
| valor | `隣接支援合計値` | 1 | Dual Support |
| variable | `X` | 1 | Air Raid |
| variable | `Z` | 1 | Air Raid |
| variable | `エンゲージカウント` | 1 | Fell Spirit |
| variable | `エンゲージカウント限界` | 1 | Fell Spirit |
| variable | `エンゲージ中` | 1 | Fell Spirit |
| variable | `回復` | 1 | Diffuse Healer |
| variable | `挟撃中` | 1 | Pincer Attack |
| variable | `武器の消費` | 1 | World Tree |
| variable | `武器レベル` | 1 | Weapon Insight |
| variable | `相手のエンゲージカウント` | 1 | Spirit Strike |
| variable | `相手の武器レベル` | 1 | Weapon Insight |
| variable | `相手の移動タイプ` | 1 | Air Raid |
| variable | `相手の隣接ユニット数` | 1 | Aspiring Hero |
| variable | `立場` | 1 | Brave Assist |
| variable | `総攻撃回数` | 1 | LynEngage Attack Break |
| variable | `識別子` | 1 | Knightly Escort |
| variable | `護衛中` | 1 | Allied Defense |
| variable | `隣接ユニット数` | 1 | Aspiring Hero |

## No cubiertas (38)

| SID | nombre | origen | Condition | Act* | falta |
|---|---|---|---|---|---|
| `SID_エスコート` | Knightly Escort | dispos/personaje | `(相手の性別 == 女性 || 相手の識別子 == 識別子) && 周囲の性別数(2, 女性) >= 2` |  | 相手の性別, 相手の識別子, 識別子, 周囲の性別数() |
| `SID_リンエンゲージ技_ブレイク` | LynEngage Attack Break | cadena | `総攻撃回数 == 4` |  | 総攻撃回数 |
| `SID_人たらし` | Charmer | dispos/personaje | `最終戦闘相手 == 相手の識別子` | 相手の必殺値 - 10 | 最終戦闘相手, 相手の識別子 |
| `SID_信仰１` | Staff Mastery 1 | emblema | `武器の種類 == 杖 && 相手の回復 > 0` | 相手の回復 = min( 相手のMaxHP - 相手のHP, 相手の回復 + 3 ) | 相手の回復, val:相手の回復 |
| `SID_信仰２` | Staff Mastery 2 | emblema | `武器の種類 == 杖 && 相手の回復 > 0` | 相手の回復 = min( 相手のMaxHP - 相手のHP, 相手の回復 + 5 ) | 相手の回復, val:相手の回復 |
| `SID_信仰３` | Staff Mastery 3 | emblema | `武器の種類 == 杖 && 相手の回復 > 0` | 相手の回復 = min( 相手のMaxHP - 相手のHP, 相手の回復 + 7 ) | 相手の回復, val:相手の回復 |
| `SID_信仰４` | Staff Mastery 4 | emblema | `武器の種類 == 杖 && 相手の回復 > 0` | 相手の回復 = min( 相手のMaxHP - 相手のHP, 相手の回復 + 10 ) | 相手の回復, val:相手の回復 |
| `SID_信仰５` | Staff Mastery 5 | emblema | `武器の種類 == 杖 && 相手の回復 > 0` | 相手の回復 = min( 相手のMaxHP - 相手のHP, 相手の回復 + 15 ) | 相手の回復, val:相手の回復 |
| `SID_助太刀` | Brave Assist | clase/dispos | `立場 == 援護 && HP == MaxHP` | 攻撃回数 = 2 | 立場 |
| `SID_名乗り上げ` | Aspiring Hero | dispos/personaje/tablero | `隣接ユニット数 + 相手の隣接ユニット数 == 0` | 命中値 + 20; 回避値 - 10 | 相手の隣接ユニット数, 隣接ユニット数 |
| `SID_執着` | Single-Minded | dispos/personaje/tablero | `最終戦闘相手 == 相手の識別子` | 命中値 + 20 | 最終戦闘相手, 相手の識別子 |
| `SID_大樹` | World Tree | clase | `武器の種類 == 杖 && 武器の消費 > 0 && スキル確率(技)` | 武器の消費 = 0 | 武器の消費 |
| `SID_大集会` | Party Animal | dispos/personaje | `周囲のユニット数(2) > 0` | 命中値 + 周囲のユニット数(2) * 3; 回避値 + 周囲のユニット数(2) * 3 | 周囲のユニット数(), val:周囲のユニット数() |
| `SID_天刻の拍動` | Divine Pulse | dispos/emblema | `攻撃結果 == ミス && 神将スキル確率( 30 + 幸運 )` | 攻撃結果 = ヒット | ミス, 攻撃結果, 神将スキル確率(), val:ヒット |
| `SID_天刻の拍動＋` | Divine Pulse+ | dispos/emblema/personaje | `攻撃結果 == ミス && 神将スキル確率( 50 + 幸運 )` | 攻撃結果 = ヒット | ミス, 攻撃結果, 神将スキル確率(), val:ヒット |
| `SID_妨害杖命中＋１０` | Staff Mastery 1 | cadena | `武器の種類 == 杖 && 杖の種類 == 妨害杖` | 命中値 + 10 | 妨害杖, 杖の種類 |
| `SID_妨害杖命中＋１５` | Staff Mastery 2 | cadena | `武器の種類 == 杖 && 杖の種類 == 妨害杖` | 命中値 + 15 | 妨害杖, 杖の種類 |
| `SID_妨害杖命中＋２０` | Staff Mastery 3 | cadena | `武器の種類 == 杖 && 杖の種類 == 妨害杖` | 命中値 + 20 | 妨害杖, 杖の種類 |
| `SID_妨害杖命中＋２５` | Staff Mastery 4 | cadena | `武器の種類 == 杖 && 杖の種類 == 妨害杖` | 命中値 + 25 | 妨害杖, 杖の種類 |
| `SID_妨害杖命中＋３０` | Staff Mastery 5 | cadena | `武器の種類 == 杖 && 杖の種類 == 妨害杖` | 命中値 + 30 | 妨害杖, 杖の種類 |
| `SID_微笑み` | Stunning Smile | dispos/personaje/tablero | `相手の性別 == 男性` | 相手の回避値 - 20 | 相手の性別 |
| `SID_急襲` | Air Raid | clase/dispos | `移動コスト(相手の移動タイプ, X, Z) > 100` | 攻撃速度 + 5 | X, Z, 相手の移動タイプ, 移動コスト() |
| `SID_挟撃` | Pincer Attack | clase/dispos | `挟撃中 && 手番回数 == 1 && スキル所持("追撃不可") == 0` | 手番回数 = 2 | 挟撃中 |
| `SID_歴戦の勘` | Weapon Insight | dispos/personaje | `武器の種類 != 0 && 武器レベル < 相手の武器レベル` | 必殺値 + 20 | 武器レベル, 相手の武器レベル |
| `SID_気の拡散` | Diffuse Healer | clase/dispos | `相手の武器の種類 == 杖 && 回復 > 0` | 一時変数 + 回復 | 回復, val:回復 |
| `SID_水鏡効果` | Back at You | cadena | `一時変数 > 0 && スキル確率( 技 )` | 威力 + 一時変数/2; 一時変数 = 0 | 一時変数, val:一時変数 |
| `SID_涙腺崩壊` | Moved to Tears | dispos/personaje | `チェインアタック回数 > 0` | 威力 + 2 | チェインアタック回数 |
| `SID_涙腺崩壊_演出用` | Moved to Tears | cadena | `チェインアタック回数 > 0 && スキル所持("涙腺崩壊_発動済み") == 0` |  | チェインアタック回数 |
| `SID_溜め息` | Disarming Sigh | dispos/personaje/tablero | `相手の性別 == 男性` | 相手の命中値 - 20 | 相手の性別 |
| `SID_狂乱の一撃` | Spirit Strike | clase/dispos | `生存 && 相手の生存 && 相手のエンゲージカウント > 0` | 相手のエンゲージカウント = max(0, 相手のエンゲージカウント - 5) | 相手のエンゲージカウント, val:相手のエンゲージカウント |
| `SID_異形リベンジ` | Holy Stance | emblema/tablero | `相手のユニット属性(異形属性) && HP > ダメージ && ダメージ >= 10 && ( 相手の攻撃属性 == 魔法属性 && ( スキル所持( "マジックシールド" ) || スキル所持( "EN_魔防の薬_効果" ) ) ) == 0 && ( 相手の攻撃属性 == 物理属性 && スキル所持( "EN_守備の薬_効果" ) ) == 0` | 相手のダメージ = ダメージ*0.1 | 異形属性, 相手のユニット属性() |
| `SID_異形リベンジ＋` | Holy Stance+ | emblema | `相手のユニット属性(異形属性) && HP > ダメージ && ダメージ >= 4 && ( 相手の攻撃属性 == 魔法属性 && ( スキル所持( "マジックシールド" ) || スキル所持( "EN_魔防の薬_効果" ) ) ) == 0 && ( 相手の攻撃属性 == 物理属性 && スキル所持( "EN_守備の薬_効果" ) ) == 0` | 相手のダメージ = ダメージ*0.3 | 異形属性, 相手のユニット属性() |
| `SID_異形リベンジ＋＋` | Holy Stance++ | emblema/personaje | `相手のユニット属性(異形属性) && HP > ダメージ && ダメージ >= 2 && ( 相手の攻撃属性 == 魔法属性 && ( スキル所持( "マジックシールド" ) || スキル所持( "EN_魔防の薬_効果" ) ) ) == 0 && ( 相手の攻撃属性 == 物理属性 && スキル所持( "EN_守備の薬_効果" ) ) == 0` | 相手のダメージ = ダメージ*0.5 | 異形属性, 相手のユニット属性() |
| `SID_絆を繋薙くもの` | Bond Forger | emblema | `相手の神将レベル != 0` |  | 相手の神将レベル |
| `SID_絆を繋薙くもの＋` | Bond Forger+ | emblema | `相手の神将レベル != 0` |  | 相手の神将レベル |
| `SID_護衛` | Allied Defense | clase/dispos | `護衛中` | 相手の威力 - 3 | 護衛中 |
| `SID_邪竜気` | Fell Spirit | clase/dispos | `エンゲージ中 == 0 && エンゲージカウント < エンゲージカウント限界` | エンゲージカウント + 1 | エンゲージカウント, エンゲージカウント限界, エンゲージ中 |
| `SID_魔力増幅` | Spell Harmony | clase/dispos | `武器の種類 == 魔道書 && 周囲の味方数(1, 魔道書) > 0` | 攻撃力 + 周囲の味方数(1, 魔道書) | 周囲の味方数(), val:周囲の味方数() |

## Parciales (4)

| SID | nombre | origen | Condition | Act* | falta |
|---|---|---|---|---|---|
| `SID_お金入手_500G` | Gold Acquisition 500G | cadena | `相手の生存 == 0 && スキル確率( 幸運 )` | 拾得アイテム = アイテム("500G") | val:アイテム() |
| `SID_デュアルサポート` | Dual Support | emblema/personaje | `周囲の味方数 > 0` | 回避値 + 隣接支援合計値 * 5 | val:隣接支援合計値 |
| `SID_死亡回避` | Avo | dispos/personaje | `HP <= ダメージ` | ダメージ = 0; 攻撃結果 = ミス | val:ミス |
| `SID_癒しの響き` | Healing Light | emblema/personaje/tablero | `武器の種類 == 杖 && 相手の回復 > 0 && HP < MaxHP` | 回復 = max( 相手の回復 * 0.5, 1 ) | 相手の回復, val:相手の回復 |

## Eventos Around* (7)

| SID | nombre | origen | Condition | Act* | falta |
|---|---|---|---|---|---|
| `SID_僕が守ります！` | Get Behind Me! | dispos/personaje/tablero | `` |  |  |
| `SID_手助け` | Reforge | clase/dispos | `` |  |  |
| `SID_死の吐息` | Savage Blow | clase/dispos/tablero | `生存` |  |  |
| `SID_気の拡散効果` | Diffuse Healer | cadena | `一時変数 > 0 ` |  | 一時変数 |
| `SID_神秘の踊り` | Curious Dance | dispos/personaje | `` |  |  |
| `SID_自壊` | Self-Destruct | clase/dispos | `HP*100 <= MaxHP*50` | HP = 0 |  |
| `SID_邪竜気・闇` | Dark Spirit | clase/dispos | `` |  |  |

## Sin efecto codificado (comandos/flags) (61)

| SID | nombre | origen | Condition | Act* | falta |
|---|---|---|---|---|---|
| `SID_すり抜け` | Pass | clase/dispos | `` |  |  |
| `SID_オルタネイト` | Night and Day | emblema | `` |  |  |
| `SID_オヴスキュリテ装備可能` | Obscurite Usable | dispos/personaje | `` |  |  |
| `SID_サイレス無効` | Silence Ward | emblema/personaje/tablero | `` |  |  |
| `SID_チェインアタック許可` | Chain Attack Allowed | cadena | `` |  |  |
| `SID_ブレイク時追撃_ダメージ５０％_発動済み` | BreakFollow-Up (50% Damage) (Triggered) | cadena | `` |  |  |
| `SID_ブレイク無効_効果` | Unbreakable (Effect) | cadena | `` |  |  |
| `SID_ベレトエンゲージ技` | Goddess Dance | emblema | `` |  |  |
| `SID_ミセリコルデ装備可能` | Misericorde Usable | dispos/personaje | `` |  |  |
| `SID_リベラシオン装備可能` | Liberation Usable | dispos/personaje/tablero | `` |  |  |
| `SID_ヴィレグランツ装備可能` | Wille Glanz Usable | dispos/personaje/tablero | `` |  |  |
| `SID_不動_効果` | Laguz Friend (Effect) | cadena | `` |  |  |
| `SID_不死身` | Immortal | dispos/personaje | `` |  |  |
| `SID_主人公` | Divine One | dispos/personaje/tablero | `` |  |  |
| `SID_以心` | Attuned | emblema | `` |  |  |
| `SID_先生` | Instruct | emblema | `` |  |  |
| `SID_努力の才` | Expertise | personaje | `` |  |  |
| `SID_双聖効果` | Sacred Twins(Effect) | cadena | `` |  |  |
| `SID_増幅` | Augment | emblema/personaje | `` |  |  |
| `SID_増幅_闇` | Dark Augment | emblema | `` |  |  |
| `SID_大好物` | Favorite Food | emblema/personaje/tablero | `` |  |  |
| `SID_大盤振る舞い` | Generosity | dispos/personaje/tablero | `` |  |  |
| `SID_平和の花効果` | Gentle Flower | cadena | `` |  |  |
| `SID_強制チェインアタック２マス` | ２ | cadena | `` |  |  |
| `SID_強制死亡` | Trigger Death | dispos/personaje | `` |  |  |
| `SID_月輪効果` | (Effect) | cadena | `` |  |  |
| `SID_杖使い` | Cleric | dispos/emblema/tablero | `` |  |  |
| `SID_杖使い＋` | Cleric+ | emblema | `` |  |  |
| `SID_杖使い＋＋` | Cleric++ | emblema/personaje | `` |  |  |
| `SID_死亡会話存在敵` | Boss Unit | dispos/personaje/tablero | `` |  |  |
| `SID_残像` | Call Doubles | emblema/personaje | `` |  |  |
| `SID_気絶` | Stun | cadena | `` |  |  |
| `SID_涙腺崩壊_発動済み` | Moved to Tears (Triggered) | cadena | `` |  |  |
| `SID_煌めく理力` | Big Personality | dispos/personaje/tablero | `` |  |  |
| `SID_特効無効_効果` | Unwavering (Effect) | cadena | `` |  |  |
| `SID_猛進` | Headlong Rush | emblema/personaje/tablero | `` |  |  |
| `SID_王族` | Royalty | dispos/personaje/tablero | `` |  |  |
| `SID_神竜の加護` | Holy Shield | emblema | `` |  |  |
| `SID_神竜気` | Divine Spirit | clase/dispos | `` |  |  |
| `SID_神速発動済み` | (Triggered) | cadena | `` |  |  |
| `SID_移動補助` | Clear the Way | clase/dispos | `` |  |  |
| `SID_立往生` | Immobilized | dispos/personaje/tablero | `` |  |  |
| `SID_竜脈` | Dragon Vein | emblema | `` |  |  |
| `SID_竜脈_気功` | Dragon Vein | cadena | `` |  |  |
| `SID_竜脈_連携` | Dragon Vein | cadena | `` |  |  |
| `SID_竜脈_重装` | Dragon Vein | cadena | `` |  |  |
| `SID_竜脈_隠密` | Dragon Vein | cadena | `` |  |  |
| `SID_竜脈_飛行` | Dragon Vein | cadena | `` |  |  |
| `SID_竜脈_騎馬` | Dragon Vein | cadena | `` |  |  |
| `SID_竜脈_魔法` | Dragon Vein | cadena | `` |  |  |
| `SID_絆の指輪_アンナ_発動` | Spur Res | cadena | `` |  |  |
| `SID_自己回復` | Self-Healing | clase/dispos | `` |  |  |
| `SID_超越` | Rise Above | emblema/personaje | `` |  |  |
| `SID_超越_闇` | Sink Below | emblema | `` |  |  |
| `SID_足狙い発動済み` | Leg Strike(Triggered) | cadena | `` |  |  |
| `SID_踊り` | Dance | clase/dispos | `` |  |  |
| `SID_踏み込み` | Advance | emblema/personaje | `` |  |  |
| `SID_追加エンゲージ武器１_巻き込み無効化` | EngageWeapon１ Friendly Fire Immune | dispos/personaje | `` |  |  |
| `SID_重唱_発動演出` | Echo | cadena | `` |  |  |
| `SID_鍵開け` | KeyOpen | clase/dispos/tablero | `` |  |  |
| `SID_順応` | Adaptable | emblema | `` |  |  |

## DLC sin datamine (overlay a mano) (116)

| SID | nombre | origen | Condition | Act* | falta |
|---|---|---|---|---|---|
| `Adaptability` |  | emblema | `` |  |  |
| `Adaptability+` |  | emblema | `` |  |  |
| `Anima Focus` |  | emblema | `` |  |  |
| `Assembly Gambit` |  | emblema | `` |  |  |
| `Assign Decoy` |  | emblema | `` |  |  |
| `Axe Guard 1` |  | emblema | `` |  |  |
| `Axe Guard 2` |  | emblema | `` |  |  |
| `Axe Guard 3` |  | emblema | `` |  |  |
| `Axe Guard 4` |  | emblema | `` |  |  |
| `Axe Guard 5` |  | emblema | `` |  |  |
| `Block Recovery` |  | emblema | `` |  |  |
| `Book of Worlds` |  | emblema | `` |  |  |
| `Bow Guard 1` |  | emblema | `` |  |  |
| `Bow Guard 2` |  | emblema | `` |  |  |
| `Bow Guard 3` |  | emblema | `` |  |  |
| `Bow Guard 4` |  | emblema | `` |  |  |
| `Bow Guard 5` |  | emblema | `` |  |  |
| `Brute Force` |  | emblema | `` |  |  |
| `Charm` |  | emblema | `` |  |  |
| `Combat Arts` |  | emblema | `` |  |  |
| `Contract` |  | emblema | `` |  |  |
| `Decisive Strike` |  | emblema | `` |  |  |
| `Decisive Strike+` |  | emblema | `` |  |  |
| `Detoxify` |  | emblema | `` |  |  |
| `Draconic Form` |  | emblema | `` |  |  |
| `Dragon Vein` |  | emblema | `` |  |  |
| `Flare` |  | emblema | `` |  |  |
| `Friendly Rivalry` |  | emblema | `` |  |  |
| `Gambit` |  | emblema | `` |  |  |
| `Geosphere` |  | emblema | `` |  |  |
| `Geosphere+` |  | emblema | `` |  |  |
| `Groundswell` |  | emblema | `` |  |  |
| `HP/Lck +10` |  | emblema | `` |  |  |
| `HP/Lck +2` |  | emblema | `` |  |  |
| `HP/Lck +4` |  | emblema | `` |  |  |
| `HP/Lck +6` |  | emblema | `` |  |  |
| `HP/Lck +8` |  | emblema | `` |  |  |
| `Heavy Attack` |  | emblema | `` |  |  |
| `Impenetrable` |  | emblema | `` |  |  |
| `Keen Insight` |  | emblema | `` |  |  |
| `Keen Insight+` |  | emblema | `` |  |  |
| `Knife Guard 1` |  | emblema | `` |  |  |
| `Knife Guard 2` |  | emblema | `` |  |  |
| `Knife Guard 3` |  | emblema | `` |  |  |
| `Knife Guard 4` |  | emblema | `` |  |  |
| `Knife Guard 5` |  | emblema | `` |  |  |
| `Lance Guard 1` |  | emblema | `` |  |  |
| `Lance Guard 2` |  | emblema | `` |  |  |
| `Lance Guard 3` |  | emblema | `` |  |  |
| `Lance Guard 4` |  | emblema | `` |  |  |
| `Lance Guard 5` |  | emblema | `` |  |  |
| `Level Boost` |  | emblema | `` |  |  |
| `Lifesphere` |  | emblema | `` |  |  |
| `Lifesphere+` |  | emblema | `` |  |  |
| `Lifesphere++` |  | emblema | `` |  |  |
| `Lightsphere` |  | emblema | `` |  |  |
| `Lineage` |  | emblema | `` |  |  |
| `Mag/Dex +1` |  | emblema | `` |  |  |
| `Mag/Dex +2` |  | emblema | `` |  |  |
| `Mag/Dex +3` |  | emblema | `` |  |  |
| `Mag/Dex +4` |  | emblema | `` |  |  |
| `Mag/Dex +5` |  | emblema | `` |  |  |
| `Mag/Res +1` |  | emblema | `` |  |  |
| `Mag/Res +2` |  | emblema | `` |  |  |
| `Mag/Res +3` |  | emblema | `` |  |  |
| `Mag/Res +4` |  | emblema | `` |  |  |
| `Mag/Res +5` |  | emblema | `` |  |  |
| `Magic Guard 1` |  | emblema | `` |  |  |
| `Magic Guard 2` |  | emblema | `` |  |  |
| `Magic Guard 3` |  | emblema | `` |  |  |
| `Magic Guard 4` |  | emblema | `` |  |  |
| `Magic Guard 5` |  | emblema | `` |  |  |
| `Other Half` |  | emblema | `` |  |  |
| `Piercing Glare` |  | emblema | `` |  |  |
| `Quick Riposte` |  | emblema | `` |  |  |
| `Quick Riposte+` |  | emblema | `` |  |  |
| `Rally Spectrum` |  | emblema | `` |  |  |
| `Rally Spectrum+` |  | emblema | `` |  |  |
| `Reprisal` |  | emblema | `` |  |  |
| `Reprisal+` |  | emblema | `` |  |  |
| `SP Conversion` |  | emblema | `` |  |  |
| `Soar` |  | emblema | `` |  |  |
| `Spd/Dex +1` |  | emblema | `` |  |  |
| `Spd/Dex +2` |  | emblema | `` |  |  |
| `Spd/Dex +3` |  | emblema | `` |  |  |
| `Spd/Dex +4` |  | emblema | `` |  |  |
| `Spd/Dex +5` |  | emblema | `` |  |  |
| `Spd/Res +1` |  | emblema | `` |  |  |
| `Spd/Res +2` |  | emblema | `` |  |  |
| `Spd/Res +3` |  | emblema | `` |  |  |
| `Spd/Res +4` |  | emblema | `` |  |  |
| `Spd/Res +5` |  | emblema | `` |  |  |
| `Special Guard 1` |  | emblema | `` |  |  |
| `Special Guard 2` |  | emblema | `` |  |  |
| `Special Guard 3` |  | emblema | `` |  |  |
| `Special Guard 4` |  | emblema | `` |  |  |
| `Special Guard 5` |  | emblema | `` |  |  |
| `Starsphere` |  | emblema | `` |  |  |
| `Str/Def +1` |  | emblema | `` |  |  |
| `Str/Def +2` |  | emblema | `` |  |  |
| `Str/Def +3` |  | emblema | `` |  |  |
| `Str/Def +4` |  | emblema | `` |  |  |
| `Str/Def +5` |  | emblema | `` |  |  |
| `Str/Dex +1` |  | emblema | `` |  |  |
| `Str/Dex +2` |  | emblema | `` |  |  |
| `Str/Dex +3` |  | emblema | `` |  |  |
| `Str/Dex +4` |  | emblema | `` |  |  |
| `Str/Dex +5` |  | emblema | `` |  |  |
| `Surprise Attack` |  | emblema | `` |  |  |
| `Sword Guard 1` |  | emblema | `` |  |  |
| `Sword Guard 2` |  | emblema | `` |  |  |
| `Sword Guard 3` |  | emblema | `` |  |  |
| `Sword Guard 4` |  | emblema | `` |  |  |
| `Sword Guard 5` |  | emblema | `` |  |  |
| `Weapon Sync` |  | emblema | `` |  |  |
| `Weapon Sync+` |  | emblema | `` |  |  |

## Implementadas a mano en el motor (54)

Candidatas a migrar al motor genérico (Fase 2). `estado` indica si la DSL ya podría sustituirlas.

| SID | nombre | estado DSL | Condition | Act* |
|---|---|---|---|---|
| `SID_アイクエンゲージ技` | Great Aether | cubierta | `` |  |
| `SID_エイリークエンゲージ技` | Twin Strike | cubierta | `` | 攻撃回数 = 2 |
| `SID_カウンター` | Divine Speed | cubierta | `手番回数 > 0 && スキル所持("追撃不可") == 0` | 手番回数 + 1 |
| `SID_カムイエンゲージ技` | Torrential Roar | cubierta | `` | 威力 * 1 |
| `SID_シグルドエンゲージ技` | Override | cubierta | `` | 威力 * 1 |
| `SID_セリカエンゲージ技` | Warp Ragnarok | cubierta | `` | 威力 * 1 |
| `SID_ブレイク時追撃` | Break Defenses | cubierta | `攻撃結果(ブレイク) && スキル所持("追撃不可") == 0` |  |
| `SID_マルスエンゲージ技` | Lodestar Rush | cubierta | `` | 攻撃回数 = 7 |
| `SID_ミカヤエンゲージ技` | Great Sacrifice | cubierta | `HP > 1` | HP = 1 |
| `SID_リンエンゲージ技` | Astra Storm | cubierta | `` | 攻撃回数 = 5 |
| `SID_リンエンゲージ技_闇_気功` | Astra Storm | cubierta | `` | 攻撃回数 = 5 |
| `SID_リーフエンゲージ技` | Quadruple Hit | cubierta | `` | 攻撃回数 = 4 |
| `SID_ルキナエンゲージ技` | All for One | cubierta | `` |  |
| `SID_ロイエンゲージ技` | Blazing Lion | cubierta | `` |  |
| `SID_優風` | Gentility | cubierta | `` | 相手の威力 - 3 |
| `SID_共鳴の黒魔法` | Resonance | cubierta | `手番回数 > 0 && 武器の種類 == 魔道書 && HP > 1` | HP - 1; 威力 + 2 |
| `SID_再移動` | Canter | cubierta | `` |  |
| `SID_再移動＋` | Canter+ | cubierta | `` |  |
| `SID_切り抜け` | Run Through | cubierta | `` |  |
| `SID_助走` | Momentum | cubierta | `移動距離 > 0 && 総行動回数 == 0` | 攻撃力 + min( 移動距離, 10 ) |
| `SID_助走＋` | Momentum+ | cubierta | `移動距離 > 0 && 総行動回数 == 0` | 攻撃力 + 移動距離 |
| `SID_勇将` | Resolve | cubierta | `` |  |
| `SID_勇将_効果` | Resolve | cubierta | `` |  |
| `SID_命中＋２０` | Hit +20 | cubierta | `` | 命中値 + 20 |
| `SID_待ち伏せ` | Vantage | cubierta | `HP*100 <= MaxHP * 25 && 手番回数 > 0` |  |
| `SID_待ち伏せ＋` | Vantage+ | cubierta | `HP*100 <= MaxHP * 50 && 手番回数 > 0` |  |
| `SID_待ち伏せ＋＋` | Vantage++ | cubierta | `HP*100 <= MaxHP * 75 && 手番回数 > 0` |  |
| `SID_戦果委譲` | Share Spoils | cubierta | `周囲の味方数 > 0` | 命中値 + 10; 回避値 + 10; 必殺値 - 10 |
| `SID_攻め立て` | Alacrity | cubierta | `スキル所持( "追撃不可" ) == 0 && 総手番回数 == 0 &&  (攻撃速度 - 相手の攻撃速度) >= 9` |  |
| `SID_月の腕輪` | Lunar Brace | cubierta | `攻撃属性 == 物理属性` | 威力 + 相手の守備 * 0.2 |
| `SID_月光` | Luna | cubierta | `スキル確率( 技 )` | 相手の防御力 - 相手の防御力 * 0.5 |
| `SID_武器相性激化` | Arms Shield | cubierta | `武器相性 == 有利` | 相手の威力 - 3 |
| `SID_殺しの技術` | Trained to Kill | cubierta | `地形回避 > 0` | 必殺値 + 15 |
| `SID_熟練者＋` | Veteran+ | cubierta | `` |  |
| `SID_特効耐性` | Stalwart | cubierta | `` |  |
| `SID_白の忠誠` | Alabaster Duty | cubierta | `相手の個人判定("リュール")` |  |
| `SID_白の忠誠_効果` | Alabaster Duty | cubierta | `` | 必殺値 + 5 |
| `SID_真っ向勝負` | Fair Fight | cubierta | `相手の手番回数 > 0` | 命中値 + 15; 相手の命中値 + 15 |
| `SID_神竜の結束` | Divinely Inspiring | cubierta | `` |  |
| `SID_神竜の結束_被ダメ軽減` | Divinely Inspiring | cubierta | `` | 相手の威力 - 1 |
| `SID_移動不可` | Move | cubierta | `` |  |
| `SID_絵になる二人` | Fairy-Tale Folk | cubierta | `周囲の隣接男女数(2, 男性, 女性) > 0` | 威力 + 2 |
| `SID_緋い声援` | Crimson Cheer | cubierta | `相手の個人判定("リュール")` |  |
| `SID_緋い声援_効果` | Crimson Cheer | cubierta | `` | 回避値 + 10 |
| `SID_自己研鑽` | Self-Improver | cubierta | `` |  |
| `SID_花園の門番` | Admiration | cubierta | `周囲の隣接男女数(2, 女性, 女性) > 0` | 相手の威力 - 2 |
| `SID_踏ん張り` | Hold Out | cubierta | `HP*100 >= (MaxHP * 30)` |  |
| `SID_踏ん張り_攻撃時効果` | Hold Out | cubierta | `HP <= ダメージ` | ダメージ = max(HP-1, 0) |
| `SID_踏ん張り_防御時効果` | Hold Out | cubierta | `HP <= ダメージ` | ダメージ = max(HP-1, 0) |
| `SID_魔力＋１` | Mag 1 | cubierta | `` |  |
| `SID_すり抜け` | Pass | sin_efecto_codificado | `` |  |
| `SID_ベレトエンゲージ技` | Goddess Dance | sin_efecto_codificado | `` |  |
| `SID_超越` | Rise Above | sin_efecto_codificado | `` |  |
| `SID_踊り` | Dance | sin_efecto_codificado | `` |  |

## Cubiertas

Not *Quite*, Laguz Friend, Laguz Friend (50% DR), Great Aether, IkeEngage Attack Renewal, Twin Strike, Knightly Escort, Engage Attack General, Divine Speed, Counter (50% Damage), Torrential Roar, Override, Quality Time, Quality Time+, Smash+, Warp Ragnarok, Dark Warp, Ragnarok Warp, Racket of Solm, Racket of Solm, DamageNullify, DamageNullify On Attack, DamageNullify On Defense, Damage２０％, Damage３０％, Hit３０％, Bond Breaker, Dual Assist, Dual Assist+, Break Defenses, BreakFollow-Up (50% Damage), Unbreakable, Diabolical Dance, BylethBoost Backup, BylethBoost Flying, Lodestar Rush, Great Sacrifice, Dragon Blast, AlearEngage Attack, Astra Storm, Astra Storm, Quadruple Hit, All for One, Blazing Lion, Make a Killing, Anchor, Unyielding, Unyielding+, Unyielding++, Build +3, Build +4, Build +5, Art Focus 1, Art Focus 2, Art Focus 3, Art Focus 4, Art Focus 5, ！(Effect), Gentility, Gentility+, Instruct, Blinding Flash, Swap, Resonance, Resonance+, Canter, Canter+, Certain Blow, Run Through, Swordbreaker, Sword Power 1, Sword Power 2, Sword Power 3, Sword Power 4, Sword Power 5, Sword Focus 1, Sword Focus 2, Sword Focus 3, Sword Focus 4, Sword Focus 5, Sword Agility 1, Sword Agility 2, Sword Agility 3, Sword Agility 4, Sword Agility 5, Seal Strength, Seal Strength (Effect), Strength +1, Strength +2, ＋２ １, Strength +3, Strength +4, Strength +5, Strength +6, Momentum, Momentum+, Resolve, Resolve, Resolve+, Resolve+, Bravery, Bravery+, Will to Win, Sacred Twins, Dreadful Aura, Hit +10, Hit +15, Hit +20, Hit +25, Hit +30, Hit１００, Cornered Beast, Pivot, Avoid +10, Avoid +15, Avoid +20, Avoid +25, Avoid +30, Avo－１０ Stealth, Sol, Solar Brace, Solar Brace+, Seal Defense, Seal Defense (Effect), Defense +1, Defense +2, Defense +3, Defense +3, Defense +4, Defense +5, Mentorship, (Effect), Gentle Flower, Luck +10, Luck +12, Luck +2, Luck +2, Luck +4, Luck +4, Luck +6, Luck +8, Bow Focus 1, Bow Focus 2, Bow Focus 3, Bow Focus 4, Bow Focus 5, Bow Agility 1, Bow Agility 2, Bow Agility 3, Bow Agility 4, Bow Agility 5, Reposition, Vantage, Vantage+, Vantage++, CritCrit０, Dodge +10, Dodge +15, Dodge +20, Dodge +25, Dodge +30, CritAvo－１０ Stealth, Crit－１０ Stealth, Crit０, Crit０ Offense, Wrath, Blood Fury, Share Spoils, Dexterity +1, Dexterity +2, Dexterity +3, Dexterity +4, Dexterity +5, Lost &amp; Found, Defeat EXPBonus５０, Alacrity, Alacrity+, Alacrity++, Engage Attack Guard, Seconds?, Axebreaker, Axe Power 1, Axe Power 2, Axe Power 3, Axe Power 4, Axe Power 5, Eclipse Brace, Eclipse Brace, Eclipse Brace+, Eclipse Brace, Eclipse Brace+, Eclipse Brace+, Warding Blow, Warding Stance, Lunar Brace, Lunar Brace+, Luna, Moon, Lancebreaker, Lance Power 1, Lance Power 2, Lance Power 3, Lance Power 4, Lance Power 5, Lance Agility 1, Lance Agility 2, Lance Agility 3, Lance Agility 4, Lance Agility 5, Contemplative, (Effect), Arms Shield, Arms Shield+, Arms Shield++, Life and Death, Trained to Kill, Back at You, Duelist's Blow, Merciless, Veteran+, Special Dance, Stalwart, Stalwart (Effect), Careful Aim, Alabaster Duty, Alabaster Duty, Triangle Adept, EXP０, Hit１００, Crit０, Fair Fight, Meditation, (Effect), Knife Precision 1, Knife Precision 2, Knife Precision 3, Knife Precision 4, Knife Precision 5, Sandstorm, Demolish, Verdant Faith, Verdant Faith, Divinely Inspiring, Divinely Inspiring (Damage Boost), Divinely Inspiring, Move, Movement +1, Move－１, Move－２, Draconic Hex, (Effect), Dragon Vein, Energized, Dual Strike, Spur Attack, Spur Attack, Spur Res, Bond Ring Anna (Effect), Bond Forger, Bond Forger+, Bonded Shield, Fairy-Tale Folk, Crimson Cheer, Crimson Cheer, Chaos Style, Self-Improver, Admiration, Ignis, Blue Skies, Blue Skies, Blue Skies+, Blue Skies Bravery, Blue Skies Bravery+, Blue Skies+, Void Curse, Grasping Void, Poison Strike, Perceptive, Perceptive+, Hobble, Leg Strike(Effect), Leg Strike(Check), Dance(Effect), Hold Out, Hold Out, Hold Out, Hold Out+, Hold Out+, Hold Out+, Hold Out++, Hold Out++, Hold Out++, Hold Out+++, Hold Out+++, Hold Out+++, Gallop, Dark Gallop, Gallop, Speedtaker, SpdBoost＋２, Seal Speed, Seal Speed (Effect), Speed +1, Speed +2, Speed +3, Speed +4, Speed +5, Fell Protection, Fell Protection (Damage Boost), Fell Protection, Echo, Echo, Steady Stance, Golden Lotus, Pair Up, No Distractions, Adaptable, Darting Blow, Darting Stance, Death Blow, Fierce Stance, Seal Magic, Seal Magic (Effect), Mag 1, Magic +2, Magic +3, Magic +4, Magic +5, Magic(50% Damage), MagicDamage６０％, Soulblade, Tome Precision 1, Tome Precision 2, Tome Precision 3, Tome Precision 4, Tome Precision 5, Seal Resistance, Seal Resistance (Effect), Resistance +2, Resistance +3, Resistance +4, Resistance +5, HP +10, HP +12, HP +15, HP +5, HP +7
