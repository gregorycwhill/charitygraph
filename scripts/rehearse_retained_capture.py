"""Run the no-provider retained-capture input rehearsal against a local archive."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from charitygraph.ethos_notability_extraction import ProviderResponse, run_ethos_extraction, run_history_extraction
from charitygraph.reality_spike_retained import load_reality_spike_universes


class OfflineAbstentionProvider:
    """Production-shaped provider boundary which cannot perform a provider call."""
    def extract(self, **_: object) -> ProviderResponse:
        return ProviderResponse('{"outcome":"abstain","ethos_candidates":[],"history_candidates":[],"reason":"provider-free retained-capture rehearsal"}', "offline-rehearsal", "none")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive_root", type=Path)
    args = parser.parse_args()
    provider = OfflineAbstentionProvider()
    results = []
    for universe in load_reality_spike_universes(args.archive_root):
        ethos = run_ethos_extraction(universe, provider)
        history = run_history_extraction(universe, provider)
        results.append({"subject_id": universe.subject_id, "capture_count": len(universe.captures), "source_families": sorted({capture.source_record.source_family for capture in universe.captures}), "ethos_packet_hash": ethos["packet_hash"], "history_packet_hash": history["packet_hash"], "ethos_handoff": ethos["handoff"]["state"], "history_handoff": history["handoff"]["state"]})
    print(json.dumps({"network_acquisition": False, "provider_calls": 0, "organisations": results}, indent=2))


if __name__ == "__main__":
    main()
