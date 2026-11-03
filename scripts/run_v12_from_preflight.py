"""Execute frozen V12 packets through persisted Compact v0.2 representations."""
from __future__ import annotations
import hashlib, json, sys
from types import SimpleNamespace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
sys.path.insert(0, "src")
from charitygraph.compact_knowledge import CompactKnowledgeOutputV02, COMPACT_V02_SCHEMA
from charitygraph.scope_resolution_contract import ScopeResolutionOutput, SCOPE_RESOLUTION_SCHEMA
from charitygraph.openai_client import responses_create, estimate_response_cost
from charitygraph.packet_locators import resolve_locator
from charitygraph.runtime.catalog import SQLiteCatalog
from charitygraph.contracts.ids import deterministic_id

ROOT = Path(r"C:\CharityGraph-runtime\broad-compact-diagnostic-v12")
LEDGER = ROOT / "v12-budget.sqlite3"
CP = "Extract all evidence-supported Compact Knowledge v0.2 atoms about the declared target. Scope fields are producer hints only. Use exact dates only when supported; use reporting_period for coarse periods. Cite packet-local locators."
RP = "Resolve scope independently using only the declared target, proposition and exact evidence excerpts. Do not use producer scope hints. Generic organisation facts/categories are subject; named_program_or_service requires one specifically named instance; other_named_scope requires one named subordinate thing; reporting_group requires formal evidence; otherwise uncertain. Return one indexed decision per atom."

