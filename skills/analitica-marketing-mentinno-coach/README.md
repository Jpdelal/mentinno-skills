# Analítica de marketing Mentinno con coach

Skill de Claude que convierte una base de datos de marketing y una pregunta de negocio en una decisión que se puede tomar el lunes por la mañana. Está diseñado para alumnos y profesionales de marketing, ventas y dirección que no programan.

Versión 1.0.0. Idioma: español. Licencia: MIT.

## Qué hace

Recibe un archivo CSV o Excel y una pregunta ("¿dónde pongo el presupuesto?", "¿a quién le doy el descuento?", "¿funcionó la prueba?"). Elige el método, ejecuta los cálculos con scripts, valida el resultado y responde en lenguaje de negocio: titular, tres hallazgos con cifras, lo que no se veía a simple vista, acciones priorizadas y un semáforo de confianza con su razón.

## Los 14 módulos

| N.º | Módulo | Responde | Script |
|---|---|---|---|
| 1 | Descriptivo, RFM y embudo | ¿Qué clientes valen más? ¿Dónde se pierde la conversión? | `rfm_funnel.py`, `profile_data.py` |
| 2 | Correlación y causalidad | ¿Esto se relaciona con aquello? ¿Lo causó mi campaña? | criterio del módulo |
| 3 | Regresión y predicción | ¿Cuánto venderé si cambio la inversión o el precio? | `regress.py` |
| 4 | Propensión y churn | ¿Quién va a comprar o abandonar? | `classify.py` |
| 5 | Mezcla de medios (MMM) | ¿Cómo reparto el presupuesto entre canales? | `mmm_lite.py` |
| 6 | Validación y calidad de datos | ¿Los datos alcanzan para afirmar esto? | `profile_data.py` |
| 7 | Relato para directivos | ¿Cómo lo presento? | plantilla |
| 8 | Coach | ¿Por qué se hace así? | integrado |
| 9 | Lenguaje claro | Traducción de jerga a lenguaje de negocio | integrado |
| 10 | Fuentes y benchmarks | ¿Qué referencia uso? | referencia |
| 11 | Pruebas A/B e incrementalidad | ¿Funcionó? ¿Cuánta gente necesito? ¿Cuánto aportó de más un canal? | `ab_test.py` |
| 12 | Uplift y diferencias en diferencias | ¿A quién le sirve el descuento? ¿Funcionó la campaña ya hecha? | `uplift_did.py` |
| 13 | Valor de vida del cliente | ¿Cuánto vale un cliente? ¿Cuánto puedo gastar en conseguirlo? | `clv.py` |
| 14 | Atribución multitoque | ¿Qué canal merece el crédito? ¿El último clic me engaña? | `attribution.py` |

## Ejemplos de uso en Claude

Adjunta el archivo y escribe una de estas frases.

- "Revisa estas ventas semanales y dime en qué canal conviene invertir más." Activa la mezcla de medios, con rangos de incertidumbre y reasignación sugerida.
- "Hicimos una prueba con un grupo de control. ¿Funcionó?" Activa el módulo 11 y verifica además que el reparto de grupos esté bien armado.
- "¿A quién le mando el descuento para no regalar margen?" Activa uplift, y compara contra ordenar por probabilidad de compra.
- "¿Cuánto vale un cliente de esta base?" Activa valor de vida, con prueba sobre los últimos seis meses y rango.
- "Google dice una cosa y Meta otra. ¿A quién le creo?" Activa atribución, con siete métodos lado a lado y señal de canales que cobran ventas ajenas.
- "Quiero aprender analítica mientras trabajo." Sube el coach al nivel medio o profundo.

## El semáforo

| Color | Mensaje | Qué hacer |
|---|---|---|
| Verde | Puedes decidir con esto | Decidir, con el rango a la vista |
| Amarillo | Decide con cautela y valida con una prueba pequeña | Probar antes de mover un presupuesto grande |
| Rojo | No decidas solo con esto. Sirve como hipótesis | Conseguir mejores datos o diseñar una prueba |

La atribución nunca pasa de amarillo, porque reparte crédito y no mide efecto causal.

## Validación

Cada módulo se corre contra datos simulados con respuesta conocida. Resultados medidos en las pruebas del repositorio:

| Módulo | Prueba | Resultado |
|---|---|---|
| Mezcla de medios | 16 semillas, rangos de aporte frente al valor verdadero | cobertura 84%, error de aporte 2,1 puntos |
| Diferencias en diferencias | 300 paneles, rango 95% frente al efecto verdadero | cobertura 97,0%, falsos positivos 5,3% |
| Uplift | 10 simulaciones, correlación del puntaje con el efecto verdadero | 0,84 |
| Atribución | 6 simulaciones, diferencia máxima con el reparto exacto (Shapley) | 3 puntos |
| Valor de vida | error de compras e ingresos sobre 6 meses no vistos | dentro de umbrales en las pruebas |

Para reproducirlas:

```bash
pip install -r requirements.txt
for t in check_classify check_ab check_uplift_did check_clv check_attribution bench_mmm; do python3 tests/$t.py; done
```

## Límites que el skill declara

- La mezcla de medios es una versión ligera. Sin experimentos de referencia su confianza máxima es amarilla. Para decisiones de gran presupuesto se recomienda Meridian, Robyn o PyMC-Marketing con un especialista.
- Los rangos no cubren variables importantes que el modelo no incluye.
- La atribución reparte crédito, no mide efecto. Un canal de retargeting sin efecto real puede recibir mucho crédito, y la señal de canal de cierre es la que lo delata.
- El valor de vida no aplica a suscripciones ni compras programadas.
- Diferencias en diferencias exige que los grupos fueran en paralelo antes de la acción.
- La validación es contra datos simulados, no contra bases reales. Antes de usarlo en una decisión de alto monto, revisa los resultados con alguien que conozca el negocio.

## Estructura de la carpeta

```
analitica-marketing-mentinno-coach/
  SKILL.md              instrucciones que lee Claude
  references/           14 guías, una por módulo
  scripts/              cálculos (Python)
  tests/                pruebas contra respuesta conocida
  assets/               plantilla de resumen ejecutivo
  requirements.txt      dependencias
```

## Datos de práctica

```bash
python3 scripts/demo_data.py datos_demo
```

Genera nueve bases (ventas semanales, transacciones, embudo, bajas de clientes, mezcla de medios, prueba A/B, campaña de uplift, panel de tiendas y toques de atribución) y un archivo `verdad.json` con las respuestas correctas, para comparar lo que estima el skill con lo que realmente ocurrió.

## Privacidad

Los scripts se ejecutan en tu equipo y no envían datos a ningún servicio. No uses atributos sensibles (género, etnia, religión, salud) para puntuar personas, y trabaja con datos pseudonimizados.
