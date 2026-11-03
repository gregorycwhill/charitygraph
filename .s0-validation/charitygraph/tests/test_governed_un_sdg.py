import hashlib
import json
import sqlite3
from pathlib import Path

from charitygraph.governed_un_sdg import (
    AUTHORITY_VERSION,
    CHARITYGRAPH_REGISTRY_VERSION,
    SCHEME_ID,
    build_definition_packet,
    packet_bytes,
    registry_models,
)
from charitygraph.runtime.catalog import SQLiteCatalog


def _fixture_html() -> str:
    counts = [7, 8, 13, 10, 9, 8, 5, 12, 8, 10, 10, 11, 5, 10, 12, 12, 19]
    sections = []
    for number, count in enumerate(counts, 1):
        targets = " ".join(
            f"{number}.{index} Official target text."
            for index in range(1, count + 1)
        )
        sections.append(f"<h3>Goal {number}. Goal {number} title</h3><div>{targets}</div>")
    return "".join(sections)


def _packet() -> dict:
    return build_definition_packet(
        source_html=_fixture_html(),
        artifact_sha256="a" * 64,
        retrieved_at="Sun, 30 Aug 2026 11:25:36 GMT",
        revision_identity={"etag": '"test"'},
    )


def test_governed_registry_has_17_assignable_goals_and_169_targets():
    packet = _packet()
    assert packet["scheme_id"] == SCHEME_ID
    assert packet["authority_version"] == AUTHORITY_VERSION
    assert packet["charitygraph_registry_version"] == CHARITYGRAPH_REGISTRY_VERSION
    assert [row["authority_goal_number"] for row in packet["concepts"]] == list(range(1, 18))
    assert [row["ordinal"] for row in packet["concepts"]] == list(range(1, 18))
    assert all(row["assignable"] for row in packet["concepts"])
    assert packet["assignable_concept_count"] == 17
    assert packet["definition_context_target_count"] == 169
    assert all(not target["assignable"] for row in packet["concepts"] for target in row["definition_context"]["targets"])
    assert packet["indicators_ingested"] is False


def test_packet_is_deterministic_and_has_authority_lineage():
    first = _packet()
    second = _packet()
    assert packet_bytes(first) == packet_bytes(second)
    assert hashlib.sha256(packet_bytes(first)).hexdigest() == hashlib.sha256(packet_bytes(second)).hexdigest()
    authority = first["authority"]
    assert authority["authority"] == "United Nations"
    assert authority["source_url"] == "https://sdgs.un.org/2030agenda"
    assert authority["artifact_sha256"] == "a" * 64
    assert authority["revision_identity"] == {"etag": '"test"'}
    assert all(row["source_lineage"] == authority for row in first["concepts"])


def test_registry_persists_to_fresh_catalogue_with_same_packet(tmp_path: Path):
    packet = _packet()
    scheme, version, concepts = registry_models(packet)
    path = tmp_path / "catalogue.sqlite3"
    catalog = SQLiteCatalog(path).open(initialize=True)
    catalog.register_taxonomy_scheme(scheme)
    catalog.register_taxonomy_version(version)
    for concept in concepts:
        catalog.register_taxonomy_concept(concept)
    catalog.close()
    with sqlite3.connect(path) as db:
        assert db.execute("select count(*) from taxonomy_schemes").fetchone()[0] == 1
        assert db.execute("select count(*) from taxonomy_versions").fetchone()[0] == 1
        assert db.execute("select count(*) from taxonomy_concepts").fetchone()[0] == 17
        rows = db.execute("select material_json from taxonomy_concepts order by external_concept_id").fetchall()
    assert all(json.loads(row[0])["external_concept_id"].startswith("SDG-") for row in rows)
    assert hashlib.sha256(packet_bytes(packet)).hexdigest() == hashlib.sha256(packet_bytes(_packet())).hexdigest()
