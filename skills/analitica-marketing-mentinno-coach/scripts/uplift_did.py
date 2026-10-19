#!/usr/bin/env python3
"""A quién le sirve la acción (uplift) y qué causó una acción ya hecha (diferencias en diferencias).

Dos usos:
  uplift  Con una prueba aleatoria (grupo con acción y grupo sin acción) y datos de cada persona,
          estima a quién le cambia la conducta la acción. Evalúa fuera de muestra usando la asignación al azar.
  did     Con zonas, tiendas o clientes observados antes y después de una acción que solo recibió una parte
          (sin aleatorizar), compara el cambio del grupo con acción contra el cambio del grupo sin acción.

Uso:
  python3 uplift_did.py uplift archivo.csv --tratamiento grupo --y compro --x edad,visitas,plan [--control control]
        [--modelo lineal|arboles] [--valor 90 --costo 5] [--reparto 0.5]
  python3 uplift_did.py did archivo.csv --unidad tienda --periodo semana --grupo grupo --resultado ventas
        --fecha-intervencion 2026-03-02 [--control control] [--gasto 20000]
"""
import argparse
import math
import os

import _deps  # noqa: F401  (revisa librerías)
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import KFold, StratifiedKFold, cross_val_predict
from sklearn.preprocessing import StandardScaler

from _utils import emit, load_table, need_cols, parse_dates
from ab_test import _etiquetas, comparar_medias, comparar_proporciones, srm


# =============================================================== UPLIFT
def matriz(d, xs):
    num = [c for c in xs if pd.api.types.is_numeric_dtype(d[c])]
    cat = [c for c in xs if c not in num and d[c].nunique() <= 20]
    omit = [c for c in xs if c not in num and c not in cat]
    partes = []
    if num:
        partes.append(d[num].apply(lambda s: s.fillna(s.median())))
    if cat:
        partes.append(pd.get_dummies(d[cat].astype(str), drop_first=True, dtype=float))
    if not partes:
        raise SystemExit("Ninguna de las variables elegidas se puede usar (texto con demasiadas categorías o inexistentes).")
    return pd.concat(partes, axis=1), omit


class Uplift:
    """Estima el cambio de probabilidad (o de monto) que produce la acción para cada persona."""

    def __init__(self, modelo="lineal", binario=True):
        self.modelo, self.binario = modelo, binario

    def fit(self, X, t, y):
        X = np.asarray(X, float)
        t = np.asarray(t, int)
        if self.modelo == "lineal":
            self.sc = StandardScaler().fit(X)
            Z = self._z(X, t)
            self.m = LogisticRegression(C=0.5, max_iter=3000).fit(Z, y) if self.binario else Ridge(alpha=10.0).fit(Z, y)
        else:
            mk = (lambda: HistGradientBoostingClassifier(max_depth=3, max_iter=150, learning_rate=0.05, min_samples_leaf=50, random_state=1)) if self.binario else \
                 (lambda: HistGradientBoostingRegressor(max_depth=3, max_iter=150, learning_rate=0.05, min_samples_leaf=50, random_state=1))
            self.m1, self.m0 = mk().fit(X[t == 1], y[t == 1]), mk().fit(X[t == 0], y[t == 0])
        return self

    def _z(self, X, t):
        Xs = self.sc.transform(X)
        return np.hstack([Xs, t.reshape(-1, 1), Xs * t.reshape(-1, 1)])

    def _p(self, X, t):
        if self.modelo == "lineal":
            Z = self._z(X, np.full(len(X), t))
            return self.m.predict_proba(Z)[:, 1] if self.binario else self.m.predict(Z)
        m = self.m1 if t == 1 else self.m0
        return m.predict_proba(X)[:, 1] if self.binario else m.predict(X)

    def predecir(self, X):
        X = np.asarray(X, float)
        p1, p0 = self._p(X, 1), self._p(X, 0)
        return p1 - p0, p1, p0


