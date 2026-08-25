"""Bounded, private program/service evidence expansion for Reality Slice 1.

This extension is deliberately separate from frozen Scoped Benchmark v2. It
only discovers source-native candidates for the seven development charities;
raw bodies are written through the existing private CAS acquirer and never
become public benchmark data.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Iterable, Mapping
from urllib.parse import urljoin, urlsplit

from .reality_slice1 import (
    BoundedPublicAcquirer,
    CohortMember,
    HoldoutFirewallError,
    SourceOpportunity,
    assert_development_member,
    development_members,
)

UTC = timezone.utc
PROGRAM_REFERENCE_VERSION = "program-reference-v1"
MAX_DEPTH = 2
MIN_REQUIRED = 10
MIN_CHARITIES = 4
MAX_SINGLE_SHARE = 0.5
PROGRAM_PROPOSITION = "durable_named_program_or_service"
_GENERIC = frozenset({
    "programs", "program", "services", "service", "our work", "what we do",
    "about us", "impact", "health", "healthcare", "education", "community development",
    "housing and homelessness", "international programs", "philanthropic services",
})


@dataclass(frozen=True)
class ExpansionSource:
    member_abn: str
    url: str
    depth: int
    parent_url: str | None
    source_record_id: str
    content_hash: str
    selector: str
    retrieved_at: str
    private_artifact: bool = True


@dataclass(frozen=True)
class ProgramReferenceCandidate:
    candidate_id: str
    member_abn: str
    charity_name: str
    canonical_label: str
    subject_kind: str
    recommendation: str
    parent_subject_id: str
    source_url: str
    source_record_id: str
    content_hash: str
    evidence_selector: str
    proposition: str
    relationship_type: str
    durability_rationale: str
    aliases: tuple[str, ...] = ()
    unresolved_reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        row = asdict(self)
        row["aliases"] = list(self.aliases)
        return row


@dataclass(frozen=True)
class RejectedCandidate:
    member_abn: str
    charity_name: str
    label: str
    source_url: str
    selector: str
    rejection_class: str
    reason: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ProgramAdequacy:
    required_durable_program_service_count: int
    charities_represented: int
    largest_charity_share: float
    minimum_count: int = MIN_REQUIRED
    minimum_charities: int = MIN_CHARITIES
    maximum_single_charity_share: float = MAX_SINGLE_SHARE
    program_benchmark_adequacy: str = "insufficient"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class _EvidenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title: list[str] = []
        self.headings: list[tuple[str, str]] = []
        self.links: list[tuple[str, str]] = []
        self._tag: str | None = None
        self._href: str | None = None
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        if tag in {"title", "h1", "h2", "h3", "h4"}:
            self._tag, self._buf = tag, []
        elif tag == "a":
            self._href = dict(attrs).get("href")
            self._buf = []

    def handle_data(self, data: str) -> None:
        if self._tag or self._href is not None:
            self._buf.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        text = " ".join(" ".join(self._buf).split())
        if self._tag == tag and text:
            if tag == "title":
                self.title.append(text)
            else:
                self.headings.append((tag, text))
            self._tag = None
            self._buf = []
        if tag == "a" and self._href:
            if text:
                self.links.append((self._href, text))
            self._href, self._buf = None, []


def _same_site(url: str, root: str) -> bool:
    return urlsplit(url).netloc.casefold().removeprefix("www.") == urlsplit(root).netloc.casefold().removeprefix("www.")


def _norm_label(label: str) -> str:
    return re.sub(r"\s+", " ", label).strip(" \t\r\n:|-—")


def _classify_false_candidate(label: str) -> tuple[str, str] | None:
    lower = label.casefold()
    if lower in _GENERIC or lower.endswith(" programs") or lower.endswith(" services"):
        return "service_domain", "broad service/program domain rather than a named durable reference"
    if any(token in lower for token in ("campaign", "appeal", "fundraising", "challenge", "event")):
        return "campaign", "campaign or event is not a durable program/service subject"
    if "lifeblood" in lower or "division" in lower or lower.endswith(" department"):
        return "division", "organisational division is not a program/service subject"
    if any(token in lower for token in ("sponsorship", "donate", "donation", "giving", "fundraising mechanism")):
        return "mechanism", "engagement/fundraising mechanism is not a program/service subject"
    return None


def _relevant_link(url: str, label: str) -> bool:
    """Permit only source-native program/service/report navigation, not a crawler."""
    signal = (url + " " + label).casefold()
    return any(token in signal for token in ("program", "service", "what-we-do", "our-work", "impact", "annual-report", "annual_report", "report"))



def _looks_named(label: str, source_url: str) -> bool:
    """Keep headings that look like source-native named references, not prose."""
    if any(ch.isdigit() for ch in label) or any(ch in label for ch in (":", ";", "?", "!", "%")):
        return False
    words_raw = re.findall(r"[A-Za-z][A-Za-z'’-]*", label)
    words = [word.casefold() for word in words_raw]
    if not words or len(words) > 6 or not label[:1].isupper():
        return False
    if words[0] in {"about", "all", "an", "any", "current", "delivered", "download", "every", "for", "get", "helping", "how", "join"}:
        return False
    stop_title = {"a", "and", "for", "in", "of", "on", "the", "to"}
    if any(word not in stop_title and not raw[:1].isupper() for raw, word in zip(words_raw, words)):
        return False
    meaningful = [word for word in words if word not in stop_title and len(word) >= 4]
    if not meaningful:
        return False
    slug = set(re.findall(r"[a-z]{4,}", urlsplit(source_url).path.casefold()))
    return bool(slug.intersection(meaningful))
def _candidate_id(member: CohortMember, label: str) -> str:
    digest = hashlib.sha256(f"{member.abn}|{label.casefold()}".encode()).hexdigest()[:20]
    return f"prv1:candidate:{digest}"


def bounded_discovery(
    *,
    members: Iterable[CohortMember],
    start_urls: Mapping[str, tuple[str, ...]],
    fetch: Callable[[str], tuple[bytes, str, int, str]],
    acquirer: BoundedPublicAcquirer,
    max_depth: int = MAX_DEPTH,
) -> tuple[tuple[ExpansionSource, ...], dict[str, bytes]]:
    """Fetch only explicit starts and same-site links, retaining bodies privately."""
    if max_depth > MAX_DEPTH:
        raise ValueError("discovery depth exceeds bounded maximum")
    allowed = {m.abn: m for m in members}
    queue: list[tuple[str, str, int, str | None]] = []
    for abn, urls in start_urls.items():
        assert_development_member(abn=abn)
        if abn not in allowed:
            raise HoldoutFirewallError("subject is not in the development cohort")
        queue.extend((abn, url, 0, None) for url in urls)
    seen: set[str] = set()
    sources: list[ExpansionSource] = []
    private_bodies: dict[str, bytes] = {}
    while queue:
        abn, url, depth, parent = queue.pop(0)
        canonical = url.split("#", 1)[0]
        if canonical in seen or depth > max_depth:
            continue
        seen.add(canonical)
        root = next((u for u in start_urls[abn]), canonical)
        if not _same_site(canonical, root):
            continue
        body, resolved, status, media_type = fetch(canonical)
        if status < 200 or status >= 300:
            continue
        opportunity = SourceOpportunity(abn, "official-website", "program_service_expansion", canonical, PROGRAM_PROPOSITION, allowed[abn].legal_current_name, locator_kind="program_page", subject_binding=abn)
        outcome = acquirer.acquire(opportunity, allow_network=True)
        if outcome.status != "available" or not outcome.source_record_id or not outcome.content_hash:
            continue
        private_bodies[outcome.source_record_id] = body
        sources.append(ExpansionSource(abn, resolved or canonical, depth, parent, outcome.source_record_id, outcome.content_hash, "html:heading-or-navigation", outcome.retrieved_at))
        parser = _EvidenceParser()
        parser.feed(body.decode("utf-8", errors="replace"))
        links = [(urljoin(canonical, href.split("#", 1)[0]), text) for href, text in parser.links if href and not href.startswith(("mailto:", "tel:", "javascript:"))]
        for link, _ in links:
            if _same_site(link, root) and _relevant_link(link, _) and link not in seen and depth < max_depth:
                queue.append((abn, link, depth + 1, canonical))
    return tuple(sources), private_bodies


def extract_candidates(
    *,
    member: CohortMember,
    sources: Iterable[ExpansionSource],
    private_bodies: Mapping[str, bytes],
) -> tuple[tuple[ProgramReferenceCandidate, ...], tuple[RejectedCandidate, ...]]:
    by_label: dict[str, list[tuple[ExpansionSource, str, str]]] = {}
    rejected: list[RejectedCandidate] = []
    for source in sources:
        if source.member_abn != member.abn:
            continue
        parser = _EvidenceParser()
        parser.feed(private_bodies[source.source_record_id].decode("utf-8", errors="replace"))
        for tag, label in parser.headings:
            clean = _norm_label(label)
            if len(clean) < 3 or len(clean) > 120:
                continue
            false = _classify_false_candidate(clean)
            selector = f"heading:{clean}"
            if false:
                rejected.append(RejectedCandidate(member.abn, member.legal_current_name, clean, source.url, selector, false[0], false[1]))
                continue
            if tag != "h1":
                continue
            if not _looks_named(clean, source.url):
                continue
            key = clean.casefold()
            by_label.setdefault(key, []).append((source, clean, selector))
    candidates: list[ProgramReferenceCandidate] = []
    for key, occurrences in sorted(by_label.items()):
        source, label, selector = occurrences[0]
        distinct_sources = {row[0].source_record_id for row in occurrences}
        repeated = len(distinct_sources) >= 2
        kind = "service" if "service" in source.url.casefold() or "service" in selector.casefold() else "program"
        path_parts = [part for part in urlsplit(source.url).path.split("/") if part]
        recommendation = "required" if repeated else ("acceptable" if len(path_parts) >= 2 else "unresolved")
        rationale = ("repeated source-native named reference across bounded official material" if repeated else ("single source-native named reference on a dedicated page; human durability review required" if recommendation == "acceptable" else "source-native label lacks an independently durable page-level boundary"))
        candidates.append(ProgramReferenceCandidate(
            _candidate_id(member, label), member.abn, member.legal_current_name, label, kind,
            recommendation, member.subject_id, source.url, source.source_record_id, source.content_hash,
            selector, PROGRAM_PROPOSITION, "has_program" if kind == "program" else "has_service", rationale,
            aliases=tuple(sorted({row[1] for row in occurrences[1:]})),
            unresolved_reason=None if repeated else "durability not established by repeated independent official material",
        ))
    return tuple(candidates), tuple(rejected)


def assess_program_adequacy(candidates: Iterable[ProgramReferenceCandidate]) -> ProgramAdequacy:
    required = [c for c in candidates if c.recommendation == "required" and c.subject_kind in {"program", "service"}]
    counts: dict[str, int] = {}
    for candidate in required:
        counts[candidate.member_abn] = counts.get(candidate.member_abn, 0) + 1
    total = len(required)
    largest = max(counts.values(), default=0) / total if total else 0.0
    adequate = total >= MIN_REQUIRED and len(counts) >= MIN_CHARITIES and largest <= MAX_SINGLE_SHARE
    return ProgramAdequacy(total, len(counts), largest, program_benchmark_adequacy="adequate" if adequate else "insufficient")


def write_review_packet(
    *,
    runtime_root: str | Path,
    candidates: Iterable[ProgramReferenceCandidate],
    rejected: Iterable[RejectedCandidate],
    adequacy: ProgramAdequacy,
) -> tuple[Path, Path]:
    root = Path(runtime_root).resolve() / "reality-slice1" / PROGRAM_REFERENCE_VERSION / "review"
    root.mkdir(parents=True, exist_ok=True)
    rows = [c.to_dict() for c in candidates]
    machine = root / "program-reference-v1-proposed.json"
    machine.write_text(json.dumps({"version": PROGRAM_REFERENCE_VERSION, "status": "proposed", "candidates": rows, "rejected": [r.to_dict() for r in rejected], "adequacy": adequacy.to_dict(), "paid_execution_allowed": False}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md: list[str] = [f"# Program/service reference review ({PROGRAM_REFERENCE_VERSION})", "", "Private, review-only; no paid calls; development cohort only.", "", f"Adequacy: **{adequacy.program_benchmark_adequacy}** ({adequacy.required_durable_program_service_count} required / {adequacy.charities_represented} charities / largest share {adequacy.largest_charity_share:.3f})", ""]
    grouped: dict[str, list[ProgramReferenceCandidate]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate.charity_name, []).append(candidate)
    for charity in sorted(grouped):
        md += [f"## {charity}", ""]
        for candidate in grouped[charity]:
            md.append(f"- **{candidate.canonical_label}** (`{candidate.subject_kind}`, {candidate.recommendation}) — {candidate.source_url} [{candidate.evidence_selector}] — {candidate.durability_rationale}")
        md.append("")
    md += ["## Rejected false-program candidates", ""]
    for item in rejected:
        md.append(f"- {item.charity_name}: **{item.label}** (`{item.rejection_class}`) — {item.reason} [{item.source_url}]")
    packet = root / "program-reference-v1-review.md"
    packet.write_text("\n".join(md) + "\n", encoding="utf-8")
    return packet, machine
