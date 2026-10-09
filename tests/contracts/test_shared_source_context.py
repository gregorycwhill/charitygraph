import json
from hashlib import sha256

from charitygraph.shared_source_context import build_registry, validate_no_duplicate_transmission


def test_registry_deduplicates_same_selected_representation_once(tmp_path):
    content = b'{"text":"retained"}'
    digest = sha256(content).hexdigest()
    (tmp_path / "representations").mkdir()
    (tmp_path / "representations" / "x.json").write_bytes(content)
    ev = {"representation_sha256": digest, "representation_locator":"representations/x.json", "representation_id":"repr:x", "raw_blob_id":"raw:x", "raw_sha256":"rawhash", "evidence_fragment_id":"ev:x", "fragment_locator":"$", "fragment_sha256":"frag"}
    p15 = {"case_id":"EEN-01", "subject_id":"subject", "section":15, "packet_hash":"p15", "evidence":[ev]}
    p17 = {"case_id":"EEN-01", "subject_id":"subject", "section":17, "packet_hash":"p17", "evidence":[ev]}
    registry = build_registry((p15, p17), str(tmp_path))
    validate_no_duplicate_transmission(registry)
    assert len(registry["evidence"]) == 1
    assert {x["section"] for x in registry["evidence"][0]["bindings"]} == {15, 17}
