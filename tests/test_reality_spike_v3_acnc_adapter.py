"""Integration-shaped checks for the Spike 3 adapter's Builder seams."""
import importlib.util
from pathlib import Path


def load():
    path = Path(__file__).parents[1] / "scripts" / "reality_spike_v3_sunrise_acnc_data.py"
    spec = importlib.util.spec_from_file_location("spike3", path); module = importlib.util.module_from_spec(spec); assert spec.loader
    spec.loader.exec_module(module); return module


def test_uses_acnc_packet_and_structured_filing_selection(monkeypatch, tmp_path):
    spike = load(); calls = []
    def acquired(abn):
        calls.append(abn)
        return {"profile": {"uuid": "acnc-uuid", "data": {"Documents": [{"Year": "2024", "type": "Annual Report", "Url": "https://example.test/report.pdf"}]}}, "latest_submitted_ais": {"Year": "2024", "AISId": "ais-uuid"}, "ais_detail": {"data": {"StatementYear": "2024", "RevenueTotal": "7"}}, "ais_acquisition_failure": None}
    monkeypatch.setattr(spike, "acquire", acquired)
    monkeypatch.setattr(spike, "fetch", lambda url: (b"not-a-pdf", url, 200, "text/plain"))
    result = spike.process("Example", "51111111111", tmp_path)
    packet = (tmp_path / "51111111111" / "packet.json").read_text(encoding="utf-8")
    assert calls == ["51111111111"]
    assert result["latest_ais_year"] == "2024" and result["filings"] == 1
    assert "select_filing_documents structured Year/type metadata" in packet
    assert "RevenueTotal" in packet


def test_absent_same_period_filing_stays_missing(monkeypatch, tmp_path):
    spike = load()
    monkeypatch.setattr(spike, "acquire", lambda abn: {"profile": {"uuid": "acnc-uuid", "data": {"Documents": [{"Year": "2023", "type": "Annual Report", "Url": "https://example.test/old.pdf"}]}}, "latest_submitted_ais": {"Year": "2024"}, "ais_detail": {"data": {}}, "ais_acquisition_failure": None})
    result = spike.process("Example", "51111111111", tmp_path)
    assert result["filings"] == 0
    assert "No same-period filing attachment" in (tmp_path / "51111111111" / "card.md").read_text(encoding="utf-8")
