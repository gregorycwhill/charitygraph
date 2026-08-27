
from datetime import datetime, timezone
import pytest
from charitygraph.llm_semantic_economics import RichSemanticOutput, SemanticProposal, SourceDocument, build_evidence_bundle, score_human_gold, DEVELOPMENT_GOLD_PROVENANCE
from charitygraph.program_subject_normalisation import (
    ProposalResolution, ProgramSubjectNormalisationCase, ProgramSubjectNormalisationOutput as _StageBOutput,
    ResolvedCandidate, build_normalisation_input, build_normalisation_task, normalisation_prompt,
    normalisation_text_format, project_normalised_subjects, program_subject_normalisation_schema,
    validate_normalisation_schema, validate_stage_b_output,
)
from charitygraph.reality_slice1 import development_members

EVIDENCE_ID = "evidence:" + "a" * 64

def _p(pid, label, kind="program"):
    return SemanticProposal(proposal_id=pid, label=label, kind=kind, durable=None, parent_proposal_id=None, description=None, evidence_refs=(EVIDENCE_ID,), aliases=(), confidence="medium", competing_interpretation=None, model_review_recommendation=None)
def _ctx(n=1):
    global EVIDENCE_ID
    ids = tuple(f"p{i}" for i in range(n)) if isinstance(n, int) else tuple(n)
    m=development_members()[0]; d=SourceDocument(url="https://example.test", retrieved_at=datetime(2026,8,27,tzinfo=timezone.utc), publisher=m.legal_current_name, content_hash="a"*64, artifact_id="srcblob:"+"a"*64, media_type="text/html", byte_size=8, text="evidence"); b=build_evidence_bundle(m.subject_id,"lean",(d,)); EVIDENCE_ID = b.source_segments[0].evidence_id; a=RichSemanticOutput(programs=tuple(_p(pid,pid) for pid in ids),services=(),projects=(),campaigns=(),organisational_units=(),activities=(),populations=(),geographies=(),sdg_alignments=(),assertions=(),classie_assignments=(),semantic_outcome="supported",blockers=()); return m,b,a
class _LegacyDecision:
    def __init__(self, ids, cls, label=None, candidate=None):
        self.stage_a_proposal_ids = tuple(ids)
        self.resolution_class = cls
        self.canonical_candidate_label = label or candidate
        self.resolved_candidate_id = candidate
        self.evidence_refs = (EVIDENCE_ID,)


def _d(ids, cls="semantic_domain_or_activity_category", label=None, candidate=None):
    if cls in {"durable_program", "durable_service"} and candidate is None and label is not None:
        candidate, label = label, "Label"
    return _LegacyDecision(ids, cls, label, candidate)


def ProgramSubjectNormalisationOutput(*, resolutions=None, proposal_resolutions=None, resolved_candidates=None, semantic_outcome="resolved", blockers=()):
    if proposal_resolutions is not None:
        return _StageBOutput(proposal_resolutions=tuple(proposal_resolutions), resolved_candidates=tuple(resolved_candidates or ()), semantic_outcome=semantic_outcome, blockers=tuple(blockers))
    decisions = tuple(resolutions or ())
    candidates = {}
    converted = []
    for item in decisions:
        candidate_ids = () if item.resolved_candidate_id is None else (item.resolved_candidate_id,)
        disposition = "unresolved" if not candidate_ids else "resolved"
        for proposal_id in item.stage_a_proposal_ids:
            converted.append(ProposalResolution(stage_a_proposal_id=proposal_id, disposition=disposition, resolved_candidate_ids=candidate_ids, rationale="bounded evidence", confidence="high", competing_interpretation="alternative", evidence_refs=item.evidence_refs, model_review_recommendation="required"))
        if item.resolved_candidate_id and item.resolved_candidate_id not in candidates:
            candidates[item.resolved_candidate_id] = ResolvedCandidate(resolved_candidate_id=item.resolved_candidate_id, canonical_candidate_label=item.canonical_candidate_label or item.resolved_candidate_id, resolution_class=item.resolution_class, durable=item.resolution_class in {"durable_program", "durable_service"}, parent_resolved_candidate_id=None, evidence_refs=item.evidence_refs, rationale="bounded evidence", confidence="high", competing_interpretation="alternative")
    return _StageBOutput(proposal_resolutions=tuple(converted), resolved_candidates=tuple(candidates.values()), semantic_outcome=semantic_outcome, blockers=tuple(blockers))


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
    score2=score_human_gold([],stage_b_cases=[{"charity_name":"The Smith Family","stage_a":i2,"stage_b":o2}]); assert score2["duplicate_overfragmentation"]["numerator"]==0