def uplift_fuera_de_muestra(X, t, y, modelo, binario, folds=5, seed=3):
    """Cada persona se puntúa con un modelo que no la vio (validación cruzada)."""
    u, p1, p0 = np.zeros(len(y)), np.zeros(len(y)), np.zeros(len(y))
    estr = t * 2 + (y if binario else (y > np.median(y)).astype(int))
    for tr, te in StratifiedKFold(folds, shuffle=True, random_state=seed).split(X, estr):
        mod = Uplift(modelo, binario).fit(X.iloc[tr], t[tr], y[tr])
        u[te], p1[te], p0[te] = mod.predecir(X.iloc[te])
    return u, p1, p0


def efecto(yt, yc, binario, boot=200):
    if len(yt) < 5 or len(yc) < 5:
        return {"n_t": len(yt), "n_c": len(yc), "dif": float("nan"), "rango": [float("nan")] * 2}
    if binario:
        r = comparar_proporciones(int(yc.sum()), len(yc), int(yt.sum()), len(yt))
    else:
        r = comparar_medias(yc, yt, boot=boot)
    return {"n_t": len(yt), "n_c": len(yc), "dif": r["dif_abs"], "rango": r["rango_abs"], "base": r.get("tasa_control", r.get("media_control"))}


def uplift_cmd(df, trat, ycol, xs, control=None, reparto=0.5, modelo="lineal", valor=None, costo=None, folds=5, boot=300):
    d = df[[trat, ycol] + xs].copy()
    d = d.dropna(subset=[trat, ycol]).reset_index(drop=True)
    c, tt = _etiquetas(d[trat].astype(str), control)
    t = (d[trat].astype(str) == tt).astype(int).values
    y = pd.to_numeric(d[ycol], errors="coerce")
    ok = y.notna().values
    d, t, y = d[ok].reset_index(drop=True), t[ok], y[ok].values.astype(float)
    binario = set(np.unique(y)) <= {0.0, 1.0}
    X, omit = matriz(d, xs)
    n = len(d)
    alertas, notas = [], ["Se tomó como grupo sin acción: %s; con acción: %s." % (c, tt)]
    if omit:
        notas.append("Se descartaron variables de texto con demasiadas categorías: %s." % omit)
    # ¿la asignación fue al azar?
    p_srm = srm(int((t == 0).sum()), int((t == 1).sum()), reparto)
    pa = cross_val_predict(LogisticRegression(max_iter=2000), StandardScaler().fit_transform(X), t, cv=KFold(5, shuffle=True, random_state=1), method="predict_proba")[:, 1]
    auc_asig = float(roc_auc_score(t, pa))
    azar_ok = p_srm >= 0.001 and auc_asig < 0.60
    if p_srm < 0.001:
        alertas.append("Los grupos no tienen el tamaño planeado: la asignación pudo no ser al azar.")
    if auc_asig >= 0.60:
        alertas.append("Las variables permiten adivinar quién recibió la acción (AUC %.2f): los grupos no son comparables y el análisis puede confundir selección con efecto." % auc_asig)
    # efecto promedio
    ate = efecto(y[t == 1], y[t == 0], binario)
    eventos = int(min(((y[t == 1] != 0).sum()), ((y[t == 0] != 0).sum())))
    if eventos < 50:
        alertas.append("Hay pocos casos con resultado en el grupo menor (%d): el uplift por persona será muy impreciso." % eventos)
    # uplift fuera de muestra
    u, p1, p0 = uplift_fuera_de_muestra(X, t, y, modelo, binario, folds)
    rank = pd.Series(u).rank(method="first", ascending=False).values
    dec = np.ceil(rank / n * 10).astype(int)
    filas = []
    for k in range(1, 11):
        m = dec == k
        e = efecto(y[m & (t == 1)], y[m & (t == 0)], binario, boot=200)
        fila = {"decil": k, "personas": int(m.sum()), "uplift_predicho": float(u[m].mean()), "uplift_observado": e["dif"], "rango_95": e["rango"]}
        if valor is not None and costo is not None:
            fila["ganancia_neta_por_persona"] = e["dif"] * (valor if binario else 1.0) - costo
        filas.append(fila)
    # curva acumulada: qué parte del efecto total se captura contactando al mejor k%
    tot = ate["dif"] * n
    curva = []
    for k in (10, 20, 30, 50):
        m = rank <= n * k / 100
        e = efecto(y[m & (t == 1)], y[m & (t == 0)], binario, boot=100)
        inc = e["dif"] * m.sum()
        curva.append({"contactando_al_mejor_pct": k, "efecto_capturado_pct": float(100 * inc / tot) if tot and tot > 0 else None, "uplift_observado": e["dif"]})
    # ¿hay diferencias reales entre quienes más y menos responden?
    top, bot = rank <= 0.3 * n, rank > 0.7 * n
    rng = np.random.default_rng(17)
    difs = []
    for _ in range(boot):
        i = rng.integers(0, n, n)
        tb, yb, tp, bt = t[i], y[i], top[i], bot[i]
        def up(m):
            a, b = yb[m & (tb == 1)], yb[m & (tb == 0)]
            return a.mean() - b.mean() if len(a) > 1 and len(b) > 1 else np.nan
        difs.append(up(tp) - up(bt))
    lo, hi = np.nanpercentile(difs, [5, 95])
    e_top, e_bot = efecto(y[top & (t == 1)], y[top & (t == 0)], binario, 100), efecto(y[bot & (t == 1)], y[bot & (t == 0)], binario, 100)
    brecha = e_top["dif"] - e_bot["dif"]
    # comparación con ordenar por probabilidad de compra
    rank_p = pd.Series(p1).rank(method="first", ascending=False).values
    topp = rank_p <= 0.3 * n
    e_prop = efecto(y[topp & (t == 1)], y[topp & (t == 0)], binario, 100)
    heterogeneidad = lo > 0
    if not azar_ok or eventos < 30:
        nivel = "rojo"
        motivo = "No se puede confiar en el uplift: " + ("la asignación no parece aleatoria." if not azar_ok else "casi no hay casos con resultado.")
    elif heterogeneidad and eventos >= 50:
        nivel = "verde"
        motivo = "El 30%% que el modelo señala responde más que el 30%% que menos (diferencia de %.1f puntos, rango %.1f a %.1f, fuera de muestra): puedes priorizar a quién dirigir la acción." % (100 * brecha, 100 * lo, 100 * hi) if binario else \
                 "El 30%% que el modelo señala responde más que el 30%% que menos (diferencia %.2f, rango %.2f a %.2f, fuera de muestra): puedes priorizar a quién dirigir la acción." % (brecha, lo, hi)
    else:
        nivel = "amarillo"
        motivo = "No se distingue con claridad a quién le sirve más la acción: el efecto promedio existe o no, pero con estos datos no se puede repartir entre personas. Trata a todos igual o amplía la prueba."
    senales = []
    senales.append("Efecto promedio de la acción: %s (rango %s a %s)." % ((("%+.2f puntos" % (100 * ate["dif"])) if binario else ("%+.2f" % ate["dif"])), (("%.2f" % (100 * ate["rango"][0])) if binario else ("%.2f" % ate["rango"][0])), (("%.2f" % (100 * ate["rango"][1])) if binario else ("%.2f" % ate["rango"][1]))))
    if nivel == "verde" and curva[2]["efecto_capturado_pct"] is not None:
        senales.append("Contactando solo al 30%% con más uplift se captura cerca del %.0f%% del efecto total." % curva[2]["efecto_capturado_pct"])
    if e_prop["dif"] is not None and not math.isnan(e_prop["dif"]) and not math.isnan(e_top["dif"]):
        senales.append("Ordenar por probabilidad de compra daría un efecto de %s en el 30%% de arriba; ordenar por uplift, %s." % (("%+.2f puntos" % (100 * e_prop["dif"])) if binario else ("%+.2f" % e_prop["dif"]), ("%+.2f puntos" % (100 * e_top["dif"])) if binario else ("%+.2f" % e_top["dif"])))
    if valor is not None and costo is not None:
        rent = [f["decil"] for f in filas if f.get("ganancia_neta_por_persona", -1) > 0]
        senales.append("Con valor %.0f y costo %.0f por contacto, convienen los deciles %s." % (valor, costo, rent or "ninguno"))
    # puntaje final con todos los datos
    final = Uplift(modelo, binario).fit(X, t, y)
    up_all, _, _ = final.predecir(X)
    out = d.copy()
    out["uplift_predicho"] = up_all
    out["decil_uplift"] = np.ceil(pd.Series(up_all).rank(method="first", ascending=False).values / n * 10).astype(int)
    res = {"tipo_resultado": "tasa (sí o no)" if binario else "valor medio", "modelo": "regresión con interacciones" if modelo == "lineal" else "dos modelos de árboles (grupo con acción y sin acción)",
           "personas": {"sin_accion": int((t == 0).sum()), "con_accion": int((t == 1).sum())},
           "efecto_promedio": ate["dif"], "rango_efecto_promedio_95": ate["rango"], "auc_adivinar_asignacion": auc_asig, "prob_desbalance_por_azar": p_srm,
           "tabla_deciles": filas, "curva_acumulada": curva, "diferencia_arriba_vs_abajo": {"valor": brecha, "rango_90": [lo, hi]},
           "arriba_por_uplift": e_top["dif"], "arriba_por_probabilidad": e_prop["dif"],
           "semaforo": nivel, "motivo_semaforo": motivo, "alertas": alertas, "notas": notas, "senales": senales}
    return res, out


