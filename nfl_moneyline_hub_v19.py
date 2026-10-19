"""NFL Moneyline V19 — consumer-first matchup surface.

Presentation-only successor over the frozen V18/V8 analytical chain. The frozen
engine still owns every schedule, availability, probability, market, Monte Carlo,
edge/EV, and grading decision. V19 executes that engine in the certified hidden
container, then renders one matchup-first surface with compact health and optional
diagnostics. No analytical formula or sportsbook influence changes.
"""
from __future__ import annotations

from datetime import date
from html import escape

import pandas as pd
import streamlit as st

import nfl_moneyline_hub_v9 as presentation
import nfl_moneyline_hub_v11 as hidden_owner
import nfl_moneyline_hub_v13 as theme_owner
import nfl_moneyline_hub_v14 as step1_visual
import nfl_moneyline_hub_v15 as matchup_visual
import nfl_moneyline_hub_v16 as analysis_visual
import nfl_moneyline_hub_v17 as market_visual
import nfl_moneyline_hub_v18 as responsive_visual

MODEL_VERSION = "NFL MONEYLINE V19 • CONSUMER-FIRST CLEAN SURFACE"
FROZEN_ENGINE = "nfl_moneyline_hub_v8"
FROZEN_PRESENTATION = "nfl_moneyline_hub_v18"
HEADLESS_FROZEN_ENGINE = "nfl_moneyline_hub_v11._hidden_run_frozen_engine"
PRESENTATION_ONLY = True
DISPLAY_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_MARKET_MATH = False
SPORTSBOOK_MODEL_INFLUENCE = 0.0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
MONTE_CARLO_SIMULATIONS = 5_000_000

_V19_CSS = r"""
<style data-nfl-moneyline-consumer-v19="true">
.kml19-hero{margin:.18rem 0 .58rem;padding:.82rem .92rem;border:1px solid rgba(88,201,255,.24);border-radius:16px;background:radial-gradient(circle at 92% 0%,rgba(88,201,255,.09),transparent 30%),linear-gradient(150deg,#091522,#061018)}
.kml19-kicker{color:#58c9ff;font-size:.55rem;font-weight:950;letter-spacing:.11em;text-transform:uppercase}
.kml19-title{margin-top:.14rem;color:#f4f8fc;font-size:1.35rem;font-weight:950;letter-spacing:-.025em}.kml19-title span{color:#7ff2c2}
.kml19-sub{margin-top:.28rem;color:#8399ad;font-size:.62rem;line-height:1.45}
.kml19-status{display:flex;gap:5px;flex-wrap:wrap;margin-top:.55rem}.kml19-status span{border:1px solid #2a506d;background:#091a29;color:#9ddcf6;border-radius:999px;padding:4px 7px;font-size:.45rem;font-weight:900}.kml19-status .good{border-color:#287b61;color:#79efbd}.kml19-status .watch{border-color:#806d2e;color:#f2d77b}
.kml19-slate{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:.5rem 0 .62rem;padding:.62rem .72rem;border:1px solid rgba(88,201,255,.13);border-radius:12px;background:#07131e}.kml19-slate span{color:#718aa1;font-size:.48rem;font-weight:900;letter-spacing:.06em}.kml19-slate b{color:#eef7fd;font-size:.72rem}
.kml19-health{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.42rem;margin-bottom:.62rem}.kml19-health>div{border:1px solid rgba(88,201,255,.11);border-radius:10px;background:#07131e;padding:.52rem}.kml19-health span{display:block;color:#6d8499;font-size:.39rem;font-weight:900;letter-spacing:.05em}.kml19-health b{display:block;margin-top:3px;color:#e8f2f9;font-size:.58rem}
.kml15-card{margin-top:.58rem!important}.kml16-analysis,.kml17-market{margin-top:.42rem!important}
@media(max-width:760px){.kml19-health{grid-template-columns:1fr 1fr}.kml19-slate{align-items:flex-start;flex-direction:column}.kml19-title{font-size:1.16rem}}
</style>
"""


def _safe(value, fallback="") -> str:
    return presentation._safe(value, fallback)


def _silent_frozen_engine() -> None:
    """Execute frozen analytical ownership without exposing its step-first UI."""
    return hidden_owner._hidden_run_frozen_engine()


def _composed_css() -> str:
    css = theme_owner.build_moneyline_theme_css(presentation._CSS)
    css = step1_visual._step1_css(css)
    css = matchup_visual._step2_css(css)
    css = analysis_visual._step3_css(css)
    css = market_visual._step4_css(css)
    css = responsive_visual._step5_css(css)
    return css + _V19_CSS


def _render_header(selected: date, games: int, depth_ready: bool, injury_ready: bool, market_ready: bool, mc_ready: bool, edge_ready: bool) -> None:
    st.markdown(
        '<div class="kml19-hero">'
        '<div class="kml19-kicker">KYRE SPORTS AI • NFL MONEYLINE</div>'
        '<div class="kml19-title">💰 Moneyline <span>Matchup Intelligence</span></div>'
        '<div class="kml19-sub">Model probability first • verified QB / injury context • sportsbook comparison • calibrated uncertainty • final recommendation.</div>'
        '<div class="kml19-status"><span class="good">PREGAME VERIFIED</span><span>MODEL / MARKET FIREWALL</span><span>5M MONTE CARLO</span><span>STAKE SIZING OFF</span></div>'
        '</div>', unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="kml19-slate"><div><span>ACTIVE NFL SLATE</span><b>'
        + escape(selected.strftime("%a • %b %d, %Y"))
        + '</b></div><div><span>NEXT VERIFIED MATCHUPS</span><b>' + str(games) + '</b></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="kml19-health">'
        f'<div><span>QB / INJURY</span><b>{"READY" if depth_ready and injury_ready else "CHECK"}</b></div>'
        f'<div><span>MARKET</span><b>{"READY" if market_ready else "WAITING"}</b></div>'
        f'<div><span>MODEL</span><b>READY</b></div>'
        f'<div><span>MONTE CARLO / EDGE</span><b>{"READY" if mc_ready and edge_ready else "CHECK"}</b></div>'
        '</div>', unsafe_allow_html=True,
    )


