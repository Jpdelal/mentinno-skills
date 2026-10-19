#!/usr/bin/env python3
"""Genera bases de práctica con verdad conocida. Sirven para probar los scripts y para el modo coach.

Uso: python3 demo_data.py [carpeta_salida]
Crea: transacciones.csv, embudo.csv, ventas_semanales.csv, bajas_clientes.csv, mmm_semanal.csv,
      ab_prueba.csv, uplift_campana.csv, tiendas_panel.csv, toques_atribucion.csv y verdad.json
"""
import json
import os
import sys

import numpy as np
import pandas as pd

if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
    print("Uso: python3 demo_data.py [carpeta_de_salida]  (por defecto datos_demo). Genera bases de práctica con verdad conocida en verdad.json")
    sys.exit(0)
out = sys.argv[1] if len(sys.argv) > 1 else "datos_demo"
os.makedirs(out, exist_ok=True)
rng = np.random.default_rng(2026)
verdad = {}

# 1. Transacciones (RFM)
fin = pd.Timestamp("2026-09-30")
ini = fin - pd.Timedelta(days=730)
rows = []
tipos = [("campeon", 0.08, 14, 120), ("leal", 0.20, 5, 70), ("ocasional", 0.40, 1.5, 45), ("perdido", 0.32, 2.5, 50)]
cid = 0
for tipo, share, nped, ticket in tipos:
    for _ in range(int(4000 * share)):
        cid += 1
        np_ = max(1, rng.poisson(nped))
        if tipo == "perdido":
            t0 = ini + pd.Timedelta(days=int(rng.integers(0, 300)))
            span = int(rng.integers(30, 250))
        else:
            t0 = ini + pd.Timedelta(days=int(rng.integers(0, 500 if tipo == "ocasional" else 120)))
            span = (fin - t0).days
        fechas = sorted(t0 + pd.Timedelta(days=int(d)) for d in rng.integers(0, max(span, 1), np_))
        for f in fechas:
            if f <= fin:
                rows.append((f"C{cid:05d}", f.strftime("%Y-%m-%d"), round(float(rng.lognormal(np.log(ticket), 0.45)), 2), tipo))
tx = pd.DataFrame(rows, columns=["id_cliente", "fecha", "monto", "tipo_real"])
tx.insert(1, "pedido", ["P%06d" % i for i in range(len(tx))])
tx.drop(columns="tipo_real").to_csv(f"{out}/transacciones.csv", index=False)
verdad["transacciones"] = {"clientes": cid, "perdidos_reales": int(4000 * 0.32)}

# 2. Embudo con paradoja de Simpson: la tasa global sube, pero baja dentro de cada dispositivo
filas = []
mix = {"T1": {"movil": 0.80, "escritorio": 0.20}, "T2": {"movil": 0.50, "escritorio": 0.50}}
conv = {"T1": {"movil": (0.40, 0.30, 0.50), "escritorio": (0.55, 0.45, 0.65)},
        "T2": {"movil": (0.37, 0.28, 0.46), "escritorio": (0.52, 0.42, 0.61)}}
for per in ("T1", "T2"):
    for dev in ("movil", "escritorio"):
        v = int(50000 * mix[per][dev])
        c1, c2, c3 = conv[per][dev]
        car = int(v * c1 * 0.5)
        chk = int(car * c2 * 1.4)
        com = int(chk * c3 * 0.9)
        filas.append((per, dev, v, car, chk, com))
pd.DataFrame(filas, columns=["periodo", "dispositivo", "visitas", "carrito", "checkout", "compra"]).to_csv(f"{out}/embudo.csv", index=False)

