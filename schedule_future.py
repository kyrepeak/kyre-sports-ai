from datetime import date, datetime, timedelta

import pandas as pd
import requests
import streamlit as st

from engine import ET, MLB_API


MAX_FUTURE_DAYS = 30


def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except Exception:
        return datetime.now(ET).date()


def current_selected_date():
    """Return the currently selected MLB slate date as YYYY-MM-DD."""
    today = datetime.now(ET).date()
    selected = _as_date(st.session_state.get("ks_slate_date_picker", today))
    selected = max(today, min(selected, today + timedelta(days=MAX_FUTURE_DAYS)))
    return selected.isoformat()


def render_slate_date_control():
    """Main-site slate picker for today through the next 30 days."""
    today = datetime.now(ET).date()
    current = _as_date(current_selected_date())

    c1, c2 = st.columns([1.0, 2.2])
    with c1:
        selected = st.date_input(
            "📅 MLB slate date",
            value=current,
            min_value=today,
            max_value=today + timedelta(days=MAX_FUTURE_DAYS),
            key="ks_slate_date_picker",
        )
    with c2:
        offset = (selected - today).days
        label = "TODAY" if offset == 0 else "TOMORROW" if offset == 1 else f"+{offset} DAYS"
        st.markdown(
            f'<div class="ks-note" style="margin-top:1.65rem"><b>{label}</b> • '
            f'{selected.strftime("%A, %B %d, %Y")} • Future probable pitchers and lineups appear as MLB publishes them.</div>',
            unsafe_allow_html=True,
        )

    return selected.isoformat()


@st.cache_data(ttl=300, show_spinner=False)
def games_for_date(target_date):
    """Official MLB schedule for one selected date, with probable pitchers when announced."""
    day = _as_date(target_date).isoformat()
    response = requests.get(
        f"{MLB_API}/schedule",
        params={
            "sportId": 1,
            "date": day,
            "hydrate": "probablePitcher,team",
        },
        timeout=18,
    )
    response.raise_for_status()

    rows = []
    for block in response.json().get("dates", []):
        for game in block.get("games", []):
            away = game.get("teams", {}).get("away", {}) or {}
            home = game.get("teams", {}).get("home", {}) or {}
            away_team = away.get("team", {}) or {}
            home_team = home.get("team", {}) or {}
            away_pitcher = away.get("probablePitcher", {}) or {}
            home_pitcher = home.get("probablePitcher", {}) or {}

            game_time = datetime.fromisoformat(
                str(game.get("gameDate", "")).replace("Z", "+00:00")
            ).astimezone(ET)

            rows.append(
                {
                    "game_pk": game.get("gamePk"),
                    "game_date": day,
                    "venue_name": (game.get("venue") or {}).get("name", "Unknown"),
                    "away_team_id": away_team.get("id"),
                    "away_team": away_team.get("name", "Unknown"),
                    "home_team_id": home_team.get("id"),
                    "home_team": home_team.get("name", "Unknown"),
                    "away_pitcher_id": away_pitcher.get("id"),
                    "away_pitcher": away_pitcher.get("fullName", "TBD"),
                    "home_pitcher_id": home_pitcher.get("id"),
                    "home_pitcher": home_pitcher.get("fullName", "TBD"),
                    "first_pitch_et": game_time.strftime("%I:%M %p").lstrip("0"),
                    "status": (game.get("status") or {}).get("detailedState", "Unknown"),
                }
            )

    columns = [
        "game_pk", "game_date", "venue_name",
        "away_team_id", "away_team", "home_team_id", "home_team",
        "away_pitcher_id", "away_pitcher", "home_pitcher_id", "home_pitcher",
        "first_pitch_et", "status",
    ]
    return pd.DataFrame(rows, columns=columns)
