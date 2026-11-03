# Experimental durable proposition envelope v0

**Status: proposed experimental envelope only — explicitly non-canonical.** It is an evidence-led shape for future testing, not a migration plan or provenance subsystem design.

## Unit

One attributable assertion of a normalised predicate/value about an identified subject, qualified by the scope and time needed to prevent a different meaning. Evidence supports the assertion; coverage is separate.

```json
{
  "proposition_id": "experimental-stable-id",
  "subject_ref": "entity-or-programme-reference",
  "predicate": "controlled-predicate",
  "value": {"kind": "typed-or-text", "data": "normalised-value-or-null"},
  "scope": {"level": "organisation|programme|site|population|unspecified", "ref": "optional-reference", "text": "optional-boundary"},
  "valid_time": {"start": "optional-ISO-date", "end": "optional-ISO-date", "precision": "day|month|year|period|unknown"},
  "assertion_mode": "reported|observed|derived",
  "status": "candidate|promoted|abstain|withdrawn",
  "evidence_refs": ["retained-evidence-reference"],
  "source_role": "first_party_report|regulator_record|other",
  "domain_semantics": {"optional": "discriminated, bounded qualifier"}
}
```

### Genuinely universal fields

`proposition_id`, `subject_ref`, `predicate`, `value` (including explicit null only where the predicate permits it), `scope`, `valid_time`, `assertion_mode`, `status`, `evidence_refs`, and `source_role` are the minimum universal set tested. Scope and time must be present as objects even when their content is `unspecified`/`unknown`; absence would collapse an important distinction. `domain_semantics` is optional and discriminated, not universal.

Not universal: routing, card wording, confidence score, section IDs, duplicate group, reviewer notes, retrieval time, parser details, and correction mechanics. Those may live in workflow/projection/relation layers.

## Separate companions

```json
{
  "coverage_observation": {
    "subject_ref": "entity-reference",
    "projection_domain": "outcomes|governance|capacity|...",
    "state": "not_processed|no_compatible_retained_evidence|withheld|examined_no_assertion",
    "evidence_boundary_refs": ["packet-or-run-reference"],
    "as_of": "optional-date"
  }
}
```

`candidate_duplicate_of`, `supports`, `contradicts`, `supersedes`, and `corrects` are reviewable relations, not base fields. A `contradicts` relation is eligible only when subject/predicate match and scope/time overlap enough for the values to be incompatible. `supersedes` additionally requires an explicit correction/replacement basis; chronology alone does not create it.
