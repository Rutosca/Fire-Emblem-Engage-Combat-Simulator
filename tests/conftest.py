"""Compatibilidad para la suite existente que inspecciona el tablero directamente."""

from app import app


# Los tests históricos importan ``tablero`` y lo manipulan fuera de una petición.
# En producción cada navegador recibe una partida aislada; aquí conservamos el
# tablero de pruebas compartido y determinista.
app.config["TESTING"] = True
