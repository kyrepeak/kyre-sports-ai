"""WNBA Points V1.9.3 — presentation-only visual upgrade.

Step 1 of the Points page redesign. The validated V1.9.2 projection,
SportsGameOdds, calibration, Monte Carlo, persistence and decision math remain
unchanged. This wrapper only adds MLB-style WNBA matchup cards and logo-enhanced
Top Points candidate cards using already-produced data.

Frozen WNBA PRA V3.2.1 and MLB V2.1.7 remain untouched.
"""
from __future__ import annotations

from html import escape

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_hub_v192 as core
import wnba_points_hub_v19 as v19
import wnba_schedule_v25 as schedule25

MODEL_VERSION = "WNBA POINTS V1.9.3 • VISUAL STEP 1"
PRA_FROZEN_BRANCH = core.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = core.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = core.MLB_FROZEN_BRANCH


def _num(value, default=np.nan):
    try:
        value = float(value)
        return default if pd.isna(value) else value
    except Exception:
        return default


def _current_day():
    return core._current_day()


def _logo(team_id):
    try:
        return schedule25.logo_url(int(float(team_id)))
    except Exception:
        return ""


def _team_id_lookup(schedule: pd.DataFrame):
    lookup = {}
    if schedule is None or schedule.empty:
        return lookup
    for _, game in schedule.iterrows():
        for side in ("away", "home"):
            name = str(game.get(f"{side}_team") or "").strip()
            try:
                tid = int(float(game.get(f"{side}_team_id")))
            except Exception:
                tid = 0
            if name and tid:
                lookup[name.lower()] = tid
    return lookup