# 3. Ventas semanales (regresión) con confusión y una variable espuria
T = 104
t = np.arange(T)
est = 1 + 0.25 * np.sin(2 * np.pi * t / 52)
inversion = 8000 * est * rng.lognormal(0, 0.15, T)
descuento = 5 + 0.0006 * inversion + rng.normal(0, 2, T)
precio_comp = 100 + rng.normal(0, 6, T)
newsletters = 20 + 10 * np.sin(2 * np.pi * t / 52) + rng.normal(0, 1.5, T)
ventas = 40000 + 2.2 * inversion + 900 * descuento - 250 * precio_comp + 120 * t + 9000 * np.sin(2 * np.pi * t / 52) + rng.normal(0, 5000, T)
fechas = pd.date_range("2024-10-07", periods=T, freq="W-MON")
pd.DataFrame({"semana": fechas.strftime("%Y-%m-%d"), "ventas": ventas.round(0), "inversion_digital": inversion.round(0),
              "descuento_pct": descuento.round(1), "precio_competencia": precio_comp.round(1),
              "newsletters_enviados": newsletters.round(1)}).to_csv(f"{out}/ventas_semanales.csv", index=False)
verdad["regresion"] = {"efecto_inversion": 2.2, "efecto_descuento_pct": 900, "efecto_precio_competencia": -250,
                       "newsletters": "sin efecto real; solo comparte estacionalidad"}

# 4. Bajas de clientes (clasificación)
N = 6000
antig = rng.integers(1, 60, N)
tickets = rng.poisson(1.5, N)
uso = rng.gamma(3, 10, N)
plan = rng.choice(["basico", "pro"], N, p=[0.65, 0.35])
desc = rng.choice([0, 1], N, p=[0.8, 0.2])
z = -1.2 - 0.04 * antig + 0.45 * tickets - 0.03 * uso + 0.6 * (plan == "basico") - 0.5 * desc
baja = rng.binomial(1, 1 / (1 + np.exp(-z)))
meses = pd.date_range("2025-01-01", periods=N, freq="h").strftime("%Y-%m-%d")
b = pd.DataFrame({"fecha_alta": meses, "antiguedad_meses": antig, "tickets_soporte": tickets, "uso_mensual": uso.round(1),
                  "plan": plan, "recibio_descuento": desc, "baja": baja})
b.to_csv(f"{out}/bajas_clientes.csv", index=False)
b.assign(cancelo_servicio_flag=np.where(baja == 1, rng.binomial(1, 0.97, N), rng.binomial(1, 0.02, N))).to_csv(f"{out}/bajas_clientes_con_fuga.csv", index=False)
verdad["bajas"] = {"tasa_base": float(baja.mean())}

# 5. MMM semanal con verdad conocida
T = 156
t = np.arange(T)
def flights(base, p_on, amp):
    on = rng.random(T) < p_on
    x = np.where(on, base * rng.lognormal(0, 0.35, T) * amp, base * 0.15)
    return x
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
    k = kmult * a.mean()
    contrib[c] = beta * (1 - np.exp(-a / k))
    y = y + contrib[c]
y = y + rng.normal(0, 6000, T)
df = pd.DataFrame({"semana": pd.date_range("2023-10-02", periods=T, freq="W-MON").strftime("%Y-%m-%d"), "ventas": y.round(0)})
for c in gasto:
    df["gasto_" + c] = gasto[c].round(0)
df["promocion"] = promo
df.to_csv(f"{out}/mmm_semanal.csv", index=False)
verdad["mmm"] = {"roi_real": {c: round(float(contrib[c].sum() / gasto[c].sum()), 3) for c in gasto},
                 "contribucion_real_pct": {c: round(float(100 * contrib[c].sum() / y.sum()), 1) for c in gasto},
                 "decay_real": {c: v[0] for c, v in verd.items()}}

# 6. Prueba A/B (módulo 11): 40.000 personas, reparto 50/50, el tratamiento sube la compra de 5,0% a 6,0%
n_ab = 40000
grupo = np.where(rng.random(n_ab) < 0.5, "tratamiento", "control")
p_ab = np.where(grupo == "tratamiento", 0.060, 0.050)
compro_ab = (rng.random(n_ab) < p_ab).astype(int)
monto_ab = np.where(compro_ab == 1, rng.gamma(4, 15, n_ab), 0).round(2)
pd.DataFrame({"persona": np.arange(n_ab), "grupo": grupo, "compro": compro_ab, "monto": monto_ab}).to_csv(f"{out}/ab_prueba.csv", index=False)
verdad["ab_prueba"] = {"tasa_control": 0.05, "tasa_tratamiento": 0.06, "efecto_real_puntos": 0.01}

