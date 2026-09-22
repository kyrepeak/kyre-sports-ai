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
            f'{selected.strftime("%A, %B %d, %Y")} • Schedule is date-verified from official MLB data. '
            f'Probable pitchers and lineups appear as MLB publishes them.</div>',
            unsafe_allow_html=True,
        )

    return selected.isoformat()


def _schedule_request(params):
    response = requests.get(
        f"{MLB_API}/schedule",
        params=params,
        timeout=18,
    )
    response.raise_for_status()
    return response.json()


def _game_pks(payload, day):
    out = set()
    for block in payload.get("dates", []):
        # The date block itself must match the requested MLB calendar date.
        if str(block.get("date", "")) != day:
            continue
        for game in block.get("games", []):
            pk = game.get("gamePk")
            if pk is not None:
                out.add(int(pk))
    return out


@st.cache_data(ttl=300, show_spinner=False)
def games_for_date(target_date):
    """Strictly verified official MLB regular-season schedule for one ET date.

    We query the official schedule two ways (start/end date and exact date),
    require matching gamePk values when both calls succeed, and then reject any
    game whose actual first-pitch timestamp does not land on the selected ET
    calendar date. This prevents stale/cross-date games from leaking into a
    future slate.
    """
    target = _as_date(target_date)
    day = target.isoformat()
    common = {
        "sportId": 1,
        "gameType": "R",
        "hydrate": "probablePitcher,team",
    }

    primary = _schedule_request(
        {
            **common,
            "startDate": day,
            "endDate": day,
        }
    )

    try:
        secondary = _schedule_request({**common, "date": day})
        secondary_pks = _game_pks(secondary, day)
    except requests.RequestException:
        secondary_pks = set()

    primary_pks = _game_pks(primary, day)
    verified_pks = primary_pks & secondary_pks if secondary_pks else primary_pks

    rows = []
    seen = set()
    for block in primary.get("dates", []):
        if str(block.get("date", "")) != day:
            continue

        for game in block.get("games", []):
            pk = game.get("gamePk")
            if pk is None:
                continue
            pk = int(pk)
            if pk not in verified_pks or pk in seen:
                continue

            raw_game_date = str(game.get("gameDate", ""))
            try:
                game_time = datetime.fromisoformat(
                    raw_game_date.replace("Z", "+00:00")
                ).astimezone(ET)
            except Exception:
                continue

            # Hard date guard: only games whose ET first pitch belongs to the
            # selected calendar date are allowed onto this slate.
            if game_time.date() != target:
                continue

            if str(game.get("gameType", "R")) != "R":
                continue

            away = game.get("teams", {}).get("away", {}) or {}
            home = game.get("teams", {}).get("home", {}) or {}
            away_team = away.get("team", {}) or {}
            home_team = home.get("team", {}) or {}
            away_pitcher = away.get("probablePitcher", {}) or {}
            home_pitcher = home.get("probablePitcher", {}) or {}

            away_id = away_team.get("id")
            home_id = home_team.get("id")
            if not away_id or not home_id or int(away_id) == int(home_id):
                continue

            rows.append(
                {
                    "game_pk": pk,
                    "game_date": day,
                    "verified": True,
                    "venue_name": (game.get("venue") or {}).get("name", "Unknown"),
                    "away_team_id": away_id,
                    "away_team": away_team.get("name", "Unknown"),
                    "home_team_id": home_id,
                    "home_team": home_team.get("name", "Unknown"),
                    "away_pitcher_id": away_pitcher.get("id"),
                    "away_pitcher": away_pitcher.get("fullName", "TBD"),
                    "home_pitcher_id": home_pitcher.get("id"),
                    "home_pitcher": home_pitcher.get("fullName", "TBD"),
                    "first_pitch_et": game_time.strftime("%I:%M %p").lstrip("0"),
                    "status": (game.get("status") or {}).get("detailedState", "Unknown"),
                }
            )
            seen.add(pk)

    columns = [
        "game_pk", "game_date", "verified", "venue_name",
        "away_team_id", "away_team", "home_team_id", "home_team",
        "away_pitcher_id", "away_pitcher", "home_pitcher_id", "home_pitcher",
        "first_pitch_et", "status",
    ]
    df = pd.DataFrame(rows, columns=columns)
    if not df.empty:
        df = df.sort_values("first_pitch_et", kind="stable").reset_index(drop=True)
    return df
