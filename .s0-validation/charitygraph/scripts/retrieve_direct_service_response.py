"""Retrieve safe metadata for the completed Red Cross Responses response."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from charitygraph.openai_client import OpenAIRequestError, responses_retrieve

def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--response-id", default="resp_016ce699ce1d578b006a958157292c87d0b0f62a669da3e9c3"); ap.add_argument("--output", type=Path, default=Path(r"C:\CharityGraph-runtime\direct-service-real-run-phase3-wire-v1\retrieved-response-metadata.json")); args = ap.parse_args()
    try:
        metadata = responses_retrieve(args.response_id)
        payload = {"retrieval": "existing_response_metadata", **metadata.__dict__}
    except OpenAIRequestError as exc:
        payload = {"retrieval": "failed", "error_class": type(exc).__name__, "error_message": str(exc)[:512], "status_code": exc.status_code, "attempts_made": exc.attempts_made, "diagnostic": exc.diagnostic.as_dict() if exc.diagnostic else None}
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"); print(json.dumps(payload, indent=2, sort_keys=True)); return 0

if __name__ == "__main__": raise SystemExit(main())
