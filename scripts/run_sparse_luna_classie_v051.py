"""Rerun Sparse Luna + private CLASSIE using the frozen v0.5 corpus only."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from charitygraph.baseline_corpus import build_corpus_manifest
from charitygraph.evidence_store import ContentAddressedArtifactStore
from charitygraph.openai_client import estimate_response_cost, responses_create
from charitygraph.runtime import SQLiteCatalog
from charitygraph.whole_card_semantic_v02 import STRICT_SCHEMA, validate_output
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.run_sparse_luna_classie_v05 import (
    CAP_USD, CLASSIE_MAX, MODEL, WHOLE_MAX, build_classie_schema,
    build_taxonomy_blind_view, call_luna, dump, source_packet,
)

RUNTIME = Path(r"C:\CharityGraph-runtime\sparse-luna-classie-v05-20260830T")
CATALOG = Path(r"C:\CharityGraph-runtime\state\charitygraph.sqlite3")
TAXONOMY = Path(r"C:\CharityGraph-runtime\classie-4.2\classie-subject-4.2-private.json")


def main() -> int:
    runtime = RUNTIME / "v051"; runtime.mkdir(parents=True, exist_ok=True)
    corpus = json.loads((RUNTIME / "corpus-manifest.json").read_text(encoding="utf-8"))
    catalog = SQLiteCatalog(CATALOG).open(initialize=True)
    store = ContentAddressedArtifactStore(RUNTIME / "objects", allowed_roots=(RUNTIME,), catalog=catalog)
    members = [__import__("charitygraph.baseline_corpus", fromlist=["CorpusMember"]).CorpusMember.model_validate(m) for m in corpus["material_members"]]
    diagnostics: list[dict] = []
    packet = source_packet(catalog, store, members, diagnostics)
    packet.update({"packet_version": "sparse-charity-semantic-v05.1", "corpus_id": corpus["corpus_id"], "material_identity_hash": corpus["material_identity_hash"], "subject": {"subject_id": corpus["subject_id"], "name": "TWEED REGIONAL GALLERY FOUNDATION LIMITED", "abn": "29003230073"}})
    packet_sha = dump(runtime / "whole-card-packet.json", packet)
    dump(runtime / "source-representation-diagnostics.json", diagnostics)
    if any(d["placeholder"] and d["representation_gap"] for d in diagnostics):
        raise RuntimeError("substantive source has placeholder representation; failed closed before provider use")
    prompt = (Path(__file__).with_name("whole_card_semantic_calibration_v02_prompt.txt").read_text(encoding="utf-8") + "\n\nFROZEN PACKET:\n" + json.dumps(packet, ensure_ascii=False, separators=(",", ":")))
    events: list[dict] = []; spent = Decimal("0")
    whole, actual, whole_text = call_luna(prompt, STRICT_SCHEMA, "sparse_whole_card_v051", WHOLE_MAX, spent, events); spent += actual
    dump(runtime / "whole-card-raw.json", whole); (runtime / "whole-card-output-text.txt").write_text(whole_text, encoding="utf-8")
    try: validate_output(whole, packet); whole_valid = True
    except Exception as exc: whole_valid = False; dump(runtime / "whole-card-validation.json", {"error": str(exc)})
    if whole_valid: dump(runtime / "whole-card-validation.json", {"status": "passed"})
    blind = build_taxonomy_blind_view(whole); blind_sha = dump(runtime / "classie-blind-knowledge-view.json", blind)
    if not TAXONOMY.is_file(): raise RuntimeError("private CLASSIE taxonomy unavailable; failed closed")
    taxonomy = json.loads(TAXONOMY.read_text(encoding="utf-8")); concept_ids = {str(c.get("concept_id") or c.get("id")) for c in taxonomy.get("concepts", [])}
    classie_prompt = "Infer CharityGraph CLASSIE assignments from this taxonomy-blind knowledge using only the supplied private taxonomy and observations. Return only the strict schema; do not use outside knowledge, ACNC CLASSIE, SDG or CharityGraph Native.\n" + json.dumps({"knowledge": blind, "taxonomy": taxonomy}, ensure_ascii=False, separators=(",", ":"))
    try:
        classie, actual, classie_text = call_luna(classie_prompt, build_classie_schema(), "sparse_classie_v051", CLASSIE_MAX, spent, events); spent += actual
    except Exception as exc:
        # Persist only sanitised failure metadata; never retry or fabricate a
        # CLASSIE result after a paid/transport failure.
        dump(runtime / "classie-error.json", {"error_class": type(exc).__name__, "error": str(exc)[:240], "events": events, "provider_calls": 2})
        catalog.close()
        raise
    dump(runtime / "classie-raw.json", classie); (runtime / "classie-output-text.txt").write_text(classie_text, encoding="utf-8")
    cg_ids = {str(a.get("concept_id")) for a in classie.get("assignments", [])}; valid_refs = set(blind["observation_refs"])
    unresolved = [r.get("observation_ref") for a in classie.get("assignments", []) for r in a.get("supporting_observations", []) if r.get("observation_ref") not in valid_refs]
    unknown = sorted(cg_ids - concept_ids)
    dump(runtime / "classie-validation.json", {"status": "passed" if not unresolved and not unknown else "failed", "unknown_concepts": unknown, "unresolved_observation_refs": unresolved})
    # ACNC CLASSIE extraction remains source-native/mechanical; this frozen corpus has no such field.
    acnc_ids: set[str] = set()
    dump(runtime / "comparison.json", {"exact_agreement": [], "cg_only": sorted(cg_ids), "acnc_only": [], "comparison_basis": "exact concept IDs only", "limitation": "no structured ACNC CLASSIE assignment field in frozen source records"})
    report = {"version": "sparse-luna-classie-v05.1", "private": True, "corpus_id": corpus["corpus_id"], "corpus_sha256": hashlib.sha256((RUNTIME / "corpus-manifest.json").read_bytes()).hexdigest(), "packet_sha256": packet_sha, "source_representation_diagnostics": diagnostics, "whole_card": {"valid": whole_valid, "observations": len(whole.get("observations", [])), "sections_with_evidence": sorted({o.get("section_id") for o in whole.get("observations", [])})}, "classie_blind_sha256": blind_sha, "classie_assignments": len(cg_ids), "acnc_assignments": len(acnc_ids), "provider_events": events, "total_cost_usd": f"{spent:.6f}", "provider_calls": 2, "source_acquisition": 0}
    dump(runtime / "run-report.json", report); catalog.close(); print(json.dumps({"runtime": str(runtime), "packet_sha256": packet_sha, "total_cost_usd": f"{spent:.6f}", "provider_calls": 2}, indent=2)); return 0


if __name__ == "__main__": raise SystemExit(main())
