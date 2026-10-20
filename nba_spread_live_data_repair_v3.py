"""NBA Spread live-data repair V3 — verified multi-source market bridge.

Source policy:
1. SportsGameOdds V3 is primary and may contribute many sportsbook rows.
2. Odds-API.io fills missing sportsbook/game rows without replacing a primary
   quote for the same exact game and sportsbook.
3. ESPN public scoreboard is the final credentialless market fallback.

All sportsbook rows remain read-only market context. Projection influence is
fixed at zero and the frozen Step-9/Step-10 model and decision ownership remain
untouched.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import Any

import nba_spread_live_data_repair_v2 as prior
from nba_spread_espn_market_fallback_v1 import load_verified_espn_spread_observations_v1
from nba_spread_odds_api_observations_v1 import load_verified_odds_api_spread_observations
from nba_spread_sportsbook_observations_v3 import load_verified_sportsbook_observations_v3

MODEL_VERSION = "NBA_SPREAD_LIVE_DATA_REPAIR_V3_MULTI_SOURCE"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_FROZEN_STEPS = False
METRIC_SUBSTITUTION = False

load_public_betting_payload = prior.load_public_betting_payload
build_public_betting_features = prior.build_public_betting_features
resolve_sgo_api_key = prior.resolve_sgo_api_key


def _clean(value: object) -> str:
    return str(value or "").strip()


def _verified(payload: Mapping[str, object] | None) -> bool:
    return isinstance(payload, Mapping) and _clean(payload.get("verification")).upper() == "VERIFIED"


def _valid_schedule_keys(schedule_games: Sequence[Mapping[str, object]]) -> set[str]:
    return {_clean(game.get("game_key")) for game in schedule_games if _clean(game.get("game_key"))}


def _valid_row(row: Mapping[str, object], schedule_keys: set[str]) -> bool:
    return bool(
        _clean(row.get("game_key")) in schedule_keys
        and _clean(row.get("sportsbook"))
        and _clean(row.get("away_tricode"))
        and _clean(row.get("home_tricode"))
    )


def combine_verified_market_payloads(
    schedule_games: Sequence[Mapping[str, object]],
    primary: Mapping[str, object],
    secondary: Mapping[str, object],
) -> dict[str, object]:
    """Primary-first exact-book merge; secondary is gap fill only."""
    schedule_keys = _valid_schedule_keys(schedule_games)
    merged: dict[tuple[str, str], dict[str, object]] = {}
    source_chain: list[str] = []

    for payload in (primary, secondary):
        if not _verified(payload):
            continue
        source = _clean(payload.get("source"))
        if source and source not in source_chain:
            source_chain.append(source)
        rows = payload.get("observations") or []
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
            continue
        for raw in rows:
            if not isinstance(raw, Mapping) or not _valid_row(raw, schedule_keys):
                continue
            row = dict(raw)
            key = (_clean(row.get("game_key")), _clean(row.get("sportsbook")).casefold())
            merged.setdefault(key, row)

    observations = list(merged.values())
    observations.sort(key=lambda row: (_clean(row.get("game_key")), _clean(row.get("sportsbook")).casefold()))
    if not observations:
        return {
            "verification": "UNAVAILABLE",
            "diagnostic_state": "MULTI_SOURCE_NO_VERIFIED_SPREADS",
            "source": "SportsGameOdds + Odds-API.io",
            "source_chain": source_chain or ["SportsGameOdds", "Odds-API.io"],
            "observations": [],
            "fabrication": False,
            "page_wide_source_authority": False,
            "sportsbook_projection_influence": 0.0,
        }
    return {
        "verification": "VERIFIED",
        "diagnostic_state": "OK",
        "source": "Multi-source sportsbook market",
        "source_chain": source_chain,
        "observations": observations,
        "sportsbook_count": len({_clean(row.get("sportsbook")).casefold() for row in observations}),
        "fabrication": False,
        "page_wide_source_authority": False,
        "sportsbook_projection_influence": 0.0,
    }


def load_market_payload_v3(
    schedule_games: Sequence[Mapping[str, object]],
    *,
    sgo_loader: Callable[..., Mapping[str, object]] | None = None,
    odds_api_loader: Callable[..., Mapping[str, object]] | None = None,
    espn_loader: Callable[..., Mapping[str, object]] | None = None,
    now_utc: datetime | None = None,
) -> dict[str, object]:
    """Build the richest verified sportsbook snapshot without fabricating rows."""
    sgo_loader = sgo_loader or load_verified_sportsbook_observations_v3
    odds_api_loader = odds_api_loader or load_verified_odds_api_spread_observations
    espn_loader = espn_loader or load_verified_espn_spread_observations_v1

    try:
        sgo = dict(sgo_loader(schedule_games, now_utc=now_utc) or {})
    except TypeError:
        sgo = dict(sgo_loader(schedule_games) or {})
    except Exception as exc:
        sgo = {"verification": "UNAVAILABLE", "diagnostic_state": f"SPORTSGAMEODDS_TRANSPORT_ERROR:{type(exc).__name__}", "source": "SportsGameOdds", "observations": []}

    try:
        odds_api = dict(odds_api_loader(schedule_games, now_utc=now_utc) or {})
    except TypeError:
        odds_api = dict(odds_api_loader(schedule_games) or {})
    except Exception as exc:
        odds_api = {"verification": "UNAVAILABLE", "diagnostic_state": f"ODDS_API_IO_TRANSPORT_ERROR:{type(exc).__name__}", "source": "Odds-API.io", "observations": []}

    combined = combine_verified_market_payloads(schedule_games, sgo, odds_api)
    if _verified(combined):
        combined["primary_source_state"] = _clean(sgo.get("diagnostic_state")) or "UNAVAILABLE"
        combined["secondary_source_state"] = _clean(odds_api.get("diagnostic_state")) or "UNAVAILABLE"
        return combined

    try:
        espn = dict(espn_loader(schedule_games, now_utc=now_utc) or {})
    except TypeError:
        espn = dict(espn_loader(schedule_games) or {})
    except Exception as exc:
        espn = {"verification": "UNAVAILABLE", "diagnostic_state": f"ESPN_MARKET_TRANSPORT_ERROR:{type(exc).__name__}", "source": "ESPN Public Scoreboard", "observations": []}

    if _verified(espn):
        espn["source_chain"] = ["SportsGameOdds", "Odds-API.io", "ESPN Public Scoreboard"]
        espn["primary_source_state"] = _clean(sgo.get("diagnostic_state")) or "UNAVAILABLE"
        espn["secondary_source_state"] = _clean(odds_api.get("diagnostic_state")) or "UNAVAILABLE"
        espn["sportsbook_projection_influence"] = 0.0
        return espn

    return {
        "verification": "UNAVAILABLE",
        "diagnostic_state": "MARKET_SOURCES_UNAVAILABLE:"
        + "|".join(
            [
                _clean(sgo.get("diagnostic_state")) or "SPORTSGAMEODDS_UNAVAILABLE",
                _clean(odds_api.get("diagnostic_state")) or "ODDS_API_IO_UNAVAILABLE",
                _clean(espn.get("diagnostic_state")) or "ESPN_MARKET_UNAVAILABLE",
            ]
        ),
        "source": "SportsGameOdds + Odds-API.io + ESPN Public Scoreboard",
        "source_chain": ["SportsGameOdds", "Odds-API.io", "ESPN Public Scoreboard"],
        "observations": [],
        "fabrication": False,
        "page_wide_source_authority": False,
        "sportsbook_projection_influence": 0.0,
    }


load_market_payload = load_market_payload_v3

__all__ = [
    "METRIC_SUBSTITUTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "build_public_betting_features",
    "combine_verified_market_payloads",
    "load_market_payload",
    "load_market_payload_v3",
    "load_public_betting_payload",
    "resolve_sgo_api_key",
]
