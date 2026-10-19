#!/usr/bin/env python3
"""Prueba del valor de vida del cliente contra verdad conocida.

Genera clientes con compras libres y abandono (proceso conocido) y verifica: error en compras y en ingresos
sobre las semanas que el modelo no vio, recuperación de parámetros, proyección a 12 meses frente al futuro simulado,
y que el semáforo no sea verde cuando el modelo no aplica (suscripción, salto de demanda, pocos datos, monto ligado a la frecuencia).

Uso: python3 tests/check_clv.py
"""
import json
import os
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
SCR = os.path.join(AQUI, "..", "scripts")
sys.path.insert(0, SCR)
import clv  # noqa: E402

ORIGEN = pd.Timestamp("2023-01-02")
fallas = []


def chequeo(nombre, valor, ok, detalle=""):
    print("%-78s %-12s %s %s" % (nombre, valor, "OK" if ok else "FALLA", detalle))
    if not ok:
        fallas.append(nombre)


def simular(n, seed, semanas_adq=104, semanas_total=182, r=0.6, alpha=12.0, a=1.5, b=3.0, p=6.0, q=4.0, gam=15.0,
            monto_ligado=False, regular=False):
    """Compras libres con abandono (BG/NBD) y monto por compra (Gamma-Gamma). Devuelve compras con semana continua."""
    rg = np.random.default_rng(seed)
    filas = []
    for i in range(n):
        lam = rg.gamma(r, 1 / alpha)
        pd_ = rg.beta(a, b)
        nu = rg.gamma(q, 1 / gam)
        t = rg.uniform(0, semanas_adq)
        compras = [t]
        while True:
            t += 4.0 if regular else rg.exponential(1 / lam)
            if t > semanas_total:
                break
            compras.append(t)
            # el abandono solo puede ocurrir después de una compra repetida (supuesto del modelo)
            if rg.random() < pd_:
                break
        for t in compras:
            filas.append((i, t))
    d = pd.DataFrame(filas, columns=["cliente", "semana"])
    if monto_ligado:
        k = d.groupby("cliente")["semana"].transform("size")
        escala = 1 + 0.5 * (k - 1)
        d["monto"] = rg.gamma(p, 1 / gam, len(d)) * escala
    else:
        nus = rg.gamma(q, 1 / gam, n)
        d["monto"] = rg.gamma(p, 1 / nus[d["cliente"].values])
    d["fecha"] = ORIGEN + pd.to_timedelta(np.floor(d["semana"] * 7), unit="D")
    return d


def hasta(d, semana):
    return d[d["semana"] <= semana].copy()


# 1. Prueba con compras que el modelo no vio, 4 semillas
errs_n, errs_v, verdes, ratios, rate_err, drop_err, mu_err, fut_err = [], [], 0, [], [], [], [], []
for s in range(4):
    d = simular(6000, 10 + s)
    obs = hasta(d, 130)
    res, out = clv.clv_cmd(obs, "cliente", "fecha", "monto", corte=ORIGEN + pd.Timedelta(weeks=130), horizonte=12, meses_val=6)
    v = res["prueba_con_datos_nuevos"]
    errs_n.append(abs(v["error_compras_totales"]))
    errs_v.append(abs(v["error_ingresos_totales"]))
    verdes += res["semaforo"] == "verde"
    for g in v["por_grupo"]:
        ratios.append(g["compras_predichas"] / max(g["compras_reales"], 1e-9))
    m = res["modelo"]["compras"]
    rate_err.append(abs(m["r"] / m["alpha"] - 0.6 / 12.0) / (0.6 / 12.0))
    drop_err.append(abs(m["a"] / (m["a"] + m["b"]) - 1.5 / 4.5) / (1.5 / 4.5))
    mu_err.append(abs(res["modelo"]["monto_medio_poblacion"] - 30.0) / 30.0)
    # futuro verdadero: compras entre las semanas 130 y 182 de los clientes ya adquiridos
    fut = d[(d["semana"] > 130)]
    reales = fut[fut["cliente"].isin(out.index)].shape[0]
    fut_err.append(abs(out["compras_esperadas_12m"].sum() - reales) / reales)
