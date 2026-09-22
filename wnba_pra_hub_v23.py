"""WNBA PRA V2.3 — mobile slate command center on the WNBA-only V2.2 data guard.

Adds a readable official WNBA slate, game cards, P/R/A/PRA player snapshots,
Last-10/Last-5 context and a slate-wide baseline Top 5. The Top 5 is explicitly
foundation-only until injury, confirmed-lineup, usage and opponent-defense
layers are connected.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_pra_hub_v2 as hub
from wnba_data_v22 import (
    current_season,
    data_health,
    empirical_profile,
    game_for_team,
    logo_url,
    official_roster,
    player_form_table,
    player_game_log,
    schedule_for_date,
    slate_player_pool,
    team_player_pool,
)

MODEL_VERSION = "PRA V2.3"

# Wire the guarded WNBA-only data layer into the original PRA engine.
hub.current_season = current_season
hub.data_health = data_health
hub.empirical_profile = empirical_profile
hub.game_for_team = game_for_team
hub.logo_url = logo_url
hub.official_roster = official_roster
hub.player_form_table = player_form_table
hub.player_game_log = player_game_log
hub.schedule_for_date = schedule_for_date
hub.slate_player_pool = slate_player_pool
hub.team_player_pool = team_player_pool
hub.MODEL_VERSION = MODEL_VERSION

EXTRA_CSS = r"""
<style>
.w23-summary{border:1px solid #42517a;background:linear-gradient(145deg,#121c31,#0a1424);border-radius:20px;padding:15px 16px;margin:12px 0 18px}.w23-title{font-weight:1000;color:#fff;font-size:1.15rem}.w23-sub{color:#8fa1bd;font-size:.68rem;margin-top:4px;line-height:1.5}.w23-topgrid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;margin-top:12px}.w23-pick{border:1px solid #334466;background:#0a1626;border-radius:14px;padding:10px}.w23-pick.first{border-color:#ff70aa;box-shadow:inset 3px 0 0 #ff70aa}.w23-rank{font-size:.5rem;color:#68dcff;font-weight:950;letter-spacing:.08em}.w23-name{font-size:.74rem;color:#fff;font-weight:950;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.w23-meta{font-size:.53rem;color:#8698b5;margin-top:3px}.w23-pra{font-size:1.35rem;color:#7af0ba;font-weight:1000;margin-top:7px}.w23-pra span{font-size:.48rem;color:#7286a5;font-weight:900;text-transform:uppercase}.w23-split{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:4px;margin-top:7px}.w23-split div{border:1px solid #263852;border-radius:8px;padding:5px}.w23-split b{display:block;color:#fff;font-size:.66rem}.w23-split span{display:block;color:#6f85a6;font-size:.42rem;text-transform:uppercase}.w23-teamgrid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px}.w23-teamcard{border:1px solid #2d405f;background:#091523;border-radius:15px;padding:10px}.w23-teamhead{display:flex;justify-content:space-between;align-items:center;gap:8px;border-bottom:1px solid #20324a;padding-bottom:8px}.w23-teamhead b{color:#fff;font-size:.76rem}.w23-teamhead span{color:#6f88a6;font-size:.5rem;text-transform:uppercase}.w23-prow{display:grid;grid-template-columns:1.55fr .48fr .48fr .48fr .55fr .55fr .55fr;gap:4px;align-items:center;padding:6px 0;border-bottom:1px solid #17283d;font-size:.55rem}.w23-prow:last-child{border-bottom:0}.w23-prow b{color:#eff4fb;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.w23-prow span{color:#92a4bc;text-align:right}.w23-prow.head b,.w23-prow.head span{color:#617b9b;font-size:.43rem;text-transform:uppercase}.w23-context{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin-top:10px}.w23-context div{border:1px solid #263a58;background:#0a1625;border-radius:11px;padding:8px}.w23-context span{display:block;color:#7186a5;font-size:.45rem;text-transform:uppercase;font-weight:900}.w23-context b{display:block;color:#fff;font-size:.7rem;margin-top:3px}
@media(max-width:900px){.w23-topgrid{grid-template-columns:repeat(2,minmax(0,1fr))}.w23-teamgrid{grid-template-columns:1fr}.w23-context{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:520px){.w23-topgrid{grid-template-columns:1fr}.w23-prow{grid-template-columns:1.6fr .55fr .55fr .6fr}.w23-prow .hide-mobile{display:none}.w23-context{grid-template-columns:1fr 1fr}}
</style>
"""


def _e(v):
    return hub._e(v)


def _num(v, default=np.nan):
    try:
        x = float(v)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _stat(row, key, fallback=0.0):
    v = _num(row.get(key), np.nan)
    return float(fallback if pd.isna(v) else v)


def _weighted_stat(row, stat):
    season = _stat(row, stat, 0.0)
    l10 = _stat(row, f"L10_{stat}", season)
    l5 = _stat(row, f"L5_{stat}", l10)
    return .50 * season + .30 * l10 + .20 * l5


def _baseline_row(row):
    p = _weighted_stat(row, "PTS")
    r = _weighted_stat(row, "REB")
    a = _weighted_stat(row, "AST")
    return p, r, a, p + r + a


def _pra(row, prefix=""):
    return sum(_stat(row, f"{prefix}{x}", 0.0) for x in ("PTS", "REB", "AST"))


def _hero(day):
    st.markdown(
        '<div class="w2-hero">'
        '<div class="w2-kicker">KYRE SPORTS AI • WNBA PRA INTELLIGENCE</div>'
        '<div class="w2-title">🏀 WNBA PRA Command Center — V2.3</div>'
        '<div class="w2-sub">WNBA-only schedule and player data with game cards, season P/R/A, Last 10, Last 5 and a slate-wide PRA baseline scanner. Points, rebounds and assists stay separate before PRA is combined. Injury, confirmed-lineup, usage and opponent-defense adjustments remain clearly pending.</div>'
        '<div class="w2-pills">'
        f'<div class="w2-pill">📅 Slate <b>{_e(day)}</b></div>'
        '<div class="w2-pill">🧠 <b>PRA V2.3</b></div>'
        '<div class="w2-pill">🔒 <b>WNBA-only data</b></div>'
        '<div class="w2-pill">🎯 <b>P / R / A modeled separately</b></div>'
        '</div></div>', unsafe_allow_html=True,
    )


def _player_table(pool, limit=6):
    if pool is None or pool.empty:
        return '<div class="w2-empty">No official player-stat rows available for this team yet.</div>'
    f = pool.copy()
    if "MIN" in f.columns:
        f = f.sort_values("MIN", ascending=False)
    rows = ['<div class="w23-prow head"><b>Player</b><span>PTS</span><span>REB</span><span>AST</span><span class="hide-mobile">PRA</span><span class="hide-mobile">L10</span><span>L5</span></div>']
    for _, p in f.head(limit).iterrows():
        rows.append(
            '<div class="w23-prow">'
            f'<b>{_e(p.get("PLAYER_NAME", "Player"))}</b>'
            f'<span>{_stat(p,"PTS"):.1f}</span>'
            f'<span>{_stat(p,"REB"):.1f}</span>'
            f'<span>{_stat(p,"AST"):.1f}</span>'
            f'<span class="hide-mobile">{_pra(p):.1f}</span>'
            f'<span class="hide-mobile">{_pra(p,"L10_"):.1f}</span>'
            f'<span>{_pra(p,"L5_"):.1f}</span>'
            '</div>'
        )
    return ''.join(rows)


def _game_card(row, stats, roster_counts=None):
    away_id, home_id = int(row.away_team_id), int(row.home_team_id)
    away_pool = team_player_pool(stats, away_id)
    home_pool = team_player_pool(stats, home_id)
    away_count = roster_counts.get(away_id) if roster_counts else None
    home_count = roster_counts.get(home_id) if roster_counts else None
    status = row.get("status_text") or row.get("status") or "Scheduled"
    st.markdown(
        '<div class="w2-game">'
        f'<div class="w2-game-top"><span>{_e(row.get("status"))}</span><span>{_e(row.get("first_tip_et"))}</span></div>'
        '<div class="w2-match">'
        f'<div class="w2-team"><img src="{logo_url(away_id)}"><b>{_e(row.get("away_team"))}</b><span>{len(away_pool)} stat rows{" • roster "+str(away_count) if away_count is not None else ""}</span></div>'
        '<div class="w2-at">@</div>'
        f'<div class="w2-team"><img src="{logo_url(home_id)}"><b>{_e(row.get("home_team"))}</b><span>{len(home_pool)} stat rows{" • roster "+str(home_count) if home_count is not None else ""}</span></div>'
        '</div>'
        f'<div class="w2-venue">📍 {_e(row.get("venue"))} • {_e(status)}</div>'
        '<div class="w23-context">'
        f'<div><span>Tip</span><b>{_e(row.get("first_tip_et"))}</b></div>'
        f'<div><span>Status</span><b>{_e(status)}</b></div>'
        f'<div><span>Away pool</span><b>{len(away_pool)} players</b></div>'
        f'<div><span>Home pool</span><b>{len(home_pool)} players</b></div>'
        '</div>'
        '<div class="w23-teamgrid">'
        f'<div class="w23-teamcard"><div class="w23-teamhead"><b>{_e(row.get("away_team"))}</b><span>season / L10 / L5</span></div>{_player_table(away_pool)}</div>'
        f'<div class="w23-teamcard"><div class="w23-teamhead"><b>{_e(row.get("home_team"))}</b><span>season / L10 / L5</span></div>{_player_table(home_pool)}</div>'
        '</div>'
        '<div class="w2-note blue" style="margin-top:10px"><b>Matchup layer:</b> opponent, venue and slate status are verified here. Confirmed starters, injuries, role/usage changes, pace and opponent defensive splits are intentionally not applied yet.</div>'
        '</div>', unsafe_allow_html=True,
    )


def _top5_baseline(schedule, stats):
    pool = slate_player_pool(schedule, stats)
    if pool is None or pool.empty:
        return []
    pool = pool.copy()
    if "MIN" in pool.columns:
        pool = pool[pd.to_numeric(pool["MIN"], errors="coerce").fillna(0).ge(15)]
    rows = []
    for _, p in pool.iterrows():
        bp, br, ba, total = _baseline_row(p)
        team_id = int(_stat(p, "TEAM_ID", 0))
        matchup = game_for_team(schedule, team_id)
        rows.append({
            "name": str(p.get("PLAYER_NAME") or "Player"),
            "team": str(p.get("TEAM_ABBREVIATION") or p.get("TEAM_NAME") or ""),
            "opponent": (matchup or {}).get("opponent") or "—",
            "p": bp, "r": br, "a": ba, "pra": total,
            "l10": _pra(p, "L10_"), "l5": _pra(p, "L5_"),
            "min": _stat(p, "MIN", 0), "gp": _stat(p, "GP", 0),
        })
    return sorted(rows, key=lambda x: x["pra"], reverse=True)[:5]


def _render_top5(picks):
    if not picks:
        st.markdown('<div class="w2-empty">No eligible WNBA players were found for the selected slate.</div>', unsafe_allow_html=True)
        return
    cards = []
    for i, p in enumerate(picks, 1):
        first = " first" if i == 1 else ""
        cards.append(
            f'<div class="w23-pick{first}"><div class="w23-rank">#{i} BASELINE</div>'
            f'<div class="w23-name">{_e(p["name"])}</div><div class="w23-meta">{_e(p["team"])} vs {_e(p["opponent"])} • {p["min"]:.1f} MIN</div>'
            f'<div class="w23-pra">{p["pra"]:.1f} <span>Expected PRA</span></div>'
            '<div class="w23-split">'
            f'<div><span>PTS</span><b>{p["p"]:.1f}</b></div><div><span>REB</span><b>{p["r"]:.1f}</b></div><div><span>AST</span><b>{p["a"]:.1f}</b></div>'
            '</div><div class="w23-meta">L10 {0:.1f} • L5 {1:.1f}</div></div>'.format(p["l10"], p["l5"])
        )
    st.markdown(
        '<div class="w23-summary"><div class="w23-title">🏆 V2.3 Slate PRA Baseline — Top 5</div>'
        '<div class="w23-sub">Ranks expected PRA from separate weighted P/R/A baselines (50% season, 30% L10, 20% L5). This is not yet the final matchup-adjusted Over/Under model and does not use sportsbook prices.</div>'
        f'<div class="w23-topgrid">{"".join(cards)}</div></div>', unsafe_allow_html=True,
    )


def _slate_tab(day, schedule, stats):
    st.markdown('<div class="w2-note blue"><b>V2.3 foundation:</b> WNBA-only schedule + player production + recent form are live. The scanner below is a descriptive PRA baseline until injury, confirmed starter, usage/role, pace and opponent-defense layers are connected.</div>', unsafe_allow_html=True)
    pool = slate_player_pool(schedule, stats)
    teams = len(set(schedule.away_team_id.tolist() + schedule.home_team_id.tolist())) if schedule is not None and not schedule.empty else 0
    hub._metrics([
        ("Games", len(schedule), "cyan"),
        ("Teams", teams, "pink"),
        ("Slate player pool", len(pool), "good"),
        ("League guard", "WNBA ONLY", "warn"),
    ])
    if schedule is None or schedule.empty:
        st.markdown('<div class="w2-empty">No official WNBA games were returned for this date. No other league will be substituted. Try another WNBA slate date.</div>', unsafe_allow_html=True)
        return

    _render_top5(_top5_baseline(schedule, stats))

    roster_counts = st.session_state.get("wnba_v23_roster_counts", {})
    if st.button("📋 LOAD OFFICIAL WNBA ROSTERS", use_container_width=True, key="wnba_v23_rosters"):
        ids = sorted(set(schedule.away_team_id.astype(int).tolist() + schedule.home_team_id.astype(int).tolist()))
        counts = {}
        bar = st.progress(0, text="Loading official WNBA rosters...")
        for i, team_id in enumerate(ids, 1):
            try:
                counts[int(team_id)] = int(len(official_roster(team_id, current_season())))
            except Exception:
                counts[int(team_id)] = None
            bar.progress(i / max(len(ids), 1), text=f"WNBA rosters {i}/{len(ids)}")
        bar.empty()
        st.session_state["wnba_v23_roster_counts"] = counts
        roster_counts = counts

    st.markdown("### 🗓️ Selected WNBA Games")
    for _, row in schedule.iterrows():
        _game_card(row, stats, roster_counts)


# Patch only the presentation/slate layer. The empirical single-player simulator
# remains the proven V2 engine, now fed by the WNBA-only V2.2 data guard.
hub._hero = _hero
hub._game_card = _game_card
hub._slate_tab = _slate_tab


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown(EXTRA_CSS, unsafe_allow_html=True)
    st.caption("🔒 WNBA league isolation active • PRA V2.3 • non-WNBA team IDs are rejected before rendering.")
    return hub.render_wnba_pra_hub(section_header, status_info, team_logo, h)
