# Development

## First local setup

From this repository in VS Code:

```powershell
uv sync --extra dev
```

Then:

```powershell
uv run pytest
```

Build the credential-free vertical slice:

```powershell
uv run charitygraph demo-build --output ..\..\work\staging\publication\demo
```

For constrained environments without `pyarrow` only:

```powershell
uv run charitygraph demo-build --allow-missing-parquet
```

Whether missing Parquet blocks a release is explicit release policy. The synthetic fixture may use this switch; no real-release policy has been frozen before the reality spike.

## Intended Codex loop

A useful default instruction is:

> Implement the change, run the narrowest relevant tests, run the fixture build, inspect the generated diagnostics, and keep iterating until the tests and fixture publication validation pass.

## Phase-5 delivery policy

Build and calibration execution uses the explicit `DeliveryPolicy.build()`
policy. Semantic work defaults to Standard delivery; Batch is disabled and an
explicit Batch request fails closed with `DeliveryPolicyError`. Flex is never
selected as a new default. A reviewed fake transport harness may opt into
`DeliveryPolicy.build(reviewed_batch_override=True)` to exercise the existing
Batch control plane without changing build defaults.

Production planning uses `DeliveryPolicy.production()`, which enables Batch
for bulk work. Production Batch remains asynchronous: submission persists the
provider file and Batch identities and returns; bounded reconciliation is a
separate operation. The OpenAI Batch transport and historical Batch runs are
retained and are not rewritten by the build-phase policy.

The initial slice contains no live ACNC, PDF, web or OpenAI integration. Add those behind explicit source/provider interfaces rather than embedding external calls throughout the pipeline. Start with the bounded 30–50 subject reality spike, not national-scale implementation.
