import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from charitygraph.questionnaire_x1 import Questionnaire, SourcePack, adapt_decisions_choice, answer, batch_choices, prepare

HERE = Path(__file__).resolve().parents[1] / "examples" / "questionnaire_x1"


@pytest.fixture
def inputs():
    pack = SourcePack.model_validate_json((HERE / "source-pack-fixture.json").read_text(encoding="utf8"))
    questionnaire = Questionnaire.model_validate_json((HERE / "questionnaire-v0.1.json").read_text(encoding="utf8"))
    return pack, questionnaire


def records(requests):
    return [{"question_id": r["question"]["question_id"], "subject_id": r["subject_id"],
             "questionnaire_id": r["questionnaire_id"], "questionnaire_version": r["questionnaire_version"],
             "source_snapshot_id": r["snapshot_id"],
             "status": "unknown", "method": "fixture", "value": None} for r in requests]


def test_scope_expansion_and_independent_requests(inputs):
    pack, q = inputs
    requests = prepare(pack, q)
    assert len(requests) == 7
    assert [r["subject_id"] for r in requests if r["question"]["scope"] == "charity"] == [pack.charitygraph_id]
    assert {r["subject_id"] for r in requests if r["question"]["scope"] == "program"} == {p.program_id for p in pack.programs}
    assert all(r["question"]["depends_on"] == [] for r in requests)
    for r in requests:
        assert len({s["representation_id"] for s in r["source_representations"]}) == len(r["source_representations"])
    assert not any(s["representation_id"] == "program-source" for r in requests if r["subject_id"] == "fixture-program-02" for s in r["source_representations"])
    batches = batch_choices(requests, 2)
    assert sum(map(len, batches)) == 6 and all(len(b) <= 2 for b in batches)
    assert all(len({r["subject_id"] for r in b}) == 1 for b in batches)
    assert all(r["question"]["answer_type"] != "numeric" for b in batches for r in b)


def test_validation_rejects_duplicated_or_dependent_contracts(inputs):
    pack, q = inputs
    raw = pack.model_dump(); raw["programs"].append(copy.deepcopy(raw["programs"][0]))
    with pytest.raises(ValidationError): SourcePack.model_validate(raw)
    raw = q.model_dump(); raw["questions"][0]["depends_on"] = ["X1-P06-01"]
    with pytest.raises(ValidationError): Questionnaire.model_validate(raw)
    raw = q.model_dump(); raw["questions"][0]["choices"].append(raw["questions"][0]["choices"][0])
    with pytest.raises(ValidationError): Questionnaire.model_validate(raw)


def test_valid_choices_probabilities_and_unknown_are_preserved(inputs):
    pack, q = inputs; rs = records(prepare(pack, q))
    rs[0].update(status="answered", value="planned", probabilities={"planned": 0.75, "unknown": 0.25})
    rs[4].update(status="answered", value="F")
    out = answer(pack, q, rs)["answers"]
    assert out[0]["value"] == "planned" and out[0]["probabilities"] == {"planned": 0.75, "unknown": 0.25}
    assert out[1]["status"] == "unknown" and out[1]["value"] is None
    assert out[4]["value"] == "F" and isinstance(out[4]["value"], str)
    rs[4]["value"] = "E"
    with pytest.raises(ValueError): answer(pack, q, rs)


def test_numeric_zero_is_reported_not_missing(inputs):
    pack, q = inputs; rs = records(prepare(pack, q))
    rs[-1].update(status="answered", value={"amount": 0, "currency": "AUD", "reporting_period": "2025",
        "source_reference": "fixture://charity-source", "basis": "reported"}, source_references=["fixture://charity-source"])
    assert answer(pack, q, rs)["answers"][-1]["value"]["amount"] == 0
    rs[-1]["source_references"] = []
    with pytest.raises(ValueError): answer(pack, q, rs)


