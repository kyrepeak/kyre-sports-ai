"""Fail-closed Streamlit client for the production NFL Receiving Yards context API.

Consumes the certified Render/shared-host ``nfl_receiving_yards_context_v1``
contract. Exact ESPN event/team/athlete IDs are authoritative. Player/team
names and image URLs are display-only. Targets are accepted only when the API
explicitly marks ESPN target data available. Projection, market, EV, ranking,
staking and wager actions remain OFF.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
import os
import time
from typing import Any

import requests

MODEL_VERSION = "NFL RECEIVING YARDS CONTEXT CLIENT V1"
SCHEMA_VERSION = "nfl_receiving_yards_context_v1"
DEFAULT_API_BASE_URL = "https://kyre-sports-api.onrender.com"
MAX_FUTURE_SKEW_SECONDS = 30
REQUEST_CONNECT_TIMEOUT_SECONDS = 3.0
REQUEST_READ_TIMEOUT_SECONDS = 18.0
MAX_REQUEST_ATTEMPTS = 2
RETRY_BACKOFF_SECONDS = 0.35
ELIGIBLE_RECEIVER_POSITIONS = {"WR", "TE", "RB", "FB"}

_TRANSIENT_REQUEST_EXCEPTIONS = (
    requests.exceptions.ConnectTimeout,
    requests.exceptions.ReadTimeout,
    requests.exceptions.ConnectionError,
)


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _finite(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _nonnegative(value: Any) -> float | None:
    out = _finite(value)
    return out if out is not None and out >= 0 else None


def _captured_at(value: Any) -> datetime | None:
    text = _safe(value).replace("Z", "+00:00")
    if not text:
        return None
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return None
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        return None
    return stamp.astimezone(timezone.utc)


def _api_base_url() -> str:
    return _safe(os.environ.get("KYRE_SPORTS_API_BASE_URL"), DEFAULT_API_BASE_URL).rstrip("/")


def _fail(reason: str, *, event_id: str = "", http: int | None = None) -> dict[str, Any]:
    return {
        "ready": False,
        "data_available": False,
        "reason": _safe(reason, "Kyre Sports API receiving context unavailable"),
        "official_event_id": _safe(event_id),
        "http": http,
        "teams": [],
        "model_enabled": False,
        "projection_enabled": False,
        "market_enabled": False,
        "sportsbook_influence": 0.0,
        "targets_inferred": False,
        "stake_sizing_enabled": False,
        "wager_actions": False,
    }


def _validate_player(raw: Any, *, event_id: str, team_id: str) -> tuple[dict[str, Any] | None, str]:
    if not isinstance(raw, dict):
        return None, "receiver row is not an object"
    athlete_id = _safe(raw.get("official_athlete_id"))
    player_team_id = _safe(raw.get("official_team_id"))
    position = _safe(raw.get("position")).upper()
    if not athlete_id.isdigit() or player_team_id != team_id:
        return None, "exact athlete/team identity failed"
    if position not in ELIGIBLE_RECEIVER_POSITIONS:
        return None, "receiver position is outside the certified eligibility set"

    receptions = _nonnegative(raw.get("receptions"))
    yards = _finite(raw.get("receiving_yards"))
    sample_games = _nonnegative(raw.get("sample_games"))
    touchdowns = _nonnegative(raw.get("receiving_touchdowns"))
    if receptions is None or yards is None or sample_games is None or touchdowns is None:
        return None, "core receiving workload is invalid"

    normalized = dict(raw)
    normalized.update(
        {
            "official_event_id": event_id,
            "official_athlete_id": athlete_id,
            "official_team_id": team_id,
            "player_name": _safe(raw.get("player_name"), "Unknown receiver"),
            "position": position,
            "sample_games": int(sample_games),
            "receptions": int(receptions),
            "receiving_yards": yards,
            "receiving_touchdowns": int(touchdowns),
        }
    )

    for key in ("yards_per_reception", "receptions_per_game", "receiving_yards_per_game"):
        value = raw.get(key)
        if value is None:
            normalized[key] = None
            continue
        number = _finite(value)
        if number is None or (key == "receptions_per_game" and number < 0):
            return None, f"invalid player metric: {key}"
        normalized[key] = number

    targets_available = raw.get("targets_data_available") is True
    normalized["targets_data_available"] = targets_available
    target_sample_games = raw.get("target_sample_games")
    targets = raw.get("targets")
    targets_per_game = raw.get("targets_per_game")
    if targets_available:
        target_games = _nonnegative(target_sample_games)
        targets_num = _nonnegative(targets)
        targets_pg = _nonnegative(targets_per_game)
        if (
            target_games is None
            or int(target_games) <= 0
            or targets_num is None
            or targets_pg is None
        ):
            return None, "explicit target contract is incomplete"
        normalized["target_sample_games"] = int(target_games)
        normalized["targets"] = int(targets_num)
        normalized["targets_per_game"] = targets_pg
    else:
        if targets is not None or targets_per_game is not None:
            return None, "targets were present without explicit ESPN target availability"
        normalized["target_sample_games"] = int(_nonnegative(target_sample_games) or 0)
        normalized["targets"] = None
        normalized["targets_per_game"] = None

    return normalized, ""


def _validate_pass_defense(raw: Any, *, opponent_id: str) -> tuple[dict[str, Any] | None, str]:
    if not isinstance(raw, dict):
        return None, "opponent pass-defense context is missing"
    if _safe(raw.get("official_team_id")) != opponent_id:
        return None, "opponent pass-defense identity mismatch"

    out = dict(raw)
    out["official_team_id"] = opponent_id
    out["data_available"] = raw.get("data_available") is True
    for key in (
        "receptions_allowed_per_game",
        "receiving_yards_allowed_per_game",
        "yards_per_reception_allowed",
        "receiving_touchdowns_allowed_per_game",
    ):
        value = raw.get(key)
        if value is None:
            out[key] = None
            continue
        number = _nonnegative(value)
        if number is None:
            return None, f"invalid pass-defense metric: {key}"
        out[key] = number

    targets_available = raw.get("targets_data_available") is True
    out["targets_data_available"] = targets_available
    target_sample_games = _nonnegative(raw.get("target_sample_games"))
    out["target_sample_games"] = int(target_sample_games or 0)
    target_value = raw.get("targets_allowed_per_game")
    if targets_available:
        target_number = _nonnegative(target_value)
        if target_number is None or out["target_sample_games"] <= 0:
            return None, "pass-defense explicit target context is incomplete"
        out["targets_allowed_per_game"] = target_number
    else:
        if target_value is not None:
            return None, "pass-defense targets were inferred"
        out["targets_allowed_per_game"] = None
    return out, ""


def validate_context_payload(
    payload: Any,
    official_event_id: str,
    *,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """Validate the exact production ``nfl_receiving_yards_context_v1`` contract."""
    event_id = _safe(official_event_id)
    if not event_id.isdigit():
        return _fail("official ESPN event ID is required", event_id=event_id)
    if not isinstance(payload, dict):
        return _fail("Kyre Sports API response is not an object", event_id=event_id)
    if _safe(payload.get("schema_version")) != SCHEMA_VERSION:
        return _fail("Kyre Sports API receiving context schema mismatch", event_id=event_id)
    if _safe(payload.get("official_event_id")) != event_id:
        return _fail("Kyre Sports API official event identity mismatch", event_id=event_id)

    identity = payload.get("identity") or {}
    semantics = payload.get("semantics") or {}
    if not isinstance(identity, dict) or not isinstance(semantics, dict):
        return _fail("Kyre Sports API safety contract missing", event_id=event_id)
    if (
        identity.get("official_event_id_required") is not True
        or identity.get("official_athlete_id_required") is not True
        or identity.get("official_team_id_required") is not True
        or identity.get("player_name_display_only") is not True
        or identity.get("player_name_matching") is not False
        or identity.get("fuzzy_matching") is not False
        or identity.get("synthetic_event_ids") is not False
        or identity.get("synthetic_player_ids") is not False
        or semantics.get("model_enabled") is not False
        or semantics.get("projection_enabled") is not False
        or semantics.get("market_enabled") is not False
        or semantics.get("sportsbook_influence") != 0.0
        or semantics.get("targets_inferred") is not False
        or semantics.get("stake_sizing_enabled") is not False
        or semantics.get("wager_actions") is not False
    ):
        return _fail("Kyre Sports API permanent safety contract failed closed", event_id=event_id)

    stamp = _captured_at(payload.get("captured_at_utc"))
    if stamp is None:
        return _fail("Kyre Sports API capture timestamp missing or invalid", event_id=event_id)
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    age_seconds = (now - stamp).total_seconds()
    if age_seconds < -MAX_FUTURE_SKEW_SECONDS:
        return _fail("Kyre Sports API capture timestamp is in the future", event_id=event_id)

    teams_raw = payload.get("teams")
    if not isinstance(teams_raw, list) or len(teams_raw) != 2:
        return _fail("Kyre Sports API must return exactly two verified teams", event_id=event_id)

    teams: list[dict[str, Any]] = []
    team_ids: set[str] = set()
    athlete_ids: set[str] = set()
    for raw_team in teams_raw:
        if not isinstance(raw_team, dict):
            return _fail("Kyre Sports API team row is invalid", event_id=event_id)
        team_id = _safe(raw_team.get("official_team_id"))
        opponent_id = _safe(raw_team.get("opponent_official_team_id"))
        if (
            not team_id.isdigit()
            or not opponent_id.isdigit()
            or team_id == opponent_id
            or team_id in team_ids
        ):
            return _fail("Kyre Sports API exact team identity failed", event_id=event_id)
        team_ids.add(team_id)

        players_raw = raw_team.get("players") or []
        if not isinstance(players_raw, list):
            return _fail("Kyre Sports API player list is invalid", event_id=event_id)
        players: list[dict[str, Any]] = []
        for raw_player in players_raw:
            player, reason = _validate_player(raw_player, event_id=event_id, team_id=team_id)
            if player is None:
                return _fail(f"Kyre Sports API player contract failed: {reason}", event_id=event_id)
            athlete_id = player["official_athlete_id"]
            if athlete_id in athlete_ids:
                return _fail("Kyre Sports API returned duplicate athlete identity", event_id=event_id)
            athlete_ids.add(athlete_id)
            players.append(player)

        defense, reason = _validate_pass_defense(
            raw_team.get("opponent_pass_defense"),
            opponent_id=opponent_id,
        )
        if defense is None:
            return _fail(f"Kyre Sports API pass-defense contract failed: {reason}", event_id=event_id)

        team = dict(raw_team)
        team.update(
            {
                "official_team_id": team_id,
                "opponent_official_team_id": opponent_id,
                "team_name": _safe(raw_team.get("team_name"), _safe(raw_team.get("team_abbreviation"), "NFL Team")),
                "team_abbreviation": _safe(raw_team.get("team_abbreviation"), "NFL").upper(),
                "players": players,
                "opponent_pass_defense": defense,
            }
        )
        teams.append(team)

    if {team["opponent_official_team_id"] for team in teams} != team_ids:
        return _fail("Kyre Sports API reciprocal opponent identity failed", event_id=event_id)

    provider_ready = payload.get("ready") is True
    data_available = provider_ready and bool(athlete_ids)
    return {
        "ready": True,
        "data_available": data_available,
        "reason": "",
        "schema_version": SCHEMA_VERSION,
        "official_event_id": event_id,
        "captured_at_utc": stamp.isoformat(),
        "age_seconds": max(0.0, age_seconds),
        "season": payload.get("season"),
        "teams": teams,
        "source_note": _safe(payload.get("source_note")),
        "model_enabled": False,
        "projection_enabled": False,
        "market_enabled": False,
        "sportsbook_influence": 0.0,
        "targets_inferred": False,
        "stake_sizing_enabled": False,
        "wager_actions": False,
    }


def fetch_event_context(
    official_event_id: str,
    *,
    now_utc: datetime | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Fetch one exact ESPN event from the deployed Receiving Yards context API."""
    event_id = _safe(official_event_id)
    if not event_id.isdigit():
        return _fail("official ESPN event ID is required", event_id=event_id)

    root = _safe(base_url, _api_base_url()).rstrip("/")
    url = f"{root}/api/v1/nfl/receiving-yards"
    response = None
    request_error: Exception | None = None
    attempts = 0
    for attempt in range(1, MAX_REQUEST_ATTEMPTS + 1):
        attempts = attempt
        try:
            response = requests.get(
                url,
                params={"event_id": event_id},
                timeout=(REQUEST_CONNECT_TIMEOUT_SECONDS, REQUEST_READ_TIMEOUT_SECONDS),
                headers={"Accept": "application/json", "User-Agent": "KyreSportsAI-Streamlit/1.0"},
            )
        except _TRANSIENT_REQUEST_EXCEPTIONS as exc:
            request_error = exc
            if attempt < MAX_REQUEST_ATTEMPTS:
                time.sleep(RETRY_BACKOFF_SECONDS)
                continue
        except Exception as exc:
            request_error = exc
        break

    if response is None:
        out = _fail(
            f"Kyre Sports API request failed: {type(request_error).__name__ if request_error else 'UnknownError'}",
            event_id=event_id,
        )
        out["request_attempts"] = attempts
        return out

    status = int(getattr(response, "status_code", 0) or 0)
    if status != 200:
        out = _fail(f"Kyre Sports API returned HTTP {status}", event_id=event_id, http=status)
        out["request_attempts"] = attempts
        return out
    try:
        payload = response.json()
    except Exception:
        out = _fail("Kyre Sports API returned invalid JSON", event_id=event_id, http=status)
        out["request_attempts"] = attempts
        return out

    out = validate_context_payload(payload, event_id, now_utc=now_utc)
    out["http"] = status
    out["request_attempts"] = attempts
    return out


__all__ = [
    "DEFAULT_API_BASE_URL",
    "ELIGIBLE_RECEIVER_POSITIONS",
    "MAX_REQUEST_ATTEMPTS",
    "MODEL_VERSION",
    "SCHEMA_VERSION",
    "fetch_event_context",
    "validate_context_payload",
]
