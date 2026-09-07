# BTYT Data Dictionary

This directory contains the table-level documentation contracts for the BTYT Banking
Analytics synthetic banking universe.

## Architecture convention

All paths such as `data/generated/...`, `data/interim/...`, and
`data/operational/...` are **world-relative**. Their physical root is resolved from
`config/active_world.json` by `scripts/core/paths.py`.

A materialized world therefore lives conceptually under:

```text
worlds/<world>/<variant>/
├── data/
│   ├── generated/
│   ├── interim/
│   └── operational/
├── database/
├── audit/
└── manifests/
```

The data dictionaries document stable table semantics, grain, keys, relationships,
generation rules, and validation contracts. They are intentionally not tied to one
specific world realization.

## Current canonical-generation context

As of 2026-09-07, the active canonical-generation candidate is:

```text
World: BTYT33
Seed: 606597249
Customers: 63,205
Status: generation and validation in progress
```

These values describe the current realization; they do not replace the generic
contracts documented in the individual dictionaries.

## Naming

All table dictionaries follow the pattern:

```text
<table_name>_data_dictionary.md
```

The cross-system audit dictionary documents the final integrated validation contract
rather than a materialized analytical table.
