"""Kyre Sports AI — NFL Moneyline V4.0 Step 4A team-strength baseline.

Step 3 remains a final-output safety gate, not a development blocker. This module
adds a descriptive/carryover team-strength layer from completed NFL regular-season
results while leaving sportsbook prices, final win probability, Monte Carlo, EV,
ranking and recommendations OFF.

Step 4A inputs:
- most recent completed prior regular season;
- current regular-season completed games through the selected slate date, when any;
- win rate, PF/G, PA/G, point differential/G and recent-L6 form;
- six-game prior shrinkage when blending an in-progress current season.

The 0-100 Team Strength Index is an internal baseline score, not a calibrated win
probability. Step 4B will add opponent/home-field matchup structure before any
P(win) can be exposed.
"""
from __future__ import annotations

from datetime import date
from html import escape

import numpy as np
import pandas as pd
import requests
import streamlit as st

import nfl_hub_v1 as foundation
import nfl_moneyline_hub_v1 as step1
import nfl_moneyline_hub_v36 as step3

MODEL_VERSION = "NFL MONEYLINE V4.0 • STEP 4A TEAM-STRENGTH BASELINE"
ESPN_TEAM_SCHEDULE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team}/schedule"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
    "Accept": "application/json,text/plain,*/*",
}
PRIOR_GAMES = 6.0
LEAGUE_PPG_REF = 22.5


def _safe(value, default="") -> str:
    text = str(value or "").strip()
    return text or default


def _num(value):
    try:
        return float(value)
    except Exception:
        return np.nan


def _season_year_for_day(day_str: str) -> int:
    d = pd.to_datetime(day_str).date()
    # Jan/Feb NFL games belong to the season that began the previous calendar year.
    return int(d.year - 1 if d.month <= 2 else d.year)


@st.cache_data(ttl=21600, show_spinner=False)
def _completed_regular_games(team_abbr: str, season: int, cutoff_day: str):
    """Fetch one team's completed regular-season games, fail-closed on bad data."""
    abbr = _safe(team_abbr).upper()
    diag = {
        "ok": False,
        "http": None,
        "error": "",
        "team": abbr,
        "season": int(season),
        "games": 0,
        "provider": "ESPN NFL team schedule",
    }
    if not abbr:
        diag["error"] = "missing team abbreviation"
        return pd.DataFrame(), diag

    url = ESPN_TEAM_SCHEDULE.format(team=abbr.lower())
    params = {"season": int(season), "seasontype": 2}
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=8)
        diag["http"] = int(r.status_code)
        r.raise_for_status()
        payload = r.json()
    except Exception as exc:
        diag["error"] = str(exc)[:220]
        return pd.DataFrame(), diag

    cutoff = pd.to_datetime(cutoff_day).date()
    rows = []
    for event in payload.get("events", []) or []:
        status = (event.get("status") or {}).get("type") or {}
        if not bool(status.get("completed")) and _safe(status.get("state")).lower() != "post":
            continue
        try:
            event_day = pd.to_datetime(event.get("date"), utc=True).tz_convert(foundation.ET).date()
        except Exception:
            continue
        if event_day > cutoff:
            continue

        comps = event.get("competitions") or []
        if not comps:
            continue
        competitors = comps[0].get("competitors") or []
        ours = None
        opp = None
        for comp in competitors:
            team = comp.get("team") or {}
            comp_abbr = _safe(team.get("abbreviation")).upper()
            if comp_abbr == abbr:
                ours = comp
            else:
                opp = comp
        if not ours or not opp:
            continue

        pf = _num(ours.get("score"))
        pa = _num(opp.get("score"))
        if not np.isfinite(pf) or not np.isfinite(pa):
            continue
        result = "T" if pf == pa else ("W" if pf > pa else "L")
        opp_team = opp.get("team") or {}
        rows.append({
            "date": pd.Timestamp(event_day),
            "result": result,
            "pf": float(pf),
            "pa": float(pa),
            "margin": float(pf - pa),
            "opponent": _safe(opp_team.get("displayName") or opp_team.get("shortDisplayName")),
            "opponent_abbr": _safe(opp_team.get("abbreviation")).upper(),
            "home_away": _safe(ours.get("homeAway")).lower(),
        })

    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.sort_values("date").drop_duplicates(subset=["date", "opponent_abbr"], keep="last").reset_index(drop=True)
    diag["ok"] = True
    diag["games"] = int(len(frame))
    return frame, diag


