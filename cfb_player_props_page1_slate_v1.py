"""CFB Player Props Page 1 V1 — next-slate schedule normalization."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Mapping
from zoneinfo import ZoneInfo

import cfb_schedule_v4 as schedule
import cfb_universal_next_slate_navigation_v1 as next_slate

MODEL_VERSION = "CFB PLAYER PROPS PAGE 1 • SLATE V1"
PHOENIX = ZoneInfo("America/Phoenix")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _aware(value: Any) -> datetime:
    text = _text(value)
    if not text:
        raise ValueError("kickoff timestamp is required")
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("kickoff timestamp must be timezone-aware")
    return parsed


def _team_id(game: Mapping[str, Any], side: str) -> str:
    for key in (f"{side}_espn_team_id", f"{side}_team_id"):
        value = _text(game.get(key))
        if value:
            return value
    return ""


def normalize_page1_game(game: Mapping[str, Any], slate_date: date) -> dict[str, Any]:
    if game.get("identity_verified") is not True:
        raise ValueError("CFB Page 1 requires verified official game identity")
    game_id = _text(game.get("game_id"))
    if not game_id:
        raise ValueError("official game id is required")
    kickoff_text = _text(game.get("kickoff_iso"))
    kickoff = _aware(kickoff_text)
    phoenix = kickoff.astimezone(PHOENIX)
    return {
        "official_game_id": game_id,
        "identity_key": _text(game.get("identity_key")) or f"ncaa:{game_id}",
        "identity_verified": True,
        "game_date": slate_date.isoformat(),
        "kickoff_iso": kickoff_text,
        "kickoff_phoenix": phoenix.strftime("%-I:%M %p %Z"),
        "status": _text(game.get("status")) or "Status unavailable",
        "away_team_id": _team_id(game, "away"),
        "away_team": _text(game.get("away_team")) or "Away",
        "away_team_slug": _text(game.get("away_team_slug")),
        "away_rank": game.get("away_rank"),
        "away_conference": _text(game.get("away_conference")),
        "home_team_id": _team_id(game, "home"),
        "home_team": _text(game.get("home_team")) or "Home",
        "home_team_slug": _text(game.get("home_team_slug")),
        "home_rank": game.get("home_rank"),
        "home_conference": _text(game.get("home_conference")),
        "venue": _text(game.get("venue")),
        "broadcast": _text(game.get("broadcast")),
    }


def load_next_player_prop_slate(
    *,
    now_provider: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict[str, Any]:
    now = now_provider()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now_utc = now.astimezone(timezone.utc)

    for offset in range(next_slate.MAX_SCAN_DAYS + 1):
        slate_date = now_utc.date() + timedelta(days=offset)
        try:
            raw_games = list(schedule.games_for_date(slate_date) or [])
        except Exception:
            continue

        normalized: list[dict[str, Any]] = []
        for raw in raw_games:
            if not isinstance(raw, Mapping):
                continue
            if not next_slate.game_is_future_pregame(raw, now_utc=now_utc):
                continue
            try:
                normalized.append(normalize_page1_game(raw, slate_date))
            except (TypeError, ValueError):
                continue

        if normalized:
            normalized.sort(key=lambda row: (row["kickoff_iso"], row["official_game_id"]))
            return {
                "state": "live",
                "slate_date": slate_date,
                "games": normalized,
                "source": schedule.MODEL_VERSION,
            }

    return {
        "state": "unavailable",
        "slate_date": None,
        "games": [],
        "source": schedule.MODEL_VERSION,
    }


__all__ = ["MODEL_VERSION", "load_next_player_prop_slate", "normalize_page1_game"]
