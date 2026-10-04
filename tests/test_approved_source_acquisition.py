from datetime import datetime, timezone

import pytest

from charitygraph.evidence_store import ContentAddressedArtifactStore
from charitygraph.sources.acquisition import (
    AcquisitionCache, AcquisitionError, ReviewState, RightsState,
    SourceAccessDecision, acquire_approved_source,
)


NOW = lambda: datetime(2026, 10, 5, tzinfo=timezone.utc)


class Headers:
    def __init__(self, value): self.value = value
    def get_content_type(self): return self.value.split(";", 1)[0]


class Response:
    def __init__(self, body, content_type="text/html", url="https://example.org/final"):
        self.body, self.headers, self.url = body, Headers(content_type), url
    def __enter__(self): return self
    def __exit__(self, *args): return None
    def read(self, _): return self.body
    def geturl(self): return self.url
    def getcode(self): return 200


def decision(rights=RightsState.APPROVED_PRODUCTION, review=ReviewState.APPROVED):
    return SourceAccessDecision("srcdef:approved-report", "annual_report", rights, review, "rights:2026-10-approved")


def test_approved_html_is_cached_by_source_decision_and_byte_identity(tmp_path):
    store = ContentAddressedArtifactStore(tmp_path / "objects")
    cache = AcquisitionCache(tmp_path / "cache.json")
    calls = []
    def opener(request, timeout):
        calls.append((request.full_url, timeout)); return Response(b"<main>approved evidence</main>")

    first, hit = acquire_approved_source("example.org/report", decision=decision(), target="production", media_family="html", cache=cache, artifact_store=store, opener=opener, now=NOW)
    second, cached = acquire_approved_source("example.org/report", decision=decision(), target="production", media_family="html", cache=cache, artifact_store=store, opener=lambda *_: pytest.fail("cache should prevent a network call"), now=NOW)
    assert not hit and cached and first == second
    assert calls == [("https://example.org/report", 20)]
    assert first.stable_locator == f"artifact:{first.content_sha256}"
    assert first.rights_state == "approved_production" and first.review_state == "approved"


def test_unapproved_or_unreviewed_source_cannot_become_production_input(tmp_path):
    store, cache = ContentAddressedArtifactStore(tmp_path / "objects"), AcquisitionCache(tmp_path / "cache.json")
    for value in (decision(RightsState.RESEARCH_ONLY), decision(review=ReviewState.PENDING), decision(RightsState.UNAPPROVED)):
        with pytest.raises(AcquisitionError, match="rights/review"):
            acquire_approved_source("example.org", decision=value, target="production", media_family="html", cache=cache, artifact_store=store, opener=lambda *_: pytest.fail("must fail before fetching"))


def test_research_only_is_explicit_and_never_reuses_production_cache_key(tmp_path):
    store, cache = ContentAddressedArtifactStore(tmp_path / "objects"), AcquisitionCache(tmp_path / "cache.json")
    result, hit = acquire_approved_source("example.org", decision=decision(RightsState.RESEARCH_ONLY, ReviewState.PENDING), target="research", media_family="html", cache=cache, artifact_store=store, opener=lambda *_: Response(b"<p>review packet</p>"), now=NOW)
    assert not hit and result.rights_state == "research_only" and result.review_state == "pending"
    with pytest.raises(AcquisitionError):
        acquire_approved_source("example.org", decision=decision(RightsState.RESEARCH_ONLY, ReviewState.PENDING), target="production", media_family="html", cache=cache, artifact_store=store)


def test_pdf_magic_is_accepted_but_html_rejects_wrong_content_type(tmp_path):
    store, cache = ContentAddressedArtifactStore(tmp_path / "objects"), AcquisitionCache(tmp_path / "cache.json")
    pdf, _ = acquire_approved_source("example.org/report", decision=decision(), target="production", media_family="pdf", cache=cache, artifact_store=store, opener=lambda *_: Response(b"%PDF-1.7 bytes", "application/octet-stream"), now=NOW)
    assert pdf.content_type == "application/octet-stream"
    with pytest.raises(AcquisitionError, match="unsupported_content_type"):
        acquire_approved_source("example.org/not-html", decision=decision(), target="production", media_family="html", cache=cache, artifact_store=store, opener=lambda *_: Response(b"%PDF-1.7", "application/pdf"), now=NOW)


def test_retry_and_size_failure_are_bounded_and_provider_free(tmp_path):
    store, cache = ContentAddressedArtifactStore(tmp_path / "objects"), AcquisitionCache(tmp_path / "cache.json")
    calls, waits = [], []
    def opener(*_):
        calls.append(1)
        if len(calls) == 1: raise TimeoutError()
        return Response(b"<p>after retry</p>")
    value, _ = acquire_approved_source("example.org", decision=decision(), target="production", media_family="html", cache=cache, artifact_store=store, opener=opener, retries=1, wait=waits.append, now=NOW)
    assert value.byte_size == len(b"<p>after retry</p>") and waits == [0.1]
    with pytest.raises(AcquisitionError, match="response_too_large"):
        acquire_approved_source("example.org/large", decision=decision(), target="production", media_family="html", cache=cache, artifact_store=store, opener=lambda *_: Response(b"123"), max_bytes=2)
