from pathlib import Path

import pytest

from charitygraph.program_evidence_expansion import (
    MAX_DEPTH,
    ProgramReferenceCandidate,
    assess_program_adequacy,
    bounded_discovery,
    extract_candidates,
    write_review_packet,
)
from charitygraph.reality_slice1 import BoundedPublicAcquirer, HoldoutFirewallError, development_members


def _fixture_pages():
    return {
        "https://example.org/": b"<title>Home</title><h1>Programs</h1><h2>Learning for Life</h2><h2>Community development</h2><h2>Annual appeal</h2><a href='/programs'>Programs</a><a href='https://outside.example/x'>outside</a>",
        "https://example.org/programs": b"<h1>Learning for Life</h1><h2>Lifeblood</h2><h2>Child sponsorship</h2><a href='/programs/learning'>Learning for Life</a>",
        "https://example.org/programs/learning": b"<h1>Learning for Life</h1><p>A continuing named program.</p><a href='/too-deep'>Too deep</a>",
        "https://example.org/too-deep": b"<h1>Should not be fetched</h1>",
    }


def _fetcher(pages, seen):
    def fetch(url):
        seen.append(url)
        return pages[url], url, 200, "text/html"
    return fetch


def test_development_only_and_holdout_firewall_before_fetch(tmp_path):
    member = development_members()[0]
    seen = []
    pages = _fixture_pages()
    acquirer = BoundedPublicAcquirer(tmp_path / "runtime", transport=_fetcher(pages, seen))
    with pytest.raises(HoldoutFirewallError):
        bounded_discovery(members=(member,), start_urls={"67649417658": ("https://example.org/",)}, fetch=_fetcher(pages, seen), acquirer=acquirer)
    assert seen == []


def test_same_site_depth_two_and_private_cas_storage(tmp_path):
    member = development_members()[0]
    pages = _fixture_pages()
    seen = []
    fetch = _fetcher(pages, seen)
    acquirer = BoundedPublicAcquirer(tmp_path / "runtime", transport=fetch)
    sources, bodies = bounded_discovery(members=(member,), start_urls={member.abn: ("https://example.org/",)}, fetch=fetch, acquirer=acquirer)
    assert len(sources) == 3
    assert all(source.depth <= MAX_DEPTH and source.private_artifact for source in sources)
    assert "https://outside.example/x" not in seen
    assert "https://example.org/too-deep" not in seen
    assert all(source.source_record_id in bodies for source in sources)
    assert all(source.content_hash == __import__("hashlib").sha256(bodies[source.source_record_id]).hexdigest() for source in sources)


def test_candidate_extraction_is_proposition_specific_and_excludes_false_programs(tmp_path):
    member = development_members()[0]
    pages = _fixture_pages()
    seen = []
    fetch = _fetcher(pages, seen)
    acquirer = BoundedPublicAcquirer(tmp_path / "runtime", transport=fetch)
    sources, bodies = bounded_discovery(members=(member,), start_urls={member.abn: ("https://example.org/",)}, fetch=fetch, acquirer=acquirer)
    candidates, rejected = extract_candidates(member=member, sources=sources, private_bodies=bodies)
    learning = next(candidate for candidate in candidates if candidate.canonical_label == "Learning for Life")
    assert learning.recommendation == "acceptable"
    assert learning.subject_kind in {"program", "service"}
    assert learning.proposition == "durable_named_program_or_service"
    assert learning.source_record_id in bodies
    assert {item.rejection_class for item in rejected} >= {"service_domain", "campaign", "division", "mechanism"}
    assert all(item.canonical_label not in {"Community development", "Annual appeal", "Lifeblood", "Child sponsorship"} for item in candidates)


def _candidate(abn: str, label: str, recommendation: str = "required"):
    return ProgramReferenceCandidate(
        candidate_id=f"x:{abn}:{label}", member_abn=abn, charity_name=abn,
        canonical_label=label, subject_kind="program", recommendation=recommendation,
        parent_subject_id="subject:test", source_url="https://example.org/program",
        source_record_id="srcrec:test", content_hash="a" * 64,
        evidence_selector="heading:" + label, proposition="durable_named_program_or_service",
        relationship_type="has_program", durability_rationale="test",
    )


def test_unresolved_candidates_do_not_enter_adequacy_denominator():
    candidates = [_candidate(str(i), f"P{i}") for i in range(10)] + [_candidate("unresolved", "Unknown", "unresolved")]
    report = assess_program_adequacy(candidates)
    assert report.required_durable_program_service_count == 10
    assert report.charities_represented == 10
    assert report.program_benchmark_adequacy == "adequate"


def test_program_minimum_spread_share_and_inadequacy():
    concentrated = [_candidate("one", f"P{i}") for i in range(10)]
    report = assess_program_adequacy(concentrated)
    assert report.program_benchmark_adequacy == "insufficient"
    assert report.largest_charity_share == 1.0
    spread = [_candidate(str(i % 4), f"P{i}") for i in range(10)]
    assert assess_program_adequacy(spread).program_benchmark_adequacy == "adequate"


def test_private_review_packet_is_proposed_and_machine_readable(tmp_path):
    candidate = _candidate("one", "Learning for Life")
    adequacy = assess_program_adequacy((candidate,))
    packet, machine = write_review_packet(runtime_root=tmp_path, candidates=(candidate,), rejected=(), adequacy=adequacy)
    assert packet.exists() and machine.exists()
    assert "Private, review-only" in packet.read_text(encoding="utf-8")
    assert machine.parent == packet.parent
    assert '"status": "proposed"' in machine.read_text(encoding="utf-8")


def test_frozen_scoped_benchmark_is_not_modified():
    manifest = Path(__file__).parents[1] / "cohort" / "scoped_benchmark_v2.json"
    data = __import__("json").loads(manifest.read_text(encoding="utf-8"))
    assert data["status"] == "approved_frozen"
    assert len(data["cases"]) == 40
    assert data["completeness"]["program_benchmark_adequacy"] == "insufficient"
