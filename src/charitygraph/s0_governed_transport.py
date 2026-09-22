"""Fail-closed network boundary for mandate-bound S0 source plans.

This layer performs all authority checks before opening a socket. It returns
transport bytes and metadata; governed acquisition remains responsible for
content-addressed persistence and source lineage.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import Message
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from collections.abc import Mapping

from charitygraph.scale_s0 import HaltController, ScaleMandate, ScalePreflightError, SourceAuthorisation
from charitygraph.s0_acquisition_bridge import SourcePlan, _durable_live_authority
from charitygraph.s0_product_owner_policy import MAX_LOCATOR_PROBES_PER_SUBJECT, alternate_locator_permitted


@dataclass(frozen=True)
class TransportResult:
    requested_locator: str
    final_locator: str
    status: int
    media_type: str
    content: bytes
    retrieved_at: str
    tool_id: str
    tool_version: str
    response_headers: tuple[tuple[str, str], ...]
    outcome: str = "available"


class GovernedTransportError(ScalePreflightError):
    """A governed transport attempt was denied or failed safely."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GovernedSourceTransport:
    def __init__(self, *, timeout_seconds: float = 20.0, max_response_bytes: int = 30_000_000,
                 max_redirects: int = 3, user_agent: str = "CharityGraph-S0/1") -> None:
        if timeout_seconds <= 0 or max_response_bytes <= 0 or max_redirects < 0:
            raise ValueError("transport bounds must be positive")
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.max_redirects = max_redirects
        self.user_agent = user_agent
        self._opener = build_opener(_NoRedirect())

    @staticmethod
    def _allowed_locator(locator: str) -> tuple[str, str]:
        parsed = urlsplit(locator)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise GovernedTransportError("governed web transport requires an HTTP(S) locator")
        return parsed.scheme.lower(), parsed.netloc.lower()

    @staticmethod
    def _same_origin_redirect(original: str, target: str) -> bool:
        old = urlsplit(original); new = urlsplit(target)
        if new.scheme not in {"http", "https"} or not new.netloc:
            return False
        if old.netloc.lower() == new.netloc.lower():
            return old.scheme == new.scheme or (old.scheme == "http" and new.scheme == "https")
        return False

    @staticmethod
    def _authorised_alternate_locators(plan: SourcePlan, authorisation: SourceAuthorisation) -> tuple[str, ...]:
        """Resolve only explicitly evidenced official alternates, bounded to five probes."""
        material = authorisation.authority_material or {}
        raw = material.get("alternate_locators")
        if raw is None and material.get("alternate_locator"):
            raw = ({"locator": material["alternate_locator"], "relationship": material.get("alternate_authoritative_relationship", "")},)
        if raw is None:
            return ()
        if not isinstance(raw, (tuple, list)):
            raise GovernedTransportError("alternate locator evidence is malformed")
        alternates: list[str] = []
        for index, item in enumerate(raw):
            if len(alternates) >= MAX_LOCATOR_PROBES_PER_SUBJECT - 1:
                break
            if not isinstance(item, Mapping):
                raise GovernedTransportError("alternate locator evidence is malformed")
            locator, relationship = item.get("locator", ""), item.get("relationship", "")
            if not alternate_locator_permitted(
                subject_abn=plan.subject_id,
                locator=str(locator),
                authoritative_relationship=str(relationship),
                probes_used=index + 1,
                authentication_bypass=bool(item.get("authentication_bypass", False)),
                paywall_bypass=bool(item.get("paywall_bypass", False)),
                tls_validation_bypass=bool(item.get("tls_validation_bypass", False)),
                anti_bot_circumvention=bool(item.get("anti_bot_circumvention", False)),
            ):
                raise GovernedTransportError("alternate locator lacks authoritative relationship or attempts bypass")
            if str(locator) != plan.locator:
                alternates.append(str(locator))
        return tuple(alternates)

    def _authorise(self, plan: SourcePlan, authorisation: SourceAuthorisation, mandate: ScaleMandate,
                   halts: HaltController | None) -> None:
        if plan.mandate_id != mandate.mandate_id or plan.mandate_hash != mandate.identity_hash or plan.slice_id != mandate.slice_id:
            raise GovernedTransportError("source plan is stale or substituted")
        if plan.subject_id not in mandate.subject_ids or not plan.locator:
            raise GovernedTransportError("source plan is outside the frozen mandate")
        allowed_locators = (plan.locator,) + self._authorised_alternate_locators(plan, authorisation)
        if authorisation.source_family != plan.source_family or authorisation.url_or_identity not in allowed_locators:
            raise GovernedTransportError("source authorisation does not bind the plan locator/family")
        if authorisation.technical_access_state != "accessible":
            raise GovernedTransportError("technical withholding prevents acquisition")
        if authorisation.access_classification == "OPEN_WEB_PUBLIC":
            if authorisation.rights_transmission_status not in {"permitted", "permitted_open_web_policy"}:
                raise GovernedTransportError("open-web source lacks adopted policy authority")
        elif authorisation.access_classification == "SEPARATELY_LICENSED_OR_CONTROLLED":
            if authorisation.rights_transmission_status != "permitted" or not authorisation.specialist_authorisation_id:
                raise GovernedTransportError("controlled source lacks exact authority")
        else:
            raise GovernedTransportError("source access classification is not executable")
        if halts and halts.active(slice_id=plan.slice_id, task_key="source-acquisition", subject_id=plan.subject_id):
            raise GovernedTransportError("hard halt prevents acquisition")
        self._allowed_locator(plan.locator)

    def fetch(self, plan: SourcePlan, authorisation: SourceAuthorisation, mandate: ScaleMandate,
              *, halts: HaltController | None = None, now: datetime | None = None, catalog: object | None = None,
              execution_attempt_id: str | None = None, offline: bool = False) -> TransportResult:
        if catalog is None:
            if not offline:
                raise GovernedTransportError("live governed transport requires durable catalogue authority")
        else:
            if offline:
                raise GovernedTransportError("offline governed transport cannot use a durable live catalogue")
            if not execution_attempt_id:
                raise GovernedTransportError("live governed transport requires an execution-attempt binding")
            attempt = catalog.get_scale_s0_execution_attempt(execution_attempt_id)
            if attempt is None or attempt["mandate_id"] != mandate.mandate_id or attempt["slice_id"] != mandate.slice_id:
                raise GovernedTransportError("transport execution-attempt binding is absent or stale")
            try:
                authorisation = _durable_live_authority(catalog, mandate, plan, authorisation, execution_attempt_id)
            except ScalePreflightError as error:
                raise GovernedTransportError(str(error)) from error
        self._authorise(plan, authorisation, mandate, halts)
        requested = plan.locator
        locators = (requested,) + self._authorised_alternate_locators(plan, authorisation)
        headers = {"User-Agent": self.user_agent, "Accept": "text/html,application/pdf,application/json;q=0.9,*/*;q=0.1"}
        for locator_index, locator in enumerate(locators):
            current = locator
            response = None
            unavailable = False
            for redirect_number in range(self.max_redirects + 1):
                try:
                    response = self._opener.open(Request(current, headers=headers), timeout=self.timeout_seconds)
                except HTTPError as error:
                    if error.code in {301, 302, 303, 307, 308}:
                        target = urljoin(current, error.headers.get("Location", ""))
                        alternate_targets = self._authorised_alternate_locators(plan, authorisation)
                        approved_host = any(urlsplit(target).netloc.lower() == urlsplit(item).netloc.lower() for item in alternate_targets)
                        if not self._same_origin_redirect(current, target) and not approved_host:
                            raise GovernedTransportError("redirect leaves the authorised origin") from error
                        if redirect_number >= self.max_redirects:
                            raise GovernedTransportError("redirect limit exceeded") from error
                        current = target
                        continue
                    if error.code in {401, 403, 407}:
                        raise GovernedTransportError(f"technical access denial HTTP {error.code}") from error
                    if locator_index < len(locators) - 1 and error.code in {404, 410, 500, 502, 503, 504}:
                        unavailable = True
                        break
                    raise GovernedTransportError(f"HTTP acquisition failure {error.code}") from error
                except (TimeoutError, URLError, OSError) as error:
                    if locator_index < len(locators) - 1:
                        unavailable = True
                        break
                    raise GovernedTransportError("network acquisition failed") from error
                else:
                    break
            if unavailable or response is None:
                continue
            status = int(getattr(response, "status", response.getcode()))
            media = response.headers.get_content_type() if hasattr(response.headers, "get_content_type") else response.headers.get("Content-Type", "").split(";", 1)[0]
            declared = response.headers.get("Content-Length")
            try:
                if declared and int(declared) > self.max_response_bytes:
                    raise GovernedTransportError("response exceeds configured byte bound")
            except (TypeError, ValueError) as error:
                raise GovernedTransportError("response Content-Length is malformed") from error
            chunks: list[bytes] = []; size = 0
            try:
                while True:
                    chunk = response.read(min(64 * 1024, self.max_response_bytes - size + 1))
                    if not chunk: break
                    size += len(chunk)
                    if size > self.max_response_bytes:
                        raise GovernedTransportError("response exceeds configured byte bound")
                    chunks.append(chunk)
            finally:
                response.close()
            content = b"".join(chunks)
            retrieved = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
            return TransportResult(requested, current, status, media, content, retrieved, "charitygraph-governed-http", "1", tuple(sorted((str(k), str(v)) for k, v in response.headers.items())))
        raise GovernedTransportError("redirect processing failed")
