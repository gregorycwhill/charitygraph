"""Create the provider-free Gate-3 fresh-holdout preparation packet.

This is deliberately structural.  It selects only from a frozen identity map
and frozen Semantic Demand Catalogue metadata; it never opens source bodies,
acquires material, calls a provider, or creates a reference answer.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
DATA = REPO.parent / "charitygraph-data"
IDENTITY_MAP = Path(r"C:\CharityGraph-runtime\phase5-top100-subject-bootstrap-v1\identity-map.json")
CG405_BENCHMARK = Path(r"C:\CharityGraph-runtime\artifacts\cg405-source-universe-sufficiency\benchmark-manifest.json")
CG406_PREPARED = REPO / "evidence" / "cg406-v14-final-development-replay" / "prepared-run-identity.json"
CATALOGUE = DATA / "docs" / "semantic-demand-catalogue-399" / "semantic-demand-catalogue.v1.json"
CATALOGUE_VALIDATION = DATA / "docs" / "semantic-demand-catalogue-399" / "validation.json"

BUILDER_COMMIT = "6daf2a10d495a933cb56a49f2e87b974e664c879"
DATA_COMMIT = "443d195abea91d7da111f5e573e90247ae823c36"
SEED = "CG-G3-FRESH-INDEPENDENT-SEMANTIC-HOLDOUT-2026-10-18-V1"
DOMAINS = tuple(range(1, 19))
SOURCE_UNIVERSE = (
    "acnc_register", "acnc_ais_bundle", "ato_abr_dgr", "official_website",
    "annual_report", "wikipedia_wikimedia", "pfra",
)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def put_json(name: str, value: Any) -> str:
    path = ROOT / name
    path.write_bytes(canonical(value))
    return sha_file(path)


def put_text(name: str, value: str) -> str:
    path = ROOT / name
    path.write_text(value.rstrip() + "\n", encoding="utf-8")
    return sha_file(path)


def rank(*parts: object) -> str:
    return sha_bytes("|".join(str(part) for part in (SEED, *parts)).encode("utf-8"))


def as_list(value: Any, description: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise RuntimeError(f"invalid {description}")
    return value


def demand_signature(demand: dict[str, Any]) -> dict[str, Any]:
    """Freeze existing catalogue fields without rewriting their semantics."""
    keys = (
        "id", "short_name", "family", "semantic_definition", "allowed_subject_types",
        "required_parameters", "optional_parameters", "scope_semantics",
        "temporal_semantics", "applicability_preconditions", "positive_proposition",
        "evidence_role_expectations", "answer_states", "missingness_cautions",
        "current_canonical_provenance",
    )
    frozen = {key: demand[key] for key in keys}
    frozen["semantic_signature_sha256"] = sha_bytes(canonical(frozen))
    return frozen


def build() -> None:
    for path in (IDENTITY_MAP, CG405_BENCHMARK, CG406_PREPARED, CATALOGUE, CATALOGUE_VALIDATION):
        if not path.is_file():
            raise RuntimeError(f"required frozen/pre-existing input is absent: {path}")

    identities = read_json(IDENTITY_MAP)
    identity_rows = as_list(identities.get("rows"), "identity map rows")
    if len(identity_rows) != 100 or len({row.get("subject_id") for row in identity_rows}) != 100:
        raise RuntimeError("identity map must contain 100 unique governed subjects")
    required_identity = {"subject_id", "abn", "display_name", "acnc_source_record_id", "source_artifact_hash", "status"}
    if any(not required_identity.issubset(row) for row in identity_rows):
        raise RuntimeError("identity map contains incomplete identity bindings")
    if identities.get("semantic_tasks_created") != 0:
        raise RuntimeError("identity pool is not provider-free bootstrap material")

    cg405_cases = as_list(read_json(CG405_BENCHMARK).get("cases"), "CG405 cases")
    cg405_names = {str(row["subject_name"]) for row in cg405_cases if row.get("subject_name")}
    if len(cg405_names) != 7:
        raise RuntimeError("expected seven CG405 exposed subjects")
    cg406_rows = as_list(read_json(CG406_PREPARED).get("prepared_rows"), "CG406 prepared rows")
    cg406_subject_ids = {str(row["instance_id"]).split(":SDC-", 1)[0].removeprefix("cg406:") for row in cg406_rows}
    if len(cg406_subject_ids) != 12:
        raise RuntimeError("expected twelve frozen CG406 subjects")

    excluded = []
    for row in identity_rows:
        reasons = []
        if row["display_name"] in cg405_names:
            reasons.append("CG405_SEMANTIC_DEVELOPMENT_OR_DEBUG_CASE")
        if row["subject_id"] in cg406_subject_ids:
            reasons.append("CG406_FROZEN_DEVELOPMENT_INSTANCE_SUBJECT")
        if reasons:
            excluded.append({
                "subject_id": row["subject_id"], "abn": row["abn"], "display_name": row["display_name"],
                "reasons": reasons,
            })
    eligible = [row for row in identity_rows if row["subject_id"] not in {item["subject_id"] for item in excluded}]
    if len(eligible) < 36:
        raise RuntimeError("fewer than 36 structurally eligible fresh subjects")

    catalogue_doc = read_json(CATALOGUE)
    candidates = as_list(catalogue_doc.get("candidates"), "catalogue candidates")
    if len(candidates) != 20 or {item.get("id") for item in candidates} != {f"SDC-C{i:02d}" for i in range(1, 21)}:
        raise RuntimeError("unexpected semantic demand catalogue identity")
    if any(not isinstance(item.get("north_star_domains"), list) for item in candidates):
        raise RuntimeError("catalogue demands lack structural domain assignments")

    # The catalogue's canonical field is north_star_domains, not primary_domain.
    # The requested 18-domain target is therefore defined ex ante as strata 1..18.
    selected_demand_by_domain: dict[int, dict[str, Any]] = {}
    for domain in DOMAINS:
        choices = [item for item in candidates if domain in item["north_star_domains"]]
        if not choices:
            raise RuntimeError(f"catalogue supplies no definition for domain {domain}")
        selected_demand_by_domain[domain] = min(choices, key=lambda item: rank("demand", domain, item["id"]))

    selected_subjects = sorted(eligible, key=lambda row: rank("subject", row["subject_id"]))[:36]
    instances = []
    for index, subject in enumerate(selected_subjects):
        domain = DOMAINS[index // 2]
        demand = selected_demand_by_domain[domain]
        signature = demand_signature(demand)
        instance_id = f"g3fresh-v1:{subject['subject_id']}:{demand['id']}:domain-{domain}"
        instances.append({
            "instance_id": instance_id,
            "selection_ordinal": index + 1,
            "domain_stratum": domain,
            "subject": {
                "subject_id": subject["subject_id"], "abn": subject["abn"], "display_name": subject["display_name"],
                "identity_authority_source_record_id": subject["acnc_source_record_id"],
                "identity_authority_artifact_sha256": subject["source_artifact_hash"],
                "identity_policy_id": subject.get("identity_policy_id"),
                "bootstrap_state": subject["status"],
            },
            "demand_definition_id": demand["id"],
            "semantic_signature": signature,
            "semantic_signature_sha256": signature["semantic_signature_sha256"],
            "evidence_acquisition_pathway": {
                "entrypoint": "governed ACNC identity binding and ABN",
                "future_source_universe_v1_only": list(SOURCE_UNIVERSE),
                "official_website_rule": "later use requires the governed ACNC Website locator and the bounded locator-derived repair rule",
                "preparation_state": "NOT_EVALUATED_NO_ACQUISITION_IN_THIS_TRANCHE",
            },
        })

    if len({row["instance_id"] for row in instances}) != 36 or len({row["subject"]["subject_id"] for row in instances}) != 36:
        raise RuntimeError("selected instances are not unique")
    distribution = {str(domain): sum(row["domain_stratum"] == domain for row in instances) for domain in DOMAINS}
    if set(distribution.values()) != {2}:
        raise RuntimeError("predeclared two-per-domain distribution was not achieved")

    # The 12 frozen CG406 identities in this baseline are deliberately hashes/IDs only;
    # no Builder result, response, oracle row, or diagnostic is consumed here.
    baseline = {
        "schema": "charitygraph.gate3.fresh-holdout-baseline/v1",
        "builder": {"branch": "gate3-cg406-remediation", "commit": BUILDER_COMMIT},
        "data": {"commit": DATA_COMMIT},
        "source_universe_v1": list(SOURCE_UNIVERSE),
        "semantic_contract": {
            "contract_id": "urn:charitygraph:builder:semantic-contract:evidence-selection-v1",
            "contract_version": "1.4", "schema_id": "urn:charitygraph:builder:schema:evidence-selection-output:1.4",
            "schema_version": "1.4-provenance-claim-separation", "adapter_version": "1.4",
            "validation_identity": "charitygraph.frozen_experiment.validate_evidence_selection",
        },
        "demand_catalogue": {
            "schema": catalogue_doc["schema"], "path": str(CATALOGUE), "sha256": sha_file(CATALOGUE),
            "validation_sha256": sha_file(CATALOGUE_VALIDATION), "candidate_count": len(candidates),
        },
        "frozen_cg406": {
            "subject_manifest_sha256": "bc0c63a6938cb23772213d3025bc70b363ddae8af6ae67e1e1b9a4d419eb66c8",
            "demand_manifest_sha256": "8aefa2a46838da065d93923004153abb905f1cabc087394aa58fa41f890b60fb",
            "v14_prepared_run_sha256": "da77187aa3fff0d59ef8931958f68b9bea7e88a716d0657dfc4a7c30ce8b5925",
            "v14_result_manifest_sha256": "12ee7636294b1ed72ad13d54f11c905494e0defc0a3081c3de23dbb5ca1a0364",
            "oracle_reference_ledger_sha256": "1af26276c216fd2af7dbaa7517e372efb08e991c947a612f6866db381c77f752",
            "oracle_manifest_sha256": "549bf31a2d3edd1f6798a4661295c916c2169781b4e7f2ec87756380c0b2890a",
            "treatment": "READ_ONLY_BASELINE_ONLY; no CG406 response, oracle content, classification, or diagnostic is input to selection",
        },
        "sdc_0019": "CANDIDATE_SOURCE_GAP; unchanged and not sampled or reclassified by this tranche",
        "provider_calls": 0, "source_acquisition": 0, "provider_reservations": 0,
    }
    excluded_inventory = {
        "schema": "charitygraph.gate3.fresh-holdout-excluded-inventory/v1",
        "purpose": "exclude all identifiable current Gate-3 semantic development/debug exposures before selection",
        "inputs": {"cg405_benchmark_sha256": sha_file(CG405_BENCHMARK), "cg406_prepared_identity_sha256": sha_file(CG406_PREPARED)},
        "cg405_exposed_subject_names": sorted(cg405_names),
        "cg406_exposed_subject_ids": sorted(cg406_subject_ids),
        "excluded_subjects_in_candidate_pool": sorted(excluded, key=lambda item: item["subject_id"]),
        "excluded_candidate_count": len(excluded),
        "note": "The identity pool itself records semantic_tasks_created=0. Only historic semantic exposure ledgers are exclusion inputs; raw sources, model outputs, oracle answers, and diagnostics are not read.",
    }
    algorithm = {
        "schema": "charitygraph.gate3.fresh-holdout-selection-algorithm/v1",
        "seed": SEED,
        "target": {"instances": 36, "domain_strata": list(DOMAINS), "instances_per_domain": 2, "minimum_acceptable_instances": 24},
        "subject_pool": {
            "identity_map_sha256": sha_file(IDENTITY_MAP), "input_subject_count": len(identity_rows),
            "eligibility": "unique governed ACNC identity binding; excluded from all supplied current Gate-3 semantic exposure ledgers",
            "ranking": "ascending SHA-256(seed | 'subject' | subject_id); select first 36",
        },
        "demand_pool": {
            "catalogue_sha256": sha_file(CATALOGUE), "catalogue_field": "north_star_domains",
            "terminology_audit": "The canonical catalogue does not expose a primary_domain field. This packet predeclares strata 1 through 18 over north_star_domains; it does not invent a new catalogue classification.",
            "ranking": "for each stratum d, ascending SHA-256(seed | 'demand' | d | demand_id); select first eligible definition containing d",
        },
        "pairing": "ranked selected subjects in order; positions 1-2 -> domain 1, 3-4 -> domain 2, …, 35-36 -> domain 18",
        "redistribution_if_short": "If fewer than two instances can be formed for a stratum, fill in ascending domain number using an unfilled catalogue-covered stratum with available eligible subjects; record the shortage. If total <24, stop without freezing a runnable holdout.",
        "prohibited_inputs": ["source body or representation text", "provider response", "oracle content", "expected answer", "CG406 result classification", "semantic development diagnostic"],
    }
    selected_definition_ids = {row["demand_definition_id"] for row in instances}
    vocabulary = {
        "schema": "charitygraph.gate3.fresh-holdout-demand-vocabulary/v1",
        "catalogue_sha256": sha_file(CATALOGUE),
        "definition_count": len(selected_definition_ids),
        "definitions": [demand_signature(item) for item in candidates if item["id"] in selected_definition_ids],
        "statement": "These are frozen copies of canonical demand-definition fields, not a semantic reference answer or new demand semantics.",
    }
    selection = {
        "schema": "charitygraph.gate3.fresh-semantic-holdout-manifest/v1",
        "selection_state": "FROZEN_BEFORE_EVIDENCE_EVALUATION_AND_ORACLE_CONSTRUCTION",
        "selection_algorithm_sha256": sha_bytes(canonical(algorithm)),
        "baseline_sha256": sha_bytes(canonical(baseline)),
        "seed": SEED, "selected_instance_count": len(instances), "domain_distribution": distribution,
        "instances": instances,
        "selection_prohibitions": algorithm["prohibited_inputs"],
    }
    eligibility = {
        "schema": "charitygraph.gate3.fresh-holdout-eligibility-audit/v1",
        "result": "PASS", "pre_evidence_only": True,
        "input_pool_count": len(identity_rows), "excluded_count": len(excluded), "eligible_subject_count": len(eligible),
        "selected_count": len(instances), "unique_selected_subjects": len({row["subject"]["subject_id"] for row in instances}),
        "all_selected_have_governed_identity_binding": all(bool(row["subject"]["identity_authority_source_record_id"]) for row in instances),
        "all_selected_have_frozen_demand_definition": all(bool(row["semantic_signature_sha256"]) for row in instances),
        "all_selected_have_admitted_future_pathway": all(row["evidence_acquisition_pathway"]["future_source_universe_v1_only"] == list(SOURCE_UNIVERSE) for row in instances),
        "cg406_instance_overlap": sorted({row["subject"]["subject_id"] for row in instances} & cg406_subject_ids),
        "cg405_subject_name_overlap": sorted({row["subject"]["display_name"] for row in instances} & cg405_names),
        "domain_distribution": distribution,
        "not_evaluated": ["evidence availability", "source acquisition success", "representation readiness", "rights approval", "semantic answer", "reference answer", "provider packet eligibility"],
        "conclusion": "36 structurally eligible, fresh-to-supplied-Gate-3-exposure-ledger instances are frozen. This is not a finding that their propositions will be easy, supported, acquirable, or provider-transmittable.",
    }
    isolation = {
        "schema": "charitygraph.gate3.fresh-holdout-independence-audit/v1",
        "result": "PASS", "provider_calls": 0, "source_acquisition": 0, "paid_oracle_generation": 0,
        "builder_result_or_response_inputs": [], "builder_validation_or_diagnostic_inputs": [], "oracle_content_inputs": [],
        "allowed_selection_inputs": [str(IDENTITY_MAP), str(CATALOGUE), str(CATALOGUE_VALIDATION), str(CG405_BENCHMARK), str(CG406_PREPARED)],
        "boundary": "The two exposure inputs contribute identifiers only for exclusion. They contribute no outcomes, evidence, scores, diagnoses, answers, or oracle material.",
    }

    put_json("baseline.json", baseline)
    put_json("excluded-case-inventory.json", excluded_inventory)
    put_json("selection-algorithm.json", algorithm)
    put_json("demand-definition-vocabulary.json", vocabulary)
    put_json("frozen-selected-holdout-manifest.json", selection)
    put_json("eligibility-audit.json", eligibility)
    put_json("independence-and-blindness-audit.json", isolation)
    put_json("domain-distribution.json", {"schema": "charitygraph.gate3.fresh-holdout-domain-distribution/v1", "distribution": distribution, "total": len(instances), "method": "two instances for each predeclared stratum 1..18"})

    rubric = """# Gate-3 fresh-holdout preregistered adjudication rubric

