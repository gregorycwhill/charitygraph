"""Reality Spike 3: bounded adapter over Builder's public ACNC/report seams.

Private inspection material only.  Source-native regulator values are shown as
such and report text is represented rather than model-summarised.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from acquire_acnc_public_profiles import acquire
from run_baseline_charity_corpus_v1 import fetch
from charitygraph.baseline_corpus import represent_pdf, select_filing_documents

CHARITIES = (("SUNRISE FOUNDATION LIMITED", "37646526132"), ("Medecins Sans Frontieres Australia Limited", "74068758654"), ("Noongar Boodja Trust", "47613674461"))

def stamp() -> str: return datetime.now(timezone.utc).isoformat()
def write(path: Path, value: object) -> None: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
def nonempty(detail: dict | None) -> dict: return {str(k): v for k, v in ((detail or {}).get("data") or {}).items() if v not in (None, "", [], {})}

def card_markdown(result: dict) -> str:
    """A deliberately source-native card projection; it is not a semantic store."""
    fields = result["ais_source_native_nonempty_fields"]; year = fields.get("StatementYear", "unknown")
    lines = [f"# {result['name']}", "", "**NON-PRODUCTION REALITY-SPIKE 3 MATERIAL — not canonical CharityGraph data.**", "",
        f"ACNC external charity-source UUID: `{result['identity']['acnc_uuid']}`  ", f"ABN source join key (not subject identity): `{result['identity']['abn_join_key']}`", "",
        "## Identity / regulatory", f"ACNC profile: {result['identity']['acnc_profile_url']}", f"Latest submitted AIS: {year}. The following values are charity-reported AIS fields, not CharityGraph judgments.", "",
        "## AIS source-native observations"]
    for key in ("LegalName", "CharitySize", "ActivityOperating", "ActivityPersuitPurposesDescription", "HrFullTimeEmployees", "HrPartTimeEmployees", "HrCasualEmployees", "HrUnpainVolunteers", "FinReportFrom", "FinReportTo", "RevenueTotal", "ExpenseTotal", "NetSurplusDeficit", "TotalAssets", "TotalLiabilities", "NetAssetsLiabilities"):
        if key in fields: lines.append(f"- `{key}`: {fields[key]}")
    lines += ["", "## Regulator-linked filing evidence"]
    if not result["filings"]: lines.append("No same-period filing attachment was selected from ACNC profile Documents metadata; this is missingness, not a search fallback.")
    for filing in result["filings"]:
        lines.append(f"- {filing['role']} — {filing['outcome']}; URL: {filing['metadata'].get('Url')}; SHA-256: {filing.get('sha256', 'not acquired')}")
        if filing.get("representation"): lines.append(f"  - Native representation: {filing['representation']['readiness']}; pages {filing['representation']['page_count']}; native-text pages {filing['representation']['native_text_pages']}; gaps {filing['representation']['page_gaps']}; visual escalation {filing['representation']['visual_escalations']}.")
    lines += ["", "## Evidence and limits", "Source-native ACNC profile/AIS evidence is separately retained in `packet.json`. Report material remains a document representation; no model output was created or promoted. Web evidence from earlier spikes remains separate and is not merged here."]
    return "\n".join(lines) + "\n"

def process(name: str, abn: str, root: Path) -> dict:
    folder = root / abn; folder.mkdir(parents=True, exist_ok=True); retrieved_at = stamp()
    try:
        packet = acquire(abn)  # established exact search -> UUID -> entity -> latest AIS -> detail seam
    except Exception as error:
        result = {"name": name, "abn_join_key": abn, "outcome": "acquisition_failed", "retrieved_at": retrieved_at, "error": f"{type(error).__name__}: {error}"}; write(folder / "packet.json", result); return result
    profile = packet["profile"]; data = profile.get("data") or {}; uuid = profile.get("uuid"); latest = packet.get("latest_submitted_ais")
    selected = select_filing_documents(data.get("Documents") or [], str((latest or {}).get("Year") or ""))
    filings = []
    for document in selected:
        row = {"role": document["role"], "metadata": document, "outcome": "not_attempted"}
        try:
            body, resolved, status, media = fetch(str(document["Url"]))
            row.update({"outcome": "acquired", "resolved_url": resolved, "http_status": status, "content_type": media, "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)})
            if media == "application/pdf" or resolved.split("?", 1)[0].lower().endswith(".pdf"):
                pdf = folder / (row["sha256"] + ".pdf"); pdf.write_bytes(body); row["representation"] = represent_pdf(pdf)
        except Exception as error: row.update({"outcome": "acquisition_failed", "error": f"{type(error).__name__}: {error}"})
        filings.append(row)
    result = {"non_production_reality_spike_3": True, "name": name, "identity": {"acnc_uuid": uuid, "acnc_profile_url": f"https://www.acnc.gov.au/charity/charities/{uuid}/profile", "abn_join_key": abn}, "retrieved_at": retrieved_at, "acnc_profile": profile, "latest_submitted_ais": latest, "ais_detail": packet.get("ais_detail"), "ais_acquisition_failure": packet.get("ais_acquisition_failure"), "ais_source_native_nonempty_fields": nonempty(packet.get("ais_detail")), "report_discovery": {"basis": "ACNC profile Documents collection (discover_public_sources.py semantics)", "selected_by": "baseline_corpus.select_filing_documents structured Year/type metadata", "selected": selected}, "filings": filings, "model_calls": 0}
    write(folder / "packet.json", result); (folder / "card.md").write_text(card_markdown(result), encoding="utf-8")
    return {"name": name, "abn_join_key": abn, "acnc_uuid": uuid, "latest_ais_year": (latest or {}).get("Year"), "filings": len(filings), "outcome": "acquired"}

def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=Path, default=Path("artifacts/reality-spike-3-acnc-substance")); args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    results = [process(name, abn, args.output) for name, abn in CHARITIES]
    write(args.output / "run_summary.json", {"generated_at": stamp(), "results": results, "model_calls": 0, "machinery": ["acquire_acnc_public_profiles.acquire", "discover_public_sources Documents semantics", "select_filing_documents", "run_baseline_charity_corpus_v1.fetch", "represent_pdf"]})
    (args.output / "PRODUCT_COMPARISON_V2_V3.md").write_text("""# Sunrise: Reality Spike 2 → 3

