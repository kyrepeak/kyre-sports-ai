"""MLB Spread / Run Line V15.6.3 — Step-1 H2H official-date repair.

This wrapper preserves the exact V15.6 Step-1 card from commit
8f44cf7da6e678be1371452f7db2de985c27c656, keeps the direct MLB-logo transport,
and keeps the V15.6.2 season-by-season newest-first H2H intake.

Root cause fixed here
---------------------
MLB StatsAPI ``gameDate`` is a UTC timestamp. Taking its first 10 characters can
move a night game to the following calendar date (for example a May 31 game in
San Diego can be represented as June 1 UTC). The H2H card must display MLB's
official schedule date, not the UTC calendar date.

Repair
------
Use the schedule block ``date`` first, then ``officialDate``. ``gameDate`` is
retained only as a precise sort key so same-day doubleheaders remain ordered.

The V15.2 H2H weighting formula, shrinkage, +/-5 pp total cap, core simulation,
projected score, ranking logic, fair odds and all downstream presentation rules
remain unchanged. A saved scan is invalidated once because corrected chronological
ordering can slightly change recency weights.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import subprocess
import sys
import types
import urllib.request

import requests
import streamlit as st

from engine import ET, MLB_API, sf
import spread_history as legacy_history


_BASE_COMMIT = "8f44cf7da6e678be1371452f7db2de985c27c656"
_BASE_PATH = "mlb_spread_hub_v156.py"
_BASE_MODULE_NAME = "_kyre_mlb_spread_v156_frozen_step1"
MODEL_VERSION = "V15.6.3 • TOP-5 CARD STEP 1 • OFFICIAL H2H DATES"
_HISTORY_SOURCE_TOKEN = "mlb_spread_h2h_official_dates_v1563"


def _load_frozen_v156():
    cached = sys.modules.get(_BASE_MODULE_NAME)
    if cached is not None:
        return cached

    try:
        source = subprocess.check_output(
            ["git", "show", f"{_BASE_COMMIT}:{_BASE_PATH}"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        url = (
            "https://raw.githubusercontent.com/kyrepeak/kyre-sports-ai/"
            f"{_BASE_COMMIT}/{_BASE_PATH}"
        )
        with urllib.request.urlopen(url, timeout=15) as response:
            source = response.read().decode("utf-8")

    module = types.ModuleType(_BASE_MODULE_NAME)
    module.__file__ = f"<{_BASE_MODULE_NAME}>"
    module.__package__ = ""
    sys.modules[_BASE_MODULE_NAME] = module
    exec(compile(source, module.__file__, "exec"), module.__dict__)
    return module


base = _load_frozen_v156()

# Preserve public helpers that downstream debugging/checkpoint code may inspect.
prior = base.prior
v154 = base.v154
v153 = base.v153
v152 = base.v152


def _mlb_logo_html(team_id) -> str:
    """Return browser-renderable MLB logo HTML from the canonical numeric team ID."""
    try:
        tid = int(float(team_id))
    except Exception:
        return ""
    if tid <= 0:
        return ""

    url = f"https://www.mlbstatic.com/team-logos/{tid}.svg"
    return (
        f'<img src="{url}" alt="MLB team {tid} logo" '
        'loading="lazy" decoding="async" referrerpolicy="no-referrer">'
    )


def _completed_state(game: dict) -> bool:
    status = str(((game.get("status") or {}).get("detailedState") or "")).lower()
    return "final" in status or "game over" in status


def _official_game_date(block: dict, game: dict):
    """Return MLB's official local schedule date, never the UTC day by accident."""
    candidates = (
        block.get("date"),
        game.get("officialDate"),
    )
    for value in candidates:
        text = str(value or "")[:10]
        if not text:
            continue
        try:
            return datetime.fromisoformat(text).date()
        except Exception:
            continue

    # Emergency fallback only. gameDate is UTC, so converting its YYYY-MM-DD part
    # is less desirable than schedule/officialDate but better than dropping a game.
    text = str(game.get("gameDate") or "")[:10]
    if text:
        try:
            return datetime.fromisoformat(text).date()
        except Exception:
            pass
    return None


def _game_sort_key(game: dict) -> tuple:
    """Newest official date first, with UTC start time resolving same-day games."""
    return (str(game.get("date") or ""), str(game.get("game_datetime_utc") or ""), int(game.get("game_pk") or 0))


