from datetime import datetime

import pandas as pd
import requests
import streamlit as st

from engine import ET, MLB_API

MODEL_VERSION = "V18.2"


def _verified_df(games_df):
    if games_df is None:
        return pd.DataFrame()
    if games_df.empty:
        return games_df.copy()
    if "verified" in games_df.columns:
        return games_df[games_df["verified"].fillna(False).astype(bool)].copy()
    return games_df.copy()


def _state_label(status):
    text = str(status or "Unknown")
    low = text.lower()
    if any(x in low for x in ["final", "game over", "completed"]):
        return "FINAL"
    if any(x in low for x in ["in progress", "live", "warmup", "manager challenge", "review"]):
        return "LIVE"
    if "delayed" in low:
        return "DELAYED"
    return "PREGAME"


def _priority(status):
    return {"LIVE": 0, "DELAYED": 1, "PREGAME": 2, "FINAL": 3}.get(_state_label(status), 4)


def _time_sort(value):
    try:
        return datetime.strptime(str(value), "%I:%M %p").time()
    except Exception:
        return datetime.max.time()


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
            r = requests.get(url, timeout=12)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            last_exc = exc
    if last_exc:
        raise last_exc
    raise RuntimeError("MLB live feed unavailable")


@st.cache_data(ttl=5, show_spinner=False)
def fetch_live_slate(game_date, allowed_pks):
    """Refresh all statuses/scores for the verified slate in one MLB request."""
    allowed = {int(x) for x in allowed_pks}
    r = requests.get(
        f"{MLB_API}/schedule",
        params={
            "sportId": 1,
            "date": str(game_date),
            "hydrate": "linescore,team,probablePitcher",
        },
        timeout=12,
    )
    r.raise_for_status()
    payload = r.json()
    out = {}
    for block in payload.get("dates", []):
        for game in block.get("games", []):
            pk = game.get("gamePk")
            if pk is None or int(pk) not in allowed:
                continue
            teams = game.get("teams") or {}
            away = teams.get("away") or {}
            home = teams.get("home") or {}
            linescore = game.get("linescore") or {}
            out[int(pk)] = {
                "status": (game.get("status") or {}).get("detailedState", "Unknown"),
                "away_runs": int(away.get("score", 0) or 0),
                "home_runs": int(home.get("score", 0) or 0),
                "inning": linescore.get("currentInningOrdinal") or linescore.get("currentInning") or "",
                "inning_state": linescore.get("inningState") or "",
            }
    return out


def _name(obj, fallback="—"):
    if not isinstance(obj, dict):
        return fallback
    return obj.get("fullName") or obj.get("name") or fallback


def _runner_name(offense, base):
    runner = (offense or {}).get(base)
    return _name(runner, "Empty") if runner else "Empty"


