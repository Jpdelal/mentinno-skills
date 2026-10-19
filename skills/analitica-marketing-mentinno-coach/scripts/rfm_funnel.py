#!/usr/bin/env python3
"""Valor de clientes (RFM) y fugas del embudo, con señales de insight ya calculadas.

RFM:    python3 rfm_funnel.py rfm   archivo --cliente COL --fecha COL --monto COL [--pedido COL] [--corte AAAA-MM-DD]
Embudo: python3 rfm_funnel.py embudo archivo --etapas "visitas,carrito,compra" [--segmento COL] [--periodo COL] [--valor 50]
"""
import argparse
import os

import _deps  # noqa: F401  (revisa librerías)
import numpy as np
import pandas as pd

from _utils import emit, load_table, need_cols, parse_dates, wilson

ACCIONES = {
    "Campeones": "Cuídalos: acceso anticipado, programa de referidos. No les regales descuentos.",
    "Leales": "Súbeles el ticket con venta cruzada y membresía. Pídeles reseñas.",
    "Nuevos o prometedores": "Asegura la segunda compra en las próximas semanas con una secuencia de bienvenida.",
    "En riesgo valiosos": "Prioridad uno: llámalos o escríbeles de forma personal antes de perderlos.",
    "Necesitan atención": "Recuérdales lo que les gustó con contenido y ofertas de su categoría.",
    "Dormidos": "Una sola campaña de reactivación de bajo costo. Si no responden, sácalos de las bases caras.",
}


def score(series, k, good_high=True):
    s = series if good_high else -series
    try:
        b = pd.qcut(s, k, labels=False, duplicates="drop")
    except ValueError:
        b = pd.Series(0, index=s.index)
    m = int(b.max()) + 1
    lvl = b / (m - 1) if m > 1 else pd.Series(0.5, index=s.index)
    return (b + 1).astype(int), lvl, m


def segmentar(lr, lf, lm):
    hiR, loR, hiF = lr >= 0.67, lr <= 0.34, lf >= 0.67
    if hiR and hiF:
        return "Campeones"
    if (not loR) and hiF:
        return "Leales"
    if loR and (lf >= 0.5 or lm >= 0.67):
        return "En riesgo valiosos"
    if hiR:
        return "Nuevos o prometedores"
    if loR:
        return "Dormidos"
    return "Necesitan atención"