This rubric is frozen before any Builder semantic response, evidence packet, or independent oracle is created.

## Reference vocabulary

- `FULLY_SUPPORTED`: the reference establishes every material proposition at the required subject, scope and temporal state.
- `PARTIALLY_SUPPORTED`: the reference establishes a bounded material subset; the unresolved or unsupported remainder is named rather than silently promoted or negated.
- `NOT_ESTABLISHED`: the reviewed reference does not establish the requested proposition at the demanded scope/time. This is not a claim of negation.
- `CONFLICTS`: material, relevant reference evidence conflicts and the conflict cannot be truthfully collapsed.

## Per-instance measures

1. **Exact semantic match**: Builder conclusion, material propositions, scope/type, temporal state and qualifications align with the sealed reference.
2. **Usable-or-better bounded conclusion**: the conclusion is materially usable without concealing a limitation, partial state or conflict.
3. **Material overreach**: Builder makes a stronger, broader, newer, different-subject or unsupported conclusion.
4. **Material miss**: Builder omits directly supported material needed for the frozen demand.
5. **Honest missingness**: evidence absence, source silence, acquisition failure, representation failure, insufficient evidence and conflict remain distinct; missingness is never negation.
6. **Mechanical validity**: output passes the frozen schema/contract and cites only packet evidence IDs. Mechanical validity alone is not semantic correctness.
7. **Source-to-claim provenance**: every material conclusion can be traced to a cited packet record and source-native locator without treating metadata as entailment.
8. **Subject and temporal correctness**: legal entity, program/service, group, geography and time do not drift beyond the evidence or demand.

