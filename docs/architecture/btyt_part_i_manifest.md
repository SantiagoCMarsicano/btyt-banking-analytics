# BTYT Part I — Final Dataset Manifest

**Component:** Final Dataset Manifest  
**Version:** V1.1.0  
**Project:** BTYT Banking Analytics — Part I  
**Status:** Manifest refresh required after October 2026 recalibration  
**Purpose:** Cryptographically inventory and freeze the finalized BTYT Part I dataset without modifying upstream data.

> **Current status — 2026-10-11:** the previously frozen manifest no longer describes the current materialized loan / loan-snapshot / performance files because those layers were regenerated during the credit-risk recalibration. A new manifest/fingerprint must **not** be issued until the active-world path and world-level RNG configuration are synchronized and the affected outputs are reverified.

---

## 1. Objective

The manifest is the final governance layer for the BTYT Part I synthetic banking dataset.

Its purpose is to establish a reproducible, auditable identity for the finalized dataset after the generators, operational reliability layer, cross-system audit, and project orchestrator have passed validation.

The manifest does **not** generate banking data and does **not** modify canonical or operational datasets.

It records the exact files that constitute the frozen Part I dataset and calculates SHA-256 hashes so later changes can be detected.

---

## 2. Generator

Canonical script:

```text
scripts/generate_manifest.py
```

Current version:

```text
V1.1.0
```

Run from the repository root:

```powershell
python -m scripts.generate_manifest
```

Verify an already frozen dataset:

```powershell
python -m scripts.generate_manifest --verify-only
```

---

## 3. Preconditions

The manifest should only be generated after the final cross-system audit has passed.

Expected validation state:

```text
BTYT FINAL CROSS-SYSTEM AUDIT V2.0.0: PASS
```

The latest orchestrator run, when available, must also resolve to `PASS`.

The manifest generator refuses to create the final freeze record if the cross-system audit resolves to `FAIL`.

---

## 4. Manifest outputs

The generator writes into the active world's manifest directory:

```text
worlds/<world>/<variant>/manifests/
├── btyt_part_i_manifest.json
└── btyt_part_i_manifest_files.csv
```

`MANIFESTS_DIR` is resolved by `scripts/core/paths.py`.

### `btyt_part_i_manifest.json`

Primary machine-readable freeze record.

It contains:

- manifest schema version;
- manifest generator version;
- dataset name;
- dataset state;
- UTC manifest creation timestamp;
- world identity;
- world configuration SHA-256;
- cross-system audit status;
- latest orchestrator status;
- inventory summary;
- Python/runtime metadata;
- Git metadata when available;
- global dataset fingerprint;
- complete per-file inventory.

### `btyt_part_i_manifest_files.csv`

Flat inventory intended for convenient inspection, BI use, repository review, and auditing.

Each row represents one inventoried file.

---

## 5. File-level metadata

For every inventoried file the manifest records:

```text
role
relative_path
format
size_bytes
rows
columns
sha256
```

### Roles

The manifest separates files into three roles:

- `canonical` — finalized analytical ground truth;
- `operational` — intentionally imperfect operational representations;
- `provenance` — reliability, lineage, and cross-system audit evidence.

---

## 6. Canonical inventory

V1.1.0 inventories the following canonical files:

```text
data/generated/world/macro_environment.csv
data/generated/core/banks.csv
data/generated/performance/bank_market_weights.csv
data/generated/performance/bank_financials.csv
data/generated/performance/bank_world_parameters.csv
data/generated/world/financial_institutions.csv
data/generated/core/branches.csv
data/generated/core/customers.parquet
data/generated/core/accounts.parquet
data/generated/core/cards.parquet
data/generated/core/loans.parquet
data/generated/credit/loan_monthly_snapshot.parquet
data/generated/world/external_shocks.csv
data/generated/transactions/transactions.parquet
data/generated/core/account_balances.parquet
data/generated/campaigns/campaigns.csv
data/generated/campaigns/campaign_customers.parquet
data/generated/campaigns/campaign_exposures.parquet
data/generated/performance/branch_monthly_performance.parquet
data/generated/performance/bank_monthly_performance.parquet
```

Path correction retained from V1.0.1:

```text
cards.parquet
```

is canonical under:

```text
data/generated/core/cards.parquet
```

and **not** under `data/generated/credit/`.

---

## 7. Operational inventory

The manifest inventories:

```text
data/operational/customers.csv
data/operational/accounts.csv
data/operational/cards.csv
data/operational/loans.csv
data/operational/branches.csv
data/operational/transactions.csv
data/operational/campaign_customers.csv
data/operational/campaign_exposures.csv
```

These files are intentionally separate from canonical truth.

Operational imperfections do not redefine the canonical banking universe.

---

## 8. Provenance and audit inventory

The manifest inventories the following supporting evidence:

```text
data/interim/data_reliability_world.csv
data/interim/data_reliability_audit.csv
data/interim/operational_export_sources.csv
data/interim/audits/cross_system_audit_results.csv
data/interim/audits/cross_system_resolved_sources.csv
```

These files document reliability behavior, source lineage, and final cross-system validation.

They are inventoried and hashed, but they are excluded from the global dataset fingerprint because audit/provenance artifacts may contain run-specific metadata.

---

## 9. Dataset fingerprint

The manifest generates a deterministic SHA-256 fingerprint for the finalized BTYT dataset.

The fingerprint scope is:

