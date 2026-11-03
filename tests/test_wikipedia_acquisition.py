import json
from pathlib import Path

from charitygraph.wikipedia_acquisition import WikipediaPlanItem, acquire_wikipedia


def test_429_honours_retry_after_and_captures_revision(tmp_path: Path):
    calls = []
    sleeps = []

    def transport(request):
        calls.append(request.full_url)
        if len(calls) == 1:
            return 429, {"Retry-After": "7"}, b"{}"
        payload = {"query": {"pages": [{"title": "Example Charity", "revisions": [{"revid": 123, "slots": {"main": {"content": "== About ==\nText"}}}]}]}}
        return 200, {}, json.dumps(payload).encode()

    result = acquire_wikipedia(
        [WikipediaPlanItem("c1", "Example Charity", "Example Charity")],
        tmp_path,
        user_agent="CharityGraph/1.0 (engineering@example.invalid)",
        transport=transport,
        sleep=sleeps.append,
    )[0]

    assert result.state == "CAPTURED"
    assert result.revision_id == "123"
    assert result.page_url.endswith("oldid=123")
    assert result.attempts[0].status == 429
    assert 7.0 in sleeps
    assert len(calls) == 2
    assert not any("https://" in line for line in json.loads(Path(result.representation_path).read_text()).get("wikitext", "").splitlines())


def test_missing_page_is_absent_without_search_or_substitution(tmp_path: Path):
    urls = []

    def transport(request):
        urls.append(request.full_url)
        return 200, {}, json.dumps({"query": {"pages": [{"title": "No Such Charity", "missing": True}]}}).encode()

    result = acquire_wikipedia(
        [WikipediaPlanItem("c2", "No Such Charity", "No Such Charity")],
        tmp_path,
        user_agent="CharityGraph/1.0 (engineering@example.invalid)",
        transport=transport,
        sleep=lambda _: None,
    )[0]
    assert result.state == "ABSENT"
    assert result.terminal_reason == "EXACT_TITLE_MISSING"
    assert len(urls) == 1
    assert "list=search" not in urls[0]