# =============================================================== DIFERENCIAS EN DIFERENCIAS
def _welch(a, b, alfa=0.05):
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = a.mean() - b.mean()
    va, vb = a.var(ddof=1) / len(a), b.var(ddof=1) / len(b)
    se = math.sqrt(va + vb)
    gl = (va + vb) ** 2 / (va ** 2 / (len(a) - 1) + vb ** 2 / (len(b) - 1)) if se > 0 else 1.0
    tq = stats.t.ppf(1 - alfa / 2, gl)
    p = float(2 * (1 - stats.t.cdf(abs(d) / se, gl))) if se > 0 else 1.0
    return d, [d - tq * se, d + tq * se], p, se


def did_cmd(df, unidad, periodo, grupo, ycol, fecha_int, control=None, gasto=None, mdy=False):
    d = df[[unidad, periodo, grupo, ycol]].dropna().copy()
    if pd.api.types.is_numeric_dtype(d[periodo]):
        per = d[periodo].astype(float)
        fi = float(fecha_int)
    else:
        per = parse_dates(d[periodo], mdy)
        fi = pd.to_datetime(fecha_int, dayfirst=("/" in str(fecha_int) and not mdy))
    d["_per"] = per
    d = d.dropna(subset=["_per"])
    d["_y"] = pd.to_numeric(d[ycol], errors="coerce")
    d = d.dropna(subset=["_y"])
    c, tt = _etiquetas(d[grupo].astype(str), control)
    g = d.groupby(unidad)[grupo].nunique()
    if (g > 1).any():
        raise SystemExit("Cada unidad debe pertenecer a un solo grupo en todo el periodo. Revisa: %s" % list(g[g > 1].index[:5]))
    d["_t"] = (d[grupo].astype(str) == tt).astype(int)
    d["_post"] = (d["_per"] >= fi).astype(int)
    periodos = sorted(pd.DatetimeIndex(d["_per"].unique())) if np.issubdtype(d["_per"].dtype, np.datetime64) else sorted(d["_per"].unique())
    pre_p = [p for p in periodos if p < fi]
    post_p = [p for p in periodos if p >= fi]
    if len(pre_p) < 2 or len(post_p) < 1:
        raise SystemExit("Hace falta al menos 2 periodos antes y 1 después de la fecha de intervención. Hay %d antes y %d después." % (len(pre_p), len(post_p)))
    pre, post = d[d._post == 0], d[d._post == 1]
    # cambio por unidad: antes frente a después (se colapsa para no inflar la confianza con periodos repetidos)
    m_pre, m_post = pre.groupby(unidad)["_y"].mean(), post.groupby(unidad)["_y"].mean()
    delta = (m_post - m_pre).dropna()
    tmap = d.groupby(unidad)["_t"].first()
    dt, dc = delta[tmap[delta.index] == 1].values, delta[tmap[delta.index] == 0].values
    if len(dt) < 2 or len(dc) < 2:
        raise SystemExit("Hace falta al menos 2 unidades con acción y 2 sin acción. Hay %d y %d." % (len(dt), len(dc)))
    ef, rg, p, se = _welch(dt, dc)
    contra = float(post[post._t == 1]["_y"].mean() - ef)
    # prueba de tendencias previas: ¿ya se separaban antes de la acción?
    idx = {p_: i for i, p_ in enumerate(pre_p)}
    pre = pre.assign(_i=pre["_per"].map(idx).astype(float))
    pend = pre.groupby(unidad).apply(lambda z: np.polyfit(z["_i"], z["_y"], 1)[0] if z["_y"].nunique() > 1 or len(z) > 1 else np.nan, include_groups=False).dropna()
    st, sc = pend[tmap[pend.index] == 1].values, pend[tmap[pend.index] == 0].values
    d_pend, rg_pend, p_pend, _ = _welch(st, sc) if len(st) > 1 and len(sc) > 1 else (float("nan"), [float("nan")] * 2, 1.0, 0.0)
    # falso inicio: se repite el análisis dentro del periodo previo, partido a la mitad
    mitad = len(pre_p) // 2
    primera, segunda = pre[pre["_per"].isin(pre_p[:mitad])], pre[pre["_per"].isin(pre_p[mitad:])]
    dp = (segunda.groupby(unidad)["_y"].mean() - primera.groupby(unidad)["_y"].mean()).dropna()
    pt, pc = dp[tmap[dp.index] == 1].values, dp[tmap[dp.index] == 0].values
    f_ef, f_rg, f_p, _ = _welch(pt, pc) if len(pt) > 1 and len(pc) > 1 else (float("nan"), [float("nan")] * 2, 1.0, 0.0)
    falso_inicio = bool(f_rg[0] > 0 or f_rg[1] < 0) if not math.isnan(f_rg[0]) else False
    pend_dif = bool(p_pend < 0.05)
    alertas, notas = [], ["Se tomó como grupo sin acción: %s; con acción: %s." % (c, tt)]
    if pend_dif:
        alertas.append("Antes de la acción los dos grupos ya iban en direcciones distintas (diferencia de tendencia significativa): el grupo sin acción no es un buen punto de comparación.")
    if falso_inicio:
        alertas.append("Al simular una acción falsa dentro del periodo previo aparece un 'efecto' (%.2f, rango %.2f a %.2f): señal de que los grupos no evolucionaban en paralelo." % (f_ef, f_rg[0], f_rg[1]))
    if len(pre_p) < 4:
        alertas.append("Hay solo %d periodos previos: no se puede comprobar bien si los grupos iban en paralelo." % len(pre_p))
    n_min = min(len(dt), len(dc))
    if n_min < 5:
        alertas.append("Hay pocas unidades en un grupo (%d con acción, %d sin acción): el rango es muy amplio y sensible a una sola unidad." % (len(dt), len(dc)))
    # contaminación por solapamiento: unidades tratadas antes de la fecha no existen por construcción
    concl = rg[0] > 0 or rg[1] < 0
    if pend_dif and falso_inicio:
        nivel, motivo = "rojo", "Los grupos no evolucionaban en paralelo antes de la acción: la diferencia de después no se puede atribuir a la acción. Busca otro grupo de comparación."
    elif pend_dif or falso_inicio:
        nivel, motivo = "amarillo", "El efecto estimado depende de que los grupos fueran en paralelo, y hay una señal de que no lo eran del todo. Trátalo como pista y confirma con otro grupo de comparación."
    elif not concl:
        nivel, motivo = "amarillo", "No concluyente: el rango del efecto incluye cero. No se puede confirmar ni descartar un efecto con estas unidades."
    elif n_min < 5 or len(pre_p) < 4:
        nivel, motivo = "amarillo", "El efecto es claro pero hay pocas unidades o pocos periodos previos para confiar del todo."
    else:
        nivel, motivo = "verde", "El grupo con acción cambió distinto al de comparación, los dos iban en paralelo antes y el rango no incluye cero."
    res = {"unidades": {"con_accion": len(dt), "sin_accion": len(dc)}, "periodos": {"antes": len(pre_p), "despues": len(post_p)},
           "efecto_por_unidad_y_periodo": ef, "rango_95": rg, "efecto_relativo_sobre_lo_esperado": float(ef / contra) if contra else None,
           "p_valor": p, "tendencias_previas": {"dif_pendiente": d_pend, "rango_95": rg_pend, "p_valor": p_pend},
           "falso_inicio": {"efecto": f_ef, "rango_95": f_rg, "p_valor": f_p}, "semaforo": nivel, "motivo_semaforo": motivo, "alertas": alertas, "notas": notas}
    inc = ef * len(dt) * len(post_p)
    res["efecto_total"] = {"incremental": inc, "rango_95": [rg[0] * len(dt) * len(post_p), rg[1] * len(dt) * len(post_p)]}
    if gasto:
        roas, rl, rh = inc / gasto, rg[0] * len(dt) * len(post_p) / gasto, rg[1] * len(dt) * len(post_p) / gasto
        res["retorno_incremental"] = {"retorno_por_cada_unidad_invertida": roas, "rango_95": [rl, rh], "gasto": gasto}
        err = (rh - rl) / (2 * stats.norm.ppf(0.975))
        res["para_calibrar_mmm"] = {"retorno": roas, "error": err, "ejemplo_comando": "--calibrar canal=%.3f:%.3f" % (roas, max(err, 1e-6))}
        if nivel != "verde":
            res["para_calibrar_mmm"]["advertencia"] = "El análisis no tiene semáforo verde: no uses esta cifra para calibrar el modelo sin otra evidencia."
    return res


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("uplift")
    u.add_argument("file")
    u.add_argument("--tratamiento", required=True)
    u.add_argument("--y", required=True)
    u.add_argument("--x", required=True)
    u.add_argument("--control")
    u.add_argument("--reparto", type=float, default=0.5)
    u.add_argument("--modelo", choices=["lineal", "arboles"], default="lineal")
    u.add_argument("--valor", type=float)
    u.add_argument("--costo", type=float)
    u.add_argument("--folds", type=int, default=5)
    u.add_argument("--boot", type=int, default=300)
    u.add_argument("--hoja")
    u.add_argument("--outdir", default="resultados")
    w = sub.add_parser("did")
    w.add_argument("file")
    w.add_argument("--unidad", required=True)
    w.add_argument("--periodo", required=True)
    w.add_argument("--grupo", required=True)
    w.add_argument("--resultado", required=True)
    w.add_argument("--fecha-intervencion", required=True, dest="fi")
    w.add_argument("--control")
    w.add_argument("--gasto", type=float)
    w.add_argument("--mdy", action="store_true")
    w.add_argument("--hoja")
    w.add_argument("--outdir", default="resultados")
    a = ap.parse_args()
    df = load_table(a.file, a.hoja)
    if a.cmd == "uplift":
        xs = [c.strip() for c in a.x.split(",")]
        need_cols(df, [a.tratamiento, a.y] + xs)
        res, out = uplift_cmd(df, a.tratamiento, a.y, xs, a.control, a.reparto, a.modelo, a.valor, a.costo, a.folds, a.boot)
        os.makedirs(a.outdir, exist_ok=True)
        f = os.path.join(a.outdir, "puntajes_uplift.csv")
        out.to_csv(f, index=False)
        res["archivo_puntajes"] = f
        emit({"resumen": res}, os.path.join(a.outdir, "uplift.json"))
    else:
        need_cols(df, [a.unidad, a.periodo, a.grupo, a.resultado])
        res = did_cmd(df, a.unidad, a.periodo, a.grupo, a.resultado, a.fi, a.control, a.gasto, a.mdy)
        emit({"resumen": res}, os.path.join(a.outdir, "did.json"))


if __name__ == "__main__":
    main()
