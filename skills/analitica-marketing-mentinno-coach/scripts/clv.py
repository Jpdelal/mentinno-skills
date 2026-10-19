#!/usr/bin/env python3
"""Valor de vida del cliente: cuánto se espera que compre y valga cada cliente en los próximos meses.

Método: modelo de compras libres (BG/NBD) para saber cuántas compras se esperan y si el cliente sigue activo,
más un modelo de monto por compra (Gamma-Gamma). Se prueba con las compras más recientes que el modelo no vio.
Incluye una tabla de cohortes (ingreso acumulado por cliente según el mes de su primera compra), que no depende de ningún modelo.
Solo para negocios donde el cliente compra cuando quiere. Para suscripciones usa retención por cohortes.

Uso: python3 clv.py archivo --cliente id_cliente --fecha fecha --monto monto
        [--corte AAAA-MM-DD] [--horizonte 12] [--descuento 0.10] [--margen 1.0] [--validacion 6]
"""
import argparse
import os

import _deps  # noqa: F401  (revisa librerías)
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import gammaln, hyp2f1

from _utils import emit, load_table, need_cols, parse_dates

SEM_POR_MES = 52.0 / 12.0


# ------------------------------------------------------------------ resumen por cliente
def resumen_clientes(tx, cliente, fecha, monto, corte):
    """Una fila por cliente: compras repetidas (x), recencia (tx) y edad (T) en semanas, y monto medio de las compras repetidas."""
    t = tx[tx[fecha] <= corte]
    g = t.groupby([cliente, fecha], as_index=False)[monto].sum()
    primera = g.groupby(cliente)[fecha].min()
    ultima = g.groupby(cliente)[fecha].max()
    n = g.groupby(cliente).size()
    out = pd.DataFrame({"x": (n - 1).astype(float), "t_x": (ultima - primera).dt.days / 7.0, "T": (corte - primera).dt.days / 7.0,
                        "primera": primera, "ultima": ultima, "compras": n, "gasto_total": g.groupby(cliente)[monto].sum()})
    rep = g.merge(primera.rename("_p"), left_on=cliente, right_index=True)
    rep = rep[rep[fecha] > rep["_p"]]
    out["m_x"] = rep.groupby(cliente)[monto].mean().reindex(out.index)
    return out


# ------------------------------------------------------------------ BG/NBD
def _nll_bgnbd(th, x, tx, T):
    r, alpha, b = np.exp(th[0]), np.exp(th[1]), np.exp(th[2])
    a = 1.01 + np.exp(th[3])
    A1 = gammaln(r + x) - gammaln(r) + r * np.log(alpha)
    A2 = gammaln(a + b) + gammaln(b + x) - gammaln(b) - gammaln(a + b + x)
    A3 = -(r + x) * np.log(alpha + T)
    A4 = np.log(a) - np.log(b + np.maximum(x, 1) - 1) - (r + x) * np.log(alpha + tx)
    A4 = np.where(x > 0, A4, -np.inf)
    m = np.maximum(A3, A4)
    ll = A1 + A2 + m + np.log(np.exp(A3 - m) + np.exp(A4 - m))
    v = -np.sum(ll)
    return v if np.isfinite(v) else 1e12


def ajustar_bgnbd(x, tx, T):
    mejor = None
    for ini in ([np.log(0.5), np.log(8.0), np.log(2.0), np.log(0.5)], [np.log(1.0), np.log(20.0), np.log(1.0), np.log(1.0)], [np.log(0.3), np.log(4.0), np.log(3.0), np.log(0.2)]):
        r = minimize(_nll_bgnbd, ini, args=(x, tx, T), method="L-BFGS-B", bounds=[(-7, 7), (-7, 7), (-7, 7), (-7, 5)])
        if mejor is None or r.fun < mejor.fun:
            mejor = r
    th = mejor.x
    return {"r": float(np.exp(th[0])), "alpha": float(np.exp(th[1])), "a": float(1.01 + np.exp(th[3])), "b": float(np.exp(th[2])), "nll": float(mejor.fun),
            "en_el_borde": bool(np.any(np.isclose(th, [-7, -7, -7, -7], atol=1e-3)) or np.any(np.isclose(th, [7, 7, 7, 5], atol=1e-3)))}


