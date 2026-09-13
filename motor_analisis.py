"""
Motor de Análisis Táctico e Inteligencia Artificial para Fire Emblem Engage.
Contiene:
- Algoritmos de búsqueda espacial BFS y posicionamiento óptimo (encontrar_pos_ataque_optima).
- Detección de unidades de apoyo (Backup / 連携) para Chain Attacks (80% Hit, 10% daño).
- Análisis completo de turno:
    1. Detección de amenazas enemigas letales y críticas.
    2. Evaluación multi-arma de oportunidades de ataque del jugador (kills seguros, follow-up, ruptura).
    3. Bastones de curación de soporte (Heal, Mend, Physic) y pociones de emergencia.
    4. Táctica de Fusión de Emblema (Burst vs Conservar).
"""

import math
from collections import deque
from motor_calculo import CalculadoraEngage, Terreno
from motor_de_movimiento_y_amenaza import AnalizadorAmenaza, ContextoMapaEnemigo, UnidadMock, ArmaMock
from catalogo_loader import _arma_desde_item, _catalogo, normalizar_texto

BACKUP_CLASSES = {
    'sword fighter', 'lance fighter', 'axe fighter',
    'swordmaster', 'halberdier', 'berserker', 'warrior', 'hero',
    'mirmidon', 'mirmidón', 'lancero', 'luchador', 'alabardero', 'guerrero', 'heroe', 'héroe'
}

def es_unidad_backup(ficha_o_stats) -> bool:
    """
    Determina si una unidad es de estilo Backup (De apoyo / 連携) en Fire Emblem Engage.
    """
    if not ficha_o_stats:
        return False
    stats = getattr(ficha_o_stats, 'stats', ficha_o_stats)
    clase = str(getattr(ficha_o_stats, 'clase_nombre', '') or getattr(stats, 'clase_nombre', '') or '').lower().strip()
    estilo = str(getattr(stats, 'estilo_combate', '') or getattr(ficha_o_stats, 'estilo_combate', '') or '').lower().strip()
    nombre = str(getattr(ficha_o_stats, 'nombre', '') or getattr(stats, 'nombre', '') or '').lower().strip()

    if any(k in estilo for k in ('apoyo', 'backup', '連', '携')):
        return True
    if clase in BACKUP_CLASSES:
        return True
    if 'lapis' in nombre:
        return True
    return False

def obtener_aliados_backup(atacante_ficha, defensor_ficha, tablero=None):
    """
    Retorna la lista de fichas compañeras vivas que pueden realizar Chain Attack contra defensor_ficha.
    Reglas FE Engage:
      - Mismo bando que el atacante (aliado o enemigo).
      - Unidad de estilo Backup (De apoyo / 連携).
      - En rango de su arma equipada respecto a la posición del defensor.
      - Viva y distinta del atacante y del defensor.
    """
    if tablero is None:
        import sys
        if '__main__' in sys.modules and hasattr(sys.modules['__main__'], 'tablero'):
            tablero = sys.modules['__main__'].tablero
        elif 'app' in sys.modules and hasattr(sys.modules['app'], 'tablero'):
            tablero = sys.modules['app'].tablero
        else:
            from app import tablero as _tab
            tablero = _tab

    if atacante_ficha.es_aliado:
        companeros = tablero.obtener_aliados()
    else:
        companeros = tablero.obtener_enemigos()

    apoyos = []
    for c in companeros:
        if not c.viva or c.nombre in (atacante_ficha.nombre, defensor_ficha.nombre):
            continue
        if not c.stats or not c.arma:
            continue
        if not es_unidad_backup(c):
            continue
        dist_c = abs(c.x - defensor_ficha.x) + abs(c.y - defensor_ficha.y)
        r_c = c.arma.rango if (c.arma and c.arma.rango) else [1]
        if dist_c in r_c:
            apoyos.append(c)
    return apoyos

def encontrar_pos_ataque_optima(aliado, enemigo, arma, mapa=None, tablero=None, analizador=None, casillas_alcanzables_precalc=None, zonas_amenaza_enemigos=None):
    """
    Encuentra la mejor casilla (x, y) libre a la que puede moverse el aliado para atacar al enemigo con el arma dada.
    Reglas oficiales de Fire Emblem Engage:
    1. Si el aliado puede atacar sin sufrir contraataque (ej. a dist 2 con Jabalina/Tomo contra arma cuerpo a cuerpo, o a dist 1 contra arquero), prioriza esa casilla segura (+500 pts).
    2. Movimiento por BFS respetando costes de terreno y obstáculos:
       - Los enemigos vivos bloquean el paso físico como muros (salvo pasiva Pass / Traspasar).
       - Se puede transitar a través de aliados vivos.
       - La casilla de destino final no puede estar ocupada por ninguna otra unidad viva (aliada ni enemiga).
    3. Exposición a líneas de peligro enemigas (Danger Zone):
       - Penaliza casillas que queden dentro del rango de ataque de otros enemigos vivos (-80 pts por cada enemigo que alcanza la casilla).
    4. Bonificaciones defensivas de terreno (DFN*15 + AVO) y menor distancia recorrida.
    5. Si NO existe ninguna casilla física libre y alcanzable -> devuelve None (no puede atacar este turno).
    """
    if tablero is None:
        from app import tablero as _tab
        tablero = _tab
    if mapa is None:
        mapa = tablero.mapa

    r_arma = arma.rango if (arma and arma.rango) else [1]
    r_enemigo = enemigo.arma.rango if (enemigo and enemigo.arma and enemigo.arma.rango) else [1]
    enemigo_roto = getattr(enemigo, 'cargas_ruptura', 0) > 0

    todas_ocupadas = {(f.x, f.y) for f in tablero.fichas.values() if f.viva and f.nombre != aliado.nombre}

    if casillas_alcanzables_precalc is not None:
        casillas_alcanzables = casillas_alcanzables_precalc
    else:
        enemigos_bloqueo = {(f.x, f.y) for f in tablero.obtener_enemigos() if f.viva and f.nombre != enemigo.nombre}
        enemigos_bloqueo.add((enemigo.x, enemigo.y))

        habs_aliado = [str(h).lower() for h in (getattr(aliado, 'habilidades', []) or [])]
        tiene_pass = any('pass' in h or 'traspasar' in h or 'すり抜け' in h for h in habs_aliado) or ('thief' in getattr(aliado, 'clase_nombre', '').lower())

        ancho = mapa.ancho
        alto = mapa.alto
        es_volador = getattr(aliado, 'es_volador', False)

        if analizador is not None:
            u_mock = UnidadMock(
                x=aliado.x,
                y=aliado.y,
                mov=aliado.mov,
                es_volador=es_volador,
                arma=ArmaMock(rango=r_arma)
            )
            setattr(u_mock, 'tiene_pass', tiene_pass)
            casillas_alcanzables = analizador.calcular_casillas_alcanzables(
                u_mock,
                casillas_bloqueadas=enemigos_bloqueo
            )
        else:
            cola = deque([(aliado.x, aliado.y, aliado.mov)])
            visitados = {(aliado.x, aliado.y): aliado.mov}
            direcciones = [(0, 1), (1, 0), (0, -1), (-1, 0)]
            while cola:
                cx, cy, mov_restante = cola.popleft()
                for dx, dy in direcciones:
                    nx, ny = cx + dx, cy + dy
                    if not (0 <= nx < ancho and 0 <= ny < alto):
                        continue
                    if not tiene_pass and (nx, ny) in enemigos_bloqueo:
                        continue
                    t = mapa.grid[nx][ny]
                    volable = getattr(t, 'volable', True)
                    caminable = getattr(t, 'caminable', True)
                    coste = 1 if es_volador and volable else (getattr(t, 'coste_mov', 1) if caminable else 999)
                    nuevo_mov = mov_restante - coste
                    if nuevo_mov >= 0 and nuevo_mov > visitados.get((nx, ny), -1):
                        visitados[(nx, ny)] = nuevo_mov
                        cola.append((nx, ny, nuevo_mov))
            casillas_alcanzables = set(visitados.keys())

    mejores = []
    for (nx, ny) in casillas_alcanzables:
        if (nx, ny) in todas_ocupadas:
            continue
        d_ene = abs(nx - enemigo.x) + abs(ny - enemigo.y)
        if d_ene in r_arma:
            t = mapa.grid[nx][ny]
            coste_pasos = abs(nx - aliado.x) + abs(ny - aliado.y)
            enemigo_contraataca = (not enemigo_roto) and (enemigo.arma is not None) and (d_ene in r_enemigo)
            bonus_seguridad = 500 if not enemigo_contraataca else 0

            # Evaluación de exposición a otros enemigos (Líneas de peligro de Engage)
            penalizacion_amenazas = 0
            if zonas_amenaza_enemigos:
                amenazas_externas = sum(
                    1 for e_nom, zona in zonas_amenaza_enemigos.items()
                    if e_nom != enemigo.nombre and (nx, ny) in zona
                )
                penalizacion_amenazas = amenazas_externas * 80

            score = bonus_seguridad + (t.dfn * 15) + t.avo - coste_pasos - penalizacion_amenazas
            mejores.append((score, [nx, ny]))

    if mejores:
        mejores.sort(key=lambda x: x[0], reverse=True)
        return mejores[0][1]

    return None


