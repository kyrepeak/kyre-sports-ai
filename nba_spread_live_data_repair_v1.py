"""NBA Spread post-freeze live-data repair V1.

Additive adapter that reconnects already-frozen observation transports to the
page-facing selectors without modifying any frozen Step 1-10 model, projection,
probability, ranking, or source-router contract.
"""
from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from typing import Any

from nba_spread_market_lines_v1 import build_spread_market_context
from nba_spread_most_bet_v1 import select_most_bet_game
from nba_spread_sharp_money_v1 import select_sharp_money_game

MODEL_VERSION = "NBA_SPREAD_LIVE_DATA_REPAIR_V1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_FROZEN_STEPS = False
METRIC_SUBSTITUTION = False
ELIGIBLE_STATES = {"UPCOMING", "DELAYED"}


def _clean_key(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    upper = text.upper()
    placeholders = ("PASTE_YOUR_KEY_HERE", "YOUR_API_KEY", "YOUR_KEY_HERE", "API_KEY_HERE")
    return None if any(token in upper for token in placeholders) else text


def resolve_sgo_api_key(
    *,
    session_state: Mapping[str, Any] | None = None,
    secrets: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> str | None:
    """Use the same credential discovery order already proven by other sports."""
    st_runtime = None
    if session_state is None or secrets is None:
        try:
            import streamlit as st_runtime  # lazy: Runless static proof stays dependency-minimal
        except Exception:
            st_runtime = None

    if session_state is not None:
        session = session_state
    elif st_runtime is not None:
        session = st_runtime.session_state
    else:
        session = {}

    if secrets is not None:
        secret_map: Mapping[str, Any] = secrets
    elif st_runtime is not None:
        try:
            secret_map = st_runtime.secrets
        except Exception:
            secret_map = {}
    else:
        secret_map = {}

    env = environ if environ is not None else os.environ
    return _clean_key(
        session.get("ks_sportsgameodds_key")
        or secret_map.get("SPORTSGAMEODDS_API_KEY")
        or env.get("SPORTSGAMEODDS_API_KEY")
        or env.get("SPORTSGAMEODDS_KEY")
    )


def load_public_betting_payload(
    schedule_games: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    try:
        from nba_spread_public_betting_observations_v1 import (
            load_verified_public_betting_observations,
        )
        payload = load_verified_public_betting_observations(schedule_games)
    except Exception as exc:
        return {
            "verification": "UNAVAILABLE",
            "diagnostic_state": f"PUBLIC_BETTING_TRANSPORT_ERROR:{type(exc).__name__}",
            "source": "Action Network",
            "observations": [],
            "fabrication": False,
            "page_wide_source_authority": False,
        }
    return dict(payload) if isinstance(payload, Mapping) else {
        "verification": "UNAVAILABLE",
        "diagnostic_state": "INVALID_PUBLIC_BETTING_PAYLOAD",
        "source": "Action Network",
        "observations": [],
        "fabrication": False,
        "page_wide_source_authority": False,
    }


def build_public_betting_features(
    schedule_games: Sequence[Mapping[str, object]],
    *,
    payload: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Drive Most Bet + Sharp Money from one exact Action observation payload."""
    public = dict(payload) if payload is not None else load_public_betting_payload(schedule_games)
    source = str(public.get("source") or "Action Network")
    if str(public.get("verification") or "").upper() != "VERIFIED":
        diagnostic = str(public.get("diagnostic_state") or "PUBLIC_BETTING_UNAVAILABLE")
        unavailable = {
            "verification": "UNAVAILABLE",
            "diagnostic_state": diagnostic,
            "source": source,
            "fabrication": False,
            "page_wide_source_authority": False,
        }
        return {
            "verification": "UNAVAILABLE",
            "diagnostic_state": diagnostic,
            "most_bet": dict(unavailable),
            "sharp_money": dict(unavailable),
            "source": source,
            "fabrication": False,
            "metric_substitution": False,
            "page_wide_source_authority": False,
        }

    observations = public.get("observations") or []
    if not isinstance(observations, Sequence) or isinstance(observations, (str, bytes)):
        observations = []
    rows = [dict(row) for row in observations if isinstance(row, Mapping)]

    most_bet = select_most_bet_game(rows, schedule_games)
    sharp_money = select_sharp_money_game(rows, schedule_games)
    for feature in (most_bet, sharp_money):
        feature.setdefault("source", source)
        feature["fabrication"] = False
        feature["page_wide_source_authority"] = False
        feature["metric_substitution"] = False

    verified = any(feature.get("verification") == "VERIFIED" for feature in (most_bet, sharp_money))
    return {
        "verification": "VERIFIED" if verified else "UNAVAILABLE",
        "diagnostic_state": "OK" if verified else "NO_VERIFIED_PUBLIC_FEATURE",
        "most_bet": most_bet,
        "sharp_money": sharp_money,
        "source": source,
        "fabrication": False,
        "metric_substitution": False,
        "page_wide_source_authority": False,
    }


def load_market_payload(
    schedule_games: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Load the frozen SportsGameOdds transport with production secret discovery."""
    key = resolve_sgo_api_key()
    if not key:
        return {
            "verification": "UNAVAILABLE",
            "diagnostic_state": "SPORTSGAMEODDS_CREDENTIAL_UNAVAILABLE",
            "source": "SportsGameOdds",
            "observations": [],
            "fabrication": False,
            "page_wide_source_authority": False,
        }

    def _secret_getter(name: str) -> str | None:
        return key if name == "SPORTSGAMEODDS_API_KEY" else None

    try:
        from nba_spread_sportsbook_observations_v1 import (
            load_verified_sportsbook_observations,
        )
        payload = load_verified_sportsbook_observations(
            schedule_games,
            secret_getter=_secret_getter,
        )
    except Exception as exc:
        return {
            "verification": "UNAVAILABLE",
            "diagnostic_state": f"SPORTSGAMEODDS_TRANSPORT_ERROR:{type(exc).__name__}",
            "source": "SportsGameOdds",
            "observations": [],
            "fabrication": False,
            "page_wide_source_authority": False,
        }
    return dict(payload) if isinstance(payload, Mapping) else {
        "verification": "UNAVAILABLE",
        "diagnostic_state": "SPORTSGAMEODDS_INVALID_PAYLOAD",
        "source": "SportsGameOdds",
        "observations": [],
        "fabrication": False,
        "page_wide_source_authority": False,
    }


def _eligible_pairs(schedule_games: Sequence[Mapping[str, object]]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for game in schedule_games:
        if str(game.get("status") or "").strip().upper() not in ELIGIBLE_STATES:
            continue
        away = str(game.get("away_tricode") or "").strip().upper()
        home = str(game.get("home_tricode") or "").strip().upper()
        if away and home:
            pairs.append((away, home))
    return pairs


def build_market_feature(
    schedule_games: Sequence[Mapping[str, object]],
    *,
    payload: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Publish the first slate game with a verified two-book spread quorum."""
    market = dict(payload) if payload is not None else load_market_payload(schedule_games)
    source = str(market.get("source") or "SportsGameOdds")
    if str(market.get("verification") or "").upper() != "VERIFIED":
        return {
            "verification": "UNAVAILABLE",
            "diagnostic_state": str(market.get("diagnostic_state") or "SPORTSBOOK_OBSERVATIONS_NOT_VERIFIED"),
            "source": source,
            "fabrication": False,
            "page_wide_source_authority": False,
        }

    observations = market.get("observations") or []
    rows = [dict(row) for row in observations if isinstance(row, Mapping)] if isinstance(observations, Sequence) and not isinstance(observations, (str, bytes)) else []
    games_by_pair = {
        (str(game.get("away_tricode") or "").strip().upper(), str(game.get("home_tricode") or "").strip().upper()): game
        for game in schedule_games
        if str(game.get("status") or "").strip().upper() in ELIGIBLE_STATES
    }

    for pair in _eligible_pairs(schedule_games):
        pair_rows = [
            row for row in rows
            if str(row.get("away_tricode") or "").strip().upper() == pair[0]
            and str(row.get("home_tricode") or "").strip().upper() == pair[1]
        ]
        books = {str(row.get("sportsbook") or "").strip().casefold() for row in pair_rows if str(row.get("sportsbook") or "").strip()}
        if len(books) < 2:
            continue
        game = games_by_pair.get(pair)
        if game is None:
            continue
        result = build_spread_market_context(pair_rows, [game])
        if result.get("verification") == "VERIFIED":
            result["source"] = source
            result["fabrication"] = False
            result["page_wide_source_authority"] = False
            return result

    return {
        "verification": "UNAVAILABLE",
        "diagnostic_state": "CONSENSUS_QUORUM_NOT_MET",
        "source": source,
        "fabrication": False,
        "page_wide_source_authority": False,
    }


__all__ = [
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_RANKING",
    "MAY_MODIFY_FROZEN_STEPS",
    "METRIC_SUBSTITUTION",
    "resolve_sgo_api_key",
    "load_public_betting_payload",
    "build_public_betting_features",
    "load_market_payload",
    "build_market_feature",
]
