# Power BI — Pages

Estado general: **seis páginas finalizadas**.

Capturas definitivas:

```text
docs/assets/Pag1.png
docs/assets/Pag2.png
docs/assets/Pag3.png
docs/assets/Pag4.png
docs/assets/Pag5.png
docs/assets/Pag6.png
```

---

## 01 — Resumen Ejecutivo

### Pregunta principal

> **¿Cómo está funcionando BTYT?**

### KPIs

- Ingresos totales
- Resultado neto
- Costos / Ingresos
- Margen neto

### Visuales

- Evolución de Ingresos y Resultado Neto
- Composición de Costos Operativos
- Eficiencia y Rentabilidad por Año

### Filtros

- Tamaño de sucursal
- Región
- 1 año / 3 años / 5 años / Todos

### Estado

**Final.**

---

## 02 — Sucursales

### Pregunta principal

> **¿Dónde se genera o destruye valor dentro de la red?**

### KPIs

- Ingresos totales
- Resultado neto
- Costos operativos
- Costos / Ingresos

### Visuales

- Resultado Neto por Sucursal
- Ingresos vs Resultado Neto por Sucursal
- Rentabilidad de la Red

### Filtros

- Tamaño de sucursal
- Región
- 1 año / 3 años / 5 años / Todos

### Estado

**Final.**

---

## 03 — Clientes y Cuentas

### Pregunta principal

> **¿Cómo evoluciona la base de clientes y qué tan profunda es su relación con BTYT?**

### KPIs

- Promedio mensual de clientes activos
- Cuentas activas
- Depósitos promedio
- Préstamos promedio

### Filtros

- Residencia
- Tipo de cliente
- 1 año / 3 años / 5 años / Todos

### Semántica temporal

- **Clientes activos:** promedio mensual dentro del período visible.
- **Cuentas activas:** stock con regla temporal explícita; no se suma entre meses.
- **Depósitos promedio:** promedio mensual del stock agregado, convertido a USD por año.
- **Préstamos promedio:** promedio mensual del stock de deuda vigente, convertido a USD por año.
- **Volumen transaccionado:** flujo acumulado dentro del período visible, convertido a USD por año.

### Visuales

- Clientes Activos y Bajas de Clientes por Año
- Top 10 clientes dinámico por:
  - Depósitos
  - Deuda vigente
  - Volumen transaccionado
- Profundidad de Relación
- Análisis de Cartera

### Matriz de cartera

Filas:

```text
Depósitos
Deuda vigente
Volumen transaccionado
Transacciones
Cuentas activas
Préstamos activos
```

Columnas:

```text
Total
Promedio
Mediana
Desv. Est.
Coef. Var.
```

### Estado

**Final.**

---

## 04 — Riesgo de Crédito

### Pregunta principal

> **¿Cuánta exposición crediticia tiene BTYT, cuánto está en mora y dónde se concentra el riesgo?**

### KPIs

- Exposición crediticia
- Exposición 30+ DPD
- Exposición 90+ DPD
- Pagos incumplidos

### Visuales

- Evolución anual de Pagos incumplidos / 30+ DPD / 90+ DPD
- Riesgo y exposición por tipo de préstamo
- Exposición 30+ / 90+ DPD por segmento de cliente
- Exposición y mora por cohorte de originación

### Filtros

- Tipo de cliente
- Tipo de préstamo
- Estado del préstamo
- Moneda

### Helpers

- `DPD Exposure Selector`
- `DPD Rate Switch`

Cumplen funciones diferentes y se conservan por diseño.

### Estado

**Final.**

---

## 05 — Transacciones y Canales

### Pregunta principal

> **¿Cómo transaccionan los clientes, por qué canales y con qué nivel de fallas operativas?**

### KPIs

- Transacciones completadas
- Volumen transaccional
- Participación por canal
- Tasa de fallas

### Visuales

- Evolución de transacciones y volumen
- Distribución por canal
- Canal por tipo de transacción
- Tasa de fallas por canal

### Filtros

- 1 año / 3 años / 5 años / Todos
- Tipo de cliente
- Tipo de transacción
- Canal
- Moneda

### Fuente

La página consume una capa agregada de PostgreSQL / analytics; no importa por defecto la fact cruda de transacciones.

Escala canónica:

```text
74,774,125 transacciones totales
72,746,246 completadas
2,027,879 fallidas
```

### Estado

**Final.**

---

## 06 — Mercado y Campañas

### Pregunta principal

> **¿Cómo se posiciona BTYT en el mercado simulado y cómo responden sus campañas?**

### KPIs

- Participación de mercado BTYT
- Posición de BTYT
- Cobertura de campaña
- Respuesta positiva

### Visuales

- Ranking de participación de mercado
- Evolución de la participación de BTYT
- Cobertura vs respuesta positiva por campaña
- Respuesta positiva por producto objetivo

### Filtros

- Tipo de campaña
- Tipo de cliente
- Producto objetivo
- Tipo de banco

La página no usa selector temporal global porque sus dos fuentes tienen una semántica temporal/grano diferente y el diseño final no lo requiere.

### Estado

**Final.**

---

## Cierre visual

El reporte final mantiene:

- fondo oscuro/grafito;
- títulos y etiquetas visibles en español;
- DAX/objetos técnicos en inglés;
- paleta analítica azul/cian/violeta;
- branding BTYT usado de forma puntual;
- navegación y alineación consistentes entre las seis páginas.

No se requiere agregar nuevas páginas para cerrar el núcleo Power BI de Part I.
