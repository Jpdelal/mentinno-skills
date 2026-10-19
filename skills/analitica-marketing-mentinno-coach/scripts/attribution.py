#!/usr/bin/env python3
"""Atribución multitoque: cómo se reparte el crédito de las conversiones entre los canales que tocó cada persona.

Compara seis formas de repartir el crédito: último clic, primer clic, lineal, decaimiento en el tiempo, por posición
y cadena de Markov (qué pasa si se quita un canal). Agrega un modelo de exposición que aprende el efecto de cada canal
con todas las personas, también las que no compraron, y estima qué parte habría ocurrido sin ningún canal.

Importante: repartir crédito no es medir efecto. Los resultados se confirman con una prueba de incrementalidad (módulos 11 y 12).

Uso: python3 attribution.py archivo --usuario id --fecha fecha --canal canal --convirtio compro [--valor monto] [--vida-media 7]
Cada fila es un contacto (toque) de una persona con un canal. La columna de conversión vale 1 en las personas que compraron.
"""
import argparse
import itertools
import math
import os
from collections import Counter

import _deps  # noqa: F401  (revisa librerías)
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from _utils import emit, load_table, need_cols, parse_dates

SI = {"1", "si", "sí", "yes", "true", "y", "s", "verdadero"}
METODOS = ["ultimo_clic", "primer_clic", "lineal", "decaimiento", "posicion", "markov", "exposicion"]


def a_binaria(s):
    if pd.api.types.is_numeric_dtype(s):
        return (s.astype(float) > 0).astype(float)
    return s.astype(str).str.strip().str.lower().isin(SI).astype(float)


# ------------------------------------------------------------------ reglas
def pesos_regla(path, tdias, m, vida_media):
    k = len(path)
    w = {n: np.zeros(m) for n in ("ultimo_clic", "primer_clic", "lineal", "decaimiento", "posicion")}
    w["ultimo_clic"][path[-1]] = 1.0
    w["primer_clic"][path[0]] = 1.0
    for c in path:
        w["lineal"][c] += 1.0 / k
    dec = 0.5 ** ((tdias[-1] - np.asarray(tdias)) / vida_media)
    dec = dec / dec.sum()
    for c, x in zip(path, dec):
        w["decaimiento"][c] += x
    if k == 1:
        w["posicion"][path[0]] = 1.0
    elif k == 2:
        w["posicion"][path[0]] += 0.5
        w["posicion"][path[1]] += 0.5
    else:
        w["posicion"][path[0]] += 0.4
        w["posicion"][path[-1]] += 0.4
        for c in path[1:-1]:
            w["posicion"][c] += 0.2 / (k - 2)
    return w


# ------------------------------------------------------------------ Markov
def _transiciones(path, conv, m):
    estados = [m] + list(path) + [m + 1 if conv else m + 2]
    return Counter(zip(estados[:-1], estados[1:]))


def _absorcion(P, m):
    T = list(range(m)) + [m]
    Q = P[np.ix_(T, T)]
    R = P[np.ix_(T, [m + 1])]
    return float(np.linalg.solve(np.eye(len(T)) - Q, R)[m, 0])


def markov_efectos(C, m):
    """Efecto de quitar cada canal: cuánto cae la probabilidad de conversión."""
    n = C.sum(1, keepdims=True)
    P = np.divide(C, n, out=np.zeros_like(C), where=n > 0)
    P[m + 1, m + 1], P[m + 2, m + 2] = 1.0, 1.0
    base = _absorcion(P, m)
    if base <= 0:
        return np.zeros(m), 0.0
    efectos = np.zeros(m)
    for c in range(m):
        P2 = P.copy()
        P2[:, m + 2] += P2[:, c]
        P2[:, c] = 0.0
        efectos[c] = max(0.0, 1 - _absorcion(P2, m) / base)
    return efectos, base


def construir_C(celdas, cuentas, m):
    C = np.zeros((m + 3, m + 3))
    for (path, conv), n in zip(celdas, cuentas):
        for (i, j), v in _transiciones(path, conv, m).items():
            C[i, j] += n * v
    return C


