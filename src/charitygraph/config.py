"""Configurable storage boundaries for local CharityGraph production work."""

from __future__ import annotations

import os
import warnings
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CharityGraphPaths:
    """Durable archive, mutable runtime and public-data repository locations."""

    archive_root: Path
    runtime_root: Path
    data_repository_root: Path

    @property
    def source_archive_root(self) -> Path:
        return self.archive_root / "sources"

    @property
    def processed_archive_root(self) -> Path:
        return self.archive_root / "processed"

    @property
    def governed_inputs_root(self) -> Path:
        return self.archive_root / "governed-inputs"

    @property
    def staging_root(self) -> Path:
        return self.runtime_root / "staging"

    def runtime_directories(self) -> tuple[Path, ...]:
        return tuple(self.runtime_root / name for name in ("state", "temp", "cache", "logs", "staging"))

    def initialise_runtime(self) -> None:
        """Create only mutable runtime directories; archive data is created on completed write."""
        for directory in self.runtime_directories():
            directory.mkdir(parents=True, exist_ok=True)


def _env(canonical: str, legacy: str, default: str | Path) -> str | Path:
    if canonical in os.environ:
        return os.environ[canonical]
    if legacy in os.environ:
        warnings.warn(
            f"{legacy} is deprecated; use {canonical}. It will be removed at the next pre-1.0 breaking release.",
            DeprecationWarning,
            stacklevel=2,
        )
        return os.environ[legacy]
    return default


def _path(value: str | Path, *, workspace_root: Path, name: str) -> Path:
    """Return a stable absolute path for a configured storage boundary.

    Environment variables are frequently supplied as relative paths by local
    scripts.  Resolving them from the configured workspace, rather than the
    process's current directory, ensures sibling scripts select the same
    archive and runtime locations.
    """
    if isinstance(value, str) and not value.strip():
        raise ValueError(f"{name} must not be empty")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = workspace_root / path
    return path.resolve()


def load_paths(workspace_root: Path | None = None) -> CharityGraphPaths:
    """Read paths without creating storage or assuming that repositories equal archives."""
    default_workspace = (workspace_root or Path.cwd().resolve().parent).expanduser().resolve()
    return CharityGraphPaths(
        archive_root=_path(
            _env("CHARITYGRAPH_ARCHIVE_ROOT", "CAUSEBASE_ARCHIVE_ROOT", default_workspace / "archive"),
            workspace_root=default_workspace,
            name="CHARITYGRAPH_ARCHIVE_ROOT",
        ),
        runtime_root=_path(
            _env("CHARITYGRAPH_RUNTIME_ROOT", "CAUSEBASE_RUNTIME_ROOT", r"C:\CharityGraph-runtime"),
            workspace_root=default_workspace,
            name="CHARITYGRAPH_RUNTIME_ROOT",
        ),
        data_repository_root=_path(
            _env("CHARITYGRAPH_DATA_REPOSITORY", "CAUSEBASE_DATA_REPOSITORY", default_workspace / "charitygraph-data"),
            workspace_root=default_workspace,
            name="CHARITYGRAPH_DATA_REPOSITORY",
        ),
    )


# Deliberate source-level compatibility alias; new code must import CharityGraphPaths.
CauseBasePaths = CharityGraphPaths
