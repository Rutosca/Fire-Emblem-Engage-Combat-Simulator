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
    def __init__(self, x: int, y: int, mov: int, es_volador: bool, arma: ArmaMock):
        self.x = x
        self.y = y
        self.movimiento_max = mov
        self.es_volador = es_volador
        self.arma = arma


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

class AnalizadorAmenaza:
    """
    Calcula las casillas a las que una unidad puede moverse y atacar.
    Usa una variante de búsqueda en anchura (BFS) / Dijkstra adaptada a casillas.
    """
    def __init__(self, grid_terreno: List[List[TerrenoMock]], ancho: int, alto: int):
        self.grid = grid_terreno
        self.ancho = ancho
        self.alto = alto

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
            unidad_mock = UnidadMock(
                x=ficha_enemigo.x,
                y=ficha_enemigo.y,
                mov=ficha_enemigo.mov,
                es_volador=ficha_enemigo.es_volador,
                arma=ArmaMock(rango=arma_rango),
            )
            casillas_movimiento = self.calcular_casillas_alcanzables(unidad_mock)
        px, py = pos_jugador

        mejor_pos = None
        mejor_distancia = None
        mejor_daño = -1
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

                if daño > mejor_daño:
                    mejor_daño = daño
                    mejor_pos = (mx, my)
                    mejor_distancia = dist
                    # El jugador puede contraatacar si su arma alcanza esa distancia
                    arma_jugador = ficha_jugador.arma
                    jugador_puede_contra = (
                        arma_jugador is not None
                        and dist in arma_jugador.rango
                    )

        return {
            "enemigo_alcanza": mejor_pos is not None,
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