from __future__ import annotations

import pytest

from charitygraph.baseline_corpus import BASELINE_SOURCE_FAMILIES
from charitygraph.phase5_baseline_corpus import MAX_NATIVE_TEXT_PAGES, NetworkLedger, NetworkPolicyError, ProviderGuard, ProviderUseProhibited, available_member, governed_website_hosts, historical_bytes, latest_report_documents


def test_phase5_baseline_source_universe_has_all_seven_families() -> None:
    assert BASELINE_SOURCE_FAMILIES == (
        "acnc_register", "acnc_ais_bundle", "ato_abr_dgr", "official_website",
        "annual_report", "wikipedia_wikimedia", "pfra",
    )


def test_provider_guard_fails_closed_and_records_no_call() -> None:
    guard = ProviderGuard()
    with pytest.raises(ProviderUseProhibited):
        guard.prohibit("responses.create")
    assert guard.report()["provider_calls"] == 0
    assert guard.report()["attempted_provider_calls"] == [{"operation": "responses.create", "status": "blocked"}]


def test_network_ledger_reuses_cached_bytes_without_second_transport(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    calls = []

    class Response:
        status = 200

        class Headers:
            @staticmethod
            def get_content_type() -> str:
                return "application/json"

        headers = Headers()

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def read(self, _size: int) -> bytes:
            return b'{"ok":true}'

        @staticmethod
        def geturl() -> str:
            return "https://example.test/resource"

    def fake_urlopen(*_args, **_kwargs):
        calls.append("transport")
        return Response()

    monkeypatch.setattr("charitygraph.phase5_baseline_corpus.urlopen", fake_urlopen)
    ledger = NetworkLedger(cache_root=tmp_path / "cache")
    first = ledger.fetch(source_family="test", url="https://example.test/resource", allowed_hosts={"example.test"})
    second = ledger.fetch(source_family="test", url="https://example.test/resource", allowed_hosts={"example.test"})
    assert first["body"] == second["body"] == b'{"ok":true}'
    assert calls == ["transport"]
    assert second["event"]["origin"] == "reused_existing"


def test_historical_inline_bytes_are_hash_verified_when_raw_archive_path_is_absent(tmp_path) -> None:
    body = b'{"frozen":true}'
    record = {"content_hash": __import__("hashlib").sha256(body).hexdigest(), "text": body.decode("utf-8")}
    assert historical_bytes(tmp_path, record) == body


def test_governed_website_hosts_allow_only_canonical_www_counterpart() -> None:
    assert governed_website_hosts("https://example.org") == {"example.org", "www.example.org"}


def test_native_representation_page_budget_is_explicit() -> None:
    assert MAX_NATIVE_TEXT_PAGES == 5


def test_zero_byte_successful_transport_is_retained_as_partial_not_available() -> None:
    member = available_member({"source_definition_id": "srcdef:test", "acquisition_receipt_id": "acq:test", "artifact_id": "srcblob:" + "a" * 64, "source_record_id": "srcrec:test", "origin": "newly_acquired", "acquisition": "partial"}, family="official_website")
    assert member.acquisition.value == "partial"


def test_unapproved_host_is_blocked_before_transport(tmp_path) -> None:
    with pytest.raises(NetworkPolicyError):
        NetworkLedger(cache_root=tmp_path).fetch(source_family="official_website", url="https://unapproved.example/", allowed_hosts={"approved.example"})


def test_latest_report_selection_remains_structured_metadata_only() -> None:
    year, documents = latest_report_documents({"data": {"AnnualReports": [{"Status": "Submitted", "IsAIS": False, "DocumentUuid": "doc", "Year": "2025"}], "Documents": [{"type": "Financial Report", "Year": "2025", "Url": "https://acnc.example/report.pdf"}]}})
    assert year == "2025"
    assert documents[0]["role"] == "financial_report"
