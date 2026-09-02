"""
compilar_catalogo.py — FE Engage Tactical Assistant
Parsea los XMLs oficiales del Datamining (FE17-DOC-main) y genera catalogo_engage.json.
"""

import xml.etree.ElementTree as ET
import os
import json
import csv
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATAMINE_DIR = os.path.join(BASE_DIR, "FE17-DOC-main", "FE17-DOC-main", "fe_assets_gamedata")
TRANS_DIR = os.path.join(BASE_DIR, "FE17-DOC-main", "FE17-DOC-main", "translations")

USEN_DIR = os.path.join(BASE_DIR, "FE17-DOC-main", "FE17-DOC-main", "fe_assets_message", "us", "usen", "csv")

JAPANESE_FALLBACK_TERMS = {
    "通常黒": "Dark",
    "通常": "Standard",
    "シンクロ専用黒": "Sync (Dark)",
    "シンクロ専用": "Sync",
    "敵エンゲージ技ダメージ軽減": "Engage Attack Guard",
    "主人公": "Divine One",
    "王族": "Royalty",
    "リーダー": "Leader",
    "立往生": "Immobilized",
    "不死身": "Immortal",
    "死亡会話存在敵": "Boss Unit",
    "強制死亡": "Trigger Death",
    "リベラシオン装備可能": "Liberation Usable",
    "ヴィレグランツ装備可能": "Wille Glanz Usable",
    "ミセリコルデ装備可能": "Misericorde Usable",
    "オヴスキュリテ装備可能": "Obscurite Usable",
    "轟雷発動可能": "Dire Thunder Usable",
    "カウンター": "Counter",
    "迅走": "Gallop",
    "重唱": "Echo",
    "増幅": "Augment",
    "超越": "Transcendence",
    "順応": "Adaptable",
    "絆盾": "Bonded Shield",
    "残像": "Illusions",
    "先生": "Instruct",
    "呪縛": "Dreadful Aura",
    "双聖": "Sacred Twins",
    "アイクエンゲージスキル": "Laguz Friend",
    "デモ用": "Demo",
    "視線設定用": "Camera Setup",
    "タイトル用": "Title",
    "リュール男": "Alear (M)",
    "リュール女": "Alear (F)",
    "雑魚": "Minion",
    "イベント": "Event",
    "ソードペガサス": "Sword Pegasus",
    "ランスアーマー": "Lance Armor",
    "ソードアーマー": "Sword Armor",
    "ランスファイター": "Lance Fighter",
    "アクスナイト": "Axe Knight",
    "アーチャー": "Archer",
    "マージ": "Mage",
    "モンク": "Monk",
    "ドラゴンナイト": "Wyvern Knight",
    "ブレイブヒーロー": "Hero",
    "スレイプニル下級": "Wingamer",
    "ティラユール下級": "Lord",
    "与ダメ上昇": "(Damage Boost)",
    "被ダメ軽減": "(Damage Reduction)",
    "ダメージ５０％": "(50% Damage)",
    "ダメージ50%減": "(50% DR)",
    "ダメージ60%減": "(60% DR)",
    "竜族効果": "(Dragon Effect)",
    "隠密効果": "(Covert Effect)",
    "隠密 効果": "(Covert Effect)",
    "飛行 効果": "(Flier Effect)",
    "発動終了チェック": "(End Check)",
    "発動終了": "(End)",
    "発動チェック": "(Check)",
    "発動済み": "(Triggered)",
    "効果": "(Effect)",
    "発動可能": "Usable",
    "お金入手": "Gold Acquisition",
    "アイギスの盾": "Aegis Shield",
    "特効": "Slayer",
    "回避": "Avo",
    "攻撃力上昇": "Atk Boost",
    "踊り": "Dance",
    "手加減": "Mercy",
    "気功": "Qi Adept",
    "ブレス": "Dragon Breath",
    "相手の防御力無視": "Ignore Def/Res",
    "チェインアタック許可": "Chain Attack Allowed",
    "ダイムサンダ": "Dire Thunder",
    "ギガスカリバー": "Gigascalibur",
    "業火": "Hellfire",
    "旋風": "Whirlwind",
    "エンゲージ技": "Engage Attack",
    "汎用設定": "General",
    "オフェンス時武器": "Offense Weapon",
    "オフェンス": "Offense",
    "アシュナード": "Ashnard",
    "アスタルテ": "Ashera",
    "イドゥン": "Idunn",
    "エフラム": "Ephraim",
    "隠蔽": "Stealth",
    "命中": "Hit",
    "必殺": "Crit",
    "魔力": "Mag",
    "ダメージ": "Damage",
    "軽減": "Reduction",
    "加算": "Bonus",
    "増強": "Boost",
    "速さ": "Spd",
    "攻撃速度": "Attack Speed",
    "撃破経験": "Defeat EXP",
    "経験": "EXP",
    "スキル": "Skill",
    "武器": "Weapon",
    "確率補正": "Rate Mod",
    "攻撃時": "On Attack",
    "竜族": "Dragon",
    "以心": "Unity",
    "日輪": "Solar Brace",
    "月光": "Luna",
    "太陽": "Sol",
    "天空": "Aether",
    "砲撃中無効": "Cannon Immune",
    "チェインアタック命中率": "Chain Attack Hit Rate",
    "追加エンゲージ武器": "Extra Engage Weapon",
    "巻き込み無効化": "Friendly Fire Immune",
    "神将": "Divine General",
    "フォルクヴァング": "Folkvangr",
    "紋章士": "Emblem",
    "エンゲージ": "Engage",
    "重装": "Armored",
    "騎馬": "Cavalry",
    "飛行": "Flying",
    "連携": "Backup",
    "隠密": "Covert",
    "魔道": "Mystic",
    "射程": "Range",
    "移動": "Move",
    "周囲": "Adjacent",
    "味方": "Allies",
    "敵": "Enemies",
    "リュール": "Alear",
    "ベレト": "Byleth",
    "アイク": "Ike",
    "マルス": "Marth",
    "シグルド": "Sigurd",
    "セリカ": "Celica",
    "ミカヤ": "Micaiah",
    "ロイ": "Roy",
    "リーフ": "Leif",
    "ルキナ": "Lucina",
    "リン": "Lyn",
    "エイリーク": "Eirika",
    "カムイ": "Corrin",
    "ブレイク": "Break",
    "防御時": "On Defense",
    "無効化": "Nullify",
    "魔法": "Magic",
    "絆の指輪": "Bond Ring",
    "共同": "Co-op",
    "撃目": "Hit",
    "判定": "Check",
    "追撃": "Follow-Up",
    "足狙い": "Leg Strike",
    "弱点変化": "Weakness Shift",
    "攻撃属性": "Atk Attribute",
    "ロプトウス": "Loptr",
    "メディウス": "Medeus",
    "ディミトリ": "Dimitri",
    "エーデルガルト": "Edelgard",
    "クロード": "Claude",
    "ヘクトル": "Hector",
    "セロ": "Soren",
    "カミラ": "Camilla",
    "クロム": "Chrom",
    "ヴェロニカ": "Veronica",
    "チキ": "Tiki",
    "チェインガード許可": "Chain Guard Allowed",
    "弓砲台": "Ballista",
    "魔砲台": "Magic Cannon",
    "毒": "Poison",
    "猛毒": "Deadly Poison",
    "劇毒": "Severe Poison",
    "沈黙": "Silence",
    "弱体化": "Debuff",
    "気絶": "Stun",
    "強化": "Buff",
    "スマッシュ": "Smash",
    "確率被ダメ半減": "Halve Damage (Chance)",
    "必中": "Sure Strike",
}

