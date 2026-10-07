"""Bounded internal evaluation contracts, not a public correction API."""
from dataclasses import dataclass
from enum import Enum
class CorrectionClass(str,Enum):
 AMENDED_EVIDENCE="amended_evidence"; SOURCE_VERSION_CHANGE="source_version_change"; EXTRACTION_REPRESENTATION_ERROR="extraction_representation_error"; SEMANTIC_MAPPING_ERROR="semantic_mapping_error"; IDENTITY_BINDING_ERROR="identity_binding_error"; SCOPE_BINDING_ERROR="scope_binding_error"; TEMPORAL_CURRENTNESS_ERROR="temporal_currentness_error"; CLASSIFICATION_ERROR="classification_error"; COVERAGE_ACQUISITION_ERROR="coverage_acquisition_error"; UNSUPPORTED_INFERENCE="unsupported_inference"; GOVERNANCE_ADJUDICATION="governance_adjudication"; PROJECTION_RENDERING_ERROR="projection_rendering_error"
class CorrectionLocus(str,Enum):
 SOURCE_ACQUISITION="source_acquisition"; SOURCE_VERSION="source_version"; REPRESENTATION="representation"; EVIDENCE_EXTRACTION="evidence_extraction"; IDENTITY_BINDING="identity_binding"; SCOPE_BINDING="scope_binding"; SEMANTIC_MAPPING="semantic_mapping"; CLASSIFICATION="classification"; GOVERNANCE_ADJUDICATION="governance_adjudication"; CANONICAL_OBSERVATION="canonical_observation"; COVERAGE="coverage"; PROJECTION="projection"
@dataclass(frozen=True)
class CorrectionChallengeScenario:
 id:str; correction_class:CorrectionClass; loci:tuple[CorrectionLocus,...]; disposition:str; creates_authority:bool=False
 def validate(self):
  if self.creates_authority: raise ValueError("evaluation scenario cannot create authority")
  if not self.loci: raise ValueError("correction locus required")
@dataclass(frozen=True)
class CorrectionTriageResult:
 scenario_id:str; accepted:bool; correction_class:CorrectionClass; loci:tuple[CorrectionLocus,...]; governance_required:bool=True
 def compare_expected(self,expected):
  expected.validate(); return self.scenario_id==expected.id and self.correction_class==expected.correction_class and self.loci==expected.loci

@dataclass(frozen=True)
class GovernedObservation:
 """Tiny evaluation projection of the existing append-only knowledge rule.

 It deliberately models lineage, not a second correction store or final-output
 patch.  Production persistence and decisions remain the canonical machinery.
 """
 observation_id:str; value:str; valid_from:str; valid_to:str|None=None; supersedes:str|None=None

def evaluate_governed_replacement(*, prior: GovernedObservation, decision: str,
                                  replacement_value: str|None, locus: CorrectionLocus,
                                  challenge_basis: str, affiliation: str="") -> tuple[GovernedObservation, GovernedObservation|None]:
 """Return immutable historical prior plus an optional governed successor.

 A challenger affiliation never accepts a change.  Projection-only fixes do
 not mutate governed knowledge; insufficient/rejected challenges retain it.
 """
 if decision not in {"accept_governed_replacement", "accept_qualification", "reject_insufficient", "reject_unsupported"}:
  raise ValueError("a governed decision is required")
 if decision.startswith("reject_") or not challenge_basis.strip():
  return prior, None
 if locus is CorrectionLocus.PROJECTION:
  return prior, None
 if not replacement_value:
  raise ValueError("accepted governed replacement needs a replacement value")
 closed=GovernedObservation(prior.observation_id, prior.value, prior.valid_from, "decision-time", prior.supersedes)
 successor=GovernedObservation(f"{prior.observation_id}-superseding", replacement_value, "decision-time", None, prior.observation_id)
 return closed, successor
