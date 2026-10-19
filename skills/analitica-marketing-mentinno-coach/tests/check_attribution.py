#!/usr/bin/env python3
"""Prueba de atribución multitoque contra verdad conocida.

Casos de cálculo a mano (reglas y Markov), exposición aleatoria con crédito verdadero por Shapley exacto,
retargeting (canal que solo aparece al final), ausencia de falsas alarmas, errores de uso y línea de comandos.

Uso: python3 tests/check_attribution.py
"""
import json
import math
import os
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
SCR = os.path.join(AQUI, "..", "scripts")
sys.path.insert(0, SCR)
import attribution as at  # noqa: E402

fallas = []


def chequeo(nombre, valor, ok, detalle=""):
    print("%-80s %-14s %s %s" % (nombre, valor, "OK" if ok else "FALLA", detalle))
    if not ok:
        fallas.append(nombre)


# ------------------------------------------------------------------ 1. reglas a mano
w = at.pesos_regla([0, 1, 2], [0.0, 7.0, 14.0], 3, 7.0)
chequeo("Último clic: todo al último canal", str(w["ultimo_clic"]), list(w["ultimo_clic"]) == [0, 0, 1])
chequeo("Primer clic: todo al primero", str(w["primer_clic"]), list(w["primer_clic"]) == [1, 0, 0])
chequeo("Lineal: un tercio a cada uno", "%.3f" % w["lineal"][0], np.allclose(w["lineal"], 1 / 3))
# vida media 7 días: pesos 0.25, 0.5, 1 -> normalizados 1/7, 2/7, 4/7
chequeo("Decaimiento con vida media de 7 días (1/7, 2/7, 4/7)", str(np.round(w["decaimiento"], 3)), np.allclose(w["decaimiento"], [1 / 7, 2 / 7, 4 / 7]))
chequeo("Por posición: 40% primero, 40% último, 20% medio", str(w["posicion"]), np.allclose(w["posicion"], [0.4, 0.2, 0.4]))
w = at.pesos_regla([1, 1, 0], [0, 1, 2], 2, 7.0)
chequeo("Canal repetido en la ruta suma sus pesos y todos suman 1", "%.3f" % w["lineal"].sum(), np.allclose(w["lineal"], [1 / 3, 2 / 3]) and all(abs(v.sum() - 1) < 1e-9 for v in w.values()))
w = at.pesos_regla([2], [0.0], 3, 7.0)
chequeo("Ruta de un solo contacto: todas las reglas dan 100% a ese canal", "", all(v[2] == 1 for v in w.values()))
w = at.pesos_regla([0, 1], [0.0, 1.0], 2, 7.0)
chequeo("Ruta de dos contactos por posición: 50 y 50", "", np.allclose(w["posicion"], [0.5, 0.5]))

# ------------------------------------------------------------------ 2. Markov a mano
# Dos canales. 100 personas A>B convierten 50, B solo convierte 10 de 100, A solo convierte 30 de 100.
m = 2
celdas = [((0, 1), 1), ((0, 1), 0), ((1,), 1), ((1,), 0), ((0,), 1), ((0,), 0)]
cuentas = np.array([50, 50, 10, 90, 30, 70], float)
C = at.construir_C(celdas, cuentas, m)
ef, base = at.markov_efectos(C, m)
# probabilidad base calculada por separado resolviendo la cadena a mano
ini = C[m] / C[m].sum()
P = np.divide(C, C.sum(1, keepdims=True), out=np.zeros_like(C), where=C.sum(1, keepdims=True) > 0)
p_b_conv = P[1, m + 1]
p_a_conv_dir = P[0, m + 1]
p_a_to_b = P[0, 1]
conv_b = p_b_conv
conv_a = p_a_conv_dir + p_a_to_b * conv_b
base_man = ini[0] * conv_a + ini[1] * conv_b
chequeo("Markov: probabilidad de conversión de la cadena igual al cálculo a mano", "%.4f" % base, abs(base - base_man) < 1e-9)
# quitar A: quienes iniciaban en A se pierden
ef_a_man = 1 - (ini[1] * conv_b) / base_man
chequeo("Markov: efecto de quitar A igual al cálculo a mano", "%.4f" % ef[0], abs(ef[0] - ef_a_man) < 1e-9)
chequeo("Markov: efectos entre 0 y 1", str(np.round(ef, 3)), ((ef >= 0) & (ef <= 1)).all())


# ------------------------------------------------------------------ 3. simuladores
def a_filas(rutas, conv, rg, valores=None):
    filas = []
    base = pd.Timestamp("2025-01-01")
    for u, (ruta, y) in enumerate(zip(rutas, conv)):
        t = np.sort(rg.uniform(0, 40, len(ruta)))
        for c, ti in zip(ruta, t):
            filas.append((u, base + pd.Timedelta(days=float(ti)), c, int(y)))
    return pd.DataFrame(filas, columns=["usuario", "fecha", "canal", "compro"])