@st.cache_data(ttl=1800, show_spinner=False)
def _fresh_pair_games(team_a: int, team_b: int, years_back: int = 4) -> list[dict]:
    """Fetch recent completed meetings for one normalized MLB team pair."""
    a, b = sorted((int(team_a), int(team_b)))
    today = datetime.now(ET).date()
    latest_allowed = today - timedelta(days=1)
    earliest_year = today.year - int(years_back)

    found: dict[int, dict] = {}

    for year in range(today.year, earliest_year - 1, -1):
        start = date(year, 1, 1)
        end = min(date(year, 12, 31), latest_allowed)
        if start > end:
            continue

        response = requests.get(
            f"{MLB_API}/schedule",
            params={
                "sportId": 1,
                "teamId": a,
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
            },
            timeout=20,
        )
        response.raise_for_status()

        for block in response.json().get("dates", []):
            for game in block.get("games", []):
                if not _completed_state(game):
                    continue

                teams = game.get("teams") or {}
                away = teams.get("away") or {}
                home = teams.get("home") or {}
                away_id = int(((away.get("team") or {}).get("id") or 0))
                home_id = int(((home.get("team") or {}).get("id") or 0))
                if {away_id, home_id} != {a, b}:
                    continue

                away_score = sf(away.get("score"))
                home_score = sf(home.get("score"))
                if away_score is None or home_score is None:
                    continue

                game_date = _official_game_date(block, game)
                if game_date is None or game_date > latest_allowed:
                    continue

                game_pk = int(game.get("gamePk") or 0)
                if not game_pk:
                    continue

                found[game_pk] = {
                    "game_pk": game_pk,
                    "date": game_date.isoformat(),
                    "year": game_date.year,
                    "game_datetime_utc": str(game.get("gameDate") or ""),
                    "away_team_id": away_id,
                    "home_team_id": home_id,
                    "away_runs": float(away_score),
                    "home_runs": float(home_score),
                    "venue": (game.get("venue") or {}).get("name", "Unknown"),
                }

        if len(found) >= 10:
            break

    games = sorted(found.values(), key=_game_sort_key, reverse=True)
    return games[:10]


def _fresh_h2h_last10(team_id, opponent_id, max_games=10, years_back=4):
    """Completed H2H games before today, always from team_id's perspective."""
    team_id = int(team_id)
    opponent_id = int(opponent_id)
    raw_games = _fresh_pair_games(team_id, opponent_id, int(years_back))

    out = []
    for game in raw_games:
        away_id = int(game["away_team_id"])
        home_id = int(game["home_team_id"])

        if away_id == team_id:
            team_runs = float(game["away_runs"])
            opp_runs = float(game["home_runs"])
            location = "away"
        elif home_id == team_id:
            team_runs = float(game["home_runs"])
            opp_runs = float(game["away_runs"])
            location = "home"
        else:
            continue

        out.append(
            {
                "game_pk": game["game_pk"],
                "date": game["date"],
                "year": game["year"],
                "game_datetime_utc": game.get("game_datetime_utc", ""),
                "team_runs": team_runs,
                "opponent_runs": opp_runs,
                "margin": team_runs - opp_runs,
                "location": location,
                "home_team_id": home_id,
                "venue": game.get("venue", "Unknown"),
            }
        )

    out.sort(key=_game_sort_key, reverse=True)
    return out[: int(max_games)]


def _invalidate_legacy_saved_scan_once():
    """Prevent pre-official-date H2H payloads from surviving this repair."""
    if st.session_state.get("_mlb_spread_history_source") == _HISTORY_SOURCE_TOKEN:
        return False

    for key in (
        "v152_spread_slate",
        "v152_spread_scan_time",
        "v152_spread_errors",
        "v15_spread_result",
    ):
        st.session_state.pop(key, None)

    st.session_state["_mlb_spread_history_source"] = _HISTORY_SOURCE_TOKEN
    return True


def render_spread_hub(games_df, section_header, status_info, team_logo, h):
    """Render frozen V15.6 with direct logos + official local H2H dates."""
    refreshed = _invalidate_legacy_saved_scan_once()

    def robust_team_logo(team_id):
        direct = _mlb_logo_html(team_id)
        if direct:
            return direct
        try:
            return team_logo(team_id) or ""
        except Exception:
            return ""

    # V15.2 imported history_adjustment from spread_history, but that function
    # resolves h2h_last10 from spread_history's module globals at call time.
    # Replacing only this data-source function preserves the verified formula.
    original_h2h = legacy_history.h2h_last10
    legacy_history.h2h_last10 = _fresh_h2h_last10
    try:
        st.caption(
            "🛠️ MLB Spread V15.6.3 • H2H official dates repaired: MLB schedule date "
            "is used for display/recency; UTC gameDate is only a same-day sort key • model formula unchanged."
        )
        if refreshed:
            st.info(
                "H2H calendar dates were repaired, so the saved spread scan was cleared. "
                "Run the V15.2 spread scan once to rebuild the H2H chronology and probability."
            )

        return base.render_spread_hub(
            games_df,
            section_header,
            status_info,
            robust_team_logo,
            h,
        )
    finally:
        legacy_history.h2h_last10 = original_h2h


__all__ = [
    "MODEL_VERSION",
    "render_spread_hub",
    "prior",
    "v154",
    "v153",
    "v152",
]
