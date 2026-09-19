"""
Escenarios reales para los tests de caracterización (golden) del motor de combate.

Cada escenario construye un EstadoTablero con unidades resueltas por el catálogo
(mismo camino que la app: resolver_unidad_con_catalogo + registrar_unidad), y
`enumerar_combates` simula TODOS los pares atacante/defensor/arma/distancia
alcanzables en ambos sentidos (fase de jugador y fase enemiga), con y sin
Fusión para los aliados con Emblema.

No se usa Flask: el golden fija el comportamiento de motor_calculo y de la
recolección de pasivas, no el de los endpoints.
"""

import os
import sys
import json
import copy

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from lector_de_mapas import MapaTactico
from estado_tablero import EstadoTablero
from cargador_dispos import CargadorDisposEngage, DISPOS_DIR
from catalogo_loader import resolver_unidad_con_catalogo
from motor_calculo import CalculadoraEngage, Terreno
from motor_analisis import obtener_aliados_backup, obtener_protector_chain_guard, _armas_aliado

DIR_MAPAS = os.path.join(RAIZ, "mapas")
DIR_FIXTURES = os.path.join(RAIZ, "tests", "fixtures")
RUTA_ROSTER = os.path.join(RAIZ, "json", "escuadron_guardado.json")


def hay_datamine() -> bool:
    return os.path.isdir(DISPOS_DIR)


def _ruta_mapa(capitulo: int) -> str:
    return os.path.join(DIR_MAPAS, f"CAP_{capitulo}_Tiled.json")


def capitulos_con_mapa() -> list:
    caps = []
    for fn in os.listdir(DIR_MAPAS):
        if fn.startswith("CAP_") and fn.endswith("_Tiled.json"):
            try:
                caps.append(int(fn[4:-11]))
            except ValueError:
                pass
    return sorted(caps)


def _cargar_roster() -> list:
    with open(RUTA_ROSTER, "r", encoding="utf-8") as f:
        return json.load(f)


def escenario_capitulo_inicial(capitulo: int, dificultad: str = "Extremo"):
    """Mapa del capítulo + dispos oficiales del datamine + roster guardado de aliados."""
    mapa = MapaTactico(_ruta_mapa(capitulo))
    tablero = EstadoTablero(mapa=mapa, auto_cargar_spawns=False)
    tablero.dificultad = dificultad
    dispos_id = getattr(mapa, "dispos_id", None) or f"M{capitulo:03d}"
    cargador = CargadorDisposEngage()
    unidades = cargador.cargar_capitulo(dispos_id, dificultad,
                                        mapa_ancho=getattr(mapa, "ancho", 24),
                                        mapa_alto=getattr(mapa, "alto", 17))
    for u in unidades:
        tablero.registrar_unidad(resolver_unidad_con_catalogo(u))
    for s in _cargar_roster():
        s = copy.deepcopy(s)
        s.setdefault("dificultad", dificultad)
        tablero.registrar_unidad(resolver_unidad_con_catalogo(s), resolver_colision=True)
    return mapa, tablero


def escenario_partida(nombre_fixture: str, capitulo: int):
    """Fotografía de una partida real exportada por la app (solo unidades vivas)."""
    mapa = MapaTactico(_ruta_mapa(capitulo))
    tablero = EstadoTablero(mapa=mapa, auto_cargar_spawns=False)
    with open(os.path.join(DIR_FIXTURES, nombre_fixture), "r", encoding="utf-8") as f:
        partida = json.load(f)
    partida = partida.get("partida") or partida
    tablero.turno_actual = int(partida.get("turno_actual", 1))
    tablero.fase = partida.get("fase", "jugador")
    tablero.dificultad = str(partida.get("dificultad") or "Extremo")
    for f_data in partida.get("fichas", []):
        if not bool(f_data.get("viva", True)) or int(f_data.get("hp_actual", 1)) <= 0:
            continue
        f_data = copy.deepcopy(f_data)
        f_data.setdefault("dificultad", tablero.dificultad)
        ficha = resolver_unidad_con_catalogo(f_data)
        if ficha.viva and ficha.hp_actual > 0:
            tablero.registrar_unidad(ficha)
    return mapa, tablero


def escenarios_disponibles() -> dict:
    """{nombre: callable() -> (mapa, tablero)} de los escenarios que se pueden construir aquí."""
    esc = {}
    if hay_datamine():
        for cap in capitulos_con_mapa():
            esc[f"cap{cap}_inicial"] = (lambda c=cap: escenario_capitulo_inicial(c))
    if os.path.exists(os.path.join(DIR_FIXTURES, "partida_cap7_turno10.json")) and os.path.exists(_ruta_mapa(7)):
        esc["cap7_turno10"] = (lambda: escenario_partida("partida_cap7_turno10.json", 7))
    return esc


# ── Enumeración de combates ──────────────────────────────────────────────────

def _terreno_de(mapa, ficha) -> Terreno:
    try:
        t = mapa.grid[ficha.x][ficha.y]
    except Exception:
        return Terreno()
    return Terreno(avo=getattr(t, "avo", 0), dfn=getattr(t, "dfn", 0),
                   curacion_turno=getattr(t, "curacion_turno", 0),
                   es_antirruptura=getattr(t, "es_antirruptura", False))


def _aliados_cercanos(tablero, ficha) -> list:
    return [
        (f.stats, abs(f.x - ficha.x) + abs(f.y - ficha.y))
        for f in tablero.fichas.values()
        if f.viva and f.es_aliado == ficha.es_aliado and f.nombre != ficha.nombre and f.stats
    ]


