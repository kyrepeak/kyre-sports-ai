"""Monster Failure Memory V1.

Read-only, deterministic memory for previously solved Kyre Sports AI failures.

The memory is deliberately conservative:
- exact KYRE error-fingerprint lookup when a verified fingerprint is known;
- exact normalized signature lookup for non-exception incidents;
- exact family lookup for deliberate browsing;
- no semantic/fuzzy matching and no automatic runtime writes.

That means an unknown failure is reported as NOT_FOUND instead of being forced
onto an unrelated historical fix. Production telemetry integration is left for
the later Monster Control Center step.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

MEMORY_VERSION = "MONSTER_FAILURE_MEMORY_V1"
PROJECTION_WEIGHT = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_SOURCE_DATA = False
MAY_AUTO_WRITE_RUNTIME_MEMORY = False
FUZZY_MATCHING = False

_KYRE_FINGERPRINT_RE = re.compile(r"^KYRE-[A-F0-9]{12}$")
_WS_RE = re.compile(r"\s+")


def normalize_signature(value: str) -> str:
    """Normalize only case/outer whitespace/repeated whitespace.

    Intentionally does *not* remove punctuation, reorder tokens, stem words, or
    calculate similarity. Two differently worded incidents stay different.
    """
    return _WS_RE.sub(" ", str(value or "").strip().lower())


def signature_id(value: str) -> str:
    normalized = normalize_signature(value)
    if not normalized:
        raise ValueError("signature must be non-empty")
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16].upper()
    return f"SIG-{digest}"


def normalize_fingerprint(value: str) -> str:
    normalized = str(value or "").strip().upper()
    if normalized and not _KYRE_FINGERPRINT_RE.fullmatch(normalized):
        raise ValueError("fingerprint must use KYRE-XXXXXXXXXXXX format")
    return normalized


@dataclass(frozen=True, slots=True)
class FailureMemoryRecord:
    memory_id: str
    family: str
    title: str
    signature: str
    symptoms: tuple[str, ...]
    root_cause: str
    fix_summary: str
    check_first: tuple[str, ...]
    files: tuple[str, ...] = field(default_factory=tuple)
    fingerprints: tuple[str, ...] = field(default_factory=tuple)
    pr_number: int | None = None
    commit_sha: str = ""
    tests: tuple[str, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)
    source_note: str = ""

    def __post_init__(self) -> None:
        if not self.memory_id.strip():
            raise ValueError("memory_id must be non-empty")
        if not self.family.strip():
            raise ValueError("family must be non-empty")
        if not self.title.strip():
            raise ValueError("title must be non-empty")
        if not normalize_signature(self.signature):
            raise ValueError("signature must be non-empty")
        if not self.root_cause.strip():
            raise ValueError("root_cause must be non-empty")
        if not self.fix_summary.strip():
            raise ValueError("fix_summary must be non-empty")
        for fingerprint in self.fingerprints:
            normalize_fingerprint(fingerprint)
        if self.pr_number is not None and self.pr_number <= 0:
            raise ValueError("pr_number must be positive when present")
        if self.commit_sha and not re.fullmatch(r"[a-fA-F0-9]{7,40}", self.commit_sha):
            raise ValueError("commit_sha must be a 7-40 character hexadecimal SHA")

    @property
    def normalized_signature(self) -> str:
        return normalize_signature(self.signature)

    @property
    def signature_id(self) -> str:
        return signature_id(self.signature)

    @property
    def normalized_family(self) -> str:
        return normalize_signature(self.family)

    def as_dict(self) -> dict[str, Any]:
        return {
            "memory_version": MEMORY_VERSION,
            "memory_id": self.memory_id,
            "family": self.family,
            "title": self.title,
            "signature": self.signature,
            "signature_id": self.signature_id,
            "symptoms": list(self.symptoms),
            "root_cause": self.root_cause,
            "fix_summary": self.fix_summary,
            "check_first": list(self.check_first),
            "files": list(self.files),
            "fingerprints": list(self.fingerprints),
            "pr_number": self.pr_number,
            "commit_sha": self.commit_sha,
            "tests": list(self.tests),
            "tags": list(self.tags),
            "source_note": self.source_note,
        }


@dataclass(frozen=True, slots=True)
class MemoryMatch:
    status: str
    match_type: str
    query: str
    records: tuple[FailureMemoryRecord, ...] = field(default_factory=tuple)

    @property
    def found(self) -> bool:
        return bool(self.records)

    @property
    def exact(self) -> bool:
        return self.match_type in {"fingerprint_exact", "signature_exact", "signature_id_exact"}

    def as_dict(self) -> dict[str, Any]:
        return {
            "memory_version": MEMORY_VERSION,
            "status": self.status,
            "found": self.found,
            "exact": self.exact,
            "match_type": self.match_type,
            "query": self.query,
            "record_count": len(self.records),
            "records": [record.as_dict() for record in self.records],
            "fuzzy_matching": FUZZY_MATCHING,
            "projection_weight": PROJECTION_WEIGHT,
            "may_modify_projection": MAY_MODIFY_PROJECTION,
            "may_modify_source_data": MAY_MODIFY_SOURCE_DATA,
            "may_auto_write_runtime_memory": MAY_AUTO_WRITE_RUNTIME_MEMORY,
        }


class FailureMemoryIndex:
    """Immutable exact-match index over curated failure records."""

    def __init__(self, records: Iterable[FailureMemoryRecord]) -> None:
        self._records = tuple(records)
        self._validate_unique()
        self._by_id = {record.memory_id: record for record in self._records}
        self._by_signature = {record.normalized_signature: record for record in self._records}
        self._by_signature_id = {record.signature_id: record for record in self._records}
        self._by_fingerprint: dict[str, FailureMemoryRecord] = {}
        self._by_family: dict[str, list[FailureMemoryRecord]] = {}
        for record in self._records:
            for fingerprint in record.fingerprints:
                self._by_fingerprint[normalize_fingerprint(fingerprint)] = record
            self._by_family.setdefault(record.normalized_family, []).append(record)

    def _validate_unique(self) -> None:
        ids: set[str] = set()
        signatures: set[str] = set()
        signature_ids: set[str] = set()
        fingerprints: set[str] = set()
        for record in self._records:
            if record.memory_id in ids:
                raise ValueError(f"duplicate memory_id: {record.memory_id}")
            ids.add(record.memory_id)

            normalized_signature = record.normalized_signature
            if normalized_signature in signatures:
                raise ValueError(f"duplicate signature: {record.signature}")
            signatures.add(normalized_signature)

            sid = record.signature_id
            if sid in signature_ids:
                raise ValueError(f"duplicate signature_id: {sid}")
            signature_ids.add(sid)

            for fingerprint in record.fingerprints:
                normalized = normalize_fingerprint(fingerprint)
                if normalized in fingerprints:
                    raise ValueError(f"duplicate fingerprint: {normalized}")
                fingerprints.add(normalized)

    @property
    def records(self) -> tuple[FailureMemoryRecord, ...]:
        return self._records

    def lookup_fingerprint(self, fingerprint: str) -> MemoryMatch:
        try:
            normalized = normalize_fingerprint(fingerprint)
        except ValueError:
            return MemoryMatch("INVALID_QUERY", "fingerprint_exact", str(fingerprint))
        record = self._by_fingerprint.get(normalized)
        return MemoryMatch(
            "FOUND" if record else "NOT_FOUND",
            "fingerprint_exact",
            normalized,
            (record,) if record else (),
        )

    def lookup_signature(self, signature: str) -> MemoryMatch:
        normalized = normalize_signature(signature)
        if not normalized:
            return MemoryMatch("INVALID_QUERY", "signature_exact", str(signature))
        record = self._by_signature.get(normalized)
        return MemoryMatch(
            "FOUND" if record else "NOT_FOUND",
            "signature_exact",
            normalized,
            (record,) if record else (),
        )

    def lookup_signature_id(self, value: str) -> MemoryMatch:
        normalized = str(value or "").strip().upper()
        record = self._by_signature_id.get(normalized)
        return MemoryMatch(
            "FOUND" if record else ("INVALID_QUERY" if not normalized else "NOT_FOUND"),
            "signature_id_exact",
            normalized,
            (record,) if record else (),
        )

    def lookup_family(self, family: str) -> MemoryMatch:
        normalized = normalize_signature(family)
        if not normalized:
            return MemoryMatch("INVALID_QUERY", "family_exact", str(family))
        records = tuple(self._by_family.get(normalized, ()))
        return MemoryMatch(
            "FOUND" if records else "NOT_FOUND",
            "family_exact",
            normalized,
            records,
        )

    def lookup_id(self, memory_id: str) -> MemoryMatch:
        normalized = str(memory_id or "").strip()
        record = self._by_id.get(normalized)
        return MemoryMatch(
            "FOUND" if record else ("INVALID_QUERY" if not normalized else "NOT_FOUND"),
            "memory_id_exact",
            normalized,
            (record,) if record else (),
        )

    def diagnose(
        self,
        *,
        fingerprint: str = "",
        signature: str = "",
        signature_id_value: str = "",
    ) -> MemoryMatch:
        """Use strongest exact identifier available; never fuzzy-fallback."""
        if str(fingerprint or "").strip():
            return self.lookup_fingerprint(fingerprint)
        if str(signature_id_value or "").strip():
            return self.lookup_signature_id(signature_id_value)
        if str(signature or "").strip():
            return self.lookup_signature(signature)
        return MemoryMatch("INVALID_QUERY", "none", "")

    def snapshot(self) -> dict[str, Any]:
        family_counts: dict[str, int] = {}
        for record in self._records:
            family_counts[record.family] = family_counts.get(record.family, 0) + 1
        return {
            "memory_version": MEMORY_VERSION,
            "record_count": len(self._records),
            "fingerprint_count": sum(len(record.fingerprints) for record in self._records),
            "families": dict(sorted(family_counts.items())),
            "records": [record.as_dict() for record in self._records],
            "fuzzy_matching": FUZZY_MATCHING,
            "projection_weight": PROJECTION_WEIGHT,
            "may_modify_projection": MAY_MODIFY_PROJECTION,
            "may_modify_source_data": MAY_MODIFY_SOURCE_DATA,
            "may_auto_write_runtime_memory": MAY_AUTO_WRITE_RUNTIME_MEMORY,
        }


def candidate_memory_record(
    *,
    family: str,
    title: str,
    signature: str,
    symptoms: Sequence[str],
    root_cause: str,
    fix_summary: str,
    check_first: Sequence[str],
    fingerprint: str = "",
    pr_number: int | None = None,
    commit_sha: str = "",
    tests: Sequence[str] = (),
    files: Sequence[str] = (),
    tags: Sequence[str] = (),
) -> dict[str, Any]:
    """Build a reviewable candidate dictionary; never persist automatically."""
    sid = signature_id(signature)
    fingerprints = (normalize_fingerprint(fingerprint),) if fingerprint else ()
    record = FailureMemoryRecord(
        memory_id=f"candidate-{sid.lower()}",
        family=str(family),
        title=str(title),
        signature=str(signature),
        symptoms=tuple(str(item) for item in symptoms),
        root_cause=str(root_cause),
        fix_summary=str(fix_summary),
        check_first=tuple(str(item) for item in check_first),
        files=tuple(str(item) for item in files),
        fingerprints=fingerprints,
        pr_number=pr_number,
        commit_sha=str(commit_sha),
        tests=tuple(str(item) for item in tests),
        tags=tuple(str(item) for item in tags),
        source_note="candidate_only_not_persisted",
    )
    payload = record.as_dict()
    payload["persistence"] = "manual_review_required"
    return payload


# Curated only from verified repository history. These are signatures for known
# incidents, not guesses about future failures. Runtime KYRE fingerprints can be
# added later only after a verified incident provides one.
DEFAULT_MEMORIES: tuple[FailureMemoryRecord, ...] = (
    FailureMemoryRecord(
        memory_id="cfb-ou-verified-identity-handoff-gated",
        family="cfb.identity",
        title="Verified CFB identity lost before frozen analysis",
        signature="cfb ou verified identity present upstream but downstream steps gate",
        symptoms=(
            "Verified schedule/runtime identity exists upstream.",
            "Downstream CFB Over/Under Steps 4-10 gate or appear unavailable.",
        ),
        root_cause=(
            "Verified event/team identity was not reliably preserved through the downstream "
            "handoff immediately before frozen V14 analysis."
        ),
        fix_summary=(
            "Added the downstream Slate V15 identity bridge to reapply already-certified "
            "official identity recovery before delegating projection work unchanged to V14."
        ),
        check_first=(
            "Inspect official ESPN event/team IDs at the schedule-to-runtime handoff.",
            "Confirm Slate V15 identity hydration before frozen V14 delegation.",
            "Do not add fuzzy matching or synthetic IDs.",
        ),
        files=(
            "cfb_over_under_slate_v15_identity_bridge.py",
            "cfb_over_under_clean_page_v31.py",
            "streamlit_memory_lazy_router_v71.py",
        ),
        pr_number=325,
        commit_sha="2baa57563556dfc463866fd03e29b00aadc9261a",
        tests=("cfb-critical", "browser-qa", "devsystem-final-gate"),
        tags=("cfb", "identity", "future-slate", "official-espn-id"),
        source_note="Verified from merged PR #325 repository history.",
    ),
    FailureMemoryRecord(
        memory_id="cfb-ou-market-metadata-cache-churn",
        family="cfb.performance.cache",
        title="Display-only market metadata invalidated expensive analysis cache",
        signature="cfb ou display-only market metadata causes frozen analysis cache misses",
        symptoms=(
            "Expensive selected-game analysis reruns even when projection inputs are unchanged.",
            "Sportsbook timestamps/provider/status metadata changes between reruns.",
        ),
        root_cause=(
            "Top-level display/context-only market fields were included in the full game mapping "
            "used at the frozen analysis cache boundary, so harmless metadata changes changed the cache key."
        ),
        fix_summary=(
            "Strip display/context-only market_* fields before the frozen V14 cache boundary, "
            "keep the explicit analysis line in the cache key, then restore current market display fields."
        ),
        check_first=(
            "Compare cache keys before and after market metadata refresh.",
            "Verify analysis_line remains explicit in the cache key.",
            "Confirm projection-relevant inputs are unchanged before reusing analysis.",
        ),
        pr_number=328,
        commit_sha="e16d38cf9850bc1e284499fa9b490cdc056b5ddb",
        tests=("cfb-critical", "browser-qa", "devsystem-final-gate"),
        tags=("cfb", "performance", "cache", "market-context"),
        source_note="Verified from merged PR #328 repository history; commit is certified PR head.",
    ),
    FailureMemoryRecord(
        memory_id="cfb-ou-serialized-provider-waits",
        family="cfb.performance.network",
        title="Independent provider waits were serialized on cold render",
        signature="cfb ou cold render serializes market request and provider cache hydration",
        symptoms=(
            "Cold selected-game analysis takes tens of seconds.",
            "Live odds wait and provider/cache hydration are both large independent spans.",
        ),
        root_cause=(
            "Independent network/cache hydration work and the live sportsbook request ran serially, "
            "inflating wall-clock time even though neither depended on the other."
        ),
        fix_summary=(
            "Prewarm only existing certified provider/cache inputs in parallel while the unchanged "
            "live sportsbook request is waiting; failures fall through to the certified path."
        ),
        check_first=(
            "Inspect performance spans for market wait versus provider/cache hydration.",
            "Check whether independent I/O can overlap without changing model inputs.",
            "Keep warmups best-effort and preserve the certified fallback path.",
        ),
        pr_number=329,
        commit_sha="0b6a49c5e9cfdc5400872fa7d161f23bdf793a6d",
        tests=("cfb-critical", "browser-qa", "devsystem-final-gate"),
        tags=("cfb", "performance", "network", "parallel-prewarm"),
        source_note="Verified from merged PR #329 repository history; commit is certified PR head.",
    ),
    FailureMemoryRecord(
        memory_id="cfb-ou-repeat-live-odds-fetch",
        family="cfb.performance.market",
        title="Repeated live-odds fetches dominated active reruns",
        signature="cfb ou active reruns repeat live odds network fetch despite fresh certified snapshot",
        symptoms=(
            "Live-odds wait remains a major refresh latency component.",
            "Backend receives repeated odds requests during active Streamlit use.",
        ),
        root_cause=(
            "Successful certified market snapshots were not reused long enough across active reruns, "
            "causing avoidable repeated network waits."
        ),
        fix_summary=(
            "Reuse successful certified market snapshots for a bounded window while rerunning the "
            "existing freshness firewall on every access; force refresh and fail closed if stale/unsafe."
        ),
        check_first=(
            "Inspect live-odds request frequency and market-load performance span.",
            "Check snapshot age against the certified freshness firewall.",
            "Never trade freshness/identity protections for cache speed.",
        ),
        pr_number=330,
        commit_sha="995f5b38690f3946e02f0af6ce792364a7d79da0",
        tests=("cfb-critical", "browser-qa", "devsystem-final-gate"),
        tags=("cfb", "performance", "odds", "snapshot-cache"),
        source_note="Verified from merged PR #330 repository history; commit is certified PR head.",
    ),
    FailureMemoryRecord(
        memory_id="cfb-ou-historical-router-cold-start",
        family="cfb.performance.import",
        title="Historical router spine inflated CFB O/U cold start",
        signature="cfb ou cold start eagerly imports historical router spine before active page",
        symptoms=(
            "Warm page render is fast but first visit/restart remains noticeably slower.",
            "Startup imports traverse many historical Streamlit router generations."
        ),
        root_cause=(
            "The entrypoint/router path eagerly imported the long frozen historical router chain "
            "before reaching the already-known active CFB Over/Under page."
        ),
        fix_summary=(
            "Make the historical router chain lazy for the exact persisted CFB O/U route while "
            "preserving frozen fallback routing for every other route."
        ),
        check_first=(
            "Compare cold bootstrap-router import time with active-page import time.",
            "Verify whether the historical router chain was skipped on the persisted fast route.",
            "Keep all non-CFB-O/U routes delegated to the frozen predecessor unchanged.",
        ),
        pr_number=331,
        commit_sha="e556b22764490e02d7ccc1b7054c9a723d927a2e",
        tests=("cfb-critical", "browser-qa", "devsystem-final-gate"),
        tags=("cfb", "performance", "cold-start", "imports", "router"),
        source_note="Verified from merged PR #331 repository history; commit is certified PR head.",
    ),
)

DEFAULT_MEMORY = FailureMemoryIndex(DEFAULT_MEMORIES)


def lookup_failure(
    *,
    fingerprint: str = "",
    signature: str = "",
    signature_id_value: str = "",
    family: str = "",
    memory_id: str = "",
) -> MemoryMatch:
    if memory_id:
        return DEFAULT_MEMORY.lookup_id(memory_id)
    if family:
        return DEFAULT_MEMORY.lookup_family(family)
    return DEFAULT_MEMORY.diagnose(
        fingerprint=fingerprint,
        signature=signature,
        signature_id_value=signature_id_value,
    )


def _compact(match: MemoryMatch) -> str:
    if not match.found:
        return f"Monster Failure Memory: {match.status} ({match.match_type})"
    record = match.records[0]
    return (
        f"SEEN BEFORE • {record.title} • PR #{record.pr_number or 'n/a'} • "
        f"check first: {record.check_first[0] if record.check_first else 'record details'}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Monster Failure Memory V1")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--fingerprint")
    group.add_argument("--signature")
    group.add_argument("--signature-id")
    group.add_argument("--family")
    group.add_argument("--memory-id")
    group.add_argument("--list", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.list or not any(
        [args.fingerprint, args.signature, args.signature_id, args.family, args.memory_id]
    ):
        payload: dict[str, Any] = DEFAULT_MEMORY.snapshot()
        exit_code = 0
    else:
        match = lookup_failure(
            fingerprint=args.fingerprint or "",
            signature=args.signature or "",
            signature_id_value=args.signature_id or "",
            family=args.family or "",
            memory_id=args.memory_id or "",
        )
        payload = match.as_dict()
        exit_code = 0 if match.found else 2

    if args.json or args.list:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        match = lookup_failure(
            fingerprint=args.fingerprint or "",
            signature=args.signature or "",
            signature_id_value=args.signature_id or "",
            family=args.family or "",
            memory_id=args.memory_id or "",
        )
        print(_compact(match))
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = [
    "DEFAULT_MEMORIES",
    "DEFAULT_MEMORY",
    "FUZZY_MATCHING",
    "FailureMemoryIndex",
    "FailureMemoryRecord",
    "MAY_AUTO_WRITE_RUNTIME_MEMORY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_SOURCE_DATA",
    "MEMORY_VERSION",
    "MemoryMatch",
    "PROJECTION_WEIGHT",
    "candidate_memory_record",
    "lookup_failure",
    "normalize_fingerprint",
    "normalize_signature",
    "signature_id",
]
