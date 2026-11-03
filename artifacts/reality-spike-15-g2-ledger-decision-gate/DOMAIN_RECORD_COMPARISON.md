# G2 versus richer domain records

| Domain | G2 retains | Rich satellite still warranted | Loss if qualifier omitted | Decision |
|---|---|---|---|---|
| Participation | subject, attributed count, period, role list | opportunity lifecycle / eligibility / actual uptake | member and volunteer merge; opportunity confused with participation | satellite for opportunity workflows |
| Governance | roster/control statement, period, source | full officeholder/committee mandate graph | incomplete roster read as complete governance | satellite for governance graph |
| Relationships | endpoints, direction and role via bounded qualifier | relation lifecycle, legal instrument, multi-party graph | `co_designed_with` or `member_of` becomes generic link | satellite for rich relation graph |
| Service/capacity | description, workforce, measurement kind | service catalogue, locations, queues, capacity denominator | reach/workforce becomes availability/capacity | satellite for operational service model |
| Ethos | value/commitment/policy stage | policy text, control/test/outcome evidence chain | commitment becomes implementation | satellite only where assessment/product needs chain |
| Evaluation | evidence existence and typed metric boundary | indicator, baseline, method, counterfactual and result graph | output/outcome/impact collapse | first-class attached evaluation record |

Measured in this fixture: 14 propositions, 4 coverage entries, 4 abstentions, 6 qualifier-bearing domains, 17 deterministic section appearances, and no duplicate proposition storage. G2 alone has 0 material loss only with bounded qualifiers; 5 propositions require qualifiers. Rich records are therefore attached satellites, not replacements for the cross-domain ledger and not projection-only.

Experimental implementation counts: G2 path 5 stages (representation → candidate ledger → coverage/relation → deterministic route → card/query), 2 adapters, 4 record types, ~154 lines disposable glue; historical path 10 stages, 8–9 adapters, 6+ record types, ~100 bridge lines plus compiler/runtime dependencies. The counts are comparison estimates, not production benchmarks.
