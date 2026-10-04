from pathlib import Path

import pytest

from charitygraph.config import load_paths


def test_paths_keep_durable_archive_separate_from_mutable_runtime(monkeypatch, tmp_path: Path):
    archive = tmp_path / "archive"
    runtime = tmp_path / "runtime"
    data = tmp_path / "charitygraph-data"
    monkeypatch.setenv("CAUSEBASE_ARCHIVE_ROOT", str(archive))
    monkeypatch.setenv("CAUSEBASE_RUNTIME_ROOT", str(runtime))
    monkeypatch.setenv("CAUSEBASE_DATA_REPOSITORY", str(data))

    paths = load_paths(tmp_path)

    assert paths.source_archive_root == archive / "sources"
    assert paths.processed_archive_root == archive / "processed"
    assert paths.staging_root == runtime / "staging"
    assert paths.data_repository_root == data

    paths.initialise_runtime()
    assert paths.staging_root.is_dir()
    assert not archive.exists()


def test_relative_environment_paths_are_workspace_relative_not_cwd(monkeypatch, tmp_path: Path):
    workspace = tmp_path / "workspace"
    other_directory = tmp_path / "elsewhere"
    workspace.mkdir()
    other_directory.mkdir()
    monkeypatch.setenv("CHARITYGRAPH_ARCHIVE_ROOT", "private/archive")
    monkeypatch.setenv("CHARITYGRAPH_RUNTIME_ROOT", "runtime")
    monkeypatch.setenv("CHARITYGRAPH_DATA_REPOSITORY", "data")
    monkeypatch.chdir(other_directory)

    paths = load_paths(workspace)

    assert paths.archive_root == workspace / "private" / "archive"
    assert paths.runtime_root == workspace / "runtime"
    assert paths.data_repository_root == workspace / "data"


@pytest.mark.parametrize(
    ("variable", "message"),
    [
        ("CHARITYGRAPH_ARCHIVE_ROOT", "CHARITYGRAPH_ARCHIVE_ROOT must not be empty"),
        ("CHARITYGRAPH_RUNTIME_ROOT", "CHARITYGRAPH_RUNTIME_ROOT must not be empty"),
        ("CHARITYGRAPH_DATA_REPOSITORY", "CHARITYGRAPH_DATA_REPOSITORY must not be empty"),
    ],
)
def test_empty_configured_path_is_rejected(monkeypatch, tmp_path: Path, variable: str, message: str):
    monkeypatch.setenv(variable, "   ")

    with pytest.raises(ValueError, match=message):
        load_paths(tmp_path)
