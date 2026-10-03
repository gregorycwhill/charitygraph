"""Provider-free, source-lineaged compatibility replays; unknown cases never default."""
from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path
import pytest
from charitygraph.contracts.common import ArtifactRef, ProducerRef, SchemaRef
from charitygraph.contracts.ids import deterministic_id
from charitygraph.contracts.knowledge import Observation, ObservationTime, SubjectRecord
from charitygraph.integrated_card import CardEvidence, IntegratedGraph, NORTH_STAR_PROJECTION_V0_1, project_subject
from charitygraph.projection_compatibility import Disposition, EvaluationGrain, evaluate_compatibility
RUNTIME=Path("C:/CharityGraph-runtime"); P6=RUNTIME/"cg-projection-factory-saturation-253-terra-p6-projection-gate-synthesis-a1"/"CHECKPOINT.md"; SEQUENCE=RUNTIME/"reality-sequence-17-terra-saturation-campaign"/"checkpoints"; NOW=datetime(2026,10,3,tzinfo=timezone.utc); SCHEMA=SchemaRef(schema_id="urn:charitygraph:builder:schema:archive-replay:1.0",schema_version="1.0")
def _sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def _graph(case_id, name="Archived replay subject"):
 s=deterministic_id("subject:",{"case":case_id,"name":name}); src=deterministic_id("srcrec:",{"case":case_id}); o=Observation(record_id=deterministic_id("observation:",{"case":case_id}),subject_id=s,predicate="archive.replay.metadata",value={"case_id":case_id},outcome_state="supported",observation_time=ObservationTime(observed_at=NOW),method="structural_archive_adapter",lifecycle_status="held",created_at=NOW,producer=ProducerRef(kind="code",producer_id="archive-replay",version="1")); sub=SubjectRecord(record_id=deterministic_id("subjectrecord:",{"id":s}),subject_id=s,subject_kind="organisation",lifecycle_status="active",display_name=name,identity_authority_refs=(ArtifactRef(artifact_id=src,content_hash="a"*64,schema=SCHEMA),),identity_policy_id="archive-replay.v2",created_at=NOW,producer=ProducerRef(kind="code",producer_id="archive-replay",version="1")); return IntegratedGraph(subjects=(sub,),scopes=(),observations=(o,),evidence=(CardEvidence(observation_id=o.record_id,disposition="REUSABLE_GOVERNED",section_ids=(20,)),)),s,o.record_id
def _inputs(case, source):
 try: intent,family,role,currentness,scope,coverage=case["i"]
 except (KeyError,ValueError) as e: raise ValueError(f"unrecognised or incomplete archive case {case.get('id')!r}") from e
 x={"answer_intent":intent,"claim_family":family,"authority_source_role":role,"currentness":currentness,"scope":scope,"coverage":coverage,"governed_input_refs":(source,f"campaign-253:P6:{case['id']}")}
 if case.get("b"): x["typed_bindings"]=( {"family":case["b"][0],"governed_ref":f"campaign-253:{case['id']}","components":case["b"][1:]}, )
 if case.get("parties"): x["claimant_ref"],x["host_ref"]=case["parties"]
 if case.get("composition"): x["composition"]=case["composition"]
 return x
def _replay(case, source, name="Archived replay subject"):
 grain=EvaluationGrain(case.get("grain","section_card")); inputs=_inputs(case,source); audit=evaluate_compatibility(inputs,grain=grain); expected=tuple(case.get("r",()))
 assert audit.reason_codes == expected
 assert audit.grain is grain
 if expected: assert audit.disposition is Disposition.ABSTAIN
 else:
  assert audit.disposition is Disposition.ALLOW_WITH_QUALIFICATION
  assert tuple(q.code for q in audit.required_qualifiers)==tuple(case.get("q",("CURRENTNESS_LIMIT",)))
 g,s,oid=_graph(case["id"],name)
 if expected:
  with pytest.raises(ValueError,match="projection compatibility gate abstained") as exc: project_subject(g,s,projection_contract=NORTH_STAR_PROJECTION_V0_1,compatibility_inputs=inputs)
  assert str(exc.value).split(": ",1)[1].split(",")==list(expected)
 else:
  result=project_subject(g,s,projection_contract=NORTH_STAR_PROJECTION_V0_1,compatibility_inputs=inputs); assert result["compatibility_audit"]==audit.model_dump(mode="json"); assert oid in result["observation_ids"]
