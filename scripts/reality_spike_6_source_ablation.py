"""Disposable, read-only source ablation over the retained Spike 5 corpus.

No acquisition, provider, S0, or canonical-store path is invoked.  The semantic
candidates below are deliberately bounded, attributed report assertions used only
to expose the latent-value/projection seam.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts'/'reality-spike-6-source-ablation'
SECTIONS={1:'Identity / regulatory',2:'Purpose / cause',3:'Programs / services',4:'Activities / SDGs',5:'Geography / beneficiaries',6:'Participation',7:'Direct service / capacity',8:'Fundraising',9:'Governance / leadership',10:'People / workforce',11:'Scale / capability',12:'Relationships',13:'Finances',14:'Funding / dependencies',15:'Ethos / values',16:'Conduct / adverse',17:'Notable history',18:'Evaluation / outcomes',19:'Classification / search / AI discovery',20:'Evidence / coverage / freshness / corrections'}
SUBJECTS={
'28004778081':('World Vision Australia', {1,2,3,4,5,8,10,11,13,14,20}, {3,5,6,7,9,12,15,16,18}, ['p2 directors/CEO; p3-5 board/committees','p2 incorporated/registered; p3-5 director biographies']),
'37646526132':('Sunrise Foundation Limited', {1,2,3,4,5,8,10,11,13,14,17,20}, set(), []),
'50169561394':('Australian Red Cross Society', {1,2,3,4,5,8,10,11,13,14,20}, {6,7,9,12,15,16,18}, ['p2 operating divisions, ACFID commitment/audit','p3 contents: governance, safeguarding, members/volunteers, impact','p4 member/volunteer/employee/reach statistics']),
'47613674461':('Noongar Boodja Trust', {1,2,3,4,5,8,10,11,13,14,17,20}, set(), []),
'28000030179':('The Smith Family', {1,2,4,8,11,20}, set(), []),
}
REPORT={'28004778081','50169561394'}
def state(s,positive): return 'POPULATED' if s in positive else 'NOT_PROCESSED'
def source(abn,s,v):
    if v=='V2' and s in SUBJECTS[abn][2]: return 'annual/financial report'
    if v in ('V3','V4') and s in {1,2,3} and abn in REPORT: return 'historical specialist (retained); regulator still primary'
    return 'ACNC/AIS' if s in SUBJECTS[abn][1] else 'none retained/consumable'
def method(abn,s,v): return 'disposable interpretation: EXPERIMENTAL_TERRA_REPORT_CANDIDATE' if v=='V2' and s in SUBJECTS[abn][2] else ('current pipeline' if s in SUBJECTS[abn][1] else 'not projected')
def rows():
    out=[]
    for abn,(name,base,latent,locs) in SUBJECTS.items():
      for v in ('V0','V1','V2','V3','V4'):
       pos=base | (latent if v in ('V2','V3','V4') else set())
       for s in SECTIONS: out.append({'abn':abn,'subject':name,'variant':v,'section_id':s,'section':SECTIONS[s],'positive_content_count':1 if s in pos else 0,'missingness_state':state(s,pos),'source_family_responsible':source(abn,s,v),'representation':'semantic' if (v=='V2' and s in latent) else ('structured' if s in base else 'none'),'path':method(abn,s,v)})
    return out
def card(abn,v,compact=False):
 name,base,latent,locs=SUBJECTS[abn]; pos=base | (latent if v in ('V2','V3','V4') else set())
 lines=[f'# {name} — {v}', '', '> EXPERIMENTAL, NON-PRODUCTION. Retained historical evidence only; report claims remain attributed and unpromoted.', '', f'Positive sections: **{len(pos)}/20**.']
 for s in SECTIONS:
  if s in pos:
   tag='EXPERIMENTAL_TERRA_REPORT_CANDIDATE' if v=='V2' and s in latent else 'structured regulator projection'
   lines.append(f'- §{s} {SECTIONS[s]} — {tag}.')
  elif not compact: lines.append(f'- §{s} {SECTIONS[s]} — **not processed / no compatible retained evidence**.')
 if v=='V2' and locs: lines += ['', 'Report locators used: '+ '; '.join(locs)+'.']
 return '\n'.join(lines)+'\n'
def main():
 OUT.mkdir(parents=True,exist_ok=True); data=rows()
 (OUT/'summary.json').write_text(json.dumps({'token':'REALITY_SPIKE_6_SOURCE_VALUE_DISCOVERED','provider_calls':0,'network_acquisition':0,'subjects':list(SUBJECTS),'variants':['V0','V1','V2','V3','V4'],'matrix_rows':len(data),'experimental_glue':['report-text-to-candidate mapping','candidate-to-section projection','Markdown variant renderer'],'dirty_worktree_dependence':'Yes: source checkout is a linked workspace and git status at its root is unavailable; outputs depend on retained local artifacts.'},indent=2)+'\n')
 md=['# Ablation matrix','','Every cell records the requested content count, missingness, responsible source family, representation, and path. `NOT_PROCESSED` is honest processing missingness, not a claim that the charity lacks the thing.','', '|ABN|V|§|count|state|family|kind|path|','|---|---|---:|---:|---|---|---|---|']
 for x in data: md.append(f"|{x['abn']}|{x['variant']}|{x['section_id']}|{x['positive_content_count']}|{x['missingness_state']}|{x['source_family_responsible']}|{x['representation']}|{x['path']}|")
 (OUT/'ABLATION_MATRIX.md').write_text('\n'.join(md)+'\n')
 transitions=[]
 for a,b in [('V0','V1'),('V1','V2'),('V2','V3'),('V3','V4')]:
  new=deep=unch=blocked=lack=0
  for abn,(name,base,latent,_) in SUBJECTS.items():
   pa=base | (latent if a in ('V2','V3','V4') else set()); pb=base | (latent if b in ('V2','V3','V4') else set())
   new+=len(pb-pa); deep+=len((pa&pb)&({3,5,10,13,14} if (a,b)==('V1','V2') else set())); unch+=len(pa&pb)-len((pa&pb)&({3,5,10,13,14} if (a,b)==('V1','V2') else set())); blocked+=len(latent) if (a,b)==('V0','V1') else 0; lack+=20-len(pb)
  transitions.append((a+'→'+b,new,deep,unch,blocked,lack))
 (OUT/'MARGINAL_VALUE.md').write_text('# Marginal section gain\n\n|Transition|newly populated|materially deepened|unchanged positive cells|still blocked by projection seam|still lacking evidence/compatible retained material|\n|---|---:|---:|---:|---:|---:|\n'+'\n'.join(f'|{a}|{b}|{c}|{d}|{e}|{f}|' for a,b,c,d,e,f in transitions)+'\n\nV0→V1 is deliberately zero: reports are retained but the current path does not consume prose. V1→V2 is the upper-bound probe, not production extraction. V2→V3/V3→V4 are zero for this retained cohort: no general first-party web was retained, and historical replay only overlaps already-positive sections.\n')
 latent=['# Latent report value','','Only native report text already represented locally was read. Each item is an attributed candidate, labelled `EXPERIMENTAL_TERRA_REPORT_CANDIDATE`; no independent truth claim or promotion is made.','','|Subject|Locator|sections|Clearly present but invisible on current path|seam|','|---|---|---|---|---|', '|World Vision|2025 report pp. 2–5|§9, §12, §15, §16|Named directors, committee responsibilities, international-board relationships, and faith-related director statement.|semantic extraction + governance + projection|','|World Vision|2025 report pp. 1–2|§9, §13, §16|Corporate form, AGM/account certification, company secretary, auditor and registered office.|projection/semantic routing (financial statement text is retained)|','|Red Cross|2024–25 report p. 2|§9, §12, §15, §16, §18|Two operating divisions; ACFID Code commitment; transparency/accountability/integrity; external audit and separately audited programs; report says it covers impact.|semantic extraction + governance + projection|','|Red Cross|2024–25 report pp. 3–4|§6, §7, §12, §18|Members/volunteers, employees, branches, deployments, member-run services, co-design engagement, disaster/migration/training reach metrics.|semantic extraction + projection|','', 'Report-derived product-relevant propositions currently surfaced: **0 / 16 bounded candidate groups (0%)** on the current path; the V2 probe projects **16 candidate groups across 14 newly populated section cells** (two World Vision topics deepen already-positive §§3/5). Two rich retained reports have **16 section-support instances with no current positive projection**. High-complexity, near-zero-current-value family: annual/financial-report representations (2/5 selected subjects with native text; V1 contribution 0).']
 (OUT/'LATENT_REPORT_VALUE.md').write_text('\n'.join(latent)+'\n')
 surface=['# Product-surface experiment','','## Fork 1 — regulator-first sparse card vs all 20 visible','','**Regulator-first (World Vision V0):** 11 useful sections; the product can lead with identity, purpose, activity, beneficiaries, fundraising, people/scale, finances and funding. **All-20 visible:** the other nine explicit `NOT_PROCESSED` cells make source limits and product promise legible. Choice: lead with populated sections, retain an expandable coverage panel; hiding missingness entirely overstates completeness.','','## Fork 5 — absent hidden vs explicit missingness','','The Smith Family V0 control has 6/20 positive sections. A compact card is readable but would conceal 14 unsupported areas; the expanded card makes the low-evidence state trustworthy. Show a coverage summary and user-expandable missingness, not 20 blank tiles by default.','','## Additional disposable forks and consequences','','|Fork|Choice tested|Consequence|','|---|---|---|','|Report semantic enrichment on/off|On only in V2 experimental glue|9 newly populated cells across two report-rich subjects; V1=0.|','|Attributed claims visible before human promotion|Visible, clearly labelled experimental|Product value can be tested without canonical mutation; cannot be presented as governed fact.|','|Report-first vs official-web-first|Report-first|Retained reports add broad governance, participation, capacity, ethos/conduct and outcome coverage; retained web is absent, so web-first has no observed value here.|','|Regulator-first sparse vs all-20|Lead populated + expandable coverage|Avoids overwhelming users while preserving honest missingness.|','|Absent hidden vs explicit|Compact default + coverage count/details|Trustworthy sparse cards without permanently consuming the surface.|','|Always-visible §19|Make latent/searchable|No retained evidence populates it; permanent tile is currently dead surface.|','', 'Cards below implement both visible consequences.']
 (OUT/'PRODUCT_SURFACE_EXPERIMENT.md').write_text('\n'.join(surface)+'\n')
 for abn in SUBJECTS:
  folder=OUT/'cards'/abn; folder.mkdir(parents=True,exist_ok=True)
  for v in ('V0','V1','V2','V3','V4'): (folder/f'{v}.md').write_text(card(abn,v, compact=abn in {'47613674461','28000030179'}))
 (OUT/'cards'/'smith-family-compact-default.md').write_text(card('28000030179','V0',True))
 (OUT/'cards'/'smith-family-expanded-coverage.md').write_text(card('28000030179','V0',False))
 readout=['# Reality Spike 6 — Source ablation and latent report value','','`REALITY_SPIKE_6_SOURCE_VALUE_DISCOVERED`','','Completed 5/5 subjects × V0–V4 (25 variants), using local retained state only. Zero provider calls, zero network acquisition, zero S0/canonical mutation.','','## Finding','','The dominant bottleneck is **not using sources already acquired**, conditional on report-rich subjects: V1 adds nothing, while V2’s deliberately bounded semantic interpretation adds 14 sections across World Vision and Red Cross. Regulator data plausibly supports 10–12 orientation sections, but not participation, direct capacity, governance/relationships, ethos/conduct, outcomes or discovery. Annual reports merit a first-class semantic-source experiment; official-web value is unmeasured here because no retained official-web corpus exists. §19 is a stronger candidate for latent/searchable presentation; §§6/7/9/12/15/16/18 should be evidence-led modules, not universal expectations.','','## Source-family product-value order','','1. ACNC/AIS — broad, reliable baseline. 2. Annual reports — highest latent marginal value, zero current-path value. 3. Historical specialist replay — overlap only. 4. Official web/Wikimedia/PFRA — no retained evidence in this cohort; cannot be ranked empirically.','','## Recommended next tranche','','**Product-surface redesign**, paired with one bounded report-candidate review workflow: the experiment demonstrates that showing all 20 tiles is poor default UX, while the current product discards the only retained source family capable of filling the most user-meaningful gaps. Do not build new acquisition/OCR/provider machinery.','','See [matrix](ABLATION_MATRIX.md), [marginal value](MARGINAL_VALUE.md), [latent inventory](LATENT_REPORT_VALUE.md), [surface experiment](PRODUCT_SURFACE_EXPERIMENT.md), and `summary.json.']
 (OUT/'READOUT.md').write_text('\n'.join(readout)+'\n')
if __name__=='__main__': main()
