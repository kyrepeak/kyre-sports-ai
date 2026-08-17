from datetime import datetime

import pandas as pd
import requests
import streamlit as st

from engine import ET

MODEL_VERSION = "V18.1"


def _verified_df(games_df):
    if games_df is None:
        return pd.DataFrame()
    if games_df.empty:
        return games_df.copy()
    if "verified" in games_df.columns:
        return games_df[games_df["verified"].fillna(False).astype(bool)].copy()
    return games_df.copy()


def _game_state_label(status):
    text = str(status or "Unknown")
    low = text.lower()
    if any(x in low for x in ["final", "game over", "completed"]):
        return "FINAL"
    if any(x in low for x in ["in progress", "live", "warmup", "delayed", "manager challenge"]):
        return "LIVE"
    return "PREGAME"


def _sort_priority(status):
    state = _game_state_label(status)
    return {"LIVE": 0, "PREGAME": 1, "FINAL": 2}.get(state, 3)


@st.cache_data(ttl=4, show_spinner=False)
def fetch_live_feed(game_pk):
    game_pk = int(game_pk)
    urls = [
        f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live",
        f"https://statsapi.mlb.com/api/v1/game/{game_pk}/feed/live",
    ]
    last_exc = None
    for url in urls:
        try:
            response = requests.get(url, timeout=12)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            last_exc = exc
    if last_exc:
        raise last_exc
    raise RuntimeError("MLB live feed unavailable")


def _name(obj, fallback="—"):
    if not isinstance(obj, dict):
        return fallback
    return obj.get("fullName") or obj.get("name") or fallback


def _runner_name(offense, base):
    runner = (offense or {}).get(base)
    return _name(runner, "Empty") if runner else "Empty"


def _current_pitch(play):
    events = (play or {}).get("playEvents") or []
    pitch_events = [e for e in events if e.get("isPitch")]
    if not pitch_events:
        return None
    return pitch_events[-1]


def _live_state(feed):
    game_data = feed.get("gameData") or {}
    live = feed.get("liveData") or {}
    linescore = live.get("linescore") or {}
    plays = live.get("plays") or {}
    current = plays.get("currentPlay") or {}
    matchup = current.get("matchup") or {}
    count = current.get("count") or {}
    offense = linescore.get("offense") or {}
    defense = linescore.get("defense") or {}
    teams = linescore.get("teams") or {}
    away_ls = teams.get("away") or {}
    home_ls = teams.get("home") or {}
    away_team = ((game_data.get("teams") or {}).get("away") or {}).get("name", "Away")
    home_team = ((game_data.get("teams") or {}).get("home") or {}).get("name", "Home")
    status = (game_data.get("status") or {}).get("detailedState", "Unknown")

    batter = matchup.get("batter") or offense.get("batter") or {}
    pitcher = matchup.get("pitcher") or defense.get("pitcher") or {}
    last_pitch = _current_pitch(current)
    pitch_desc = None
    pitch_speed = None
    pitch_type = None
    if last_pitch:
        details = last_pitch.get("details") or {}
        pitch_data = last_pitch.get("pitchData") or {}
        pitch_desc = details.get("description")
        pitch_speed = pitch_data.get("startSpeed")
        pitch_type = ((details.get("type") or {}).get("description"))

    recent = []
    for play in (plays.get("allPlays") or [])[-5:]:
        about = play.get("about") or {}
        result = play.get("result") or {}
        inning = about.get("inning")
        half = str(about.get("halfInning") or "").title()
        recent.append(
            {
                "Inning": f"{half} {inning}" if inning else half,
                "Play": result.get("description") or result.get("event") or "—",
                "Score": f'{result.get("awayScore", away_ls.get("runs", 0))}-{result.get("homeScore", home_ls.get("runs", 0))}',
            }
        )

    return {
        "status": status,
        "state": _game_state_label(status),
        "away_team": away_team,
        "home_team": home_team,
        "away_runs": int(away_ls.get("runs", 0) or 0),
        "home_runs": int(home_ls.get("runs", 0) or 0),
        "away_hits": int(away_ls.get("hits", 0) or 0),
        "home_hits": int(home_ls.get("hits", 0) or 0),
        "away_errors": int(away_ls.get("errors", 0) or 0),
        "home_errors": int(home_ls.get("errors", 0) or 0),
        "inning": linescore.get("currentInningOrdinal") or linescore.get("currentInning") or "—",
        "inning_state": linescore.get("inningState") or "—",
        "balls": int(count.get("balls", linescore.get("balls", 0)) or 0),
        "strikes": int(count.get("strikes", linescore.get("strikes", 0)) or 0),
        "outs": int(count.get("outs", linescore.get("outs", 0)) or 0),
        "batter": _name(batter),
        "pitcher": _name(pitcher),
        "on_deck": _name(offense.get("onDeck"), "—"),
        "in_hole": _name(offense.get("inHole"), "—"),
        "first": _runner_name(offense, "first"),
        "second": _runner_name(offense, "second"),
        "third": _runner_name(offense, "third"),
        "last_play": ((current.get("result") or {}).get("description") or "Waiting for live play data…"),
        "last_pitch_desc": pitch_desc,
        "last_pitch_speed": pitch_speed,
        "last_pitch_type": pitch_type,
        "recent": recent,
        "updated": datetime.now(ET).strftime("%I:%M:%S %p ET").lstrip("0"),
    }


