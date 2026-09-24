from charitygraph.s0_locator_discovery import LocatorSearchResponse
from charitygraph.s0_orchestration import ScaleS0Executor, S0LocatorWork

from .test_s0_locator_search_lifecycle import _prepared_catalog


class FakeLocator:
    provider_id = "fake-locator"

    def __init__(self):
        self.calls = 0

    def search(self, *, query, subject_abn, request_identity):
        self.calls += 1
        return LocatorSearchResponse("response:fake-locator", ())


def test_s0_executor_locator_dry_run_never_calls_provider(tmp_path):
    catalog, _, packet, prepared = _prepared_catalog(tmp_path)
    fake = FakeLocator()
    from .test_s0_locator_search_lifecycle import NOW
    executor = ScaleS0Executor(catalog=catalog, attempt_id="attempt:locator", runtime_root=tmp_path, locator_provider=fake, now=lambda: NOW)
    work = S0LocatorWork(packet.packet_id, prepared.request, prepared.delivery_attempt_id, prepared.client_request_id, packet.locator_query)
    summary = executor.run(locator=(work,), dry_run=True)
    assert summary.provider_posts == 0 and summary.counts == {"eligible": 1}
    assert fake.calls == 0


def test_s0_executor_locator_live_and_terminal_reentry_are_idempotent(tmp_path):
    catalog, _, packet, prepared = _prepared_catalog(tmp_path)
    fake = FakeLocator()
    from .test_s0_locator_search_lifecycle import NOW
    executor = ScaleS0Executor(catalog=catalog, attempt_id="attempt:locator", runtime_root=tmp_path, locator_provider=fake, now=lambda: NOW)
    work = S0LocatorWork(packet.packet_id, prepared.request, prepared.delivery_attempt_id, prepared.client_request_id, packet.locator_query)
    first = executor.run(locator=(work,))
    assert catalog.get_provider_request_item(packet.provider_request_identity)["status"] == "completed"
    second = executor.run(locator=(work,))
    assert first.provider_posts == 1 and first.counts == {"completed": 1}
    assert second.provider_posts == 0 and second.counts == {"replayed_terminal": 1}
    assert fake.calls == 1
