# Ejemplos de práctica

Estos ejemplos usan las bases que genera `demo_data.py`, que incluyen la respuesta correcta en `verdad.json`. Los resultados abajo son los obtenidos al correr los comandos con la versión 1.0.0.

## Preparación

```bash
cd skills/analitica-marketing-mentinno-coach
pip install -r requirements.txt
python3 scripts/demo_data.py datos_demo
```

## 1. Prueba A/B (módulo 11)

```bash
python3 scripts/ab_test.py leer datos_demo/ab_prueba.csv --grupo grupo --resultado compro --control control
```

Resultado: efecto de +1,04 puntos sobre la compra, valor p de 0,000006, semáforo verde. El efecto simulado fue +1,00.

Antes de la prueba, para saber cuánta gente se necesita y cuántos días:

```bash
python3 scripts/ab_test.py tamano --base 0.05 --mejora 0.10 --trafico 2000
```

Resultado: para detectar una mejora de 5,0% a 5,5% se necesitan 31.234 personas por grupo y 32 días, redondeados a 35 para cubrir semanas completas.

## 2. Uplift (módulo 12)

```bash
python3 scripts/uplift_did.py uplift datos_demo/uplift_campana.csv --tratamiento grupo --y compro --x sensibilidad_precio,compras_previas,antiguedad,visitas --control control --valor 100 --costo 8
```

Resultado: efecto promedio de +6,3 puntos. El 30% que el modelo señala responde 12,2 puntos más que el 30% que menos responde (rango 8,7 a 15,0, medido fuera de muestra). Semáforo verde.

## 3. Diferencias en diferencias (módulo 12)

```bash
python3 scripts/uplift_did.py did datos_demo/tiendas_panel.csv --unidad tienda --periodo semana --grupo grupo --resultado ventas --fecha-intervencion 20 --control sin_cambio
```

Resultado: las tiendas con rediseño vendieron 5,48 unidades semanales más que las de comparación (rango 4,57 a 6,38). El efecto simulado fue 5,0. Los grupos iban en paralelo antes de la acción. Semáforo verde.

## 4. Valor de vida del cliente (módulo 13)

```bash
python3 scripts/clv.py datos_demo/transacciones.csv --cliente id_cliente --fecha fecha --monto monto
```

Resultado: la base de 4.000 clientes debería aportar unos 426.000 en 12 meses. El 10% de arriba concentra 52% del valor. Hay 56 clientes de alto gasto con baja probabilidad de seguir activos.

## 5. Mezcla de medios (módulo 5)

```bash
python3 scripts/mmm_lite.py datos_demo/mmm_semanal.csv --fecha semana --y ventas --canales gasto_tv,gasto_busqueda,gasto_redes,gasto_email --controles promocion
```

Resultado: la televisión aporta 18,4% de las ventas (simulado: 17,8%), con retorno de 7,3 por unidad invertida (simulado: 7,0). El email tiene un rango de retorno de 10,7 a 52,9: el skill advierte que es muy incierto y no recomienda mover dinero a ese canal sin una prueba. Semáforo amarillo, porque no hay experimentos de referencia.

## 6. Atribución (módulo 14)

```bash
python3 scripts/attribution.py datos_demo/toques_atribucion.csv --usuario persona --fecha fecha --canal canal --convirtio compro
```

Resultado: con último clic, búsqueda se lleva 45% del crédito y email 10%. El modelo de exposición da a email 0%. En la simulación, email no tiene ningún efecto real. Semáforo amarillo.

## 7. Propensión (módulo 4)

```bash
python3 scripts/classify.py datos_demo/bajas_clientes.csv --y baja --x antiguedad_meses,tickets_soporte,uso_mensual,plan,recibio_descuento
```

Resultado: AUC de 0,75 (rango 0,72 a 0,77). El 10% de arriba concentra 2,8 veces el promedio de bajas. Semáforo verde.

## Comparar con la verdad

`datos_demo/verdad.json` guarda los valores reales con que se generó cada base. Compara lo que estima el skill con ese archivo para entender qué tan cerca queda y cuándo el rango incluye la verdad.