def cmd_rfm(a):
    df = load_table(a.file, a.hoja)
    need_cols(df, [a.cliente, a.fecha, a.monto] + ([a.pedido] if a.pedido else []))
    df[a.fecha] = parse_dates(df[a.fecha], a.mdy)
    n0 = len(df)
    df = df.dropna(subset=[a.cliente, a.fecha, a.monto])
    neg = int((df[a.monto] <= 0).sum())
    df = df[df[a.monto] > 0]
    corte = pd.to_datetime(a.corte) if a.corte else df[a.fecha].max() + pd.Timedelta(days=1)
    g = df.groupby(a.cliente)
    freq = g[a.pedido].nunique() if a.pedido else g.size()
    t = pd.DataFrame({"recencia_dias": (corte - g[a.fecha].max()).dt.days, "frecuencia": freq, "monto_total": g[a.monto].sum()})
    n = len(t)
    k = 5 if n >= 1000 else 3
    t["R"], lr, mr = score(t["recencia_dias"], k, good_high=False)
    t["F"], lf, mf = score(t["frecuencia"], k)
    t["M"], lm, mm = score(t["monto_total"], k)
    t["segmento"] = [segmentar(x, y, z) for x, y, z in zip(lr, lf, lm)]
    tot = t["monto_total"].sum()
    seg = t.groupby("segmento").agg(clientes=("R", "size"), ingresos=("monto_total", "sum"), recencia_media=("recencia_dias", "mean"),
                                    frecuencia_media=("frecuencia", "mean")).reset_index()
    seg["pct_clientes"] = 100 * seg["clientes"] / n
    seg["pct_ingresos"] = 100 * seg["ingresos"] / tot
    seg["ticket_por_cliente"] = seg["ingresos"] / seg["clientes"]
    seg["que_hacer"] = seg["segmento"].map(ACCIONES)
    seg = seg.sort_values("ingresos", ascending=False)

    # señales
    top20 = t["monto_total"].sort_values(ascending=False).head(int(np.ceil(0.2 * n))).sum() / tot * 100
    una_compra = 100 * (t["frecuencia"] == 1).mean()
    rep = df.groupby(a.cliente)[a.fecha].agg(["min", "max", "count"])
    rep = rep[rep["count"] >= 2]
    ventana = float(((rep["max"] - rep["min"]).dt.days / (rep["count"] - 1)).median()) if len(rep) >= 20 else None
    senales = []
    senales.append("El 20%% de tus clientes genera %.0f%% de los ingresos." % top20)
    senales.append("%.0f%% de tus clientes compró una sola vez: ahí está el mayor espacio para crecer." % una_compra)
    riesgo = seg[seg["segmento"] == "En riesgo valiosos"]
    if len(riesgo):
        r = riesgo.iloc[0]
        senales.append("%d clientes valiosos llevan tiempo sin comprar (%.0f%% de los ingresos históricos). Es la primera lista a trabajar." % (r["clientes"], r["pct_ingresos"]))
    if ventana:
        lapsed = int(((t["recencia_dias"] > 2 * ventana) & (t["monto_total"] >= t["monto_total"].quantile(0.6))).sum())
        senales.append("Quienes repiten compran cada %.0f días en promedio. %d clientes de valor alto superan el doble de ese plazo: probablemente ya se fueron." % (ventana, lapsed))
    os.makedirs(a.outdir, exist_ok=True)
    t.reset_index().to_csv(os.path.join(a.outdir, "rfm_clientes.csv"), index=False)
    seg.to_csv(os.path.join(a.outdir, "rfm_segmentos.csv"), index=False)
    conf = "verde" if n >= 1000 and n0 > 0 and neg / n0 < 0.05 else "amarillo"
    res = {"clientes": n, "niveles_usados": k, "fecha_de_corte": str(corte.date()), "filas_excluidas_por_monto_cero_o_negativo": neg,
           "ventana_de_recompra_dias": ventana, "semaforo": conf,
           "motivo_semaforo": ("Hay clientes suficientes y pocas devoluciones o montos inválidos para segmentar con confianza." if conf == "verde" else "Hay pocos clientes (menos de 1.000) o muchas filas con monto cero o negativo: los segmentos son orientativos."),
           "segmentos": seg.round(1).drop(columns=["que_hacer"]).to_dict("records"), "senales": senales,
           "archivos": [os.path.join(a.outdir, "rfm_clientes.csv"), os.path.join(a.outdir, "rfm_segmentos.csv")]}
    emit({"resumen": res, "acciones": ACCIONES}, os.path.join(a.outdir, "rfm.json"))


