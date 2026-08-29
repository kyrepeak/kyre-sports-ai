"""Step 7F — safe Streamlit client for the hosted Kyre Sports WNBA API.

This module is intentionally GET-only.  It never accepts arbitrary hosts, never
sends API keys, never mutates Render/Supabase, and never calls sportsbook vendors
directly.  Streamlit can use it as the single read transport to the hosted
FastAPI service.
"""
from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Mapping
from urllib.parse import urlsplit

import requests

BASE_URL = "https://kyre-sports-api.onrender.com"
EXPECTED_API_NAME = "Kyre Sports API"
SUPPORTED_SEASON = 2026
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_ATTEMPTS = 3


class KyreWNBAAPIError(RuntimeError):
    """Raised when the hosted API cannot be consumed safely."""


def _clean_base_url(value: str) -> str:
    text = str(value or "").strip().rstrip("/")
    parsed = urlsplit(text)
    if parsed.scheme != "https" or parsed.netloc != "kyre-sports-api.onrender.com":
        raise KyreWNBAAPIError("WNBA API base URL is not the certified Render origin.")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise KyreWNBAAPIError("WNBA API base URL contains an unsafe component.")
    return text


def _safe_path(path: str) -> str:
    value = str(path or "").strip()
    if not value.startswith("/") or value.startswith("//"):
        raise KyreWNBAAPIError("API path must be a local absolute path.")
    if "://" in value or "\\" in value or "#" in value:
        raise KyreWNBAAPIError("API path contains an unsafe component.")
    allowed = value in {"/", "/health", "/openapi.json"} or value.startswith("/api/v1/wnba/")
    if not allowed:
        raise KyreWNBAAPIError("API path is outside the certified WNBA read surface.")
    return value


def _json_object(response: requests.Response, path: str) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError as exc:
        raise KyreWNBAAPIError(f"{path} returned non-JSON HTTP {response.status_code}.") from exc
    if not isinstance(body, dict):
        raise KyreWNBAAPIError(f"{path} returned a non-object JSON payload.")
    return body


