from charitygraph.s0_locator_discovery import LocatorSearchResponse
from charitygraph.s0_orchestration import ScaleS0Executor, S0LocatorWork
from charitygraph.scale_s0 import ScalePreflightError
import pytest
from charitygraph.phase5_standard_transport import StandardCampaignCoordinator
from test_phase5_standard_transport import FakeCatalog, FakeProvider, _row

from .test_s0_locator_search_lifecycle import _prepared_catalog


class FakeLocator:
    provider_id = "fake-locator"

    def __init__(self):
        self.calls = 0

    def search(self, *, query, subject_abn, request_identity):
        self.calls += 1
        return LocatorSearchResponse("response:fake-locator", (), {
            "input_tokens": 10,
            "output_tokens": 5,
            "provider_cost": {"amount": "0.04", "currency": "USD"},
            "pricing_snapshot_id": "pricing:locator-v1",
        })


class IncompleteLocator(FakeLocator):
    def search(self, *, query, subject_abn, request_identity):
        self.calls += 1
        return LocatorSearchResponse("response:incomplete-locator", (), {"total_tokens": 15})


class AmbiguousLocator(FakeLocator):
    def search(self, *, query, subject_abn, request_identity):
        self.calls += 1
        raise RuntimeError("provider crossing lost before a response")


def test_s0_executor_locator_dry_run_never_calls_provider(tmp_path):
    catalog, _, packet, prepared = _prepared_catalog(tmp_path)
    fake = FakeLocator()
    from .test_s0_locator_search_lifecycle import NOW
    executor = ScaleS0Executor(catalog=catalog, attempt_id="attempt:locator", builder_commit_sha="a" * 40, runtime_root=tmp_path, locator_provider=fake, now=lambda: NOW, on_reconciled=lambda *_: None)
    work = S0LocatorWork(packet.packet_id, prepared.request, prepared.delivery_attempt_id, prepared.client_request_id, packet.locator_query)
    summary = executor.run(locator=(work,), dry_run=True)
    assert summary.provider_posts == 0 and summary.counts == {"eligible": 1}
    assert fake.calls == 0


def test_s0_executor_locator_live_and_terminal_reentry_are_idempotent(tmp_path):
    catalog, _, packet, prepared = _prepared_catalog(tmp_path)
    fake = FakeLocator()
    from .test_s0_locator_search_lifecycle import NOW
    executor = ScaleS0Executor(catalog=catalog, attempt_id="attempt:locator", builder_commit_sha="a" * 40, runtime_root=tmp_path, locator_provider=fake, now=lambda: NOW, on_reconciled=lambda *_: None)
    work = S0LocatorWork(packet.packet_id, prepared.request, prepared.delivery_attempt_id, prepared.client_request_id, packet.locator_query)
    first = executor.run(locator=(work,))
    assert catalog.get_provider_request_item(packet.provider_request_identity)["status"] == "completed"
    second = executor.run(locator=(work,))
    assert first.provider_posts == 1 and first.counts == {"completed": 1}
    assert second.provider_posts == 0 and second.counts == {"replayed_terminal": 1}
    assert fake.calls == 1
    assert "reservation:locator" in first.accounting


def test_s0_executor_default_accounting_rejects_missing_usage_after_crossing(tmp_path):
    catalog, _, packet, prepared = _prepared_catalog(tmp_path)
    fake = IncompleteLocator()
    executor = ScaleS0Executor(catalog=catalog, attempt_id="attempt:locator", builder_commit_sha="a" * 40, runtime_root=tmp_path, locator_provider=fake, now=lambda: __import__("datetime").datetime(2099, 9, 22, tzinfo=__import__("datetime").timezone.utc))
    work = S0LocatorWork(packet.packet_id, prepared.request, prepared.delivery_attempt_id, prepared.client_request_id, packet.locator_query)
    summary = executor.run(locator=(work,))
    assert summary.counts == {"completed_accounting_failed": 1}
    assert catalog.get_provider_request_item(packet.provider_request_identity)["status"] == "completed"
    assert fake.calls == 1


