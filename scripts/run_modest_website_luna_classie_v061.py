"""Private v0.6.1 scope/blindness correction run.

The frozen v0.6 packet is projected mechanically to remove only ACNC
source-native external-taxonomy fields.  No source is reacquired and no
semantic Python filtering is performed.
"""
from __future__ import annotations

import copy
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from charitygraph.openai_client import estimate_response_cost  # noqa: E402
from charitygraph.whole_card_semantic_v02 import STRICT_SCHEMA, validate_output  # noqa: E402
from scripts.run_modest_website_luna_classie_v06 import (  # noqa: E402
    CAP, build_classie_schema, build_taxonomy_blind_view, call_luna, now, sha,
)

RUNTIME = Path(r"C:\CharityGraph-runtime\modest-website-luna-classie-v061-20260831T")
FROZEN = Path(r"C:\CharityGraph-runtime\modest-website-luna-classie-v06-20260831T")


def write_json(path: Path, value: object) -> str:
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path.write_bytes(data)
    return sha(data)


def project_external_taxonomy(value: dict) -> tuple[dict, list[str]]:
    """Drop only source-native ACNC classification fields, recursively."""
    removed: list[str] = []
    keys = {"ProgramClassification", "ProgramClassificationID", "ProgramClassie", "CLASSIE", "Classifications"}

    def walk(node: object, path: str) -> object:
        if isinstance(node, dict):
            out = {}
            for key, child in node.items():
                if key in keys or "classie" in key.casefold():
                    removed.append(f"{path}/{key}")
                    continue
                out[key] = walk(child, f"{path}/{key}")
            return out
        if isinstance(node, list):
            return [walk(child, f"{path}[{idx}]") for idx, child in enumerate(node)]
        return node

    return walk(copy.deepcopy(value), "") , removed


def projected_packet(packet: dict) -> tuple[dict, list[str], set[str]]:
    out = copy.deepcopy(packet)
    removed: list[str] = []
    acnc_ids: set[str] = set()
    for source in out.get("sources", []):
        if source.get("source_family", "").startswith("acnc"):
            original = next((s for s in packet.get("sources", []) if s.get("source_key") == source.get("source_key")), None)
            if original:
                try:
                    raw = json.loads("\n".join(item["text"] for item in original.get("locators", [])))
                    def collect(node: object) -> None:
                        if isinstance(node, dict):
                            # ProgramClassificationID is source-defined as the
                            # selected assignment.  ProgramClassie parents are
                            # context unless the item explicitly says selected=true.
                            selected_id = node.get("ProgramClassificationID")
                            if selected_id:
                                acnc_ids.add(str(selected_id))
                            items = node.get("ProgramClassie")
                            if isinstance(items, list):
                                for item in items:
                                    if isinstance(item, dict) and item.get("selected") is True:
                                        val = item.get("classie_id") or item.get("concept_id") or item.get("id")
                                        if val: acnc_ids.add(str(val))
                            for k, v in node.items():
                                if k not in {"ProgramClassie", "ProgramClassificationID"}:
                                    collect(v)
                        elif isinstance(node, list):
                            for item in node: collect(item)
                    collect(raw)
                    clean, paths = project_external_taxonomy(raw); removed.extend(f"{source['source_key']}{p}" for p in paths)
                    text = json.dumps(clean, ensure_ascii=False, indent=2)
                    source["locators"] = [{"locator": f"L{n:04d}", "text": line} for n, line in enumerate(text.splitlines(), 1)]
                except (json.JSONDecodeError, KeyError):
                    continue
    return out, removed, acnc_ids