# 7. Uplift (módulo 12): el descuento solo mueve a quienes tienen alta sensibilidad al precio y baja compra de base
n_up = 20000
X = pd.DataFrame({"sensibilidad_precio": rng.normal(size=n_up), "compras_previas": rng.normal(size=n_up), "antiguedad": rng.normal(size=n_up), "visitas": rng.normal(size=n_up)})
pc = 1 / (1 + np.exp(-(-1.2 + 1.3 * X["compras_previas"] + 0.3 * X["antiguedad"])))
tau = 0.20 / (1 + np.exp(-3 * X["sensibilidad_precio"])) * (1 - pc) - 0.01
trat = rng.random(n_up) < 0.5
y_up = (rng.random(n_up) < np.clip(np.where(trat, pc + tau, pc), 0.001, 0.999)).astype(int)
up = X.round(3)
up["grupo"] = np.where(trat, "descuento", "control")
up["compro"] = y_up
up.to_csv(f"{out}/uplift_campana.csv", index=False)
verdad["uplift"] = {"efecto_promedio_real": round(float(tau.mean()), 4), "regla": "el efecto crece con sensibilidad_precio; quienes más compran de base responden menos"}

# 8. Diferencias en diferencias (módulo 12): 12 tiendas con rediseño y 12 sin cambio, 30 semanas, efecto real +5 desde la semana 20
t_n, c_n, sem = 12, 12, 30
a = rng.normal(100, 15, t_n + c_n)
tt = np.arange(sem)
comun = 0.5 * tt + 10 * np.sin(2 * np.pi * tt / 12)
tr = np.r_[np.ones(t_n), np.zeros(c_n)]
v = a[:, None] + comun[None, :] + 5.0 * (tt[None, :] >= 20) * tr[:, None] + rng.normal(0, 4, (t_n + c_n, sem))
pd.DataFrame({"tienda": np.repeat(np.arange(t_n + c_n), sem), "semana": np.tile(tt, t_n + c_n),
              "grupo": np.repeat(np.where(tr == 1, "rediseno", "sin_cambio"), sem), "ventas": v.ravel().round(2)}).to_csv(f"{out}/tiendas_panel.csv", index=False)
verdad["did"] = {"efecto_real_por_tienda_y_semana": 5.0, "semana_intervencion": 20}

# 9. Atribución (módulo 14): 4 canales, exposición independiente, conversión logística; solo personas con al menos un contacto
canales_at = ["busqueda", "redes", "email", "display"]
pe = np.array([0.30, 0.20, 0.15, 0.10])
be = np.array([1.0, 0.5, 0.0, 1.5])
n_at = 40000
M = (rng.random((n_at, 4)) < pe).astype(int)
M = M[M.sum(1) > 0]
yc = (rng.random(len(M)) < 1 / (1 + np.exp(-(-3.5 + M @ be)))).astype(int)
base_f = pd.Timestamp("2026-08-01")
filas_at = []
for u, (fila, yy) in enumerate(zip(M, yc)):
    usados = [canales_at[i] for i in range(4) if fila[i]]
    ts = np.sort(rng.uniform(0, 40, len(usados)))
    for c_, t_ in zip(rng.permutation(usados), ts):
        filas_at.append((u, (base_f + pd.Timedelta(days=float(t_))).strftime("%Y-%m-%d"), c_, int(yy)))
pd.DataFrame(filas_at, columns=["persona", "fecha", "canal", "compro"]).to_csv(f"{out}/toques_atribucion.csv", index=False)
verdad["atribucion"] = {"efecto_real_en_logit": dict(zip(canales_at, be.tolist())), "nota": "email no tiene efecto real; display tiene el mayor"}

json.dump(verdad, open(f"{out}/verdad.json", "w"), indent=1, ensure_ascii=False)
print("Bases creadas en", out)
