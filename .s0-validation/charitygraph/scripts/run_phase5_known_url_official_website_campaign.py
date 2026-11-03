"""Prepare/certify, but never implicitly execute, the Phase-5 website campaign."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from charitygraph.phase5_official_website_campaign import build_campaign, execute_campaign, rehearse_network_edge, validate_campaign


def write_json(path: Path, value: object) -> None:
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profiles", type=Path, default=Path(r"C:\CharityGraph-runtime\top100-terra-v31-20260829\acnc-profiles.json"))
    parser.add_argument("--identity-map", type=Path, default=Path(r"C:\CharityGraph-runtime\phase5-top100-subject-bootstrap-v1\identity-map.json"))
    parser.add_argument("--inventory", type=Path, default=Path(r"C:\CharityGraph-runtime\phase5-top100-baseline-corpus-v1-clean\corrected-pre-run-source-inventory.json"))
    parser.add_argument("--output-root", type=Path, default=Path(r"C:\CharityGraph-runtime\phase5-top100-known-url-official-website-acquisition-v1"))
    parser.add_argument("--catalogue", type=Path, default=Path(r"C:\CharityGraph-runtime\state\charitygraph.sqlite3"))
    parser.add_argument("--execute", action="store_true", help="cross the network boundary; requires a separately reviewed host authorization")
    args = parser.parse_args()
    historical_attempt_ids: set[str] = set()
    manifest_path = args.output_root / "acquisition-manifest.json"
    if manifest_path.exists():
        # A BOM changes byte identity but not JSON meaning.  Never rewrite an
        # already prepared artefact merely to normalise its encoding; accept it
        # only when its parsed immutable object is exactly the candidate for a
        # fresh preparation. Resume uses the immutable manifest directly so a
        # historical row rejected by current pre-send policy is never rebuilt
        # or sent again.
        existing = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        if args.execute:
            state_path = args.output_root / "acquisition-runtime-state.json"
            state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
            historical_attempt_ids = set((state.get("attempts") or {}).keys())
            validate_campaign(existing, historical_attempt_ids=historical_attempt_ids)
            manifest = existing
        else:
            manifest = build_campaign(profiles_path=args.profiles, identity_map_path=args.identity_map, inventory_path=args.inventory)
            validate_campaign(manifest)
            if existing != manifest:
                raise RuntimeError("existing acquisition manifest differs; refuse replacement")
            manifest = existing
    else:
        manifest = build_campaign(profiles_path=args.profiles, identity_map_path=args.identity_map, inventory_path=args.inventory)
        validate_campaign(manifest)
        write_json(manifest_path, manifest)
    rehearsal = rehearse_network_edge(manifest, historical_attempt_ids=historical_attempt_ids)
    write_json(args.output_root / "network-edge-rehearsal.json", {"manifest_sha256": manifest["manifest_sha256"], "rows": rehearsal, "network_operations": 0, "provider_operations": 0})
    if args.execute:
        execution = execute_campaign(manifest=manifest, runtime_root=args.output_root, catalog_path=args.catalogue)
        write_json(args.output_root / "acquisition-execution-report.json", execution)
    print(json.dumps({"manifest_path": str(manifest_path), "manifest_sha256": manifest["manifest_sha256"], "manifest_file_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(), "manifest_byte_length": manifest_path.stat().st_size, "rows": len(manifest["rows"]), "network_edge_rehearsal_rows": len(rehearsal), "network_operations": "performed only with --execute", "provider_operations": 0}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