def test_s0_executor_rejects_wrong_builder_head_before_reconstruction(tmp_path):
    catalog, _, packet, prepared = _prepared_catalog(tmp_path)
    fake = FakeLocator()
    executor = ScaleS0Executor(catalog=catalog, attempt_id="attempt:locator", builder_commit_sha="b" * 40,
                               runtime_root=tmp_path, locator_provider=fake)
    work = S0LocatorWork(packet.packet_id, prepared.request, prepared.delivery_attempt_id, prepared.client_request_id, packet.locator_query)
    with pytest.raises(ScalePreflightError, match="different Builder head"):
        executor.run(locator=(work,), dry_run=True)
    assert fake.calls == 0


def test_standard_lifecycle_rechecks_mandate_immediately_before_send_started(tmp_path):
    row = _row(901)
    catalog = FakeCatalog([row])
    decisions = iter((True, False))

    def evaluate(_row):
        return type("Decision", (), {"authorized": next(decisions)})()

    result = StandardCampaignCoordinator(
        catalog=catalog, provider=FakeProvider(), runtime_root=tmp_path,
        mandate_evaluator=evaluate).run([row])
    assert result["provider_posts"] == 0
    assert result["counts"] == {"failed_pre_send": 1}
    assert len(catalog.started) == 0


def test_locator_accounting_failure_is_terminal_and_reentry_never_resends(tmp_path):
    catalog, _, packet, prepared = _prepared_catalog(tmp_path)
    fake = FakeLocator()
    def fail_accounting(*_args):
        raise RuntimeError("synthetic accounting interruption")
    executor = ScaleS0Executor(catalog=catalog, attempt_id="attempt:locator", builder_commit_sha="a" * 40, runtime_root=tmp_path,
                               locator_provider=fake, now=lambda: __import__("datetime").datetime(2099, 9, 22, tzinfo=__import__("datetime").timezone.utc),
                               on_reconciled=fail_accounting)
    work = S0LocatorWork(packet.packet_id, prepared.request, prepared.delivery_attempt_id, prepared.client_request_id, packet.locator_query)
    first = executor.run(locator=(work,))
    second = ScaleS0Executor(catalog=catalog, attempt_id="attempt:locator", builder_commit_sha="a" * 40, runtime_root=tmp_path,
                             locator_provider=fake, now=executor.now).run(locator=(work,))
    assert first.counts == {"completed_accounting_failed": 1}
    assert second.counts == {"replayed_terminal": 1} and second.provider_posts == 0
    assert fake.calls == 1


def test_locator_a3_expiry_is_pre_send_and_has_no_provider_post(tmp_path):
    catalog, _, packet, prepared = _prepared_catalog(tmp_path)
    fake = FakeLocator()
    expired = __import__("datetime").datetime(2100, 1, 1, tzinfo=__import__("datetime").timezone.utc)
    executor = ScaleS0Executor(catalog=catalog, attempt_id="attempt:locator", builder_commit_sha="a" * 40,
                               runtime_root=tmp_path, locator_provider=fake, now=lambda: expired)
    work = S0LocatorWork(packet.packet_id, prepared.request, prepared.delivery_attempt_id, prepared.client_request_id, packet.locator_query)
    summary = executor.run(locator=(work,))
    assert summary.counts == {"failed": 1} and summary.provider_posts == 0
    assert catalog.get_provider_request_item(packet.provider_request_identity)["status"] == "prepared"
    assert fake.calls == 0


def test_locator_ambiguous_crossing_is_held_and_reentry_never_resends(tmp_path):
    catalog, _, packet, prepared = _prepared_catalog(tmp_path)
    fake = AmbiguousLocator()
    from .test_s0_locator_search_lifecycle import NOW
    executor = ScaleS0Executor(catalog=catalog, attempt_id="attempt:locator", builder_commit_sha="a" * 40,
                               runtime_root=tmp_path, locator_provider=fake, now=lambda: NOW)
    work = S0LocatorWork(packet.packet_id, prepared.request, prepared.delivery_attempt_id, prepared.client_request_id, packet.locator_query)
    first = executor.run(locator=(work,))
    second = executor.run(locator=(work,))
    assert first.counts == {"failed": 1} and first.provider_posts == 1
    assert second.counts == {"replayed_terminal": 1} and second.provider_posts == 0
    assert catalog.get_provider_request_item(packet.provider_request_identity)["status"] == "send_ambiguous"
    assert fake.calls == 1
