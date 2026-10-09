import pytest

from charitygraph.unified_semantic_experiment import (
    ARMS, METRICS, UnifiedSemanticOutput, enforce_spend, freeze_contract, runnable_cases, score_rows,
)


def cohort():
    return {"cases": [{"case_id": f"c{i}", "subject_id": f"s{i}", "arm": "challenge" if i < 10 else "blind"} for i in range(15)]}


def frozen_corpus(c):
    from charitygraph.unified_semantic_experiment import canonical_hash
    return {"cohort_sha256": canonical_hash(c), "provider_calls": 0, "candidate_outputs_present": False}


def test_contract_freezes_existing_general_boundary_and_all_three_arms():
    c = cohort(); frozen = freeze_contract(c, frozen_corpus(c))
    assert len(ARMS) == 3 and frozen.baseline["general_contract"] == "compact-knowledge-v0.2"
    assert "qualification_loss" in METRICS and frozen.unified_schema_sha256


def test_holdout_is_not_runnable_before_final_validation():
    c = cohort()
    assert len(runnable_cases(c)) == 10
    assert len(runnable_cases(c, final_holdout=True)) == 15
    with pytest.raises(ValueError):
        freeze_contract({"cases": c["cases"][:-1]}, frozen_corpus(c))


def test_corpus_must_be_presemantic_and_spend_is_cumulative():
    c = cohort(); bad = frozen_corpus(c); bad["provider_calls"] = 1
    with pytest.raises(ValueError): freeze_contract(c, bad)
    assert str(enforce_spend({"entries": [{"cost_usd": "1.95"}]}, "0.05")) == "0.00"
    with pytest.raises(ValueError): enforce_spend({"entries": [{"cost_usd": "1.95"}]}, "0.051")


def test_unified_contract_retains_domain_separation_and_scoring_is_label_driven():
    assert set(UnifiedSemanticOutput.model_fields) == {"general", "ethos_notability"}
    out = score_rows(({"case_id": "c1", "unsupported_positive": True, "calls": 1, "input_tokens": 9, "output_tokens": 2, "usd_per_organisation": 0.01},))
    assert out["metrics"]["unsupported_positive"] == 1 and out["usd_per_organisation"] == 0.01
