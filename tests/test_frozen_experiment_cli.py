import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


def _runner_module():
    path = Path(__file__).parents[1] / "scripts" / "run_frozen_experiment.py"
    spec = importlib.util.spec_from_file_location("run_frozen_experiment_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_execute_binds_project_using_standard_client_constructor(monkeypatch, tmp_path):
    runner = _runner_module()
    prepared = tmp_path / "prepared.json"
    prepared.write_text(json.dumps({"rows": [], "mandate_id": "mandate:fixture"}), encoding="utf-8")
    args = SimpleNamespace(
        mode="execute", prepared=prepared, catalog=tmp_path / "catalog.sqlite3",
        authorization_catalog=tmp_path / "authorization.sqlite3", runtime_root=tmp_path / "runtime",
        provider_project="proj_fixture",
    )
    captured = {}

    class Client:
        def __init__(self, *, provider_account_project):
            captured["project"] = provider_account_project

    monkeypatch.setattr(runner, "_args", lambda: args)
    monkeypatch.setattr(runner, "OpenAIHTTPStandardClient", Client)
    monkeypatch.setattr(runner, "execute_prepared_standard", lambda **kwargs: captured.update(kwargs) or {"counts": {}})

    assert runner.main() == 0
    assert captured["project"] == "proj_fixture"
    assert isinstance(captured["provider"], Client)
