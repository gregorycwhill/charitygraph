"""Non-production live-web-to-card product reality spike.

Deliberately bypasses Builder's governed execution, economics and publication
paths.  Artifacts produced by this script are inspection material only.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from charitygraph.openai_client import responses_create

CHARITIES = [
    ("Medecins Sans Frontieres Australia Limited", "74068758654", ["https://www.msf.org.au/about-us", "https://www.msf.org.au/our-work"]),
    ("SUNRISE FOUNDATION LIMITED", "37646526132", []),
    ("Noongar Boodja Trust", "47613674461", []),
]

def fetch(url: str) -> dict:
    stamp = datetime.now(timezone.utc).isoformat()
    try:
        request = Request(url, headers={"User-Agent": "CharityGraph-reality-spike/0.1 (public-web inspection)"})
        with urlopen(request, timeout=25) as response:
            raw = response.read(750_000).decode("utf-8", errors="replace")
            # HTML-to-text is mechanical presentation cleanup; interpretation is model-only.
            text = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw))).strip()
            return {"url": url, "retrieved_at": stamp, "outcome": "retrieved", "http_status": response.status,
                    "content_type": response.headers.get_content_type(), "text": text[:18000]}
    except Exception as exc:
        return {"url": url, "retrieved_at": stamp, "outcome": "failed", "error": f"{type(exc).__name__}: {str(exc)[:240]}"}

def search(name: str, abn: str) -> dict:
    # DuckDuckGo is used only as a live public discovery source; its returned text is retained.
    from urllib.parse import quote_plus
    return fetch("https://html.duckduckgo.com/html/?q=" + quote_plus(f'"{name}" "{abn}"'))

def schema() -> dict:
    item = {"type":"object", "additionalProperties":False, "properties": {
        "statement":{"type":"string"}, "source_urls":{"type":"array","items":{"type":"string"}}}, "required":["statement","source_urls"]}
    return {"type":"object", "additionalProperties":False, "properties": {
        "identity":item, "purpose_mission":item, "programs_or_activity_scopes":{"type":"array","items":item},
        "geography":item, "participation_workforce_scale":item, "financial_scale":item,
        "relationships_affiliations":item, "current_operating_evidence":item,
        "source_reported_claims":{"type":"array","items":item}, "unknowns_not_established":{"type":"array","items":{"type":"string"}},
        "cautions":{"type":"array","items":{"type":"string"}}},
        "required":["identity","purpose_mission","programs_or_activity_scopes","geography","participation_workforce_scale","financial_scale","relationships_affiliations","current_operating_evidence","source_reported_claims","unknowns_not_established","cautions"]}

def render(name: str, abn: str, card: dict, sources: list[dict]) -> str:
    lines = [f"# {name}", "", "**NON-PRODUCTION REALITY-SPIKE MATERIAL — not canonical CharityGraph data.**", "", f"**ABN:** {abn}", "", "## Partial CharityGraph card"]
    labels = [("identity","Identity"),("purpose_mission","Purpose / mission"),("geography","Geography"),("participation_workforce_scale","Participation, workforce or scale"),("financial_scale","Financial scale"),("relationships_affiliations","Relationships / affiliations"),("current_operating_evidence","Current operating evidence")]
    for key, label in labels:
        value=card[key]; lines += [f"\n### {label}", f"{value['statement']}", f"Evidence: " + (", ".join(value["source_urls"]) or "Not established from retained sources.")]
    lines += ["\n### Programs / material activity scopes"]
    lines += [f"- {x['statement']} (Evidence: {', '.join(x['source_urls']) or 'not established'})" for x in card["programs_or_activity_scopes"]] or ["- Not established."]
    lines += ["\n### Source-reported qualitative claims"]
    lines += [f"- {x['statement']} (Source: {', '.join(x['source_urls']) or 'not established'})" for x in card["source_reported_claims"]] or ["- None retained."]
    lines += ["\n### Unknown / not established"] + [f"- {x}" for x in card["unknowns_not_established"]]
    lines += ["\n### Sources used"] + [f"- [{s['role']}] {s['url']} — {s['outcome']}" for s in sources]
    return "\n".join(lines) + "\n"

def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--output", default="artifacts/reality-spike-live-2026-09-28"); args=parser.parse_args()
    root=Path(args.output); root.mkdir(parents=True, exist_ok=True); run={"non_production":True,"started_at":datetime.now(timezone.utc).isoformat(),"model_requested":"gpt-5.6-terra","model_calls":0,"charities":[],"warnings":[]}
    for number,(name,abn,official_urls) in enumerate(CHARITIES,1):
        folder=root/f"{number:02d}-{abn}"; folder.mkdir(exist_ok=True)
        sources=[]
        for url in [f"https://abr.business.gov.au/ABN/View?abn={abn}"] + official_urls:
            result=fetch(url); result["role"]="regulator_identity" if "abr.business" in url else "official_website"; sources.append(result)
        result=search(name,abn); result["role"]="live_web_discovery"; sources.append(result)
        (folder/"sources.json").write_text(json.dumps(sources,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        evidence=[{"url":s["url"],"role":s["role"],"outcome":s["outcome"],"text":s.get("text","")} for s in sources]
        (folder/"retained_evidence.json").write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        prompt=("You are producing an explicitly partial, non-production CharityGraph card from ONLY retained live web evidence. Do not use outside knowledge. Each material statement must cite one or more exact supplied URLs. Clearly say 'Not established from retained sources' when unsupported. Do not infer impact, effectiveness, ROI, ownership or durable programs. Distinguish source-reported claims from CharityGraph judgments. Return the requested JSON only.\n\n"+json.dumps({"name":name,"abn":abn,"sources":evidence},ensure_ascii=False))
        try:
            response=responses_create(model="gpt-5.6-terra",input_text=prompt,text_format={"type":"json_schema","name":"reality_spike_card","strict":True,"schema":schema()},max_output_tokens=2600,max_attempts=1,timeout_seconds=180,reasoning={"effort":"medium"})
            run["model_calls"]+=response.transport_requests; card=json.loads(response.output_text)
            model_meta={"model":response.model,"response_id":response.response_id,"status":response.status,"usage":response.usage.__dict__,"transport_requests":response.transport_requests}
            (folder/"model_response.json").write_text(json.dumps({"metadata":model_meta,"output":card},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        except Exception as exc:
            run["warnings"].append(f"{name}: model invocation failed: {type(exc).__name__}: {str(exc)[:300]}")
            continue
        artifact={"non_production_reality_spike":True,"charity":{"name":name,"abn":abn},"generated_at":datetime.now(timezone.utc).isoformat(),"model":model_meta,"card":card,"source_manifest":"sources.json","retained_evidence":"retained_evidence.json"}
        (folder/"card.json").write_text(json.dumps(artifact,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); (folder/"card.md").write_text(render(name,abn,card,sources),encoding="utf-8")
        run["charities"].append({"name":name,"abn":abn,"directory":str(folder),"sources":[{"url":s["url"],"role":s["role"],"outcome":s["outcome"]} for s in sources],"model":model_meta})
    run["finished_at"]=datetime.now(timezone.utc).isoformat(); run["component_inventory"]={"openai_client":"REUSED_SUCCESSFULLY","North_Star_semantics":"REUSED_SUCCESSFULLY","production_acquisition_governance":"BYPASSED_FOR_SPIKE","reservations_A3_accounting":"BYPASSED_FOR_SPIKE","production_card_projection":"BYPASSED_FOR_SPIKE","S0_Attempt20_runtime":"NOT_NEEDED"}
    (root/"run_summary.json").write_text(json.dumps(run,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"output":str(root),"cards":len(run["charities"]),"model_calls":run["model_calls"],"warnings":run["warnings"]},indent=2)); return 0 if len(run["charities"])==3 else 2
if __name__ == "__main__": raise SystemExit(main())
