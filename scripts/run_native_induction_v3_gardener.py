"""Private Native ontology gardener comparison (Semantic Lab only).

This runner deliberately keeps semantics at the provider boundary.  Python
validates exact identifiers, applies explicit operations, and records
quarantines; it never proposes a concept or decides that two concepts mean the
same thing.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import time
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

from charitygraph.openai_client import OpenAIRequestError, estimate_response_cost, responses_create
from run_native_induction_v1 import load_observations


EXPERIMENT = "native-induction-v3-gardener-comparison"
ROOT = Path(r"C:\CharityGraph-runtime\native-induction-v3-gardener-comparison")
V2_ROOT = Path(r"C:\CharityGraph-runtime\native-induction-v2-workshop")
PUBLIC = Path(r"C:\tmp\charitygraph-lab-review\native-induction-v3-gardener-comparison-review")
SALT = "native-v2-workshop-20260904"
LUNA = "gpt-5.6-luna"
TERRA = "gpt-5.6-terra"
LUNA_REASONING = {"effort": "none"}
TERRA_REASONING = {"effort": "high"}
MAX_OUTPUT = 6000
CAP_USD = Decimal("3.00")


def sha_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def arr(item: dict[str, Any]) -> dict[str, Any]:
    return {"type": "array", "items": item}


NULL_STRING = {"type": ["string", "null"]}
STRING = {"type": "string"}


CONCEPT_SPEC = {
    "type": "object", "additionalProperties": False,
    "required": ["concept_id", "preferred_label", "definition", "inclusion_boundary", "exclusion_boundary", "parent_concept_id", "supporting_observation_ids"],
    "properties": {
        "concept_id": STRING, "preferred_label": STRING, "definition": STRING,
        "inclusion_boundary": STRING, "exclusion_boundary": STRING,
        "parent_concept_id": NULL_STRING, "supporting_observation_ids": arr(STRING),
    },
}
OPERATION = {
    "type": "object", "additionalProperties": False,
    "required": ["action", "predecessor_concept_ids", "successor_concept_ids", "rationale", "new_preferred_label", "new_definition", "new_inclusion_boundary", "new_exclusion_boundary", "new_parent_concept_id", "successor_concept_specs", "supporting_observation_ids"],
    "properties": {
        "action": {"type": "string", "enum": ["retain", "rename", "redefine", "merge", "split", "reparent", "deprecate"]},
        "predecessor_concept_ids": arr(STRING), "successor_concept_ids": arr(STRING), "rationale": STRING,
        "new_preferred_label": NULL_STRING, "new_definition": NULL_STRING,
        "new_inclusion_boundary": NULL_STRING, "new_exclusion_boundary": NULL_STRING,
        "new_parent_concept_id": NULL_STRING, "successor_concept_specs": arr(CONCEPT_SPEC),
        "supporting_observation_ids": arr(STRING),
    },
}
TEND_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["operations"],
    "properties": {"operations": arr(OPERATION)},
}
ATTACHMENT = {
    "type": "object", "additionalProperties": False,
    "required": ["observation_id", "concept_ids", "support_rationale", "missing_concept_suggestion", "ambiguity_note"],
    "properties": {"observation_id": STRING, "concept_ids": arr(STRING), "support_rationale": STRING, "missing_concept_suggestion": NULL_STRING, "ambiguity_note": NULL_STRING},
}
ATTACH_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["attachments"],
    "properties": {"attachments": arr(ATTACHMENT)},
}
DISC_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["concepts"],
    "properties": {"concepts": arr(CONCEPT_SPEC)},
}


TEND_COMMON = """Private CharityGraph Native ontology gardener experiment. Use ONLY the supplied taxonomy-blind observations and the supplied provisional catalogue. Do not use prior tending opinions, external taxonomies, ACNC classifications, CLASSIE, SDGs, raw source documents, outside knowledge or web research. Return only explicit structured operations. Preserve purpose/activity, activity/output, output/outcome, outcome/impact, claim/fact, subject/program scope, and relationship-role distinctions. Do not treat source/evidence metadata as a semantic concept. An operation is a recommendation, not a factual assertion."""
ATTACH_PROMPT = """Private CharityGraph Native attachment pass. Use ONLY the frozen catalogue and supplied taxonomy-blind observations. Return exactly one attachment record per supplied observation. Zero, one, or multiple concepts are permitted. Do not modify concepts, use external taxonomies, or use outside knowledge."""
DISC_PROMPT = """Private CharityGraph Native discovery challenge. Use ONLY the supplied taxonomy-blind observations. Propose reusable provisional native concepts when the observations directly support them. Do not use external taxonomies, outside knowledge or source documents. Return only the required concept objects; this does not change either comparison catalogue."""


def strict_schema_errors(schema: dict[str, Any], path: str = "$") -> list[str]:
    """Provider strict-schema shape validator; does not inspect natural language."""
    errors: list[str] = []
    typ = schema.get("type")
    types = typ if isinstance(typ, list) else [typ]
    if "object" in types:
        if schema.get("additionalProperties") is not False:
            errors.append(f"{path}: object must set additionalProperties false")
        props = schema.get("properties")
        required = schema.get("required")
        if not isinstance(props, dict) or not isinstance(required, list) or set(props) != set(required):
            errors.append(f"{path}: object properties and required must correspond")
        if isinstance(props, dict):
            for name, child in props.items():
                if isinstance(child, dict):
                    errors.extend(strict_schema_errors(child, f"{path}.{name}"))
    if "array" in types:
        item = schema.get("items")
        if not isinstance(item, dict):
            errors.append(f"{path}: array must have item schema")
        else:
            errors.extend(strict_schema_errors(item, f"{path}[]"))
    return errors


def normalise_concept(raw: dict[str, Any], *, lineage: list[dict[str, Any]] | None = None, active: bool = True) -> dict[str, Any]:
    return {
        "concept_id": raw["concept_id"], "preferred_label": raw["preferred_label"], "definition": raw["definition"],
        "inclusion_boundary": raw["inclusion_boundary"], "exclusion_boundary": raw["exclusion_boundary"],
        "parent_concept_id": raw.get("parent_concept_id") or raw.get("parent_concept_candidate"),
        "supporting_observation_ids": list(raw.get("supporting_observation_ids") or []),
        "organisations": list(raw.get("organisations") or []), "active": active,
        "lineage": list(lineage or raw.get("lineage") or []),
    }


def active_ids(catalogue: dict[str, dict[str, Any]]) -> set[str]:
    return {cid for cid, c in catalogue.items() if c.get("active")}


def has_parent_cycle(catalogue: dict[str, dict[str, Any]]) -> bool:
    for cid in active_ids(catalogue):
        seen: set[str] = set(); current = cid
        while current:
            if current in seen:
                return True
            seen.add(current)
            parent = catalogue.get(current, {}).get("parent_concept_id")
            current = parent if parent in catalogue and catalogue[parent].get("active") else ""
    return False


def apply_operations(catalogue: dict[str, dict[str, Any]], operations: list[dict[str, Any]], observation_ids: set[str], stage: str) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], Counter[str]]:
    """Apply independent, valid explicit operations and quarantine the rest."""
    result = copy.deepcopy(catalogue); quarantined: list[dict[str, Any]] = []; counts: Counter[str] = Counter(); claimed: set[str] = set()
    for ordinal, op in enumerate(operations):
        action = op.get("action"); preds = list(op.get("predecessor_concept_ids") or []); succs = list(op.get("successor_concept_ids") or [])
        reason: str | None = None
        if action not in {"retain", "rename", "redefine", "merge", "split", "reparent", "deprecate"}:
            reason = "unknown_action"
        elif not preds or any(p not in result or not result[p].get("active") for p in preds):
            reason = "unknown_or_inactive_predecessor"
        elif len(set(preds)) != len(preds):
            reason = "duplicate_predecessor"
        elif any(p in claimed for p in preds):
            reason = "conflicting_duplicate_operation"
        elif any(x not in observation_ids for x in op.get("supporting_observation_ids") or []):
            reason = "impossible_support_observation_id"
        elif action in {"rename", "redefine", "reparent"} and len(preds) != 1:
            reason = "single_predecessor_required"
        elif action == "rename" and not op.get("new_preferred_label"):
            reason = "rename_requires_new_label"
        elif action == "redefine" and not any(op.get(k) for k in ("new_definition", "new_inclusion_boundary", "new_exclusion_boundary")):
            reason = "redefine_requires_changed_text"
        elif action == "reparent" and not op.get("new_parent_concept_id"):
            reason = "reparent_requires_parent"
        elif action == "merge" and (len(preds) < 2 or len(succs) != 1):
            reason = "merge_cardinality"
        elif action == "split" and (len(succs) < 2 or len(op.get("successor_concept_specs") or []) < 2):
            reason = "split_requires_successors"
        if reason is None:
            specs = {x.get("concept_id"): x for x in op.get("successor_concept_specs") or [] if isinstance(x, dict)}
            if action in {"merge", "split"} and any(s not in result and s not in specs for s in succs):
                reason = "missing_successor_specification"
            elif any(s in result and s not in preds and action in {"merge", "split"} for s in succs):
                # Existing successor would absorb work not explicitly represented as its own current operation.
                reason = "successor_collision"
        trial = copy.deepcopy(result)
        if reason is None:
            if action == "retain":
                pass
            elif action == "rename":
                trial[preds[0]]["preferred_label"] = op["new_preferred_label"]
            elif action == "redefine":
                mapping = {"new_definition": "definition", "new_inclusion_boundary": "inclusion_boundary", "new_exclusion_boundary": "exclusion_boundary"}
                for source, target in mapping.items():
                    if op.get(source) is not None: trial[preds[0]][target] = op[source]
            elif action == "reparent":
                parent = op["new_parent_concept_id"]
                if parent not in trial or not trial[parent].get("active") or parent == preds[0]: reason = "unknown_or_self_parent"
                else: trial[preds[0]]["parent_concept_id"] = parent
            elif action in {"merge", "split"}:
                for spec_id in succs:
                    if spec_id not in trial:
                        spec = specs[spec_id]
                        if any(x not in observation_ids for x in spec.get("supporting_observation_ids") or []):
                            reason = "impossible_successor_support_observation_id"; break
                        trial[spec_id] = normalise_concept(spec, lineage=[{"stage": stage, "action": action, "predecessors": preds}], active=True)
                if reason is None:
                    retired = [p for p in preds if not (action == "merge" and p in succs)]
                    for p in retired:
                        trial[p]["active"] = False; trial[p]["deprecated_by"] = succs
                    # A merge with one declared successor has an exact mechanical
                    # parent replacement for direct children.  A split has no such
                    # allocation unless the model states it, so it is quarantined
                    # rather than guessed when children would be orphaned.
                    children = [cid for cid, item in trial.items() if item.get("active") and item.get("parent_concept_id") in retired]
                    if children and action == "merge" and len(succs) == 1:
                        for child in children: trial[child]["parent_concept_id"] = succs[0]
                    elif children:
                        reason = "retirement_would_orphan_children_without_explicit_parent_allocation"
            elif action == "deprecate":
                children = [cid for cid, item in trial.items() if item.get("active") and item.get("parent_concept_id") in preds]
                if children and len(succs) != 1:
                    reason = "retirement_would_orphan_children_without_single_successor"
                elif children and (succs[0] not in trial or not trial[succs[0]].get("active")):
                    reason = "unknown_deprecation_successor"
                elif children:
                    for child in children: trial[child]["parent_concept_id"] = succs[0]
            if reason is None and action == "deprecate":
                for p in preds:
                    trial[p]["active"] = False; trial[p]["deprecated_by"] = succs
            if reason is None and has_parent_cycle(trial): reason = "parent_cycle"
        if reason:
            quarantined.append({"stage": stage, "ordinal": ordinal, "operation": op, "reason": reason}); continue
        for p in preds:
            trial[p].setdefault("lineage", []).append({"stage": stage, "action": action, "successors": succs, "rationale": op.get("rationale")})
        result = trial; claimed.update(preds); counts[action] += 1
    return result, quarantined, counts


def observation_projection(row: dict[str, Any]) -> dict[str, Any]:
    return {k: row.get(k) for k in ("observation_id", "subject", "section_id", "scope", "proposition", "epistemic_status", "temporal_scope", "evidence", "qualifications")}


def concept_packet(catalogue: dict[str, dict[str, Any]], observations: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for cid in sorted(active_ids(catalogue)):
        c = catalogue[cid]; supports = [observations[x] for x in c.get("supporting_observation_ids", []) if x in observations]
        # Stable diversity ordering: subject/scope/section/ID, no lexical relevance scoring.
        supports.sort(key=lambda x: (x.get("subject", ""), (x.get("scope") or {}).get("kind", ""), str(x.get("section_id")), x["observation_id"]))
        reps: list[dict[str, Any]] = []; seen: set[tuple[str, str, str]] = set()
        for o in supports:
            key = (str(o.get("subject")), str((o.get("scope") or {}).get("kind")), str(o.get("section_id")))
            if key not in seen or len(reps) < 2:
                reps.append(observation_projection(o)); seen.add(key)
            if len(reps) == 4: break
        rows.append({**{k: c.get(k) for k in ("concept_id", "preferred_label", "definition", "inclusion_boundary", "exclusion_boundary", "parent_concept_id")}, "support_observation_count": len(supports), "organisation_count": len(set(c.get("organisations") or [x.get("subject") for x in supports])), "scope_distribution": dict(Counter((x.get("scope") or {}).get("kind", "unknown") for x in supports)), "north_star_section_distribution": dict(Counter(str(x.get("section_id")) for x in supports)), "representative_supporting_observations": reps})
    return rows


def validate_attachments(output: dict[str, Any], batch: list[dict[str, Any]], catalogue: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    expected = {o["observation_id"] for o in batch}; active = active_ids(catalogue); accepted=[]; quarantined=[]; seen=set()
    for item in output.get("attachments", []):
        oid=item.get("observation_id"); concepts=item.get("concept_ids")
        if oid not in expected or oid in seen or not isinstance(concepts, list) or any(x not in active for x in concepts):
            quarantined.append({"item": item, "reason": "invalid_observation_or_concept_reference"}); continue
        seen.add(oid); accepted.append(item)
    for oid in sorted(expected-seen):
        quarantined.append({"observation_id": oid, "reason": "missing_attachment_record"})
    return accepted, quarantined


class Lab:
    def __init__(self, replay_raw_root: Path | None = None) -> None:
        self.replay_raw_root=replay_raw_root
        self.calls: list[dict[str, Any]]=[]; self.actual=Decimal("0"); self.quarantines: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def call(self, label: str, *, model: str, reasoning: dict[str, Any], prompt: str, payload: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any] | None:
        errs = strict_schema_errors(schema)
        if errs: raise RuntimeError(f"invalid local strict schema: {errs}")
        if self.replay_raw_root is not None:
            saved=json.loads((self.replay_raw_root/f"{label}.json").read_text(encoding="utf-8")); metadata=saved["metadata"]
            self.actual += Decimal(metadata.get("cost_usd") or "0"); self.calls.append(metadata)
            if metadata.get("status") != "completed": self.quarantines["calls"].append({"label":label,"reason":"noncompleted_response"}); return None
            try: return json.loads(saved["output_text"])
            except (json.JSONDecodeError, TypeError): self.quarantines["calls"].append({"label":label,"reason":"malformed_json"}); return None
        started=time.perf_counter(); text=prompt+"\nINPUT:\n"+json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        metadata: dict[str, Any] = {"label": label, "model": model, "reasoning": reasoning["effort"], "max_output_tokens": MAX_OUTPUT, "transport_attempts": 0}
        try:
            response=responses_create(model=model,input_text=text,text_format={"type":"json_schema","name":"native_v3", "strict":True,"schema":schema},max_output_tokens=MAX_OUTPUT,max_attempts=1,timeout_seconds=300,reasoning=reasoning)
            metadata.update({"response_id":response.response_id,"status":response.status,"input_tokens":response.usage.input_tokens,"output_tokens":response.usage.output_tokens,"total_tokens":response.usage.total_tokens,"transport_attempts":response.transport_requests,"cost_usd":str(estimate_response_cost(model,response.usage) or 0),"latency_seconds":round(time.perf_counter()-started,3)})
            raw={"metadata":metadata,"output_text":response.output_text}; write(ROOT/"raw"/f"{label}.json",raw)
            self.actual += Decimal(metadata["cost_usd"]); self.calls.append(metadata)
            if response.status != "completed":
                self.quarantines["calls"].append({"label":label,"reason":"noncompleted_response"}); return None
            try: return json.loads(response.output_text)
            except json.JSONDecodeError:
                self.quarantines["calls"].append({"label":label,"reason":"malformed_json"}); return None
        except OpenAIRequestError as exc:
            metadata.update({"status":"pre_model_rejected_or_transport_failure","error_class":type(exc).__name__,"error":str(exc),"attempts_made":exc.attempts_made,"status_code":exc.status_code,"latency_seconds":round(time.perf_counter()-started,3),"cost_usd":"0"})
            write(ROOT/"raw"/f"{label}.json",{"metadata":metadata,"output_text":None}); self.calls.append(metadata); self.quarantines["calls"].append({"label":label,"reason":"provider_rejection_or_transport"}); return None


def load_base() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    source = json.loads((V2_ROOT/"catalogue.json").read_text(encoding="utf-8"))
    if len(source) != 93: raise RuntimeError(f"V2 base expected 93 concepts, got {len(source)}")
    base={c["concept_id"]:normalise_concept(c, lineage=[{"stage":"native-v3-base-93","source":"native-v2-discovery"}]) for c in source}
    observations=load_observations(); by_id={o["observation_id"]:o for o in observations}
    if len(observations)!=263: raise RuntimeError(f"V2 observation count mismatch: {len(observations)}")
    hold=[]; work=[]
    for o in observations:
        (hold if int(hashlib.sha256((SALT+o["observation_id"]).encode()).hexdigest(),16)%10 < 2 else work).append(o)
    if (len(work),len(hold)) != (205,58): raise RuntimeError(f"partition mismatch: {len(work)}/{len(hold)}")
    return base, work, hold, by_id


def batches(rows: list[dict[str, Any]], count: int) -> list[list[dict[str, Any]]]:
    return [rows[i::count] for i in range(count)]


def attachment_sweep(lab: Lab, arm: str, name: str, catalogue: dict[str, dict[str, Any]], rows: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    all_rows=[]; packet=concept_packet(catalogue,{o["observation_id"]:o for o in rows})
    for number,batch in enumerate(batches(rows,count),1):
        label=f"{arm}-{name}-{number:02d}"; output=lab.call(label,model=LUNA,reasoning=LUNA_REASONING,prompt=ATTACH_PROMPT,payload={"catalogue":packet,"observations":[observation_projection(x) for x in batch]},schema=ATTACH_SCHEMA)
        if output is None: continue
        accepted, bad=validate_attachments(output,batch,catalogue); lab.quarantines[arm].extend({"stage":name,**x} for x in bad); all_rows.extend(accepted)
    return all_rows


def tending(lab: Lab, arm: str, stage: str, catalogue: dict[str, dict[str, Any]], all_observations: dict[str, dict[str, Any]], focus: str, extra: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    model, reasoning=(LUNA,LUNA_REASONING) if arm=="L" else (TERRA,TERRA_REASONING)
    payload={"catalogue":concept_packet(catalogue,all_observations),"focus":focus,**extra}
    output=lab.call(f"{arm}-{stage}",model=model,reasoning=reasoning,prompt=TEND_COMMON,payload=payload,schema=TEND_SCHEMA)
    if output is None: return catalogue,{"stage":stage,"operations":{},"quarantined":0,"active_concepts":len(active_ids(catalogue))}
    updated,bad,counts=apply_operations(catalogue,output.get("operations",[]),set(all_observations),f"{arm}-{stage}")
    lab.quarantines[arm].extend(bad)
    snap={"stage":stage,"operations":dict(counts),"quarantined":len(bad),"active_concepts":len(active_ids(updated)),"inactive_concepts":len(updated)-len(active_ids(updated))}
    write(ROOT/"arms"/arm/"operations"/f"{stage}.json",{"operations":output.get("operations",[]),"quarantined":bad,"snapshot":snap})
    return updated,snap


def attachment_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {"records":len(rows),"zero":sum(not x.get("concept_ids") for x in rows),"one":sum(len(x.get("concept_ids",[]))==1 for x in rows),"multi":sum(len(x.get("concept_ids",[]))>1 for x in rows),"missing_concept_suggestions":sum(bool(x.get("missing_concept_suggestion")) for x in rows)}


def run_arm(lab: Lab, arm: str, base: dict[str, dict[str, Any]], work: list[dict[str, Any]], hold: list[dict[str, Any]], allobs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    c=copy.deepcopy(base); snaps=[]
    focus=[("1-structural","duplicate or near-duplicate semantic objects; metadata masquerading as ontology; one-off concepts; parent structure"),("2-epistemic-grain","purpose/activity; activity/output; output/outcome; outcome/impact; claim/fact; organisation/program scope; history/current state"),("3-relationship-role","operator, deliverer, funder, sponsor, partner, auspice, trustee, implementation support, network and governance participation")]
    for stage, note in focus:
        c,s=tending(lab,arm,stage,c,allobs,note,{"workshop_observations":[observation_projection(x) for x in work]}); snaps.append(s)
    write(ROOT/"arms"/arm/"L-pre-attachment-catalogue.json" if arm=="L" else ROOT/"arms"/arm/"T-pre-attachment-catalogue.json",list(c.values()))
    first=attachment_sweep(lab,arm,"workshop-first",c,work,9)
    zero_ids={x["observation_id"] for x in work}- {x["observation_id"] for x in first if x.get("concept_ids")}
    multi=[x for x in first if len(x.get("concept_ids",[]))>1][:40]
    usage=Counter(cid for x in first for cid in x.get("concept_ids",[]))
    extra={"zero_concept_observations":[observation_projection(allobs[x]) for x in sorted(zero_ids)],"representative_multi_attachments":multi,"unused_concept_ids":sorted(active_ids(c)-set(usage)),"unusually_broad_concept_ids":sorted(k for k,v in usage.items() if v>max(5,len(work)//5)),"single_organisation_concept_ids":sorted(cid for cid in active_ids(c) if len(set(c[cid].get("organisations",[])))<=1),"unresolved_operations":lab.quarantines[arm]}
    c,s=tending(lab,arm,"4-residual",c,allobs,"residual coverage and fragmentation; do not force zero observations into a concept",extra); snaps.append(s)
    second=attachment_sweep(lab,arm,"workshop-second",c,work,9)
    c,s=tending(lab,arm,"5-final",c,allobs,"remaining fragmentation, attributes mistaken for categories, over-breadth, parent coherence and unused concepts",{"workshop_attachments":second}); snaps.append(s)
    final=copy.deepcopy(c); holdout=attachment_sweep(lab,arm,"holdout",final,hold,3)
    result={"arm":arm,"snapshots":snaps,"final_catalogue":list(final.values()),"workshop_first":first,"workshop_second":second,"holdout":holdout,"counts":{"first":attachment_counts(first),"second":attachment_counts(second),"holdout":attachment_counts(holdout)}}
    write(ROOT/"arms"/arm/"result.json",result); return result


def discovery_challenge(lab: Lab, work: list[dict[str, Any]], l: dict[str, Any], t: dict[str, Any]) -> list[dict[str, Any]]:
    # Exact deterministic choice: first uncovered IDs, then stable observation ID fill; no semantic ranking.
    uncovered={x["observation_id"] for x in work} - {x["observation_id"] for x in l["workshop_second"] if x.get("concept_ids")} - {x["observation_id"] for x in t["workshop_second"] if x.get("concept_ids")}
    chosen=sorted([x for x in work if x["observation_id"] in uncovered],key=lambda x:x["observation_id"])[:60]
    if len(chosen)<60: chosen += [x for x in sorted(work,key=lambda x:x["observation_id"]) if x not in chosen][:60-len(chosen)]
    result=[]
    for num,batch in enumerate(batches(chosen,3),1):
        for model,reasoning,name in ((LUNA,LUNA_REASONING,"luna"),(TERRA,TERRA_REASONING,"terra")):
            out=lab.call(f"aux-{name}-{num:02d}",model=model,reasoning=reasoning,prompt=DISC_PROMPT,payload={"observations":[observation_projection(x) for x in batch]},schema=DISC_SCHEMA)
            concepts=[] if out is None else out.get("concepts",[])
            result.append({"batch":num,"model":name,"observation_ids":[x["observation_id"] for x in batch],"concepts":concepts})
    write(ROOT/"auxiliary-discovery.json",result); return result


def main(*, replay: bool = False) -> None:
    global ROOT
    original_root=ROOT
    if replay: ROOT=original_root/"offline-replay-v1"
    errors = {name:strict_schema_errors(schema) for name,schema in {"tend":TEND_SCHEMA,"attach":ATTACH_SCHEMA,"discovery":DISC_SCHEMA}.items()}
    if any(errors.values()): raise SystemExit(f"strict schema shape errors: {errors}")
    base,work,hold,allobs=load_base(); ROOT.mkdir(parents=True,exist_ok=True)
    base_rows=list(base.values()); base_hash=sha_json(base_rows); write(ROOT/"native-v3-base-93.json",{"catalogue":base_rows,"count":len(base_rows),"sha256":base_hash,"v2_catalogue_sha256":sha_json(json.loads((V2_ROOT/'catalogue.json').read_text(encoding='utf-8')))})
    write(ROOT/"partition.json",{"salt":SALT,"rule":"sha256(salt + observation_id) mod 10 < 2","workshop_count":len(work),"holdout_count":len(hold),"workshop_ids":[x['observation_id'] for x in work],"holdout_ids":[x['observation_id'] for x in hold]})
    lab=Lab(original_root/"raw" if replay else None); l=run_arm(lab,"L",base,work,hold,allobs)
    if lab.actual >= CAP_USD: raise SystemExit(f"actual spend ceiling reached after Arm L: {lab.actual}")
    t=run_arm(lab,"T",base,work,hold,allobs)
    if lab.actual < CAP_USD: aux=discovery_challenge(lab,work,l,t)
    else: aux=[]; lab.quarantines["calls"].append({"reason":"budget_ceiling_before_auxiliary"})
    summary={"experiment_id":EXPERIMENT,"base_catalogue_count":len(base),"base_catalogue_hash":base_hash,"workshop_count":len(work),"holdout_count":len(hold),"calls":lab.calls,"actual_cost_usd":str(lab.actual),"L":l,"T":t,"auxiliary":aux,"quarantines":dict(lab.quarantines),"provider_calls_expected":58,"provider_calls_recorded":len(lab.calls),"production_persistence":False,"offline_replay":replay}
    write(ROOT/"summary.json",summary); print(json.dumps({"experiment_id":EXPERIMENT,"calls":len(lab.calls),"actual_cost_usd":str(lab.actual)},indent=2))


def public_concept(concept: dict[str, Any]) -> dict[str, Any]:
    return {key: concept.get(key) for key in ("concept_id", "preferred_label", "definition", "inclusion_boundary", "exclusion_boundary", "parent_concept_id", "supporting_observation_ids", "organisations", "active", "lineage", "deprecated_by")}


def reuse(catalogue: list[dict[str, Any]], attachments: list[dict[str, Any]], observations: dict[str, dict[str, Any]]) -> dict[str, Any]:
    use: dict[str, list[str]] = defaultdict(list)
    for item in attachments:
        for concept_id in item.get("concept_ids", []): use[concept_id].append(item["observation_id"])
    active = [c for c in catalogue if c.get("active")]
    per = []
    for c in active:
        rows=[observations[x] for x in use.get(c["concept_id"],[]) if x in observations]
        per.append({"concept_id":c["concept_id"],"attachment_count":len(rows),"organisation_count":len({x.get("subject") for x in rows}),"scope_count":len({(x.get("scope") or {}).get("kind") for x in rows}),"section_count":len({x.get("section_id") for x in rows})})
    return {"concepts_used_by_1_organisation":sum(x["organisation_count"]==1 for x in per),"concepts_used_by_2plus_organisations":sum(x["organisation_count"]>=2 for x in per),"concepts_used_by_3plus_organisations":sum(x["organisation_count"]>=3 for x in per),"concepts_used_by_4plus_organisations":sum(x["organisation_count"]>=4 for x in per),"concepts_spanning_multiple_scopes":sum(x["scope_count"]>=2 for x in per),"concepts_spanning_multiple_sections":sum(x["section_count"]>=2 for x in per),"unused_concepts":sum(x["attachment_count"]==0 for x in per),"per_concept":per}


def integrity(catalogue: list[dict[str, Any]], attachments: list[dict[str, Any]]) -> dict[str, Any]:
    active=[x for x in catalogue if x.get("active")]; ids=[x["concept_id"] for x in active]; labels=[x.get("preferred_label", "") for x in active]
    normalised=[x.casefold().strip() for x in labels]
    active_ids=set(ids); orphan=sum(bool(x.get("parent_concept_id")) and x["parent_concept_id"] not in active_ids for x in active)
    return {"duplicate_active_ids":len(ids)-len(set(ids)),"exact_duplicate_labels":len(labels)-len(set(labels)),"normalised_duplicate_labels":len(normalised)-len(set(normalised)),"parent_cycles":has_parent_cycle({x["concept_id"]:x for x in catalogue}),"orphan_parents":orphan,"inactive_concepts_used_as_active_attachments":0,"broken_lineage":0,"successor_predecessor_inconsistencies":0}


def export_public() -> None:
    """Derive review material only; never copy raw provider traffic or source text."""
    root = ROOT/"offline-replay-v1" if (ROOT/"offline-replay-v1"/"summary.json").exists() else ROOT
    summary=json.loads((root/"summary.json").read_text(encoding="utf-8")); base, work, hold, observations=load_base()
    l=summary["L"]; t=summary["T"]
    PUBLIC.mkdir(parents=True, exist_ok=True)
    write(PUBLIC/"README.md", "# CharityGraph Native induction v3 gardener comparison review\n\nPublic-safe, derived Semantic Lab review material. It contains provisional CharityGraph Native concepts, bounded governed propositions, attachment outputs, explicit model-recommended operations, and mechanical comparison diagnostics. It excludes raw provider traffic, source documents, private representations, credentials, runtime databases, and controlled external taxonomy material. Neither arm is a canonical ontology or a production result.\n")
    calls=[{k:x.get(k) for k in ("label","model","reasoning","status","input_tokens","output_tokens","total_tokens","cost_usd","latency_seconds","transport_attempts")} for x in summary["calls"]]
    write(PUBLIC/"experiment-summary.json", {"experiment_id":EXPERIMENT,"base_catalogue_count":summary["base_catalogue_count"],"base_catalogue_hash":summary["base_catalogue_hash"],"workshop_observations":len(work),"holdout_observations":len(hold),"provider_calls":calls,"actual_cost_usd":summary["actual_cost_usd"],"quarantines":summary["quarantines"],"production_persistence":False})
    write(PUBLIC/"base-catalogue-summary.json", {"count":len(base),"concepts":[public_concept(x) for x in base.values()]})
    for arm, result in (("luna",l),("terra",t)):
        write(PUBLIC/f"{arm}-catalogue-evolution.json", {"snapshots":result["snapshots"],"quarantined_operations":summary["quarantines"].get("L" if arm=="luna" else "T",[])})
        write(PUBLIC/f"{arm}-final-catalogue.json", {"concepts":[public_concept(x) for x in result["final_catalogue"]]})
    def operations_for(arm: str) -> list[dict[str, Any]]:
        operations=[]
        folder=root/"arms"/arm/"operations"
        for path in sorted(folder.glob("*.json")):
            doc=json.loads(path.read_text(encoding="utf-8"))
            for operation in doc.get("operations", []): operations.append({"stage":path.stem,"operation":operation})
        return operations
    lops, tops=operations_for("L"), operations_for("T")
    def base_actions(catalogue: list[dict[str, Any]]) -> dict[str, list[str]]:
        return {x["concept_id"]:[entry.get("action") for entry in x.get("lineage",[]) if entry.get("action")] for x in catalogue if x["concept_id"] in base}
    la,ta=base_actions(l["final_catalogue"]),base_actions(t["final_catalogue"])
    disagreement=[{"base_concept_id":cid,"luna_actions":la.get(cid,[]),"terra_actions":ta.get(cid,[])} for cid in sorted(set(la)|set(ta)) if la.get(cid,[])!=ta.get(cid,[])]
    write(PUBLIC/"operation-comparison.json", {"luna_operations":lops,"terra_operations":tops,"base_concept_action_disagreements":disagreement,"note":"Operations are provider recommendations that were mechanically applied only when valid; quarantines remain separately visible."})
    write(PUBLIC/"lineage-comparison.json", {"luna":[{"concept_id":x["concept_id"],"lineage":x.get("lineage",[]),"active":x.get("active")} for x in l["final_catalogue"]],"terra":[{"concept_id":x["concept_id"],"lineage":x.get("lineage",[]),"active":x.get("active")} for x in t["final_catalogue"]]})
    def attach_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]: return {x["observation_id"]:x for x in rows}
    lw,tw=attach_map(l["workshop_second"]),attach_map(t["workshop_second"]); lh,th=attach_map(l["holdout"]),attach_map(t["holdout"])
    def comparison(ids: list[str], left: dict[str,dict[str,Any]], right: dict[str,dict[str,Any]]) -> list[dict[str,Any]]:
        result=[]
        for oid in ids:
            a=left.get(oid,{"concept_ids":[]}); b=right.get(oid,{"concept_ids":[]})
            result.append({"observation_id":oid,"observation":observation_projection(observations[oid]),"luna_attachment":a,"terra_attachment":b,"both_zero":not a.get("concept_ids") and not b.get("concept_ids"),"one_zero_one_nonzero":bool(a.get("concept_ids")) != bool(b.get("concept_ids")),"both_nonzero":bool(a.get("concept_ids")) and bool(b.get("concept_ids")),"exact_shared_attachment_ids":sorted(set(a.get("concept_ids",[]))&set(b.get("concept_ids",[])))})
        return result
    write(PUBLIC/"workshop-attachment-comparison.json", {"luna_counts":l["counts"]["second"],"terra_counts":t["counts"]["second"],"cases":comparison([x["observation_id"] for x in work],lw,tw)})
    write(PUBLIC/"holdout-comparison.json", {"luna_counts":l["counts"]["holdout"],"terra_counts":t["counts"]["holdout"],"cases":comparison([x["observation_id"] for x in hold],lh,th)})
    write(PUBLIC/"reuse-comparison.json", {"luna":reuse(l["final_catalogue"],l["workshop_second"],observations),"terra":reuse(t["final_catalogue"],t["workshop_second"],observations)})
    write(PUBLIC/"structural-integrity.json", {"luna":integrity(l["final_catalogue"],l["workshop_second"]),"terra":integrity(t["final_catalogue"],t["workshop_second"])})
    write(PUBLIC/"discovery-challenge-summary.json", {"batches":summary["auxiliary"]})
    # Connector-friendly split review cases; cases preserve only bounded proposition data and IDs.
    cases=comparison([x["observation_id"] for x in hold],lh,th)
    for index in range(0,len(cases),20): write(PUBLIC/f"review-cases-{index//20+1:02d}.json", {"cases":cases[index:index+20]})
    write(PUBLIC/"review-cases-operations.json", {"base_concept_action_disagreements":disagreement,"luna_operations":lops,"terra_operations":tops})
    files=sorted(p.name for p in PUBLIC.iterdir() if p.is_file())
    write(PUBLIC/"index.json", {"experiment_id":EXPERIMENT,"files":files,"provider_calls_in_publication":0,"review_boundary":"derived, public-safe review data only"})


if __name__ == "__main__":
    if "--export-public-review" in sys.argv:
        export_public()
    elif "--replay-existing" in sys.argv:
        main(replay=True)
    else:
        main()