## Treatment rules frozen now

- A partial answer is scored `PARTIALLY_SUPPORTED` when it identifies the supported subset and its limitation. It is not automatically a false negative or generic insufficient-evidence response.
- Unresolved evidence is retained as unresolved; it cannot be scored as supporting a stronger claim.
- An oracle may use authoritative public material outside Source Universe v1 only to classify source-universe coverage. Such material must never enter Builder evidence packets or amend Source Universe v1.
- Builder acquisition, representation and rights failures are separately coded from interpretation and validation failures. A source-coverage limitation cannot be silently converted into semantic failure.
- Aggregate reporting must provide per-domain denominators and aggregate counts for exact match, usable-or-better, overreach, miss, honest missingness and mechanical validity. No threshold or Gate-3 closure recommendation is implied by this packet.
"""
    put_text("preregistered-scoring-rubric.md", rubric)
    oracle = """# Sealed independent-oracle construction instructions

## Isolation boundary

Create the oracle in a physically or access-controlled workspace separate from Builder execution and semantic-development materials. The reviewer receives only the frozen holdout manifest, frozen demand-definition vocabulary, this rubric, and the oracle handoff template. The reviewer must not receive Builder semantic responses, Builder outcome labels, validation outcomes, CG406 answers/patterns, or development diagnostics.

