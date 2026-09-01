"""Full-corpus Compact Knowledge v0.2 shard runner.

Shard planning is delegated to the established deterministic planner; provider
execution is deliberately hard-wired to the validated Compact v0.2 contract.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR.parent / "src"))
from charitygraph.compact_knowledge import COMPACT_V02_SCHEMA, CompactKnowledgeOutputV02
from charitygraph.openai_client import estimate_response_cost, responses_create
from run_complete_card_sharded_v01 import _packet_for, _shard, _public_packet

MODEL = "gpt-5.6-luna"
REASONING_EFFORT = "none"
MAX_OUTPUT_TOKENS = 7000
MAX_ATTEMPTS = 1
EXPERIMENT_CAP_USD = Decimal("0.15")
PROMPT = (
    "Extract all evidence-supported CharityGraph knowledge atoms from this packet. "
    "Return only Compact Knowledge v0.2 JSON with an atoms array. Each atom must "
    "contain one concise proposition, scope, ISO temporal fields, epistemic status, "
    "packet-local evidence locators and qualifications. Do not use North-Star "
    "sections, taxonomies, card completeness, opaque IDs or outside knowledge. "
    "Sparse output is correct."
)


def plan(abns: list[str]) -> dict:
    subjects = []
    total = Decimal("0")
    for abn in abns:
        packet = _packet_for(abn)
        rows = []
        for index, shard in enumerate(_shard(packet), 1):
            public = _public_packet(shard)
            payload = json.dumps(public, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
            input_tokens = (len(payload) + len(PROMPT.encode()) + 3) // 4
            projected = (Decimal(input_tokens) * Decimal("0.20") + Decimal(MAX_OUTPUT_TOKENS) * Decimal("1.20")) / Decimal(1_000_000)
            total += projected
            rows.append({
                "shard": index,
                "packet_sha256": hashlib.sha256(payload).hexdigest(),
                "input_tokens_estimate": input_tokens,
                "model": MODEL,
                "schema_version": "compact-knowledge-v0.2",
                "reasoning_effort": REASONING_EFFORT,
                "max_output_tokens": MAX_OUTPUT_TOKENS,
                "max_attempts": MAX_ATTEMPTS,
                "projected_cost_usd": str(projected.quantize(Decimal("0.000001"))),
                "deterministic_task_identity": f"compact-v02:{abn}:shard-{index:02d}",
            })
        subjects.append({"abn": abn, "subject": packet["subject"], "shard_count": len(rows), "shards": rows})
    return {
        "runner": "full-corpus-compact-v02",
        "model": MODEL,
        "schema_version": "compact-knowledge-v0.2",
        "reasoning_effort": REASONING_EFFORT,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "max_attempts": MAX_ATTEMPTS,
        "experiment_cap_usd": str(EXPERIMENT_CAP_USD),
        "projected_total_usd": str(total.quantize(Decimal("0.000001"))),
        "subjects": subjects,
    }


def execute_shard(public_packet: dict) -> tuple[object, object]:
    """Execute one shard through the validated Compact v0.2 provider path.

    Callers must explicitly opt into this function; the CLI is dry-run only.
    The fixed arguments prevent fallback to the superseded whole-card executor.
    """
    payload = json.dumps(public_packet, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    response = responses_create(
        model=MODEL,
        input_text=PROMPT + "\nPACKET:\n" + payload,
        text_format={"type": "json_schema", "name": "compact_knowledge_v02", "strict": True, "schema": COMPACT_V02_SCHEMA},
        max_output_tokens=MAX_OUTPUT_TOKENS,
        max_attempts=MAX_ATTEMPTS,
        timeout_seconds=300,
        reasoning={"effort": REASONING_EFFORT},
    )
    return CompactKnowledgeOutputV02.model_validate(json.loads(response.output_text)), response.usage


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("abn", nargs="+")
    parser.add_argument("--root", type=Path, default=Path(r"C:\CharityGraph-runtime\full-corpus-compact-v02"))
    args = parser.parse_args()
    result = plan(args.abn)
    args.root.mkdir(parents=True, exist_ok=True)
    (args.root / "dry-run-plan.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if Decimal(result["projected_total_usd"]) > EXPERIMENT_CAP_USD:
        print("provider execution blocked: projected exposure exceeds cap", file=sys.stderr)


if __name__ == "__main__":
    main()
