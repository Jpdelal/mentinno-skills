"""Utilidades compartidas. Lectura de tablas, fechas, intervalos y salida limpia."""
import json
import math
import os
import warnings

import numpy as np
import pandas as pd


def load_table(path, sheet=None):
    p = str(path).lower()
    if p.endswith((".xlsx", ".xlsm", ".xls")):
        try:
            return pd.read_excel(path, sheet_name=sheet if sheet is not None else 0)
        except ImportError:
            raise SystemExit("Para leer Excel falta la librería openpyxl. Instálala con: pip install --break-system-packages openpyxl (o guarda el archivo como CSV).")
    if p.endswith(".tsv"):
        return pd.read_csv(path, sep="\t", encoding_errors="replace")
    return pd.read_csv(path, sep=None, engine="python", encoding_errors="replace")


def parse_dates(s, mdy=False):
    """Convierte a fecha. En formatos con barra asume dia/mes/anio salvo mdy=True."""
    if pd.api.types.is_datetime64_any_dtype(s):
        return s
    txt = s.astype(str)
    slash = txt.str.contains("/", regex=False).mean() > 0.5
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return pd.to_datetime(s, errors="coerce", dayfirst=bool(slash and not mdy))


def wilson(k, n, z=1.96):
    if n <= 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def need_cols(df, cols):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise SystemExit(
            "No encuentro estas columnas: %s. Columnas disponibles: %s"
            % (missing, list(df.columns))
        )


def _clean(o):
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        v = float(o)
        return None if (math.isnan(v) or math.isinf(v)) else round(v, 6)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return _clean(o.tolist())
    if isinstance(o, (pd.Timestamp,)):
        return o.strftime("%Y-%m-%d")
    return o


def emit(result, out, resumen_key="resumen"):
    """Guarda el detalle completo en JSON e imprime solo el resumen (ahorra tokens)."""
    out = os.path.abspath(out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    clean = _clean(result)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=1)
    print(json.dumps({"archivo_completo": out, **clean[resumen_key]}, ensure_ascii=False, indent=1))


def semaforo(nivel):
    return {
        "verde": "Puedes decidir con esto.",
        "amarillo": "Decide con cautela y valida con una prueba pequeña.",
        "rojo": "No decidas solo con esto. Sirve como hipótesis.",
    }[nivel]
