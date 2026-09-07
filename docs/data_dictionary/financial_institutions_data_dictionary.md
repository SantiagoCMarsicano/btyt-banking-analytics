# BTYT — Financial Institutions Data Dictionary

## 1. Purpose

`financial_institutions.csv` is the canonical BTYT dimension for financial counterparties that may participate in transaction flows.

It separates the concept of a **financial institution** from the narrower concept of a **bank**:

> A bank is a financial institution, but not every financial institution used as a transaction counterparty is a bank.

The dimension therefore combines:

- banks already defined by the BTYT banking-system model; and
- selected Uruguayan electronic-money issuers (IEDEs) relevant to the transaction universe.

This dimension does **not** replace `banks.csv`. The banking model remains responsible for bank-specific market structure, market shares, affinities, financial characteristics, and bank dynamics. `financial_institutions.csv` provides the broader counterparty namespace required by the transaction engine.

---

## 2. Canonical location

```text
data/generated/world/financial_institutions.csv
```

Generator:

```text
scripts/generators/generate_financial_institutions.py
```

The generator is deterministic and structural. It does not use an RNG stream.

---

## 3. Upstream dependency

The generator consumes the canonical bank dimension:

```text
data/generated/core/banks.csv
```

Each bank receives a corresponding financial-institution row with a stable semantic identifier:

```text
BANK_<bank_id>
```

Examples:

```text
B000 → BANK_B000
B001 → BANK_B001
B107 → BANK_B107
```

Electronic-money institutions are configured explicitly in the generator and do not receive a `bank_id`.

---

## 4. Current dimension composition

The current BTYT dimension contains **23 institutions**:

| Category | Count |
|---|---:|
| Banks | 19 |
| Domestic banks | 12 |
| International banks | 7 |
| Electronic-money issuers | 4 |
| Domestic institutions, total | 16 |
| International institutions, total | 7 |

The four explicitly modeled electronic-money issuers are:

| institution_id | institution_name | legal_name | active_from |
|---|---|---|---|
| `IEDE_PREX` | Prex | Econstar S.A. | 2015-09-23 |
| `IEDE_MIDINERO` | Midinero | Findarin S.A. | 2015-04-15 |
| `IEDE_OCA_BLUE` | OCA Blue | OCA Dinero Electrónico S.A. | 2020-07-07 |
| `IEDE_MERCADO_PAGO` | Mercado Pago Uruguay | MercadoPago Uruguay S.R.L. | 2023-07-11 |

All four currently have an open-ended `active_to`.

### Historical modeling note

`active_from` represents the date from which the institution or product is considered available to the BTYT transaction universe. It is used as a transaction-counterparty availability constraint rather than as a complete legal-entity-history model.

For Midinero, the static dimension uses the current legal name `Findarin S.A.` while retaining the earlier modeled availability of the Midinero product. BTYT does not currently implement a slowly changing legal-entity history for this institution.

For Mercado Pago Uruguay, BTYT uses **2023-07-11** as the effective availability date for the transaction model.

---

## 5. Schema

| Column | Type / representation | Nullable | Description |
|---|---|---:|---|
| `institution_id` | string | No | Stable primary key for the financial institution. Bank IDs use `BANK_<bank_id>`; non-bank institutions use semantic IDs such as `IEDE_PREX`. |
| `institution_name` | string | No | Display/common name of the institution used in BTYT. |
| `legal_name` | string | No | Legal or modeled legal name associated with the institution. |
| `institution_type` | categorical string | No | Institution class. Current values: `BANK` and `ELECTRONIC_MONEY_ISSUER`. |
| `country` | string | No | Operating country used for domestic/international classification. |
| `domestic_flag` | boolean | No | `True` when `country == "Uruguay"`; otherwise `False`. |
| `bank_id` | string | Yes | Foreign key to `banks.csv` for institutions of type `BANK`. Must be null for electronic-money issuers. |
| `active_from` | ISO date (`YYYY-MM-DD`) | Yes | Earliest date on which the institution is eligible to appear in the BTYT transaction universe. Null means no explicit lower temporal bound is modeled. |
| `active_to` | ISO date (`YYYY-MM-DD`) | Yes | Last date on which the institution is eligible to appear. Null means open-ended activity. |

---

## 6. Keys and relationships

### Primary key

```text
institution_id
```

`institution_id` must be unique and non-null.

### Bank foreign key

For bank rows:

```text
financial_institutions.bank_id
    → banks.bank_id
```

Every bank in `banks.csv` must appear exactly once in `financial_institutions.csv`.

For non-bank institutions:

```text
bank_id = NULL
```

An IEDE must never be inserted into the banking-market-share simplex merely to make it available as a transaction counterparty.

---

## 7. Institution types

### `BANK`

Represents institutions belonging to the BTYT bank dimension.

Bank-specific economic behavior continues to come from the banking subsystem, including, where applicable:

- market weights;
- USD affinity;
- business affinity;
- large-transfer affinity;
- foreign-selection weights; and
- bank-specific market dynamics.

`financial_institutions.csv` does not duplicate those modeled variables.

### `ELECTRONIC_MONEY_ISSUER`

Represents selected non-bank electronic-money institutions that are plausible external counterparties in BTYT transfer flows.

The current modeled set is deliberately limited to:

```text
Prex
Midinero
OCA Blue
Mercado Pago Uruguay
```

The dimension is not intended to be a complete catalog of the Uruguayan payment system.

---

## 8. Domestic and international classification

Domesticity is derived from `country`, not from `bank_scope`:

