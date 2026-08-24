from datetime import datetime, timezone

import pytest

from charitygraph.contracts import (
    AcquisitionReceipt,
    ProducerRef,
    SourceDefinition,
    StructuredFieldLocator,
)
from charitygraph.evidence_store import (
    ArtifactConflictError,
    ArtifactStoreError,
    ContentAddressedArtifactStore,
)
from charitygraph.runtime.catalog import SQLiteCatalog


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
PRODUCER = ProducerRef(kind='code', producer_id='evidence-store-test', version='1')


def source_definition():
    return SourceDefinition(
        record_id='srcdef:store',
        created_at=NOW,
        producer=PRODUCER,
        publisher='Example publisher',
        source_class='directory',
        authority_roles=({'proposition': 'identity', 'role': 'authoritative'},),
        acquisition_locator='https://example.org/source',
        temporal_semantics='retrieval snapshot',
        publication_eligibility='private review only',
        steward='builder',
    )


def test_content_addressed_store_is_deduplicated_and_immutable(tmp_path):
    store = ContentAddressedArtifactStore(tmp_path / 'objects')
    first = store.put_bytes(b'hello')
    second = store.put_bytes(b'hello')
    assert first.artifact_id == second.artifact_id
    assert first.storage_path == second.storage_path
    assert store.read(first) == b'hello'
    assert store.exists(first)
    target = tmp_path / 'objects' / first.storage_path
    target.write_bytes(b'changed')
    with pytest.raises(ArtifactConflictError):
        store.read(first)


def test_store_rejects_unsafe_root_and_invalid_ids(tmp_path):
    allowed = tmp_path / 'allowed'
    with pytest.raises(ArtifactStoreError):
        ContentAddressedArtifactStore(tmp_path / 'outside', allowed_roots=(allowed,))
    store = ContentAddressedArtifactStore(allowed)
    with pytest.raises(ArtifactStoreError):
        store.read('artifact:not-a-hash')


def test_derived_artifact_records_input_lineage_in_catalogue(tmp_path):
    db = SQLiteCatalog(tmp_path / 'state.sqlite3').open(initialize=True)
    store = ContentAddressedArtifactStore(tmp_path / 'objects', catalog=db)
    source = store.put(b'raw source')
    derived = store.put_derived(b'parsed record', input_artifact_ids=(source.artifact_id,))
    assert derived.artifact_kind == 'derived'
    assert db.get_artifact_lineage(derived.artifact_id) == [
        {'artifact_id': derived.artifact_id, 'input_artifact_id': source.artifact_id, 'edge_type': 'derived_from'}
    ]


def test_catalogue_chain_persists_definition_receipt_artifact_and_locator(tmp_path):
    db = SQLiteCatalog(tmp_path / 'state.sqlite3').open(initialize=True)
    definition = source_definition()
    db.register_source_definition(definition)
    store = ContentAddressedArtifactStore(tmp_path / 'objects', catalog=db)
    source = store.put(b'bounded source')
    receipt = AcquisitionReceipt(
        record_id='acq:store',
        created_at=NOW,
        producer=PRODUCER,
        source_definition_id=definition.record_id,
        requested_locator='https://example.org/source',
        resolved_locator='https://example.org/source',
        retrieved_at=NOW,
        outcome='available',
        content_hash=source.content_hash,
        byte_size=source.byte_size,
        artifact_id=source.artifact_id,
        tool_id='test-tool',
        tool_version='1',
    )
    assert db.record_acquisition_receipt(receipt)['artifact_id'] == source.artifact_id
    locator = db.register_evidence_locator(
        StructuredFieldLocator(artifact_id=source.artifact_id, field_path='rows[0].name')
    )
    assert db.get_evidence_locator(locator['evidence_locator_id'])['kind'] == 'structured_field'
    assert db.get_source_definition(definition.record_id)['source_class'] == 'directory'


def test_catalogue_rejects_unknown_lineage_and_idempotent_conflicts(tmp_path):
    db = SQLiteCatalog(tmp_path / 'state.sqlite3').open(initialize=True)
    with pytest.raises(Exception):
        db.record_artifact_lineage('artifact:' + 'a' * 64, ('srcblob:' + 'b' * 64,))
    store = ContentAddressedArtifactStore(tmp_path / 'objects', catalog=db)
    source = store.put(b'one')
    (tmp_path / 'objects' / source.storage_path).write_bytes(b'tampered')
    with pytest.raises(ArtifactConflictError):
        store.put(b'one')
