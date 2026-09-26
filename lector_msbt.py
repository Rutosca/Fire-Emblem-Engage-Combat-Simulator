# -*- coding: utf-8 -*-
"""
lector_msbt.py — Lee los ficheros de texto del juego (MSBT) para sacar las traducciones.

El datamine público traía los textos ya convertidos a CSV, pero es anterior al DLC: los
nombres de los Emblemas, armas y habilidades del DLC no están. Los del propio juego sí,
dentro de `fe_assets_message/<region>/<idioma>/*.bytes.bundle`. EngageXml saca el
`.bytes`, que es un MSBT tal cual, y este módulo lo interpreta.

Formato MSBT (Nintendo MessageStudio): cabecera "MsgStdBn" + secciones de 16 bytes de
cabecera cada una. Solo hacen falta dos:
  LBL1  tabla hash de etiquetas (el MID, p.ej. "MSID_Flare") -> índice de cadena
  TXT2  las cadenas, en UTF-16, por índice
El resto (ATR1, TSY1, NLI1…) se ignora.
"""
from __future__ import annotations

import os
import struct

MAGIA = b"MsgStdBn"


def _leer_seccion(datos: bytes, inicio: int):
    """(tipo, cuerpo, siguiente_inicio) de la sección que empieza en `inicio`."""
    tipo = datos[inicio:inicio + 4]
    tam = struct.unpack_from("<I", datos, inicio + 4)[0]
    cuerpo = datos[inicio + 16:inicio + 16 + tam]
    siguiente = inicio + 16 + tam
    siguiente += (-siguiente) % 16          # las secciones van alineadas a 16
    return tipo, cuerpo, siguiente


def _etiquetas(cuerpo: bytes) -> dict:
    """{índice de cadena: etiqueta} a partir de la tabla hash de LBL1."""
    n_grupos = struct.unpack_from("<I", cuerpo, 0)[0]
    salida = {}
    for g in range(n_grupos):
        n_etiquetas, desplazamiento = struct.unpack_from("<II", cuerpo, 4 + g * 8)
        p = desplazamiento
        for _ in range(n_etiquetas):
            largo = cuerpo[p]
            etiqueta = cuerpo[p + 1:p + 1 + largo].decode("ascii", "ignore")
            indice = struct.unpack_from("<I", cuerpo, p + 1 + largo)[0]
            salida[indice] = etiqueta
            p += 1 + largo + 4
    return salida


def _cadenas(cuerpo: bytes, little_endian: bool = True) -> list:
    """Las cadenas de TXT2, ya decodificadas y sin los códigos de control del juego."""
    n = struct.unpack_from("<I", cuerpo, 0)[0]
    desplazamientos = [struct.unpack_from("<I", cuerpo, 4 + i * 4)[0] for i in range(n)]
    desplazamientos.append(len(cuerpo))
    orden = "utf-16-le" if little_endian else "utf-16-be"
    salida = []
    for i in range(n):
        crudo = cuerpo[desplazamientos[i]:desplazamientos[i + 1]]
        texto = crudo.decode(orden, "ignore")
        salida.append(_limpiar(texto))
    return salida


def _limpiar(texto: str) -> str:
    """
    Quita el terminador y los códigos de control. El juego mete etiquetas como
    \\x0e<grupo><tipo><tam>… para iconos, colores y pausas; no son texto visible.
    """
    limpio = []
    i = 0
    while i < len(texto):
        c = texto[i]
        if c == "\x00":
            break
        if c == "\x0e":                      # inicio de etiqueta de control
            if i + 3 < len(texto):
                tam = ord(texto[i + 3])
                i += 4 + tam // 2
                continue
            break
        if c == "\x0f":                      # fin de etiqueta
            i += 3
            continue
        limpio.append(c)
        i += 1
    return "".join(limpio).strip()


def leer(ruta: str) -> dict:
    """{etiqueta: texto} de un .msbt / .bytes. {} si el fichero no es un MSBT válido."""
    try:
        with open(ruta, "rb") as f:
            datos = f.read()
    except OSError:
        return {}
    if not datos.startswith(MAGIA):
        return {}
    little_endian = datos[8:10] == b"\xff\xfe"
    n_secciones = struct.unpack_from("<H", datos, 0x0E)[0]
    etiquetas, cadenas = {}, []
    pos = 0x20
    for _ in range(n_secciones):
        if pos >= len(datos):
            break
        tipo, cuerpo, pos = _leer_seccion(datos, pos)
        if tipo == b"LBL1":
            etiquetas = _etiquetas(cuerpo)
        elif tipo == b"TXT2":
            cadenas = _cadenas(cuerpo, little_endian)
    return {etiqueta: cadenas[i] for i, etiqueta in etiquetas.items()
            if i < len(cadenas) and cadenas[i]}


def leer_carpeta(carpeta: str) -> dict:
    """Junta las traducciones de todos los MSBT de una carpeta."""
    salida = {}
    if not os.path.isdir(carpeta):
        return salida
    for nombre in sorted(os.listdir(carpeta)):
        if nombre.endswith((".msbt", ".bytes")):
            salida.update(leer(os.path.join(carpeta, nombre)))
    return salida