CAN = ["A", "B", "C", "D"]
PEXP = np.array([0.30, 0.20, 0.15, 0.10])
BETA = np.array([1.0, 0.5, 0.0, 1.5])
B0 = -3.5


def sim_exposicion(n, seed):
    """Exposición independiente a 4 canales, conversión logística con efectos conocidos. Solo se observan personas con al menos un contacto."""
    rg = np.random.default_rng(seed)
    X = (rg.random((n, 4)) < PEXP).astype(int)
    X = X[X.sum(1) > 0]
    p = 1 / (1 + np.exp(-(B0 + X @ BETA)))
    y = (rg.random(len(X)) < p).astype(int)
    rutas = []
    for fila in X:
        idx = [CAN[i] for i in range(4) if fila[i]]
        rutas.append(list(rg.permutation(idx)))
    return a_filas(rutas, y, rg), X, y


def credito_verdadero(X, y):
    """Crédito verdadero por Shapley exacto con los parámetros reales, sobre las conversiones esperadas por patrón.
    Las conversiones de patrones sin efecto de canal (p. ej. solo el canal C, sin efecto) no se reparten: quedan como sin canal.
    Devuelve (proporción por canal sobre todas las conversiones esperadas, proporción sin canal)."""
    f = lambda mask: 1 / (1 + math.exp(-(B0 + float(np.dot(BETA, mask)))))
    pats, cnt = np.unique(X, axis=0, return_counts=True)
    cred, sin = np.zeros(4), 0.0
    for p, c in zip(pats, cnt):
        phi = np.maximum(at._shapley_patron(tuple(p), f), 0)
        esp = c * f(tuple(p))
        if phi.sum() <= 0:
            sin += esp
        else:
            cred += esp * phi / phi.sum()
    tot = cred.sum() + sin
    return cred / tot, sin / tot


# ------------------------------------------------------------------ 4. exposición aleatoria
errs, cubre, tot, spread = [], 0, 0, []
for s in range(6):
    d, X, y = sim_exposicion(60000, 100 + s)
    res = at.atribuir(d, "usuario", "fecha", "canal", "compro", boot=60, seed=s)
    verdad, _ = credito_verdadero(X, y)
    est = np.array([f["exposicion"]["pct"] for f in res["por_canal"]])
    errs.append(np.abs(est - verdad).max())
    for i, f in enumerate(res["por_canal"]):
        lo, hi = f["exposicion"]["rango_pct_90"]
        cubre += lo - 0.01 <= verdad[i] <= hi + 0.01
        tot += 1
    spread.append(res["por_canal"][3]["exposicion"]["pct"] - res["por_canal"][2]["exposicion"]["pct"])
chequeo("Exposición: diferencia máxima con el crédito verdadero (Shapley exacto)", "%.3f" % np.mean(errs), np.mean(errs) < 0.04 and max(errs) < 0.06, "(un canal sin efecto puede recibir hasta unos 5 puntos por ruido)")
chequeo("Exposición: el rango 90% contiene la verdad (con holgura de 1 punto)", "%.0f%%" % (100 * cubre / tot), cubre / tot >= 0.80)
chequeo("Exposición: el canal sin efecto real (C) recibe menos crédito que el de mayor efecto (D)", "%.3f" % np.mean(spread), np.mean(spread) > 0.05)

d, X, y = sim_exposicion(60000, 7)
res = at.atribuir(d, "usuario", "fecha", "canal", "compro", boot=40)
pct_c = res["por_canal"][2]["exposicion"]["pct"]
verdad, _ = credito_verdadero(X, y)
chequeo("Canal sin efecto real: su crédito de exposición es bajo y cercano al verdadero", "%.3f vs %.3f" % (pct_c, verdad[2]), abs(pct_c - verdad[2]) < 0.04)
sumas = {k: sum(f[k]["pct"] for f in res["por_canal"]) for k in at.METODOS}
reglas_ok = all(abs(sumas[k] - 1) < 1e-6 for k in sumas if k != "exposicion")
chequeo("Reglas y Markov reparten 100%; exposición deja fuera solo lo que no tiene efecto de canal", "%.3f" % sumas["exposicion"], reglas_ok and 0.85 <= sumas["exposicion"] <= 1 + 1e-9)
chequeo("Sin personas sin contacto: se advierte que no se puede estimar la base", "", any("sin ningún contacto" in a or "Casi no hay personas" in a for a in res["alertas"]))
chequeo("Semáforo nunca es verde (atribución no es causal)", res["semaforo"], res["semaforo"] != "verde")
chequeo("Con exposición aleatoria ningún canal se marca como de cierre", str([f["canal_de_cierre"] for f in res["por_canal"]]), not any(f["canal_de_cierre"] for f in res["por_canal"]))

