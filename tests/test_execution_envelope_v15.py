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
