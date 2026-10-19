#!/usr/bin/env python3
"""Prueba del semáforo de classify.py con casos de verdad conocida.

Casos: señal fuerte, señal moderada, señal débil, ruido puro, fuga de información,
y decisión con dinero (valor y costo). Falla si el semáforo no es el esperado.

Uso: python3 tests/check_classify.py
"""
import json
import os
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(AQUI, "..", "scripts", "classify.py")


def base(n, fuerza, seed):
    rng = np.random.default_rng(seed)
    d = pd.DataFrame({"fecha": pd.date_range("2024-01-01", periods=n, freq="D").strftime("%Y-%m-%d"),
                      "x1": rng.normal(size=n), "x2": rng.normal(size=n), "x3": rng.normal(size=n)})
    logit = -2.0 + fuerza * (d.x1 + 0.6 * d.x2)
    d["baja"] = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    return d


def correr(nombre, d, extra=None, x="x1,x2,x3"):
    carpeta = tempfile.mkdtemp(prefix="chk_cls_")
    ruta = os.path.join(carpeta, nombre + ".csv")
    d.to_csv(ruta, index=False)
    cmd = [sys.executable, SCRIPT, ruta, "--y", "baja", "--x", x, "--fecha", "fecha", "--outdir", carpeta] + (extra or [])
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return json.load(open(os.path.join(carpeta, "clasificacion.json")))["resumen"]


CASOS = []


def caso(nombre, d, esperado, extra=None, x="x1,x2,x3"):
    CASOS.append((nombre, d, esperado, extra, x))


caso("señal fuerte (AUC alto, sin dinero)", base(8000, 1.6, 1), {"verde"})
caso("señal moderada (AUC cercano a 0,75, sin dinero)", base(6000, 0.9, 2), {"verde", "amarillo"})
caso("señal moderada con dinero en juego", base(6000, 0.9, 2), {"amarillo"}, ["--valor", "500", "--costo", "20"])
caso("señal débil", base(4000, 0.25, 3), {"amarillo", "rojo"})
caso("ruido puro", base(4000, 0.0, 4), {"rojo"})
caso("pocos datos con señal moderada", base(600, 0.9, 5), {"amarillo", "rojo"})
f = base(4000, 0.9, 6)
f["cancelo"] = f.baja
caso("fuga de información", f, {"rojo"}, x="x1,x2,x3,cancelo")


def main():
    fallas = 0
    for nombre, d, esperado, extra, x in CASOS:
        r = correr(nombre.split(" (")[0].replace(" ", "_"), d, extra, x)
        ok = r["semaforo"] in esperado
        fallas += 0 if ok else 1
        print("%-52s AUC %.3f | semáforo %-8s | esperado %-16s | %s" % (nombre, max(r["auc"].values()), r["semaforo"], "/".join(sorted(esperado)), "OK" if ok else "FALLA"))
        if "motivo_semaforo" in r:
            print("   motivo:", r["motivo_semaforo"])
    if fallas:
        print("\n%d caso(s) fallan" % fallas)
        sys.exit(1)
    print("\nOK: todos los casos dan el semáforo esperado")


if __name__ == "__main__":
    main()
