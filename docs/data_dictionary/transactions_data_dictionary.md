# BTYT Transactions V6 â€” Persistent Transfer Network Rework

**Status:** implementation draft prepared for future integration
**Current production world:** unchanged
**Base engine:** Transactions V5.0.0 EXACT FAST
**New module:** `scripts/generators/transfer_network.py`
**Execution status:** syntax-checked only; not run against BTYT-01

---

## 1. Why this rework exists

Transactions V5 already solves the difficult operational problems: deterministic generation, staged Parquet output, resumable checkpoints, chronological ledger replay, exact paired internal transfers, balance reconciliation, institution scope rules, and large-world performance.

The remaining weakness is behavioral rather than structural:

> a plausible transfer event is not necessarily a plausible transfer history.

In V5, many transfer counterparties are selected at event time. V6 introduces a persistent network so customers tend to reuse counterparties across months and years.

The core objective is therefore:

> **Transfers should emerge from persistent financial relationships, while the chronological ledger remains authoritative.**

---

## 2. What was implemented in the draft

A standalone `transfer.py` module has been created. It is deliberately not wired into the accepted production engine yet.

The module implements:

- deterministic relationship identifiers;
- account/customer network context;
- bounded persistent relationship generation;
- internal BTYT relationships;
- explicit own-account / treasury relationships;
- domestic external relationships;
- bank and IEDE relationships;
- international relationships;
- relationship lifecycle dates;
- recurrence profiles;
- latent relationship strength;
- preferred channels;
- relationship-aware event selection;
- relationship-aware amount multipliers;
- relationship-aware channel weights;
- structural relationship audits.

The module compiles successfully, but this is **not** an empirical validation of the future V6 engine.

---

## 3. V5 mechanics that must remain authoritative

The current production engine must preserve the following behaviors during a future integration:

1. semantic deterministic RNG based on the BTYT world seed;
2. canonical customer/account/institution inputs;
3. account-local transaction intent generation;
4. Parquet staging;
5. monthly chronological replay;
6. live balance carry-forward;
7. non-overdraft debit execution;
8. operational failure logic;
9. exact paired internal transfers;
10. account-balance reconciliation;
11. resumable checkpoints;
12. final validation and audit output.

V6 changes **counterparty persistence**, not the accounting authority of the ledger.

---

## 4. New relationship table

### `customer_counterparty_relationships`

| Field | Meaning |
|---|---|
| `relationship_id` | Stable deterministic synthetic relationship ID |
| `customer_id` | Customer owning the relationship |
| `source_account_id` | Preferred BTYT source account |
| `counterparty_scope` | INTERNAL / DOMESTIC_EXTERNAL / INTERNATIONAL |
| `counterparty_type` | BTYT_CUSTOMER / FINANCIAL_INSTITUTION |
| `counterparty_customer_id` | Internal BTYT customer when applicable |
| `counterparty_account_id` | Internal BTYT account when applicable |
| `counterparty_institution_id` | External financial institution when applicable |
| `relationship_type` | Economic meaning of the relationship |
| `relationship_strength` | Relative propensity to reuse the relationship |
| `start_date` | Relationship activation date |
| `end_date` | Optional termination date |
| `recurrence_profile` | RECURRING / OCCASIONAL / SPORADIC |
| `preferred_channel` | Typical channel |
| `currency` | Relationship currency |

This table should eventually be written to an interim/network location, for example:

```text
worlds/<world>/<variant>/data/interim/transactions/customer_counterparty_relationships.parquet
```

It is not required to become part of the canonical business model unless the analytical use case justifies it.

---

## 5. Relationship classes

### Individuals

Internal:

- `OWN_ACCOUNT`
- `HOUSEHOLD_FAMILY`
- `PEER_TO_PEER`
- `RECURRING_PERSONAL`

Domestic external:

- `EXTERNAL_BANK_SELF_TRANSFER`
- `SAVINGS_INVESTMENT`
- `WALLET_FUNDING`

International:

- `REMITTANCE`

### Businesses

Internal:

- `SUPPLIER_CUSTOMER_NETWORK`
- `PAYROLL_OR_STAFF`
- `BUSINESS_PARTNER`
- `TREASURY_INTERNAL`

Domestic external:

- `TREASURY_EXTERNAL`
- `SUPPLIER_SETTLEMENT`
- `LIQUIDITY_MANAGEMENT`
- `FINANCING_RELATIONSHIP`

International:

