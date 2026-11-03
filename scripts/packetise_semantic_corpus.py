"""Mechanically packetise a retained frozen corpus; never acquires or interprets."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from charitygraph.semantic_packetisation import build_packets, canonical

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--chunk-size", type=int, default=0)
    args = parser.parse_args()
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    result = build_packets(corpus, chunk_size=args.chunk_size)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(canonical(result))
    print(json.dumps({"packetisation_sha256": result["packetisation_sha256"], "registry_entries": len(result["registry"]), "packets": len(result["packets"]), "network_allowed": result["network"]["allowed"]}, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
