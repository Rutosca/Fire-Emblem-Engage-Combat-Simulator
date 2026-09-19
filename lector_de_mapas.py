import json
import os
import base64
import zlib
import struct
from dataclasses import dataclass
from typing import List, Optional

_ruta_catalogo_json = os.path.join(os.path.dirname(__file__), "json", "catalogo_engage.json")
_ruta_catalogo = _ruta_catalogo_json if os.path.exists(_ruta_catalogo_json) else os.path.join(os.path.dirname(__file__), "catalogo_engage.json")
_CANONICO_TERRENOS = {}
if os.path.exists(_ruta_catalogo):
    try:
        with open(_ruta_catalogo, "r", encoding="utf-8") as f:
            _terrenos_raw = json.load(f).get("terrenos", {})
        for _tid, _info in _terrenos_raw.items():
            _CANONICO_TERRENOS[_tid.lower()] = _info
            if _info.get("nombre"):
                _CANONICO_TERRENOS[_info["nombre"].lower()] = _info
    except Exception:
        pass

# Tiled usa los 3 bits más significativos de cada GID para indicar
# transformaciones (flip horizontal, vertical y diagonal/rotación 90°).
# Hay que eliminarlos antes de buscar propiedades de terreno.
FLIP_MASK = 0x1FFFFFFF


def _props_a_dict(props) -> dict:
    """Propiedades de Tiled → dict. Admite lista [{name, value}] (>=1.2) o dict {name: value} (1.1)."""
    if isinstance(props, dict):
        return dict(props)
    return {p['name']: p['value'] for p in (props or [])}

# Asumimos que Terreno viene de nuestro motor_calculo_engage.py
@dataclass
class Terreno:
    nombre: str = "Llanura"
    caminable: bool = True
    volable: bool = True
    avo: int = 0
    dfn: int = 0
    coste_mov: int = 1
    curacion_turno: int = 0       # HP recuperados por turno (ej. +10 en casillas de curación)
    es_antirruptura: bool = False  # Inmunidad a Ruptura (Break) al defender en esta casilla
    es_recarga_emblema: bool = False # Recarga inmediata de energía de Emblema (Fusión al 100%)
    es_fuego: bool = False         # Terreno en llamas (Blazing Lion): daño al empezar la fase y coste de movimiento +1
    # Objetivo de mapa asociado a la casilla (independiente del terreno físico):
    #   "derrota"  → si un ENEMIGO termina su movimiento aquí, se pierde el mapa (Cap. 8: "toman tu posición")
    #   "victoria" → si un ALIADO termina aquí, se gana el mapa (mapas de "llega a X")
    # Se marca en Tiled con la propiedad de tile `objetivo` en una capa aparte
    # sobre el terreno; el cargador la fusiona sin sobreescribir avo/dfn/etc.
    objetivo: str = ""



# Tipos (campo "Clase"/type de Tiled) de los objetos de mapa con estado, en minúsculas.
# Todo lo que no esté aquí se trata como spawn de unidad (Aliado / Enemigo / Lord...).
#   arma_usable      → ballesta, cañón, cañón mágico: lo usa una unidad que cumpla los
#                      requisitos (p.ej. puede_usar_ballesta) y tiene `usos`.
#   destructible     → cajas, muros rompibles: bloquean sus casillas hasta ser destruidos
#                      (todas a la vez, aunque ocupen varias).
#   recarga_emblema  → pozo de Emblema: recarga al 100% y desaparece al usarse.
TIPOS_OBJETO_MAPA = {"arma_usable", "destructible", "recarga_emblema"}

# `tipo` del tile (tileset) → clase de objeto de mapa. Permite colocar objetos-tile
# en Tiled sin rellenar la clase a mano: las propiedades viven en el tileset.
_TIPO_TILE_A_CLASE = {
    "recarga": "recarga_emblema", "pozo": "recarga_emblema", "emblema": "recarga_emblema",
    "ballesta": "arma_usable", "cañon": "arma_usable", "canon": "arma_usable",
    "cañon_magico": "arma_usable", "canon_magico": "arma_usable", "arma_usable": "arma_usable",
    "valla": "destructible", "caja": "destructible", "barril": "destructible",
    "muro_rompible": "destructible", "destructible": "destructible",
}


