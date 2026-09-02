import json
import base64
import zlib
import struct
from dataclasses import dataclass
from typing import List, Dict, Optional

# Tiled usa los 3 bits más significativos de cada GID para indicar
# transformaciones (flip horizontal, vertical y diagonal/rotación 90°).
# Hay que eliminarlos antes de buscar propiedades de terreno.
FLIP_MASK = 0x1FFFFFFF

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


@dataclass
class EntidadMapa:
    """Representa una unidad, cofre o ballesta colocada en la Capa de Objetos de Tiled."""
    id_entidad: str
    nombre: str
    tipo: str  # ej: "Aliado", "Enemigo", "Arma_Usable"
    x: int
    y: int
    propiedades: dict

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
        self.entidades: List[EntidadMapa] = [] # LISTA DE SPAWNS Y OBJETOS
        self._cargar_mapa()

    def _cargar_mapa(self):
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            print(f"Error: No se encontro el archivo {self.filepath}")
            # Crear un mapa de llanuras por defecto para pruebas
            self.ancho, self.alto = 16, 24
            self.grid = [[Terreno() for _ in range(self.alto)] for _ in range(self.ancho)]
            return

        self.ancho = data['width']
        self.alto = data['height']
        
        # 1. Extraer las propiedades de TODOS los Tilesets
        # Tiled guarda las propiedades de cada tile en el bloque tilesets -> tiles.
        # Un mapa puede tener múltiples tilesets (terreno base, decoración, objetos…).
        # Cada tileset tiene su propio 'firstgid', por lo que iteramos todos.
        propiedades_tiles = {}
        for tileset in data.get('tilesets', []):
            primer_gid = tileset.get('firstgid', 1)
            for tile in tileset.get('tiles', []):
                tile_id = tile['id'] + primer_gid
                props_dict = {p['name']: p['value'] for p in tile.get('properties', [])}
                propiedades_tiles[tile_id] = props_dict
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
                    tipo_nombre = str(props.get('tipo', 'Desconocido')).lower()

                    # Defaults automáticos de Engage según el tipo si no están explícitos
                    def_avo = 30 if tipo_nombre in ('curacion', 'fortaleza', 'trono') else props.get('avo', 0)
                    def_dfn = 1 if tipo_nombre in ('curacion', 'fortaleza') else (2 if tipo_nombre == 'trono' else props.get('dfn', 0))
                    def_curacion = 10 if tipo_nombre in ('curacion', 'fortaleza', 'trono') else props.get('curacion_turno', 0)
                    def_antirruptura = True if tipo_nombre in ('curacion', 'fortaleza', 'trono') else props.get('es_antirruptura', False)
                    def_recarga = True if tipo_nombre in ('recarga', 'emblema', 'pozo_energia') else props.get('es_recarga_emblema', False)

                    self.grid[x][y] = Terreno(
                        nombre=props.get('tipo', 'Desconocido'),
                        caminable=props.get('caminable', True),
                        volable=props.get('volable', True),
                        avo=props.get('avo', def_avo),
                        dfn=props.get('dfn', def_dfn),
                        coste_mov=props.get('coste_mov', 1),
                        curacion_turno=props.get('curacion_turno', def_curacion),
                        es_antirruptura=props.get('es_antirruptura', def_antirruptura),
                        es_recarga_emblema=props.get('es_recarga_emblema', def_recarga)
                    )

        # 4. Leer entidades/objetos (Spawns, Cofres, Ballestas)
        for capa_obj in capas_objetos:
            for obj in capa_obj.get('objects', []):
                # Tiled guarda x,y en píxeles. Convertimos a coordenadas de la cuadrícula
                tile_w = data.get('tilewidth', 32)
                tile_h = data.get('tileheight', 32)
                
                grid_x = int(obj['x'] // tile_w)
                # Ajuste porque Tiled usa la esquina inferior para algunos objetos
                grid_y = int((obj['y'] - obj.get('height', 0)) // tile_h)
                
                props_obj = {p['name']: p['value'] for p in obj.get('properties', [])}
                
                self.entidades.append(EntidadMapa(
                    id_entidad=str(obj.get('id', '')),
                    nombre=obj.get('name', 'Desconocido'),
                    tipo=obj.get('type', 'Generico'),
                    x=grid_x,
                    y=grid_y,
                    propiedades=props_obj
                ))

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