The implementation agent must not create, inspect, copy, or summarize the completed oracle. Return only a sealed oracle package hash, manifest hash, row count, and a statement that the contents remained inaccessible to Builder.

## Oracle workflow

1. Verify the incoming selection and vocabulary hashes against `artifact-inventory.json`.
2. For each frozen instance ID, independently research and adjudicate the exact demand definition using authoritative sources appropriate to the proposition. The reviewer may use public sources beyond Source Universe v1.
3. For each conclusion, record the reference vocabulary state, subject/scope/time, material proposition decomposition, source-to-claim locators, and limitations.
4. Classify every material limitation separately: `SOURCE_UNIVERSE_COVERAGE_GAP`, `ACQUISITION_GAP`, `REPRESENTATION_GAP`, `SELECTION_GAP`, `INTERPRETATION_FAILURE`, `VALIDATION_FAILURE`, or `UNRESOLVED`.
5. Freeze all reference rows, compute a row ledger SHA-256 and an oracle manifest SHA-256, and seal the content outside Builder.
6. Supply Builder only the oracle package identities after Builder's first terminal response freeze and mechanical validation. Do not disclose answer content earlier.

## Required sealed handoff fields

`oracle_workspace_identity`, `selection_manifest_sha256`, `demand_vocabulary_sha256`, `rubric_sha256`, `reference_row_count`, `independent_reference_ledger_sha256`, `oracle_manifest_sha256`, `sealed_at`, `reviewer_attestation`, `builder_content_disclosure_before_terminal_freeze=false`.
"""
    put_text("sealed-oracle-construction-instructions.md", oracle)
    execution = """# Later execution and blindness protocol

