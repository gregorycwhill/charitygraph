"""One-shot Standard Responses transport and bounded Phase-5 coordinator.

This is deliberately separate from the legacy retrying Responses helper and
from Batch transport.  It accepts already-pinned request bodies and never
reconstructs or retries them.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from concurrent.futures import Future, ThreadPoolExecutor, wait, FIRST_COMPLETED
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class StandardTransportError(RuntimeError):
    def __init__(self, message: str, *, ambiguous: bool = False, systemic: bool = False, status_code: int | None = None) -> None:
        super().__init__(message)
        self.ambiguous = ambiguous
        self.systemic = systemic
        self.status_code = status_code


class StandardAmbiguous(StandardTransportError):
    def __init__(self, message: str = "Standard POST outcome is ambiguous") -> None:
        super().__init__(message, ambiguous=True, systemic=True)


class StandardSystemic(StandardTransportError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message, systemic=True, status_code=status_code)


@dataclass(frozen=True)
class StandardProviderResponse:
    status_code: int
    request_id: str
    body: dict[str, Any]
    raw_bytes: bytes


class StandardProvider(Protocol):
    def create_response_once(self, body: bytes) -> StandardProviderResponse: ...

    def retrieve_response(self, response_id: str) -> StandardProviderResponse: ...


class OpenAIHTTPStandardClient:
    """Exactly-one-POST OpenAI Responses adapter."""

    base_url = "https://api.openai.com/v1/responses"

    def _key(self) -> str:
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise StandardSystemic("OPENAI_API_KEY is not available")
        return key

    @staticmethod
    def _decode(status_code: int, headers: Any, raw: bytes) -> StandardProviderResponse:
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StandardAmbiguous("provider returned an unreadable response body") from exc
        if not isinstance(body, dict) or not isinstance(body.get("id"), str) or not body["id"]:
            raise StandardAmbiguous("provider response did not contain a trustworthy response ID")
        request_id = headers.get("x-request-id") or body["id"]
        return StandardProviderResponse(status_code, str(request_id), body, raw)

    def create_response_once(self, body: bytes) -> StandardProviderResponse:
        if not isinstance(body, bytes) or not body:
            raise ValueError("Standard request body must be non-empty UTF-8 bytes")
        request = Request(self.base_url, data=body, method="POST", headers={"Authorization": f"Bearer {self._key()}", "Content-Type": "application/json; charset=utf-8"})
        try:
            with urlopen(request, timeout=120) as response:
                return self._decode(response.status, response.headers, response.read())
        except HTTPError as exc:
            raw = exc.read(8192)
            # These failures invalidate campaign-wide execution authority or
            # routing; stop the feeder before launching more independent rows.
            if exc.code in {401, 402, 403, 404, 408, 429} or exc.code >= 500:
                raise StandardSystemic(f"provider systemic HTTP {exc.code}", status_code=exc.code) from None
            try:
                detail = json.loads(raw.decode("utf-8"))
                message = detail.get("error", {}).get("message", "provider terminal request failure") if isinstance(detail, dict) else "provider terminal request failure"
            except Exception:
                message = "provider terminal request failure"
            raise StandardTransportError(str(message)[:512], status_code=exc.code) from None
        except (URLError, TimeoutError, OSError) as exc:
            raise StandardAmbiguous("Standard POST connection outcome is ambiguous") from exc

    def retrieve_response(self, response_id: str) -> StandardProviderResponse:
        if not response_id or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for ch in response_id):
            raise ValueError("invalid provider response ID")
        request = Request(f"https://api.openai.com/v1/responses/{response_id}", method="GET", headers={"Authorization": f"Bearer {self._key()}"})
        try:
            with urlopen(request, timeout=120) as response:
                return self._decode(response.status, response.headers, response.read())
        except Exception as exc:
            raise StandardSystemic("provider response retrieval failed") from exc


def canonical_standard_body_bytes(body: dict[str, Any]) -> bytes:
    return json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def body_sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _response_completed(response: StandardProviderResponse) -> bool:
    return response.status_code in range(200, 300) and response.body.get("status") == "completed" and response.body.get("incomplete_details") is None


@dataclass(frozen=True)
class StandardRunResult:
    request_item_id: str
    status: str
    provider_posts: int
    stop_campaign: bool = False
    response_id: str | None = None
    parse_status: str | None = None
    error: str | None = None


class StandardCampaignCoordinator:
    """Bounded feeder for one-shot Standard request items."""

    def __init__(self, *, catalog: Any, provider: StandardProvider, runtime_root: Path, max_concurrency: int = 4, now: Any = None, validator: Callable[[dict[str, Any]], None] | None = None, on_reconciled: Callable[[dict[str, Any], StandardProviderResponse, dict[str, Any]], None] | None = None, mandate_evaluator: Callable[[dict[str, Any]], Any] | None = None) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be positive")
        self.catalog = catalog
        self.provider = provider
        self.runtime_root = Path(runtime_root)
        self.max_concurrency = max_concurrency
        self.now = now
        self.validator = validator
        self.on_reconciled = on_reconciled
        self.mandate_evaluator = mandate_evaluator
        self.max_observed_concurrency = 0
        self._active = 0
        self._active_lock = threading.Lock()

    def _validate_pinned(self, row: dict[str, Any]) -> bytes:
        if row.get("delivery_mode") != "standard" or row.get("model") != "gpt-5.6-luna" or row.get("reasoning_effort") != "low":
            raise StandardSystemic("pinned Standard route mismatch")
        request_body = row["request_body"]
        body = canonical_standard_body_bytes(request_body)
        if body_sha256(body) != row["request_body_sha256"]:
            raise StandardSystemic("pinned Standard request body hash mismatch")
        provider_schema_name = row.get("provider_schema_name")
        if not isinstance(provider_schema_name, str) or not provider_schema_name:
            raise StandardSystemic("pinned provider schema is missing")
        if row.get("max_output_tokens") != 8000:
            raise StandardSystemic("pinned output ceiling mismatch")
        if row.get("provider_request_item_id", "").split(":", 1)[0] != "requestitem":
            raise StandardSystemic("provider request identity is malformed")
        if row["provider_request_item_id"].split(":", 1)[-1] != row["provider_request_item_id"].split(":", 1)[-1].lower():
            raise StandardSystemic("provider request identity is malformed")
        if request_body.get("model") != row["model"] or request_body.get("max_output_tokens") != row["max_output_tokens"]:
            raise StandardSystemic("provider body does not match pinned model/output ceiling")
        if request_body.get("reasoning", {}).get("effort") != row["reasoning_effort"]:
            raise StandardSystemic("provider body does not match pinned reasoning")
        if row.get("provider_service_tier") is not None or "service_tier" in request_body:
            raise StandardSystemic("Standard request contains an unauthorized service tier")
        metadata = request_body.get("metadata")
        contract_identity = row.get("contract_identity_hash", row.get("semantic_contract_hash"))
        if not isinstance(metadata, dict) or metadata.get("logical_task_id") != row["logical_task_id"] or metadata.get("semantic_contract_hash") != contract_identity:
            raise StandardSystemic("provider body metadata does not match pinned semantic identity")
        text_format = request_body.get("text", {}).get("format", {})
        if text_format.get("name") != provider_schema_name or text_format.get("type") != "json_schema" or text_format.get("strict") is not True:
            raise StandardSystemic("provider structured-output contract is not pinned")
        schema_bytes = json.dumps(text_format.get("schema"), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if hashlib.sha256(schema_bytes).hexdigest() != row["schema_hash"]:
            raise StandardSystemic("provider schema hash does not match pinned schema")
        return body

    def _one(self, row: dict[str, Any]) -> StandardRunResult:
        request_id = row["provider_request_item_id"]
        durable = self.catalog.get_provider_request_item(request_id)
        if durable is None:
            return StandardRunResult(request_id, "failed_pre_send", 0, True, error="durable request item missing")
        if durable["status"] in {"completed", "failed", "held", "send_ambiguous", "cancelled"}:
            return StandardRunResult(request_id, "replayed_terminal", 0)
        posted = False
        try:
            body = self._validate_pinned(row)
            if self.mandate_evaluator is not None:
                evaluation = self.mandate_evaluator(row)
                if not bool(getattr(evaluation, "authorized", False)):
                    raise StandardSystemic("execution mandate proof did not authorize this request")
            attempt_id = row["delivery_attempt_id"]
            raw_path = self.runtime_root / "standard-results" / f"{request_id.replace(':', '_')}.json"
            meta_path = raw_path.with_suffix(".meta.json")
            if durable["status"] != "prepared":
                if raw_path.exists() and meta_path.exists():
                    saved = json.loads(raw_path.read_bytes().decode("utf-8"))
                    meta = json.loads(meta_path.read_bytes().decode("utf-8"))
                    response = StandardProviderResponse(int(meta["status_code"]), str(meta["request_id"]), saved, raw_path.read_bytes())
                    return self._finish_response(row, attempt_id, response, posted=False, raw_path=raw_path)
                self.catalog.settle_standard_failure(attempt_id, failure_class="ambiguous_restart", message="Standard send-started state has no recoverable response identity", ambiguous=True, now=self.now)
                return StandardRunResult(request_id, "ambiguous", 0, True, error="send-started state requires reconciliation")
            self.catalog.mark_standard_send_started(attempt_id, now=self.now)
            with self._active_lock:
                self._active += 1
                self.max_observed_concurrency = max(self.max_observed_concurrency, self._active)
            try:
                posted = True
                response = self.provider.create_response_once(body)
            finally:
                with self._active_lock:
                    self._active -= 1
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_bytes(response.raw_bytes)
            meta_path.write_text(json.dumps({"status_code": response.status_code, "request_id": response.request_id}, sort_keys=True), encoding="utf-8")
            return self._finish_response(row, attempt_id, response, posted=True, raw_path=raw_path)
        except StandardTransportError as exc:
            failure_class = "ambiguous_transport" if exc.ambiguous else ("systemic_provider" if exc.systemic else "terminal_provider")
            if not posted:
                failure_class = "pre_send_validation"
            self.catalog.settle_standard_failure(row["delivery_attempt_id"], failure_class=failure_class, message=str(exc), ambiguous=exc.ambiguous, now=self.now)
            status = "ambiguous" if exc.ambiguous else ("failed_terminal" if posted else "failed_pre_send")
            return StandardRunResult(request_id, status, int(posted), exc.ambiguous or exc.systemic, error=str(exc))
        except Exception as exc:
            try:
                # Once POST may have begun, an unclassified exception cannot
                # prove that OpenAI did not accept it. Quarantine and stop;
                # never make it eligible for a resend.
                self.catalog.settle_standard_failure(
                    row["delivery_attempt_id"],
                    failure_class="ambiguous_transport" if posted else "pre_send_or_lifecycle",
                    message=str(exc), ambiguous=posted, now=self.now,
                )
            except Exception:
                pass
            return StandardRunResult(
                request_id, "ambiguous" if posted else "failed_pre_send", int(posted), True,
                error=str(exc)[:512],
            )

    def _finish_response(self, row: dict[str, Any], attempt_id: str, response: StandardProviderResponse, *, posted: bool, raw_path: Path) -> StandardRunResult:
        request_id = row["provider_request_item_id"]
        receipt_id = "standard-receipt:" + hashlib.sha256((request_id + ":" + response.body["id"]).encode()).hexdigest()
        result_ref = "standard-result:" + body_sha256(response.raw_bytes)
        usage = response.body.get("usage") or {}
        post_count = int(posted)
        if not _response_completed(response):
            self.catalog.settle_standard_failure(attempt_id, failure_class="provider_terminal", message="Responses body was not completed", ambiguous=False, now=self.now)
            return StandardRunResult(request_id, "failed_terminal", post_count, False, response_id=response.body.get("id"), error="Responses body was not completed")
        if hasattr(self.catalog, "persist_provider_receipt"):
            self.catalog.persist_provider_receipt(physical_attempt_id=self.catalog.get_provider_request_item(request_id)["physical_attempt_id"], provider_receipt_id=receipt_id, raw_result_ref=str(raw_path), usage=usage, now=self.now)
        self.catalog.complete_standard_delivery(attempt_id, provider_request_id=response.request_id, provider_receipt_id=receipt_id, raw_result_ref=str(raw_path), usage=usage, result_ref=result_ref, now=self.now)
        if self.on_reconciled is not None:
            try:
                self.on_reconciled(row, response, usage)
            except Exception as exc:
                return StandardRunResult(request_id, "completed_accounting_failed", post_count, False, response_id=response.body["id"], error=str(exc)[:512])
        parse_status = "valid"
        if self.validator is not None:
            try:
                self.validator(response.body)
            except Exception as exc:
                parse_status = "invalid"
                return StandardRunResult(request_id, "completed_parse_failed", post_count, False, response_id=response.body["id"], parse_status=parse_status, error=str(exc)[:512])
        return StandardRunResult(request_id, "completed", post_count, False, response_id=response.body["id"], parse_status=parse_status)

    def run(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        """Feed at most ``max_concurrency`` futures; never enqueue the cohort."""
        ordered = sorted(rows, key=lambda row: row["provider_request_item_id"])
        results: list[StandardRunResult] = []
        next_index = 0
        stop = False
        with ThreadPoolExecutor(max_workers=self.max_concurrency) as pool:
            active: dict[Future[StandardRunResult], dict[str, Any]] = {}
            while next_index < len(ordered) or active:
                while not stop and next_index < len(ordered) and len(active) < self.max_concurrency:
                    row = ordered[next_index]
                    next_index += 1
                    future = pool.submit(self._one, row)
                    active[future] = row
                if not active:
                    break
                done, _ = wait(tuple(active), return_when=FIRST_COMPLETED)
                for future in done:
                    active.pop(future)
                    result = future.result()
                    results.append(result)
                    if result.stop_campaign:
                        stop = True
        results.sort(key=lambda result: result.request_item_id)
        counts = {status: sum(result.status == status for result in results) for status in {result.status for result in results}}
        return {"results": [result.__dict__ for result in results], "counts": counts, "stop_campaign": stop, "unattempted": len(ordered) - len(results), "max_observed_concurrency": self.max_observed_concurrency, "provider_posts": sum(result.provider_posts for result in results)}


__all__ = ["StandardTransportError", "StandardAmbiguous", "StandardSystemic", "StandardProviderResponse", "OpenAIHTTPStandardClient", "StandardCampaignCoordinator", "canonical_standard_body_bytes", "body_sha256"]
