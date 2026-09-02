from charitygraph.scope_resolution import resolve_scope
from charitygraph.document_representation import represent_document

def test_scope_hint_is_not_authoritative_without_structured_evidence():
    r = resolve_scope(producer_scope_kind="named_program_or_service", producer_scope_label="literacy programs")
    assert r.resolved_scope_kind == "uncertain"

def test_structured_named_scope_resolves():
    r = resolve_scope(producer_scope_kind="subject", producer_scope_label=None, evidenced_scope_kind="named_program_or_service", evidenced_scope_label="Learning for Life", evidence_refs=("L1",))
    assert r.resolved_scope_kind == "named_program_or_service" and r.evidence_refs == ("L1",)

def test_html_representation_excludes_scripts_and_preserves_text():
    r = represent_document(b"<html><script>x</script><body>Hello <b>world</b></body></html>", content_type="text/html")
    assert r.complete and r.text == "Hello\nworld" and r.representation_type == "readable_text"

def test_binary_is_not_treated_as_prose():
    r = represent_document(b"\x00\x01binary")
    assert r.complete and r.material_type == "html"  # decoded only when not identified as PDF
