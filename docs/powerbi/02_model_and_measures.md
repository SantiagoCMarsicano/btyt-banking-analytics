# Power BI — Model and Measures

## Modelo actual

El modelo visible en Power BI contiene 15 tablas:

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
Market Performance
Portfolio Metric
Transactions and Channels
```

`Customer Segment Monthly` fue eliminado del modelo de Power BI porque no aportaba valor adicional en la capa semántica actual.

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

## Tablas desconectadas intencionalmente

```text
Market Performance
Campaign Performance
Analysis Window
Customer Ranking Metric
DimRelationshipDepth
Portfolio Metric
```

Las tablas auxiliares de parámetros permanecen desconectadas por diseño.

## DimDate

`DimDate` es una tabla de fechas explícita y Auto date/time está desactivado.

La tabla incluye:

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

## Analysis Window

Valores:

```text
1M
3M
6M
12M
All
```

### Clientes activos

Cuenta clientes distintos activos al menos una vez dentro de la ventana seleccionada.

No es un promedio mensual.

### Cuentas activas

Cuenta cuentas distintas activas al menos una vez dentro de la ventana.

`Customer Accounts` contiene columnas reutilizables:

```text
active_accounts_1m
active_accounts_3m
active_accounts_6m
active_accounts_12m
active_accounts_all
```

### Depósitos promedio / Préstamos promedio

Son stocks de cartera promediados entre los meses de la ventana.

```text
1M  → snapshot mensual actual
All → promedio mensual histórico del período
```

No son sumas acumuladas de stock.

## Measures — Clientes y Cuentas

Entre las measures activas se encuentran:

```text
Active Customers
Active Accounts Period
Average Deposits
Average Loan Balance
New Customers
Closed Customers
Net Customer Growth
Active Card Penetration
```

La página también usa parámetros para:

```text
Customer Ranking Metric
Portfolio Metric
Relationship Depth
```

## Measures — Riesgo de Crédito

### Total Credit Exposure

Exposición del último mes disponible, convertida a USD respetando la moneda nativa del préstamo.

### 90+ DPD Exposure Rate

```text
exposición con days_past_due > 90
/
exposición total
```

La condición `> 90` coincide con el bucket canónico `DPD_90_PLUS`.

### Restructured Exposure Rate

```text
exposición con loan_status = RESTRUCTURED
/
exposición total
```

### Credit Loss Ratio

Measure de pérdida crediticia anualizada respecto de la cartera media en el contexto temporal seleccionado.

El resultado debe interpretarse como KPI sintético de gestión, no como ratio regulatorio.

## Valores actuales observados — Página 04

Después del refresh de PostgreSQL y Power BI:

```text
Total Credit Exposure        ≈ US$4.338B
90+ DPD Exposure Rate          5.16%
Restructured Exposure Rate     0.64%
Credit Loss Ratio              0.63%
```

## Principio de mantenimiento

Antes de agregar una tabla o view nueva:

```text
pregunta de negocio
    ↓
¿la información ya existe al grano correcto?
    ├─ sí → DAX
    └─ no → SQL reusable
```

Evitar crear measures temporales o tablas auxiliares solo para resolver un visual aislado.