def test_failures_not_applicable_and_scope_validation(inputs):
    pack, q = inputs; rs = records(prepare(pack, q))
    rs[0].update(status="processing_failure"); rs[1].update(status="not_applicable")
    out = answer(pack, q, rs)["answers"]
    assert [out[0]["status"], out[1]["status"]] == ["processing_failure", "not_applicable"]
    rs[1]["value"] = False
    with pytest.raises(ValueError): answer(pack, q, rs)
    rs[1]["value"] = None; rs[1]["source_references"] = ["fixture://program-source"]
    with pytest.raises(ValueError): answer(pack, q, rs)


def test_versions_reuse_pack_without_acquisition(inputs, monkeypatch):
    import charitygraph.document_representation as document
    import charitygraph.sources.acnc as acnc
    def forbidden(*args, **kwargs): raise AssertionError("acquisition or parsing called")
    monkeypatch.setattr(document, "represent_document", forbidden)
    monkeypatch.setattr(acnc, "parse_acnc_register_csv", forbidden)
    pack, q1 = inputs
    q2 = Questionnaire.model_validate_json((HERE / "questionnaire-v0.2.json").read_text(encoding="utf8"))
    a1 = answer(pack, q1, records(prepare(pack, q1)))
    a2 = answer(pack, q2, records(prepare(pack, q2)))
    assert a1["source_pack_id"] == a2["source_pack_id"]
    assert a1["questionnaire_version"] != a2["questionnaire_version"]
    assert all(x["questionnaire_version"] == a2["questionnaire_version"] for x in a2["answers"])


def test_no_raw_representation_text_in_requests_or_answers(inputs):
    pack, q = inputs
    raw = pack.model_dump(); raw["source_representations"][0]["text"] = "PRIVATE SENTINEL"
    with pytest.raises(ValidationError): SourcePack.model_validate(raw)
    req = prepare(pack, q); out = answer(pack, q, records(req))
    assert "PRIVATE SENTINEL" not in json.dumps(req) + json.dumps(out)


def test_captured_native_choice_and_version_binding(inputs):
    pack, q = inputs; rs = records(prepare(pack, q)); qid = rs[0]["question_id"]
    native = {"type": "choice", "name": qid, "choice": "planned", "confidence": 0.8,
              "probabilities": [{"value": "planned", "probability": 0.8}, {"value": "unknown", "probability": 0.2}]}
    rs[0] = adapt_decisions_choice(native, question_id=qid, subject_id=rs[0]["subject_id"],
        questionnaire_id=q.questionnaire_id, questionnaire_version=q.version, source_snapshot_id=pack.snapshot_id,
        source_references=["fixture://program-source"])
    out = answer(pack, q, rs)["answers"][0]
    assert out["confidence"] == 0.8 and out["probabilities"] == {"planned": 0.8, "unknown": 0.2}
    rs[0]["questionnaire_version"] = "0.2.0"
    with pytest.raises(ValueError): answer(pack, q, rs)


def test_boolean_choices_preserve_false_and_unknown(inputs):
    pack, questionnaire = inputs; data = questionnaire.model_dump(); q = data["questions"][0]
    q.update(question_id="fixture-boolean", answer_type="boolean", choices=[{"value": x, "description": x} for x in ("true", "false", "unknown")])
    data["questions"] = [q]; questionnaire = Questionnaire.model_validate(data)
    rs = records(prepare(pack, questionnaire)); rs[0].update(status="answered", value="false")
    out = answer(pack, questionnaire, rs)["answers"]
    assert out[0]["value"] == "false" and out[1]["status"] == "unknown"


def test_missing_inventory_and_missing_representation_are_explicit(inputs):
    pack, q = inputs; data = pack.model_dump()
    data["programs"] = []; data["program_inventory_state"] = "unavailable"
    data["source_representations"][0].update(state="missing", reference=None, representation_sha256=None)
    pack = SourcePack.model_validate(data); requests = prepare(pack, q)
    out = answer(pack, q, records(requests))
    assert out["program_inventory_state"] == "unavailable"
    assert len(out["program_questions_without_subjects"]) == 3
    assert len(out["answers"]) == 1 and out["answers"][0]["status"] == "unknown"
