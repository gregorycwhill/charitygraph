from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from run_full_corpus_compact_v02 import MAX_ATTEMPTS, MAX_OUTPUT_TOKENS, MODEL, REASONING_EFFORT


def test_full_corpus_runner_is_compact_v02_and_non_retrying():
    assert MODEL == "gpt-5.6-luna"
    assert REASONING_EFFORT == "none"
    assert MAX_OUTPUT_TOKENS == 7000
    assert MAX_ATTEMPTS == 1


def test_full_corpus_runner_does_not_expose_old_executor():
    import run_full_corpus_compact_v02 as runner
    assert "whole_card" not in runner.PROMPT.lower()
    assert runner.execute_shard.__doc__
