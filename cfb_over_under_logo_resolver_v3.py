"""CFB O/U exact ESPN team-ID logo resolver V3.

Presentation-only replacement for the network-heavy multi-source V2 resolver.

V3 never chooses a logo from a team-name similarity search. It resolves each
side only from the official ESPN team ID already carried by the certified CFB
schedule/runtime identity path, then uses ESPN's NCAA team-logo CDN convention.
If an exact numeric ESPN team ID is unavailable, V3 fails closed and lets the
existing Step-1 monogram render instead of guessing.

No schedule identity, model input, projection, ranking, qualification, market,
EV, or selection behavior is changed.
"""
from __future__ import annotations

from typing import Any, Mapping

MODEL_VERSION = "CFB O/U LOGO RESOLVER V3 • EXACT ESPN TEAM-ID ONLY"
ESPN_LOGO_CDN_TEMPLATE = "https://a.espncdn.com/i/teamlogos/ncaa/500/{team_id}.png"
ESPN_TEAM_PAGE_TEMPLATE = "https://www.espn.com/college-football/team/_/id/{team_id}"
NETWORK_LOOKUPS_ENABLED = False
FUZZY_LOGO_MATCHING = False
NAME_BASED_LOGO_MATCHING = False


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _numeric_team_id(value: Any) -> str:
    text = _clean(value)
    return text if text.isdigit() else ""


def _team_id_for_side(game: Mapping[str, Any], side: str) -> tuple[str, str]:
    """Return an exact ESPN team ID and its certified source, or fail closed."""
    top_level = _numeric_team_id(game.get(f"{side}_espn_team_id"))
    if top_level:
        return top_level, "schedule_exact_espn_team_id"

    nested = game.get(side) if isinstance(game.get(side), Mapping) else {}
    nested_id = _numeric_team_id(nested.get("team_id"))
    if nested_id:
        return nested_id, "runtime_snapshot_exact_espn_team_id"

    return "", "unavailable"


def _visual_for_side(game: Mapping[str, Any], side: str) -> dict[str, Any]:
    team_id, method = _team_id_for_side(game, side)
    if not team_id:
        return {
            "team_id": "",
            "logo": "",
            "source": "",
            "logo_provider": "",
            "logo_source_url": "",
            "confidence": "UNAVAILABLE",
            "resolution_method": method,
            "exact_identity": False,
        }

    logo = ESPN_LOGO_CDN_TEMPLATE.format(team_id=team_id)
    return {
        "team_id": team_id,
        "logo": logo,
        "source": "ESPN College Football exact team identity",
        "logo_provider": "espn_exact_team_id",
        "logo_source_url": logo,
        "team_page_url": ESPN_TEAM_PAGE_TEMPLATE.format(team_id=team_id),
        "confidence": "HIGH",
        "resolution_method": method,
        "exact_identity": True,
    }


def resolve_visuals(game: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Resolve away/home logos strictly by exact ESPN team ID."""
    return {
        "away": _visual_for_side(game, "away"),
        "home": _visual_for_side(game, "home"),
    }


def clear_logo_cache() -> None:
    """Compatibility no-op: V3 performs no network or data cache lookups."""
    return None


__all__ = [
    "ESPN_LOGO_CDN_TEMPLATE",
    "ESPN_TEAM_PAGE_TEMPLATE",
    "FUZZY_LOGO_MATCHING",
    "MODEL_VERSION",
    "NAME_BASED_LOGO_MATCHING",
    "NETWORK_LOOKUPS_ENABLED",
    "_team_id_for_side",
    "clear_logo_cache",
    "resolve_visuals",
]
