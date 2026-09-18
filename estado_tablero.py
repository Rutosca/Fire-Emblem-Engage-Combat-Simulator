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
    habilidades_sids: list = field(default_factory=list)  # Sids crudos (SID_...) para lookups deterministas por Condition/Act*
    inventario: list = field(default_factory=list)
    potenciadores_usados: list = field(default_factory=list) # e.g. ["Botas (+1 MOV)", "Túnica Angelical (+5 HP)"]
    boosts_fusion: dict = field(default_factory=dict)  # Bono de stats en Fusión observado en el juego (Rise Above de Roy): {"hp":5,"str":3,...}
    es_verde: bool = False             # True para aliados que se unen en turno 1 (Alcryst, Citrinne, Lapis)
    es_fijo: bool = False              # True si su posición no puede cambiarse en preparación (Alear, verdes)
    ha_actuado: bool = False           # True si ya consumió su acción de movimiento / ataque este turno
    cargas_ruptura: int = 0            # Cargas de Ruptura (Break): 1 = no puede contraatacar en el siguiente combate
    hp_stock: int = 0                  # Piedras resurrectoras / barras de vida extra (jefes)
    nivel_veneno: int = 0              # Nivel de veneno (0..3): cada nivel aumenta en +1 todo daño recibido
    lider_tres_casas: str = "Dimitri"  # Líder activo del brazalete Tres Casas ("Edelgard", "Dimitri", "Claude")
    ataque_emblema_usado: bool = False # True si ya ejecutó el ataque o técnica especial de Engage en esta Fusión
    chain_guard_activo: bool = True    # True si puede realizar Guardia en Cadena (Martial Monk/Master/Dancer)
    chain_guard_usado: bool = False    # True si ya absorbió un golpe este turno
    nivel_vinculo: int = 1             # Nivel de vínculo con el Emblema (>=11 otorga +1 turno de Fusión, total 4)
    estilo_combate: str = ""           # Estilo de combate: Qi Adept, Backup, Dragon, Covert, etc.
    es_jefe: bool = False              # True si la unidad es un jefe (boss)
    es_refuerzo: bool = False          # True si entró como refuerzo (no estaba en el despliegue inicial)
    accion_turno: str = ""             # Acción consumida este turno: "combate" | "objeto" | "baston" | "" (esperó / aún no actuó)
    # Estados temporales (buffs "de 1 turno" del juego, p.ej. SID_力＋２_１ターン). Cada uno:
    #   {"sid", "nombre", "stat_boosts": {str,mag,...}, "expira_fase", "expira_turno", "origen"}
    # Caduca al ENTRAR en (expira_fase, expira_turno). Ver otorgar_estado_temporal / purgar_estados_temporales.
    estados_temporales: list = field(default_factory=list)

    @property
    def arma_equipada(self):
        """Alias para el arma activa equipada de combate."""
        return self.arma

    def __setattr__(self, name, value):
        # La posición vive en la ficha, pero las pasivas de proximidad que evalúa el
        # motor (Gente de Cuento: pareja hombre-mujer adyacente) solo ven `stats`.
        # Mantener x/y reflejados en stats sin depender de cada sitio que mueve fichas.
        object.__setattr__(self, name, value)
        if name in ("x", "y"):
            st = self.__dict__.get("stats")
            if st is not None:
                try:
                    setattr(st, name, value)
                except Exception:
                    pass
        elif name == "stats" and value is not None:
            try:
                setattr(value, "x", self.__dict__.get("x", 0))
                setattr(value, "y", self.__dict__.get("y", 0))
            except Exception:
                pass

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

        if not self.viva or self.hp_actual <= 0:
            self.viva = False
            self.hp_actual = 0

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
            setattr(self.stats, 'hp_stock', self.hp_stock)
            setattr(self.stats, 'estados_temporales', self.estados_temporales)
            setattr(self.stats, 'boosts_fusion', dict(self.boosts_fusion or {}))
        elif self.hp_max <= 0:
            self.hp_max = 30
            self.hp_actual = 30

    # ── Estados temporales ───────────────────────────────────────────────

    def _sincronizar_estados_temporales(self):
        if self.stats and self.stats is not self:
            setattr(self.stats, 'estados_temporales', self.estados_temporales)

    def tiene_estado_temporal(self, sid: str) -> bool:
        return any(e.get("sid") == sid for e in self.estados_temporales)

    def otorgar_estado_temporal(self, sid: str, nombre: str, stat_boosts: dict,
                                expira_fase: str, expira_turno: int, origen: str = "") -> dict:
        """
        Otorga (o refresca) un buff temporal. Como en el juego, un mismo SID no se
        acumula: si ya estaba activo se sustituye por el nuevo, extendiendo su caducidad.
        """
        self.estados_temporales = [e for e in self.estados_temporales if e.get("sid") != sid]
        estado = {
            "sid": sid,
            "nombre": nombre,
            "stat_boosts": {k: int(v) for k, v in (stat_boosts or {}).items() if int(v or 0) != 0},
            "expira_fase": expira_fase,
            "expira_turno": int(expira_turno),
            "origen": origen,
        }
        self.estados_temporales.append(estado)
        self._sincronizar_estados_temporales()
        return estado

    def purgar_estados_temporales(self, fase: str, turno: int) -> list:
        """Elimina los estados que caducan al entrar en (fase, turno). Devuelve los eliminados."""
        vencidos = [e for e in self.estados_temporales
                    if e.get("expira_fase") == fase and int(e.get("expira_turno", 0)) <= int(turno)]
        if vencidos:
            self.estados_temporales = [e for e in self.estados_temporales if e not in vencidos]
            self._sincronizar_estados_temporales()
        return vencidos

    @property
    def armas_permitidas(self) -> list:
        """Tipos de arma con maestría según la clase (Job.xml). Vacío si la clase no está en el catálogo."""
        from catalogo_loader import armas_permitidas_clase
        return armas_permitidas_clase(self.clase_id, self.clase_nombre)

    @property
    def puede_usar_ballesta(self) -> bool:
        """Maestría en Arco + un arco en el inventario (requisito de las ballestas de mapa)."""
        from catalogo_loader import puede_usar_ballesta
        return puede_usar_ballesta(self)

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
            "accion_turno": self.accion_turno,
            "es_refuerzo": self.es_refuerzo,
            "estados_temporales": self.estados_temporales,
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
            "es_jefe": bool(self.es_jefe or (self.hp_stock > 0 and not self.es_aliado) or (getattr(self.stats, "es_jefe", False) if self.stats else False)),
            "pct_hp": pct,
            "energia_emblema": self.energia_emblema,
            "max_energia_emblema": self.max_energia_emblema,
            "turnos_fusion": self.turnos_fusion,
            "en_fusion": self.en_fusion or (self.turnos_fusion > 0),
            "ataque_emblema_usado": self.ataque_emblema_usado,
            "chain_guard_activo": self.chain_guard_activo,
            "chain_guard_usado": self.chain_guard_usado,
            "nivel_vinculo": self.nivel_vinculo,
            "clase_id": self.clase_id,
            "clase_nombre": self.clase_nombre,
            "armas_permitidas": self.armas_permitidas,
            "puede_usar_ballesta": self.puede_usar_ballesta,
            "estilo_combate": self.estilo_combate or (getattr(self.stats, 'estilo_combate', '') if self.stats else ''),
            "nivel": self.nivel,
            "emblema_id": self.emblema_id,
            "emblema_nombre": self.emblema_nombre,
            "habilidades": self.habilidades,
            "inventario": self.inventario,
            "potenciadores_usados": self.potenciadores_usados,
            "boosts_fusion": dict(self.boosts_fusion or {}),
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
        # Estado de los objetos de mapa (ballestas, destructibles, pozos de Emblema):
        #   {id: {"activo": bool, "usos": int|None, "tipo": str, "nombre": str}}
        self.objetos: Dict[str, dict] = {}
        self.inicializar_objetos_mapa()
        # Refuerzos pendientes: {turno: [dict de unidad resuelto por el cargador de dispos]}.
        # Se despliegan al entrar en la fase de jugador de ese turno (avanzar_turno).
        self.refuerzos_pendientes: Dict[int, list] = {}
        self.refuerzos_desplegados_ultimo: list = []
        self.dificultad: str = "Hard"   # dificultad con la que se desplegó el capítulo (refuerzos)
        # Fuego de Blazing Lion: {(x, y): turno_en_que_se_apaga}. Prende en el turno T del
        # jugador, quema a quien empiece su fase encima y se apaga al empezar el turno T+1.
        self.casillas_fuego: Dict[tuple, int] = {}
        self.quemados_ultimo: list = []   # [(nombre, daño)] del último inicio de fase
        self.curados_ultimo: list = []    # [(nombre, HP recuperados)] por terreno curativo en el último inicio de fase

        if auto_cargar_spawns and self.mapa:
            self.cargar_spawns_desde_mapa()

    # ── Fuego temporal (Blazing Lion) ─────────────────────────────────────

    def encender_fuego(self, casillas, turnos: int = 1) -> list:
        """Prende `casillas` hasta el turno actual + `turnos`. Devuelve las casillas encendidas."""
        encendidas = []
        for c in casillas:
            c = (int(c[0]), int(c[1]))
            self.casillas_fuego[c] = self.turno_actual + int(turnos)
            encendidas.append(c)
        self.sincronizar_fuego_mapa()
        return encendidas

    def sincronizar_fuego_mapa(self) -> None:
        """Proyecta el estado del fuego sobre el grid del mapa."""
        if not self.mapa or not hasattr(self.mapa, 'aplicar_fuego'):
            return
        self.mapa.limpiar_fuego()
        if self.casillas_fuego:
            self.mapa.aplicar_fuego(list(self.casillas_fuego.keys()))

    def apagar_fuego_caducado(self) -> list:
        """Apaga el fuego cuyo turno de caducidad ya llegó. Devuelve las casillas apagadas."""
        apagadas = [c for c, t in self.casillas_fuego.items() if self.turno_actual >= t]
        for c in apagadas:
            self.casillas_fuego.pop(c, None)
        if apagadas:
            self.sincronizar_fuego_mapa()
        return apagadas

    def quemar_unidades_en_fuego(self, es_aliado: bool) -> list:
        """
        Daño del fuego a las unidades del bando indicado que empiezan su fase sobre una
        casilla en llamas (10 HP, nunca por debajo de 1: el fuego no mata en el juego).
        Los voladores no se queman (verificado en el juego).
        Devuelve [(nombre, daño), ...].
        """
        from ataques_area import FUEGO_DANO_POR_FASE
        quemados = []
        if not self.casillas_fuego:
            return quemados
        for f in self.fichas.values():
            if getattr(f, 'es_volador', False):
                continue
            if f.viva and bool(f.es_aliado) == bool(es_aliado) and (f.x, f.y) in self.casillas_fuego:
                nuevo = max(1, f.hp_actual - FUEGO_DANO_POR_FASE)
                dano = f.hp_actual - nuevo
                if dano > 0:
                    f.sincronizar_hp(nuevo)
                    quemados.append((f.nombre, dano))
        return quemados

    def curar_unidades_en_terreno(self, es_aliado: bool) -> list:
        """
        Curación de terreno (Terrain.xml `Heal`: fuertes, tronos, casillas de recuperación…):
        las unidades del bando indicado que empiezan su fase sobre una casilla con
        `curacion_turno` > 0 recuperan esos HP (tope: HP máximo). Viene del mapa (Tiled →
        tipo de terreno → catálogo de terrenos), no de ningún capítulo concreto.
        Devuelve [(nombre, curado), ...].
        """
        curados = []
        if not self.mapa or not hasattr(self.mapa, 'obtener_terreno'):
            return curados
        for f in self.fichas.values():
            if not f.viva or bool(f.es_aliado) != bool(es_aliado):
                continue
            t = self.mapa.obtener_terreno(f.x, f.y)
            cura = int(getattr(t, 'curacion_turno', 0) or 0) if t else 0
            if cura <= 0 or f.hp_actual >= f.hp_max:
                continue
            nuevo = min(f.hp_max, f.hp_actual + cura)
            ganado = nuevo - f.hp_actual
            if ganado > 0:
                f.sincronizar_hp(nuevo)
                curados.append((f.nombre, ganado))
        return curados

    def casillas_fuego_lista(self) -> list:
        return [{"x": x, "y": y, "expira_turno": t} for (x, y), t in sorted(self.casillas_fuego.items())]

    # ── Objetos de mapa (capa de objetos de Tiled) ───────────────────────

    def inicializar_objetos_mapa(self) -> None:
        """Reconstruye el estado de los objetos desde el mapa (todos activos, usos a tope)."""
        self.objetos = {}
        if not self.mapa or not hasattr(self.mapa, 'objetos_mapa'):
            return
        for ent in self.mapa.objetos_mapa():
            usos = ent.propiedades.get("usos")
            vida = ent.propiedades.get("vida", ent.propiedades.get("hp"))
            self.objetos[ent.id_entidad] = {
                "activo": True,
                "usos": int(usos) if usos is not None else None,
                "vida": int(vida) if vida is not None else None,   # HP de los destructibles
                "vida_max": int(vida) if vida is not None else None,
                "tipo": str(ent.tipo).lower(),
                "nombre": ent.nombre,
            }
        self.sincronizar_objetos_mapa()

    def sincronizar_objetos_mapa(self) -> None:
        """Vuelca el estado actual de los objetos sobre el grid del mapa."""
        if self.mapa and hasattr(self.mapa, 'aplicar_objetos'):
            self.mapa.aplicar_objetos(self.objetos)

    def objetos_como_lista(self) -> List[dict]:
        """Objetos del mapa con su estado, para la API / UI."""
        if not self.mapa or not hasattr(self.mapa, 'objetos_mapa'):
            return []
        return [{**ent.como_dict(), **self.objetos.get(ent.id_entidad, {"activo": True})}
                for ent in self.mapa.objetos_mapa()]

    def consumir_objeto_mapa(self, id_objeto: str) -> bool:
        """
        Gasta un uso del objeto (ballesta con `usos`) o lo desactiva del todo
        (destructible destruido, pozo de Emblema agotado, arma sin `usos`).
        Devuelve False si no existe o ya estaba inactivo.
        """
        est = self.objetos.get(str(id_objeto))
        if not est or not est.get("activo"):
            return False
        if est.get("usos") is not None and est["tipo"] == "arma_usable":
            est["usos"] = max(0, est["usos"] - 1)
            if est["usos"] > 0:
                return True
        est["activo"] = False
        self.sincronizar_objetos_mapa()
        return True

    def dañar_objeto_mapa(self, id_objeto: str, daño: int = 0, vida: Optional[int] = None) -> Optional[dict]:
        """
        Resta HP a un destructible con `vida` (o la fija en `vida` si se indica);
        al llegar a 0 se destruye entero (todas sus casillas quedan libres).
        Si no tiene `vida`, se destruye directamente.
        """
        est = self.objetos.get(str(id_objeto))
        if not est or not est.get("activo"):
            return None
        if est.get("vida") is None:
            self.consumir_objeto_mapa(id_objeto)
            return est
        if vida is not None:
            nueva = int(vida)
        else:
            nueva = int(est["vida"]) - max(0, int(daño))
        tope = int(est["vida_max"]) if est.get("vida_max") is not None else nueva
        est["vida"] = max(0, min(tope, nueva))
        if est["vida"] <= 0:
            est["activo"] = False
            self.sincronizar_objetos_mapa()
        return est

    def restaurar_objeto_mapa(self, id_objeto: str) -> bool:
        """Reactiva un objeto (corrección manual)."""
        est = self.objetos.get(str(id_objeto))
        if not est:
            return False
        est["activo"] = True
        ent = next((e for e in self.mapa.objetos_mapa() if e.id_entidad == str(id_objeto)), None) if self.mapa else None
        if ent and ent.propiedades.get("usos") is not None:
            est["usos"] = int(ent.propiedades["usos"])
        if est.get("vida_max") is not None:
            est["vida"] = est["vida_max"]
        self.sincronizar_objetos_mapa()
        return True

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
            if getattr(ent, 'es_objeto_mapa', False):
                continue  # ballestas, destructibles, pozos: no son unidades
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
        """Elimina todas las fichas del tablero (y apaga el fuego temporal)."""
        self.fichas.clear()
        if self.casillas_fuego:
            self.casillas_fuego = {}
            self.sincronizar_fuego_mapa()

    def registrar_unidad(self, ficha: FichaUnidad, resolver_colision: bool = True) -> None:
        """
        Añade o sobreescribe una ficha en el tablero.
        Si resolver_colision es True, elimina cualquier ficha previa que ocupe la misma casilla (x, y).
        """
        if resolver_colision and ficha.viva:
            duplicados = [
                nom for nom, f in self.fichas.items()
                if f.x == ficha.x and f.y == ficha.y and nom != ficha.nombre
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
        if prev and not getattr(ficha, '_chain_guard_activo_explicito', False):
            ficha.chain_guard_activo = prev.chain_guard_activo
        if prev and not getattr(ficha, '_hp_stock_explicito', False):
            if ficha.hp_stock == 0 and prev.hp_stock > 0:
                ficha.hp_stock = prev.hp_stock
        if prev and not getattr(ficha, '_energia_emblema_explicito', False):
            ficha.energia_emblema = prev.energia_emblema
            if ficha.stats:
                setattr(ficha.stats, 'energia_emblema', ficha.energia_emblema)
        if prev and prev.estados_temporales and not ficha.estados_temporales:
            ficha.estados_temporales = list(prev.estados_temporales)
            ficha._sincronizar_estados_temporales()
        if prev and prev.accion_turno and not ficha.accion_turno:
            ficha.accion_turno = prev.accion_turno

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
        # La casilla de recarga de Emblema NO actúa al pisarla: se aplica cuando la
        # unidad termina su acción encima (ver aplicar_recarga_emblema_en_casilla).
        return True

    def aplicar_recarga_emblema_en_casilla(self, nombre: str) -> Optional[dict]:
        """
        La unidad ha terminado su acción (ataque, objeto, esperar) sobre su casilla
        actual. Si es una casilla de recarga de Emblema y la unidad no está en
        fusión, recarga el medidor al 100%; si la recarga viene de un pozo de la
        capa de objetos, el pozo se agota y desaparece.
        Devuelve {"unidad", "pozo"} si hubo recarga, None si no.
        """
        ficha = self.fichas.get(nombre)
        if not ficha or not ficha.viva or not ficha.es_aliado or not self.mapa or not hasattr(self.mapa, 'grid'):
            return None
        if not (0 <= ficha.x < len(self.mapa.grid) and 0 <= ficha.y < len(self.mapa.grid[0])):
            return None
        casilla = self.mapa.grid[ficha.x][ficha.y]
        if not getattr(casilla, 'es_recarga_emblema', False):
            return None
        if ficha.en_fusion or ficha.turnos_fusion > 0:
            return None
        ficha.energia_emblema = ficha.max_energia_emblema
        if ficha.stats:
            ficha.stats.energia_emblema = ficha.max_energia_emblema
        pozo_id = None
        if hasattr(self.mapa, 'objeto_en'):
            pozo = self.mapa.objeto_en(ficha.x, ficha.y, "recarga_emblema")
            if pozo:
                self.consumir_objeto_mapa(pozo.id_entidad)
                pozo_id = pozo.id_entidad
        return {"unidad": ficha.nombre, "pozo": pozo_id}

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
            "fichas": copy.deepcopy(self.fichas),
            "objetos": copy.deepcopy(self.objetos),
            "refuerzos_pendientes": copy.deepcopy(self.refuerzos_pendientes),
            "casillas_fuego": dict(self.casillas_fuego),
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
        self.objetos = snap.get("objetos", self.objetos)
        self.refuerzos_pendientes = snap.get("refuerzos_pendientes", self.refuerzos_pendientes)
        self.casillas_fuego = dict(snap.get("casillas_fuego", {}))
        self.sincronizar_objetos_mapa()
        self.sincronizar_fuego_mapa()
        return True

    # ── Gestión de Acciones de Turno ─────────────────────────────────────

    def reiniciar_acciones_turno(self) -> None:
        """Reactiva las acciones de todas las unidades vivas y limpia la ruptura de aliados al inicio de turno."""
        for f in self.fichas.values():
            f.ha_actuado = False
            f.chain_guard_usado = False
            f.accion_turno = ""
            if f.es_aliado:
                f.cargas_ruptura = 0

    def alternar_actuado(self, nombre: str) -> bool:
        """Alterna el estado de acción (ha_actuado) de una unidad."""
        if nombre not in self.fichas:
            return False
        self.fichas[nombre].ha_actuado = not self.fichas[nombre].ha_actuado
        return True

    def alternar_chain_guard(self, nombre: str, nuevo_estado: Optional[bool] = None) -> bool:
        """Alterna o establece si una unidad Qi Adept tiene activa su postura de Guardia en Cadena."""
        if nombre not in self.fichas:
            return False
        ficha = self.fichas[nombre]
        if nuevo_estado is not None:
            ficha.chain_guard_activo = bool(nuevo_estado)
        else:
            ficha.chain_guard_activo = not ficha.chain_guard_activo
        return True

    # ── Refuerzos ────────────────────────────────────────────────────────

    def programar_refuerzos(self, calendario: dict) -> None:
        """Fija el calendario {turno: [unidades]} del capítulo (se usa al cargar el preset)."""
        self.refuerzos_pendientes = {int(t): list(us) for t, us in (calendario or {}).items() if us}
        self.refuerzos_desplegados_ultimo = []

    def refuerzos_previstos(self, turno: Optional[int] = None) -> list:
        """Refuerzos que aparecerán en `turno` (o todos los pendientes, ordenados) — para la UI / análisis."""
        if turno is not None:
            return list(self.refuerzos_pendientes.get(int(turno), []))
        return [dict(u, turno=t) for t in sorted(self.refuerzos_pendientes) for u in self.refuerzos_pendientes[t]]

    def desplegar_refuerzos(self, turno: int) -> list:
        """
        Coloca los refuerzos programados para `turno`. Si su casilla de aparición
        está ocupada, en el juego el refuerzo no aparece ese turno: se pospone al
        siguiente. Devuelve las fichas desplegadas (como_dict).
        """
        pendientes = self.refuerzos_pendientes.pop(int(turno), [])
        if not pendientes:
            self.refuerzos_desplegados_ultimo = []
            return []
        from catalogo_loader import resolver_unidad_con_catalogo
        desplegados, pospuestos = [], []
        ocupadas = {(f.x, f.y) for f in self.fichas.values() if f.viva}
        for u in pendientes:
            if (u["x"], u["y"]) in ocupadas:
                pospuestos.append(u)
                continue
            datos = dict(u)
            # Nombre único si ya existiera una ficha (viva o muerta) con ese nombre
            base = datos["nombre"]
            n = 2
            while datos["nombre"] in self.fichas:
                datos["nombre"] = f"{base} #{n}"
                n += 1
            ficha = resolver_unidad_con_catalogo(datos)
            ficha.es_refuerzo = True
            self.registrar_unidad(ficha, resolver_colision=False)
            ocupadas.add((ficha.x, ficha.y))
            desplegados.append(ficha.como_dict())
        if pospuestos:
            self.refuerzos_pendientes.setdefault(int(turno) + 1, []).extend(pospuestos)
        self.refuerzos_desplegados_ultimo = desplegados
        return desplegados

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
                    # Si el arma equipada es de Emblema, volver a arma regular del inventario
                    if f.arma and (getattr(f.arma, 'es_engage', False) or '(emblema)' in str(f.arma.nombre).lower()):
                        arma_regular = None
                        for it in getattr(f, 'inventario', []):
                            if not it.get('es_engage') and '(emblema)' not in str(it.get('nombre', '')).lower():
                                arma_regular = it
                                break
                        if arma_regular:
                            from catalogo_loader import _arma_desde_item
                            f.arma = _arma_desde_item(arma_regular)
                        else:
                            from motor_calculo import Arma
                            f.arma = Arma("Espada de Hierro", mt=5, wt=5, hit=90, crit=0, es_magica=False, tipo="Espada", rango=[1])
                if f.stats:
                    f.stats.turnos_fusion_restantes = f.turnos_fusion
                    f.stats.en_fusion = f.en_fusion
                    f.stats.energia_emblema = f.energia_emblema
                    f.stats.ataque_emblema_usado = f.ataque_emblema_usado

        # Buffs temporales que caducan al entrar en la fase de jugador (p.ej. Self-Improver)
        for f in self.fichas.values():
            f.purgar_estados_temporales("jugador", self.turno_actual)

        # Fuego (Blazing Lion): quema a los aliados que empiezan el turno encima y se apaga
        self.quemados_ultimo = self.quemar_unidades_en_fuego(es_aliado=True)
        self.apagar_fuego_caducado()
        # Curación de terreno (fuertes, tronos, casillas de recuperación) para los aliados
        self.curados_ultimo = self.curar_unidades_en_terreno(es_aliado=True)

        # Refuerzos enemigos programados para este turno (aparecen al inicio de la fase de jugador)
        self.desplegar_refuerzos(self.turno_actual)

    def iniciar_fase_enemigo(self) -> None:
        """Marca que estamos en la fase de movimiento enemigo y limpia la ruptura de enemigos."""
        self.guardar_snapshot()
        self.fase = "enemigo"
        # Fuego (Blazing Lion): quema a los enemigos que empiezan su fase encima
        self.quemados_ultimo = self.quemar_unidades_en_fuego(es_aliado=False)
        # Curación de terreno para los enemigos que empiezan su fase sobre ella
        self.curados_ultimo = self.curar_unidades_en_terreno(es_aliado=False)
        for f in self.fichas.values():
            f.chain_guard_usado = False
            if not f.es_aliado:
                f.cargas_ruptura = 0
            # Buffs temporales que caducan al entrar en la fase enemiga (p.ej. ¡Ponte detrás de mí!)
            f.purgar_estados_temporales("enemigo", self.turno_actual)

    # ── Serialización ────────────────────────────────────────────────────

    def snapshot(self) -> dict:
        """
        Serializa el estado completo del tablero como JSON.
        Esto es lo que el LLM recibe para contexto.
        """
        return {
            "turno": self.turno_actual,
            "turno_actual": self.turno_actual,
            "fase": self.fase,
            "dificultad": self.dificultad,
            "refuerzos_pendientes": {str(t): list(us) for t, us in sorted(self.refuerzos_pendientes.items())},
            "casillas_fuego": self.casillas_fuego_lista(),
            "aliados": [f.como_dict() for f in self.obtener_aliados()],
            "enemigos": [f.como_dict() for f in self.obtener_enemigos()],
            "fichas": [f.como_dict() for f in self.fichas.values() if f.viva and f.hp_actual > 0]
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
