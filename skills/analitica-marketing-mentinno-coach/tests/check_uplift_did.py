#!/usr/bin/env python3
"""Prueba de uplift y diferencias en diferencias contra verdad conocida.

Diferencias en diferencias: cobertura del rango, falsos positivos, detección de grupos que no iban en paralelo,
pocas unidades, fechas y retorno incremental.
Uplift: ranking frente al efecto real, falsos hallazgos sin diferencias reales, asignación no aleatoria,
comparación contra ordenar por probabilidad de compra.

Uso: python3 tests/check_uplift_did.py
"""
import json
import os
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

AQUI = os.path.dirname(os.path.abspath(__file__))
SCR = os.path.join(AQUI, "..", "scripts")
sys.path.insert(0, SCR)
import uplift_did as ud  # noqa: E402

rng = np.random.default_rng(77)
fallas = []


def chequeo(nombre, valor, ok, detalle=""):
    print("%-72s %-14s %s %s" % (nombre, valor, "OK" if ok else "FALLA", detalle))
    if not ok:
        fallas.append(nombre)


# ------------------------------------------------------------------ diferencias en diferencias
def panel(n_t, n_c, T, t0, tau, dif_tendencia=0.0, seed=0, fechas=False):
    r = np.random.default_rng(seed)
    n = n_t + n_c
    a = r.normal(100, 15, n)
    t = np.arange(T)
    comun = 0.5 * t + 10 * np.sin(2 * np.pi * t / 12)
    trat = np.r_[np.ones(n_t), np.zeros(n_c)]
    y = a[:, None] + comun[None, :] + dif_tendencia * t[None, :] * trat[:, None] + tau * (t[None, :] >= t0) * trat[:, None] + r.normal(0, 4, (n, T))
    df = pd.DataFrame({"tienda": np.repeat(np.arange(n), T), "periodo": np.tile(t, n), "grupo": np.repeat(np.where(trat == 1, "campana", "control"), T), "ventas": y.ravel()})
    if fechas:
        df["periodo"] = (pd.Timestamp("2025-01-06") + pd.to_timedelta(df["periodo"] * 7, unit="D")).dt.strftime("%Y-%m-%d")
    return df


TAU, T0, S = 5.0, 20, 300
cubre = pos = verde = 0
for s in range(S):
    r = ud.did_cmd(panel(15, 15, 30, T0, TAU, seed=s), "tienda", "periodo", "grupo", "ventas", T0)
    cubre += r["rango_95"][0] <= TAU <= r["rango_95"][1]
    verde += r["semaforo"] == "verde"
chequeo("Diferencias en diferencias: cobertura del rango 95% (efecto real 5)", "%.1f%%" % (100 * cubre / S), 0.92 <= cubre / S <= 0.98, "(%d paneles)" % S)
chequeo("Con grupos paralelos y efecto real, el semáforo es verde casi siempre", "%.0f%%" % (100 * verde / S), verde / S >= 0.75)

fp = noverde = 0
for s in range(S):
    r = ud.did_cmd(panel(15, 15, 30, T0, 0.0, seed=1000 + s), "tienda", "periodo", "grupo", "ventas", T0)
    fp += (r["rango_95"][0] > 0 or r["rango_95"][1] < 0)
    noverde += r["semaforo"] != "verde"
chequeo("Sin efecto real: falsos positivos del rango (meta 5%)", "%.1f%%" % (100 * fp / S), 0.02 <= fp / S <= 0.09)
chequeo("Sin efecto real: el semáforo no es verde casi siempre", "%.0f%%" % (100 * noverde / S), noverde / S >= 0.90)

flag = sesgo = 0
for s in range(S):
    r = ud.did_cmd(panel(15, 15, 30, T0, 0.0, dif_tendencia=0.35, seed=2000 + s), "tienda", "periodo", "grupo", "ventas", T0)
    flag += r["semaforo"] in ("amarillo", "rojo")
    sesgo += r["efecto_por_unidad_y_periodo"]
chequeo("Grupos que no iban en paralelo: se advierte (amarillo o rojo)", "%.0f%%" % (100 * flag / S), flag / S >= 0.80, "(sesgo medio sin la advertencia: %+.1f)" % (sesgo / S))