def _summarize_games(frame: pd.DataFrame) -> dict:
    if frame is None or frame.empty:
        return {
            "games": 0, "wins": 0, "losses": 0, "ties": 0, "win_pct": np.nan,
            "ppg": np.nan, "papg": np.nan, "diff_pg": np.nan,
            "recent6_win_pct": np.nan, "recent6_diff_pg": np.nan,
        }
    g = len(frame)
    wins = int((frame["result"] == "W").sum())
    losses = int((frame["result"] == "L").sum())
    ties = int((frame["result"] == "T").sum())
    recent = frame.tail(6)
    return {
        "games": int(g),
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "win_pct": float((wins + 0.5 * ties) / g),
        "ppg": float(frame["pf"].mean()),
        "papg": float(frame["pa"].mean()),
        "diff_pg": float(frame["margin"].mean()),
        "recent6_win_pct": float(((recent["result"] == "W").sum() + 0.5 * (recent["result"] == "T").sum()) / len(recent)),
        "recent6_diff_pg": float(recent["margin"].mean()),
    }


def _blend(prior: dict, current: dict) -> dict:
    """Six-game prior shrinkage; current season gradually earns more weight."""
    cg = float(current.get("games") or 0)
    if cg <= 0:
        out = dict(prior)
        out["blend_current_weight"] = 0.0
        out["source_mode"] = "PRIOR SEASON CARRYOVER"
        return out

    pw = PRIOR_GAMES
    cw = cg
    out = {"games": int(cg), "blend_current_weight": float(cw / (pw + cw)), "source_mode": "SHRUNK CURRENT + PRIOR"}
    for key in ("win_pct", "ppg", "papg", "diff_pg"):
        pv = prior.get(key)
        cv = current.get(key)
        if np.isfinite(_num(pv)) and np.isfinite(_num(cv)):
            out[key] = float((pw * float(pv) + cw * float(cv)) / (pw + cw))
        elif np.isfinite(_num(cv)):
            out[key] = float(cv)
        else:
            out[key] = float(pv) if np.isfinite(_num(pv)) else np.nan

    # Recent form should react faster once at least three current games exist.
    if cg >= 3 and np.isfinite(_num(current.get("recent6_diff_pg"))):
        out["recent6_diff_pg"] = float(current.get("recent6_diff_pg"))
        out["recent6_win_pct"] = float(current.get("recent6_win_pct"))
    else:
        out["recent6_diff_pg"] = float(prior.get("recent6_diff_pg")) if np.isfinite(_num(prior.get("recent6_diff_pg"))) else np.nan
        out["recent6_win_pct"] = float(prior.get("recent6_win_pct")) if np.isfinite(_num(prior.get("recent6_win_pct"))) else np.nan
    return out


def _clip100(value: float) -> float:
    return float(np.clip(value, 0.0, 100.0))


def _strength_index(profile: dict) -> tuple[float, dict]:
    """Transparent V1 baseline index; deliberately NOT a calibrated P(win)."""
    needed = [profile.get(k) for k in ("win_pct", "ppg", "papg", "diff_pg", "recent6_diff_pg")]
    if not all(np.isfinite(_num(x)) for x in needed):
        return np.nan, {}

    parts = {
        "win": _clip100(float(profile["win_pct"]) * 100.0),
        "margin": _clip100(50.0 + 3.0 * float(profile["diff_pg"])),
        "offense": _clip100(50.0 + 2.5 * (float(profile["ppg"]) - LEAGUE_PPG_REF)),
        "defense": _clip100(50.0 + 2.5 * (LEAGUE_PPG_REF - float(profile["papg"]))),
        "recent": _clip100(50.0 + 3.0 * float(profile["recent6_diff_pg"])),
    }
    score = (
        0.30 * parts["win"]
        + 0.30 * parts["margin"]
        + 0.15 * parts["offense"]
        + 0.15 * parts["defense"]
        + 0.10 * parts["recent"]
    )
    return float(score), parts


