import json
from pathlib import Path
from charitygraph.ethos_notability_extraction import FrozenEthosNotabilityPacket, ProviderResponse, run_ethos_extraction, run_extraction, validate_bundle
from charitygraph.retained_capture import RetainedCaptureUniverse

PACKET=FrozenEthosNotabilityPacket(packet_id="p1",packet_hash="packet-hash",subject_id="subject:one",permitted_scope_ids=("scope:one",),evidence=({"evidence_id":"e1","source_record_id":"s1","lineage_id":"l1","text":"We state a commitment.","source_role":"supporting"},))
class Fake:
 def __init__(self, value): self.value=value
 def extract(self, **_): return ProviderResponse(json.dumps(self.value),"fake","fake-model",1,2,3,"0",1)
def ethos(**overrides):
 d={"subject_id":"subject:one","scope_id":"scope:one","epistemic_role":"self_described","descriptor":"a stated commitment","source_role":"supporting","evidence_ids":["e1"]}; d.update(overrides); return {"outcome":"candidates","ethos_candidates":[d],"history_candidates":[]}
def test_provider_free_e2e_is_candidate_review_only(tmp_path):
 out=run_extraction(PACKET,Fake(ethos()),ledger_path=tmp_path/'ledger.json')
 assert out['validation']['accepted'] and out['handoff']['state']=='REVIEW_REQUIRED'
 assert 'Observation' not in str(out) and (tmp_path/'ledger.json').exists()
def test_abstain_and_invented_evidence_fail_closed():
 assert validate_bundle(PACKET,{"outcome":"abstain","ethos_candidates":[],"history_candidates":[]}).accepted
 assert not validate_bundle(PACKET,ethos(evidence_ids=['invented'])).accepted
def test_nontransfer_and_scope_subject_adversaries_fail_closed():
 for change in ({"subject_id":"parent:two"},{"scope_id":"scope:beneficiary"},{"evidence_ids":["e1","network-evidence"]}):
  assert not validate_bundle(PACKET,ethos(**change)).accepted
def test_history_boundaries_and_duplicate_identity():
 d={"outcome":"candidates","ethos_candidates":[],"history_candidates":[{"subject_id":"subject:one","scope_id":"scope:one","event_family":"public_inquiry_or_review","statement":"review announced","evidence_ids":["e1"],"source_roles":["supporting"]}]}
 assert not validate_bundle(PACKET,d).accepted
 d['history_candidates'][0]['procedural_status']='announced'; assert validate_bundle(PACKET,d).accepted
def test_temporal_and_predecessor_boundaries_fail_closed():
 d=ethos(currentness='current')
 assert validate_bundle(PACKET,d).accepted # currentness is recorded, never inferred by validator
 h={"outcome":"candidates","ethos_candidates":[],"history_candidates":[{"subject_id":"subject:one","scope_id":"scope:one","event_family":"succession","statement":"successor named","evidence_ids":["e1"],"source_roles":["supporting"],"related_subject_id":"subject:old","relationship_kind":"predecessor"}]}
 assert validate_bundle(PACKET,h).accepted
 h['history_candidates'][0]['event_date']='not-a-date'; assert not validate_bundle(PACKET,h).accepted
def test_malformed_and_unresolved_are_explicit():
 assert not validate_bundle(PACKET,'not json').accepted
 assert validate_bundle(PACKET,{"outcome":"unresolved","ethos_candidates":[],"history_candidates":[],"reason":"source is silent"}).accepted

def test_empty_retained_universe_abstains_as_section_15_coverage_gap_without_provider(tmp_path):
 class ExplodingProvider:
  def extract(self, **_): raise AssertionError("provider must not be called for a coverage gap")
 out=run_ethos_extraction(RetainedCaptureUniverse(subject_id="subject:one", permitted_scope_ids=("scope:one",)), ExplodingProvider(), ledger_path=tmp_path/'gap.json')
 assert out["abstention"] == {"section_id": 15, "state": "COVERAGE_GAP", "reason": "no_retained_relevant_source"}
 assert out["handoff"]["state"] == "ABSTAINED"
 assert out["handoff"]["coverage_gap"] == "no_retained_relevant_source"