def unidad_tiene_canter(ficha) -> bool:
    """Canter puede proceder de Sigurd o de una habilidad heredada."""
    habilidades = [str(h).lower() for h in (getattr(ficha, 'habilidades', []) or [])]
    emblema = str(getattr(ficha, 'emblema_nombre', '') or '').lower()
    return (
        any('canter' in h or 'canto' in h or 'galopada' in h or '再移動' in h for h in habilidades)
        or 'sigurd' in emblema or 'シグルド' in emblema
    )


def alcance_canter(ficha) -> int:
    """Devuelve 2 para Canter y 3 para Canter+ (incluida herencia)."""
    habilidades = [str(h).strip().lower().replace(" ", "")
                   for h in (getattr(ficha, 'habilidades', []) or [])]
    if any("canter+" in h or "canterplus" in h for h in habilidades):
        return 3
    return 2


def calcular_retirada_canter(aliado, pos_ataque, mapa, tablero, zonas_amenaza_enemigos,
                              objetivo_nombre=None, objetivo_derrotado=False,
                              posicion_inicial=None, analizador=None, permitir_sin_repliegue=False):
    """Propone una retirada Canter solo si reduce amenazas tras el combate.

    El presupuesto es el movimiento que realmente quedó después de llegar a la
    casilla de ataque, no una distancia fija.
    """
    if not unidad_tiene_canter(aliado):
        return None

    if analizador is None:
        class _TerrenoAdapter:
            def __init__(self, t):
                self.caminable = t.caminable
                self.volable = t.volable
                self.coste = t.coste_mov
        grid = [[_TerrenoAdapter(mapa.grid[x][y]) for y in range(mapa.alto)] for x in range(mapa.ancho)]
        analizador = AnalizadorAmenaza(grid, mapa.ancho, mapa.alto)

    inicio = posicion_inicial or (aliado.x, aliado.y)
    enemigos_bloqueo = {
        (f.x, f.y) for f in tablero.obtener_enemigos()
        if f.viva and f.nombre != aliado.nombre
    }
    mock_inicio = UnidadMock(inicio[0], inicio[1], aliado.mov, aliado.es_volador, ArmaMock([1]))
    habilidades = [str(h).lower() for h in (getattr(aliado, 'habilidades', []) or [])]
    setattr(mock_inicio, 'tiene_pass', any('pass' in h or 'traspasar' in h for h in habilidades))
    restantes_inicio = analizador.calcular_movimiento_restante(mock_inicio, enemigos_bloqueo)
    restante = restantes_inicio.get(tuple(pos_ataque))
    if restante is None or restante <= 0:
        return None

    # Canter solo permite 2 casillas; Canter+ permite 3. No debe consumir todo
    # el movimiento restante de la unidad tras alcanzar la casilla de ataque.
    movimiento_canter = min(restante, alcance_canter(aliado))
    if movimiento_canter <= 0:
        return None
    mock_canter = UnidadMock(pos_ataque[0], pos_ataque[1], movimiento_canter, aliado.es_volador, ArmaMock([1]))
    setattr(mock_canter, 'tiene_pass', getattr(mock_inicio, 'tiene_pass', False))
    enemigos_despues = {
        (f.x, f.y) for f in tablero.obtener_enemigos()
        if f.viva and f.nombre != aliado.nombre
        and not (objetivo_derrotado and f.nombre == objetivo_nombre)
    }
    restantes_canter = analizador.calcular_movimiento_restante(mock_canter, enemigos_despues)
    ocupadas = {(f.x, f.y) for f in tablero.fichas.values() if f.viva and f.nombre != aliado.nombre}
    if objetivo_derrotado and objetivo_nombre:
        objetivo = tablero.obtener_ficha(objetivo_nombre)
        if objetivo:
            ocupadas.discard((objetivo.x, objetivo.y))

    zonas = dict(zonas_amenaza_enemigos or {})
    if objetivo_derrotado and objetivo_nombre:
        zonas.pop(objetivo_nombre, None)

    def contar_amenazas(pos):
        return sum(1 for zona in zonas.values() if pos in zona)

    amenazas_ataque = contar_amenazas(tuple(pos_ataque))
    candidatas = [pos for pos in restantes_canter if pos not in ocupadas and pos != tuple(pos_ataque)]
    if not candidatas:
        return None
    candidatas.sort(key=lambda pos: (
        contar_amenazas(pos),
        -(getattr(mapa.grid[pos[0]][pos[1]], 'dfn', 0) * 15 + getattr(mapa.grid[pos[0]][pos[1]], 'avo', 0)),
        -restantes_canter[pos]
    ))
    mejor = candidatas[0]
    amenazas_final = contar_amenazas(mejor)
    if amenazas_final >= amenazas_ataque and not permitir_sin_repliegue:
        return None
    return {
        'pos_canter': [mejor[0], mejor[1]],
        'movimiento_restante': restante,
        'amenazas_ataque': amenazas_ataque,
        'amenazas_final': amenazas_final,
        'casillas_legales': {tuple(pos) for pos in candidatas},
    }

def _armas_aliado(aliado):
    """Obtiene todas las armas usables del inventario de un aliado."""
    armas = []
    for item in (aliado.inventario or []):
        if not isinstance(item, dict):
            continue
        tipo = item.get("tipo", "")
        if tipo in ("Bastón", "Objeto", "Accesorio"):
            continue
        a = _arma_desde_item(item)
        if a and a.mt > 0:
            es_engage = item.get("es_engage", False)
            nota = ""
            if "ragnarok" in a.nombre.lower() or "teleragna" in a.nombre.lower():
                nota = "TeleRagnarok: expone al aliado (solo si kill seguro)"
            elif es_engage:
                nota = "Arma de Engage"
            armas.append((a, es_engage, nota))

    if not armas and aliado.arma:
        armas.append((aliado.arma, False, ""))

    return armas