def cmd_embudo(a):
    df = load_table(a.file, a.hoja)
    et = [e.strip() for e in a.etapas.split(",")]
    need_cols(df, et + [c for c in (a.segmento, a.periodo) if c])
    notas = []

    def paso(sub):
        s = [float(sub[e].sum()) for e in et]
        out = []
        for i in range(len(et) - 1):
            k, n = s[i + 1], s[i]
            lo, hi = wilson(k, n)
            out.append({"de": et[i], "a": et[i + 1], "entran": n, "pasan": k, "conversion_pct": 100 * k / n if n else np.nan,
                        "rango_pct": [100 * lo, 100 * hi]})
        return s, out

    s, pasos = paso(df)
    for p in pasos:
        if p["pasan"] > p["entran"]:
            notas.append("Entre %s y %s hay más gente en la etapa siguiente que en la anterior: revisa la definición de las etapas." % (p["de"], p["a"]))
    punta = 100 * s[-1] / s[0] if s[0] else np.nan
    mayor_perdida = max(pasos, key=lambda p: p["entran"] - p["pasan"])
    menor_conv = min(pasos, key=lambda p: p["conversion_pct"])
    senales = ["Convierte el %.2f%% de principio a fin (%d de %d)." % (punta, s[-1], s[0]),
               "Donde más gente se pierde en número: entre %s y %s (%d personas)." % (mayor_perdida["de"], mayor_perdida["a"], mayor_perdida["entran"] - mayor_perdida["pasan"])]
    if menor_conv is not mayor_perdida:
        senales.append("El paso más débil en proporción: %s a %s (%.1f%%)." % (menor_conv["de"], menor_conv["a"], menor_conv["conversion_pct"]))
    # impacto de mejorar 10% relativo el paso más débil
    mejora = 0.10 * s[-1]
    msg = "Si mejoras un 10%% relativo el paso %s a %s, sumarías unas %d conversiones finales." % (menor_conv["de"], menor_conv["a"], round(mejora))
    if a.valor:
        msg += " Equivale a unos %.0f en ingresos por el mismo volumen de tráfico." % (mejora * a.valor)
    senales.append(msg)

    brechas, simpson = [], None
    if a.segmento:
        for v, sub in df.groupby(a.segmento):
            ss, pp = paso(sub)
            for po, pg in zip(pasos, pp):
                if pg["entran"] >= 100:
                    lo, hi = pg["rango_pct"]
                    if po["conversion_pct"] < lo or po["conversion_pct"] > hi:
                        brechas.append({"segmento": v, "paso": "%s a %s" % (pg["de"], pg["a"]), "conversion_pct": pg["conversion_pct"],
                                        "promedio_pct": po["conversion_pct"], "personas_en_el_paso": pg["entran"]})
        brechas.sort(key=lambda b: abs(b["conversion_pct"] - b["promedio_pct"]), reverse=True)
        for b in brechas[:3]:
            dir_ = "mejor" if b["conversion_pct"] > b["promedio_pct"] else "peor"
            senales.append("El segmento %s convierte %s que el promedio en %s: %.1f%% frente a %.1f%%." % (b["segmento"], dir_, b["paso"], b["conversion_pct"], b["promedio_pct"]))
    if a.periodo:
        per = sorted(df[a.periodo].dropna().unique().tolist(), key=lambda v: str(v))
        if len(per) >= 2:
            p0, p1 = per[0], per[-1]
            c = lambda sub: 100 * sub[et[-1]].sum() / sub[et[0]].sum()
            d0, d1 = df[df[a.periodo] == p0], df[df[a.periodo] == p1]
            senales.append("Conversión total en %s: %.2f%%; en %s: %.2f%%." % (p0, c(d0), p1, c(d1)))
            if a.segmento:
                bajan, sube_global = 0, c(d1) > c(d0)
                vals = df[a.segmento].dropna().unique()
                for v in vals:
                    x0, x1 = d0[d0[a.segmento] == v], d1[d1[a.segmento] == v]
                    if x0[et[0]].sum() > 0 and x1[et[0]].sum() > 0 and c(x1) < c(x0):
                        bajan += 1
                if sube_global and bajan == len(vals):
                    simpson = "La conversión global subió, pero bajó dentro de cada %s. El cambio viene de la mezcla de tráfico, no de una mejora real." % a.segmento
                elif (not sube_global) and bajan == 0:
                    simpson = "La conversión global bajó, pero subió dentro de cada %s. El problema es la mezcla de tráfico." % a.segmento
                if simpson:
                    senales.insert(0, "ATENCIÓN: " + simpson)
    conf = "verde" if s[0] >= 1000 and not notas else "amarillo"
    res = {"embudo": [{"etapa": e, "personas": x} for e, x in zip(et, s)], "pasos": pasos, "senales": senales,
           "brechas_por_segmento": brechas[:6], "paradoja_de_simpson": simpson, "notas_de_datos": notas, "semaforo": conf,
           "motivo_semaforo": ("Hay volumen suficiente y sin problemas en los datos del embudo." if conf == "verde" else "Hay poco volumen (menos de 1.000 en la primera etapa) o notas sobre los datos: las diferencias pequeñas pueden ser ruido.")}
    os.makedirs(a.outdir, exist_ok=True)
    emit({"resumen": res}, os.path.join(a.outdir, "embudo.json"))


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("rfm")
    r.add_argument("file")
    r.add_argument("--cliente", required=True)
    r.add_argument("--fecha", required=True)
    r.add_argument("--monto", required=True)
    r.add_argument("--pedido")
    r.add_argument("--corte")
    e = sp.add_parser("embudo")
    e.add_argument("file")
    e.add_argument("--etapas", required=True)
    e.add_argument("--segmento")
    e.add_argument("--periodo")
    e.add_argument("--valor", type=float)
    for p in (r, e):
        p.add_argument("--hoja")
        p.add_argument("--mdy", action="store_true")
        p.add_argument("--outdir", default="resultados")
    a = ap.parse_args()
    cmd_rfm(a) if a.cmd == "rfm" else cmd_embudo(a)


if __name__ == "__main__":
    main()
