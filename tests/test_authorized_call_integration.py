from decimal import Decimal
import json
import re
import sqlite3

from charitygraph.llm_semantic_economics import ApiResult, ApiUsage, SpikeRunConfig, build_fx_snapshot, build_pricing_snapshot, run_spike
from charitygraph.contracts.economics import PriceRate

def test_paid_run_claims_authorization_slot_before_provider(tmp_path):
    calls = []
    pricing = build_pricing_snapshot(provider_id="fake", model_snapshot="fake-model", rates=(PriceRate(dimension="input_tokens", unit_quantity=Decimal("1000000"), price_per_unit=Decimal("0.20")), PriceRate(dimension="cached_input_tokens", unit_quantity=Decimal("1000000"), price_per_unit=Decimal("0.02")), PriceRate(dimension="output_tokens", unit_quantity=Decimal("1000000"), price_per_unit=Decimal("1.20"))), source_content_hash="a" * 64, authoritative_source_url="https://pricing.example.test")
    fx = build_fx_snapshot(aud_per_usd=Decimal("1.50"), source_name="fixture", source_url="https://fx.example.test", source_content_hash="b" * 64)
    def transport(url):
        return (f"<html><h1>Official</h1><p>Evidence for {url}</p></html>".encode(), "text/html")
    def provider(task, prompt):
        calls.append(task.record_id)
        evidence_id = re.search(r"\[(evidence:[0-9a-f]+)\]", prompt).group(1)
        payload = {"programs": [], "services": [], "projects": [], "campaigns": [], "organisational_units": [], "activities": [{"proposition": "activity", "subject_proposal_id": None, "scope_kind": "organisation", "evidence_refs": [evidence_id], "confidence": None, "competing_interpretation": None}], "populations": [], "geographies": [], "sdg_alignments": [], "assertions": [], "classie_assignments": [], "semantic_outcome": "supported", "blockers": []}
        return ApiResult(response_id="slot-response", model="fake-model", status="completed", output_text=json.dumps(payload), usage=ApiUsage(input_tokens=100, output_tokens=20, total_tokens=120))
    report = run_spike(SpikeRunConfig(runtime_root=str(tmp_path / "runtime"), provider_id="fake", model_snapshot="fake-model", execute_paid=True, authorization_scope_hash="f" * 64), transport=transport, pricing_snapshot=pricing, fx_snapshot=fx, provider_call=provider)
    assert len(calls) == report["unique_semantic_evidence_pack_count"]
    with sqlite3.connect(report["ledger"]["database"]) as conn:
        rows = conn.execute("SELECT status, provider_transmitted FROM authorized_call_slots").fetchall()
    assert len(rows) == len(calls)
    assert all(status == "completed" and transmitted == 1 for status, transmitted in rows)
