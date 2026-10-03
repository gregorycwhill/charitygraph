"""Temporary, deterministic 0.5 staging migration; never writes a final release."""
from __future__ import annotations
import json
from pathlib import Path
from .adapter import adapt_rc4_card
from .models import CapabilityRegistry, ReleaseContext
from ..projection_compatibility import Disposition, EvaluationGrain, evaluate_compatibility


def stage_rc4_release(rc4_release: Path, output: Path, registry: CapabilityRegistry, context: ReleaseContext, *, compatibility_requests: dict[str, dict] | None = None) -> list[dict]:
    """Stage cards only with a private, governed compatibility context.

    ``compatibility_requests`` is deliberately not reconstructed from an RC4
    card and is never serialized into the public v0.5 contract.  It is an
    ephemeral evaluation view over governed records held by the publisher.
    """
    if compatibility_requests is None:
        raise ValueError("authoritative governed compatibility context is required")
    sources={}
    for path in (rc4_release / "source-records").glob("*.json"):
        item=json.loads(path.read_text(encoding="utf-8")); sources[item["source_record_id"]]=item
    cards=[]
    for path in sorted((rc4_release / "cards").glob("*.json")):
        card=adapt_rc4_card(json.loads(path.read_text(encoding="utf-8")),sources,registry,context)
        request=compatibility_requests.get(card["causebase_id"])
        if request is None:
            raise ValueError("missing authoritative governed compatibility context: " + card["causebase_id"])
        decision=evaluate_compatibility(request, grain=EvaluationGrain.SECTION_CARD)
        if decision.disposition is Disposition.ABSTAIN:
            raise ValueError("projection compatibility gate abstained: " + ",".join(decision.reason_codes))
        cards.append(card)
    (output / "cards").mkdir(parents=True,exist_ok=True)
    for card in cards:(output / "cards" / f"{card['causebase_id']}.json").write_text(json.dumps(card,indent=2)+"\n",encoding="utf-8")
    return cards
