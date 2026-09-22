"""Step 9A exact-game-ID MLB live game state API contract.

Step 9A defines only the read-only validation boundary that a later Step 9 stage
may use to transport official MLB live game state into the existing V19.3 Live
Game page. It does not collect live state, add an API endpoint, change Streamlit
routing, replace the existing direct MLB Stats API transport, or alter V19 live
simulation / run expectancy / probability / market logic.

Identity is deliberately strict: one live game state is keyed only by the exact
official MLB gamePk. Team names, pitcher/batter names, scores and display text are
metadata and never participate in matching. Synthetic IDs, fractional coercion,
Unicode numeral coercion, duplicate official IDs, stale or unproven snapshots,
and structurally invalid payloads fail closed. Invalid unrelated rows are
isolated when the remaining exact-ID rows are unambiguous.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import math
from typing import Any, Mapping

DATA_TYPE = "mlb_step9a_live_game_state_api_contract_v1"
CONTEXT_DATA_TYPE = "mlb_step9a_live_game_state_context_v1"
SCHEMA_VERSION = 1
EXPECTED_API_DATA_TYPE = "mlb_live_game_state_api_response_v1"
EXPECTED_API_SCHEMA_VERSION = 1
EXPECTED_SOURCE = "MLB Stats API"
MATCH_METHOD = "official_mlb_game_id_exact"
API_CONNECTED = "API_LIVE_GAME_STATE_CONTEXT_AVAILABLE"
FALLBACK = "LIVE_GAME_STATE_API_CONTEXT_UNAVAILABLE"
DEFAULT_MAX_SNAPSHOT_AGE_SECONDS = 20.0
MAX_FUTURE_CLOCK_SKEW_SECONDS = 5.0

PREGAME = "PREGAME"
LIVE = "LIVE"
DELAYED = "DELAYED"
FINAL = "FINAL"
SUPPORTED_STATES = frozenset({PREGAME, LIVE, DELAYED, FINAL})

PROTECTED_FALSE_FLAGS = (
    "model_math_impact",
    "projection_impact",
    "simulation_impact",
    "probability_impact",
    "run_expectancy_impact",
    "live_win_probability_impact",
    "run_line_model_impact",
    "total_model_impact",
    "history_adjustment_impact",
    "ranking_impact",
    "selection_impact",
    "fair_odds_impact",
    "sportsbook_sync_impact",
    "sportsbook_price_model_input",
    "streamlit_presentation_impact",
    "production_exposure_impact",
    "wagering_impact",
    "durable_persistence",
    "wnba_impact",
)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _ascii_int(value: Any, *, minimum: int = 0) -> int | None:
    """Accept integers or ASCII-decimal serialized integers only.

    Floats (including 823340.0), booleans, signs, exponent strings and Unicode
    numeral glyphs are rejected so identity cannot be created through coercion.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= minimum else None
    if isinstance(value, str):
        text = value.strip()
        if not text or not text.isascii() or not text.isdecimal():
            return None
        parsed = int(text)
        return parsed if parsed >= minimum else None
    return None


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except Exception:
        return None
    return parsed if math.isfinite(parsed) else None


def _utc_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except Exception:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _canonical_state(value: Any) -> str | None:
    state = str(value or "").strip().upper()
    return state if state in SUPPORTED_STATES else None


