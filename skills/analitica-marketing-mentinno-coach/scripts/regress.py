#!/usr/bin/env python3
"""Relaciones y predicción de una cifra de negocio (regresión simple o múltiple).

Uso: python3 regress.py archivo --y ventas --x inversion,descuento,precio [--fecha semana]
        [--palancas inversion,descuento] [--cambio 0.10] [--log] [--escenario "Agresivo:inversion=+30%,descuento=+10%"]
"""
import argparse
import os
import re

import _deps  # noqa: F401  (revisa librerías)
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.diagnostic import het_breuschpagan
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.stattools import durbin_watson

from _utils import emit, load_table, need_cols, parse_dates


def parse_escenario(txt):
    nombre, _, resto = txt.partition(":")
    cambios = {}
    for par in resto.split(","):
        k, _, v = par.partition("=")
        cambios[k.strip()] = float(v.strip().replace("%", "")) / 100.0
    return nombre.strip(), cambios


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--y", required=True)
    ap.add_argument("--x", required=True)
    ap.add_argument("--fecha")
    ap.add_argument("--palancas")
    ap.add_argument("--cambio", type=float, default=0.10)
    ap.add_argument("--log", action="store_true")
    ap.add_argument("--sin-controles", action="store_true", help="no agregar tendencia ni temporada automáticas")
    ap.add_argument("--escenario", action="append", default=[])
    ap.add_argument("--hoja")
    ap.add_argument("--mdy", action="store_true")
    ap.add_argument("--outdir", default="resultados")
    a = ap.parse_args()

    xs = [c.strip() for c in a.x.split(",")]
    df = load_table(a.file, a.hoja)
    need_cols(df, [a.y] + xs + ([a.fecha] if a.fecha else []))
    cols = [a.y] + xs + ([a.fecha] if a.fecha else [])
    d = df[cols].copy()
    if a.fecha:
        d[a.fecha] = parse_dates(d[a.fecha], a.mdy)
        d = d.sort_values(a.fecha)
    for c in [a.y] + xs:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    n0 = len(d)
    d = d.dropna().reset_index(drop=True)
    n, p = len(d), len(xs)
    notas = []
    if n < n0:
        notas.append("Se excluyeron %d filas con datos vacíos." % (n0 - n))

    logx = [c for c in xs if a.log and (d[c] > 0).all()]
    if a.log and (d[a.y] <= 0).any():
        raise SystemExit("Para el modo de elasticidad la variable a explicar debe ser positiva.")
    T = d.copy()
    if a.log:
        T[a.y] = np.log(T[a.y])
        for c in logx:
            T[c] = np.log(T[c])

    ctrl = []
    if a.fecha and not a.sin_controles:
        T["tendencia"] = np.arange(n) / n
        ctrl.append("tendencia")
        med = d[a.fecha].diff().dt.days.median()
        per = 52 if 5 <= med <= 9 else 12 if 25 <= med <= 35 else None
        if per and n >= 2 * per:
            tt = np.arange(n)
            for j in (1, 2):
                T["temp_s%d" % j] = np.sin(2 * np.pi * j * tt / per)
                T["temp_c%d" % j] = np.cos(2 * np.pi * j * tt / per)
                ctrl += ["temp_s%d" % j, "temp_c%d" % j]
            notas.append("Se agregaron controles automáticos de tendencia y temporada para no confundirlos con efectos de tus variables.")
        else:
            notas.append("Se agregó un control automático de tendencia.")
    xm = xs + ctrl

    # 1. Relación simple con cada variable
    cor = []
    for c in xs:
        pe = float(d[[a.y, c]].corr().iloc[0, 1])
        sp = float(d[[a.y, c]].corr(method="spearman").iloc[0, 1])
        cor.append({"variable": c, "correlacion": pe, "correlacion_por_rangos": sp})

    # 2. Modelo
    X = sm.add_constant(T[xm])
    cov = {"cov_type": "HAC", "cov_kwds": {"maxlags": 4}} if a.fecha else {"cov_type": "HC3"}
    mod = sm.OLS(T[a.y], X).fit(**cov)
    ci = mod.conf_int()
    sdx, sdy = T[xm].std(), T[a.y].std()
    coefs = []
    for c in xs:
        co = {"variable": c, "efecto_por_unidad": float(mod.params[c]), "rango_95": [float(ci.loc[c, 0]), float(ci.loc[c, 1])],
              "p_valor": float(mod.pvalues[c]), "peso_relativo": float(mod.params[c] * sdx[c] / sdy) if sdy else None,
              "significativo": bool(mod.pvalues[c] < 0.05)}
        coefs.append(co)
    vif = {}
    if len(xm) > 1:
        Xv = sm.add_constant(T[xm]).values
        vif = {c: float(variance_inflation_factor(Xv, i + 1)) for i, c in enumerate(xm) if c in xs}
    bp = float(het_breuschpagan(mod.resid, X)[1]) if n > p + 5 else None
    dw = float(durbin_watson(mod.resid)) if a.fecha else None

    # 3. Prueba con datos que el modelo no vio
    k = max(int(round(0.2 * n)), 5)
    if a.fecha:
        tr, te = T.iloc[:-k], T.iloc[-k:]
    else:
        idx = np.random.default_rng(42).permutation(n)
        tr, te = T.iloc[idx[k:]], T.iloc[idx[:k]]
    m2 = sm.OLS(tr[a.y], sm.add_constant(tr[xm])).fit()
    pr = m2.predict(sm.add_constant(te[xm], has_constant="add"))
    yt = np.exp(te[a.y]) if a.log else te[a.y]
    yp = np.exp(pr) if a.log else pr
    mape = float(np.mean(np.abs((yt - yp) / yt)) * 100) if (yt != 0).all() else None
    r2_out = float(1 - ((yt - yp) ** 2).sum() / ((yt - yt.mean()) ** 2).sum())

    # 4. Escenarios
    pal = [c.strip() for c in a.palancas.split(",")] if a.palancas else xs
    base_raw = d[xs].iloc[-4:].mean() if a.fecha else d[xs].mean()
    for c in ctrl:
        base_raw[c] = T[c].iloc[-4:].mean()

    def predecir(raw_row):
        r = raw_row.copy()
        for c in logx:
            r[c] = np.log(r[c])
        ex = pd.DataFrame([r[xm].values], columns=xm)
        ex.insert(0, "const", 1.0)
        pg = mod.get_prediction(ex)
        f95, f80 = pg.summary_frame(alpha=0.05), pg.summary_frame(alpha=0.20)
        g = (lambda v: float(np.exp(v))) if a.log else float
        return {"estimado": g(f95["mean"].iloc[0]), "rango_80": [g(f80["obs_ci_lower"].iloc[0]), g(f80["obs_ci_upper"].iloc[0])],
                "rango_95": [g(f95["obs_ci_lower"].iloc[0]), g(f95["obs_ci_upper"].iloc[0])]}

    esc = {"Base (situación actual)": predecir(base_raw)}
    for nom, sg in (("Prudente", -a.cambio), ("Optimista", a.cambio)):
        r = base_raw.copy()
        for c in pal:
            r[c] = r[c] * (1 + sg)
        esc["%s (%+.0f%% en %s)" % (nom, 100 * sg, ", ".join(pal))] = predecir(r)
    for txt in a.escenario:
        nom, ch = parse_escenario(txt)
        r = base_raw.copy()
        for c, v in ch.items():
            need_cols(d, [c])
            r[c] = r[c] * (1 + v)
        esc[nom] = predecir(r)
    base_v = esc["Base (situación actual)"]["estimado"]
    impacto = []
    for c in pal:
        r = base_raw.copy()
        r[c] = r[c] * (1 + a.cambio)
        impacto.append({"palanca": c, "cambio_pct": 100 * a.cambio, "efecto_en_resultado": predecir(r)["estimado"] - base_v})
    impacto.sort(key=lambda z: abs(z["efecto_en_resultado"]), reverse=True)

    # 5. Señales de insight
    senales = []
    for c, co in zip(cor, coefs):
        v = c["variable"]
        cm = next(x for x in coefs if x["variable"] == v)
        if abs(c["correlacion"]) >= 0.3 and np.sign(c["correlacion"]) != np.sign(cm["efecto_por_unidad"]) and cm["p_valor"] < 0.1:
            senales.append("%s parece ir en un sentido por sí sola, pero al controlar las demás variables su efecto es el contrario. Cuidado con leerla de forma aislada." % v)
        if abs(c["correlacion"]) >= 0.3 and cm["p_valor"] >= 0.1:
            senales.append("%s se mueve junto con el resultado (correlación %.2f), pero no aporta nada propio cuando se consideran las demás. Probablemente comparte tendencia o temporada sin causar el resultado." % (v, c["correlacion"]))
    fuerte = max(coefs, key=lambda z: abs(z["peso_relativo"] or 0))
    senales.append("La variable con más peso explicativo es %s." % fuerte["variable"])
    if impacto:
        senales.append("Con un cambio de %+.0f%%, la palanca de mayor efecto es %s (%+.0f en el resultado)." % (100 * a.cambio, impacto[0]["palanca"], impacto[0]["efecto_en_resultado"]))
    if a.log:
        for co in coefs:
            if co["variable"] in logx:
                senales.append("Elasticidad de %s: un aumento de 1%% se asocia con %.2f%% de cambio en %s." % (co["variable"], co["efecto_por_unidad"], a.y))

    # 6. Semáforo
    alertas = []
    if n / (p + len(ctrl)) < 15:
        alertas.append("Pocos datos para tantas variables (%.0f filas por variable; conviene al menos 15)." % (n / (p + len(ctrl))))
    if vif and max(vif.values()) > 5:
        alertas.append("Algunas variables se parecen demasiado entre sí (%s): no se puede separar su efecto." % ", ".join(k for k, v in vif.items() if v > 5))
    if dw is not None and (dw < 1.5 or dw > 2.5):
        alertas.append("Los errores del modelo se repiten en el tiempo: puede faltar una variable de tendencia o temporada.")
    if mape is not None and mape > 20:
        alertas.append("Con datos nuevos el modelo se equivoca en promedio %.0f%%." % mape)
    if bp is not None and bp < 0.05:
        alertas.append("La precisión del modelo cambia según el nivel de ventas; los rangos son orientativos.")
    nivel = "rojo" if (n / (p + len(ctrl)) < 8 or (mape is not None and mape > 35)) else "amarillo" if alertas else "verde"
    if nivel == "verde":
        motivo = "Hay datos suficientes, el modelo predice bien con datos que no vio y no hay variables que se confundan entre sí."
    elif nivel == "rojo":
        motivo = "Hay muy pocos datos para tantas variables o el error con datos nuevos es muy alto: úsalo como hipótesis."
    else:
        motivo = alertas[0]
    res = {"filas": n, "variables": p, "explica_pct_de_la_variacion": float(mod.rsquared * 100),
           "error_medio_con_datos_nuevos_pct": mape, "r2_con_datos_nuevos": r2_out, "semaforo": nivel, "motivo_semaforo": motivo, "alertas": alertas + notas,
           "relacion_simple": cor, "efectos": coefs, "escenarios": esc, "impacto_por_palanca": impacto, "senales": senales,
           "diagnostico_tecnico": {"VIF": vif, "p_breusch_pagan": bp, "durbin_watson": dw, "r2_ajustado": float(mod.rsquared_adj), "errores_robustos": cov["cov_type"]}}
    os.makedirs(a.outdir, exist_ok=True)
    emit({"resumen": res}, os.path.join(a.outdir, "regresion.json"))


if __name__ == "__main__":
    main()
