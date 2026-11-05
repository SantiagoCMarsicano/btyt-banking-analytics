# BTYT Banking Analytics — Power BI

## Objetivo

Documentar la capa de visualización de **BTYT Banking Analytics — Part I: Business Intelligence & Performance Management**.

Power BI es la principal superficie de BI corporativo implementada en Part I.

## Estado actual

**Dashboard finalizado.**

El reporte contiene seis páginas funcionales y visualmente cerradas:

| # | Página | Estado |
|---|---|---|
| 01 | Resumen Ejecutivo | Final |
| 02 | Sucursales | Final |
| 03 | Clientes y Cuentas | Final |
| 04 | Riesgo de Crédito | Final |
| 05 | Transacciones y Canales | Final |
| 06 | Mercado y Campañas | Final |

Capturas finales:

```text
docs/assets/Pag1.png
docs/assets/Pag2.png
docs/assets/Pag3.png
docs/assets/Pag4.png
docs/assets/Pag5.png
docs/assets/Pag6.png
```

## Convenciones

```text
Tablas / columnas / measures / DAX → inglés
Títulos / etiquetas visibles       → español
```

## Moneda de presentación

Los importes monetarios finales del dashboard se presentan en USD cuando corresponde.

- `performance.*` llega desde PostgreSQL en UYU-equivalente.
- Las measures monetarias convierten a USD con el tipo de cambio anual documentado.
- En `Credit Risk`, los saldos nativos USD permanecen en USD y los saldos UYU se convierten.
- En `Customer Monthly`, los importes UYU se convierten por año antes de su agregación de presentación.
- Ratios, conteos, fechas y porcentajes no se convierten por FX.

Tipo de cambio anual usado en BI:

| Año | UYU / USD |
|---|---:|
| 2021 | 43.6 |
| 2022 | 41.2 |
| 2023 | 38.8 |
| 2024 | 40.3 |
| 2025 | 42.0 |
| 2026 | 43.5 |

## Archivo PBIX

Archivo canónico:

```text
powerbi/BTYT_Banking_Analytics.pbix
```

El PBIX se versiona mediante Git LFS.

## Fuente

Fuente principal:

```text
PostgreSQL
```

La capa BI consume tablas/vistas analíticas y agregaciones reutilizables. La fact cruda de transacciones no se importa directamente por defecto.

Escala canónica actual de transacciones:

```text
Total       74,774,125
Completed   72,746,246
Failed       2,027,879
```

## Período analítico

```text
2021-01 → 2026-12
```

## Selector temporal

Las páginas con análisis longitudinal usan controles visibles:

```text
1 año
3 años
5 años
Todos
```

La implementación final respeta el contexto temporal de `DimDate`.

Regla semántica:

- **flujos**: se acumulan dentro del período seleccionado;
- **stocks**: se evalúan con una regla temporal explícita, normalmente promedio mensual para análisis de cartera;
- **ratios**: se recalculan desde numerador/denominador en el contexto seleccionado.

Esto evita sumar stocks mensuales de forma mecánica.

## Principio de construcción

```text
pregunta de negocio
    ↓
¿el grano ya existe?
    ├─ sí → measure DAX
    └─ no → view/fact reusable en SQL
```

No se modifica el modelo físico por una necesidad aislada de un gráfico.

## Alcance de Part I

Implementado:

```text
Python → PostgreSQL → SQL → Power BI
```

Extensiones previstas:

```text
Excel
Tableau
```

Excel y Tableau deben complementar el mismo universo analítico, no duplicar un segundo pipeline independiente.

## Reproducibilidad pendiente antes del próximo freeze

Antes de generar un nuevo manifest/fingerprint del dataset debe resolverse la sincronización entre `active_world.json` y `world_config.json` y revalidarse cualquier salida RNG-driven afectada.

Ver:

```text
docs/README.md
docs/architecture/btyt_part_i_manifest.md
```
