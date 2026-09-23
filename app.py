"""
app.py — FE Engage Tactical Assistant
API REST Flask que conecta la UI del Gemelo con el motor de cálculo.
"""

from flask import Flask, jsonify, request, render_template, abort, has_request_context, session
from werkzeug.local import LocalProxy
from motor_calculo import CalculadoraEngage, Unidad, Arma, Terreno
from estado_tablero import EstadoTablero, FichaUnidad
import pasivas
import pasivas_temporales
from lector_de_mapas import MapaTactico
from motor_de_movimiento_y_amenaza import AnalizadorAmenaza, UnidadMock, ArmaMock, casillas_advance

import os
import re
import math
import json
import unicodedata
import threading
import time
from collections import deque
import cargador_dispos
from cargador_dispos import CargadorDisposEngage

from ataques_area import resolver_ataque_area, tipo_ataque_area
from catalogo_loader import (
    normalizar_texto, round_half_up, cargar_catalogo,
    _catalogo, GRABADOS_EMBLEMA, REFINES_GENERICOS,
    parsear_arma_string, _buscar_en_catalogo, _arma_desde_item,
    resolver_unidad_con_catalogo, puede_usar_arma_de_mapa, arma_de_mapa_desde, tipo_arma_de_objeto
)
from motor_analisis import (
    BACKUP_CLASSES, es_unidad_backup, obtener_aliados_backup,
    encontrar_pos_ataque_optima, analizar_situacion_tactica,
    obtener_protector_chain_guard, _armas_aliado
)

app = Flask(__name__)

