import io
import zipfile

from charitygraph.source_transmission import payload_selection, render_complete_workbook


def test_complete_workbook_rendering_preserves_each_nonempty_cell_without_range_cap():
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="First" sheetId="1" r:id="rId1"/><sheet name="Second" sheetId="2" r:id="rId2"/></sheets></workbook>')
        archive.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Target="worksheets/sheet2.xml"/></Relationships>')
        archive.writestr("xl/sharedStrings.xml", '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>one</t></si><si><t>far</t></si></sst>')
        archive.writestr("xl/worksheets/sheet1.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row><c r="A1" t="s"><v>0</v></c><c r="Z99" t="s"><v>1</v></c></row></sheetData></worksheet>')
        archive.writestr("xl/worksheets/sheet2.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row><c r="C4"><v>3</v></c></row></sheetData></worksheet>')

    rendered = render_complete_workbook(data.getvalue(), "srcblob:" + "a" * 64)

    assert rendered["representation_kind"] == "complete_source_native_workbook"
    assert rendered["sheets"] == [
        {"title": "First", "cells": [{"coordinate": "A1", "value": "one"}, {"coordinate": "Z99", "value": "far"}]},
        {"title": "Second", "cells": [{"coordinate": "C4", "value": "3"}]},
    ]


def test_bounded_payload_selection_is_explicitly_economic_not_a_rights_decision():
    assert payload_selection(candidate_representation_artifact_id="drvblob:" + "b" * 64, selection_reason="economic_optimization")["selection_reason"] == "economic_optimization"