nv = 0
for s in range(100):
    r = ud.did_cmd(panel(3, 3, 30, T0, TAU, seed=3000 + s), "tienda", "periodo", "grupo", "ventas", T0)
    nv += r["semaforo"] == "verde"
chequeo("Con solo 3 unidades por grupo nunca es verde", "%d de 100" % nv, nv == 0)

# retorno incremental con verdad conocida
gasto, c_roas = 9000.0, 0
verdad = TAU * 15 * 10 / gasto
for s in range(200):
    r = ud.did_cmd(panel(15, 15, 30, T0, TAU, seed=4000 + s), "tienda", "periodo", "grupo", "ventas", T0, gasto=gasto)
    lo, hi = r["retorno_incremental"]["rango_95"]
    c_roas += lo <= verdad <= hi
chequeo("Cobertura del retorno incremental (real %.2f)" % verdad, "%.1f%%" % (100 * c_roas / 200), 0.90 <= c_roas / 200 <= 0.99)

# fechas como periodo y línea de comandos
carpeta = tempfile.mkdtemp(prefix="chk_did_")
ruta = os.path.join(carpeta, "panel.csv")
panel(12, 12, 30, T0, TAU, seed=5, fechas=True).to_csv(ruta, index=False)
fecha_int = (pd.Timestamp("2025-01-06") + pd.Timedelta(weeks=T0)).strftime("%Y-%m-%d")
o = subprocess.run([sys.executable, os.path.join(SCR, "uplift_did.py"), "did", ruta, "--unidad", "tienda", "--periodo", "periodo", "--grupo", "grupo", "--resultado", "ventas",
                    "--fecha-intervencion", fecha_int, "--control", "control", "--gasto", "7000", "--outdir", carpeta], capture_output=True, text=True)
ok = o.returncode == 0
j = json.loads(o.stdout) if ok else {}
chequeo("Línea de comandos con fechas: efecto estimado cerca de 5", "%.2f" % j.get("efecto_por_unidad_y_periodo", float("nan")), ok and abs(j["efecto_por_unidad_y_periodo"] - TAU) < 2.5)


# ------------------------------------------------------------------ uplift
def sim_uplift(n, seed, heterogeneo=True, confundido=False, tau_const=0.05):
    r = np.random.default_rng(seed)
    X = pd.DataFrame({"x1": r.normal(size=n), "x2": r.normal(size=n), "x3": r.normal(size=n), "x4": r.normal(size=n)})
    pc = 1 / (1 + np.exp(-(-1.2 + 1.3 * X.x2 + 0.3 * X.x3)))
    tau = 0.20 / (1 + np.exp(-3 * X.x1)) * (1 - pc) - 0.01 if heterogeneo else np.full(n, tau_const)
    pt = np.clip(pc + tau, 0.001, 0.999)
    t = (r.random(n) < (1 / (1 + np.exp(-1.6 * X.x2)) if confundido else 0.5)).astype(int)
    y = (r.random(n) < np.where(t == 1, pt, pc)).astype(int)
    d = X.copy()
    d["grupo"] = np.where(t == 1, "campana", "control")
    d["compro"] = y
    return d, np.asarray(tau)


N = 20000
rhos, verdes, mejora = [], 0, []
for s in range(10):
    d, tau = sim_uplift(N, s)
    res, out = ud.uplift_cmd(d, "grupo", "compro", ["x1", "x2", "x3", "x4"], control="control", boot=150)
    rhos.append(spearmanr(out["uplift_predicho"], tau)[0])
    verdes += res["semaforo"] == "verde"
    top_u = out["decil_uplift"] <= 3
    # ordenar por probabilidad de compra (modelo común, sin mirar la acción)
    from sklearn.linear_model import LogisticRegression
    pm = LogisticRegression(max_iter=2000).fit(d[["x1", "x2", "x3", "x4"]], d["compro"]).predict_proba(d[["x1", "x2", "x3", "x4"]])[:, 1]
    top_p = pd.Series(pm).rank(ascending=False, method="first") <= 0.3 * N
    mejora.append(tau[top_u.values].mean() - tau[top_p.values].mean())
