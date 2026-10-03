"""
cargador_dispos.py — Lector y Conversor de Despliegues Oficiales de Fire Emblem Engage
Extrae las disposiciones exactas de enemigos, aliados, niveles y armas de la carpeta dispos/
del datamine de FE Engage (FE17-DOC-main).
"""

import os
import sys
import json
import re
import xml.etree.ElementTree as ET
from typing import List, Dict, Tuple, Optional
from motor_calculo import resolver_estilo_combate

# Rutas base
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
from compilar_catalogo import DATAMINE_DIR   # el datamine activo (FE17_200 o el público)
DISPOS_DIR = os.path.join(DATAMINE_DIR, "dispos")
SCRIPTS_DIR = os.path.join(BASE_DIR, "FE17-DOC-main", "FE17-DOC-main", "fe_assets_scripts")

_CONDICION_VICTORIA_CACHE = {}
_PIDS_JEFE_CACHE = {}


def pids_jefe(dispos_id: str) -> set:
    """PIDs de los jefes del capítulo: filas enemigas del dispos con el bit 16 del Flag."""
    clave = (dispos_id or "").upper()
    if clave in _PIDS_JEFE_CACHE:
        return _PIDS_JEFE_CACHE[clave]
    salida = set()
    ruta = os.path.join(DISPOS_DIR, f"{clave}.xml")
    try:
        for param in ET.parse(ruta).getroot().findall(".//Data/Param"):
            flag = param.get("Flag", "0")
            if param.get("Force") == "1" and flag.isdigit() and int(flag) & 16 and param.get("Pid"):
                salida.add(param.get("Pid"))
    except (OSError, ET.ParseError):
        pass
    _PIDS_JEFE_CACHE[clave] = salida
    return salida


def condicion_victoria(dispos_id: str) -> str:
    """
    Condición de victoria del capítulo según su guion (.lua):
      "jefe"       WinRuleSetDestroyBoss(true)            → derrotar al jefe termina el mapa
      "exterminio" WinRuleSetEnemyNumberLessThanOrEqualTo → derrotar a todos los enemigos
      ""           otra (escapar, sobrevivir X turnos, llegar a una casilla…) o sin guion
    """
    clave = (dispos_id or "").upper()
    if clave in _CONDICION_VICTORIA_CACHE:
        return _CONDICION_VICTORIA_CACHE[clave]
    resultado = ""
    ruta = os.path.join(SCRIPTS_DIR, f"{clave}.lua")
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            txt = f.read()
        if re.search(r"WinRuleSetDestroyBoss\(\s*true\s*\)", txt):
            resultado = "jefe"
        elif re.search(r"WinRuleSetEnemyNumberLessThanOrEqualTo\(", txt):
            resultado = "exterminio"
    except OSError:
        resultado = ""
    _CONDICION_VICTORIA_CACHE[clave] = resultado
    return resultado

# Unidades que el guion del capítulo mueve antes de dar el control al jugador
# (UnitMovePos en el evento de apertura del .lua). {dispos_id: {pid: (X, Y)}} en
# coordenadas del datamine (1-indexed, Y=1 fila inferior).
# Pasivas observadas en el juego que el datamine NO asigne para esa dificultad.
# {dispos_id: {dificultad_norm: {pid: [SIDs]}}}. Se suman a las del datamine
# (CommonSids + {Normal,Hard,Lunatic}Sids de Person.xml + Sid de la fila del dispos).
# Vacío a día de hoy: lo observado en Extremo (Veteran+ en Kagetsu/Zelkov/Ivy,
# Ivy sin Stalwart) coincide exactamente con Person.xml (LunaticSids / HardSids).
PASIVAS_OBSERVADAS = {}

# Pasivas que el datamine asigne para esa dificultad pero que en el juego NO
# aparezcan (observado): se retiran tras aplicar todo lo demás. Misma estructura.
PASIVAS_AUSENTES = {}


def _dificultad_norm(dificultad: str) -> str:
    d = (dificultad or "").lower()
    if d in ("extremo", "lunatic", "maddening"):
        return "lunatic"
    if d in ("dificil", "difícil", "hard"):
        return "hard"
    return "normal"


# Emblemas que el guion entrega por evento y que por eso NO aparecen en el atributo
# Gid del dispos: en M007 la cinemática le da a Hortensia el Emblema Oscuro de Lucina.
# Clave: el pid, o "pid@X,Y" (casilla del dispos) cuando varias filas comparten pid.
EMBLEMA_POR_EVENTO = {
    "M007": {"PID_M007_オルテンシア": "GID_M007_敵ルキナ"},
    # M011: seis anillos en tropas Corrupted (según la guía del capítulo) y, cuando
    # aparecen, los Cuatro Sabuesos con los suyos (Zephia & Marth, Griss & Celica,
    # Mauvier & Micaiah, Marni & Sigurd).
    "M011": {
        "PID_アイビー": "GID_リン",   # Ivy llega con Lyn
        "PID_M011_異形兵_アクスナイト@7,29": "GID_M011_敵シグルド",
        "PID_M011_異形兵_モンク@9,28": "GID_M011_敵ミカヤ",
        "PID_M011_異形兵_ソードペガサス@3,18": "GID_M011_敵マルス",
        "PID_M011_異形兵_アクスファイター@11,16": "GID_M011_敵ロイ",
        "PID_M011_異形兵_ランスファイター@7,12": "GID_M011_敵リーフ",
        "PID_M011_異形兵_マージ@9,8": "GID_M011_敵セリカ",
        "PID_M011_セピア": "GID_M011_敵マルス",
        "PID_M011_グリ": "GID_M011_敵セリカ",
        "PID_M011_モーヴ": "GID_M011_敵ミカヤ",
        "PID_M011_マロン": "GID_M011_敵シグルド",
    },
}

RECOLOCACIONES_APERTURA = {
    # M008: Amber aparece en (8,14) y el evento inicial lo lleva junto a Diamant
    "M008": {"PID_アンバー": (8, 16)},
    # M010 (配置調整): la apertura baja a Hortensia al vestíbulo (junto a los pozos de
    # Emblema) y sube a Hyacinth al fondo del trono. UnitSetPos del .lua.
    "M010": {"PID_M010_オルテンシア": (9, 12), "PID_M010_ハイアシンス": (9, 30)},
}


