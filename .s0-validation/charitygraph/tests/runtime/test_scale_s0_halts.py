from datetime import datetime, timezone
import pytest

from charitygraph.runtime import CatalogError, SQLiteCatalog


NOW = datetime(2026, 9, 17, tzinfo=timezone.utc)


def test_scale_s0_halt_is_durable_scoped_and_requires_auditable_recovery(tmp_path):
    catalog = SQLiteCatalog(tmp_path / "state.sqlite3").open(initialize=True)
    catalog.record_scale_s0_halt(halt_id="halt:test", slice_id="slice:test", scope="slice", reason="candidate_to_governed_bypass", created_at=NOW)
    assert catalog.active_scale_s0_halt(slice_id="slice:test", task_key="task@1", subject_id="subject:test")["halt_id"] == "halt:test"
    with pytest.raises(CatalogError):
        catalog.recover_scale_s0_halt(halt_id="halt:test", actor="", rationale="missing", recovered_at=NOW)
    catalog.recover_scale_s0_halt(halt_id="halt:test", actor="reviewer:test", rationale="controls repaired", recovered_at=NOW)
    assert catalog.active_scale_s0_halt(slice_id="slice:test", task_key="task@1", subject_id="subject:test") is None
    assert SQLiteCatalog(tmp_path / "state.sqlite3").open().active_scale_s0_halt(slice_id="slice:test", task_key="task@1", subject_id="subject:test") is None
