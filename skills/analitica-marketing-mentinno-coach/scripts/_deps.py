"""Revisa las librerías necesarias antes de correr un análisis.

Se importa primero en cada script. Si falta alguna, muestra un mensaje claro
con el comando de instalación en lugar de un error técnico.
"""
import importlib.util
import sys

REQUERIDAS = {
    "pandas": "pandas",
    "numpy": "numpy",
    "scipy": "scipy",
    "statsmodels": "statsmodels",
    "sklearn": "scikit-learn",
}


def _faltan():
    return [pip for mod, pip in REQUERIDAS.items() if importlib.util.find_spec(mod) is None]


_f = _faltan()
if _f:
    sys.stderr.write(
        "Faltan librerías para este análisis: " + ", ".join(_f) + ".\n"
        "Instálalas con:\n"
        "  pip install --break-system-packages " + " ".join(_f) + "\n"
        "y vuelve a ejecutar el mismo comando.\n"
    )
    sys.exit(3)
