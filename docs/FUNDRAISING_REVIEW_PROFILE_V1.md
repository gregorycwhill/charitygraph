# Fundraising review profile v1

**Status:** implemented review-only capability slice

**Contract:** `fundraising-review-profile-v1`

This projection lets a consumer inspect, for a small representative review set:

- standing practices and their lifecycle/currentness;
- named campaigns or appeals and their bounded scope;
- explicitly evidenced provider relationships only;
- source-native money facts with period, accounting scope, and linkage status; and
- coverage states that distinguish scoped non-findings, not-yet-processed material, unavailable amounts, and unknowns.

The input fixture is a governed cached review fixture, not production acquisition
or a public release.  It contains four deliberately contrasting cases and uses
opaque review subject IDs rather than asserting a production identity.  The
renderer canonicalises JSON before hashing, so the fixture, hash, JSON, Markdown,
and manifest can be reproduced with:

```powershell
$env:PYTHONPATH='src'
python scripts/render_fundraising_review_profile.py
```

The resulting local artifact is under `artifacts/fundraising-review/` and is
intentionally excluded from Git as a generated review projection.

## Consumer reading rules

An `unknown` money linkage means that the fact remains at the reporting
organisation and is rendered as **organisation (not attributed)**. It is not
allocated to a practice, campaign, appeal, or provider merely because those
facts happen to appear in the same review profile. A `not_found_in_scoped_source`
coverage state is bounded to its displayed scope and is not evidence that the
organisation does not use a practice.

The slice never calculates or displays fundraising performance or causal claims.
It does not assert setting, external agency, compensation, recurring giving, or
organisation-wide continuity from generic F2F evidence. It is a capability
demonstration, not completion of the fundraising, relationships, finance, or
evidence/freshness product areas.
