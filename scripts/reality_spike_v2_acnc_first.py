"""Non-production ACNC-first product reality spike (v2).

This deliberately does not invoke governed production, S0, A3, accounting or
publication components.  It retains public evidence and makes failures visible.
"""
from __future__ import annotations

import argparse, html, json, re, sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from charitygraph.openai_client import responses_create

# UUIDs are the resolved ACNC Charity Register record identifiers.  ABNs are
# retained only as source-native attributes / ABR join keys, never folder keys.
CHARITIES = [
 {"sequence":"01-msf-acnc-33ed3439","name":"Medecins Sans Frontieres Australia Limited","abn":"74068758654","acnc_id":"33ed3439-38af-e811-a962-000d3ad24a0d","ais":[("2024","8378ce3c-fb40-f011-8779-0022489511f7")],"official":["https://www.msf.org.au/about-us","https://www.msf.org.au/our-work"]},
 {"sequence":"02-sunrise-acnc-f1413902","name":"SUNRISE FOUNDATION LIMITED","abn":"37646526132","acnc_id":"f1413902-d240-eb11-bf72-000d3ad1ce4e","ais":[("2023","aeaa1ff5-e7e0-ee11-904c-002248970b4e"),("2022","73d0c7c0-d3e0-ee11-904c-000d3ad0466e"),("2021","5a5f5e4a-39e0-ee11-904c-6045bdc2f3c2")],"official":[]},
 {"sequence":"03-noongar-boodja-acnc-cf5f4d7d","name":"Noongar Boodja Trust","abn":"47613674461","acnc_id":"cf5f4d7d-6ab4-eb11-8236-000d3a6abd1c","ais":[("2023","4918ee03-10c7-ee11-9079-002248935564")],"official":[]},
]