def _last_pitch(current):
    events = (current or {}).get("playEvents") or []
    pitches = [event for event in events if event.get("isPitch")]
    return pitches[-1] if pitches else None


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
    ls_teams = linescore.get("teams") or {}
    away_ls = ls_teams.get("away") or {}
    home_ls = ls_teams.get("home") or {}
    teams = game_data.get("teams") or {}
    away_team = (teams.get("away") or {}).get("name", "Away")
    home_team = (teams.get("home") or {}).get("name", "Home")
    status = (game_data.get("status") or {}).get("detailedState", "Unknown")

    pitch = _last_pitch(current)
    pitch_desc = pitch_type = None
    pitch_speed = None
    if pitch:
        details = pitch.get("details") or {}
        pitch_desc = details.get("description")
        pitch_type = (details.get("type") or {}).get("description")
        pitch_speed = (pitch.get("pitchData") or {}).get("startSpeed")

    recent = []
    for play in (plays.get("allPlays") or [])[-5:]:
        about = play.get("about") or {}
        result = play.get("result") or {}
        inning = about.get("inning")
        half = str(about.get("halfInning") or "").title()
        recent.append({
            "Inning": f"{half} {inning}" if inning else half,
            "Play": result.get("description") or result.get("event") or "—",
            "Score": f'{result.get("awayScore", away_ls.get("runs", 0))}-{result.get("homeScore", home_ls.get("runs", 0))}',
        })

    return {
        "status": status,
        "state": _state_label(status),
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
        "batter": _name(matchup.get("batter") or offense.get("batter")),
        "pitcher": _name(matchup.get("pitcher") or defense.get("pitcher")),
        "on_deck": _name(offense.get("onDeck")),
        "in_hole": _name(offense.get("inHole")),
        "first": _runner_name(offense, "first"),
        "second": _runner_name(offense, "second"),
        "third": _runner_name(offense, "third"),
        "last_play": (current.get("result") or {}).get("description") or "Waiting for live play data…",
        "last_pitch_desc": pitch_desc,
        "last_pitch_type": pitch_type,
        "last_pitch_speed": pitch_speed,
        "recent": recent,
        "updated": datetime.now(ET).strftime("%I:%M:%S %p ET").lstrip("0"),
    }


def _scoreboard(state):
    st.markdown(f"### {state['away_team']} **{state['away_runs']}** — **{state['home_runs']}** {state['home_team']}")
    st.caption(
        f"R/H/E • {state['away_team']}: {state['away_runs']}/{state['away_hits']}/{state['away_errors']} • "
        f"{state['home_team']}: {state['home_runs']}/{state['home_hits']}/{state['home_errors']}"
    )


def _render_final(state):
    winner = state["away_team"] if state["away_runs"] > state["home_runs"] else state["home_team"]
    st.markdown("## 🏁 Final Game Summary")
    cols = st.columns(4)
    values = [
        ("Winner", winner),
        ("Final Margin", abs(state["away_runs"] - state["home_runs"])),
        ("Total Runs", state["away_runs"] + state["home_runs"]),
        ("Status", "FINAL"),
    ]
    for col, (label, value) in zip(cols, values):
        with col:
            st.metric(label, value)
    st.dataframe(pd.DataFrame([
        {"Team": state["away_team"], "R": state["away_runs"], "H": state["away_hits"], "E": state["away_errors"]},
        {"Team": state["home_team"], "R": state["home_runs"], "H": state["home_hits"], "E": state["home_errors"]},
    ]), use_container_width=True, hide_index=True)
    st.markdown("### 📝 Final play")
    st.write(state["last_play"])
    if state["recent"]:
        with st.expander("📜 Last 5 plays"):
            st.dataframe(pd.DataFrame(state["recent"]), use_container_width=True, hide_index=True)


def _render_active(state):
    cols = st.columns(4)
    values = [
        ("Inning", f"{state['inning_state']} {state['inning']}"),
        ("Outs", state["outs"]),
        ("Count", f"{state['balls']}-{state['strikes']}"),
        ("Status", state["state"]),
    ]
    for col, (label, value) in zip(cols, values):
        with col:
            st.metric(label, value)

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
    runners = [("1B", state["first"]), ("2B", state["second"]), ("3B", state["third"])]
    for col, (base, runner) in zip(st.columns(3), runners):
        with col:
            st.info(f"{'●' if runner != 'Empty' else '○'} {base}: {runner}")

    st.markdown("### 📝 Current play")
    st.write(state["last_play"])
    if state["recent"]:
        with st.expander("📜 Last 5 plays"):
            st.dataframe(pd.DataFrame(state["recent"]), use_container_width=True, hide_index=True)


def _render_selected(game_pk, section_header):
    try:
        state = _live_state(fetch_live_feed(int(game_pk)))
    except Exception as exc:
        st.error(f"Live MLB feed could not be loaded: {exc}")
        return

    section_header(
        f'{state["away_team"]} @ {state["home_team"]}',
        f'{state["state"]} • Updated {state["updated"]}',
    )
    _scoreboard(state)
    if state["state"] == "FINAL":
        _render_final(state)
    elif state["state"] == "PREGAME":
        st.info("⏳ This game has not started yet. Live state will appear automatically when MLB marks it in progress.")
    else:
        _render_active(state)


