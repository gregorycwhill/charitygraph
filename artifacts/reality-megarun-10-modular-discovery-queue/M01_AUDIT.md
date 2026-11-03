# M01 — twenty run-182 proposition audit

Consumed: `charitygraph/scripts/run_megarun8b_direct_semantic.py` and the three cited runtime representations: `C:\CharityGraph-runtime\reality-megarun-8-rich-semantic-furnace\representations\australian-red-cross-9.txt`, `world-vision-australia-11.txt`, and `the-smith-family-41.txt`.

Direct source-text check by this agent. “Entailed” does not rehabilitate the predecessor: its claim list was hard-coded.

| # | Prior proposition | Result | Reason |
|---|---|---|---|
|1|Red Cross supports disaster preparedness, relief and recovery|Entailed/useful|Explicit organisation work; keep report role and page scope.|
|2|Red Cross uses five psychosocial principles|Entailed/useful|The five named principles are explicit.|
|3|Red Cross offers psychological first aid|Entailed/useful|Listed core activity.|
|4|Red Cross reunites families separated during emergencies|Entailed/useful|Listed core activity; emergency qualifier retained.|
|5|Red Cross offers psychosocial education|Entailed/useful|Listed core activity.|
|6|Red Cross builds community resilience|Entailed but broad|Text says it strengthens resilience; avoid implying a measured outcome.|
|7|Red Cross reached people through preparedness campaigns|Entailed but qualifier loss|5.8m+ and campaign scope were stripped.|
|8|Red Cross activated to respond to 70 events|Entailed but time loss|Explicit interval is 1 July 2023–24 June 2024.|
|9|WVA conducts scheduled evaluations and reviews|Entailed/useful|Declared process, not impact finding.|
|10|WVA uses evaluation to assess effects on participants|Overstates|Source says evaluations assess impact; assessment intent is not evidence of effects.|
|11|WVA prioritises vulnerable/excluded people|Entailed but scoped|This is in its accountability/evaluation paragraph.|
|12|WVA uses lessons to improve projects|Entailed/useful|Explicitly says lessons inform current/new projects.|
|13|WVA conducted 12 evaluations/reviews in 2024|Entailed/useful|Measurement needs count/year/unit.|
|14|WVA conducted seven evaluations in 2024|Entailed/useful|Component of total; do not detach from five mid-term reviews.|
|15|WVA conducted five mid-term reviews in 2024|Entailed/useful|Component of total; same caution.|
|16|Smith Family reported 5,478 individual volunteers|Entailed/useful|National figure; first-party report.|
|17|Smith Family reported 5,983 volunteer roles|Entailed but qualifier loss|Must retain “nationally” and multiple-role caveat.|
|18|Smith Family reported 113,792 donated volunteer hours|Entailed/useful|Participation/capacity measure, not beneficiary outcome.|
|19|Smith Family uses National Volunteer Week to recognise volunteers|Entailed/useful|Campaign activity, not evidence of volunteer impact.|
|20|Smith Family treats volunteering as measurable participation contribution|Model-generated inference|Numbers support a measurement observation, not that abstract interpretation as a source proposition.|

Physical exercise: opened and read the three text representations; inspected the predecessor generator’s literal `units` table. Defects: hard-coded lineage cannot establish direct reading; broad paraphrases lose qualifiers; model conclusions were mixed into propositions. Later work remains independent.