def _diagnostics(final: dict, snap: dict, away: str, home: str) -> None:
    with st.expander(f"Advanced Diagnostics — {away} @ {home}", expanded=False):
        prereq = final.get("prerequisites") or {}
        reasons = [_safe(x) for x in (prereq.get("reasons") or []) if _safe(x)]
        if reasons:
            st.caption("Gate status: " + " • ".join(reasons))
        st.caption(
            "Frozen ownership: V8 final grading • V7 edge/EV • V6 Monte Carlo • "
            "V5 market/no-vig • V4.x calibrated probability • V3/V2 availability. "
            "Sportsbook prices never alter model P(win)."
        )
        rows = []
        for row in (snap.get("rows") or []):
            rows.append({
                "Book": row.get("book") or "—",
                "Away ML": presentation._ml(row.get("away_ml")),
                "Home ML": presentation._ml(row.get("home_ml")),
                "Freshness": row.get("freshness") or "UNKNOWN",
                "Provider": row.get("provider") or "—",
            })
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def render_nfl_moneyline_hub() -> None:
    st.markdown(_composed_css(), unsafe_allow_html=True)

    selected = st.session_state.get("nfl_v1_date") or st.session_state.get("nfl_active_slate_date") or date.today()
    try:
        selected = pd.to_datetime(selected).date()
    except Exception:
        selected = date.today()
    presentation._sync_frozen_date(selected)

    with st.spinner("Building verified Moneyline matchup intelligence…"):
        _silent_frozen_engine()

    pregame = list(st.session_state.get("nfl_moneyline_v3_pregame") or st.session_state.get("nfl_moneyline_v1_pregame") or [])
    contexts = st.session_state.get("nfl_moneyline_v3_team_context") or st.session_state.get("nfl_moneyline_v2_team_context") or {}
    gameplans = st.session_state.get("nfl_moneyline_v3_gameplan_context") or {}
    edges = st.session_state.get("nfl_moneyline_v7_edge_outputs") or {}
    mc_outputs = st.session_state.get("nfl_moneyline_v6_mc_outputs") or {}
    snapshots = st.session_state.get("nfl_moneyline_v5_market_snapshots") or {}
    profiles = st.session_state.get("nfl_moneyline_v4_strength_profiles") or {}

    depth_ready = bool(st.session_state.get("nfl_moneyline_v3_depth_ready") or st.session_state.get("nfl_moneyline_v2_depth_ready"))
    injury_ready = bool(st.session_state.get("nfl_moneyline_v3_injuries_ready") or st.session_state.get("nfl_moneyline_v2_injuries_ready"))
    market_ready = bool(st.session_state.get("nfl_moneyline_v5_market_ready"))
    mc_ready = bool(st.session_state.get("nfl_moneyline_v6_mc_ready"))
    edge_ready = bool(st.session_state.get("nfl_moneyline_v7_edge_ready"))

    _render_header(selected, len(pregame), depth_ready, injury_ready, market_ready, mc_ready, edge_ready)

    if not pregame:
        st.info("No verified pregame NFL matchup is available on the active slate. The page will advance with the shared NFL active-slate runtime.")
        return

    calibration = presentation.frozen.v431.v43._fit_calibration_model()
    for game in pregame:
        gid = presentation._gid(game)
        edge_out = edges.get(gid, {})
        mc_out = mc_outputs.get(gid, {})
        snap = snapshots.get(gid, {})
        final = presentation.frozen._build_final(game, gid, edge_out, mc_out, snap, profiles, calibration)
        html = market_visual._market_matchup_html(game, final, edge_out, mc_out, snap, contexts, gameplans)
        st.markdown('<div class="kml9-page">' + html + '</div>', unsafe_allow_html=True)
        _diagnostics(final, snap, _safe(game.get("away_team"), "Away"), _safe(game.get("home_team"), "Home"))

    st.caption("Model probabilities are estimates, not guarantees. V19 changes presentation only; frozen analytical ownership remains authoritative.")


def render_nfl_hub(market: str = "Moneyline") -> None:
    if str(market or "Moneyline") != "Moneyline":
        raise RuntimeError("NFL Moneyline V19 handles Moneyline only.")
    return render_nfl_moneyline_hub()


__all__ = [
    "DISPLAY_ONLY", "FROZEN_ENGINE", "FROZEN_PRESENTATION", "HEADLESS_FROZEN_ENGINE",
    "MAY_MODIFY_MARKET_MATH", "MAY_MODIFY_PROJECTION", "MODEL_VERSION", "MONTE_CARLO_SIMULATIONS",
    "PRESENTATION_ONLY", "SPORTSBOOK_MODEL_INFLUENCE", "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED", "_silent_frozen_engine", "render_nfl_hub", "render_nfl_moneyline_hub",
]