This packet authorizes none of these steps. They are the required order for a later, separately authorized experiment:

1. Verify and freeze this selection manifest and its inventory.
2. Independently establish and seal the reference oracle outside Builder.
3. Acquire and represent evidence only through Source Universe v1, preserving acquisition/representation/rights states.
4. Freeze Builder evidence packets and their source/representation/rights identities.
5. Freeze prepared provider-request identities, costs and exactly-once execution controls.
6. Obtain fresh trusted direct execution authority; CG406 authority is not transferable.
7. Execute each exact request once, with no semantic retries or post-hoc sample replacement.
8. Freeze each first terminal response, its receipt and cost accounting.
9. Run mechanical schema, packet-ID, lineage and contract validation.
10. Reveal the sealed oracle only to the independent adjudicator; score against the preregistered rubric and report per-domain plus aggregate results.

Every boundary requires a content-addressed manifest. Any identity or rights drift fails closed and requires a fresh decision; it does not permit a resend or silent substitution.
"""
    put_text("later-execution-and-blindness-protocol.md", execution)
    budget = {
        "schema": "charitygraph.gate3.fresh-holdout-indicative-budget/v1",
        "status": "INDICATIVE_ONLY_NOT_RESERVED_NOT_AUTHORIZED",
        "provider_calls_this_tranche": 0, "provider_reservations_this_tranche": 0, "actual_spend_aud": "0.00",
        "basis": "three times the frozen CG406 v1.4 12-request hard-max envelope, only if a later independent authority adopts identical model, token cap, pricing/FX snapshot and packet limits",
        "future_36_request_illustrative_hard_max_usd": "0.547971",
        "future_36_request_illustrative_hard_max_aud": "0.832935",
        "not_transferable": "CG406 execution authority, reservations and actuals are not authority for this fresh holdout.",
        "reestimate_required_before_execution": True,
    }
    put_json("indicative-provider-budget.json", budget)
    summary = f"""# Fresh Gate-3 semantic-quality holdout preparation