def test_p6_exact_source_backed_matrix():
 f=json.loads((Path(__file__).parents[1]/"fixtures"/"campaign253_p6_cases.json").read_text()); assert _sha(P6).upper()==f["source_checkpoint_sha256"]; assert len(f["cases"])==30
 for case in f["cases"]: _replay(case,str(P6))
def test_unknown_replay_case_cannot_fall_back_to_generic_defaults():
 with pytest.raises(ValueError,match="unrecognised or incomplete"): _inputs({"id":"not-a-case"},str(P6))
def test_partial_binding_fails_and_complete_binding_passes():
 base={"answer_intent":"evaluation_summary","claim_family":"evaluation","authority_source_role":"claimant","currentness":"current","scope":"bounded","coverage":"complete","governed_input_refs":("obs",)}
 assert evaluate_compatibility({**base,"typed_bindings":({"family":"evaluation","governed_ref":"x","components":["population"]},)}).reason_codes==("MISSING_TYPED_BINDING",)
 assert evaluate_compatibility({**base,"typed_bindings":({"family":"evaluation","governed_ref":"x","components":["population","comparator","horizon"]},)}).disposition is Disposition.ALLOW
@pytest.mark.parametrize("item,case",[("CG-PROJECTION-FACTORY-SATURATION-253-TERRA--f2-coldstart-local--a1",{"id":"cold-f2","i":["service_information","service_capacity","claimant","stale","bounded","complete"],"b":["service_capacity","access_context"]}),("CG-PROJECTION-FACTORY-SATURATION-253-TERRA--f3-coldstart-complex-service--a1",{"id":"cold-f3","i":["service_information","service_capacity","regulator","stale","bounded","not_available_from_source"],"b":["service_capacity","capacity_context"],"q":["CURRENTNESS_LIMIT","COVERAGE_LIMIT"]}),("CG-PROJECTION-FACTORY-SATURATION-253-TERRA--f4-coldstart-international--a1",{"id":"cold-f4","i":["programme_context","programme","claimant","stale","bounded","complete"]})])
def test_cold_start_distinct_cases(item,case):
 manifest=json.loads((Path(__file__).parents[1]/"fixtures"/"campaign253_replay_manifest.json").read_text()); record=next(x for x in manifest["cold_start"] if x["checkpoint_id"]==item); p=Path(record["checkpoint"]); assert _sha(p)==record["checkpoint_sha256"]; _replay(case,str(p),record["subject"])
@pytest.mark.parametrize("n,case",[("029",{"id":"c29","i":["factual_summary","programme","regulator","stale","bounded","not_available_from_source"],"q":["CURRENTNESS_LIMIT","COVERAGE_LIMIT"]}),("030",{"id":"c30","i":["factual_summary","programme","claimant","stale","bounded","complete"]}),("031",{"id":"c31","i":["evaluation_summary","evaluation","claimant","stale","bounded","complete"],"b":["evaluation","population","comparator","horizon"]}),("033",{"id":"c33","i":["regulatory_history","regulatory","claimant","stale","bounded","complete"]}),("034",{"id":"c34","i":["historical_notice","tax_guidance","regulator","stale","bounded","complete"]}),("035",{"id":"c35","i":["historical_notice","resource_flow","claimant","stale","bounded","complete"],"b":["resource_flow","pool","programme"]})])
def test_sequence17_distinct_cases(n,case):
 p=SEQUENCE/f"{n}.json"; assert json.loads(p.read_text())["experiment_id"]==int(n); _replay(case,str(p))
