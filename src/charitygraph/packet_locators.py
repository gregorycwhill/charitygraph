"""Deterministic packet-local locator resolution."""
from __future__ import annotations
import re

def resolve_locator(units: dict[str, str], locator: str) -> str | None:
    m = re.fullmatch(r"(L\d{4})(?:-(L\d{4}))?", locator)
    if not m:
        return None
    start, end = m.group(1), m.group(2) or m.group(1)
    a, b = int(start[1:]), int(end[1:])
    if b < a:
        return None
    vals = [units.get(f"L{i:04d}") for i in range(a, b + 1)]
    return "\n".join(vals) if all(v for v in vals) else None