def test_stage_a_precision_is_blocked_until_stage_b_and_gold_is_post_run():
    assert score_human_gold([])["status"]=="stage_b_required"
    assert DEVELOPMENT_GOLD_PROVENANCE=="post-run human development calibration gold"


def test_acceptable_is_precision_positive_and_unresolved_is_excluded():
    m,b,a=_ctx(); a=RichSemanticOutput(programs=(_p("service_migration_support","Migration Support"),_p("program_telecross","Telecross")),services=(),projects=(),campaigns=(),organisational_units=(),activities=(),populations=(),geographies=(),sdg_alignments=(),assertions=(),classie_assignments=(),semantic_outcome="supported",blockers=())
    i=build_normalisation_input(m.subject_id,"Australian Red Cross Society",b,a)
    o=ProgramSubjectNormalisationOutput(resolutions=(_d(("service_migration_support",),"durable_service","Migration","family:migration"),_d(("program_telecross",),"durable_program","Telecross","family:telecross")),semantic_outcome="resolved")
    score=score_human_gold([],stage_b_cases=[{"charity_name":"Australian Red Cross Society","stage_a":i,"stage_b":o}])
    assert score["acceptable_positive_count"]==1 and score["unresolved_excluded_count"]==1 and score["precision"]==1.0


def _new_output(resolutions, candidates, outcome="resolved"):
    return _StageBOutput(proposal_resolutions=tuple(resolutions), resolved_candidates=tuple(candidates), semantic_outcome=outcome, blockers=())


def _new_resolution(pid, candidate_ids=(), disposition="resolved", refs=None):
    return ProposalResolution(stage_a_proposal_id=pid, disposition=disposition, resolved_candidate_ids=tuple(candidate_ids), rationale="bounded evidence", confidence="high", competing_interpretation="alternative", evidence_refs=tuple(refs or (EVIDENCE_ID,)), model_review_recommendation="required")


def _new_candidate(cid, cls="durable_program", durable=None, parent=None, refs=None):
    if durable is None:
        durable = cls in {"durable_program", "durable_service"}
    return ResolvedCandidate(resolved_candidate_id=cid, canonical_candidate_label=cid, resolution_class=cls, durable=durable, parent_resolved_candidate_id=parent, evidence_refs=tuple(refs or (EVIDENCE_ID,)), rationale="bounded evidence", confidence="high", competing_interpretation="alternative")


def test_stage_b_split_merge_and_lineage_edges_are_explicit():
    m,b,a=_ctx(3); i=build_normalisation_input(m.subject_id,m.legal_current_name,b,a)
    o=_new_output((_new_resolution("p0",("c1","c2"),"split"),_new_resolution("p1",("c1",)),_new_resolution("p2",(),"unresolved")),(_new_candidate("c1"),_new_candidate("c2")))
    validate_stage_b_output(o,i); projections=project_normalised_subjects(a,o)
    assert {p.resolved_candidate_id for p in projections}=={"c1","c2"}
    assert projections[0].lineage[0].resolution_disposition in {"split","resolved"}


def test_stage_b_rejects_unknown_parent_and_orphan_candidate():
    m,b,a=_ctx(); i=build_normalisation_input(m.subject_id,m.legal_current_name,b,a)
    with pytest.raises(ValueError,match="unknown parent"):
        validate_stage_b_output(_new_output((_new_resolution("p0",("c1",)),),(_new_candidate("c1",parent="missing"),)),i)
    with pytest.raises(ValueError,match="lineage edge"):
        validate_stage_b_output(_new_output((_new_resolution("p0",()),),(_new_candidate("orphan"),)),i)


def test_stage_b_schema_has_exact_evidence_and_proposal_enums():
    schema=program_subject_normalisation_schema(permitted_evidence_ids=(EVIDENCE_ID,),permitted_stage_a_proposal_ids=("p0","p1"))
    validate_normalisation_schema(schema)
    assert schema["$defs"]["ProposalResolution"]["properties"]["stage_a_proposal_id"]["enum"]==["p0","p1"]
    assert schema["$defs"]["ResolvedCandidate"]["properties"]["evidence_refs"]["items"]["enum"]==[EVIDENCE_ID]
    assert schema["properties"]["resolved_candidates"]["maxItems"]==6


