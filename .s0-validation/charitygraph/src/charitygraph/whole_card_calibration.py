"""Private Whole-Card Semantic Calibration v0.1 experiment harness."""
from __future__ import annotations

import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SectionAssessment(_Strict):
    section_id: int = Field(ge=1, le=20)
    status: Literal["observations_found", "insufficient_evidence", "not_applicable", "deferred"]
    note: str | None = None


class Scope(_Strict):
    kind: Literal["subject", "reporting_group", "named_program_or_service", "other_named_scope", "uncertain"]
    label: str | None = None


class TemporalScope(_Strict):
    kind: Literal["current", "reporting_period", "historical", "undated", "mixed"]
    value: str | None = None


class EvidenceRef(_Strict):
    source_record_id: str
    packet_locator: str
    role: Literal["supporting", "corroborating", "context"]
    excerpt: str | None = Field(default=None, max_length=240)


class ObservationCandidate(_Strict):
    section_id: int = Field(ge=1, le=20)
    scope: Scope
    proposition: str = Field(min_length=1)
    epistemic_status: Literal["supported", "explicit_absence"]
    temporal_scope: TemporalScope
    evidence: tuple[EvidenceRef, ...] = ()
    qualifications: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _evidence_required(self) -> "ObservationCandidate":
        if self.epistemic_status in {"supported", "explicit_absence"} and not any(e.role == "supporting" for e in self.evidence):
            raise ValueError("supported and explicit_absence observations require supporting evidence")
        if len(self.proposition) > 500:
            raise ValueError("proposition is too broad")
        return self


class WholeCardExtractionOutput(_Strict):
    section_assessments: tuple[SectionAssessment, ...]
    observations: tuple[ObservationCandidate, ...] = ()

    @model_validator(mode="after")
    def _sections(self) -> "WholeCardExtractionOutput":
        ids = [item.section_id for item in self.section_assessments]
        if len(ids) != 20 or set(ids) != set(range(1, 21)):
            raise ValueError("exactly one assessment is required for each section 1 through 20")
        return self


STRICT_SCHEMA: dict[str, Any] = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "section_assessments": {"type": "array", "minItems": 20, "maxItems": 20, "items": {
            "type": "object", "additionalProperties": False,
            "properties": {"section_id": {"type": "integer", "minimum": 1, "maximum": 20}, "status": {"type": "string", "enum": ["observations_found", "insufficient_evidence", "not_applicable", "deferred"]}, "note": {"anyOf": [{"type": "string"}, {"type": "null"}]}},
            "required": ["section_id", "status", "note"]}},
        "observations": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "properties": {
                "section_id": {"type": "integer", "minimum": 1, "maximum": 20},
                "scope": {"type": "object", "additionalProperties": False, "properties": {"kind": {"type": "string", "enum": ["subject", "reporting_group", "named_program_or_service", "other_named_scope", "uncertain"]}, "label": {"anyOf": [{"type": "string"}, {"type": "null"}]}}, "required": ["kind", "label"]},
                "proposition": {"type": "string", "minLength": 1, "maxLength": 500},
                "epistemic_status": {"type": "string", "enum": ["supported", "explicit_absence"]},
                "temporal_scope": {"type": "object", "additionalProperties": False, "properties": {"kind": {"type": "string", "enum": ["current", "reporting_period", "historical", "undated", "mixed"]}, "value": {"anyOf": [{"type": "string"}, {"type": "null"}]}}, "required": ["kind", "value"]},
                "evidence": {"type": "array", "items": {"type": "object", "additionalProperties": False, "properties": {"source_record_id": {"type": "string"}, "packet_locator": {"type": "string"}, "role": {"type": "string", "enum": ["supporting", "corroborating", "context"]}, "excerpt": {"anyOf": [{"type": "string", "maxLength": 240}, {"type": "null"}]}}, "required": ["source_record_id", "packet_locator", "role", "excerpt"]}},
                "qualifications": {"type": "array", "items": {"type": "string"}},
            }, "required": ["section_id", "scope", "proposition", "epistemic_status", "temporal_scope", "evidence", "qualifications"]}},
    }, "required": ["section_assessments", "observations"]
}


def validate_output(value: dict[str, Any], packet: dict[str, Any]) -> WholeCardExtractionOutput:
    result = WholeCardExtractionOutput.model_validate(value)
    spaces = {item["source_record_id"]: {loc["locator"] for loc in item["locators"]} for item in packet["sources"]}
    for observation in result.observations:
        for evidence in observation.evidence:
            if evidence.source_record_id not in spaces or not locator_resolves(evidence.packet_locator, spaces[evidence.source_record_id]):
                raise ValueError("evidence locator does not resolve in packet")
    return result


_LOCATOR = re.compile(r"^\[S(?P<source>\d{3}):L(?P<start>\d{4})\](?:-\[S(?P<source_end>\d{3}):L(?P<end>\d{4})\])?$")


def locator_resolves(value: str, valid_locators: set[str]) -> bool:
    """Resolve a packet line or same-source inclusive line range."""
    if value in valid_locators:
        return True
    match = _LOCATOR.fullmatch(value)
    if not match or (match.group("source_end") and match.group("source_end") != match.group("source")):
        return False
    start, end = int(match.group("start")), int(match.group("end") or match.group("start"))
    return start <= end and all(f"[S{match.group('source')}:L{line:04d}]" in valid_locators for line in range(start, end + 1))


class _VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(); self.parts: list[str] = []; self.hidden = 0
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() in {"script", "style", "noscript", "template"}: self.hidden += 1
    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"script", "style", "noscript", "template"} and self.hidden: self.hidden -= 1
    def handle_data(self, data: str) -> None:
        if not self.hidden and data.strip(): self.parts.append(" ".join(data.split()))


def visible_html(text: str) -> str:
    parser = _VisibleText(); parser.feed(text); return "\n".join(parser.parts)


def packet_sha(packet: dict[str, Any]) -> str:
    value = {key: item for key, item in packet.items() if key != "packet_sha256"}
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
