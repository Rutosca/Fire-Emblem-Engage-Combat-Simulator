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
from catalogo_loader import _arma_desde_item

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

def encontrar_refugio_canter(aliado, pos_ataque, enemigo_derrotado, enemigo_nombre,
                             mapa, tablero, zonas_amenaza_enemigos=None, rango_canter=2):
    """
    Para una unidad con Canter que ataca desde pos_ataque, busca una casilla
    de repliegue/refugio (distancia Manhattan <= rango_canter) que minimice las
    amenazas enemigas (idealmente 0 amenazas), alejándose del enemigo y refugiándose en
    terreno defensivo o hacia la retaguardia de aliados.
    Retorna (rx, ry) o None si la mejor casilla es la misma pos_ataque.
    """
    ax, ay = pos_ataque
    ocupadas = {(f.x, f.y) for f in tablero.fichas.values() if f.viva and f.nombre != aliado.nombre}
    ancho = getattr(mapa, "ancho", 24)
    alto = getattr(mapa, "alto", 17)
    es_vol = getattr(aliado, "es_volador", False) or getattr(getattr(aliado, "stats", None), "es_volador", False)

    # Posición del enemigo objetivo (para maximizar distancia en la retirada)
    f_ene = tablero.obtener_ficha(enemigo_nombre) if (enemigo_nombre and hasattr(tablero, "obtener_ficha")) else None
    if f_ene is None and hasattr(tablero, "fichas"):
        f_ene = tablero.fichas.get(enemigo_nombre)
    ex, ey = (f_ene.x, f_ene.y) if f_ene else (ax, ay)

    # Evaluar amenazas en la casilla de ataque actual
    amenazas_actual = 0
    if zonas_amenaza_enemigos:
        for e_nom, zona in zonas_amenaza_enemigos.items():
            if e_nom == enemigo_nombre and enemigo_derrotado:
                continue
            if (ax, ay) in zona:
                amenazas_actual += 1

    t_actual = mapa.grid[ax][ay]
    dist_ene_act = abs(ax - ex) + abs(ay - ey)
    mejor_score = (-amenazas_actual * 1000) + (dist_ene_act * 50) + (getattr(t_actual, 'avo', 0) + getattr(t_actual, 'dfn', 0) * 2) - (ax * 2)
    mejor_pos = (ax, ay)

    for dx in range(-rango_canter, rango_canter + 1):
        for dy in range(-rango_canter, rango_canter + 1):
            dist = abs(dx) + abs(dy)
            if dist == 0 or dist > rango_canter:
                continue
            cx, cy = ax + dx, ay + dy
            if not (0 <= cx < ancho and 0 <= cy < alto):
                continue
            if (cx, cy) in ocupadas:
                continue

            # Transitabilidad del terreno
            t = mapa.grid[cx][cy]
            volable = getattr(t, 'volable', True)
            caminable = getattr(t, 'caminable', True)
            if es_vol and not volable:
                continue
            if not es_vol and not caminable:
                continue

            amenazas = 0
            if zonas_amenaza_enemigos:
                for e_nom, zona in zonas_amenaza_enemigos.items():
                    if e_nom == enemigo_nombre and enemigo_derrotado:
                        continue
                    if (cx, cy) in zona:
                        amenazas += 1

            dist_ene = abs(cx - ex) + abs(cy - ey)
            score_candidata = (-amenazas * 1000) + (dist_ene * 50) + (getattr(t, 'avo', 0) + getattr(t, 'dfn', 0) * 2) - (cx * 2)

            if score_candidata > mejor_score:
                mejor_score = score_candidata
                mejor_pos = (cx, cy)

    if mejor_pos != (ax, ay):
        return mejor_pos
    return None

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
                nota = "⚠️ TeleRagnarok: expone al aliado (solo si kill seguro)"
            elif es_engage:
                nota = "⚡ Arma de Engage"
            armas.append((a, es_engage, nota))

    if not armas and aliado.arma:
        armas.append((aliado.arma, False, ""))

    return armas

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
                        eff_tag = f" [✨ {desc_eff}]" if desc_eff else ""
                        if enemigo.arma.es_magica and aliado.stats.tipo_movimiento == 'acorazado':
                            eff_tag += " [✨ Magia penetra Armadura]"

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
                            chain_e_txt = "⚔️ Chain Attack enemigo: " + " ".join(chain_parts_e) + " Y luego el ataque del enemigo. "

                        jugador_contra = peor_caso.get("jugador_puede_contra", False)
                        if jugador_contra:
                            contra_tag = f" | ⚔️ {aliado.nombre} contraataca"
                        else:
                            r_ali = aliado.arma.rango if (aliado.arma and aliado.arma.rango) else [1]
                            contra_tag = f" | ⚠️ {aliado.nombre} no contraataca a dist. {dist_combate} (arma rango {r_ali})"

                        rec_texto = (
                            f"⚠️ AMENAZA: {chain_e_txt}{enemigo.nombre} → {aliado.nombre}{eff_tag} | "
                            f"Daño: {atk_e.get('daño_total_ronda', '?')} ({atk_e.get('golpes_en_ronda','?')}x{atk_e.get('daño_por_golpe','?')}) | "
                            f"Hit: {atk_e.get('precision','?')}% | "
                            f"{aliado.nombre} quedaría en {hp_aliado_tras}/{aliado.stats.hp} HP.{contra_tag} "
                        )
                        if verd.get("kill_seguro") or hp_aliado_tras <= 0:
                            rec_texto += f"💀 LETAL — mueve a {aliado.nombre} fuera de alcance o interpón otra unidad."
                        elif hp_aliado_tras <= aliado.stats.hp * 0.3:
                            rec_texto += f"🔴 CRÍTICO — {aliado.nombre} quedaría muy débil. Considera retroceder o usar Rescatar."

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
            eff_tag = f" [✨ {desc_eff}]" if desc_eff else ""
            if mejor_arma.es_magica and enemigo.stats.tipo_movimiento == 'acorazado':
                eff_tag += " [✨ Magia penetra Armadura]"

            hp_atk_fin = res_f.get("hp_atacante_final", aliado.stats.hp)
            daño_recibido_final = max(0, aliado.stats.hp - hp_atk_fin)

            if verd.get("kill_seguro"):
                if daño_recibido_final == 0:
                    resultado_tag = f"✅ CLEAN KILL ({precision}% hit · 0 daño recibido)"
                else:
                    resultado_tag = f"✅ KILL SEGURO ({precision}% hit · recibe {daño_recibido_final} dmg)"
            elif verd.get("kill_probable"):
                if daño_recibido_final == 0:
                    resultado_tag = f"🎯 CLEAN KILL probable ({precision}% hit · 0 daño recibido)"
                else:
                    resultado_tag = f"🎯 Kill probable ({precision}% hit · recibe {daño_recibido_final} dmg)"
            elif verd.get("kill_con_critico"):
                resultado_tag = f"⚡ Solo mata con crítico ({atk_f.get('prob_critico',0)}%)"
            else:
                contra_txt = " · 0 daño recibido" if daño_recibido_final == 0 else f" · recibe {daño_recibido_final} dmg"
                resultado_tag = f"→ {enemigo.nombre} queda en {hp_enemigo_tras}/{hp_enemigo_ini} HP{contra_txt}"

            tiene_ds = atk_f.get("tiene_divine_speed", False)
            if follow_up and tiene_ds:
                dmg_ds = max(1, math.floor(dpp * 0.50))
                golpe_txt = f"2x{dpp} + {dmg_ds} (Velocidad Divina) = {dpp * 2 + dmg_ds} dmg"
            elif follow_up:
                golpe_txt = f"2x{dpp} = {dpp * 2} dmg (Follow-up)"
            elif tiene_ds:
                dmg_ds = max(1, math.floor(dpp * 0.50))
                golpe_txt = f"1x{dpp} + {dmg_ds} (Velocidad Divina) = {dpp + dmg_ds} dmg"
            else:
                golpe_txt = f"1x{dpp} = {dpp} dmg"

            nivel_riesgo = verd.get("nivel_riesgo", "bajo")
            riesgo_txt = ""
            if nivel_riesgo == "critico":
                riesgo_txt = f" | 🔴 RIESGO CRÍTICO"
            elif nivel_riesgo == "alto":
                riesgo_txt = f" | 🟠 Riesgo alto"
            elif nivel_riesgo == "moderado":
                riesgo_txt = f" | 🟡 Riesgo moderado"

            bonus_txt = ""
            if ruptura:
                bonus_txt += " | 💥 Aplica Ruptura"
            if combate_info.get("resultado", {}).get("chain_attacks_daño", 0) > 0:
                cdmg = combate_info["resultado"]["chain_attacks_daño"]
                bonus_txt += f" | ⚔️ Chain Attack (+{cdmg} dmg)"
            if combate_info.get("atacante", {}).get("recoil_hp", 0) > 0:
                bonus_txt += " | 🩸 Resonancia (-1 HP)"
            if combate_info.get("atacante", {}).get("puede_canter", False):
                bonus_txt += " | 🏃 Canter (mueve 2 tras atacar)"

            pasivas_list = res_f.get("pasivas_activas") or atk_f.get("pasivas_activas") or []
            if pasivas_list:
                pasivas_strs = [p if isinstance(p, str) else str(p.get("nombre", p)) for p in pasivas_list]
                bonus_txt += f" | 🌟 {', '.join(pasivas_strs)}"
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
                    bonus_txt += f" | 🤝 Apoyos: {', '.join(apoyos_strs)}"

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

            if len(amenazas_en_destino) == 0:
                expo_txt = " | 🛡️ Casilla segura (0 amenazas enemigas)"
            elif len(amenazas_en_destino) == 1:
                expo_txt = f" | ⚠️ Al alcance de 1 enemigo ({amenazas_en_destino[0]})"
            else:
                nombres_e = ", ".join(amenazas_en_destino[:2])
                expo_txt = f" | 🔴 Al alcance de {len(amenazas_en_destino)} enemigos ({nombres_e})"

            bonus_txt += expo_txt

            pos_txt = f"📍 Mover a ({pos_sug[0]},{pos_sug[1]}) · " if (pos_sug[0] != aliado.x or pos_sug[1] != aliado.y) else "📍 En rango directo · "

            pos_canter = None
            tiene_canter = (
                combate_info.get("atacante", {}).get("puede_canter", False)
                or any('canter' in str(h).lower() or '再移動' in str(h) for h in (getattr(aliado.stats, 'habilidades', []) or []))
                or 'sigurd' in (getattr(aliado, 'emblema_nombre', '') or '').lower()
                or 'sigurd' in (getattr(aliado.stats, 'emblema_nombre', '') or '').lower()
            )
            if tiene_canter and daño_recibido_final < aliado.stats.hp:
                pos_canter = encontrar_refugio_canter(
                    aliado, pos_sug,
                    enemigo_derrotado=verd.get("kill_seguro", False),
                    enemigo_nombre=enemigo.nombre,
                    mapa=mapa, tablero=tablero,
                    zonas_amenaza_enemigos=zonas_amenaza_enemigos
                )

            canter_txt = f" | 🏃 Canter → Refugio en ({pos_canter[0]},{pos_canter[1]})" if pos_canter else ""

            # Texto conciso y directo para la tarjeta: los apoyos, chain attacks y zona de peligro
            # ya se renderizan de forma clara y visual en sus propias insignias superiores.
            rec_texto = (
                f"🎯 {aliado.nombre} → usa {mejor_arma.nombre}{eff_tag} contra {enemigo.nombre} | "
                f"{pos_txt}{golpe_txt} | Hit {precision}% | {resultado_tag}{canter_txt}"
            )

            chain_attacks = res_f.get("chain_attacks", [])

            oportunidades_jugador.append({
                "tipo_analisis": "oportunidad_jugador",
                "aliado": aliado.nombre,
                "enemigo": enemigo.nombre,
                "distancia_combate": abs(pos_sug[0] - enemigo.x) + abs(pos_sug[1] - enemigo.y),
                "arma_recomendada": mejor_arma.nombre,
                "pos_sugerida": pos_sug,
                "pos_canter": list(pos_canter) if pos_canter else None,
                "veredicto": verd,
                "chain_attacks": chain_attacks,
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

                    pos_txt = f"📍 Mover a ({pos_sanacion[0]},{pos_sanacion[1]}) · " if pos_sanacion != [sanador.x, sanador.y] else "📍 En rango directo · "
                    urgencia = "🔴 URGENTE" if obj.stats.hp <= hp_max_obj * 0.35 else ("🟡 RECOMENDADO" if obj.stats.hp <= hp_max_obj * 0.65 else "🟢 PREVENTIVO")

                    acciones_soporte.append({
                        "tipo_analisis": "apoyo_curacion",
                        "aliado": sanador.nombre,
                        "objetivo": obj.nombre,
                        "baston": nom_b,
                        "curacion_estimada": curacion,
                        "pos_sugerida": pos_sanacion,
                        "prioridad": 350 if "URGENTE" in urgencia else 150,
                        "recomendacion": (
                            f"🩹 APOYO ({urgencia}): {sanador.nombre} → usar {nom_b} en {obj.nombre} | "
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
                        f"🧪 SUPERVIVENCIA ({'🔴 CRÍTICO' if urgente else '🟡 AVISO'}): {aliado.nombre} debe usar {pocion.get('nombre')} "
                        f"(+{cur_pocion} HP) para evitar caer ante contragolpe o fase enemiga."
                    )
                })

    # 3c. Táctica de Emblema (Burst con Fusión vs Conservar para Jefe)
    for op in oportunidades_jugador:
        aliado_nom = op.get("aliado")
        enemigo_nom = op.get("enemigo")
        ficha_ali = tablero.obtener_ficha(aliado_nom)
        ficha_ene = tablero.obtener_ficha(enemigo_nom)
        if not ficha_ali or not ficha_ene:
            continue

        es_jefe = any(j in ficha_ene.nombre.lower() for j in ("hortensia", "nelucce", "marni", "zephia", "griss")) or bool(getattr(ficha_ene, 'es_jefe', False)) or bool(getattr(ficha_ene.stats, 'es_jefe', False))
        tiene_emblema_listo = ficha_ali.energia_emblema >= ficha_ali.max_energia_emblema or ficha_ali.en_fusion

        emb_nom_ali = (getattr(ficha_ali, 'emblema_nombre', '') or '').lower()
        es_emblema_soporte = any(u in emb_nom_ali for u in ('micaiah', 'byleth', 'ベレト', 'ミカヤ'))

        if es_jefe and tiene_emblema_listo and not es_emblema_soporte:
            op["tactica_emblema"] = "burst"
        elif not es_jefe and tiene_emblema_listo and op.get("veredicto", {}).get("kill_seguro"):
            op["tactica_emblema"] = "conservar"

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
    top_oportunidades = oportunidades_filtradas[:8]

    soporte_urgente = [s for s in acciones_soporte if s.get("prioridad", 0) >= 300]
    soporte_normal = [s for s in acciones_soporte if s.get("prioridad", 0) < 300]
    # No incluir alertas invasivas de peligro enemigo en el panel; mantenerlo limpio y enfocado a acciones aliadas
    resultados = soporte_urgente + top_oportunidades + (soporte_normal[:2] if len(top_oportunidades) < 8 else [])

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
                f"🛡️ ZONA SEGURA: Puedes avanzar. No te expongas más allá de la columna X={max(0, col_segura)} "
                f"para no entrar en rango de {e_cercano.nombre} este turno."
            )
        })

    return {"turno": tablero.turno_actual, "total_analizados": len(resultados), "resultados": resultados}
