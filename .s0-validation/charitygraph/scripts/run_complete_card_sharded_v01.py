"""Run the bounded, section-agnostic complete-card shard experiment.

This runner only partitions existing representations; it never filters by
section or keyword. Raw packets and responses are written to private runtime.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, "src")
import run_worldvision_luna_v02 as whole_card  # noqa: E402

REPORT = Path(r"C:\CharityGraph-runtime\baseline-corpus-v1-final-correction2-20260830\baseline-corpus-v1-report.json")
CATALOG = Path(r"C:\CharityGraph-runtime\state\charitygraph.sqlite3")
DEFAULT_ROOT = Path(r"C:\CharityGraph-runtime\complete-card-sharded-v01")
TARGET_INPUT_TOKENS = 35_000
MAX_OUTPUT_TOKENS = 5_000


def _packet_for(abn: str) -> dict[str, Any]:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    subject = next(row for row in report["subjects"] if row["abn"] == abn)
    corpus = next(row for row in report["corpora"] if row["subject_id"] == subject["subject_id"])
    db = sqlite3.connect(CATALOG)
    sources: list[dict[str, Any]] = []
    for member in corpus["material_members"]:
        for record_id in member["source_record_ids"]:
            row = db.execute(
                "select source_record_id,source_family,source_role,source_version,source_locator,payload_ref,material_json from source_records where source_record_id=?",
                (record_id,),
            ).fetchone()
            if row is None or row[2] in {"robots", "sitemap"}:
                continue
            content, kind = whole_card._content(row, member)
            sources.append(
                {
                    "source_record_id": row[0], "source_family": row[1], "source_role": row[2],
                    "source_version": row[3], "source_locator": row[4],
                    "effective_period": member.get("effective_period"),
                    "binding_context": member.get("binding_context"),
                    "representation_readiness": member.get("representation_readiness"),
                    "representation_gaps": member.get("representation_gaps", []),
                    "content_kind": kind,
                    "content": content,
                }
            )
    db.close()
    return {
        "packet_version": "whole-card-semantic-knowledge-production-v0.2",
        "subject": {"name": subject["registered_name"], "abn": abn, "subject_id": subject["subject_id"]},
        "corpus_id": corpus["corpus_id"], "material_identity_hash": corpus["material_identity_hash"],
        "sources": sources,
    }


def _estimate(packet: dict[str, Any]) -> int:
    return (len(json.dumps(packet, ensure_ascii=False, sort_keys=True, separators=(",", ":"))) + len(whole_card._prompt())) // 4


def _public_packet(packet: dict[str, Any]) -> dict[str, Any]:
    sources = []
    for index, source in enumerate(packet["sources"], 1):
        key = f"S{index:03d}"
        locators = [{"locator": f"{key}:L{i:04d}", "text": line} for i, line in enumerate(whole_card._lines(source["content"]), 1)]
        sources.append({k: source[k] for k in source if k != "content"} | {"source_key": key, "locators": locators})
    return {k: packet[k] for k in packet if k != "sources"} | {"sources": sources}


def _shard(packet: dict[str, Any]) -> list[dict[str, Any]]:
    shards: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    for source in packet["sources"]:
        candidate = current + [source]
        probe = dict(packet, sources=candidate)
        if current and _estimate(probe) > TARGET_INPUT_TOKENS:
            shards.append(dict(packet, sources=current))
            current = []
        if len(source["content"]) and _estimate(dict(packet, sources=[source])) > TARGET_INPUT_TOKENS:
            lines = whole_card._lines(source["content"])
            chunk_size = max(1, int(len(lines) * TARGET_INPUT_TOKENS / max(_estimate(dict(packet, sources=[source])), 1)))
            for start in range(0, len(lines), chunk_size):
                current_source = dict(source, content="\n".join(lines[start : start + chunk_size]))
                shards.append(dict(packet, sources=[current_source]))
            current = []
        else:
            current.append(source)
    if current:
        shards.append(dict(packet, sources=current))
    return shards


def _run_shard(shard: dict[str, Any], output: Path) -> dict[str, Any]:
    output.parent.mkdir(parents=True, exist_ok=True)
    original = whole_card.build_packet
    whole_card.build_packet = lambda *args, **kwargs: (_public_packet(shard), {s["source_key"]: s["source_record_id"] for s in _public_packet(shard)["sources"]})
    whole_card.MAX_OUTPUT_TOKENS = MAX_OUTPUT_TOKENS
    whole_card.MAX_ATTEMPTS = 1
    whole_card.SPEND_CAP_USD = Decimal("0.15")
    try:
        return whole_card.run(output)
    finally:
        whole_card.build_packet = original


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("abn", nargs="+")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    total_projected = Decimal("0")
    plans: list[dict[str, Any]] = []
    for abn in args.abn:
        packet = _packet_for(abn)
        shards = _shard(packet)
        rows = []
        for index, shard in enumerate(shards, 1):
            packet_bytes = json.dumps(_public_packet(shard), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
            tokens = (len(packet_bytes) + len(whole_card._prompt().encode()) + 3) // 4
            projected = (Decimal(tokens) * Decimal("0.20") + Decimal(MAX_OUTPUT_TOKENS) * Decimal("1.20")) / Decimal(1_000_000)
            total_projected += projected
            row = {"shard": index, "sources": len(shard["sources"]), "input_tokens": tokens, "projected_usd": str(projected.quantize(Decimal("0.000001")))}
            if args.execute:
                row["report"] = _run_shard(shard, args.root / abn / f"shard-{index:02d}")
            rows.append(row)
        plans.append({"abn": abn, "subject": packet["subject"], "shard_count": len(shards), "shards": rows})
    result = {"target_input_tokens": TARGET_INPUT_TOKENS, "max_output_tokens": MAX_OUTPUT_TOKENS, "projected_total_usd": str(total_projected.quantize(Decimal("0.000001"))), "subjects": plans}
    args.root.mkdir(parents=True, exist_ok=True)
    (args.root / "shard-plan.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
