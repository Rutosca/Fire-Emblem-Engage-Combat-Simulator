# Inicio rápido — FE Engage Tactical Assistant

## Requisitos

- Python 3.11 o superior.
- El datamine local opcional en `FE17-DOC-main/`. No se versiona por tamaño y
  atribución; no debe añadirse a Git. Hace falta para recompilar el catálogo y
  cargar despliegues/refuerzos directamente de los XML del juego.

## Ejecutar la aplicación

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Abre `http://localhost:5000`.

Cada navegador usa una partida independiente en memoria. La UI conserva una copia
local para recuperarse de un reinicio, pero Exportar partida es la forma portable de
guardar una fotografía del tablero.

Para un despliegue estable, define `ENGAGE_SECRET_KEY`; en desarrollo se genera una
clave efímera al arrancar.

## Verificar el proyecto

```powershell
python -m pytest
```

La configuración de pytest limita la recogida a `tests/`, de modo que los scripts
experimentales de `scratch/` no interfieren con la suite.
