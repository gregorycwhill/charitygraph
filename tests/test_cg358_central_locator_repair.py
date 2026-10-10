import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "acquire_rich_empirical_corpus_v2.py"
SPEC = importlib.util.spec_from_file_location("cg358_acquisition", SCRIPT)
acquisition = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(acquisition)


@pytest.mark.parametrize(("raw", "expected"), [
    ("www.worldvision.com.au", "https://www.worldvision.com.au"),
    ("www.rspcansw.org.au/", "https://www.rspcansw.org.au/"),
    ("example.org.au/path?x=1", "https://example.org.au/path?x=1"),
    ("https://example.org.au/path", "https://example.org.au/path"),
    ("http://example.org.au/path", "http://example.org.au/path"),
])
def test_normalise_web_locator(raw, expected):
    assert acquisition.normalise_web_locator(raw) == expected


@pytest.mark.parametrize("raw", ["", " example.org.au", "ftp://example.org.au", "//example.org.au", "localhost", "a..org.au"])
def test_normalise_web_locator_keeps_unsupported_values_explicit(raw):
    with pytest.raises(ValueError):
        acquisition.normalise_web_locator(raw)


def test_acquisition_complete_rejects_unretried_repairable_transport_failure():
    old = {"case_id": "one", "source_family": "official_website", "status": "unavailable", "requested_locator": "example.org.au"}
    assert not acquisition.acquisition_complete(original_attempts=[old], retry_attempts=[])
    retry = {"predecessor_attempt_sha256": acquisition.sha(acquisition.canon(old))}
    assert acquisition.acquisition_complete(original_attempts=[old], retry_attempts=[retry])


def test_missing_locator_is_not_mislabelled_as_repairable_transport_failure():
    old = {"case_id": "one", "source_family": "official_website", "status": "unavailable", "requested_locator": ""}
    assert not acquisition.retryable_bare_domain_failure(old)
    assert acquisition.acquisition_complete(original_attempts=[old], retry_attempts=[])