chequeo("Error en compras de las semanas no vistas (promedio de 4 simulaciones)", "%.1f%%" % (100 * np.mean(errs_n)), np.mean(errs_n) < 0.08)
chequeo("Error en ingresos de las semanas no vistas", "%.1f%%" % (100 * np.mean(errs_v)), np.mean(errs_v) < 0.12)
chequeo("Semáforo verde cuando el modelo aplica", "%d de 4" % verdes, verdes >= 3)
chequeo("Compras predichas frente a reales por grupo de frecuencia (rango de la razón)", "%.2f a %.2f" % (min(ratios), max(ratios)), 0.75 <= min(ratios) and max(ratios) <= 1.25)
chequeo("Tasa media de compra recuperada (real 0,05 por semana)", "%.1f%%" % (100 * np.mean(rate_err)), np.mean(rate_err) < 0.10, "(error relativo)")
chequeo("Probabilidad media de abandono recuperada (real 33%)", "%.1f%%" % (100 * np.mean(drop_err)), np.mean(drop_err) < 0.15, "(error relativo)")
chequeo("Monto medio por compra recuperado (real 30)", "%.1f%%" % (100 * np.mean(mu_err)), np.mean(mu_err) < 0.08, "(error relativo)")
chequeo("Proyección a 12 meses frente al futuro simulado (compras totales)", "%.1f%%" % (100 * np.mean(fut_err)), np.mean(fut_err) < 0.10)

# 2. Casos donde el modelo no debe dar verde
d = simular(6000, 50)
obs = hasta(d, 130).copy()
fin = ORIGEN + pd.Timedelta(weeks=130)
corte_val = fin - pd.DateOffset(months=6)
surge = obs[obs["fecha"] > corte_val].copy()
surge["fecha"] = surge["fecha"] + pd.Timedelta(days=1)
obs2 = pd.concat([obs, surge, surge.assign(fecha=surge["fecha"] + pd.Timedelta(days=1))], ignore_index=True)
res, _ = clv.clv_cmd(obs2, "cliente", "fecha", "monto", corte=fin, meses_val=6)
chequeo("Salto de demanda en el último semestre (triple de compras): no es verde", res["semaforo"], res["semaforo"] != "verde", "error compras %.0f%%" % (100 * abs(res["prueba_con_datos_nuevos"]["error_compras_totales"])))

dreg = simular(4000, 51, regular=True, semanas_total=130)
res, _ = clv.clv_cmd(dreg, "cliente", "fecha", "monto", corte=fin, meses_val=6)
chequeo("Compras a intervalos fijos (suscripción): se advierte y no es verde", res["semaforo"], res["semaforo"] != "verde" and any("regulares" in x for x in res["alertas"]))

dp = hasta(simular(250, 52), 130)
res, _ = clv.clv_cmd(dp, "cliente", "fecha", "monto", corte=fin, meses_val=6)
chequeo("Pocos clientes (250): no es verde", res["semaforo"], res["semaforo"] != "verde")

dl = hasta(simular(5000, 53, monto_ligado=True), 130)
res, _ = clv.clv_cmd(dl, "cliente", "fecha", "monto", corte=fin, meses_val=6)
chequeo("El monto sube con la frecuencia (supuesto roto): se advierte", res["semaforo"], res["semaforo"] != "verde" and any("correlación" in x for x in res["alertas"]))

dc = hasta(simular(5000, 54), 65)
res, _ = clv.clv_cmd(dc, "cliente", "fecha", "monto", corte=ORIGEN + pd.Timedelta(weeks=65), meses_val=6, horizonte=12)
chequeo("Solo 15 meses de historia: no es verde", res["semaforo"], res["semaforo"] != "verde")

# 3. Línea de comandos con las transacciones de práctica
carpeta = tempfile.mkdtemp(prefix="chk_clv_")
ruta = os.path.join(carpeta, "tx.csv")
d = hasta(simular(3000, 60), 130)
d[["cliente", "fecha", "monto"]].to_csv(ruta, index=False)
o = subprocess.run([sys.executable, os.path.join(SCR, "clv.py"), ruta, "--cliente", "cliente", "--fecha", "fecha", "--monto", "monto", "--margen", "0.4", "--outdir", carpeta], capture_output=True, text=True)
ok = o.returncode == 0 and os.path.exists(os.path.join(carpeta, "clv_clientes.csv"))
j = json.loads(o.stdout) if ok else {}
chequeo("Línea de comandos: clientes con valor esperado y semáforo", j.get("semaforo", o.stderr[-100:]), ok and j.get("clientes") == len(d["cliente"].unique()))

print()
if fallas:
    print("FALLAN %d chequeo(s):" % len(fallas))
    for f in fallas:
        print(" -", f)
    sys.exit(1)
print("OK: valor de vida del cliente validado contra verdad conocida")
