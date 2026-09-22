"""NFL Passing Yards V8 — Step 7 transparent baseline projection.

Preserves certified Steps 1–6 and turns on only the first market-independent
passing-yards baseline. Sportsbook input, probability, Monte Carlo, fair-line,
EV, ranking and recommendation logic remain OFF.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
import math

import pandas as pd
import streamlit as st

import nfl_hub_v25 as nfl
import nfl_passing_yards_hub_v7 as prior
import nfl_passing_yards_projection_v1 as projection

foundation = prior.foundation
step1_ui = prior.step1_ui
step2_ui = prior.step2_ui
step3_ui = prior.step3_ui
step4_ui = prior.step4_ui
identity = prior.identity
profile = prior.profile
defense = prior.defense
pressure = prior.pressure
personnel = prior.personnel
environment = prior.environment

MODEL_VERSION = "NFL PASSING YARDS V8 • STEP 7 BASELINE PROJECTION"

_STEP7_CSS = r"""
<style>
.kpy-projgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:8px 0 10px}
.kpy-proj{border:1px solid #455f78;background:#07131f;border-radius:14px;padding:11px}
.kpy-projtop{display:flex;justify-content:space-between;gap:10px;align-items:flex-start;margin-bottom:9px}
.kpy-projname{font-size:.94rem;font-weight:950;color:#f8fbff}.kpy-projsub{font-size:.5rem;color:#7890a3;margin-top:3px;line-height:1.45}
.kpy-projgrade{font-size:.54rem;font-weight:950;border-radius:999px;padding:5px 8px;border:1px solid #4b6278;color:#a9bccb;white-space:nowrap}
.kpy-projgrade.green{color:#79efbc;border-color:#32775b;background:#0a2a20}.kpy-projgrade.watch{color:#f2ca74;border-color:#796538;background:#2a2412}.kpy-projgrade.check{color:#a6b6c3}
.kpy-projhero{display:grid;grid-template-columns:1.25fr repeat(2,minmax(0,1fr));gap:6px;margin-bottom:7px}.kpy-projhero>div{border:1px solid #213e54;background:#06111b;border-radius:10px;padding:8px}
.kpy-projhero b{display:block;font-size:1.16rem;color:#fff}.kpy-projhero span{display:block;font-size:.43rem;color:#70879a;text-transform:uppercase;margin-top:2px}
.kpy-projmeta{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px}.kpy-projmeta>div{border:1px solid #1d374b;background:#07121c;border-radius:9px;padding:7px 6px;font-size:.47rem;color:#7990a4}
.kpy-projmeta b{display:block;color:#eff6fb;font-size:.7rem;margin-bottom:2px}
.kpy-projctx{margin-top:7px;padding-top:7px;border-top:1px solid #1b3449;color:#7f97a9;font-size:.49rem;line-height:1.55}
@media(max-width:820px){.kpy-projgrid{grid-template-columns:1fr}.kpy-projhero{grid-template-columns:1fr 1fr}.kpy-projhero>div:first-child{grid-column:1/-1}}
</style>
"""


def _safe(value, default="") -> str:
    return prior._safe(value, default)


def _finite(value) -> bool:
    try:
        return math.isfinite(float(value))
    except Exception:
        return False


def _fmt(value, digits=1, suffix="") -> str:
    return prior._fmt(value, digits, suffix)


def _pct(value) -> str:
    if not _finite(value):
        return "—"
    return f"{float(value) * 100:.0f}%"


def _projection_card(p: dict) -> str:
    grade = _safe(p.get("coverage_grade"), "CHECK").upper()
    css = grade.lower() if grade.lower() in {"green", "watch"} else "check"
    state = "READY" if p.get("ready") else "WITHHELD"
    return (
        '<section class="kpy-proj">'
        '<div class="kpy-projtop">'
        f'<div><div class="kpy-projname">{escape(_safe(p.get("qb_name"),"Unresolved QB1"))} • Baseline Projection</div>'
        f'<div class="kpy-projsub">vs {escape(_safe(p.get("opponent_team_name"),"Opponent"))} • {escape(_safe(p.get("formula"),"volume × efficiency"))} • {state}</div></div>'
        f'<div class="kpy-projgrade {css}">{escape(grade)}</div></div>'
        '<div class="kpy-projhero">'
        f'<div><b>{_fmt(p.get("projection_yards"),1)}</b><span>Baseline Pass Yards</span></div>'
        f'<div><b>{_fmt(p.get("expected_attempts"),1)}</b><span>Expected Attempts</span></div>'
        f'<div><b>{_fmt(p.get("expected_ypa"),2)}</b><span>Expected YPA</span></div>'
        '</div>'
        '<div class="kpy-projmeta">'
        f'<div><b>{_pct(p.get("attempt_coverage"))}</b>Attempt-source coverage</div>'
        f'<div><b>{_pct(p.get("ypa_coverage"))}</b>Efficiency-source coverage</div>'
        f'<div><b>{escape(_safe(p.get("pressure_context"),"CHECK"))}</b>Pressure context • not numerically adjusted</div>'
        f'<div><b>{escape(_safe(p.get("personnel_context"),"CHECK"))}</b>Personnel context • not numerically adjusted</div>'
        '</div>'
        '<div class="kpy-projctx">'
        f'Environment: <b>{escape(_safe(p.get("environment_context"),"CHECK"))}</b> • weather: <b>{escape(_safe(p.get("weather_context"),"CHECK"))}</b><br>'
        f'{escape(_safe(p.get("coverage_basis"), p.get("reason") or "projection evidence incomplete"))}'
        '</div></section>'
    )


def _component_table(p: dict) -> pd.DataFrame:
    rows = []
    for group, items in (("Attempts", p.get("attempt_components") or []), ("YPA", p.get("ypa_components") or [])):
        for item in items:
            rows.append({
                "Group": group,
                "Input": _safe(item.get("key")),
                "Value": round(float(item.get("value")), 3) if _finite(item.get("value")) else "—",
                "Intended Weight": f"{float(item.get('intended_weight')) * 100:.0f}%" if _finite(item.get("intended_weight")) else "—",
                "Normalized Weight": f"{float(item.get('normalized_weight')) * 100:.1f}%" if _finite(item.get("normalized_weight")) else "—",
            })
    return pd.DataFrame(rows)


def render_nfl_passing_yards_hub() -> None:
    st.markdown(foundation._CSS, unsafe_allow_html=True)
    st.markdown(step1_ui._STEP1_CSS, unsafe_allow_html=True)
    st.markdown(step2_ui._STEP2_CSS, unsafe_allow_html=True)
    st.markdown(step3_ui._STEP3_CSS, unsafe_allow_html=True)
    st.markdown(step4_ui._STEP4_CSS, unsafe_allow_html=True)
    st.markdown(prior._STEP5_CSS, unsafe_allow_html=True)
    st.markdown(prior._STEP6_CSS, unsafe_allow_html=True)
    st.markdown(_STEP7_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="kpy-head"><div><div class="kpy-title">🏈 NFL <span>Passing Yards</span></div>'
        '<div class="kpy-sub">Steps 1–7 • verified evidence + transparent volume × efficiency baseline • market inputs still OFF</div></div>'
        '<div class="kpy-chips"><span class="kpy-chip">STEP 7</span><span class="kpy-chip">BASELINE PROJECTION</span><span class="kpy-chip">SPORTSBOOK 0%</span></div></div>',
        unsafe_allow_html=True,
    )

    key = "nfl_passing_yards_v8_date"
    if key not in st.session_state:
        st.session_state[key] = datetime.now(nfl.ET).date()
    day = st.date_input("NFL Passing Yards slate date", value=st.session_state[key], key="nfl_passing_yards_v8_date_input", label_visibility="collapsed")
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
        st.error("NFL schedule verification failed. No matchup or downstream passing-yards evidence is synthesized.")
        return
    if games.empty:
        st.info("No verified NFL games were returned for this ET date.")
        return

    labels, index_by_label = [], {}
    for idx, row in games.iterrows():
        label = f"{_safe(row.get('away_team'),'Away')} @ {_safe(row.get('home_team'),'Home')} • {_safe(row.get('tip_et'),'TBD')}"
        labels.append(label); index_by_label[label] = idx
    chosen = st.selectbox("Verified matchup", labels, key="nfl_passing_yards_v8_matchup")
    game = games.loc[index_by_label[chosen]].to_dict()
    year = int(pd.to_datetime(day).year)
    season_code = step2_ui._season_type_code(game.get("season_type"))

    st.markdown('<div class="kpy-step"><div class="kpy-step-title">✅ Step 1 — Verified Matchup + Quarterback Identity</div>'
                f'<div class="kpy-step-sub">ESPN event {escape(_safe(game.get("game_id"),"—"))} • {escape(_safe(game.get("tip_et"),"TBD"))} • {escape(_safe(game.get("venue"),"Venue TBD"))} • {escape(_safe(game.get("broadcast"),"—"))}</div></div>', unsafe_allow_html=True)
    with st.spinner("Resolving verified QB depth identity…"):
        resolved = identity.resolve_matchup_identity(game, year)
    preseason = _safe(game.get("season_type")).lower() == "preseason"
    away, home = resolved.get("away") or {}, resolved.get("home") or {}
    st.markdown(f'<div class="kpy-qbgrid">{step1_ui._qb_card(away, preseason)}{step1_ui._qb_card(home, preseason)}</div>', unsafe_allow_html=True)
    if resolved.get("ready"):
        st.success("✅ STEP 1 IDENTITY GREEN • official matchup ID and both ESPN depth-chart QB1 identities are verified.")
    else:
        st.warning("⚠️ STEP 1 IDENTITY CHECK • " + _safe(resolved.get("reason"), "QB identity unresolved."))

    st.markdown('<div class="kpy-step"><div class="kpy-step-title">📊 Step 2 — Quarterback Passing Profile</div><div class="kpy-step-sub">Season production + recent game logs • verified profile evidence</div></div>', unsafe_allow_html=True)
    profiles = []
    for ctx in (away, home):
        qb = ctx.get("qb1") or {}
        if ctx.get("identity_verified"):
            with st.spinner(f"Loading {_safe(qb.get('name'),'QB')} passing profile…"):
                p = profile.build_qb_profile(_safe(qb.get("athlete_id")), _safe(qb.get("name")), year, season_code)
        else:
            p = {"ready": False, "reason": "Step 1 verified QB1 identity required", "season": {}, "recent_games": []}
        profiles.append(p)
    st.markdown(f'<div class="kpy-pgrid">{step2_ui._profile_card(away, profiles[0])}{step2_ui._profile_card(home, profiles[1])}</div>', unsafe_allow_html=True)
    if all(p.get("ready") for p in profiles):
        st.success("✅ STEP 2 PROFILE GREEN • both verified QB1 season passing baselines are available.")
    else:
        st.warning("⚠️ STEP 2 PROFILE CHECK • one or both passing profiles are incomplete.")

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
        st.warning("⚠️ STEP 3 PASS DEFENSE CHECK • one or both opponent profiles are incomplete.")

    st.markdown('<div class="kpy-step"><div class="kpy-step-title">🧱⚡ Step 4 — Pass Protection vs Defensive Pressure</div><div class="kpy-step-sub">Sacks allowed + offensive sack rate vs opponent sacks + defensive sack rate • still context-only in Step 7</div></div>', unsafe_allow_html=True)
    pressure_profiles = []
    for offense_ctx, defense_ctx in ((away, home), (home, away)):
        with st.spinner(f"Loading {_safe(offense_ctx.get('team'),'offense')} protection vs {_safe(defense_ctx.get('team'),'defense')} pressure…"):
            p = pressure.build_pressure_matchup(_safe(offense_ctx.get("team_id")), _safe(offense_ctx.get("team"), offense_ctx.get("abbr")), _safe(defense_ctx.get("team_id")), _safe(defense_ctx.get("team"), defense_ctx.get("abbr")), year, season_code, day_str)
        pressure_profiles.append(p)
    st.markdown(f'<div class="kpy-xgrid">{step4_ui._pressure_card(away, away, home, pressure_profiles[0])}{step4_ui._pressure_card(home, home, away, pressure_profiles[1])}</div>', unsafe_allow_html=True)
    if all(p.get("ready") for p in pressure_profiles):
        st.success("✅ STEP 4 PRESSURE GREEN • both pressure profiles are verified from exact ESPN team identity.")
    else:
        st.warning("⚠️ STEP 4 PRESSURE CHECK • one or both pressure profiles are incomplete.")

    st.markdown('<div class="kpy-step"><div class="kpy-step-title">🩻🎯 Step 5 — Weapons + Injuries</div><div class="kpy-step-sub">QB health • WR/TE/RB availability • offensive-line injuries • opponent secondary injuries • still context-only in Step 7</div></div>', unsafe_allow_html=True)
    personnel_profiles = []
    for offense_ctx, defense_ctx, pressure_ctx in ((away, home, pressure_profiles[0]), (home, away, pressure_profiles[1])):
        team_attempts = (pressure_ctx.get("offense") or {}).get("passing_attempts")
        with st.spinner(f"Loading {_safe(offense_ctx.get('team'),'offense')} personnel vs {_safe(defense_ctx.get('team'),'defense')} secondary…"):
            p = personnel.build_personnel_matchup(offense_ctx, defense_ctx, year, season_code, team_attempts)
        personnel_profiles.append(p)
    st.markdown(f'<div class="kpy-igrid">{prior._personnel_card(personnel_profiles[0])}{prior._personnel_card(personnel_profiles[1])}</div>', unsafe_allow_html=True)
    if all(p.get("ready") for p in personnel_profiles):
        st.success("✅ STEP 5 PERSONNEL GREEN • current ESPN injury feed is verified for both teams; exact athlete IDs are used for target usage when available.")
    else:
        reasons = [p.get("reason") for p in personnel_profiles if not p.get("ready") and p.get("reason")]
        st.warning("⚠️ STEP 5 PERSONNEL CHECK • " + " • ".join(reasons or ["personnel evidence incomplete"]))

    cols = st.columns(2)
    for col, p in zip(cols, personnel_profiles):
        with col:
            with st.expander(f"Personnel details — {_safe(p.get('offense_team_name'),'Team')}", expanded=False):
                table = prior._personnel_table(p)
                if table.empty:
                    st.success("No listed skill/OL/opponent-secondary injuries were returned in the verified current ESPN injury snapshot.")
                else:
                    st.dataframe(table, hide_index=True, use_container_width=True)
                st.caption(f"Offense depth HTTP: {p.get('offense_depth_http') or '—'} • opponent depth HTTP: {p.get('defense_depth_http') or '—'}")

    st.markdown('<div class="kpy-step"><div class="kpy-step-title">🌤️🏟️ Step 6 — Game Environment</div><div class="kpy-step-sub">Team pass-attempt pace becomes one transparent Step 7 volume input • weather/rest/site labels remain descriptive</div></div>', unsafe_allow_html=True)
    with st.spinner("Loading verified game-environment context…"):
        env = environment.build_game_environment(game, away, home, year, season_code, day_str)
    st.markdown(prior._environment_card(env), unsafe_allow_html=True)
    if env.get("ready"):
        st.success("✅ STEP 6 ENVIRONMENT GREEN • verified ESPN event/team identities power pace, venue/weather, rest and site context without sportsbook input.")
    else:
        st.warning("⚠️ STEP 6 ENVIRONMENT CHECK • " + _safe(env.get("reason"), "environment evidence incomplete"))

    st.markdown('<div class="kpy-step"><div class="kpy-step-title">🧮📈 Step 7 — Transparent Baseline Projection</div><div class="kpy-step-sub">Expected attempts × expected yards/attempt • verified inputs only • sportsbook influence 0.0%</div></div>', unsafe_allow_html=True)
    projections = []
    for side, qb_ctx, qb_profile, defense_profile, pressure_ctx, personnel_ctx in (
        ("away", away, profiles[0], defense_profiles[0], pressure_profiles[0], personnel_profiles[0]),
        ("home", home, profiles[1], defense_profiles[1], pressure_profiles[1], personnel_profiles[1]),
    ):
        p = projection.build_baseline_projection(qb_ctx, qb_profile, defense_profile, pressure_ctx, personnel_ctx, env, side, preseason=preseason)
        projections.append(p)
    st.markdown(f'<div class="kpy-projgrid">{_projection_card(projections[0])}{_projection_card(projections[1])}</div>', unsafe_allow_html=True)
    if all(p.get("ready") for p in projections):
        st.success("✅ STEP 7 BASELINE PROJECTION GREEN • both verified QB1s have a market-independent volume × efficiency baseline.")
    else:
        reasons = [p.get("reason") for p in projections if not p.get("ready") and p.get("reason")]
        st.warning("⚠️ STEP 7 BASELINE PROJECTION CHECK • " + " • ".join(reasons or ["projection evidence incomplete"]))

    cols = st.columns(2)
    for col, p in zip(cols, projections):
        with col:
            with st.expander(f"Step 7 formula inputs — {_safe(p.get('qb_name'),'QB')}", expanded=False):
                table = _component_table(p)
                if table.empty:
                    st.info("No certified Step 7 projection components are available for this quarterback.")
                else:
                    st.dataframe(table, hide_index=True, use_container_width=True)
                st.caption("Attempt weights: QB season 45% • recent 3 20% • opponent attempts allowed 20% • team pass-attempt pace 15%.")
                st.caption("YPA weights: QB season 45% • recent 3 20% • opponent season allowed 25% • opponent recent 3 allowed 10%. Missing inputs are renormalized and coverage is shown explicitly.")

    with st.expander("Step 7 methodology + hard guardrails", expanded=False):
        st.write("Step 7 is intentionally a baseline, not the final betting model. It separates passing volume from passing efficiency and exposes every input weight used.")
        st.write("Pressure, personnel and weather/rest labels are carried forward for visibility but receive no arbitrary yardage bonus or penalty in Step 7. Their numerical treatment remains uncertified here.")
        st.write("The projection is withheld if verified QB/opponent identity is missing, if source coverage falls below 65% in either volume or efficiency, or if the selected game is preseason.")
        st.write("No sportsbook total, player prop, market consensus, price, implied probability or no-vig probability enters this baseline.")
        st.caption("sportsbook_influence = 0.0 • context_adjustment_yards = 0.0 • Monte Carlo = OFF")

    if preseason:
        st.warning("Preseason projection lock is active: Step 7 withholds the full-game baseline because depth-chart QB1 does not certify workload or participation.")
    st.caption(f"{MODEL_VERSION} • sportsbook influence 0.0% • transparent baseline model ON • pressure/personnel/weather label adjustment 0.0 • Monte Carlo/probability/fair-line/EV/ranking/recommendation OFF.")


__all__ = ["MODEL_VERSION", "render_nfl_passing_yards_hub"]