def clasificar_objeto_por_props(props: dict) -> str:
    """Clase de objeto de mapa deducida de sus propiedades ('' si no es un objeto de mapa)."""
    if not props:
        return ""
    if props.get("destructible") is True:
        return "destructible"
    return _TIPO_TILE_A_CLASE.get(str(props.get("tipo", "")).lower(), "")


@dataclass
class EntidadMapa:
    """Representa una unidad, cofre o ballesta colocada en la Capa de Objetos de Tiled."""
    id_entidad: str
    nombre: str
    tipo: str  # ej: "Aliado", "Enemigo", "Arma_Usable", "Destructible", "Recarga_Emblema"
    x: int
    y: int
    propiedades: dict
    ancho: int = 1   # tamaño en casillas (los destructibles suelen ocupar 2 o más)
    alto: int = 1

    @property
    def es_objeto_mapa(self) -> bool:
        return str(self.tipo).lower() in TIPOS_OBJETO_MAPA

    @property
    def casillas(self) -> List[tuple]:
        """Todas las casillas que ocupa el objeto."""
        return [(self.x + dx, self.y + dy) for dx in range(self.ancho) for dy in range(self.alto)]

    def como_dict(self) -> dict:
        return {
            "id": self.id_entidad, "nombre": self.nombre, "tipo": self.tipo,
            "x": self.x, "y": self.y, "ancho": self.ancho, "alto": self.alto,
            "casillas": self.casillas, "propiedades": self.propiedades,
        }