# ------------------------------------------------------------------ modelo de exposición (regresión + Shapley)
def _shapley_patron(bits, f_sub):
    """Reparte f(S) - f(vacío) entre los canales expuestos. f_sub(mask_tuple) devuelve la probabilidad con ese subconjunto."""
    S = [i for i, b in enumerate(bits) if b]
    k = len(S)
    phi = np.zeros(len(bits))
    if k == 0:
        return phi
    fact = [math.factorial(i) for i in range(k + 1)]
    cache = {}

    def v(sub):
        if sub not in cache:
            mask = [0] * len(bits)
            for j in sub:
                mask[j] = 1
            cache[sub] = f_sub(tuple(mask))
        return cache[sub]

    for c in S:
        otros = [x for x in S if x != c]
        for r in range(len(otros) + 1):
            for T in itertools.combinations(otros, r):
                peso = fact[r] * fact[k - r - 1] / fact[k]
                phi[c] += peso * (v(tuple(sorted(T + (c,)))) - v(T))
    return phi


def exposicion_creditos(patrones, n_conv, n_tot, m, base_identificada):
    """Devuelve (credito por canal en conversiones, credito de la base sin canal)."""
    pats = np.array(patrones, float)
    filas, y, w = [], [], []
    for p, nc, nt in zip(patrones, n_conv, n_tot):
        if nc > 0:
            filas.append(p), y.append(1), w.append(nc)
        if nt - nc > 0:
            filas.append(p), y.append(0), w.append(nt - nc)
    X = np.array(filas, float)
    lr = LogisticRegression(C=10.0, max_iter=2000).fit(X, y, sample_weight=w)
    b0, beta = float(lr.intercept_[0]), lr.coef_[0]
    sig = lambda z: 1 / (1 + math.exp(-z))
    f_sub = lambda mask: sig(b0 + float(np.dot(beta, mask)))
    f0 = f_sub(tuple([0] * m))
    cred, base = np.zeros(m), 0.0
    for p, nc in zip(patrones, n_conv):
        if nc == 0 or sum(p) == 0:
            base += nc if sum(p) == 0 else 0
            continue
        fS = f_sub(tuple(p))
        phi = np.maximum(_shapley_patron(p, f_sub), 0.0)
        frac_base = min(max(f0 / fS, 0.0), 1.0) if base_identificada else 0.0
        if phi.sum() <= 0:
            base += nc
            continue
        cred += nc * phi / phi.sum() * (1 - frac_base)
        base += nc * frac_base
    return cred, base, {"intercepto": b0, "efecto_por_canal_en_logit": beta.tolist()}


# ------------------------------------------------------------------ flujo
def preparar(df, usuario, fecha, canal, conv, valor, max_canales=8):
    cols = [usuario, fecha, canal, conv] + ([valor] if valor else [])
    d = df[cols].dropna(subset=[usuario, fecha, canal]).copy()
    d[canal] = d[canal].astype(str).str.strip()
    vol = d[canal].value_counts()
    notas = []
    if len(vol) > max_canales:
        resto = list(vol.index[max_canales - 1:])
        d[canal] = d[canal].where(~d[canal].isin(resto), "otros")
        notas.append("Se agruparon %d canales pequeños en 'otros' para que el modelo sea estable." % len(resto))
    d["_y"] = a_binaria(d[conv])
    if valor:
        d["_v"] = pd.to_numeric(d[valor], errors="coerce")
    canales = sorted(d[canal].unique())
    cid = {c: i for i, c in enumerate(canales)}
    d["_i"] = d[canal].map(cid)
    d["_t"] = (d[fecha] - d[fecha].min()).dt.total_seconds() / 86400.0
    d = d.sort_values([usuario, "_t"], kind="stable")
    g = d.groupby(usuario, sort=False)
    paths = g["_i"].apply(list)
    tiempos = g["_t"].apply(list)
    y = g["_y"].max().astype(int)
    val = g["_v"].max().fillna(0.0) if valor else pd.Series(1.0, index=y.index)
    return canales, paths, tiempos, y, val, notas


