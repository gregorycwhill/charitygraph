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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class StandardTransportError(RuntimeError):
    def __init__(self, message: str, *, ambiguous: bool = False, systemic: bool = False, status_code: int | None = None, raw_bytes: bytes | None = None, request_id: str | None = None, client_request_id: str | None = None, endpoint: str | None = None, request_started_at: str | None = None, response_headers_received: bool = False) -> None:
        super().__init__(message)
        self.ambiguous = ambiguous
        self.systemic = systemic
        self.status_code = status_code
        self.raw_bytes = raw_bytes
        self.request_id = request_id
        self.client_request_id = client_request_id
        self.endpoint = endpoint
        self.request_started_at = request_started_at
        self.response_headers_received = response_headers_received


class StandardAmbiguous(StandardTransportError):
    def __init__(self, message: str = "Standard POST outcome is ambiguous", *, status_code: int | None = None, raw_bytes: bytes | None = None, request_id: str | None = None, client_request_id: str | None = None, endpoint: str | None = None, request_started_at: str | None = None, response_headers_received: bool = False) -> None:
        super().__init__(message, ambiguous=True, systemic=False, status_code=status_code, raw_bytes=raw_bytes, request_id=request_id, client_request_id=client_request_id, endpoint=endpoint, request_started_at=request_started_at, response_headers_received=response_headers_received)


class StandardSystemic(StandardTransportError):
    def __init__(self, message: str, *, status_code: int | None = None, raw_bytes: bytes | None = None, request_id: str | None = None, client_request_id: str | None = None, endpoint: str | None = None, request_started_at: str | None = None, response_headers_received: bool = False) -> None:
        super().__init__(message, systemic=True, status_code=status_code, raw_bytes=raw_bytes, request_id=request_id, client_request_id=client_request_id, endpoint=endpoint, request_started_at=request_started_at, response_headers_received=response_headers_received)


@dataclass(frozen=True)
class StandardProviderResponse:
    status_code: int
    request_id: str
    body: dict[str, Any]
    raw_bytes: bytes
    client_request_id: str | None = None
    server_request_id: str | None = None
    endpoint: str | None = None
    request_started_at: str | None = None
    response_headers_received: bool = True


