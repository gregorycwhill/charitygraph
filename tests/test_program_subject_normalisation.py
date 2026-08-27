
from datetime import datetime, timezone
import pytest
from charitygraph.llm_semantic_economics import RichSemanticOutput, SemanticProposal, SourceDocument, build_evidence_bundle, score_human_gold, DEVELOPMENT_GOLD_PROVENANCE
from charitygraph.program_subject_normalisation import *
from charitygraph.reality_slice1 import development_members

def _p(pid, label, kind="program"):
    return SemanticProposal(proposal_id=pid, label=label, kind=kind, durable=None, parent_proposal_id=None, description=None, evidence_refs=("evidence:"+"a"*64,), aliases=(), confidence="medium", competing_interpretation=None, model_review_recommendation=None)
def _ctx(n=1):
    m=development_members()[0]; d=SourceDocument(url="https://example.test", retrieved_at=datetime(2026,8,27,tzinfo=timezone.utc), publisher=m.legal_current_name, content_hash="a"*64, artifact_id="srcblob:"+"a"*64, media_type="text/html", byte_size=8, text="evidence"); b=build_evidence_bundle(m.subject_id,"lean",(d,)); a=RichSemanticOutput(programs=tuple(_p(f"p{i}",f"P{i}") for i in range(n)),services=(),projects=(),campaigns=(),organisational_units=(),activities=(),populations=(),geographies=(),sdg_alignments=(),assertions=(),classie_assignments=(),semantic_outcome="supported",blockers=()); return m,b,a
def _d(ids, cls="semantic_domain_or_activity_category", label=None, candidate=None):
    if cls in {"durable_program", "durable_service"} and candidate is None and label is not None:
        candidate, label = label, "Label"
    return ProgramSubjectNormalisationDecision(stage_a_proposal_ids=tuple(ids),resolved_candidate_id=candidate,canonical_candidate_label="Label" if candidate else None,resolution_class=cls,durable=True if cls in {"durable_program","durable_service"} else False,parent_resolved_candidate_id=None,evidence_refs=("evidence:"+"a"*64,),rationale="bounded evidence",confidence="high",competing_interpretation="alternative",model_review_recommendation="required")
def test_stage_b_category_project_and_complete_lineage():
    m,b,a=_ctx(2); i=build_normalisation_input(m.subject_id,m.legal_current_name,b,a); o=ProgramSubjectNormalisationOutput(resolutions=(_d(("p0",),"semantic_domain_or_activity_category"),_d(("p1",),"project")),semantic_outcome="resolved"); validate_stage_b_output(o,i); assert not project_normalised_subjects(a,o)
    merged=ProgramSubjectNormalisationOutput(resolutions=(_d(("p0","p1"),"durable_program","family:1"),),semantic_outcome="resolved"); p=project_normalised_subjects(a,merged)[0]; assert {x.stage_a_proposal_id for x in p.lineage}=={"p0","p1"}
def test_stage_b_rejects_unknown_or_missing_candidates():
    m,b,a=_ctx(2); i=build_normalisation_input(m.subject_id,m.legal_current_name,b,a)
    with pytest.raises(ValueError): validate_stage_b_output(ProgramSubjectNormalisationOutput(resolutions=(_d(("unknown",)),),semantic_outcome="x"),i)
    with pytest.raises(ValueError,match="exactly once"): validate_stage_b_output(ProgramSubjectNormalisationOutput(resolutions=(_d(("p0",)),),semantic_outcome="x"),i)
def test_stage_b_task_contains_no_gold_and_is_typed():
    m,b,a=_ctx(); i=build_normalisation_input(m.subject_id,m.legal_current_name,b,a); t=build_normalisation_task(i,b,provider_id="fake",model_snapshot="fake"); prompt=normalisation_prompt(i,b); assert t.task_type=="program_subject_normalisation"; assert "do not include or infer any human gold" in prompt.lower(); assert "REQUIRED" not in prompt
def test_stage_b_case_rejects_charity_mismatch():
    m,b,a=_ctx(); i=build_normalisation_input(m.subject_id,m.legal_current_name,b,a); o=ProgramSubjectNormalisationOutput(resolutions=(_d(("p0",)),),semantic_outcome="x")
    with pytest.raises(ValueError): ProgramSubjectNormalisationCase(charity_name="Other",stage_a=i,stage_b=o)


