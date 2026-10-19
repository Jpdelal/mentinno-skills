#!/usr/bin/env python3
"""Prueba del módulo de pruebas A/B contra verdad conocida (simulaciones).

Verifica: tamaño de muestra y potencia real, cobertura del rango, falsos positivos en pruebas A/A,
detección de desbalance de grupos, efecto de mirar varias veces, retorno incremental y uso por línea de comandos.

Uso: python3 tests/check_ab.py
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
import ab_test as ab  # noqa: E402

rng = np.random.default_rng(2026)
fallas = []


def chequeo(nombre, valor, ok, detalle=""):
    print("%-62s %-12s %s %s" % (nombre, valor, "OK" if ok else "FALLA", detalle))
    if not ok:
        fallas.append(nombre)


# 1. Tamaño de muestra: contra un cálculo independiente y contra simulación
p1, mejora = 0.04, 0.15
p2 = p1 * (1 + mejora)
n = ab.n_proporciones(p1, p2)
from statsmodels.stats.power import NormalIndPower  # noqa: E402
from statsmodels.stats.proportion import proportion_effectsize  # noqa: E402
n_ref = NormalIndPower().solve_power(proportion_effectsize(p2, p1), power=0.8, alpha=0.05)
chequeo("Tamaño de muestra frente a statsmodels", "%d vs %d" % (n, n_ref), abs(n - n_ref) / n_ref < 0.05, "(tolerancia 5%)")

S = 4000
k_c, k_t = rng.binomial(n, p1, S), rng.binomial(n, p2, S)
sig = np.array([ab.comparar_proporciones(int(a), n, int(b), n)["p"] < 0.05 for a, b in zip(k_c, k_t)])
pot = sig.mean()
chequeo("Potencia real con el tamaño calculado (meta 80%)", "%.1f%%" % (100 * pot), 0.76 <= pot <= 0.84)

# 2. Falsos positivos en pruebas A/A y cobertura del rango
n2 = 5000
k_c, k_t = rng.binomial(n2, 0.05, S), rng.binomial(n2, 0.05, S)
rs = [ab.comparar_proporciones(int(a), n2, int(b), n2) for a, b in zip(k_c, k_t)]
fp = np.mean([r["p"] < 0.05 for r in rs])
chequeo("Falsos positivos en pruebas sin efecto (meta 5%)", "%.1f%%" % (100 * fp), 0.035 <= fp <= 0.065)
cub0 = np.mean([r["rango_abs"][0] <= 0 <= r["rango_abs"][1] for r in rs])
chequeo("Cobertura del rango 95% sin efecto", "%.1f%%" % (100 * cub0), 0.93 <= cub0 <= 0.97)
k_c, k_t = rng.binomial(n2, 0.05, S), rng.binomial(n2, 0.06, S)
rs = [ab.comparar_proporciones(int(a), n2, int(b), n2) for a, b in zip(k_c, k_t)]
cub1 = np.mean([r["rango_abs"][0] <= 0.01 <= r["rango_abs"][1] for r in rs])
chequeo("Cobertura del rango 95% con efecto real de 1 punto", "%.1f%%" % (100 * cub1), 0.93 <= cub1 <= 0.97)

# 3. Valores continuos y asimétricos (montos de compra)
cubre, T = 0, 120
for _ in range(T):
    xc = rng.lognormal(3.5, 1.2, 1500)
    xt = rng.lognormal(3.5, 1.2, 1500) * 1.10
    verdad = (np.exp(3.5 + 1.2 ** 2 / 2)) * 0.10
    r = ab.comparar_medias(xc, xt, boot=300, seed=int(rng.integers(1e9)))
    cubre += r["rango_abs"][0] <= verdad <= r["rango_abs"][1]
chequeo("Cobertura del rango en montos muy asimétricos", "%.1f%%" % (100 * cubre / T), 0.88 <= cubre / T <= 0.99, "(%d pruebas)" % T)

# 4. Desbalance de grupos
falsa = np.mean([ab.srm(int(c), 10000 - int(c)) < 0.001 for c in rng.binomial(10000, 0.5, 4000)])
chequeo("Falsas alarmas de desbalance con reparto correcto (meta ~0,1%)", "%.2f%%" % (100 * falsa), falsa < 0.005)
det = np.mean([ab.srm(int(c), 40000 - int(c)) < 0.001 for c in rng.binomial(40000, 0.48, 1000)])
chequeo("Detección de un reparto 52/48 con 40.000 personas", "%.0f%%" % (100 * det), det > 0.95)
det_pocas = np.mean([ab.srm(int(c), 10000 - int(c)) < 0.001 for c in rng.binomial(10000, 0.48, 1000)])
chequeo("Con 10.000 personas un 52/48 se detecta solo en parte (límite conocido)", "%.0f%%" % (100 * det_pocas), 0.6 < det_pocas < 0.9)
chequeo("Reparto planeado 90/10 se respeta (sin falsa alarma)", "%.3f" % ab.srm(1000, 9000, 0.9), ab.srm(1000, 9000, 0.9) > 0.05)

# 5. Mirar varias veces: el ajuste por revisiones controla los falsos positivos
look = 5
naive = ajust = 0
SIM = 1500
for _ in range(SIM):
    n_max = 10000
    xc, xt = rng.binomial(1, 0.05, n_max), rng.binomial(1, 0.05, n_max)
    pa = pb = False
    for f in range(1, look + 1):
        m = n_max * f // look
        r = ab.comparar_proporciones(int(xc[:m].sum()), m, int(xt[:m].sum()), m)
        pa |= r["p"] < 0.05
        pb |= r["p"] < 0.05 / look
    naive += pa
    ajust += pb
chequeo("Falsos positivos al mirar 5 veces sin ajustar", "%.1f%%" % (100 * naive / SIM), naive / SIM > 0.10, "(debe ser alto: es el problema)")
chequeo("Falsos positivos al mirar 5 veces con ajuste", "%.1f%%" % (100 * ajust / SIM), ajust / SIM < 0.06)

# 6. Retorno incremental: verdad conocida
n_t = n_c = 20000
valor, gasto, tasa_c, tasa_t = 90.0, 30000.0, 0.040, 0.046
roas_real = (tasa_t - tasa_c) * n_t * valor / gasto
cub, T = 0, 300
for _ in range(T):
    kc, kt = rng.binomial(n_c, tasa_c), rng.binomial(n_t, tasa_t)
    df = pd.DataFrame({"g": ["control"] * n_c + ["tratamiento"] * n_t, "y": np.r_[np.ones(kc), np.zeros(n_c - kc), np.ones(kt), np.zeros(n_t - kt)]})
    r = ab.leer(df, "g", "y", valor=valor, gasto=gasto)
    lo, hi = r["retorno_incremental"]["rango_95"]
    cub += lo <= roas_real <= hi
chequeo("Cobertura del retorno incremental (real %.2f)" % roas_real, "%.1f%%" % (100 * cub / T), 0.90 <= cub / T <= 0.99, "(%d pruebas)" % T)
ejemplo = r["para_calibrar_mmm"]["ejemplo_comando"]
chequeo("Línea para calibrar la mezcla de medios", ejemplo, ejemplo.startswith("--calibrar canal=") and ":" in ejemplo)

# 7. Semáforo en casos extremos
df = pd.DataFrame({"g": ["control"] * 5000 + ["tratamiento"] * 5000, "y": np.r_[rng.binomial(1, 0.05, 5000), rng.binomial(1, 0.09, 5000)]})
r = ab.leer(df, "g", "y")
chequeo("Efecto grande y claro da verde", r["semaforo"], r["semaforo"] == "verde")
df = pd.DataFrame({"g": ["control"] * 800 + ["tratamiento"] * 800, "y": np.r_[rng.binomial(1, 0.05, 800), rng.binomial(1, 0.05, 800)]})
r = ab.leer(df, "g", "y")
chequeo("Sin efecto con poca muestra da amarillo y dice el mínimo detectable", r["semaforo"], r["semaforo"] == "amarillo" and "detectar" in r["motivo_semaforo"])
df = pd.DataFrame({"g": ["control"] * 3000 + ["tratamiento"] * 7000, "y": rng.binomial(1, 0.05, 10000)})
r = ab.leer(df, "g", "y")
chequeo("Reparto 30/70 cuando se planeó 50/50 da rojo", r["semaforo"], r["semaforo"] == "rojo")

# 8. Línea de comandos de punta a punta
carpeta = tempfile.mkdtemp(prefix="chk_ab_")
ruta = os.path.join(carpeta, "prueba.csv")
pd.DataFrame({"grupo": ["control"] * 4000 + ["campana"] * 4000, "compro": np.r_[rng.binomial(1, 0.05, 4000), rng.binomial(1, 0.08, 4000)]}).to_csv(ruta, index=False)
o = subprocess.run([sys.executable, os.path.join(SCR, "ab_test.py"), "leer", ruta, "--grupo", "grupo", "--resultado", "compro", "--valor", "80", "--gasto", "9000", "--outdir", carpeta], capture_output=True, text=True)
ok = o.returncode == 0 and json.loads(o.stdout)["semaforo"] == "verde"
chequeo("Línea de comandos: leer", "ok" if ok else o.stderr[-120:], ok)
o = subprocess.run([sys.executable, os.path.join(SCR, "ab_test.py"), "tamano", "--base", "0.04", "--mejora", "0.15", "--trafico", "2000", "--outdir", carpeta], capture_output=True, text=True)
j = json.loads(o.stdout) if o.returncode == 0 else {}
chequeo("Línea de comandos: tamano (días con tráfico 2.000 por día)", str(j.get("dias_necesarios")), o.returncode == 0 and j.get("dias_necesarios", 0) > 0)

print()
if fallas:
    print("FALLAN %d chequeo(s): %s" % (len(fallas), "; ".join(fallas)))
    sys.exit(1)
print("OK: módulo de pruebas A/B validado contra verdad conocida")
