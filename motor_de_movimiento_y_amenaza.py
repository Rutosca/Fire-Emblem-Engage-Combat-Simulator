from collections import deque
from dataclasses import dataclass
from typing import List, Set, Tuple, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from estado_tablero import FichaUnidad

class TerrenoMock:
    def __init__(self, caminable=True, volable=True, coste=1):
        self.caminable = caminable
        self.volable = volable
        self.coste = coste

class ArmaMock:
    def __init__(self, rango: List[int]):
        self.rango = rango  # Ej: [1] para espada, [2] para arco, [1, 2] para tomo magico

class UnidadMock:
    def __init__(self, x: int, y: int, mov: int, es_volador: bool, arma: ArmaMock,
                 tamano: int = 1, es_dragon: bool = False):
        self.x = x
        self.y = y
        self.movimiento_max = mov
        self.es_volador = es_volador
        self.arma = arma
        # Huella (Corrupted Wyrm 2x2, anclada abajo a la izquierda) y tipo de movimiento
        # dragón (MoveType 4: bosque y agua le cuestan 1, como el llano).
        self.tamano = max(1, int(tamano or 1))
        self.es_dragon = bool(es_dragon)


def mock_de_ficha(ficha, mov: Optional[int] = None, rango: Optional[List[int]] = None) -> UnidadMock:
    """UnidadMock de una ficha con su huella y su tipo de movimiento."""
    stats = getattr(ficha, 'stats', None)
    tipo = str(getattr(stats, 'tipo_movimiento', '') or '').lower()
    arma = getattr(ficha, 'arma', None)
    return UnidadMock(
        x=ficha.x, y=ficha.y,
        mov=ficha.movimiento_disponible if mov is None else mov,
        es_volador=ficha.es_volador,
        arma=ArmaMock(rango=rango if rango is not None else (getattr(arma, 'rango', None) or [1])),
        tamano=getattr(ficha, 'tamano', 1),
        es_dragon=tipo in ('dragón', 'dragon'),
    )


# =============================================================================
# Contexto de Mapa para evaluar_riesgo
# =============================================================================

@dataclass
class ContextoMapaEnemigo:
    """
    Empaqueta la información espacial del enemigo que evaluar_riesgo necesita
    para calcular el peor caso de amenaza en el turno enemigo.

    Uso:
        analizador = AnalizadorAmenaza(grid, ancho, alto)
        contexto = ContextoMapaEnemigo(
            analizador=analizador,
            ficha_enemigo=tablero.obtener_ficha("Wyvern"),
            pos_jugador=(5, 4),
            ficha_jugador=tablero.obtener_ficha("Alear"),
        )
    """
    analizador: object          # instancia de AnalizadorAmenaza
    ficha_enemigo: object       # instancia de estado_tablero.FichaUnidad
    pos_jugador: Tuple[int, int]
    ficha_jugador: object       # instancia de estado_tablero.FichaUnidad

def casillas_advance(alcanzables, posiciones_enemigas, ocupadas, grid, ancho, alto, es_volador=False) -> dict:
    """
    Advance (SID_踏み込み, Roy): desde una casilla alcanzable P con un enemigo a
    distancia 2, la unidad avanza 1 casilla hacia él y ataca cuerpo a cuerpo.
    Devuelve {Q: P}: casilla final Q (adyacente a P y al enemigo, libre y
    transitable) → casilla P desde la que se lanza el comando. Solo se incluyen
    las Q que NO se alcanzan ya con el movimiento normal (ahí Advance no aporta).
    `ocupadas`: casillas de cualquier unidad viva (no se puede terminar en ellas).
    """
    alcanzables = set(alcanzables or ())
    enemigos = set(posiciones_enemigas or ())
    ocupadas = set(ocupadas or ())
    salida = {}

    def transitable(x, y):
        if not (0 <= x < ancho and 0 <= y < alto):
            return False
        t = grid[x][y]
        return bool(getattr(t, 'volable', True)) if es_volador else bool(getattr(t, 'caminable', True))

    for (px, py) in alcanzables:
        if (px, py) in ocupadas and False:
            continue
        for (ex, ey) in enemigos:
            if abs(px - ex) + abs(py - ey) != 2:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                qx, qy = px + dx, py + dy
                if abs(qx - ex) + abs(qy - ey) != 1:
                    continue
                q = (qx, qy)
                if q in alcanzables or q in ocupadas or q in enemigos or not transitable(qx, qy):
                    continue
                # de varias P posibles, la más cercana al origen no se conoce aquí: se guarda la primera
                salida.setdefault(q, (px, py))
    return salida


