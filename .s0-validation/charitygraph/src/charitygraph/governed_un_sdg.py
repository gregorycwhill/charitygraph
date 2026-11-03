"""Governed UN Sustainable Development Goals reference ingestion.

The importer is intentionally source-bound: it parses only the already acquired
official 2030 Agenda artefact and registers the 17 goals through the existing
taxonomy registry. Targets are retained as non-assignable definition context.
"""
from __future__ import annotations

import html as html_lib
import json
import re
from datetime import date, datetime, timezone
from typing import Any

from .contracts.ids import deterministic_id
from .contracts.taxonomy import TaxonomyConcept, TaxonomyScheme, TaxonomyVersion


SCHEME_ID = "un-sdg"
SCHEME_NAME = "UN Sustainable Development Goals"
AUTHORITY_VERSION = "2030 Agenda / 2015"
CHARITYGRAPH_REGISTRY_VERSION = "1"
SOURCE_URL = "https://sdgs.un.org/2030agenda"


def _text(value: str) -> str:
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html_lib.unescape(value).replace("\r", "\n")
    return " ".join(value.split())


def parse_goals(source_html: str) -> list[dict[str, Any]]:
    """Extract Goal headings and their target text from the official page."""
    sections = re.findall(
        r"<h3>\s*Goal\s+(\d+)\.\s*(.*?)</h3>(.*?)(?=<h3>\s*Goal\s+\d+\.|</div>)",
        source_html,
        flags=re.I | re.S,
    )
    goals: list[dict[str, Any]] = []
    for number_text, title_html, body_html in sections:
        number = int(number_text)
        title = _text(title_html)
        body = _text(body_html)
        target_pattern = rf"(?<!\d)({number}\.(?:\d{{1,2}}|[a-z]))\s+(.*?)(?=(?:\s+{number}\.(?:\d{{1,2}}|[a-z])\s)|$)"
        targets = [{"target_id": target_id, "text": text.strip(), "assignable": False} for target_id, text in re.findall(target_pattern, body, flags=re.I)]
        goals.append({"goal_number": number, "ordinal": number, "official_goal_text": title, "targets": targets})
    goals.sort(key=lambda item: item["goal_number"])
    if [item["goal_number"] for item in goals] != list(range(1, 18)):
        raise ValueError("official UN artefact did not yield exactly Goals 1 through 17")
    if sum(len(item["targets"]) for item in goals) != 169:
        raise ValueError("official UN artefact did not yield the expected 169 target texts")
    return goals


def build_definition_packet(*, source_html: str, artifact_sha256: str, retrieved_at: str, revision_identity: dict[str, Any] | None = None) -> dict[str, Any]:
    goals = parse_goals(source_html)
    lineage = {"authority": "United Nations", "source_title": "Transforming our world: the 2030 Agenda for Sustainable Development", "source_url": SOURCE_URL, "retrieved_at": retrieved_at, "artifact_sha256": artifact_sha256, "revision_identity": revision_identity or {}}
    concepts = []
    for goal in goals:
        number = goal["goal_number"]
        concepts.append({
            "concept_id": deterministic_id("concept:", {"scheme_id": SCHEME_ID, "authority_goal_number": number}),
            "authority_goal_number": number,
            "ordinal": number,
            "authority_native_id": f"SDG-{number}",
            "official_goal_text": goal["official_goal_text"],
            "assignable": True,
            "definition_context": {"targets": goal["targets"]},
            "source_lineage": lineage,
        })
    return {
        "scheme_id": SCHEME_ID,
        "scheme_name": SCHEME_NAME,
        "authority_version": AUTHORITY_VERSION,
        "charitygraph_registry_version": CHARITYGRAPH_REGISTRY_VERSION,
        "authority": lineage,
        "assignable_concept_count": len(concepts),
        "definition_context_target_count": sum(len(c["definition_context"]["targets"]) for c in concepts),
        "concepts": concepts,
        "indicators_ingested": False,
    }


def packet_bytes(packet: dict[str, Any]) -> bytes:
    return (json.dumps(packet, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def registry_models(packet: dict[str, Any]) -> tuple[TaxonomyScheme, TaxonomyVersion, tuple[TaxonomyConcept, ...]]:
    # Stable registry material is independent of the import execution time;
    # retrieval time remains in the authority lineage packet.
    created = datetime(2015, 9, 25, tzinfo=timezone.utc)
    authority = packet["authority"]
    scheme = TaxonomyScheme(
        record_id=deterministic_id("scheme:", {"scheme_id": packet["scheme_id"]}),
        created_at=created, producer={"kind": "code", "producer_id": "governed-un-sdg-import", "version": packet["charitygraph_registry_version"]},
        scheme_id=packet["scheme_id"], owner="United Nations", purpose="Multi-label alignment reference to the UN Sustainable Development Goals",
        jurisdiction="global", disposition="reference_only", licence="UN source terms", reuse_policy="private inference; public publication gated",
        attribution="United Nations", steward="CharityGraph taxonomy steward", review_status="frozen-governed-reference",
    )
    version = TaxonomyVersion(
        record_id=deterministic_id("schemever:", {"scheme_id": packet["scheme_id"], "authority_version": packet["authority_version"], "registry_version": packet["charitygraph_registry_version"]}),
        created_at=created, producer={"kind": "code", "producer_id": "governed-un-sdg-import", "version": packet["charitygraph_registry_version"]},
        scheme_id=packet["scheme_id"], version=packet["charitygraph_registry_version"], release_date=date(2015, 9, 25), jurisdiction_scope="global",
        source_locator=authority["source_url"], status="frozen", licence="UN source terms", reuse_policy="private inference; public publication gated", attribution="United Nations",
    )
    concepts: list[TaxonomyConcept] = []
    for row in packet["concepts"]:
        definition = json.dumps({"official_goal_text": row["official_goal_text"], "targets": row["definition_context"]["targets"]}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        concepts.append(TaxonomyConcept(
            record_id=row["concept_id"], created_at=created, producer={"kind": "code", "producer_id": "governed-un-sdg-import", "version": packet["charitygraph_registry_version"]},
            scheme_version_id=version.record_id, external_concept_id=row["authority_native_id"], preferred_label=row["official_goal_text"], definition=definition,
            notes=(f"authority_artifact_sha256:{authority['artifact_sha256']}", f"authority_goal_number:{row['authority_goal_number']}", "targets_assignable:false"),
        ))
    return scheme, version, tuple(concepts)
