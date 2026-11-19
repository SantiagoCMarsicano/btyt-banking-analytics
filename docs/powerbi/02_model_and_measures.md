# Power BI — Model and Measures

## Modelo actual

El modelo semántico se versiona en TMDL dentro de `powerbi/BTYT_Banking_Analytics.SemanticModel/definition/` y alimenta las siete páginas del informe.

Tablas (18):

```text
Hechos         Bank Performance · Branch Performance · Credit Risk · Customer Monthly
               Transactions and Channels · Market Performance · Campaign Performance
Dimensiones    DimDate · Customer Accounts · DimCustomerType
Parámetros     Customer Ranking Metric · Portfolio Metric · DimRelationshipDepth
               DPD Exposure Selector · DPD Rate Switch
Auxiliares     Bridge Steps (puente del resultado neto)
               Comparación temporal (grupo de cálculo)
Medidas        _Measures
```

Configuración del modelo:

- Auto date/time desactivado: `DimDate` es la única tabla de fechas.
- `discourageImplicitMeasures`: los visuales usan siempre medidas explícitas, no sumas automáticas de columnas.
- Las columnas técnicas y las que no usa ningún visual están ocultas, para que el panel de datos muestre solo lo necesario para el análisis.

## Relaciones

Todas son 1 → * con filtro en una dirección.

```text
DimDate[Date]
    1 → * Bank Performance[year_month]
    1 → * Branch Performance[year_month]
    1 → * Credit Risk[year_month]
    1 → * Transactions and Channels[year_month]
    1 → * Customer Monthly[year_month]
    1 → * Market Performance[Year Date]        (31/12 de cada año)
    1 → * Campaign Performance[start_date]     (solo parte fecha)

Customer Accounts[customer_id]
    1 → * Credit Risk[customer_id]
    1 → * Customer Monthly[customer_id]

DimCustomerType[customer_type]
    1 → * Customer Accounts[customer_type]
```

`Market Performance` tiene grano anual. La columna calculada `Year Date = DATE(year, 12, 31)` la conecta con el calendario, de modo que las medidas de mercado pueden filtrar por `DimDate[Year]` igual que el resto.

La segmentación por tipo de cliente llega a `Customer Monthly` a través de `DimCustomerType → Customer Accounts → Customer Monthly`.

Quedan desconectadas solo las tablas de parámetros (selectores de métrica, profundidad de relación, 30+/90+ DPD), `Bridge Steps` y el grupo de cálculo. `DPD Exposure Selector` (parámetro de campo) y `DPD Rate Switch` cumplen funciones distintas en Riesgo de Crédito.

## DimDate

Tabla calculada con `CALENDARAUTO(12)`. Columnas:

```text
Date · Year · MonthNumber · Month · MonthName · Quarter · YearMonth · YearMonthSort · UYU per USD
```

## Tipo de cambio anual

`DimDate[UYU per USD]` es la única fuente del tipo de cambio. Las medidas lo leen con `RELATED` o `LOOKUPVALUE`; ninguna tiene las tasas escritas a mano.

| Año | UYU / USD |
|---|---:|
| 2021 | 43.6 |
| 2022 | 41.2 |
| 2023 | 38.8 |
| 2024 | 40.3 |
| 2025 | 42.0 |
| 2026 | 43.5 |

## Regla monetaria

- **Performance:** los importes de `performance.*` llegan en UYU-equivalente y se convierten a USD con el tipo de cambio de cada año.
- **Customer Monthly:** depósitos, deuda vigente y volumen transaccionado se convierten con el tipo de cambio del año de cada observación.
- **Credit Risk:** `currency` define la moneda nativa del préstamo. Los préstamos en USD conservan el importe y los de UYU se dividen por el tipo de cambio anual.
- **No se convierten:** ratios, conteos, fechas, dimensiones y porcentajes.

## Comparaciones temporales: grupo de cálculo

`Comparación temporal` aplica la misma lógica a cualquier medida:

| Ítem | Expresión |
|---|---|
| Actual | `SELECTEDMEASURE()` |
| Año anterior | `CALCULATE(SELECTEDMEASURE(), SAMEPERIODLASTYEAR(DimDate[Date]))` |
| Variación | Actual − Año anterior |
| Variación % | (Actual − Año anterior) / Año anterior |

