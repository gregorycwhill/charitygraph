import importlib.util
import json
from pathlib import Path

import pytest

from charitygraph.questionnaire_x1 import Questionnaire, SourcePack, prepare


def load_script():
    path = Path(__file__).resolve().parents[1] / "examples/questionnaire_x1/x2_plan.py"
    spec = importlib.util.spec_from_file_location("x2_plan", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_real_preparation_and_single_attempt_guard(tmp_path, monkeypatch):
    module = load_script()
    if not (module.ROOT / "execution/49004875807-B-request.json").exists():
        pytest.skip("private E5A source unavailable")
    monkeypatch.setattr(module, "OUT", tmp_path)
    module.offline()
    pack = SourcePack.model_validate(module.read(tmp_path / "source-pack.json"))
    q = Questionnaire.model_validate(module.read(tmp_path / "questionnaire.json"))
    payload = module.read(tmp_path / "provider-request.json")
    manifest = module.read(tmp_path / "manifest.json")
    assert len(pack.programs) == 2 and len(prepare(pack, q)) == 6 and len(payload["questions"]) == 6
    assert len({x["name"] for x in payload["questions"]}) == 6
    assert all(x["scope"] == "program" for x in q.model_dump()["questions"])
    assert manifest["payload_sha256"] == module.digest(module.compact(payload))
    assert float(manifest["reservation_aud"]) <= 0.5
    (tmp_path / "ledger.json").write_text(json.dumps({"status": "reserved"}), encoding="utf8")
    with pytest.raises(RuntimeError): module.offline()
    with pytest.raises(RuntimeError): module.live()