def _base_chip(label, runner):
    occupied = runner != "Empty"
    icon = "●" if occupied else "○"
    return f"{icon} {label}: {runner}"


def _scoreboard(state):
    st.markdown(
        f"### {state['away_team']} **{state['away_runs']}** — **{state['home_runs']}** {state['home_team']}"
    )
    st.caption(
        f"R/H/E • {state['away_team']}: {state['away_runs']}/{state['away_hits']}/{state['away_errors']} • "
        f"{state['home_team']}: {state['home_runs']}/{state['home_hits']}/{state['home_errors']}"
    )


def _render_final_summary(state):
    away_won = state["away_runs"] > state["home_runs"]
    home_won = state["home_runs"] > state["away_runs"]
    winner = state["away_team"] if away_won else state["home_team"] if home_won else "Tie"
    margin = abs(state["away_runs"] - state["home_runs"])

    st.markdown("## 🏁 Final Game Summary")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Winner", winner)
    with c2:
        st.metric("Final Margin", margin)
    with c3:
        st.metric("Total Runs", state["away_runs"] + state["home_runs"])
    with c4:
        st.metric("Status", "FINAL")

    st.markdown("### 📊 Final R/H/E")
    final_table = pd.DataFrame(
        [
            {
                "Team": state["away_team"],
                "R": state["away_runs"],
                "H": state["away_hits"],
                "E": state["away_errors"],
            },
            {
                "Team": state["home_team"],
                "R": state["home_runs"],
                "H": state["home_hits"],
                "E": state["home_errors"],
            },
        ]
    )
    st.dataframe(final_table, use_container_width=True, hide_index=True)

    st.markdown("### 📝 Final play")
    st.write(state["last_play"])

    if state["recent"]:
        with st.expander("📜 Last 5 plays", expanded=False):
            st.dataframe(pd.DataFrame(state["recent"]), use_container_width=True, hide_index=True)

    st.caption(
        "Completed games automatically switch to Final Summary mode so stale batter, count and base-runner data are not presented as live."
    )


def _render_pregame_summary(state):
    st.info("⏳ This game has not started yet. Live batter, pitcher, count, outs and base-runner data will appear automatically once MLB marks the game in progress.")
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Away", state["away_team"])
    with c2:
        st.metric("Home", state["home_team"])


