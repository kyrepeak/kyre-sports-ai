"""Football-only NFL Game Totals feature contract V1.

This layer accepts one verified official game plus two already-certified team
scoring profiles and emits only football inputs for the future totals model.
Sportsbook market data is forbidden at this boundary and fails closed.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

SCHEMA_VERSION = "nfl_game_totals_features_v1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
SPORTSBOOK_INPUTS: tuple[str, ...] = ()
FORBIDDEN_MARKET_KEYS = frozenset(
    {
        "total",
        "market_total",
        "sportsbook_total",
        "over_price",
        "under_price",
        "sportsbook",
        "market_id",
        "provider_event_id",
        "book",
        "odds",
        "price",
        "implied_probability",
        "no_vig_probability",
    }
)
PROFILE_NUMERIC_FIELDS = (
    "ppg",
    "papg",
    "recent6_pf_pg",
    "recent6_pa_pg",
)
FEATURE_NAMES = (
    "away_offense_ppg",
    "away_defense_papg",
    "away_recent6_pf_pg",
    "away_recent6_pa_pg",
    "home_offense_ppg",
    "home_defense_papg",
    "home_recent6_pf_pg",
    "home_recent6_pa_pg",
    "neutral_site",
)


class NFLGameTotalsFeatureError(RuntimeError):
    """The football-only Game Totals feature contract could not be proven."""


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise NFLGameTotalsFeatureError(f"{field} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise NFLGameTotalsFeatureError(f"{field} must be numeric") from exc
    if not math.isfinite(number):
        raise NFLGameTotalsFeatureError(f"{field} must be finite")
    return number


def _count(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise NFLGameTotalsFeatureError(f"{field} must be a non-negative integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise NFLGameTotalsFeatureError(f"{field} must be a non-negative integer") from exc
    if number < 0:
        raise NFLGameTotalsFeatureError(f"{field} must be a non-negative integer")
    return number


def _assert_no_market_keys(value: Any, path: str = "input") -> None:
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = _text(raw_key).casefold()
            if key in FORBIDDEN_MARKET_KEYS:
                raise NFLGameTotalsFeatureError(
                    f"sportsbook/market field {raw_key!r} is forbidden in football feature input ({path})"
                )
            _assert_no_market_keys(child, f"{path}.{raw_key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _assert_no_market_keys(child, f"{path}[{index}]")


def _profile(side: str, expected_team: Mapping[str, Any], raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or raw.get("ready") is not True:
        raise NFLGameTotalsFeatureError(f"{side} team scoring profile is not ready")

    expected_id = _text(expected_team.get("team_id"))
    expected_abbr = _text(expected_team.get("abbr")).upper()
    actual_id = _text(raw.get("official_team_id"))
    actual_abbr = _text(raw.get("abbr")).upper()
    if not expected_id.isdigit() or actual_id != expected_id:
        raise NFLGameTotalsFeatureError(f"{side} official team identity mismatch")
    if expected_abbr and actual_abbr != expected_abbr:
        raise NFLGameTotalsFeatureError(f"{side} team abbreviation mismatch")

    numeric = {field: _finite(raw.get(field), f"{side}.{field}") for field in PROFILE_NUMERIC_FIELDS}
    prior_games = _count(raw.get("prior_games"), f"{side}.prior_games")
    current_games = _count(raw.get("current_games"), f"{side}.current_games")
    current_weight = _finite(raw.get("current_weight"), f"{side}.current_weight")
    if prior_games < 12:
        raise NFLGameTotalsFeatureError(f"{side} prior-season sample is below the 12-game minimum")
    if not 0.0 <= current_weight <= 1.0:
        raise NFLGameTotalsFeatureError(f"{side}.current_weight must be between 0 and 1")

    return {
        "official_team_id": actual_id,
        "abbr": actual_abbr,
        "prior_games": prior_games,
        "current_games": current_games,
        "current_weight": current_weight,
        **numeric,
    }


def build_game_totals_feature_vector(
    game: Mapping[str, Any],
    away_profile: Mapping[str, Any],
    home_profile: Mapping[str, Any],
) -> dict[str, Any]:
    """Build one exact-ID football-only feature vector; market data fails closed."""
    if not isinstance(game, Mapping):
        raise NFLGameTotalsFeatureError("verified game must be an object")
    _assert_no_market_keys(game, "game")
    _assert_no_market_keys(away_profile, "away_profile")
    _assert_no_market_keys(home_profile, "home_profile")

    event_id = _text(game.get("official_event_id"))
    away_team = game.get("away") if isinstance(game.get("away"), Mapping) else {}
    home_team = game.get("home") if isinstance(game.get("home"), Mapping) else {}
    if not event_id.isdigit():
        raise NFLGameTotalsFeatureError("official event ID must be numeric")
    if _text(away_team.get("team_id")) == _text(home_team.get("team_id")):
        raise NFLGameTotalsFeatureError("away/home official team IDs must be distinct")

    away = _profile("away", away_team, away_profile)
    home = _profile("home", home_team, home_profile)
    feature_values = {
        "away_offense_ppg": away["ppg"],
        "away_defense_papg": away["papg"],
        "away_recent6_pf_pg": away["recent6_pf_pg"],
        "away_recent6_pa_pg": away["recent6_pa_pg"],
        "home_offense_ppg": home["ppg"],
        "home_defense_papg": home["papg"],
        "home_recent6_pf_pg": home["recent6_pf_pg"],
        "home_recent6_pa_pg": home["recent6_pa_pg"],
        "neutral_site": bool(game.get("neutral_site")),
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "service": "Kyre Sports API",
        "sport": "nfl",
        "official_event_id": event_id,
        "away_team_id": away["official_team_id"],
        "home_team_id": home["official_team_id"],
        "feature_names": list(FEATURE_NAMES),
        "features": feature_values,
        "quality": {
            "away_prior_games": away["prior_games"],
            "away_current_games": away["current_games"],
            "away_current_weight": away["current_weight"],
            "home_prior_games": home["prior_games"],
            "home_current_games": home["current_games"],
            "home_current_weight": home["current_weight"],
        },
        "football_only": True,
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
        "sportsbook_inputs": list(SPORTSBOOK_INPUTS),
        "projection_generated": False,
    }


__all__ = [
    "FEATURE_NAMES",
    "FORBIDDEN_MARKET_KEYS",
    "NFLGameTotalsFeatureError",
    "PROFILE_NUMERIC_FIELDS",
    "SCHEMA_VERSION",
    "SPORTSBOOK_INPUTS",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "build_game_totals_feature_vector",
]
