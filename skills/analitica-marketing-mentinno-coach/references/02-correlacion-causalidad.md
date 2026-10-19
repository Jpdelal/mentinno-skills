# Módulo 2: relaciones entre variables y causalidad

## Cuándo usarlo
"¿Esto se relaciona con las ventas?", "¿Funcionó mi campaña?", "¿Fue el descuento o fue la temporada?"

## Escalera de evidencia (siempre di en qué peldaño estás)
1. **Observación:** dos cosas se mueven juntas. Es una pista.
2. **Asociación controlada:** se mantiene al descontar tendencia, temporada y otras variables (script `regress.py`). Mejor pista, todavía no prueba.
3. **Cuasi experimento:** comparación antes y después contra un grupo parecido que no recibió la acción (diferencias en diferencias, control sintético, zonas geográficas pareadas). Evidencia sólida si el grupo es realmente comparable.
4. **Experimento con grupo de control aleatorio:** la mejor evidencia. Respuesta a "¿cuánto vendí por la campaña y no por otra cosa?".

Usa la palabra "causa" solo en los peldaños 3 y 4. En 1 y 2 usa "se asocia con".

## Correlación en lenguaje de negocio
Dos cosas que suben juntas no implican que una empuje a la otra. Tres razones típicas por las que engañan:
- **Tercer factor:** la temporada sube ventas y envíos de newsletters a la vez. El newsletter parece funcionar y no hace nada.
- **Sentido inverso:** se invierte más cuando se espera vender más, no al revés.
- **Mezcla de público:** el efecto global desaparece o se invierte dentro de cada grupo (Simpson).

El script `regress.py` marca automáticamente las variables que se mueven con el resultado pero no aportan nada propio al descontar las demás.

## Cuando la persona pregunta "¿lo causó mi campaña?"
1. Pregunta si hubo grupo sin campaña (zona, segmento, lista excluida). Si sí, compara y usa diferencias en diferencias.
2. Si no hubo, explica que solo se puede hablar de asociación, y propón una prueba pequeña: excluir al azar una parte de la audiencia o apagar la campaña en 2 o 3 zonas comparables por 4 a 6 semanas.
3. Para diseñar la prueba: elegir zonas parecidas en historia de ventas, definir de antemano la métrica y el plazo, y no cambiar nada más durante la prueba. Cuidado con que las zonas se contaminen entre sí (la gente se mueve).

## Cómo narrarlo (ejemplo ilustrativo, no reutilices las cifras)
"Entre las semanas con más inversión y las de más ventas hay relación clara, pero también coinciden con la temporada alta. Descontando eso, cada 1.000 invertidos se asocian con unas 2.500 más en ventas, con un rango de 2.000 a 3.000. Para confirmar que es la inversión y no la temporada, sugiero apagarla 4 semanas en dos ciudades comparables."