```text
country == "Uruguay" → domestic_flag = True
otherwise             → domestic_flag = False
```

This distinction is important because `bank_scope` has its own semantics inside the bank model and must not be reused as a proxy for institution geography.

Current composition:

```text
Domestic institutions
├── BTYT
├── other Uruguayan banks
└── selected Uruguayan IEDEs

International institutions
└── international banks
```

---

## 9. Temporal availability

An institution is eligible for a transaction occurring at date `t` when:

```text
(active_from is NULL or active_from <= t)
AND
(active_to   is NULL or t <= active_to)
```

This constraint is enforced downstream by the transaction engine.

Example:

```text
IEDE_MERCADO_PAGO
active_from = 2023-07-11
```

Therefore Mercado Pago Uruguay cannot be selected as a counterparty for a BTYT transaction dated before 2023-07-11.

---

## 10. Transaction-engine semantics

Beginning with **Transactions V4.0.0**, the canonical transaction fact uses:

```text
counterparty_institution_id
```

instead of the narrower:

```text
counterparty_bank_id
```

The modeled transfer hierarchy is:

```text
TRANSFER
├── INTERNAL
│   └── BTYT account / BANK_B000
│
├── DOMESTIC_EXTERNAL
│   ├── BANK
│   └── ELECTRONIC_MONEY_ISSUER
│
└── INTERNATIONAL
    └── BANK
```

The institution type itself does not need to be duplicated in the transaction fact. It can be obtained through a join:

```text
transactions.counterparty_institution_id
    → financial_institutions.institution_id
```

This keeps the transaction schema normalized and makes the dimension the authoritative source for institution metadata.

---

## 11. Probabilistic selection principle

The existence of an institution in this dimension makes it **eligible** as a counterparty; it does not assign transactions to that institution deterministically.

BTYT follows the broader modeling principle:

> **BTYT models causes as probabilistic shifts in behavior, not deterministic assignments of outcomes.**

For domestic external transfers, banks and eligible IEDEs compete probabilistically. Customer characteristics, transaction characteristics, bank prominence, bank affinities, digital behavior, and other modeled conditions may shift selection probabilities without forcing ex-post target shares.

IEDE shares are therefore emergent properties of the synthetic world rather than hard-coded final percentages.

---

## 12. Validation rules

The generator validates the following structural invariants:

1. `institution_id` is non-null and unique.
2. Required descriptive fields are non-null and non-empty.
3. `institution_type` belongs to the supported set.
4. Every `BANK` has a non-null `bank_id`.
5. Every `ELECTRONIC_MONEY_ISSUER` has a null `bank_id`.
6. Every source bank appears exactly once in the institution dimension.
7. No unknown bank is introduced through the dimension.
8. A `bank_id` cannot map to multiple financial-institution rows.
9. `domestic_flag` is consistent with `country`.
10. The configured IEDE set is realized exactly.
11. Current IEDEs are domestic.
12. Temporal fields must contain valid dates when populated.
13. `active_to` cannot precede `active_from`.

Transactions V4.0.0 adds downstream integrity checks including:

- valid `counterparty_institution_id` foreign keys;
- correct institution scope for domestic external transfers;
- correct institution scope for international transfers;
- international counterparties must be banks under the current model;
- BTYT cannot appear as an external institution;
- internal transfers resolve to the BTYT institution;
- non-transfer transactions do not carry transfer institution metadata; and
- institutions cannot appear outside their modeled activity period.

---

## 13. Current transaction integration status

Transactions V4.0.0 has been validated against this dimension in smoke mode with the canonical world seed.

The transaction engine successfully generated external counterparties across:

- domestic banks;
- international banks;
- Prex;
- Midinero;
- OCA Blue; and
- Mercado Pago Uruguay.

The engine also passed the temporal-availability validation, including the Mercado Pago activation constraint.

Chunk-size invariance was tested using different account chunk sizes while preserving the same world seed and smoke population. The realized logical transaction world remained unchanged.

---

## 14. Design boundaries

This dimension intentionally does **not** model:

- complete Uruguayan payment-system membership;
- payment processors merely because they exist;
- acquirers unless they become relevant transaction counterparties;
- full historical corporate/legal-entity succession;
- market shares for IEDEs without defensible data;
- forced transaction shares by institution;
- institution-specific financial statements for non-banks; or
- bank-market competition for IEDEs.

Additional institution classes should only be introduced when they solve a concrete modeling requirement.

---

## 15. Architectural role

The intended dependency structure is:

```text
banks.csv
    ↓
financial_institutions.csv
    ↓
transactions.parquet
```

Conceptually:

```text
BANKING SYSTEM
└── banks
    ├── market structure
    ├── bank affinities
    └── bank dynamics

FINANCIAL COUNTERPARTY SYSTEM
└── financial institutions
    ├── banks
    └── electronic-money issuers

TRANSACTION SYSTEM
└── selects eligible counterparties probabilistically
```

This preserves a clean separation between **banking-system economics** and the broader **financial-counterparty universe** required for transaction modeling.

---

## 16. Reproducibility and governance

`generate_financial_institutions.py` is deterministic. Given the same canonical bank dimension and the same explicit institution configuration, it must produce the same financial-institution dimension.

No random seed is required because no stochastic realization occurs in this generator.

The canonical file name should remain stable:

```text
financial_institutions.csv
```

Generator history belongs in Git rather than in versioned filenames such as `financial_institutions_v2.csv`.

If the schema or semantics change materially, dependent generators—especially Transactions—must be revalidated before the new world can be promoted or frozen.
