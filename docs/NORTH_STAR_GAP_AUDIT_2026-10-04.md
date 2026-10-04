# North Star gap audit — 2026-10-04

**Status:** Local implementation audit; not product authority or an execution
authorisation.  It maps the 20-section planning anchor onto the Attempt 21
Builder checkout and its contract tests.  It does not claim that a record type,
historical experiment, or empty projection cell proves live coverage.

## Method and boundaries

Starting Builder identity: `228066e00bc7dec07a00ddcd45fed07372f0bda7`
(`s0-attempt21-successor-builder`).  The audit worktree is a clean local branch
from that commit.  Evidence reviewed: `AGENTS.md`, `BUILDER_MACHINERY.md`,
`ARCHITECTURE.md`, `integrated_card.py`, `north_star_projection.py`, and the
section-contract suites.  The sibling Data `DOCUMENT_AUTHORITY.md` and
`INTEGRATED_PRODUCT_AND_DATA_MODEL.md` remain controlling for product meaning.

“Supported” below means a typed representation/projection or tested bounded
path exists.  It does not mean national coverage, current evidence, automatic
promotion, or authority to acquire/search/call a provider.  “Semantic/authority
gap” means the omitted work needs a domain policy, governed evidence universe,
review rule, or authorised model/source operation; it must not be filled by
Python prose heuristics.

| # | North Star section | Evidence-backed current support | Honest gap / disposition |
|---:|---|---|---|
| 1 | Identity & regulatory | Durable subjects, authoritative-ID binding, lifecycle and coverage envelopes (`ARCHITECTURE.md`; `contracts/knowledge.py`) | Registry breadth and live freshness are acquisition/authority work. |
| 2 | Purpose, mandate & cause | Typed observations and source-native/semantic candidate separation; card projection | Current-vs-legal-purpose interpretation remains governed semantic work. |
| 3 | Programs, services, projects & campaigns | Native discovery contract and section 3 reprojection tests | Expansion requires governed evidence and model/review authority. |
| 4 | Populations & beneficiaries | Scoped observations and section 3/6/11 reprojection tests preserve distinction | Population-role extraction is semantic/domain-policy work. |
| 5 | Geography | Scoped observation projection and section 3/6/11 tests | Geographic role/edition coverage needs source and scheme authority. |
| 6 | Participation | `ParticipationObservation`; section 3/6/11 tests | Discovery and role interpretation remain semantic. |
| 7 | Fundraising & mobilisation | Section 7 reprojection contract; architecture separates practice, campaign and expenditure | Practice extraction/coverage is not authorised by a projection schema alone. |
| 8 | Finance & resource flows | Source-faithful financial records/metrics; section 13 finance reprojection tests | New financial interpretation and reconciliation require applicable source policy. |
| 9 | Governance | Shared observation, scope and relationship primitives | No settled specialised extraction/promotion path found; semantic/domain authority gap. |
| 10 | Workforce | Aggregate observation/projection support; section 3/6/11 tests | Workforce interpretation and source scope remain semantic/authority work. |
| 11 | Capability, capacity, access & availability | Typed direct-service/capacity distinction; section 3/6/11 tests | Coverage expansion requires semantic evidence processing. |
| 12 | Relationships & ecosystem | Directed typed relationships, role/scope invariants, specialist relationship tests | Relationship candidate extraction and review policy are separate governed work. |
| 13 | Memberships, schemes, registrations & accreditations | Scheme/classification primitives and section 13 reprojection tests | Scheme-specific authority/rights and extraction remain unresolved by design. |
| 14 | Ethos & institutional identity | Section 14 reprojection tests and explicit architecture separation from service orientation | Ethos interpretation needs evidence/review authority. |
| 15 | Positions, commitments & implementation | Shared typed observation/provenance envelope | No settled specialised promotion contract found; semantic/authority gap. |
| 16 | Conduct, adverse matters & compliance | Correction, status and provenance architecture | High-consequence source/review rules are a product authority question. |
| 17 | Notable context & institutional history | Neutral `notable_context` architecture rule and projection support | Selection/interpretation requires explicit scope and review. |
| 18 | Outcomes, impact & evaluation | Typed observation/evidence model and specialist section tests | Evaluation-method semantics and causal claims need domain authority. |
| 19 | Classifications & semantic lenses | Separate classifications, mappings and source-vs-assessed rule | Scheme rights, mapping and assessment policy remain controlling gaps. |
| 20 | Evidence, coverage, freshness & corrections | Explicit missingness/coverage matrix, provenance fields and correction architecture | Live coverage/freshness needs actual governed evidence processing. |

## Mechanical repair made in this audit

`NorthStarLensOutput` and `NorthStarLensOutputVNext` now reject duplicate
`observation_key` assignments at model validation.  Previously the retained
runner detected duplicates after parsing, but another caller could validate an
ambiguous response and choose an assignment accidentally.  The repair changes
no section semantics, sources, provider boundary, policy, or public contract.

## Verification and ending state

- `python -m pytest tests/contracts/test_north_star_projection.py
  tests/contracts/test_integrated_card.py
  tests/contracts/test_section3_6_11_reprojection.py
  tests/contracts/test_section7_reprojection.py
  tests/contracts/test_section13_finance_reprojection.py
  tests/contracts/test_section14_reprojection.py
  tests/contracts/test_section_c5_reprojection.py
  tests/contracts/test_section_specialist_reprojection.py -q` — **110 passed**.
- `git diff --check` — passed before commit.
- A broad `python -m pytest -q` run was not a code failure: it first stopped at
  a `PermissionError` opening the host-owned shared pytest base directory.
  Re-runs with worktree-local `--basetemp` progressed past that point but did
  not yield a terminal result in the executor and were terminated before any
  provider boundary.  Their local-only SQLite test artefacts were removed.

Ending state is the clean local branch `cg-s0-northstar-gap-audit-286`, with
one audit commit on top of the stated Attempt 21 base.  No authenticated GitHub,
provider/source call, live S0 action, or reset-credit action occurred.

## Remaining boundaries

No additional safe mechanical omission was found in the section projection
contracts.  The dominant gaps are deliberately non-mechanical: source-rights
and acquisition scope, model-task authorisation, domain-specific promotion and
review policy, and evidence-backed coverage execution.  No provider, source,
live S0, authenticated GitHub, or reset-credit action was performed.
