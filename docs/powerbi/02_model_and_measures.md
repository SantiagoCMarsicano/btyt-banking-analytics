# Power BI — Model and Measures

## Modelo actual

El modelo final visible en Power BI contiene las tablas analíticas principales, dimensiones y helpers necesarios para las seis páginas.

Tablas principales y auxiliares:

```text
_Measures
Analysis Window
Bank Performance
Branch Performance
Campaign Performance
Credit Risk
Customer Accounts
Customer Monthly
Customer Ranking Metric
DimCustomerType
DimDate
DimRelationshipDepth
DPD Exposure Selector
DPD Rate Switch
Market Performance
Portfolio Metric
Transactions and Channels
```

`Customer Segment Monthly` fue eliminado del modelo porque no aportaba valor adicional en la capa semántica final.

## Relaciones principales

```text
DimDate[Date]
    1 → * Bank Performance[year_month]

DimDate[Date]
    1 → * Branch Performance[year_month]

DimDate[Date]
    1 → * Credit Risk[year_month]

DimDate[Date]
    1 → * Transactions and Channels[year_month]

DimDate[Date]
    1 → * Customer Monthly[year_month]

DimCustomerType[customer_type]
    1 → * Customer Accounts[customer_type]

Customer Accounts[customer_id]
    1 → * Credit Risk[customer_id]

Customer Accounts[customer_id]
    1 → * Customer Monthly[customer_id]
```

La segmentación por tipo de cliente llega a `Customer Monthly` a través de:

```text
DimCustomerType
    ↓
Customer Accounts
    ↓
Customer Monthly
```

## Tablas desconectadas / helpers

Se mantienen desconectadas cuando su función es parametrizar un visual o conservar un grano independiente:

```text
Market Performance
Campaign Performance
Analysis Window
Customer Ranking Metric
DimRelationshipDepth
Portfolio Metric
DPD Exposure Selector
DPD Rate Switch
```

`DPD Exposure Selector` y `DPD Rate Switch` cumplen funciones distintas en la página de Riesgo de Crédito y deben conservarse.

## DimDate

`DimDate` es una tabla de fechas explícita y Auto date/time está desactivado.

Incluye, entre otros:

```text
Year
MonthNumber
Month
MonthName
Quarter
YearMonth
YearMonthSort
UYU per USD
```

## Tipo de cambio anual

| Año | UYU / USD |
|---|---:|
| 2021 | 43.6 |
| 2022 | 41.2 |
| 2023 | 38.8 |
| 2024 | 40.3 |
| 2025 | 42.0 |
| 2026 | 43.5 |

## Regla monetaria

### Performance

Los importes de `performance.*` llegan en UYU-equivalente y las measures de presentación los convierten a USD según el año.

### Customer Monthly

Variables monetarias UYU, como depósitos, deuda vigente y volumen transaccionado, se convierten a USD usando el FX correspondiente al año de cada observación.

### Credit Risk

`Credit Risk[currency]` define la moneda nativa del préstamo:

```text
USD → conservar importe
UYU → dividir por FX anual
```

### No convertir

```text
ratios
conteos
fechas
dimensiones
porcentajes
```

## Semántica temporal final

Los selectores visibles usan:

```text
1 año
3 años
5 años
Todos
```

Las measures finales que deben reaccionar al período respetan directamente el contexto de `DimDate`.

### Flujos

Ejemplo:

```text
Transaction Volume
```

Se suman dentro del período seleccionado, después de aplicar la conversión monetaria correspondiente.

### Stocks

Ejemplos:

```text
Outstanding Debt
Customer Deposits
Active Accounts
Period Deposits
Period Loan Balance
```

No se suman mecánicamente entre meses. Para el análisis de cartera se usan promedios mensuales dentro del período seleccionado.

### Clientes activos

`Active Customers Period` se interpreta como promedio mensual de clientes activos en el período visible.

## Measures — Clientes y Cuentas

Entre las measures activas se encuentran:

```text
Active Customers Period
Active Accounts
Period Deposits
Period Loan Balance
Transaction Volume
Outstanding Debt
Customer Deposits
Customer Ranking Value
```

`Customer Ranking Value` selecciona dinámicamente:

```text
0 → Transaction Volume
1 → Outstanding Debt
2 → Customer Deposits
```

La página también usa parámetros para:

```text
Customer Ranking Metric
Portfolio Metric
Relationship Depth
```

## Measures — Riesgo de Crédito

La página final prioriza:

```text
Total Credit Exposure
30+ DPD Exposure
90+ DPD Exposure
Payment Shortfall
```

También usa medidas de tasa y selectores auxiliares para comparar 30+ / 90+ DPD por segmento, préstamo y cohorte.

## Measures — Transacciones y Canales

Medidas principales:

```text
Completed Transactions
Completed Transaction Volume
Channel Share
Failed Transaction Rate
```

La capa SQL/materializada reduce el volumen antes de la ingestión en Power BI.

## Measures — Mercado y Campañas

Medidas principales:

```text
BTYT Market Share
BTYT Market Rank
Campaign Coverage Rate
Positive Response Rate
```

`Market Performance` y `Campaign Performance` pueden permanecer desconectadas cuando su grano no justifica una relación física con el resto del modelo.

## Principio de mantenimiento

Antes de agregar una tabla, view o measure:

```text
pregunta de negocio
    ↓
¿la información ya existe al grano correcto?
    ├─ sí → DAX
    └─ no → SQL reusable
```

Evitar crear objetos auxiliares solo para resolver un visual aislado y no eliminar measures/tables que tengan dependencias visuales sin validar primero todas las páginas.