# Cada navegador recibe un identificador firmado en su cookie de sesión. El valor
# por defecto es deliberadamente efímero para el uso local: al reiniciar el proceso
# la UI ya restaura la partida que guarda en el navegador. En un despliegue estable,
# ENGAGE_SECRET_KEY debe configurarse para conservar las cookies entre reinicios.
import uuid as _uuid
app.config.update(
    SECRET_KEY=os.environ.get("ENGAGE_SECRET_KEY") or _uuid.uuid4().hex,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

# Identificador del arranque del servidor. El tablero vive en memoria: si el proceso
# se reinicia (p.ej. el autoreload de Flask al editar código) mientras el navegador
# sigue abierto, el cliente lo detecta por esta cabecera y restaura su partida local
# en vez de seguir enviando acciones a un tablero recién inicializado.
_BOOT_ID = _uuid.uuid4().hex


@app.after_request
def _marcar_arranque(resp):
    resp.headers["X-Engage-Boot"] = _BOOT_ID
    return resp

# =============================================================================
# Estado de la partida por navegador
# =============================================================================

# Mapas por capítulo: mapas/CAP_<n>_Tiled.json. El capítulo activo se cambia en
# caliente con /api/mapa/seleccionar; el tablero se vacía (las unidades se
# despliegan aparte con los presets / dispos de cada capítulo).
_DIR_MAPAS = os.path.join(os.path.dirname(__file__), "mapas")
# Valor de compatibilidad para scripts de exploración antiguos. Las rutas usan el
# capítulo de la partida de la sesión, no este módulo global.
_capitulo_actual = 7


def _ruta_mapa_capitulo(n: int) -> str:
    return os.path.join(_DIR_MAPAS, f"CAP_{int(n)}_Tiled.json")


def capitulos_disponibles() -> list:
    """Números de capítulo con mapa Tiled en la carpeta mapas/, ordenados."""
    caps = []
    for fn in os.listdir(_DIR_MAPAS) if os.path.isdir(_DIR_MAPAS) else []:
        m = re.fullmatch(r"CAP_(\d+)_Tiled\.json", fn)
        if m:
            caps.append(int(m.group(1)))
    return sorted(caps)


def _info_capitulo(n: int) -> dict:
    """Nombre del capítulo desde el datamine (mapas/M0NN.json) si existe."""
    ruta_dm = os.path.join(_DIR_MAPAS, f"M{int(n):03d}.json")
    nombre = f"Capítulo {n}"
    try:
        with open(ruta_dm, "r", encoding="utf-8") as f:
            nombre = json.load(f).get("nombre_en", nombre)
    except Exception:
        pass
    disponibles = capitulos_disponibles()
    return {
        "capitulo": n,
        "nombre": nombre,
        "tiene_mapa": n in disponibles,
        "anterior": max((c for c in disponibles if c < n), default=None),
        "siguiente": min((c for c in disponibles if c > n), default=None),
        "disponibles": disponibles,
    }


class _PartidaEnMemoria:
    """Estado volátil de una partida perteneciente a una sesión de navegador."""

    def __init__(self, capitulo: int = 7):
        self.capitulo = capitulo
        self.mapa = MapaTactico(_ruta_mapa_capitulo(capitulo))
        self.tablero = EstadoTablero(mapa=self.mapa)
        self.ultimo_acceso = time.monotonic()


_PARTIDA_POR_DEFECTO = _PartidaEnMemoria()
_PARTIDAS_POR_SESION = {}
_PARTIDAS_LOCK = threading.RLock()
_MAX_PARTIDAS_EN_MEMORIA = 32


def _partida_actual() -> _PartidaEnMemoria:
    """Devuelve la partida aislada de la petición actual.

    Los accesos fuera de una petición (scripts y la suite histórica) mantienen el
    tablero por defecto. La suite activa ``TESTING`` para conservar su contrato
    directo con ``from app import tablero``.
    """
    if not has_request_context() or app.config.get("TESTING"):
        return _PARTIDA_POR_DEFECTO

    identificador = session.get("engage_session_id")
    if not identificador:
        identificador = _uuid.uuid4().hex
        session["engage_session_id"] = identificador

    with _PARTIDAS_LOCK:
        partida = _PARTIDAS_POR_SESION.get(identificador)
        if partida is None:
            partida = _PartidaEnMemoria()
            _PARTIDAS_POR_SESION[identificador] = partida
        partida.ultimo_acceso = time.monotonic()

        # Límite defensivo para un servidor local que reciba muchas sesiones. Nunca
        # elimina la partida que está realizando la petición actual.
        while len(_PARTIDAS_POR_SESION) > _MAX_PARTIDAS_EN_MEMORIA:
            candidata = min(
                (p for sid, p in _PARTIDAS_POR_SESION.items() if sid != identificador),
                key=lambda p: p.ultimo_acceso,
                default=None,
            )
            if candidata is None:
                break
            sid_caducada = next(sid for sid, p in _PARTIDAS_POR_SESION.items() if p is candidata)
            del _PARTIDAS_POR_SESION[sid_caducada]
        return partida


def _capitulo_sesion() -> int:
    return _partida_actual().capitulo


# Los proxies preservan el contrato de los módulos del motor: dentro de una ruta
# ``tablero`` y ``_mapa`` siempre se resuelven a la partida del navegador actual.
tablero = LocalProxy(lambda: _partida_actual().tablero)
_mapa = LocalProxy(lambda: _partida_actual().mapa)




@app.route("/api/catalogo/recargar", methods=["POST", "GET"])
def recargar_catalogo_endpoint():
    cargar_catalogo()
    return jsonify({"ok": True, "armas": len(_catalogo.get('armas', {})), "emblemas": len(_catalogo.get('emblemas', {}))})


@app.route("/api/catalogo/emblemas", methods=["GET"])
def obtener_catalogo_emblemas():
    """
    Devuelve los Emblemas equipables (14 base + DLC) con sus 20 niveles de vínculo.
    Los Emblemas Oscuros de jefe (es_oscuro) se excluyen: los asigna el preset del capítulo.
    """
    return jsonify({"ok": True, "emblemas": {k: v for k, v in _catalogo.get("emblemas", {}).items() if not v.get("es_oscuro")}})


@app.route("/api/mapa/capitulos", methods=["GET"])
def listar_capitulos():
    """Capítulo activo y lista de capítulos con mapa disponible (para las flechas de navegación)."""
    return jsonify({"ok": True, **_info_capitulo(_capitulo_sesion())})


@app.route("/api/mapa/seleccionar", methods=["POST"])
def seleccionar_mapa():
    """
    Cambia el capítulo activo (mapas/CAP_<n>_Tiled.json). Vacía el tablero,
    reinicia turno/fase y los objetos de mapa; las unidades se despliegan aparte.
    Body: {"capitulo": 8}  o  {"direccion": 1 | -1} (siguiente/anterior disponible).
    """
    data = request.get_json(force=True) or {}
    partida = _partida_actual()
    if "capitulo" in data:
        objetivo = int(data["capitulo"])
    else:
        info = _info_capitulo(partida.capitulo)
        objetivo = info["siguiente"] if int(data.get("direccion", 1)) > 0 else info["anterior"]
    if objetivo is None or objetivo not in capitulos_disponibles():
        return jsonify({"error": f"No hay mapa para el capítulo {objetivo}", **_info_capitulo(partida.capitulo)}), 400
    try:
        nuevo_mapa = MapaTactico(_ruta_mapa_capitulo(objetivo))
    except Exception as e:
        return jsonify({"error": f"No se pudo cargar el mapa del capítulo {objetivo}: {e}"}), 500

    partida.capitulo = objetivo
    partida.mapa = nuevo_mapa
    tablero.mapa = nuevo_mapa
    tablero.limpiar()
    tablero.historial.clear()
    tablero.turno_actual = 1
    tablero.fase = "jugador"
    tablero.inicializar_objetos_mapa()
    tablero.programar_refuerzos({})
    tablero.programar_refuerzos_por_evento([])
    snap = tablero.snapshot()
    snap["mapa"] = _mapa_como_dict()
    return jsonify({"ok": True, **_info_capitulo(objetivo), "estado": snap})


def _mapa_como_dict() -> dict:
    """Bloque `mapa` de /api/estado: dimensiones, objetivos, propiedades, objetos y capítulo."""
    if not _mapa:
        return {"ancho": 24, "alto": 17}
    return {
        "ancho": _mapa.ancho, "alto": _mapa.alto,
        "casillas_objetivo": [{"x": x, "y": y, "objetivo": o} for x, y, o in _mapa.casillas_objetivo()] if hasattr(_mapa, 'casillas_objetivo') else [],
        "propiedades": getattr(_mapa, 'propiedades_mapa', {}) or {},
        "objetos": tablero.objetos_como_lista(),
        **{k: v for k, v in _info_capitulo(_capitulo_sesion()).items() if k != "tiene_mapa"},
    }


@app.route("/api/mapa/recargar", methods=["POST", "GET"])
def recargar_mapa_endpoint():
    """Recarga el JSON del mapa activo en caliente, sin reiniciar el servidor.
    Util durante el desarrollo: edita en Tiled, exporta, llama a este endpoint."""
    try:
        partida = _partida_actual()
        partida.mapa = MapaTactico(_ruta_mapa_capitulo(partida.capitulo))
        tablero.mapa = partida.mapa
        tablero.inicializar_objetos_mapa()
        tipos = {}
        for x in range(_mapa.ancho):
            for y in range(_mapa.alto):
                t = _mapa.grid[x][y]
                tipos[t.nombre] = tipos.get(t.nombre, 0) + 1
        print(f"[Mapa recargado] {_mapa.ancho}x{_mapa.alto} | tipos: {tipos}")
        return jsonify({"ok": True, "ancho": _mapa.ancho, "alto": _mapa.alto, "tipos": tipos})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# =============================================================================
# API — Estado del tablero
# =============================================================================

@app.route("/")
def index():
    return render_template("index.html")

def _resincronizar_eventos_del_capitulo():
    """
    Los disparadores de los refuerzos por evento se programan al cargar el capítulo y se
    quedan guardados en la partida. Si se corrige una condición (p.ej. los arqueros del
    Cap. 10 pasaron de "turno 6" a "cuando Hortensia actúa"), una partida ya empezada se
    quedaría con la antigua. Aquí se ponen al día sin tocar el tablero ni lo ya disparado.
    """
    if not tablero.refuerzos_por_evento:
        return []
    try:
        cap = _dispos_id_activo()
        eventos = _cargador_dispos.refuerzos_por_evento(
            cap, tablero.dificultad, mapa_ancho=_mapa.ancho, mapa_alto=_mapa.alto)
        return tablero.resincronizar_refuerzos_por_evento(eventos)
    except Exception as e:
        print(f"[refuerzos] no se pudieron resincronizar los eventos: {e}")
        return []


@app.route("/api/estado", methods=["GET"])
def obtener_estado():
    """Devuelve el estado completo del tablero."""
    _resincronizar_eventos_del_capitulo()
    snap = tablero.snapshot()
    snap["mapa"] = _mapa_como_dict()
    return jsonify(snap)


@app.route("/api/mapa/objetos", methods=["GET"])
def listar_objetos_mapa():
    """Objetos de la capa de objetos (ballestas, destructibles, pozos de Emblema) con su estado."""
    return jsonify({"ok": True, "objetos": tablero.objetos_como_lista()})


@app.route("/api/mapa/objeto/consumir", methods=["POST"])
def consumir_objeto_mapa():
    """
    Gasta/destruye un objeto de mapa: un uso de ballesta, destruir una caja
    (libera todas sus casillas), agotar un pozo de Emblema.
    """
    data = request.get_json(force=True) or {}
    id_obj = str(data.get("id", ""))
    if not id_obj:
        return jsonify({"error": "Falta campo id"}), 400
    tablero.guardar_snapshot()
    ok = tablero.consumir_objeto_mapa(id_obj)
    if not ok:
        tablero.historial.pop()
        return jsonify({"error": f"Objeto '{id_obj}' no existe o ya estaba inactivo"}), 400
    return jsonify({"ok": True, "objetos": tablero.objetos_como_lista()})


@app.route("/api/mapa/objeto/abrir_cofre", methods=["POST"])
def abrir_cofre_mapa():
    """
    Abre un cofre gastando la acción de una unidad adyacente.
    Body: {"id": "<id del cofre>", "unidad": "Yunaka"}  (`unidad` opcional: sin ella
    solo se marca el cofre como abierto, sin gastar acción).
    El cofre sigue bloqueando su casilla; el contenido lo anota el jugador en el
    inventario de la unidad (la herramienta no lo conoce ni lo recomienda).
    """
    data = request.get_json(force=True) or {}
    id_obj = str(data.get("id", ""))
    if not id_obj:
        return jsonify({"error": "Falta campo id"}), 400
    tablero.guardar_snapshot()
    est = tablero.abrir_cofre(id_obj, str(data.get("unidad", "") or ""))
    if est is None:
        tablero.historial.pop()
        return jsonify({"error": getattr(tablero, "ultimo_error_cofre", "") or f"No se pudo abrir '{id_obj}'"}), 400
    return jsonify({
        "ok": True,
        "objeto": est,
        "objetos": tablero.objetos_como_lista(),
        "fichas": [f.como_dict() for f in tablero.fichas.values()],
    })


@app.route("/api/mapa/objeto/dañar", methods=["POST"])
@app.route("/api/mapa/objeto/danar", methods=["POST"])
def dañar_objeto_mapa():
    """
    Resta `daño` HP a un destructible con vida, o fija su vida con `vida` (edición manual);
    al llegar a 0 se destruye entero.
    """
    data = request.get_json(force=True) or {}
    id_obj = str(data.get("id", ""))
    if not id_obj:
        return jsonify({"error": "Falta campo id"}), 400
    vida = data.get("vida")
    tablero.guardar_snapshot()
    est = tablero.dañar_objeto_mapa(
        id_obj,
        int(data.get("daño", data.get("dano", 0)) or 0),
        vida=int(vida) if vida is not None else None,
    )
    if est is None:
        tablero.historial.pop()
        return jsonify({"error": f"Objeto '{id_obj}' no existe o ya estaba destruido"}), 400
    # Al derribar la puerta (u otro objeto del guion) pueden llegar refuerzos
    refuerzos = []
    if not est.get("activo"):
        entrada = next((o for o in tablero.objetos_como_lista() if str(o.get("id")) == id_obj), None)
        refuerzos = tablero.disparar_refuerzos_por_objeto(entrada or est)
    return jsonify({
        "ok": True, "objeto": est,
        "objetos": tablero.objetos_como_lista(),
        "refuerzos_desplegados": refuerzos,
        "fichas": [f.como_dict() for f in tablero.fichas.values()] if refuerzos else None,
    })


@app.route("/api/mapa/objeto/usos", methods=["POST"])
def fijar_usos_objeto_mapa():
    """
    Fija los usos restantes de un arma de mapa (los enemigos también la usan).
    Body: {"id": "<id>", "usos": 2}. Con 0 queda agotada; con >0 vuelve a poder usarse.
    """
    data = request.get_json(force=True) or {}
    id_obj = str(data.get("id", ""))
    if not id_obj or data.get("usos") is None:
        return jsonify({"error": "Faltan campos: id, usos"}), 400
    tablero.guardar_snapshot()
    est = tablero.fijar_usos_objeto(id_obj, int(data["usos"]))
    if est is None:
        tablero.historial.pop()
        return jsonify({"error": f"'{id_obj}' no es un arma de mapa con usos"}), 400
    return jsonify({"ok": True, "objeto": est, "objetos": tablero.objetos_como_lista()})


@app.route("/api/mapa/objeto/restaurar", methods=["POST"])
def restaurar_objeto_mapa():
    """Reactiva un objeto de mapa (corrección manual)."""
    data = request.get_json(force=True) or {}
    id_obj = str(data.get("id", ""))
    if not id_obj:
        return jsonify({"error": "Falta campo id"}), 400
    tablero.guardar_snapshot()
    if not tablero.restaurar_objeto_mapa(id_obj):
        tablero.historial.pop()
        return jsonify({"error": f"Objeto '{id_obj}' no existe"}), 400
    return jsonify({"ok": True, "objetos": tablero.objetos_como_lista()})

@app.route("/api/terreno/<int:x>/<int:y>", methods=["GET"])
def obtener_info_terreno(x, y):
    """Devuelve información táctica de una casilla."""
    mapa_actual = tablero.mapa if (tablero and tablero.mapa) else _mapa
    t = mapa_actual.obtener_terreno(x, y) if mapa_actual else None
    if t is None:
        return jsonify({"error": "Casilla fuera del mapa"}), 404
    return jsonify({
        "x": x, "y": y,
        "nombre": t.nombre,
        "caminable": t.caminable,
        "volable": t.volable,
        "avo": t.avo,
        "dfn": t.dfn,
        "coste_mov": t.coste_mov,
        "curacion_turno": getattr(t, 'curacion_turno', 0),
        "es_antirruptura": getattr(t, 'es_antirruptura', False),
        "es_recarga_emblema": getattr(t, 'es_recarga_emblema', False),
        "objetivo": getattr(t, 'objetivo', ''),
    })

@app.route("/api/catalogo/buscar", methods=["GET"])
def buscar_catalogo():
    """
    Buscador rápido autocompletable en el catálogo maestro de Engage.
    Query params:
        q: término de búsqueda (ej: 'Iron Sword', 'Marth', 'Canto', 'Poción')
        tipo: 'armas' | 'clases' | 'habilidades' | 'emblemas' | 'personajes' | 'todos'
    """
    q = request.args.get("q", "").strip()
    tipo = request.args.get("tipo", "todos").strip().lower()

    if not q:
        return jsonify({"resultados": []})

    q_norm = normalizar_texto(q)
    resultados = []
    categorias = [tipo] if tipo in _catalogo else ["armas", "clases", "habilidades", "emblemas", "personajes"]
    vistos = set()

    for cat in categorias:
        if cat not in _catalogo:
            continue
        for key, item in _catalogo[cat].items():
            nombre = item.get("nombre", "")
            nombre_norm = normalizar_texto(nombre)
            key_norm = normalizar_texto(key)
            ascii_norm = normalizar_texto(item.get("ascii_name", ""))

            # Filtrar duplicados de scripts de eventos / enemigos para emblemas
            if cat == "emblemas" and (key.startswith("GID_M0") or "相手" in key or "敵" in key or nombre == "???"):
                continue

            if q_norm in nombre_norm or q_norm in key_norm or (ascii_norm and q_norm in ascii_norm):
                display_nombre = nombre

                # Deduplicar en la lista devuelta
                dedup_key = (cat, display_nombre)
                if dedup_key in vistos:
                    continue
                vistos.add(dedup_key)

                # Si es un objeto consumible con usos múltiples (ej: Poción de 3 usos), ofrecer desglose
                usos_max = item.get("usos_max")
                if cat == "armas" and usos_max and usos_max > 1:
                    for u in range(usos_max, 0, -1):
                        resultados.append({
                            "categoria": cat,
                            "id": key,
                            "nombre": f"{display_nombre} ({u})",
                            "nombre_base": display_nombre,
                            "usos": u,
                            "usos_max": usos_max,
                            "datos": item
                        })
                else:
                    resultados.append({
                        "categoria": cat,
                        "id": key,
                        "nombre": display_nombre,
                        "datos": item
                    })

                    # Sugerir variantes de forja (+1..+5) y grabado si la búsqueda encaja
                    if cat == "armas" and item.get("tipo") in {'Espada', 'Hacha', 'Lanza', 'Artes', 'Arco', 'Tomo', 'Daga'}:
                        if "+" in q or any(k in q_norm for k in GRABADOS_EMBLEMA):
                            parsed_exact = parsear_arma_string(q)
                            if parsed_exact and parsed_exact["nombre_base"] == display_nombre:
                                resultados.insert(0, {
                                    "categoria": cat,
                                    "id": key,
                                    "nombre": parsed_exact["nombre"],
                                    "nombre_base": display_nombre,
                                    "datos": parsed_exact
                                })

                if len(resultados) >= 40:
                    break

    # Si la búsqueda es directamente un arma con + o grabado (ej: 'Libération+2 (Marth)')
    if (tipo == "todos" or tipo == "armas") and not any(r["nombre"] == q for r in resultados):
        parsed_q = parsear_arma_string(q)
        if parsed_q:
            resultados.insert(0, {
                "categoria": "armas",
                "id": parsed_q["id"],
                "nombre": parsed_q["nombre"],
                "nombre_base": parsed_q["nombre_base"],
                "datos": parsed_q
            })

    return jsonify({"query": q, "total": len(resultados), "resultados": resultados})


# =============================================================================
# API — Gestión de fichas
# =============================================================================

_ruta_squad_file_json = os.path.join(os.path.dirname(__file__), "json", "escuadron_guardado.json")
_ruta_squad_file = _ruta_squad_file_json if os.path.exists(_ruta_squad_file_json) else os.path.join(os.path.dirname(__file__), "escuadron_guardado.json")

@app.route("/api/unidad/guardar", methods=["POST"])
@app.route("/api/registrar", methods=["POST"])
def guardar_unidad():
    """
    Crea o actualiza una unidad resolviendo sus stats con catalogo_engage.json.
    """
    data = request.get_json(force=True)
    if not data or "nombre" not in data:
        return jsonify({"error": "Falta campo 'nombre'"}), 400

    # Dificultad del capítulo desplegado: decide las pasivas extra de los enemigos
    # (HardSids / LunaticSids del datamine) al resolver una ficha creada a mano.
    data.setdefault("dificultad", tablero.dificultad)
    # Nombre original (edición con renombrado) para detectar bajadas de HP respecto a la ficha previa
    prev = tablero.obtener_ficha(data.get("nombre_original") or data.get("nombre"))
    hp_previo = prev.hp_actual if prev else None
    pid_edit = data.get("pid") or (getattr(prev, "pid", "") if prev else "")
    if pid_edit and pid_edit in cargador_dispos.pids_jefe(f"M{_capitulo_sesion():03d}") and not data.get("es_aliado", False):
        data["es_jefe"] = True

    ficha = resolver_unidad_con_catalogo(data)
    tablero.registrar_unidad(ficha)

    # Editar la vida a la baja de un aliado en fase enemiga == "ha sido atacado" (ver ajustar_hp)
    estados_otorgados = []
    if hp_previo is not None and ficha.hp_actual < hp_previo:
        estados_otorgados = pasivas_temporales.al_danar_aliado(tablero, ficha)
    # Marcar "ha actuado" desde el modal sin combate ni objeto == "Esperar" (Self-Improver, Meditación)
    if ficha.ha_actuado and not ficha.accion_turno and not (prev and prev.ha_actuado):
        estados_otorgados += pasivas_temporales.al_esperar(tablero, ficha)
    return jsonify({
        "ok": True,
        "ficha": ficha.como_dict(),
        "estados_otorgados": [{"unidad": n, **e} for n, e in estados_otorgados],
    })

# El escuadrón y el roster de aliados viven en el localStorage del navegador (ver gemelo.js).
# El servidor solo conserva el fichero legado como fuente de migración inicial (solo lectura).
@app.route("/api/escuadron/cargar", methods=["GET"])
def cargar_escuadron():
    """Devuelve la plantilla legada de aliados guardada en disco (migración al roster del navegador)."""
    if os.path.exists(_ruta_squad_file):
        try:
            with open(_ruta_squad_file, "r", encoding="utf-8") as f:
                aliados = json.load(f)
                return jsonify({"ok": True, "escuadron": aliados})
        except Exception:
            pass
    return jsonify({"ok": True, "escuadron": []})

@app.route("/api/escuadron/desplegar", methods=["POST"])
def desplegar_escuadron():
    """
    Despliega en el mapa actual el escuadrón que envía el navegador (lista de aliados con posición).
    Sustituye limpiamente a los aliados existentes / genéricos sin solapamientos ni duplicados.
    """
    data = request.get_json(force=True, silent=True) or {}
    squad = data.get("escuadron")
    if not isinstance(squad, list) or not squad:
        return jsonify({"error": "No hay ningún escuadrón guardado previamente."}), 404

    tablero.guardar_snapshot()

    # Eliminar todos los aliados existentes para evitar solapamientos con el escuadrón guardado
    aliados_actuales = [nom for nom, f in list(tablero.fichas.items()) if f.es_aliado]
    for nom in aliados_actuales:
        del tablero.fichas[nom]

    # Registrar cada aliado del escuadrón
    for s_data in squad:
        f_res = resolver_unidad_con_catalogo(s_data)
        tablero.registrar_unidad(f_res, resolver_colision=True)

    return jsonify({
        "ok": True,
        "mensaje": f"Escuadrón desplegado con éxito ({len(squad)} aliados)",
        "fichas": [f.como_dict() for f in tablero.fichas.values()]
    })

@app.route("/api/partida/exportar", methods=["GET"])
def exportar_partida():
    """Exporta el estado completo de la partida en formato JSON (fotografía exacta de unidades vivas)."""
    fichas_vivas = [f.como_dict() for f in tablero.fichas.values() if f.viva and f.hp_actual > 0]
    estado = {
        "turno_actual": tablero.turno_actual,
        "fase": tablero.fase,
        "capitulo": _capitulo_sesion(),
        "dificultad": tablero.dificultad,
        "refuerzos_pendientes": {str(t): list(us) for t, us in sorted(tablero.refuerzos_pendientes.items())},
        "refuerzos_por_evento": [dict(e, casilla=list(e["casilla"])) for e in tablero.refuerzos_por_evento],
        "casillas_fuego": tablero.casillas_fuego_lista(),
        "fichas": fichas_vivas
    }
    return jsonify({"ok": True, "partida": estado})

@app.route("/api/partida/importar", methods=["POST"])
def importar_partida():
    """Importa el estado completo de la partida desde un JSON (fotografía exacta)."""
    data = request.get_json(force=True)
    partida = data.get("partida") or data
    fichas_raw = partida.get("fichas", [])
    if not fichas_raw:
        return jsonify({"error": "No se encontraron fichas en el archivo de partida"}), 400

    tablero.guardar_snapshot()
    tablero.limpiar()
    tablero.turno_actual = int(partida.get("turno_actual", 1))
    tablero.fase = partida.get("fase", "jugador")
    if partida.get("dificultad"):
        tablero.dificultad = str(partida["dificultad"])
    else:
        # Guardados antiguos sin dificultad: la de las fichas (cada unidad recuerda con
        # cuál se desplegó), nunca un valor por defecto del servidor
        dif_fichas = [str(f.get("dificultad")) for f in fichas_raw if f.get("dificultad")]
        if dif_fichas:
            tablero.dificultad = max(set(dif_fichas), key=dif_fichas.count)

    # Una partida guardada es una fotografía del estado actual del mapa.
    # Se filtran y colocan exclusivamente las unidades vivas (viva: true y hp_actual > 0).
    fichas_vivas_raw = [
        f for f in fichas_raw
        if bool(f.get("viva", True)) and int(f.get("hp_actual", 1)) > 0
    ]

    jefes_cap = cargador_dispos.pids_jefe(f"M{_capitulo_sesion():03d}")
    for f_data in fichas_vivas_raw:
        f_data.setdefault("dificultad", tablero.dificultad)
        # El jefe lo marca el dispos (bit 16 del Flag), aunque el guardado venga de antes
        if f_data.get("pid") in jefes_cap and not f_data.get("es_aliado", False):
            f_data["es_jefe"] = True
        f_res = resolver_unidad_con_catalogo(f_data)
        if f_res.viva and f_res.hp_actual > 0:
            tablero.registrar_unidad(f_res)

    # Refuerzos: los pendientes guardados o, si la partida no los trae (guardados
    # antiguos), los del calendario del capítulo aún no llegados (turno > actual).
    tablero.casillas_fuego = {(int(c["x"]), int(c["y"])): int(c.get("expira_turno", tablero.turno_actual + 1))
                              for c in (partida.get("casillas_fuego") or []) if "x" in c and "y" in c}
    tablero.sincronizar_fuego_mapa()
    ref_guardados = partida.get("refuerzos_pendientes")
    if isinstance(ref_guardados, dict) and ref_guardados:
        tablero.programar_refuerzos({int(t): us for t, us in ref_guardados.items() if str(t).isdigit()})
    else:
        try:
            cal = _cargador_dispos.calendario_refuerzos(
                f"M{_capitulo_sesion():03d}", tablero.dificultad,
                mapa_ancho=getattr(_mapa, "ancho", 24), mapa_alto=getattr(_mapa, "alto", 17))
            tablero.programar_refuerzos({t: us for t, us in cal.items() if t > tablero.turno_actual})
        except Exception:
            tablero.programar_refuerzos({})
    ev_guardados = partida.get("refuerzos_por_evento")
    # Definiciones guardadas con OTRA dificultad (p.ej. tras un reinicio del servidor que
    # volvió al valor por defecto): las no disparadas se regeneran del datamine
    if isinstance(ev_guardados, list) and any(
        not e.get("disparado") and any(str(u.get("dificultad") or tablero.dificultad) != str(tablero.dificultad) for u in (e.get("unidades") or []))
        for e in ev_guardados
    ):
        try:
            frescos = {e["grupo"]: e for e in _cargador_dispos.refuerzos_por_evento(
                f"M{_capitulo_sesion():03d}", tablero.dificultad,
                mapa_ancho=getattr(_mapa, "ancho", 24), mapa_alto=getattr(_mapa, "alto", 17))}
            ev_guardados = [e if e.get("disparado") or e.get("grupo") not in frescos else dict(frescos[e["grupo"]], disparado=False)
                            for e in ev_guardados]
        except Exception:
            pass
    if isinstance(ev_guardados, list):
        tablero.programar_refuerzos_por_evento(ev_guardados)
    else:
        try:
            tablero.programar_refuerzos_por_evento(_cargador_dispos.refuerzos_por_evento(
                f"M{_capitulo_sesion():03d}", tablero.dificultad,
                mapa_ancho=getattr(_mapa, "ancho", 24), mapa_alto=getattr(_mapa, "alto", 17)))
        except Exception:
            tablero.programar_refuerzos_por_evento([])

    fichas_retorno = [f.como_dict() for f in tablero.fichas.values() if f.viva and f.hp_actual > 0]
    return jsonify({
        "ok": True,
        "mensaje": f"Partida importada con éxito ({len(fichas_retorno)} unidades vivas)",
        "fichas": fichas_retorno,
        "refuerzos_previstos": tablero.refuerzos_previstos(),
        "refuerzos_por_evento": tablero.refuerzos_por_evento_previstos(),
        "eventos_por_accion": tablero.eventos_por_accion(),
    })

@app.route("/api/unidad/eliminar", methods=["POST"])
def eliminar_unidad():
    """Elimina permanentemente una unidad del tablero."""
    data = request.get_json(force=True)
    nombre = data.get("nombre")
    if not nombre:
        return jsonify({"error": "Falta campo 'nombre'"}), 400
    ok = tablero.eliminar_unidad(nombre)
    return jsonify({"ok": ok, "nombre": nombre})

_cargador_dispos = CargadorDisposEngage()


def _desplegar_capitulo(capitulo_id: str, dificultad: str = "Extremo") -> dict:
    """
    Nucleo reutilizable de despliegue: limpia el tablero y carga las unidades
    del capitulo indicado desde los XMLs de dispos/ del datamine.
    Devuelve un dict con el resultado listo para jsonify.
    """
    tablero.fichas.clear()
    tablero.turno_actual = 1
    tablero.fase = "jugador"
    tablero.dificultad = dificultad
    tablero.inicializar_objetos_mapa()   # pozos, ballestas y destructibles vuelven al estado inicial

    ancho_m = getattr(_mapa, "ancho", 24)
    alto_m = getattr(_mapa, "alto", 17)
    unidades_dispos = _cargador_dispos.cargar_capitulo(capitulo_id, dificultad, mapa_ancho=ancho_m, mapa_alto=alto_m)
    if not unidades_dispos:
        num = tablero.cargar_spawns_desde_mapa()
        return {
            "ok": True,
            "mensaje": f"Sin dispos para {capitulo_id}; cargados {num} spawns del mapa",
            "fichas": [f.como_dict() for f in tablero.fichas.values()]
        }

    for u in unidades_dispos:
        ficha = resolver_unidad_con_catalogo(u)
        tablero.registrar_unidad(ficha)

    # Refuerzos del capítulo (calendario del .lua + grupos del dispos filtrados por dificultad)
    calendario = _cargador_dispos.calendario_refuerzos(capitulo_id, dificultad, mapa_ancho=ancho_m, mapa_alto=alto_m)
    tablero.programar_refuerzos(calendario)
    n_ref = sum(len(v) for v in calendario.values())
    txt_ref = f" · {n_ref} refuerzos programados (turnos {', '.join(str(t) for t in sorted(calendario))})" if n_ref else ""
    # Refuerzos condicionales del guion (p.ej. M009: al llegar Kagetsu/Zelkov a su fuerte)
    eventos = _cargador_dispos.refuerzos_por_evento(capitulo_id, dificultad, mapa_ancho=ancho_m, mapa_alto=alto_m)
    tablero.programar_refuerzos_por_evento(eventos)
    if eventos:
        txt_ref += " · " + "; ".join(
            f"{len(e['unidades'])} refuerzos cuando {e['descripcion'] or e['grupo']}"
            + (f" ({e['casilla'][0]},{e['casilla'][1]})" if e.get('casilla') else "")
            for e in eventos)

    return {
        "ok": True,
        "mensaje": f"Despliegue de {capitulo_id} ({len(unidades_dispos)} unidades) en {dificultad}{txt_ref}",
        "fichas": [f.como_dict() for f in tablero.fichas.values()],
        "refuerzos_previstos": tablero.refuerzos_previstos(),
        "refuerzos_por_evento": tablero.refuerzos_por_evento_previstos(),
    }


def _auto_despliegue_inicial():
    """
    Si el mapa cargado al arranque es formato datamine, despliega automaticamente
    las unidades del capitulo correspondiente en dificultad Extremo (Maddening).
    """
    if not getattr(_mapa, "es_datamine", False):
        return
    dispos_id = getattr(_mapa, "dispos_id", None)
    if not dispos_id:
        return
    try:
        resultado = _desplegar_capitulo(dispos_id, "Extremo")
        print(f"[Auto-despliegue] {len(tablero.fichas)} unidades cargadas para {dispos_id} (Extremo)")
    except Exception as e:
        print(f"[Auto-despliegue] Error al cargar {dispos_id}: {e}")


# Auto-despliegue de unidades en el arranque si el mapa es de datamine
_auto_despliegue_inicial()


def _dispos_id_activo() -> str:
    """Id de dispos del capítulo activo: M007, M008, ... (o el del mapa datamine si lo trae)."""
    return getattr(_mapa, "dispos_id", None) or f"M{_capitulo_sesion():03d}"


@app.route("/api/preset/actual", methods=["POST"])
@app.route("/api/preset/capitulo7", methods=["POST"])
@app.route("/api/preset/<capitulo_id>", methods=["POST"])
def cargar_preset_capitulo(capitulo_id=None):
    """
    Carga el despliegue oficial (grupos iniciales, sin refuerzos) desde dispos/ del
    datamine para el capítulo solicitado; sin capitulo_id, el del mapa activo.
    """
    data = request.get_json(silent=True) or {}
    dificultad = data.get("dificultad", "Extremo")
    if not capitulo_id or capitulo_id in ("actual", "capitulo7"):
        capitulo_id = _dispos_id_activo() if capitulo_id != "capitulo7" else "M007"
    return jsonify(_desplegar_capitulo(capitulo_id, dificultad))

@app.route("/api/unidad/rango_movimiento", methods=["GET"])
def obtener_rango_movimiento():
    """
    Calcula y devuelve las casillas que puede alcanzar una unidad específica
    según su MOV, tipo de movimiento y costes reales del terreno del mapa.
    """
    nombre = request.args.get("nombre")
    if not nombre:
        return jsonify({"error": "Falta parametro nombre"}), 400

    ficha = tablero.obtener_ficha(nombre)
    if not ficha:
        for f in tablero.fichas.values():
            if normalizar_texto(f.nombre) == normalizar_texto(nombre):
                ficha = f
                nombre = f.nombre
                break

    if not ficha:
        return jsonify({"error": f"Unidad '{nombre}' no encontrada"}), 404

    # Analizador de movimiento y amenazas
    analizador = AnalizadorAmenaza(_mapa.grid, _mapa.ancho, _mapa.alto)
    
    # Construir objeto para el analizador
    umock = UnidadMock(
        x=ficha.x,
        y=ficha.y,
        mov=ficha.mov or 4,
        es_volador=ficha.es_volador,
        arma=ArmaMock(ficha.arma.rango if ficha.arma else [1])
    )
    casillas_mov = analizador.calcular_casillas_alcanzables(umock)

    # Ocupantes: no se puede terminar el movimiento en una casilla ocupada por otra unidad viva
    ocupadas = {(f.x, f.y) for f in tablero.fichas.values() if f.viva and f.nombre != nombre}
    casillas_validas = [[x, y] for (x, y) in casillas_mov if (x, y) not in ocupadas or (x == ficha.x and y == ficha.y)]
    advance = _casillas_advance_de(ficha, casillas_mov)

    return jsonify({
        "ok": True,
        "nombre": nombre,
        "mov": ficha.mov or 4,
        "es_volador": ficha.es_volador,
        "casillas": casillas_validas,
        # Advance (Roy): casillas a las que solo se llega avanzando 1 hacia un enemigo para atacarlo
        "casillas_advance": [[x, y] for (x, y) in advance],
    })


def _casillas_advance_de(ficha, alcanzables) -> dict:
    """{Q: P} de Advance (SID_踏み込み) para `ficha`, o {} si no lo tiene."""
    if not pasivas.tiene_advance(ficha):
        return {}
    rivales = {(f.x, f.y) for f in tablero.fichas.values() if f.viva and f.es_aliado != ficha.es_aliado}
    ocupadas = {(f.x, f.y) for f in tablero.fichas.values() if f.viva and f.nombre != ficha.nombre}
    return casillas_advance(alcanzables, rivales, ocupadas, _mapa.grid, _mapa.ancho, _mapa.alto, ficha.es_volador)

@app.route("/api/mover", methods=["POST"])
def mover_unidad():
    """
    Actualiza la posición de una unidad respetando las reglas de movimiento táctico.
    Llamado por la UI cuando el jugador arrastra un token.
    Body JSON: {nombre, x, y, accion_pendiente?}
    `accion_pendiente`: el movimiento forma parte de una acción que sigue (hablar,
    usar objeto): no marca la unidad como "ha actuado"; lo hará la acción.
    """
    data = request.get_json(force=True)
    nombre = data.get("nombre")
    x = data.get("x")
    y = data.get("y")
    accion_pendiente = bool(data.get("accion_pendiente", False))

    if nombre is None or x is None or y is None:
        return jsonify({"error": "Faltan campos: nombre, x, y"}), 400

    if not _mapa.obtener_terreno(x, y):
        return jsonify({"error": f"Coordenada ({x},{y}) fuera del mapa"}), 400

    ficha = tablero.obtener_ficha(nombre)
    if not ficha:
        for f in tablero.fichas.values():
            if normalizar_texto(f.nombre) == normalizar_texto(nombre):
                ficha = f
                nombre = f.nombre
                break

    if not ficha:
        return jsonify({"error": f"Unidad '{nombre}' no encontrada"}), 404

    # En fase de jugador, si el aliado ya actuó, no se le permite volver a mover
    # (los verdes pendientes de unión los mueve la CPU: se recolocan libremente)
    if tablero.fase == "jugador" and ficha.controlable and ficha.ha_actuado:
        return jsonify({"error": f"{nombre} ya ha actuado este turno. Usa la Cronogema (Deshacer) para cambiar la elección."}), 400

    # 1. Casilla ocupada por otra unidad viva?
    otra_unidad = next((f for f in tablero.fichas.values() if f.viva and f.nombre != nombre and f.x == x and f.y == y), None)
    if otra_unidad:
        return jsonify({"error": f"La casilla ({x},{y}) ya está ocupada por {otra_unidad.nombre}."}), 400

    # 2. Validar alcance de movimiento táctico para la unidad (aliada o enemiga)
    analizador = AnalizadorAmenaza(_mapa.grid, _mapa.ancho, _mapa.alto)
    umock = UnidadMock(
        x=ficha.x,
        y=ficha.y,
        mov=ficha.mov or 4,
        es_volador=ficha.es_volador,
        arma=ArmaMock(ficha.arma.rango if ficha.arma else [1])
    )
    alcanzables = analizador.calcular_casillas_alcanzables(umock)
    via_advance = None
    if (x, y) not in alcanzables:
        via_advance = _casillas_advance_de(ficha, alcanzables).get((x, y))
        if via_advance is None:
            return jsonify({"error": f"{nombre} solo puede moverse {ficha.mov or 4} casillas. La casilla ({x},{y}) está fuera de su alcance o es intransitable."}), 400

    tablero.guardar_snapshot()
    ok = tablero.mover_unidad(nombre, x, y)
    if not ok:
        return jsonify({"error": f"Unidad '{nombre}' no encontrada"}), 404

    # Si un aliado se mueve en la fase de jugador, consume su acción del turno
    # (salvo que el movimiento sea el primer paso de una acción: mover + hablar/curar)
    if tablero.fase == "jugador" and ficha.controlable:
        ficha.ha_actuado = not accion_pendiente
    elif tablero.fase == "enemigo" and not ficha.es_aliado:
        ficha.ha_actuado = True

    return jsonify({
        "ok": True,
        "nombre": nombre,
        "x": x,
        "y": y,
        "turno": tablero.turno_actual,
        "advance_desde": list(via_advance) if via_advance else None,
        "ficha": ficha.como_dict(),
        "refuerzos_desplegados": tablero.refuerzos_desplegados_ultimo,
        "fichas": [f.como_dict() for f in tablero.fichas.values()]
    })

@app.route("/api/unidad/registrar_accion", methods=["POST"])
def registrar_accion_de_unidad():
    """
    El jugador marca que una unidad enemiga ha ACTUADO (ha atacado, ha usado un bastón…),
    algo que la herramienta no puede observar porque pasa en la fase enemiga. Dispara los
    refuerzos del guion que dependían de ello. Body: {"nombre": "Hortensia"}.
    """
    data = request.get_json(force=True) or {}
    nombre = str(data.get("nombre", "") or "")
    if not nombre:
        return jsonify({"error": "Falta campo 'nombre'"}), 400
    ficha = tablero.obtener_ficha(nombre)
    if ficha is None:
        return jsonify({"error": f"'{nombre}' no está en el tablero"}), 400
    if not tablero.tiene_evento_por_accion(nombre):
        return jsonify({"error": f"{nombre} no tiene ningún evento pendiente de que actúe"}), 400
    tablero.guardar_snapshot()
    refuerzos = tablero.disparar_refuerzos_por_evento("accion", ficha)
    return jsonify({
        "ok": True, "unidad": nombre,
        "refuerzos_desplegados": refuerzos,
        "eventos_por_accion": tablero.eventos_por_accion(),
        "fichas": [f.como_dict() for f in tablero.fichas.values()],
    })


@app.route("/api/unidad/escudo_vinculo", methods=["POST"])
def activar_escudo_vinculo():
    """
    Bonded Shield (Emblema de Lucina): marca a los aliados adyacentes como protegidos
    del primer ataque hasta el turno siguiente, con el % que corresponda a su estilo.
    Body: {"nombre": "Lucina"}.
    """
    data = request.get_json(force=True) or {}
    nombre = str(data.get("nombre", "") or "")
    if not nombre:
        return jsonify({"error": "Falta campo 'nombre'"}), 400
    tablero.guardar_snapshot()
    protegidos, error = tablero.activar_escudo_vinculo(nombre)
    if error:
        tablero.historial.pop()
        return jsonify({"error": error}), 400
    f = tablero.obtener_ficha(nombre)
    if f is not None and f.es_aliado:
        f.ha_actuado = True   # el comando consume la acción de la unidad
    return jsonify({
        "ok": True, "unidad": nombre, "protegidos": protegidos,
        "fichas": [x.como_dict() for x in tablero.fichas.values()],
    })


@app.route("/api/unidad/invocar_dobles", methods=["POST"])
def invocar_dobles_unidad():
    """
    Call Doubles (SID_残像, Emblema de Lyn): rodea a la unidad de copias suyas con 1 HP.
    El jugador lo usa para reflejar que el jefe (Hyacinth en el Cap. 10) ha usado el
    comando. Body: {"nombre": "Hyacinth"}.
    """
    data = request.get_json(force=True) or {}
    nombre = str(data.get("nombre", "") or "")
    if not nombre:
        return jsonify({"error": "Falta campo 'nombre'"}), 400
    tablero.guardar_snapshot()
    dobles, error = tablero.invocar_dobles(nombre)
    if error:
        tablero.historial.pop()
        return jsonify({"error": error}), 400
    f = tablero.obtener_ficha(nombre)
    if f is not None and f.es_aliado:
        f.ha_actuado = True   # el comando consume la acción de la unidad
    return jsonify({
        "ok": True, "invocador": nombre, "dobles": dobles,
        "fichas": [x.como_dict() for x in tablero.fichas.values()],
    })


@app.route("/api/unidad/disipar_dobles", methods=["POST"])
def disipar_dobles_unidad():
    """Dispel Doubles: retira del tablero los dobles de una unidad. Body: {"nombre": ...}."""
    data = request.get_json(force=True) or {}
    nombre = str(data.get("nombre", "") or "")
    if not nombre:
        return jsonify({"error": "Falta campo 'nombre'"}), 400
    tablero.guardar_snapshot()
    retirados = tablero.disipar_dobles(nombre)
    if not retirados:
        tablero.historial.pop()
        return jsonify({"error": f"'{nombre}' no tiene dobles en el tablero"}), 400
    return jsonify({
        "ok": True, "retirados": retirados,
        "fichas": [x.como_dict() for x in tablero.fichas.values()],
    })


@app.route("/api/muerte", methods=["POST"])
def registrar_muerte():
    """Marca una unidad como muerta. Body JSON: {nombre}"""
    data = request.get_json(force=True)
    nombre = data.get("nombre")
    if not nombre:
        return jsonify({"error": "Falta campo 'nombre'"}), 400
    tablero.guardar_snapshot()
    ficha = tablero.obtener_ficha(nombre)
    tablero.registrar_muerte(nombre)
    # Refuerzos que el guion dispara al caer esa unidad (M010: Morion)
    refuerzos = tablero.disparar_refuerzos_por_evento("muerte", ficha) if ficha else []
    dobles_disipados = tablero.purgar_dobles_huerfanos()
    return jsonify({
        "ok": True, "nombre": nombre, "dobles_disipados": dobles_disipados,
        "refuerzos_desplegados": refuerzos,
        "fichas": [f.como_dict() for f in tablero.fichas.values()] if refuerzos else None,
    })




# (Armas, posicionamiento optimo y backup modularizados en catalogo_loader y motor_analisis)

# =============================================================================
# API — Cronogema (Deshacer) y Gestión de Acciones
# =============================================================================

@app.route("/api/tablero/deshacer", methods=["POST"])
def deshacer_accion():
    """Restaura el estado anterior de la Cronogema (Time Crystal)."""
    ok = tablero.deshacer()
    return jsonify({
        "ok": ok,
        "mensaje": "Cronogema activada: Acción deshecha." if ok else "No hay más acciones previas para deshacer.",
        "turno": tablero.turno_actual,
        "fase": tablero.fase,
        "casillas_fuego": tablero.casillas_fuego_lista(),
        "objetos": tablero.objetos_como_lista(),
        "fichas": [f.como_dict() for f in tablero.fichas.values()]
    })

@app.route("/api/turno/reiniciar_acciones", methods=["POST"])
def reiniciar_acciones_turno():
    """Reactiva las acciones de todos los aliados para el turno actual."""
    tablero.guardar_snapshot()
    tablero.reiniciar_acciones_turno()
    return jsonify({
        "ok": True,
        "mensaje": "Acciones de turno reactivadas para todos los aliados.",
        "fichas": [f.como_dict() for f in tablero.fichas.values()]
    })

@app.route("/api/unidad/alternar_actuado", methods=["POST"])
def alternar_actuado():
    """Alterna el estado ha_actuado de una unidad."""
    data = request.get_json(force=True) or {}
    nombre = data.get("nombre")
    if not nombre:
        return jsonify({"error": "Falta campo nombre"}), 400
    tablero.guardar_snapshot()
    ok = tablero.alternar_actuado(nombre)
    f = tablero.obtener_ficha(nombre)
    # Marcar como actuado = "Esperar" en esa casilla: aplica pozos de Emblema y las
    # pasivas "al esperar" (Self-Improver, Meditación)
    recarga = tablero.aplicar_recarga_emblema_en_casilla(nombre) if (f and f.ha_actuado) else None
    estados_otorgados = pasivas_temporales.al_esperar(tablero, f) if (f and f.ha_actuado) else []
    return jsonify({
        "ok": ok,
        "ficha": f.como_dict() if f else None,
        "estados_otorgados": [{"unidad": n, **e} for n, e in estados_otorgados],
        "recarga_emblema": recarga,
        "objetos": tablero.objetos_como_lista() if recarga else None,
        "fichas": [x.como_dict() for x in tablero.fichas.values()]
    })

@app.route("/api/unidad/usar_objeto", methods=["POST"])
def usar_objeto():
    """
    Consume un uso de un objeto del inventario (bastón, poción, etc.) y marca
    la unidad como que ha actuado este turno de forma DEFINITIVA (a diferencia
    de /api/unidad/alternar_actuado, que alterna y puede des-marcar por error
    si se invoca dos veces — p.ej. al curar a dos objetivos distintos seguidos).
    """
    data = request.get_json(force=True) or {}
    nombre = data.get("nombre")
    item_nombre = data.get("item_nombre")
    if not nombre:
        return jsonify({"error": "Falta campo nombre"}), 400
    f = tablero.obtener_ficha(nombre)
    if not f:
        return jsonify({"error": f"Unidad '{nombre}' no encontrada"}), 404

    tablero.guardar_snapshot()

    if item_nombre:
        norm_buscado = normalizar_texto(item_nombre)
        for it in (f.inventario or []):
            nom_it = normalizar_texto(it.get("nombre") or it.get("arma") or "")
            if nom_it == norm_buscado or norm_buscado in nom_it or nom_it in norm_buscado:
                usos = it.get("usos")
                if usos is not None:
                    usos = max(0, int(usos) - 1)
                    if usos <= 0:
                        f.inventario.remove(it)
                    else:
                        it["usos"] = usos
                break

    # Antídoto: además de curar, elimina el veneno (Item.xml AddType=18)
    if item_nombre and any(k in normalizar_texto(item_nombre) for k in ("antidoto", "antidote")):
        f.nivel_veneno = 0
        if f.stats:
            setattr(f.stats, 'nivel_veneno', 0)

    f.ha_actuado = True
    # Usar objeto/bastón no es "Esperar": pasivas como Self-Improver no deben dispararse
    f.accion_turno = "baston" if any(k in normalizar_texto(item_nombre or "") for k in ("baston", "staff", "cura", "heal", "mend", "physic")) else "objeto"
    recarga = tablero.aplicar_recarga_emblema_en_casilla(nombre)

    return jsonify({
        "ok": True,
        "ficha": f.como_dict(),
        "recarga_emblema": recarga,
        "objetos": tablero.objetos_como_lista() if recarga else None,
        "fichas": [x.como_dict() for x in tablero.fichas.values()]
    })

@app.route("/api/unidad/hablar", methods=["POST"])
def hablar_con_unidad():
    """
    Recluta a un aliado verde pendiente de unión: `hablante` (adyacente, autorizado,
    con acción disponible) gasta su acción y `objetivo` pasa a ser controlable.
    Body: {"hablante": "Alear", "objetivo": "Jade", "x": 11, "y": 9}
    `x`, `y` (opcional): casilla adyacente al objetivo a la que se mueve el hablante
    antes de hablar; mover + hablar es UNA sola acción.
    """
    data = request.get_json(force=True) or {}
    hablante = data.get("hablante") or data.get("aliado")
    objetivo = data.get("objetivo")
    if not hablante or not objetivo:
        return jsonify({"error": "Faltan campos: hablante, objetivo"}), 400
    tablero.guardar_snapshot()
    f_h = tablero.obtener_ficha(hablante)
    if f_h and data.get("x") is not None and data.get("y") is not None:
        x, y = int(data["x"]), int(data["y"])
        if (x, y) != (f_h.x, f_h.y):
            if f_h.ha_actuado:
                tablero.historial.pop()
                return jsonify({"error": f"{f_h.nombre} ya ha actuado este turno"}), 400
            if any(f.viva and f.nombre != f_h.nombre and (f.x, f.y) == (x, y) for f in tablero.fichas.values()):
                tablero.historial.pop()
                return jsonify({"error": f"La casilla ({x},{y}) está ocupada"}), 400
            analizador = AnalizadorAmenaza(_mapa.grid, _mapa.ancho, _mapa.alto)
            umock = UnidadMock(x=f_h.x, y=f_h.y, mov=f_h.mov or 4, es_volador=f_h.es_volador, arma=ArmaMock([1]))
            setattr(umock, 'tiene_pass', pasivas.tiene_sid(f_h, 'SID_すり抜け'))
            bloqueo = {(f.x, f.y) for f in tablero.fichas.values() if f.viva and f.es_aliado != f_h.es_aliado}
            if (x, y) not in analizador.calcular_casillas_alcanzables(umock, casillas_bloqueadas=bloqueo):
                tablero.historial.pop()
                return jsonify({"error": f"{f_h.nombre} no puede llegar a ({x},{y}) este turno"}), 400
            tablero.mover_unidad(f_h.nombre, x, y)
    ok, mensaje = tablero.hablar(hablante, objetivo)
    if not ok:
        tablero.deshacer()
        return jsonify({"error": mensaje}), 400
    return jsonify({
        "ok": True,
        "mensaje": mensaje,
        "objetivo": tablero.obtener_ficha(objetivo).como_dict(),
        "fichas": [f.como_dict() for f in tablero.fichas.values()],
    })


@app.route("/api/unidad/alternar_chain_guard", methods=["POST"])
def alternar_chain_guard():
    """Alterna o fija el estado de Guardia en Cadena (Chain Guard) de una unidad Qi Adept."""
    data = request.get_json(force=True) or {}
    nombre = data.get("nombre")
    if not nombre:
        return jsonify({"error": "Falta campo nombre"}), 400
    nuevo_estado = data.get("activo")
    tablero.guardar_snapshot()
    ok = tablero.alternar_chain_guard(nombre, nuevo_estado)
    f = tablero.obtener_ficha(nombre)
    return jsonify({
        "ok": ok,
        "ficha": f.como_dict() if f else None,
        "fichas": [x.como_dict() for x in tablero.fichas.values()]
    })


# =============================================================================
# API — Combate Interactivo y Ajustes en Tiempo Real
# =============================================================================

def _casillas_movidas_en_mapa(ficha, destino):
    """Pasos del camino más corto de la ficha a `destino` sobre el mapa actual (Momentum)."""
    try:
        from motor_de_movimiento_y_amenaza import AnalizadorAmenaza
        from motor_analisis import _casillas_movidas

        class _T:
            def __init__(self, t):
                self.caminable = t.caminable
                self.volable = t.volable
                self.coste = t.coste_mov

        grid = [[_T(_mapa.grid[x][y]) for y in range(_mapa.alto)] for x in range(_mapa.ancho)]
        analizador = AnalizadorAmenaza(grid, _mapa.ancho, _mapa.alto)
        bloqueo = {(f.x, f.y) for f in tablero.fichas.values() if f.viva and f.es_aliado != ficha.es_aliado}
        return _casillas_movidas(ficha, destino, analizador, bloqueo)
    except Exception:
        return abs(ficha.x - destino[0]) + abs(ficha.y - destino[1])


def _activar_fusion(ficha, es_engage_attack: bool = False):
    """
    Activa la Fusión de Emblema de `ficha` (gasta el medidor). Devuelve un mensaje de
    error si no tiene energía, o None si se activó. El Mov se recalcula porque la
    Fusión puede cambiarlo (Gallop de Sigurd).
    """
    max_e = getattr(ficha, "max_energia_emblema", 6) or 6
    cur_e = getattr(ficha, "energia_emblema", max_e)
    if cur_e < max_e and not es_engage_attack:
        arma_nom = getattr(ficha.arma, 'nombre', 'su arma de Emblema') if ficha.arma else 'su Emblema'
        return (f"{ficha.nombre} no tiene energía suficiente ({cur_e}/{max_e}) para usar {arma_nom}. "
                "Debe recargar el medidor de Emblema.")
    # Todas las clases reciben 3 turnos de Fusión; solo el nivel de vínculo
    # con el Emblema (>=11) lo eleva a 4, sin excepción por estilo de clase.
    ficha.en_fusion = True
    ficha.turnos_fusion = 4 if getattr(ficha, 'nivel_vinculo', 1) >= 11 else 3
    ficha.energia_emblema = 0
    if ficha.stats:
        setattr(ficha.stats, 'en_fusion', True)
        setattr(ficha.stats, 'turnos_fusion_restantes', ficha.turnos_fusion)
        setattr(ficha.stats, 'energia_emblema', 0)
    ficha.actualizar_movimiento_fusion()   # Gallop (Sigurd): +5 Mov, +7 en caballería
    return None


@app.route("/api/combate/ejecutar", methods=["POST"])
def ejecutar_combate():
    """
    Ejecuta un ataque táctico en el tablero:
    1. Si se provee pos_destino (o se calcula), mueve al atacante a la casilla.
    2. Equipa el arma seleccionada en el atacante.
    3. Simula el combate determinista exacto de Engage con pasivas y chain attacks.
    4. Resta HP real al defensor, contraataque y recoil al atacante.
    5. Marca al atacante como ha_actuado = True.
    6. Otorga cargas de energía de Emblema (+1 combate, +1 kill).
    """
    data = request.get_json(force=True) or {}
    nombre_atk = data.get("atacante")
    nombre_def = data.get("defensor")
    nombre_arma = data.get("arma_nombre") or data.get("arma")
    pos_destino = data.get("pos_destino")
    es_engage_attack = bool(data.get("es_engage_attack", False))
    engage_attack_nombre = str(data.get("engage_attack_nombre", "") or "")

    f_atk = tablero.obtener_ficha(nombre_atk)
    f_def = tablero.obtener_ficha(nombre_def)

    if not f_atk or not f_def:
        return jsonify({"error": "No se encontraron las unidades especificadas"}), 400

    # La jugada pide Fusión: se activa ANTES de mover, porque la Fusión puede cambiar
    # el movimiento (Gallop de Sigurd: +5 Mov, +7 en caballería) y la casilla de ataque
    # propuesta puede depender de ese alcance extra.
    if bool(data.get("requiere_fusion", False)) and not f_atk.en_fusion:
        error_fusion = _activar_fusion(f_atk, es_engage_attack)
        if error_fusion:
            return jsonify({"error": error_fusion}), 400

    # 0. Ballesta de mapa (objeto_id): la unidad dispara su propio arco desde la
    # casilla de la ballesta. Requiere maestría en Arco + un arco en el inventario.
    objeto_id = str(data.get("objeto_id", "") or "")
    objeto_ballesta = None
    if objeto_id:
        est_obj = tablero.objetos.get(objeto_id)
        ent_obj = next((e for e in _mapa.objetos_mapa() if e.id_entidad == objeto_id), None) if hasattr(_mapa, 'objetos_mapa') else None
        if not est_obj or not ent_obj or est_obj.get("tipo") != "arma_usable":
            return jsonify({"error": f"No hay un arma usable con id '{objeto_id}' en el mapa"}), 400
        if not est_obj.get("activo") or (est_obj.get("usos") is not None and est_obj["usos"] <= 0):
            return jsonify({"error": f"{ent_obj.nombre} ya no tiene usos"}), 400
        if not puede_usar_arma_de_mapa(f_atk, ent_obj.propiedades):
            tipo_req = tipo_arma_de_objeto(ent_obj.propiedades)
            return jsonify({"error": f"{f_atk.nombre} no puede usar {ent_obj.nombre}: necesita una clase con maestría en {tipo_req} y un arma de ese tipo en el inventario"}), 400
        objeto_ballesta = ent_obj
        pos_destino = list(ent_obj.casillas[0])   # hay que disparar desde la propia ballesta
        nombre_arma = None                          # el arma se construye a partir del arco propio

    # Guardar snapshot antes de la acción para la Cronogema
    tablero.guardar_snapshot()

    # 1. Posición de ataque: si viene pos_destino válida, mover al atacante tras validar ocupación
    distancia_movida = 0
    if pos_destino and isinstance(pos_destino, (list, tuple)) and len(pos_destino) == 2:
        nx, ny = int(pos_destino[0]), int(pos_destino[1])
        if (nx, ny) != (f_atk.x, f_atk.y):
            otra = [f for f in tablero.fichas.values() if f.viva and f.nombre != f_atk.nombre and f.x == nx and f.y == ny]
            if otra:
                return jsonify({"error": f"La casilla ({nx}, {ny}) está ocupada por {otra[0].nombre}. No se puede atacar desde ahí."}), 400
            distancia_movida = _casillas_movidas_en_mapa(f_atk, (nx, ny))
            tablero.mover_unidad(nombre_atk, nx, ny)
    # Momentum (Sigurd): casillas recorridas antes de atacar (0 si ataca desde donde está)
    if f_atk.stats is not None:
        setattr(f_atk.stats, 'distancia_movida', int(data.get("distancia_movida", distancia_movida) or 0))

    # 2. Equipar arma
    if nombre_arma:
        arma_encontrada = False
        norm_nom_arma = normalizar_texto(nombre_arma)
        for item in f_atk.inventario:
            n_it = normalizar_texto(item.get("nombre") or item.get("arma") or "")
            if n_it == norm_nom_arma or item.get("id") == nombre_arma:
                for it in f_atk.inventario:
                    it["equipada"] = (it == item)
                a_obj = _arma_desde_item(item)
                if a_obj:
                    f_atk.arma = a_obj
                arma_encontrada = True
                break
        if not arma_encontrada:
            for a_eng, es_eng, _ in _armas_aliado(f_atk):
                if normalizar_texto(a_eng.nombre) == norm_nom_arma or norm_nom_arma in normalizar_texto(a_eng.nombre):
                    f_atk.arma = a_eng
                    if getattr(a_eng, 'es_engage_attack', False):
                        es_engage_attack = True
                        engage_attack_nombre = getattr(a_eng, 'engage_attack_nombre', nombre_arma)
                    arma_encontrada = True
                    break
        if not arma_encontrada:
            a_obj = _arma_desde_item({"arma": nombre_arma})
            if a_obj:
                f_atk.arma = a_obj
                arma_encontrada = True

    # 2b. Arma efectiva de la ballesta (arco propio + Hit 20, alcance 3–7, un golpe)
    arma_original_ballesta = None
    if objeto_ballesta:
        arma_b = arma_de_mapa_desde(f_atk, objeto_ballesta.propiedades, objeto_ballesta.nombre)
        if not arma_b:
            return jsonify({"error": f"{f_atk.nombre} no lleva ningún arma de tipo {tipo_arma_de_objeto(objeto_ballesta.propiedades)}"}), 400
        arma_original_ballesta = f_atk.arma
        f_atk.arma = arma_b

    # 3. Detectar aliados de apoyo (Backup) cercanos al objetivo para Chain Attacks
    apoyos_fichas = obtener_aliados_backup(
        f_atk, f_def, tablero=tablero,
        ataque_emblema=engage_attack_nombre if es_engage_attack else "") if not objeto_ballesta else []
    for a in apoyos_fichas:
        if a.stats and a.arma:
            setattr(a.stats, 'arma', a.arma)
    aliados_backup = [a.stats for a in apoyos_fichas]

    # 4. Distancia y terrenos
    dist = abs(f_atk.x - f_def.x) + abs(f_atk.y - f_def.y)
    r_arma = f_atk.arma.rango if (f_atk.arma and f_atk.arma.rango) else [1]

    # Si no se pasó pos_destino y la unidad no está en rango desde su casilla actual:
    if dist not in r_arma and not pos_destino:
        pos_sug = encontrar_pos_ataque_optima(f_atk, f_def, f_atk.arma)
        if pos_sug is not None and pos_sug != [f_atk.x, f_atk.y]:
            tablero.mover_unidad(nombre_atk, pos_sug[0], pos_sug[1])
            dist = abs(f_atk.x - f_def.x) + abs(f_atk.y - f_def.y)

    # Si tras verificar/mover NO está en rango válido del arma, RECHAZAR el combate
    if dist not in r_arma:
        return jsonify({
            "error": f"El atacante {f_atk.nombre} en ({f_atk.x}, {f_atk.y}) no alcanza al objetivo {f_def.nombre} en ({f_def.x}, {f_def.y}) con {f_atk.arma.nombre} (distancia actual {dist}, rango de arma {r_arma}). No hay casilla libre válida."
        }), 400

    dist_combate = dist

    t_atk = _mapa.grid[f_atk.x][f_atk.y]
    t_def = _mapa.grid[f_def.x][f_def.y]

    casillas_ocupadas = {(f.x, f.y) for f in tablero.fichas.values() if f.viva and f.nombre not in (f_atk.nombre, f_def.nombre)}

    # Los verdes pendientes de unión no dan apoyos ni auras al ejército (ni al revés)
    def _mismo_bando(f, ref):
        return f.es_aliado == ref.es_aliado and f.union_pendiente == ref.union_pendiente

    aliados_cercanos_atk = [
        (f.stats, abs(f.x - f_atk.x) + abs(f.y - f_atk.y))
        for f in tablero.fichas.values()
        if f.viva and _mismo_bando(f, f_atk) and f.nombre != f_atk.nombre and f.stats
    ]
    aliados_cercanos_def = [
        (f.stats, abs(f.x - f_def.x) + abs(f.y - f_def.y))
        for f in tablero.fichas.values()
        if f.viva and _mismo_bando(f, f_def) and f.nombre != f_def.nombre and f.stats
    ]

    es_engage_attack = bool(data.get("es_engage_attack", False) or es_engage_attack)
    engage_attack_nombre = str(data.get("engage_attack_nombre", "") or engage_attack_nombre)

    # 2c. Ataques de Emblema de área (Override / Blazing Lion): resolver la geometría
    # ANTES del combate, con todos los objetivos aún vivos. Se aplica después.
    area_engage = None
    if es_engage_attack and engage_attack_nombre and tipo_ataque_area(engage_attack_nombre):
        area_engage = resolver_ataque_area(engage_attack_nombre, (f_atk.x, f_atk.y), f_def, f_atk, tablero, _mapa)
        if not area_engage.get("valido"):
            return jsonify({"error": f"{engage_attack_nombre} no puede usarse desde ({f_atk.x}, {f_atk.y}): {area_engage.get('motivo')}"}), 400

    es_arma_emblema = bool(getattr(f_atk.arma, 'es_engage', False) or "(emblema)" in getattr(f_atk.arma, 'nombre', '').lower())
    if (es_engage_attack or es_arma_emblema) and not f_atk.en_fusion:
        error_fusion = _activar_fusion(f_atk, es_engage_attack)
        if error_fusion:
            return jsonify({"error": error_fusion}), 400

    # Sincronización estricta de HP actual con el objeto de stats antes de simular
    if f_atk.stats:
        f_atk.stats.hp = f_atk.hp_actual
        f_atk.stats.hp_max = f_atk.hp_max
        setattr(f_atk.stats, 'hp_actual', f_atk.hp_actual)
    if f_def.stats:
        f_def.stats.hp = f_def.hp_actual
        f_def.stats.hp_max = f_def.hp_max
        setattr(f_def.stats, 'hp_actual', f_def.hp_actual)
        setattr(f_def.stats, 'hp_stock', getattr(f_def, 'hp_stock', 0))

    cg_protector = obtener_protector_chain_guard(f_def, tablero)

    combate = CalculadoraEngage.simular_combate(
        atacante=f_atk.stats,
        defensor=f_def.stats,
        arma_atk=f_atk.arma,
        arma_def=f_def.arma,
        terreno_atk=Terreno(avo=t_atk.avo, dfn=t_atk.dfn,
            curacion_turno=getattr(t_atk, 'curacion_turno', 0),
            es_antirruptura=getattr(t_atk, 'es_antirruptura', False)),
        terreno_def=Terreno(avo=t_def.avo, dfn=t_def.dfn,
            curacion_turno=getattr(t_def, 'curacion_turno', 0),
            es_antirruptura=getattr(t_def, 'es_antirruptura', False)),
        distancia=dist_combate,
        aliados_apoyo_backup=aliados_backup,
        pos_atk=(f_atk.x, f_atk.y),
        pos_def=(f_def.x, f_def.y),
        mapa=_mapa,
        casillas_ocupadas=casillas_ocupadas,
        defensor_en_ruptura=(getattr(f_def, 'cargas_ruptura', 0) > 0),
        aliados_cercanos_atk=aliados_cercanos_atk,
        aliados_cercanos_def=aliados_cercanos_def,
        es_engage_attack=es_engage_attack,
        engage_attack_nombre=engage_attack_nombre,
        chain_guard_protector=cg_protector,
    )

    res = combate["resultado"]
    hp_def_final = res["hp_defensor_final"]
    hp_atk_final = res["hp_atacante_final"]

    # Piedra resurrectora consumida:
    if res.get("piedra_resurrectora_consumida"):
        f_def.hp_stock = max(0, getattr(f_def, 'hp_stock', 0) - 1)
        hp_def_final = f_def.hp_max
        if f_def.stats:
            f_def.stats.hp = f_def.hp_max

    # Guardia en cadena: aplicar retroceso al protector
    cg_res = res.get("chain_guard", {})
    if cg_res.get("activo") and cg_res.get("protector"):
        f_prot = tablero.obtener_ficha(cg_res["protector"])
        if f_prot:
            dmg_cg = cg_res.get("daño_protector", 0)
            nuevo_hp_prot = max(1, f_prot.hp_actual - dmg_cg)
            tablero.modificar_hp(f_prot.nombre, nuevo_hp_prot)
            f_prot.chain_guard_usado = True

    # Aplicar HP resultante en el estado mutable del tablero
    tablero.modificar_hp(nombre_def, hp_def_final)
    tablero.modificar_hp(nombre_atk, hp_atk_final)

    # Aplicar efecto de Veneno si corresponde
    if res.get("aplica_veneno") and hp_def_final > 0:
        f_def.nivel_veneno = min(3, max(0, getattr(f_def, 'nivel_veneno', 0)) + 1)
        if f_def.stats:
            setattr(f_def.stats, 'nivel_veneno', f_def.nivel_veneno)

    # Efecto Smash: empuje físico de 1 casilla o ruptura si choca contra obstáculo
    smash_res = res.get("smash", {})
    if smash_res.get("empujado") and smash_res.get("nueva_pos") and hp_def_final > 0:
        nueva_x, nueva_y = smash_res["nueva_pos"]
        tablero.mover_unidad(nombre_def, nueva_x, nueva_y)

    # Gestión canónica de Ruptura (Break) en FE Engage:
    if hp_def_final > 0:
        if res.get("aplica_ruptura") or smash_res.get("rompio_por_choque"):
            f_def.cargas_ruptura = 1
        elif getattr(f_def, 'cargas_ruptura', 0) > 0:
            f_def.cargas_ruptura = 0

    # Disparadores de pasivas temporales: un aliado atacado en fase enemiga
    # (p.ej. ¡Ponte detrás de mí! en portadores a <=2 casillas). Se considera
    # atacado a cualquier aliado que participe en el combate, aunque no pierda HP.
    estados_otorgados = []
    for u_atacada in (f_def, f_atk):
        estados_otorgados += pasivas_temporales.al_danar_aliado(tablero, u_atacada)

    # Ataques de Emblema de área (Override / Blazing Lion): objetivos extra, casilla de
    # llegada del atacante y fuego. La geometría la decide ataques_area con las
    # posiciones reales tras el movimiento de ataque.
    objetivos_extra_res = []
    fuego_encendido = []
    pos_final_area = None
    if area_engage is not None and hp_atk_final > 0:
        area = area_engage
        if area.get("valido"):
            for e_extra in (area.get("objetivos") or [])[1:]:
                if not e_extra.viva or not e_extra.stats:
                    continue
                t_ex = _mapa.grid[e_extra.x][e_extra.y]
                # Mismos bonos de posición del atacante que contra el objetivo principal
                # (Guía Divina, Gente de Cuento…): golpea a todos desde su casilla de ataque
                aliados_cercanos_ex = [
                    (f.stats, abs(f.x - e_extra.x) + abs(f.y - e_extra.y))
                    for f in tablero.fichas.values()
                    if f.viva and _mismo_bando(f, e_extra) and f.nombre != e_extra.nombre and f.stats
                ]
                r_ex = CalculadoraEngage.simular_combate(
                    f_atk.stats, e_extra.stats, f_atk.arma, e_extra.arma,
                    Terreno(avo=t_atk.avo, dfn=t_atk.dfn), Terreno(avo=t_ex.avo, dfn=t_ex.dfn), distancia=1,
                    es_engage_attack=True, engage_attack_nombre=engage_attack_nombre,
                    aliados_cercanos_atk=aliados_cercanos_atk, aliados_cercanos_def=aliados_cercanos_ex,
                    pos_atk=(f_atk.x, f_atk.y), pos_def=(e_extra.x, e_extra.y),
                )
                dmg_ex = int(r_ex["atacante"].get("daño_total_ronda", 0) or 0)
                nuevo_hp = max(0, e_extra.hp_actual - dmg_ex)
                tablero.modificar_hp(e_extra.nombre, nuevo_hp)
                if nuevo_hp > 0 and getattr(e_extra, 'cargas_ruptura', 0) > 0:
                    e_extra.cargas_ruptura = 0
                objetivos_extra_res.append({"nombre": e_extra.nombre, "daño": dmg_ex, "hp_tras": nuevo_hp, "muere": nuevo_hp <= 0})
            if area.get("tipo") == "override" and area.get("pos_final"):
                lx, ly = area["pos_final"]
                if not any(f.viva and f.nombre != f_atk.nombre and (f.x, f.y) == (lx, ly) for f in tablero.fichas.values()):
                    tablero.mover_unidad(nombre_atk, lx, ly)
                    pos_final_area = [lx, ly]
            elif area.get("tipo") == "blazing_lion" and area.get("casillas_fuego"):
                fuego_encendido = [list(c) for c in tablero.encender_fuego(area["casillas_fuego"])]

    # Repliegue táctico de Canter (Movimiento ágil tras combate si atacante sobrevive)
    pos_canter = data.get("pos_canter")
    if pos_canter and isinstance(pos_canter, (list, tuple)) and len(pos_canter) == 2 and hp_atk_final > 0:
        cx, cy = int(pos_canter[0]), int(pos_canter[1])
        if (cx, cy) != (f_atk.x, f_atk.y):
            casilla_libre = not any(f.viva and f.nombre != f_atk.nombre and f.x == cx and f.y == cy for f in tablero.fichas.values())
            if casilla_libre:
                tablero.mover_unidad(nombre_atk, cx, cy)

    # Marcar atacante como que ha actuado este turno si es aliado
    if f_atk.es_aliado:
        f_atk.ha_actuado = True
        f_atk.accion_turno = "combate"

    # Registrar uso de ataque o tecnica especial de Engage (solo 1 vez por fusion)
    if es_engage_attack:
        f_atk.ataque_emblema_usado = True
        if f_atk.stats:
            setattr(f_atk.stats, 'ataque_emblema_usado', True)

    # Medidor de Emblema (Engage Gauge): +1 por cada ataque que la unidad HACE o
    # RECIBE en el combate (acierte o falle; los golpes dobles de Brave/Artes y el de
    # Velocidad Divina cuentan cada uno), sin contar los Chain Attacks. Derrotar al
    # rival no da carga por sí mismo: solo Libération (SID_撃破時エンゲージカウント＋１).
    # Se cuentan los golpes REALES de la secuencia (si el rival muere al primer golpe
    # no hay follow-up ni contraataque que sumar). Verificado en juego (Cap. 9).
    secuencia_combate = res.get("secuencia", [])
    combatientes = {f_atk.nombre, f_def.nombre}
    ataques_en_combate = sum(
        1 for s in secuencia_combate
        if s.get("actor") in combatientes and s.get("tipo") not in ("piedra_resurrectora", "chain_attack")
    )

    def _sumar_medidor(ficha, ganancia):
        if ficha.es_aliado and not ficha.en_fusion and getattr(ficha, 'turnos_fusion', 0) <= 0 and ganancia > 0:
            ficha.energia_emblema = min(ficha.max_energia_emblema, ficha.energia_emblema + ganancia)
            if ficha.stats:
                ficha.stats.energia_emblema = ficha.energia_emblema

    # Ballesta: gasta el turno como un ataque normal pero NO recarga el medidor de
    # Emblema (sin verificar en el juego; cambiar aquí si se confirma lo contrario).
    if not objeto_ballesta:
        if f_atk.es_aliado and getattr(t_atk, 'es_recarga_emblema', False) and not f_atk.en_fusion:
            f_atk.energia_emblema = f_atk.max_energia_emblema
            if f_atk.stats:
                f_atk.stats.energia_emblema = f_atk.energia_emblema
        else:
            ganancia_atk = ataques_en_combate
            if hp_def_final <= 0 and (pasivas.tiene_sid(f_atk, 'SID_撃破時エンゲージカウント＋１')
                                      or 'SID_撃破時エンゲージカウント＋１' in (getattr(f_atk.arma, 'sids', None) or [])):
                ganancia_atk += 1
            _sumar_medidor(f_atk, ganancia_atk)
        _sumar_medidor(f_def, ataques_en_combate)

    # Ballesta: gastar un uso y devolver a la unidad su arma equipada real
    if objeto_ballesta:
        tablero.consumir_objeto_mapa(objeto_ballesta.id_entidad)
        if arma_original_ballesta is not None:
            f_atk.arma = arma_original_ballesta

    # Pozo de Emblema: la acción termina sobre la casilla final (tras Canter) → recarga y se agota
    recarga = tablero.aplicar_recarga_emblema_en_casilla(f_atk.nombre) if (f_atk.es_aliado and hp_atk_final > 0) else None

    # Refuerzos que dispara el guion al combatir con cierta unidad (M010: Hortensia) o
    # al derrotarla (M010: Morion). Ver cargador_dispos.REFUERZOS_POR_EVENTO.
    refuerzos_evento = tablero.disparar_refuerzos_por_evento("combate", f_atk, f_def)
    caidos = [f_def] if hp_def_final <= 0 else []
    caidos += [tablero.obtener_ficha(e["nombre"]) for e in objetivos_extra_res if e.get("muere")]
    if hp_atk_final <= 0:
        caidos.append(f_atk)
    if caidos:
        refuerzos_evento += tablero.disparar_refuerzos_por_evento("muerte", *[c for c in caidos if c])
    dobles_disipados = tablero.purgar_dobles_huerfanos()

    return jsonify({
        "ok": True,
        "combate": combate,
        "atacante": f_atk.como_dict(),
        "defensor": f_def.como_dict(),
        "estados_otorgados": [{"unidad": n, **e} for n, e in estados_otorgados],
        "recarga_emblema": recarga,
        "objetivos_extra": objetivos_extra_res,
        "pos_final_area": pos_final_area,
        "casillas_fuego": tablero.casillas_fuego_lista(),
        "refuerzos_desplegados": refuerzos_evento,
        "dobles_disipados": dobles_disipados,
        "objetos": tablero.objetos_como_lista() if (objeto_ballesta or recarga) else None,
        "fichas": [f.como_dict() for f in tablero.fichas.values()]
    })

@app.route("/api/unidad/alternar_lider_tres_casas", methods=["POST"])
def api_alternar_lider_tres_casas():
    """Alterna el líder activo del Emblema de las Tres Casas (Edelgard / Dimitri / Claude)."""
    data = request.get_json(force=True) or {}
    nombre = data.get("nombre")
    lider = data.get("lider")
    if not nombre:
        return jsonify({"error": "Falta campo nombre"}), 400
    tablero.guardar_snapshot()
    nuevo = tablero.alternar_lider_tres_casas(nombre, lider)
    f = tablero.obtener_ficha(nombre)
    return jsonify({
        "ok": True,
        "lider_activo": nuevo,
        "ficha": f.como_dict() if f else None,
        "fichas": [x.como_dict() for x in tablero.fichas.values()]
    })

@app.route("/api/unidad/ajustar_veneno", methods=["POST"])
def api_ajustar_veneno():
    """Modifica directamente el nivel de veneno (0..3) de una unidad."""
    data = request.get_json(force=True) or {}
    nombre = data.get("nombre")
    nivel = data.get("nivel_veneno", 0)
    if not nombre:
        return jsonify({"error": "Falta campo nombre"}), 400
    tablero.guardar_snapshot()
    nuevo = tablero.ajustar_nivel_veneno(nombre, nivel)
    f = tablero.obtener_ficha(nombre)
    return jsonify({
        "ok": True,
        "nivel_veneno": nuevo,
        "ficha": f.como_dict() if f else None,
        "fichas": [x.como_dict() for x in tablero.fichas.values()]
    })

@app.route("/api/unidad/ajustar_hp", methods=["POST"])
def ajustar_hp():
    """Modifica directamente el HP actual de una unidad."""
    data = request.get_json(force=True) or {}
    nombre = data.get("nombre")
    hp = data.get("hp_actual")
    if not nombre or hp is None:
        return jsonify({"error": "Faltan campos nombre y hp_actual"}), 400
    tablero.guardar_snapshot()
    f = tablero.obtener_ficha(nombre)
    hp_previo = f.hp_actual if f else None
    ok = tablero.modificar_hp(nombre, int(hp))
    # Una bajada manual de HP de un aliado durante la fase enemiga se interpreta
    # como "ha sido atacado" (no hay otra fuente de daño aliado en esa fase):
    # dispara pasivas como ¡Ponte detrás de mí! sin necesitar acciones enemigas.
    estados_otorgados = []
    if ok and f and hp_previo is not None and int(hp) < hp_previo:
        estados_otorgados = pasivas_temporales.al_danar_aliado(tablero, f)
    # Bajar el HP a 0 a mano es derrotar a la unidad: puede disparar refuerzos del guion
    refuerzos = tablero.disparar_refuerzos_por_evento("muerte", f) if (ok and f and int(hp) <= 0) else []
    dobles_disipados = tablero.purgar_dobles_huerfanos()
    return jsonify({
        "ok": ok,
        "ficha": f.como_dict() if f else None,
        "dobles_disipados": dobles_disipados,
        "estados_otorgados": [{"unidad": n, **e} for n, e in estados_otorgados],
        "refuerzos_desplegados": refuerzos,
        "fichas": [x.como_dict() for x in tablero.fichas.values()]
    })

@app.route("/api/unidad/ajustar_nivel", methods=["POST"])
def ajustar_nivel():
    """Recalcula las estadísticas de una unidad según un nuevo nivel."""
    data = request.get_json(force=True) or {}
    nombre = data.get("nombre")
    nuevo_nivel = int(data.get("nivel", 1))
    if not nombre:
        return jsonify({"error": "Falta campo nombre"}), 400
    f = tablero.obtener_ficha(nombre)
    if not f:
        return jsonify({"error": "Unidad no encontrada"}), 404
    tablero.guardar_snapshot()
    f_dict = f.como_dict()
    f_dict["nivel"] = nuevo_nivel
    nueva_ficha = resolver_unidad_con_catalogo(f_dict)
    tablero.registrar_unidad(nueva_ficha)
    return jsonify({
        "ok": True,
        "ficha": nueva_ficha.como_dict(),
        "fichas": [x.como_dict() for x in tablero.fichas.values()]
    })

@app.route("/api/unidad/bono_fusion_estimado", methods=["GET"])
def bono_fusion_estimado():
    """
    Estimación del bono de stats de Rise Above (Roy, Nv+5 en Fusión) por
    crecimientos personaje+clase. El valor real lo decide el juego: el jugador
    puede anotar la diferencia observada en la ficha (boosts_fusion).
    """
    from catalogo_loader import boosts_rise_above
    nombre = request.args.get("nombre", "")
    clase = request.args.get("clase", "")
    return jsonify({"ok": True, "estimado": boosts_rise_above(nombre, clase)})


@app.route("/api/unidad/resolver_preview", methods=["POST"])
def resolver_unidad_preview():
    """
    Recibe nombre, clase (opcional), nivel (opcional), es_aliado, etc. y devuelve
    las estadísticas exactas resueltas del catálogo junto con clase_default, nivel_base y stats.
    """
    data = request.get_json(force=True) or {}
    nombre = data.get("nombre", "").strip()
    if not nombre:
        return jsonify({"error": "Falta nombre"}), 400

    # Buscar si existe el personaje en el catálogo para rellenar clase_default y nivel_base
    p_info = None
    n_norm = normalizar_texto(nombre)
    for cpid, cperson in _catalogo.get("personajes", {}).items():
        if normalizar_texto(cperson.get("nombre", "")) == n_norm or normalizar_texto(cpid) == n_norm:
            p_info = cperson
            break

    clase_nombre = data.get("clase_nombre", "").strip()
    if not clase_nombre and p_info:
        clase_nombre = p_info.get("clase_default", "")

    nivel_raw = data.get("nivel")
    if nivel_raw is None or str(nivel_raw).strip() == "" or str(nivel_raw) == "0":
        nivel = p_info.get("nivel_base", 1) if p_info else 10
    else:
        nivel = max(1, int(nivel_raw))

    payload = dict(data)
    payload["nombre"] = p_info.get("nombre", nombre) if p_info else nombre
    payload["clase_nombre"] = clase_nombre
    payload["nivel"] = nivel

    ficha = resolver_unidad_con_catalogo(payload)
    f_dict = ficha.como_dict()

    return jsonify({
        "ok": True,
        "nombre": ficha.nombre,
        "clase_nombre": ficha.clase_nombre,
        "nivel": ficha.nivel,
        "hp_max": ficha.hp_max,
        "hp_actual": ficha.hp_actual,
        "mov": ficha.mov,
        "stats": f_dict.get("stats", {}),
        "es_aliado": ficha.es_aliado,
        "arma_nombre": ficha.arma.nombre if ficha.arma else "",
        "ficha": f_dict
    })


# =============================================================================
# API — Turnos
# =============================================================================

@app.route("/api/turno/inicio_fase_enemigo", methods=["POST"])
def iniciar_fase_enemigo():
    """Marca que el jugador está arrastrando fichas del turno enemigo."""
    estados_otorgados = []
    recargas = []
    if tablero.fase == "jugador":
        # Cerrar la fase de jugador: quien no actuó, esperó (dispara Self-Improver, etc.)
        estados_otorgados = pasivas_temporales.al_terminar_fase_jugador(tablero)
        # ...y si esperó sobre un pozo de Emblema, lo usa
        for f in list(tablero.fichas.values()):
            if f.viva and f.es_aliado and not f.accion_turno:
                r = tablero.aplicar_recarga_emblema_en_casilla(f.nombre)
                if r:
                    recargas.append(r)
    tablero.iniciar_fase_enemigo()
    return jsonify({
        "ok": True, "fase": tablero.fase, "turno": tablero.turno_actual,
        "quemados": [{"unidad": n, "daño": d} for n, d in tablero.quemados_ultimo],
        "curados_terreno": [{"unidad": n, "curacion": c} for n, c in tablero.curados_ultimo],
        "casillas_fuego": tablero.casillas_fuego_lista(),
        "estados_otorgados": [{"unidad": n, **e} for n, e in estados_otorgados],
        "recargas_emblema": recargas,
        "objetos": tablero.objetos_como_lista(),
        "fichas": [f.como_dict() for f in tablero.fichas.values()]
    })

@app.route("/api/turno/fin", methods=["POST"])
def fin_turno():
    """
    El jugador ha terminado de actualizar las posiciones enemigas.
    Avanza al siguiente turno y vuelve a la fase del jugador, reactivando aliados.
    """
    tablero.avanzar_turno()
    return jsonify({
        "ok": True, "fase": tablero.fase, "turno": tablero.turno_actual,
        "quemados": [{"unidad": n, "daño": d} for n, d in tablero.quemados_ultimo],
        "curados_terreno": [{"unidad": n, "curacion": c} for n, c in tablero.curados_ultimo],
        "casillas_fuego": tablero.casillas_fuego_lista(),
        "refuerzos_desplegados": tablero.refuerzos_desplegados_ultimo,
        "refuerzos_previstos": tablero.refuerzos_previstos(),
        "fichas": [f.como_dict() for f in tablero.fichas.values()],
    })


@app.route("/api/refuerzos", methods=["GET"])
def listar_refuerzos():
    """Refuerzos pendientes del capítulo activo, con el turno en que aparecen."""
    return jsonify({"ok": True, "turno_actual": tablero.turno_actual, "refuerzos": tablero.refuerzos_previstos(),
                    "refuerzos_por_evento": tablero.refuerzos_por_evento_previstos()})


# =============================================================================
# API — Análisis (el botón [Analizar])
# =============================================================================

@app.route("/api/analizar", methods=["POST"])
def analizar():
    """
    Análisis táctico completo por turno (delegado a motor_analisis.py).
    """
    try:
        data = request.get_json(force=True) or {}
        perfil = data.get("perfil", "seguro")
        cronogema = data.get("cronogema_usada", False)
        return jsonify(analizar_situacion_tactica(
            tablero, _mapa, perfil, cronogema,
            condicion_victoria=cargador_dispos.condicion_victoria(f"M{_capitulo_sesion():03d}"),
        ))
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e), "resultados": []}), 500


