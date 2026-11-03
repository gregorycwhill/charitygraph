"""Bounded, revision-pinned acquisition of charity Wikipedia pages.

This module is deliberately mechanical: it resolves only the supplied title,
never searches Wikipedia and never follows links or citations.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Callable, Mapping, Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen


TERMINAL_STATES = {"CAPTURED", "ABSENT", "NOT_BOUND", "UNAVAILABLE"}


@dataclass(frozen=True)
class WikipediaPlanItem:
    charity_id: str
    charity_name: str
    title: str


@dataclass(frozen=True)
class Attempt:
    ordinal: int
    url: str
    started_at: str
    status: int | None = None
    retry_after_seconds: float | None = None
    error: str | None = None


@dataclass
class WikipediaResult:
    charity_id: str
    charity_name: str
    requested_title: str
    state: str
    resolved_title: str | None = None
    revision_id: str | None = None
    page_url: str | None = None
    raw_hash: str | None = None
    representation_hash: str | None = None
    raw_path: str | None = None
    representation_path: str | None = None
    terminal_reason: str | None = None
    attempts: list[Attempt] = field(default_factory=list)


class HttpTransport(Protocol):
    def __call__(self, request: Request) -> tuple[int, Mapping[str, str], bytes]: ...


def _default_transport(request: Request) -> tuple[int, Mapping[str, str], bytes]:
    with urlopen(request, timeout=30) as response:  # noqa: S310 - fixed MediaWiki endpoint
        return response.status, dict(response.headers.items()), response.read()


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _retry_after(headers: Mapping[str, str], now: Callable[[], float]) -> float | None:
    value = headers.get("Retry-After") or headers.get("retry-after")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            return max(0.0, (parsedate_to_datetime(value).timestamp() - now()))
        except (TypeError, ValueError, OverflowError):
            return None


def _request_json(endpoint: str, params: Mapping[str, str], user_agent: str, transport: HttpTransport):
    url = endpoint + "?" + urlencode(params)
    request = Request(url, headers={"User-Agent": user_agent, "Accept": "application/json"})
    return url, transport(request)


def acquire_wikipedia(
    plan: list[WikipediaPlanItem] | tuple[WikipediaPlanItem, ...],
    retention_root: Path,
    *,
    endpoint: str = "https://en.wikipedia.org/w/api.php",
    user_agent: str,
    max_attempts: int = 4,
    base_backoff_seconds: float = 1.0,
    throttle_seconds: float = 0.2,
    transport: HttpTransport = _default_transport,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.time,
) -> tuple[WikipediaResult, ...]:
    """Acquire exactly the supplied titles, returning one terminal result each."""
    if not user_agent or "(" not in user_agent:
        raise ValueError("user_agent must identify the application and contact information")
    retention_root.mkdir(parents=True, exist_ok=True)
    results: list[WikipediaResult] = []
    for item in plan:
        result = WikipediaResult(item.charity_id, item.charity_name, item.title, "UNAVAILABLE")
        params = {"action": "query", "format": "json", "formatversion": "2", "prop": "revisions", "rvprop": "ids|content", "rvslots": "main", "titles": item.title}
        for ordinal in range(1, max_attempts + 1):
            if ordinal > 1:
                sleep(throttle_seconds)
            try:
                url, (status, headers, body) = _request_json(endpoint, params, user_agent, transport)
                retry_after = _retry_after(headers, now) if status == 429 else None
                result.attempts.append(Attempt(ordinal, url, _iso_now(), status, retry_after))
                if status == 429 and ordinal < max_attempts:
                    sleep(retry_after if retry_after is not None else base_backoff_seconds * (2 ** (ordinal - 1)))
                    continue
                if status != 200:
                    result.terminal_reason = f"HTTP_{status}"
                    break
                payload = json.loads(body)
                pages = payload.get("query", {}).get("pages", [])
                page = pages[0] if pages else None
                if not page or page.get("missing") is True:
                    result.state, result.terminal_reason = "ABSENT", "EXACT_TITLE_MISSING"
                    break
                resolved = page.get("title")
                if resolved != item.title:
                    result.state, result.terminal_reason = "NOT_BOUND", "TITLE_RESOLUTION_CHANGED"
                    break
                revisions = page.get("revisions") or []
                if not revisions or not revisions[0].get("revid"):
                    result.state, result.terminal_reason = "UNAVAILABLE", "NO_REVISION"
                    break
                revision_id = str(revisions[0]["revid"])
                raw = body
                representation = json.dumps({"title": resolved, "revision_id": revision_id, "wikitext": revisions[0].get("slots", {}).get("main", {}).get("content", "")}, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
                raw_hash, representation_hash = hashlib.sha256(raw).hexdigest(), hashlib.sha256(representation).hexdigest()
                raw_path = retention_root / f"raw-{raw_hash}.json"
                rep_path = retention_root / f"representation-{representation_hash}.json"
                if not raw_path.exists(): raw_path.write_bytes(raw)
                if not rep_path.exists(): rep_path.write_bytes(representation)
                result.state, result.resolved_title, result.revision_id = "CAPTURED", resolved, revision_id
                result.page_url = f"https://en.wikipedia.org/w/index.php?oldid={revision_id}"
                result.raw_hash, result.representation_hash = raw_hash, representation_hash
                result.raw_path, result.representation_path = str(raw_path), str(rep_path)
                break
            except Exception as exc:  # transport/TLS/JSON failures are auditable attempts
                result.attempts.append(Attempt(ordinal, endpoint, _iso_now(), error=type(exc).__name__ + ": " + str(exc)))
                result.terminal_reason = type(exc).__name__
                if ordinal < max_attempts:
                    sleep(base_backoff_seconds * (2 ** (ordinal - 1)))
        if result.state not in TERMINAL_STATES:
            result.state = "UNAVAILABLE"
        results.append(result)
    return tuple(results)


def write_audit(results: tuple[WikipediaResult, ...], path: Path) -> None:
    """Write a stable, line-oriented audit manifest for replay and review."""
    path.write_text(json.dumps([asdict(result) for result in results], ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
