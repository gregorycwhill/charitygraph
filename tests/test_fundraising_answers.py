import json
from pathlib import Path

from charitygraph.fundraising_answers import FundraisingQuestion, answer_fundraising_question
from charitygraph.fundraising_money_linkage import FundraisingMoneyScopeLink
from charitygraph.fundraising_query import FundraisingQueryInput
from charitygraph.models import CauseBaseCard


def item():
    fixture = Path(__file__).parent / "fixtures" / "fundraising_card_projection.json"
    data = json.loads(fixture.read_text(encoding="utf-8"))
    return FundraisingQueryInput(card=CauseBaseCard.model_validate(data["card"]), money_links=tuple(FundraisingMoneyScopeLink.model_validate(x) for x in data["money_links"]))


def test_every_user_question_has_a_deterministic_governed_shape():
    subject = item()
    questions = (
        FundraisingQuestion(kind="current_f2f"), FundraisingQuestion(kind="evidenced_methods"),
        FundraisingQuestion(kind="external_provider"), FundraisingQuestion(kind="disclosed_costs"),
        FundraisingQuestion(kind="disclosed_income_or_proceeds"), FundraisingQuestion(kind="amounts_linked_to_activity", activity_scope_kind="campaign", activity_scope_id="fc_card_appeal"),
        FundraisingQuestion(kind="unknowns"), FundraisingQuestion(kind="compatible_cost_change"),
    )
    answers = tuple(answer_fundraising_question(subject, question) for question in questions)
    assert [answer.status for answer in answers] == ["supported", "supported", "unknown", "supported", "unknown", "unknown", "supported", "refused"]
    assert all(answer.causebase_id == subject.card.causebase_id for answer in answers)
    assert all(answer.model_dump(mode="json") == answer_fundraising_question(subject, answer.question).model_dump(mode="json") for answer in answers)
    assert answers[0].evidence and answers[0].source_wording
    assert answers[3].money_observation_ids and answers[3].evidence
    assert answers[-1].refusal_reason == "comparison_input_and_compatibility_required"


def test_linkage_question_refuses_missing_target_and_never_allocates_aggregate_money():
    subject = item()
    missing = answer_fundraising_question(subject, FundraisingQuestion(kind="amounts_linked_to_activity"))
    aggregate = answer_fundraising_question(subject, FundraisingQuestion(kind="amounts_linked_to_activity", activity_scope_kind="practice", activity_scope_id="fp_card_f2f"))
    assert missing.status == "refused"
    assert missing.refusal_reason == "activity_scope_required"
    assert aggregate.status == "unknown"
    assert aggregate.money_observation_ids == ()


def test_historical_f2f_is_unknown_not_a_false_currentness_answer():
    subject = item()
    payload = subject.card.model_dump(mode="json")
    payload["fundraising_practice_observed"][0]["lifecycle"] = "historical"
    historical = FundraisingQueryInput(card=CauseBaseCard.model_validate(payload), money_links=subject.money_links)
    answer = answer_fundraising_question(historical, FundraisingQuestion(kind="current_f2f"))
    assert answer.status == "unknown"
    assert answer.observation_ids == ()