chequeo("Uplift: correlación de rangos entre el puntaje y el efecto real", "%.2f" % np.mean(rhos), np.mean(rhos) >= 0.5)
# signo y tamaño del efecto: el promedio estimado debe coincidir con el efecto verdadero y el decil 1 debe rendir más que el 10
d0, tau0 = sim_uplift(N, 0)
res0, _ = ud.uplift_cmd(d0, "grupo", "compro", ["x1", "x2", "x3", "x4"], control="control", boot=100)
lo0, hi0 = res0["rango_efecto_promedio_95"]
chequeo("Efecto promedio: mismo signo y rango que contiene el efecto verdadero", "%+.3f (real %+.3f)" % (res0["efecto_promedio"], tau0.mean()), lo0 <= tau0.mean() <= hi0 and res0["efecto_promedio"] * tau0.mean() > 0)
dec = res0["tabla_deciles"]
chequeo("Decil 1 observado mayor que el decil 10 (signo del efecto por decil)", "%+.3f vs %+.3f" % (dec[0]["uplift_observado"], dec[-1]["uplift_observado"]), dec[0]["uplift_observado"] > dec[-1]["uplift_observado"] + 0.05)
d1 = d0.copy()
d1["compro"] = (np.random.default_rng(1).random(len(d1)) < np.where(d1["grupo"] == "campana", 0.30, 0.20)).astype(int)
res1, _ = ud.uplift_cmd(d1, "grupo", "compro", ["x1", "x2", "x3", "x4"], control="control", boot=50)
chequeo("Efecto promedio con diferencia conocida de +10 puntos", "%+.3f" % res1["efecto_promedio"], abs(res1["efecto_promedio"] - 0.10) < 0.02)
chequeo("Uplift con diferencias reales: el semáforo es verde", "%d de 10" % verdes, verdes >= 8)
chequeo("Dirigir por uplift rinde más que por probabilidad de compra (efecto real medio, 30% de arriba)", "%+.3f" % np.mean(mejora), np.mean(mejora) > 0.02 and all(m > 0 for m in mejora))

nulos = 0
for s in range(30):
    d, tau = sim_uplift(N, 100 + s, heterogeneo=False)
    res, _ = ud.uplift_cmd(d, "grupo", "compro", ["x1", "x2", "x3", "x4"], control="control", boot=150)
    nulos += res["semaforo"] == "verde"
chequeo("Sin diferencias reales entre personas: falsos hallazgos (meta cerca de 5%)", "%.0f%%" % (100 * nulos / 30), nulos / 30 <= 0.15)

conf = 0
for s in range(10):
    d, tau = sim_uplift(N, 200 + s, confundido=True)
    res, _ = ud.uplift_cmd(d, "grupo", "compro", ["x1", "x2", "x3", "x4"], control="control", boot=100)
    conf += res["semaforo"] == "rojo"
chequeo("Asignación no aleatoria (la acción llegó más a quienes compran más): rojo", "%d de 10" % conf, conf >= 9)

rho_tree = []
for s in range(3):
    d, tau = sim_uplift(30000, 300 + s)
    res, out = ud.uplift_cmd(d, "grupo", "compro", ["x1", "x2", "x3", "x4"], control="control", modelo="arboles", boot=100)
    rho_tree.append(spearmanr(out["uplift_predicho"], tau)[0])
chequeo("Modelo de árboles también ordena (correlación con el efecto real)", "%.2f" % np.mean(rho_tree), np.mean(rho_tree) >= 0.35)

d, tau = sim_uplift(N, 7)
ruta = os.path.join(carpeta, "uplift.csv")
d.to_csv(ruta, index=False)
o = subprocess.run([sys.executable, os.path.join(SCR, "uplift_did.py"), "uplift", ruta, "--tratamiento", "grupo", "--y", "compro", "--x", "x1,x2,x3,x4", "--control", "control",
                    "--valor", "100", "--costo", "8", "--outdir", carpeta], capture_output=True, text=True)
ok = o.returncode == 0 and os.path.exists(os.path.join(carpeta, "puntajes_uplift.csv"))
chequeo("Línea de comandos de uplift y archivo de puntajes", "ok" if ok else o.stderr[-100:], ok)

print()
if fallas:
    print("FALLAN %d chequeo(s):" % len(fallas))
    for f in fallas:
        print(" -", f)
    sys.exit(1)
print("OK: uplift y diferencias en diferencias validados contra verdad conocida")