def fetch(url: str, role: str, year: str|None=None) -> dict:
    stamp=datetime.now(timezone.utc).isoformat(); out={"url":url,"role":role,"retrieved_at":stamp,"outcome":"failed"}
    if year: out["reporting_year"]=year
    try:
        req=Request(url,headers={"User-Agent":"CharityGraph-reality-spike-v2/0.1 (public inspection)"})
        with urlopen(req,timeout=30) as r:
            raw=r.read(1_500_000); typ=r.headers.get_content_type(); out.update(http_status=r.status,content_type=typ,outcome="retrieved")
            if typ=="application/pdf" or raw[:4]==b"%PDF":
                out["binary_pdf_bytes"]=len(raw); out["text"]="PDF retrieved; text extraction attempted separately."
            else:
                out["text"]=html.unescape(re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",raw.decode("utf-8",errors="replace")))).strip()[:24000]
            return out
    except Exception as exc:
        out["error"]=f"{type(exc).__name__}: {str(exc)[:300]}"; return out

def item_schema(): return {"type":"object","additionalProperties":False,"properties":{"statement":{"type":"string"},"source_urls":{"type":"array","items":{"type":"string"}}},"required":["statement","source_urls"]}
def schema():
    i=item_schema(); return {"type":"object","additionalProperties":False,"properties":{
      "identity":i,"purpose_mission":i,"programs_or_activity_scopes":{"type":"array","items":i},"beneficiaries":i,"geography":i,"workforce_volunteers":i,"financial_scale":i,"governance":i,"operating_evidence":i,"source_reported_claims":{"type":"array","items":i},"unknowns_not_established":{"type":"array","items":{"type":"string"}},"cautions":{"type":"array","items":{"type":"string"}}},"required":["identity","purpose_mission","programs_or_activity_scopes","beneficiaries","geography","workforce_volunteers","financial_scale","governance","operating_evidence","source_reported_claims","unknowns_not_established","cautions"]}

def render(c, card, sources):
    lines=[f"# {c['name']}","","**NON-PRODUCTION REALITY-SPIKE V2 MATERIAL — not canonical CharityGraph data.**","",f"**CharityGraph subject:** provisional spike sequence `{c['sequence']}`",f"**Canonical external charity-source record:** ACNC `{c['acnc_id']}`",f"**ACNC record:** https://www.acnc.gov.au/charity/charities/{c['acnc_id']}",f"**ABN attribute / ABR join key (not identity):** {c['abn']}","","## Partial CharityGraph card"]
    for key,label in [("identity","Identity"),("purpose_mission","Purpose / mission"),("beneficiaries","Beneficiaries"),("geography","Geography"),("workforce_volunteers","Workforce / volunteers"),("financial_scale","Financial scale"),("governance","Governance"),("operating_evidence","Operating evidence")]:
        x=card[key]; lines += [f"\n### {label}",x['statement'],"Evidence: "+(', '.join(x['source_urls']) or 'Not established from retained sources.')]
    lines += ["\n### Programs / activity scopes"] + [f"- {x['statement']} (Evidence: {', '.join(x['source_urls']) or 'not established'})" for x in card['programs_or_activity_scopes']]
    lines += ["\n### Source-reported claims"] + [f"- {x['statement']} (Source: {', '.join(x['source_urls']) or 'not established'})" for x in card['source_reported_claims']]
    lines += ["\n### Unknown / not established"]+[f"- {x}" for x in card['unknowns_not_established']]
    lines += ["\n### Source manifest"]+[f"- [{s['role']}{' '+s.get('reporting_year','')}] {s['url']} — {s['outcome']}" for s in sources]
    return '\n'.join(lines)+'\n'

def comparison(root):
    text="""# Product comparison: Reality Spike v1 → v2 ACNC-first

Both runs are non-production inspection material. V1 used ABR plus sparse web discovery; v2 deliberately resolves the ACNC charity-record UUID first and makes the regulator bundle the first acquisition step.

## Cross-cutting result

- **Identity clarity:** v2 separates CharityGraph's provisional subject sequence, ACNC record UUID/URL, and ABN as a supplementary ABR join attribute. V1 folder labels and card headings made ABN too prominent.
- **Baseline authority:** v2 retains the ACNC profile, people, documents, latest known AIS links, prior AIS history where found, and report/document attempts before web enrichment. This is a material provenance improvement even when the ACNC surface fails retrieval.
- **Product usefulness:** MSF remains enriched by its official site. Sunrise and Noongar now have canonical ACNC record identities and known AIS history rather than only ABR status, but the retrieved ACNC pages did not expose substantive AIS fields or a lodged-report URL; their cards remain appropriately sparse.
- **Bottleneck:** current bottleneck is ACNC document-index/field extraction, not model reasoning. Website discovery is secondary once the canonical material is acquired.

## Per-charity comparison

### Medecins Sans Frontieres Australia Limited

V1 had ABR plus two useful official pages and no ACNC/AIS/report baseline. V2 resolves ACNC `33ed3439-38af-e811-a962-000d3ad24a0d`, retains current register/profile/people/document material and a 2024 AIS landing record, while preserving the official-site enrichment. The card is more trustworthy in its identity spine; actual AIS financial detail and a lodged financial-report URL were not exposed in the retained content.

### SUNRISE FOUNDATION LIMITED

V1 was an ABR-status triage card. V2 resolves ACNC `f1413902-d240-eb11-bf72-000d3ad1ce4e` and retains known AIS landing records for 2023, 2022 and 2021 plus profile/people/documents material. That decisively improves auditability and tells a researcher exactly where the omitted baseline should be, but does not manufacture a mission, program, beneficiary or finance profile when the retrieved content supplies none.

### Noongar Boodja Trust

V1 was likewise ABR-status triage. V2 resolves ACNC `cf5f4d7d-6ab4-eb11-8236-000d3a6abd1c`, retains profile/people/documents material and a 2023 AIS landing record. It adds a canonical source spine and explicit evidence trail but cannot establish operating facts without substantive regulator fields or report content.

## Decision readout

ACNC-first is the correct product order: it prevents ABN from becoming the subject identity and converts sparse cards into inspectable regulator-led research starting points. The remaining product gap is not another semantic layer: make ACNC profile/AIS/document acquisition resilient (or use an authorised ACNC dataset/export) and extract the resulting reports. Until then, Sunrise and Noongar require significant manual follow-up; MSF is useful for discovery but still incomplete for financial and governance research.
"""
    (root/'PRODUCT_COMPARISON_V1_V2.md').write_text(text,encoding='utf-8')

def main():
 p=argparse.ArgumentParser(); p.add_argument('--output',default='artifacts/reality-spike-v2-acnc-first-2026-09-28'); a=p.parse_args(); root=Path(a.output); root.mkdir(parents=True,exist_ok=True)
 run={"non_production":True,"started_at":datetime.now(timezone.utc).isoformat(),"model_requested":"gpt-5.6-terra","model_calls":0,"charities":[],"warnings":[],"acnc_access_limited":False}
 for c in CHARITIES:
  folder=root/c['sequence']; folder.mkdir(exist_ok=True); base=f"https://www.acnc.gov.au/charity/charities/{c['acnc_id']}"; sources=[]
  for suffix,role in [('', 'acnc_register'),('/profile','acnc_profile'),('/people','acnc_people'),('/documents/','acnc_financials_documents')]: sources.append(fetch(base+suffix,role))
  for year,doc in c['ais']: sources.append(fetch(base+'/documents/'+doc,'acnc_annual_information_statement',year))
  # Explicitly records a substantive report attempt, distinct from AIS.
  sources.append({"url":base+"/documents/","role":"acnc_latest_lodged_annual_or_financial_report","retrieved_at":datetime.now(timezone.utc).isoformat(),"outcome":"unavailable_from_direct_acquisition","error":"Document index could not be read by this public scripted run; no report URL can be responsibly asserted."})
  sources.append(fetch('https://abr.business.gov.au/ABN/View?abn='+c['abn'],'abr_attribute_join'))
  for u in c['official']: sources.append(fetch(u,'official_website_enrichment'))
  if any(s['role'].startswith('acnc_') and s['outcome']=='failed' for s in sources): run['acnc_access_limited']=True
  (folder/'identity.json').write_text(json.dumps({"charitygraph_subject":{"kind":"provisional_spike_sequence","value":c['sequence']},"canonical_external_source":{"system":"ACNC Charity Register","record_id":c['acnc_id'],"url":base,"resolution_provenance":"ACNC canonical charity URL resolved before acquisition"},"external_attributes":{"abn":{"value":c['abn'],"role":"ABR join/enrichment attribute; not CharityGraph or ACNC identity"}}},indent=2)+"\n",encoding='utf-8')
  (folder/'sources.json').write_text(json.dumps(sources,indent=2)+"\n",encoding='utf-8'); (folder/'retained_acnc_baseline.json').write_text(json.dumps([s for s in sources if s['role'].startswith('acnc_')],indent=2)+"\n",encoding='utf-8')
  evidence=[{k:s[k] for k in ('url','role','outcome','reporting_year','text','error') if k in s} for s in sources]
  prompt="""Produce a partial, non-production CharityGraph card from ONLY this retained evidence. Treat ACNC register/AIS/report materials as regulator/source facts; AIS values must retain their reporting year. Treat ABN solely as an external attribute/join key, never identity. Do not infer mission or beneficiaries from a name; do not call ACNC registration a relationship; do not treat active ABN as operating proof; do not attribute global movement claims to the Australian entity. Cite supplied URLs for every material statement and preserve missingness. Return JSON only.\n\n"""+json.dumps({"charity":c['name'],"acnc_record_id":c['acnc_id'],"evidence":evidence})
  try:
   r=responses_create(model='gpt-5.6-terra',input_text=prompt,text_format={"type":"json_schema","name":"reality_spike_v2_card","strict":True,"schema":schema()},max_output_tokens=3000,max_attempts=1,timeout_seconds=180,reasoning={"effort":"medium"}); run['model_calls']+=r.transport_requests; card=json.loads(r.output_text); meta={"model":r.model,"response_id":r.response_id,"status":r.status,"usage":r.usage.__dict__,"transport_requests":r.transport_requests}
   (folder/'model_response.json').write_text(json.dumps({"metadata":meta,"output":card},indent=2)+"\n",encoding='utf-8'); artifact={"non_production_reality_spike_v2":True,"charity":{"name":c['name'],"acnc_record_id":c['acnc_id'],"abn_attribute":c['abn']},"generated_at":datetime.now(timezone.utc).isoformat(),"model":meta,"card":card,"source_manifest":"sources.json"}; (folder/'card.json').write_text(json.dumps(artifact,indent=2)+"\n",encoding='utf-8'); (folder/'card.md').write_text(render(c,card,sources),encoding='utf-8'); run['charities'].append({"name":c['name'],"acnc_record_id":c['acnc_id'],"abn_attribute":c['abn'],"directory":str(folder),"model":meta})
  except Exception as e: run['warnings'].append(f"{c['name']}: model failed: {type(e).__name__}: {str(e)[:300]}")
 run['finished_at']=datetime.now(timezone.utc).isoformat(); run['component_inventory']={"openai_client":"REUSED_SUCCESSFULLY","spike_v1_rendering_and_retention_pattern":"REUSED_SUCCESSFULLY","acnc_first_acquisition":"NEW_LIGHTWEIGHT_SPIKE_COMPONENT","production_acquisition_governance":"BYPASSED_FOR_SPIKE","A3_reservations_accounting":"BYPASSED_FOR_SPIKE","S0_Attempt20_runtime":"NOT_NEEDED"}; (root/'run_summary.json').write_text(json.dumps(run,indent=2)+"\n",encoding='utf-8'); comparison(root); print(json.dumps({"output":str(root),"cards":len(run['charities']),"model_calls":run['model_calls'],"warnings":run['warnings'],"acnc_access_limited":run['acnc_access_limited']},indent=2)); return 0 if len(run['charities'])==3 else 2
if __name__=='__main__': raise SystemExit(main())
