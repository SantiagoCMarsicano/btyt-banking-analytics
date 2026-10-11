# BTYT Banking Analytics — Power BI

## Objetivo

Documentar la capa de visualización de **BTYT Banking Analytics — Part I: Business Intelligence & Performance Management**.

Power BI es la superficie principal de BI corporativo del proyecto.

## Convenciones

```text
Tablas / columnas / measures / DAX → inglés
Títulos / etiquetas visibles         → español
```

### Moneda de presentación

El dashboard presenta importes seleccionados en USD.

- `performance.*` llega desde PostgreSQL en UYU-equivalente.
- Las measures monetarias convierten a USD con el tipo de cambio anual documentado.
- En `Credit Risk`, los saldos nativos USD permanecen en USD; los saldos UYU se convierten.
- Ratios, conteos y porcentajes no se convierten por FX.

## Páginas

| # | Página | Estado |
|---|---|---|
| 01 | Resumen Ejecutivo | Funcionalmente cerrada |
| 02 | Sucursales | Funcionalmente cerrada |
| 03 | Clientes y Cuentas | Funcionalmente cerrada |
| 04 | Riesgo de Crédito | KPIs cerrados; visuales analíticos en construcción |
| 05 | Transacciones y Canales | Pendiente |
| 06 | Mercado y Campañas | Pendiente |

El pulido visual final, tema, colores y alineación global se deja para el cierre funcional de las seis páginas.

## Archivos PBIX

En el repositorio existen dos archivos con funciones distintas:

```text
powerbi/BTYT_Banking_Analytics.pbix
    → archivo base/canónico del modelo

powerbi/BTYT PRESENTATION.pbix
    → copia de trabajo utilizada para construir la presentación visual actual
```

Ambos pueden versionarse mediante Git LFS.

## Fuente

Fuente principal:

```text
PostgreSQL
```

El 2026-10-11 se completó un full refresh de las 23 tablas físicas y se refrescaron las materialized views de `analytics`.

## Período analítico

```text
2021-01 → 2026-12
```

## Selector temporal

No existe un único selector universal para todas las páginas.

- Resumen Ejecutivo / Sucursales usan principalmente contexto anual.
- Clientes y Cuentas usa `Analysis Window`:
  - `1M`
  - `3M`
  - `6M`
  - `12M`
  - `All`
- La semántica del selector depende del KPI: clientes/cuentas activos son únicos dentro de la ventana; depósitos/préstamos son stocks mensuales promediados en la ventana.

## Principio de construcción

```text
pregunta de negocio
    ↓
¿el grano ya existe?
    ├─ sí → measure DAX
    └─ no → view/fact reusable en SQL
```

No se modifica el modelo físico por una necesidad aislada de un gráfico.

## Estado actual de riesgo

La fila superior de Página 04 ya está validada después de la recalibración:

```text
Exposición crediticia          ≈ US$4.338B
Exposición 90+ DPD              5.16%
Cartera reestructurada          0.64%
Pérdida crediticia / cartera    0.63%
```

Estos son resultados sintéticos del mundo BTYT y no métricas regulatorias.

## Reproducibilidad pendiente antes del próximo freeze

Los resultados actuales están cargados y funcionando en Power BI, pero antes de generar un nuevo manifest/fingerprint del dataset debe resolverse la sincronización entre `active_world.json` y `world_config.json`.

Ver:

```text
docs/README.md
docs/analytics/credit_risk_calibration.md
```
