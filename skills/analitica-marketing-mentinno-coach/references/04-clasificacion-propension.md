# Módulo 4: resultados sí o no (compra, abandono, respuesta)

## Cuándo usarlo
"¿Quién se va a ir?", "¿A quién le hablo para la oferta?", "¿Qué leads tienen más probabilidad de cerrar?"

## Regla de diseño
Un modelo por acción: compra, abandono, upsell, respuesta a un correo. Mezclarlos produce puntajes que nadie sabe leer. Define con precisión el resultado ("abandonó en los 90 días siguientes") antes de modelar.

## Qué método usa el script
- Base explicable: regresión logística, que dice qué factores aumentan o reducen la probabilidad.
- Comparación con un modelo más complejo (boosting). Solo se recomienda el complejo si mejora de forma relevante (2 puntos de AUC o más), porque a igual capacidad conviene el explicable.
- Partición por fecha cuando hay fecha, para probar con lo más reciente y evitar mirar el futuro.

## Cómo leer los resultados (en lenguaje de negocio)
- **Tabla por deciles:** si ordenas a tus clientes por puntaje, el 10% de arriba concentra X% de los casos reales. Es el resultado que mueve presupuesto.
- **Lift:** cuántas veces más casos que el promedio hay en ese grupo.
- **Calibración:** si el modelo dice 30%, ¿pasa cerca de 30%? Si no, sirve para ordenar pero no para leer el porcentaje.
- **Factores:** qué empuja la probabilidad hacia arriba o abajo, en frases ("cada ticket de soporte extra casi duplica el riesgo de baja").
- **Economía:** con valor por conversión y costo por contacto, el script indica a qué deciles conviene actuar.

## Alertas que el script lanza
- **Resultado demasiado perfecto:** AUC mayor a 0,95 o una variable que predice casi sola. Casi siempre es fuga de información: una columna que ya contiene la respuesta (por ejemplo, una marca de "canceló"). Se quita la variable y se repite.
- **Pocos casos:** menos de 10 casos del grupo menor por variable.
- **Mala calibración** o **capacidad de ordenar baja**.

## Cómo se decide el semáforo
- **Rojo:** posible fuga de información, o el modelo ordena apenas mejor que el azar (AUC menor a 0,60 o límite inferior del rango menor a 0,55).
- **Amarillo:** hay advertencias, o ordena de forma útil pero no concluyente.
- **Verde:** sin advertencias, con límite inferior del AUC de 0,70 o más y el 10% de arriba concentrando al menos 2 veces el promedio.
- **Tope amarillo con dinero en juego:** si el usuario da valor y costo por contacto, el máximo es amarillo, porque el modelo mide quién tiene más probabilidad, no a quién influye la acción. Pasa a verde de decisión solo con una prueba con grupo de control.
El resultado trae `motivo_semaforo` (una frase para dar al usuario) y `auc_rango_90`. Usa esa frase como el "por qué" del color.

## Límite importante: propensión no es efecto
Alta probabilidad de comprar no significa que tu acción la cause. Quien ya iba a comprar recibe descuento de más. Cuando haya presupuesto de por medio, recomienda una prueba con grupo de control: contactar a una parte y no a otra de los de mayor puntaje, y comparar. Esa es la base del uplift.

## Ética
No uses atributos sensibles para puntuar personas. Revisa que el modelo no perjudique a un grupo por variables que lo representan (por ejemplo, zona como sustituto de nivel de ingresos) cuando la decisión afecte acceso o precio.

## Mantenimiento
Un puntaje envejece: revisar la calibración cada trimestre y reentrenar cuando se desvíe.
