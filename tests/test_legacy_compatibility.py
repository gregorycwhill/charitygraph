"""Explicit coverage for the temporary pre-CharityGraph compatibility surface."""

from __future__ import annotations

import importlib
import sys
import tomllib
import warnings
from pathlib import Path


def test_legacy_package_import_warns_and_resolves_canonical_module():
    sys.modules.pop("causebase_builder", None)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        legacy = importlib.import_module("causebase_builder")
    canonical = importlib.import_module("charitygraph")

    assert legacy.__path__ == canonical.__path__
    assert any("deprecated" in str(item.message) for item in caught)


def test_packaging_declares_canonical_and_legacy_console_scripts():
    project = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = project["project"]["scripts"]
    assert scripts["charitygraph"] == "charitygraph.cli:main"
    assert scripts["causebase"] == "charitygraph.cli:legacy_main"


def test_legacy_cli_alias_warns_and_delegates_directly(monkeypatch):
    cli = importlib.import_module("charitygraph.cli")
    called = []
    monkeypatch.setattr(cli, "main", lambda: called.append(True) or 17)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = cli.legacy_main()
    assert result == 17
    assert called == [True]
    assert any("deprecated" in str(item.message).lower() for item in caught)
