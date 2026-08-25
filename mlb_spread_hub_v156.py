"""MLB Spread / Run Line V15.6.4 — Step-1 H2H regular-season repair.

This wrapper preserves the exact V15.6 Step-1 card from commit
8f44cf7da6e678be1371452f7db2de985c27c656, keeps the direct MLB-logo transport,
keeps the season-by-season newest-first H2H intake, and removes Spring Training
(and any other non-regular-season game types) from the history sample.

Root cause
----------
The repaired season-by-season MLB StatsAPI loader correctly found newer games,
but it accepted every completed game returned for the team pair. MLB schedule
responses can include Spring Training games (gameType ``S``). Those exhibition
games were therefore appearing in the Last-5 ledger and were also contaminating
current-season H2H counts, venue history, recency weighting and the existing V15.2
history adjustment.

Repair
------
Only completed MLB regular-season games (gameType ``R``) are eligible for the
Spread Scanner H2H sample. Official schedule-date handling remains in place so
UTC rollover cannot shift a local game to the following calendar date.

Protected behavior
------------------
The V15.2 H2H weighting formula, shrinkage, +/-5 pp total cap, core simulation,
projected score, ranking logic, fair odds and all downstream presentation rules
remain unchanged. Because the source history is corrected, a fresh scan can
legitimately produce a different history adjustment/final probability.
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
MODEL_VERSION = "V15.6.4 • TOP-5 CARD STEP 1 • REGULAR-SEASON H2H"
_HISTORY_SOURCE_TOKEN = "mlb_spread_h2h_regular_season_v1564"


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


def _regular_season(game: dict) -> bool:
    """True only for MLB regular-season games; excludes Spring Training/exhibitions."""
    return str(game.get("gameType") or "").upper() == "R"


@st.cache_data(ttl=1800, show_spinner=False)
def _fresh_pair_games(team_a: int, team_b: int, years_back: int = 4) -> list[dict]:
    """Fetch recent completed regular-season meetings for one MLB team pair.

    Requests are segmented by season because a single multi-season StatsAPI range
    can yield an incomplete/stale schedule slice. The official schedule date is
    used for display/history bucketing; UTC ``gameDate`` is retained only as a
    same-day ordering tiebreaker.
    """
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
            schedule_date_text = str(block.get("date") or "")[:10]
            for game in block.get("games", []):
                if not _completed_state(game):
                    continue
                if not _regular_season(game):
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

                # ``block['date']`` is MLB's official schedule date and avoids a
                # local night game rolling into the next UTC date via gameDate.
                date_text = schedule_date_text or str(game.get("gameDate") or "")[:10]
                try:
                    game_date = datetime.fromisoformat(date_text).date()
                except Exception:
                    continue
                if game_date > latest_allowed:
                    continue

                game_pk = int(game.get("gamePk") or 0)
                if not game_pk:
                    continue

                found[game_pk] = {
                    "game_pk": game_pk,
                    "date": game_date.isoformat(),
                    "year": game_date.year,
                    "game_type": str(game.get("gameType") or "").upper(),
                    "game_datetime": str(game.get("gameDate") or ""),
                    "away_team_id": away_id,
                    "home_team_id": home_id,
                    "away_runs": float(away_score),
                    "home_runs": float(home_score),
                    "venue": (game.get("venue") or {}).get("name", "Unknown"),
                }

        if len(found) >= 10:
            break

    games = sorted(
        found.values(),
        key=lambda x: (x["date"], x.get("game_datetime") or ""),
        reverse=True,
    )
    return games[:10]


def _fresh_h2h_last10(team_id, opponent_id, max_games=10, years_back=4):
    """Completed regular-season H2H games, always from team_id's perspective."""
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
                "team_runs": team_runs,
                "opponent_runs": opp_runs,
                "margin": team_runs - opp_runs,
                "location": location,
                "home_team_id": home_id,
                "venue": game.get("venue", "Unknown"),
            }
        )

    out.sort(key=lambda x: x["date"], reverse=True)
    return out[: int(max_games)]


def _invalidate_legacy_saved_scan_once():
    """Prevent pre-filter H2H payloads from surviving the regular-season repair."""
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
    """Render frozen V15.6 with direct logos + regular-season-only H2H intake."""
    refreshed = _invalidate_legacy_saved_scan_once()

    def robust_team_logo(team_id):
        direct = _mlb_logo_html(team_id)
        if direct:
            return direct
        try:
            return team_logo(team_id) or ""
        except Exception:
            return ""

    # V15.2 imported ``history_adjustment`` from spread_history, but that function
    # resolves ``h2h_last10`` from spread_history's module globals at call time.
    # Replacing only this data-source function preserves all verified weighting,
    # shrinkage and cap formulas.
    original_h2h = legacy_history.h2h_last10
    legacy_history.h2h_last10 = _fresh_h2h_last10
    try:
        st.caption(
            "🛠️ MLB Spread V15.6.4 • H2H source repaired: official MLB regular-season "
            "games only, newest-first, with local schedule dates • model formula unchanged."
        )
        if refreshed:
            st.info(
                "Spring Training/non-regular-season games were removed from H2H history, "
                "so the saved pre-repair spread scan was cleared. Run the V15.2 spread "
                "scan once to rebuild probabilities from regular-season H2H only."
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
