import importlib.util
import json
from pathlib import Path

import pytest

from charitygraph.questionnaire_x1 import Questionnaire, SourcePack, prepare


def module(name):
    path = Path(__file__).resolve().parents[1] / f"examples/questionnaire_x1/{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


def test_real_pack_scope_financial_record_and_frozen_questions(tmp_path, monkeypatch):
    prep, run = module("x3_prepare"), module("x3_run")
    if not prep.REPORT.exists() or not run.SOL.exists():
        pytest.skip("private retained source or reviewed questionnaire unavailable")
    monkeypatch.setattr(prep, "OUT", tmp_path); monkeypatch.setattr(run, "OUT", tmp_path)
    ref = str(prep.REPORT) + "#/pages/16"
    fixture = {"value": {"amount": 1234000, "currency": "AUD", "reporting_period": "2023-07-01/2024-06-30", "source_reference": ref, "basis": "reported"},
        **{key: "synthetic test value" for key in ("source_label", "accounting_scope", "source_statement", "source_locator", "source_unit", "validation", "nscoa")}}
    (tmp_path / "finance-transcription.json").write_text(json.dumps(fixture), encoding="utf8")
    prep.build(); run.offline()
    pack = SourcePack.model_validate(prep.load(tmp_path / "source-pack.json"))
    q = Questionnaire.model_validate(prep.load(tmp_path / "questionnaire.json"))
    requests = prepare(pack, q)
    assert len(requests) == 4
    assert all(r["program_source_context"][0]["representation_id"] == "A01" for r in requests)
    assert len({p.source_context[0].locator for p in pack.programs}) == 2
    financial = prep.load(tmp_path / "finance-answer.json")["answers"][0]
    assert financial["value"]["amount"] == 1234000 and financial["value"]["basis"] == "reported"
    assert financial["value"]["currency"] == "AUD" and financial["answering_method"] == "source_native"
    payload = prep.load(tmp_path / "provider-request.json"); manifest = prep.load(tmp_path / "manifest.json")
    assert len(payload["questions"]) == 4 and run.sha(run.canonical(payload)) == manifest["payload_sha256"]
    assert float(manifest["reservation_aud"]) <= .25
    (tmp_path / "ledger.json").write_text('{}', encoding="utf8")
    with pytest.raises(RuntimeError): prep.build()
    with pytest.raises(RuntimeError): run.offline()
    with pytest.raises(RuntimeError): run.live()
