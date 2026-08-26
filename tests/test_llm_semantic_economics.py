from datetime import datetime, timezone
from pathlib import Path
from decimal import Decimal
import json
import re

import pytest

from charitygraph.llm_semantic_economics import (
    EvidenceBundle,
    RichSemanticOutput,
    SemanticProposal,
    SourceDocument,
    SpikeRunConfig,
    build_evidence_bundle,
    build_fx_snapshot,
    build_pricing_snapshot,
    build_model_task,
    parse_document,
    run_spike,
    ApiResult,
    ApiUsage,
    semantic_prompt,
    validate_output,
)
from charitygraph.reality_slice1 import development_members


def _doc(url: str, text: str, digest: str = "a" * 64) -> SourceDocument:
    return SourceDocument(
        url=url,
        retrieved_at=datetime(2026, 8, 26, tzinfo=timezone.utc),
        publisher="The Smith Family",
        content_hash=digest,
        artifact_id="srcblob:" + digest,
        media_type="text/html",
        byte_size=len(text),
        text=text,
    )


def test_parser_is_mechanical_and_does_not_classify_repeated_wording():
    text = parse_document(b"<h1>Mission</h1><p>program program</p><script>program</script>")
    assert text == "Mission\nprogram program"
    assert "semantic_outcome" not in text


def test_evidence_bundle_hash_and_selection_are_exact_and_deterministic():
    member = development_members()[0]
    docs = (_doc("https://example.test/a", "A"), _doc("https://example.test/b", "B", "b" * 64))
    one = build_evidence_bundle(member.subject_id, "broad", docs)
    two = build_evidence_bundle(member.subject_id, "broad", docs)
    assert one.bundle_hash == two.bundle_hash
    assert one.selection_hash == two.selection_hash
    assert [s.evidence_id for s in one.source_segments] == [s.evidence_id for s in two.source_segments]
    assert one.source_segments[0].content_hash == "a" * 64


def test_model_task_binds_every_input_to_bundle_hash_and_prompt_policy():
    member = development_members()[0]
    bundle = build_evidence_bundle(member.subject_id, "lean", (_doc("https://example.test", "delivered activity"),))
    task = build_model_task(member.subject_id, bundle, provider_id="openai", model_snapshot="gpt-5.6-luna")
    assert task.cache_key
    assert task.policy_refs[0].policy_id == "CG-D027"
    assert task.evidence_inputs[0].selection_hash == bundle.selection_hash
    assert bundle.bundle_hash in semantic_prompt(bundle, member.legal_current_name)


def test_unbound_model_evidence_is_rejected():
    member = development_members()[0]
    bundle = build_evidence_bundle(member.subject_id, "lean", (_doc("https://example.test", "evidence"),))
    output = RichSemanticOutput(
        programs=(SemanticProposal(proposal_id="p1", label="Example", kind="program", evidence_refs=("evidence:unknown",)),),
    )
    with pytest.raises(ValueError, match="unbound evidence"):
        validate_output(output, bundle)


def test_missing_evidence_refs_are_rejected():
    member = development_members()[0]
    bundle = build_evidence_bundle(member.subject_id, "lean", (_doc("https://example.test", "evidence"),))
    output = RichSemanticOutput(
        programs=(SemanticProposal(proposal_id="p1", label="Example", kind="program"),),
    )
    with pytest.raises(ValueError, match="at least one evidence reference"):
        validate_output(output, bundle)

def test_fixture_run_is_seven_only_three_tiers_and_private(tmp_path: Path):
    def transport(url: str):
        return (f"<html><h1>Official</h1><p>Evidence for {url}</p></html>".encode(), "text/html")

    report = run_spike(SpikeRunConfig(runtime_root=str(tmp_path / "runtime")), transport=transport)
    assert report["development_abns"] == [m.abn for m in development_members()]
    assert report["holdout_firewall"]["enforced"] is True
    assert report["task_count"] == 21
    assert report["tiers"] == ["lean", "broad", "very_broad"]
    assert report["paid_execution"] is False
    assert report["human_review"]["denominator_current"] == 1
    assert report["human_review"]["model_output_is_not_gold"] is True

def test_fake_paid_path_reserves_before_call_and_reports_proposals(tmp_path: Path):
    calls = []
    pricing = build_pricing_snapshot(provider_id="fake", model_snapshot="fake-model", source_content_hash="c" * 64, authoritative_source_url="https://pricing.example.test")
    fx = build_fx_snapshot(aud_per_usd=Decimal("1.50"), source_name="fixture", source_url="https://fx.example.test", source_content_hash="d" * 64)

    def transport(url: str):
        return (f"<html><h1>Official</h1><p>Delivered service for {url}</p></html>".encode(), "text/html")

    def provider(task, prompt):
        assert (tmp_path / "runtime" / "reality-slice1-llm-semantic-economics" / "ledger.sqlite3").is_file()
        calls.append(task.record_id)
        evidence_id = re.search(r"\[(evidence:[0-9a-f]+)\]", prompt).group(1)
        payload = {"programs": [{"proposal_id": "p1", "label": "Example service", "kind": "service", "durable": True, "evidence_refs": [evidence_id], "model_review_recommendation": "required"}], "services": [], "projects": [], "campaigns": [], "organisational_units": [], "activities": [{"proposition": "delivered activity", "evidence_refs": [evidence_id]}], "populations": [], "geographies": [], "sdg_alignments": [], "assertions": [], "semantic_outcome": "supported", "blockers": []}
        return ApiResult(response_id="fixture-response", model="fake-model", status="completed", output_text=json.dumps(payload), usage=ApiUsage(input_tokens=100, output_tokens=100, total_tokens=200))

    report = run_spike(SpikeRunConfig(runtime_root=str(tmp_path / "runtime"), provider_id="fake", model_snapshot="fake-model", execute_paid=True), transport=transport, pricing_snapshot=pricing, fx_snapshot=fx, provider_call=provider)
    assert len(calls) == report["task_count"] == 21
    assert report["human_review"]["proposed_durable_program_service_subjects"]
    row = report["human_review"]["proposed_durable_program_service_subjects"][0]
    assert row["model_recommendation"] == "required"
    assert row["review_status"] == "proposed"
    assert row["human_disposition"] is None
    assert report["human_review"]["denominator_current"] == 1
    assert report["ledger"]["budget_position"]["actual_spend_aud"] != "0"
    assert report["economics"]["aggregate"]["actual_cost_aud"] != "0"
    assert report["economics"]["aggregate"]["grounded_propositions"] > 0
    assert report["economics"]["aggregate"]["unresolved_count"] == 0
    assert report["economics"]["incremental_tier_yield"]
    assert report["pricing_snapshot"]["record_id"] == pricing.record_id
    assert report["fx_snapshot"]["record_id"] == fx.record_id
    assert report["holdout_firewall"]["holdout_model_tasks"] == 0
    assert Path(report["human_review_report"]).is_file()