def prob_activo(P, x, tx, T):
    r, alpha, a, b = P["r"], P["alpha"], P["a"], P["b"]
    lg = (r + x) * (np.log(alpha + T) - np.log(alpha + tx))
    return 1.0 / (1.0 + np.where(x > 0, a / (b + np.maximum(x, 1) - 1) * np.exp(np.minimum(lg, 700)), 0.0))


def compras_esperadas(P, x, tx, T, t):
    """Compras esperadas en las próximas t semanas, dado lo observado."""
    r, alpha, a, b = P["r"], P["alpha"], P["a"], P["b"]
    hyp = hyp2f1(r + x, b + x, a + b + x - 1, t / (alpha + T + t))
    primero = (a + b + x - 1) / (a - 1)
    segundo = 1 - np.exp((r + x) * (np.log(alpha + T) - np.log(alpha + t + T))) * hyp
    lg = (r + x) * (np.log(alpha + T) - np.log(alpha + tx))
    den = 1 + np.where(x > 0, a / (b + np.maximum(x, 1) - 1) * np.exp(np.minimum(lg, 700)), 0.0)
    return primero * segundo / den


# ------------------------------------------------------------------ Gamma-Gamma (monto por compra)
def _nll_gg(th, x, m):
    p, q, v = np.exp(th[0]), 1.01 + np.exp(th[1]), np.exp(th[2])
    ll = gammaln(p * x + q) - gammaln(p * x) - gammaln(q) + q * np.log(v) + (p * x - 1) * np.log(m) + p * x * np.log(x) - (p * x + q) * np.log(x * m + v)
    s = -np.sum(ll)
    return s if np.isfinite(s) else 1e12


def ajustar_gg(x, m):
    mejor = None
    for ini in ([np.log(5.0), np.log(2.0), np.log(15.0)], [np.log(2.0), np.log(1.0), np.log(30.0)], [np.log(10.0), np.log(4.0), np.log(10.0)]):
        r = minimize(_nll_gg, ini, args=(x, m), method="L-BFGS-B", bounds=[(-5, 6), (-6, 5), (-3, 8)])
        if mejor is None or r.fun < mejor.fun:
            mejor = r
    th = mejor.x
    return {"p": float(np.exp(th[0])), "q": float(1.01 + np.exp(th[1])), "v": float(np.exp(th[2]))}


def valor_por_compra(G, x, m):
    """Monto esperado por compra: mezcla lo del cliente con el promedio general, con más peso al cliente cuantas más compras repetidas tiene."""
    media_pob = G["v"] * G["p"] / (G["q"] - 1)
    peso = G["p"] * x / (G["p"] * x + G["q"] - 1)
    m = np.where(np.isnan(m), media_pob, m)
    return np.where(x > 0, (1 - peso) * media_pob + peso * m, media_pob), media_pob


def clv_clientes(P, G, S, horizonte, descuento, margen):
    x, tx, T = S["x"].values, S["t_x"].values, S["T"].values
    val, _ = valor_por_compra(G, x, S["m_x"].values)
    dm = (1 + descuento) ** (1 / 12.0) - 1
    ant = np.zeros(len(S))
    total = np.zeros(len(S))
    for i in range(1, horizonte + 1):
        cum = compras_esperadas(P, x, tx, T, i * SEM_POR_MES)
        total += (cum - ant) / (1 + dm) ** i
        ant = cum
    return total * val * margen, ant, val


