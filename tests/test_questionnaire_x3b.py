import importlib.util
import json
from pathlib import Path

import pytest

from charitygraph.questionnaire_x1 import Questionnaire, SourcePack, prepare


def module():
    path = Path(__file__).resolve().parents[1] / "examples/questionnaire_x1/x3b.py"
    spec = importlib.util.spec_from_file_location("x3b", path)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


def test_paired_sources_questions_and_single_attempt_controls(tmp_path, monkeypatch):
    m = module()
    if not (m.SRC / f"{m.ABN}-B-request.json").exists() or not (m.X3 / "ledger.json").exists():
        pytest.skip("private previous experiment data unavailable")
    monkeypatch.setattr(m, "OUT", tmp_path); m.offline()
    a = m.read(tmp_path / "provider-request-A.json"); b = m.read(tmp_path / "provider-request-B.json")
    assert a["questions"] == b["questions"] and b["input"].startswith(a["input"])
    qa = Questionnaire.model_validate(m.read(tmp_path / "questionnaire.json"))
    pa = SourcePack.model_validate(m.read(tmp_path / "pack-A.json")); pb = SourcePack.model_validate(m.read(tmp_path / "pack-B.json"))
    assert len(prepare(pa, qa)) == len(prepare(pb, qa)) == 4
    assert [x.representation_id for x in pa.source_representations] == ["A01"]
    assert [x.representation_id for x in pb.source_representations] == ["A01", "P01"]
    assert pa.programs[0].source_context == pb.programs[0].source_context
    manifest = m.read(tmp_path / "manifest.json")
    assert sum(float(x) for x in manifest["reserves_aud"].values()) <= .25
    (tmp_path / "ledger-A.json").write_text(json.dumps({"status": "reserved"}), encoding="utf8")
    with pytest.raises(RuntimeError): m.offline()
    with pytest.raises(RuntimeError): m.live("A")
    with pytest.raises(RuntimeError): m.live("B")
