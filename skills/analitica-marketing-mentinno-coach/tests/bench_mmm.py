#!/usr/bin/env python3
"""Prueba de la mezcla de medios contra verdad conocida, con varias semillas.

Mide: error en el aporte por canal, cobertura del rango de 90%, error en el retorno,
y si el efecto acumulado estimado se acerca al real. Sirve para validar cualquier cambio en mmm_lite.py.

Uso: python3 tests/bench_mmm.py [--semillas 8] [--boot 100] [--salida carpeta]
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(AQUI, "..", "scripts", "mmm_lite.py")
CANALES = ["tv", "busqueda", "redes", "email"]


def generar(seed, carpeta):
    rng = np.random.default_rng(seed)
    T = 156
    t = np.arange(T)

    def flights(base, p_on, amp):
        on = rng.random(T) < p_on
        return np.where(on, base * rng.lognormal(0, 0.35, T) * amp, base * 0.15)

    gasto = {"tv": flights(9000, 0.55, 1.0), "busqueda": 4000 * rng.lognormal(0, 0.25, T) * (1 + 0.2 * np.sin(2 * np.pi * t / 52)),
             "redes": flights(5000, 0.65, 1.0), "email": 800 * rng.lognormal(0, 0.3, T)}
    verd = {"tv": (0.6, 1.0, 70000), "busqueda": (0.25, 1.2, 60000), "redes": (0.45, 1.0, 30000), "email": (0.1, 1.5, 25000)}

    def adst(x, d):
        o, c = np.zeros(T), 0
        for i in range(T):
            c = x[i] + d * c
            o[i] = c
        return o

    y = 120000 + 150 * t + 15000 * np.sin(2 * np.pi * t / 52) + 9000 * np.cos(2 * np.pi * t / 52)
    promo = (rng.random(T) < 0.12).astype(int)
    y = y + 18000 * promo
    contrib = {}
    for c, (dec, kmult, beta) in verd.items():
        a = adst(gasto[c], dec)
        contrib[c] = beta * (1 - np.exp(-a / (kmult * a.mean())))
        y = y + contrib[c]
    y = y + rng.normal(0, 6000, T)
    df = pd.DataFrame({"semana": pd.date_range("2023-10-02", periods=T, freq="W-MON").strftime("%Y-%m-%d"), "ventas": y.round(0)})
    for c in gasto:
        df["gasto_" + c] = gasto[c].round(0)
    df["promocion"] = promo
    ruta = os.path.join(carpeta, "mmm_%d.csv" % seed)
    df.to_csv(ruta, index=False)
    verdad = {c: {"pct": 100 * contrib[c].sum() / y.sum(), "roi": contrib[c].sum() / gasto[c].sum(), "decay": verd[c][0]} for c in gasto}
    return ruta, verdad


def correr(seed, boot, carpeta, cal=(), err_exp=0.15):
    ruta, verdad = generar(seed, carpeta)
    out = os.path.join(carpeta, "out_%d" % seed)
    cmd = [sys.executable, SCRIPT, ruta, "--fecha", "semana", "--y", "ventas", "--canales", ",".join("gasto_" + c for c in CANALES),
           "--controles", "promocion", "--boot", str(boot), "--outdir", out]
    # experimentos simulados: miden el retorno real con un error relativo conocido
    rexp = np.random.default_rng(seed + 9000)
    for c in cal:
        medido = verdad[c]["roi"] * (1 + rexp.normal(0, err_exp))
        cmd += ["--calibrar", "gasto_%s=%.4f:%.4f" % (c, medido, err_exp * verdad[c]["roi"])]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    res = json.load(open(os.path.join(out, "mmm.json")))["resumen"]
    filas = []
    for c in res["canales"]:
        nombre = c["canal"].replace("gasto_", "")
        v = verdad[nombre]
        lo, hi = c["rango_pct_ventas"]
        rlo, rhi = c["rango_retorno_90"]
        filas.append({"semilla": seed, "canal": nombre, "pct_real": v["pct"], "pct_est": c["pct_de_las_ventas_que_aporta"],
                      "cubre_pct": lo <= v["pct"] <= hi, "roi_real": v["roi"], "roi_est": c["retorno_por_cada_unidad_invertida"],
                      "cubre_roi": rlo <= v["roi"] <= rhi, "decay_real": v["decay"], "decay_est": res["parametros_tecnicos"][c["canal"]]["arrastre_decay"],
                      "semaforo": res["semaforo"]})
    return filas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--semillas", type=int, default=8)
    ap.add_argument("--boot", type=int, default=100)
    ap.add_argument("--salida")
    ap.add_argument("--hilos", type=int, default=4)
    ap.add_argument("--calibrar", default="", help="canales con experimento simulado, por ejemplo busqueda,email")
    ap.add_argument("--error-exp", type=float, default=0.15, help="error relativo del experimento simulado")
    ap.add_argument("--sin-compuerta", action="store_true", help="solo informa, no falla")
    a = ap.parse_args()
    carpeta = a.salida or tempfile.mkdtemp(prefix="bench_mmm_")
    os.makedirs(carpeta, exist_ok=True)
    with ThreadPoolExecutor(a.hilos) as ex:
        cal = [c for c in a.calibrar.split(',') if c]
        res = list(ex.map(lambda s: correr(s, a.boot, carpeta, cal, a.error_exp), range(101, 101 + a.semillas)))
    df = pd.DataFrame([f for r in res for f in r])
    df.to_csv(os.path.join(carpeta, "bench_mmm.csv"), index=False)
    df["err_pct"] = (df.pct_est - df.pct_real).abs()
    df["err_roi_rel"] = ((df.roi_est - df.roi_real) / df.roi_real).abs()
    df["err_decay"] = (df.decay_est - df.decay_real).abs()
    por = df.groupby("canal").agg(err_pct=("err_pct", "mean"), cobertura_pct=("cubre_pct", "mean"), err_roi_rel=("err_roi_rel", "mean"),
                                  cobertura_roi=("cubre_roi", "mean"), err_decay=("err_decay", "mean"), decay_est_prom=("decay_est", "mean"))
    print(por.round(3).to_string())
    print("\nGlobal: error aporte %.2f pts | cobertura aporte %.0f%% | error retorno %.0f%% | cobertura retorno %.0f%% | error decay %.2f" % (
        df.err_pct.mean(), 100 * df.cubre_pct.mean(), 100 * df.err_roi_rel.mean(), 100 * df.cubre_roi.mean(), df.err_decay.mean()))
    print("Semaforos:", df.drop_duplicates("semilla").semaforo.value_counts().to_dict())
    print("Detalle en", carpeta)
    if a.sin_compuerta:
        return
    # compuerta de regresión: si falla, el cambio empeoró el modelo
    fallas = []
    if df.cubre_pct.mean() < 0.75:
        fallas.append("cobertura del rango menor a 75%")
    if df.err_pct.mean() > 2.6:
        fallas.append("error de aporte mayor a 2,6 puntos")
    if df.err_decay.mean() > 0.12:
        fallas.append("error del efecto acumulado mayor a 0,12")
    if fallas:
        print("FALLA:", "; ".join(fallas))
        sys.exit(1)
    print("OK: pasa la compuerta (cobertura >= 75%, error aporte <= 2,6, error efecto acumulado <= 0,12)")


if __name__ == "__main__":
    main()
