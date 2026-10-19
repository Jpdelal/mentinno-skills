# Módulo 11: pruebas A/B e incrementalidad

## Cuándo usarlo
"¿Funciona esta versión de la página?", "¿Cuántas personas necesito para probar esto?", "¿La campaña vendió algo que no habría vendido igual?", "Tengo el resultado de una prueba con grupo sin campaña".
Es el peldaño 4 de la escalera de evidencia (módulo 2): la única forma de usar la palabra "causa" con tranquilidad. También es lo que calibra la mezcla de medios (módulo 5).

## Qué es en lenguaje simple
Se divide al azar a la audiencia en dos grupos parecidos. A uno se le aplica la acción y al otro no. Como el azar los hizo iguales, la diferencia entre ambos es lo que la acción causó. Incrementalidad es esa diferencia: las ventas que ocurrieron gracias a la campaña y no habrían ocurrido sin ella.

## Dos usos del script `ab_test.py`
1. **Antes de lanzar (`tamano`):** cuántas personas por grupo y cuántos días hacen falta para detectar una mejora mínima. Datos que pides: tasa actual, mejora relativa mínima que importaría al negocio y tráfico diario. Si no sabes la tasa actual, saca la del último trimestre.
2. **Después (`leer`):** efecto con rango, efecto relativo, desbalance de grupos, retorno incremental y la línea lista para calibrar la mezcla de medios.

## Reglas de diseño que siempre recuerdas
- **Una sola cifra a medir y una fecha de cierre, definidas antes.** Mirar cada día y parar cuando "ya se ve bien" produce falsos ganadores: en pruebas simuladas, mirar 5 veces sube los falsos positivos de 5% a 15%. Si la persona necesita mirar, usa `--revisiones N` y se exige más evidencia.
- **Reparto al azar.** Si el grupo con campaña se eligió "porque eran los mejores clientes", no es una prueba.
- **Duración en semanas completas.** El comportamiento cambia por día de la semana.
- **No cambiar nada más durante la prueba** (precio, promociones, otras campañas).
- **Contaminación.** Si el grupo de control ve la campaña por otro canal, el efecto se subestima. Si la prueba es por zonas, cuida que la gente no se mueva entre ellas.
- **El efecto mínimo importa.** Detectar mejoras de 2% exige muchísima gente. Pregunta qué mejora justificaría el costo y diseña para esa.

## Cómo leer el resultado (en lenguaje de negocio)
- **Efecto con rango:** "La campaña subió la compra de 4,0% a 4,6%, con un rango de 3 a 9 décimas de punto". El rango, no la cifra puntual, es lo que decide.
- **Prueba no concluyente:** que el rango incluya cero no significa "no funciona". Significa que con esta muestra no se podía ver. El script dice qué efecto mínimo se podía detectar.
- **Desbalance de grupos:** si pediste 50/50 y salió 30/70, algo falló en la asignación o en el registro. No interpretes el efecto hasta resolverlo. Con pocas personas, un desbalance pequeño (por ejemplo 52/48 con 10.000) puede pasar sin alarma: revisa la fuente si hay dudas.
- **Retorno incremental:** con gasto y valor por conversión, el script calcula cuánto se vendió de más por cada peso invertido, con su rango. Es la cifra que corrige la atribución inflada de los canales.

## Calibrar la mezcla de medios con el resultado
Si la prueba es concluyente y confiable, el script entrega `--calibrar canal=retorno:error`. Pásalo a `mmm_lite.py` (módulo 5). Eso ancla la estimación del canal a un experimento y es lo que permite subir el semáforo de la mezcla de medios. Si la prueba no es concluyente, no calibres con ella: el script lo advierte.

## Semáforo
- **Verde:** rango del efecto sin cero, grupos con el reparto planeado y al menos 50 casos con resultado en el grupo menor.
- **Amarillo:** no concluyente, o efecto claro con pocos casos.
- **Rojo:** desbalance de grupos o casi ningún caso con resultado.

## Errores comunes
- Parar la prueba al primer día "ganador".
- Medir muchas cifras y celebrar la que salió bien (si mides 20 cifras, una sale significativa por azar).
- Comparar a quienes abrieron el correo con quienes no: es una selección, no un experimento.
- Declarar "no funciona" cuando la prueba no tenía gente suficiente para verlo.
- Usar el resultado de una prueba de hace dos años: cambió el mercado, cambió el efecto.

## Cuando no se puede aleatorizar
Si no hay forma de formar un grupo de control al azar (una campaña de TV nacional, un cambio de precio ya hecho), usa el módulo 12 (diferencias en diferencias con zonas o periodos de comparación). La evidencia es más débil y el script lo marca.

## Cómo narrarlo (ejemplo ilustrativo, no reutilices las cifras)
"Con 18.000 personas por grupo podías detectar mejoras de 15% o más sobre tu tasa actual de 4%. La campaña subió la compra de 4,0% a 4,6%, con un rango de 3 a 9 décimas, así que la mejora es real aunque su tamaño exacto tiene margen. Cada peso invertido trajo unos 0,36 pesos de ventas adicionales, no los 2,10 que atribuía la plataforma. Antes de repetir el gasto, evalúa si ese retorno incremental cubre tu margen."
