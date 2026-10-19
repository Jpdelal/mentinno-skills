#!/usr/bin/env python3
"""Mezcla de medios ligera: cuánto aporta cada canal, dónde saturó y cómo reasignar presupuesto.

Estima efecto acumulado (arrastre) y saturación por canal, con rangos por remuestreo y prueba con datos nuevos.
Acepta resultados de experimentos para calibrar. Para MMM bayesiano completo, usar Meridian, Robyn o PyMC-Marketing.

Uso: python3 mmm_lite.py archivo --fecha semana --y ventas --canales gasto_tv,gasto_busqueda
        [--controles promocion] [--calibrar "gasto_tv=3.0:0.8"] [--limite 0.5] [--boot 200]
"""
import argparse
import itertools
import os

import _deps  # noqa: F401  (revisa librerías)
import numpy as np
import pandas as pd
from scipy.optimize import minimize, nnls

from _utils import emit, load_table, need_cols, parse_dates

DECAYS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
KS = [0.5, 0.75, 1.0, 1.5, 2.0]


def adstock(x, d):
    out, c = np.zeros(len(x)), 0.0
    for i, v in enumerate(x):
        c = v + d * c
        out[i] = c
    return out


class Modelo:
    def __init__(self, y, S, Z, calib, ysc):
        self.y, self.S, self.Z, self.calib, self.ysc = y, S, Z, calib, ysc

    def design(self, shapes, A_idx=None):
        cols = []
        for j, (dec, ks) in enumerate(shapes):
            a = adstock(self.S[:, j], dec)
            cols.append(1 - np.exp(-a / (ks * a.mean() + 1e-9)))
        return np.column_stack(cols)

    def fit(self, shapes, sigma=None, y=None):
        y = self.y if y is None else y
        C = self.design(shapes)
        Z = self.Z
        A = np.hstack([Z, -Z, C])
        b = y.copy()
        if self.calib and sigma:
            rows, tg = [], []
            for j, (roi, se) in self.calib.items():
                tot = self.S[:, j].sum()
                w = sigma / max(se * tot / self.ysc, 1e-9)
                r = np.zeros(A.shape[1])
                r[2 * Z.shape[1] + j] = C[:, j].sum() * w
                rows.append(r)
                tg.append(roi * tot / self.ysc * w)
            A, b = np.vstack([A] + rows), np.concatenate([b, tg])
        coef, _ = nnls(A, b, maxiter=5000)
        p = Z.shape[1]
        gam, beta = coef[:p] - coef[p:2 * p], coef[2 * p:]
        fit = Z @ gam + C @ beta
        return gam, beta, fit, C

    def search(self, init=None, passes=3):
        m = self.S.shape[1]
        shapes = init or [(0.3, 1.0)] * m
        sigma = None
        for _ in range(passes):
            for j in range(m):
                best, bs = None, shapes[j]
                for dec, ks in itertools.product(DECAYS, KS):
                    trial = shapes.copy()
                    trial[j] = (dec, ks)
                    _, _, fit, _ = self.fit(trial, sigma)
                    sse = float(((self.y - fit) ** 2).sum())
                    if best is None or sse < best:
                        best, bs = sse, (dec, ks)
                shapes[j] = bs
            _, _, fit, _ = self.fit(shapes)
            sigma = float(np.std(self.y - fit)) or 1e-6
        return shapes, sigma


def contrib_ss(beta_abs, dec, kabs, x):
    a = x / (1 - dec)
    return beta_abs * (1 - np.exp(-a / kabs))