# ------------------------------------------------------------------ cohortes
def cohortes(tx, cliente, fecha, monto, corte, meses=(1, 3, 6, 12)):
    t = tx[tx[fecha] <= corte].copy()
    t["_p"] = t.groupby(cliente)[fecha].transform("min")
    t["_k"] = ((t[fecha] - t["_p"]).dt.days / 30.44).astype(int)
    t["_c"] = t["_p"].dt.to_period("M")
    tam = t.groupby("_c")[cliente].nunique()
    filas = []
    for c in tam.index:
        fila = {"cohorte": str(c), "clientes": int(tam[c])}
        inicio = c.to_timestamp()
        for k in meses:
            if inicio + pd.DateOffset(months=k + 1) > corte:
                fila["ingreso_por_cliente_%dm" % k] = None
                continue
            sub = t[(t["_c"] == c) & (t["_k"] <= k)]
            fila["ingreso_por_cliente_%dm" % k] = float(sub[monto].sum() / tam[c])
        filas.append(fila)
    return filas


# ------------------------------------------------------------------ flujo completo
def regularidad(tx, cliente, fecha):
    """Mide qué tan regulares son los intervalos entre compras (señal de suscripción)."""
    g = tx.groupby([cliente, fecha]).size().reset_index()[[cliente, fecha]].sort_values([cliente, fecha])
    g["_d"] = g.groupby(cliente)[fecha].diff().dt.days
    f = g.groupby(cliente)["_d"].agg(["count", "mean", "std"])
    f = f[f["count"] >= 3]
    if len(f) < 30:
        return None
    return float((f["std"] / f["mean"]).median())


def validar(tx, cliente, fecha, monto, fin, meses_val, horizonte):
    corte = fin - pd.DateOffset(months=meses_val)
    S = resumen_clientes(tx, cliente, fecha, monto, corte)
    S = S[S["T"] >= 0]
    if len(S) < 300 or (corte - tx[fecha].min()).days < 365:
        return None
    P = ajustar_bgnbd(S["x"].values, S["t_x"].values, S["T"].values)
    rep = S[(S["x"] > 0) & S["m_x"].notna() & (S["m_x"] > 0)]
    G = ajustar_gg(rep["x"].values, rep["m_x"].values) if len(rep) >= 50 else None
    sem = (fin - corte).days / 7.0
    pred = compras_esperadas(P, S["x"].values, S["t_x"].values, S["T"].values, sem)
    nuevas = tx[(tx[fecha] > corte) & (tx[fecha] <= fin)].groupby([cliente, fecha])[monto].sum().reset_index()
    real_n = nuevas.groupby(cliente).size().reindex(S.index).fillna(0).values
    real_v = nuevas.groupby(cliente)[monto].sum().reindex(S.index).fillna(0).values
    err_n = float((pred.sum() - real_n.sum()) / max(real_n.sum(), 1e-9))
    grupos = []
    for etq, m in (("0 compras repetidas", S["x"] == 0), ("1", S["x"] == 1), ("2", S["x"] == 2), ("3 o más", S["x"] >= 3)):
        mm = m.values
        if mm.sum() >= 20:
            grupos.append({"grupo": etq, "clientes": int(mm.sum()), "compras_predichas": float(pred[mm].mean()), "compras_reales": float(real_n[mm].mean())})
    out = {"corte_calibracion": str(corte.date()), "semanas_probadas": sem, "clientes": len(S), "error_compras_totales": err_n, "por_grupo": grupos, "params": P}
    if G is not None:
        val, _ = valor_por_compra(G, S["x"].values, S["m_x"].values)
        err_v = float(((pred * val).sum() - real_v.sum()) / max(real_v.sum(), 1e-9))
        out["error_ingresos_totales"] = err_v
    return out


