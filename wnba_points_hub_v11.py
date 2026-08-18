"""WNBA Points V1.1 — isolated production page.

WNBA-only development surface. The known-good PRA V3.2.1 checkpoint is frozen on
branch wnba-pra-v321-frozen-20260818 and is not modified by this module.
MLB V2.1.7 remains frozen on mlb-v217-frozen-20260818.

This page intentionally keeps Points development separate from PRA and from the
future WNBA Daily Master Card until the Points connector passes validation.
It reuses only shared verified WNBA infrastructure (schedule, roster/role,
matchup context and SportsGameOdds transport). PRA totals are never used as a
shortcut for the Points projection.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_points_v10 as points
import wnba_schedule_v24 as schedule

MODEL_VERSION = "WNBA POINTS V1.1 • ISOLATED PAGE"
PRA_FROZEN_BRANCH = "wnba-pra-v321-frozen-20260818"
PRA_FROZEN_COMMIT = "5f29fc48856a198d74bcdbde47821e55e275222a"
MLB_FROZEN_BRANCH = "mlb-v217-frozen-20260818"


def _default_day():
    existing = st.session_state.get("wnba_points_date") or st.session_state.get("wnba_pra_v2_date")
    if existing:
        try:
            return pd.to_datetime(existing).date()
        except Exception:
            pass
    return datetime.now(ZoneInfo("America/New_York")).date()


def _day_string(value):
    return pd.to_datetime(value).strftime("%Y-%m-%d")


def _status_counts(day):
    diag = schedule.schedule_diagnostics(day)
    try:
        pairs, snap = points._paired_points_markets(day)
    except Exception:
        pairs, snap = pd.DataFrame(), {}
    current = points.combined_rows(day)
    games = int(diag.get("games") or 0)
    market_players = 0 if pairs is None or pairs.empty else int(pairs["player_key"].nunique())
    exact_pairs = 0 if pairs is None else int(len(pairs))
    distributions = 0 if current is None or current.empty else int(
        current[["game_id", "player_key", "line"]].drop_duplicates().shape[0]
    )
    return diag, snap, games, market_players, exact_pairs, distributions


def _render_header(day):
    diag, snap, games, market_players, exact_pairs, distributions = _status_counts(day)
    verified = str(diag.get("state") or "").upper() in {"VERIFIED", "VERIFIED_OFF_DAY"}
    api_connected = bool(snap.get("connected")) if isinstance(snap, dict) else False
    if not api_connected and isinstance(snap, dict):
        api_connected = str(snap.get("status") or "").upper() in {"CONNECTED", "OK", "READY"}

    st.markdown(
        """
<div style="border:1px solid #2f6381;background:linear-gradient(145deg,#091c2d,#071421);border-radius:20px;padding:16px;margin:8px 0 14px">
  <div style="font-size:10px;letter-spacing:1.35px;font-weight:950;color:#65dcff">KYRE SPORTS AI • WNBA POINTS • ISOLATED PRODUCTION PAGE</div>
  <div style="font-size:30px;font-weight:1000;color:white;margin-top:5px">🏀 WNBA Points Command Center — V1.1</div>
  <div style="font-size:12px;color:#93aabd;line-height:1.55;margin-top:7px">Points-only development surface. PRA V3.2.1 is frozen and the WNBA Daily Master Card is intentionally not fed by Points until this page passes validation.</div>
</div>
""",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Verified games", games)
    c2.metric("Points market players", market_players)
    c3.metric("Exact same-book pairs", exact_pairs)
    c4.metric("5M distributions", distributions)

    if verified:
        st.success(f"✅ WNBA schedule verified for {day} • PRA frozen • MLB frozen")
    else:
        st.warning(f"⚠️ WNBA schedule state: {diag.get('state') or 'UNKNOWN'}")

    if api_connected or exact_pairs > 0:
        st.caption("🎯 SportsGameOdds WNBA Points transport is available. Sportsbook lines grade the model only; they never move the Points projection.")
    else:
        st.caption("🎯 SportsGameOdds Points markets have not matched yet. No market is fabricated when an exact pair is unavailable.")


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.caption(
        "🏀 WNBA Points V1.1 • separate production page ACTIVE • PRA V3.2.1 frozen • "
        "SportsGameOdds WNBA • MLB V2.1.7 frozen"
    )

    selected = st.date_input(
        "WNBA Points slate date",
        value=_default_day(),
        key="wnba_points_date_control",
    )
    day = _day_string(selected)
    st.session_state["wnba_points_date"] = day

    _render_header(day)

    with st.expander("🧊 Freeze / isolation status", expanded=False):
        st.write(f"PRA checkpoint: `{PRA_FROZEN_BRANCH}` @ `{PRA_FROZEN_COMMIT[:12]}`")
        st.write(f"MLB checkpoint: `{MLB_FROZEN_BRANCH}`")
        st.write("Points work is isolated from both frozen production stacks. Shared data utilities may be read, but PRA/MLB model files are not changed by this page.")

    points.render_points_connector(day)

    st.info(
        "Phase 1 rule: validate the Points page first. After the Points model, exact-market matching, 5M diagnostics, persistence and decision gates pass, we will plug its qualified candidates into the shared WNBA Daily Master Card."
    )


__all__ = [
    "MODEL_VERSION",
    "PRA_FROZEN_BRANCH",
    "PRA_FROZEN_COMMIT",
    "MLB_FROZEN_BRANCH",
    "render_wnba_points_hub",
]