def _emblema_equipado(ficha):
    """Devuelve el nombre del emblema realmente equipado, si existe.

    No basta con que la ficha tenga energía de emblema: las unidades sin anillo
    también conservan el contador por compatibilidad con partidas antiguas.
    """
    # FichaUnidad es la fuente de verdad del anillo equipado. No heredamos un
    # nombre antiguo de stats si la ficha se ha actualizado a "sin emblema".
    if hasattr(ficha, "emblema_nombre"):
        nombre = getattr(ficha, "emblema_nombre", "")
    else:
        nombre = getattr(getattr(ficha, "stats", None), "emblema_nombre", "")
    nombre = str(nombre or "").strip()
    if nombre.lower() in {"none", "null", "ninguno", "sin emblema"}:
        return ""
    return nombre


def _detalle_acciones_emblema(nombre):
    """Obtiene armas y habilidades de Engage desde el catálogo, sin hardcodear emblemas."""
    buscado = normalizar_texto(nombre)
    info = None
    for dato in (_catalogo.get("emblemas", {}) or {}).values():
        if normalizar_texto(dato.get("nombre", "")) == buscado or normalizar_texto(dato.get("ascii_name", "")) == buscado:
            info = dato
            break
    if not info:
        return []
    acciones = []
    for iid in info.get("engage_items", []):
        arma_info = (_catalogo.get("armas", {}) or {}).get(iid, {})
        acciones.append(arma_info.get("nombre", iid))
    for sid in info.get("engage_skills", []):
        skill_info = (_catalogo.get("habilidades", {}) or {}).get(sid, {})
        nombre_skill = skill_info.get("nombre", sid)
        if nombre_skill and "daño" not in str(nombre_skill).lower() and "damage" not in str(nombre_skill).lower():
            acciones.append(nombre_skill)
    return acciones


def _sugerencia_habilidad_engage(nombre, ficha):
    """Describe una ventaja táctica de Engage usando el catálogo cargado."""
    emb = normalizar_texto(nombre)
    ataques = _ataques_engage_catalogo(nombre)
    if ataques:
        nombre_ataque, poder = ataques[0]
        detalle = f"usar {nombre_ataque}"
        if poder:
            detalle += f" (bonificador de poder del catálogo: +{poder})"
        if emb == "marth":
            detalle += "; ejecuta varios golpes y aprovecha una Velocidad suficiente para rematar"
        elif emb == "sigurd":
            clase = normalizar_texto(getattr(ficha, "clase_nombre", "") or getattr(getattr(ficha, "stats", None), "clase_nombre", ""))
            mov = "+7" if any(k in clase for k in ("caballero", "paladin", "jinete", "cavalier", "great knight")) else "+5"
            detalle += f"; la Fusión también concede {mov} Movimiento para alcanzar o replegarse"
        elif emb == "edelgard" or emb == "three houses":
            detalle += "; Houses Unite combina los golpes de hacha, lanza y arco del brazalete"
        elif emb == "celica":
            detalle += "; permite alcanzar objetivos lejanos con Warp"
        elif emb == "lyn":
            detalle += "; permite atacar a distancia extrema con Astra Storm"
        elif emb == "micaiah":
            detalle += "; cura al grupo con Great Sacrifice a cambio de los PV de la usuaria"
        return detalle
    if emb == "sigurd":
        clase = normalizar_texto(getattr(ficha, "clase_nombre", "") or getattr(getattr(ficha, "stats", None), "clase_nombre", ""))
        mov = "+7" if any(k in clase for k in ("caballero", "paladin", "jinete", "cavalier", "great knight")) else "+5"
        return f"usar la movilidad de Sigurd ({mov} Movimiento durante la Fusión) para alcanzar o replegarse tras atacar"
    if emb == "celica":
        return "usar Warp Ragnarok: teletransportarse hasta 10 casillas y atacar con el arma especial"
    if emb == "lyn":
        return "valorar Astra Storm para eliminar o debilitar a distancia sin exponer a la unidad"
    if emb == "micaiah":
        return "valorar Great Sacrifice si varias unidades necesitan curación y la posición es segura"
    return ""


def _ataques_engage_catalogo(nombre):
    """Devuelve (nombre, poder) de los ataques asociados al emblema.

    Los SID del datamine siguen el patrón GID/SID_<emblema>エンゲージ技;
    así se incorporan variantes por estilo sin mantener una tabla manual.
    """
    buscado = normalizar_texto(nombre)
    info = None
    for dato in (_catalogo.get("emblemas", {}) or {}).values():
        if normalizar_texto(dato.get("nombre", "")) == buscado or normalizar_texto(dato.get("ascii_name", "")) == buscado:
            info = dato
            break
    if not info:
        return []
    emblema_id = str(info.get("id", ""))
    token = emblema_id.removeprefix("GID_")
    encontrados = []
    for sid, skill in (_catalogo.get("habilidades", {}) or {}).items():
        sid_txt = str(sid)
        if token and token in sid_txt and "エンゲージ技" in sid_txt and "ブレイク" not in sid_txt:
            nombre_skill = skill.get("nombre", "")
            poder = int((skill.get("combat_mods") or {}).get("power", 0) or 0)
            if nombre_skill and (nombre_skill, poder) not in encontrados:
                encontrados.append((nombre_skill, poder))
    return encontrados


def _es_jefe(ficha):
    nombre = str(getattr(ficha, "nombre", "") or "").lower()
    return bool(getattr(getattr(ficha, "stats", None), "es_jefe", False)) or bool(getattr(ficha, "es_jefe", False)) or nombre.endswith("(boss)") or "hortensia" in nombre


def _barras_vida(ficha):
    """Barras que deben agotarse: HP normal más piedras resurrectoras."""
    return 1 + max(0, int(getattr(ficha, "hp_stock", 0) or 0))

