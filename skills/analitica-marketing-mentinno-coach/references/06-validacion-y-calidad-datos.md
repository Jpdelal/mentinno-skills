# Módulo 6: calidad de datos, validación y semáforo

## Compuerta de calidad (script `profile_data.py`)
Nota A a D según vacíos, duplicados, saltos en el calendario, valores extremos, valores negativos y tamaño. Qué hacer con cada nota está en SKILL.md. Después, `alcances_posibles` dice qué análisis es defendible.

## Umbrales orientativos (heurísticas, no leyes)
| Análisis | Mínimo razonable | Qué pasa si no se cumple |
|---|---|---|
| RFM | cliente, fecha y monto por compra; 1000 o más clientes para 5 niveles | Con menos se usan 3 niveles; con menos de 200 es solo descriptivo |
| Embudo | 100 personas por etapa para comparar segmentos | Se omiten las comparaciones con poca gente |
| Regresión | 15 filas por variable; fecha si es serie de tiempo | Semáforo baja; se reduce el número de variables |
| Resultado sí o no | 10 casos del grupo menor por variable; resultado bien definido | Se reducen variables o se agrupan |
| MMM | 104 semanas, canales con variación, idealmente un experimento | De 52 a 103 es orientativo; menos de 52 no se hace |

## Lista de validación (10 puntos)
1. La decisión del intake queda respondida.
2. Los datos alcanzan (nota y alcance).
3. Prueba con datos nuevos (los scripts la hacen: partición por fecha o aleatoria).
4. Sin fuga de información (el script alerta si el resultado es demasiado bueno).
5. Confusores revisados: temporada, promociones, mezcla de público.
6. Rangos útiles: si el rango incluye "no pasa nada" y "pasa mucho", se dice.
7. Sentido de negocio: la persona confirma que una cifra clave es creíble.
8. Lenguaje causal bajo control: "se asocia" salvo experimento.
9. Recomendaciones coherentes con el semáforo.
10. Trazabilidad: cada cifra viene de la base o de un script.

## Semáforo (frases fijas)
- **Verde:** "Puedes decidir con esto." Datos suficientes, prueba con datos nuevos buena, sin alertas relevantes.
- **Amarillo:** "Decide con cautela y valida con una prueba pequeña." Hay alertas o falta calibración.
- **Rojo:** "No decidas solo con esto. Sirve como hipótesis." Datos insuficientes, resultado sospechoso o error alto con datos nuevos. No se recomienda mover dinero.
Acompaña el color con la razón principal en una frase.

## Reglas de semáforo por módulo
- Pruebas A/B y uplift: sin aleatorización verificable (reparto 50/50, variables que no adivinan el grupo) es rojo. Mirar los resultados cada día sin corregir infla los falsos positivos: usa `--revisiones`.
- Diferencias en diferencias: sin tendencias paralelas previas no hay efecto que afirmar; menos de 5 unidades por grupo nunca es verde.
- Valor de vida: la prueba con los últimos 6 meses decide el color; suscripciones y saltos de demanda no son verdes.
- Atribución: máximo amarillo siempre, porque reparte crédito y no mide efecto.
- Cada módulo se valida con `tests/` contra datos simulados con respuesta conocida; córrelos tras cualquier cambio en un script.

## Qué hacer cuando falla algo
- Datos insuficientes: baja el alcance y dilo ("con 6 meses de datos puedo describir, no predecir").
- Resultado sospechoso: busca la variable que filtra la respuesta, retírala y repite.
- Rango demasiado amplio: dilo como resultado ("con estos datos no se puede distinguir entre A y B") y propón qué dato lo resolvería.
- Una cifra no tiene sentido para el negocio: no la defiendas; revisa la definición de la columna con la persona.

## Reproducibilidad
Anota en el anexo: archivo y fecha de los datos, columnas usadas, parámetros del script, y semilla cuando aplique. Una persona distinta debe poder obtener lo mismo.
