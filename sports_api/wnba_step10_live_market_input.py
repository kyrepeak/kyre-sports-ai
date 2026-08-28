"""Step 10A: strict caller-supplied WNBA live market input contract.

This layer standardizes raw WNBA player-prop quotes before any sportsbook adapter,
market-snapshot reconciliation, Step-9 comparison, ranking, persistence, scheduler,
or production path is allowed to run.

It accepts caller-supplied market records only. It does not fetch a sportsbook,
change a basketball projection, calculate model probability, remove vig, calculate
edge/EV, form cross-book consensus, rank plays, write Supabase, or persist state.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from typing import Any, Mapping, Sequence

from sports_api import wnba_step9_release_freeze as step9_freeze

SOURCE = "Kyre Sports API WNBA Step 10A live market input contract"
SCHEMA_VERSION = "wnba_step_10a_live_market_input_v1"
MODEL_VERSION = "wnba_step10a_strict_live_market_normalization_2026_regular_v1"
RELEASE_ID = "wnba_step10a_live_market_input_2026_regular_season_v1"
STEP10A_LIVE_MARKET_INPUT_ENABLED_ENV = "WNBA_STEP10A_LIVE_MARKET_INPUT_ENABLED"
STEP9_FROZEN_HEAD_SHA = "bd228921ea993c8c74b6454ae56cee94711b0e94"

MAX_RECORDS = 5_000
MAX_PROP_LINE = 250.0
MAX_AMERICAN_ODDS = 100_000
MARKET_FUTURE_TOLERANCE_SECONDS = 120
SUPPORTED_STATS = ("points", "rebounds", "assists", "pra")
STAT_ALIASES = {
    "points": "points",
    "point": "points",
    "pts": "points",
    "rebounds": "rebounds",
    "rebound": "rebounds",
    "reb": "rebounds",
    "rebs": "rebounds",
    "assists": "assists",
    "assist": "assists",
    "ast": "assists",
    "asts": "assists",
    "pra": "pra",
    "points+rebounds+assists": "pra",
    "points rebounds assists": "pra",
}

_OFF_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)


class WNBAStep10LiveMarketInputDisabledError(RuntimeError):
    """Raised when Step 10A is not explicitly enabled or production is unsafe."""


class WNBAStep10LiveMarketInputDuplicateError(ValueError):
    """Raised when one snapshot contains an ambiguous duplicate quote identity."""


class WNBAStep10LiveMarketInputIdentityError(ValueError):
    """Raised when records disagree about a shared game/player identity."""


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step10a_live_market_input_enabled(
    env: Mapping[str, str] | None = None,
) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP10A_LIVE_MARKET_INPUT_ENABLED_ENV))


def _assert_safe_environment(env: Mapping[str, str] | None = None) -> None:
    source = os.environ if env is None else env
    bad = [name for name in _OFF_ENV_KEYS if _truthy(source.get(name))]
    if bad:
        raise WNBAStep10LiveMarketInputDisabledError(
            "Step 10A refuses to run while production switches are enabled: "
            + ", ".join(bad)
        )
    if not _truthy(source.get(STEP10A_LIVE_MARKET_INPUT_ENABLED_ENV)):
        raise WNBAStep10LiveMarketInputDisabledError(
            f"Step 10A requires {STEP10A_LIVE_MARKET_INPUT_ENABLED_ENV}=true."
        )
    if step9_freeze.DEFAULT_ENABLED is not False:
        raise WNBAStep10LiveMarketInputDisabledError(
            "Step 10A requires the frozen Step-9 API to remain default-OFF."
        )
    if step9_freeze.PRODUCTION_ACTIVATION_ALLOWED is not False:
        raise WNBAStep10LiveMarketInputDisabledError(
            "Step 10A requires frozen Step-9 production activation to remain disallowed."
        )


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _clean_text(value: Any, label: str, *, maximum: int) -> str:
    text = " ".join(str(value or "").strip().split())
    if not text or len(text) > maximum:
        raise ValueError(f"WNBA {label} must contain 1 through {maximum} characters.")
    return text


def _game_id(value: Any) -> str:
    text = str(value or "").strip()
    if len(text) != 10 or not text.isdigit():
        raise ValueError("WNBA game_id must be exactly 10 digits.")
    return text


def _player_id(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("WNBA player_id must be a positive integer.")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("WNBA player_id must be a positive integer.") from exc
    if result <= 0 or str(result) != str(value).strip():
        if not isinstance(value, int):
            raise ValueError("WNBA player_id must be a positive integer.")
    return result


def _stat(value: Any) -> str:
    text = " ".join(str(value or "").strip().casefold().split())
    result = STAT_ALIASES.get(text)
    if result is None:
        raise ValueError(
            f"Unsupported WNBA prop stat {value!r}. Allowed canonical values: "
            + ", ".join(SUPPORTED_STATS)
            + "."
        )
    return result


def _line(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError(f"WNBA prop line must be a number from 0 through {MAX_PROP_LINE:g}.")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"WNBA prop line must be a number from 0 through {MAX_PROP_LINE:g}."
        ) from exc
    if not math.isfinite(result) or not 0.0 <= result <= MAX_PROP_LINE:
        raise ValueError(f"WNBA prop line must be a number from 0 through {MAX_PROP_LINE:g}.")
    return round(result, 6)


def _american_odds(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"WNBA {label} must be integer American odds with absolute value >= 100.")
    if isinstance(value, float) and not value.is_integer():
        raise ValueError(f"WNBA {label} must be integer American odds with absolute value >= 100.")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"WNBA {label} must be integer American odds with absolute value >= 100."
        ) from exc
    if abs(result) < 100 or abs(result) > MAX_AMERICAN_ODDS:
        raise ValueError(
            f"WNBA {label} must have absolute value from 100 through {MAX_AMERICAN_ODDS}."
        )
    return result


def _parse_timestamp(value: Any) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("WNBA market_captured_at_utc is required.")
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(
            "WNBA market_captured_at_utc must be an ISO-8601 timestamp with timezone."
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(
            "WNBA market_captured_at_utc must include a timezone offset."
        )
    return parsed.astimezone(timezone.utc)


def _evaluation_time(value: datetime | None) -> datetime:
    result = datetime.now(timezone.utc) if value is None else value
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("WNBA evaluated_at must be timezone-aware.")
    return result.astimezone(timezone.utc)


def _normalize_record(record: Mapping[str, Any], *, evaluated_at: datetime) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        raise ValueError("WNBA Step 10A market records must be objects.")

    allowed = {
        "game_id",
        "player_id",
        "player_name",
        "sportsbook",
        "stat",
        "line",
        "over_odds",
        "under_odds",
        "market_captured_at_utc",
    }
    extra = sorted(str(key) for key in record if key not in allowed)
    missing = sorted(key for key in allowed if key not in record)
    if extra:
        raise ValueError("WNBA Step 10A rejects unknown market fields: " + ", ".join(extra))
    if missing:
        raise ValueError("WNBA Step 10A missing required market fields: " + ", ".join(missing))

    game = _game_id(record.get("game_id"))
    player = _player_id(record.get("player_id"))
    player_name = _clean_text(record.get("player_name"), "player_name", maximum=120)
    sportsbook = _clean_text(record.get("sportsbook"), "sportsbook", maximum=80)
    stat = _stat(record.get("stat"))
    line = _line(record.get("line"))
    over_odds = _american_odds(record.get("over_odds"), "over_odds")
    under_odds = _american_odds(record.get("under_odds"), "under_odds")
    captured = _parse_timestamp(record.get("market_captured_at_utc"))
    delta_seconds = (evaluated_at - captured).total_seconds()
    if delta_seconds < -MARKET_FUTURE_TOLERANCE_SECONDS:
        raise ValueError(
            "WNBA market_captured_at_utc cannot be more than 120 seconds in the future."
        )
    age_seconds = max(0.0, delta_seconds)

    quote_core = {
        "game_id": game,
        "player_id": player,
        "player_name": player_name,
        "sportsbook": sportsbook,
        "stat": stat,
        "line": line,
        "over_odds": over_odds,
        "under_odds": under_odds,
        "market_captured_at_utc": captured.isoformat(),
    }
    return {
        **quote_core,
        "quote_id": _canonical_hash(quote_core),
        "market_age_seconds_at_evaluation": round(age_seconds, 3),
    }


def _duplicate_key(record: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        record["game_id"],
        int(record["player_id"]),
        record["stat"],
        str(record["sportsbook"]).casefold(),
        float(record["line"]),
    )


def _content_record(record: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(record)
    result.pop("market_age_seconds_at_evaluation", None)
    return result


def build_step10a_live_market_input_snapshot(
    records: Sequence[Mapping[str, Any]],
    *,
    evaluated_at: datetime | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Normalize one caller-supplied WNBA player-prop market snapshot.

    Duplicate identity is sportsbook + game + player + stat + exact line. Alternative
    lines from one book are allowed; multiple updates of the exact same book/line in
    one snapshot are rejected so Step 10C can later own line-movement history.
    """
    _assert_safe_environment(env)
    if isinstance(records, (str, bytes)) or not isinstance(records, Sequence):
        raise ValueError("WNBA Step 10A records must be a sequence of market objects.")
    if not 1 <= len(records) <= MAX_RECORDS:
        raise ValueError(f"WNBA Step 10A requires 1 through {MAX_RECORDS} market records.")

    evaluated = _evaluation_time(evaluated_at)
    normalized = [_normalize_record(record, evaluated_at=evaluated) for record in records]

    seen_quotes: dict[tuple[Any, ...], dict[str, Any]] = {}
    player_names: dict[tuple[str, int], str] = {}
    for record in normalized:
        duplicate_key = _duplicate_key(record)
        if duplicate_key in seen_quotes:
            prior = seen_quotes[duplicate_key]
            raise WNBAStep10LiveMarketInputDuplicateError(
                "Step 10A refuses duplicate sportsbook/game/player/stat/line records: "
                f"{record['sportsbook']} {record['game_id']} {record['player_id']} "
                f"{record['stat']} {record['line']}; timestamps "
                f"{prior['market_captured_at_utc']} and {record['market_captured_at_utc']}."
            )
        seen_quotes[duplicate_key] = record

        identity_key = (record["game_id"], int(record["player_id"]))
        normalized_name = str(record["player_name"]).casefold()
        prior_name = player_names.get(identity_key)
        if prior_name is not None and prior_name != normalized_name:
            raise WNBAStep10LiveMarketInputIdentityError(
                "Step 10A found conflicting player_name values for the same game_id/player_id."
            )
        player_names[identity_key] = normalized_name

    normalized.sort(
        key=lambda item: (
            item["game_id"],
            int(item["player_id"]),
            item["stat"],
            str(item["sportsbook"]).casefold(),
            float(item["line"]),
            item["market_captured_at_utc"],
        )
    )

    captured_times = [_parse_timestamp(item["market_captured_at_utc"]) for item in normalized]
    earliest = min(captured_times)
    latest = max(captured_times)
    unique_games = sorted({item["game_id"] for item in normalized})
    unique_players = sorted({(item["game_id"], int(item["player_id"])) for item in normalized})
    unique_books = sorted({str(item["sportsbook"]) for item in normalized}, key=str.casefold)
    unique_stats = sorted({str(item["stat"]) for item in normalized})

    result = {
        "data_type": "wnba_live_player_prop_market_input_snapshot",
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "release_id": RELEASE_ID,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "evaluated_at_utc": evaluated.isoformat(),
        "snapshot": {
            "record_count": len(normalized),
            "unique_game_count": len(unique_games),
            "unique_player_game_count": len(unique_players),
            "unique_sportsbook_count": len(unique_books),
            "unique_stat_count": len(unique_stats),
            "unique_game_ids": unique_games,
            "unique_sportsbooks": unique_books,
            "unique_stats": unique_stats,
            "earliest_market_capture_utc": earliest.isoformat(),
            "latest_market_capture_utc": latest.isoformat(),
            "capture_spread_seconds": round((latest - earliest).total_seconds(), 3),
            "future_clock_tolerance_seconds": MARKET_FUTURE_TOLERANCE_SECONDS,
        },
        "records": normalized,
        "lineage": {
            "step9_release_id": step9_freeze.RELEASE_ID,
            "step9_integration_version": step9_freeze.INTEGRATION_VERSION,
            "step9_frozen_head_sha": STEP9_FROZEN_HEAD_SHA,
            "step9_default_enabled": step9_freeze.DEFAULT_ENABLED,
            "step9_production_activation_allowed": step9_freeze.PRODUCTION_ACTIVATION_ALLOWED,
        },
        "contract": {
            "quote_source": "caller_supplied_only",
            "duplicate_identity": "sportsbook+game_id+player_id+stat+exact_line",
            "alternative_lines_from_same_sportsbook_allowed": True,
            "multiple_updates_same_book_same_line_same_snapshot_allowed": False,
            "timestamp_must_be_timezone_aware": True,
            "timestamp_normalized_to_utc": True,
            "player_name_consistent_within_game_player_identity": True,
            "step10c_owns_staleness_line_movement_and_snapshot_reconciliation": True,
        },
        "guardrails": {
            "basketball_projection_changed": False,
            "step8_distribution_changed": False,
            "step9_called": False,
            "sportsbook_quote_consumed": True,
            "sportsbook_network_fetch_performed": False,
            "sportsbook_adapter_applied": False,
            "vig_removed": False,
            "edge_calculated": False,
            "expected_value_calculated": False,
            "cross_sportsbook_consensus_calculated": False,
            "line_movement_calculated": False,
            "cross_prop_ranking_calculated": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "scheduler_started": False,
            "production_runtime_enabled": False,
            "production_activation_allowed": False,
        },
    }

    hash_surface = {
        "data_type": result["data_type"],
        "schema_version": result["schema_version"],
        "source": result["source"],
        "model_version": result["model_version"],
        "release_id": result["release_id"],
        "snapshot": {
            key: value
            for key, value in result["snapshot"].items()
            if key != "future_clock_tolerance_seconds"
        },
        "records": [_content_record(record) for record in normalized],
        "lineage": result["lineage"],
        "contract": result["contract"],
        "guardrails": result["guardrails"],
    }
    result["snapshot_content_sha256"] = _canonical_hash(hash_surface)
    _assert_safe_environment(env)
    return result