- `INTERNATIONAL_SUPPLIER`
- `INTERNATIONAL_CUSTOMER`
- `FOREIGN_TREASURY`

These categories are behavioral semantics, not deterministic rules.

---

## 6. Deterministic network generation

The draft uses the existing BTYT semantic RNG philosophy.

Relationship creation is keyed by stable entities such as:

```text
customer_id
source_account_id
scope
relationship_type
counterparty identifier
sequence
```

Relationship IDs use SHA-256-derived stable identifiers rather than Python `hash()`.

This matters because network generation must remain reproducible across:

- machines;
- interpreter sessions;
- chunk sizes;
- later performance optimizations.

A future V6 implementation may intentionally generate a different world from V5, but the same V6 seed must always reproduce the same V6 world.

---

## 7. Bounded scale

The draft intentionally avoids creating a dense customer-to-customer graph.

Each customer receives a bounded number of persistent relationships. This makes a 100k+ customer world feasible without producing millions of irrelevant all-to-all links.

The network is sparse by design:

```text
customer
  â”œâ”€â”€ a few internal counterparties
  â”œâ”€â”€ one or more domestic external relationships
  â”œâ”€â”€ possible IEDE relationship
  â””â”€â”€ sparse international relationships
```

Businesses receive broader networks on average than individuals.

---

## 8. Internal BTYT relationships

The draft supports two conceptually different internal regimes.

### Different-customer transfers

Examples:

```text
household/family
peer-to-peer
business partner
supplier/customer network
payroll/staff
```

### Same-customer transfers

Examples:

```text
OWN_ACCOUNT
TREASURY_INTERNAL
```

This is an intentional V6 change.

V5 currently excludes same-customer pairing during internal replay. Future V6 integration must therefore update that validation rule so same-customer transfers are permitted **only** when explicitly labeled as `OWN_ACCOUNT` or `TREASURY_INTERNAL`.

Same-account loops remain invalid.

---

## 9. Internal ledger semantics do not change

Persistent relationships do not bypass the ledger.

The correct future execution flow remains:

```text
persistent relationship
        â†“
transfer intent
        â†“
chronological monthly replay
        â†“
source balance check
        â†“
COMPLETED or FAILED
        â†“
if completed INTERNAL:
create exact opposite leg atomically
```

A completed internal pair must still satisfy:

```text
1 TRANSFER_OUT
1 TRANSFER_IN
same timestamp
equal amount
same currency
valid active accounts
no same-account loop
```

---

## 10. Domestic external relationships

V5 already models domestic institutions using the financial-institution dimension, including banks and IEDEs.

V6 adds persistence on top of that system.

Instead of selecting an external institution independently every time, a customer first develops a small set of institution relationships. Future transfer events then select among those relationships.

Conceptually:

```text
P(institution at t)
âˆ market structure
Ã— persistent customer relationship
Ã— customer segment
Ã— currency
Ã— amount
Ã— institution type
Ã— time / shock context
```

The current market and institution dimensions should remain the authoritative structural inputs.

---

## 11. IEDE behavior

IEDE relationships are modeled separately from traditional bank relationships.

Their probability can increase with:

- digital preference;
- individual-customer status;
- UYU usage;
- smaller-value flows;
- previous relationship persistence.

Their probability can decrease with:

- business-customer status;
- USD transfers;
- very large transfers.

Temporal institution activity remains mandatory: an institution cannot be used before `active_from` or after `active_to`.

---

## 12. International relationships

International links are intentionally sparse.

The draft makes them more likely when the customer:

- is a business;
- owns USD accounts;
- has stronger external-bank affinity.

This network layer should later be combined with the existing macro cross-border factor and bank-world affinities instead of replacing them.

International events remain a distinct behavioral regime.

---

## 13. Relationship lifecycle

Each relationship receives:

```text
start_date
end_date
recurrence_profile
relationship_strength
```

The first implementation uses probabilistic lifecycle boundaries while respecting the observable source-account interval.

Future versions may make relationships evolve dynamically:

```text
creation
  â†“
repeated successful use
  â†“
strengthening
  â†“
inactivity / shock / closure
  â†“
weakening or termination
```

The current draft creates the lifecycle once rather than mutating it after every transaction. This is intentional to keep the first V6 implementation testable and performant.

---

## 14. Relationship-aware event selection

The draft provides:

```python
resolve_persistent_transfer(...)
```

It performs the future equivalent of event-time counterparty resolution.