# ------------------------------------------------------------------ 5. retargeting: canal R aparece al final y cobra lo que iba a ocurrir
def sim_retarget(n, seed):
    """Canal R (retargeting) solo se muestra a quienes ya tocaron otro canal y tienen alta intención. R no tiene efecto causal."""
    rg = np.random.default_rng(seed)
    rutas, conv = [], []
    for _ in range(n):
        base_chan = [c for c, p in zip(["A", "B"], [0.4, 0.3]) if rg.random() < p]
        if not base_chan:
            base_chan = ["A"] if rg.random() < 0.5 else ["B"]
        intencion = rg.random() < 0.15
        pc = 0.55 if intencion else 0.02
        y = int(rg.random() < pc)
        ruta = list(rg.permutation(base_chan))
        if intencion and rg.random() < 0.9:
            ruta.append("R")
        rutas.append(ruta)
        conv.append(y)
    return a_filas(rutas, conv, rg)


d = sim_retarget(40000, 1)
d = d.sort_values(["usuario", "fecha"])
# R siempre al final por construcción de fechas
res = at.atribuir(d, "usuario", "fecha", "canal", "compro", boot=40)
filR = [f for f in res["por_canal"] if f["canal"] == "R"][0]
chequeo("Retargeting: R se marca como canal de cierre", "%.0f%% al final" % (100 * (filR["veces_ultimo_en_rutas_de_2_o_mas_pct"] or 0)), filR["canal_de_cierre"])
chequeo("Retargeting: se avisa que conviene confirmar con prueba de incrementalidad", "", any("incrementalidad" in s for s in res["senales"]))
chequeo("Retargeting: el semáforo no es verde", res["semaforo"], res["semaforo"] != "verde")

# ------------------------------------------------------------------ 6. errores de uso
d = sim_exposicion(60000, 3)[0]
poca = d[d["usuario"] < 400].copy()
poca["compro"] = 0
try:
    at.atribuir(poca, "usuario", "fecha", "canal", "compro")
    ok = False
except SystemExit as e:
    ok = "100" in str(e) or "conversiones" in str(e)
chequeo("Menos de 100 conversiones: se rechaza con mensaje claro", "", ok)
todos = d.copy()
todos["compro"] = 1
try:
    at.atribuir(todos, "usuario", "fecha", "canal", "compro")
    ok = False
except SystemExit as e:
    ok = "Todas" in str(e)
chequeo("Todos convirtieron: se rechaza con mensaje claro", "", ok)
txt = d.copy()
txt["compro"] = np.where(txt["compro"] == 1, "Sí", "No")
r1 = at.atribuir(d, "usuario", "fecha", "canal", "compro", boot=0)
r2 = at.atribuir(txt, "usuario", "fecha", "canal", "compro", boot=0)
chequeo("Conversión como texto Sí/No equivale a 1/0", "", abs(r1["conversiones"] - r2["conversiones"]) == 0)

muchos = d.copy()
rg = np.random.default_rng(5)
extra = rg.choice(["e%d" % i for i in range(12)], len(muchos))
muchos["canal"] = np.where(rg.random(len(muchos)) < 0.5, extra, muchos["canal"])
r = at.atribuir(muchos, "usuario", "fecha", "canal", "compro", boot=0)
chequeo("Más de 8 canales: los pequeños se agrupan en 'otros' con aviso", str(len(r["por_canal"])), len(r["por_canal"]) <= 8 and any("otros" in a for a in r["alertas"]))

# ------------------------------------------------------------------ 7. con valor y línea de comandos
carpeta = tempfile.mkdtemp(prefix="chk_att_")
ruta = os.path.join(carpeta, "toques.csv")
d["monto"] = np.where(d["compro"] == 1, 100.0, 0.0)
d.to_csv(ruta, index=False)
o = subprocess.run([sys.executable, os.path.join(SCR, "attribution.py"), ruta, "--usuario", "usuario", "--fecha", "fecha", "--canal", "canal", "--convirtio", "compro",
                    "--valor", "monto", "--boot", "30", "--outdir", carpeta], capture_output=True, text=True)
ok = o.returncode == 0 and os.path.exists(os.path.join(carpeta, "atribucion_por_canal.csv"))
j = json.loads(o.stdout) if ok else {}
rs = j
chequeo("Línea de comandos: tabla por canal y resumen", "ok" if ok else o.stderr[-120:], ok and len(rs.get("por_canal", [])) == 4)
if ok:
    tot_valor = sum(f["ultimo_clic"]["valor"] for f in rs["por_canal"])
    chequeo("Valor atribuido por último clic suma el valor total de las conversiones", "%.0f" % tot_valor, abs(tot_valor - 100.0 * rs["conversiones"]) < 1e-6)

print()
if fallas:
    print("FALLAN %d chequeo(s):" % len(fallas))
    for f in fallas:
        print(" -", f)
    sys.exit(1)
print("OK: atribución validada contra verdad conocida")