def _sincronizar_hp(ficha):
    if ficha.stats:
        ficha.stats.hp = ficha.hp_actual
        ficha.stats.hp_max = ficha.hp_max
        setattr(ficha.stats, "hp_actual", ficha.hp_actual)
        setattr(ficha.stats, "hp_stock", getattr(ficha, "hp_stock", 0))


def _con_fusion(ficha, activa: bool):
    ficha.en_fusion = activa
    ficha.turnos_fusion = 3 if activa else 0
    if ficha.stats:
        setattr(ficha.stats, "en_fusion", activa)
        setattr(ficha.stats, "turnos_fusion_restantes", 3 if activa else 0)


def _compactar(res: dict) -> dict:
    """Subconjunto estable y legible del resultado de simular_combate."""
    a, d, r = res["atacante"], res["defensor"], res["resultado"]
    return {
        "atk": {
            "dano": a["daño_por_golpe"], "crit": a["daño_critico"], "hit": a["precision"],
            "pcrit": a["prob_critico"], "golpes": a["golpes_en_ronda"], "follow": a["tiene_follow_up"],
            "recoil": a["recoil_hp"], "efect": a.get("multiplicador_efectividad"),
            "pasivas": sorted(str(p) for p in a.get("pasivas_activas", [])),
            "apoyos": sorted(str(p) for p in a.get("apoyos_activos", [])),
        },
        "def": {
            "contra": d["puede_contraatacar"], "dano": d["daño_por_golpe"], "crit": d["daño_critico"],
            "hit": d["precision"], "pcrit": d["prob_critico"], "golpes": d["golpes_en_ronda"],
            "follow": d["tiene_follow_up"],
            "pasivas": sorted(str(p) for p in d.get("pasivas_activas", [])),
            "apoyos": sorted(str(p) for p in d.get("apoyos_activos", [])),
        },
        "res": {
            "hp_atk": r["hp_atacante_final"], "hp_def": r["hp_defensor_final"],
            "ruptura": r["aplica_ruptura"], "roto": r["defensor_roto"],
            "chain": r["chain_attacks_daño"], "veneno": r["nivel_veneno_defensor_post"],
            "secuencia": [f"{s.get('actor')}|{s.get('tipo')}|{s.get('daño')}" for s in r.get("secuencia", [])],
        },
    }


def enumerar_combates(mapa, tablero, con_fusion: bool = True) -> dict:
    """
    {clave: resultado_compacto} para todo par (atacante, defensor) de bandos
    opuestos, cada arma del atacante y cada distancia del rango del arma.
    La clave codifica atacante|arma|fusión|distancia|defensor.
    """
    salida = {}
    fichas = [f for f in tablero.fichas.values() if f.viva and f.stats]
    for f_atk in fichas:
        variantes_fusion = [False]
        if con_fusion and f_atk.es_aliado and getattr(f_atk, "emblema_nombre", "") and not getattr(f_atk, "es_verde", False):
            variantes_fusion.append(True)
        for fusion in variantes_fusion:
            _con_fusion(f_atk, fusion)
            armas = _armas_aliado(f_atk)
            for arma, es_engage, _nota in armas:
                if getattr(arma, "es_engage_attack", False):
                    continue   # los Ataques de Emblema de área tienen su propio módulo/tests
                rango = arma.rango or [1]
                for f_def in fichas:
                    if f_def.es_aliado == f_atk.es_aliado or f_def.nombre == f_atk.nombre:
                        continue
                    for dist in sorted(set(int(r) for r in rango)):
                        _sincronizar_hp(f_atk)
                        _sincronizar_hp(f_def)
                        arma_prev = f_atk.arma
                        f_atk.arma = arma
                        try:
                            apoyos = obtener_aliados_backup(f_atk, f_def, tablero=tablero)
                            for ap in apoyos:
                                setattr(ap.stats, "arma", ap.arma)
                            res = CalculadoraEngage.simular_combate(
                                atacante=f_atk.stats, defensor=f_def.stats,
                                arma_atk=arma, arma_def=f_def.arma,
                                terreno_atk=_terreno_de(mapa, f_atk), terreno_def=_terreno_de(mapa, f_def),
                                distancia=dist,
                                aliados_apoyo_backup=[ap.stats for ap in apoyos],
                                pos_atk=(f_atk.x, f_atk.y), pos_def=(f_def.x, f_def.y), mapa=mapa,
                                casillas_ocupadas={(f.x, f.y) for f in fichas if f.nombre not in (f_atk.nombre, f_def.nombre)},
                                defensor_en_ruptura=bool(getattr(f_def, "en_ruptura", False)),
                                aliados_cercanos_atk=_aliados_cercanos(tablero, f_atk),
                                aliados_cercanos_def=_aliados_cercanos(tablero, f_def),
                                chain_guard_protector=obtener_protector_chain_guard(f_def, tablero),
                            )
                            valor = _compactar(res)
                        except Exception as e:   # el golden también fija los errores actuales
                            valor = {"error": f"{type(e).__name__}: {e}"}
                        finally:
                            f_atk.arma = arma_prev
                        clave = f"{f_atk.nombre}|{arma.nombre}|{'F' if fusion else '-'}|d{dist}|{f_def.nombre}"
                        salida[clave] = valor
            _con_fusion(f_atk, False)
    return salida