# =============================================================================
# API — Reset y Limpieza
# =============================================================================

@app.route("/api/tablero/limpiar", methods=["POST"])
def limpiar_tablero():
    """Elimina absolutamente todas las fichas del tablero."""
    tablero.guardar_snapshot()
    tablero.limpiar()
    return jsonify({
        "ok": True,
        "mensaje": "Tablero limpio: todas las fichas eliminadas.",
        "fichas": []
    })

@app.route("/api/reset", methods=["POST"])
def reset():
    """
    Reinicia el tablero al estado inicial (Turno 1, Fase Jugador, Spawns del capitulo activo).
    - Mapa Datamine: recarga dispos desde el XML del capitulo.
    - Mapa Tiled: limpia el tablero y carga los spawns de la capa de objetos del mapa.
    """
    tablero.guardar_snapshot()
    tablero.inicializar_objetos_mapa()  # ballestas, destructibles y pozos vuelven a estar activos
    cap_id = getattr(_mapa, "dispos_id", None)
    if cap_id:
        # Mapa Datamine: despliegue normal desde XML de dispos
        resultado = _desplegar_capitulo(cap_id, "Extremo")
        nombre_cap = getattr(_mapa, "nombre_en", cap_id)
        fichas_result = resultado["fichas"]
    else:
        # Mapa Tiled (o cualquier mapa sin dispos_id)
        tablero.fichas.clear()
        tablero.turno_actual = 1
        tablero.fase = "jugador"
        num = tablero.cargar_spawns_desde_mapa()
        nombre_cap = getattr(_mapa, "filepath", "Mapa Tiled").split("/")[-1].split("\\")[-1]
        fichas_result = [f.como_dict() for f in tablero.fichas.values()]
    return jsonify({
        "ok": True,
        "mensaje": f"Tablero reiniciado al Turno 1 con {nombre_cap} ({len(tablero.fichas)} unidades).",
        "fase": tablero.fase,
        "turno": tablero.turno_actual,
        "fichas": fichas_result
    })


# =============================================================================
# Entrada
# =============================================================================

if __name__ == "__main__":
    print("=== FE Engage Tactical Assistant ===")
    capitulo_info = getattr(_mapa, 'nombre_en', None) or getattr(_mapa, 'cid', 'Tiled')
    print(f"Mapa cargado: {_mapa.ancho}x{_mapa.alto} | {capitulo_info}")
    print("Servidor en http://localhost:5000")
    app.run(debug=True, port=5000)