def _team_profile(abbr: str, team_name: str, day_str: str) -> dict:
    season_year = _season_year_for_day(day_str)
    prior_year = season_year - 1

    prior_games, prior_diag = _completed_regular_games(abbr, prior_year, f"{prior_year}-12-31")
    # Include Jan regular-season boundary games by allowing cutoff through Feb of following year.
    if prior_diag.get("ok"):
        prior_games2, prior_diag2 = _completed_regular_games(abbr, prior_year, f"{prior_year + 1}-02-28")
        if prior_diag2.get("ok") and len(prior_games2) >= len(prior_games):
            prior_games, prior_diag = prior_games2, prior_diag2

    current_games, current_diag = _completed_regular_games(abbr, season_year, day_str)
    prior = _summarize_games(prior_games)
    current = _summarize_games(current_games)

    ready = bool(prior_diag.get("ok") and prior.get("games", 0) >= 12)
    if not ready:
        return {
            "team": team_name, "abbr": abbr, "ready": False,
            "prior_year": prior_year, "season_year": season_year,
            "prior_diag": prior_diag, "current_diag": current_diag,
            "error": "insufficient completed prior regular-season data",
        }

    blended = _blend(prior, current)
    index, parts = _strength_index(blended)
    quality = "HIGH" if prior.get("games", 0) >= 16 else "MEDIUM"
    return {
        "team": team_name,
        "abbr": abbr,
        "ready": bool(np.isfinite(index)),
        "prior_year": prior_year,
        "season_year": season_year,
        "prior": prior,
        "current": current,
        "blended": blended,
        "strength_index": index,
        "components": parts,
        "quality": quality,
        "prior_diag": prior_diag,
        "current_diag": current_diag,
    }


def _fmt(value, digits=1, suffix=""):
    return "—" if not np.isfinite(_num(value)) else f"{float(value):.{digits}f}{suffix}"


