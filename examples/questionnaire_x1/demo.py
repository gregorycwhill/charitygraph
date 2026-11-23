"""Run synthetic X1 examples without acquisition, parsing or provider calls."""
from pathlib import Path
import sys

from charitygraph.questionnaire_x1 import answer, load_pack, load_questionnaire, prepare, write_json

HERE = Path(__file__).resolve().parent


def fixture_responses(requests):
    result = []
    for request in requests:
        q = request["question"]
        record = {"question_id": q["question_id"], "subject_id": request["subject_id"],
                  "questionnaire_id": request["questionnaire_id"], "questionnaire_version": request["questionnaire_version"],
                  "source_snapshot_id": request["snapshot_id"],
                  "status": "unknown", "method": "fixture", "value": None}
        if q["question_id"] == "X1-P03-01" and request["subject_id"] == "fixture-program-01":
            record.update(status="answered", value="currently_operating",
                          probabilities={"currently_operating": 0.7, "planned": 0.1,
                                         "paused": 0.05, "historical_or_completed": 0.05,
                                         "unknown": 0.1}, source_references=["fixture://program-source"])
        if q["question_id"] == "X1-P13-01":
            record.update(status="answered", value={"amount": 0, "currency": "AUD",
                "reporting_period": "2025", "source_reference": "fixture://charity-source",
                "basis": "reported"}, source_references=["fixture://charity-source"])
        result.append(record)
    return result


def main(destination: Path):
    destination.mkdir(parents=True, exist_ok=True)
    pack = load_pack(HERE / "source-pack-fixture.json")
    for version in ("0.1", "0.2"):
        questionnaire = load_questionnaire(HERE / f"questionnaire-v{version}.json")
        requests = prepare(pack, questionnaire)
        write_json(destination / f"requests-v{version}.json", requests)
        write_json(destination / f"answers-v{version}.json", answer(pack, questionnaire, fixture_responses(requests)))
    print(f"Synthetic private fixture output: {destination}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python examples/questionnaire_x1/demo.py PRIVATE_OUTPUT_DIRECTORY")
    main(Path(sys.argv[1]))
