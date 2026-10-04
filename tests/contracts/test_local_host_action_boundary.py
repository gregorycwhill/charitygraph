"""Keep local engineering separate from remote-host authentication/mutation."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

# These are execution primitives, not prose.  Documentation can describe the
# guarded boundary; production Python must not route through it.
FORBIDDEN_HOST_ACTIONS = (
    "git push",
    "git credential",
    "gh auth",
    "gh pr create",
    "gh pr merge",
    "GITHUB_TOKEN",
    "GH_TOKEN",
)


def test_tracked_production_python_has_no_remote_host_mutation_or_auth_routing():
    targets = sorted((ROOT / "src").rglob("*.py")) + sorted((ROOT / "scripts").glob("*.py"))
    violations: list[str] = []
    for path in targets:
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        for primitive in FORBIDDEN_HOST_ACTIONS:
            if primitive.lower() in lowered:
                violations.append(f"{path.relative_to(ROOT)}: {primitive}")
    assert not violations, "remote host action/auth routing is forbidden:\n" + "\n".join(violations)
