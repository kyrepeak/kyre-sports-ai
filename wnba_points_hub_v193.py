"""WNBA Points V1.9.3 — route-proof visual command center.

Presentation-only wrapper over the validated V1.9.2 Points stack. This version
replaces the inherited Points header renderer itself so the MLB-style WNBA
matchup cards are visible at the top of the live page rather than appended after
the legacy engine UI. Projection, SportsGameOdds matching, calibration, Monte
Carlo, persistence and decision math remain unchanged.

Frozen WNBA PRA V3.2.1 and MLB V2.1.7 remain untouched.
"""
from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

import wnba_points_hub_v192 as core
import wnba_schedule_v25 as schedule25

MODEL_VERSION = "WNBA POINTS V1.9.3 • VISUAL COMMAND CENTER"
PRA_FROZEN_BRANCH = core.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = core.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = core.MLB_FROZEN_BRANCH


def _logo(team_id):
    try:
        return schedule25.logo_url(int(float(team_id)))
    except Exception:
        return ""


def _visual_css():
    st.markdown(
        """
<style>
.kyre-wnba-hero{border:1px solid #2f6d8d;background:linear-gradient(145deg,#0a2034,#071421);border-radius:24px;padding:20px;margin:8px 0 16px;box-shadow:0 12px 34px rgba(0,0,0,.20)}
.kyre-wnba-kicker{font-size:10px;letter-spacing:1.45px;font-weight:950;color:#65dcff;text-transform:uppercase}
.kyre-wnba-title{font-size:31px;font-weight:1000;color:#fff;margin-top:6px;line-height:1.1}
.kyre-wnba-sub{font-size:12px;color:#9ab0c3;line-height:1.55;margin-top:8px}
.kyre-game-head{font-size:1.55rem;font-weight:900;color:#f8fbff;margin:1.0rem 0 .75rem}
.kyre-game-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-bottom:18px}
.kyre-game-card{background:linear-gradient(145deg,#0c2035,#081523);border:1px solid #2a526e;border-radius:22px;padding:18px;box-shadow:0 8px 24px rgba(0,0,0,.18)}
.kyre-game-meta{display:flex;justify-content:space-between;gap:10px;color:#9ab0c3;font-size:.72rem;font-weight:850;letter-spacing:.05em;text-transform:uppercase;margin-bottom:14px}
.kyre-team-grid{display:grid;grid-template-columns:1fr 38px 1fr;align-items:center;gap:8px;text-align:center}
.kyre-team img{height:70px;max-width:88px;object-fit:contain;margin-bottom:8px}
.kyre-team-name{font-size:1.05rem;font-weight:900;color:#fff;line-height:1.15}
.kyre-at{font-size:1rem;font-weight:900;color:#718ba2}
.kyre-venue{text-align:center;color:#8da5b9;font-size:.77rem;margin-top:14px;padding-top:10px;border-top:1px solid rgba(92,132,163,.25)}
.kyre-engine-note{background:#091a2a;border:1px solid #20435e;border-radius:14px;padding:11px 13px;color:#8fa8bc;font-size:.78rem;margin:5px 0 14px}
@media(max-width:760px){.kyre-game-grid{grid-template-columns:1fr}.kyre-team img{height:62px}.kyre-wnba-title{font-size:27px}}
</style>
        """,
        unsafe_allow_html=True,
    )


def _render_matchup_cards(day: str):
    schedule = schedule25.schedule_for_date(day)
    if schedule is None or schedule.empty:
        st.warning("⚠️ Visual matchup layer is waiting on the verified WNBA schedule.")
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
<div class="kyre-game-card">
  <div class="kyre-game-meta"><span>🏀 {status}</span><span>{tip}</span></div>
  <div class="kyre-team-grid">
    <div class="kyre-team">{away_img}<div class="kyre-team-name">{away}</div></div>
    <div class="kyre-at">@</div>
    <div class="kyre-team">{home_img}<div class="kyre-team-name">{home}</div></div>
  </div>
  <div class="kyre-venue">📍 {venue}</div>
</div>
            """
        )

    st.markdown(
        '<div class="kyre-game-head">🏀 Today’s WNBA Points Matchups</div>'
        '<div class="kyre-game-grid">' + "".join(cards) + "</div>",
        unsafe_allow_html=True,
    )


def _visual_header(day, slate):
    """Replace V1.9.1's inherited header without touching model/data functions."""
    _visual_css()

    try:
        rows = core.v19.points.combined_rows(day)
    except Exception:
        rows = pd.DataFrame()
    distributions = 0
    if isinstance(rows, pd.DataFrame) and not rows.empty:
        keys = [c for c in ("game_id", "player_key", "line") if c in rows.columns]
        distributions = int(rows[keys].drop_duplicates().shape[0]) if len(keys) == 3 else int(len(rows))

    st.markdown(
        """
<div class="kyre-wnba-hero">
  <div class="kyre-wnba-kicker">KYRE SPORTS AI • WNBA POINTS • VISUAL COMMAND CENTER</div>
  <div class="kyre-wnba-title">🏀 WNBA Points Command Center — V1.9.3</div>
  <div class="kyre-wnba-sub">MLB-style matchup presentation • verified four-game Eastern slate • current rosters • rotation-aware L3/L5 minutes • role/usage • opponent pace + L10 defense • positional matchup • empirical variance • exact SportsGameOdds Points markets. Production model math is unchanged.</div>
</div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Slate games", int(slate.get("total") or 0))
    c2.metric("Upcoming", int(slate.get("upcoming") or 0))
    pairs = slate.get("pairs")
    market_players = 0 if not isinstance(pairs, pd.DataFrame) or pairs.empty else int(pairs["player_key"].nunique())
    c3.metric("Points market players", market_players)
    c4.metric("Protected distributions", distributions)

    diag = slate.get("diag") or {}
    state = str(diag.get("state") or "UNKNOWN").upper()
    if state in {"VERIFIED", "VERIFIED_SINGLE_SOURCE", "VERIFIED_OFF_DAY"}:
        st.success(f"✅ VERIFIED WNBA POINTS SLATE • {day} • {int(slate.get('total') or 0)} game(s) • Eastern Time")
    else:
        st.warning(f"⚠️ WNBA schedule state: {state}")

    _render_matchup_cards(day)

    st.markdown(
        '<div class="kyre-engine-note">⚙️ <b>Production engine room below:</b> roster, minutes, history, matchup, Monte Carlo and calibration checks stay visible for auditability. The visual layer above does not alter any projection.</div>',
        unsafe_allow_html=True,
    )


# Critical route fix: V1.9.1 installs its own header hook every rerun. Replace the
# function it installs, rather than appending UI after the inherited page renders.
core.clean._clean_header = _visual_header


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    # Re-apply on every Streamlit rerun in case module state was refreshed.
    core.clean._clean_header = _visual_header
    return core.render_wnba_points_hub(section_header, status_info, team_logo, h)


__all__ = [
    "MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT",
    "MLB_FROZEN_BRANCH", "render_wnba_points_hub",
]
