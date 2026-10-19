# Módulo 12: uplift y diferencias en diferencias

## Cuándo usarlo
- **Uplift:** "¿A quién le sirve el descuento?", "¿A quién contacto para que cambie su conducta?", "¿Estoy regalando descuento a gente que iba a comprar igual?". Requiere una prueba aleatoria previa (módulo 11).
- **Diferencias en diferencias:** "¿Funcionó la campaña que ya hicimos en estas ciudades?", "¿Qué pasó con las ventas de las tiendas que rediseñamos frente a las que no?". Sirve cuando no hubo aleatorización pero hay un grupo parecido sin la acción.

Ambos están en el peldaño 3 y 4 de la escalera de evidencia (módulo 2). Uplift con asignación aleatoria sube al peldaño 4. Diferencias en diferencias es peldaño 3: dice "se asocia con, bajo el supuesto de que los grupos iban en paralelo".

## Uplift: qué es en lenguaje simple
Un modelo de propensión (módulo 4) dice quién tiene más probabilidad de comprar. Uplift dice a quién le **cambia** la conducta la acción. Hay cuatro tipos de personas: los que compran con o sin tu acción, los que no compran con o sin ella, los que compran solo si los contactas (los que importan) y los que se molestan y se van si los contactas. Dirigir por probabilidad de compra suele elegir al primer grupo, que no necesitaba el descuento.

## Uplift: datos mínimos
- Una prueba aleatoria: una parte recibió la acción y otra no, con resultado por persona.
- Variables de cada persona anteriores a la acción (nunca posteriores).
- Al menos 50 casos con resultado en cada grupo. Con muy pocos casos el uplift por persona es ruido, y el script lo dice.
- Entre 10.000 y 30.000 personas es un tamaño cómodo. Con 2.000 solo se detectan diferencias grandes entre personas.

## Uplift: lo que hace `uplift_did.py uplift`
1. Revisa que la asignación haya sido al azar (reparto de grupos y si las variables permiten adivinar quién recibió la acción). Si no fue al azar, semáforo rojo: el análisis confundiría quién fue elegido con el efecto de la acción.
2. Estima el cambio de probabilidad por persona. Por defecto usa una regresión con interacciones (estable y explicable); la opción `--modelo arboles` usa dos modelos de árboles y conviene con más de 30.000 personas y relaciones no lineales.
3. **Evalúa fuera de muestra:** cada persona se puntúa con un modelo que no la vio. Luego usa la asignación aleatoria para medir el efecto real dentro de cada décimo del ranking. Esa es la prueba de que el ranking sirve.
4. Compara el 30% de arriba con el 30% de abajo y da el rango de esa diferencia.
5. Compara contra ordenar por probabilidad de compra.
6. Con valor y costo por contacto, indica en qué deciles conviene actuar.

## Cómo leer el resultado de uplift
- **Efecto promedio:** lo que la acción logró en promedio. Es la primera pregunta de la prueba.
- **Tabla por deciles:** efecto observado en cada décimo del ranking. Si el decil 1 muestra un efecto claramente mayor que el 10, el ranking sirve.
- **Efecto capturado:** "contactando al mejor 30% se obtiene cerca del 60% del efecto total". Es la cifra que justifica no contactar a todos.
- **Arriba por uplift frente a arriba por probabilidad:** muestra cuánto pierde quien dirige por probabilidad de compra.

## Uplift: semáforo
- **Verde:** asignación al azar y el 30% de arriba responde más que el 30% de abajo con rango que no incluye cero.
- **Amarillo:** no se distingue a quién le sirve más. El efecto promedio puede ser real, pero conviene tratar a todos igual o ampliar la prueba.
- **Rojo:** asignación que no parece aleatoria, o casi sin casos con resultado.

## Diferencias en diferencias: qué es en lenguaje simple
Se compara cuánto cambió el grupo con acción entre antes y después, contra cuánto cambió el grupo sin acción en el mismo periodo. Lo que el primero cambió de más es el efecto. Así se descuentan la temporada, el ciclo económico y todo lo que afectó a ambos por igual.

## Diferencias en diferencias: supuesto que lo sostiene
**Los dos grupos habrían evolucionado en paralelo sin la acción.** No se puede probar, pero se puede revisar con lo que pasó antes. El script lo hace de dos formas:
- **Tendencias previas:** compara la pendiente de cada grupo antes de la acción.
- **Falso inicio:** simula que la acción ocurrió a mitad del periodo previo. Si ahí aparece un efecto, los grupos ya se separaban solos.

Si ambas señales fallan, semáforo rojo. Si falla una, amarillo.

## Diferencias en diferencias: datos mínimos
- Unidades repetidas en el tiempo (tiendas, ciudades, clientes) con una cifra por periodo.
- Al menos 4 periodos antes (para revisar el paralelismo) y 1 después.
- Al menos 5 unidades por grupo para un rango fiable. Con 3 frente a 3 el resultado es muy sensible a una sola unidad y nunca sale verde.
- Cada unidad pertenece a un grupo durante todo el periodo.

## Diferencias en diferencias: lo que hay que cuidar
- **Cómo se eligió el grupo con acción.** Si se eligieron las tiendas que ya iban mejor, el supuesto probablemente falla.
- **Otros cambios al mismo tiempo** en solo un grupo (una promoción local, una nueva competencia).
- **Contaminación:** el grupo sin acción también vio la campaña (la gente cruza zonas, medios que llegan a todos).
- **Acción escalonada:** si las unidades recibieron la acción en fechas distintas, este script no corresponde. Propón dividir en cohortes por fecha o usar un especialista.
- **Un solo grupo con acción (una sola ciudad):** el rango no es fiable. Dilo y propone más unidades de comparación.

## Retorno incremental y calibración
Con `--gasto`, el script de diferencias en diferencias da el retorno incremental con su rango y la línea `--calibrar canal=retorno:error` para la mezcla de medios, igual que el módulo 11. Solo úsala si el semáforo es verde.

## Errores comunes
- Dirigir por probabilidad de compra y llamar a eso "personalización".
- Usar variables posteriores a la acción para predecir el uplift (el modelo parece perfecto y no sirve).
- Declarar un efecto causal con diferencias en diferencias sin mostrar que los grupos iban en paralelo.
- Comparar "antes y después" sin grupo de comparación: mezcla el efecto con la temporada.
- Interpretar un uplift por persona como si fuera exacto: es un ranking, no una medida individual.

## Cómo narrarlo (ejemplo ilustrativo, no reutilices las cifras)
Uplift: "La campaña subió la compra en promedio 1,8 puntos. Pero ese efecto no es parejo: el 30% que el modelo señala subió 5 puntos y el 30% de abajo no cambió. Si contactas solo a ese 30%, capturas más de la mitad del efecto con la tercera parte del costo. Dirigir por probabilidad de compra habría capturado menos, porque elige a quienes ya iban a comprar."
Diferencias en diferencias: "En las 12 tiendas con rediseño, las ventas subieron 4 unidades semanales más que en las 12 tiendas sin cambio, con rango de 2 a 6. Antes del rediseño ambos grupos evolucionaban igual, así que la diferencia se puede atribuir al rediseño con confianza media. Para confirmarlo con más fuerza, extiéndelo al azar a otras tiendas."
