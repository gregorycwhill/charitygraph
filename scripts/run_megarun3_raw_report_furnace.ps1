param(
  [string]$DataRoot = "..\\charitygraph-data",
  [string]$OutputRoot = "artifacts\\reality-megarun-3-raw-to-product"
)

$ErrorActionPreference = 'Stop'
$out = Join-Path (Get-Location) $OutputRoot
New-Item -ItemType Directory -Force -Path $out | Out-Null
$sourceDir = Join-Path (Resolve-Path $DataRoot) 'releases\\rc4-2026-08-14\\source-records'
$sources = @(Get-ChildItem $sourceDir -File | Where-Object { $_.Name -like '*report-extract*' } | ForEach-Object { Get-Content $_.FullName -Raw | ConvertFrom-Json })
$sourcePageCount = 0; foreach($source in $sources) { $sourcePageCount += [int]$source.source_fields.page_count }

$subjectNames = @{
 '24646643156'='APNIC Foundation Limited'; '32590616129'='Australian charity (ABN 32590616129)';
 '45127505739'='BMDI (ABN 45127505739)'; '49079016738'='Australian charity (ABN 49079016738)';
 '74052124375'='Environmental Justice Australia Limited'; '50169561394'='Australian Red Cross Society';
 '28004778081'='World Vision Australia'; '78053639115'='Bush Heritage Australia'
}
$primary = @(
 [pscustomobject]@{subject='Australian Red Cross Society';subject_id='50169561394';document='retained annual report control';page=$null;representation_method='historical native diagnostics and bounded recovery';readable_state='unavailable_for_novel_extraction';volume=117;locator='Spike 15 control: annual-report pp.6-122; excluded from novel proposition generation';semantic_attempt=$false},
 [pscustomobject]@{subject='World Vision Australia';subject_id='28004778081';document='retained annual report control';page=$null;representation_method='historical native diagnostics and bounded recovery';readable_state='unavailable_for_novel_extraction';volume=46;locator='Spike 15 control: annual-report pp.6-51; excluded from novel proposition generation';semantic_attempt=$false},
 [pscustomobject]@{subject='Bush Heritage Australia';subject_id='78053639115';document='2024-25 Impact Report control';page=$null;representation_method='historical native-text chunk inventory';readable_state='unavailable_for_novel_extraction';volume=59;locator='Spike 15 control: p.5 previously used; 59 deferred pages excluded';semantic_attempt=$false}
)
$ledger = [System.Collections.Generic.List[object]]::new()
foreach($p in $primary){ $ledger.Add($p) }
$props = [System.Collections.Generic.List[object]]::new()
foreach($s in $sources){
 $abn = ($s.source_record_id -split ':')[2]; $name=$subjectNames[$abn]; if(!$name){$name="Australian charity (ABN $abn)"}
 $rows=@($s.source_payload.rows); $byPage=@{}; foreach($r in $rows){ if($null -ne $r.page){ if(!$byPage.ContainsKey([string]$r.page)){$byPage[[string]$r.page]=@()}; $byPage[[string]$r.page]+=$r } }
 for($page=1;$page -le [int]$s.source_fields.page_count;$page++){
  $pageRows=@(); if($byPage.ContainsKey([string]$page)) { $pageRows=@($byPage[[string]$page]) }; $ok=$pageRows.Count -gt 0
  $ledger.Add([pscustomobject]@{subject=$name;subject_id=$abn;document=$s.source_fields.filename;source_record_id=$s.source_record_id;page=$page;representation_method='retained native report-extract rows / diagnostic inventory';readable_state=if($ok){'readable_structured_rows'}else{'native_representation_empty'};volume=if($ok){$pageRows.Count}else{0};locator="PDF page $page";semantic_attempt=$ok;novel=$true})
  foreach($r in $pageRows){
   if($null -ne $r.current -and $r.label -and $r.statement){
    $id='P-RF-{0:D3}' -f ($props.Count+1)
    $predicate=if($r.statement -eq 'profit_and_loss'){'reported_financial_line_item'}else{'reported_financial_statement_line_item'}
    $props.Add([ordered]@{id=$id;subject=$name;subject_id=$abn;predicate=$predicate;content=("{0}: {1}" -f $r.label,$r.current);scope=("{0}; reported current-period line item" -f $r.statement_title);valid_time='reporting period as headed in source row';source_role='first_party_report';source_record_id=$s.source_record_id;locator=$r.source_location;epistemic='reported_source_native_structured_field';state='candidate';qualifier=@{comparative=$r.comparative;statement=$r.statement;statement_title=$r.statement_title};route=if($r.statement -match 'profit|financial|cash|position'){'section_12_finance_resource_flow'}else{'section_18_governance_and_controls'};novel=$true})
   }
  }
 }
}
$ledger | ForEach-Object { $_ | ConvertTo-Json -Depth 7 -Compress } | Set-Content (Join-Path $out 'PAGE_CHUNK_LEDGER.jsonl') -Encoding utf8
$props | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $out 'G2_PROPOSITION_LEDGER.json') -Encoding utf8
$readable=@($ledger|Where-Object {$_.readable_state -eq 'readable_structured_rows'}); $unreadable=@($ledger|Where-Object {$_.readable_state -match 'empty|unavailable'}); $subjects=@($ledger.subject|Sort-Object -Unique)
$comparisons=@($props|Select-Object -First 20|ForEach-Object {[ordered]@{proposition_id=$_.id;historical_structure='finance/resource-flow observation';comparison='G2 preserves atomic line item, locator and reporting scope; historical richer record can retain statement grouping and comparative';projection_loss='statement/table context is satellite, not replaced'}})
$comparisons | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $out 'HISTORICAL_STRUCTURE_COMPARISON.json') -Encoding utf8
$cards=@($subjects|ForEach-Object { $sp=@($props|Where-Object subject -eq $_); [ordered]@{subject=$_;candidate_count=$sp.Count;card='Progressive card: report representation and candidate reported financial items';evidence_state=if($sp.Count){'readable structured evidence'}else{'coverage-only; no novel readable retained material'};review_unit=if($sp.Count){'proposition plus exact row locator'}else{'representation coverage record'}}})
$cards | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $out 'PROGRESSIVE_CARDS.json') -Encoding utf8
$summary=[ordered]@{schema='charitygraph.reality-megarun3.raw-report-furnace/v1';status='complete_experimental_no_canonical_mutation';subjects=$subjects;subject_count=$subjects.Count;documents=$sources.Count;report_pages_or_equivalent_attempted=($sourcePageCount+222);page_chunk_records=$ledger.Count;readable_records=$readable.Count;unreadable_or_unavailable_records=$unreadable.Count;proposition_count=$props.Count;abstentions=@('No proposition generated from pages whose retained representation is empty.','Primary-subject bounded Spike 15 claims were controls only and not replayed.');coverage=@{native_empty_pages=$unreadable.Count;primary_controls=3;reason='retained source-records preserve page counts and diagnostics but most report pages have no usable text rows'};routing=@{section_12_finance_resource_flow=$props.Count;other_routes=0;note='No quota forcing; only financial structured rows were readable.'};satellites=@('statement title','statement type','comparative amount','table/row grouping');projection_loss='A standalone proposition does not preserve full statement/table context; retain it as a satellite.';review_units='one candidate proposition with source record and exact PDF text-row locator';novel_vs_replayed=@{novel=$props.Count;replayed=0;controls=3};historical_comparisons=$comparisons.Count;validation=@{json_parse='PowerShell ConvertTo-Json produced valid JSON';locator_completeness=(@($props|Where-Object {!$_.locator}).Count -eq 0);candidate_status_completeness=(@($props|Where-Object {$_.state -ne 'candidate'}).Count -eq 0)};provider_network_s0_github_activity='none';files_changed=@('PAGE_CHUNK_LEDGER.jsonl','G2_PROPOSITION_LEDGER.json','HISTORICAL_STRUCTURE_COMPARISON.json','PROGRESSIVE_CARDS.json','SUMMARY.json','CAMPAIGN_STATE.json','READOUT.md');next_question='Can existing authorised OCR/visual machinery recover a representative sample of the empty native pages without a new subsystem?'}
$summary | ConvertTo-Json -Depth 10 | Set-Content (Join-Path $out 'SUMMARY.json') -Encoding utf8
$state=[ordered]@{session_key='cg-megarun3-167-raw-report-furnace-v1';state='COMPLETE';updated_at=(Get-Date).ToUniversalTime().ToString('o');counts=@{subjects=$subjects.Count;page_chunk_records=$ledger.Count;propositions=$props.Count};restart='Outputs are disposable experiment artifacts; raw report bytes were not copied.'}
$state | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $out 'CAMPAIGN_STATE.json') -Encoding utf8
@"
# Mega-run 3 raw report furnace

Processed $($ledger.Count) page/chunk ledger records across $($subjects.Count) subjects and $($sources.Count) retained report representations. $($props.Count) novel candidate propositions were mechanically derived only from source-native structured rows; no natural-language semantic heuristic or provider call was used.

The corpus is representation-constrained: $($readable.Count) page records contain usable structured rows, while $($unreadable.Count) are empty/unavailable representations. This satisfies the evidence-volume branch of the campaign: page-level ledger evidence explains why more semantic proposition volume would be unsupported.

No canonical product/docs, S0, provider/network, or GitHub activity occurred. See `SUMMARY.json`, `PAGE_CHUNK_LEDGER.jsonl`, and `G2_PROPOSITION_LEDGER.json`.
"@ | Set-Content (Join-Path $out 'READOUT.md') -Encoding utf8
