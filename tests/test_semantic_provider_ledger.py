import pytest

from charitygraph.semantic_provider_ledger import ProviderLedgerError, reconcile_provider_ledger


def test_reconciles_physical_33_against_logical_31_without_erasing_unlinked_receipts():
    physical = [
        {"response_id": "r1", "model": "gpt-5.6-luna", "input_tokens": 10, "output_tokens": 2, "cost_usd": "0.01"},
        {"response_id": "r2", "model": "gpt-5.6-luna", "input_tokens": 20, "output_tokens": 3, "cost_usd": "0.02"},
        {"response_id": "r3", "model": "gpt-5.6-luna", "input_tokens": 30, "output_tokens": 4, "cost_usd": "0.03"},
    ]
    result = reconcile_provider_ledger(physical, [{"execution_id": "t04:A:one", "response_id": "r1"}, {"execution_id": "t05:C:two", "response_id": "r3"}])
    assert result["physical"] == {"calls": 3, "input_tokens": 60, "output_tokens": 9, "usd": "0.06"}
    assert result["logical"] == {"calls": 2, "input_tokens": 40, "output_tokens": 6, "usd": "0.04"}
    assert result["unlinked_physical"] == [{"response_id": "r2", "model": "gpt-5.6-luna", "input_tokens": 20, "output_tokens": 3, "cost_usd": "0.02"}]


def test_rejects_duplicate_or_ambiguous_physical_bindings():
    row = {"response_id": "r1", "model": "gpt-5.6-luna", "input_tokens": 1, "output_tokens": 1, "cost_usd": "0.01"}
    with pytest.raises(ProviderLedgerError, match="duplicate"):
        reconcile_provider_ledger([row, row], [])
    with pytest.raises(ProviderLedgerError, match="multiple"):
        reconcile_provider_ledger([row], [{"execution_id": "a", "response_id": "r1"}, {"execution_id": "b", "response_id": "r1"}])
