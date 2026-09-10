BTYT World Builder
==================

Canonical package:
    world_builder/

Run:
    python -m world_builder.app

Core configuration contract
---------------------------
The Builder deliberately separates its UI execution profile from BTYT Core:

Builder Full  -> execution.mode = "production"
Builder Smoke -> execution.mode = "development"

For a Smoke world with N customers:
    population.customers = N
    execution.smoke_customers = N

BTYT Core requires smoke_customers > 0 and smoke_customers <= the resolved
customer population.

Implemented Builder behavior
----------------------------
- deterministic world identity and seed;
- Full / Smoke profiles;
- real per-stage, selected-pipeline and whole-world progress;
- whole-world progress reserves 100% for verified/frozen state;
- existing-world state reconstruction;
- Resume World from the first incomplete safe stage;
- no generic Pause button;
- Stop Run with truthful checkpoint/restart semantics;
- explicit audit -> manifest -> verification -> frozen finalization;
- registered-world loading;
- destructive cleanup confirmation;
- canonical unversioned filenames.

Validation performed before packaging
-------------------------------------
- Python syntax compilation;
- AST parsing;
- static contract checks for execution.mode;
- static smoke-customer consistency checks;
- static finalization/manifest filename checks;
- no Pause control;
- canonical filenames only.

The full GUI + 15-stage engine integration still has to be proven by an actual
Smoke run inside the BTYT repository. No static check can honestly guarantee
that every runtime integration bug is absent.