# Calendario de refuerzos por capítulo, extraído de EventEntryTurn(...) en el .lua del
# mapa: {dispos_id: {turno: [grupos del dispos]}}. Aparecen al INICIO de la fase de
# jugador de ese turno. Los grupos "_Normal" / "_Lunatic" ya vienen filtrados por el
# Flag de dificultad de cada fila, así que se listan todos y el flag decide.
CALENDARIO_REFUERZOS = {
    # M010.lua: EventEntryTurn(シーフ登場と魔砲台のAI変更, 2, 2) → Dispos("Thief") solo si
    # NO es Extremo (`if not モードはルナティック()`); el Flag 3 de esas filas ya lo filtra.
    "M010": {
        2: ["Thief"],
    },
    # M012.lua: los refuerzos de Difícil/Extremo son EventEntryTurn(増援N, 3/4/6, FORCE_ALLY):
    # llegan en la fase aliada (verde) de esos turnos, que va tras la enemiga, así que el
    # jugador los ve al empezar los turnos 4, 5 y 7 (lo que dicen las guías). En Normal
    # llegan un turno más tarde (4/5/7 en la fase aliada) y la herramienta no lo distingue.
    # Reinforcement1_4 solo en Difícil y superiores; su Flag ya lo filtra.
    "M012": {
        4: ["Reinforcement1_1", "Reinforcement1_2", "Reinforcement1_3", "Reinforcement1_4"],
        5: ["Reinforcement2_1", "Reinforcement2_2"],
        7: ["Reinforcement3_1", "Reinforcement3_2"],
    },
    "M008": {
        2: ["Enemy_Reinforcement0", "Enemy_Reinforcement0_Normal"],
        3: ["Enemy_Reinforcement1", "Enemy_Reinforcement1_Normal"],
        4: ["Enemy_Reinforcement2", "Enemy_Reinforcement2_1", "Enemy_Reinforcement2_Normal"],
        5: ["Enemy_Reinforcement3", "Enemy_Reinforcement3_Normal"],
        7: ["Enemy_Reinforcement4", "Enemy_Reinforcement4_1",
            "Enemy_Reinforcement６_Lunatic1", "Enemy_Reinforcement６_Lunatic1_1"],
    },
}


# Refuerzos disparados por un EVENTO del guion, no por turno: en el .lua, una función
# `判定_<evento>` comprueba que la unidad `pid` está en la casilla (x, z) y entonces
# `<evento>` hace Dispos(grupo). Coordenadas en el sistema del datamine (1-indexed,
# Y=1 fila inferior), igual que las filas del dispos. El grupo se retira del
# despliegue inicial y el tablero lo coloca cuando la unidad pisa la casilla.
# `disparos` lista las condiciones que lo activan (basta UNA, la primera que ocurra):
#   {"tipo": "casilla", "pid": ..., "casilla_datamine": (x, y)}  la unidad llega a la casilla
#   {"tipo": "combate", "pid": ...}   esa unidad entra en combate (g_flag_battle_*)
#   {"tipo": "muerte",  "pid": ...}   esa unidad cae (o tiene su conversación de combate)
#   {"tipo": "turno",   "turno": 6}   al empezar ese turno de jugador
#   {"tipo": "objeto",  "objeto_tipo": "puerta"}  se destruye/abre ese objeto del mapa
#   {"tipo": "fila", "fila_datamine": 7, "pid": ...}  esa unidad (sin pid: cualquiera del
#       jugador) llega a esa fila o más al sur (Y del datamine; en el tablero, y >= alto - 7)
# Opciones del evento: "junto_al_disparo" coloca el grupo en las casillas libres más
# cercanas a la unidad que lo disparó; "retira_emblemas" quita a quien los llevara los
# anillos que traen las unidades del grupo (guarda su versión sin anillo en "sin_emblema").
#   {"tipo": "accion",  "pid": ...}   esa unidad HACE algo que la herramienta no puede
#       observar (atacar o usar un bastón en la fase enemiga). Lo registra el jugador con
#       el botón del modal de esa unidad; al entrar en la fase enemiga se le recuerda.
# Se admite la forma antigua (`pid` + `casilla_datamine` sueltos = disparo por casilla).
REFUERZOS_POR_EVENTO = {
    # M011: cuando ALEAR llega a la fila Y=7 del datamine (y=23 en el tablero, en todo el
    # ancho; la línea roja de la guía) aparecen Ivy (con Lyn), Kagetsu y Zelkov junto a
    # Alear, los Cuatro Sabuesos arriba y cuatro Corrupted abajo, y se activan los
    # Corrupted Wyrm (AI_AC_FlagTrue: FLAG_四狗とアイビー登場_済). Observado en juego.
    # Ivy/Kagetsu/Zelkov salen en casillas algo aleatorias según por dónde cruce Alear: la
    # herramienta los pone en las libres más cercanas a él y el jugador los ajusta en su
    # modal. Los Sabuesos y los Corrupted del sur sí salen siempre en su sitio.
    # Cada Sabueso trae un anillo, y el Corrupted que lo llevaba lo pierde ("retira_emblemas").
    "M011": [
        {"grupo": grupo, "descripcion": desc,
         "disparos": [{"tipo": "fila", "fila_datamine": 7, "pid": "PID_リュール"}], **extra}
        for grupo, desc, extra in (
            ("Ally_Add0", "Alear llega a la fila 23 — Ivy (con Lyn) y Kagetsu se unen junto a él", {"junto_al_disparo": True}),
            ("Ally_Add1", "Alear llega a la fila 23 — Zelkov se une junto a él", {"junto_al_disparo": True}),
            ("Enemy_4dogs", "Alear llega a la fila 23 — los Cuatro Sabuesos se llevan los anillos", {"retira_emblemas": True}),
            ("Enemy_EV1", "Alear llega a la fila 23 — Corrupted por el sur", {}),
        )
    ],
    "M009": [
        # 砦到着_カゲツ: Kagetsu llega al fuerte norte → 2 Sword Fighters a ambos lados
        {"grupo": "Enemy_Kagetsu_Fort", "pid": "PID_M009_カゲツ", "casilla_datamine": (15, 16),
         "descripcion": "Kagetsu llega al fuerte del norte"},
        # 砦到着_ゼルコバ: Zelkov llega al fuerte sur → 2 Thieves a ambos lados
        {"grupo": "Enemy_Zelkova_Fort", "pid": "PID_M009_ゼルコバ", "casilla_datamine": (15, 2),
         "descripcion": "Zelkov llega al fuerte del sur"},
    ],
    "M010": [
        # オルテンシア行動変化 (condition: g_flag_battle_holtencia == 1): al entrar en combate
        # con Hortensia llegan 2 arqueros por los extremos de su misma fila. Las guías los
        # anotan como "turno 6" (es cuando se suele llegar a ella): vale lo que pase antes.
        # Verificado en juego: NO llegan en el turno 6 (las guías lo cuentan así porque es
        # cuando se suele llegar a ella), y no basta con combatir: basta con que Hortensia
        # HAGA ALGO — atacar, congelar con Freeze o recibir un ataque. Atacar o usar el
        # bastón ocurre en fase enemiga y la herramienta no lo ve, así que el disparo
        # "accion" lo registra el jugador desde el modal de la unidad.
        {"grupo": "Enemy_Reinforcement1", "descripcion": "Hortensia actúa — arquero por el oeste",
         "disparos": [{"tipo": "accion", "pid": "PID_M010_オルテンシア"},
                      {"tipo": "combate", "pid": "PID_M010_オルテンシア"}]},
        {"grupo": "Enemy_Reinforcement2", "descripcion": "Hortensia actúa — arquero por el este",
         "disparos": [{"tipo": "accion", "pid": "PID_M010_オルテンシア"},
                      {"tipo": "combate", "pid": "PID_M010_オルテンシア"}]},
        # 増援 (condition_増援: Morion muere, queda fijado o tiene su conversación de combate).
        # Morion está pasada la puerta, así que en la práctica ocurre al abrirla: las guías lo
        # describen como "tras abrir la puerta"; aparecen en las escaleras junto a Hyacinth.
        {"grupo": "Enemy_Reinforcement3", "descripcion": "Cae Morion o se abre la puerta — jinete con espada (escalera izquierda)",
         "disparos": [{"tipo": "muerte", "pid": "PID_M010_異形兵_モリオン"}, {"tipo": "objeto", "objeto_tipo": "puerta"}]},
        {"grupo": "Enemy_Reinforcement4", "descripcion": "Cae Morion o se abre la puerta — jinete con hacha (escalera derecha)",
         "disparos": [{"tipo": "muerte", "pid": "PID_M010_異形兵_モリオン"}, {"tipo": "objeto", "objeto_tipo": "puerta"}]},
    ],
}


