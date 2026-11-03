"""Prospectively address the 100 ACNC Register members, offline and atomically."""
from pathlib import Path
import json
from charitygraph.phase5_evidence_addressing import address, prove_discovery

CORPUS = Path(r"C:\CharityGraph-runtime\phase5-top100-baseline-corpus-v1-clean\corpora")
CATALOG = Path(r"C:\CharityGraph-runtime\state\charitygraph.sqlite3")
RUNTIME = Path(r"C:\CharityGraph-runtime\phase5-top100-baseline-corpus-v1")
OUTPUT = Path(r"C:\CharityGraph-runtime\phase5-top100-acnc-addressed-v1")

projection = address(corpus_dir=CORPUS, catalog_path=CATALOG, store_roots=(RUNTIME / "objects", Path(r"C:\CharityGraph-runtime\state\objects")), output_root=OUTPUT)
proof = prove_discovery(projection=projection, catalog_path=CATALOG, runtime_root=RUNTIME, store_root=RUNTIME)
(OUTPUT / "discovery-v2-readiness.json").write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"projection_hash": projection["projection_hash"], "locators": len(projection["members"]), **{k: v for k, v in proof.items() if k != "results"}}, sort_keys=True))
