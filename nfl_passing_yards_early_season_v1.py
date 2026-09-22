"""NFL Passing Yards early-season verified baseline helpers.

Current-season verified data always wins. Before a new regular season has a
usable completed-game sample, the immediately previous regular season may be
used as a clearly-labeled baseline. Recent history can be filled from the prior
regular season only to complete a short rolling window; event IDs stay exact and
duplicates are removed.

No sportsbook data is accepted here and no projection adjustment is created.
"""
from __future__ import annotations

from typing import Any

MODEL_VERSION = "NFL PASSING YARDS EARLY SEASON BRIDGE V1"


def allow_prior_regular_fallback(season_type: int) -> bool:
    try:
        return int(season_type) == 2
    except Exception:
        return False


def prior_regular_year(year: int) -> int:
    return int(year) - 1


def merge_recent_rows(current: list[dict] | None, prior: list[dict] | None, limit: int = 5) -> list[dict]:
    """Keep current rows first, then fill from prior season by exact event ID."""
    out: list[dict] = []
    seen: set[str] = set()
    for source in (current or [], prior or []):
        for raw in source:
            if not isinstance(raw, dict):
                continue
            row = dict(raw)
            event_id = str(row.get("event_id") or row.get("eventId") or row.get("id") or "").strip()
            dedupe_key = event_id or "|".join(
                str(row.get(k) or "").strip() for k in ("date", "opponent", "passing_yards", "attempts")
            )
            if dedupe_key and dedupe_key in seen:
                continue
            if dedupe_key:
                seen.add(dedupe_key)
            out.append(row)
            if len(out) >= max(0, int(limit)):
                return out
    return out


def provenance(current_ready: bool, fallback_used: bool, current_year: int, source_year: int | None = None) -> dict[str, Any]:
    source = int(source_year if source_year is not None else current_year)
    if fallback_used:
        label = f"EARLY-SEASON BASELINE • {source} REGULAR SEASON"
    elif current_ready:
        label = f"CURRENT-SEASON BASELINE • {source}"
    else:
        label = "BASELINE CHECK"
    return {
        "baseline_source_year": source,
        "early_season_fallback": bool(fallback_used),
        "baseline_provenance": label,
    }


__all__ = [
    "MODEL_VERSION",
    "allow_prior_regular_fallback",
    "merge_recent_rows",
    "prior_regular_year",
    "provenance",
]
