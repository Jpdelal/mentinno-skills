# Módulo 5: mezcla de medios (MMM ligero)

## Cuándo usarlo
"¿Cuánto aporta cada canal?", "¿Dónde pongo el próximo peso?", "¿Estoy invirtiendo de más en algo?"

## Qué es en lenguaje simple
Se mira, semana a semana, cuánto se invirtió en cada canal y cuánto se vendió, descontando lo que habría vendido sin publicidad (base, tendencia, temporada, promociones). Se estima cuánto aporta cada canal, cuánto tarda en notarse su efecto y cuándo deja de rendir (saturación).

## Datos mínimos (la compuerta decide)
- Recomendable: 2 años semanales (104 semanas). Entre 52 y 103: orientativo. Menos de 52: no se hace.
- Inversión por canal y una cifra de resultado (ventas o conversiones) por periodo.
- Variación real de la inversión. Un canal que casi no cambia no se puede medir.
- Controles conocidos: promociones, precio, estacionalidad especial.
- Canales que se mueven casi igual no se pueden separar: se dice y se evita atribuir de más.

## Calibración con experimentos (lo que más sube la confianza)
Si hay resultados de pruebas con grupo de control o estudios de incrementalidad, se pasan con `--calibrar canal=retorno:error`. El modelo ajusta el retorno del canal hacia lo medido en el experimento. Sin calibración, la confianza máxima es amarilla. El resultado de una prueba se obtiene con `ab_test.py leer` (módulo 11), que entrega la línea `--calibrar` ya armada. En 16 bases simuladas, calibrar dos canales con experimentos de 15% de error bajó el error del retorno de 26% a 13% y dejó los rangos con 91% de cobertura. Los rangos de un canal calibrado incluyen el error del propio experimento. Si la persona no tiene experimentos, recomienda diseñar uno para el canal más grande o más dudoso (ver módulo 2).

## Qué entrega el script
Por canal: porcentaje de inversión frente a porcentaje de ventas aportadas, retorno medio, **retorno de la siguiente unidad invertida** (lo que decide la reasignación), saturación, cuánto dura el efecto y un rango por remuestreo. También: reasignación sugerida del mismo presupuesto con probabilidad de mejora, escenario de +10% de presupuesto, y semáforo.

## Cómo decidir con el resultado
- La reasignación se basa en el retorno de la siguiente unidad, no en el promedio. Un canal con buen promedio puede estar saturado.
- Mueve poco a poco: límite del 50% por canal por defecto, y siempre con una prueba de validación del cambio principal.
- Con semáforo rojo no se recomienda mover dinero. Con amarillo, se recomienda un movimiento acotado y una prueba.

## Lo que el rango cubre y lo que no
Los rangos (90%) incluyen el ruido de los datos y la incertidumbre sobre cuánto dura el efecto y dónde satura cada canal. En 16 bases simuladas con verdad conocida (`tests/bench_mmm.py`) contuvieron el valor real el 86% de las veces. No cubren que falte una variable importante (precio, competencia, distribución).
Cada canal trae `incertidumbre_retorno` (baja, media, alta). Si es alta, el rango es más ancho que la cifra: no recomiendes mover dinero desde o hacia ese canal sin una prueba con grupo de control. Suele ocurrir con canales de poca inversión (por ejemplo, email con 5% del gasto).
Para decisiones grandes: Meridian, Robyn o PyMC-Marketing con un especialista y datos calibrados.

## Errores comunes
- Atribuir ventas a un canal que solo se activa cuando ya se vende más (la inversión sigue a la demanda).
- Ignorar el efecto acumulado: TV y redes siguen vendiendo semanas después.
- Presentar el resultado como causa sin calibración.

## Cómo narrarlo (ejemplo ilustrativo, no reutilices las cifras)
"Tres cuartas partes de tu inversión está en TV y búsqueda, que aportan 30% de las ventas. Email recibe 5% y es el canal que más rinde por peso adicional. Mover 15% del presupuesto de redes a email y TV sumaría entre 1% y 3% de ventas. Antes de moverlo todo, validemos con una prueba de 6 semanas."
