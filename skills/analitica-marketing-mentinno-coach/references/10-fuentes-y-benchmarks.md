# Módulo 10: fuentes y uso de benchmarks

## Política de benchmarks
No uses benchmarks sectoriales de memoria. Orden de preferencia:
1. Histórico propio de la persona (mismo negocio, periodos anteriores).
2. Fuente externa citada con fecha y alcance, presentada como orientativa.
3. Ninguno, y decirlo.

Para benchmarks de conversión, costos de adquisición o tasas por industria que se necesiten actuales, busca en la web en la sesión (fecha incluida) y cita. Para cualquier dato de Mentinno u otras cifras de negocio de Juan Pablo que no estén en el contexto, marca `[DATO REAL: qué falta]` en lugar de reconstruir.

## Qué se sabe del perfil profesional (2026) y por qué importa al diseño
- Las ofertas de analista de marketing piden consistentemente SQL, Excel, una herramienta de visualización y, cada vez más, Python o R, además de comunicar a públicos no técnicos. El skill se concentra en la parte menos abundante: pasar del análisis a la decisión y contarlo.
- La literatura docente sobre CRISP-DM señala que la formación suele sobreenfatizar lo técnico y subestimar el storytelling; por eso el módulo 7 es parte central del flujo.

## Criterios técnicos con respaldo en práctica documentada
- RFM: los cuantiles necesitan volumen; con bases pequeñas conviene menos niveles. No copiar benchmarks de otra industria.
- Causalidad: jerarquía de evidencia con experimento aleatorio, geo-pruebas, diferencias en diferencias o control sintético, y emparejamiento; la correlación es lo más débil. Diferencias en diferencias exige tendencias paralelas.
- Clasificación: un modelo por acción, regresión logística como base, calibración aparte del AUC, y tabla de lift por deciles como entregable de negocio. Un AUC extremo es sospecha de fuga.
- MMM: es correlacional por naturaleza; la práctica actual calibra con experimentos y reporta incertidumbre. Meridian, Robyn y PyMC-Marketing admiten calibración. Algunos proveedores sugieren que bajo cierta inversión anual el MMM tradicional no compensa; es un dato comercial, úsalo solo como alerta.

## Fuentes principales consultadas (octubre de 2026)
- PyMC-Marketing: Bayesian Marketing Mix Models (JOSS), https://joss.theoj.org/papers/10.21105/joss.10805.pdf
- Calibración de MMM con experimentos (documentación diff-diff), https://diff-diff.readthedocs.io/en/latest/api/mmm.html
- Meridian, primeras impresiones (Jaywing), https://jaywing.com/views/news/first-impressions-meridian-google-s-mmm-software-is-finally-released
- Skills de analista de marketing 2026, https://resumegeni.com/blog/marketing-analyst-skills-guide
- Robert Half, Marketing Analytics Manager 2026, https://www.roberthalf.com/us/en/insights/career-development/hot-job-marketing-analytics-manager
- Jaggia, Kelly, Lertwachara y Chen, CRISP-DM en analítica de negocios, https://info.mheducation.com/rs/128-SJW-347/images/Jaggia_Kelly_Lertwachara_Chen%20Paper.pdf
- RFM y volumen (Darkroom), https://www.darkroomagency.com/observatory/rfm-analysis
- Geo-experimentos y diferencias en diferencias, https://medium.com/@a.takeuchi121/beyond-the-a-b-test-measuring-incrementality-with-geo-experiments-2a68a61b0ab5
- Chen y colaboradores (Google), Robust Causal Inference for iROAS (Annals of Applied Statistics, 2022), https://research.google/pubs/robust-causal-inference-for-incremental-return-on-ad-spend-with-randomized-paired-geo-experiments/
- Clasificación, propensión y churn (NYU), https://nyu.manifoldapp.org/read/chapter-09-classification-propensity-and-churn-models
- Flujo de modelo de propensión y lift (MetricGate), https://metricgate.com/blogs/workflow-for-building-a-propensity-model/

- Módulos 11 a 14: los métodos son estándar (prueba de proporciones y medias, corrección de Bonferroni, regresión con interacciones para uplift, diferencias en diferencias con prueba de tendencias previas, BG/NBD de Fader, Hardie y Lee, Gamma-Gamma, cadena de Markov de absorción y valores de Shapley). Se validaron en `tests/` contra datos simulados con respuesta conocida, no contra bases reales.

Los umbrales numéricos de este skill (por ejemplo, 15 filas por variable, 10 casos por variable, 104 semanas) son heurísticas de buena práctica, no normas. Ajusta con criterio cuando el contexto lo justifique y explica por qué.
