# Power BI — Pages

## 01 — Resumen Ejecutivo

### Pregunta principal

> **¿Cómo está funcionando BTYT?**

### KPIs

- Ingresos Totales
- Resultado Neto
- Costos Operativos / Cost-to-Income según versión visual
- Margen Neto

### Visuales

- Evolución de Ingresos y Resultado Neto
- Composición de Costos Operativos
- Eficiencia y Rentabilidad por Año

### Filtros

Selector anual 2021–2026.

### Estado

**Funcionalmente cerrada.**

El pulido visual final queda para el cierre de todas las páginas.

---

## 02 — Sucursales

### Pregunta principal

> **¿Dónde se genera o destruye valor dentro de la red?**

### KPIs

- Ingresos
- Resultado Neto
- Costos Operativos
- Cost-to-Income

### Visuales

- Ranking de resultado neto por sucursal
- Ingresos vs Resultado Neto por sucursal / región
- Rentabilidad de la red:
  - rentables;
  - deficitarias;
  - proporción rentable.

### Estado

**Funcionalmente cerrada.**

---

## 03 — Clientes y Cuentas

### Pregunta principal

> **¿Cómo crece la base de clientes de BTYT y qué tan profunda es la relación con el banco, diferenciando Personas y Empresas?**

### KPIs

- Clientes Activos
- Cuentas Activas
- Depósitos promedio
- Préstamos promedio

### Filtros

#### Residencia

Dropdown compacto.

Los casos sin residencia uruguaya visible se presentan como:

```text
Extranjeros
```

#### Tipo de cliente

Etiquetas visibles:

```text
Personas
Empresas
```

#### Analysis Window

```text
1M
3M
6M
12M
All
```

### Semántica temporal

#### Clientes activos

Clientes distintos activos al menos una vez dentro de la ventana.

#### Cuentas activas

Cuentas distintas activas al menos una vez dentro de la ventana.

#### Depósitos promedio

Promedio mensual del stock agregado de depósitos dentro de la ventana.

#### Préstamos promedio

Promedio mensual del stock agregado de deuda vigente dentro de la ventana.

Por tanto:

```text
1M  → snapshot mensual
All → promedio mensual histórico
```

### Visuales

- Clientes Activos y Bajas de Clientes por Año
- Top 10 clientes dinámico por:
  - Depósitos
  - Deuda vigente
  - Volumen transaccionado
- Profundidad de Relación:
  - Básica
  - Vinculada
  - Profunda
  - Integral
- Matriz de Análisis de Cartera

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

**Funcionalmente cerrada.**

---

## 04 — Riesgo de Crédito

### Pregunta principal

> **¿Cuánta exposición crediticia tiene BTYT, cuánto está en mora y qué tan severo es ese riesgo?**

### KPIs actuales

```text
Exposición crediticia
Exposición 90+ DPD
Cartera reestructurada
Pérdida crediticia / cartera
```

### Estado actual observado

```text
Exposición crediticia          ≈ US$4.338B
Exposición 90+ DPD              5.16%
Cartera reestructurada          0.64%
Pérdida crediticia / cartera    0.63%
```

### Decisión sobre 30+ DPD

El 30+ DPD sigue siendo una métrica analítica válida, pero no se usa como KPI principal en la fila superior.

La página prioriza 90+ DPD como señal de severidad y cartera reestructurada como estado contractual relevante.

### Fuente

- `Credit Risk`
- `Bank Performance`
- `DimDate`
- `Customer Accounts` para contexto de cliente

### Próximo paso

Construir 3–4 visuales útiles sin sobrecargar la página.

La prioridad es terminar funcionalmente la página antes de entrar en pulido visual.

---

## 05 — Transacciones y Canales

### Estado

**Pendiente.**

La capa SQL/materializada ya reduce el volumen de la fact cruda para evitar importar por defecto los ~76.8M eventos a Power BI.

---

## 06 — Mercado y Campañas

### Estado

**Pendiente.**

`Market Performance` y `Campaign Performance` permanecen desconectadas intencionalmente cuando su grano no justifica una relación física con el resto del modelo.

---

## Cierre visual

Una vez finalizadas las seis páginas:

- unificar tema;
- revisar alineación;
- normalizar títulos y unidades;
- revisar slicers;
- ajustar espaciados;
- validar navegación;
- publicar versión final de presentación.
