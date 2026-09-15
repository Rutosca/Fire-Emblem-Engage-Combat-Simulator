"""
cargador_dispos.py — Lector y Conversor de Despliegues Oficiales de Fire Emblem Engage
Extrae las disposiciones exactas de enemigos, aliados, niveles y armas de la carpeta dispos/
del datamine de FE Engage (FE17-DOC-main).
"""

import os
import sys
import json
import xml.etree.ElementTree as ET
from typing import List, Dict, Tuple, Optional

# Rutas base
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATAMINE_DIR = os.path.join(BASE_DIR, "FE17-DOC-main", "FE17-DOC-main", "fe_assets_gamedata")
DISPOS_DIR = os.path.join(DATAMINE_DIR, "dispos")

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

        # Si es un soldado genérico, usar la clase en inglés + coordenadas para ser identificable
        clase_info = self.catalogo.get("clases", {}).get(jid)
        clase_nom = clase_info.get("nombre", jid.replace("JID_", "")) if clase_info else jid.replace("JID_", "")
        return f"{clase_nom} ({x},{y})"

    def cargar_capitulo(self, dispos_id: str = "M007", dificultad: str = "Extremo", mapa_ancho: int = 24, mapa_alto: int = 17) -> List[dict]:
        """
        Lee el XML de dispos/{dispos_id}.xml y retorna la lista de diccionarios de unidades
        listas para ser enviadas a la UI o cargadas en EstadoTablero.
        """
        ruta_xml = os.path.join(DISPOS_DIR, f"{dispos_id}.xml")
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

        for param in root.findall(".//Data/Param"):
            pid = param.get("Pid", "")
            force = param.get("Force", "")
            x_str = param.get("DisposX", "")
            y_str = param.get("DisposY", "")
            flag_str = param.get("Flag", "0")
            flag_val = int(flag_str) if flag_str.isdigit() else 0

            # Ignorar casillas de terreno (PID_紋章氣) o filas vacías
            if not x_str or not y_str or "紋章氣" in pid:
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
            estilo_str_c = str(clase_info.get("estilo_combate", "")).lower()

            es_volador = (
                estilo_str_c in ("flier", "volador", "飛行スタイル", "飛行", "flying")
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
            if pid.endswith("オルテンシア") and dispos_id.upper() == "M007":
                emblema_nombre = "Lucina"
                emblema_bonos = {"hp": 10, "str": 5, "dex": 4, "spd": 3, "def": 3}
                rapier_id = "IID_ルキナ_ノーブルレイピア_M007"
                if not any(item.get("id") == rapier_id or item.get("nombre") == "Noble Rapier (Evento)" for item in inventario):
                    for item in inventario:
                        item["equipada"] = False
                    inventario.insert(0, {
                        "id": rapier_id,
                        "nombre": self.resolver_nombre_item(rapier_id),
                        "arma": self.resolver_nombre_item(rapier_id),
                        "equipada": True,
                        "es_drop": False,
                    })
                    arma_principal = inventario[0]["nombre"]
            else:
                emblema_nombre = "Marth" if pid == "PID_リュール" else ""
                emblema_bonos = {}

            unidades.append({
                "nombre": nombre_unidad,
                "pid": pid,
                "es_aliado": es_aliado,
                "es_verde": es_verde,
                "es_fijo": es_fijo,
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
                "emblema_nombre": emblema_nombre,
                "emblema_bonos": emblema_bonos,
                # Metadatos de dificultad para el resolver de stats
                "dificultad": dificultad,
                "auto_grow_extra": auto_grow_extra,  # level-ups bonus para cálculo de crecimientos
                "p_offset": p_offset,                # offsets de stats por dificultad desde Person.xml
                "es_jefe": (hp_stock > 0 and not es_aliado) or "(Boss)" in nombre_unidad,
            })

        return unidades


if __name__ == "__main__":
    cargador = CargadorDisposEngage()
    cap7 = cargador.cargar_capitulo("M007", "Extremo")
    print(f"[OK] Cargadas {len(cap7)} unidades del Capítulo 7:")
    for u in cap7:
        bando = "Aliado" if u["es_aliado"] else "Enemigo"
        inv = ", ".join([item["nombre"] for item in u["inventario"]])
        print(f" - {bando:10} | ({u['x']:>2},{u['y']:>2}) | {u['nombre']:28} | Nv {u['nivel']:>2} | {u['clase_nombre']:18} | Armas: {inv}")