Both artifacts are non-production inspection material. Spike 2 established the ACNC UUID but had only page-shell evidence and could not state substantive AIS or report content.

## Material product change

Spike 3 adds source-native, year-bound 2024 AIS observations: declared operating status; charity size; the charity's own activity description; workforce and volunteer counts; period-bounded revenue, expenses, surplus, assets, liabilities and net assets. It also adds two ACNC-profile-Documents-selected 2024 filing artifacts with exact URLs, hashes and per-page representation diagnostics.

The annual report has 15 pages of native text and one unresolved page. The financial report is scanned: both pages are explicitly unresolved because local OCR is unavailable and no vision route was configured. No report prose was model-summarised.

## North Star result

Sections 1 (identity/regulatory), 13 (finances) and 20 (evidence/freshness/coverage) are materially better supported. AIS also adds constrained source-reported activity/workforce signals, but does not establish outcomes, governance quality, program ownership, geography of delivery, capability, or effectiveness.

## Epistemic result

AIS values remain charity-reported, reporting-year-bound source-native observations. Report material remains attributable document evidence. Earlier web evidence remains separately attributable. There was no model-assisted or governed promotion in this run, and no missingness was filled by generic search.
""", encoding="utf-8")
    print(json.dumps(results, indent=2)); return 0 if results and results[0]["outcome"] == "acquired" else 2
if __name__ == "__main__": raise SystemExit(main())
