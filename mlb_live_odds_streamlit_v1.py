"""Streamlit presentation for the read-only MLB live game-odds API."""
from __future__ import annotations

from datetime import datetime
import os
from typing import Any, Callable, Mapping
from zoneinfo import ZoneInfo

import requests
import streamlit as st

DEFAULT_API_BASE_URL = "https://kyre-sports-api.onrender.com"
EASTERN = ZoneInfo("America/New_York")


class MLBLiveOddsUIError(RuntimeError):
    """Raised when the MLB live-odds API response is unusable."""


def api_base_url() -> str:
    value = (
        os.getenv("KYRE_SPORTS_API_BASE_URL")
        or os.getenv("SPORTS_API_BASE_URL")
        or DEFAULT_API_BASE_URL
    )
    return str(value).strip().rstrip("/")


def fetch_live_mlb_odds(
    *,
    base_url: str | None = None,
    max_events: int = 30,
    request_get: Callable[..., Any] = requests.get,
) -> dict[str, Any]:
    if max_events <= 0:
        raise ValueError("max_events must be positive")
    root = (base_url or api_base_url()).strip().rstrip("/")
    if not root:
        raise MLBLiveOddsUIError("MLB API base URL is empty")

    try:
        response = request_get(
            f"{root}/api/v1/mlb/odds",
            params={"max_events": max_events, "fully_priced_only": "true"},
            timeout=25,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise MLBLiveOddsUIError(f"MLB live-odds API request failed: {exc}") from exc

    if not isinstance(payload, dict):
        raise MLBLiveOddsUIError("MLB live-odds API did not return a JSON object")
    if payload.get("data_type") != "mlb_live_odds_api_response_v1":
        raise MLBLiveOddsUIError("MLB live-odds API returned an unexpected data_type")
    if payload.get("schema_version") != 1:
        raise MLBLiveOddsUIError("MLB live-odds API returned an unsupported schema version")
    if payload.get("source") != "FanDuel":
        raise MLBLiveOddsUIError("MLB live-odds API returned an unexpected source")
    games = payload.get("games")
    if not isinstance(games, list):
        raise MLBLiveOddsUIError("MLB live-odds API games payload is not a list")
    return dict(payload)


def format_american_odds(value: Any) -> str:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return "—"
    return f"+{number}" if number > 0 else str(number)


def format_line(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if number.is_integer():
        number_text = str(int(number))
    else:
        number_text = f"{number:g}"
    return f"+{number_text}" if number > 0 else number_text


def _team_name(game: Mapping[str, Any], side: str) -> str:
    row = game.get(f"{side}_team") or {}
    if isinstance(row, Mapping):
        return str(row.get("name") or side.title()).strip()
    return side.title()


def _start_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "Start time unavailable"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return text
        return parsed.astimezone(EASTERN).strftime("%a %b %-d • %-I:%M %p ET")
    except Exception:
        return text


def build_game_cards(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    games = payload.get("games") or []
    if not isinstance(games, list):
        return cards

    for game in games:
        if not isinstance(game, Mapping) or game.get("fully_priced") is not True:
            continue
        markets = game.get("markets") or {}
        if not isinstance(markets, Mapping):
            continue
        moneyline = markets.get("moneyline") or {}
        run_line = markets.get("run_line") or {}
        total = markets.get("total") or {}
        if not all(isinstance(row, Mapping) for row in (moneyline, run_line, total)):
            continue

        away = _team_name(game, "away")
        home = _team_name(game, "home")
        cards.append(
            {
                "official_game_id": game.get("official_game_id"),
                "matchup": f"{away} @ {home}",
                "away_team": away,
                "home_team": home,
                "start": _start_text(game.get("scheduled_start_utc")),
                "sportsbook": str(game.get("sportsbook") or "FanDuel"),
                "moneyline": {
                    "away": format_american_odds(moneyline.get("away_odds")),
                    "home": format_american_odds(moneyline.get("home_odds")),
                },
                "run_line": {
                    "away_line": format_line(run_line.get("away_line")),
                    "away_odds": format_american_odds(run_line.get("away_odds")),
                    "home_line": format_line(run_line.get("home_line")),
                    "home_odds": format_american_odds(run_line.get("home_odds")),
                },
                "total": {
                    "line": format_line(total.get("line")),
                    "over": format_american_odds(total.get("over_odds")),
                    "under": format_american_odds(total.get("under_odds")),
                },
            }
        )
    return cards


@st.cache_data(ttl=30, show_spinner=False)
def _cached_live_mlb_odds(base_url: str) -> dict[str, Any]:
    return fetch_live_mlb_odds(base_url=base_url)


def render_mlb_live_odds_page() -> None:
    st.markdown("## ⚾ MLB Live Odds")
    st.caption("Real pregame FanDuel moneyline, run line, and total markets matched to official MLB games.")

    left, right = st.columns([1, 1])
    with left:
        if st.button("← Back to Sports AI", key="mlb_live_odds_back", use_container_width=True):
            st.session_state["ks_mlb_live_odds_route"] = False
            st.rerun()
    with right:
        if st.button("↻ Refresh Odds", key="mlb_live_odds_refresh", use_container_width=True):
            _cached_live_mlb_odds.clear()
            st.rerun()

    base = api_base_url()
    try:
        with st.spinner("Loading live MLB odds…"):
            payload = _cached_live_mlb_odds(base)
    except MLBLiveOddsUIError as exc:
        st.error(str(exc))
        st.caption(f"API: {base}/api/v1/mlb/odds")
        return

    cards = build_game_cards(payload)
    game_count = len(cards)
    collected_at = str(payload.get("collected_at_utc") or "")
    status_col, source_col = st.columns([1, 1])
    status_col.metric("Fully priced games", game_count)
    source_col.metric("Sportsbook", "FanDuel")
    if collected_at:
        st.caption(f"Snapshot: {collected_at}")

    if not cards:
        st.info("No fully priced MLB games are available right now. Refresh when markets reopen.")
        return

    for card in cards:
        with st.container(border=True):
            st.markdown(f"### {card['matchup']}")
            st.caption(f"{card['start']} • {card['sportsbook']} • MLB game {card['official_game_id']}")

            ml_col, rl_col, total_col = st.columns(3, gap="small")
            with ml_col:
                st.markdown("**Moneyline**")
                st.write(f"{card['away_team']}: **{card['moneyline']['away']}**")
                st.write(f"{card['home_team']}: **{card['moneyline']['home']}**")
            with rl_col:
                st.markdown("**Run Line**")
                st.write(
                    f"{card['away_team']}: **{card['run_line']['away_line']} ({card['run_line']['away_odds']})**"
                )
                st.write(
                    f"{card['home_team']}: **{card['run_line']['home_line']} ({card['run_line']['home_odds']})**"
                )
            with total_col:
                st.markdown("**Total**")
                st.write(f"Over {card['total']['line']}: **{card['total']['over']}**")
                st.write(f"Under {card['total']['line']}: **{card['total']['under']}**")


__all__ = [
    "DEFAULT_API_BASE_URL",
    "MLBLiveOddsUIError",
    "api_base_url",
    "build_game_cards",
    "fetch_live_mlb_odds",
    "format_american_odds",
    "format_line",
    "render_mlb_live_odds_page",
]
