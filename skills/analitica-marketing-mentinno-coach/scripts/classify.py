#!/usr/bin/env python3
"""Quién va a comprar, abandonar o responder (resultado sí/no), con tabla de priorización por deciles.

Uso: python3 classify.py archivo --y baja --x antiguedad,tickets,plan [--fecha fecha_alta]
        [--valor 120 --costo 5] [--test 0.3]
"""
import argparse
import os

import _deps  # noqa: F401  (revisa librerías)
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from _utils import emit, load_table, need_cols, parse_dates

SI = {"1", "si", "sí", "yes", "true", "y", "s", "verdadero"}


def a_binaria(s):
    if pd.api.types.is_numeric_dtype(s):
        return s.astype(float)
    return s.astype(str).str.strip().str.lower().isin(SI).astype(float).where(s.notna())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--y", required=True)
    ap.add_argument("--x", required=True)
    ap.add_argument("--fecha")
    ap.add_argument("--valor", type=float, help="valor de una conversión o de retener un cliente")
    ap.add_argument("--costo", type=float, help="costo de contactar a una persona")
    ap.add_argument("--test", type=float, default=0.3)
    ap.add_argument("--hoja")
    ap.add_argument("--mdy", action="store_true")
    ap.add_argument("--outdir", default="resultados")
    a = ap.parse_args()

    df = load_table(a.file, a.hoja)
    xs = [c.strip() for c in a.x.split(",")]
    need_cols(df, [a.y] + xs + ([a.fecha] if a.fecha else []))
    d = df.copy()
    d["_y"] = a_binaria(d[a.y])
    d = d.dropna(subset=["_y"])
    if a.fecha:
        d["_f"] = parse_dates(d[a.fecha], a.mdy)
        d = d.sort_values("_f").reset_index(drop=True)
    else:
        d = d.reset_index(drop=True)
    y = d["_y"].astype(int)
    notas, descartadas = [], []
    num = [c for c in xs if pd.api.types.is_numeric_dtype(d[c])]
    cat = [c for c in xs if c not in num and d[c].nunique() <= 20]
    descartadas = [c for c in xs if c not in num and c not in cat]
    if descartadas:
        notas.append("Se descartaron variables de texto con demasiadas categorías: %s." % descartadas)
    partes = []
    if num:
        partes.append(d[num].apply(lambda s: s.fillna(s.median())))
    if cat:
        partes.append(pd.get_dummies(d[cat].astype(str), drop_first=True, dtype=float))
    if not partes:
        raise SystemExit("Ninguna de las variables elegidas se puede usar: son texto con demasiadas categorías o no existen. Elige otras o agrupa las categorías.")
    X = pd.concat(partes, axis=1)
    feats = list(X.columns)
    n, base = len(d), float(y.mean())

    if a.fecha:
        k = int(round(n * (1 - a.test)))
        itr, ite = np.arange(k), np.arange(k, n)
        split = "por fecha: se entrena con lo más antiguo y se prueba con lo más reciente"
    else:
        itr, ite = train_test_split(np.arange(n), test_size=a.test, random_state=42, stratify=y)
        split = "aleatoria: %d%% para probar" % round(100 * a.test)
    Xtr, Xte, ytr, yte = X.iloc[itr], X.iloc[ite], y.iloc[itr], y.iloc[ite]
    if yte.nunique() < 2:
        raise SystemExit("El grupo de prueba no tiene casos de ambos resultados. Usa más datos o cambia la partición.")

    sc = StandardScaler().fit(Xtr)
    lr = LogisticRegression(max_iter=2000).fit(sc.transform(Xtr), ytr)
    p_lr = lr.predict_proba(sc.transform(Xte))[:, 1]
    gb = HistGradientBoostingClassifier(max_depth=3, max_iter=200, learning_rate=0.06, random_state=1).fit(Xtr, ytr)
    p_gb = gb.predict_proba(Xte)[:, 1]
    auc_lr, auc_gb = roc_auc_score(yte, p_lr), roc_auc_score(yte, p_gb)
    usa_gb = auc_gb - auc_lr >= 0.02
    modelo, p = ("boosting", p_gb) if usa_gb else ("regresión logística", p_lr)

    # tabla por deciles
    q = pd.DataFrame({"p": p, "y": yte.values})
    q["decil"] = pd.qcut(q["p"].rank(method="first", ascending=False), 10, labels=False) + 1
    tab = q.groupby("decil").agg(personas=("y", "size"), tasa_real=("y", "mean"), prob_estimada=("p", "mean")).reset_index()
    tab["lift"] = tab["tasa_real"] / q["y"].mean()
    tab["ganancia_acumulada_pct"] = 100 * (tab["tasa_real"] * tab["personas"]).cumsum() / (tab["tasa_real"] * tab["personas"]).sum()
    brecha = float((tab["tasa_real"] - tab["prob_estimada"]).abs().mean())
    brier, brier_ref = brier_score_loss(yte, p), brier_score_loss(yte, np.full(len(yte), ytr.mean()))

    # fuga de información
    sospechas = []
    for c in feats:
        v = X[c]
        if v.nunique() > 1:
            au = roc_auc_score(y, v)
            if max(au, 1 - au) > 0.90:
                sospechas.append(c)
    fuga = auc_lr > 0.95 or auc_gb > 0.95 or bool(sospechas)

    # factores
    coef = pd.Series(lr.coef_[0], index=feats)
    mult = np.exp(coef)
    top = coef.abs().sort_values(ascending=False).head(6).index
    factores = [{"variable": c, "efecto": "aumenta" if coef[c] > 0 else "reduce", "multiplicador_de_probabilidad_relativa_por_cada_desviacion": float(mult[c])} for c in top]

    epv = float(ytr.sum() if ytr.mean() < 0.5 else (1 - ytr).sum()) / max(len(feats), 1)
    senales = ["Tasa base: %.1f%%. El 10%% con mayor puntaje concentra %.0f%% de los casos reales (%.1f veces el promedio)." % (100 * base, tab["ganancia_acumulada_pct"].iloc[0], tab["lift"].iloc[0]),
               "El 30%% con mayor puntaje concentra %.0f%% de los casos reales." % tab["ganancia_acumulada_pct"].iloc[2]]
    if usa_gb:
        senales.append("Un modelo más complejo mejora el AUC en %.3f; úsalo para priorizar, pero explica menos." % (auc_gb - auc_lr))
    else:
        senales.append("Un modelo más complejo no mejora de forma relevante (diferencia de AUC %.3f): se usa el explicable." % (auc_gb - auc_lr))
    if a.valor is not None and a.costo is not None:
        tab["ganancia_neta_por_persona"] = tab["tasa_real"] * a.valor - a.costo
        rentables = tab[tab["ganancia_neta_por_persona"] > 0]
        todos = float((tab["ganancia_neta_por_persona"] * tab["personas"]).sum())
        sel = float((rentables["ganancia_neta_por_persona"] * rentables["personas"]).sum())
        senales.append("Con valor %.0f y costo %.0f por contacto, conviene actuar sobre los deciles %s. Ganancia neta en la muestra de prueba: %.0f, frente a %.0f si contactas a todos." % (a.valor, a.costo, list(rentables["decil"]) or "ninguno", sel, todos))
        senales.append("Ojo: esto mide quién tiene más probabilidad, no a quién influye tu acción. Una prueba con grupo de control confirma el efecto real.")
    alertas = []
    if fuga:
        alertas.append("Resultado demasiado perfecto (AUC %.2f). Probable fuga de información%s: variable que ya contiene la respuesta." % (max(auc_lr, auc_gb), (" en: " + ", ".join(sospechas)) if sospechas else ""))
    if epv < 10:
        alertas.append("Pocos casos del grupo menor para tantas variables (%.1f por variable; conviene al menos 10)." % epv)
    if brecha > 0.05:
        alertas.append("Las probabilidades no están bien calibradas (brecha media %.1f puntos). Sirven para ordenar, no para leer como porcentaje." % (100 * brecha))
    if auc_lr < 0.65 and auc_gb < 0.65:
        alertas.append("Capacidad de ordenar baja: las variables disponibles dicen poco sobre quién responde.")
    # rango del AUC por remuestreo del grupo de prueba
    rng = np.random.default_rng(11)
    yv, aucs = yte.values, []
    for _ in range(300):
        i = rng.integers(0, len(yv), len(yv))
        if yv[i].min() != yv[i].max():
            aucs.append(roc_auc_score(yv[i], p[i]))
    auc_sel = float(roc_auc_score(yte, p))
    auc_lo, auc_hi = (float(np.percentile(aucs, 5)), float(np.percentile(aucs, 95))) if aucs else (auc_sel, auc_sel)
    lift_top = float(tab["lift"].iloc[0])
    if auc_hi - auc_lo > 0.10:
        alertas.append("Con tan pocos casos de prueba el AUC es muy impreciso (entre %.2f y %.2f)." % (auc_lo, auc_hi))
    dinero = a.valor is not None and a.costo is not None
    if fuga:
        nivel, motivo = "rojo", "El resultado es demasiado perfecto: casi seguro hay una variable que ya contiene la respuesta."
    elif auc_sel < 0.6 or auc_lo < 0.55:
        nivel, motivo = "rojo", "El modelo ordena apenas mejor que el azar (AUC %.2f, rango %.2f a %.2f): no sirve para decidir a quién contactar." % (auc_sel, auc_lo, auc_hi)
    elif alertas:
        nivel, motivo = "amarillo", "Hay advertencias que limitan lo que se puede afirmar; revísalas antes de actuar."
    elif auc_lo >= 0.70 and lift_top >= 2.0:
        nivel, motivo = "verde", "Ordena bien (AUC %.2f, rango %.2f a %.2f) y el 10%% de arriba concentra %.1f veces el promedio." % (auc_sel, auc_lo, auc_hi, lift_top)
    else:
        nivel, motivo = "amarillo", "Ordena de forma útil pero no concluyente (AUC %.2f, rango %.2f a %.2f; el 10%% de arriba concentra %.1f veces el promedio)." % (auc_sel, auc_lo, auc_hi, lift_top)
    if dinero and nivel == "verde":
        nivel = "amarillo"
        motivo += " Como hay dinero en juego, queda en amarillo: el modelo mide quién tiene más probabilidad, no a quién influye tu acción. Confirma con una prueba con grupo de control."

    # puntaje para todos
    model_all = (lambda Z: gb.predict_proba(Z)[:, 1]) if usa_gb else (lambda Z: lr.predict_proba(sc.transform(Z))[:, 1])
    out = d.drop(columns=["_y"] + (["_f"] if a.fecha else []))
    out["probabilidad"] = model_all(X)
    out["decil"] = pd.qcut(out["probabilidad"].rank(method="first", ascending=False), 10, labels=False) + 1
    out["conjunto"] = "entrenamiento"
    out.loc[out.index[ite], "conjunto"] = "prueba"
    os.makedirs(a.outdir, exist_ok=True)
    f_scores = os.path.join(a.outdir, "puntajes_clientes.csv")
    out.to_csv(f_scores, index=False)
    res = {"filas": n, "tasa_base_pct": 100 * base, "particion": split, "modelo_recomendado": modelo, "auc": {"logistica": auc_lr, "boosting": auc_gb},
           "precision_promedio": float(average_precision_score(yte, p)), "error_cuadratico_vs_adivinar": [brier, brier_ref], "brecha_calibracion": brecha,
           "semaforo": nivel, "motivo_semaforo": motivo, "auc_rango_90": [auc_lo, auc_hi], "alertas": alertas + notas, "tabla_deciles": tab.round(4).to_dict("records"), "factores": factores, "senales": senales,
           "casos_por_variable": epv, "archivo_puntajes": f_scores}
    emit({"resumen": res}, os.path.join(a.outdir, "clasificacion.json"))


if __name__ == "__main__":
    main()
