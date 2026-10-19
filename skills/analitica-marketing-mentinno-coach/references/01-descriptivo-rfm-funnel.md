# Módulo 1: descriptivo, valor de clientes (RFM) y embudo

## Cuándo usarlo
La persona quiere saber qué pasó, quién vale más, a quién cuidar o reactivar, o dónde se pierde la conversión.

## Descriptivo: lo mínimo que siempre se mira
- Total y evolución en el tiempo (por semana o mes), con comparación contra el periodo anterior y el mismo periodo del año anterior.
- Concentración: qué porcentaje de ventas viene del 20% de clientes o productos.
- Cortes que cambian decisiones: canal, producto, ciudad, tipo de cliente.
- Antes de interpretar una caída o subida, revisa temporada, promociones y cambios en la mezcla de público.
- Regla: una cifra sin comparación no se presenta.

## RFM (script `rfm_funnel.py rfm`)
**Qué es en lenguaje simple:** ordenar a los clientes por qué tan recientemente compraron, qué tan seguido y cuánto gastan, para decidir un trato distinto a cada grupo.

**Datos mínimos:** una fila por compra con cliente, fecha y monto. El pedido es opcional pero mejora la frecuencia.

**Decisiones de método (ya implementadas):**
- Con 1000 clientes o más usa 5 niveles; con menos, 3, para que los cortes no cambien por azar.
- La frecuencia tiene muchos empates (todos los que compraron una vez). El script no los separa arbitrariamente.
- Se excluyen montos en cero o negativos (devoluciones) y se informa cuántos fueron.

**Segmentos y qué hacer:** Campeones, Leales, Nuevos o prometedores, En riesgo valiosos, Necesitan atención, Dormidos. El script entrega la acción por segmento. La prioridad casi siempre es En riesgo valiosos, porque es dinero que se está yendo y aún se puede recuperar.

**Insights que suele revelar:**
- Concentración de ingresos (por ejemplo, 20% de clientes, 69% de ingresos).
- Porcentaje de clientes que compró una sola vez: el mayor espacio de crecimiento.
- Ventana de recompra: cada cuántos días vuelve quien repite. Quien supera el doble ya probablemente se perdió, y eso define cuándo lanzar la reactivación.

**Errores comunes:** copiar benchmarks de otra industria; tratar los segmentos como permanentes (hay que recalcular cada mes o trimestre); ofrecer descuentos a Campeones que comprarían igual.

**Extensión opcional:** valor de vida del cliente (CLV). RFM dice a quién contactar esta semana; CLV dice cuánto vale la relación y cuánto conviene invertir. Si la persona lo pide, estímalo de forma simple (margen por compra, frecuencia anual, años de vida esperados) y marca que es una estimación.

## Embudo (script `rfm_funnel.py embudo`)
**Qué es:** ver cuántas personas pasan de una etapa a la siguiente (visita, carrito, pago, compra) y dónde se pierden.

**Datos mínimos:** una columna de conteo por etapa, por fila de periodo o segmento. Opcionales: segmento (dispositivo, canal) y periodo.

**Lo que calcula:** conversión por paso con rango, dónde se pierde más gente en número y en proporción, brechas entre segmentos, impacto de mejorar el paso más débil y revisión de la paradoja de Simpson.

**Cuidado al interpretar:** el paso más bajo en proporción casi siempre es el de arriba del embudo (visita a carrito). No significa que sea el mejor lugar para actuar. Cruza con el costo y la facilidad de mejorar cada paso, y con la brecha entre segmentos.

**Paradoja de Simpson:** si la conversión total sube pero baja dentro de cada segmento, el cambio viene de la mezcla de tráfico (más gente de un segmento que convierte mejor), no de una mejora real. Siempre comparar dentro de cada segmento.

**Benchmarks:** no impongas tasas "típicas". Pide el histórico propio de la persona. Si usas un dato externo, cita fuente y fecha y di que es orientativo.

## Cómo narrarlo (ejemplo ilustrativo, no reutilices las cifras)
"Tu 20% de mejores clientes genera casi 70% de las ventas, y 444 de ellos llevan meses sin comprar. Recuperar a un tercio equivale a X en ingresos. Empieza por ahí."