def to_int(val, default=0):
    if val is None:
        return default
    val_str = str(val).strip()
    if not val_str:
        return default
    try:
        return int(val_str)
    except ValueError:
        return default

def cargar_traducciones():
    """Carga mapeo completo de identificadores a nombres oficiales en inglés."""
    traducciones = {}

    # 1. Cargar todas las traducciones oficiales en inglés (fe_assets_message/us/usen/csv)
    if os.path.exists(USEN_DIR):
        for fname in os.listdir(USEN_DIR):
            if fname.endswith(".csv"):
                fpath = os.path.join(USEN_DIR, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    for row in reader:
                        if len(row) >= 2 and row[0]:
                            k = row[0].strip().lstrip("\ufeff")
                            v = row[1].strip()
                            traducciones[k] = v
                            for pfx in ["MIID_", "MJID_", "MPID_", "MSID_", "MGID_", "MID_"]:
                                if k.startswith(pfx):
                                    traducciones[k[len(pfx):]] = v

    # 2. Cargar traducciones desde translations/fee-translations.csv
    trans_file = os.path.join(TRANS_DIR, "fee-translations.csv")
    if os.path.exists(trans_file):
        with open(trans_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 3 and row[0] and row[2]:
                    en = row[0].strip()
                    jp = row[2].strip()
                    traducciones[jp] = en
                    traducciones[en] = en
                    for pfx in ["PID_", "JID_", "IID_", "SID_", "GID_", "MID_", "MSID_", "MJID_", "MIID_", "MPID_", "MGID_"]:
                        traducciones[f"{pfx}{jp}"] = en
                        traducciones[f"{pfx}{en}"] = en

    # 3. Cargar traducciones específicas de Item, Job, Person, Skill
    for fname in ["Item.csv", "Job.csv", "Person.csv", "Skill.csv"]:
        fpath = os.path.join(TRANS_DIR, fname)
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                for row in reader:
                    if len(row) >= 2 and row[0]:
                        key = row[0].strip().lstrip("\ufeff")
                        name_en = row[1].strip() if row[1] else key
                        jp = row[2].strip() if len(row) > 2 and row[2] else ""
                        traducciones[key] = name_en
                        traducciones[f"MID_{key}"] = name_en
                        traducciones[f"MID_JOB_{key}"] = name_en
                        traducciones[f"MID_ITEM_{key}"] = name_en
                        traducciones[f"MID_PERSON_{key}"] = name_en
                        traducciones[f"MID_SKILL_{key}"] = name_en
                        traducciones[f"MSID_{key}"] = name_en
                        traducciones[f"SID_{key}"] = name_en
                        traducciones[f"IID_{key}"] = name_en
                        traducciones[f"JID_{key}"] = name_en
                        traducciones[f"PID_{key}"] = name_en
                        if jp:
                            traducciones[jp] = name_en
                            traducciones[f"SID_{jp}"] = name_en
                            traducciones[f"IID_{jp}"] = name_en
                            traducciones[f"JID_{jp}"] = name_en
                            traducciones[f"PID_{jp}"] = name_en

    # 4. Añadir términos japoneses directos del fallback
    for jp_term, en_term in JAPANESE_FALLBACK_TERMS.items():
        traducciones[jp_term] = en_term
        for pfx in ["PID_", "JID_", "IID_", "SID_", "GID_", "MID_"]:
            traducciones[f"{pfx}{jp_term}"] = en_term

    return traducciones

def parsear_xml_generico(filepath):
    """Parsea un archivo XML del datamine y devuelve una lista de diccionarios de filas de todas las Sheets."""
    if not os.path.exists(filepath):
        print(f"Aviso: {filepath} no encontrado.")
        return []

    tree = ET.parse(filepath)
    root = tree.getroot()
    
    filas = []
    for sheet in root.findall("Sheet"):
        data_elem = sheet.find("Data")
        if data_elem is None:
            continue
        for row in data_elem.findall("Param"):
            d = {}
            for k, v in row.attrib.items():
                d[k] = v
            filas.append(d)

    return filas

# Mapeo oficial de Kind en FE Engage
TIPO_ARMA_KIND = {
    "1": "Espada",
    "2": "Lanza",
    "3": "Hacha",
    "4": "Arco",
    "5": "Daga",
    "6": "Tomo",
    "7": "Bastón",
    "8": "Artes",
    "9": "Especial",
    "10": "Objeto",
    "11": "Accesorio",
}

def limpiar_nombre(ident, name_tag, trans):
    """Obtiene un nombre legible en inglés a partir del identificador de mensaje."""
    # 1. Intentar con name_tag directo
    if name_tag and name_tag in trans:
        return trans[name_tag]
    if ident in trans:
        return trans[ident]

    # 2. Desglosar prefijos
    raw_str = name_tag or ident
    for pfix in ["MIID_H_", "MIID_HE_", "MIID_", "MJID_", "MPID_", "MSID_", "MGID_", "MRID_", "MID_", "IID_", "JID_", "PID_", "SID_", "GID_", "RID_"]:
        if raw_str.startswith(pfix):
            raw_str = raw_str[len(pfix):]
            break

    if raw_str in trans:
        return trans[raw_str]

    # 3. Separar por guiones bajos y traducir componentes
    parts = []
    for p in raw_str.split("_"):
        t = trans.get(p, trans.get(f"MID_{p}", JAPANESE_FALLBACK_TERMS.get(p, p)))
        parts.append(t)
    res = " ".join(parts)

    # 4. Reemplazos finales de términos japoneses residuales
    for jp_k, en_v in JAPANESE_FALLBACK_TERMS.items():
        if jp_k in res:
            res = res.replace(jp_k, en_v)

    # 5. Limpieza de caracteres japoneses residuales en scripts internos
    jp_re = re.compile(r'[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]+')
    if jp_re.search(res):
        res = jp_re.sub('', res).strip()
        res = re.sub(r'\s+', ' ', res).strip()

    return res if res else ident.replace("SID_", "").replace("IID_", "").replace("PID_", "").replace("JID_", "")

def compilar():
    print("=== Iniciando compilación de catálogo FE Engage desde Datamine ===")
    trans = cargar_traducciones()
    print(f"Traducciones cargadas: {len(trans)}")

    # 1. Armas e Ítems
    items_raw = parsear_xml_generico(os.path.join(DATAMINE_DIR, "Item.xml"))
    armas = {}
    for it in items_raw:
        iid = it.get("Iid")
        if not iid or iid.startswith("IID_None"):
            continue

        name_tag = it.get("Name")
        if iid in armas and not name_tag:
            continue

        kind_code = str(it.get("Kind", "0"))
        tipo_str = TIPO_ARMA_KIND.get(kind_code, "Espada")
        nombre = limpiar_nombre(iid, name_tag, trans)
        
        # Atributos de combate
        mt = to_int(it.get("Power"))
        wt = to_int(it.get("Weight"))
        hit = to_int(it.get("Hit"))
        crit = to_int(it.get("Critical"))
        avo = to_int(it.get("Avoid"))
        ddg = to_int(it.get("Secure"))
        
        range_i = to_int(it.get("RangeI"), 1)
        range_o = to_int(it.get("RangeO"), 1)
        if range_i == range_o:
            rango = [range_i]
        else:
            rango = list(range(range_i, range_o + 1))

        # Magia / Física (WeaponAttr: 2 suele ser Mágica, o Flag con bit 65536 para Levin Sword, Flame Lance, Hurricane Axe, Radiant Bow)
        attr = it.get("WeaponAttr", "0")
        flag_val = to_int(it.get("Flag", 0))
        es_magica = (tipo_str == "Tomo" or str(attr) in ("2", "3") or bool(flag_val & 65536) or iid in ("IID_いかづちの剣", "IID_ほのおの槍", "IID_かぜの大斧", "IID_光の弓"))

        # Efectividades — vienen en EquipSids separadas por ;
        # Mapeamos los SIDs a tipos de movimiento legibles
        SID_A_EFECTIVIDAD = {
            "SID_飛行特効": "volador",
            "SID_鎧特効":   "acorazado",
            "SID_馬特効":   "caballería",
            "SID_竜特効":   "dragón",
            "SID_異形特効": "monstruo",
        }
        equip_sids_raw = it.get("EquipSids", "")
        efectividades = []
        for sid in equip_sids_raw.split(";"):
            sid = sid.strip()
            if sid in SID_A_EFECTIVIDAD:
                efectividades.append(SID_A_EFECTIVIDAD[sid])

        # Durabilidad / Usos máximos (Endurance)
        endurance_val = it.get("Endurance", "1")
        endurance_int = to_int(endurance_val, 1)
        usos_max = endurance_int if (1 < endurance_int < 255) else (1 if tipo_str == "Objeto" else None)

        # Mapeo de nombres en español comunes para consumibles
        ALIASES_ESPANOL = {
            "IID_傷薬": "Poción",
            "IID_特効薬": "Elixir",
            "IID_聖水": "Agua pura",
            "IID_毒消し": "Antídoto",
            "IID_たいまつ": "Antorcha",
        }
        if iid in ALIASES_ESPANOL:
            nombre = ALIASES_ESPANOL[iid]

        # Distinguir versiones de tutorial/prólogo o eventos especiales
        if iid.endswith("_M000"):
            nombre = f"{nombre} (Prólogo)"
        elif "_M0" in iid or "_敵" in iid:
            nombre = f"{nombre} (Evento)"

        armas[iid] = {
            "id": iid,
            "nombre": nombre,
            "tipo": tipo_str,
            "mt": mt,
            "wt": wt,
            "hit": hit,
            "crit": crit,
            "avo": avo,
            "ddg": ddg,
            "rango": rango,
            "es_magica": es_magica,
            "precio": to_int(it.get("Price")),
            "usos_max": usos_max,
            "efectividades": efectividades,  # e.g. ["volador"], ["acorazado", "caballería"]
        }

    print(f"Armas e ítems procesados: {len(armas)}")

    # 2. Clases (Jobs)
    jobs_raw = parsear_xml_generico(os.path.join(DATAMINE_DIR, "Job.xml"))
    clases = {}
    for j in jobs_raw:
        jid = j.get("Jid")
        if not jid:
            continue

        name_tag = j.get("Name")
        if jid in clases and not name_tag:
            continue

        nombre = limpiar_nombre(jid, name_tag, trans)
        
        # Distinción de clases reales compartidas con el mismo nombre en la traducción
        CLASES_DISAMBIGUATION = {
            "JID_アヴニール下級": "Noble (Caballería)",
            "JID_フロラージュ下級": "Noble (Mística)",
            "JID_スュクセサール下級": "Lord (Diamant)",
            "JID_ティラユール下級": "Lord (Alcryst)",
            "JID_リンドブルム下級": "Wing Tamer (Ivy)",
            "JID_スレイプニル下級": "Wing Tamer (Hortensia)",
            "JID_ピッチフォーク下級": "Sentinel (Timerra)",
            "JID_クピードー下級": "Sentinel (Fogado)",
        }
        if jid in CLASES_DISAMBIGUATION:
            nombre = CLASES_DISAMBIGUATION[jid]

        style = j.get("StyleName", "None")
        mov = to_int(j.get("Base.Move"), 5)

        # Tipo de movimiento (MoveType del datamine)
        MOVE_TYPE_MAP = {
            "1": "infantería",
            "2": "caballería",
            "3": "volador",
            "4": "acorazado",
        }
        move_type_raw = j.get("MoveType", "1")
        tipo_movimiento = MOVE_TYPE_MAP.get(str(move_type_raw), "infantería")

        clases[jid] = {
            "id": jid,
            "nombre": nombre,
            "estilo_combate": style,
            "mov": mov,
            "tipo_movimiento": tipo_movimiento,
            "base_stats": {
                "hp": to_int(j.get("Base.Hp")),
                "str": to_int(j.get("Base.Str")),
                "mag": to_int(j.get("Base.Magic")),
                "dex": to_int(j.get("Base.Tech")),
                "spd": to_int(j.get("Base.Quick")),
                "def": to_int(j.get("Base.Def")),
                "res": to_int(j.get("Base.Mdef")),
                "lck": to_int(j.get("Base.Luck")),
                "bld": to_int(j.get("Base.Phys")),
            },
            "growths": {
                "hp": to_int(j.get("DiffGrow.Hp")) or to_int(j.get("GrowRatio.Hp")),
                "str": to_int(j.get("DiffGrow.Str")) or to_int(j.get("GrowRatio.Str")),
                "mag": to_int(j.get("DiffGrow.Magic")) or to_int(j.get("GrowRatio.Magic")),
                "dex": to_int(j.get("DiffGrow.Tech")) or to_int(j.get("GrowRatio.Tech")),
                "spd": to_int(j.get("DiffGrow.Quick")) or to_int(j.get("GrowRatio.Quick")),
                "def": to_int(j.get("DiffGrow.Def")) or to_int(j.get("GrowRatio.Def")),
                "res": to_int(j.get("DiffGrow.Mdef")) or to_int(j.get("GrowRatio.Mdef")),
                "lck": to_int(j.get("DiffGrow.Luck")) or to_int(j.get("GrowRatio.Luck")),
                "bld": to_int(j.get("DiffGrow.Phys")) or to_int(j.get("GrowRatio.Phys")),
            },
            "max_stats": {
                "hp": to_int(j.get("Limit.Hp")),
                "str": to_int(j.get("Limit.Str")),
                "mag": to_int(j.get("Limit.Magic")),
                "dex": to_int(j.get("Limit.Tech")),
                "spd": to_int(j.get("Limit.Quick")),
                "def": to_int(j.get("Limit.Def")),
                "res": to_int(j.get("Limit.Mdef")),
                "lck": to_int(j.get("Limit.Luck")),
                "bld": to_int(j.get("Limit.Phys")),
            },
            "enemy_growths": {
                "base": {
                    "hp": to_int(j.get("BaseGrow.Hp")),
                    "str": to_int(j.get("BaseGrow.Str")),
                    "mag": to_int(j.get("BaseGrow.Magic")),
                    "dex": to_int(j.get("BaseGrow.Tech")),
                    "spd": to_int(j.get("BaseGrow.Quick")),
                    "def": to_int(j.get("BaseGrow.Def")),
                    "res": to_int(j.get("BaseGrow.Mdef")),
                    "lck": to_int(j.get("BaseGrow.Luck")),
                    "bld": to_int(j.get("BaseGrow.Phys")),
                },
                "hard": {
                    "hp": to_int(j.get("DiffGrow.Hp")),
                    "str": to_int(j.get("DiffGrow.Str")),
                    "mag": to_int(j.get("DiffGrow.Magic")),
                    "dex": to_int(j.get("DiffGrow.Tech")),
                    "spd": to_int(j.get("DiffGrow.Quick")),
                    "def": to_int(j.get("DiffGrow.Def")),
                    "res": to_int(j.get("DiffGrow.Mdef")),
                    "lck": to_int(j.get("DiffGrow.Luck")),
                    "bld": to_int(j.get("DiffGrow.Phys")),
                },
                "lunatic": {
                    "hp": to_int(j.get("DiffGrowLunatic.Hp")),
                    "str": to_int(j.get("DiffGrowLunatic.Str")),
                    "mag": to_int(j.get("DiffGrowLunatic.Magic")),
                    "dex": to_int(j.get("DiffGrowLunatic.Tech")),
                    "spd": to_int(j.get("DiffGrowLunatic.Quick")),
                    "def": to_int(j.get("DiffGrowLunatic.Def")),
                    "res": to_int(j.get("DiffGrowLunatic.Mdef")),
                    "lck": to_int(j.get("DiffGrowLunatic.Luck")),
                    "bld": to_int(j.get("DiffGrowLunatic.Phys")),
                }
            }
        }

    print(f"Clases procesadas: {len(clases)}")

    # 3. Personajes (Person)
    persons_raw = parsear_xml_generico(os.path.join(DATAMINE_DIR, "Person.xml"))
    personajes = {}
    for p in persons_raw:
        pid = p.get("Pid")
        if not pid or pid.startswith("PID_None"):
            continue

        name_tag = p.get("Name")
        if pid in personajes and not name_tag:
            continue

        nombre = limpiar_nombre(pid, name_tag, trans)
        
        # Stats base personales (Base + OffsetN)
        p_bases = {
            "hp": to_int(p.get("Base.Hp")) + to_int(p.get("OffsetN.Hp")),
            "str": to_int(p.get("Base.Str")) + to_int(p.get("OffsetN.Str")),
            "mag": to_int(p.get("Base.Magic")) + to_int(p.get("OffsetN.Magic")),
            "dex": to_int(p.get("Base.Tech")) + to_int(p.get("OffsetN.Tech")),
            "spd": to_int(p.get("Base.Quick")) + to_int(p.get("OffsetN.Quick")),
            "def": to_int(p.get("Base.Def")) + to_int(p.get("OffsetN.Def")),
            "res": to_int(p.get("Base.Mdef")) + to_int(p.get("OffsetN.Mdef")),
            "lck": to_int(p.get("Base.Luck")) + to_int(p.get("OffsetN.Luck")),
            "bld": to_int(p.get("Base.Phys")) + to_int(p.get("OffsetN.Phys")),
        }

        # Crecimientos personales
        p_growths = {
            "hp": to_int(p.get("Grow.Hp")) or to_int(p.get("BaseGrow.Hp")),
            "str": to_int(p.get("Grow.Str")) or to_int(p.get("BaseGrow.Str")),
            "mag": to_int(p.get("Grow.Magic")) or to_int(p.get("BaseGrow.Magic")),
            "dex": to_int(p.get("Grow.Tech")) or to_int(p.get("BaseGrow.Tech")),
            "spd": to_int(p.get("Grow.Quick")) or to_int(p.get("BaseGrow.Quick")),
            "def": to_int(p.get("Grow.Def")) or to_int(p.get("BaseGrow.Def")),
            "res": to_int(p.get("Grow.Mdef")) or to_int(p.get("BaseGrow.Mdef")),
            "lck": to_int(p.get("Grow.Luck")) or to_int(p.get("BaseGrow.Luck")),
            "bld": to_int(p.get("Grow.Phys")) or to_int(p.get("BaseGrow.Phys")),
        }

        default_jid = p.get("Jid", "")
        join_lvl = to_int(p.get("Level"), 1)
        clase_def = clases.get(default_jid, {})
        c_bases = clase_def.get("base_stats", {})
        c_growths = clase_def.get("growths", {})

        # Estadísticas canónicas exactas al unirse (Serenes Forest / Juego oficial)
        join_stats = {}
        lvl_diff = max(0, join_lvl - 1)
        for stat in ["hp", "str", "mag", "dex", "spd", "def", "res", "lck", "bld"]:
            b = c_bases.get(stat, 0) + p_bases.get(stat, 0)
            g = c_growths.get(stat, 0) + p_growths.get(stat, 0)
            join_stats[stat] = b + int(g * lvl_diff / 100.0)
        
        personajes[pid] = {
            "id": pid,
            "nombre": nombre,
            "jid_default": default_jid,
            "clase_default": clase_def.get("nombre", ""),
            "nivel_base": join_lvl,
            "base_stats": p_bases,
            "growths": p_growths,
            "join_stats": join_stats,
        }

    print(f"Personajes procesados: {len(personajes)}")

    # 4. Habilidades (Skill)
    skills_raw = parsear_xml_generico(os.path.join(DATAMINE_DIR, "Skill.xml"))
    habilidades = {}
    for s in skills_raw:
        sid = s.get("Sid")
        if not sid or sid.startswith("SID_None"):
            continue

        name_tag = s.get("Name")
        if sid in habilidades and not name_tag:
            continue

        nombre = limpiar_nombre(sid, name_tag, trans)

        habilidades[sid] = {
            "id": sid,
            "nombre": nombre,
            "icono": s.get("IconName", ""),
            "stat_boosts": {
                "hp": to_int(s.get("Enhance.Hp")),
                "str": to_int(s.get("Enhance.Str")),
                "mag": to_int(s.get("Enhance.Magic")),
                "dex": to_int(s.get("Enhance.Tech")),
                "spd": to_int(s.get("Enhance.Quick")),
                "def": to_int(s.get("Enhance.Def")),
                "res": to_int(s.get("Enhance.Mdef")),
                "lck": to_int(s.get("Enhance.Luck")),
                "bld": to_int(s.get("Enhance.Phys")),
                "mov": to_int(s.get("Enhance.Move")),
            },
            "combat_mods": {
                "power": to_int(s.get("Power")),
                "hit": to_int(s.get("Hit")),
                "crit": to_int(s.get("Critical")),
                "avo": to_int(s.get("Avoid")),
                "ddg": to_int(s.get("Secure")),
            }
        }

    print(f"Habilidades procesadas: {len(habilidades)}")

    # 5. Emblemas (God) — Extracción en dos pasadas
    gods_raw = parsear_xml_generico(os.path.join(DATAMINE_DIR, "God.xml"))
    
    # Pasada 1: Tablas de crecimiento de Engage (armas, habilidades synchro y habilidades engage hasta nivel 10)
    tablas_crecimiento = {}
    current_ggid = None
    for g in gods_raw:
        g_ggid = g.get("Ggid")
        if g_ggid:
            current_ggid = g_ggid
            if current_ggid not in tablas_crecimiento:
                tablas_crecimiento[current_ggid] = {"items": [], "skills": [], "synchro_skills": []}
        if current_ggid:
            lvl_str = g.get("Level")
            if lvl_str and lvl_str.isdigit():
                lvl = int(lvl_str)
                if 1 <= lvl <= 10:
                    e_items = g.get("EngageItems", "")
                    if e_items:
                        for iid in e_items.split(";"):
                            iid = iid.strip()
                            if iid and iid not in tablas_crecimiento[current_ggid]["items"]:
                                tablas_crecimiento[current_ggid]["items"].append(iid)
                    e_skills = g.get("EngageSkills", "")
                    if e_skills:
                        for sid in e_skills.split(";"):
                            sid = sid.strip()
                            if sid and sid not in tablas_crecimiento[current_ggid]["skills"]:
                                tablas_crecimiento[current_ggid]["skills"].append(sid)
                    s_skills = g.get("SynchroSkills", "")
                    if s_skills:
                        for sid in s_skills.split(";"):
                            sid = sid.strip()
                            if sid and sid not in tablas_crecimiento[current_ggid]["synchro_skills"]:
                                tablas_crecimiento[current_ggid]["synchro_skills"].append(sid)

    # Pasada 2: Registro maestro de Emblemas (GID_*)
    emblemas = {}
    for g in gods_raw:
        gid = g.get("Gid")
        if not gid:
            continue

        # Filtrar duplicados de scripts de eventos / enemigos de capítulos / marcadores vacíos
        if gid.startswith("GID_M0") or "相手" in gid or "敵" in gid:
            continue

        mid = g.get("Mid", "")
        ascii_name = g.get("AsciiName", "")
        nombre = trans.get(mid) or ascii_name or limpiar_nombre(gid, g.get("Name"), trans)
        if not nombre or nombre.startswith("GID_") or nombre == "???":
            continue

        gt = g.get("GrowTable", "")
        engage_items = list(tablas_crecimiento.get(gt, {}).get("items", []))
        engage_skills = list(tablas_crecimiento.get(gt, {}).get("skills", []))
        synchro_skills = list(tablas_crecimiento.get(gt, {}).get("synchro_skills", []))

        emblemas[gid] = {
            "id": gid,
            "nombre": nombre,
            "ascii_name": ascii_name,
            "link_name": g.get("LinkName", ""),
            "grow_table": gt,
            "engage_items": engage_items,
            "engage_skills": engage_skills,
            "synchro_skills": synchro_skills,
        }

    print(f"Emblemas procesados: {len(emblemas)}")

    # Guardar catálogo maestro compilado
    catalogo_final = {
        "armas": armas,
        "clases": clases,
        "personajes": personajes,
        "habilidades": habilidades,
        "emblemas": emblemas,
    }

    output_path = os.path.join(BASE_DIR, "catalogo_engage.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(catalogo_final, f, indent=2, ensure_ascii=False)

    print(f"\n[OK] Catalogo maestro compilado con exito: {output_path}")
    print(f"Tamano total: {os.path.getsize(output_path) / 1024:.1f} KB")

if __name__ == "__main__":
    compilar()