def _optional_player_id(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return _ascii_int(value, minimum=1)


def _optional_nonnegative_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return _ascii_int(value, minimum=0)


def _normalized_recent_plays(value: Any) -> list[dict[str, Any]] | None:
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        return None
    out: list[dict[str, Any]] = []
    for raw in value[:5]:
        if not isinstance(raw, Mapping):
            return None
        out.append(deepcopy(dict(raw)))
    return out


def _base_state() -> dict[str, Any]:
    state = {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "integration_status": FALLBACK,
        "api_integration_active": False,
        "source": EXPECTED_SOURCE,
        "api_data_type": None,
        "collected_at_utc": None,
        "match_method": MATCH_METHOD,
        "fallback_matching_used": False,
        "team_name_matching_used": False,
        "player_name_matching_used": False,
        "fuzzy_matching_allowed": False,
        "synthetic_game_id_allowed": False,
        "unverified_game_id_allowed": False,
        "production_endpoint_added": False,
        "live_state_collection_added": False,
        "preexisting_v19_live_model_preserved": True,
        "preexisting_direct_transport_preserved": True,
        "contexts_by_official_game_id": {},
        "api_game_count": 0,
        "usable_live_game_count": 0,
        "unusable_live_game_count": 0,
        "unusable_game_rows": [],
        "snapshot_age_seconds": None,
        "feed_fresh": None,
        "max_snapshot_age_seconds": DEFAULT_MAX_SNAPSHOT_AGE_SECONDS,
        "failures": [],
    }
    state.update({key: False for key in PROTECTED_FALSE_FLAGS})
    return state


def build_live_game_state_api_state(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Validate a future live-state API payload into exact gamePk contexts."""
    body = deepcopy(_mapping(payload))
    state = _base_state()
    failures: list[str] = []
    contexts: dict[int, dict[str, Any]] = {}
    unusable_rows: list[dict[str, Any]] = []

    if body.get("data_type") != EXPECTED_API_DATA_TYPE:
        failures.append("unexpected_api_data_type")
    if body.get("schema_version") != EXPECTED_API_SCHEMA_VERSION:
        failures.append("unexpected_api_schema_version")
    if body.get("source") != EXPECTED_SOURCE:
        failures.append("unexpected_api_source")
    if _utc_datetime(body.get("collected_at_utc")) is None:
        failures.append("invalid_or_missing_collected_at_utc")

    games = body.get("games")
    if not isinstance(games, list):
        failures.append("games_not_list")
        games = []

    seen: set[int] = set()
    for index, raw_game in enumerate(games):
        row = _mapping(raw_game)
        game_id = _ascii_int(row.get("official_game_id"), minimum=1)
        canonical_state = _canonical_state(row.get("state"))
        status = str(row.get("status") or "").strip()
        away_team = str(row.get("away_team") or "").strip()
        home_team = str(row.get("home_team") or "").strip()
        away_runs = _ascii_int(row.get("away_runs"), minimum=0)
        home_runs = _ascii_int(row.get("home_runs"), minimum=0)

        if None in (game_id, canonical_state, away_runs, home_runs) or not status or not away_team or not home_team:
            unusable_rows.append({"index": index, "reason": "invalid_required_live_game_fields"})
            continue

        if game_id in seen:
            failures.append("duplicate_exact_official_game_id")
            unusable_rows.append({
                "index": index,
                "reason": "duplicate_exact_official_game_id",
                "official_game_id": game_id,
            })
            continue
        seen.add(game_id)

        balls = _optional_nonnegative_int(row.get("balls"))
        strikes = _optional_nonnegative_int(row.get("strikes"))
        outs = _optional_nonnegative_int(row.get("outs"))
        if balls is not None and balls > 4:
            balls = None
        if strikes is not None and strikes > 3:
            strikes = None
        if outs is not None and outs > 3:
            outs = None

        batter_id = _optional_player_id(row.get("batter_id"))
        pitcher_id = _optional_player_id(row.get("pitcher_id"))
        runner_first_id = _optional_player_id(row.get("runner_first_id"))
        runner_second_id = _optional_player_id(row.get("runner_second_id"))
        runner_third_id = _optional_player_id(row.get("runner_third_id"))

        supplied_optional_ids = (
            ("batter_id", row.get("batter_id"), batter_id),
            ("pitcher_id", row.get("pitcher_id"), pitcher_id),
            ("runner_first_id", row.get("runner_first_id"), runner_first_id),
            ("runner_second_id", row.get("runner_second_id"), runner_second_id),
            ("runner_third_id", row.get("runner_third_id"), runner_third_id),
        )
        if any(raw not in (None, "") and parsed is None for _, raw, parsed in supplied_optional_ids):
            unusable_rows.append({
                "index": index,
                "reason": "invalid_optional_official_player_id",
                "official_game_id": game_id,
            })
            continue

        recent_plays = _normalized_recent_plays(row.get("recent_plays"))
        if recent_plays is None:
            unusable_rows.append({
                "index": index,
                "reason": "recent_plays_not_list_of_mappings",
                "official_game_id": game_id,
            })
            continue

        inning = str(row.get("inning") or "").strip() or None
        inning_state = str(row.get("inning_state") or "").strip() or None
        if canonical_state == LIVE and (inning is None or inning_state is None or None in (balls, strikes, outs)):
            unusable_rows.append({
                "index": index,
                "reason": "live_state_missing_inning_or_count",
                "official_game_id": game_id,
            })
            continue

        last_pitch_speed = None
        if row.get("last_pitch_speed") not in (None, ""):
            last_pitch_speed = _finite_number(row.get("last_pitch_speed"))
            if last_pitch_speed is None or last_pitch_speed < 0:
                unusable_rows.append({
                    "index": index,
                    "reason": "invalid_last_pitch_speed",
                    "official_game_id": game_id,
                })
                continue

        contexts[game_id] = {
            "official_game_id": game_id,
            "status": status,
            "state": canonical_state,
            "away_team": away_team,
            "home_team": home_team,
            "away_runs": away_runs,
            "home_runs": home_runs,
            "away_hits": _optional_nonnegative_int(row.get("away_hits")),
            "home_hits": _optional_nonnegative_int(row.get("home_hits")),
            "away_errors": _optional_nonnegative_int(row.get("away_errors")),
            "home_errors": _optional_nonnegative_int(row.get("home_errors")),
            "inning": inning,
            "inning_state": inning_state,
            "balls": balls,
            "strikes": strikes,
            "outs": outs,
            "batter_id": batter_id,
            "batter": str(row.get("batter") or "").strip() or None,
            "pitcher_id": pitcher_id,
            "pitcher": str(row.get("pitcher") or "").strip() or None,
            "on_deck": str(row.get("on_deck") or "").strip() or None,
            "in_hole": str(row.get("in_hole") or "").strip() or None,
            "runner_first_id": runner_first_id,
            "first": str(row.get("first") or "").strip() or None,
            "runner_second_id": runner_second_id,
            "second": str(row.get("second") or "").strip() or None,
            "runner_third_id": runner_third_id,
            "third": str(row.get("third") or "").strip() or None,
            "last_play": str(row.get("last_play") or "").strip() or None,
            "last_pitch_desc": str(row.get("last_pitch_desc") or "").strip() or None,
            "last_pitch_type": str(row.get("last_pitch_type") or "").strip() or None,
            "last_pitch_speed": last_pitch_speed,
            "recent_plays": recent_plays,
            "match_method": MATCH_METHOD,
            "fallback_matching_used": False,
            "team_name_matching_used": False,
        }

    if not games:
        failures.append("empty_live_game_slate")
    if not contexts:
        failures.append("no_usable_live_game_contexts")

    active = not failures
    state.update({
        "integration_status": API_CONNECTED if active else FALLBACK,
        "api_integration_active": active,
        "api_data_type": body.get("data_type"),
        "collected_at_utc": body.get("collected_at_utc"),
        "contexts_by_official_game_id": contexts,
        "api_game_count": len(games),
        "usable_live_game_count": len(contexts),
        "unusable_live_game_count": len(unusable_rows),
        "unusable_game_rows": unusable_rows,
        "failures": list(dict.fromkeys(failures)),
    })
    return state


def enforce_live_game_state_api_freshness(
    api_state: Mapping[str, Any] | None,
    *,
    as_of_utc: datetime | str | None = None,
    max_age_seconds: float = DEFAULT_MAX_SNAPSHOT_AGE_SECONDS,
) -> dict[str, Any]:
    """Require explicitly proven freshness before any live-game context is exposed."""
    state = deepcopy(_mapping(api_state))
    failures = list(state.get("failures") or [])
    max_age = _finite_number(max_age_seconds)
    if max_age is None or max_age < 0:
        raise ValueError("max_age_seconds must be a finite non-negative number")

    collected = _utc_datetime(state.get("collected_at_utc"))
    as_of = _utc_datetime(as_of_utc) if as_of_utc is not None else datetime.now(timezone.utc)
    if as_of is None:
        raise ValueError("as_of_utc must be a parseable datetime")

    age: float | None = None
    fresh = False
    if collected is None:
        if "invalid_or_missing_collected_at_utc" not in failures:
            failures.append("invalid_or_missing_collected_at_utc")
    else:
        raw_age = (as_of - collected).total_seconds()
        if raw_age < -MAX_FUTURE_CLOCK_SKEW_SECONDS:
            failures.append("api_snapshot_from_future")
        else:
            age = max(0.0, raw_age)
            fresh = age <= max_age
            if not fresh:
                failures.append("api_snapshot_stale")

    if failures:
        state["integration_status"] = FALLBACK
        state["api_integration_active"] = False
    state["snapshot_age_seconds"] = age
    state["feed_fresh"] = fresh and not failures
    state["max_snapshot_age_seconds"] = max_age
    state["failures"] = list(dict.fromkeys(failures))
    state["preexisting_v19_live_model_preserved"] = True
    state["preexisting_direct_transport_preserved"] = True
    return state


def live_game_state_for_official_game_id(
    api_state: Mapping[str, Any] | None,
    *,
    official_game_id: Any,
) -> dict[str, Any] | None:
    """Return one fresh context only for the exact official MLB gamePk."""
    state = deepcopy(_mapping(api_state))
    if state.get("api_integration_active") is not True or state.get("feed_fresh") is not True:
        return None
    if state.get("match_method") != MATCH_METHOD:
        return None
    for key in (
        "fallback_matching_used",
        "team_name_matching_used",
        "player_name_matching_used",
        "fuzzy_matching_allowed",
        "synthetic_game_id_allowed",
        "unverified_game_id_allowed",
    ):
        if state.get(key) is not False:
            return None
    if state.get("sportsbook_price_model_input") is not False:
        return None

    game_id = _ascii_int(official_game_id, minimum=1)
    if game_id is None:
        return None
    contexts = state.get("contexts_by_official_game_id")
    if not isinstance(contexts, Mapping):
        return None
    context = _mapping(contexts.get(game_id))
    if _ascii_int(context.get("official_game_id"), minimum=1) != game_id:
        return None
    if _canonical_state(context.get("state")) is None:
        return None
    if context.get("match_method") != MATCH_METHOD:
        return None
    if context.get("fallback_matching_used") is not False:
        return None
    if context.get("team_name_matching_used") is not False:
        return None

    out = deepcopy(context)
    out.update({
        "data_type": CONTEXT_DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "source": EXPECTED_SOURCE,
        "snapshot_age_seconds": state.get("snapshot_age_seconds"),
        "feed_fresh": True,
        "player_name_matching_used": False,
        "fuzzy_matching_allowed": False,
        "synthetic_game_id_allowed": False,
        "sportsbook_price_model_input": False,
    })
    return out


__all__ = [
    "DATA_TYPE",
    "CONTEXT_DATA_TYPE",
    "SCHEMA_VERSION",
    "EXPECTED_API_DATA_TYPE",
    "EXPECTED_API_SCHEMA_VERSION",
    "EXPECTED_SOURCE",
    "MATCH_METHOD",
    "API_CONNECTED",
    "FALLBACK",
    "DEFAULT_MAX_SNAPSHOT_AGE_SECONDS",
    "PREGAME",
    "LIVE",
    "DELAYED",
    "FINAL",
    "SUPPORTED_STATES",
    "PROTECTED_FALSE_FLAGS",
    "build_live_game_state_api_state",
    "enforce_live_game_state_api_freshness",
    "live_game_state_for_official_game_id",
]
