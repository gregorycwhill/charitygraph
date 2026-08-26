from datetime import datetime, timezone
from pathlib import Path

import pytest

from charitygraph.llm_semantic_economics import (
    EvidenceBundle,
    RichSemanticOutput,
    SemanticProposal,
    SourceDocument,
    SpikeRunConfig,
    build_evidence_bundle,
    build_model_task,
    parse_document,
    run_spike,
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