class AnalizadorAmenaza:
    """
    Calcula las casillas a las que una unidad puede moverse y atacar.
    Usa una variante de búsqueda en anchura (BFS) / Dijkstra adaptada a casillas.
    """
    def __init__(self, grid_terreno: List[List[TerrenoMock]], ancho: int, alto: int):
        self.grid = grid_terreno
        self.ancho = ancho
        self.alto = alto

    def _huella(self, unidad, x: int, y: int):
        t = getattr(unidad, 'tamano', 1) or 1
        return [(x + dx, y - dy) for dy in range(t) for dx in range(t)]

    def _coste_huella(self, unidad, x: int, y: int, bloqueadas) -> int:
        """Coste de que la unidad (toda su huella) pase a tener la esquina en (x, y)."""
        coste = 0
        for (hx, hy) in self._huella(unidad, x, y):
            if not getattr(unidad, 'tiene_pass', False) and (hx, hy) in bloqueadas:
                return 999
            if getattr(unidad, 'es_dragon', False) and not unidad.es_volador:
                c = 999 if not (0 <= hx < self.ancho and 0 <= hy < self.alto) or not getattr(self.grid[hx][hy], 'caminable', True) else 1
            else:
                c = self._obtener_coste_terreno(hx, hy, unidad.es_volador)
            coste = max(coste, c)
        return coste

    def _anclas(self, unidad, bloqueadas) -> dict:
        """{esquina: movimiento restante} de una unidad grande o dragón."""
        visitados = {(unidad.x, unidad.y): unidad.movimiento_max}
        cola = deque([(unidad.x, unidad.y, unidad.movimiento_max)])
        while cola:
            cx, cy, mov_restante = cola.popleft()
            for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0)):
                nx, ny = cx + dx, cy + dy
                nuevo_mov = mov_restante - self._coste_huella(unidad, nx, ny, bloqueadas)
                if nuevo_mov >= 0 and nuevo_mov > visitados.get((nx, ny), -1):
                    visitados[(nx, ny)] = nuevo_mov
                    cola.append((nx, ny, nuevo_mov))
        return visitados

    def _es_especial(self, unidad) -> bool:
        return (getattr(unidad, 'tamano', 1) or 1) > 1 or getattr(unidad, 'es_dragon', False)

    def calcular_anclas_alcanzables(self, unidad, casillas_bloqueadas=None) -> Set[Tuple[int, int]]:
        """Posiciones (esquina de la huella) a las que puede ir la unidad."""
        return set(self._anclas(unidad, casillas_bloqueadas or set()))

    def _obtener_coste_terreno(self, x: int, y: int, es_volador: bool) -> int:
        """Devuelve el coste de pisar una casilla. Retorna 999 si es intransitable."""
        if not (0 <= x < self.ancho and 0 <= y < self.alto):
            return 999 # Fuera del mapa
            
        terreno = self.grid[x][y]
        
        # Voladores ignoran costes de terreno y agua, siempre les cuesta 1 (si no es muro)
        volable = getattr(terreno, 'volable', True)
        if es_volador:
            return 1 if volable else 999
            
        # Unidades terrestres
        caminable = getattr(terreno, 'caminable', True)
        if caminable:
            return getattr(terreno, 'coste_mov', getattr(terreno, 'coste', 1))
        return 999

    def calcular_casillas_alcanzables(
        self,
        unidad: UnidadMock,
        casillas_bloqueadas: Optional[Set[Tuple[int, int]]] = None
    ) -> Set[Tuple[int, int]]:
        """
        Paso 1: Calcula las casillas a las que la unidad puede Moverse (Rango Azul).
        - casillas_bloqueadas (ej. enemigos sin pasiva Pass/Traspasar) actúan como muros infranqueables.
        """
        # Unidades grandes (2x2) y dragones: se mueve la huella entera. Se devuelven todas
        # las casillas que puede cubrir, que son las que cuentan para alcanzar a alguien.
        if self._es_especial(unidad):
            return {c for (ax, ay) in self._anclas(unidad, casillas_bloqueadas or set())
                    for c in self._huella(unidad, ax, ay)}

        # Formato de la cola: (x, y, movimiento_restante)
        cola = deque([(unidad.x, unidad.y, unidad.movimiento_max)])
        
        # Diccionario para guardar el máximo movimiento con el que hemos llegado a una casilla
        visitados = {(unidad.x, unidad.y): unidad.movimiento_max}
        bloqueadas = casillas_bloqueadas or set()
        tiene_pass = getattr(unidad, 'tiene_pass', False)
        
        direcciones = [(0, 1), (1, 0), (0, -1), (-1, 0)] # Arriba, Derecha, Abajo, Izquierda

        while cola:
            cx, cy, mov_restante = cola.popleft()

            for dx, dy in direcciones:
                nx, ny = cx + dx, cy + dy
                
                # Unidades enemigas bloquean el paso físico salvo que tenga pasiva Pass / Traspasar
                if not tiene_pass and (nx, ny) in bloqueadas:
                    continue

                coste = self._obtener_coste_terreno(nx, ny, unidad.es_volador)
                nuevo_mov = mov_restante - coste
                
                # Si tenemos movimiento para entrar y es una mejor ruta de la que ya conocíamos
                if nuevo_mov >= 0 and nuevo_mov > visitados.get((nx, ny), -1):
                    visitados[(nx, ny)] = nuevo_mov
                    cola.append((nx, ny, nuevo_mov))

        # Devolvemos solo las coordenadas (x, y) de las casillas alcanzables
        return set(visitados.keys())

    def calcular_movimiento_restante(
        self,
        unidad: UnidadMock,
        casillas_bloqueadas: Optional[Set[Tuple[int, int]]] = None
    ) -> dict:
        """Devuelve cada casilla alcanzable y el movimiento que queda al llegar."""
        if self._es_especial(unidad):
            restantes = {}
            for (ax, ay), m in self._anclas(unidad, casillas_bloqueadas or set()).items():
                for c in self._huella(unidad, ax, ay):
                    restantes[c] = max(m, restantes.get(c, -1))
            return restantes
        cola = deque([(unidad.x, unidad.y, unidad.movimiento_max)])
        visitados = {(unidad.x, unidad.y): unidad.movimiento_max}
        bloqueadas = casillas_bloqueadas or set()
        tiene_pass = getattr(unidad, 'tiene_pass', False)
        direcciones = [(0, 1), (1, 0), (0, -1), (-1, 0)]

        while cola:
            cx, cy, mov_restante = cola.popleft()
            for dx, dy in direcciones:
                nx, ny = cx + dx, cy + dy
                if not tiene_pass and (nx, ny) in bloqueadas:
                    continue
                coste = self._obtener_coste_terreno(nx, ny, unidad.es_volador)
                nuevo_mov = mov_restante - coste
                if nuevo_mov >= 0 and nuevo_mov > visitados.get((nx, ny), -1):
                    visitados[(nx, ny)] = nuevo_mov
                    cola.append((nx, ny, nuevo_mov))
        return visitados

    def calcular_rango_amenaza(self, unidad: UnidadMock) -> Tuple[Set[Tuple[int, int]], Set[Tuple[int, int]]]:
        """
        Paso 2: A partir de donde puede moverse, calcula hasta dónde puede atacar (Rango Rojo).
        """
        casillas_movimiento = self.calcular_casillas_alcanzables(unidad)
        casillas_ataque = set()

        # Para cada casilla donde la unidad puede detenerse...
        for mx, my in casillas_movimiento:
            # ...miramos la distancia de su arma
            for distancia in unidad.arma.rango:
                # Calculamos las casillas exactas a esa distancia (Geometría Manhattan)
                for dx in range(-distancia, distancia + 1):
                    dy = distancia - abs(dx)
                    
                    # Añadimos los 4 cuadrantes
                    puntos_ataque = [
                        (mx + dx, my + dy),
                        (mx + dx, my - dy)
                    ]
                    
                    for ax, ay in puntos_ataque:
                        # Si está dentro del mapa, es atacable
                        if 0 <= ax < self.ancho and 0 <= ay < self.alto:
                            casillas_ataque.add((ax, ay))

        # Algunas casillas pueden ser atacables pero no pisables, por lo que las separamos.
        # Quitamos de la zona de ataque las casillas que ya son de movimiento (para no solapar colores).
        solo_ataque = casillas_ataque - casillas_movimiento
        
        return casillas_movimiento, solo_ataque
    def calcular_peor_caso_amenaza(
        self,
        ficha_enemigo,
        pos_jugador: Tuple[int, int],
        ficha_jugador,
        calc=None,
        casillas_movimiento_precalc=None,
    ) -> dict:
        """
        Calcula el peor caso de amenaza del enemigo en su turno.

        De todas las casillas alcanzables por el enemigo, encuentra aquella
        desde la que puede atacar al jugador con el máximo daño esperado.
        El LLM usa esto para advertir: "el Wyvern llegará a (6,4) y hará X daño".

        Args:
            ficha_enemigo:  FichaUnidad del enemigo (posición, stats, arma, mov).
            pos_jugador:    (x, y) donde estará el jugador tras su movimiento.
            ficha_jugador:  FichaUnidad del jugador (para calcular si puede contraatacar).
            calc:           Instancia de CalculadoraEngage. Si es None, sólo se
                            calcula viabilidad espacial (sin proyección de daño).
            casillas_movimiento_precalc: Set opcional de casillas alcanzables ya calculadas.

        Returns:
            dict con:
                enemigo_alcanza         bool  — el enemigo puede llegar al jugador
                pos_optima              (x,y) — mejor posición de ataque del enemigo
                distancia_ataque        int   — distancia Manhattan usada
                daño_proyectado         int   — daño total esperado (0 si calc=None)
                jugador_puede_contra    bool  — si el jugador puede contraatacar
        """
        arma_rango = ficha_enemigo.arma.rango if ficha_enemigo.arma else [1]
        if casillas_movimiento_precalc is not None:
            casillas_movimiento = casillas_movimiento_precalc
        else:
            unidad_mock = mock_de_ficha(ficha_enemigo, mov=ficha_enemigo.mov, rango=arma_rango)
            casillas_movimiento = self.calcular_casillas_alcanzables(unidad_mock)
        px, py = pos_jugador

        mejor_pos = None
        mejor_distancia = None
        mejor_daño = -1
        mejor_score = -999999
        jugador_puede_contra = False

        for (mx, my) in casillas_movimiento:
            for dist in arma_rango:
                # Comprobamos si desde (mx, my) el enemigo alcanza al jugador
                # a esta distancia Manhattan exacta.
                if abs(mx - px) + abs(my - py) != dist:
                    continue

                # El enemigo PUEDE atacar al jugador desde esta casilla.
                # Calculamos el daño si tenemos el calculador y los stats.
                daño = 0
                if (calc is not None
                        and ficha_enemigo.stats is not None
                        and ficha_enemigo.arma is not None
                        and ficha_jugador.stats is not None):
                    try:
                        sim = calc.simular_combate(
                            ficha_enemigo.stats,
                            ficha_jugador.stats,
                            ficha_enemigo.arma,
                            ficha_jugador.arma,   # puede ser None (sin contraataque)
                            distancia=dist,
                        )
                        daño = sim["atacante"]["daño_total_ronda"]
                    except (ValueError, TypeError):
                        # Distancia fuera de rango del arma del jugador, etc.
                        daño = 0

                arma_jugador = ficha_jugador.arma
                jugador_puede_contra_aqui = (
                    arma_jugador is not None
                    and dist in arma_jugador.rango
                    and (getattr(ficha_jugador, 'cargas_ruptura', 0) == 0)
                )
                score = (daño * 10) + (100 if not jugador_puede_contra_aqui else 0)

                if score > mejor_score or (score == mejor_score and daño > mejor_daño):
                    mejor_score = score
                    mejor_daño = daño
                    mejor_pos = (mx, my)
                    mejor_distancia = dist
                    jugador_puede_contra = jugador_puede_contra_aqui

        alcanza = mejor_pos is not None
        return {
            "enemigo_alcanza": alcanza,
            "puede_atacar": alcanza,
            "pos_optima": mejor_pos,
            "distancia_ataque": mejor_distancia,
            "daño_proyectado": max(0, mejor_daño),
            "jugador_puede_contra": jugador_puede_contra,
        }