def main() -> None:
    dry_run = "--dry-run" in sys.argv
    manifest = ROOT / "persisted-representation-manifest.json"
    if not manifest.exists():
        raise SystemExit("preflight failed: persisted-representation-manifest.json is required")
    entries = []
    for item in json.loads(manifest.read_text(encoding="utf-8"))["representations"]:
        path = Path(item["representation_path"])
        if not path.exists():
            raise SystemExit(f"preflight failed: missing persisted representation {path}")
        entries.append((json.loads(path.read_text(encoding="utf-8")), item))
    packets = []
    for data, item in entries:
        lines = [line for line in data["text"].splitlines() if line.strip()]
        step = max(1, min(80, len(lines) // 4 or 1))
        for start in range(0, len(lines), step):
            packets.append((data, lines[start:start + step], start))
    if "--proof" in sys.argv:
        packets = packets[:6] if "--first-half" in sys.argv else (packets[7:12] if "--second-half" in sys.argv else packets[:12])
    else:
        packets = packets[:100]
    summary = {"campaign": "broad-compact-diagnostic-v12", "packets": [], "atoms": []}
    prior_spend = Decimal("0")
    existing_packet_shas = set()
    for old in ROOT.glob("v12-*/compact-raw.json"):
        try:
            old_json = json.loads(old.read_text(encoding="utf-8")); usage = old_json.get("usage") or {}
            prior_spend += Decimal(str(estimate_response_cost("gpt-5.6-luna", SimpleNamespace(input_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens"))) or 0))
            packet_file = old.parent / "packet.json"
            if packet_file.exists(): existing_packet_shas.add(hashlib.sha256(packet_file.read_bytes()).hexdigest())
        except Exception: pass
    total = prior_spend; now = datetime.now(timezone.utc).isoformat(); registration_time = "2026-09-02T22:28:04.553607+00:00"
    catalog = SQLiteCatalog(LEDGER).open(initialize=True)
    cohort_id, run_id = deterministic_id("cohort:", "v12-central-corpus-20260903"), deterministic_id("run:", "v12-central-corpus-20260903")
    catalog.register_cohort({"record_id": cohort_id, "cohort_code": "V12-CENTRAL-CORPUS", "definition_version": "1", "membership_hash": hashlib.sha256(b"v12").hexdigest(), "budget_cap": {"amount": "1.60", "currency": "AUD"}, "created_at": registration_time})
    catalog.register_run({"record_id": run_id, "cohort_id": cohort_id, "run_kind": "diagnostic", "status": "planned", "configuration_hash": hashlib.sha256(b"v12-luna-none").hexdigest(), "created_at": registration_time})
    if dry_run:
        rows = []
        for idx, (data, lines, start) in enumerate(packets, 1):
            encoded = json.dumps({"target": {"name": data["target"]}, "evidence": [{"locator": f"L{i + 1:04d}", "source": "S001", "text": text[:1200]} for i, text in enumerate(lines)]}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            estimate_input = Decimal(len(CP + data["target"] + encoded)) / Decimal(4)
            proposed = (estimate_input * Decimal("0.20") / Decimal(1_000_000) + Decimal(7000) * Decimal("1.20") / Decimal(1_000_000)).quantize(Decimal("0.000001"))
            rows.append({"packet": idx, "subject": data["target"], "model": "gpt-5.6-luna", "schema": "compact_knowledge_v02", "reasoning": "none", "max_output_tokens": 7000, "max_attempts": 1, "projected_cost_usd": str(proposed)})
        catalog.close(); print(json.dumps({"dry_run": True, "planned_transmissions": len(rows), "rows": rows, "aggregate_projected_usd": str(sum((Decimal(r["projected_cost_usd"]) for r in rows), Decimal("0")).quantize(Decimal("0.000001")))})); return
    for idx, (data, lines, start) in enumerate(packets, 1):
        locs = [{"source": "S001", "locator": f"L{i + 1:04d}", "text": text[:1200]} for i, text in enumerate(lines)]
        packet = {"target": {"name": data["target"]}, "source": {"publisher": data["publisher"], "relation": data["source_relation"], "material_role": data["material_role"], "original_url": data.get("original_url"), "raw_sha256": data["raw_sha256"], "representation_sha256": data["representation_sha256"], "parent_document": data["raw_path"], "chunk_identity": f"lines-{start + 1}-{start + len(lines)}"}, "evidence": locs}
        encoded = json.dumps(packet, ensure_ascii=False, sort_keys=True, separators=(",", ":")); packet_sha = hashlib.sha256(encoded.encode()).hexdigest()
        outdir = ROOT / f"v12-{idx:03d}"; outdir.mkdir(exist_ok=True); (outdir / "packet.json").write_text(encoded, encoding="utf-8")
        if idx <= 2 and (outdir / "compact-raw.json").exists():
            continue
        if packet_sha in existing_packet_shas: continue
        input_est = Decimal(len(CP + data["target"] + encoded)) / Decimal(4)
        proposed = (input_est * Decimal("0.20") / Decimal(1_000_000) + Decimal(7000) * Decimal("1.20") / Decimal(1_000_000)).quantize(Decimal("0.000001"))
        position = catalog.budget_position(cohort_id); remaining = Decimal("1.00") - prior_spend - (position.net_actual_spend_aud + position.outstanding_reserved_exposure_aud) / Decimal("1.50")
        if proposed > remaining:
            catalog.close(); raise SystemExit(json.dumps({"status": "budget_exhausted", "packet": idx, "projected_usd": str(proposed), "remaining_usd": str(remaining)}))
        reservation_id = deterministic_id("reservation:", f"v12:{packet_sha}:compact")
        reserved_aud = (proposed * Decimal("1.50")).quantize(Decimal("0.000001"))
        catalog.reserve_cost({"record_id": reservation_id, "cohort_id": cohort_id, "run_id": run_id, "reserved_aud": {"amount": str(reserved_aud), "currency": "AUD"}, "model_task_ids": ()}, now=now)
        response = responses_create(model="gpt-5.6-luna", input_text=CP + "\nDECLARED TARGET: " + data["target"] + "\nPACKET:\n" + encoded, text_format={"type": "json_schema", "name": "compact_knowledge_v02", "strict": True, "schema": COMPACT_V02_SCHEMA}, max_output_tokens=7000, max_attempts=1, timeout_seconds=300, reasoning={"effort": "none"})
        usage = response.usage; cost = estimate_response_cost("gpt-5.6-luna", usage) or Decimal("0"); total += Decimal(str(cost))
        (outdir / "compact-raw.json").write_text(json.dumps({"response_id": response.response_id, "status": response.status, "output_text": response.output_text, "usage": usage.__dict__}, ensure_ascii=False), encoding="utf-8")
        aud_actual = (Decimal(str(cost)) * Decimal("1.50")).quantize(Decimal("0.000001"))
        catalog.record_cost_entry({"cohort_id": cohort_id, "run_id": run_id, "task_run_id": deterministic_id("taskrun:", f"v12:{packet_sha}:compact"), "reservation_id": reservation_id, "pricing_snapshot_id": deterministic_id("pricing:", "v12-luna"), "fx_snapshot_id": deterministic_id("fx:", "v12-aud"), "entry_type": "actual", "paid_output_category": "semantic_judgement", "provider_cost": {"amount": str(cost), "currency": "USD"}, "aud_cost": {"amount": str(aud_actual), "currency": "AUD"}, "usage": {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens}, "recorded_at": now}, entry_key=f"actual:v12-{idx:03d}-compact")
        unused = catalog.reservation_position(reservation_id)["outstanding"]
        if unused > 0: catalog.release_cost(reservation_id, {"amount": str(unused), "currency": "AUD"}, now=now, entry_key=f"release:v12-{idx:03d}-compact")
        try: parsed = CompactKnowledgeOutputV02.model_validate(json.loads(response.output_text))
        except Exception: parsed = None
        prow = {"target": data["target"], "packet_sha": packet_sha, "status": response.status, "valid": parsed is not None, "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens, "cost_usd": str(cost)}
        if parsed:
            line_map = {loc["locator"]: loc["text"] for loc in locs}; resolver_input = []
            for atom_index, atom in enumerate(parsed.atoms):
                items = []
                for evidence_index, evidence in enumerate(atom.evidence):
                    try: excerpt = resolve_locator(line_map, evidence.locator)
                    except Exception: excerpt = ""
                    if excerpt.strip(): items.append({"evidence_index": evidence_index, "canonical_ref": f"{evidence.source}:{evidence.locator}", "exact_excerpt": excerpt})
                if items: resolver_input.append({"atom_index": atom_index, "proposition": atom.proposition, "evidence_items": items})
            if resolver_input:
                resolver_estimate = Decimal(len(RP + data["target"] + json.dumps(resolver_input, ensure_ascii=False))) / Decimal(4)
                resolver_proposed = (resolver_estimate * Decimal("0.20") / Decimal(1_000_000) + Decimal(7000) * Decimal("1.20") / Decimal(1_000_000)).quantize(Decimal("0.000001"))
                position = catalog.budget_position(cohort_id); remaining = Decimal("1.00") - (position.net_actual_spend_aud + position.outstanding_reserved_exposure_aud) / Decimal("1.50")
                if resolver_proposed > remaining:
                    catalog.close(); raise SystemExit(json.dumps({"status": "budget_exhausted", "packet": idx, "phase": "resolver", "projected_usd": str(resolver_proposed), "remaining_usd": str(remaining)}))
                resolver_reservation_id = deterministic_id("reservation:", f"v12:{packet_sha}:resolver")
                resolver_aud_reserved = (resolver_proposed * Decimal("1.50")).quantize(Decimal("0.000001"))
                catalog.reserve_cost({"record_id": resolver_reservation_id, "cohort_id": cohort_id, "run_id": run_id, "reserved_aud": {"amount": str(resolver_aud_reserved), "currency": "AUD"}, "model_task_ids": ()}, now=now)
                rr = responses_create(model="gpt-5.6-luna", input_text=RP + "\nTARGET: " + data["target"] + "\nATOMS:\n" + json.dumps(resolver_input, ensure_ascii=False), text_format={"type": "json_schema", "name": "scope_resolution_v1", "strict": True, "schema": SCOPE_RESOLUTION_SCHEMA}, max_output_tokens=7000, max_attempts=1, timeout_seconds=300, reasoning={"effort": "none"})
                ru = rr.usage; rc = estimate_response_cost("gpt-5.6-luna", ru) or Decimal("0"); total += Decimal(str(rc)); prow.update({"resolver_status": rr.status, "resolver_input_tokens": ru.input_tokens, "resolver_output_tokens": ru.output_tokens, "resolver_cost_usd": str(rc)})
                resolver_aud = (Decimal(str(rc)) * Decimal("1.50")).quantize(Decimal("0.000001"))
                catalog.record_cost_entry({"cohort_id": cohort_id, "run_id": run_id, "task_run_id": deterministic_id("taskrun:", f"v12:{packet_sha}:resolver"), "reservation_id": resolver_reservation_id, "pricing_snapshot_id": deterministic_id("pricing:", "v12-luna"), "fx_snapshot_id": deterministic_id("fx:", "v12-aud"), "entry_type": "actual", "paid_output_category": "semantic_judgement", "provider_cost": {"amount": str(rc), "currency": "USD"}, "aud_cost": {"amount": str(resolver_aud), "currency": "AUD"}, "usage": {"input_tokens": ru.input_tokens, "output_tokens": ru.output_tokens}, "recorded_at": now}, entry_key=f"actual:v12-{idx:03d}-resolver")
                unused = catalog.reservation_position(resolver_reservation_id)["outstanding"]
                if unused > 0: catalog.release_cost(resolver_reservation_id, {"amount": str(unused), "currency": "AUD"}, now=now, entry_key=f"release:v12-{idx:03d}-resolver")
            summary["atoms"].extend({"target": data["target"], "packet_sha": packet_sha, "raw_compact_atom": atom.model_dump(mode="json")} for atom in parsed.atoms)
        summary["packets"].append(prow)
    catalog.close()
    (ROOT / "campaign-summary.json").write_text(json.dumps({**summary, "compact_calls": len(summary["packets"]), "resolver_calls": sum(1 for p in summary["packets"] if p.get("resolver_status")), "total_cost_usd": str(total.quantize(Decimal("0.000001")))}, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "aggregate-review.json").write_text(json.dumps({"atoms": summary["atoms"]}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"compact_calls": len(summary["packets"]), "resolver_calls": sum(1 for p in summary["packets"] if p.get("resolver_status")), "atoms": len(summary["atoms"]), "cost": str(total.quantize(Decimal("0.000001")))}))

if __name__ == "__main__": main()
