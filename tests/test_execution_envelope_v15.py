import copy
import pytest
from charitygraph.execution_envelope_v15 import ExecutionEnvelopeError, build_envelope

def template():
 return {"template_id":"SYN","final_template_identity":"SYN@v1","question":"Q {subject}","operation":"Return dated historical events or metric changes with succession and scope preserved.","scope":"s","time":"t","user_parameter_slots":None,"approved_fixture_bindings":{},"discoverable_answer_variables":["event"],"evidence":{"expected_roles":["r"],"obligation":"o"},"permitted_states":["SUPPORTED","PARTIAL","MISSING","CONFLICTED","ABSTAIN"],"template_specific_forbidden_inference":"no","successor_forbidden_inferences":[],"v1_4_compatibility":"CONTRACT_FIT_GAP","provenance":"synthetic"}
def instance():
 return {"bound_question_identity":"QI","final_template_identity":"SYN@v1","requested_operation":{"operation":template()["operation"]},"bound_user_choice_parameters":[],"governed_subject":{"governed_subject_id":"subject:synthetic","external_authority_identifiers":[]},"question_text":"Q subject:synthetic","referent_and_scope":"s","temporal_constraints":"t","evidence_obligations":["r"],"valid_partial_answer_behaviour":"p","contract_fit_status":"CONTRACT_FIT_GAP","diagnostic_classification":None}
def test_envelope_is_lossless_and_subject_opaque():
 e=build_envelope(instance(),template()); assert e["outcome"]=="LOSSLESSLY_ENVELOPED"; assert e["template_contract"]["permitted_states"][0]=="SUPPORTED"; assert e["subject"]["governed_subject_id"]=="subject:synthetic"
def test_mismatch_fails_closed():
 x=instance(); x["requested_operation"]={"operation":"other"}
 with pytest.raises(ExecutionEnvelopeError): build_envelope(x,template())

def test_approved_version_serialization_alias_requires_frozen_lineage():
 t=template(); t["final_template_identity"]="QFT-D05B-v2"; t["template_id"]="QFT-D05B"
 x=instance(); x["final_template_identity"]="QFT-D05B@v2"; x["bound_user_choice_parameters"]=[]
 # A no-parameter template cannot establish the required frozen successor
 # lineage, and therefore remains fail-closed.
 with pytest.raises(ExecutionEnvelopeError): build_envelope(x,t)

def test_approved_version_serialization_alias_joins_only_with_exact_successor_record():
 t=template(); t["final_template_identity"]="QFT-D05B-v2"; t["template_id"]="QFT-D05B"; t["user_parameter_slots"]="metric_or_event"; t["approved_fixture_bindings"]={"slot_id":"metric_or_event","exact_value":"defined metric"}
 x=instance(); x["final_template_identity"]="QFT-D05B@v2"; x["bound_user_choice_parameters"]=[{"slot_id":"metric_or_event","exact_value":"defined metric","source_record":"QFT-D05B-v2"}]
 assert build_envelope(x,t)["compatibility_decisions"] == [{"type":"VERSION_SERIALIZATION_ALIAS"}]

def test_article_alias_preserves_frozen_question_text_and_canonicalises_only_approved_slot():
 t=template(); t["template_id"]="QFT-D08B"; t["final_template_identity"]="QFT-D08B@v1"
 t["user_parameter_slots"]=["channel"]
 t["approved_fixture_bindings"]={"slot_id":"channel","exact_value":"online donation page"}
 x=instance(); x["final_template_identity"]="QFT-D08B@v1"; x["question_text"]="Does the charity have an online donation page?"
 x["bound_user_choice_parameters"]=[{"slot_id":"channel","exact_value":"an online donation page","source_record":"QFT-D08B-v1"}]
 e=build_envelope(x,t)
 assert e["question_text"] == "Does the charity have an online donation page?"
 assert e["semantic_user_parameters"] == {"channel":"online donation page"}
 assert e["frozen_user_parameters"][0]["exact_value"] == "an online donation page"
