"""NFL Passing Yards V3 — Step 2 quarterback passing profile.

Preserves Step 1 official matchup + QB identity and adds descriptive ESPN season
passing production plus recent-game context. No passing-yards projection,
probability, sportsbook grade, Monte Carlo, ranking, or recommendation is active.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
import math

import pandas as pd
import streamlit as st

import nfl_hub_v20 as nfl
import nfl_passing_yards_hub_v1 as foundation
import nfl_passing_yards_hub_v2 as step1_ui
import nfl_passing_yards_identity_v1 as identity
import nfl_passing_yards_profile_v1 as profile

MODEL_VERSION = "NFL PASSING YARDS V3 • STEP 2 QB PASSING PROFILE"

_STEP2_CSS = r"""
<style>
.kpy-pgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:8px 0 10px}
.kpy-profile{border:1px solid #34516c;background:#091725;border-radius:13px;padding:10px}
.kpy-profile-head{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:7px}
.kpy-profile-name{color:#f8fafc;font-size:.92rem;font-weight:950}.kpy-profile-state{font-size:.54rem;font-weight:950;color:#7ff2c2}
.kpy-profile-state.check{color:#f1ca72}.kpy-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px}
.kpy-metric{border:1px solid #203c53;background:#07121d;border-radius:9px;padding:7px 6px;min-width:0}
.kpy-metric b{display:block;color:#f6fbff;font-size:.82rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.kpy-metric span{display:block;color:#70879a;font-size:.45rem;text-transform:uppercase;margin-top:2px}
.kpy-trend{margin-top:7px;padding-top:7px;border-top:1px solid #1b3449;color:#8299ad;font-size:.52rem;line-height:1.55}
@media(max-width:820px){.kpy-pgrid{grid-template-columns:1fr}.kpy-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""


def _safe(value, default="") -> str:
    text = str(value or "").strip()
    return text or default


def _finite(value) -> bool:
    try:
        return math.isfinite(float(value))
    except Exception:
        return False


def _fmt(value, digits=1, suffix="") -> str:
    if not _finite(value):
        return "—"
    return f"{float(value):.{digits}f}{suffix}"


def _count(value) -> str:
    if not _finite(value):
        return "—"
    return str(int(round(float(value))))


def _season_type_code(text: str) -> int:
    return {"preseason": 1, "regular season": 2, "postseason": 3}.get(_safe(text).lower(), 2)


def _profile_card(team_ctx: dict, qb_profile: dict) -> str:
    qb = team_ctx.get("qb1") or {}
    name = _safe(qb.get("name"), "Unresolved QB1")
    team = _safe(team_ctx.get("team"), team_ctx.get("abbr"))
    season = qb_profile.get("season") or {}
    ready = bool(qb_profile.get("ready"))
    state_class = "" if ready else " check"
    state = "PROFILE GREEN" if ready else "PROFILE CHECK"
    recent3_yards = _fmt(qb_profile.get("recent3_yards"), 1)
    recent5_yards = _fmt(qb_profile.get("recent5_yards"), 1)
    recent3_att = _fmt(qb_profile.get("recent3_attempts"), 1)
    split_home = _fmt(qb_profile.get("home_yards"), 1)
    split_away = _fmt(qb_profile.get("away_yards"), 1)
    return (
        '<section class="kpy-profile">'
        '<div class="kpy-profile-head">'
        f'<div><div class="kpy-profile-name">{escape(name)}</div><div class="kpy-step-sub">{escape(team)} • ESPN athlete {escape(_safe(qb_profile.get("athlete_id"), "—"))}</div></div>'
        f'<div class="kpy-profile-state{state_class}">{state}</div></div>'
        '<div class="kpy-metrics">'
        f'<div class="kpy-metric"><b>{_count(season.get("games"))}</b><span>Games</span></div>'
        f'<div class="kpy-metric"><b>{_fmt(season.get("yards_per_game"),1)}</b><span>Pass Yds/G</span></div>'
        f'<div class="kpy-metric"><b>{_fmt(season.get("attempts_per_game"),1)}</b><span>Attempts/G</span></div>'
        f'<div class="kpy-metric"><b>{_fmt(season.get("yards_per_attempt"),2)}</b><span>Yards/Att</span></div>'
        f'<div class="kpy-metric"><b>{_fmt(season.get("completion_pct"),1,"%")}</b><span>Completion</span></div>'
        f'<div class="kpy-metric"><b>{_count(season.get("passing_yards"))}</b><span>Pass Yards</span></div>'
        f'<div class="kpy-metric"><b>{_count(season.get("passing_tds"))}</b><span>Pass TD</span></div>'
        f'<div class="kpy-metric"><b>{_count(season.get("interceptions"))}</b><span>INT</span></div>'
        '</div>'
        '<div class="kpy-trend">'
        f'Recent 3: <b>{recent3_yards}</b> yds • <b>{recent3_att}</b> att/game &nbsp; | &nbsp; '
        f'Recent 5: <b>{recent5_yards}</b> yds/game<br>'
        f'Home split: <b>{split_home}</b> yds/game ({int(qb_profile.get("home_games") or 0)} games) • '
        f'Away split: <b>{split_away}</b> yds/game ({int(qb_profile.get("away_games") or 0)} games)'
        '</div></section>'
    )


def _recent_table(qb_profile: dict) -> pd.DataFrame:
    rows = []
    for row in (qb_profile.get("recent_games") or [])[:5]:
        rows.append({
            "Date": _safe(row.get("date"), "—"),
            "Site": _safe(row.get("home_away"), "—").title(),
            "Opp": _safe(row.get("opponent"), "—"),
            "Cmp": _count(row.get("completions")),
            "Att": _count(row.get("attempts")),
            "Pass Yds": _count(row.get("passing_yards")),
            "TD": _count(row.get("passing_tds")),
            "INT": _count(row.get("interceptions")),
        })
    return pd.DataFrame(rows)


def render_nfl_passing_yards_hub() -> None:
    st.markdown(foundation._CSS, unsafe_allow_html=True)
    st.markdown(step1_ui._STEP1_CSS, unsafe_allow_html=True)
    st.markdown(_STEP2_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="kpy-head">'
        '<div><div class="kpy-title">🏈 NFL <span>Passing Yards</span></div>'
        '<div class="kpy-sub">Steps 1–2 • verified QB identity + descriptive ESPN passing profile • projection engine still OFF</div></div>'
        '<div class="kpy-chips"><span class="kpy-chip">STEP 2</span><span class="kpy-chip">QB PROFILE</span><span class="kpy-chip">MODEL OFF</span></div>'
        '</div>', unsafe_allow_html=True)

    key = "nfl_passing_yards_v3_date"
    if key not in st.session_state:
        st.session_state[key] = datetime.now(nfl.ET).date()
    day = st.date_input("NFL Passing Yards slate date", value=st.session_state[key], key="nfl_passing_yards_v3_date_input", label_visibility="collapsed")
    st.session_state[key] = day
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")

    with st.spinner("Verifying NFL slate…"):
        games, diag = nfl.load_nfl_slate(day_str)
    live = int((games.get("state", pd.Series(dtype=str)).astype(str) == "in").sum()) if not games.empty else 0
    final = int((games.get("state", pd.Series(dtype=str)).astype(str) == "post").sum()) if not games.empty else 0
    upcoming = int((games.get("state", pd.Series(dtype=str)).astype(str) == "pre").sum()) if not games.empty else 0
    st.markdown(
        '<div class="kpy-strip">'
        f'<div class="kpy-stat"><b>{len(games)}</b><span>Games</span></div><div class="kpy-stat"><b>{upcoming}</b><span>Upcoming</span></div>'
        f'<div class="kpy-stat"><b>{live}</b><span>Live</span></div><div class="kpy-stat"><b>{final}</b><span>Final</span></div>'
        f'<div class="kpy-stat"><b>{escape(day_str)}</b><span>ET Slate</span></div></div>', unsafe_allow_html=True)

    if not diag.get("request_ok"):
        st.error("NFL schedule verification failed. No matchup, QB identity, or passing profile is synthesized.")
        return
    if games.empty:
        st.info("No verified NFL games were returned for this ET date.")
        return

    labels, index_by_label = [], {}
    for idx, row in games.iterrows():
        label = f"{_safe(row.get('away_team'),'Away')} @ {_safe(row.get('home_team'),'Home')} • {_safe(row.get('tip_et'),'TBD')}"
        labels.append(label); index_by_label[label] = idx
    chosen = st.selectbox("Verified matchup", labels, key="nfl_passing_yards_v3_matchup")
    game = games.loc[index_by_label[chosen]].to_dict()

    st.markdown(
        '<div class="kpy-step"><div class="kpy-step-title">✅ Step 1 — Verified Matchup + Quarterback Identity</div>'
        f'<div class="kpy-step-sub">ESPN event {escape(_safe(game.get("game_id"),"—"))} • {escape(_safe(game.get("tip_et"),"TBD"))} • '
        f'{escape(_safe(game.get("venue"),"Venue TBD"))} • {escape(_safe(game.get("broadcast"),"—"))}</div></div>', unsafe_allow_html=True)

    with st.spinner("Resolving verified QB depth identity…"):
        resolved = identity.resolve_matchup_identity(game, int(pd.to_datetime(day).year))
    preseason = _safe(game.get("season_type")).lower() == "preseason"
    away, home = resolved.get("away") or {}, resolved.get("home") or {}
    st.markdown(f'<div class="kpy-qbgrid">{step1_ui._qb_card(away, preseason)}{step1_ui._qb_card(home, preseason)}</div>', unsafe_allow_html=True)
    if resolved.get("ready"):
        st.success("✅ STEP 1 IDENTITY GREEN • official matchup ID and both ESPN depth-chart QB1 identities are verified.")
    else:
        st.warning("⚠️ STEP 1 IDENTITY CHECK • " + _safe(resolved.get("reason"), "QB identity unresolved."))

    st.markdown('<div class="kpy-step"><div class="kpy-step-title">📊 Step 2 — Quarterback Passing Profile</div><div class="kpy-step-sub">Season production + recent game logs • descriptive evidence only • no opponent adjustment or projection yet</div></div>', unsafe_allow_html=True)

    season_code = _season_type_code(game.get("season_type"))
    year = int(pd.to_datetime(day).year)
    profiles = []
    for ctx in (away, home):
        qb = ctx.get("qb1") or {}
        if ctx.get("identity_verified"):
            with st.spinner(f"Loading {_safe(qb.get('name'),'QB')} passing profile…"):
                p = profile.build_qb_profile(_safe(qb.get("athlete_id")), _safe(qb.get("name")), year, season_code)
        else:
            p = {"ready": False, "reason": "Step 1 verified QB1 identity required", "athlete_id": "", "qb_name": "Unresolved QB1", "season": {}, "recent_games": []}
        profiles.append(p)

    st.markdown(f'<div class="kpy-pgrid">{_profile_card(away, profiles[0])}{_profile_card(home, profiles[1])}</div>', unsafe_allow_html=True)
    if all(p.get("ready") for p in profiles):
        st.success("✅ STEP 2 PROFILE GREEN • both verified QB1 season passing baselines are available.")
    else:
        reasons = [p.get("reason") for p in profiles if not p.get("ready") and p.get("reason")]
        st.warning("⚠️ STEP 2 PROFILE CHECK • " + " • ".join(reasons or ["one or both passing profiles are incomplete"]))

    cols = st.columns(2)
    for col, ctx, p in zip(cols, (away, home), profiles):
        with col:
            qb = ctx.get("qb1") or {}
            with st.expander(f"Recent passing — {_safe(qb.get('name'),'QB')}", expanded=False):
                table = _recent_table(p)
                if table.empty:
                    st.info("No verified ESPN game-log passing rows were returned yet.")
                else:
                    st.dataframe(table, hide_index=True, use_container_width=True)
                st.caption(f"Season stats HTTP: {p.get('season_http') or '—'} • game log HTTP: {p.get('gamelog_http') or '—'}")

    if preseason:
        st.warning("Preseason guardrail remains active: depth QB1 + preseason statistics do not prove expected drives, quarters, attempts, or full-game participation.")
    st.caption(f"{MODEL_VERSION} • sportsbook influence 0.0% • descriptive stats only • projection/Monte Carlo/probability/ranking/recommendation OFF.")


__all__ = ["MODEL_VERSION", "render_nfl_passing_yards_hub"]