class StandardProvider(Protocol):
    def create_response_once(self, body: bytes, *, client_request_id: str, request_started_at: str | None = None) -> StandardProviderResponse: ...

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
    def _decode(status_code: int, headers: Any, raw: bytes, *, client_request_id: str, endpoint: str, request_started_at: str) -> StandardProviderResponse:
        server_request_id = headers.get("x-request-id")
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StandardAmbiguous("provider returned an unreadable response body", status_code=status_code, raw_bytes=raw, request_id=server_request_id, client_request_id=client_request_id, endpoint=endpoint, request_started_at=request_started_at, response_headers_received=True) from exc
        if not isinstance(body, dict) or not isinstance(body.get("id"), str) or not body["id"]:
            raise StandardAmbiguous("provider response did not contain a trustworthy response ID", status_code=status_code, raw_bytes=raw, request_id=server_request_id, client_request_id=client_request_id, endpoint=endpoint, request_started_at=request_started_at, response_headers_received=True)
        request_id = server_request_id or body["id"]
        return StandardProviderResponse(status_code, str(request_id), body, raw, client_request_id, server_request_id, endpoint, request_started_at, True)

    def create_response_once(self, body: bytes, *, client_request_id: str, request_started_at: str | None = None) -> StandardProviderResponse:
        if not isinstance(body, bytes) or not body:
            raise ValueError("Standard request body must be non-empty UTF-8 bytes")
        validate_client_request_id(client_request_id)
        started = request_started_at or datetime.now(timezone.utc).isoformat(timespec="microseconds")
        request = Request(self.base_url, data=body, method="POST", headers={"Authorization": f"Bearer {self._key()}", "Content-Type": "application/json; charset=utf-8", "X-Client-Request-Id": client_request_id})
        response_headers_received = False
        response_headers = None
        try:
            response = urlopen(request, timeout=120)
            response_headers_received = True
            response_headers = response.headers
            with response:
                raw = response.read()
                return self._decode(response.status, response.headers, raw, client_request_id=client_request_id, endpoint=self.base_url, request_started_at=started)
        except HTTPError as exc:
            raw = exc.read()
            provider_request_id = exc.headers.get("x-request-id") if exc.headers else None
            # These failures invalidate campaign-wide execution authority or
            # routing; stop the feeder before launching more independent rows.
            if exc.code in {401, 402, 403, 404, 408, 429} or exc.code >= 500:
                raise StandardSystemic(f"provider systemic HTTP {exc.code}", status_code=exc.code, raw_bytes=raw, request_id=provider_request_id, client_request_id=client_request_id, endpoint=self.base_url, request_started_at=started, response_headers_received=True) from None
            try:
                detail = json.loads(raw.decode("utf-8"))
                message = detail.get("error", {}).get("message", "provider terminal request failure") if isinstance(detail, dict) else "provider terminal request failure"
            except Exception:
                message = "provider terminal request failure"
            raise StandardTransportError(str(message)[:512], status_code=exc.code, raw_bytes=raw, request_id=provider_request_id, client_request_id=client_request_id, endpoint=self.base_url, request_started_at=started, response_headers_received=True) from None
        except (URLError, TimeoutError, OSError) as exc:
            server_request_id = response_headers.get("x-request-id") if response_headers is not None else None
            raise StandardAmbiguous("Standard POST connection outcome is ambiguous", request_id=server_request_id, client_request_id=client_request_id, endpoint=self.base_url, request_started_at=started, response_headers_received=response_headers_received) from exc

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


