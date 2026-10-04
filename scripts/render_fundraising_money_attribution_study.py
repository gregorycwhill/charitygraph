"""Render and mechanically validate the research-only attribution-grain table."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "research" / "fundraising_money_attribution_grain_v1.json"
OUTPUT = ROOT / "docs" / "research" / "FUNDRAISING_MONEY_ATTRIBUTION_GRAIN_STUDY_V1.md"
REQUIRED = {"source", "subject", "period", "metric", "amount", "smallest_justified_scope", "attribution_evidence", "incompatibilities", "missingness", "locator"}


def validate(study: dict) -> None:
    cases = study["cases"]
    assert len(cases) == study["case_count"]
    assert len({case["id"] for case in cases}) == len(cases)
    allowed = set(study["scope_order"])
    for case in cases:
        missing = REQUIRED - set(case)
        assert not missing, f"{case['id']}: missing {sorted(missing)}"
        assert case["smallest_justified_scope"] in allowed
        assert case["locator"]
        # An incompatibility must state what cannot be inferred; a scope is not
        # silently treated as a downstream allocation.
        assert any(token in case["incompatibilities"].lower() for token in ("not", "infer"))
        if case["amount"] is None:
            assert case["amount_status"]
        # The table must be able to name a prohibited inference in order to
        # reject it.  Prohibited metrics therefore belong only in the explicit
        # incompatibility field, never in the source-native metric field.
        metric = case["metric"].lower()
        assert not any(term in metric for term in ("roi", "cost-to-raise", "cost to raise", "profitability"))


def render(study: dict) -> str:
    counts = Counter(case["smallest_justified_scope"] for case in study["cases"])
    lines = [
        "# Fundraising money-attribution grain study v1", "",
        "**Status:** research-only, reproducible evidence study; not production ingestion.", "",
        f"As at {study['as_of']}, this retained/local-public cohort has **{study['case_count']}** cases. "
        f"Target was {study['target_case_count']}; shortfall: {study['cohort_shortfall']}", "",
        "## Finding", "",
        "The evidence supports money observations most often at organisation or fundraising-portfolio grain. "
        "Appeal- and provider-relationship grain are strongly supported as record-keeping/reporting possibilities by NSW rules, but no retained public charity return supplies a reusable amount. "
        "Campaign-platform/benchmark sources can support campaign-reported amounts only when the named row, metric definition and subject binding are retained. No aggregate total may be allocated downward merely because a practice/campaign/provider is also observed.", "",
        "| Smallest justified scope | Cases | Interpretation |", "|---|---:|---|",
    ]
    labels = {"organisation":"common in retained financial statements", "fundraising_portfolio":"common enough for direct/functional total only", "standing_practice_or_channel":"rare for money; PFRA supports practice evidence, not amount", "campaign":"possible but unsupported in frozen cohort without a retained benchmark row", "appeal":"regulator-required/possible, no retained public amount", "provider_relationship":"possible operational record, no retained attributed amount"}
    lines.extend(f"| {scope} | {counts[scope]} | {labels[scope]} |" for scope in study["scope_order"])
    lines += ["", "## Case table", "", "| ID | Source / subject / period | Source-native metric and amount | Smallest justified scope | Attribution evidence | Incompatibilities and missingness |", "|---|---|---|---|---|---|"]
    for c in study["cases"]:
        left = f"{c['source']}<br>{c['subject']}<br>{c['period']}"
        metric = f"{c['metric']}<br>{c['amount'] if c['amount'] is not None else 'Amount unavailable'} ({c['amount_status']})"
        right = f"{c['incompatibilities']}<br>Missing: {c['missingness']}<br>Locator: {c['locator']}"
        lines.append(f"| {c['id']} | {left} | {metric} | {c['smallest_justified_scope']} | {c['attribution_evidence']} | {right} |")
    lines += ["", "## Concrete negative cases", "", "- **c14:** a source-native mixed `Donations, Fundraisings, Lectures` row is organisation-level only; splitting it changes the source claim.", "- **c15:** a direct fundraising functional allocation (and its mechanical approximate amount) is a portfolio total; observed channels/campaigns do not establish components or additivity.", "- **c04/c07:** a trader rule or provider directory does not evidence a charity-provider contract, much less a share of income or expenditure.", "- **c16:** even explicit expense labels can support a bounded portfolio construct in a test fixture without identifying channels; it is deliberately non-publishable.", "", "## Reproduction", "", "Run `python scripts/render_fundraising_money_attribution_study.py`. The script validates required evidence fields, scope vocabulary, locator presence, null-money explanations and absence of prohibited performance language, then rewrites this report deterministically."]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    study = json.loads(INPUT.read_text(encoding="utf-8"))
    validate(study)
    OUTPUT.write_text(render(study), encoding="utf-8")
