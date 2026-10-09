"""Regression coverage for the central retained-source successor freezer."""
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[2]
FREEZER = ROOT / "scripts" / "freeze_rich_empirical_corpus_v2.py"


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_successor_freeze_preserves_cohort_and_reports_source_family_coverage(tmp_path):
    cohort = {"cases": [
        {"case_id": "EEN-01", "subject_id": "subject:one", "arm": "challenge"},
        {"case_id": "EEN-02", "subject_id": "subject:two", "arm": "blind"},
    ]}
    # The executable's hash routine is canonical JSON; obtain its exact value
    # through the same stable JSON material rather than prose interpretation.
    import hashlib
    cohort_hash = hashlib.sha256(json.dumps(cohort, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    regulatory = tmp_path / "regulatory"
    rich = tmp_path / "rich"
    _write(regulatory / "source-attempt-manifest.json", {"corpus_id": "old", "version": "1.0.0", "manifest_sha256": "old-manifest", "cohort_sha256": cohort_hash, "attempts": [{"case_id": "EEN-01", "status": "captured", "source_family": "acnc_regulatory"}]})
    _write(rich / "source-attempt-manifest.json", {"manifest_sha256": "rich-manifest", "cohort_sha256": cohort_hash, "attempts": [{"case_id": "EEN-01", "status": "captured", "source_family": "regulatory_filing"}, {"case_id": "EEN-02", "status": "unavailable", "source_family": "official_website"}]})
    cohort_path = tmp_path / "cohort.json"
    _write(cohort_path, cohort)
    output = tmp_path / "out"
    result = subprocess.run([sys.executable, str(FREEZER), "--cohort", str(cohort_path), "--regulatory", str(regulatory), "--rich", str(rich), "--out", str(output)], check=True, capture_output=True, text=True)
    frozen = json.loads((output / "frozen-corpus.json").read_text())
    assert json.loads(result.stdout)["packets"] == 4
    assert frozen["cohort_sha256"] == cohort_hash
    assert frozen["source_family_case_coverage"] == {"acnc_regulatory": 1, "regulatory_filing": 1}
    assert frozen["coverage_by_case"][0]["rich_non_acnc"] is True
    assert frozen["coverage_by_case"][1]["rich_non_acnc"] is False