def main() -> int:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    packet = json.loads((FROZEN / "whole-card-packet-v06.json").read_text(encoding="utf-8"))
    projected, removed, acnc_ids = projected_packet(packet)
    packet_sha = write_json(RUNTIME / "semantic-packet-v061.json", projected)
    write_json(RUNTIME / "projection-diagnostics.json", {"removed_paths": removed, "removed_count": len(removed), "projection": "mechanical ACNC external-taxonomy exclusion only"})
    events: list[dict] = []
    spent = Decimal("0")
    instructions = (
        "\n\nSCOPE AND PROVENANCE INSTRUCTIONS (v0.6.1):\n"
        "The target is the governed CharityGraph subject corresponding to Local Buying Foundation (WA). "
        "Domain provenance is not entity ownership: an official website may serve a network, brand, auspice arrangement "
        "or related legal entities. Attribute propositions to the target only when supplied evidence supports that scope; "
        "preserve network or sibling material under an appropriate non-subject scope or relationship. "
        "Funding is not delivery: preserve funded external projects and distinguish funding/support from operation or delivery. "
        "External taxonomy information is source-native knowledge, not semantic extraction. Do not generate ACNC CLASSIE or "
        "other source-reported external-taxonomy propositions or assignments from this packet; those are merged separately.\n"
        "FROZEN PROJECTED PACKET:\n" + json.dumps(projected, ensure_ascii=False, separators=(",", ":"))
    )
    prompt = (Path(__file__).with_name("whole_card_semantic_calibration_v02_prompt.txt")).read_text(encoding="utf-8") + instructions
    whole, whole_cost = call_luna(prompt, STRICT_SCHEMA, "whole-card-v061", 24000, spent, events, RUNTIME); spent += whole_cost
    try:
        parsed = validate_output(whole, projected); whole_valid = True; validation = {"json_schema": "passed", "citation": "passed"}; write_json(RUNTIME / "whole-card-parsed.json", parsed.model_dump(mode="json"))
    except Exception as exc:
        whole_valid = False; validation = {"json_schema_or_citation": "failed", "error": str(exc)}; write_json(RUNTIME / "whole-card-parsed.json", whole)
    write_json(RUNTIME / "whole-card-validation.json", validation)
    blind = build_taxonomy_blind_view(whole); blind_sha = write_json(RUNTIME / "classie-blind-view-v061.json", blind)
    taxonomy = json.loads(Path(r"C:\CharityGraph-runtime\classie-4.2\classie-subject-4.2-private.json").read_text(encoding="utf-8"))
    classie_prompt = "Use only this taxonomy-blind CharityGraph knowledge and permitted private taxonomy. Do not use raw source documents, ACNC CLASSIE, SDG or CharityGraph Native. Return the strict CLASSIE schema.\n" + json.dumps({"knowledge": blind, "taxonomy": taxonomy}, ensure_ascii=False, separators=(",", ":"))
    classie, classie_cost = call_luna(classie_prompt, build_classie_schema(), "classie-v061", 12000, spent, events, RUNTIME); spent += classie_cost
    ids = {str(c.get("external_concept_id") or c.get("concept_id") or c.get("id")) for c in taxonomy.get("concepts", [])}
    refs = set(blind.get("observation_refs", {})); unknown = sorted({str(a.get("concept_id")) for a in classie.get("assignments", [])} - ids); bad_refs = sorted({str(ref.get("observation_ref")) for a in classie.get("assignments", []) for ref in a.get("supporting_observations", []) if ref.get("observation_ref") not in refs})
    duplicate_pairs = len(classie.get("assignments", [])) - len({(json.dumps(a.get("target_scope"), sort_keys=True), a.get("concept_id")) for a in classie.get("assignments", [])})
    write_json(RUNTIME / "classie-parsed.json", classie); write_json(RUNTIME / "classie-validation.json", {"json_schema": "passed", "unknown_concepts": unknown, "unresolved_observation_refs": bad_refs, "duplicate_target_concept_pairs": duplicate_pairs})
    scope_counts = Counter(str(o.get("scope", {}).get("kind")) for o in whole.get("observations", []))
    relationships = whole.get("relationships", [])
    subject_obs = sum(o.get("scope", {}).get("kind") == "subject" for o in whole.get("observations", []))
    network_obs = sum(o.get("scope", {}).get("kind") in {"reporting_group", "other_named_scope", "uncertain"} for o in whole.get("observations", []))
    write_json(RUNTIME / "run-report-v061.json", {"private": True, "packet_sha256": packet_sha, "projection_removed_count": len(removed), "whole_card": {"valid": whole_valid, "observations": len(whole.get("observations", [])), "sections": sorted({o.get("section_id") for o in whole.get("observations", [])}), "scope_counts": dict(scope_counts), "relationships": len(relationships), "target_subject_observations": subject_obs, "network_sibling_context_observations": network_obs, "funded_external_project_observations": "unavailable_without_structured_activity_role", "experiment_note": "Future semantic contracts should expose an enumerated activity/relationship role if this aggregate is required mechanically."}, "classie_blind_sha256": blind_sha, "classie_assignments": len(classie.get("assignments", [])), "target_assessments": dict(Counter(a.get("status") for a in classie.get("target_assessments", []))), "acnc_exact_agreement": sorted({str(a.get("concept_id")) for a in classie.get("assignments", [])} & acnc_ids), "acnc_exact_agreement_count": len({str(a.get("concept_id")) for a in classie.get("assignments", [])} & acnc_ids), "cg_only_count": len({str(a.get("concept_id")) for a in classie.get("assignments", [])} - acnc_ids), "acnc_only_count": len(acnc_ids - {str(a.get("concept_id")) for a in classie.get("assignments", [])}), "acnc_selected_assignment_count": len(acnc_ids), "source_native_taxonomy_context_id_count": 0, "provider_events": events, "total_cost_usd": f"{spent:.6f}", "provider_calls": 2, "acnc_comparison": "exact source-native selected IDs only; ACNC is reported reference, not ground truth"})
    print(json.dumps({"runtime": str(RUNTIME), "packet_sha256": packet_sha, "whole_observations": len(whole.get("observations", [])), "scope_counts": dict(scope_counts), "relationships": len(relationships), "blind_sha256": blind_sha, "classie_assignments": len(classie.get("assignments", [])), "acnc_id_count": len(acnc_ids), "provider_calls": 2, "total_cost_usd": f"{spent:.6f}"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
