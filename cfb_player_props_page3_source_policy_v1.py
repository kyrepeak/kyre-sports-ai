"""CFB Page-3 field-specific source policy.

Presentation/source-routing only. This module never mutates the frozen player-prop
projection and never treats the approved provider pool as the active provider set.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence

FIELD_SOURCE_PRIORITIES: dict[str, tuple[str, ...]] = {
    "player_props": ("direct_sportsbook_feed", "the_odds_api", "sportsdataio"),
    "game_lines": ("direct_sportsbook_feed", "the_odds_api", "action_network", "vegasinsider"),
    "player_stats": ("ncaa_official", "sportsdataio", "collegefootballdata", "sports_reference"),
    "game_state": ("sportsdataio", "ncaa_official", "espn", "cbs_sports"),
    "history": ("sports_reference", "collegefootballdata", "ncaa_official", "espn"),
    "availability": ("official_team_sites", "rotowire", "sportsdataio"),
}


def rank_sources(field_family: str, available_provider_ids: Sequence[str]) -> tuple[str, ...]:
    """Return configured/reachable providers in field-specific priority order."""
    available = {str(value or "").strip() for value in available_provider_ids if str(value or "").strip()}
    return tuple(provider for provider in FIELD_SOURCE_PRIORITIES.get(str(field_family or "").strip(), ()) if provider in available)[:4]


def _timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def choose_newest_equivalent(
    rows: Sequence[Mapping[str, Any]], *, timestamp_key: str = "observed_at_utc"
) -> Mapping[str, Any] | None:
    """Choose the newest semantically equivalent row without rewriting its values."""
    valid: list[tuple[datetime, int, Mapping[str, Any]]] = []
    fallback: Mapping[str, Any] | None = None
    for index, row in enumerate(rows or ()):
        if not isinstance(row, Mapping):
            continue
        if fallback is None:
            fallback = row
        stamp = _timestamp(row.get(timestamp_key))
        if stamp is not None:
            valid.append((stamp, index, row))
    if valid:
        return max(valid, key=lambda item: (item[0], item[1]))[2]
    return fallback


def provenance(
    field_family: str,
    consulted_provider_ids: Sequence[str],
    *,
    newest_timestamp: str = "",
) -> dict[str, Any]:
    """Report only providers actually consulted for this semantic field."""
    seen: set[str] = set()
    active: list[str] = []
    for raw in consulted_provider_ids or ():
        provider = str(raw or "").strip()
        if provider and provider not in seen:
            seen.add(provider)
            active.append(provider)
    return {
        "field_family": str(field_family or "").strip(),
        "active_provider_ids": tuple(active),
        "newest_timestamp": str(newest_timestamp or "").strip(),
    }


__all__ = [
    "FIELD_SOURCE_PRIORITIES",
    "rank_sources",
    "choose_newest_equivalent",
    "provenance",
]