def _render_team_strength(profile: dict):
    team = _safe(profile.get("team"), profile.get("abbr"))
    st.markdown(f"#### {escape(team)}")
    if not profile.get("ready"):
        st.warning("Baseline unavailable — historical regular-season data did not pass the minimum-data guard.")
        diag = profile.get("prior_diag") or {}
        st.caption(f"Provider: {diag.get('provider', 'ESPN')} • HTTP {diag.get('http') or '—'} • {diag.get('error') or profile.get('error') or 'insufficient data'}")
        return

    b = profile["blended"]
    p = profile["prior"]
    c = profile["current"]
    m1, m2, m3 = st.columns(3)
    m1.metric("Strength index", _fmt(profile.get("strength_index"), 1))
    m2.metric("Blended diff/G", _fmt(b.get("diff_pg"), 1))
    m3.metric("Data quality", profile.get("quality", "—"))

    a, bcol, ccol, d = st.columns(4)
    a.metric("Win %", _fmt(b.get("win_pct") * 100 if np.isfinite(_num(b.get("win_pct"))) else np.nan, 1, "%"))
    bcol.metric("PF/G", _fmt(b.get("ppg"), 1))
    ccol.metric("PA/G", _fmt(b.get("papg"), 1))
    d.metric("Recent L6 diff", _fmt(b.get("recent6_diff_pg"), 1))

    current_games = int(c.get("games") or 0)
    if current_games:
        st.caption(
            f"Profile blend: {profile['prior_year']} prior + {current_games} completed {profile['season_year']} regular-season game(s) • "
            f"current-season weight {100 * profile['blended'].get('blend_current_weight', 0):.0f}%"
        )
    else:
        st.caption(f"Profile source: {profile['prior_year']} completed regular season carryover • current regular-season games: 0")

    with st.expander("📐 Step 4A baseline components", expanded=False):
        comp = profile.get("components") or {}
        rows = [
            {"Component": "Win rate", "Weight": "30%", "Score": _fmt(comp.get("win"), 1)},
            {"Component": "Point differential", "Weight": "30%", "Score": _fmt(comp.get("margin"), 1)},
            {"Component": "Offense PF/G", "Weight": "15%", "Score": _fmt(comp.get("offense"), 1)},
            {"Component": "Defense PA/G", "Weight": "15%", "Score": _fmt(comp.get("defense"), 1)},
            {"Component": "Recent L6 margin", "Weight": "10%", "Score": _fmt(comp.get("recent"), 1)},
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption("Internal baseline only. This index is not a probability and is not yet opponent-adjusted, home-field-adjusted, QB-adjusted or market-calibrated.")


def _render_step4a():
    selected = st.session_state.get("nfl_v1_date", date.today())
    day_str = pd.to_datetime(selected).strftime("%Y-%m-%d")
    schedule, diag = foundation.load_nfl_slate(day_str)
    pregame, _ = step1._pregame_partition(schedule, day_str, now_et=pd.Timestamp.now(tz=foundation.ET))

    st.markdown("### 🧮 Step 4 — Team-Strength Win Model")
    st.caption(
        "Step 4A baseline ACTIVE • completed regular-season results only • current season shrinks toward a six-game prior • "
        "preseason results are not used as team-strength evidence • final P(win) remains locked."
    )

    if not diag.get("request_ok") or pregame.empty:
        st.warning("Step 4A cannot build a team baseline because no verified pregame game is available.")
        return False

    teams = {}
    for _, game in pregame.iterrows():
        for side in ("away", "home"):
            abbr = _safe(game.get(f"{side}_abbr")).upper()
            name = _safe(game.get(f"{side}_team"), abbr)
            if abbr and abbr not in teams:
                teams[abbr] = _team_profile(abbr, name, day_str)

    ready_count = sum(1 for x in teams.values() if x.get("ready"))
    q1, q2, q3 = st.columns(3)
    q1.metric("Teams modeled", f"{ready_count}/{len(teams)}")
    q2.metric("Baseline state", "ACTIVE" if ready_count == len(teams) and teams else "CHECK")
    q3.metric("Final P(win)", "LOCKED")

    if ready_count == len(teams) and teams:
        st.success("✅ STEP 4A PASSED • historical team-strength baseline calculated for every pregame team.")
    else:
        st.warning("⚠️ STEP 4A CHECK • at least one team lacks sufficient historical regular-season data. No missing value is fabricated.")

    for _, game in pregame.iterrows():
        away = _safe(game.get("away_abbr")).upper()
        home = _safe(game.get("home_abbr")).upper()
        st.markdown(f"#### Baseline — {escape(_safe(game.get('away_team')))} @ {escape(_safe(game.get('home_team')))}")
        left, right = st.columns(2)
        with left:
            _render_team_strength(teams.get(away, {}))
        with right:
            _render_team_strength(teams.get(home, {}))
        if teams.get(away, {}).get("ready") and teams.get(home, {}).get("ready"):
            delta = float(teams[away]["strength_index"] - teams[home]["strength_index"])
            leader = _safe(game.get("away_team")) if delta > 0 else _safe(game.get("home_team")) if delta < 0 else "Even"
            st.info(
                f"Baseline-only separation: {abs(delta):.1f} index points • stronger historical profile: {leader}. "
                "This is NOT a Moneyline pick and does not include home field, current game plan, matchup, sportsbook or probability calibration."
            )

    st.session_state["nfl_moneyline_v4_strength_profiles"] = teams
    st.session_state["nfl_moneyline_v4_strength_ready"] = bool(teams and ready_count == len(teams))
    return bool(teams and ready_count == len(teams))


def render_nfl_moneyline_hub():
    """Render Step 3.6 unchanged, injecting Step 4A immediately before production locks."""
    real_markdown = st.markdown
    real_dataframe = st.dataframe
    real_caption = st.caption
    state = {"step4_injected": False, "step4_ready": False}

    def _markdown(body, *args, **kwargs):
        if isinstance(body, str):
            if "<span class=\"knfl-ml-chip\">STEP 3</span>" in body:
                body = body.replace(
                    '<span class="knfl-ml-chip">STEP 3</span>',
                    '<span class="knfl-ml-chip">STEP 4A</span>',
                )
                body = body.replace(
                    "No sportsbook/model math is active.",
                    "Team-strength baseline is active; final win probability, sportsbook math and Monte Carlo remain off.",
                )
            if body.strip() == "### 🔒 Moneyline production locks" and not state["step4_injected"]:
                state["step4_injected"] = True
                state["step4_ready"] = _render_step4a()
        return real_markdown(body, *args, **kwargs)

    def _dataframe(data=None, *args, **kwargs):
        if isinstance(data, pd.DataFrame) and "Layer" in data.columns and "State" in data.columns:
            values = set(data["Layer"].astype(str).tolist())
            if "Team-strength win model" in values:
                data = data.copy()
                mask = data["Layer"].astype(str) == "Team-strength win model"
                data.loc[mask, "State"] = (
                    "STEP 4A BASELINE READY • FINAL P(WIN) GATED"
                    if state.get("step4_ready")
                    else "STEP 4A CHECK • FINAL P(WIN) GATED"
                )
        return real_dataframe(data, *args, **kwargs)

    def _caption(body, *args, **kwargs):
        if isinstance(body, str) and body.startswith("Step 3 performs zero sportsbook requests"):
            body = (
                "Step 4A calculates a descriptive historical team-strength baseline only. "
                "Sportsbook prices, calibrated win probability, Monte Carlo, edge/EV and final grading remain OFF. "
                "Step 3 remains a final-output safety gate during preseason."
            )
        return real_caption(body, *args, **kwargs)

    st.markdown = _markdown
    st.dataframe = _dataframe
    st.caption = _caption
    try:
        return step3.render_nfl_moneyline_hub()
    finally:
        st.markdown = real_markdown
        st.dataframe = real_dataframe
        st.caption = real_caption


__all__ = ["MODEL_VERSION", "render_nfl_moneyline_hub"]
