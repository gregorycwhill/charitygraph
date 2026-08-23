"""Isolated implementation of the approved CharityGraph public contract 0.5.

This package deliberately does not alter the legacy RC4 models or publisher.
"""

from .adapter import ReleaseContext, adapt_rc4_card, adapt_rc4_fixture
from .models import FutureReleaseContext, PublicationIdentity
from .validate import validate_v05_card, validate_v05_fixture_release
from .release import assemble_release, audit_losslessness

__all__ = ["ReleaseContext", "FutureReleaseContext", "PublicationIdentity", "adapt_rc4_card", "adapt_rc4_fixture", "validate_v05_card", "validate_v05_fixture_release", "assemble_release", "audit_losslessness"]