def _live_center_body(verified, section_header):
    if st.button("🔄 REFRESH ALL LIVE GAMES", use_container_width=True, key="v182_refresh"):
        fetch_live_feed.clear()
        fetch_live_slate.clear()

    game_date = str(verified.iloc[0].get("game_date", datetime.now(ET).date().isoformat()))
    allowed = tuple(sorted(pd.to_numeric(verified["game_pk"], errors="coerce").dropna().astype(int).tolist()))
    try:
        fresh = fetch_live_slate(game_date, allowed)
    except Exception:
        fresh = {}

    rows = []
    for _, row in verified.iterrows():
        data = row.to_dict()
        pk = int(data["game_pk"])
        if pk in fresh:
            data.update(fresh[pk])
        rows.append(data)

    rows.sort(key=lambda row: (_priority(row.get("status")), _time_sort(row.get("first_pitch_et")), str(row.get("away_team", ""))))

    live_rows = [r for r in rows if _state_label(r.get("status")) == "LIVE"]
    delayed_rows = [r for r in rows if _state_label(r.get("status")) == "DELAYED"]
    upcoming_rows = [r for r in rows if _state_label(r.get("status")) == "PREGAME"]
    final_rows = [r for r in rows if _state_label(r.get("status")) == "FINAL"]
    st.caption(f"📡 {len(live_rows)} LIVE • ⚠️ {len(delayed_rows)} delayed • ⏳ {len(upcoming_rows)} upcoming • 🏁 {len(final_rows)} final")

    if live_rows:
        st.markdown("### 🔴 Live right now")
        for r in live_rows:
            inning = f"{r.get('inning_state', '')} {r.get('inning', '')}".strip()
            st.info(
                f"**{r['away_team']} {int(r.get('away_runs', 0) or 0)} — {int(r.get('home_runs', 0) or 0)} {r['home_team']}**"
                + (f" • {inning}" if inning else "")
            )

    labels = []
    for r in rows:
        state = _state_label(r.get("status"))
        icon = {"LIVE": "🔴", "DELAYED": "⚠️", "PREGAME": "⏳", "FINAL": "🏁"}.get(state, "⚾")
        score = ""
        if state in {"LIVE", "FINAL"}:
            score = f" • {int(r.get('away_runs', 0) or 0)}-{int(r.get('home_runs', 0) or 0)}"
        labels.append(f"{icon} {state} • {r['away_team']} @ {r['home_team']}{score} • {r.get('first_pitch_et', 'TBD')} ET")

    if not labels:
        st.info("No games found on this verified slate.")
        return

    # When a stored selection points to an old label, Streamlit falls back to the
    # first item. Because rows are live-first, an active game becomes the default.
    choice = st.selectbox("Game", labels, key="v182_live_game")
    game = rows[labels.index(choice)]
    _render_selected(int(game["game_pk"]), section_header)


def render_live_hub(games_df, section_header, status_info, team_logo, h):
    verified = _verified_df(games_df)
    section_header(
        "MLB Live Game Center — V18.2",
        "Live slate refresh + live-first selector + score, inning, batter, pitcher, count, outs, runners and recent plays.",
    )
    if verified.empty:
        st.info("No verified games are available on this selected slate.")
        return

    fragment = getattr(st, "fragment", None)
    if callable(fragment):
        @fragment(run_every="10s")
        def _auto_center():
            _live_center_body(verified, section_header)
        _auto_center()
    else:
        st.caption("Auto-refresh is not supported by this Streamlit version. Use the refresh button for current game state.")
        _live_center_body(verified, section_header)
