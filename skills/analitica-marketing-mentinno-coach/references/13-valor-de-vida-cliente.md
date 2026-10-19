# Módulo 13: valor de vida del cliente

## Cuándo usarlo
"¿Cuánto vale un cliente?", "¿Cuánto puedo gastar en conseguir uno?", "¿Qué clientes valen más hacia adelante, no solo hacia atrás?", "¿Cuánto vale mi base de clientes?", "¿Mis clientes nuevos valen menos que los de antes?"
Es la continuación natural de RFM (módulo 1): RFM mira lo que el cliente hizo; este módulo estima lo que **se espera que haga** en los próximos meses.

## Cuándo no usarlo
El método es para negocios donde el cliente compra cuando quiere (comercio, retail, e-commerce, servicios por evento). **No es para suscripciones ni compras programadas**, donde el cliente se va en un momento claro. El script detecta intervalos muy regulares y lo advierte. En esos casos usa la tabla de cohortes (ingreso acumulado por cliente según el mes en que llegó) y la retención por mes.

## Qué es en lenguaje simple
Dos preguntas por cliente. Primera: ¿cuántas compras se esperan y qué tan probable es que siga activo? Se responde con su historial y con lo que se parece a otros clientes (compró 3 veces en 8 meses, la última hace 5 semanas). Segunda: ¿cuánto suele gastar por compra? Se responde con su gasto y con el promedio general, dando más peso al cliente cuantas más compras repetidas tiene. El valor de vida es compras esperadas por monto esperado, con descuento para traer el dinero futuro a valor presente.

## Datos mínimos
- Una fila por compra con cliente, fecha y monto.
- Al menos 12 meses de historia para probar el modelo, y más cuanto mayor sea el horizonte. Con menos de 12 meses la proyección es orientativa.
- Al menos 300 clientes para que el modelo se pueda probar con datos nuevos, y 50 con compras repetidas para estimar el monto.
- El monto debe estar limpio: sin devoluciones (el script las excluye) y sin cargos que no son compras.

## Lo que hace `clv.py`
1. Resume a cada cliente: compras repetidas, tiempo entre la primera y la última compra, antigüedad y monto medio de sus compras repetidas.
2. Estima el modelo de compras (BG/NBD) y el de monto por compra (Gamma-Gamma).
3. **Se prueba con datos nuevos:** reserva los últimos 6 meses (`--validacion`), estima con lo anterior y compara lo que predijo con lo que realmente pasó, en total y por grupo de frecuencia.
4. Calcula, por cliente, probabilidad de seguir activo, compras esperadas, valor por compra, y valor de vida a `--horizonte` meses con `--descuento` anual y `--margen`.
5. Entrega la tabla de cohortes y señales: concentración del valor, clientes que compraron una vez y clientes valiosos que ya probablemente se fueron.

## Parámetros que decide la persona
- **Margen:** el valor de vida en ventas no es el valor de vida en ganancia. Si el margen es 30%, pasa `--margen 0.3` y presenta la cifra en ganancia. Pregunta por el margen antes de comparar el valor de vida con el costo de adquirir un cliente.
- **Horizonte:** 12 meses es lo habitual. El modelo se prueba a 6 meses, así que a más de 12 es extrapolar y el script lo marca.
- **Descuento:** 10% anual por defecto. Cambia poco el resultado a 12 meses.

## Cómo leer el resultado
- **Valor esperado total de la base:** lo que se espera que la base actual aporte en el horizonte, sin contar clientes nuevos.
- **Concentración:** "el 10% de arriba concentra 52% del valor futuro" decide dónde poner atención.
- **Clientes valiosos en riesgo:** alto gasto histórico y baja probabilidad de seguir activos. Es la lista de reactivación con más retorno.
- **Prueba con datos nuevos:** el error en compras e ingresos de los meses reservados. Es el dato que da o quita confianza.
- **Cohortes:** si el ingreso por cliente a 6 y 12 meses de las cohortes recientes es menor que el de las antiguas, el negocio está atrayendo clientes que valen menos aunque la cantidad suba.

## Semáforo
- **Verde:** error menor a 10% en compras y 15% en ingresos sobre los meses reservados, y sin advertencias.
- **Amarillo:** no se pudo probar con datos nuevos, error intermedio, o advertencias (suscripción, monto ligado a la frecuencia, pocos clientes, horizonte demasiado largo).
- **Rojo:** error mayor a 25% en compras o 30% en ingresos. Suele ocurrir tras un cambio fuerte de demanda (una promoción, un cambio de precio, una pandemia).

## Límites que siempre dices
- El valor de vida es una estimación con rango, no una cifra contable. Prefiere hablar de "unos 140, probablemente entre 120 y 165" o del orden de magnitud.
- Supone que el comportamiento del pasado reciente se mantiene. Un cambio de precio, de mix o de competencia lo invalida.
- Un cliente con una sola compra se considera activo con certeza (es un rasgo del modelo): no uses la probabilidad de seguir activo de quien compró una vez para decir que "sigue activo". Úsala en quienes ya repitieron.
- El modelo de monto supone que quien compra más veces no gasta sistemáticamente más o menos por compra. Si no se cumple, el script lo avisa.

## Errores comunes
- Dividir el ingreso total entre clientes y llamar a eso valor de vida: promedia a los que se fueron con los que siguen.
- Comparar el valor de vida en ventas con el costo de adquisición, sin margen.
- Aplicarlo a una suscripción.
- Proyectar a 5 años con 15 meses de datos.
- Usar el valor de vida para negar atención a clientes de bajo valor sin considerar que algunos de ellos son nuevos y aún no se sabe.

## Cómo narrarlo (ejemplo ilustrativo, no reutilices las cifras)
"Tu base actual de 4.000 clientes debería aportar unos 430.000 en los próximos 12 meses, con un error probable de 3% a 10% según lo que el modelo predijo con los últimos 6 meses. El 10% de clientes con más valor concentra más de la mitad. Hay 56 clientes de alto gasto con menos de 30% de probabilidad de seguir activos: es la lista que reactivaría primero. Cuidado: los clientes que llegaron en los últimos 6 meses valen menos en sus primeros 3 meses que los de hace un año, así que conviene revisar de dónde vienen."