## Frozen selection

This provider-free packet freezes **36** fresh instances: exactly **two** in each predeclared Semantic Demand Catalogue stratum **1–18**. The selection is SHA-256 ranked from a governed 100-subject identity pool, after exclusion of the supplied CG405 and CG406 semantic-development exposure ledgers. It did not inspect evidence bodies, provider output, oracle material, classifications or diagnostics.

The catalogue itself has `north_star_domains`, not a `primary_domain` field. The strata are therefore a declared evaluation partition rather than a newly invented catalogue classification. All 36 subjects have a governed ACNC identity binding and an admitted future acquisition route; neither fact predicts evidence availability or an answer.

## Boundaries

- Builder branch/commit: `gate3-cg406-remediation` / `{BUILDER_COMMIT}`.
- Data commit: `{DATA_COMMIT}`.
- Source Universe v1 remains the seven admitted families listed in `baseline.json`.
- CG406 is read-only baseline history. No CG406 result, oracle content or diagnostic was used to select the new cases.
- This tranche: 0 provider calls, 0 source acquisitions, 0 paid oracle generation, 0 reservations, AUD 0 actual spend.
- SDC-0019 remains `CANDIDATE_SOURCE_GAP` and is not reclassified.

## Next controlled step

Transfer only the selected-manifest, demand vocabulary, rubric and sealed-oracle instructions to an independent isolated reviewer. The reviewer must return only sealed package identities until Builder’s future terminal-result freeze and mechanical validation complete.
"""
    put_text("summary.md", summary)

    tests = {
        "schema": "charitygraph.gate3.fresh-holdout-provider-free-tests/v1",
        "status": "PASS",
        "structural_checks": {
            "selected_count_is_36": len(instances) == 36,
            "each_stratum_has_two": set(distribution.values()) == {2},
            "all_subjects_unique": len({row["subject"]["subject_id"] for row in instances}) == 36,
            "cg405_overlap_empty": not eligibility["cg405_subject_name_overlap"],
            "cg406_overlap_empty": not eligibility["cg406_instance_overlap"],
            "catalogue_demand_signature_per_instance": all(row["semantic_signature_sha256"] for row in instances),
            "provider_calls_zero": True,
            "source_acquisition_zero": True,
            "selection_precedes_evidence_evaluation": True,
        },
        "note": "Repository regression-test invocation is recorded separately after this deterministic packet build.",
    }
    put_json("packet-structural-test-results.json", tests)

    # The preliminary content inventory is recorded before the handoff.  A final
    # inventory below then covers this file, the handoff, and the verifier too.
    inventory = {path.name: {"sha256": sha_file(path), "bytes": path.stat().st_size} for path in sorted(ROOT.iterdir()) if path.is_file() and path.name not in {"artifact-inventory.json", "handoff.json", "build_holdout_packet.py", "verify_holdout_packet.py"}}
    inventory["build_holdout_packet.py"] = {"sha256": sha_file(ROOT / "build_holdout_packet.py"), "bytes": (ROOT / "build_holdout_packet.py").stat().st_size}
    put_json("content-artifact-inventory.json", {"schema": "charitygraph.gate3.fresh-holdout-content-artifact-inventory/v1", "inventory_scope": "content artifacts plus generator before handoff; excludes inventory metadata itself", "artifacts": inventory})
    handoff = {
        "schema": "charitygraph.gate3.fresh-holdout-handoff/v1", "status": "READY_FOR_FRESH_G3_ORACLE_CONSTRUCTION",
        "selection_manifest_sha256": sha_file(ROOT / "frozen-selected-holdout-manifest.json"),
        "selection_algorithm_sha256": sha_file(ROOT / "selection-algorithm.json"),
        "content_artifact_inventory_sha256": sha_file(ROOT / "content-artifact-inventory.json"),
        "selected_instance_count": len(instances), "domain_distribution": distribution,
        "freshness": "No selected subject overlaps the supplied CG405 or CG406 semantic exposure ledgers.",
        "next_step": "Independent reviewer constructs and seals the oracle under sealed-oracle-construction-instructions.md; Builder must not inspect its contents.",
        "provider_calls": 0, "source_acquisition": 0, "provider_reservations": 0,
    }
    put_json("handoff.json", handoff)
    # No finite file can include its own final SHA-256.  This final inventory
    # covers every other packet artifact, including both generator/verifier and
    # the handoff; its self-hash is recorded by the verification command and
    # final human handoff.
    complete_inventory = {
        path.name: {"sha256": sha_file(path), "bytes": path.stat().st_size}
        for path in sorted(ROOT.iterdir())
        if path.is_file() and path.name != "artifact-inventory.json"
    }
    put_json("artifact-inventory.json", {"schema": "charitygraph.gate3.fresh-holdout-artifact-inventory/v1", "inventory_scope": "every packet artifact except this inventory's unavoidable self-reference", "artifacts": complete_inventory})


if __name__ == "__main__":
    build()