@dataclass(frozen=True)
class KyreWNBAAPIClient:
    base_url: str = BASE_URL
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    attempts: int = DEFAULT_ATTEMPTS

    def __post_init__(self) -> None:
        object.__setattr__(self, "base_url", _clean_base_url(self.base_url))
        if float(self.timeout_seconds) <= 0 or float(self.timeout_seconds) > 90:
            raise KyreWNBAAPIError("timeout_seconds must be between 0 and 90.")
        if int(self.attempts) < 1 or int(self.attempts) > 5:
            raise KyreWNBAAPIError("attempts must be between 1 and 5.")

    def get_json(self, path: str, *, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        safe_path = _safe_path(path)
        last_error: Exception | None = None
        for attempt in range(1, int(self.attempts) + 1):
            try:
                response = requests.get(
                    self.base_url + safe_path,
                    params=dict(params or {}),
                    headers={
                        "accept": "application/json",
                        "user-agent": "kyre-sports-ai-streamlit-step7f/1",
                    },
                    timeout=float(self.timeout_seconds),
                    allow_redirects=True,
                )
                if response.status_code != 200:
                    raise KyreWNBAAPIError(f"{safe_path} returned HTTP {response.status_code}.")
                return _json_object(response, safe_path)
            except (requests.RequestException, KyreWNBAAPIError) as exc:
                last_error = exc
                if attempt < int(self.attempts):
                    time.sleep(min(1.5 * attempt, 4.0))
        raise KyreWNBAAPIError(f"Hosted WNBA API read failed for {safe_path}: {last_error}")

    def health(self) -> dict[str, Any]:
        body = self.get_json("/health")
        if body.get("status") != "ok":
            raise KyreWNBAAPIError("Hosted API health is not ok.")
        return body

    def root(self) -> dict[str, Any]:
        body = self.get_json("/")
        if body.get("name") != EXPECTED_API_NAME or body.get("status") != "online":
            raise KyreWNBAAPIError("Hosted API identity is invalid.")
        return body

    def teams(self, season: int = SUPPORTED_SEASON) -> dict[str, Any]:
        return self.get_json("/api/v1/wnba/teams", params={"season": int(season)})

    def league(self, season: int = SUPPORTED_SEASON) -> dict[str, Any]:
        return self.get_json("/api/v1/wnba/league", params={"season": int(season)})

    def games_today(self, season: int = SUPPORTED_SEASON) -> dict[str, Any]:
        return self.get_json("/api/v1/wnba/games/today", params={"season": int(season)})

    def games_for_date(self, date: str, season: int = SUPPORTED_SEASON) -> dict[str, Any]:
        return self.get_json("/api/v1/wnba/games", params={"date": str(date), "season": int(season)})

    def verify_slate(self, date: str, season: int = SUPPORTED_SEASON) -> dict[str, Any]:
        return self.get_json("/api/v1/wnba/slate/verify", params={"date": str(date), "season": int(season)})

    def players(self, season: int = SUPPORTED_SEASON, *, current_roster_only: bool = True) -> dict[str, Any]:
        return self.get_json(
            "/api/v1/wnba/players",
            params={"season": int(season), "current_roster_only": str(bool(current_roster_only)).lower()},
        )

    def team_roster(self, team_key: str, season: int = SUPPORTED_SEASON) -> dict[str, Any]:
        key = str(team_key or "").strip()
        if not key or "/" in key or "?" in key:
            raise KyreWNBAAPIError("Invalid WNBA team key.")
        return self.get_json(f"/api/v1/wnba/teams/{key}/roster", params={"season": int(season)})

    def player_game_log(self, player_id: int, season: int = SUPPORTED_SEASON) -> dict[str, Any]:
        pid = int(player_id)
        if pid <= 0:
            raise KyreWNBAAPIError("player_id must be positive.")
        return self.get_json(f"/api/v1/wnba/players/{pid}/game-log", params={"season": int(season)})

    def consumer_latest(self) -> dict[str, Any]:
        """Read the certified Step-18A latest-board snapshot; never compute on request."""
        body = self.get_json("/api/v1/wnba/consumer/latest")
        if body.get("data_type") != "wnba_step18a_streamlit_consumer_latest":
            raise KyreWNBAAPIError("WNBA consumer endpoint data_type is invalid.")
        if body.get("schema_version") != "wnba_step_18a_streamlit_consumer_v1":
            raise KyreWNBAAPIError("WNBA consumer endpoint schema is invalid.")
        if not isinstance(body.get("enabled"), bool) or not isinstance(body.get("available"), bool):
            raise KyreWNBAAPIError("WNBA consumer endpoint availability flags are invalid.")
        if not isinstance(body.get("board"), dict) or not isinstance(body.get("snapshot"), dict):
            raise KyreWNBAAPIError("WNBA consumer endpoint board/snapshot shape is invalid.")
        return body

    def readiness(self) -> dict[str, Any]:
        """Read only the hosted API/Supabase pre-activation safety surface."""
        health = self.health()
        step6r = self.get_json("/api/v1/wnba/runtime/step6r-supabase-storage")
        step6t = self.get_json("/api/v1/wnba/runtime/step6t-canary-evidence/status")
        step6u = self.get_json("/api/v1/wnba/runtime/step6u-activation-bridge/status")
        return {
            "health": health.get("status"),
            "selected_backend": step6r.get("selected_backend"),
            "supabase_ready": step6r.get("configuration_ready") is True,
            "evidence_ready": step6t.get("configuration_ready") is True,
            "scheduler_authorized": step6u.get("scheduler_authorized") is True,
            "production_runtime_enabled": bool((step6u.get("safety") or {}).get("production_runtime_enabled")),
        }


__all__ = [
    "BASE_URL",
    "EXPECTED_API_NAME",
    "SUPPORTED_SEASON",
    "KyreWNBAAPIError",
    "KyreWNBAAPIClient",
]
