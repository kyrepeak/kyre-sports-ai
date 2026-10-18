"""Evidence normalization for the WNBA PRA playoff product."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

EVIDENCE_STATES = (
    "VERIFIED_MULTI_SOURCE", "VERIFIED_PRIMARY", "SINGLE_SOURCE",
    "CONFLICT", "STALE", "UNAVAILABLE",
)


@dataclass(frozen=True)
class SourceObservation:
    source: str
    category: str
    identity: str
    value: Any
    observed_at: str | None
    freshness: str
    priority: int
    authoritative: bool


@dataclass(frozen=True)
class EvidenceSummary:
    state: str
    value: Any
    sources: tuple[str, ...]
    conflicts: tuple[str, ...]
    freshness: str


def _rank(obs: SourceObservation) -> tuple[int, int, str]:
    return (0 if obs.authoritative else 1, int(obs.priority), str(obs.source))


def fuse_observations(observations: Sequence[SourceObservation]) -> EvidenceSummary:
    items = tuple(observations or ())
    if not items:
        return EvidenceSummary("UNAVAILABLE", None, (), (), "UNAVAILABLE")

    ordered = tuple(sorted(items, key=_rank))
    current = tuple(o for o in ordered if str(o.freshness or "").upper() != "STALE")
    if not current:
        chosen = ordered[0]
        return EvidenceSummary("STALE", chosen.value, tuple(o.source for o in ordered), (), "STALE")

    chosen = current[0]
    same_identity = tuple(o for o in current if o.identity == chosen.identity)
    conflicts = tuple(o.source for o in same_identity if o.value != chosen.value)
    sources = tuple(dict.fromkeys(o.source for o in same_identity))
    if conflicts:
        return EvidenceSummary("CONFLICT", chosen.value, sources, conflicts, "CURRENT")

    agreeing = tuple(o for o in same_identity if o.value == chosen.value)
    if len({o.source for o in agreeing}) >= 2:
        state = "VERIFIED_MULTI_SOURCE"
    elif chosen.authoritative:
        state = "VERIFIED_PRIMARY"
    else:
        state = "SINGLE_SOURCE"
    return EvidenceSummary(state, chosen.value, sources, (), "CURRENT")


__all__ = ["EVIDENCE_STATES", "SourceObservation", "EvidenceSummary", "fuse_observations"]
