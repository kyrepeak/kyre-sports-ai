"""NFL Passing Yards V5 — Step 4 pass protection + defensive pressure.

Preserves Steps 1–3 and adds descriptive sack/protection pressure evidence using
verified ESPN team IDs. Step 4 has 0.0 projection influence; projections, fair
lines, probabilities, EV, Monte Carlo, rankings, and recommendations remain OFF.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
import math

import pandas as pd
import streamlit as st

import nfl_hub_v22 as nfl
import nfl_passing_yards_hub_v1 as foundation
import nfl_passing_yards_hub_v2 as step1_ui
import nfl_passing_yards_hub_v3 as step2_ui
import nfl_passing_yards_hub_v4 as step3_ui
import nfl_passing_yards_identity_v1 as identity
import nfl_passing_yards_profile_v1 as profile
import nfl_passing_yards_defense_v1 as defense
import nfl_passing_yards_pressure_v1 as pressure

MODEL_VERSION = "NFL PASSING YARDS V5 • STEP 4 PROTECTION + PRESSURE"

_STEP4_CSS = r"""
<style>
.kpy-xgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:8px 0 10px}
.kpy-pressure{border:1px solid #3c526d;background:#091522;border-radius:13px;padding:10px}
.kpy-xhead{display:flex;justify-content:space-between;align-items:flex-start;gap:8px;margin-bottom:7px}
.kpy-xname{color:#f8fafc;font-size:.92rem;font-weight:950}.kpy-xsub{color:#7990a4;font-size:.52rem;margin-top:2px}
.kpy-xgrade{font-size:.55rem;font-weight:950;border-radius:999px;padding:4px 7px;border:1px solid #486078;white-space:nowrap}
.kpy-xgrade.high-pressure{color:#ff9d94;border-color:#8a4b49;background:#321716}.kpy-xgrade.low-pressure{color:#73efb8;border-color:#2f765a;background:#0b2a20}.kpy-xgrade.moderate{color:#f1ca72;border-color:#7a6a38;background:#2a2412}.kpy-xgrade.check{color:#9eb2c3}
.kpy-xmetrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px}.kpy-xmetric{border:1px solid #203c53;background:#07121d;border-radius:9px;padding:7px 6px;min-width:0}
.kpy-xmetric b{display:block;color:#f6fbff;font-size:.8rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kpy-xmetric span{display:block;color:#70879a;font-size:.44rem;text-transform:uppercase;margin-top:2px}
.kpy-xrecent{margin-top:7px;padding-top:7px;border-top:1px solid #1b3449;color:#8299ad;font-size:.52rem;line-height:1.55}
.kpy-blitz{margin-top:6px;color:#6f8497;font-size:.49rem}
@media(max-width:820px){.kpy-xgrid{grid-template-columns:1fr}.kpy-xmetrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
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


def _pressure_card(qb_ctx: dict, offense_ctx: dict, defense_ctx: dict, p: dict) -> str:
    qb = qb_ctx.get("qb1") or {}
    qb_name = _safe(qb.get("name"), "Unresolved QB1")
    offense_name = _safe(offense_ctx.get("team"), offense_ctx.get("abbr"))
    defense_name = _safe(defense_ctx.get("team"), defense_ctx.get("abbr"))
    offense = p.get("offense") or {}
    d = p.get("defense") or {}
    label = _safe(p.get("pressure_label"), "CHECK").upper()
    css = label.lower().replace(" ", "-") if label in {"HIGH PRESSURE", "LOW PRESSURE", "MODERATE"} else "check"
    return (
        '<section class="kpy-pressure">'
        '<div class="kpy-xhead">'
        f'<div><div class="kpy-xname">{escape(qb_name)} • Protection vs Pressure</div>'
        f'<div class="kpy-xsub">{escape(offense_name)} protection vs {escape(defense_name)} rush • {escape(_safe(p.get("pressure_basis"),"evidence incomplete"))}</div></div>'
        f'<div class="kpy-xgrade {css}">{escape(label)}</div></div>'
        '<div class="kpy-xmetrics">'
        f'<div class="kpy-xmetric"><b>{_fmt(offense.get("sacks_allowed_per_game"),2)}</b><span>Sacks Allowed/G</span></div>'
        f'<div class="kpy-xmetric"><b>{_fmt(offense.get("sack_rate_allowed"),1,"%")}</b><span>Offense Sack Rate</span></div>'
        f'<div class="kpy-xmetric"><b>{_count(offense.get("sacks_allowed"))}</b><span>Sacks Allowed</span></div>'
        f'<div class="kpy-xmetric"><b>{_count(offense.get("sack_yards_lost"))}</b><span>Sack Yds Lost</span></div>'
        f'<div class="kpy-xmetric"><b>{_fmt(d.get("sacks_per_game"),2)}</b><span>Defense Sacks/G</span></div>'
        f'<div class="kpy-xmetric"><b>{_fmt(d.get("sack_rate_generated"),1,"%")}</b><span>Defense Sack Rate</span></div>'
        f'<div class="kpy-xmetric"><b>{_count(d.get("sacks_made"))}</b><span>Defense Sacks</span></div>'
        f'<div class="kpy-xmetric"><b>{_count(d.get("opponent_pass_attempts"))}</b><span>Opp Pass Attempts</span></div>'
        '</div>'
        '<div class="kpy-xrecent">'
        f'Recent 3 protection: <b>{_fmt(p.get("recent3_sacks_allowed"),2)}</b> sacks allowed/game • '
        f'<b>{_fmt(p.get("recent3_sack_rate_allowed"),1,"%")}</b> sack rate<br>'
        f'Recent 3 rush: <b>{_fmt(p.get("recent3_sacks_made"),2)}</b> sacks/game • '
        f'<b>{_fmt(p.get("recent3_sack_rate_generated"),1,"%")}</b> sack rate'
        '</div>'
        f'<div class="kpy-blitz">Blitz context: {escape(_safe(p.get("blitz_state"),"UNAVAILABLE — not synthesized"))}</div>'
        '</section>'
    )


def render_nfl_passing_yards_hub() -> None:
    st.markdown(foundation._CSS, unsafe_allow_html=True)
    st.markdown(step1_ui._STEP1_CSS, unsafe_allow_html=True)
    st.markdown(step2_ui._STEP2_CSS, unsafe_allow_html=True)
    st.markdown(step3_ui._STEP3_CSS, unsafe_allow_html=True)
    st.markdown(_STEP4_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="kpy-head"><div><div class="kpy-title">🏈 NFL <span>Passing Yards</span></div>'
        '<div class="kpy-sub">Steps 1–4 • QB identity + passing profile + pass defense + protection/pressure • projection engine still OFF</div></div>'
        '<div class="kpy-chips"><span class="kpy-chip">STEP 4</span><span class="kpy-chip">PRESSURE</span><span class="kpy-chip">MODEL OFF</span></div></div>',
        unsafe_allow_html=True,
    )

    key = "nfl_passing_yards_v5_date"
    if key not in st.session_state:
        st.session_state[key] = datetime.now(nfl.ET).date()
    day = st.date_input("NFL Passing Yards slate date", value=st.session_state[key], key="nfl_passing_yards_v5_date_input", label_visibility="collapsed")
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
        st.error("NFL schedule verification failed. No matchup, QB, profile, defense, or pressure data is synthesized.")
        return
    if games.empty:
        st.info("No verified NFL games were returned for this ET date.")
        return

    labels, index_by_label = [], {}
    for idx, row in games.iterrows():
        label = f"{_safe(row.get('away_team'),'Away')} @ {_safe(row.get('home_team'),'Home')} • {_safe(row.get('tip_et'),'TBD')}"
        labels.append(label); index_by_label[label] = idx
    chosen = st.selectbox("Verified matchup", labels, key="nfl_passing_yards_v5_matchup")
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

    st.markdown('<div class="kpy-step"><div class="kpy-step-title">🛡️ Step 3 — Quarterback vs Opponent Pass Defense</div><div class="kpy-step-sub">Pass yards/attempts/completions allowed • efficiency allowed • TD/INT/sack context • recent form</div></div>', unsafe_allow_html=True)
    defense_profiles = []
    for opp in (home, away):
        with st.spinner(f"Loading {_safe(opp.get('team'),'opponent')} pass defense…"):
            d = defense.build_pass_defense_profile(_safe(opp.get("team_id")), _safe(opp.get("team"), opp.get("abbr")), year, season_code, day_str)
        defense_profiles.append(d)
    st.markdown(f'<div class="kpy-dgrid">{step3_ui._defense_card(away, home, defense_profiles[0])}{step3_ui._defense_card(home, away, defense_profiles[1])}</div>', unsafe_allow_html=True)
    if all(d.get("ready") for d in defense_profiles):
        st.success("✅ STEP 3 PASS DEFENSE GREEN • both opponent season pass-defense profiles are verified from ESPN team identity.")
    else:
        reasons = [d.get("reason") for d in defense_profiles if not d.get("ready") and d.get("reason")]
        st.warning("⚠️ STEP 3 PASS DEFENSE CHECK • " + " • ".join(reasons or ["one or both opponent pass-defense profiles are incomplete"]))

    st.markdown('<div class="kpy-step"><div class="kpy-step-title">🧱⚡ Step 4 — Pass Protection vs Defensive Pressure</div><div class="kpy-step-sub">Sacks allowed + offensive sack rate vs opponent sacks + defensive sack rate • recent verified box-score context • blitz rate fails closed when unavailable • 0.0 projection influence</div></div>', unsafe_allow_html=True)
    pressure_profiles = []
    for offense_ctx, defense_ctx in ((away, home), (home, away)):
        with st.spinner(f"Loading {_safe(offense_ctx.get('team'),'offense')} protection vs {_safe(defense_ctx.get('team'),'defense')} pressure…"):
            p = pressure.build_pressure_matchup(
                _safe(offense_ctx.get("team_id")),
                _safe(offense_ctx.get("team"), offense_ctx.get("abbr")),
                _safe(defense_ctx.get("team_id")),
                _safe(defense_ctx.get("team"), defense_ctx.get("abbr")),
                year,
                season_code,
                day_str,
            )
        pressure_profiles.append(p)
    st.markdown(
        f'<div class="kpy-xgrid">{_pressure_card(away, away, home, pressure_profiles[0])}{_pressure_card(home, home, away, pressure_profiles[1])}</div>',
        unsafe_allow_html=True,
    )
    if all(p.get("ready") for p in pressure_profiles):
        st.success("✅ STEP 4 PRESSURE GREEN • both pass-protection vs defensive-pressure profiles are verified from exact ESPN team identity.")
    else:
        reasons = [p.get("reason") for p in pressure_profiles if not p.get("ready") and p.get("reason")]
        st.warning("⚠️ STEP 4 PRESSURE CHECK • " + " • ".join(reasons or ["one or both pressure profiles are incomplete"]))

    with st.expander("Step 4 methodology + source guardrails", expanded=False):
        st.write("Offensive sack rate = sacks taken ÷ (pass attempts + sacks taken). Defensive sack rate uses sacks made over opponent pass attempts + sacks. Recent values come from completed ESPN game box scores before the selected slate date.")
        st.write("Blitz rate is not guessed. If the verified ESPN path does not expose a stable blitz-rate field, the page shows it as unavailable instead of substituting a synthetic number.")
        st.caption("Step 4 is descriptive evidence only. projection_adjustment = 0.0.")

    if preseason:
        st.warning("Preseason guardrail remains active: depth QB1 and descriptive pressure data do not prove expected drives, quarters, attempts, or full-game participation.")
    st.caption(f"{MODEL_VERSION} • sportsbook influence 0.0% • Step 4 projection influence 0.0% • descriptive evidence only • projection/Monte Carlo/probability/fair-line/EV/ranking/recommendation OFF.")


__all__ = ["MODEL_VERSION", "render_nfl_passing_yards_hub"]