# Aliados verdes (Force=2) que NO se unen al empezar el mapa: hay que gastar la
# acción de una unidad concreta (adyacente) para hablar con ellos. Hasta entonces
# los mueve la CPU y no son controlables. Del .lua: `<pid>加入_<hablante>()` → UnitJoin.
# {dispos_id: {pid del verde: [pids que pueden hablar con él]}}
UNION_POR_CONVERSACION = {
    # M009.lua: ジェーデ加入_リュール / ジェーデ加入_ディアマンド
    "M009": {"PID_ジェーデ": ["PID_リュール", "PID_ディアマンド"]},
}


# Tipo de cada aliado verde del dispos (Force 2). Tres tipos:
#   "inmediato"     se une al empezar la batalla (UnitJoin del turno 1: Cap. 7, 8, 12...):
#                   azul desde el Preset, en su casilla fija de aparición.
#   "conversacion"  sigue verde, lo mueve la CPU, hasta que le habla una unidad concreta
#                   (UNION_POR_CONVERSACION); entonces pasa a azul. Cap. 9: Jade.
#   "npc"           genérico que la CPU mueve toda la batalla: nunca se une, nunca se
#                   controla y no ataca. Cap. 12: los aldeanos de Solm.
# Por defecto se deduce del guion (ver tipo_de_aliado_verde); esta tabla manda cuando el
# datamine no lo deja claro. {dispos_id: {pid: tipo}}
TIPO_ALIADO = {}

_UNIONES_CACHE: dict = {}


def uniones_del_guion(dispos_id: str):
    """
    PIDs que el guion (.lua) une al ejército con UnitJoin("PID_…", …). None si no se puede
    saber: sin guion, sin UnitJoin, o alguna llamada con una variable (`UnitJoin( pid )`,
    Cap. 9, 15, 19…), porque entonces no se sabe a quién une.
    """
    clave = (dispos_id or "").upper()
    if clave not in _UNIONES_CACHE:
        resultado = None
        try:
            with open(os.path.join(SCRIPTS_DIR, f"{clave}.lua"), "r", encoding="utf-8") as f:
                llamadas = re.findall(r"UnitJoin\s*\(([^)]*)\)", f.read())
            argumentos = [a.strip() for ll in llamadas for a in ll.split(",") if a.strip()]
            if argumentos and all(a.startswith('"') for a in argumentos):
                resultado = {a.strip('"') for a in argumentos}
        except OSError:
            pass
        _UNIONES_CACHE[clave] = resultado
    return _UNIONES_CACHE[clave]