def mroi_ss(beta_abs, dec, kabs, x):
    a = x / (1 - dec)
    return beta_abs * np.exp(-a / kabs) / (kabs * (1 - dec))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--fecha", required=True)
    ap.add_argument("--y", required=True)
    ap.add_argument("--canales", required=True)
    ap.add_argument("--controles", default="")
    ap.add_argument("--calibrar", action="append", default=[], help='canal=retorno:error  (resultado de un experimento)')
    ap.add_argument("--limite", type=float, default=0.5, help="cuánto puede subir o bajar un canal al reasignar (0.5 = 50%%)")
    ap.add_argument("--boot", type=int, default=200)
    ap.add_argument("--hoja")
    ap.add_argument("--mdy", action="store_true")
    ap.add_argument("--outdir", default="resultados")
    a = ap.parse_args()

    ch = [c.strip() for c in a.canales.split(",")]
    ctl = [c.strip() for c in a.controles.split(",") if c.strip()]
    df = load_table(a.file, a.hoja)
    need_cols(df, [a.fecha, a.y] + ch + ctl)
    df[a.fecha] = parse_dates(df[a.fecha], a.mdy)
    df = df.sort_values(a.fecha).dropna(subset=[a.fecha, a.y] + ch).reset_index(drop=True)
    df[ctl] = df[ctl].fillna(0) if ctl else df[ctl]
    T, m = len(df), len(ch)
    med = df[a.fecha].diff().dt.days.median()
    per = 52 if 5 <= med <= 9 else 12 if 25 <= med <= 35 else None
    freq = "semanas" if per == 52 else "meses" if per == 12 else "periodos"
    alertas = []
    if per == 52 and T < 104:
        alertas.append("Hay %d semanas de datos; lo recomendable son 104 o más. Los resultados son orientativos." % T)
    if T < 52:
        raise SystemExit("Con menos de 52 periodos no se puede separar el efecto de los canales de la temporada. Reúne más historia.")
    ysc = float(df[a.y].mean())
    y = df[a.y].values / ysc
    S = df[ch].values.astype(float)
    tt = np.arange(T)
    Zc = [np.ones(T), tt / T]
    if per and T >= 2 * per:
        for j in (1, 2):
            Zc += [np.sin(2 * np.pi * j * tt / per), np.cos(2 * np.pi * j * tt / per)]
    for c in ctl:
        v = df[c].values.astype(float)
        Zc.append((v - v.mean()) / (v.std() or 1))
    Z = np.column_stack(Zc)

    calib = {}
    for txt in a.calibrar:
        k, _, v = txt.partition("=")
        r, _, e = v.partition(":")
        if k.strip() not in ch:
            raise SystemExit("El canal calibrado %s no está en --canales." % k)
        calib[ch.index(k.strip())] = (float(r), float(e or 0.3 * float(r)))

    # alertas de identificación
    for j, c in enumerate(ch):
        cv = S[:, j].std() / (S[:, j].mean() or 1)
        if cv < 0.15:
            alertas.append("%s casi no cambia en el tiempo (variación %.0f%%): no se puede medir su efecto con confianza." % (c, 100 * cv))
    with np.errstate(all="ignore"):
        cm = np.nan_to_num(np.corrcoef(S.T)) if m > 1 else np.array([[1.0]])
    for i, j in itertools.combinations(range(m), 2):
        if abs(cm[i, j]) > 0.8:
            alertas.append("%s y %s se mueven casi igual (correlación %.2f): sus efectos no se pueden separar bien." % (ch[i], ch[j], cm[i, j]))

    mod = Modelo(y, S, Z, calib, ysc)
    shapes, sigma = mod.search()
    gam, beta, fit, C = mod.fit(shapes, sigma)
    resid = y - fit
    r2 = 1 - (resid ** 2).sum() / ((y - y.mean()) ** 2).sum()
    mape_in = float(np.mean(np.abs(resid / y)) * 100)
    dw = float(np.sum(np.diff(resid) ** 2) / np.sum(resid ** 2))

    # prueba con datos nuevos: se vuelve a estimar todo con el pasado
    h = min(12, T // 5)
    tr = Modelo(y[:-h], S[:-h], Z[:-h], calib, ysc)
    sh_tr, sg_tr = tr.search()
    g2, b2, _, _ = tr.fit(sh_tr, sg_tr)
    cols = []
    for j, (dec, ks) in enumerate(sh_tr):
        aa = adstock(S[:, j], dec)
        cols.append(1 - np.exp(-aa / (ks * aa[:-h].mean() + 1e-9)))
    pred = Z @ g2 + np.column_stack(cols) @ b2
    mape_out = float(np.mean(np.abs((y[-h:] - pred[-h:]) / y[-h:])) * 100)

    # resultados puntuales
    spend_tot = S.sum(0)
    contrib_tot = (C * beta).sum(0) * ysc
    roi = contrib_tot / spend_tot
    base_share = 100 * (1 - contrib_tot.sum() / df[a.y].sum())
    x_cur = S[-8:].mean(0)
    kabs = np.array([shapes[j][1] * adstock(S[:, j], shapes[j][0]).mean() for j in range(m)])
    decs = np.array([s[0] for s in shapes])
    beta_abs = beta * ysc
    mroi = np.array([mroi_ss(beta_abs[j], decs[j], kabs[j], x_cur[j]) for j in range(m)])
    satur = np.array([1 - np.exp(-(x_cur[j] / (1 - decs[j])) / kabs[j]) for j in range(m)])

    # reasignación del mismo presupuesto
    lo, hi = x_cur * (1 - a.limite), x_cur * (1 + a.limite)

    def optimizar(total, b_abs):
        f = lambda x: -sum(contrib_ss(b_abs[j], decs[j], kabs[j], x[j]) for j in range(m))
        r = minimize(f, x_cur * total / x_cur.sum(), method="SLSQP", bounds=list(zip(lo, hi)), constraints=[{"type": "eq", "fun": lambda x: x.sum() - total}])
        return r.x

    x_opt = optimizar(x_cur.sum(), beta_abs)
    def cs(x, b_abs, d=None, k=None):
        d = decs if d is None else d
        k = kabs if k is None else k
        return sum(contrib_ss(b_abs[j], d[j], k[j], x[j]) for j in range(m))
    uplift = cs(x_opt, beta_abs) - cs(x_cur, beta_abs)
    x_plus = optimizar(x_cur.sum() * 1.10, beta_abs)
    inc_plus = cs(x_plus, beta_abs) - cs(x_cur, beta_abs)

    # rangos por remuestreo de bloques
    rng = np.random.default_rng(7)
    blk = 4
    B = a.boot
    rois, mrois, ups, shares = [], [], [], []
    for _ in range(B):
        idx = []
        while len(idx) < T:
            s0 = rng.integers(0, T - blk + 1)
            idx.extend(range(s0, s0 + blk))
        idx = np.array(idx[:T])
        yb = fit + resid[idx]
        # en cada remuestreo se vuelve a estimar también la forma de la curva de cada canal
        # y el error de cada experimento: su resultado también es una medición con ruido
        calib_b = {j: (max(r0 + rng.normal(0, e0), 1e-6), e0) for j, (r0, e0) in calib.items()}
        mb = Modelo(yb, S, Z, calib_b, ysc)
        sh_b, sg_b = mb.search(init=list(shapes), passes=1)
        g_b, b_b, f_b, C_b = mb.fit(sh_b, sg_b)
        ba = b_b * ysc
        d_b = np.array([s[0] for s in sh_b])
        k_b = np.array([sh_b[j][1] * adstock(S[:, j], sh_b[j][0]).mean() for j in range(m)])
        rois.append((C_b * b_b).sum(0) * ysc / spend_tot)
        mrois.append([mroi_ss(ba[j], d_b[j], k_b[j], x_cur[j]) for j in range(m)])
        ups.append(cs(x_opt, ba, d_b, k_b) - cs(x_cur, ba, d_b, k_b))
        shares.append(100 * (C_b * b_b).sum(0) * ysc / df[a.y].sum())
    rois, mrois, ups, shares = map(np.array, (rois, mrois, ups, shares))
    q = lambda arr, i: [float(np.percentile(arr[:, i], 5)), float(np.percentile(arr[:, i], 95))]

    canales = []
    for j, c in enumerate(ch):
        canales.append({"canal": c, "pct_de_la_inversion": float(100 * spend_tot[j] / spend_tot.sum()),
                        "pct_de_las_ventas_que_aporta": float(100 * contrib_tot[j] / df[a.y].sum()), "rango_pct_ventas": q(shares, j),
                        "retorno_por_cada_unidad_invertida": float(roi[j]), "rango_retorno_90": q(rois, j),
                        "retorno_de_la_siguiente_unidad": float(mroi[j]), "rango_siguiente_unidad_90": q(mrois, j),
                        "saturacion_pct": float(100 * satur[j]), "efecto_se_extiende_%s" % freq: float(np.log(0.5) / np.log(decs[j])) if 0 < decs[j] < 1 else 0.0,
                        "inversion_actual_por_periodo": float(x_cur[j]), "inversion_sugerida_por_periodo": float(x_opt[j]),
                        "sin_senal_detectable": bool(beta[j] <= 1e-9)})
    ranking = sorted(canales, key=lambda z: z["retorno_de_la_siguiente_unidad"], reverse=True)
    senales = []
    if base_share > 0:
        senales.append("Cerca del %.0f%% de las ventas ocurriría sin publicidad (base, tendencia y temporada)." % base_share)
    mejor, peor = ranking[0], ranking[-1]
    senales.append("La siguiente unidad invertida rinde más en %s (%.2f) y menos en %s (%.2f)." % (mejor["canal"], mejor["retorno_de_la_siguiente_unidad"], peor["canal"], peor["retorno_de_la_siguiente_unidad"]))
    for c in canales:
        if c["saturacion_pct"] > 80:
            senales.append("%s está cerca de su techo de respuesta (%.0f%% de saturación): invertir más rinde poco." % (c["canal"], c["saturacion_pct"]))
        gap = c["pct_de_las_ventas_que_aporta"] - c["pct_de_la_inversion"]
        if abs(gap) > 8:
            senales.append("%s recibe %.0f%% de la inversión y aporta %.0f%% de las ventas." % (c["canal"], c["pct_de_la_inversion"], c["pct_de_las_ventas_que_aporta"]))
        if c["sin_senal_detectable"]:
            senales.append("%s no muestra efecto detectable en estos datos. No significa que no funcione: puede faltar variación o temporada." % c["canal"])
    p_pos = float((ups > 0).mean())
    senales.append("Reasignar el mismo presupuesto (movimientos de hasta %.0f%% por canal) aportaría %+.1f%% de ventas por periodo (rango 90%%: %+.1f%% a %+.1f%%); probabilidad de mejora %.0f%%." % (
        100 * a.limite, 100 * uplift / df[a.y].mean(), 100 * np.percentile(ups, 5) / df[a.y].mean(), 100 * np.percentile(ups, 95) / df[a.y].mean(), 100 * p_pos))
    senales.append("Subir 10%% el presupuesto total y repartirlo mejor aportaría %.1f%% más de ventas por periodo." % (100 * inc_plus / df[a.y].mean()))

    if mape_out > 15:
        alertas.append("Con datos nuevos el modelo se equivoca en promedio %.0f%%." % mape_out)
    if dw < 1.3:
        alertas.append("Los errores se repiten en el tiempo: pueden faltar variables que muevan las ventas (precio, competencia, distribución).")
    for c in canales:
        lo, hi = c["rango_retorno_90"]
        ancho = (hi - lo) / max(c["retorno_por_cada_unidad_invertida"], 1e-9)
        c["incertidumbre_retorno"] = "alta" if ancho > 1.0 else "media" if ancho > 0.5 else "baja"
        if c["incertidumbre_retorno"] == "alta":
            alertas.append("El retorno de %s es muy incierto (el rango es más ancho que la cifra): no muevas dinero hacia o desde este canal sin una prueba con grupo de control." % c["canal"])
    alertas.append("Los rangos incluyen el ruido de los datos y la incertidumbre sobre la forma de la curva de cada canal. En pruebas con datos simulados contuvieron el valor real cerca del 85% de las veces (nominal 90%); no cubren que el modelo omita una variable importante.")
    if not calib:
        alertas.append("Sin experimentos de referencia (pruebas con grupo de control) la lectura es de asociación, no de causa.")
    if p_pos < 0.8:
        alertas.append("La mejora por reasignar no es segura: en %.0f%% de las simulaciones no mejora." % (100 * (1 - p_pos)))
    graves = [x for x in alertas if "casi igual" in x or "casi no cambia" in x or "equivoca" in x]
    nivel = "rojo" if (mape_out > 30 or len(graves) >= 2 or p_pos < 0.6) else "amarillo"
    if len(calib) >= max(1, m // 2) and not graves and mape_out <= 10 and T >= 104 and p_pos >= 0.8:
        nivel = "verde"
    if nivel == "verde":
        motivo = "Los experimentos de referencia, el error con datos nuevos y la estabilidad del reparto sostienen la recomendación."
    elif nivel == "rojo":
        motivo = "El modelo se equivoca demasiado con datos nuevos o la mejora de reasignar no es segura: úsalo como hipótesis y no muevas dinero."
    elif not calib:
        motivo = "Sin experimentos con grupo de control el modelo mide asociación, no causa: úsalo para decidir qué probar antes de mover un presupuesto grande."
    else:
        motivo = "Hay alertas que limitan la confianza (rangos amplios, errores con datos nuevos o poca historia): revisa la lista antes de reasignar."
    res = {"periodos": T, "frecuencia": freq, "explica_pct_de_la_variacion": float(100 * r2), "error_medio_con_datos_nuevos_pct": mape_out, "error_medio_dentro_de_la_muestra_pct": mape_in,
           "durbin_watson": dw, "semaforo": nivel, "motivo_semaforo": motivo, "calibrado_con_experimentos": bool(calib), "se_puede_recomendar_reasignacion": nivel != "rojo", "alertas": alertas, "ventas_base_pct": base_share,
           "canales": canales, "ranking_siguiente_unidad": [c["canal"] for c in ranking], "senales": senales,
           "reasignacion": {"mejora_pct_ventas_por_periodo": float(100 * uplift / df[a.y].mean()), "prob_de_mejora": p_pos,
                            "con_10pct_mas_presupuesto_mejora_pct": float(100 * inc_plus / df[a.y].mean())},
           "parametros_tecnicos": {c: {"arrastre_decay": s[0], "escala_saturacion": s[1]} for c, s in zip(ch, shapes)}}
    os.makedirs(a.outdir, exist_ok=True)
    pd.DataFrame(canales).to_csv(os.path.join(a.outdir, "mmm_canales.csv"), index=False)
    emit({"resumen": res}, os.path.join(a.outdir, "mmm.json"))


if __name__ == "__main__":
    main()
