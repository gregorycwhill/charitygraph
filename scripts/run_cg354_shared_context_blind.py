"""Execute frozen CG354 D on every original blind control exactly once.

This is a transport/economics experiment.  It validates immutable retained
bytes, makes one Responses request per case and records raw telemetry; it does
not classify evidence or score language in Python.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

from charitygraph.openai_client import OpenAIRequestError, estimate_response_cost, responses_create
from charitygraph.shared_source_context import (
    CONTEXT_VERSION, build_registry, canonical_hash, provider_evidence_body,
    validate_no_duplicate_transmission,
)
from charitygraph.unified_semantic_experiment import (
    MODEL, UNIFIED_PROMPT, UNIFIED_SCHEMA, UnifiedSemanticOutput, enforce_spend,
)

EXPECTED_CORPUS = "120e20160adbfd27a53b526b200e85841850ded612a839dd4381110295300644"
BLIND_CASES = ("EEN-11", "EEN-12", "EEN-13", "EEN-14", "EEN-15")
D_PROMPT_VERSION = "cg354-shared-source-context-prompt-v1"
D_PROMPT = UNIFIED_PROMPT + """

The evidence below is a shared retained-source registry.  Each S evidence id is
transmitted exactly once; its binding list identifies every frozen section
packet using it.  Treat the registry as the complete admissible evidence
universe.  For ethos/notability candidates cite the registry S evidence ids.
"""


def strict_schema(schema):
    value = json.loads(json.dumps(schema))
    def visit(node):
        if isinstance(node, dict):
            node.pop("default", None)
            if node.get("type") == "object" and isinstance(node.get("properties"), dict):
                node["required"] = list(node["properties"])
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)
    visit(value)
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--representations", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cap", default="2.00")
    args = parser.parse_args()
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    if corpus.get("corpus_sha256") != EXPECTED_CORPUS:
        raise SystemExit("frozen corpus identity mismatch")
    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    schema = strict_schema(UNIFIED_SCHEMA)
    report = {"experiment_id": "CG-SHARED-SEMANTIC-READ-354", "arm": "D_shared_source_context",
              "model": MODEL, "provider_path": "openai.responses", "corpus_sha256": EXPECTED_CORPUS,
              "context_version": CONTEXT_VERSION, "prompt_version": D_PROMPT_VERSION,
              "prompt_sha256": sha256(D_PROMPT.encode()).hexdigest(),
              "schema_sha256": canonical_hash(schema), "cases": []}
    for case_id in BLIND_CASES:
        packets = tuple(next(p for p in corpus["packets"] if p["case_id"] == case_id and p["section"] == section) for section in (15, 17))
        row = {"case_id": case_id, "packet_hashes": {str(p["section"]): p["packet_hash"] for p in packets}}
        try:
            registry = build_registry(packets, str(args.representations))
            validate_no_duplicate_transmission(registry)
            body = provider_evidence_body(registry, str(args.representations))
            request = D_PROMPT + "\nSHARED REGISTRY:\n" + json.dumps(
                {k: v for k, v in registry.items() if k != "evidence"}, sort_keys=True, ensure_ascii=False
            ) + "\nEVIDENCE:\n" + body
        except (KeyError, StopIteration, ValueError, OSError) as error:
            row.update({"packet_failure": True, "failure": str(error), "request_hash": None,
                        "response_hash": None, "raw_response": None,
                        "telemetry": {"input_tokens": 0, "output_tokens": 0, "cost_usd": "0", "response_id": None}})
            report["cases"].append(row)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            continue
        enforce_spend(ledger, "0.01", cap_usd=args.cap)
        try:
            response = responses_create(model=MODEL, input_text=request,
                text_format={"type": "json_schema", "name": "cg354_shared_context", "strict": True, "schema": schema},
                max_output_tokens=1200, max_attempts=1, timeout_seconds=120, reasoning={"effort": "none"})
        except OpenAIRequestError as error:
            row.update({"packet_failure": False, "registry_sha256": registry["registry_sha256"],
                        "registry_evidence_count": len(registry["evidence"]), "request_hash": sha256(request.encode()).hexdigest(),
                        "response_hash": None, "raw_response": None, "provider_failure": str(error),
                        "telemetry": {"input_tokens": 0, "output_tokens": 0, "cost_usd": "0", "response_id": None}})
            report["cases"].append(row)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            continue
        cost = estimate_response_cost(response.model, response.usage)
        telemetry = {"at": datetime.now(timezone.utc).isoformat(), "model": response.model,
                     "cost_usd": str(cost or 0), "input_tokens": response.usage.input_tokens,
                     "output_tokens": response.usage.output_tokens, "response_id": response.response_id}
        ledger.setdefault("entries", []).append(telemetry)
        try:
            UnifiedSemanticOutput.model_validate_json(response.output_text)
            valid, reasons = True, []
        except Exception as error:
            valid, reasons = False, ["malformed_schema:" + str(error).splitlines()[0]]
        row.update({"packet_failure": False, "registry_sha256": registry["registry_sha256"],
                    "registry_evidence_count": len(registry["evidence"]), "request_hash": sha256(request.encode()).hexdigest(),
                    "response_hash": sha256(response.output_text.encode()).hexdigest(), "raw_response": response.output_text,
                    "valid": valid, "validation_reasons": reasons, "telemetry": telemetry})
        report["cases"].append(row)
        args.ledger.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    report["aggregate"] = {"calls": sum(row["telemetry"]["response_id"] is not None for row in report["cases"]), "valid": sum(row.get("valid", False) for row in report["cases"]),
        "input_tokens": sum((row["telemetry"]["input_tokens"] or 0) for row in report["cases"]),
        "output_tokens": sum((row["telemetry"]["output_tokens"] or 0) for row in report["cases"]),
        "cost_usd": str(sum((Decimal(row["telemetry"]["cost_usd"]) for row in report["cases"]), Decimal("0")))}
    report["report_sha256"] = canonical_hash(report)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
