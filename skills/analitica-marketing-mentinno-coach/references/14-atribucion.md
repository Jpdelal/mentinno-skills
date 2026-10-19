# Módulo 14: atribución multitoque

## Cuándo usarlo
"¿Qué canal merece el crédito de las ventas?", "¿Por qué Google dice una cosa y Meta otra?", "¿El último clic me engaña?", "¿Qué canal ayuda a vender aunque no cierre?"
Sirve para **entender recorridos y decidir qué probar**. No sirve para mover presupuesto grande por sí solo: repartir crédito no es medir efecto.

## Cuándo no usarlo
- Si la pregunta es "¿cuánto vendí de más gracias a este canal?", usa una prueba de incrementalidad (módulo 11), uplift o diferencias en diferencias (módulo 12) o la mezcla de medios (módulo 5).
- Con menos de 100 conversiones el script se niega: el reparto sería ruido.
- Si casi todas las conversiones tienen un solo contacto, las reglas dan casi lo mismo y el módulo aporta poco. El script lo avisa.

## Qué es en lenguaje simple
Cada persona deja un recorrido de contactos (anuncio, correo, búsqueda, tienda) antes de comprar o no comprar. La atribución reparte la compra entre esos contactos. Hay varias formas de repartir y ninguna es la verdad; por eso el script las pone lado a lado.

## Datos mínimos
- Una fila por contacto: persona, fecha, canal, y una columna que vale 1 si esa persona terminó comprando (la misma en todas sus filas).
- Incluir también a las personas que **no compraron**. Sin ellas no hay manera de saber qué canal se asocia con comprar.
- Al menos 100 conversiones y 200 personas alcanzadas por canal. Más de 8 canales se agrupan en "otros".
- Si hay valor de la compra, se reparte también el valor con las reglas.

## Lo que hace `attribution.py`
1. **Cinco reglas:** último clic, primer clic, lineal, decaimiento en el tiempo (`--vida-media`, 7 días por defecto) y por posición (40% primero, 40% último, 20% el medio).
2. **Cadena de Markov:** cuánto cae la probabilidad de comprar si se quita un canal del recorrido.
3. **Modelo de exposición:** una regresión con todas las personas, también las que no compraron, y un reparto exacto tipo Shapley del efecto de cada canal dentro de cada combinación de contactos. Aprende de quién tocó qué canal y compró o no.
4. Rango 90% por remuestreo en cada método y la mínima y máxima entre métodos.
5. Señales: canales de cierre, canales con desacuerdo entre métodos, y qué parte habría ocurrido sin ningún canal (solo si hay personas sin contacto en la base).

## Cómo leer el resultado
- **Tabla por canal con siete columnas de porcentaje.** Mira el rango entre métodos, no un solo número. Si un canal pasa de 10% a 40% según el método, su crédito depende del método.
- **Canal de cierre:** aparece al final en 60% o más de sus contactos en recorridos de 2 o más contactos. Es el patrón típico de retargeting y de búsqueda de marca: cobra ventas que ya iban a ocurrir. Pide una prueba de incrementalidad antes de darle más presupuesto.
- **Primer clic alto y último clic bajo:** canal que abre la conversación (descubrimiento). Suele subestimarse con último clic.
- **Desacuerdo de más de 15 puntos entre métodos:** el dato no decide, el método sí. Dilo.
- **Rango 90%:** si dos canales se solapan, no se pueden ordenar.

## Semáforo
Siempre **amarillo** como máximo. La atribución nunca da verde porque no es causal: con datos observacionales el modelo no puede separar "este canal causó la compra" de "este canal se mostró a quien ya iba a comprar". Rojo no se usa: el script se detiene con un mensaje cuando los datos no alcanzan.

## Límites que siempre dices
- **Repartir crédito no es medir efecto.** El retargeting es el caso claro: si solo se muestra a quien ya está por comprar, todos los métodos, incluido el modelo de exposición, le darán mucho crédito. En la prueba, el canal de retargeting sin efecto causal recibió el 70% o más de crédito con el modelo de exposición, y solo la señal de canal de cierre lo delata.
- Un canal sin efecto real puede recibir hasta unos 5 puntos de crédito por ruido de estimación, sobre todo si casi siempre aparece solo.
- Si no hay personas sin ningún contacto en los datos (lo habitual cuando solo hay registro de contactos), no se puede estimar qué parte habría ocurrido sin canal y el crédito se reparte entre los canales. El modelo de exposición deja sin asignar las conversiones de combinaciones cuyo efecto estimado es cero, por eso su suma puede ser algo menor que 100%.
- Los contactos que no se registran (voz a voz, televisión, tienda) no entran. Su crédito se reparte entre los canales que sí se ven.
- Cookies, dispositivos y consentimiento: una misma persona con dos dispositivos aparece como dos. El recorrido real es más largo que el observado.

## Errores comunes
- Elegir un método y presentarlo como "el" crédito de cada canal.
- Mover presupuesto grande por la atribución sin una prueba.
- Medir con último clic y concluir que el canal de descubrimiento no sirve.
- No incluir a las personas que no compraron.
- Comparar porcentajes de atribución con los que reporta cada plataforma: cada una usa su propia regla y se atribuye todo lo que toca.

## Cómo narrarlo (ejemplo ilustrativo, no reutilices las cifras)
"Con último clic, la búsqueda de marca se lleva 45% de las ventas. Con el modelo de exposición baja a 22% y con primer clic a 8%. Aparece casi siempre al final del recorrido, que es lo que hace un canal que cobra ventas que otro empezó. No muevas presupuesto con esto. Lo que sí vale la pena: una prueba de 4 semanas apagando la búsqueda de marca en dos regiones, que es lo que mide cuánto de ese crédito era real."