Las medidas del resumen ejecutivo lo invocan en vez de repetir lógica de fechas. Ejemplo:

```DAX
Exec Revenue PY = CALCULATE([Exec Revenue], 'Comparación temporal'[Comparación] = "Año anterior")
```

## Semántica temporal

- **Selector de año:** en Rentabilidad, Sucursales, Clientes y Transacciones hay un selector de año en botones, sincronizado entre esas cuatro páginas.
- **Año analizado del resumen ejecutivo:** `Exec Current Year`, que es el último año con datos dentro del filtro.
- **Flujos** (`Transaction Volume`, ingresos, costos): se suman dentro del período seleccionado, después de convertir la moneda.
- **Saldos** (`Outstanding Debt`, `Customer Deposits`, `Active Accounts`, `Period Deposits`, `Period Loan Balance`): no se suman entre meses; se usan promedios mensuales del período.
- **Clientes activos** (`Average Monthly Active Customers`): promedio mensual de clientes con al menos una cuenta activa.

## Medidas

Hay 107 medidas en `_Measures`, todas con carpeta y descripción en español (visible al pasar el mouse en Power BI).

| Carpeta | Medidas | Contenido |
|---|---:|---|
| Resultados | 7 | Ingresos, resultado neto, margen, costos / ingresos, margen financiero, comisiones, impuesto |
| Costos | 5 | Costos totales, de personal, operativos, variables y fijos |
| Sucursales | 14 | Las mismas métricas a nivel sucursal, sucursales rentables y deficitarias, color por signo |
| Clientes y cartera | 16 | Clientes activos, cuentas, depósitos, deuda, ranking dinámico, estadísticas de cartera |
| Riesgo de crédito | 10 | Pérdida de crédito, exposición, 30+ / 90+ DPD, faltantes de pago, títulos dinámicos |
| Transacciones y canales | 5 | Transacciones y volumen completados, participación por canal y digital, tasa de fallas |
| Mercado y campañas | 7 | Cuota y ranking de BTYT, cobertura y respuesta de campañas, clientes expuestos |
| Resumen Ejecutivo \ Indicadores | 24 | Valor, año anterior y variación de los seis indicadores |
| Resumen Ejecutivo \ Colores | 6 | Verde / rojo según si cada indicador mejora o empeora |
| Resumen Ejecutivo \ Textos | 5 | Titulares automáticos, mes pico, nota de datos, resumen del puente |
| Resumen Ejecutivo \ Gráficos | 8 | Puente, inicio del eje, alerta y color de anomalías de pérdida de crédito |

### Medidas destacadas

- **`Customer Ranking Value`:** cambia la métrica del Top 10 según el parámetro (`0` volumen transaccionado, `1` deuda vigente, `2` depósitos).
- **`Bridge Value` + `Bridge Base / Total / Increase / Decrease`:** puente del resultado neto a tipo de cambio del año anterior, con el efecto cambiario aparte. Se dibuja como barras apiladas con una base invisible.
- **`Credit Loss Anomaly Flag`:** vale 1 cuando la pérdida de crédito del mes supera el doble de la mediana de los 12 meses previos.
- **`Exec Headline Results` / `Exec Headline Drivers`:** el titular del resumen ejecutivo, armado con `FORMAT(..., "es-UY")`.
- **`Digital Channel Share`:** transacciones completadas por móvil o web sobre el total completado.
- **`Customer Accounts[Customer Display]`:** columna calculada que muestra la razón social de las empresas y "Cliente + ID" para las personas en los rankings.

La capa SQL y las vistas materializadas reducen el volumen antes de cargarlo en Power BI: el modelo no importa los eventos de transacción individuales.

## Principio de mantenimiento

Antes de agregar una tabla, una vista o una medida:

```text
pregunta de negocio
    ↓
¿la información ya existe al grano correcto?
    ├─ sí → DAX
    └─ no → SQL reutilizable
```

- No crear objetos auxiliares para resolver un visual aislado.
- No eliminar medidas ni tablas sin validar antes todas las páginas.
- En DAX, `Before` y `Levels` son palabras reservadas: no usarlas como nombres de variable.
