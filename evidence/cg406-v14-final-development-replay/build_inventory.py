"""Build final SHA-256 inventory; the inventory intentionally excludes itself."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
RUNTIME = Path(r"C:\CharityGraph-runtime\cg406-v14-final-development-replay-run01")
FROZEN = Path(r"C:\CharityGraph-runtime\cg406-fresh-governed-quality-holdout-a1")
V13 = Path(r"C:\CharityGraph-runtime\cg406-v13-inference-integrity-a3")
ORACLE = Path(r"C:\CharityGraph-blind-reference\cg406\oracle-output")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    destination = ROOT / "artifact-inventory.json"
    if destination.exists():
        raise RuntimeError(f"refusing to overwrite inventory: {destination}")
    files = sorted(path for path in ROOT.rglob("*") if path.is_file() and path != destination)
    referenced_paths = {
        "prepared-run.json": RUNTIME / "prepared-run.json",
        "frozen-pricing-snapshot.json": RUNTIME / "frozen-pricing-snapshot.json",
        "frozen-subject-manifest.json": FROZEN / "frozen-subject-manifest.json",
        "frozen-demand-instance-manifest.json": FROZEN / "frozen-demand-instance-manifest.json",
        "governed-provider-corpus.json": V13 / "governed-provider-corpus.json",
        "artifact-rights-decisions.json": V13 / "artifact-rights-decisions.json",
        "v13-frozen-result-manifest.json": V13 / "v13-frozen-result-manifest.json",
        "v13-terminal-result-ledger.json": V13 / "v13-terminal-result-ledger.json",
        "v13-validation-results.json": REPO / "evidence" / "cg406-v13-development-replay" / "validation-results.json",
        "oracle-independent-reference-ledger.json (hash-only after v1.4 freeze)": ORACLE / "independent-reference-ledger.json",
        "oracle-manifest.json (hash-only after v1.4 freeze)": ORACLE / "oracle-manifest.json",
    }
    value = {
        "schema": "charitygraph.cg406-v14-final-evidence-inventory/v1",
        "hash_algorithm": "SHA-256",
        "inventory_self_hash_excluded": True,
        "local_artifact_count_excluding_inventory": len(files),
        "local_artifacts": [
            {"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)}
            for path in files
        ],
        "referenced_frozen_inputs_and_comparison_sources": [
            {"name": name, "path": str(path), "sha256": sha(path), "copied_into_packet": False}
            for name, path in referenced_paths.items()
        ],
        "frozen_result_manifest_embedded_sha256": json.loads((ROOT / "frozen-result-manifest.json").read_text(encoding="utf-8"))["result_manifest_sha256"],
        "scope_note": "Raw request bodies and governed source bodies are not copied into the evidence packet. The twelve unchanged first terminal provider responses are included. Oracle content was not semantically inspected; its two listed files were read only for SHA-256 after the v1.4 result manifest was frozen.",
    }
    destination.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
