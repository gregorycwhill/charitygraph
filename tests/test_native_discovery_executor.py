from datetime import datetime, timezone
from pathlib import Path

from charitygraph.native_discovery_executor import DISCOVERY_PROMPT, build_prompt

from tests.contracts._helpers import task


def test_prompt_is_explicit_and_evidence_bound():
    assert "Do not infer effectiveness" in DISCOVERY_PROMPT
    assert "Every proposal must cite" in DISCOVERY_PROMPT


def test_build_prompt_preserves_task_evidence_order():
    model_task = task()
    first = model_task.evidence_inputs[0].evidence_id
    rendered = build_prompt(model_task, {first: "bounded evidence"})
    assert rendered.index(f"[{first}]") < rendered.index("bounded evidence")