Candidate relationships are filtered by:

- source account or customer;
- currency;
- lifecycle date.

They are then weighted by:

```text
relationship_strength
Ã— recurrence profile
Ã— transfer size
Ã— scope
Ã— customer type
Ã— relationship type
```

The result is a `TransferResolution` object carrying:

```text
relationship_id
transfer_scope
counterparty_type
counterparty_customer_id
counterparty_account_id
counterparty_institution_id
relationship_type
preferred_channel
relationship_strength
```

---

## 15. Amount behavior

The draft includes:

```python
relationship_amount_multiplier(...)
```

Examples of intended behavior:

- peer-to-peer: smaller;
- household/family: moderate;
- own-account: larger than casual peer transfers;
- business supplier settlement: larger;
- treasury flows: larger still;
- remittances: intermediate;
- foreign treasury: large and concentrated.

This multiplier should eventually sit on top of the existing V5 amount model rather than replace customer scale, volatility, currency conversion, or rare-tail mechanics.

---

## 16. Channel behavior

The draft includes:

```python
relationship_channel_weights(...)
```

Channel probability responds to:

- preferred relationship channel;
- digital preference;
- customer type;
- transfer amount;
- recurrence.

Examples:

```text
small P2P             â†’ more MOBILE
business transfers    â†’ more WEB
recurring flows        â†’ more AUTOMATIC
very large transfers   â†’ more WEB / BRANCH
```

These remain probabilistic tendencies.

---

## 17. Future integration with `generate_transactions.py`

The current V5 engine contains several transfer-specific areas. V6 should be integrated deliberately rather than by replacing random blocks of code.

### Integration point A â€” startup

After customers, accounts, roles, traits, and `INSTITUTION_CONTEXT` exist:

```python
relationships = build_transfer_relationships(
    customers=d["customers"],
    accounts=accounts,
    roles=roles,
    institution_context=INSTITUTION_CONTEXT,
    obs_start=OBS_START.start_time,
    obs_end=OBS_END.end_time,
    currency_map=CURRENCY,
    rng_for=rng_for,
    customer_traits=traits,
    fixed_products=FIXED,
)

relationship_index = build_relationship_index(relationships)
```

Then write the relationship table to interim Parquet.

### Integration point B â€” transfer counterparty resolution

The V5 event-time logic currently relies on:

```text
counterparty(...)
resolve_transfer_institution(...)
```

For transfers only, V6 should instead call:

```python
resolution = resolve_persistent_transfer(...)
```

Non-transfer counterparties such as merchant, employer, government, loan account, and service provider can remain in the existing system.

### Integration point C â€” staging schema

Transfer intents should carry private staging metadata such as:

```text
_relationship_id
_counterparty_customer_id
_counterparty_account_id
_relationship_type
```

These fields can remain interim-only if the canonical transaction fact is kept compact.

### Integration point D â€” internal replay

The current V5 replay randomly selects an internal counterpart after staging.

V6 should stop doing that when `_counterparty_account_id` already exists.

Future logic:

```text
if persistent internal relationship exists:
    use relationship counterparty account
else:
    optional fallback to legacy pool selection
```

The exact two-leg replay mechanism remains unchanged.

### Integration point E â€” same-customer transfer validation

Update the V5 rule that currently treats every same-customer pair as invalid.

Future rule:

```text
same account       â†’ always invalid
same customer      â†’ valid only for OWN_ACCOUNT / TREASURY_INTERNAL
other internal     â†’ source and target customers must differ
```

---

## 18. Recommended migration strategy

Do **not** replace V5 all at once.

Recommended path:

### Phase 1 â€” network only

Generate and audit `customer_counterparty_relationships` without generating transactions.

Check:

- size;
- duplicate IDs;
- orphan accounts/customers/institutions;
- lifecycle dates;
- scope consistency;
- internal same-account loops;
- relationship counts by customer.

### Phase 2 â€” smoke integration

Use persistent relationships only for transfer counterparty selection in a very small world.

Keep V5:

- amount model;
- timing;
- channel;
- failure model;
- ledger replay.

### Phase 3 â€” internal network integration

Use explicit internal relationship target accounts during monthly replay.

Test exact atomic pairing.

### Phase 4 â€” behavioral depth

Add relationship-aware:

- amounts;
- channels;
- recurrence timing;
- failures.

### Phase 5 â€” performance and invariance

Profile only after semantics are stable.