if __name__ == "__main__":
    # 1. Creamos un mapa pequeño de 5x5
    ancho, alto = 5, 5
    grid = [[TerrenoMock() for _ in range(alto)] for _ in range(ancho)]
    
    # Ponemos un muro en medio que bloquee el paso
    grid[2][1] = TerrenoMock(caminable=False, volable=False)
    grid[2][2] = TerrenoMock(caminable=False, volable=False)
    grid[2][3] = TerrenoMock(caminable=False, volable=False)

    analizador = AnalizadorAmenaza(grid, ancho, alto)

    # 2. Creamos un Arquero enemigo con 2 de movimiento y rango 2 (Arco)
    arquero = UnidadMock(x=0, y=2, mov=2, es_volador=False, arma=ArmaMock(rango=[2]))

    movimiento, ataque = analizador.calcular_rango_amenaza(arquero)

    # 3. Dibujamos el mapa en la consola
    print("Mapa de Amenaza (A = Arquero, M = Muro, m = Movimiento (Azul), X = Ataque (Rojo), . = Seguro)")
    for y in range(alto):
        fila = ""
        for x in range(ancho):
            if x == arquero.x and y == arquero.y:
                fila += "[A]"
            elif not grid[x][y].caminable:
                fila += "[M]"
            elif (x, y) in movimiento:
                fila += " m "
            elif (x, y) in ataque:
                fila += " X "
            else:
                fila += " . "
        print(fila)