class MapaTactico:
    """
    Carga un mapa exportado en JSON desde Tiled y crea una cuadrícula (grid) 2D
    accesible mediante coordenadas (x, y).
    """
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.ancho = 0
        self.alto = 0
        self.grid: List[List[Terreno]] = []
        self.es_datamine = False
        self.cid: Optional[str] = None
        self.dispos_id: Optional[str] = None
        self.terrain_id: Optional[str] = None
        self.entidades: List[EntidadMapa] = []
        self.propiedades_mapa: dict = {}
        self._cargar_mapa()

    def casillas_objetivo(self, objetivo: Optional[str] = None) -> List[tuple]:
        """[(x, y, objetivo), ...] de las casillas marcadas; filtra por 'derrota' / 'victoria' si se indica."""
        return [
            (x, y, self.grid[x][y].objetivo)
            for x in range(self.ancho) for y in range(self.alto)
            if self.grid[x][y].objetivo and (objetivo is None or self.grid[x][y].objetivo == objetivo)
        ]

    def casillas_derrota(self) -> List[tuple]:
        """Casillas que, ocupadas por un enemigo al final de su movimiento, hacen perder el mapa."""
        return [(x, y) for x, y, _ in self.casillas_objetivo("derrota")]

    def casillas_victoria(self) -> List[tuple]:
        """Casillas que, ocupadas por un aliado, hacen ganar el mapa."""
        return [(x, y) for x, y, _ in self.casillas_objetivo("victoria")]

    def _init_llanuras(self, ancho: int, alto: int):
        """Inicializa el grid con Terreno generico de llanura."""
        self.ancho = ancho
        self.alto = alto
        self.grid = [[Terreno() for _ in range(self.alto)] for _ in range(self.ancho)]

    def _cargar_datamine(self, data: dict):
        """
        Lee un JSON generado por generar_mapas.py (formato datamine).
        Almacena la metadata del capitulo como atributos de instancia y crea
        un grid de llanuras. Las dimensiones reales del mapa no estan en el
        datamine, asi que usamos un placeholder hasta que se integre Terrain.xml.
        """
        self.cid = data.get("cid")
        self.dispos_id = data.get("dispos_id")
        self.terrain_id = data.get("terrain_id")
        self.field_id = data.get("field_id")
        self.script_bmap = data.get("script_bmap")
        self.nivel = data.get("nivel_recomendado", 1)
        self.nombre_en = data.get("nombre_en")
        self.nombre_japones = data.get("nombre_japones")
        self.siguiente = data.get("siguiente_capitulo")
        self.nacion = data.get("nacion")
        self.entorno = data.get("entorno_sonido")
        self.flag = data.get("flag", 0)
        self.gmap_spot = data.get("gmap_spot")
        self.es_datamine = True

        # Placeholder: grid 24x17 (dimensiones del cap7 original)
        self._init_llanuras(24, 17)
        print(f"[Datamine] Mapa cargado: {self.cid} ({self.nombre_en}) | dispos: {self.dispos_id}")

    def _cargar_mapa(self):
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            print(f"Aviso: No se encontro el archivo {self.filepath}. Usando mapa de llanuras.")
            self._init_llanuras(16, 24)
            return

        # -----------------------------------------------------------------------
        # Formato DATAMINE (generado por generar_mapas.py)
        # -----------------------------------------------------------------------
        if "cid" in data:
            self._cargar_datamine(data)
            return

        # -----------------------------------------------------------------------
        # Formato TILED (legacy)
        # -----------------------------------------------------------------------
        self.ancho = data['width']
        self.alto = data['height']
        
        # 1. Extraer las propiedades de TODOS los Tilesets
        # Tiled puede exportar en dos formatos segun la version:
        #   - Moderno (>=1.2): tilesets -> tiles[] -> properties[]
        #   - Legacy  (1.1):   tilesets -> tileproperties {id_str: {key: val}}
        # Soportamos ambos.
        propiedades_tiles = {}
        for tileset in data.get('tilesets', []):
            primer_gid = tileset.get('firstgid', 1)

            # Formato MODERNO: array "tiles" con lista "properties".
            # Algunas exportaciones (Tiled 1.1 con metadatos extra) guardan "tiles"
            # como dict {id_str: {...}} sin propiedades: se normaliza a lista.
            tiles_ts = tileset.get('tiles', [])
            if isinstance(tiles_ts, dict):
                tiles_ts = [{'id': int(k), **(v if isinstance(v, dict) else {})} for k, v in tiles_ts.items()]
            for tile in tiles_ts:
                tile_id = tile['id'] + primer_gid
                props_dict = _props_a_dict(tile.get('properties', []))
                if props_dict:
                    propiedades_tiles[tile_id] = props_dict

            # Formato LEGACY: dict "tileproperties" con {id_str: {key: val}}
            for id_str, props_dict in tileset.get('tileproperties', {}).items():
                tile_id = int(id_str) + primer_gid
                # El formato legacy ya tiene valores Python nativos (bool, int, str)
                if tile_id not in propiedades_tiles:  # el formato moderno tiene prioridad
                    propiedades_tiles[tile_id] = dict(props_dict)
        # 2. Leer las capas del mapa (Tile Layers y Object Layers)
        capas_terreno = [layer for layer in data['layers'] if layer['type'] == 'tilelayer']
        capas_objetos = [layer for layer in data['layers'] if layer['type'] == 'objectgroup']
        
        if not capas_terreno:
            raise ValueError("El JSON no contiene una capa de tiles (tilelayer).")

        # 3. Construir la cuadrícula 2D (Array de Columnas x Filas)
        # Inicializamos todo con terreno básico (por si hay casillas vacías en Tiled)
        self.grid = [[Terreno() for _ in range(self.alto)] for _ in range(self.ancho)]
        
        # Iteramos sobre TODAS las capas de terreno de abajo a arriba (orden de Tiled)
        # Si pones un 'Muro' en la Capa 2 sobre una 'Llanura' de la Capa 1, el Muro sobreescribe la Llanura.
        for capa in capas_terreno:
            datos_1d = capa['data']

            # ¡NUEVO! Descompresión de datos si vienen en base64+zlib (Exportación de Tiled)
            if capa.get('encoding') == 'base64':
                decoded_data = base64.b64decode(datos_1d)
                if capa.get('compression') == 'zlib':
                    decompressed_data = zlib.decompress(decoded_data)
                    # Convertir bytes a array de enteros de 32 bits (formato interno de Tiled)
                    formato = f"<{len(decompressed_data) // 4}I"
                    datos_1d = struct.unpack(formato, decompressed_data)
                else:
                    raise ValueError("Formato de compresión no soportado. Usa zlib.")

            for i, gid_raw in enumerate(datos_1d):
                # Eliminamos los bits de flip (H/V/diagonal) que Tiled puede poner
                # en los 3 bits más significativos del GID de 32 bits.
                # Sin esta máscara, un tile volteado nunca encontraría sus propiedades.
                gid = gid_raw & FLIP_MASK
                # gid 0 significa "vacío/transparente" en esta capa, así que lo ignoramos
                if gid == 0:
                    continue
                    
                x = i % self.ancho
                y = i // self.ancho
                
                # Si el gid tiene propiedades personalizadas (nuestros stats tácticos), las aplicamos
                if gid in propiedades_tiles:
                    props = propiedades_tiles[gid]

                    # Tile de capa "objetivos": solo marca la casilla, conserva el terreno de debajo.
                    # Admite `tipo=objetivo` + `condicion=derrota|victoria` (convención de los mapas)
                    # o directamente `objetivo=derrota|victoria`.
                    tipo_prop = str(props.get('tipo', '')).lower()
                    if tipo_prop == 'objetivo' or ('objetivo' in props and 'tipo' not in props):
                        self.grid[x][y].objetivo = str(props.get('condicion', props.get('objetivo', ''))).lower()
                        continue

                    tipo_nombre = str(props.get('tipo', 'Desconocido')).lower()
                    tid_nombre = str(props.get('tid', '')).lower()
                    name_nombre = str(props.get('name', '')).lower()

                    # Consulta a datos canónicos de Engage (Terrain.xml extraído)
                    t_canon = _CANONICO_TERRENOS.get(tipo_nombre) or _CANONICO_TERRENOS.get(tid_nombre) or _CANONICO_TERRENOS.get(name_nombre)
                    if not t_canon and _CANONICO_TERRENOS:
                        for k, v in _CANONICO_TERRENOS.items():
                            if k.lower() in (tipo_nombre, tid_nombre, name_nombre):
                                t_canon = v
                                break

                    # Defaults automáticos de Engage según el tipo si no están explícitos.
                    #   baluarte (curación/fortaleza/trono): +30 Avo, +10 HP/turno, antirruptura
                    #   evasion: solo +30 Avo (sin curación ni antirruptura). Los voladores
                    #   no reciben bonos de terreno: lo aplica motor_calculo, no el mapa.
                    es_baluarte = tipo_nombre in ('curacion', 'fortaleza', 'trono', 'baluarte', 'tiledefense')
                    es_evasion = tipo_nombre in ('evasion', 'evasión')
                    def_avo = t_canon.get('avoid', 30 if (es_baluarte or es_evasion) else 0) if t_canon else (30 if (es_baluarte or es_evasion) else props.get('avo', 0))
                    def_dfn = t_canon.get('defense', 0) if t_canon else ((2 if tipo_nombre == 'trono' else 0) if es_baluarte else props.get('dfn', 0))
                    def_curacion = t_canon.get('heal_turno', 10 if es_baluarte else 0) if t_canon else (10 if es_baluarte else props.get('curacion_turno', 0))
                    def_antirruptura = t_canon.get('es_antirruptura', es_baluarte) if t_canon else (es_baluarte or props.get('es_antirruptura', False))
                    # evasion: coste +1 (como el fuego). Los voladores no lo pagan: el
                    # analizador de movimiento les cobra siempre 1.
                    def_coste = t_canon.get('coste_mov', 1) if t_canon else props.get('coste_mov', 2 if es_evasion else 1)
                    def_recarga = tipo_nombre in ('recarga', 'emblema', 'pozo_energia') or props.get('es_recarga_emblema', False)

                    self.grid[x][y] = Terreno(
                        nombre=props.get('tipo', t_canon.get('nombre', 'Desconocido') if t_canon else 'Desconocido'),
                        caminable=props.get('caminable', not t_canon.get('combate_prohibido', False) if t_canon else True),
                        volable=props.get('volable', True),
                        avo=props.get('avo', def_avo),
                        dfn=props.get('dfn', def_dfn),
                        coste_mov=props.get('coste_mov', def_coste),
                        curacion_turno=props.get('curacion_turno', def_curacion),
                        es_antirruptura=props.get('es_antirruptura', def_antirruptura),
                        es_recarga_emblema=props.get('es_recarga_emblema', def_recarga),
                        # Un tile puede llevar tipo y objetivo a la vez (p.ej. trono + victoria);
                        # si el objetivo ya venía de una capa inferior, se conserva.
                        objetivo=str(props.get('objetivo', self.grid[x][y].objetivo or '')).lower(),
                    )

        # 3b. Condiciones globales del mapa (Tiled: Mapa → Propiedades personalizadas),
        # p.ej. victoria="derrotar_jefe", derrota="alear_muere;posicion_tomada", turnos_limite=15
        self.propiedades_mapa = _props_a_dict(data.get('properties', []))

        # 4. Leer entidades/objetos (Spawns, Cofres, Ballestas, Destructibles, Pozos de Emblema)
        for capa_obj in capas_objetos:
            for obj in capa_obj.get('objects', []):
                # Tiled guarda x,y en píxeles. Convertimos a coordenadas de la cuadrícula
                tile_w = data.get('tilewidth', 32)
                tile_h = data.get('tileheight', 32)

                grid_x = int(obj['x'] // tile_w)
                # Los objetos-tile (con gid) tienen el origen en la esquina INFERIOR
                # izquierda; los rectángulos, en la superior izquierda.
                if obj.get('gid'):
                    grid_y = int((obj['y'] - obj.get('height', 0)) // tile_h)
                else:
                    grid_y = int(obj['y'] // tile_h)

                # Huella en casillas (un rectángulo de 64x32 px sobre tiles de 32 = 2x1)
                ancho_t = max(1, int(round(obj.get('width', tile_w) / tile_w)))
                alto_t = max(1, int(round(obj.get('height', tile_h) / tile_h)))

                # Propiedades: las del tile del tileset (si es un objeto-tile) como base,
                # y las propias del objeto encima (p.ej. `usos` distinto en cada ballesta).
                gid_obj = (obj.get('gid') or 0) & FLIP_MASK
                props_obj = dict(propiedades_tiles.get(gid_obj, {})) if gid_obj else {}
                props_obj.update(_props_a_dict(obj.get('properties', [])))

                # Tiled >= 1.9 llama "class" a lo que antes era "type"; si el objeto no
                # trae clase, se deduce del `tipo` del tile (convención de los mapas).
                tipo_obj = obj.get('type') or obj.get('class') or clasificar_objeto_por_props(props_obj) or 'Generico'
                nombre_obj = obj.get('name') or str(props_obj.get('tipo', tipo_obj)).capitalize()

                self.entidades.append(EntidadMapa(
                    id_entidad=str(obj.get('id', '')),
                    nombre=nombre_obj,
                    tipo=tipo_obj,
                    x=grid_x,
                    y=grid_y,
                    propiedades=props_obj,
                    ancho=ancho_t,
                    alto=alto_t,
                ))

        # 5. Guardar el terreno base bajo cada objeto de mapa para poder
        # aplicar/retirar sus efectos (bloqueo, recarga) según su estado.
        import copy as _copy
        self._terreno_base = {}
        for ent in self.objetos_mapa():
            for (cx, cy) in ent.casillas:
                if 0 <= cx < self.ancho and 0 <= cy < self.alto and (cx, cy) not in self._terreno_base:
                    self._terreno_base[(cx, cy)] = _copy.copy(self.grid[cx][cy])
        # Por defecto todos los objetos están activos
        self.aplicar_objetos({ent.id_entidad: {"activo": True} for ent in self.objetos_mapa()})

    def objetos_mapa(self) -> List[EntidadMapa]:
        """Entidades de la capa de objetos que NO son unidades (ballestas, destructibles, pozos)."""
        return [e for e in self.entidades if e.es_objeto_mapa]

    def objeto_en(self, x: int, y: int, tipo: Optional[str] = None) -> Optional[EntidadMapa]:
        """Objeto de mapa (opcionalmente de un tipo) que ocupa la casilla (x, y)."""
        for ent in self.objetos_mapa():
            if (x, y) in ent.casillas and (tipo is None or str(ent.tipo).lower() == tipo.lower()):
                return ent
        return None

    def aplicar_fuego(self, casillas) -> None:
        """
        Prende (o refresca) el fuego temporal de Blazing Lion en `casillas`: guarda el
        terreno base y marca la casilla como en llamas (coste de movimiento +1).
        `limpiar_fuego` restaura el terreno original.
        """
        import copy as _copy
        from ataques_area import FUEGO_COSTE_EXTRA
        if not hasattr(self, '_terreno_base_fuego'):
            self._terreno_base_fuego = {}
        for (x, y) in casillas:
            if not (0 <= x < self.ancho and 0 <= y < self.alto):
                continue
            if (x, y) not in self._terreno_base_fuego:
                self._terreno_base_fuego[(x, y)] = _copy.copy(self.grid[x][y])
            t = self.grid[x][y]
            t.es_fuego = True
            t.nombre = "Fuego"
            t.coste_mov = int(self._terreno_base_fuego[(x, y)].coste_mov) + FUEGO_COSTE_EXTRA

    def limpiar_fuego(self, casillas=None) -> None:
        """Apaga el fuego de `casillas` (todas si None) devolviendo el terreno base."""
        import copy as _copy
        base = getattr(self, '_terreno_base_fuego', {})
        claves = list(base.keys()) if casillas is None else [tuple(c) for c in casillas if tuple(c) in base]
        for (x, y) in claves:
            self.grid[x][y] = _copy.copy(base.pop((x, y)))

    def aplicar_objetos(self, estados: dict) -> None:
        """
        Proyecta sobre el grid el efecto de cada objeto según su estado
        (`estados[id] = {"activo": bool, ...}`, mantenido por EstadoTablero):
          - destructible activo    → sus casillas no son transitables (ni volables salvo
                                     que el objeto diga volable=True). Destruido → terreno base.
          - recarga_emblema activo → es_recarga_emblema en sus casillas. Usado → terreno base.
          - arma_usable            → no altera el terreno (es una acción, no un obstáculo).
        """
        import copy as _copy
        base = getattr(self, '_terreno_base', {})
        for (cx, cy), t_base in base.items():
            self.grid[cx][cy] = _copy.copy(t_base)
        for ent in self.objetos_mapa():
            activo = bool((estados.get(ent.id_entidad) or {}).get("activo", True))
            if not activo:
                continue
            tipo_l = str(ent.tipo).lower()
            for (cx, cy) in ent.casillas:
                if not (0 <= cx < self.ancho and 0 <= cy < self.alto):
                    continue
                t = self.grid[cx][cy]
                if tipo_l == "destructible":
                    t.caminable = bool(ent.propiedades.get("caminable", False))
                    t.volable = bool(ent.propiedades.get("volable", False))
                    t.nombre = str(ent.propiedades.get("nombre_terreno", ent.propiedades.get("tipo", ent.nombre or "Obstáculo"))).capitalize()
                elif tipo_l == "recarga_emblema":
                    t.es_recarga_emblema = True

    def obtener_terreno(self, x: int, y: int) -> Optional[Terreno]:
        """Devuelve las propiedades del terreno en la coordenada dada."""
        if 0 <= x < self.ancho and 0 <= y < self.alto:
            return self.grid[x][y]
        return None

    def es_casilla_valida_para_unidad(self, x: int, y: int, es_volador: bool) -> bool:
        """Verifica si una unidad puede detenerse en esta coordenada."""
        terreno = self.obtener_terreno(x, y)
        if not terreno:
            return False
        return terreno.volable if es_volador else terreno.caminable

if __name__ == "__main__":
    print("Iniciando parser de Tiled...")
    # Prueba simulada. En tu PC usarás: mapa = MapaTactico("mi_mapa_16x24.json")
    mapa = MapaTactico("dummy.json") 
    
    print(f"Mapa cargado: {mapa.ancho}x{mapa.alto} casillas.")
    # Forzamos una casilla de prueba para demostrar cómo lo lee
    mapa.grid[5][5] = Terreno(nombre="Bosque", caminable=True, volable=True, avo=30, coste_mov=2)
    mapa.grid[6][5] = Terreno(nombre="Muro", caminable=False, volable=False)
    mapa.grid[7][5] = Terreno(nombre="Agua Profunda", caminable=False, volable=True)

    test_coords = [(5,5), (6,5), (7,5)]
    print("\n--- ANALISIS TACTICO DEL TERRENO ---")
    for x, y in test_coords:
        t = mapa.obtener_terreno(x, y)
        print(f"Casilla ({x},{y}): {t.nombre}")
        print(f"  - ¿Infantería puede pasar?: {'Sí' if t.caminable else 'No'}")
        print(f"  - ¿Voladores pueden pasar?: {'Sí' if t.volable else 'No'}")
        print(f"  - Bonus Defensivo: +{t.avo} Evasión, +{t.dfn} Defensa\n")