def analizar_situacion_tactica(tablero, mapa, perfil="seguro", cronogema=False):
    """
    Análisis táctico determinista completo de la situación actual del tablero:
    1. Amenazas enemigas inminentes.
    2. Oportunidades de ataque del jugador con selección óptima de arma.
    3. Bastones de curación y pociones de supervivencia.
    4. Gestión de Emblema (Burst vs Conservar).
    """
    class _TerrenoAdapter:
        def __init__(self, t):
            self.caminable = t.caminable
            self.volable = t.volable
            self.coste = t.coste_mov

    grid_adapted = [
        [_TerrenoAdapter(mapa.grid[x][y])
         for y in range(mapa.alto)]
        for x in range(mapa.ancho)
    ]
    analizador = AnalizadorAmenaza(grid_adapted, mapa.ancho, mapa.alto)

    aliados_activos = [a for a in tablero.obtener_aliados() if a.stats and a.arma and a.viva and not a.ha_actuado]
    enemigos_activos = [e for e in tablero.obtener_enemigos() if e.stats and e.arma and e.viva]

    for a in aliados_activos:
        if a.stats:
            a.stats.hp = a.hp_actual
            a.stats.hp_max = a.hp_max
            setattr(a.stats, 'hp_actual', a.hp_actual)
    for e in enemigos_activos:
        if e.stats:
            e.stats.hp = e.hp_actual
            e.stats.hp_max = e.hp_max
            setattr(e.stats, 'hp_actual', e.hp_actual)

    # Precomputar casillas de movimiento una sola vez por bando
    enemigos_bloqueo = {(f.x, f.y) for f in enemigos_activos}

    casillas_mov_aliados = {}
    for a in aliados_activos:
        habs_aliado = [str(h).lower() for h in (getattr(a, 'habilidades', []) or [])]
        tiene_pass = any('pass' in h or 'traspasar' in h or 'すり抜け' in h for h in habs_aliado) or ('thief' in getattr(a, 'clase_nombre', '').lower())
        u_mock = UnidadMock(
            x=a.x,
            y=a.y,
            mov=a.mov,
            es_volador=a.es_volador,
            arma=ArmaMock(rango=[1])
        )
        setattr(u_mock, 'tiene_pass', tiene_pass)
        casillas_mov_aliados[a.nombre] = analizador.calcular_casillas_alcanzables(
            u_mock,
            casillas_bloqueadas=enemigos_bloqueo
        )

    casillas_mov_enemigos = {}
    zonas_amenaza_enemigos = {}
    ancho_m = mapa.ancho
    alto_m = mapa.alto
    for e in enemigos_activos:
        r_arma = e.arma.rango if (e.arma and e.arma.rango) else [1]
        u_mock = UnidadMock(
            x=e.x,
            y=e.y,
            mov=e.mov,
            es_volador=e.es_volador,
            arma=ArmaMock(rango=r_arma)
        )
        mov_e = analizador.calcular_casillas_alcanzables(u_mock)
        casillas_mov_enemigos[e.nombre] = mov_e

        # Precalcular zona de peligro de Engage (todas las casillas atacables por este enemigo)
        amenaza_e = set()
        for mx, my in mov_e:
            for dist in r_arma:
                for dx in range(-dist, dist + 1):
                    dy = dist - abs(dx)
                    for ax, ay in ((mx + dx, my + dy), (mx + dx, my - dy)):
                        if 0 <= ax < ancho_m and 0 <= ay < alto_m:
                            amenaza_e.add((ax, ay))
        zonas_amenaza_enemigos[e.nombre] = amenaza_e

    amenazas_inminentes = []
    oportunidades_jugador = []
    distancias_frente = []

    # ── 1. Evaluar amenazas enemigas sobre aliados ────────────────────────
    for enemigo in enemigos_activos:
        rango_max_enemigo = max(enemigo.arma.rango) if enemigo.arma.rango else 1
        alcance_enemigo = enemigo.mov + rango_max_enemigo

        for aliado in aliados_activos:
            dist = abs(aliado.x - enemigo.x) + abs(aliado.y - enemigo.y)
            distancias_frente.append((dist, enemigo, aliado))

            if dist <= alcance_enemigo + 1:
                try:
                    contexto = ContextoMapaEnemigo(
                        analizador=analizador,
                        ficha_enemigo=enemigo,
                        pos_jugador=(aliado.x, aliado.y),
                        ficha_jugador=aliado,
                    )
                    peor_caso = analizador.calcular_peor_caso_amenaza(
                        enemigo, (aliado.x, aliado.y), aliado,
                        casillas_movimiento_precalc=casillas_mov_enemigos.get(enemigo.nombre)
                    )

                    if peor_caso and (peor_caso.get("puede_atacar", False) or peor_caso.get("enemigo_alcanza", False)):
                        dist_combate = peor_caso.get("distancia_ataque", 1)
                        t_def = mapa.grid[aliado.x][aliado.y]
                        t_atk = mapa.grid[enemigo.x][enemigo.y]

                        apoyos_enemigos = obtener_aliados_backup(enemigo, aliado, tablero=tablero)
                        aliados_backup_stats = [e_sup.stats for e_sup in apoyos_enemigos]

                        veredicto = CalculadoraEngage.evaluar_riesgo(
                            atacante=enemigo.stats,
                            defensor=aliado.stats,
                            arma_atk=enemigo.arma,
                            arma_def=aliado.arma,
                            terreno_def=Terreno(avo=t_def.avo, dfn=t_def.dfn,
                                curacion_turno=getattr(t_def, 'curacion_turno', 0),
                                es_antirruptura=getattr(t_def, 'es_antirruptura', False),
                                es_recarga_emblema=getattr(t_def, 'es_recarga_emblema', False)),
                            terreno_atk=Terreno(avo=t_atk.avo, dfn=t_atk.dfn,
                                curacion_turno=getattr(t_atk, 'curacion_turno', 0),
                                es_antirruptura=getattr(t_atk, 'es_antirruptura', False),
                                es_recarga_emblema=getattr(t_atk, 'es_recarga_emblema', False)),
                            distancia=dist_combate,
                            perfil=perfil,
                            cronogema_usada=cronogema,
                            contexto_mapa=contexto,
                            defensor_en_ruptura=(getattr(aliado, 'cargas_ruptura', 0) > 0),
                            aliados_apoyo_backup=aliados_backup_stats,
                        )

                        mult_eff, desc_eff = CalculadoraEngage.calcular_efectividad(enemigo.arma, aliado.stats)
                        eff_tag = f" [{desc_eff}]" if desc_eff else ""
                        if enemigo.arma.es_magica and aliado.stats.tipo_movimiento == 'acorazado':
                            eff_tag += " [Magia penetra Armadura]"

                        verd = veredicto["veredicto"]
                        combate_e = veredicto.get("combate", {})
                        atk_e = combate_e.get("atacante", {})
                        res_e = combate_e.get("resultado", {})
                        hp_aliado_tras = res_e.get("hp_defensor_final", aliado.stats.hp)

                        chain_attacks_e = res_e.get("chain_attacks", [])
                        chain_e_txt = ""
                        if chain_attacks_e:
                            chain_parts_e = [
                                f"La unidad {ca['nombre']} puede realizar ataque en cadena contra {aliado.nombre} haciendo {ca['daño']} de daño (80% Hit)."
                                for ca in chain_attacks_e
                            ]
                            chain_e_txt = "Chain Attack enemigo: " + " ".join(chain_parts_e) + " Y luego el ataque del enemigo. "

                        jugador_contra = peor_caso.get("jugador_puede_contra", False)
                        if jugador_contra:
                            contra_tag = f" | {aliado.nombre} contraataca"
                        else:
                            r_ali = aliado.arma.rango if (aliado.arma and aliado.arma.rango) else [1]
                            contra_tag = f" | {aliado.nombre} no contraataca a dist. {dist_combate} (arma rango {r_ali})"

                        rec_texto = (
                            f"AMENAZA: {chain_e_txt}{enemigo.nombre} -> {aliado.nombre}{eff_tag} | "
                            f"Daño: {atk_e.get('daño_total_ronda', '?')} ({atk_e.get('golpes_en_ronda','?')}x{atk_e.get('daño_por_golpe','?')}) | "
                            f"Hit: {atk_e.get('precision','?')}% | "
                            f"{aliado.nombre} quedaría en {hp_aliado_tras}/{aliado.stats.hp} HP.{contra_tag} "
                        )
                        if verd.get("kill_seguro") or hp_aliado_tras <= 0:
                            rec_texto += f"LETAL — mueve a {aliado.nombre} fuera de alcance o interpón otra unidad."
                        elif hp_aliado_tras <= aliado.stats.hp * 0.3:
                            rec_texto += f"CRÍTICO — {aliado.nombre} quedaría muy débil. Considera retroceder o usar Rescatar."

                        amenazas_inminentes.append({
                            "tipo_analisis": "amenaza_enemiga",
                            "aliado": aliado.nombre,
                            "enemigo": enemigo.nombre,
                            "arma_recomendada": enemigo.arma.nombre if (enemigo.arma and hasattr(enemigo.arma, 'nombre')) else "",
                            "pos_sugerida": peor_caso.get("pos_optima") if peor_caso else None,
                            "distancia_combate": dist_combate,
                            "veredicto": verd,
                            "chain_attacks": chain_attacks_e,
                            "recomendacion": rec_texto,
                        })
                except Exception:
                    pass

    # ── 2. Evaluar oportunidades de ataque del jugador (multi-arma) ───────
    for aliado in aliados_activos:
        todas_armas = _armas_aliado(aliado)

        for enemigo in enemigos_activos:
            dist = abs(aliado.x - enemigo.x) + abs(aliado.y - enemigo.y)

            mejor_veredicto = None
            mejor_arma = None
            mejor_nota = ""
            mejor_pos = None
            mejor_score = -1

            for (arma_candidata, es_engage, nota_arma) in todas_armas:
                rango_max = max(arma_candidata.rango) if arma_candidata.rango else 1
                alcance = aliado.mov + rango_max
                if dist > alcance:
                    continue

                pos_candidata = encontrar_pos_ataque_optima(
                    aliado, enemigo, arma_candidata,
                    mapa=mapa, tablero=tablero, analizador=analizador,
                    casillas_alcanzables_precalc=casillas_mov_aliados.get(aliado.nombre),
                    zonas_amenaza_enemigos=zonas_amenaza_enemigos
                )
                if pos_candidata is None:
                    continue

                dist_combate = abs(pos_candidata[0] - enemigo.x) + abs(pos_candidata[1] - enemigo.y)
                if dist_combate not in (arma_candidata.rango or [1]):
                    continue

                is_tele = "ragnarok" in arma_candidata.nombre.lower()
                apoyos_aliados = obtener_aliados_backup(aliado, enemigo, tablero=tablero)
                aliados_backup_stats = [a_sup.stats for a_sup in apoyos_aliados]

                try:
                    t_def = mapa.grid[enemigo.x][enemigo.y]
                    t_atk = mapa.grid[pos_candidata[0]][pos_candidata[1]]

                    aliados_cercanos_atk = [
                        (a.stats, abs(a.x - pos_candidata[0]) + abs(a.y - pos_candidata[1]))
                        for a in tablero.obtener_aliados()
                        if a.viva and a.stats and a.nombre != aliado.nombre
                    ]
                    aliados_cercanos_def = [
                        (e_def.stats, abs(e_def.x - enemigo.x) + abs(e_def.y - enemigo.y))
                        for e_def in tablero.obtener_enemigos()
                        if e_def.viva and e_def.stats and e_def.nombre != enemigo.nombre
                    ]

                    v = CalculadoraEngage.evaluar_riesgo(
                        atacante=aliado.stats,
                        defensor=enemigo.stats,
                        arma_atk=arma_candidata,
                        arma_def=enemigo.arma,
                        terreno_def=Terreno(avo=t_def.avo, dfn=t_def.dfn,
                            curacion_turno=getattr(t_def, 'curacion_turno', 0),
                            es_antirruptura=getattr(t_def, 'es_antirruptura', False),
                            es_recarga_emblema=getattr(t_def, 'es_recarga_emblema', False)),
                        terreno_atk=Terreno(avo=t_atk.avo, dfn=t_atk.dfn,
                            curacion_turno=getattr(t_atk, 'curacion_turno', 0),
                            es_antirruptura=getattr(t_atk, 'es_antirruptura', False),
                            es_recarga_emblema=getattr(t_atk, 'es_recarga_emblema', False)),
                        distancia=dist_combate,
                        perfil=perfil,
                        cronogema_usada=cronogema,
                        defensor_en_ruptura=(getattr(enemigo, 'cargas_ruptura', 0) > 0),
                        aliados_apoyo_backup=aliados_backup_stats,
                        aliados_cercanos_atk=aliados_cercanos_atk,
                        aliados_cercanos_def=aliados_cercanos_def,
                        pos_atk=pos_candidata,
                        pos_def=(enemigo.x, enemigo.y),
                    )

                    verd = v["veredicto"]
                    combate_info = v.get("combate", {})
                    atk_info = combate_info.get("atacante", {})
                    res_info = combate_info.get("resultado", {})
                    dfn_info = combate_info.get("defensor", {})

                    daño_total = atk_info.get("daño_total_ronda", 0)
                    precision = atk_info.get("precision", 0)
                    hp_aliado_ini = aliado.stats.hp
                    hp_aliado_fin = res_info.get("hp_atacante_final", hp_aliado_ini)
                    daño_recibido = max(0, hp_aliado_ini - hp_aliado_fin)

                    kill_seguro = verd.get("kill_seguro", False)
                    kill_probable = verd.get("kill_probable", False)
                    kill_con_critico = verd.get("kill_con_critico", False)
                    atacante_muere = verd.get("atacante_muere_si_falla", False) or verd.get("atacante_muere_en_contra", False)
                    prob_muerte = verd.get("prob_muerte_atacante", 0)
                    ruptura = res_info.get("aplica_ruptura", False)
                    es_jefe_e = any(j in enemigo.nombre.lower() for j in ("hortensia", "nelucce", "marni", "zephia", "griss")) or bool(getattr(enemigo, 'es_jefe', False))

                    # ── Ratio Daño - Acierto - Supervivencia ──
                    if atacante_muere or prob_muerte >= 50:
                        if not kill_seguro:
                            score = -1000
                        else:
                            score = -500 if daño_recibido >= hp_aliado_ini else 200
                    elif daño_total == 0:
                        score = -1
                    elif kill_seguro:
                        if daño_recibido == 0:
                            # Clean Kill / OHKO: enemigo derrotado sin sufrir contragolpe
                            # (Prioridad absoluta sobre overkill innecesario que cause daño)
                            score = 1000 + precision + min(50, daño_total)
                        else:
                            # Kill seguro pero recibiendo contragolpe (penalizar cada punto de HP perdido)
                            score = 650 - (daño_recibido * 15) + (precision // 2)
                            if hp_aliado_fin <= 5:
                                score -= 150
                    elif kill_probable:
                        if daño_recibido == 0:
                            score = 450 + (precision * 2) - int(prob_muerte * 10)
                        else:
                            score = 350 - (daño_recibido * 15) + precision - int(prob_muerte * 15)
                            if atacante_muere:
                                score -= 200
                    elif kill_con_critico:
                        score = 180 - (daño_recibido * 10) + atk_info.get("prob_critico", 0)
                    else:
                        # Ataque sin kill (desgaste / chip damage)
                        daño_util = min(daño_total, enemigo.stats.hp)
                        if daño_recibido == 0:
                            # Golpe seguro a rango o aplicando Ruptura sin represalia
                            score = 120 + (daño_util * 2) + (precision // 2)
                            if ruptura:
                                score += 50
                        else:
                            score = 50 + daño_util - (daño_recibido * 12) + (precision // 4)
                            if daño_recibido >= hp_aliado_ini:
                                score = -1000

                    if es_jefe_e and score > 0:
                        score += 150
                    if is_tele and not kill_seguro:
                        score -= 150
                    if verd.get("nivel_riesgo") == "critico" and not kill_seguro:
                        score -= 200
                    elif verd.get("nivel_riesgo") == "alto" and not kill_seguro:
                        score -= 100

                    # Preferir casillas más seguras (con menos amenazas enemigas tras atacar)
                    pos_cand_tuple = (pos_candidata[0], pos_candidata[1])
                    amenazas_candidata = sum(
                        1 for e_nom, zona in zonas_amenaza_enemigos.items()
                        if e_nom != enemigo.nombre and pos_cand_tuple in zona
                    )
                    score -= (amenazas_candidata * 40 + max(0, amenazas_candidata - 2) * 120)

                    if score > mejor_score:
                        mejor_score = score
                        mejor_veredicto = v
                        mejor_arma = arma_candidata
                        mejor_nota = nota_arma
                        mejor_pos = pos_candidata

                except Exception:
                    continue

            if mejor_veredicto is None or mejor_score < 0:
                continue

            verd = mejor_veredicto["veredicto"]
            combate_final = mejor_veredicto.get("combate", {})
            atk_f = combate_final.get("atacante", {})
            res_f = combate_final.get("resultado", {})

            golpes = atk_f.get("golpes_en_ronda", 1)
            dpp = atk_f.get("daño_por_golpe", 0)
            dtotal = atk_f.get("daño_total_ronda", 0)
            precision = atk_f.get("precision", 0)
            hp_enemigo_ini = enemigo.stats.hp
            hp_enemigo_tras = res_f.get("hp_defensor_final", hp_enemigo_ini)
            follow_up = atk_f.get("tiene_follow_up", False)
            ruptura = res_f.get("aplica_ruptura", False)

            mult_eff, desc_eff = CalculadoraEngage.calcular_efectividad(mejor_arma, enemigo.stats)
            eff_tag = f" [{desc_eff}]" if desc_eff else ""
            if mejor_arma.es_magica and enemigo.stats.tipo_movimiento == 'acorazado':
                eff_tag += " [Magia penetra Armadura]"

            hp_atk_fin = res_f.get("hp_atacante_final", aliado.stats.hp)
            daño_recibido_final = max(0, aliado.stats.hp - hp_atk_fin)

            if verd.get("kill_seguro"):
                if daño_recibido_final == 0:
                    resultado_tag = f"CLEAN KILL ({precision}% hit · 0 daño recibido)"
                else:
                    resultado_tag = f"KILL SEGURO ({precision}% hit · recibe {daño_recibido_final} dmg)"
            elif verd.get("kill_probable"):
                if daño_recibido_final == 0:
                    resultado_tag = f"CLEAN KILL probable ({precision}% hit · 0 daño recibido)"
                else:
                    resultado_tag = f"Kill probable ({precision}% hit · recibe {daño_recibido_final} dmg)"
            elif verd.get("kill_con_critico"):
                resultado_tag = f"Solo mata con crítico ({atk_f.get('prob_critico',0)}%)"
            else:
                contra_txt = " · 0 daño recibido" if daño_recibido_final == 0 else f" · recibe {daño_recibido_final} dmg"
                resultado_tag = f"-> {enemigo.nombre} queda en {hp_enemigo_tras}/{hp_enemigo_ini} HP{contra_txt}"

            chain_attacks = res_f.get("chain_attacks", [])
            chain_dmg = sum(ca.get("daño", 0) for ca in chain_attacks)
            chain_txt = f" + {chain_dmg} (Chain Attack)" if chain_dmg > 0 else ""

            dano_arma_base = dpp * 2 if follow_up else dpp
            tiene_ds = atk_f.get("tiene_divine_speed", False)
            if follow_up and tiene_ds:
                dmg_ds = max(1, math.floor(dpp * 0.50))
                golpe_txt = f"2x{dpp} + {dmg_ds} (Velocidad Divina){chain_txt} = {dano_arma_base + dmg_ds + chain_dmg} dmg"
            elif follow_up:
                golpe_txt = f"2x{dpp}{chain_txt} = {dano_arma_base + chain_dmg} dmg" + (" (Follow-up)" if not chain_txt else "")
            elif tiene_ds:
                dmg_ds = max(1, math.floor(dpp * 0.50))
                golpe_txt = f"1x{dpp} + {dmg_ds} (Velocidad Divina){chain_txt} = {dpp + dmg_ds + chain_dmg} dmg"
            else:
                if chain_dmg > 0:
                    golpe_txt = f"1x{dpp} + {chain_dmg} (Chain Attack) = {dpp + chain_dmg} dmg"
                else:
                    golpe_txt = f"1x{dpp} = {dpp} dmg"

            nivel_riesgo = verd.get("nivel_riesgo", "bajo")
            riesgo_txt = ""
            if nivel_riesgo == "critico":
                riesgo_txt = f" | RIESGO CRÍTICO"
            elif nivel_riesgo == "alto":
                riesgo_txt = f" | Riesgo alto"
            elif nivel_riesgo == "moderado":
                riesgo_txt = f" | Riesgo moderado"

            bonus_txt = ""
            if ruptura:
                bonus_txt += " | Aplica Ruptura"
            if combate_info.get("atacante", {}).get("recoil_hp", 0) > 0:
                bonus_txt += " | Resonancia (-1 HP)"

            pasivas_list = res_f.get("pasivas_activas") or atk_f.get("pasivas_activas") or []
            if pasivas_list:
                pasivas_strs = [p if isinstance(p, str) else str(p.get("nombre", p)) for p in pasivas_list]
                bonus_txt += f" | Pasivas: {', '.join(pasivas_strs)}"
            apoyos_list = res_f.get("apoyos_activos") or atk_f.get("apoyos_activos") or []
            if apoyos_list:
                apoyos_strs = []
                for ap in apoyos_list:
                    if isinstance(ap, dict):
                        nom_a = ap.get("aliado", "Aliado")
                        r_a = ap.get("rango", "")
                        apoyos_strs.append(f"{nom_a} ({r_a})" if r_a else nom_a)
                    else:
                        apoyos_strs.append(str(ap))
                if apoyos_strs:
                    bonus_txt += f" | Apoyos: {', '.join(apoyos_strs)}"

            if mejor_nota:
                bonus_txt += f" | {mejor_nota}"

            pos_sug = mejor_pos if mejor_pos is not None else encontrar_pos_ataque_optima(
                aliado, enemigo, mejor_arma,
                mapa=mapa, tablero=tablero, analizador=analizador,
                casillas_alcanzables_precalc=casillas_mov_aliados.get(aliado.nombre),
                zonas_amenaza_enemigos=zonas_amenaza_enemigos
            )
            if pos_sug is None:
                continue

            # Evaluación de exposición a peligro enemigo en la casilla de destino
            amenazas_en_destino = []
            if zonas_amenaza_enemigos:
                for e_nom, zona in zonas_amenaza_enemigos.items():
                    if e_nom == enemigo.nombre and verd.get("kill_seguro"):
                        continue
                    if (pos_sug[0], pos_sug[1]) in zona:
                        amenazas_en_destino.append(e_nom)

            canter = calcular_retirada_canter(
                aliado, pos_sug, mapa, tablero, zonas_amenaza_enemigos,
                objetivo_nombre=enemigo.nombre,
                objetivo_derrotado=verd.get("kill_seguro", False),
                analizador=analizador,
            )
            pos_canter = canter["pos_canter"] if canter else None
            if canter:
                bonus_txt += (
                    f" | Canter: tras atacar, replegar a ({pos_canter[0]},{pos_canter[1]}) "
                    f"({canter['amenazas_ataque']}->{canter['amenazas_final']} amenazas)"
                )

            # Prioridad Maddening: evitar ataques suicidas.
            # Se evalúa el HP restante real del aliado tras el combate (hp_atk_fin)
            # contra el daño acumulado de todos los enemigos que alcanzan la casilla final.
            amenazas_finales = canter.get("amenazas_final", len(amenazas_en_destino)) if canter else len(amenazas_en_destino)
            if amenazas_finales >= 4:
                continue

            hp_restante = hp_atk_fin
            dano_acumulado_amenazas = 0
            amenaza_letal = False
            casilla_evaluar = tuple(pos_canter) if pos_canter else tuple(pos_sug)

            enemigos_amenazantes = []
            if zonas_amenaza_enemigos:
                for e_nom, zona in zonas_amenaza_enemigos.items():
                    if e_nom == enemigo.nombre and verd.get("kill_seguro"):
                        continue
                    if casilla_evaluar in zona:
                        enemigos_amenazantes.append(e_nom)

            for e_nom in enemigos_amenazantes:
                e_ficha = tablero.obtener_ficha(e_nom)
                if not e_ficha or not e_ficha.viva:
                    continue
                try:
                    peor_pos = analizador.calcular_peor_caso_amenaza(
                        e_ficha, casilla_evaluar, aliado,
                        casillas_movimiento_precalc=casillas_mov_enemigos.get(e_nom)
                    )
                    if peor_pos and (peor_pos.get("puede_atacar") or peor_pos.get("enemigo_alcanza")):
                        dano_amenaza = int(peor_pos.get("daño_proyectado", 0) or 0)
                        dano_acumulado_amenazas += dano_amenaza
                        if dano_acumulado_amenazas >= hp_restante:
                            amenaza_letal = True
                            break
                except Exception:
                    continue
            if amenaza_letal:
                continue

            if len(amenazas_en_destino) == 0:
                expo_txt = " | Casilla segura (0 amenazas enemigas)"
            elif len(amenazas_en_destino) == 1:
                expo_txt = f" | Al alcance de 1 enemigo ({amenazas_en_destino[0]})"
            else:
                nombres_e = ", ".join(amenazas_en_destino[:2])
                expo_txt = f" | Al alcance de {len(amenazas_en_destino)} enemigos ({nombres_e})"

            pos_txt = f"Mover a ({pos_sug[0]},{pos_sug[1]}) · " if (pos_sug[0] != aliado.x or pos_sug[1] != aliado.y) else "En rango directo · "

            rec_texto = (
                f"{aliado.nombre} -> usa {mejor_arma.nombre}{eff_tag} contra {enemigo.nombre} | "
                f"{pos_txt}{golpe_txt} | Hit {precision}% | {resultado_tag}{riesgo_txt}{bonus_txt}"
            )

            oportunidades_jugador.append({
                "tipo_analisis": "oportunidad_jugador",
                "aliado": aliado.nombre,
                "enemigo": enemigo.nombre,
                "distancia_combate": abs(pos_sug[0] - enemigo.x) + abs(pos_sug[1] - enemigo.y),
                "arma_recomendada": mejor_arma.nombre,
                "pos_sugerida": pos_sug,
                "pos_canter": pos_canter,
                "veredicto": verd,
                "chain_attacks": chain_attacks,
                "dano_total": dtotal,
                "pasivas_activas": pasivas_list,
                "apoyos_activos": apoyos_list,
                "score_tactico": mejor_score,
                "daño_recibido": daño_recibido_final,
                "amenazas_en_destino": amenazas_en_destino,
                "num_amenazas_destino": len(amenazas_en_destino),
                "recomendacion": rec_texto,
            })

    # ── 3. Evaluar Bastones de Curación y Pociones de Supervivencia ──────
    acciones_soporte = []
    aliados_todos = tablero.obtener_aliados()
    heridos = [a for a in aliados_todos if a.viva and a.stats and a.stats.hp < getattr(a.stats, 'hp_max', a.stats.hp)]

    # 3a. Bastones (Heal, Mend, Physic, etc.)
    for sanador in aliados_activos:
        bastones = []
        for it in (sanador.inventario or []):
            nom_it = (it.get("nombre") or "").lower()
            tipo_it = it.get("tipo", "")
            if tipo_it == "Bastón" or any(b in nom_it for b in ("curar", "heal", "sanar", "mend", "physic", "recuperar")):
                bastones.append(it)

        if not bastones or not heridos:
            continue

        for obj in heridos:
            if obj.nombre == sanador.nombre:
                continue
            hp_max_obj = getattr(obj.stats, 'hp_max', obj.stats.hp)
            deficit = hp_max_obj - obj.stats.hp
            if deficit <= 0:
                continue

            for baston in bastones:
                nom_b = baston.get("nombre", "Bastón de Curar")
                es_physic = "physic" in nom_b.lower() or "fortalecer" in nom_b.lower()
                rango_baston = range(1, max(2, getattr(sanador.stats, 'magia', 10) // 2 + 1)) if es_physic else [1]

                pos_sanacion = None
                dist_actual = abs(sanador.x - obj.x) + abs(sanador.y - obj.y)
                if dist_actual in rango_baston:
                    pos_sanacion = [sanador.x, sanador.y]
                else:
                    for dx, dy in ((0,1), (0,-1), (1,0), (-1,0)):
                        cx, cy = obj.x + dx, obj.y + dy
                        if 0 <= cx < mapa.ancho and 0 <= cy < mapa.alto:
                            if any(f.viva and f.nombre != sanador.nombre and f.x == cx and f.y == cy for f in tablero.fichas.values()):
                                continue
                            t = mapa.grid[cx][cy]
                            if t.caminable and (abs(cx - sanador.x) + abs(cy - sanador.y) <= sanador.mov):
                                pos_sanacion = [cx, cy]
                                break

                if pos_sanacion is not None:
                    base_cur = 20 if "sanar" in nom_b.lower() or "mend" in nom_b.lower() else 10
                    curacion = base_cur + max(0, getattr(sanador.stats, 'magia', 0) // 3)
                    curacion = min(deficit, curacion)

                    pos_txt = f"Mover a ({pos_sanacion[0]},{pos_sanacion[1]}) · " if pos_sanacion != [sanador.x, sanador.y] else "En rango directo · "
                    urgencia = "URGENTE" if obj.stats.hp <= hp_max_obj * 0.35 else ("RECOMENDADO" if obj.stats.hp <= hp_max_obj * 0.65 else "PREVENTIVO")

                    acciones_soporte.append({
                        "tipo_analisis": "apoyo_curacion",
                        "aliado": sanador.nombre,
                        "objetivo": obj.nombre,
                        "baston": nom_b,
                        "curacion_estimada": curacion,
                        "pos_sugerida": pos_sanacion,
                        "prioridad": 350 if "URGENTE" in urgencia else 150,
                        "recomendacion": (
                            f"APOYO ({urgencia}): {sanador.nombre} -> usar {nom_b} en {obj.nombre} | "
                            f"{pos_txt}Recupera +{curacion} HP ({obj.nombre} pasa a {obj.stats.hp + curacion}/{hp_max_obj} HP)."
                        )
                    })

    # 3b. Pociones y Vulnerarios
    for aliado in aliados_activos:
        hp_max_ali = getattr(aliado.stats, 'hp_max', aliado.stats.hp)
        if aliado.stats.hp <= hp_max_ali * 0.60:
            pocion = None
            for it in (aliado.inventario or []):
                nom_p = (it.get("nombre") or "").lower()
                if any(p in nom_p for p in ("pocion", "poción", "vulnerary", "elixir", "brebaje")):
                    pocion = it
                    break
            if pocion:
                cur_pocion = 15 if "elixir" in pocion.get("nombre", "").lower() else 10
                urgente = aliado.stats.hp <= hp_max_ali * 0.35
                acciones_soporte.append({
                    "tipo_analisis": "uso_pocion",
                    "aliado": aliado.nombre,
                    "item": pocion.get("nombre"),
                    "pos_sugerida": [aliado.x, aliado.y],
                    "prioridad": 400 if urgente else 160,
                    "recomendacion": (
                        f"SUPERVIVENCIA ({'CRÍTICO' if urgente else 'AVISO'}): {aliado.nombre} debe usar {pocion.get('nombre')} "
                        f"(+{cur_pocion} HP) para evitar caer ante contragolpe o fase enemiga."
                    )
                })

    # 3c. Táctica de Emblema (Burst con Fusión vs Conservar para Jefe)
    # Daño agregado necesario para vaciar todas las barras del jefe.
    dano_jefe_por_nombre = {}
    for op in oportunidades_jugador:
        ficha_obj = tablero.obtener_ficha(op.get("enemigo"))
        if not ficha_obj or not _es_jefe(ficha_obj):
            continue
        dano = max(0, int(op.get("dano_total", 0) or op.get("veredicto", {}).get("combate", {}).get("atacante", {}).get("daño_total_ronda", 0) or 0))
        if ficha_obj.nombre not in dano_jefe_por_nombre:
            dano_jefe_por_nombre[ficha_obj.nombre] = {}
        prev_dano = dano_jefe_por_nombre[ficha_obj.nombre].get(op.get("aliado"), 0)
        dano_jefe_por_nombre[ficha_obj.nombre][op.get("aliado")] = max(prev_dano, dano)
    jefes_derrotables = set()
    for nombre_jefe, por_aliado in dano_jefe_por_nombre.items():
        ficha_jefe = tablero.obtener_ficha(nombre_jefe)
        hp_barra = int(getattr(ficha_jefe, "hp_max", 0) or getattr(ficha_jefe.stats, "hp", 0) or 0)
        hp_actual = int(getattr(ficha_jefe, "hp_actual", hp_barra) or hp_barra)
        hp_total_restante = hp_actual + max(0, _barras_vida(ficha_jefe) - 1) * hp_barra
        if hp_barra > 0 and sum(por_aliado.values()) >= hp_total_restante:
            jefes_derrotables.add(nombre_jefe)

    for op in oportunidades_jugador:
        aliado_nom = op.get("aliado")
        enemigo_nom = op.get("enemigo")
        ficha_ali = tablero.obtener_ficha(aliado_nom)
        ficha_ene = tablero.obtener_ficha(enemigo_nom)
        if not ficha_ali or not ficha_ene:
            continue

        es_jefe = _es_jefe(ficha_ene)
        emblema = _emblema_equipado(ficha_ali)
        esta_fusion = bool(getattr(ficha_ali, 'en_fusion', False) or getattr(ficha_ali.stats, 'en_fusion', False))
        atk_usado = bool(getattr(ficha_ali, 'ataque_emblema_usado', False) or (ficha_ali.stats and getattr(ficha_ali.stats, 'ataque_emblema_usado', False)))
        turnos_rest = int(getattr(ficha_ali, 'turnos_fusion', getattr(ficha_ali.stats, 'turnos_fusion_restantes', 0) if ficha_ali.stats else 0) or 0)
        energia = int(getattr(ficha_ali, 'energia_emblema', getattr(ficha_ali.stats, 'energia_emblema', 0) if ficha_ali.stats else 0) or 0)
        energia_max = int(getattr(ficha_ali, 'max_energia_emblema', getattr(ficha_ali.stats, 'max_energia_emblema', 0) if ficha_ali.stats else 0) or 0)
        tiene_emblema_listo = bool(emblema) and (esta_fusion or (energia_max > 0 and energia >= energia_max))
        kill_seguro = op.get("veredicto", {}).get("kill_seguro", False)

        # Considerar fusiones y habilidades de emblema solo para el flujo del combate cuando sea necesario y viable:
        if tiene_emblema_listo:
            if es_jefe:
                op["tactica_emblema"] = "burst"
                acciones = _detalle_acciones_emblema(emblema)
                if not acciones and normalizar_texto(emblema) in {"edelgard", "three houses", "tres casas"}:
                    lider = getattr(ficha_ali, "lider_tres_casas", getattr(ficha_ali.stats, "lider_tres_casas", "Dimitri"))
                    acciones = [f"Houses Unite y el arte de combate de {lider}"]
                accion_txt = ", ".join(acciones[:2]) if acciones else "técnica especial de Engage"
                if esta_fusion:
                    if atk_usado:
                        op["recomendacion"] += f" | FUSION ACTIVA ({turnos_rest}t restantes): Técnica especial ya usada en esta fusión."
                    else:
                        op["recomendacion"] += f" | FUSION ACTIVA ({turnos_rest}t restantes): Usar {accion_txt} para daño masivo contra el jefe."
                else:
                    op["recomendacion"] += f" | FUSION RECOMENDADA: Activar Fusión con {emblema} ({accion_txt}) para derrotar al jefe."
            elif esta_fusion:
                op["tactica_emblema"] = "en_fusion"
            elif not kill_seguro and op.get("veredicto", {}).get("nivel_riesgo") in {"alto", "critico"}:
                op["tactica_emblema"] = "necesario"
                op["recomendacion"] += f" | OPCION: Si necesitas asegurar la baja o sobrevivir, considera activar Fusión con {emblema}."

    # ── 4. Filtrar y Priorizar Recomendaciones para Reducir Sobrecarga ──────
    # Agrupar oportunidades de ataque por aliado: 1 mejor acción decisiva por aliado
    oportunidades_por_aliado = {}
    for op in oportunidades_jugador:
        score_op = op.get("score_tactico", 0)
        if score_op <= 0:
            continue
        nom_a = op["aliado"]
        if nom_a not in oportunidades_por_aliado:
            oportunidades_por_aliado[nom_a] = []
        oportunidades_por_aliado[nom_a].append(op)

    oportunidades_filtradas = []
    for nom_a, ops in oportunidades_por_aliado.items():
        # Ordenar las opciones del aliado de mayor a menor score táctico
        ops.sort(key=lambda x: x.get("score_tactico", 0), reverse=True)
        # Seleccionar la mejor acción disponible para ese aliado
        oportunidades_filtradas.append(ops[0])

    # Ordenar globalmente todas las mejores opciones por impacto táctico
    oportunidades_filtradas.sort(key=lambda x: x.get("score_tactico", 0), reverse=True)

    # Limitar a las mejores oportunidades (máximo 8) para mantener el panel enfocado y determinista
    jefes_vivos = [e for e in tablero.obtener_enemigos() if e.viva and e.stats and _es_jefe(e)]
    oportunidades_jefe = [o for o in oportunidades_filtradas if _es_jefe(tablero.obtener_ficha(o.get("enemigo"))) and o.get("enemigo") in jefes_derrotables]
    objetivo_avance = []
    if jefes_vivos and oportunidades_jefe:
        jefe = min(jefes_vivos, key=lambda e: min((abs(a.x - e.x) + abs(a.y - e.y) for a in aliados_activos), default=999))
        for op in oportunidades_jefe:
            op["objetivo_victoria"] = True
            ficha_jefe = tablero.obtener_ficha(op.get("enemigo"))
            op["barras_vida_objetivo"] = _barras_vida(ficha_jefe)
            op["recomendacion"] = f"OBJETIVO: derrotar a {jefe.nombre} ({_barras_vida(ficha_jefe)} barras). " + op["recomendacion"]
        aliados_jefe = {o.get("aliado") for o in oportunidades_jefe}
        resto_ops = [o for o in oportunidades_filtradas if o.get("aliado") not in aliados_jefe]
        top_oportunidades = (oportunidades_jefe + resto_ops)[:8]
    else:
        top_oportunidades = oportunidades_filtradas[:8]

    soporte_urgente = [s for s in acciones_soporte if s.get("prioridad", 0) >= 300]
    soporte_normal = [s for s in acciones_soporte if s.get("prioridad", 0) < 300]
    # No incluir alertas invasivas de peligro enemigo en el panel; mantenerlo limpio y enfocado a acciones aliadas
    resultados = soporte_urgente + objetivo_avance + top_oportunidades + (soporte_normal[:2] if len(top_oportunidades) < 8 else [])

    # Fallback: zona segura
    if not resultados and distancias_frente:
        distancias_frente.sort(key=lambda x: x[0])
        dist_min, e_cercano, a_cercano = distancias_frente[0]
        alcance_e = e_cercano.mov + (max(e_cercano.arma.rango) if e_cercano.arma else 1)
        col_segura = e_cercano.x - alcance_e - 1

        resultados.append({
            "tipo_analisis": "vanguardia_segura",
            "aliado": a_cercano.nombre,
            "enemigo": e_cercano.nombre,
            "distancia_combate": dist_min,
            "veredicto": {
                "nivel_riesgo": "bajo",
                "motivos": [
                    f"Frente seguro: ningún enemigo alcanza este turno (distancia mínima: {dist_min} casillas).",
                    f"Enemigo más próximo: {e_cercano.nombre} en ({e_cercano.x}, {e_cercano.y}), alcance {alcance_e} casillas.",
                ]
            },
            "recomendacion": (
                f"ZONA SEGURA: Puedes avanzar. No te expongas más allá de la columna X={max(0, col_segura)} "
                f"para no entrar en rango de {e_cercano.nombre} este turno."
            )
        })

    return {"turno": tablero.turno_actual, "total_analizados": len(resultados), "resultados": resultados}