def validate_client_request_id(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 512 or not value.isascii():
        raise ValueError("X-Client-Request-Id must be non-empty ASCII and at most 512 characters")
    return value


def client_request_id_for_physical_attempt(physical_attempt_id: str) -> str:
    """Return the immutable, non-secret trace ID for one physical attempt."""
    if not isinstance(physical_attempt_id, str) or not physical_attempt_id or not physical_attempt_id.isascii():
        raise ValueError("physical attempt identity must be non-empty ASCII")
    return validate_client_request_id("cgpa-" + hashlib.sha256(physical_attempt_id.encode("ascii")).hexdigest())


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

    def __init__(self, *, catalog: Any, provider: StandardProvider, runtime_root: Path, max_concurrency: int = 4, prior_ambiguous_crossings: int = 0, ambiguity_stop_threshold: int = 2, now: Any = None, validator: Callable[[dict[str, Any]], None] | None = None, on_reconciled: Callable[[dict[str, Any], StandardProviderResponse, dict[str, Any]], None] | None = None, mandate_evaluator: Callable[[dict[str, Any]], Any] | None = None) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be positive")
        if prior_ambiguous_crossings < 0 or ambiguity_stop_threshold < 1 or prior_ambiguous_crossings >= ambiguity_stop_threshold:
            raise ValueError("ambiguity threshold must exceed the recorded prior ambiguity count")
        self.catalog = catalog
        self.provider = provider
        self.runtime_root = Path(runtime_root)
        self.max_concurrency = max_concurrency
        self.prior_ambiguous_crossings = prior_ambiguous_crossings
        self.ambiguity_stop_threshold = ambiguity_stop_threshold
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
        physical_attempt_id = row.get("physical_attempt_id")
        client_request_id: str | None = None
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
            physical_attempt_id = row["physical_attempt_id"]
            client_request_id = client_request_id_for_physical_attempt(physical_attempt_id)
            request_started_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
            self.catalog.prepare_standard_transport_trace(
                attempt_id, client_request_id=client_request_id, endpoint=OpenAIHTTPStandardClient.base_url,
                request_body_sha256=body_sha256(body), now=self.now,
            )
            self.catalog.mark_standard_send_started(attempt_id, client_request_id=client_request_id, now=request_started_at)
            with self._active_lock:
                self._active += 1
                self.max_observed_concurrency = max(self.max_observed_concurrency, self._active)
            try:
                posted = True
                response = self.provider.create_response_once(body, client_request_id=client_request_id, request_started_at=request_started_at)
            finally:
                with self._active_lock:
                    self._active -= 1
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            self.catalog.record_standard_transport_outcome(
                physical_attempt_id, status="PROVIDER_RESPONSE_RECEIVED", response_headers_received=response.response_headers_received,
                server_request_id=response.server_request_id, response_identity=response.body.get("id"),
                provider_model_identity=response.body.get("model"), usage=response.body.get("usage"), now=self.now,
            )
            raw_path.write_bytes(response.raw_bytes)
            meta_path.write_text(json.dumps({"status_code": response.status_code, "request_id": response.request_id}, sort_keys=True), encoding="utf-8")
            result = self._finish_response(row, attempt_id, response, posted=True, raw_path=raw_path)
            if result.status == "completed":
                self.catalog.record_standard_transport_outcome(physical_attempt_id, status="COMPLETED", response_headers_received=True, server_request_id=response.server_request_id, response_identity=response.body.get("id"), provider_model_identity=response.body.get("model"), usage=response.body.get("usage"), now=self.now)
            return result
        except StandardTransportError as exc:
            failure_class = "ambiguous_transport" if exc.ambiguous else ("systemic_provider" if exc.systemic else "terminal_provider")
            if not posted:
                failure_class = "pre_send_validation"
            if physical_attempt_id and client_request_id:
                outcome = "PROVIDER_CROSSING_AMBIGUOUS" if exc.ambiguous else ("PROVIDER_REJECTED" if posted else "LOCAL_PRE_SEND_FAILURE")
                try:
                    self.catalog.record_standard_transport_outcome(physical_attempt_id, status=outcome, response_headers_received=exc.response_headers_received, server_request_id=exc.request_id, transport_exception=str(exc), now=self.now)
                except Exception:
                    pass
            self.catalog.settle_standard_failure(row["delivery_attempt_id"], failure_class=failure_class, message=str(exc), ambiguous=exc.ambiguous, now=self.now)
            status = "ambiguous" if exc.ambiguous else ("failed_terminal" if posted else "failed_pre_send")
            return StandardRunResult(request_id, status, int(posted), exc.systemic, error=str(exc))
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
                if physical_attempt_id and client_request_id:
                    self.catalog.record_standard_transport_outcome(physical_attempt_id, status="PROVIDER_CROSSING_AMBIGUOUS" if posted else "LOCAL_PRE_SEND_FAILURE", response_headers_received=False, transport_exception=str(exc), now=self.now)
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
        ambiguous_crossings = self.prior_ambiguous_crossings
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
                    if result.status == "ambiguous":
                        ambiguous_crossings += 1
                        if ambiguous_crossings >= self.ambiguity_stop_threshold:
                            stop = True
                    if result.stop_campaign:
                        stop = True
        results.sort(key=lambda result: result.request_item_id)
        counts = {status: sum(result.status == status for result in results) for status in {result.status for result in results}}
        return {"results": [result.__dict__ for result in results], "counts": counts, "stop_campaign": stop, "unattempted": len(ordered) - len(results), "max_observed_concurrency": self.max_observed_concurrency, "provider_posts": sum(result.provider_posts for result in results), "ambiguous_crossings": ambiguous_crossings, "ambiguity_stop_threshold": self.ambiguity_stop_threshold}


__all__ = ["StandardTransportError", "StandardAmbiguous", "StandardSystemic", "StandardProviderResponse", "OpenAIHTTPStandardClient", "StandardCampaignCoordinator", "canonical_standard_body_bytes", "body_sha256", "validate_client_request_id", "client_request_id_for_physical_attempt"]