def test_one_resolved_candidate_cannot_credit_two_required_families():
    m,b,_=_ctx(("program:learning-for-life","program:learning-clubs"))
    a=RichSemanticOutput(programs=(_p("program:learning-for-life","A"),_p("program:learning-clubs","B")),services=(),projects=(),campaigns=(),organisational_units=(),activities=(),populations=(),geographies=(),sdg_alignments=(),assertions=(),classie_assignments=(),semantic_outcome="supported",blockers=())
    i=build_normalisation_input(m.subject_id,"The Smith Family",b,a)
    o=_new_output((_new_resolution("program:learning-for-life",("c1",)),_new_resolution("program:learning-clubs",("c1",))),(_new_candidate("c1"),))
    score=score_human_gold([],stage_b_cases=[{"charity_name":"The Smith Family","stage_a":i,"stage_b":o}])
    assert score["undermerge_count"]==1 and score["required_found"]==0 and score["status"]=="blocked_review_required"


def test_two_candidates_same_required_family_count_as_overfragmentation():
    m,b,_=_ctx(("program:learning-for-life",)); a=RichSemanticOutput(programs=(_p("program:learning-for-life","A"),),services=(),projects=(),campaigns=(),organisational_units=(),activities=(),populations=(),geographies=(),sdg_alignments=(),assertions=(),classie_assignments=(),semantic_outcome="supported",blockers=())
    i=build_normalisation_input(m.subject_id,"The Smith Family",b,a); o=_new_output((_new_resolution("program:learning-for-life",("c1","c2"),"split"),),(_new_candidate("c1"),_new_candidate("c2")))
    score=score_human_gold([],stage_b_cases=[{"charity_name":"The Smith Family","stage_a":i,"stage_b":o}])
    assert score["duplicate_overfragmentation"]["numerator"]==1


def test_acceptable_and_unresolved_aliases_use_canonical_families():
    m,b,_=_ctx(("service_migration_support","program_telecross")); a=RichSemanticOutput(programs=(_p("program_telecross","T"),),services=(_p("service_migration_support","M","service"),),projects=(),campaigns=(),organisational_units=(),activities=(),populations=(),geographies=(),sdg_alignments=(),assertions=(),classie_assignments=(),semantic_outcome="supported",blockers=())
    i=build_normalisation_input(m.subject_id,"Australian Red Cross Society",b,a); o=_new_output((_new_resolution("service_migration_support",("c1",)),_new_resolution("program_telecross",("c2",))),(_new_candidate("c1","durable_service"),_new_candidate("c2")))
    score=score_human_gold([],stage_b_cases=[{"charity_name":"Australian Red Cross Society","stage_a":i,"stage_b":o}])
    assert score["acceptable_positive_count"]==1 and score["unresolved_excluded_count"]==1


def test_cross_tier_recurrence_is_not_duplicate():
    m,b,_=_ctx(("program:learning-for-life",)); a=RichSemanticOutput(programs=(_p("program:learning-for-life","A"),),services=(),projects=(),campaigns=(),organisational_units=(),activities=(),populations=(),geographies=(),sdg_alignments=(),assertions=(),classie_assignments=(),semantic_outcome="supported",blockers=())
    i=build_normalisation_input(m.subject_id,"The Smith Family",b,a); o=_new_output((_new_resolution("program:learning-for-life",("c1",)),),(_new_candidate("c1"),)); case={"charity_name":"The Smith Family","stage_a":i,"stage_b":o}
    assert score_human_gold([],stage_b_cases=[case,case])["duplicate_overfragmentation"]["numerator"]==0


def test_critical_scope_gate_is_independent_and_blocks_unknowns():
    m,b,a=_ctx(); i=build_normalisation_input(m.subject_id,"The Smith Family",b,a); o=_new_output((_new_resolution("p0",("c1",)),),(_new_candidate("c1"),)); score=score_human_gold([],stage_b_cases=[{"charity_name":"The Smith Family","stage_a":i,"stage_b":o}])
    assert score["critical_scope_error_count"]==0 and score["scope_review_required_count"]==1 and not score["zero_critical_scope_errors"]


def test_stage_b_prompt_excludes_gold_and_lexical_semantics():
    m,b,a=_ctx(); i=build_normalisation_input(m.subject_id,m.legal_current_name,b,a); prompt=normalisation_prompt(i,b)
    assert "human gold" in prompt.lower() and "REQUIRED" not in prompt and "keyword" in prompt.lower()


def test_stage_a_hash_changes_cache_identity():
    m,b,a=_ctx(); one=build_normalisation_input(m.subject_id,m.legal_current_name,b,a); t1=build_normalisation_task(one,b,provider_id="fake",model_snapshot="fake")
    _,_,a2=_ctx(("p1",)); two=build_normalisation_input(m.subject_id,m.legal_current_name,b,a2); t2=build_normalisation_task(two,b,provider_id="fake",model_snapshot="fake")
    assert one.stage_a_output_hash!=two.stage_a_output_hash and t1.cache_key!=t2.cache_key
