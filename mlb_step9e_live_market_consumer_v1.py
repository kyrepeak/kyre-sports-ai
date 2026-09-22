"""Step 9E API-first live-market transport for the frozen MLB V19.2.2 UI.

This module changes transport only. V19.2.2 keeps ownership of settlement-line
sync, Streamlit state, model-vs-market probability math and edge grading. The
transport wrapper first requests the hosted Step 9D FanDuel in-play endpoint by
exact official MLB gamePk, validates the row through the frozen Step 5.2 market
context, and maps that row into the snapshot shape V19.2.2 already consumes.
Any network, freshness, schema, identity or market-completeness failure delegates
to the original Odds-API.io connection/snapshot path unchanged.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from typing import Any, Mapping
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sports_api.mlb_live_market_context_v1 import market_context_from_game

DATA_TYPE = "mlb_step9e_live_market_consumer_v1"
SCHEMA_VERSION = 1
DEFAULT_API_BASE_URL = "https://kyre-sports-api.onrender.com"
DEFAULT_TIMEOUT_SECONDS = 8.0
DEFAULT_MAX_SNAPSHOT_AGE_SECONDS = 180.0
API_SENTINEL = "__kyre_step9e_api_first__"
MATCH_METHOD = "official_mlb_game_id_exact"

PROTECTED_FALSE_FLAGS = (
    "model_math_impact",
    "projection_impact",
    "simulation_math_impact",
    "probability_math_impact",
    "run_expectancy_math_impact",
    "edge_grading_math_impact",
    "ranking_impact",
    "selection_impact",
    "sportsbook_price_model_input",
    "team_name_matching_used",
    "player_name_matching_used",
    "fuzzy_matching_used",
    "synthetic_game_id_used",
    "durable_persistence",
    "wnba_impact",
)

_LAST_STATUS: dict[str, Any] = {
    "data_type": DATA_TYPE,
    "schema_version": SCHEMA_VERSION,
    "installed": False,
    "api_attempted": False,
    "api_used": False,
    "legacy_fallback_used": False,
    "official_game_id": None,
    "failure": None,
    **{key: False for key in PROTECTED_FALSE_FLAGS},
}


def _strict_positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str):
        text = value.strip()
        if text and text.isascii() and text.isdecimal():
            parsed = int(text)
            return parsed if parsed > 0 else None
    return None


def _utc_dt(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _fmt_american(value: Any) -> str:
    if isinstance(value, bool):
        raise ValueError("American odds cannot be boolean")
    return f"{int(round(float(value))):+d}"


def _fmt_line(value: Any) -> str:
    if isinstance(value, bool):
        raise ValueError("market line cannot be boolean")
    return f"{float(value):+g}"


def _base_url() -> str:
    value = str(os.getenv("KYRE_SPORTS_API_BASE_URL") or DEFAULT_API_BASE_URL).strip()
    return value.rstrip("/")


def _api_payload(
    official_game_id: int,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    params = urlencode(
        {
            "official_game_id": official_game_id,
            "max_events": 30,
            "fully_priced_only": "true",
        }
    )
    request = Request(
        f"{_base_url()}/api/v1/mlb/live-odds?{params}",
        headers={
            "Accept": "application/json",
            "User-Agent": "KyreSportsMLBStep9EConsumer/1.0",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=float(timeout)) as response:
            status = int(getattr(response, "status", 0) or 0)
            if status != 200:
                raise RuntimeError(f"live-odds API returned HTTP {status}")
            raw = response.read(2_000_001)
    except HTTPError as exc:
        raise RuntimeError(f"live-odds API returned HTTP {exc.code}") from exc
    if len(raw) > 2_000_000:
        raise RuntimeError("live-odds API response exceeded 2 MB")
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("live-odds API did not return a JSON object")
    return payload


def _snapshot_from_payload(
    payload: Mapping[str, Any],
    *,
    official_game_id: int,
    as_of_utc: datetime | None = None,
) -> dict[str, Any] | None:
    game_id = _strict_positive_int(official_game_id)
    if game_id is None:
        return None
    if not isinstance(payload, Mapping):
        return None
    if payload.get("data_type") != "mlb_inplay_odds_api_response_v1":
        return None
    if payload.get("schema_version") != 1:
        return None
    if payload.get("source") != "FanDuel":
        return None
    if payload.get("market_phase") != "IN_PLAY":
        return None
    if payload.get("fuzzy_matching_used") is not False:
        return None
    if payload.get("synthetic_game_id_used") is not False:
        return None
    if _strict_positive_int(payload.get("requested_official_game_id")) != game_id:
        return None

    collected = _utc_dt(payload.get("collected_at_utc"))
    now = as_of_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        return None
    now = now.astimezone(timezone.utc)
    if collected is None:
        return None
    age = (now - collected).total_seconds()
    if age < -30.0 or age > DEFAULT_MAX_SNAPSHOT_AGE_SECONDS:
        return None

    games = payload.get("games")
    if not isinstance(games, list) or len(games) != 1:
        return None
    raw_game = games[0]
    if not isinstance(raw_game, Mapping):
        return None
    if _strict_positive_int(raw_game.get("official_game_id")) != game_id:
        return None
    if raw_game.get("market_phase") != "IN_PLAY":
        return None
    if raw_game.get("in_play") is not True:
        return None
    if raw_game.get("fully_priced") is not True:
        return None
    if raw_game.get("fuzzy_matching_used") is not False:
        return None
    if raw_game.get("synthetic_game_id_used") is not False:
        return None

    context = market_context_from_game(deepcopy(dict(raw_game)))
    if context is None:
        return None
    if _strict_positive_int(context.get("official_game_id")) != game_id:
        return None
    if context.get("match_method") != MATCH_METHOD:
        return None
    if context.get("fallback_matching_used") is not False:
        return None

    moneyline = context["moneyline"]
    run_line = context["run_line"]
    total = context["total"]
    age_seconds = max(0, int(age))
    row = {
        "Book": "FanDuel",
        "Away ML": int(round(float(moneyline["away_odds"]))),
        "Home ML": int(round(float(moneyline["home_odds"]))),
        "Away RL": f"{_fmt_line(run_line['away_line'])} ({_fmt_american(run_line['away_odds'])})",
        "Home RL": f"{_fmt_line(run_line['home_line'])} ({_fmt_american(run_line['home_odds'])})",
        "Over": f"O {float(total['line']):g} ({_fmt_american(total['over_odds'])})",
        "Under": f"U {float(total['line']):g} ({_fmt_american(total['under_odds'])})",
        "updatedAt": collected.isoformat(),
        "home_hdp": float(run_line["home_line"]),
        "total_line": float(total["line"]),
        "age_seconds": age_seconds,
    }
    away = raw_game.get("away_team") if isinstance(raw_game.get("away_team"), Mapping) else {}
    home = raw_game.get("home_team") if isinstance(raw_game.get("home_team"), Mapping) else {}
    return {
        "rows": [row],
        "home_spread": float(run_line["home_line"]),
        "total_line": float(total["line"]),
        "away": away.get("name"),
        "home": home.get("name"),
        "event_id": raw_game.get("sportsbook_event_id"),
        "official_game_id": game_id,
        "source": "FanDuel",
        "transport": "kyre_sports_api_step9d",
        "match_method": MATCH_METHOD,
        "fallback_matching_used": False,
        "fuzzy_matching_used": False,
        "synthetic_game_id_used": False,
    }


def snapshot_for_official_game_id(
    official_game_id: Any,
    *,
    payload_getter=None,
    as_of_utc: datetime | None = None,
) -> dict[str, Any] | None:
    game_id = _strict_positive_int(official_game_id)
    if game_id is None:
        return None
    getter = payload_getter or _api_payload
    payload = getter(game_id)
    return _snapshot_from_payload(
        payload,
        official_game_id=game_id,
        as_of_utc=as_of_utc,
    )


def consumer_status() -> dict[str, Any]:
    return deepcopy(_LAST_STATUS)


def install_step9e_live_market_consumer() -> dict[str, Any]:
    """Install API-first transport under the existing V19.2.2 market-sync logic."""
    import live_game_hub_v192 as v192
    import live_game_hub_v1921 as v1921

    current_snapshots = v1921.snapshots_for_games
    current_setup = v1921.render_connection_setup
    current_books = v1921.get_bookmakers
    legacy_snapshots = getattr(current_snapshots, "_step9e_legacy", current_snapshots)
    legacy_setup = getattr(current_setup, "_step9e_legacy", current_setup)
    legacy_books = getattr(current_books, "_step9e_legacy", current_books)

    def render_connection_setup_api_first(prefix="live_odds"):
        return API_SENTINEL

    render_connection_setup_api_first._step9e_legacy = legacy_setup
    render_connection_setup_api_first._step9e_wrapper = True

    def get_bookmakers_api_first():
        if _LAST_STATUS.get("api_used") is True:
            return "FanDuel"
        return legacy_books()

    get_bookmakers_api_first._step9e_legacy = legacy_books
    get_bookmakers_api_first._step9e_wrapper = True

    def snapshots_for_games_api_first(games_df, api_key=None, bookmakers=None):
        if games_df is None or getattr(games_df, "empty", True):
            return legacy_snapshots(games_df, api_key, bookmakers)

        try:
            rows = list(games_df.iterrows())
        except Exception:
            return legacy_snapshots(games_df, api_key, bookmakers)
        if len(rows) != 1:
            return legacy_snapshots(games_df, api_key, bookmakers)

        _, row = rows[0]
        try:
            raw_game_id = row.get("game_pk")
        except Exception:
            raw_game_id = None
        game_id = _strict_positive_int(raw_game_id)
        if game_id is None:
            return legacy_snapshots(games_df, api_key, bookmakers)

        _LAST_STATUS.update(
            {
                "installed": True,
                "api_attempted": True,
                "api_used": False,
                "legacy_fallback_used": False,
                "official_game_id": game_id,
                "failure": None,
            }
        )
        try:
            snapshot = snapshot_for_official_game_id(game_id)
            if snapshot is None:
                raise RuntimeError("Step 9E rejected hosted live-market context")
            if _strict_positive_int(snapshot.get("official_game_id")) != game_id:
                raise RuntimeError("Step 9E exact gamePk snapshot boundary failed")
            _LAST_STATUS.update(
                {
                    "api_used": True,
                    "legacy_fallback_used": False,
                    "failure": None,
                }
            )
            return {game_id: deepcopy(snapshot)}
        except Exception as exc:
            _LAST_STATUS.update(
                {
                    "api_used": False,
                    "legacy_fallback_used": True,
                    "failure": type(exc).__name__,
                }
            )
            legacy_key = legacy_setup("v192_step9e_fallback")
            if not legacy_key:
                return {}
            return legacy_snapshots(games_df, legacy_key, legacy_books())

    snapshots_for_games_api_first._step9e_legacy = legacy_snapshots
    snapshots_for_games_api_first._step9e_wrapper = True

    # V19.2 and V19.2.2 imported these transport callables into module globals.
    # Patch those bindings only; V19.2.2's _market_sync function is left intact.
    for module in (v192, v1921):
        module.render_connection_setup = render_connection_setup_api_first
        module.get_bookmakers = get_bookmakers_api_first
        module.snapshots_for_games = snapshots_for_games_api_first

    _LAST_STATUS.update({"installed": True})
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "installed": True,
        "patched_modules": ["live_game_hub_v192", "live_game_hub_v1921"],
        "api_first": True,
        "hosted_endpoint": "/api/v1/mlb/live-odds",
        "match_method": MATCH_METHOD,
        "legacy_odds_api_io_fallback_preserved": True,
        "v1922_market_sync_function_preserved": True,
        **{key: False for key in PROTECTED_FALSE_FLAGS},
    }


__all__ = [
    "API_SENTINEL",
    "DATA_TYPE",
    "DEFAULT_API_BASE_URL",
    "DEFAULT_MAX_SNAPSHOT_AGE_SECONDS",
    "DEFAULT_TIMEOUT_SECONDS",
    "MATCH_METHOD",
    "PROTECTED_FALSE_FLAGS",
    "SCHEMA_VERSION",
    "consumer_status",
    "install_step9e_live_market_consumer",
    "snapshot_for_official_game_id",
]
