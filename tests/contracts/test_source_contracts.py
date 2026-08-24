from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from charitygraph.contracts import (
    AcquisitionReceipt,
    DocumentLocator,
    EvidenceLocator,
    ProducerRef,
    SourceDefinition,
    StructuredFieldLocator,
    TextSpanLocator,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
PRODUCER = ProducerRef(kind='code', producer_id='source-contract-test', version='1')


def make_source(**overrides):
    values = dict(
        record_id='srcdef:test',
        created_at=NOW,
        producer=PRODUCER,
        publisher='Example publisher',
        source_class='directory',
        authority_roles=({'proposition': 'identity', 'role': 'authoritative'},),
        acquisition_locator='https://example.org/directory',
        temporal_semantics='current membership at retrieval',
        publication_eligibility='private review only',
        steward='data-team',
    )
    values.update(overrides)
    return SourceDefinition(**values)


def test_source_definition_has_proposition_authority_and_rejects_subjects():
    assert make_source().authority_roles[0].proposition == 'identity'
    with pytest.raises(ValidationError, match='proposition-specific'):
        SourceDefinition(**{**make_source().model_dump(), 'authority_roles': ()})
    with pytest.raises(ValidationError, match='not a subject'):
        make_source(source_class='subject')


def test_source_and_receipt_reject_secret_material():
    with pytest.raises(ValidationError, match='secret'):
        make_source(acquisition_locator='https://example.org/x?api_key=secret')
    with pytest.raises(ValidationError, match='secrets'):
        AcquisitionReceipt(
            record_id='acq:test',
            created_at=NOW,
            producer=PRODUCER,
            source_definition_id='srcdef:test',
            requested_locator='https://example.org/x',
            outcome='absent',
            material_parameters={'token': 'nope'},
        )


def test_receipt_distinguishes_unavailable_from_content():
    receipt = AcquisitionReceipt(
        record_id='acq:absent',
        created_at=NOW,
        producer=PRODUCER,
        source_definition_id='srcdef:test',
        requested_locator='https://example.org/x',
        outcome='unavailable',
    )
    assert receipt.artifact_id is None
    with pytest.raises(ValidationError, match='require content hash'):
        AcquisitionReceipt(
            record_id='acq:bad',
            created_at=NOW,
            producer=PRODUCER,
            source_definition_id='srcdef:test',
            requested_locator='https://example.org/x',
            outcome='available',
            byte_size=4,
        )


def test_evidence_locators_have_kind_specific_shapes():
    structured = StructuredFieldLocator(artifact_id='srcblob:' + 'a' * 64, field_path='rows[0].name')
    span = TextSpanLocator(source_record_id='srcrec:1', start=2, end=7)
    document = DocumentLocator(artifact_id='srcblob:' + 'a' * 64, page=3, section='financials')
    assert (structured.kind, span.kind, document.kind) == ('structured_field', 'text_span', 'document')
    with pytest.raises(ValidationError):
        EvidenceLocator(kind='text_span', source_record_id='srcrec:1', start=3, end=2)