def _visual_css():
    st.markdown(
        """
        <style>
        .wnba-viz-wrap{margin-top:1.0rem;margin-bottom:1.2rem}
        .wnba-viz-head{font-size:1.55rem;font-weight:850;margin:.55rem 0 .7rem;color:#f7fbff}
        .wnba-game-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-bottom:18px}
        .wnba-game-card{background:linear-gradient(145deg,#0b1c30 0%,#081424 100%);border:1px solid #244764;border-radius:22px;padding:18px;box-shadow:0 8px 25px rgba(0,0,0,.18)}
        .wnba-game-meta{display:flex;justify-content:space-between;gap:8px;color:#93a8bd;font-size:.76rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase;margin-bottom:14px}
        .wnba-teams{display:grid;grid-template-columns:1fr 38px 1fr;align-items:center;text-align:center;gap:8px}
        .wnba-team img{height:66px;max-width:82px;object-fit:contain;margin-bottom:7px}
        .wnba-team-name{font-size:1.03rem;font-weight:850;color:#f7fbff;line-height:1.12}
        .wnba-vs{font-size:1rem;color:#6f8aa4;font-weight:900}
        .wnba-venue{text-align:center;color:#8ea4ba;font-size:.78rem;margin-top:13px;border-top:1px solid rgba(90,130,165,.24);padding-top:10px}
        .wnba-candidate-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
        .wnba-candidate{background:linear-gradient(150deg,#0b2034,#081624);border:1px solid #28516f;border-radius:20px;padding:17px;position:relative;overflow:hidden}
        .wnba-candidate.rank1{border-color:#d8aa29;box-shadow:inset 4px 0 0 #d8aa29}
        .wnba-rank{color:#65d9ff;font-size:.75rem;font-weight:900;letter-spacing:.08em;text-transform:uppercase}
        .wnba-player-line{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:8px 0 7px}
        .wnba-player-name{font-size:1.13rem;font-weight:900;color:#fff}
        .wnba-mini-logos{display:flex;align-items:center;gap:5px;color:#69879f;font-size:.73rem}
        .wnba-mini-logos img{height:27px;width:34px;object-fit:contain}
        .wnba-big-prob{font-size:2.25rem;font-weight:900;color:#58ddff;line-height:1;margin:12px 0 2px}
        .wnba-prob-label{font-size:.67rem;color:#8da5ba;font-weight:800;text-transform:uppercase;letter-spacing:.04em}
        .wnba-stat-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin-top:14px}
        .wnba-stat{background:#091725;border:1px solid #25445d;border-radius:11px;padding:8px 7px}
        .wnba-stat .k{font-size:.61rem;color:#7591a8;text-transform:uppercase;font-weight:800}
        .wnba-stat .v{font-size:.86rem;color:#f5fbff;font-weight:850;margin-top:2px}
        .wnba-tier{display:inline-block;border-radius:999px;padding:4px 9px;font-size:.68rem;font-weight:900;margin-top:10px}
        .tier-monitor{background:#493b00;color:#ffd856;border:1px solid #826c09}
        .tier-strong{background:#073927;color:#66edae;border:1px solid #147752}
        .tier-best{background:#452b00;color:#ffd46d;border:1px solid #a47512}
        .tier-avoid{background:#3d1717;color:#ff8d8d;border:1px solid #783232}
        @media(max-width:760px){.wnba-game-grid,.wnba-candidate-grid{grid-template-columns:1fr}.wnba-stat-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.wnba-team img{height:58px}}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_matchup_cards(day: str):
    schedule = schedule25.schedule_for_date(day)
    if schedule is None or schedule.empty:
        return
    cards = []
    for _, g in schedule.iterrows():
        away = escape(str(g.get("away_team") or "Away"))
        home = escape(str(g.get("home_team") or "Home"))
        tip = escape(str(g.get("first_tip_et") or "TBD"))
        venue = escape(str(g.get("venue") or "Venue TBD"))
        status = escape(str(g.get("status") or "UPCOMING"))
        away_logo = escape(_logo(g.get("away_team_id")), quote=True)
        home_logo = escape(_logo(g.get("home_team_id")), quote=True)
        away_img = f'<img src="{away_logo}" alt="{away} logo">' if away_logo else "🏀"
        home_img = f'<img src="{home_logo}" alt="{home} logo">' if home_logo else "🏀"
        cards.append(
            f"""
            <div class="wnba-game-card">
              <div class="wnba-game-meta"><span>⏳ {status}</span><span>{tip}</span></div>
              <div class="wnba-teams">
                <div class="wnba-team">{away_img}<div class="wnba-team-name">{away}</div></div>
                <div class="wnba-vs">@</div>
                <div class="wnba-team">{home_img}<div class="wnba-team-name">{home}</div></div>
              </div>
              <div class="wnba-venue">📍 {venue}</div>
            </div>
            """
        )
    st.markdown('<div class="wnba-viz-wrap"><div class="wnba-viz-head">🏀 Today’s WNBA Points Matchups</div><div class="wnba-game-grid">' + "".join(cards) + "</div></div>", unsafe_allow_html=True)


def _tier_class(tier: str):
    if "BEST" in tier:
        return "tier-best"
    if "STRONG" in tier:
        return "tier-strong"
    if "MONITOR" in tier:
        return "tier-monitor"
    return "tier-avoid"


def _render_candidate_cards(day: str):
    try:
        rows = v19.points.combined_rows(day)
    except Exception:
        rows = pd.DataFrame()
    if rows is None or rows.empty:
        return

    schedule = schedule25.schedule_for_date(day)
    team_ids = _team_id_lookup(schedule)
    work = rows.copy()
    vals = work.apply(core._calibrated_values, axis=1, result_type="expand")
    vals.columns = ["raw_p", "stability_buffer", "cal_p_floor", "conservative_edge"]
    for col in vals.columns:
        work[col] = vals[col].values
    work["Decision"] = work.apply(core._calibrated_decision_tier, axis=1)
    work["_tier"] = work["Decision"].map({"🔥 BEST BET":0,"✅ STRONG":1,"⚠️ MONITOR":2,"⛔ AVOID":3}).fillna(9)
    for col in ("cal_p_floor", "conservative_edge", "model_over", "projection", "sim_mean", "line", "proj_min", "usage"):
        if col in work.columns:
            work[col] = pd.to_numeric(work[col], errors="coerce")
    work = work.sort_values(["_tier", "cal_p_floor", "conservative_edge"], ascending=[True, False, False])
    best = work.drop_duplicates(["player_key", "line"], keep="first").head(5).copy()
    if best.empty:
        return

    cards = []
    for rank, (_, r) in enumerate(best.iterrows(), start=1):
        player = escape(str(r.get("player") or "Player"))
        team = str(r.get("team_name") or "").strip()
        opp = str(r.get("opponent") or "").strip()
        team_id = team_ids.get(team.lower(), 0)
        opp_id = team_ids.get(opp.lower(), 0)
        team_logo = escape(_logo(team_id), quote=True)
        opp_logo = escape(_logo(opp_id), quote=True)
        team_img = f'<img src="{team_logo}" alt="{escape(team)}">' if team_logo else "🏀"
        opp_img = f'<img src="{opp_logo}" alt="{escape(opp)}">' if opp_logo else "🏀"
        line = _num(r.get("line"), np.nan)
        proj = _num(r.get("projection"), np.nan)
        raw = _num(r.get("raw_p"), np.nan)
        floor_p = _num(r.get("cal_p_floor"), np.nan)
        edge = _num(r.get("conservative_edge"), np.nan)
        mins = _num(r.get("proj_min"), np.nan)
        usage = _num(r.get("usage"), _num(r.get("USG_PCT"), np.nan))
        tier = str(r.get("Decision") or "⛔ AVOID")
        matchup = escape(f"{team} vs {opp}" if team and opp else team or opp)
        pass_src = escape(str(r.get("pass_source") or ""))
        stat_line = "—" if pd.isna(line) else f"{line:.1f}"
        stat_proj = "—" if pd.isna(proj) else f"{proj:.2f}"
        stat_raw = "—" if pd.isna(raw) else f"{raw*100:.1f}%"
        stat_floor = "—" if pd.isna(floor_p) else f"{floor_p*100:.1f}%"
        stat_edge = "—" if pd.isna(edge) else f"{edge*100:+.1f} pp"
        stat_min = "—" if pd.isna(mins) else f"{mins:.1f}"
        stat_usage = "—" if pd.isna(usage) else (f"{usage:.1f}%" if usage > 1.5 else f"{usage*100:.1f}%")
        cards.append(
            f"""
            <div class="wnba-candidate {'rank1' if rank == 1 else ''}">
              <div class="wnba-rank">{'🥇' if rank == 1 else '•'} RANK {rank} • {pass_src}</div>
              <div class="wnba-player-line">
                <div><div class="wnba-player-name">{player}</div><div style="color:#8ca4b9;font-size:.76rem;margin-top:3px">{matchup}</div></div>
                <div class="wnba-mini-logos">{team_img}<span>vs</span>{opp_img}</div>
              </div>
              <div class="wnba-big-prob">{stat_floor}</div>
              <div class="wnba-prob-label">calibrated probability floor • raw {stat_raw}</div>
              <div class="wnba-stat-grid">
                <div class="wnba-stat"><div class="k">Line</div><div class="v">{stat_line}</div></div>
                <div class="wnba-stat"><div class="k">Proj PTS</div><div class="v">{stat_proj}</div></div>
                <div class="wnba-stat"><div class="k">Proj MIN</div><div class="v">{stat_min}</div></div>
                <div class="wnba-stat"><div class="k">Usage</div><div class="v">{stat_usage}</div></div>
                <div class="wnba-stat"><div class="k">Cal Edge</div><div class="v">{stat_edge}</div></div>
                <div class="wnba-stat"><div class="k">Book</div><div class="v">{escape(str(r.get('book') or '—'))}</div></div>
                <div class="wnba-stat"><div class="k">Opponent</div><div class="v">{escape(opp or '—')}</div></div>
                <div class="wnba-stat"><div class="k">Lineup</div><div class="v">{'Confirmed' if bool(r.get('lineup_ready')) else 'Pending'}</div></div>
              </div>
              <span class="wnba-tier {_tier_class(tier)}">{escape(tier)}</span>
            </div>
            """
        )

    st.markdown('<div class="wnba-viz-wrap"><div class="wnba-viz-head">⭐ Visual Top Points Candidates</div><div class="wnba-candidate-grid">' + "".join(cards) + "</div></div>", unsafe_allow_html=True)
    st.caption("Presentation-only view. Rankings and numbers come from the existing V1.9.2 calibrated production output; no projection or sportsbook math is changed here.")


def _render_visual_step(day: str):
    _visual_css()
    st.markdown("---")
    st.caption("✨ WNBA Points Visual Step 1 • matchup logos + candidate cards • production model untouched")
    _render_matchup_cards(day)
    _render_candidate_cards(day)


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    result = core.render_wnba_points_hub(section_header, status_info, team_logo, h)
    day = _current_day()
    if day:
        _render_visual_step(day)
    return result


__all__ = ["MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH", "render_wnba_points_hub"]