def atribuir(df, usuario, fecha, canal, conv, valor=None, vida_media=7.0, boot=100, seed=11):
    canales, paths, tiempos, y, val, notas = preparar(df, usuario, fecha, canal, conv, valor)
    m = len(canales)
    n = len(y)
    conv_total = int(y.sum())
    alertas = list(notas)
    if conv_total < 100:
        raise SystemExit("Hay solo %d conversiones: con menos de 100 no se puede repartir crédito con sentido." % conv_total)
    if conv_total == n:
        raise SystemExit("Todas las personas convirtieron. El análisis necesita también personas que tocaron canales y no compraron.")
    # reglas, por persona que compró
    idx_c = [u for u in paths.index if y[u] == 1]
    W = {k: np.zeros((len(idx_c), m)) for k in ("ultimo_clic", "primer_clic", "lineal", "decaimiento", "posicion")}
    for r, u in enumerate(idx_c):
        w = pesos_regla(paths[u], tiempos[u], m, vida_media)
        for k in W:
            W[k][r] = w[k]
    vc = val[idx_c].values.astype(float)
    # celdas únicas para Markov y exposición
    celdas = Counter((tuple(paths[u]), int(y[u])) for u in paths.index)
    claves = list(celdas.keys())
    cuentas = np.array([celdas[k] for k in claves], float)
    C = construir_C(claves, cuentas, m)
    ef, p_conv = markov_efectos(C, m)
    cred = {k: W[k].sum(0) for k in W}
    cred["markov"] = ef / ef.sum() * conv_total if ef.sum() > 0 else np.zeros(m)
    # exposición
    pat_c = Counter()
    pat_t = Counter()
    for u in paths.index:
        bits = tuple(1 if i in set(paths[u]) else 0 for i in range(m))
        pat_t[bits] += 1
        pat_c[bits] += int(y[u])
    pats = list(pat_t.keys())
    n_sin = pat_t.get(tuple([0] * m), 0)
    base_ident = n_sin >= max(200, 0.02 * n)
    if not base_ident:
        alertas.append("Casi no hay personas sin ningún contacto (%d de %d): no se puede estimar cuántas conversiones habrían ocurrido sin ningún canal, y todo el crédito se reparte entre canales." % (n_sin, n))
    pat_idx = {p: i for i, p in enumerate(pats)}
    celda_pat = np.array([pat_idx[tuple(1 if i in set(pth) else 0 for i in range(m))] for pth, _ in claves])
    celda_conv = np.array([cv for _, cv in claves], float)
    ce, base_c, coefs = exposicion_creditos(pats, [pat_c[p] for p in pats], [pat_t[p] for p in pats], m, base_ident)
    cred["exposicion"] = ce
    # rangos por remuestreo
    rng = np.random.default_rng(seed)
    pct = {k: cred[k] / max(cred[k].sum() + (base_c if k == "exposicion" else 0), 1e-12) for k in METODOS}
    rangos = {k: [] for k in METODOS}
    for _ in range(boot):
        cnt = rng.multinomial(len(idx_c), np.ones(len(idx_c)) / len(idx_c))
        for k in W:
            c_ = cnt @ W[k]
            rangos[k].append(c_ / max(c_.sum(), 1e-12))
        cb = rng.multinomial(int(cuentas.sum()), cuentas / cuentas.sum()).astype(float)
        Cb = construir_C(claves, cb, m)
        efb, _ = markov_efectos(Cb, m)
        rangos["markov"].append(efb / efb.sum() if efb.sum() > 0 else np.zeros(m))
        pc_b = np.bincount(celda_pat, weights=cb * celda_conv, minlength=len(pats))
        pt_b = np.bincount(celda_pat, weights=cb, minlength=len(pats))
        ceb, bb, _ = exposicion_creditos(pats, pc_b, pt_b, m, base_ident)
        rangos["exposicion"].append(ceb / max(ceb.sum() + bb, 1e-12))
    # tabla por canal
    posic = {i: [] for i in range(m)}
    ultimo = Counter()
    multi = Counter()
    primero = Counter()
    for u in paths.index:
        p = paths[u]
        if len(p) >= 2:
            for j, c in enumerate(p):
                posic[c].append(j / (len(p) - 1))
                multi[c] += 1
            ultimo[p[-1]] += 1
            primero[p[0]] += 1
    filas = []
    for i, c in enumerate(canales):
        fila = {"canal": c, "personas_alcanzadas": int(sum(v for k, v in pat_t.items() if k[i])), "toques": int(sum(p.count(i) for p in paths))}
        for k in METODOS:
            lo, hi = np.percentile(np.array(rangos[k])[:, i], [5, 95]) if boot else (None, None)
            fila[k] = {"conversiones": float(cred[k][i]), "pct": float(pct[k][i]), "rango_pct_90": [None if lo is None else float(lo), None if hi is None else float(hi)]}
        fila["pct_min_entre_modelos"], fila["pct_max_entre_modelos"] = float(min(fila[k]["pct"] for k in METODOS)), float(max(fila[k]["pct"] for k in METODOS))
        fila["posicion_media_en_rutas_de_2_o_mas"] = float(np.mean(posic[i])) if posic[i] else None
        fila["veces_ultimo_en_rutas_de_2_o_mas_pct"] = float(ultimo[i] / multi[i]) if multi[i] else None
        if valor:
            for k in ("ultimo_clic", "primer_clic", "lineal", "decaimiento", "posicion"):
                fila[k]["valor"] = float((W[k][:, i] * vc).sum())
        filas.append(fila)
    # canales de cierre: cobran al final y es donde más crédito reciben
    senales = []
    for i, f in enumerate(filas):
        prop_ultimo = ultimo[i] / multi[i] if multi[i] else 0.0
        # un canal "de cierre" aparece casi siempre al final de las rutas de 2 o más contactos
        f["canal_de_cierre"] = bool(prop_ultimo >= 0.6 and multi[i] >= 100)
        if f["canal_de_cierre"]:
            senales.append("%s casi siempre aparece al final del recorrido (%.0f%% de sus contactos en rutas de 2 o más). Puede estar cobrando ventas que ya iban a ocurrir: confirma con una prueba de incrementalidad antes de darle más presupuesto." % (f["canal"], 100 * prop_ultimo))
    desacuerdo = [f["canal"] for f in filas if (f["pct_max_entre_modelos"] - f["pct_min_entre_modelos"]) > 0.15]
    if desacuerdo:
        senales.append("Los modelos no se ponen de acuerdo en %s (diferencias de más de 15 puntos): el crédito de esos canales depende del método, no de los datos." % ", ".join(desacuerdo))
    base_pct = float(base_c / (cred["exposicion"].sum() + base_c)) if base_ident else None
    if base_pct is not None:
        senales.append("El modelo de exposición estima que cerca de %.0f%% de las conversiones habría ocurrido sin ningún canal." % (100 * base_pct))
    largo = float(np.mean([len(paths[u]) for u in idx_c]))
    una = float(np.mean([len(paths[u]) == 1 for u in idx_c]))
    if una > 0.7:
        alertas.append("%.0f%% de las conversiones tuvo un solo contacto: las reglas dan casi lo mismo y la atribución multitoque aporta poco." % (100 * una))
    if min(f["personas_alcanzadas"] for f in filas) < 200:
        alertas.append("Algún canal alcanza a menos de 200 personas: su resultado es muy inestable.")
    alertas.append("Repartir crédito no es medir efecto: los cuatro tipos de resultado de abajo se confirman con una prueba de incrementalidad (módulos 11 y 12).")
    nivel = "amarillo"
    motivo = "Los modelos reparten el crédito de formas distintas y ninguno mide efecto causal por sí solo: úsalo para decidir qué probar, no para mover presupuesto grande sin una prueba."
    res = {"personas": n, "conversiones": conv_total, "contactos_por_conversion": largo, "conversiones_de_un_solo_contacto_pct": una, "vida_media_dias": vida_media,
           "por_canal": filas, "base_sin_canal_pct": base_pct, "modelo_exposicion": dict(coefs, canales=canales), "semaforo": nivel, "motivo_semaforo": motivo, "alertas": alertas, "senales": senales,
           "rutas_mas_frecuentes": [{"ruta": " > ".join(canales[i] for i in k[0]), "convirtio": bool(k[1]), "personas": int(celdas[k])} for k in sorted(celdas, key=celdas.get, reverse=True)[:10]]}
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--usuario", required=True)
    ap.add_argument("--fecha", required=True)
    ap.add_argument("--canal", required=True)
    ap.add_argument("--convirtio", required=True)
    ap.add_argument("--valor")
    ap.add_argument("--vida-media", type=float, default=7.0, dest="vida")
    ap.add_argument("--boot", type=int, default=100)
    ap.add_argument("--hoja")
    ap.add_argument("--mdy", action="store_true")
    ap.add_argument("--outdir", default="resultados")
    a = ap.parse_args()
    df = load_table(a.file, a.hoja)
    need_cols(df, [a.usuario, a.fecha, a.canal, a.convirtio] + ([a.valor] if a.valor else []))
    df[a.fecha] = parse_dates(df[a.fecha], a.mdy)
    res = atribuir(df, a.usuario, a.fecha, a.canal, a.convirtio, a.valor, a.vida, a.boot)
    os.makedirs(a.outdir, exist_ok=True)
    tabla = pd.DataFrame([{"canal": f["canal"], **{k: f[k]["pct"] for k in METODOS}} for f in res["por_canal"]])
    tabla.to_csv(os.path.join(a.outdir, "atribucion_por_canal.csv"), index=False)
    emit({"resumen": res}, os.path.join(a.outdir, "atribucion.json"))


if __name__ == "__main__":
    main()
