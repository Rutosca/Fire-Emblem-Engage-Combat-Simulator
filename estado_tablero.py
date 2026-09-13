"""
EstadoTablero — FE Engage Tactical Assistant
Gestiona el estado mutable del tablero entre turnos.
La UI escribe aquí cuando el jugador arrastra tokens; el motor de cálculo lee de aquí.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from motor_calculo import Unidad, Arma
    from lector_de_mapas import MapaTactico


# =============================================================================
# Ficha de Unidad
# =============================================================================

@dataclass
class FichaUnidad:
    """
    Representa una unidad colocada en el mapa con su posición actual.
    Actúa como puente entre la UI (coordenadas x, y) y el motor de cálculo
    (instancias de Unidad y Arma).
    """
    nombre: str
    es_aliado: bool
    x: int
    y: int
    stats: Optional[object] = None     # instancia de motor_calculo.Unidad
    arma: Optional[object] = None      # instancia de motor_calculo.Arma
    mov: int = 5                       # Puntos de movimiento base
    es_volador: bool = False
    viva: bool = True                  # False cuando muere — se mantiene en el dict para el historial
    hp_max: int = 0                    # HP máximo de la unidad
    hp_actual: int = 0                 # HP actual restante
    energia_emblema: int = 6           # Cargas de medidor de Fusión (0 a max)
    max_energia_emblema: int = 6       # Cargas necesarias para activar Fusión
    turnos_fusion: int = 0             # Turnos restantes de Fusión activa
    en_fusion: bool = False            # True si está en modo Engage / Fusión activa
    clase_id: str = ""
    clase_nombre: str = ""
    nivel: int = 1
    emblema_id: str = ""
    emblema_nombre: str = ""
    habilidades: list = field(default_factory=list)
    inventario: list = field(default_factory=list)
    potenciadores_usados: list = field(default_factory=list) # e.g. ["Botas (+1 MOV)", "Túnica Angelical (+5 HP)"]
    es_verde: bool = False             # True para aliados que se unen en turno 1 (Alcryst, Citrinne, Lapis)
    es_fijo: bool = False              # True si su posición no puede cambiarse en preparación (Alear, verdes)
    ha_actuado: bool = False           # True si ya consumió su acción de movimiento / ataque este turno
    cargas_ruptura: int = 0            # Cargas de Ruptura (Break): 1 = no puede contraatacar en el siguiente combate
    hp_stock: int = 0                  # Piedras resurrectoras / barras de vida extra (jefes)
    nivel_veneno: int = 0              # Nivel de veneno (0..3): cada nivel aumenta en +1 todo daño recibido
    lider_tres_casas: str = "Dimitri"  # Líder activo del brazalete Tres Casas ("Edelgard", "Dimitri", "Claude")
    ataque_emblema_usado: bool = False # True si ya ejecutó el ataque o técnica especial de Engage en esta Fusión
    nivel_vinculo: int = 1             # Nivel de vínculo con el Emblema (>=11 otorga +1 turno de Fusión, total 4)

    def __post_init__(self):
        # Canónico FE Engage: 3 turnos de fusión base; nivel de vínculo >= 11 otorga +1 turno (4 turnos).
        # No se distingue entre tipos de unidades para los turnos de fusión.
        duracion_base = 4 if self.nivel_vinculo >= 11 else 3
        if self.en_fusion and self.turnos_fusion <= 0:
            self.turnos_fusion = duracion_base

        # Regla Nivel 20: El medidor de recarga máxima se reduce en 1 (de 6 a 5)
        if self.nivel_vinculo >= 20:
            self.max_energia_emblema = 5
        elif self.max_energia_emblema == 5 and self.nivel_vinculo < 20:
            self.max_energia_emblema = 6
        if self.energia_emblema > self.max_energia_emblema:
            self.energia_emblema = self.max_energia_emblema

        if self.stats:
            stat_hp = getattr(self.stats, 'hp', 30)
            if self.hp_max <= 0:
                self.hp_max = getattr(self.stats, 'hp_max', stat_hp) or stat_hp
            if self.hp_actual <= 0 and self.viva and stat_hp > 0:
                self.hp_actual = self.hp_max
            self.stats.hp = self.hp_actual
            self.stats.hp_max = self.hp_max
            setattr(self.stats, 'hp_actual', self.hp_actual)
            setattr(self.stats, 'nivel_veneno', self.nivel_veneno)
            setattr(self.stats, 'lider_tres_casas', self.lider_tres_casas)
            setattr(self.stats, 'nivel_vinculo', self.nivel_vinculo)
            setattr(self.stats, 'ataque_emblema_usado', self.ataque_emblema_usado)
            setattr(self.stats, 'turnos_fusion_restantes', self.turnos_fusion)
            setattr(self.stats, 'en_fusion', self.en_fusion or (self.turnos_fusion > 0))
            setattr(self.stats, 'energia_emblema', self.energia_emblema)
            setattr(self.stats, 'max_energia_emblema', self.max_energia_emblema)
        elif self.hp_max <= 0:
            self.hp_max = 30
            self.hp_actual = 30

    @property
    def hp(self) -> int:
        """Acceso unificado al HP actual para cálculos de combate."""
        return self.hp_actual

    @hp.setter
    def hp(self, val: int):
        self.sincronizar_hp(val)

    def sincronizar_hp(self, nuevo_hp: int):
        """Fuente única de mutación de HP: sincroniza ficha, stats y estado viva."""
        self.hp_actual = max(0, min(self.hp_max, int(nuevo_hp))) if self.hp_max > 0 else max(0, int(nuevo_hp))
        if self.stats and self.stats is not self:
            self.stats.hp = self.hp_actual
            self.stats.hp_max = self.hp_max
            setattr(self.stats, 'hp_actual', self.hp_actual)
        self.viva = (self.hp_actual > 0)

    def como_dict(self) -> dict:
        """Serialización completa para la API REST y el LLM."""
        hp_m = self.hp_max if self.hp_max > 0 else (getattr(self.stats, 'hp_max', getattr(self.stats, 'hp', 30)) if self.stats else 30)
        hp_a = max(0, min(hp_m, self.hp_actual)) if self.viva else 0
        pct = round((hp_a / hp_m) * 100) if hp_m > 0 else 0
        if self.stats:
            self.stats.hp = hp_a
            self.stats.hp_max = hp_m
            setattr(self.stats, 'hp_actual', hp_a)

        return {
            "nombre": self.nombre,
            "es_aliado": self.es_aliado,
            "es_verde": self.es_verde,
            "es_fijo": self.es_fijo,
            "ha_actuado": self.ha_actuado,
            "cargas_ruptura": self.cargas_ruptura,
            "en_ruptura": self.cargas_ruptura > 0,
            "nivel_veneno": max(0, min(3, self.nivel_veneno)),
            "lider_tres_casas": self.lider_tres_casas,
            "x": self.x,
            "y": self.y,
            "mov": self.mov,
            "es_volador": self.es_volador,
            "viva": self.viva and hp_a > 0,
            "hp_actual": hp_a,
            "hp_max": hp_m,
            "hp_stock": self.hp_stock,
            "pct_hp": pct,
            "energia_emblema": self.energia_emblema,
            "max_energia_emblema": self.max_energia_emblema,
            "turnos_fusion": self.turnos_fusion,
            "en_fusion": self.en_fusion or (self.turnos_fusion > 0),
            "ataque_emblema_usado": self.ataque_emblema_usado,
            "nivel_vinculo": self.nivel_vinculo,
            "clase_id": self.clase_id,
            "clase_nombre": self.clase_nombre,
            "nivel": self.nivel,
            "emblema_id": self.emblema_id,
            "emblema_nombre": self.emblema_nombre,
            "habilidades": self.habilidades,
            "inventario": self.inventario,
            "potenciadores_usados": self.potenciadores_usados,
            "tiene_stats": self.stats is not None,
            "tiene_arma": self.arma is not None,
            "stats": {
                "hp": hp_a,
                "hp_actual": hp_a,
                "hp_max": hp_m,
                "fuerza": getattr(self.stats, 'fuerza', 10),
                "magia": getattr(self.stats, 'magia', 0),
                "destreza": getattr(self.stats, 'destreza', 10),
                "velocidad": getattr(self.stats, 'velocidad', 10),
                "defensa": getattr(self.stats, 'defensa', 8),
                "resistencia": getattr(self.stats, 'resistencia', 5),
                "suerte": getattr(self.stats, 'suerte', 5),
                "complexion": getattr(self.stats, 'complexion', 7),
                "es_lord": getattr(self.stats, 'es_lord', False),
            } if self.stats else None,
            "arma_equipada": {
                "nombre": getattr(self.arma, 'nombre', 'Arma'),
                "tipo": getattr(self.arma, 'tipo', 'Espada'),
                "mt": getattr(self.arma, 'mt', 5),
                "wt": getattr(self.arma, 'wt', 5),
                "hit": getattr(self.arma, 'hit', 80),
                "crit": getattr(self.arma, 'crit', 0),
                "rango": getattr(self.arma, 'rango', [1]),
            } if self.arma else None,
        }


# =============================================================================
# Estado del Tablero
# =============================================================================

class EstadoTablero:
    """
    Estado mutable del tablero entre turnos con historial de Cronogema (Deshacer).
    """

    def __init__(self, mapa=None, auto_cargar_spawns: bool = True):
        self.mapa = mapa
        self.fichas: Dict[str, FichaUnidad] = {}
        self.turno_actual: int = 1
        self.fase: str = "jugador"   # "jugador" | "enemigo"
        self.historial: List[dict] = []  # Pila de snapshots para Cronogema (Deshacer)

        if auto_cargar_spawns and self.mapa:
            self.cargar_spawns_desde_mapa()

    def cargar_spawns_desde_mapa(self) -> int:
        """
        Carga las unidades colocadas en la Capa de Objetos de Tiled (mapa.entidades).
        Si el objeto tiene propiedades tácticas (hp, fuerza, arma, etc.), construye Unidad y Arma.
        Devuelve el número de fichas cargadas.
        """
        if not self.mapa or not hasattr(self.mapa, 'entidades'):
            return 0

        from motor_calculo import Unidad, Arma

        cargadas = 0
        for ent in self.mapa.entidades:
            tipo_l = str(ent.tipo).lower()
            es_aliado = tipo_l in ('aliado', 'player', 'ally', 'lord') or ent.propiedades.get('es_aliado', True)

            p = ent.propiedades
            stats = None
            if any(k in p for k in ('hp', 'fuerza', 'str', 'magia', 'mag', 'velocidad', 'spd')):
                stats = Unidad(
                    nombre=ent.nombre,
                    hp=p.get('hp', 30),
                    fuerza=p.get('fuerza', p.get('str', 10)),
                    magia=p.get('magia', p.get('mag', 0)),
                    destreza=p.get('destreza', p.get('dex', 10)),
                    velocidad=p.get('velocidad', p.get('spd', 10)),
                    defensa=p.get('defensa', p.get('def', 8)),
                    resistencia=p.get('resistencia', p.get('res', 5)),
                    suerte=p.get('suerte', p.get('lck', 5)),
                    complexion=p.get('complexion', p.get('bld', 7)),
                    es_lord=p.get('es_lord', tipo_l == 'lord')
                )

            arma = None
            if 'arma_tipo' in p or 'arma_mt' in p:
                arma = Arma(
                    nombre=p.get('arma_nombre', 'Arma'),
                    mt=p.get('arma_mt', 5),
                    wt=p.get('arma_wt', 5),
                    hit=p.get('arma_hit', 80),
                    crit=p.get('arma_crit', 0),
                    es_magica=p.get('arma_magica', False),
                    tipo=p.get('arma_tipo', 'Espada'),
                    rango=p.get('arma_rango', [1])
                )

            ficha = FichaUnidad(
                nombre=ent.nombre,
                es_aliado=es_aliado,
                x=ent.x,
                y=ent.y,
                stats=stats,
                arma=arma,
                mov=p.get('mov', 5),
                es_volador=p.get('es_volador', False)
            )
            self.registrar_unidad(ficha)
            cargadas += 1

        return cargadas

    # ── Registro y Limpieza ─────────────────────────────────────────────

    def limpiar(self) -> None:
        """Elimina todas las fichas del tablero."""
        self.fichas.clear()

    def registrar_unidad(self, ficha: FichaUnidad, resolver_colision: bool = True) -> None:
        """
        Añade o sobreescribe una ficha en el tablero.
        Si resolver_colision es True, elimina cualquier ficha previa que ocupe la misma casilla (x, y).
        """
        if resolver_colision:
            duplicados = [
                nom for nom, f in self.fichas.items()
                if f.viva and f.x == ficha.x and f.y == ficha.y and nom != ficha.nombre
            ]
            for dup in duplicados:
                del self.fichas[dup]

        # Si la unidad ya existía en el tablero y había actuado este turno,
        # asegurar que no pierda su turno gastado, veneno o líder de tres casas simplemente por editar stats/equipo
        prev = self.fichas.get(ficha.nombre)
        if prev and prev.ha_actuado and not getattr(ficha, '_ha_actuado_explicito', False):
            ficha.ha_actuado = True
        if prev and prev.cargas_ruptura > 0 and ficha.cargas_ruptura == 0:
            ficha.cargas_ruptura = prev.cargas_ruptura
        if prev and prev.nivel_veneno > 0 and ficha.nivel_veneno == 0:
            ficha.nivel_veneno = prev.nivel_veneno
            if ficha.stats:
                setattr(ficha.stats, 'nivel_veneno', ficha.nivel_veneno)
        if prev and hasattr(prev, 'lider_tres_casas') and prev.lider_tres_casas:
            if not getattr(ficha, '_lider_tres_casas_explicito', False):
                ficha.lider_tres_casas = prev.lider_tres_casas
                if ficha.stats:
                    setattr(ficha.stats, 'lider_tres_casas', ficha.lider_tres_casas)
        if prev and (prev.en_fusion or prev.turnos_fusion > 0) and prev.turnos_fusion > 0:
            ficha.en_fusion = True
            if ficha.turnos_fusion <= 0:
                ficha.turnos_fusion = prev.turnos_fusion
            ficha.ataque_emblema_usado = prev.ataque_emblema_usado
            if ficha.stats:
                setattr(ficha.stats, 'en_fusion', True)
                setattr(ficha.stats, 'turnos_fusion_restantes', ficha.turnos_fusion)
                setattr(ficha.stats, 'ataque_emblema_usado', ficha.ataque_emblema_usado)

        self.fichas[ficha.nombre] = ficha

    def registrar_muerte(self, nombre: str) -> None:
        """
        Marca una unidad como muerta.
        La ficha se conserva en el dict para trazabilidad, pero queda excluida
        de los cálculos de amenaza y análisis.
        """
        if nombre in self.fichas:
            self.fichas[nombre].sincronizar_hp(0)

    def modificar_hp(self, nombre: str, nuevo_hp: int) -> bool:
        """Ajusta directamente el HP actual de una unidad."""
        if nombre not in self.fichas:
            return False
        self.fichas[nombre].sincronizar_hp(nuevo_hp)
        return True

    def aplicar_daño(self, nombre: str, daño: int) -> int:
        """Resta HP a una unidad y actualiza su estado viva si llega a 0."""
        if nombre not in self.fichas:
            return 0
        f = self.fichas[nombre]
        f.sincronizar_hp(f.hp_actual - max(0, daño))
        return f.hp_actual

    def curar_unidad(self, nombre: str, cantidad: int) -> int:
        """Cura HP a una unidad hasta su máximo."""
        if nombre not in self.fichas:
            return 0
        f = self.fichas[nombre]
        f.sincronizar_hp(f.hp_actual + max(0, cantidad))
        return f.hp_actual

    def eliminar_unidad(self, nombre: str) -> bool:
        """Elimina completamente la ficha del tablero."""
        if nombre in self.fichas:
            del self.fichas[nombre]
            return True
        return False

    # ── Movimiento ───────────────────────────────────────────────────────

    def mover_unidad(self, nombre: str, nueva_x: int, nueva_y: int) -> bool:
        """
        Actualiza la posición de una unidad.
        Llamado por la UI cuando el jugador arrastra un token.

        Returns:
            True si la unidad existe y se movió, False si no se encontró.
        """
        if nombre not in self.fichas:
            return False
        ficha = self.fichas[nombre]
        ficha.x = nueva_x
        ficha.y = nueva_y

        # Casilla de recarga de Emblema al 100%: solo surte efecto si la unidad no esta en fusion y agoto sus turnos
        if self.mapa and hasattr(self.mapa, 'grid'):
            if 0 <= nueva_x < len(self.mapa.grid) and 0 <= nueva_y < len(self.mapa.grid[0]):
                casilla = self.mapa.grid[nueva_x][nueva_y]
                if getattr(casilla, 'es_recarga_emblema', False) and ficha.es_aliado and not ficha.en_fusion and ficha.turnos_fusion <= 0:
                    ficha.energia_emblema = ficha.max_energia_emblema
                    if ficha.stats:
                        ficha.stats.energia_emblema = ficha.max_energia_emblema

        return True

    def alternar_lider_tres_casas(self, nombre: str, nuevo_lider: Optional[str] = None) -> Optional[str]:
        """Alterna o establece el líder activo de Tres Casas (Edelgard, Dimitri, Claude)."""
        f = self.fichas.get(nombre)
        if not f:
            return None
        ciclo = ["Dimitri", "Edelgard", "Claude"]
        if nuevo_lider and nuevo_lider in ciclo:
            f.lider_tres_casas = nuevo_lider
        else:
            idx = ciclo.index(f.lider_tres_casas) if f.lider_tres_casas in ciclo else 0
            f.lider_tres_casas = ciclo[(idx + 1) % len(ciclo)]
        if f.stats:
            setattr(f.stats, 'lider_tres_casas', f.lider_tres_casas)
        return f.lider_tres_casas

    def ajustar_nivel_veneno(self, nombre: str, nivel: int) -> int:
        """Ajusta directamente el nivel de veneno (0..3) de una unidad."""
        f = self.fichas.get(nombre)
        if not f:
            return 0
        f.nivel_veneno = max(0, min(3, int(nivel)))
        if f.stats:
            setattr(f.stats, 'nivel_veneno', f.nivel_veneno)
        return f.nivel_veneno

    # ── Consultas ────────────────────────────────────────────────────────

    def obtener_ficha(self, nombre: str) -> Optional[FichaUnidad]:
        return self.fichas.get(nombre)

    def obtener_aliados(self) -> List[FichaUnidad]:
        """Devuelve aliados vivos."""
        return [f for f in self.fichas.values() if f.es_aliado and f.viva]

    def obtener_enemigos(self) -> List[FichaUnidad]:
        """Devuelve enemigos vivos."""
        return [f for f in self.fichas.values() if not f.es_aliado and f.viva]

    def posicion_de(self, nombre: str) -> Optional[tuple]:
        """Devuelve (x, y) de la unidad o None si no existe."""
        f = self.fichas.get(nombre)
        return (f.x, f.y) if f else None

    # ── Cronogema (Deshacer / Time Crystal) ──────────────────────────────

    def guardar_snapshot(self) -> None:
        """Guarda un snapshot completo para la Cronogema (Deshacer) antes de cualquier acción."""
        import copy
        snap = {
            "turno": self.turno_actual,
            "fase": self.fase,
            "fichas": copy.deepcopy(self.fichas)
        }
        self.historial.append(snap)
        if len(self.historial) > 50:
            self.historial.pop(0)

    def deshacer(self) -> bool:
        """Restaura el estado anterior de la Cronogema. Retorna True si hubo estado que restaurar."""
        if not self.historial:
            return False
        snap = self.historial.pop()
        self.turno_actual = snap["turno"]
        self.fase = snap["fase"]
        self.fichas = snap["fichas"]
        return True

    # ── Gestión de Acciones de Turno ─────────────────────────────────────

    def reiniciar_acciones_turno(self) -> None:
        """Reactiva las acciones de todas las unidades vivas y limpia la ruptura de aliados al inicio de turno."""
        for f in self.fichas.values():
            f.ha_actuado = False
            if f.es_aliado:
                f.cargas_ruptura = 0

    def alternar_actuado(self, nombre: str) -> bool:
        """Alterna el estado de acción (ha_actuado) de una unidad."""
        if nombre not in self.fichas:
            return False
        self.fichas[nombre].ha_actuado = not self.fichas[nombre].ha_actuado
        return True

    # ── Turno ────────────────────────────────────────────────────────────

    def avanzar_turno(self) -> None:
        """
        Registra el fin del turno enemigo y prepara el siguiente turno del jugador.
        Reactiva todas las acciones de los aliados y limpia estados temporales.
        """
        self.guardar_snapshot()
        self.turno_actual += 1
        self.fase = "jugador"
        self.reiniciar_acciones_turno()

        # Decremento canonico de turnos de Fusion de Emblema para aliados
        for f in self.obtener_aliados():
            if f.en_fusion or f.turnos_fusion > 0:
                f.turnos_fusion = max(0, f.turnos_fusion - 1)
                if f.turnos_fusion == 0:
                    f.en_fusion = False
                    f.energia_emblema = 0
                    f.ataque_emblema_usado = False
                if f.stats:
                    f.stats.turnos_fusion_restantes = f.turnos_fusion
                    f.stats.en_fusion = f.en_fusion
                    f.stats.energia_emblema = f.energia_emblema
                    f.stats.ataque_emblema_usado = f.ataque_emblema_usado

    def iniciar_fase_enemigo(self) -> None:
        """Marca que estamos en la fase de movimiento enemigo y limpia la ruptura de enemigos."""
        self.guardar_snapshot()
        self.fase = "enemigo"
        for f in self.fichas.values():
            if not f.es_aliado:
                f.cargas_ruptura = 0

    # ── Serialización ────────────────────────────────────────────────────

    def snapshot(self) -> dict:
        """
        Serializa el estado completo del tablero como JSON.
        Esto es lo que el LLM recibe para contexto.
        """
        return {
            "turno": self.turno_actual,
            "fase": self.fase,
            "aliados": [f.como_dict() for f in self.obtener_aliados()],
            "enemigos": [f.como_dict() for f in self.obtener_enemigos()],
            "fichas": [f.como_dict() for f in self.fichas.values()]
        }

    def como_dict(self) -> dict:
        return self.snapshot()


# =============================================================================
# Prueba de Ejecución
# =============================================================================

if __name__ == "__main__":
    import json

    tablero = EstadoTablero(mapa=None)

    # Registrar fichas de prueba
    tablero.registrar_unidad(FichaUnidad("Alear",   es_aliado=True,  x=4, y=4, mov=5))
    tablero.registrar_unidad(FichaUnidad("Louis",   es_aliado=True,  x=3, y=5, mov=4))
    tablero.registrar_unidad(FichaUnidad("Wyvern",  es_aliado=False, x=8, y=4, mov=6, es_volador=True))
    tablero.registrar_unidad(FichaUnidad("Arquero", es_aliado=False, x=9, y=6, mov=5))

    print("=== Estado inicial ===")
    print(json.dumps(tablero.snapshot(), indent=2, ensure_ascii=False))

    # Simular: el jugador mueve a Alear
    tablero.mover_unidad("Alear", 5, 4)
    # El jugador reporta que el Wyvern se movió a (6, 4) en el turno enemigo
    tablero.iniciar_fase_enemigo()
    tablero.mover_unidad("Wyvern", 6, 4)
    tablero.avanzar_turno()

    print("\n=== Estado tras turno enemigo ===")
    print(json.dumps(tablero.snapshot(), indent=2, ensure_ascii=False))

    # Simular baja
    tablero.registrar_muerte("Arquero")
    print(f"\nEnemigos vivos: {[f.nombre for f in tablero.obtener_enemigos()]}")
