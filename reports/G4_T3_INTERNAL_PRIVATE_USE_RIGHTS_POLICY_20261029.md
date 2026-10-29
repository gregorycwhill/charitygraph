# Gate 4 T3 internal-private-use rights policy — 2026-10-29

## Outcome

Implemented a separate, versioned Product Owner project policy through the
clean rights-record and governed-preflight seams. Policy identity is
`CG_INTERNAL_PRIVATE_USE_RIGHTS_POLICY_V1` / `1.0.0`; it records the authority
actor, project-authority basis, local-private operation, all seven admitted
source families, provenance, and decision reference. It is not a third-party
licence and does not authorize provider processing or public redistribution.

The fixed five-subject, ten-row ACNC register/AIS cohort now has exact
source, receipt, subject/scope, representation, lineage and hash matches and
is **10/10 eligible for local-private preflight**. Provider processing remains
`blocked` without an independently verified provider contract ID/version;
public redistribution remains `not_assessed`; downstream/provider tasks,
requests and spend remain zero. The binding manifest fence is `v45`.

Explicit exclusion evidence lowers only the affected row; retained-byte hash
mismatch lowers that row without substitution; unknown source families,
missing authority/current projection and other identity mismatches fail closed.
The existing v29 projection was not schema-migrated. Record serialization,
store reload, projection rebuild/reload and two-root replay remain
deterministic.

## Verification

- Clean `git archive HEAD` overlay focused suite: **14 passed**.
- Clean rights-record serialization/store/projection suite: **18 passed, 1
  pre-existing committed compatibility failure**. The failure is the known
  clean-HEAD mismatch where the legacy `ArtifactRightsDecision` does not yet
  accept newer compatibility fields; the quarantined dirty `source_rights.py`
  and `tests/test_source_rights.py` were not imported or changed.
- No source acquisition, network/provider/model call, AUD spend, publication,
  release, durable catalog reload, or public projection occurred.
- SQLite/catalog state used only disposable OS-temporary test roots. No raw
  source bytes, prompts, model responses, credentials, caches or runtime state
  were added to the repository.

## Residual gaps

Provider contract authority and any future public-redistribution decision are
separate later steps. A durable production-catalog reload is also not
authorized by this task.
