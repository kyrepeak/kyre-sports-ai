"""NFL Passing Yards V7 — Step 6 game environment.

Preserves Steps 1–5 and adds descriptive pace/play-volume, pass tendency,
venue/weather, rest/turnaround and site/travel context from verified ESPN event
and team identities. Step 6 has 0.0 projection influence; projection math stays OFF.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
import math

import pandas as pd
import streamlit as st

import nfl_hub_v24 as nfl
import nfl_passing_yards_hub_v1 as foundation
import nfl_passing_yards_hub_v2 as step1_ui
import nfl_passing_yards_hub_v3 as step2_ui
import nfl_passing_yards_hub_v4 as step3_ui
import nfl_passing_yards_hub_v5 as step4_ui
import nfl_passing_yards_identity_v1 as identity
import nfl_passing_yards_profile_v1 as profile
import nfl_passing_yards_defense_v1 as defense
import nfl_passing_yards_pressure_v1 as pressure
import nfl_passing_yards_personnel_v1 as personnel
import nfl_passing_yards_environment_v1 as environment

MODEL_VERSION = "NFL PASSING YARDS V7 • STEP 6 GAME ENVIRONMENT"

_STEP5_CSS = r"""
<style>
.kpy-igrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:8px 0 10px}
.kpy-personnel{border:1px solid #3c526d;background:#091522;border-radius:13px;padding:10px}
.kpy-ihead{display:flex;justify-content:space-between;align-items:flex-start;gap:8px;margin-bottom:7px}
.kpy-iname{color:#f8fafc;font-size:.92rem;font-weight:950}.kpy-isub{color:#7990a4;font-size:.52rem;margin-top:2px}
.kpy-ilabel{font-size:.55rem;font-weight:950;border-radius:999px;padding:4px 7px;border:1px solid #486078;white-space:nowrap}
.kpy-ilabel.help{color:#73efb8;border-color:#2f765a;background:#0b2a20}.kpy-ilabel.hurt{color:#ff9d94;border-color:#8a4b49;background:#321716}.kpy-ilabel.mixed,.kpy-ilabel.watch{color:#f1ca72;border-color:#7a6a38;background:#2a2412}.kpy-ilabel.neutral{color:#9ed3ff;border-color:#416d8d;background:#0b2234}.kpy-ilabel.check{color:#9eb2c3}
.kpy-imetrics{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:5px}.kpy-imetric{border:1px solid #203c53;background:#07121d;border-radius:9px;padding:7px 6px;min-width:0}
.kpy-imetric b{display:block;color:#f6fbff;font-size:.76rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kpy-imetric span{display:block;color:#70879a;font-size:.42rem;text-transform:uppercase;margin-top:2px}
.kpy-inote{margin-top:7px;padding-top:7px;border-top:1px solid #1b3449;color:#8299ad;font-size:.5rem;line-height:1.55}
@media(max-width:820px){.kpy-igrid{grid-template-columns:1fr}.kpy-imetrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""

_STEP6_CSS = r"""
<style>
.kpy-env{border:1px solid #3a5368;background:#08131f;border-radius:14px;padding:11px;margin:8px 0 10px}
.kpy-envtop{display:flex;justify-content:space-between;gap:10px;align-items:flex-start;margin-bottom:9px}
.kpy-envtitle{font-size:.95rem;font-weight:950;color:#f7fbff}.kpy-envsub{font-size:.52rem;color:#7d93a6;margin-top:3px;line-height:1.45}
.kpy-envlabel{font-size:.55rem;font-weight:950;border-radius:999px;padding:5px 8px;border:1px solid #49657c;color:#c8d7e4;white-space:nowrap}
.kpy-envlabel.controlled{color:#77efbd;border-color:#2f765a;background:#0b2a20}.kpy-envlabel.watch{color:#f3c76e;border-color:#776134;background:#2b2310}.kpy-envlabel.neutral,.kpy-envlabel.normal{color:#9ed3ff;border-color:#416d8d;background:#0b2234}
.kpy-envmetrics{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:5px}.kpy-envmetric{border:1px solid #1e3a50;background:#06111b;border-radius:9px;padding:7px 6px;min-width:0}
.kpy-envmetric b{display:block;font-size:.72rem;color:#f3f8fb;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kpy-envmetric span{display:block;font-size:.41rem;color:#6f8799;text-transform:uppercase;margin-top:2px}
.kpy-envteams{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;margin-top:8px}.kpy-envteam{border:1px solid #213f56;background:#07131e;border-radius:10px;padding:8px}.kpy-envteam h4{margin:0 0 6px;color:#f8fafc;font-size:.78rem}.kpy-envrow{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px}.kpy-envcell{font-size:.5rem;color:#8098aa}.kpy-envcell b{display:block;color:#f3f8fb;font-size:.7rem;margin-bottom:1px}
@media(max-width:820px){.kpy-envmetrics{grid-template-columns:repeat(2,minmax(0,1fr))}.kpy-envteams{grid-template-columns:1fr}}
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


def _personnel_card(p: dict) -> str:
    label = _safe(p.get("personnel_label"), "CHECK").upper()
    css = label.lower() if label.lower() in {"help", "hurt", "mixed", "watch", "neutral"} else "check"
    return (
        '<section class="kpy-personnel">'
        '<div class="kpy-ihead">'
        f'<div><div class="kpy-iname">{escape(_safe(p.get("qb_name"),"Unresolved QB1"))} • Weapons + Availability</div>'
        f'<div class="kpy-isub">{escape(_safe(p.get("offense_team_name"),"Offense"))} offense vs {escape(_safe(p.get("defense_team_name"),"Defense"))} secondary • {escape(_safe(p.get("personnel_basis"),"evidence incomplete"))}</div></div>'
        f'<div class="kpy-ilabel {css}">{escape(label)}</div></div>'
        '<div class="kpy-imetrics">'
        f'<div class="kpy-imetric"><b>{escape(_safe(p.get("qb_status"),"—"))}</b><span>QB Status</span></div>'
        f'<div class="kpy-imetric"><b>{int(p.get("skill_hard_count") or 0)}</b><span>Skill Hard</span></div>'
        f'<div class="kpy-imetric"><b>{_fmt(p.get("hard_target_share"),1,"%")}</b><span>Hard Target Share</span></div>'
        f'<div class="kpy-imetric"><b>{int(p.get("ol_hard_count") or 0)}</b><span>OL Hard</span></div>'
        f'<div class="kpy-imetric"><b>{int(p.get("secondary_hard_count") or 0)}</b><span>Opp Secondary Hard</span></div>'
        '</div>'
        '<div class="kpy-inote">'
        f'Watch-list skill players: <b>{int(p.get("skill_watch_count") or 0)}</b> • '
        f'watch target share: <b>{_fmt(p.get("watch_target_share"),1,"%")}</b><br>'
        f'Target-share state: {escape(_safe(p.get("target_share_state"),"UNAVAILABLE"))}'
        '</div></section>'
    )


def _personnel_table(p: dict) -> pd.DataFrame:
    rows = []
    for group, items in (
        ("Pass catcher", p.get("skill_injuries") or []),
        ("Offensive line", p.get("ol_injuries") or []),
        ("Opponent secondary", p.get("secondary_injuries") or []),
    ):
        for item in items:
            rank = item.get("depth_rank")
            rows.append({
                "Group": group,
                "Player": _safe(item.get("name"), "Unknown"),
                "Pos": _safe(item.get("position"), "—"),
                "Status": _safe(item.get("status"), "Unspecified"),
                "Depth": f"#{rank}" if isinstance(rank, int) and rank < 99 else "—",
                "Targets": int(round(float(item.get("targets")))) if _finite(item.get("targets")) else "—",
                "Target Share": _fmt(item.get("target_share"), 1, "%"),
                "Detail": _safe(item.get("detail")),
            })
    return pd.DataFrame(rows)


def _team_environment(name: str, pace: dict, rest: dict, site: str, tendency: str) -> str:
    return (
        '<div class="kpy-envteam">'
        f'<h4>{escape(_safe(name,"Team"))} • {escape(_safe(tendency,"CHECK"))}</h4>'
        '<div class="kpy-envrow">'
        f'<div class="kpy-envcell"><b>{_fmt(pace.get("offensive_plays_per_game"),1)}</b>Plays / game</div>'
        f'<div class="kpy-envcell"><b>{_fmt(pace.get("pass_attempts_per_game"),1)}</b>Pass att / game</div>'
        f'<div class="kpy-envcell"><b>{_fmt(pace.get("pass_rate"),1,"%")}</b>Pass rate</div>'
        f'<div class="kpy-envcell"><b>{escape(_safe(rest.get("turnaround_days"),"—"))}</b>Turnaround days</div>'
        f'<div class="kpy-envcell"><b>{escape(_safe(rest.get("rest_label"),"CHECK"))}</b>Rest state</div>'
        f'<div class="kpy-envcell"><b>{escape(_safe(site,"CHECK"))}</b>Site / travel</div>'
        '</div></div>'
    )


def _environment_card(ctx: dict) -> str:
    event = ctx.get("event") or {}
    label = _safe(ctx.get("environment_label"), "CHECK").upper()
    css = label.lower() if label.lower() in {"controlled", "watch", "neutral", "normal"} else "check"
    return (
        '<section class="kpy-env">'
        '<div class="kpy-envtop">'
        f'<div><div class="kpy-envtitle">Game Environment • {escape(_safe(ctx.get("pace_label"),"CHECK"))} pace context</div>'
        f'<div class="kpy-envsub">{escape(_safe(event.get("venue"),"Venue unavailable"))} • {escape(_safe(event.get("location"),"Location unavailable"))} • {escape(_safe(ctx.get("environment_basis"),"evidence incomplete"))}</div></div>'
        f'<div class="kpy-envlabel {css}">{escape(label)}</div></div>'
        '<div class="kpy-envmetrics">'
        f'<div class="kpy-envmetric"><b>{escape(_safe(event.get("venue_type"),"CHECK"))}</b><span>Venue Type</span></div>'
        f'<div class="kpy-envmetric"><b>{escape(_safe(event.get("surface"),"—"))}</b><span>Surface</span></div>'
        f'<div class="kpy-envmetric"><b>{escape(_safe(ctx.get("weather_label"),"CHECK"))}</b><span>Weather</span></div>'
        f'<div class="kpy-envmetric"><b>{_fmt(event.get("temperature_f"),0,"°F")}</b><span>Temperature</span></div>'
        f'<div class="kpy-envmetric"><b>{_fmt(event.get("wind_mph"),0," mph")}</b><span>Wind</span></div>'
        f'<div class="kpy-envmetric"><b>{escape(_safe(ctx.get("pace_label"),"CHECK"))}</b><span>Play Volume</span></div>'
        '</div>'
        '<div class="kpy-envteams">'
        f'{_team_environment(ctx.get("away_team_name"), ctx.get("away_pace") or {}, ctx.get("away_rest") or {}, ctx.get("away_site"), ctx.get("away_pass_tendency"))}'
        f'{_team_environment(ctx.get("home_team_name"), ctx.get("home_pace") or {}, ctx.get("home_rest") or {}, ctx.get("home_site"), ctx.get("home_pass_tendency"))}'
        '</div></section>'
    )


def render_nfl_passing_yards_hub() -> None:
    st.markdown(foundation._CSS, unsafe_allow_html=True)
    st.markdown(step1_ui._STEP1_CSS, unsafe_allow_html=True)
    st.markdown(step2_ui._STEP2_CSS, unsafe_allow_html=True)
    st.markdown(step3_ui._STEP3_CSS, unsafe_allow_html=True)
    st.markdown(step4_ui._STEP4_CSS, unsafe_allow_html=True)
    st.markdown(_STEP5_CSS, unsafe_allow_html=True)
    st.markdown(_STEP6_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="kpy-head"><div><div class="kpy-title">🏈 NFL <span>Passing Yards</span></div>'
        '<div class="kpy-sub">Steps 1–6 • identity + profile + pass defense + pressure + personnel + game environment • projection engine still OFF</div></div>'
        '<div class="kpy-chips"><span class="kpy-chip">STEP 6</span><span class="kpy-chip">ENVIRONMENT</span><span class="kpy-chip">MODEL OFF</span></div></div>',
        unsafe_allow_html=True,
    )

    key = "nfl_passing_yards_v7_date"
    if key not in st.session_state:
        st.session_state[key] = datetime.now(nfl.ET).date()
    day = st.date_input("NFL Passing Yards slate date", value=st.session_state[key], key="nfl_passing_yards_v7_date_input", label_visibility="collapsed")
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
    chosen = st.selectbox("Verified matchup", labels, key="nfl_passing_yards_v7_matchup")
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

    st.markdown('<div class="kpy-step"><div class="kpy-step-title">📊 Step 2 — Quarterback Passing Profile</div><div class="kpy-step-sub">Season production + recent game logs • descriptive evidence only</div></div>', unsafe_allow_html=True)
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

    st.markdown('<div class="kpy-step"><div class="kpy-step-title">🧱⚡ Step 4 — Pass Protection vs Defensive Pressure</div><div class="kpy-step-sub">Sacks allowed + offensive sack rate vs opponent sacks + defensive sack rate • 0.0 projection influence</div></div>', unsafe_allow_html=True)
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

    st.markdown('<div class="kpy-step"><div class="kpy-step-title">🩻🎯 Step 5 — Weapons + Injuries</div><div class="kpy-step-sub">QB health • WR/TE/RB availability • offensive-line injuries • opponent secondary injuries • exact-ID target-share loss when ESPN explicitly exposes targets • 0.0 projection influence</div></div>', unsafe_allow_html=True)
    personnel_profiles = []
    for offense_ctx, defense_ctx, pressure_ctx in ((away, home, pressure_profiles[0]), (home, away, pressure_profiles[1])):
        team_attempts = (pressure_ctx.get("offense") or {}).get("passing_attempts")
        with st.spinner(f"Loading {_safe(offense_ctx.get('team'),'offense')} personnel vs {_safe(defense_ctx.get('team'),'defense')} secondary…"):
            p = personnel.build_personnel_matchup(offense_ctx, defense_ctx, year, season_code, team_attempts)
        personnel_profiles.append(p)
    st.markdown(f'<div class="kpy-igrid">{_personnel_card(personnel_profiles[0])}{_personnel_card(personnel_profiles[1])}</div>', unsafe_allow_html=True)
    if all(p.get("ready") for p in personnel_profiles):
        st.success("✅ STEP 5 PERSONNEL GREEN • current ESPN injury feed is verified for both teams; exact athlete IDs are used for target usage when available.")
    else:
        reasons = [p.get("reason") for p in personnel_profiles if not p.get("ready") and p.get("reason")]
        st.warning("⚠️ STEP 5 PERSONNEL CHECK • " + " • ".join(reasons or ["personnel evidence incomplete"]))

    cols = st.columns(2)
    for col, p in zip(cols, personnel_profiles):
        with col:
            with st.expander(f"Personnel details — {_safe(p.get('offense_team_name'),'Team')}", expanded=False):
                table = _personnel_table(p)
                if table.empty:
                    st.success("No listed skill/OL/opponent-secondary injuries were returned in the verified current ESPN injury snapshot.")
                else:
                    st.dataframe(table, hide_index=True, use_container_width=True)
                st.caption(f"Offense depth HTTP: {p.get('offense_depth_http') or '—'} • opponent depth HTTP: {p.get('defense_depth_http') or '—'}")

    with st.expander("Step 5 methodology + source guardrails", expanded=False):
        st.write("Player-to-depth and player-to-target usage links use exact ESPN athlete IDs. No fuzzy name matching is used for Step 5 impact evidence.")
        st.write("Target share is calculated only from an explicit ESPN targets stat divided by verified team pass attempts. If ESPN does not expose targets, target share stays unavailable instead of being estimated from receptions.")
        st.write("HELP/HURT/MIXED/WATCH/NEUTRAL is descriptive personnel context only: own-offense absences can hurt the passing environment, while multiple verified starter-level opponent secondary absences can help it.")
        st.caption("Step 5 uses the current ESPN injury snapshot and is not a historical injury-report backfill. projection_adjustment = 0.0.")

    st.markdown('<div class="kpy-step"><div class="kpy-step-title">🌤️🏟️ Step 6 — Game Environment</div><div class="kpy-step-sub">Season play volume + pass tendency • indoor/outdoor • weather • rest/turnaround • home/away/neutral travel context • 0.0 projection influence</div></div>', unsafe_allow_html=True)
    with st.spinner("Loading verified game-environment context…"):
        env = environment.build_game_environment(game, away, home, year, season_code, day_str)
    st.markdown(_environment_card(env), unsafe_allow_html=True)
    if env.get("ready"):
        st.success("✅ STEP 6 ENVIRONMENT GREEN • verified ESPN event/team identities power pace, venue/weather, rest and site context without sportsbook input.")
    else:
        st.warning("⚠️ STEP 6 ENVIRONMENT CHECK • " + _safe(env.get("reason"), "environment evidence incomplete"))

    with st.expander("Step 6 methodology + source guardrails", expanded=False):
        st.write("Play volume and pass tendency use explicit ESPN season team statistics. Official offensive plays are never reconstructed from other stats when ESPN does not expose the play field.")
        st.write("Venue, indoor/outdoor, surface, neutral-site and weather fields come from the verified ESPN event summary. Missing weather stays CHECK instead of being guessed from city or stadium history.")
        st.write("Rest is calendar-day turnaround from the most recent completed ESPN schedule event. Travel context is limited to verified home/away/neutral designation; Step 6 does not fabricate mileage or time-zone effects.")
        st.write("Pace and pass-tendency labels are transparent descriptive thresholds only. They do not alter a passing-yards number in Step 6.")
        st.caption("projection_adjustment = 0.0 • sportsbook_influence = 0.0")

    if preseason:
        st.warning("Preseason guardrail remains active: depth order, personnel, pace and environment do not prove expected drives, quarters, attempts or full-game participation.")
    st.caption(f"{MODEL_VERSION} • sportsbook influence 0.0% • Steps 4–6 projection influence 0.0% • descriptive evidence only • projection/Monte Carlo/probability/fair-line/EV/ranking/recommendation OFF.")


__all__ = ["MODEL_VERSION", "render_nfl_passing_yards_hub"]
