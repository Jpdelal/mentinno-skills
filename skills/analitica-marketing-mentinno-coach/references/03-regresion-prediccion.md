# Módulo 3: relaciones cuantificadas y predicción (regresión simple y múltiple)

## Cuándo usarlo
"¿Cuánto vendré si subo la inversión 20%?", "¿Qué pesa más: precio, descuento o inversión?", "Dame un pronóstico con escenarios".

## Qué método y por qué
- **Una sola variable explicativa:** regresión simple. Sirve para una primera lectura.
- **Varias variables:** regresión múltiple. Separa el efecto de cada una descontando las demás.
- **Resultado en proporciones o elasticidades** ("¿cuánto cambian las ventas si el precio sube 1%?"): activa `--log`.
El script `regress.py` agrega solo tendencia y temporada cuando hay fecha, para no confundirlas con efectos de las variables.

## Datos y límites
- Mínimo orientativo: 15 filas por cada variable que se incluye. Con menos, el script baja el semáforo.
- Variables que se mueven casi igual no se pueden separar. El script avisa.
- Nunca extrapoles muy lejos del rango observado: si nunca se invirtió más de 10.000, no pronostiques con 30.000.

## Qué entrega el script
Efecto de cada variable por unidad con rango, peso relativo, escenarios (actual, prudente, optimista y los que la persona defina) con rango del 80% y 95%, y la palanca de mayor impacto. También: error con datos nuevos y alertas.

## Cómo comunicar un pronóstico
- Siempre tres escenarios y un rango. "Base: unas 56.000 por semana (rango probable 50.000 a 62.000)".
- Explica qué supone cada escenario ("inversión +10%, resto igual").
- El rango del 80% es el que se usa para planear; el del 95% para gestionar riesgo.
- Di cuánto se equivoca el modelo con datos nuevos ("en pruebas pasadas se equivocó 10% en promedio").

## Señales de insight que vale la pena mirar
- Variable fuertemente relacionada que desaparece al controlar otras: no aporta por sí sola.
- Efecto de signo contrario al de la relación simple: la lectura aislada engaña.
- Elasticidades: qué palanca mueve más el resultado por cada 1% de cambio.
- Palanca con mayor efecto por la misma variación porcentual: dónde empujar primero.

## Errores comunes
- Meter todas las variables disponibles. Más variables con pocos datos dan modelos frágiles.
- Presentar R cuadrado como "precisión". Lo que importa es el error con datos nuevos.
- Usar el modelo para afirmar causa.
