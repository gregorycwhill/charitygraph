# Provider-free regression results

Command:

`pytest tests/test_frozen_experiment.py tests/test_source_rights.py tests/test_source_transmission.py tests/test_phase5_baseline_corpus.py tests/test_phase5_official_website_campaign.py -q -p no:cacheprovider`

Result: 60 passed.

The frozen-experiment tests cover packet-bound proposition identity, seven
generic rejected noncanonical patterns, partial support, positive-scope
fail-closed validation, and weak service-scope basis rejection. No provider
transport or source acquisition was invoked.
