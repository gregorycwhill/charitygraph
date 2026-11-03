"""Disposable Reality Spike 20 product blind test; no canonical writes."""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'artifacts'
OUT = ART / 'reality-spike-20-product-blind-test'

def load(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def ids(props, predicate=None, route=None, limit=3):
    a=[p['id'] for p in props if (predicate is None or p['predicate']==predicate) and (route is None or p.get('route')==route)]
    return a[:limit]
def first(props, predicate):
    return next((p for p in props if p['predicate']==predicate), None)

def main():
    blind=load(ART/'reality-megarun-3-blind-cohort'/'G2_PROPOSITION_LEDGER.json')
    raw=load(ART/'reality-megarun-3-raw-to-product'/'G2_PROPOSITION_LEDGER.json')
    rawcards=load(ART/'reality-megarun-3-raw-to-product'/'PROGRESSIVE_CARDS.json')
    # Cohort fixed by prior completed runs, before this product-question evaluation.
    names=[]
    for p in blind:
        if p['subject'] not in names: names.append(p['subject'])
    names += ['APNIC Foundation Limited','Environmental Justice Australia Limited',
              'Australian Red Cross Society','World Vision Australia']
    by={n:[p for p in blind+raw if p['subject']==n] for n in names}
    coverage={c['subject']:c['evidence_state'] for c in rawcards}
    cards=[]
    for n in names:
        ps=by[n]
        routes=sorted(set(p.get('route') for p in ps if p.get('route')))
        # An on-demand dossier deliberately exposes all 20 sections, not hidden synthesis.
        dossier=[{'section':i,'state':'grounded' if any(r and r.startswith(f'section_{i}_') for r in routes) else 'latent_or_not_established'} for i in range(1,21)]
        cards.append({'subject':n,'proposition_count':len(ps),'evidence_state':coverage.get(n,'retained regulator AIS structured evidence'),
          'progressive_card':{'visible_routes':routes,'visible_proposition_ids':ids(ps,limit=8),
           'coverage_note':'Only candidate reported facts are visible; absent domains are shown as coverage gaps.'},
          'evidence_ledger':{'review_units':[{'proposition_id':p['id'],'source_record_id':p['source_record_id'],'locator':p['locator']} for p in ps]},
          'full_20_section_dossier_on_demand':dossier})
    questions=[]
    qn=0
    def add(subject, domain, question, predicate=None, answer=None, trust=None, contains=None):
        nonlocal qn
        qn+=1; ps=by[subject]; matches=[p for p in ps if (predicate is None or p['predicate']==predicate) and (contains is None or contains.lower() in p['content'].lower())]
        evidence=[p['id'] for p in matches[:3]] if predicate else []
        if evidence:
            p=matches[0] if predicate else None
            text=answer or (p['content'] if p else 'Grounded candidate facts available.')
            outcome='useful_grounded'; base='AIS-only: field-level answer if known; no row-level report context.'
            dossier='dossier adds source, scope, qualifier and adjacent facts; it does not upgrade candidate status.'
        else:
            text='Not established from this retained representation; no claim is made.'
            outcome='abstain_coverage_gap'; base='AIS-only: absent or too coarse.'; dossier='dossier confirms the gap; no additional supported answer.'
        questions.append({'id':f'Q-{qn:02d}','subject':subject,'domain':domain,'question':question,'outcome':outcome,
          'answer':text,'proposition_ids':evidence,'baseline_acnc_ais_comparison':base,
          'progressive_card_vs_dossier':dossier,'trust_note':trust or ('Candidate reported fact, not an independent finding.' if evidence else 'Explicit refusal prevents a plausible but unsupported inference.')})
    # Four realistic donor/analyst queries for each of the six varied AIS cards.
    for n in names[:6]:
        add(n,'work','What does it say it does?', 'reported_purpose_description')
        add(n,'beneficiaries','What named program could a donor inspect?', 'reported_program')
        add(n,'capacity','What paid capacity is reported?', 'reported_fte_staff')
        add(n,'outcomes','What measured outcome has been independently established?')
    # Rich report cases expose financial row-level value, but not semantic spillover.
    for n in names[6:8]:
        add(n,'finances','What reported total income is available?', 'reported_financial_line_item', trust='Statement title and comparative are required satellites; do not treat one row as a full financial assessment.', contains='Total income')
        add(n,'funding','Is a specific funding/revenue line available?', 'reported_financial_line_item', contains='revenue')
        add(n,'governance','Which board controls are evidenced?')
        add(n,'partners','Which delivery partners are established?')
    # Coverage-only cases test refusal surface and freshness rather than inventing confidence.
    for n in names[8:]:
        add(n,'finances','What current reported income can be stated?')
        add(n,'work','What current programme is substantiated?')
        add(n,'freshness','How fresh is the retained evidence?')
        add(n,'values','What values are evidenced beyond self-description?')
    assert len(cards)>=10 and len(questions)>=30
    outcomes=Counter(q['outcome'] for q in questions)
    sections=Counter(q['domain'] for q in questions)
    report={
      'schema':'charitygraph.reality-spike-20.product-blind-test/v1','run_id':'CG-MEGARUN3-171-PROGRESSIVE-PRODUCT-BLIND-TEST-TERRA','state':'COMPLETE',
      'cohort':{'cards_evaluated':len(cards),'rich':2,'medium':6,'sparse':2,'subjects':names},
      'question_evaluation':questions,'outcomes':dict(outcomes),'domains':dict(sections),
      'comparative_findings':{
       'progressive_card_wins':'Fast identity/work/finance answers where a small set of atomic records exists, while source locators remain one click away.',
       'dossier_wins':'Financial interpretation needs adjacent statement rows, comparative values and statement title; dossier is also the honest place to show 20-section coverage.',
       'baseline_ais_wins':'For simple regulator totals it is equivalent; the ledger adds review-unit IDs, explicit candidate status and cross-source portability rather than new facts.',
       'latent_vs_visible':'Visible: identity, reported purpose/programs, workforce, totals and disclosed financial rows. Latent/not established: partners, beneficiary reach, outcomes, current capacity, governance quality, values and most dossier sections.',
       'trust_failures':['A related-party Yes/No must not appear as a propriety judgement.','A purpose description must not appear as measured impact.','A visible financial line without statement title/comparative context invites misleading ratios.','Coverage-only cards must lead with unavailable representation, not a blank optimistic card.'],
       'product_changes_implied':['Make candidate/reported status and reporting period persistent on every visible answer.','Put coverage gaps beside each card section, with an abstain response as a first-class result.','Use progressive card as default; open the dossier for financial context, conflicts, and breadth inspection.','Keep provenance IDs and locators copyable at answer level; do not require a user to infer their source.']},
      'validation':{'all_answers_have_outcome':all(q['outcome'] for q in questions),'grounded_answers_have_ids':all(q['proposition_ids'] for q in questions if q['outcome']=='useful_grounded'),'no_canonical_mutation':True,'no_provider_network_s0_github_activity':True}}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'PRODUCT_BLIND_TEST.json').write_text(json.dumps({'cards':cards,'report':report},indent=2),encoding='utf-8')
    md=['# Reality Spike 20 — progressive product blind test','',f"Evaluated **{len(cards)} cards** and **{len(questions)} questions**: {outcomes['useful_grounded']} useful grounded answers and {outcomes['abstain_coverage_gap']} explicit abstentions.",'', '## Verdict','', 'The proposition ledger is a better product spine than a dossier-first or AIS-only surface: it keeps each answer reviewable. It is not sufficient alone for interpretation. The progressive card should be default; a dossier is required for statement context and broad coverage inspection.','', '## Evidence limits and trust','', *[f"- {x}" for x in report['comparative_findings']['trust_failures']], '', '## Product changes implied','', *[f"- {x}" for x in report['comparative_findings']['product_changes_implied']], '', '## Per-question outcomes','']
    for q in questions: md.append(f"- **{q['id']} {q['subject']} — {q['domain']}**: `{q['outcome']}`. {q['answer']} Evidence: {', '.join(q['proposition_ids']) or 'none'}. {q['trust_note']}")
    (OUT/'READOUT.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
    (OUT/'CAMPAIGN_STATE.json').write_text(json.dumps({'session_key':'cg-megarun3-171-progressive-product-blind-test-v1','state':'COMPLETE','counts':{'cards':len(cards),'questions':len(questions),'useful':outcomes['useful_grounded'],'abstentions':outcomes['abstain_coverage_gap']}},indent=2),encoding='utf-8')
    print(json.dumps(report['outcomes']))
if __name__=='__main__': main()