```text
canonical + operational files
```

For each file, the fingerprint incorporates:

- role;
- relative path;
- file size;
- row count;
- column count;
- SHA-256.

The records are sorted deterministically before the global fingerprint is calculated.

Volatile metadata such as manifest creation time is excluded.

Provenance and audit artifacts are also excluded from the global dataset fingerprint.

This allows the fingerprint to represent the content identity of the frozen analytical and operational dataset rather than the timestamp of a particular audit execution.

---

## 10. Freeze semantics

A successful manifest generation records:

```text
dataset_state = FROZEN
```

This means that the inventoried Part I dataset is the official frozen BTYT Part I data release.

After freeze, changes to inventoried canonical or operational files should be treated as a new dataset version rather than silently replacing the frozen release.

The manifest itself does not enforce filesystem immutability. It provides cryptographic detection of changes.

---

## 11. Verification mode

After the manifest has been created, run:

```powershell
python -m scripts.generate_manifest --verify-only
```

Verification recalculates, for every inventoried file:

- SHA-256;
- file size;
- row count;
- column count.

It then recalculates the global dataset fingerprint.

Expected successful result:

```text
Dataset fingerprint: PASS
FINAL MANIFEST VERIFICATION: PASS
The inventoried BTYT Part I dataset matches the frozen manifest.
```

A missing file, changed hash, changed size, changed row count, changed column count, or changed global fingerprint causes verification to fail with a non-zero exit code.

---

## 12. Read-only contract

The manifest generator is a downstream governance component.

It may read:

- world configuration;
- canonical datasets;
- operational datasets;
- provenance artifacts;
- cross-system audit results;
- latest orchestrator run metadata;
- Git repository metadata.

It may write only:

```text
manifests/btyt_part_i_manifest.json
manifests/btyt_part_i_manifest_files.csv
```

It must not modify any inventoried source dataset.

---

## 13. Relationship to the final architecture

The finalization chain is:

```text
BTYT generators
        ↓
canonical datasets
        ↓
campaign / performance layers
        ↓
operational reliability layer
        ↓
final cross-system audit
        ↓
full-project orchestrator validation
        ↓
final dataset manifest
        ↓
BTYT Part I dataset freeze
```

The manifest is therefore the final identity and integrity record, not another simulation layer.

---

## 14. Current finalization versions

At the time of this manifest specification:

```text
Transactions                         V5.0.0 EXACT FAST
Loan master                           V5.2.0 FINAL RISK CALIBRATION
Loan monthly snapshot                 V4.2 RISK RECALIBRATED
Campaign behavioral engine            V2.1.0
Branch performance                    V3.2.0
Operational data reliability layer    V2.0.2
Final cross-system audit              V2.0.0
Full-project orchestrator             V1.0.0
Final dataset manifest                V1.1.0; regeneration pending
```

---

## 15. Final acceptance criteria

The manifest component is accepted when:

1. all required inventory files resolve;
2. file hashes are calculated successfully;
3. table shapes are recorded successfully;
4. the final cross-system audit resolves to `PASS`;
5. the latest orchestrator run does not resolve to `FAIL`;
6. both manifest outputs are written;
7. a global dataset fingerprint is produced;
8. `--verify-only` passes immediately after creation;
9. no upstream canonical or operational dataset is modified.

Expected final generation message:

```text
BTYT FINAL DATASET MANIFEST V1.1.0: PASS
Dataset state recorded as FROZEN.
No inventoried source dataset was modified.
```

Expected verification message:

```text
FINAL MANIFEST VERIFICATION: PASS
The inventoried BTYT Part I dataset matches the frozen manifest.
```

---

## 16. Current freeze condition after risk recalibration

The October 2026 recalibration changed canonical or derived files including:

```text
data/generated/core/loans.parquet
data/generated/credit/loan_monthly_snapshot.parquet
data/generated/performance/branch_monthly_performance.parquet
data/generated/performance/bank_monthly_performance.parquet
```

The PostgreSQL full refresh successfully consumed the current files, but a database refresh is **not** a dataset freeze.

Before generating a replacement manifest:

1. synchronize `config/active_world.json` and `config/world_config.json` to BTYT/01;
2. verify the intended canonical seed against `worlds/registry.json`;
3. rerun / verify the RNG-driven recalibrated layers as needed;
4. run the integrated audits required by the manifest contract;
5. generate the new manifest;
6. run `--verify-only`;
7. only then mark the updated Part I dataset as frozen.

Until those steps are complete, the previous manifest should be treated as an older frozen release record rather than proof that the current recalibrated files match the old fingerprint.

---

## 17. Version history

### V1.1.0

- Manifest generator operates against the active isolated world.
- Manifest outputs resolve through the active world's `MANIFESTS_DIR`.
- Generation and verification refuse to proceed without an active isolated world.
- Canonical inventory uses the current world-relative `external_shocks` path.
- Existing fingerprint and file-inventory semantics remain intact.

### V1.0.1

- Corrected canonical cards path from `data/generated/credit/cards.parquet` to `data/generated/core/cards.parquet`.
- Retained the V1.0.0 manifest architecture and freeze semantics.
- No upstream dataset changes.

### V1.0.0

- Initial final dataset manifest design.
- Added canonical, operational, and provenance inventory.
- Added per-file SHA-256.
- Added deterministic global dataset fingerprint.
- Added cross-system audit and orchestrator validation metadata.
- Added verification mode.
