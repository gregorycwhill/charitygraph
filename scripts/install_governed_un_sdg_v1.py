"""Install the private governed UN SDG goal reference into the stable catalogue."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from charitygraph.governed_un_sdg import (  # noqa: E402
    SOURCE_URL,
    build_definition_packet,
    packet_bytes,
    registry_models,
)
from charitygraph.runtime.catalog import SQLiteCatalog, _canonical_hash  # noqa: E402


SOURCE_HTML = Path(r"C:\CharityGraph-runtime\governed-un-sdg-v1-20260830T\2030agenda.html")
HEADERS = Path(r"C:\CharityGraph-runtime\governed-un-sdg-v1-20260830T\http-headers.txt")
CATALOG = Path(r"C:\CharityGraph-runtime\state\charitygraph.sqlite3")
OUTPUT = SOURCE_HTML.parent


def _headers() -> dict[str, str]:
    values: dict[str, str] = {}
    if HEADERS.is_file():
        for line in HEADERS.read_text(encoding="utf-8").splitlines():
            if ":" in line:
                key, value = line.split(":", 1); values[key.strip()] = value.strip()
    return values


def _register(catalog_path: Path, packet: dict[str, Any]) -> dict[str, Any]:
    scheme, version, concepts = registry_models(packet)
    catalog = SQLiteCatalog(catalog_path).open(initialize=not catalog_path.exists())
    # The taxonomy scheme registry's legacy idempotency key is its record id,
    # while the table's canonical key is scheme_id. Reconcile by the table's
    # actual keys before invoking the supported registration methods so a
    # second installation reuses identical material rather than colliding on
    # the unique scheme key.
    def existing_hash(table: str, key_column: str, key: str) -> str | None:
        with sqlite3.connect(catalog_path) as db:
            row = db.execute(f"select material_hash from {table} where {key_column}=?", (key,)).fetchone()
            return row[0] if row else None

    if existing_hash("taxonomy_schemes", "scheme_id", scheme.scheme_id) is None:
        catalog.register_taxonomy_scheme(scheme)
    elif existing_hash("taxonomy_schemes", "scheme_id", scheme.scheme_id) != _canonical_hash(scheme):
        raise RuntimeError("existing UN SDG scheme has different material")
    if existing_hash("taxonomy_versions", "scheme_version_id", version.record_id) is None:
        catalog.register_taxonomy_version(version)
    elif existing_hash("taxonomy_versions", "scheme_version_id", version.record_id) != _canonical_hash(version):
        raise RuntimeError("existing UN SDG version has different material")
    for concept in concepts:
        current_hash = existing_hash("taxonomy_concepts", "concept_id", concept.record_id)
        if current_hash is None:
            catalog.register_taxonomy_concept(concept)
        elif current_hash != _canonical_hash(concept):
            raise RuntimeError(f"existing UN SDG concept {concept.record_id} has different material")
    catalog.close()
    db = sqlite3.connect(catalog_path)
    counts = {
        "schemes": db.execute("select count(*) from taxonomy_schemes where scheme_id=?", (packet["scheme_id"],)).fetchone()[0],
        "versions": db.execute("select count(*) from taxonomy_versions where scheme_id=?", (packet["scheme_id"],)).fetchone()[0],
        "concepts": db.execute("select count(*) from taxonomy_concepts where scheme_version_id=?", (version.record_id,)).fetchone()[0],
    }
    db.close()
    return {"scheme_id": scheme.record_id, "scheme_version_id": version.record_id, **counts}


def install(*, source_html: Path = SOURCE_HTML, catalog_path: Path = CATALOG, output: Path = OUTPUT) -> dict[str, Any]:
    raw = source_html.read_bytes()
    artifact_sha = hashlib.sha256(raw).hexdigest()
    headers = _headers()
    retrieved_at = headers.get("Date") or datetime.now(timezone.utc).isoformat()
    packet = build_definition_packet(source_html=raw.decode("utf-8"), artifact_sha256=artifact_sha, retrieved_at=retrieved_at, revision_identity={"etag": headers.get("ETag"), "last_modified": headers.get("Last-Modified"), "http_date": headers.get("Date")})
    encoded = packet_bytes(packet)
    inference_sha = hashlib.sha256(encoded).hexdigest()
    output.mkdir(parents=True, exist_ok=True)
    (output / "un-sdg-definition-packet.json").write_bytes(encoded)
    (output / "un-sdg-definition-packet.sha256").write_text(inference_sha + "\n", encoding="ascii")
    report = {"authority": packet["authority"], "scheme_id": packet["scheme_id"], "authority_version": packet["authority_version"], "charitygraph_registry_version": packet["charitygraph_registry_version"], "assignable_concept_count": packet["assignable_concept_count"], "definition_context_target_count": packet["definition_context_target_count"], "inference_packet_sha256": inference_sha, "indicators_ingested": packet["indicators_ingested"], "rights_publication": {"status": "private_runtime_inference_only", "licence_note": "UN source terms retained; public publication of definitions remains gated under CharityGraph source governance"}, "stable_catalogue": _register(catalog_path, packet)}
    # Verify an independent fresh catalogue round-trip with the same registry
    # mechanism and deterministic packet bytes.
    fresh = output / "fresh-catalogue.sqlite3"
    if fresh.exists():
        fresh.unlink()
    report["fresh_catalogue"] = _register(fresh, packet)
    report["fresh_catalogue"]["inference_packet_sha256"] = hashlib.sha256(packet_bytes(packet)).hexdigest()
    (output / "un-sdg-install-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(install(), indent=2))