def test_resolved_family_scorer_uses_review_classes_not_raw_ids():
    m,b,a=_ctx(3); i=build_normalisation_input(m.subject_id,"The Smith Family",b,a)
    o=ProgramSubjectNormalisationOutput(resolutions=(_d(("p0",),"durable_program","family:r"),_d(("p1",),"project"),_d(("p2",),"semantic_domain_or_activity_category")),semantic_outcome="resolved")
    # unknown durable family blocks precision; project/category are not false programs
    score=score_human_gold([],stage_b_cases=[{"charity_name":"The Smith Family","stage_a":i,"stage_b":o}])
    assert score["status"]=="blocked_review_required" and score["precision"] is None
    assert score["false_program_creation_count"]==0

def test_resolved_required_acceptable_and_exclude_metrics_are_separate():
    m,b,a=_ctx(3); i=build_normalisation_input(m.subject_id,"The Smith Family",b,a)
    # map real governed IDs through Stage-A IDs for deterministic scorer testing
    a2=RichSemanticOutput(programs=(
        _p("learning-clubs","Learning Clubs"), _p("program:lets-read","Let's Read"), _p("literacy-programs","Literacy")),services=(),projects=(),campaigns=(),organisational_units=(),activities=(),populations=(),geographies=(),sdg_alignments=(),assertions=(),classie_assignments=(),semantic_outcome="supported",blockers=())
    i=build_normalisation_input(m.subject_id,"The Smith Family",b,a2)
    o=ProgramSubjectNormalisationOutput(resolutions=(_d(("learning-clubs",),"durable_program","Learning Clubs","family:clubs"),_d(("program:lets-read",),"durable_program","Let's Read","family:read"),_d(("literacy-programs",),"durable_program","Literacy","family:lit")),semantic_outcome="resolved")
    score=score_human_gold([],stage_b_cases=[{"charity_name":"The Smith Family","stage_a":i,"stage_b":o}])
    assert score["required_found"]==2 and score["false_program_creation_count"]==1 and score["zero_critical_scope_errors"] is False

def test_cross_tier_recurrence_not_overfragmentation_but_within_case_is():
    m,b,a=_ctx(); i=build_normalisation_input(m.subject_id,"The Smith Family",b,a); o=ProgramSubjectNormalisationOutput(resolutions=(_d(("p0",),"durable_program","Same","family:same"),),semantic_outcome="resolved")
    score=score_human_gold([],stage_b_cases=[{"charity_name":"The Smith Family","stage_a":i,"stage_b":o},{"charity_name":"The Smith Family","stage_a":i,"stage_b":o}]); assert score["duplicate_overfragmentation"]["numerator"]==0
    i2=build_normalisation_input(m.subject_id,"The Smith Family",b,RichSemanticOutput(programs=(_p("p0","One"),_p("p1","Two")),services=(),projects=(),campaigns=(),organisational_units=(),activities=(),populations=(),geographies=(),sdg_alignments=(),assertions=(),classie_assignments=(),semantic_outcome="supported",blockers=()))
    o2=ProgramSubjectNormalisationOutput(resolutions=(_d(("p0",),"durable_program","Same","family:same"),_d(("p1",),"durable_program","Same","family:same")),semantic_outcome="resolved")
    score2=score_human_gold([],stage_b_cases=[{"charity_name":"The Smith Family","stage_a":i2,"stage_b":o2}]); assert score2["duplicate_overfragmentation"]["numerator"]==1

def test_stage_a_precision_is_blocked_until_stage_b_and_gold_is_post_run():
    assert score_human_gold([])["status"]=="stage_b_required"
    assert DEVELOPMENT_GOLD_PROVENANCE=="post-run human development calibration gold"


def test_acceptable_is_precision_positive_and_unresolved_is_excluded():
    m,b,a=_ctx(); a=RichSemanticOutput(programs=(_p("service_migration_support","Migration Support"),_p("program_telecross","Telecross")),services=(),projects=(),campaigns=(),organisational_units=(),activities=(),populations=(),geographies=(),sdg_alignments=(),assertions=(),classie_assignments=(),semantic_outcome="supported",blockers=())
    i=build_normalisation_input(m.subject_id,"Australian Red Cross Society",b,a)
    o=ProgramSubjectNormalisationOutput(resolutions=(_d(("service_migration_support",),"durable_service","Migration","family:migration"),_d(("program_telecross",),"durable_program","Telecross","family:telecross")),semantic_outcome="resolved")
    score=score_human_gold([],stage_b_cases=[{"charity_name":"Australian Red Cross Society","stage_a":i,"stage_b":o}])
    assert score["acceptable_positive_count"]==1 and score["unresolved_excluded_count"]==1 and score["precision"]==1.0
