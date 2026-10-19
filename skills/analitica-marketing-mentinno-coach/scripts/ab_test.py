#!/usr/bin/env python3
"""Pruebas A/B y de incrementalidad: cuánta gente necesitas y qué dice el resultado.

Dos usos:
  tamano  calcula cuántas personas por grupo (y cuántos días) hacen falta antes de lanzar la prueba.
  leer    lee el resultado de una prueba con grupo de control: efecto, rango, desbalance de grupos,
          retorno incremental (si das gasto y valor) y la línea lista para calibrar la mezcla de medios.

Uso:
  python3 ab_test.py tamano --base 0.04 --mejora 0.15 [--potencia 0.8] [--alfa 0.05] [--trafico 2000]
  python3 ab_test.py tamano --media 80 --desv 60 --mejora 0.05
  python3 ab_test.py leer archivo.csv --grupo grupo --resultado compro [--control control]
        [--reparto 0.5] [--valor 90 --gasto 12000] [--canal gasto_tv] [--revisiones 1]
"""
import argparse
import math
import os

import _deps  # noqa: F401  (revisa librerías)
import numpy as np
import pandas as pd
from scipy import stats

from _utils import emit, load_table, need_cols, wilson


# ---------------------------------------------------------------- tamaño de muestra
def n_proporciones(p1, p2, alfa=0.05, potencia=0.8):
    za, zb = stats.norm.ppf(1 - alfa / 2), stats.norm.ppf(potencia)
    pb = (p1 + p2) / 2
    num = (za * math.sqrt(2 * pb * (1 - pb)) + zb * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2
    return int(math.ceil(num / (p1 - p2) ** 2))


def n_medias(delta, desv, alfa=0.05, potencia=0.8):
    za, zb = stats.norm.ppf(1 - alfa / 2), stats.norm.ppf(potencia)
    return int(math.ceil(2 * ((za + zb) * desv / delta) ** 2))


def mde_proporcion(p, n, alfa=0.05, potencia=0.8):
    """Diferencia mínima detectable (absoluta) con n por grupo."""
    za, zb = stats.norm.ppf(1 - alfa / 2), stats.norm.ppf(potencia)
    return (za + zb) * math.sqrt(2 * p * (1 - p) / n)


# ---------------------------------------------------------------- lectura de resultados
def srm(n_c, n_t, share_t=0.5):
    """Prueba de desbalance: ¿el reparto observado es compatible con el planeado?"""
    n = n_c + n_t
    chi = (n_c - n * (1 - share_t)) ** 2 / (n * (1 - share_t)) + (n_t - n * share_t) ** 2 / (n * share_t)
    return float(1 - stats.chi2.cdf(chi, 1))


def comparar_proporciones(k_c, n_c, k_t, n_t, alfa=0.05):
    """Diferencia de tasas con rango de Newcombe (mejor cobertura que la fórmula simple)."""
    z = stats.norm.ppf(1 - alfa / 2)
    p_c, p_t = k_c / n_c, k_t / n_t
    l1, u1 = wilson(k_t, n_t, z)
    l2, u2 = wilson(k_c, n_c, z)
    d = p_t - p_c
    lo = d - math.sqrt((p_t - l1) ** 2 + (u2 - p_c) ** 2)
    hi = d + math.sqrt((u1 - p_t) ** 2 + (p_c - l2) ** 2)
    pb = (k_c + k_t) / (n_c + n_t)
    se0 = math.sqrt(pb * (1 - pb) * (1 / n_c + 1 / n_t)) or 1e-12
    p = float(2 * (1 - stats.norm.cdf(abs(d) / se0)))
    return {"tasa_control": p_c, "tasa_tratamiento": p_t, "dif_abs": d, "rango_abs": [lo, hi], "p": p}


def comparar_medias(x_c, x_t, alfa=0.05, boot=1000, seed=5):
    d = float(np.mean(x_t) - np.mean(x_c))
    asim = float(max(abs(stats.skew(x_c)), abs(stats.skew(x_t))))
    if asim > 2 or min(len(x_c), len(x_t)) < 200:
        rng = np.random.default_rng(seed)
        ds = [rng.choice(x_t, len(x_t)).mean() - rng.choice(x_c, len(x_c)).mean() for _ in range(boot)]
        lo, hi = np.percentile(ds, [100 * alfa / 2, 100 * (1 - alfa / 2)])
        metodo = "remuestreo (valores muy asimétricos o pocos casos)"
    else:
        se = math.sqrt(np.var(x_t, ddof=1) / len(x_t) + np.var(x_c, ddof=1) / len(x_c))
        z = stats.norm.ppf(1 - alfa / 2)
        lo, hi, metodo = d - z * se, d + z * se, "aproximación normal"
    p = float(stats.ttest_ind(x_t, x_c, equal_var=False).pvalue)
    return {"media_control": float(np.mean(x_c)), "media_tratamiento": float(np.mean(x_t)), "dif_abs": d, "rango_abs": [float(lo), float(hi)], "p": p, "metodo_rango": metodo}


def _etiquetas(g, control):
    vals = sorted(g.astype(str).unique())
    if len(vals) != 2:
        raise SystemExit("La columna de grupo debe tener exactamente 2 valores (control y tratamiento). Encontré: %s" % vals)
    if control is not None:
        if str(control) not in vals:
            raise SystemExit("El valor de control %r no aparece. Valores: %s" % (control, vals))
        c = str(control)
    else:
        c = next((v for v in vals if v.strip().lower() in {"control", "testigo", "holdout", "a", "0", "false", "no", "sin_campana", "sin campaña"}), vals[0])
    return c, [v for v in vals if v != c][0]


def leer(df, grupo, resultado, control=None, reparto=0.5, valor=None, gasto=None, revisiones=1, alfa=0.05, boot=1000):
    d = df[[grupo, resultado]].dropna().copy()
    d[grupo] = d[grupo].astype(str)
    c, t = _etiquetas(d[grupo], control)
    x = pd.to_numeric(d[resultado], errors="coerce")
    d = d.assign(_x=x).dropna(subset=["_x"])
    x_c, x_t = d.loc[d[grupo] == c, "_x"].values.astype(float), d.loc[d[grupo] == t, "_x"].values.astype(float)
    n_c, n_t = len(x_c), len(x_t)
    alfa_aj = alfa / max(1, revisiones)
    binario = set(np.unique(d["_x"])) <= {0.0, 1.0}
    alertas, notas = [], ["Se tomó como control: %s; como tratamiento: %s." % (c, t)]
    if binario:
        r = comparar_proporciones(int(x_c.sum()), n_c, int(x_t.sum()), n_t, alfa_aj)
        base = r["tasa_control"]
        mde = mde_proporcion(max(base, 1e-6), min(n_c, n_t))
        eventos = min(int(x_c.sum()), int(x_t.sum()))
    else:
        r = comparar_medias(x_c, x_t, alfa_aj, boot)
        base = r["media_control"]
        sd = float(np.sqrt((np.var(x_c, ddof=1) + np.var(x_t, ddof=1)) / 2))
        mde = (stats.norm.ppf(1 - alfa_aj / 2) + stats.norm.ppf(0.8)) * sd * math.sqrt(2 / min(n_c, n_t))
        eventos = min(int((x_c != 0).sum()), int((x_t != 0).sum()))
    lo, hi = r["rango_abs"]
    rel = lambda v: float(v / base) if base else None
    p_srm = srm(n_c, n_t, reparto)
    if p_srm < 0.001:
        alertas.append("Los grupos no tienen el tamaño planeado (%d frente a %d; probabilidad de que sea azar menor a 0,1%%). La asignación no fue aleatoria o hay un error de registro: no confíes en este resultado hasta resolverlo." % (n_c, n_t))
    if eventos < 30:
        alertas.append("Hay muy pocos casos con resultado en el grupo menor (%d): el rango es poco fiable." % eventos)
    if revisiones > 1:
        notas.append("Con %d revisiones se exigió más evidencia (nivel ajustado a %.3f) para no declarar un efecto por mirar muchas veces." % (revisiones, alfa_aj))
    concluyente = lo > 0 or hi < 0
    if p_srm < 0.001 or eventos < 10:
        nivel = "rojo"
        motivo = "El resultado no es confiable: " + ("los grupos no tienen el reparto planeado." if p_srm < 0.001 else "hay casi ningún caso con resultado.")
    elif concluyente and eventos >= 50:
        nivel = "verde"
        motivo = "El rango del efecto no incluye cero y la prueba está bien armada: hay evidencia de que la acción %s el resultado." % ("subió" if r["dif_abs"] > 0 else "bajó")
    elif concluyente:
        nivel, motivo = "amarillo", "El efecto es claro pero hay pocos casos (%d): confírmalo con más muestra." % eventos
    else:
        nivel = "amarillo"
        motivo = "No concluyente: el rango incluye cero. Con este tamaño solo se podían detectar cambios de %.0f%% o más sobre la base; un efecto menor no se puede descartar ni confirmar." % (100 * abs(rel(mde)) if base else float("nan"))
    res = {"tipo_resultado": "tasa (sí o no)" if binario else "valor medio", "personas": {"control": n_c, "tratamiento": n_t},
           "base_control": base, "efecto_absoluto": r["dif_abs"], "rango_efecto_absoluto_95": [lo, hi],
           "efecto_relativo": rel(r["dif_abs"]), "rango_efecto_relativo_95": [rel(lo), rel(hi)], "p_valor": r["p"],
           "efecto_minimo_detectable_relativo": rel(mde), "prob_desbalance_por_azar": p_srm, "semaforo": nivel, "motivo_semaforo": motivo,
           "alertas": alertas, "notas": notas}
    # retorno incremental
    if gasto is not None and (valor is not None or not binario):
        z = stats.norm.ppf(1 - alfa_aj / 2)
        if binario:
            valor_inc = lambda dif: dif * n_t * valor
        else:
            valor_inc = lambda dif: dif * n_t
        inc, inc_lo, inc_hi = valor_inc(r["dif_abs"]), valor_inc(lo), valor_inc(hi)
        roas, rlo, rhi = inc / gasto, inc_lo / gasto, inc_hi / gasto
        res["retorno_incremental"] = {"ventas_incrementales": inc, "retorno_por_cada_unidad_invertida": roas, "rango_95": [rlo, rhi], "gasto": gasto}
        se = (rhi - rlo) / (2 * z)
        res["para_calibrar_mmm"] = {"retorno": roas, "error": se, "ejemplo_comando": "--calibrar canal=%.3f:%.3f" % (roas, max(se, 1e-6))}
        if nivel == "rojo" or not concluyente:
            res["para_calibrar_mmm"]["advertencia"] = "No uses esta cifra para calibrar el modelo: el resultado de la prueba no es concluyente o no es confiable."
    return res


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("tamano")
    t.add_argument("--base", type=float, help="tasa actual (por ejemplo 0.04 para 4%%)")
    t.add_argument("--media", type=float, help="valor medio actual si el resultado es un monto")
    t.add_argument("--desv", type=float, help="desviación típica del monto")
    t.add_argument("--mejora", type=float, required=True, help="mejora relativa mínima que quieres detectar (0.10 = 10%%)")
    t.add_argument("--potencia", type=float, default=0.8)
    t.add_argument("--alfa", type=float, default=0.05)
    t.add_argument("--trafico", type=float, help="personas por día que entrarían a la prueba (total)")
    t.add_argument("--reparto", type=float, default=0.5, help="proporción que va al tratamiento")
    t.add_argument("--outdir", default="resultados")
    l = sub.add_parser("leer")
    l.add_argument("file")
    l.add_argument("--grupo", required=True)
    l.add_argument("--resultado", required=True)
    l.add_argument("--control")
    l.add_argument("--reparto", type=float, default=0.5, help="proporción planeada para el tratamiento")
    l.add_argument("--valor", type=float, help="valor de una conversión (si el resultado es sí o no)")
    l.add_argument("--gasto", type=float, help="gasto total del grupo de tratamiento")
    l.add_argument("--revisiones", type=int, default=1, help="cuántas veces miraste resultados antes del final")
    l.add_argument("--alfa", type=float, default=0.05)
    l.add_argument("--boot", type=int, default=1000)
    l.add_argument("--hoja")
    l.add_argument("--outdir", default="resultados")
    a = ap.parse_args()

    if a.cmd == "tamano":
        if a.base is not None:
            p1, p2 = a.base, a.base * (1 + a.mejora)
            if not 0 < p1 < 1 or not 0 < p2 < 1:
                raise SystemExit("La tasa base y la tasa con la mejora deben estar entre 0 y 1.")
            n = n_proporciones(p1, p2, a.alfa, a.potencia)
            desc = "tasa de %.2f%% a %.2f%%" % (100 * p1, 100 * p2)
        elif a.media is not None and a.desv is not None:
            n = n_medias(a.media * a.mejora, a.desv, a.alfa, a.potencia)
            desc = "valor medio de %.1f a %.1f" % (a.media, a.media * (1 + a.mejora))
        else:
            raise SystemExit("Indica --base (tasa) o --media y --desv (monto).")
        # con reparto desigual hace falta más gente en total: N = n / (2 s (1 - s))
        total = int(math.ceil(n / (2 * a.reparto * (1 - a.reparto))))
        res = {"detectar": desc, "personas_por_grupo": n, "personas_en_total": total, "potencia": a.potencia, "nivel_de_error": a.alfa}
        if a.trafico:
            res["dias_necesarios"] = int(math.ceil(total / a.trafico))
            res["recomendacion_duracion"] = "Redondea a semanas completas (%d) para cubrir los ciclos de la semana." % (7 * math.ceil(res["dias_necesarios"] / 7))
        res["advertencia"] = "Define de antemano la cifra a medir y la fecha de cierre, y no mires para detener la prueba antes: mirar muchas veces infla los falsos positivos."
        emit({"resumen": res}, os.path.join(a.outdir, "ab_tamano.json"))
        return

    df = load_table(a.file, a.hoja)
    need_cols(df, [a.grupo, a.resultado])
    res = leer(df, a.grupo, a.resultado, a.control, a.reparto, a.valor, a.gasto, a.revisiones, a.alfa, a.boot)
    emit({"resumen": res}, os.path.join(a.outdir, "ab_resultado.json"))


if __name__ == "__main__":
    main()
