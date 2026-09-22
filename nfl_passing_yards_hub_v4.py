"""NFL Passing Yards V4 — Step 3 opponent pass-defense matchup.

Preserves Steps 1–2 and adds descriptive opponent pass-defense evidence from
verified ESPN team identity. No passing-yards projection, sportsbook influence,
probability, Monte Carlo, ranking, EV, fair line, or recommendation is active.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
import math

import pandas as pd
import streamlit as st

import nfl_hub_v21 as nfl
import nfl_passing_yards_hub_v1 as foundation
import nfl_passing_yards_hub_v2 as step1_ui
import nfl_passing_yards_hub_v3 as step2_ui
import nfl_passing_yards_identity_v1 as identity
import nfl_passing_yards_profile_v1 as profile
import nfl_passing_yards_defense_v1 as defense

MODEL_VERSION = "NFL PASSING YARDS V4 • STEP 3 OPPONENT PASS DEFENSE"

_STEP3_CSS = r"""
<style>
.kpy-dgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:8px 0 10px}
.kpy-defense{border:1px solid #3d5068;background:#091522;border-radius:13px;padding:10px}
.kpy-dhead{display:flex;justify-content:space-between;align-items:flex-start;gap:8px;margin-bottom:7px}
.kpy-dname{color:#f8fafc;font-size:.92rem;font-weight:950}.kpy-dsub{color:#7990a4;font-size:.52rem;margin-top:2px}
.kpy-grade{font-size:.55rem;font-weight:950;border-radius:999px;padding:4px 7px;border:1px solid #486078;white-space:nowrap}
.kpy-grade.favorable{color:#73efb8;border-color:#2f765a;background:#0b2a20}.kpy-grade.tough{color:#ff9d94;border-color:#8a4b49;background:#321716}.kpy-grade.balanced{color:#f1ca72;border-color:#7a6a38;background:#2a2412}.kpy-grade.check{color:#9eb2c3}
.kpy-dmetrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px}.kpy-dmetric{border:1px solid #203c53;background:#07121d;border-radius:9px;padding:7px 6px;min-width:0}
.kpy-dmetric b{display:block;color:#f6fbff;font-size:.8rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kpy-dmetric span{display:block;color:#70879a;font-size:.44rem;text-transform:uppercase;margin-top:2px}
.kpy-drecent{margin-top:7px;padding-top:7px;border-top:1px solid #1b3449;color:#8299ad;font-size:.52rem;line-height:1.55}
@media(max-width:820px){.kpy-dgrid{grid-template-columns:1fr}.kpy-dmetrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
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


def _defense_card(qb_ctx: dict, opp_ctx: dict, d: dict) -> str:
    qb = qb_ctx.get("qb1") or {}
    qb_name = _safe(qb.get("name"), "Unresolved QB1")
    opp_name = _safe(opp_ctx.get("team"), opp_ctx.get("abbr"))
    season = d.get("season") or {}
    grade = _safe(d.get("matchup_grade"), "CHECK").upper()
    grade_class = grade.lower() if grade.lower() in {"favorable", "tough", "balanced"} else "check"
    rank = season.get("passing_yards_allowed_rank")
    rank_text = f"#{int(rank)}" if rank is not None else "—"
    return (
        '<section class="kpy-defense">'
        '<div class="kpy-dhead">'
        f'<div><div class="kpy-dname">{escape(qb_name)} vs {escape(opp_name)}</div>'
        f'<div class="kpy-dsub">Opponent pass defense • ESPN team {escape(_safe(d.get("team_id"),"—"))} • {escape(_safe(d.get("grade_basis"),"rank unavailable"))}</div></div>'
        f'<div class="kpy-grade {grade_class}">{escape(grade)}</div></div>'
        '<div class="kpy-dmetrics">'
        f'<div class="kpy-dmetric"><b>{_fmt(season.get("passing_yards_allowed_per_game"),1)}</b><span>Pass Yds Allowed/G</span></div>'
        f'<div class="kpy-dmetric"><b>{rank_text}</b><span>Pass Yds Rank</span></div>'
        f'<div class="kpy-dmetric"><b>{_fmt(season.get("passing_attempts_allowed_per_game"),1)}</b><span>Attempts Allowed/G</span></div>'
        f'<div class="kpy-dmetric"><b>{_fmt(season.get("completion_pct_allowed"),1,"%")}</b><span>Completion Allowed</span></div>'
        f'<div class="kpy-dmetric"><b>{_fmt(season.get("yards_per_attempt_allowed"),2)}</b><span>Yards/Att Allowed</span></div>'
        f'<div class="kpy-dmetric"><b>{_count(season.get("passing_tds_allowed"))}</b><span>Pass TD Allowed</span></div>'
        f'<div class="kpy-dmetric"><b>{_count(season.get("interceptions"))}</b><span>INT Made</span></div>'
        f'<div class="kpy-dmetric"><b>{_count(season.get("sacks"))}</b><span>Sacks</span></div>'
        '</div>'
        '<div class="kpy-drecent">'
        f'Recent 3: <b>{_fmt(d.get("recent3_yards_allowed"),1)}</b> pass yds allowed/game • '
        f'<b>{_fmt(d.get("recent3_completion_pct_allowed"),1,"%")}</b> completion • '
        f'<b>{_fmt(d.get("recent3_ypa_allowed"),2)}</b> Y/A<br>'
        f'Recent 5: <b>{_fmt(d.get("recent5_yards_allowed"),1)}</b> pass yds allowed/game • '
        f'verified recent games: <b>{int(d.get("recent_verified_games") or 0)}</b>'
        '</div></section>'
    )


def _recent_defense_table(d: dict) -> pd.DataFrame:
    rows = []
    for row in (d.get("recent_games") or [])[:5]:
        rows.append({
            "Date": _safe(row.get("date"), "—"),
            "Pass Yds Allowed": _count(row.get("passing_yards_allowed")),
            "Cmp% Allowed": _fmt(row.get("completion_pct_allowed"), 1, "%"),
            "Y/A Allowed": _fmt(row.get("yards_per_attempt_allowed"), 2),
        })
    return pd.DataFrame(rows)


def render_nfl_passing_yards_hub() -> None:
    st.markdown(foundation._CSS, unsafe_allow_html=True)
    st.markdown(step1_ui._STEP1_CSS, unsafe_allow_html=True)
    st.markdown(step2_ui._STEP2_CSS, unsafe_allow_html=True)
    st.markdown(_STEP3_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="kpy-head"><div><div class="kpy-title">🏈 NFL <span>Passing Yards</span></div>'
        '<div class="kpy-sub">Steps 1–3 • verified QB identity + passing profile + opponent pass defense • projection engine still OFF</div></div>'
        '<div class="kpy-chips"><span class="kpy-chip">STEP 3</span><span class="kpy-chip">PASS DEFENSE</span><span class="kpy-chip">MODEL OFF</span></div></div>',
        unsafe_allow_html=True,
    )

    key = "nfl_passing_yards_v4_date"
    if key not in st.session_state:
        st.session_state[key] = datetime.now(nfl.ET).date()
    day = st.date_input("NFL Passing Yards slate date", value=st.session_state[key], key="nfl_passing_yards_v4_date_input", label_visibility="collapsed")
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
        st.error("NFL schedule verification failed. No matchup, QB, passing profile, or defense data is synthesized.")
        return
    if games.empty:
        st.info("No verified NFL games were returned for this ET date.")
        return

    labels, index_by_label = [], {}
    for idx, row in games.iterrows():
        label = f"{_safe(row.get('away_team'),'Away')} @ {_safe(row.get('home_team'),'Home')} • {_safe(row.get('tip_et'),'TBD')}"
        labels.append(label); index_by_label[label] = idx
    chosen = st.selectbox("Verified matchup", labels, key="nfl_passing_yards_v4_matchup")
    game = games.loc[index_by_label[chosen]].to_dict()
    year = int(pd.to_datetime(day).year)
    season_code = step2_ui._season_type_code(game.get("season_type"))

    st.markdown(
        '<div class="kpy-step"><div class="kpy-step-title">✅ Step 1 — Verified Matchup + Quarterback Identity</div>'
        f'<div class="kpy-step-sub">ESPN event {escape(_safe(game.get("game_id"),"—"))} • {escape(_safe(game.get("tip_et"),"TBD"))} • '
        f'{escape(_safe(game.get("venue"),"Venue TBD"))} • {escape(_safe(game.get("broadcast"),"—"))}</div></div>', unsafe_allow_html=True)
    with st.spinner("Resolving verified QB depth identity…"):
        resolved = identity.resolve_matchup_identity(game, year)
    preseason = _safe(game.get("season_type")).lower() == "preseason"
    away, home = resolved.get("away") or {}, resolved.get("home") or {}
    st.markdown(f'<div class="kpy-qbgrid">{step1_ui._qb_card(away, preseason)}{step1_ui._qb_card(home, preseason)}</div>', unsafe_allow_html=True)
    if resolved.get("ready"):
        st.success("✅ STEP 1 IDENTITY GREEN • official matchup ID and both ESPN depth-chart QB1 identities are verified.")
    else:
        st.warning("⚠️ STEP 1 IDENTITY CHECK • " + _safe(resolved.get("reason"), "QB identity unresolved."))

    st.markdown('<div class="kpy-step"><div class="kpy-step-title">📊 Step 2 — Quarterback Passing Profile</div><div class="kpy-step-sub">Season production + recent game logs • descriptive evidence only</div></div>', unsafe_allow_html=True)
    profiles = []
    for ctx in (away, home):
        qb = ctx.get("qb1") or {}
        if ctx.get("identity_verified"):
            with st.spinner(f"Loading {_safe(qb.get('name'),'QB')} passing profile…"):
                p = profile.build_qb_profile(_safe(qb.get("athlete_id")), _safe(qb.get("name")), year, season_code)
        else:
            p = {"ready": False, "reason": "Step 1 verified QB1 identity required", "athlete_id": "", "qb_name": "Unresolved QB1", "season": {}, "recent_games": []}
        profiles.append(p)
    st.markdown(f'<div class="kpy-pgrid">{step2_ui._profile_card(away, profiles[0])}{step2_ui._profile_card(home, profiles[1])}</div>', unsafe_allow_html=True)
    if all(p.get("ready") for p in profiles):
        st.success("✅ STEP 2 PROFILE GREEN • both verified QB1 season passing baselines are available.")
    else:
        reasons = [p.get("reason") for p in profiles if not p.get("ready") and p.get("reason")]
        st.warning("⚠️ STEP 2 PROFILE CHECK • " + " • ".join(reasons or ["one or both passing profiles are incomplete"]))

    st.markdown('<div class="kpy-step"><div class="kpy-step-title">🛡️ Step 3 — Quarterback vs Opponent Pass Defense</div><div class="kpy-step-sub">Passing yards/attempts/completions allowed • efficiency allowed • TD/INT/sack context • recent verified box-score form • league-relative matchup label only when ESPN rank exists</div></div>', unsafe_allow_html=True)
    defense_profiles = []
    # Away QB faces home defense; home QB faces away defense. Verified Step 1 team IDs only.
    for opp in (home, away):
        with st.spinner(f"Loading {_safe(opp.get('team'),'opponent')} pass defense…"):
            d = defense.build_pass_defense_profile(
                _safe(opp.get("team_id")),
                _safe(opp.get("team"), opp.get("abbr")),
                year,
                season_code,
                day_str,
            )
        defense_profiles.append(d)
    st.markdown(f'<div class="kpy-dgrid">{_defense_card(away, home, defense_profiles[0])}{_defense_card(home, away, defense_profiles[1])}</div>', unsafe_allow_html=True)
    if all(d.get("ready") for d in defense_profiles):
        st.success("✅ STEP 3 PASS DEFENSE GREEN • both opponent season pass-defense profiles are verified from ESPN team identity.")
    else:
        reasons = [d.get("reason") for d in defense_profiles if not d.get("ready") and d.get("reason")]
        st.warning("⚠️ STEP 3 PASS DEFENSE CHECK • " + " • ".join(reasons or ["one or both opponent pass-defense profiles are incomplete"]))

    cols = st.columns(2)
    for col, opp, d in zip(cols, (home, away), defense_profiles):
        with col:
            with st.expander(f"Recent pass defense — {_safe(opp.get('team'),'Opponent')}", expanded=False):
                table = _recent_defense_table(d)
                if table.empty:
                    st.info("No verified pre-game ESPN box-score defense rows were returned yet.")
                else:
                    st.dataframe(table, hide_index=True, use_container_width=True)
                st.caption(f"Team stats HTTP: {d.get('stats_http') or '—'} • schedule HTTP: {d.get('schedule_http') or '—'}")

    if preseason:
        st.warning("Preseason guardrail remains active: depth QB1 and descriptive matchup data do not prove expected drives, quarters, attempts, or full-game participation.")
    st.caption(f"{MODEL_VERSION} • sportsbook influence 0.0% • descriptive matchup evidence only • projection/Monte Carlo/probability/fair-line/EV/ranking/recommendation OFF.")


__all__ = ["MODEL_VERSION", "render_nfl_passing_yards_hub"]
