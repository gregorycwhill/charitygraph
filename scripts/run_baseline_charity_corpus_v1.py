"""Run the private Baseline Charity Corpus v1 reality test.

Outputs are written only below ``C:\\CharityGraph-runtime`` (or ``--runtime``).
The script consumes retained Reality Slice bytes when present and records
missing/blocked sources explicitly; it never writes Data/Viewer artefacts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from charitygraph.baseline_corpus import (
    AcquisitionState, BindingState, CorpusMember, DiscoveryState, MaterialOrigin,
    RepresentationReadiness, build_corpus_manifest, enumerate_site_candidates,
    load_v05_cards, normalise_host, rank_site_candidates_with_luna, represent_pdf, sha256_json,
)
from charitygraph.contracts import BudgetCohort, Money
from charitygraph.evidence_store import ContentAddressedArtifactStore
from charitygraph.runtime import SQLiteCatalog
from charitygraph.openai_client import OpenAIRequestError


DEV_ABNS = ("28000030179", "50169561394", "20077830347", "22007498482", "15000002522", "28004778081", "46070556642")
HOLDOUTS = (("67649417658", "Landscape Recovery Foundation Ltd."), ("45146631843", "Indigenous Literacy Foundation Ltd."), ("15101252171", "Life Without Barriers"))
NAMES = {"28000030179": "The Smith Family", "50169561394": "Australian Red Cross Society", "20077830347": "Australian Communities Foundation Limited", "22007498482": "Australian Conservation Foundation Incorporated", "15000002522": "Mission Australia", "28004778081": "World Vision Australia", "46070556642": "The Fred Hollows Foundation"}
WEBSITES = {
    "28000030179": "https://www.thesmithfamily.com.au", "50169561394": "https://www.redcross.org.au",
    "20077830347": "https://www.communityfoundation.org.au", "22007498482": "https://www.acf.org.au",
    "15000002522": "https://www.missionaustralia.com.au", "28004778081": "https://www.worldvision.com.au",
    "46070556642": "https://www.hollows.org", "67649417658": "https://landscaperecovery.com.au",
    "45146631843": "https://www.ilf.org.au", "15101252171": "https://www.lwb.org.au",
}


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _find_object(roots: list[Path], digest: str) -> Path | None:
    for root in roots:
        if not root.exists():
            continue
        matches = list(root.rglob(digest))
        if matches:
            return matches[0]
    return None


def _load_retained(dev_path: Path, holdout_path: Path) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    if dev_path.exists():
        for row in json.loads(dev_path.read_text(encoding="utf-8")):
            result.setdefault(str(row.get("source", {}).get("member_abn", "")), []).append(row)
    if holdout_path.exists():
        frozen = json.loads(holdout_path.read_text(encoding="utf-8"))
        for abn, bundle in frozen.get("bundles", {}).items():
            for segment in bundle.get("source_segments", []):
                url = segment.get("source_url", "")
                family = "acnc_register" if "acnc.gov.au" in url else "ato_abr_dgr" if "abr.business.gov.au" in url else "acnc_ais_bundle" if "annualreport" in url or "annual-report" in url else "official_website"
                result.setdefault(str(abn), []).append({"source": {"member_abn": abn, "family": family, "url": url, "publisher": "retained Reality Slice source"}, "content_hash": segment.get("content_hash"), "artifact_id": segment.get("source_artifact_id"), "source_record_id": segment.get("evidence_id"), "status": "available", "byte_size": len(segment.get("text", "").encode("utf-8")), "retrieved_at": bundle.get("retrieved_at"), "_text": segment.get("text", "")})
    return result


def _reserve_catalogue(path: Path) -> tuple[SQLiteCatalog, str, str]:
    catalog = SQLiteCatalog(path).open(initialize=True)
    now = datetime.now(timezone.utc)
    cohort_id = "cohort:" + _hash("baseline-corpus-v1")[:32]
    run_id = "run:" + _hash("baseline-corpus-v1-run")[:32]
    cohort = BudgetCohort(record_id=cohort_id, producer={"kind":"code","producer_id":"baseline-corpus-v1","version":"1"}, cohort_code="SPIKE", definition_version="baseline-corpus-v1", ranking_metric="donor_decision_exposure_proxy", rank_start=1, rank_end=10, expected_member_count=10, membership_manifest_ref="private://baseline-corpus-v1/cohort.json", membership_hash=_hash("baseline-corpus-v1-members"), budget_cap=Money(amount="25", currency="AUD"), pooling="within_cohort_only", created_at=now)
    catalog.register_cohort(cohort)
    catalog.register_run({"record_id": run_id, "cohort_id": cohort_id, "run_kind": "cohort_build", "status": "running", "configuration_hash": _hash("baseline-corpus-v1"), "created_at": now})
    return catalog, cohort_id, run_id


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--runtime", type=Path, default=Path(r"C:\\CharityGraph-runtime\\baseline-corpus-v1-20260829")); parser.add_argument("--data", type=Path, default=Path(r"..\\charitygraph-data\\releases\\v0.5.0-2026-08-15\\cards")); parser.add_argument("--skip-luna", action="store_true")
    args = parser.parse_args(); runtime = args.runtime.resolve(); runtime.mkdir(parents=True, exist_ok=True)
    data_cards = args.data.resolve(); cards = {str(card["identity"].get("external_identifiers", [{}])[0].get("value")): card for card in load_v05_cards(data_cards)}
    dev_path = Path(r"C:\\CharityGraph-runtime\\reality-slice1-run8\\reality-slice1\\source-outcomes.json")
    holdout_path = Path(r"C:\\CharityGraph-runtime\\classie-4.2\\holdout-20260827\\acquisition\\frozen-manifest.json")
    retained = _load_retained(dev_path, holdout_path)
    subjects = [(abn, cards.get(abn, {}).get("identity", {}).get("display_name") or NAMES.get(abn) or abn, "development") for abn in DEV_ABNS] + [(abn, name, "holdout") for abn, name in HOLDOUTS]
    roots = [Path(r"C:\\CharityGraph-runtime\\reality-slice1-run8\\reality-slice1\\objects"), Path(r"C:\\CharityGraph-runtime\\classie-4.2\\holdout-20260827\\acquisition\\objects")]
    catalog, cohort_id, run_id = _reserve_catalogue(runtime / "ledger.sqlite3")
    derived_store = ContentAddressedArtifactStore(runtime / "objects", allowed_roots=(runtime,), catalog=None)
    manifests, matrix, rankings, repr_rows, all_hashes = [], [], {}, [], set()
    for abn, name, membership in subjects:
        rows = retained.get(abn, []); families: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            raw_family = str(row.get("source", {}).get("family", "unknown"))
            family = {"acnc": "acnc_register", "official-website": "official_website", "annual-report": "acnc_ais_bundle", "abr": "ato_abr_dgr", "ato-dgr": "ato_abr_dgr"}.get(raw_family, raw_family)
            families.setdefault(family, []).append(row)
        members: list[CorpusMember] = []; coverage: dict[str, Any] = {}
        for family in ("acnc_register", "acnc_ais_bundle", "ato_abr_dgr", "official_website", "wikipedia_wikimedia", "pfra"):
            source_rows = families.get(family) or ([r for r in rows if family == "ato_abr_dgr" and r.get("source", {}).get("family") in {"abr", "ato-dgr"}] if family == "ato_abr_dgr" else [])
            if source_rows:
                artifacts = tuple(str(r.get("artifact_id")) for r in source_rows if r.get("artifact_id")); hashes = tuple(str(r.get("content_hash")) for r in source_rows if r.get("content_hash")); all_hashes.update(hashes)
                source_records = tuple(str(r.get("source_record_id")) for r in source_rows if r.get("source_record_id"))
                representation_ids: list[str] = []; representation_gaps: list[str] = []
                for source_row in source_rows:
                    if str(source_row.get("media_type", "")) != "application/pdf": continue
                    pdf_path = _find_object(roots, str(source_row.get("content_hash", "")))
                    if not pdf_path: representation_gaps.append("source_bytes_not_found"); continue
                    try:
                        representation = represent_pdf(pdf_path)
                        derived = derived_store.put_derived(json.dumps(representation, ensure_ascii=False, sort_keys=True).encode("utf-8"), input_artifact_ids=(str(source_row.get("artifact_id")),), schema_id="urn:charitygraph:builder:baseline-pdf-representation:1.0", schema_version="1.0")
                        representation_ids.append(derived.artifact_id); representation_gaps.extend(str(item) for item in representation.get("page_gaps", []))
                        repr_rows.append({"abn": abn, "source_record_id": source_row.get("source_record_id"), "source_sha256": representation.get("source_sha256"), "readiness": representation.get("readiness"), "page_count": representation.get("page_count"), "native_text_pages": representation.get("native_text_pages"), "visual_escalations": representation.get("visual_escalations"), "page_gaps": representation.get("page_gaps", []), "derived_artifact_id": derived.artifact_id})
                    except Exception as exc:
                        repr_rows.append({"abn": abn, "source_record_id": source_row.get("source_record_id"), "readiness": "failed", "error": type(exc).__name__}); representation_gaps.append(type(exc).__name__)
                member_readiness = RepresentationReadiness.READY if representation_ids and not representation_gaps else RepresentationReadiness.PARTIAL if representation_ids else RepresentationReadiness.NOT_REQUIRED
                representation_ids = representation_ids
                representation_gaps = representation_gaps
                origin = MaterialOrigin.REUSED_EXISTING
                members.append(CorpusMember(source_family=family, source_definition_id="srcdef:" + _hash(f"{family}:{abn}")[:32], acquisition_receipt_ids=("acq:" + _hash(f"{family}:{abn}")[:32],), artifact_ids=artifacts, source_record_ids=source_records or ("srcrec:" + _hash(f"{family}:{abn}")[:32],), discovery=DiscoveryState.RESOLVED, acquisition=AcquisitionState.AVAILABLE, subject_binding=BindingState.BOUND, material_origin=origin, representation_readiness=member_readiness, representation_artifact_ids=tuple(representation_ids), representation_gaps=tuple(representation_gaps)))
                coverage[family] = {"discovery": "resolved", "acquisition": "available", "subject_binding": "bound", "material_origin": origin.value, "member_count": len(source_rows), "artifact_ids": artifacts}
            else:
                coverage[family] = {"discovery": "not_attempted" if family in {"wikipedia_wikimedia", "pfra"} else "unresolved", "acquisition": "unavailable", "subject_binding": "none", "material_origin": "none", "member_count": 0, "artifact_ids": ()}
        site_rows = families.get("official-website") or families.get("official_website") or []
        site_result = {"candidate_count": 0, "ranking": None, "top10": [], "status": "not_available"}
        if site_rows:
            chosen = site_rows[0]; path = _find_object(roots, str(chosen.get("content_hash", "")))
            if path:
                text = path.read_text(encoding="utf-8", errors="replace"); candidates = enumerate_site_candidates(text, WEBSITES[abn]); site_result["candidate_count"] = len(candidates); site_result["status"] = "enumerated"
                if not args.skip_luna and candidates:
                    try:
                        reservation_id = "reservation:" + _hash(f"site-ranking:{abn}")[:32]
                        catalog.reserve_cost({"record_id": reservation_id, "cohort_id": cohort_id, "run_id": run_id, "reserved_aud": {"amount": "1", "currency": "AUD"}, "model_task_ids": ()}, now=datetime.now(timezone.utc))
                        ranking = rank_site_candidates_with_luna(candidates, subject_name=name)
                        ranked = ranking["ranked_ordinals"]; site_result["ranking"] = ranking; site_result["top10"] = [candidates[i] for i in ranked[:10] if 0 <= i < len(candidates)] if not ranking.get("validation_error") else []
                        amount = ranking.get("cost_usd", "0")
                        catalog.record_cost_entry({"cohort_id": cohort_id, "run_id": run_id, "task_run_id": "taskrun:" + _hash(f"site-ranking:{abn}")[:32], "reservation_id": reservation_id, "pricing_snapshot_id": "pricing:" + "0" * 32, "fx_snapshot_id": "fx:" + "0" * 32, "entry_type": "actual", "paid_output_category": "relevance", "provider_cost": {"amount": amount, "currency": "USD"}, "aud_cost": {"amount": amount, "currency": "AUD"}, "usage": {"input_tokens": (ranking.get("usage", {}) or {}).get("input_tokens") or 0, "output_tokens": (ranking.get("usage", {}) or {}).get("output_tokens") or 0}, "recorded_at": datetime.now(timezone.utc)}, entry_key=f"actual:site-ranking:{abn}")
                    except (OpenAIRequestError, ValueError, OSError) as exc:
                        site_result["status"] = "ranking_failed:" + type(exc).__name__
        rankings[abn] = site_result
        manifest = build_corpus_manifest(subject_id=str(cards.get(abn, {}).get("causebase_id") or ("cb:" + _hash(abn)[:32])), profile_version="baseline-charity-corpus-v1", members=members, cohort_id=cohort_id, run_id=run_id, retrieval_timestamps=tuple(str(r.get("retrieved_at")) for r in rows if r.get("retrieved_at")), builder_commit="5e5656df635f6531b676e595ae41d4f5a8a523a5")
        manifests.append(manifest.model_dump(mode="json")); matrix.append({"abn": abn, "name": name, "cohort_membership": membership, "corpus_id": manifest.corpus_id, "coverage": coverage})
    report = {"version": "baseline-charity-corpus-v1", "private": True, "subjects": matrix, "corpora": manifests, "official_site_rankings": rankings, "pdf_representation": repr_rows, "aggregate": {"unique_artifact_count": len(all_hashes), "duplicate_reuse_count": sum(len(v) - len({r.get("content_hash") for r in v if r.get("content_hash")}) for v in retained.values()), "luna_calls": sum(1 for row in rankings.values() if row.get("ranking")), "provider": "gpt-5.6-luna", "semantic_extraction": False}}
    out = runtime / "baseline-corpus-v1-report.json"; out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"); (runtime / "baseline-corpus-v1-report.sha256").write_text(hashlib.sha256(out.read_bytes()).hexdigest(), encoding="ascii"); catalog.close(); print(json.dumps({"report": str(out), "sha256": hashlib.sha256(out.read_bytes()).hexdigest(), "subjects": len(subjects), "luna_calls": report["aggregate"]["luna_calls"]}, indent=2)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