def clv_cmd(tx, cliente, fecha, monto, corte=None, horizonte=12, descuento=0.10, margen=1.0, meses_val=6):
    t = tx[[cliente, fecha, monto]].dropna().copy()
    t[monto] = pd.to_numeric(t[monto], errors="coerce")
    t = t.dropna(subset=[monto])
    notas, alertas = [], []
    neg = int((t[monto] <= 0).sum())
    if neg:
        notas.append("Se excluyeron %d filas con monto cero o negativo (devoluciones)." % neg)
    t = t[t[monto] > 0]
    fin = pd.to_datetime(corte) if corte else t[fecha].max()
    t = t[t[fecha] <= fin]
    S = resumen_clientes(t, cliente, fecha, monto, fin)
    n = len(S)
    if n < 100:
        raise SystemExit("Con menos de 100 clientes el modelo no es estable. Hay %d." % n)
    historia_m = (fin - t[fecha].min()).days / 30.44
    if historia_m < 12:
        alertas.append("Hay solo %.0f meses de historia: no se puede probar el modelo con datos nuevos y la proyección es orientativa." % historia_m)
    reg = regularidad(t, cliente, fecha)
    suscripcion = reg is not None and reg < 0.35
    if suscripcion:
        alertas.append("Las compras llegan a intervalos muy regulares (parece suscripción o compra programada): este modelo es para compras libres. Usa la tabla de cohortes como base.")
    P = ajustar_bgnbd(S["x"].values, S["t_x"].values, S["T"].values)
    if P["en_el_borde"]:
        alertas.append("El modelo no encontró una solución estable (un parámetro quedó en el límite): las cifras por cliente son poco fiables.")
    rep = S[(S["x"] > 0) & S["m_x"].notna() & (S["m_x"] > 0)]
    if len(rep) < 50:
        raise SystemExit("Hay menos de 50 clientes con compras repetidas: no se puede estimar el monto por compra.")
    G = ajustar_gg(rep["x"].values, rep["m_x"].values)
    corr = float(rep[["x", "m_x"]].corr(method="spearman").iloc[0, 1])
    if abs(corr) > 0.3:
        alertas.append("Los clientes que compran más veces tienen un monto por compra distinto (correlación %.2f): el modelo de monto supone que no, así que el valor por compra puede estar sesgado." % corr)
    clv, compras_h, val = clv_clientes(P, G, S, horizonte, descuento, margen)
    pa = prob_activo(P, S["x"].values, S["t_x"].values, S["T"].values)
    val_res = validar(t, cliente, fecha, monto, fin, meses_val, horizonte) if historia_m >= 12 + meses_val else None
    if val_res is None and historia_m >= 12:
        alertas.append("No hay suficiente historia o clientes para reservar %d meses de prueba: no se pudo validar con datos nuevos." % meses_val)
    if horizonte > 2 * meses_val:
        alertas.append("Se proyecta a %d meses y el modelo se probó a %d: más allá del doble de lo probado es extrapolar." % (horizonte, meses_val))
    # semáforo
    err_n = val_res["error_compras_totales"] if val_res else None
    err_v = val_res.get("error_ingresos_totales") if val_res else None
    if val_res is None:
        nivel, motivo = "amarillo", "No se pudo probar con datos nuevos: úsalo como orden de magnitud y no como cifra exacta."
    elif abs(err_n) > 0.25 or (err_v is not None and abs(err_v) > 0.30):
        nivel, motivo = "rojo", "En las compras recientes que el modelo no vio, se equivocó en %.0f%% en compras%s: no lo uses para decidir cuánto invertir por cliente." % (100 * abs(err_n), (" y %.0f%% en ingresos" % (100 * abs(err_v))) if err_v is not None else "")
    elif abs(err_n) > 0.10 or (err_v is not None and abs(err_v) > 0.15) or alertas:
        nivel, motivo = "amarillo", "Predijo las compras recientes con un error de %.0f%%, pero hay advertencias que limitan la confianza (revísalas)." % (100 * abs(err_n))
    else:
        nivel, motivo = "verde", "Predijo las compras recientes que no había visto con un error de %.0f%% en compras y %.0f%% en ingresos." % (100 * abs(err_n), 100 * abs(err_v) if err_v is not None else float("nan"))
    if suscripcion and nivel == "verde":
        nivel = "amarillo"
    # tabla de salida y señales
    out = S.copy()
    out["prob_activo"] = pa
    out["compras_esperadas_%dm" % horizonte] = compras_h
    out["valor_por_compra_esperado"] = val
    out["clv_%dm" % horizonte] = clv
    out["decil_clv"] = np.ceil(pd.Series(clv, index=out.index).rank(method="first", ascending=False) / n * 10).astype(int)
    orden = np.sort(clv)[::-1]
    top10 = float(orden[: max(1, n // 10)].sum() / max(orden.sum(), 1e-9))
    una = float((S["compras"] == 1).mean())
    hist_alto = S["gasto_total"] >= S["gasto_total"].quantile(0.8)
    riesgo = hist_alto & (pa < 0.3)
    senales = ["El 10%% de clientes con más valor esperado concentra %.0f%% del valor futuro." % (100 * top10),
               "%.0f%% de los clientes compró una sola vez: ahí está el mayor margen de recuperación." % (100 * una)]
    if riesgo.sum() > 0:
        senales.append("%d clientes de alto gasto histórico ya tienen menos de 30%% de probabilidad de seguir activos: son los que conviene intentar recuperar primero." % int(riesgo.sum()))
    coh = cohortes(t, cliente, fecha, monto, fin)
    res = {"clientes": n, "meses_de_historia": historia_m, "horizonte_meses": horizonte, "descuento_anual": descuento, "margen": margen,
           "valor_esperado_total_base": float(clv.sum()), "valor_esperado_medio_por_cliente": float(clv.mean()), "valor_esperado_mediano": float(np.median(clv)),
           "concentracion_top10pct": top10, "pct_una_sola_compra": una, "clientes_alto_valor_en_riesgo": int(riesgo.sum()),
           "modelo": {"compras": {k: P[k] for k in ("r", "alpha", "a", "b")}, "monto": G, "monto_medio_poblacion": G["v"] * G["p"] / (G["q"] - 1), "corr_monto_frecuencia": corr},
           "prueba_con_datos_nuevos": val_res, "semaforo": nivel, "motivo_semaforo": motivo, "alertas": alertas, "notas": notas, "senales": senales, "cohortes": coh}
    return res, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--cliente", required=True)
    ap.add_argument("--fecha", required=True)
    ap.add_argument("--monto", required=True)
    ap.add_argument("--corte", help="fecha de corte (por defecto, la última compra)")
    ap.add_argument("--horizonte", type=int, default=12, help="meses hacia adelante")
    ap.add_argument("--descuento", type=float, default=0.10, help="tasa de descuento anual")
    ap.add_argument("--margen", type=float, default=1.0, help="margen sobre ventas (1.0 = ventas; 0.3 = margen de 30%%)")
    ap.add_argument("--validacion", type=int, default=6, help="meses recientes que se reservan para probar el modelo")
    ap.add_argument("--hoja")
    ap.add_argument("--mdy", action="store_true")
    ap.add_argument("--outdir", default="resultados")
    a = ap.parse_args()
    df = load_table(a.file, a.hoja)
    need_cols(df, [a.cliente, a.fecha, a.monto])
    df[a.fecha] = parse_dates(df[a.fecha], a.mdy)
    df = df.dropna(subset=[a.fecha])
    res, out = clv_cmd(df, a.cliente, a.fecha, a.monto, a.corte, a.horizonte, a.descuento, a.margen, a.validacion)
    os.makedirs(a.outdir, exist_ok=True)
    f = os.path.join(a.outdir, "clv_clientes.csv")
    out.reset_index().to_csv(f, index=False)
    res["archivo_clientes"] = f
    emit({"resumen": res}, os.path.join(a.outdir, "clv.json"))


if __name__ == "__main__":
    main()
