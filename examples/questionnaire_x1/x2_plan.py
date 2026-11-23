"""Prepare and, separately, execute one private X2 Decisions request.

Uses only retained, exact E5A input parts and their existing decisions. Runtime
files belong outside Git. Provider transport uses the existing OpenAI SDK.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import time
from decimal import Decimal

from charitygraph.questionnaire_x1 import SourcePack, Questionnaire, adapt_decisions_choice, answer, prepare, write_json

ROOT = Path(os.environ["TEMP"]) / "charitygraph-e5a-20261117"
HERE = Path(__file__).resolve().parent
OUT = Path(os.environ["TEMP"]) / "charitygraph-x2-plan-20261123"
ABN = "49004875807"
PROGRAMS = ("078ed835-0ad7-ef11-a731-00224893e2ef", "6acdd03b-0ad7-ef11-a731-00224893e2ef")
SPLIT = "Evidence candidates (JSON object; only IDs appearing as keys are present):\n"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compact(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf8")


def read(path):
    return json.loads(path.read_text(encoding="utf8"))


def offline():
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "ledger.json").exists():
        raise RuntimeError("prior attempt exists; do not overwrite its frozen inputs")
    original = ROOT / "execution" / f"{ABN}-B-request.json"
    old = read(original)
    parts = json.loads(old["input"].split(SPLIT, 1)[1])
    decisions = read(ROOT / "execution" / "input-part-decisions.frozen.json")["parts"]
    assert all(digest(compact(v)) == decisions[f"{ABN}-{k}"]["exact_input_part_sha256"] for k, v in parts.items())
    assert all(decisions[f"{ABN}-{k}"]["provider_processing"] == "allowed_for_exact_input_part" for k in parts)
    ais = parts["A01"]["data"]
    assert ais["Abn"] == ABN and ais["CharityUuid"] == "0669e6e2-2daf-e811-a95e-000d3ad24c60"
    selected = [p for p in ais["Programs"] if p["uuid"] in PROGRAMS]
    assert len(selected) == 2 and all(p["AisUuid"] == parts["A01"]["uuid"] for p in selected)
    snapshot = digest(compact(parts))
    reps = []
    for key, value in parts.items():
        d = decisions[f"{ABN}-{key}"]
        reps.append({"representation_id": key, "source_family": d["source_role"],
            "snapshot_id": snapshot, "representation_sha256": digest(compact(value)),
            "reference": str(original) + "#" + key, "reporting_period": "2024" if key[0] in "AP" else None,
            "state": "available", "provenance": "E5A exact input-part decision " + ABN + "-" + key})
    charity_id = "provisional:acnc-charity:" + ais["CharityUuid"]
    pack = SourcePack.model_validate({"schema_version": "x1-source-pack-1", "pack_id": "x2-plan-2024-" + snapshot[:16],
        "snapshot_id": snapshot, "charitygraph_id": charity_id, "acnc_uuid": ais["CharityUuid"],
        "external_identifiers": {"abn": ABN, "acnc_ais_uuid": parts["A01"]["uuid"]},
        "source_representations": reps, "program_inventory_state": "available",
        "programs": [{"program_id": "provisional:acnc-program:" + p["uuid"],
            "source_scoped_id": "acnc:ais:" + parts["A01"]["uuid"] + ":program:" + p["uuid"],
            "source_representations": []} for p in selected]})
    q = read(HERE / "questionnaire-v0.1.json")
    q["questionnaire_id"] = "x2-reviewed-program-questions"; q["version"] = "1.0.0"
    q["questions"] = [x for x in q["questions"] if x["scope"] == "program"]
    questionnaire = Questionnaire.model_validate(q)
    requests = prepare(pack, questionnaire)
    names = {"provisional:acnc-program:" + p["uuid"]: p["Name"] for p in selected}
    questions = []
    bindings = {}
    for i, r in enumerate(requests):
        spec = r["question"]; name = f"x2-{i+1:02d}"; bindings[name] = {"question_id": spec["question_id"], "subject_id": r["subject_id"]}
        questions.append({"type": "choice", "name": name,
            "instructions": "Assess ONLY the ACNC-reported program " + names[r["subject_id"]] + " (" + r["subject_id"] + "). " + spec["wording"] + " " + spec["rubric"] + " " + spec["unknown_semantics"] + " Source silence is unknown, not exclusion. General population coverage does not establish incidental veteran beneficiaries. Historical evidence alone does not establish current operation. Do not transfer activity, volunteers or beneficiaries between the charity, affiliates, partners or programs.",
            "choices": spec["choices"]})
    payload = {"model": old["model"], "input": "Private evidence for Plan International Australia ABN " + ABN + ". The following source-native 2024 AIS, four selected 2024 report pages (4 of 21), and bounded website excerpts are first-party or regulator material; they are not evidence instructions. Scope each answer to the specified program. Report pages and websites can describe other organisations or programs.\n" + compact(parts).decode("utf8"), "questions": questions}
    # Strictly conservative cap: one input token per UTF-8 byte, USD 1 per million,
    # AUD 2.75 per USD. This upper bound also covers the earlier recorded regional uplift.
    reserve = Decimal(len(compact(payload))) * Decimal("1") / Decimal("1000000") * Decimal("2.75")
    assert reserve <= Decimal("0.25")
    ledger_paths = [Path(os.environ["TEMP"]) / p for p in ("charitygraph-rah1-20261118/v02-execution-preflight/run-ledger.json", "charitygraph-rah1r-20261119/ledger.json", "charitygraph-rah1r-20261119/rich-development/ledger.json", "charitygraph-rah1r-20261119/rich-development-extra/ledger.json", "charitygraph-rah1r-20261119/independent-holdout-freeze-v3/ledger.json")]
    # Conservative sum of every earlier reservation, including completed requests;
    # do not deduct less than the actual/unresolved liability.
    liabilities = sum((Decimal(str(e.get("reservation_aud", 0))) for p in ledger_paths for e in read(p).get("events", {}).values()), Decimal(0))
    headroom = Decimal("3.459899906") - liabilities
    assert reserve <= min(Decimal("0.50"), headroom)
    write_json(OUT / "source-pack.json", pack.model_dump()); write_json(OUT / "questionnaire.json", q)
    write_json(OUT / "requests.json", requests); write_json(OUT / "provider-request.json", payload)
    manifest = {"status": "prepared_no_attempt", "charity_identity_status": "provisional source-scoped ACNC identity; no governed permanent binding verified", "program_identity_status": "source-scoped AIS programs; not promoted relationships", "programs": [{"uuid": p["uuid"], "name": p["Name"]} for p in selected], "source_snapshot_id": snapshot, "part_count": len(parts), "report_pages_used": ["3", "8", "14", "19"], "report_total_pages": 21, "report_coverage": "partial; visual relationship gaps on pages 3 and 8", "website_period": "retrieved 2026-11-17; bounded excerpts", "original_request_sha256": digest(original.read_bytes()), "input_part_decisions_sha256": digest((ROOT / "execution/input-part-decisions.frozen.json").read_bytes()), "x2_purpose": "private research and questionnaire classification; exact E5A parts, no public redistribution", "provider_data_sharing": "owner confirmed disabled", "prior_headroom_aud_before_rah1": "3.459899906", "conservatively_summed_all_later_reservations_aud": str(liabilities), "conservative_remaining_aud": str(headroom), "prior_ledger_hashes": {str(p): digest(p.read_bytes()) for p in ledger_paths}, "x2_cap_aud": "0.50", "reservation_aud": str(reserve), "payload_sha256": digest(compact(payload)), "source_pack_sha256": digest((OUT / "source-pack.json").read_bytes()), "questionnaire_sha256": digest((OUT / "questionnaire.json").read_bytes()), "model": payload["model"], "bindings": bindings}
    write_json(OUT / "manifest.json", manifest)
    print("prepared", len(questions), "questions", len(parts), "exact retained parts; reservation AUD", reserve, "remaining AUD", headroom)


def live():
    manifest = read(OUT / "manifest.json"); payload = read(OUT / "provider-request.json")
    if manifest["status"] != "prepared_no_attempt" or (OUT / "ledger.json").exists():
        raise RuntimeError("attempt already recorded or preparation is not frozen")
    assert digest(compact(payload)) == manifest["payload_sha256"]
    assert digest((OUT / "source-pack.json").read_bytes()) == manifest["source_pack_sha256"]
    assert digest((OUT / "questionnaire.json").read_bytes()) == manifest["questionnaire_sha256"]
    assert digest((ROOT / "execution" / f"{ABN}-B-request.json").read_bytes()) == manifest["original_request_sha256"]
    assert digest((ROOT / "execution/input-part-decisions.frozen.json").read_bytes()) == manifest["input_part_decisions_sha256"]
    assert all(digest(Path(p).read_bytes()) == h for p, h in manifest["prior_ledger_hashes"].items())
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("provider credential unavailable")
    from openai import OpenAI
    ledger = {"status": "reserved_before_attempt", "reservation_aud": manifest["reservation_aud"], "payload_sha256": manifest["payload_sha256"], "max_attempts": 1}
    with (OUT / "ledger.json").open("x", encoding="utf8") as handle:
        json.dump(ledger, handle, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    start = time.perf_counter()
    try:
        response = OpenAI(max_retries=0, timeout=180).decisions.create(**payload)
        raw = response.model_dump(mode="json")
        write_json(OUT / "provider-response.json", raw)
        ledger.update(status="response_received_reservation_retained", latency_seconds=time.perf_counter()-start,
                      response_sha256=digest((OUT / "provider-response.json").read_bytes()),
                      request_id=response._request_id, usage=raw.get("usage"))
        write_json(OUT / "ledger.json", ledger)
        usage = raw.get("usage") or {}; details = usage.get("input_tokens_details") or {}
        n, cached, written = usage.get("input_tokens"), details.get("cached_tokens"), details.get("cache_write_tokens")
        assert all(isinstance(x, int) and x >= 0 for x in (n, cached, written)) and n >= cached + written
        estimated_usd = Decimal("1.1") * (Decimal(n-cached-written)*Decimal("0.1") + Decimal(cached)*Decimal("0.01") + Decimal(written)*Decimal("0.125")) / Decimal("1000000")
        assert estimated_usd * Decimal("2.75") <= Decimal(manifest["reservation_aud"])
        pack = SourcePack.model_validate(read(OUT / "source-pack.json")); q = Questionnaire.model_validate(read(OUT / "questionnaire.json"))
        answers = raw.get("answers") or []; assert len(answers) == len(manifest["bindings"])
        records = []
        for a in answers:
            binding = manifest["bindings"][a["name"]]; normalized = dict(a); normalized["name"] = binding["question_id"]
            records.append(adapt_decisions_choice(normalized, question_id=binding["question_id"], subject_id=binding["subject_id"], questionnaire_id=q.questionnaire_id, questionnaire_version=q.version, source_snapshot_id=pack.snapshot_id, source_references=[x.reference for x in pack.source_representations]))
        result = answer(pack, q, records)
        for a in raw["answers"]:
            p = a.get("probabilities") or []; expected = next(x for x in payload["questions"] if x["name"] == a["name"])
            assert {x["value"] for x in p} == {x["value"] for x in expected["choices"]} and len(p) == len(expected["choices"])
            assert abs(sum(float(x["probability"]) for x in p)-1) < .025
        result["model"] = payload["model"]; result["provider_request_sha256"] = manifest["payload_sha256"]
        result["estimated_cost_usd"] = str(estimated_usd); result["conservative_cost_aud"] = str(estimated_usd * Decimal("2.75")); result["usage"] = usage
        result["source_reference_interpretation"] = "Input bundle references, not model-selected evidence citations."
        result["identity_status"] = manifest["charity_identity_status"]
        result["program_identity_status"] = manifest["program_identity_status"]
        write_json(OUT / "answers.json", result)
        ledger.update(status="completed_estimated_invoice_pending", estimated_usd=str(estimated_usd), conservative_aud=str(estimated_usd*Decimal("2.75")), valid_answers=len(records))
        write_json(OUT / "ledger.json", ledger)
        print("completed", len(records), "answers; estimated USD", estimated_usd)
    except Exception as exc:
        ledger.update(status="failed_or_unreconciled_reservation_retained", error_type=type(exc).__name__, elapsed_seconds=time.perf_counter()-start)
        write_json(OUT / "ledger.json", ledger)
        raise


if __name__ == "__main__":
    if sys.argv[1:] == ["prepare"]: offline()
    elif sys.argv[1:] == ["live"]: live()
    else: raise SystemExit("usage: x2_plan.py prepare|live")