def _guion(dispos_id: str) -> str:
    try:
        with open(os.path.join(SCRIPTS_DIR, f"{(dispos_id or '').upper()}.lua"), "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def emblemas_del_guion(dispos_id: str) -> dict:
    """{pid: gid} de los anillos que el guion entrega al abrir el mapa con
    UnitCreateGodUnit("PID_…", "GID_…") (M013: Timerra llega con Ike)."""
    return {pid: gid for pid, gid in
            re.findall(r'UnitCreateGodUnit\s*\(\s*"(PID_[^"]+)"\s*,\s*"(GID_[^"]+)"', _guion(dispos_id))}


def movimientos_del_guion(dispos_id: str) -> dict:
    """{pid: (X, Y)} en coordenadas del datamine de los aliados que el guion recoloca con
    UnitMovePos("PID_…", X, Y) antes de unirlos (M013: la conversación del turno 1 mueve a
    Timerra, Panette y Merrin y luego UnitJoin). Solo los que el guion une."""
    unidos = uniones_del_guion(dispos_id) or set()
    return {pid: (int(x), int(y)) for pid, x, y in
            re.findall(r'UnitMovePos\s*\(\s*"(PID_[^"]+)"\s*,\s*(\d+)\s*,\s*(\d+)', _guion(dispos_id))
            if pid in unidos}


def tipo_de_aliado_verde(dispos_id: str, pid: str) -> str:
    """"inmediato", "conversacion" o "npc" (ver TIPO_ALIADO)."""
    clave = (dispos_id or "").upper()
    explicito = TIPO_ALIADO.get(clave, {}).get(pid)
    if explicito:
        return explicito
    if pid in UNION_POR_CONVERSACION.get(clave, {}):
        return "conversacion"
    uniones = uniones_del_guion(clave)
    if uniones is not None and pid not in uniones:
        return "npc"   # el guion une a otros por su nombre, a este nunca
    return "inmediato"


def _grupos_por_evento(dispos_id: str) -> set:
    return {e["grupo"] for e in REFUERZOS_POR_EVENTO.get((dispos_id or "").upper(), [])}


def _grupos_por_turno(dispos_id: str) -> set:
    """Grupos del dispos que el guion despliega en un turno concreto (CALENDARIO_REFUERZOS).
    No todos se llaman "Enemy_ReinforcementN" (M010: "Thief")."""
    return {g for grupos in CALENDARIO_REFUERZOS.get((dispos_id or "").upper(), {}).values() for g in grupos}


class CargadorDisposEngage:
    def __init__(self, ruta_catalogo: Optional[str] = None):
        _cat_json = os.path.join(BASE_DIR, "json", "catalogo_engage.json")
        self.ruta_catalogo = ruta_catalogo or (_cat_json if os.path.exists(_cat_json) else os.path.join(BASE_DIR, "catalogo_engage.json"))
        self.catalogo = {}
        if os.path.exists(self.ruta_catalogo):
            with open(self.ruta_catalogo, "r", encoding="utf-8") as f:
                self.catalogo = json.load(f)
        
        # Cargar diccionario de Person.xml
        self.persons = {}
        self._cargar_persons_xml()

    def _cargar_persons_xml(self):
        person_xml = os.path.join(DATAMINE_DIR, "Person.xml")
        if not os.path.exists(person_xml):
            return

        try:
            tree = ET.parse(person_xml)
            for p in tree.getroot().findall(".//Data/Param"):
                pid = p.get("Pid", "")
                if pid:
                    self.persons[pid] = {
                        "name_id": p.get("Name", ""),
                        "jid": p.get("Jid", ""),
                        "level": int(p.get("Level", 1)) if p.get("Level", "").isdigit() else 1,
                        # Inventario por defecto del personaje: el juego lo usa cuando la fila
                        # del dispos no lista objetos (Item1..6 vacíos), p.ej. Jade en M009.
                        "items": [i for i in p.get("Items", "").split(";") if i],
                        "auto_grow_offset_l": int(p.get("AutoGrowOffsetL", 0)) if p.get("AutoGrowOffsetL", "").lstrip("-").isdigit() else 0,
                        "auto_grow_offset_h": int(p.get("AutoGrowOffsetH", 0)) if p.get("AutoGrowOffsetH", "").lstrip("-").isdigit() else 0,
                        "auto_grow_offset_n": int(p.get("AutoGrowOffsetN", 0)) if p.get("AutoGrowOffsetN", "").lstrip("-").isdigit() else 0,
                        "offset_l": {
                            "hp": int(p.get("OffsetL.Hp", 0)) if p.get("OffsetL.Hp", "").lstrip("-").isdigit() else 0,
                            "str": int(p.get("OffsetL.Str", 0)) if p.get("OffsetL.Str", "").lstrip("-").isdigit() else 0,
                            "dex": int(p.get("OffsetL.Tech", 0)) if p.get("OffsetL.Tech", "").lstrip("-").isdigit() else 0,
                            "spd": int(p.get("OffsetL.Quick", 0)) if p.get("OffsetL.Quick", "").lstrip("-").isdigit() else 0,
                            "def": int(p.get("OffsetL.Def", 0)) if p.get("OffsetL.Def", "").lstrip("-").isdigit() else 0,
                            "mag": int(p.get("OffsetL.Magic", 0)) if p.get("OffsetL.Magic", "").lstrip("-").isdigit() else 0,
                            "res": int(p.get("OffsetL.Mdef", 0)) if p.get("OffsetL.Mdef", "").lstrip("-").isdigit() else 0,
                            "lck": int(p.get("OffsetL.Luck", 0)) if p.get("OffsetL.Luck", "").lstrip("-").isdigit() else 0,
                            "bld": int(p.get("OffsetL.Phys", 0)) if p.get("OffsetL.Phys", "").lstrip("-").isdigit() else 0,
                        },
                        "offset_h": {
                            "hp": int(p.get("OffsetH.Hp", 0)) if p.get("OffsetH.Hp", "").lstrip("-").isdigit() else 0,
                            "str": int(p.get("OffsetH.Str", 0)) if p.get("OffsetH.Str", "").lstrip("-").isdigit() else 0,
                            "dex": int(p.get("OffsetH.Tech", 0)) if p.get("OffsetH.Tech", "").lstrip("-").isdigit() else 0,
                            "spd": int(p.get("OffsetH.Quick", 0)) if p.get("OffsetH.Quick", "").lstrip("-").isdigit() else 0,
                            "def": int(p.get("OffsetH.Def", 0)) if p.get("OffsetH.Def", "").lstrip("-").isdigit() else 0,
                            "mag": int(p.get("OffsetH.Magic", 0)) if p.get("OffsetH.Magic", "").lstrip("-").isdigit() else 0,
                            "res": int(p.get("OffsetH.Mdef", 0)) if p.get("OffsetH.Mdef", "").lstrip("-").isdigit() else 0,
                            "lck": int(p.get("OffsetH.Luck", 0)) if p.get("OffsetH.Luck", "").lstrip("-").isdigit() else 0,
                            "bld": int(p.get("OffsetH.Phys", 0)) if p.get("OffsetH.Phys", "").lstrip("-").isdigit() else 0,
                        },
                        "offset_n": {
                            "hp": int(p.get("OffsetN.Hp", 0)) if p.get("OffsetN.Hp", "").lstrip("-").isdigit() else 0,
                            "str": int(p.get("OffsetN.Str", 0)) if p.get("OffsetN.Str", "").lstrip("-").isdigit() else 0,
                            "dex": int(p.get("OffsetN.Tech", 0)) if p.get("OffsetN.Tech", "").lstrip("-").isdigit() else 0,
                            "spd": int(p.get("OffsetN.Quick", 0)) if p.get("OffsetN.Quick", "").lstrip("-").isdigit() else 0,
                            "def": int(p.get("OffsetN.Def", 0)) if p.get("OffsetN.Def", "").lstrip("-").isdigit() else 0,
                            "mag": int(p.get("OffsetN.Magic", 0)) if p.get("OffsetN.Magic", "").lstrip("-").isdigit() else 0,
                            "res": int(p.get("OffsetN.Mdef", 0)) if p.get("OffsetN.Mdef", "").lstrip("-").isdigit() else 0,
                            "lck": int(p.get("OffsetN.Luck", 0)) if p.get("OffsetN.Luck", "").lstrip("-").isdigit() else 0,
                            "bld": int(p.get("OffsetN.Phys", 0)) if p.get("OffsetN.Phys", "").lstrip("-").isdigit() else 0,
                        },
                        "sids_lunatic": p.get("LunaticSids", ""),
                        "sids_hard": p.get("HardSids", ""),
                        "sids_normal": p.get("NormalSids", ""),
                        "sids_common": p.get("CommonSids", ""),
                    }
        except Exception as e:
            print(f"Aviso al parsear Person.xml: {e}")

    def resolver_nombre_item(self, iid: str) -> str:
        """Traduce IID_... a nombre legible en español/inglés desde catalogo_engage.json."""
        if not iid:
            return ""
        # Buscar en catálogo
        arma = self.catalogo.get("armas", {}).get(iid)
        if arma:
            nombre = arma.get("nombre", iid)
            usos_max = arma.get("usos_max")
            if usos_max and usos_max > 1:
                return f"{nombre} ({usos_max})"
            return nombre
        # Limpieza estándar si no está en catálogo
        limpio = iid.replace("IID_", "").replace("IID_E_", "")
        return limpio

    def resolver_nombre_personaje(self, pid: str, jid: str, x: int, y: int) -> str:
        """Determina un nombre claro e intuitivo para la unidad en inglés."""
        # Nombres de jefes / personajes únicos conocidos
        nombres_unicos = {
            "PID_M007_オルテンシア": "Hortensia (Boss)",
            "PID_M007_ロサード": "Rosado",
            "PID_M007_ゴルドマリー": "Goldmary",
            "PID_リュール": "Alear",
            "PID_スタルーク": "Alcryst",
            "PID_シトリニカ": "Citrinne",
            "PID_ラピス": "Lapis",
        }
        if pid in nombres_unicos:
            return nombres_unicos[pid]

        p_info = self.catalogo.get("personajes", {}).get(pid)
        if p_info and p_info.get("nombre"):
            nom = p_info["nombre"]
            nombres_genericos = {
                "Elusian Soldier", "Brodian Soldier", "Firenese Soldier", "Solm Soldier",
                "Corrupted", "Soldier", "Minion", "Enemy", "Demo", "Camera Setup"
            }
            if not nom.startswith("PID_") and nom not in nombres_genericos and not any(w in pid for w in ["兵", "雑魚", "汎用"]):
                return nom
            # Personajes con nombre propio convertidos en Corrupted (PID_M010_異形兵_モリオン,
            # MPID_MorphMorion): su PID lleva 兵 como la tropa, pero el juego los muestra con
            # su nombre ("Corrupted Morion"), no con la clase.
            propio = nom[len("Corrupted "):] if nom.startswith("Corrupted ") else ""
            if propio and any(p.get("nombre") == propio for p in self.catalogo.get("personajes", {}).values()):
                return nom

        # Si es un soldado genérico, usar la clase en inglés + coordenadas para ser identificable
        clase_info = self.catalogo.get("clases", {}).get(jid)
        clase_nom = clase_info.get("nombre", jid.replace("JID_", "")) if clase_info else jid.replace("JID_", "")
        return f"{clase_nom} ({x},{y})"

    def cargar_capitulo(self, dispos_id: str = "M007", dificultad: str = "Extremo", mapa_ancho: int = 24, mapa_alto: int = 17,
                        incluir_refuerzos: bool = False, sin_emblemas_de_guion: bool = False) -> List[dict]:
        """
        Lee el XML de dispos/{dispos_id}.xml y retorna la lista de diccionarios de unidades
        listas para ser enviadas a la UI o cargadas en EstadoTablero.

        El XML está dividido en grupos (una fila con `Group="Player"|"Enemy"|"Ally"|
        "Enemy_Reinforcement3"...` sin coordenadas abre el grupo; las filas siguientes
        pertenecen a él). Por defecto solo se devuelven los grupos INICIALES; los
        refuerzos (grupo que empieza por "Enemy_Reinforcement") se omiten salvo que
        `incluir_refuerzos` sea True — cada unidad lleva `grupo` y `es_refuerzo`.
        """
        ruta_xml = os.path.join(DISPOS_DIR, f"{dispos_id}.xml")
        grupos_evento = _grupos_por_evento(dispos_id)
        if not os.path.exists(ruta_xml):
            print(f"Error: No existe {ruta_xml}")
            return []

        tree = ET.parse(ruta_xml)
        root = tree.getroot()

        unidades = []
        slot_jugador = 1

        dif = str(dificultad).lower().replace("í", "i").replace("?", "i")
        if dif in ("extremo", "lunatic", "maddening"):
            mask = 4
        elif dif in ("dificil", "hard"):
            mask = 2
        else:
            mask = 1

        grupo_actual = ""
        for param in root.findall(".//Data/Param"):
            pid = param.get("Pid", "")
            force = param.get("Force", "")
            x_str = param.get("DisposX", "")
            y_str = param.get("DisposY", "")
            flag_str = param.get("Flag", "0")
            flag_val = int(flag_str) if flag_str.isdigit() else 0

            # Fila cabecera de grupo (sin coordenadas): abre un nuevo grupo
            if param.get("Group") and not x_str:
                grupo_actual = param.get("Group")
                continue

            # Ignorar casillas de terreno (PID_紋章氣) o filas vacías
            if not x_str or not y_str or "紋章氣" in pid:
                continue

            es_refuerzo = (grupo_actual.startswith("Enemy_Reinforcement") or grupo_actual in grupos_evento
                           or grupo_actual in _grupos_por_turno(dispos_id))
            if es_refuerzo and not incluir_refuerzos:
                continue

            # Filtrar por bitmask de dificultad si el flag está especificado
            if flag_val > 0 and (flag_val & mask) == 0:
                continue

            try:
                # El datamine de Nintendo usa coordenadas 1-indexed con Y=1 en la fila INFERIOR
                # (origen abajo-izquierda). Tiled/CSS tiene Y=0 en la fila SUPERIOR (origen arriba-izq).
                # Por eso X = DisposX - 1  (solo restar 1)
                # Pero Y = mapa_alto - DisposY  (invertir el eje Y)
                x = max(0, min(mapa_ancho - 1, int(x_str) - 1))
                y = max(0, min(mapa_alto - 1, mapa_alto - int(y_str)))
            except ValueError:
                continue

            # Fuerza: 0 = Jugador / Neutral, 1 = Enemigo, 2 = Aliado Verde (se une al pulsar comenzar)
            force_int = int(force) if force.isdigit() else 0
            es_aliado = (force_int == 0 or force_int == 2)
            es_verde = (force_int == 2)
            es_fijo = (force_int == 2 or pid == "PID_リュール")
            # Grupos "Ally_Add" (M011: Ivy, Kagetsu, Zelkov): llevan Force 2, pero en cuanto
            # aparecen se unen al ejército como unidades azules normales (observado en juego).
            if grupo_actual.startswith("Ally_Add"):
                es_verde = es_fijo = False
            # Los tres tipos de aliado verde (TIPO_ALIADO): el inmediato es azul desde el
            # Preset (conserva su casilla fija); el conversacional y el NPC siguen verdes.
            tipo_verde = tipo_de_aliado_verde(dispos_id, pid) if es_verde else ""
            habla_con = (list(UNION_POR_CONVERSACION.get((dispos_id or "").upper(), {}).get(pid, []))
                         if tipo_verde == "conversacion" else [])
            union_pendiente = tipo_verde == "conversacion"
            nunca_se_une = tipo_verde == "npc"
            if tipo_verde == "inmediato":
                es_verde = False

            # Buscar datos de Person.xml
            p_info = self.persons.get(pid, {})
            jid = param.get("Jid") or p_info.get("jid", "")

            # Obtener nivel base: si Dispos tiene un nivel explícito > 0 se usa, si no, se usa el de Person.xml
            dispos_l = int(param.get("LevelL", 0) or 0) if str(param.get("LevelL", "")).isdigit() else 0
            dispos_h = int(param.get("LevelH", 0) or 0) if str(param.get("LevelH", "")).isdigit() else 0
            dispos_n = int(param.get("LevelN", 0) or 0) if str(param.get("LevelN", "")).isdigit() else 0

            dif = dificultad.lower()
            if dif in ("extremo", "lunatic", "maddening"):
                lvl_base = dispos_l if dispos_l > 0 else (p_info.get("level") or 10)
                nivel_final = max(1, lvl_base)
                auto_grow_extra = p_info.get("auto_grow_offset_l", 0)  # level-ups extra para growths
                p_offset = p_info.get("offset_l", {})
            elif dif in ("dificil", "hard"):
                lvl_base = dispos_h if dispos_h > 0 else (p_info.get("level") or 10)
                nivel_final = max(1, lvl_base)
                auto_grow_extra = p_info.get("auto_grow_offset_h", 0)
                p_offset = p_info.get("offset_h", {})
            else:  # Normal
                lvl_base = dispos_n if dispos_n > 0 else (p_info.get("level") or 10)
                nivel_final = max(1, lvl_base)
                auto_grow_extra = p_info.get("auto_grow_offset_n", 0)
                p_offset = p_info.get("offset_n", {})

            # Para slots de jugador libres en preparación o Alear:
            if force_int == 0 and not pid:
                nivel_final = 10
                auto_grow_extra = 0
                p_offset = {}
            elif pid == "PID_リュール":
                nivel_final = 10
                auto_grow_extra = 0
                p_offset = {}

            # Resolver armas
            inventario = []
            for i in range(1, 7):
                iid = param.get(f"Item{i}.Iid", "")
                if iid:
                    nom_arma = self.resolver_nombre_item(iid)
                    drop = param.get(f"Item{i}.Drop", "0") == "1"
                    inventario.append({
                        "id": iid,
                        "nombre": nom_arma,
                        "arma": nom_arma,
                        "equipada": (len(inventario) == 0),
                        "es_drop": drop
                    })

            # Sin objetos en el dispos: inventario por defecto de Person.xml (Items)
            if not inventario and pid:
                for iid in (self.persons.get(pid, {}).get("items") or []):
                    nom_arma = self.resolver_nombre_item(iid)
                    inventario.append({
                        "id": iid, "nombre": nom_arma, "arma": nom_arma,
                        "equipada": (len(inventario) == 0), "es_drop": False,
                    })

            # Alear despliega canónicamente con Libération y Poción si el slot de dispos no lista armas
            if pid == "PID_リュール" and not inventario:
                inventario = [
                    {"id": "IID_リベラシオン", "nombre": "Libération", "arma": "Libération", "equipada": True, "es_drop": False},
                    {"id": "IID_傷薬", "nombre": "Poción", "arma": "Poción", "equipada": False, "es_drop": False}
                ]

            # Nombre de la unidad
            if force_int == 0 and not pid:
                slot_jugador += 1
                nombre_unidad = f"Aliado {slot_jugador}"
                jid = jid or "JID_ソードファイター"
            else:
                nombre_unidad = self.resolver_nombre_personaje(pid, jid, x, y)

            # Clase
            clase_info = self.catalogo.get("clases", {}).get(jid, {})
            clase_nombre = clase_info.get("nombre", jid.replace("JID_", ""))
            tipo_mov_c = str(clase_info.get("tipo_movimiento", "")).lower()
            c_nombre_c = str(clase_nombre).lower()
            c_jid_c = str(jid).lower()
            estilo_str_c = clase_info.get("estilo_combate", "")

            es_volador = (
                resolver_estilo_combate(estilo_str_c) == 'volador'
                or tipo_mov_c in ("volador", "flier", "flying")
                or any(w in c_nombre_c for w in ["flier", "pegas", "wyvern", "griffin", "grifo", "wing tamer", "sleipnir", "lindwurm", "melusine"])
                or any(w in c_jid_c for w in ["ペガサス", "ドラゴンナイト", "グリフォン", "スレイプニル", "リンドブルム", "メリュジーヌ", "flier", "wyvern", "pegas"])
            )

            # Emblema / Jefe
            hp_stock = int(param.get("HpStockCount", 0))
            ai_move = param.get("AI_MoveName", "")
            ai_rate = param.get("AI_BattleRate", "")

            arma_principal = inventario[0]["nombre"] if inventario else "Espada de Hierro"

            # En M007 el mapa entrega a Hortensia el emblema enemigo de Lucina
            # mediante un evento (no aparece en el atributo Gid de Dispos.xml).
            # El arma de ese emblema también forma parte de su inventario real.
            # Emblema asignado en el propio dispos (atributo Gid, p.ej. Diamant con
            # GID_ロイ en M008, Hyacinth con GID_M010_敵リン). Se resuelve contra el
            # catálogo de emblemas; los Emblemas Oscuros de jefe (GID_M0xx_敵…) están
            # compilados con sus propias stats/sincronías, así que los bonos salen del
            # catálogo y no de aquí.
            # `sin_emblemas_de_guion`: la misma unidad sin el anillo que le da el guion (para
            # quitárselo cuando pasa a otra, ver REFUERZOS_POR_EVENTO "retira_emblemas")
            por_evento = {} if sin_emblemas_de_guion else EMBLEMA_POR_EVENTO.get(dispos_id.upper(), {})
            gid = (param.get("Gid", "") or por_evento.get(f"{pid}@{x_str},{y_str}", "")
                   or por_evento.get(pid, "")
                   or ("" if sin_emblemas_de_guion else emblemas_del_guion(dispos_id).get(pid, "")))
            emblema_id = gid if gid in self.catalogo.get("emblemas", {}) else ""
            emblema_info = self.catalogo.get("emblemas", {}).get(emblema_id, {}) if emblema_id else {}
            emblema_nombre = emblema_info.get("nombre", "")
            if not emblema_nombre and pid == "PID_リュール":
                emblema_nombre = "Marth"
            emblema_bonos = None

            # Un Emblema Oscuro no se fusiona: sus armas forman parte del inventario real
            # del jefe durante toda la batalla (la Noble Rapier de Hortensia en el Cap. 7,
            # la Mani Katti y la Killer Bow de Lyn que lleva Hyacinth en el Cap. 10...).
            if emblema_info.get("es_oscuro"):
                ya_tiene = {str(item.get("id") or "") for item in inventario}
                nuevas = [iid for iid in emblema_info.get("engage_items", []) if iid not in ya_tiene]
                for offset, iid in enumerate(nuevas):
                    nombre_iid = self.resolver_nombre_item(iid)
                    if offset == 0:
                        for item in inventario:
                            item["equipada"] = False
                    inventario.insert(offset, {
                        "id": iid,
                        "nombre": nombre_iid,
                        "arma": nombre_iid,
                        "equipada": offset == 0,
                        "es_drop": False,
                    })
                if nuevas:
                    arma_principal = inventario[0]["nombre"]

            # Recolocaciones de guion (UnitMovePos en el .lua de apertura): la posición
            # real al empezar a jugar no es la del dispos. Coordenadas del datamine (1-indexed).
            recoloc = RECOLOCACIONES_APERTURA.get(dispos_id.upper(), {}).get(pid)
            if recoloc:
                x = max(0, min(mapa_ancho - 1, recoloc[0] - 1))
                y = max(0, min(mapa_alto - 1, mapa_alto - recoloc[1]))

            # Habilidad extra asignada en la propia fila del dispos (atributo Sid),
            # p.ej. SID_虚無の呪い (Void Curse: no da experiencia) en refuerzos de Extremo.
            habs_fila = [sd for sd in str(param.get("Sid", "") or "").split(";") if sd.strip()]
            # Pasivas por dificultad de Person.xml (NormalSids / HardSids / LunaticSids)
            # + pasivas observadas en el juego que el datamine no lista (PASIVAS_OBSERVADAS).
            dif_norm = _dificultad_norm(dificultad)
            sids_dif = str(p_info.get(f"sids_{dif_norm}", "") or "")
            for sd in sids_dif.split(";"):
                if sd.strip() and sd.strip() not in habs_fila:
                    habs_fila.append(sd.strip())
            for sd in PASIVAS_OBSERVADAS.get(dispos_id.upper(), {}).get(dif_norm, {}).get(pid, []):
                if sd not in habs_fila:
                    habs_fila.append(sd)
            ausentes = PASIVAS_AUSENTES.get(dispos_id.upper(), {}).get(dif_norm, {}).get(pid, [])
            habs_fila = [sd for sd in habs_fila if sd not in ausentes]

            unidades.append({
                "nombre": nombre_unidad,
                "habilidades": habs_fila,
                "pid": pid,
                "es_aliado": es_aliado,
                "es_verde": es_verde,
                "es_fijo": es_fijo,
                "union_pendiente": union_pendiente,   # verde que aún no se ha unido (hablar para reclutar)
                "nunca_se_une": nunca_se_une,         # verde de la CPU que nunca se une (aldeanos)
                "habla_con": habla_con,               # pids que pueden hablar con él
                # casilla a la que el guion lo lleva al empezar la batalla, antes de unirlo
                "pos_tras_guion": ([max(0, min(mapa_ancho - 1, movimientos_del_guion(dispos_id)[pid][0] - 1)),
                                    max(0, min(mapa_alto - 1, mapa_alto - movimientos_del_guion(dispos_id)[pid][1]))]
                                   if es_aliado and pid in movimientos_del_guion(dispos_id) else []),
                "x": x,
                "y": y,
                "clase_id": jid,
                "clase_nombre": clase_nombre,
                "es_volador": es_volador,
                "nivel": nivel_final,
                "arma_nombre": arma_principal,
                "inventario": inventario,
                "hp_stock": hp_stock,
                "ia_move": ai_move,
                "ia_rate": ai_rate,
                "emblema_id": emblema_id,
                "emblema_nombre": emblema_nombre,
                "emblema_bonos": emblema_bonos,
                # Metadatos de dificultad para el resolver de stats
                "dificultad": dificultad,
                "auto_grow_extra": auto_grow_extra,  # level-ups bonus para cálculo de crecimientos
                "p_offset": p_offset,                # offsets de stats por dificultad desde Person.xml
                # Bit 16 del Flag del dispos = jefe del mapa (Hortensia M007, Ivy M008/M009, Hyacinth
                # y Morion M010…); las piedras resurrectoras son solo una consecuencia en Extremo
                "es_jefe": (not es_aliado and bool(flag_val & 16)) or (hp_stock > 0 and not es_aliado) or "(Boss)" in nombre_unidad,
                "grupo": grupo_actual,
                "es_refuerzo": es_refuerzo,
            })

        # El tablero identifica las fichas por nombre: dos con el mismo (los dos Corrupted
        # Wyrm de M011, PID_M011_異形竜 sin 兵) se pisarían. Se distinguen por su casilla,
        # como las tropas genéricas.
        repetidos = {n for n in (u["nombre"] for u in unidades)
                     if sum(1 for v in unidades if v["nombre"] == n) > 1 and not re.search(r"\(\d+,\d+\)$", n)}
        for u in unidades:
            if u["nombre"] in repetidos:
                u["nombre"] = f"{u['nombre']} ({u['x']},{u['y']})"

        return unidades

    def calendario_refuerzos(self, dispos_id: str, dificultad: str = "Extremo", mapa_ancho: int = 24, mapa_alto: int = 17) -> dict:
        """{turno: [unidad, ...]} de refuerzos del capítulo para esa dificultad (ya filtrados por Flag)."""
        grupos = self.cargar_refuerzos(dispos_id, dificultad, mapa_ancho, mapa_alto)
        calendario = {}
        for turno, nombres in CALENDARIO_REFUERZOS.get(dispos_id.upper(), {}).items():
            unidades = [u for g in nombres for u in grupos.get(g, [])]
            if unidades:
                calendario[int(turno)] = unidades
        return calendario

    def refuerzos_por_evento(self, dispos_id: str, dificultad: str = "Extremo", mapa_ancho: int = 24, mapa_alto: int = 17) -> list:
        """[{grupo, pid, casilla: (x, y) en coordenadas del mapa, descripcion, unidades}] de los
        refuerzos condicionales del capítulo (REFUERZOS_POR_EVENTO), ya filtrados por dificultad."""
        grupos = self.cargar_refuerzos(dispos_id, dificultad, mapa_ancho, mapa_alto)
        salida = []
        def _a_mapa(casilla_datamine):
            dx, dy = casilla_datamine
            return (max(0, min(mapa_ancho - 1, int(dx) - 1)), max(0, min(mapa_alto - 1, mapa_alto - int(dy))))

        for ev in REFUERZOS_POR_EVENTO.get((dispos_id or "").upper(), []):
            unidades = grupos.get(ev["grupo"], [])
            if not unidades:
                continue
            disparos = list(ev.get("disparos") or [])
            if not disparos:   # forma antigua: pid + casilla (o `disparo` suelto)
                disparos = [{"tipo": ev.get("disparo", "casilla"), "pid": ev.get("pid", ""),
                             "casilla_datamine": ev.get("casilla_datamine")}]
            normalizados = []
            for d in disparos:
                d = dict(d)
                if d.get("casilla_datamine"):
                    d["casilla"] = _a_mapa(d.pop("casilla_datamine"))
                d.pop("casilla_datamine", None)
                if d.get("fila_datamine") is not None:
                    d["fila_min"] = mapa_alto - int(d.pop("fila_datamine"))
                normalizados.append(d)
            primero = normalizados[0]
            extra = {}
            if ev.get("junto_al_disparo"):
                extra["junto_al_disparo"] = True
            if ev.get("retira_emblemas"):
                extra["sin_emblema"] = self._portadores_sin_emblema(
                    dispos_id, dificultad, mapa_ancho, mapa_alto,
                    {u.get("emblema_id") for u in unidades if u.get("emblema_id")})
            salida.append({
                "grupo": ev["grupo"], "descripcion": ev.get("descripcion", ""),
                "disparos": normalizados, "unidades": unidades, **extra,
                # Compatibilidad con los guardados y la UI anteriores (primer disparo)
                "pid": ev.get("pid", primero.get("pid", "")),
                "disparo": primero.get("tipo", "casilla"),
                "casilla": primero.get("casilla"),
            })
        return salida

    def _portadores_sin_emblema(self, dispos_id, dificultad, mapa_ancho, mapa_alto, gids) -> dict:
        """{gid: unidad del despliegue inicial que lleva ese anillo, cargada SIN él}."""
        if not gids:
            return {}
        con = self.cargar_capitulo(dispos_id, dificultad, mapa_ancho, mapa_alto)
        sin = self.cargar_capitulo(dispos_id, dificultad, mapa_ancho, mapa_alto, sin_emblemas_de_guion=True)
        return {u["emblema_id"]: s for u, s in zip(con, sin)
                if u.get("emblema_id") in gids and u["nombre"] == s["nombre"]}

    def cargar_refuerzos(self, dispos_id: str, dificultad: str = "Extremo", mapa_ancho: int = 24, mapa_alto: int = 17) -> dict:
        """Refuerzos del capítulo agrupados por nombre de grupo del dispos: {grupo: [unidad, ...]}."""
        grupos = {}
        for u in self.cargar_capitulo(dispos_id, dificultad, mapa_ancho, mapa_alto, incluir_refuerzos=True):
            if u.get("es_refuerzo"):
                grupos.setdefault(u["grupo"], []).append(u)
        return grupos


if __name__ == "__main__":
    cargador = CargadorDisposEngage()
    cap7 = cargador.cargar_capitulo("M007", "Extremo")
    print(f"[OK] Cargadas {len(cap7)} unidades del Capítulo 7:")
    for u in cap7:
        bando = "Aliado" if u["es_aliado"] else "Enemigo"
        inv = ", ".join([item["nombre"] for item in u["inventario"]])
        print(f" - {bando:10} | ({u['x']:>2},{u['y']:>2}) | {u['nombre']:28} | Nv {u['nivel']:>2} | {u['clase_nombre']:18} | Armas: {inv}")