Then optimize without changing V6 RNG keys or network semantics.

---

## 19. Structural audit implemented in `transfer.py`

The draft includes:

```python
audit_transfer_relationships(...)
```

Current checks include:

- duplicate relationship IDs;
- missing columns;
- unknown customers;
- unknown source accounts;
- invalid scopes;
- invalid recurrence profiles;
- non-positive relationship strength;
- missing start dates;
- end date before start date;
- missing internal counterpart customers/accounts;
- orphan internal counterpart customers/accounts;
- missing external institutions;
- orphan external institutions;
- internal same-account loops;
- same-customer transfers without an explicit own-account/treasury label.

Future integration must add transaction-to-relationship reconciliation audits.

---

## 20. Required transaction-level audits after integration

### Referential

- every `_relationship_id` exists;
- transaction customer/source account match relationship owner;
- counterparty account/institution matches relationship;
- transaction falls inside relationship lifecycle;
- transaction currency matches relationship currency.

### Internal pairing

- exactly two completed legs;
- one OUT and one IN;
- equal amount;
- equal timestamp;
- compatible currency;
- source and target match relationship;
- no same-account loop;
- same-customer only when relationship type allows it.

### Behavioral

- repeat-counterparty rate;
- median relationships per customer;
- counterparty concentration;
- one-off relationship share;
- transfers per relationship;
- relationship duration;
- institution switching;
- business vs individual recurrence;
- international concentration;
- channel distribution by relationship type.

These diagnostics should detect strange worlds rather than force arbitrary target percentages.

---

## 21. Performance design

The network is intended for tens of millions of transactions.

Important rules:

- precompute relationship indexes once;
- never filter the full relationship DataFrame per event;
- keep hot-path lookup account-local or customer-local;
- store lightweight records/dicts for selection;
- keep sequential ledger replay where balances require chronology;
- do not parallelize shared mutable ledger state naively;
- profile before introducing multiprocessing;
- preserve semantic RNG keys after V6 is frozen.

The main performance advantage of a persistent network is that expensive counterparty discovery moves from **every transfer event** to **bounded relationship creation**.

---

## 22. Graph analytics becomes a real downstream option

Once persistent relationships exist, the network can be interpreted as a graph.

Nodes:

```text
customers
accounts
institutions
```

Edges:

```text
persistent counterparty relationships
```

Possible future features:

- degree;
- weighted degree;
- counterparty concentration;
- connected components;
- centrality;
- community membership;
- new relationships in last 30/90 days;
- relationship churn;
- unusual connectivity changes.

These may later support fraud/anomaly work or graph-based ML, but are outside the first V6 integration.

---

## 23. Canonical schema decision

The first integration should **not** automatically add every network field to `transactions.parquet`.

Recommended canonical transaction columns to preserve:

```text
transaction_id
account_id
transaction_datetime
transaction_type
direction
channel
amount
counterparty_type
transfer_scope
counterparty_institution_id
transaction_branch_id
transaction_status
merchant_category
failure_reason
```

Relationship metadata can initially remain in staging/interim and be joined analytically through an optional relationship bridge.

A later schema version may add `relationship_id` canonically if its analytical value justifies a schema change.

---

## 24. What this draft does not claim

The current accepted BTYT world was generated with V5.0.0 EXACT FAST.

This V6 draft:

- has not regenerated BTYT-01;
- has not altered canonical transaction data;
- has not been distribution-tested;
- has not been benchmarked at 100k+ customers;
- has not been proven chunk-size invariant;
- has not been integrated into monthly ledger replay;
- has not replaced the accepted V5 engine.

Only the standalone module has been syntax-checked.

---

## 25. Proposed future version identity

When integrated and validated, this should become a semantic engine change rather than another `EXACT FAST` patch.

Recommended identity:

```text
Transactions V6.0.0 â€” Persistent Transfer Network
```

V6.0.0 should intentionally be treated as producing a new synthetic world relative to V5.

---

## 26. Portfolio value

This rework adds a much deeper modeling layer to BTYT:

```text
synthetic banking data
        +
chronological ledger
        +
persistent financial network
        +
behavioral recurrence
        +
financial-institution topology
        +
future graph analytics
```

The main gain is not simply â€œmore realistic random data.â€

It is a move from independent plausible records toward **longitudinal economic structure**.

> **A realistic synthetic bank is not only a collection of valid rows. It is a system in which relationships persist, behavior has memory, and accounting constraints remain exact.**
