#!/usr/bin/env python3
"""Perfila una base de datos y dice qué análisis es defendible con ella.

Uso: python3 profile_data.py archivo.csv [--hoja NOMBRE] [--out salida.json]
"""
import argparse
import re

import _deps  # noqa: F401  (revisa librerías)
import numpy as np
import pandas as pd

from _utils import emit, load_table, parse_dates

SPEND = re.compile(r"(gasto|inversi|spend|cost|presupuesto|budget|invest|inv_)", re.I)
ID = re.compile(r"(^id$|_id$|^id_|cliente|customer|usuario|user|correo|email|codigo|sku|pedido|order)", re.I)
DATE = re.compile(r"(fecha|date|dia|day|semana|week|mes|month|periodo|period)", re.I)
AMOUNT = re.compile(r"(monto|importe|total|venta|revenue|amount|ingreso|valor|precio)", re.I)
FUNNEL = re.compile(r"(impresi|alcance|click|clic|visita|sesion|session|lead|registro|carrito|cart|checkout|compra|purchase|conversi)", re.I)


def role_of(name, s, n):
    nn = s.dropna()
    if nn.empty:
        return "vacia"
    if pd.api.types.is_numeric_dtype(s):
        vals = set(nn.unique().tolist())
        if len(vals) <= 2 and vals <= {0, 1, 0.0, 1.0}:
            return "binaria"
        if SPEND.search(name) or AMOUNT.search(name):
            return "numerica"
        if ID.search(name) and nn.nunique() > 0.5 * n:
            return "id"
        return "numerica"
    if pd.api.types.is_datetime64_any_dtype(s):
        return "fecha"
    sample = nn.astype(str).head(300)
    if sample.str.match(r"^\d{1,4}[-/.]\d{1,2}([-/.]\d{1,4})?").mean() > 0.8:
        d = parse_dates(sample)
        if d.notna().mean() > 0.8:
            return "fecha"
    if ID.search(name) and nn.nunique() > 20 and nn.nunique() > 0.01 * n:
        return "id"
    if nn.nunique() <= 50:
        return "categoria"
    return "texto"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--hoja")
    ap.add_argument("--out", default="perfil_datos.json")
    ap.add_argument("--mdy", action="store_true", help="fechas mes/dia/anio")
    a = ap.parse_args()

    df = load_table(a.file, a.hoja)
    n, p = df.shape
    cols, issues = {}, []
    for c in df.columns:
        r = role_of(str(c), df[c], n)
        cols[c] = {"rol": r, "vacios_pct": round(100 * df[c].isna().mean(), 1)}
        if r == "fecha":
            df[c] = parse_dates(df[c], a.mdy)
    dup = int(df.duplicated().sum())
    if dup:
        issues.append("%d filas duplicadas (%.1f%%)" % (dup, 100 * dup / n))
    worst_nulls = [c for c, v in cols.items() if v["vacios_pct"] > 20]
    if worst_nulls:
        issues.append("Columnas con más de 20%% de vacíos: %s" % worst_nulls)

    # fechas
    fechas = [c for c, v in cols.items() if v["rol"] == "fecha"]
    freq, n_per, gaps_pct, fcol = None, None, 0.0, None
    if fechas:
        fcol = max(fechas, key=lambda c: df[c].nunique())
        u = df[fcol].dropna().drop_duplicates().sort_values()
        n_per = len(u)
        if n_per > 2:
            d = u.diff().dt.days.dropna()
            med = d.median()
            freq = "diaria" if med <= 1.5 else "semanal" if 5 <= med <= 9 else "mensual" if 25 <= med <= 35 else "irregular"
            gaps_pct = round(100 * (d > 1.5 * med).mean(), 1)
            if gaps_pct > 10:
                issues.append("Hay saltos en el calendario en %.0f%% de los periodos" % gaps_pct)

    # atipicos y negativos
    for c, v in cols.items():
        if v["rol"] == "numerica":
            x = df[c].dropna()
            if len(x) > 20 and x.std() == 0:
                issues.append("%s no varía (valor constante)" % c)
            q1, q3 = x.quantile([0.25, 0.75])
            iqr = q3 - q1
            if iqr > 0:
                out = ((x < q1 - 3 * iqr) | (x > q3 + 3 * iqr)).mean()
                if out > 0.02:
                    issues.append("%s tiene %.1f%% de valores extremos" % (c, 100 * out))
            if (AMOUNT.search(str(c)) or SPEND.search(str(c))) and (x < 0).any():
                issues.append("%s tiene valores negativos (¿devoluciones o errores?)" % c)

    # nota de calidad
    score = 100
    if n < 100:
        score -= 30
    elif n < 300:
        score -= 10
    if worst_nulls:
        score -= 20
    if dup / max(n, 1) > 0.05:
        score -= 10
    if gaps_pct > 10:
        score -= 10
    score -= 5 * min(len([i for i in issues if "extremos" in i or "negativos" in i or "constante" in i]), 3)
    calidad = "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 50 else "D"

    alcance = {}
    ids = [c for c, v in cols.items() if v["rol"] == "id"]
    montos = [c for c, v in cols.items() if v["rol"] == "numerica" and AMOUNT.search(str(c))]
    cli = [c for c in ids if re.search(r"(cliente|customer|usuario|user|correo|email)", str(c), re.I)]
    rep = [c for c in ids if df[c].nunique() < 0.9 * n]
    if ids and fechas and montos and (cli or rep):
        idc = (cli or rep)[0]
        nc = df[idc].nunique()
        est = "listo" if nc >= 1000 else "limitado" if nc >= 200 else "limitado"
        alcance["clientes_RFM"] = {"estado": est, "clientes": int(nc), "columnas_sugeridas": {"cliente": idc, "fecha": fcol, "monto": montos[0]},
                                   "nota": "Con menos de 1000 clientes se usan 3 niveles en lugar de 5."}
    fun = [c for c, v in cols.items() if v["rol"] == "numerica" and FUNNEL.search(str(c))]
    if len(fun) >= 2:
        alcance["embudo"] = {"estado": "listo", "etapas_candidatas": fun}
    spend = [c for c, v in cols.items() if v["rol"] == "numerica" and SPEND.search(str(c))]
    if fcol and len(spend) >= 2 and n_per:
        thr = {"semanal": (104, 52), "mensual": (36, 24), "diaria": (500, 300)}.get(freq, (104, 52))
        est = "listo" if n_per >= thr[0] else "limitado" if n_per >= thr[1] else "no_viable"
        flags = []
        for c in spend:
            x = df.groupby(fcol)[c].sum()
            if x.mean() > 0 and x.std() / x.mean() < 0.15:
                flags.append("%s casi no varía en el tiempo" % c)
        if len(spend) > 1:
            cm = df.groupby(fcol)[spend].sum().corr().abs().values
            if (np.triu(cm, 1) > 0.85).any():
                flags.append("hay canales que se mueven casi igual y no se podrán separar")
        alcance["mezcla_de_medios_MMM"] = {"estado": est, "periodos": int(n_per), "frecuencia": freq, "canales": spend, "alertas": flags,
                                           "nota": "Sin experimentos para calibrar, la confianza máxima es media."}
    nums = [c for c, v in cols.items() if v["rol"] == "numerica"]
    if len(nums) >= 3:
        maxp = max(1, n // 15)
        alcance["relacion_y_prediccion_regresion"] = {"estado": "listo" if n >= 60 else "limitado", "filas": n, "variables_maximas_recomendadas": maxp}
    bins = [c for c, v in cols.items() if v["rol"] == "binaria"]
    for b in bins[:3]:
        ev = int(min(df[b].sum(), n - df[b].sum()))
        alcance["resultado_si_no_%s" % b] = {"estado": "listo" if ev >= 100 else "limitado" if ev >= 30 else "no_viable", "casos_del_grupo_menor": ev,
                                              "variables_maximas_recomendadas": max(1, ev // 10)}

    resumen = {"filas": n, "columnas": p, "calidad_datos": calidad, "puntaje": score,
               "periodos_y_frecuencia": [n_per, freq], "problemas": issues or ["Sin problemas graves detectados"],
               "alcances_posibles": alcance,
               "columnas_por_rol": {r: [c for c, v in cols.items() if v["rol"] == r] for r in sorted({v["rol"] for v in cols.values()})}}
    emit({"resumen": resumen, "columnas": cols}, a.out)


if __name__ == "__main__":
    main()