def _render_active_game(state):
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Inning", f"{state['inning_state']} {state['inning']}")
    with c2:
        st.metric("Outs", state["outs"])
    with c3:
        st.metric("Count", f"{state['balls']}-{state['strikes']}")
    with c4:
        st.metric("Status", state["state"])

    st.markdown("### ⚾ At the plate")
    p1, p2 = st.columns(2)
    with p1:
        st.markdown(f"**Batter:** {state['batter']}")
        st.caption(f"On deck: {state['on_deck']} • In hole: {state['in_hole']}")
    with p2:
        st.markdown(f"**Pitcher:** {state['pitcher']}")
        if state["last_pitch_desc"]:
            extras = []
            if state["last_pitch_type"]:
                extras.append(str(state["last_pitch_type"]))
            if state["last_pitch_speed"] is not None:
                extras.append(f"{float(state['last_pitch_speed']):.1f} mph")
            suffix = f" • {' • '.join(extras)}" if extras else ""
            st.caption(f"Last pitch: {state['last_pitch_desc']}{suffix}")

    st.markdown("### ◇ Base runners")
    b1, b2, b3 = st.columns(3)
    with b1:
        st.info(_base_chip("1B", state["first"]))
    with b2:
        st.info(_base_chip("2B", state["second"]))
    with b3:
        st.info(_base_chip("3B", state["third"]))

    st.markdown("### 📝 Current play")
    st.write(state["last_play"])

    if state["recent"]:
        with st.expander("📜 Last 5 plays", expanded=False):
            st.dataframe(pd.DataFrame(state["recent"]), use_container_width=True, hide_index=True)


def _render_live_panel(game_pk, section_header):
    try:
        feed = fetch_live_feed(int(game_pk))
        state = _live_state(feed)
    except Exception as exc:
        st.error(f"Live MLB feed could not be loaded: {exc}")
        return

    section_header(
        f'{state["away_team"]} @ {state["home_team"]}',
        f'{state["state"]} • Updated {state["updated"]}',
    )
    _scoreboard(state)

    if state["state"] == "FINAL":
        _render_final_summary(state)
    elif state["state"] == "PREGAME":
        _render_pregame_summary(state)
    else:
        _render_active_game(state)


def render_live_hub(games_df, section_header, status_info, team_logo, h):
    verified = _verified_df(games_df)
    section_header(
        "MLB Live Game Center — V18.1",
        "LIVE games first • upcoming games second • finals last. Active games show batter, pitcher, count, outs, runners and recent plays.",
    )

    if verified.empty:
        st.info("No verified games are available on this selected slate.")
        return

    rows = [row for _, row in verified.iterrows()]
    rows.sort(
        key=lambda row: (
            _sort_priority(row.get("status")),
            str(row.get("first_pitch_et", "99:99")),
            str(row.get("away_team", "")),
        )
    )

    live_count = sum(1 for row in rows if _game_state_label(row.get("status")) == "LIVE")
    pregame_count = sum(1 for row in rows if _game_state_label(row.get("status")) == "PREGAME")
    final_count = sum(1 for row in rows if _game_state_label(row.get("status")) == "FINAL")
    st.caption(f"📡 {live_count} LIVE • ⏳ {pregame_count} upcoming • 🏁 {final_count} final")

    labels = []
    for row in rows:
        state = _game_state_label(row.get("status"))
        icon = {"LIVE": "🔴", "PREGAME": "⏳", "FINAL": "🏁"}.get(state, "⚾")
        labels.append(
            f'{icon} {state} • {row["away_team"]} @ {row["home_team"]} • '
            f'{row.get("first_pitch_et", "TBD")} ET'
        )

    choice = st.selectbox("Game", labels, key="v18_live_game")
    game = rows[labels.index(choice)]
    selected_state = _game_state_label(game.get("status"))

    if selected_state == "LIVE":
        st.caption("Auto-refreshes about every 10 seconds when supported by the running Streamlit version. You can also refresh manually.")
    elif selected_state == "FINAL":
        st.caption("Final games use a clean summary view instead of showing the last plate appearance as if it were still live.")
    else:
        st.caption("Pregame view will switch automatically to the full live dashboard when the game begins.")

    if st.button("🔄 REFRESH GAME STATE", use_container_width=True, key="v18_manual_refresh"):
        fetch_live_feed.clear()

    fragment = getattr(st, "fragment", None)
    if callable(fragment) and selected_state == "LIVE":
        @fragment(run_every="10s")
        def _auto_panel():
            _render_live_panel(int(game["game_pk"]), section_header)
        _auto_panel()
    else:
        _render_live_panel(int(game["game_pk"]), section_header)
