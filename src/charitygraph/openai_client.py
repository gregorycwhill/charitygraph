"""Small, credential-safe OpenAI HTTP client for bounded CauseBase jobs.

The API key is read only from the process environment at request time.  It is
never returned, persisted, or included in raised error text.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_URL = "https://api.openai.com/v1"


class OpenAIRequestError(RuntimeError):
    """A deliberately sanitised API error suitable for private run metadata."""

    def __init__(self, message: str, *, status_code: int | None = None, diagnostics: dict[str, Any] | None = None, retryable: bool = False) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.diagnostics = diagnostics or ({"status": status_code} if status_code is not None else {})
        self.retryable = retryable


@dataclass(frozen=True)
class ApiUsage:
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None


@dataclass(frozen=True)
class ApiResult:
    response_id: str | None
    model: str
    status: str | None
    output_text: str
    usage: ApiUsage


def _credential() -> str:
    value = os.environ.get("OPENAI_API_KEY")
    if not value:
        raise OpenAIRequestError("OPENAI_API_KEY is not available to this process")
    return value


def _bounded(value: object, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    return value[:limit]


def _safe_error(error: BaseException) -> OpenAIRequestError:
    if isinstance(error, HTTPError):
        diagnostics: dict[str, Any] = {"status": error.code}
        try:
            raw = error.read(4096)
            parsed = json.loads(raw.decode("utf-8", errors="replace"))
            detail = parsed.get("error") if isinstance(parsed, dict) else None
            if isinstance(detail, dict):
                for key, limit in (("type", 128), ("code", 128), ("param", 256), ("message", 512)):
                    value = _bounded(detail.get(key), limit)
                    if value is not None:
                        diagnostics[key] = value
        except (OSError, UnicodeError, json.JSONDecodeError, AttributeError):
            pass
        parts = [f"OpenAI API request failed with HTTP {error.code}"]
        for key in ("type", "code", "param", "message"):
            if key in diagnostics:
                parts.append(f"{key}={diagnostics[key]}")
        return OpenAIRequestError("; ".join(parts), status_code=error.code, diagnostics=diagnostics, retryable=error.code == 429 or error.code >= 500)
    if isinstance(error, TimeoutError):
        return OpenAIRequestError("OpenAI API request timed out", retryable=True)
    if isinstance(error, URLError):
        return OpenAIRequestError("OpenAI API request could not connect", retryable=True)
    return OpenAIRequestError("OpenAI API request failed", retryable=False)

def _post(path: str, payload: dict[str, Any], *, timeout_seconds: int = 60) -> dict[str, Any]:
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = Request(
        f"{API_URL}{path}",
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {_credential()}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as error:
        raise _safe_error(error) from None


def _output_text(raw: dict[str, Any]) -> str:
    """Read text from raw Responses API output (the SDK exposes a convenience property)."""
    if raw.get("output_text"):
        return str(raw["output_text"])
    parts: list[str] = []
    for item in raw.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                parts.append(str(content["text"]))
    return "".join(parts)


def responses_create(
    *, model: str, input_text: str, text_format: dict[str, Any], max_output_tokens: int = 1_200,
    max_attempts: int = 2, timeout_seconds: int = 60, reasoning: dict[str, Any] | None = None,
    on_retry: Callable[[int, OpenAIRequestError], None] | None = None,
) -> ApiResult:
    """Create one structured response with at most one bounded retry.

    Calls are intentionally serial at this layer. Corpus orchestration controls
    concurrency and cache checks, preventing an accidental retry storm.
    """
    payload = {
        "model": model,
        "input": input_text,
        "max_output_tokens": max_output_tokens,
        "text": {"format": text_format},
    }
    if reasoning is not None:
        payload["reasoning"] = reasoning
    last_error: OpenAIRequestError | None = None
    for attempt in range(max_attempts):
        try:
            raw = _post("/responses", payload, timeout_seconds=timeout_seconds)
            usage = raw.get("usage") or {}
            return ApiResult(
                response_id=raw.get("id"),
                model=raw.get("model", model),
                status=raw.get("status"),
                output_text=_output_text(raw),
                usage=ApiUsage(
                    input_tokens=usage.get("input_tokens"),
                    output_tokens=usage.get("output_tokens"),
                    total_tokens=usage.get("total_tokens"),
                ),
            )
        except OpenAIRequestError as error:
            last_error = error
            if error.retryable and attempt + 1 < max_attempts:
                if on_retry is not None:
                    on_retry(attempt + 1, error)
                time.sleep(1 + attempt)
            elif not error.retryable:
                break
    assert last_error is not None
    raise last_error


def embeddings_create(*, model: str, texts: list[str]) -> tuple[list[list[float]], ApiUsage]:
    if not texts:
        return [], ApiUsage(None, None, None)
    raw = _post("/embeddings", {"model": model, "input": texts})
    rows = sorted(raw.get("data", []), key=lambda row: row["index"])
    usage = raw.get("usage") or {}
    return (
        [row["embedding"] for row in rows],
        ApiUsage(usage.get("prompt_tokens"), None, usage.get("total_tokens")),
    )


def estimate_synthesis_cost(usage: ApiUsage) -> Decimal | None:
    """Current gpt-5-mini non-cached token price, in USD, for run telemetry."""
    if usage.input_tokens is None or usage.output_tokens is None:
        return None
    return (
        Decimal(usage.input_tokens) * Decimal("0.25") / Decimal(1_000_000)
        + Decimal(usage.output_tokens) * Decimal("2.00") / Decimal(1_000_000)
    ).quantize(Decimal("0.000001"))


def estimate_response_cost(model: str, usage: ApiUsage) -> Decimal | None:
    """Estimate text-token cost for approved, replaceable CauseBase models."""
    if usage.input_tokens is None or usage.output_tokens is None:
        return None
    prices = {
        "gpt-5-mini": ("0.25", "2.00"),
        "gpt-5-mini-2025-08-07": ("0.25", "2.00"),
        "gpt-5.6-sol": ("5.00", "30.00"),
        "gpt-5.6-terra": ("2.00", "12.00"),
        "gpt-5.6-luna": ("0.20", "1.20"),
    }
    input_price, output_price = prices.get(model, prices.get(model.split("-")[0], (None, None)))
    if input_price is None:
        return None
    return (
        Decimal(usage.input_tokens) * Decimal(input_price) / Decimal(1_000_000)
        + Decimal(usage.output_tokens) * Decimal(output_price) / Decimal(1_000_000)
    ).quantize(Decimal("0.000001"))
