# Power BI — Pages

Estado general: **siete páginas finalizadas**. La primera es un resumen ejecutivo de cierre de año; las otras seis son páginas de análisis por área.

Capturas definitivas:

```text
docs/assets/Pag1.png   Resumen ejecutivo
docs/assets/Pag2.png   Rentabilidad y costos
docs/assets/Pag3.png   Sucursales
docs/assets/Pag4.png   Clientes y Cuentas
docs/assets/Pag5.png   Riesgo de Crédito
docs/assets/Pag6.png   Transacciones y Canales
docs/assets/Pag7.png   Mercado y Campañas
```

Todas las páginas comparten la misma grilla:
- arriba, cuatro indicadores a la izquierda, los filtros al centro y el selector de año a la derecha;
- abajo, cuatro paneles (o un panel alto y dos chicos).

---

## 01 — Resumen ejecutivo

### Pregunta principal

> **¿Cómo cerró BTYT el año y qué lo explica?**

### Contenido

- **Titular automático** en dos líneas: ingresos y resultado neto contra el año anterior; pérdida de crédito, mes pico y cuota de mercado.
- **Seis indicadores**: ingresos, resultado neto, costos / ingresos, margen neto, pérdida de crédito y cuota de mercado. Cada uno muestra el valor, la variación interanual (verde si mejora, rojo si empeora) y la tendencia de seis años.
- **Qué movió el resultado neto**: puente del año anterior al actual, con cada partida a tipo de cambio del año anterior y el efecto cambiario aparte. El subtítulo lista todas las variaciones.
- **Resultado neto y pérdida de crédito por mes**: en rojo, los meses con pérdida mayor al doble de la mediana de los 12 meses previos.
- **Cuota de mercado de BTYT** y **nota sobre los datos** (aviso automático sobre el último mes observado).

### Filtros

- Año analizado: abre en 2026. No filtra las tendencias.

Detalle técnico: [04_resumen_ejecutivo.md](04_resumen_ejecutivo.md).

---

## 02 — Rentabilidad y costos

### Pregunta principal

> **¿Cómo evolucionan los ingresos, los costos y la rentabilidad del banco?**

### KPIs

- Ingresos totales
- Resultado neto
- Costos / Ingresos
- Margen neto

### Visuales

- Evolución de ingresos y resultado neto (mensual, con línea de cero)
- Composición de costos operativos (personal, operativos, variables, fijos)
- Eficiencia y rentabilidad por año (costos / ingresos y margen neto en un mismo eje)

### Filtros

- Tamaño de sucursal
- Región
- Año

---

## 03 — Sucursales

### Pregunta principal

> **¿Dónde se genera o destruye valor dentro de la red?**

### KPIs

- Ingresos totales
- Resultado neto
- Costos operativos
- Costos / Ingresos

### Visuales

- Resultado neto por sucursal: ranking con las sucursales deficitarias en rojo.
- Ingresos vs. resultado neto por sucursal, por región.
- Rentabilidad de la red: proporción de sucursales rentables.

### Filtros

- Tamaño de sucursal
- Región
- Año

---

## 04 — Clientes y Cuentas

### Pregunta principal

> **¿Cómo evoluciona la base de clientes y qué tan profunda es su relación con BTYT?**

### KPIs

- Promedio mensual de clientes activos
- Cuentas activas
- Depósitos promedio
- Préstamos promedio

### Semántica temporal

- **Clientes activos:** promedio mensual dentro del período visible.
- **Cuentas activas:** saldo con regla temporal explícita; no se suma entre meses.
- **Depósitos promedio:** promedio mensual del saldo agregado, convertido a USD por año.
- **Préstamos promedio:** promedio mensual de la deuda vigente, convertido a USD por año.
- **Volumen transaccionado:** flujo acumulado dentro del período visible, convertido a USD por año.

### Visuales

- **Clientes activos y bajas por año**, separados en empresas y personas.
- **Top 10 clientes dinámico** por depósitos, deuda vigente o volumen transaccionado, según el selector de la esquina. Las empresas aparecen con su razón social y las personas como "Cliente + ID".
- **Profundidad de la relación:** básica, vinculada, profunda e integral.
- **Análisis de cartera:** total, promedio, mediana, desvío estándar y coeficiente de variación por cliente para depósitos, deuda vigente, volumen transaccionado, transacciones, cuentas activas y préstamos activos.

### Filtros

- Residencia
- Tipo de cliente
- Año

---

## 05 — Riesgo de Crédito

### Pregunta principal

> **¿Cuánta exposición crediticia tiene BTYT, cuánto está en mora y dónde se concentra el riesgo?**

### KPIs

- Exposición crediticia
- Exposición 30+ DPD
- Exposición 90+ DPD
- Pagos incumplidos

### Visuales

- Pagos incumplidos, 30+ DPD y 90+ DPD por año, las tres tasas en un mismo eje.
- Riesgo y exposición por tipo de préstamo: mora 90+ contra exposición, con el tamaño según los pagos incumplidos.
- Exposición 30+ o 90+ DPD por segmento de cliente, con botones 30+ / 90+ (`DPD Exposure Selector`).
- Exposición y mora por cohorte de originación, con botones 30+ / 90+ (`DPD Rate Switch`).

### Filtros

- Tipo de cliente
- Tipo de préstamo
- Estado del préstamo
- Moneda

---

## 06 — Transacciones y Canales

### Pregunta principal

> **¿Cómo transaccionan los clientes, por qué canales y con qué nivel de fallas operativas?**

### KPIs

- Transacciones completadas
- Volumen transaccional
- Participación digital (móvil + web)
- Tasa de fallas

### Visuales

- Evolución de transacciones y volumen.
- Distribución de transacciones por canal.
- Distribución de canales por tipo de transacción.
- Tasa de fallas por canal.

Cada canal tiene un color fijo en toda la página: Móvil azul, Web gris, Sucursal dorado, POS verde, Cajero automático violeta, Automático coral.

### Filtros

- Tipo de cliente
- Transacción
- Canal
- Moneda
- Año

### Fuente

La página usa una capa agregada de PostgreSQL; no importa la tabla de hechos de transacciones individuales.

```text
74,774,125 transacciones totales
72,746,246 completadas
 2,027,879 fallidas
```

---

## 07 — Mercado y Campañas

### Pregunta principal

> **¿Cómo se posiciona BTYT en el mercado simulado y cómo responden sus campañas?**

### KPIs

- Cuota de mercado
- Posición de BTYT
- Cobertura de campaña
- Respuesta positiva

### Visuales

- Participación de mercado por banco: BTYT resaltado en azul y el resto en gris.
- Evolución de la participación de mercado de BTYT.
- Cobertura y respuesta de las campañas, con el tamaño según los clientes expuestos.
- Respuesta positiva por producto objetivo.

### Filtros

- Tipo de campaña
- Tipo de cliente
- Producto objetivo
- Tipo de banco

La página no tiene selector de año: el mercado es anual y las campañas tienen fechas propias.

---

## Criterios visuales

- Tema **BTYT Oscuro** (`powerbi/themes/BTYT_Oscuro.json`), con Segoe UI y una escala de tamaños única.
- **Colores con significado:**
  - azul: BTYT o valores normales;
  - gris: contexto;
  - verde y rojo: solo para mejora o empeoramiento.
- Títulos en español y con mayúscula solo al inicio; DAX y objetos técnicos en inglés.
- Gráficos de torta o dona solo para partes de un todo con pocas categorías.
