"""Default-deny, injectable OpenAI Batch transport for the Phase-5 Factory.

This module contains no HTTP implementation and performs no provider operation
unless a caller supplies an explicitly authorised provider client.  The client
boundary is intentionally small so production HTTP and provider-shaped tests
share the same lifecycle and reconciliation code.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol, Sequence

from .phase5_openai_dry_run import BatchPayloadError, parse_provider_result, validate_batch_jsonl_bytes


class BatchProviderClient(Protocol):
    def upload_batch_file(self, content: bytes, *, purpose: str) -> str: ...
    def create_batch(self, *, input_file_id: str, endpoint: str, completion_window: str, metadata: dict[str, str]) -> str: ...
    def retrieve_batch(self, batch_id: str) -> dict[str, Any]: ...
    def retrieve_file_content(self, file_id: str) -> bytes: ...


class OpenAIHTTPBatchClient:
    """Minimal real OpenAI Batch adapter used by the existing lifecycle."""

    base_url = "https://api.openai.com/v1"

    def _key(self) -> str:
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not available")
        return key

    def _request(self, method: str, path: str, *, body: bytes | None = None, content_type: str = "application/json") -> dict[str, Any] | bytes:
        request = Request(self.base_url + path, data=body, method=method, headers={"Authorization": f"Bearer {self._key()}", "Content-Type": content_type})
        try:
            with urlopen(request, timeout=120) as response:
                payload = response.read()
        except (HTTPError, URLError, TimeoutError) as exc:
            raise RuntimeError("OpenAI Batch HTTP operation failed") from exc
        if path.endswith("/content"):
            return payload
        return json.loads(payload.decode("utf-8"))

    def upload_batch_file(self, content: bytes, *, purpose: str) -> str:
        boundary = "----charitygraph-" + uuid.uuid4().hex
        parts = [
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"purpose\"\r\n\r\n{purpose}\r\n".encode(),
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"batch.jsonl\"\r\nContent-Type: application/jsonl\r\n\r\n".encode() + content + b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
        result = self._request("POST", "/files", body=b"".join(parts), content_type=f"multipart/form-data; boundary={boundary}")
        file_id = result.get("id") if isinstance(result, dict) else None
        if not isinstance(file_id, str) or not file_id:
            raise RuntimeError("OpenAI file upload returned no file ID")
        return file_id

    def create_batch(self, *, input_file_id: str, endpoint: str, completion_window: str, metadata: dict[str, str]) -> str:
        result = self._request("POST", "/batches", body=json.dumps({"input_file_id": input_file_id, "endpoint": endpoint, "completion_window": completion_window, "metadata": metadata}, separators=(",", ":")).encode())
        batch_id = result.get("id") if isinstance(result, dict) else None
        if not isinstance(batch_id, str) or not batch_id:
            raise RuntimeError("OpenAI Batch creation returned no Batch ID")
        return batch_id

    def retrieve_batch(self, batch_id: str) -> dict[str, Any]:
        result = self._request("GET", f"/batches/{batch_id}")
        if not isinstance(result, dict):
            raise RuntimeError("OpenAI Batch retrieval returned an invalid object")
        return result

    def retrieve_file_content(self, file_id: str) -> bytes:
        result = self._request("GET", f"/files/{file_id}/content")
        if not isinstance(result, bytes):
            raise RuntimeError("OpenAI file content retrieval returned an invalid payload")
        return result


class BatchTransportError(RuntimeError):
    """A provider operation failed before a trustworthy result was known."""


class BatchSubmissionAmbiguous(BatchTransportError):
    """The provider may have accepted a file or batch; automatic resend is forbidden."""


@dataclass(frozen=True)
class BatchAuthorization:
    approved_run: str
    plan_hash: str
    packet_hash: str
    pricing_snapshot_id: str
    model: str
    projected_usd: Decimal
    projected_aud: Decimal
    max_usd: Decimal
    max_aud: Decimal
    real_provider_enabled: bool = False
    no_automatic_retry: bool = True
    no_fallback: bool = True
    max_submissions: int = 1
    payload_sha256: str | None = None
    payload_bytes: int | None = None
    authorized_custom_ids: tuple[str, ...] = ()
    payload_local_ref: str | None = None

    def assert_allowed(self, *, run_id: str, model: str) -> None:
        if not self.real_provider_enabled:
            raise PermissionError("real-provider Batch transmission is disabled")
        if self.approved_run != run_id or self.model != model:
            raise PermissionError("Batch authorization does not match the run or model route")
        if not self.plan_hash or not self.packet_hash or not self.pricing_snapshot_id:
            raise PermissionError("Batch authorization is missing plan, packet, or pricing identity")
        if self.projected_usd > self.max_usd or self.projected_aud > self.max_aud:
            raise PermissionError("Batch projected exposure exceeds its hard ceiling")
        if not self.no_automatic_retry or not self.no_fallback or self.max_submissions != 1:
            raise PermissionError("Batch authorization permits an unsafe retry or fallback policy")

    def assert_payload(self, payload: bytes, *, custom_ids: Sequence[str]) -> None:
        try:
            validate_batch_jsonl_bytes(payload, expected_custom_ids=custom_ids or self.authorized_custom_ids or None)
        except BatchPayloadError as exc:
            raise BatchTransportError(str(exc)) from exc
        digest = hashlib.sha256(payload).hexdigest()
        if self.payload_sha256 is not None and digest != self.payload_sha256:
            raise BatchTransportError("Batch payload SHA-256 does not match authorization")
        if self.payload_bytes is not None and len(payload) != self.payload_bytes:
            raise BatchTransportError("Batch payload byte length does not match authorization")
        if self.authorized_custom_ids and set(custom_ids) != set(self.authorized_custom_ids):
            raise BatchTransportError("Batch payload custom_id set does not match authorization")


@dataclass(frozen=True)
class BatchReconciliation:
    delivery_job_id: str
    provider_batch_id: str
    provider_status: str
    item_statuses: tuple[dict[str, Any], ...]
    output_retrieved: bool
    error_retrieved: bool


def _jsonl(payload: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in payload.decode("utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise BatchTransportError("Batch file contains a non-object line")
        rows.append(value)
    return rows


class OpenAIBatchTransport:
    provider_id = "openai"
    endpoint = "/v1/responses"

    def __init__(self, client: BatchProviderClient) -> None:
        self.client = client

    def submit_batch(
        self,
        catalog: Any,
        *,
        delivery_job_id: str,
        physical_attempt_id: str | None = None,
        request_items: Sequence[dict[str, Any]],
        jsonl: bytes,
        authorization: BatchAuthorization,
        now: Any,
    ) -> dict[str, Any]:
        job = catalog.get_delivery_job(delivery_job_id)
        if job is None:
            raise BatchTransportError("unknown delivery job")
        if job["status"] != "prepared" or job.get("provider_batch_id") or job.get("provider_input_file_id"):
            raise BatchSubmissionAmbiguous("delivery job already has a send identity; reconcile instead of resubmitting")
        if not request_items:
            raise BatchTransportError("Batch submission requires at least one request item")
        if any(item.get("status") != "prepared" for item in request_items):
            raise BatchTransportError("all request items must be prepared before Batch submission")
        models = {str(item.get("model")) for item in request_items}
        if len(models) != 1:
            raise BatchTransportError("a Batch job must have one model route")
        authorization.assert_allowed(run_id=str(job["run_id"]), model=next(iter(models)))
        item_ids = tuple(str(item["provider_request_item_id"]) for item in request_items)
        authorization.assert_payload(jsonl, custom_ids=item_ids)
        if authorization.payload_sha256 is not None and hasattr(catalog, "persist_delivery_payload_identity"):
            catalog.persist_delivery_payload_identity(
                delivery_job_id,
                payload_sha256=authorization.payload_sha256,
                payload_bytes=len(jsonl),
                payload_local_ref=authorization.payload_local_ref or "authorized:in-memory-payload",
                now=now,
            )
        if any(item.get("delivery_job_id") != delivery_job_id or not item.get("physical_attempt_id") for item in request_items):
            raise BatchTransportError("every Batch request item must carry its delivery job and physical attempt")
        attempt_mode = any(item.get("delivery_attempt_id") for item in request_items)
        if attempt_mode and not all(item.get("delivery_attempt_id") for item in request_items):
            raise BatchTransportError("Batch request items cannot mix stable-only and delivery-attempt records")
        if attempt_mode:
            attempt_ids = tuple(str(item["delivery_attempt_id"]) for item in request_items)
            durable_attempts = {item["delivery_attempt_id"]: item for item in catalog.list_provider_request_attempts(delivery_job_id=delivery_job_id)}
            if any(attempt_ids[index] not in durable_attempts or durable_attempts[attempt_ids[index]]["provider_request_item_id"] != item_ids[index] or durable_attempts[attempt_ids[index]]["physical_attempt_id"] != request_items[index]["physical_attempt_id"] for index in range(len(request_items))):
                raise BatchTransportError("Batch delivery-attempt mapping conflicts with durable state")
        else:
            durable_items = {item["provider_request_item_id"]: item for item in catalog.list_provider_request_items(str(job["run_id"])) if item.get("delivery_job_id") == delivery_job_id}
            if any(item_ids[index] not in durable_items or durable_items[item_ids[index]].get("physical_attempt_id") != request_items[index].get("physical_attempt_id") for index in range(len(request_items))):
                raise BatchTransportError("Batch request item physical-attempt mapping conflicts with durable state")
        if physical_attempt_id is not None and len(request_items) == 1 and physical_attempt_id != request_items[0]["physical_attempt_id"]:
            raise BatchTransportError("explicit physical attempt does not match the request item")
        try:
            if attempt_mode:
                catalog.mark_provider_delivery_attempts_send_started(delivery_job_id, attempt_ids, now=now)
            else:
                catalog.mark_delivery_physical_attempts_send_started(delivery_job_id, item_ids, now=now)
        except Exception as exc:
            raise BatchTransportError("Batch physical-attempt cohort is not ready for send") from exc
        try:
            input_file_id = self.client.upload_batch_file(jsonl, purpose="batch")
        except Exception as exc:
            raise BatchSubmissionAmbiguous("Batch input upload outcome is unknown; reconcile before any resend") from exc
        if not input_file_id:
            raise BatchSubmissionAmbiguous("Batch input upload returned no provider file ID")
        catalog.persist_delivery_file_id(delivery_job_id, "input", input_file_id, now=now)
        try:
            batch_id = self.client.create_batch(input_file_id=input_file_id, endpoint=self.endpoint, completion_window="24h", metadata={"delivery_job_id": delivery_job_id, "packet_hash": authorization.packet_hash})
        except Exception as exc:
            raise BatchSubmissionAmbiguous("Batch creation outcome is unknown; reconcile the durable input file before any resend") from exc
        if not batch_id:
            raise BatchSubmissionAmbiguous("Batch creation returned no provider Batch ID")
        catalog.transition_delivery_job(delivery_job_id, "submitted", now=now, provider_batch_id=batch_id)
        if attempt_mode:
            catalog.bind_provider_delivery_attempts_batch(delivery_job_id, batch_id, now=now)
        else:
            catalog.bind_delivery_physical_attempts_batch(delivery_job_id, batch_id, now=now)
        for item in request_items:
            if attempt_mode:
                catalog.transition_provider_request_attempt(item["delivery_attempt_id"], "submitted", now=now)
            else:
                catalog.transition_provider_request_item(item["provider_request_item_id"], "submitted", now=now, provider_request_id=item["provider_request_item_id"])
        return {"delivery_job_id": delivery_job_id, "provider_input_file_id": input_file_id, "provider_batch_id": batch_id, "submitted_items": len(request_items)}

    def reconcile_batch(self, catalog: Any, *, delivery_job_id: str, now: Any) -> BatchReconciliation:
        job = catalog.get_delivery_job(delivery_job_id)
        if job is None or not job.get("provider_batch_id"):
            raise BatchTransportError("known provider Batch identity is required for reconciliation")
        attempt_rows = catalog.list_provider_request_attempts(delivery_job_id=delivery_job_id) if hasattr(catalog, "list_provider_request_attempts") else []
        attempt_mode = bool(attempt_rows)
        if attempt_mode:
            items = []
            for attempt in attempt_rows:
                stable = catalog.get_provider_request_item(attempt["provider_request_item_id"])
                item = dict(stable or {})
                item.update({"provider_request_item_id": attempt["provider_request_item_id"], "physical_attempt_id": attempt["physical_attempt_id"], "delivery_attempt_id": attempt["delivery_attempt_id"], "delivery_job_id": delivery_job_id, "status": attempt["status"], "provider_request_id": attempt.get("provider_request_id"), "provider_receipt_id": attempt.get("provider_receipt_id"), "result_ref": attempt.get("result_ref"), "usage_json": attempt.get("usage_json")})
                items.append(item)
        else:
            items = catalog.list_provider_request_items(job["run_id"])
            items = [item for item in items if item.get("delivery_job_id") == delivery_job_id]
        terminal_items = {"completed", "failed", "expired", "cancelled", "held"}
        if items and all(item["status"] in terminal_items for item in items) and job["status"] in {"completed", "failed", "expired", "cancelled", "held"}:
            return BatchReconciliation(delivery_job_id, job["provider_batch_id"], job["status"], tuple(items), False, False)
        try:
            remote = self.client.retrieve_batch(job["provider_batch_id"])
        except Exception as exc:
            raise BatchTransportError("Batch status retrieval failed") from exc
        remote_status = str(remote.get("status") or "unknown")
        if remote.get("output_file_id") and not job.get("provider_output_file_id"):
            catalog.persist_delivery_file_id(delivery_job_id, "output", str(remote["output_file_id"]), now=now)
            job = catalog.get_delivery_job(delivery_job_id) or job
        if remote.get("error_file_id") and not job.get("provider_error_file_id"):
            catalog.persist_delivery_file_id(delivery_job_id, "error", str(remote["error_file_id"]), now=now)
            job = catalog.get_delivery_job(delivery_job_id) or job
        if job["status"] == "submitted" and remote_status not in {"queued", "validating", "in_progress", "finalizing"}:
            catalog.transition_delivery_job(delivery_job_id, "in_progress", now=now)
        output_retrieved = False
        error_retrieved = False
        if job.get("provider_output_file_id"):
            try:
                output_rows = _jsonl(self.client.retrieve_file_content(job["provider_output_file_id"]))
            except Exception as exc:
                raise BatchTransportError("Batch output-file retrieval failed") from exc
            output_retrieved = True
            known = {item["provider_request_item_id"] for item in items}
            for row in output_rows:
                parsed = parse_provider_result(row, known)
                item_id = parsed["provider_request_item_id"]
                current = next(item for item in items if item["provider_request_item_id"] == item_id)
                if current["status"] in terminal_items:
                    continue
                if current["status"] == "submitted":
                    if attempt_mode:
                        catalog.transition_provider_request_attempt(current["delivery_attempt_id"], "in_progress", now=now)
                    else:
                        catalog.transition_provider_request_item(item_id, "in_progress", now=now)
                if parsed["status"] == "completed":
                    receipt = f"batchreceipt:{job['provider_batch_id']}:{item_id.split(':', 1)[-1]}"
                    ref = "batch-result:" + hashlib.sha256(json.dumps(row, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                    physical_id = current.get("physical_attempt_id")
                    if physical_id:
                        catalog.persist_provider_receipt(physical_attempt_id=physical_id, provider_receipt_id=receipt, raw_result_ref=ref, usage=parsed.get("usage") or {}, now=now)
                    if attempt_mode:
                        catalog.transition_provider_request_attempt(current["delivery_attempt_id"], "completed", now=now, provider_request_id=parsed.get("provider_request_id"), provider_receipt_id=receipt, result_ref=ref, usage=parsed.get("usage"))
                    else:
                        catalog.transition_provider_request_item(item_id, "completed", now=now, provider_request_id=parsed.get("provider_request_id"), provider_receipt_id=receipt, result_ref=ref, usage=parsed.get("usage"))
                else:
                    physical_id = current.get("physical_attempt_id")
                    if physical_id:
                        catalog.mark_physical_failed(physical_id, now=now)
                    if attempt_mode:
                        catalog.transition_provider_request_attempt(current["delivery_attempt_id"], "failed", now=now, provider_request_id=parsed.get("provider_request_id"), result_ref="batch-error:" + item_id)
                    else:
                        catalog.transition_provider_request_item(item_id, "failed", now=now, provider_request_id=parsed.get("provider_request_id"), result_ref="batch-error:" + item_id)
        if job.get("provider_error_file_id"):
            try:
                error_rows = _jsonl(self.client.retrieve_file_content(job["provider_error_file_id"]))
            except Exception as exc:
                raise BatchTransportError("Batch error-file retrieval failed") from exc
            error_retrieved = True
            known = {item["provider_request_item_id"] for item in items}
            for row in error_rows:
                parsed = parse_provider_result(row, known)
                item_id = parsed["provider_request_item_id"]
                current = next(item for item in items if item["provider_request_item_id"] == item_id)
                if current["status"] not in terminal_items:
                    if current["status"] == "submitted":
                        if attempt_mode:
                            catalog.transition_provider_request_attempt(current["delivery_attempt_id"], "in_progress", now=now)
                        else:
                            catalog.transition_provider_request_item(item_id, "in_progress", now=now)
                    physical_id = current.get("physical_attempt_id")
                    if physical_id:
                        catalog.mark_physical_failed(physical_id, now=now)
                    if attempt_mode:
                        catalog.transition_provider_request_attempt(current["delivery_attempt_id"], "failed", now=now, provider_request_id=parsed.get("provider_request_id"), result_ref="batch-error:" + item_id)
                    else:
                        catalog.transition_provider_request_item(item_id, "failed", now=now, provider_request_id=parsed.get("provider_request_id"), result_ref="batch-error:" + item_id)
        if remote_status in {"failed", "expired", "cancelled"} and not job.get("provider_output_file_id") and not job.get("provider_error_file_id"):
            # A Batch can fail before producing per-item files. Close each
            # submitted item locally while preserving the Batch-level reason.
            for current in items:
                if current["status"] in terminal_items:
                    continue
                item_id = current["provider_request_item_id"]
                physical_id = current.get("physical_attempt_id")
                if physical_id:
                    catalog.mark_physical_failed(physical_id, now=now)
                target = "failed" if remote_status == "failed" else remote_status
                if attempt_mode:
                    catalog.transition_provider_request_attempt(current["delivery_attempt_id"], target, now=now, result_ref="batch-terminal:" + job["provider_batch_id"], failure_class="batch_terminal")
                else:
                    catalog.transition_provider_request_item(item_id, target, now=now, result_ref="batch-terminal:" + job["provider_batch_id"])
        if attempt_mode:
            refreshed = []
            for attempt in catalog.list_provider_request_attempts(delivery_job_id=delivery_job_id):
                stable = catalog.get_provider_request_item(attempt["provider_request_item_id"])
                item = dict(stable or {})
                item.update({"provider_request_item_id": attempt["provider_request_item_id"], "physical_attempt_id": attempt["physical_attempt_id"], "delivery_attempt_id": attempt["delivery_attempt_id"], "delivery_job_id": delivery_job_id, "status": attempt["status"], "provider_request_id": attempt.get("provider_request_id"), "provider_receipt_id": attempt.get("provider_receipt_id"), "result_ref": attempt.get("result_ref"), "usage_json": attempt.get("usage_json")})
                refreshed.append(item)
        else:
            refreshed = [item for item in catalog.list_provider_request_items(job["run_id"]) if item.get("delivery_job_id") == delivery_job_id]
        statuses = {item["status"] for item in refreshed}
        target = None
        if remote_status in {"expired", "cancelled", "failed"}:
            target = remote_status
        elif remote_status == "completed" and statuses and statuses.issubset({"completed", "failed", "expired", "cancelled", "held"}):
            target = "completed" if statuses == {"completed"} else "failed"
        if target and job["status"] not in {"completed", "failed", "expired", "cancelled", "held"}:
            catalog.transition_delivery_job(delivery_job_id, target, now=now)
        final_job = catalog.get_delivery_job(delivery_job_id) or job
        return BatchReconciliation(delivery_job_id, final_job["provider_batch_id"], final_job["status"], tuple(refreshed), output_retrieved, error_retrieved)


__all__ = ["BatchAuthorization", "BatchProviderClient", "BatchReconciliation", "BatchSubmissionAmbiguous", "BatchTransportError", "OpenAIHTTPBatchClient", "OpenAIBatchTransport"]
