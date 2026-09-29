"""WNBA PRA Page Cleanup V1.

Presentation-only cleanup for the active WNBA PRA route.  The module collapses
legacy version/step diagnostics into a clean slate/data status surface, keeps raw
verification data behind one Advanced diagnostics expander, and renders the
existing market/matchup outputs with user-facing labels.

No projection, qualification, ranking, Monte Carlo, provider ownership, or
identity/data fail-closed behavior is changed here.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Callable

import pandas as pd
import streamlit as st

import wnba_pra_hub_v24 as v24
import wnba_pra_hub_v27 as v27
import wnba_pra_hub_v28 as v28
import wnba_pra_market_v29 as market
import wnba_pra_matchup_v30 as matchup
import wnba_pra_api_market_bridge_v1 as api_market
import wnba_sportsgameodds_v1 as legacy_market


MODEL_VERSION = "WNBA PRA PAGE CLEANUP V1"

CLEANUP_CONTRACT = {
    "scope": "presentation_only",
    "hero_cleaned": True,
    "off_day_zero_wall_removed": True,
    "raw_diagnostics_collapsed": True,
    "provider_secret_message_removed": True,
    "market_labels_user_facing": True,
    "matchup_labels_user_facing": True,
    "api_ownership_changed": False,
    "projection_math_changed": False,
    "market_math_changed": False,
    "ranking_changed": False,
    "qualification_changed": False,
    "monte_carlo_changed": False,
    "nfl_changed": False,
    "mlb_changed": False,
}

CLEANUP_CSS = r"""
<style>
.wpc-shell{
  border:1px solid rgba(56,189,248,.28);
  background:
    radial-gradient(circle at 92% 0%,rgba(236,72,153,.10),transparent 34%),
    linear-gradient(145deg,#0b1728,#08111e);
  border-radius:20px;padding:18px 18px 16px;margin:8px 0 14px
}
.wpc-kicker{color:#55c7ff;font-size:.68rem;font-weight:950;letter-spacing:.12em;text-transform:uppercase}
.wpc-title{color:#fff;font-size:clamp(1.75rem,5vw,2.55rem);font-weight:950;letter-spacing:-.035em;margin-top:4px}
.wpc-sub{color:#9eb2c9;font-size:.78rem;line-height:1.5;margin-top:5px}
.wpc-pills{display:flex;flex-wrap:wrap;gap:7px;margin-top:12px}
.wpc-pill{border:1px solid #2b4663;background:#0a1625;border-radius:999px;padding:5px 9px;color:#a9c3dc;font-size:.58rem;font-weight:850}
.wpc-pill.good{border-color:#2c7258;color:#80edbd;background:#0a241d}
.wpc-pill.warn{border-color:#7b6527;color:#f8dc83;background:#251f0d}
.wpc-pill.bad{border-color:#783845;color:#ff9daa;background:#271117}
.wpc-off{border:1px solid #3c536e;background:#0a1523;border-radius:16px;padding:14px;margin:10px 0 14px}
.wpc-off b{display:block;color:#fff;font-size:1rem}.wpc-off span{display:block;color:#9db0c5;font-size:.7rem;line-height:1.5;margin-top:4px}
.wpc-status{border:1px solid #263e59;background:#091522;border-radius:16px;padding:13px;margin:10px 0 14px}
.wpc-status h4{margin:0 0 9px;color:#fff;font-size:.93rem}
.wpc-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}
.wpc-metric{border:1px solid #263b54;background:#08131f;border-radius:12px;padding:9px}
.wpc-metric span{display:block;color:#748aa3;font-size:.46rem;font-weight:900;text-transform:uppercase;letter-spacing:.08em}
.wpc-metric b{display:block;color:#f8fafc;font-size:.88rem;margin-top:3px}
.wpc-metric.good b{color:#7be8b7}.wpc-metric.warn b{color:#f5db86}.wpc-metric.bad b{color:#ff9aa5}
.w27-note{display:none!important}
@media(max-width:760px){.wpc-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""

_TECHNICAL_CAPTION_MARKERS = (
    "WNBA league isolation active",
    "PRA V2.",
    "PRA V3.",
    "SportsGameOdds WNBA",
    "MLB V2.1.7 frozen",
    "production checkpoint preserved",
    "model/market/MC/ranking unchanged",
    "Step 1 Opportunity Decomposition",
)

_MARKDOWN_REPLACEMENTS = (
    ("🏆 V2.8 Minutes + Role PRA — Top 5", "🏆 Top PRA Projections"),
    ("V2.8 Step 5:", "Projection model:"),
    ("Step 5 • Projected minutes + role", "Projected minutes + role"),
    ("STEP-5 PRA", "PRA"),
    ("Step 5 is active:", "Projection inputs:"),
)

_ORIGINAL_SLATE_TAB = v28._slate_tab


def _safe_call(fn: Callable[..., Any], *args: Any) -> dict[str, Any]:
    try:
        value = fn(*args)
        return value if isinstance(value, dict) else {}
    except Exception as exc:
        return {"state": "CHECK", "error": f"{type(exc).__name__}: {exc}"}


def _clean_state(value: Any) -> str:
    return str(value or "CHECK").replace("_", " ").strip()


def _status_class(state: str) -> str:
    upper = state.upper()
    if upper in {"VERIFIED", "CONNECTED", "READY"}:
        return "good"
    if upper in {"PROVIDER FAILURE", "ERROR", "API ERROR"}:
        return "bad"
    return "warn"


def _clean_hero(day: Any) -> None:
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")
    sdiag = _safe_call(v24.schedule_diagnostics, day)
    pdiag = _safe_call(v27.availability.player_pool_diagnostics, day)
    cdiag = _safe_call(v27.context.context_diagnostics, day)
    adiag = _safe_call(v27.availability.availability_diagnostics, day)
    role_diag = _safe_call(v28.role.role_diagnostics, day)

    schedule_state = str(sdiag.get("state") or "CHECK")
    games = int(sdiag.get("games") or 0)
    players = int(pdiag.get("players") or pdiag.get("roster_players") or 0)
    teams = int(pdiag.get("teams") or sdiag.get("teams") or 0)
    lineups = int(adiag.get("lineups_confirmed") or 0)

    st.markdown(CLEANUP_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="wpc-shell">'
        '<div class="wpc-kicker">KYRE SPORTS AI • WNBA</div>'
        '<div class="wpc-title">🏀 WNBA PRA</div>'
        '<div class="wpc-sub">Clean slate view for schedule, player availability, projections, market analysis and final decision support. '
        'Raw provider and verification detail stays available under Advanced diagnostics.</div>'
        '<div class="wpc-pills">'
        f'<div class="wpc-pill">📅 {day_str}</div>'
        '<div class="wpc-pill good">🔒 Kyre Sports API owned</div>'
        '<div class="wpc-pill">⏱️ Projected minutes</div>'
        '<div class="wpc-pill">📈 Role / usage</div>'
        '<div class="wpc-pill">🎯 P / R / A separate</div>'
        '</div></div>',
        unsafe_allow_html=True,
    )

    if schedule_state == "VERIFIED_OFF_DAY" or games == 0 and schedule_state == "VERIFIED_OFF_DAY":
        st.markdown(
            '<div class="wpc-off"><b>🌙 No WNBA games on this date</b>'
            '<span>The selected date was verified as an off day. Nothing is wrong with the page, and no player or market rows are fabricated.</span></div>',
            unsafe_allow_html=True,
        )
    else:
        state_text = _clean_state(schedule_state)
        cls = _status_class(state_text)
        st.markdown(
            '<div class="wpc-status"><h4>Slate & data status</h4><div class="wpc-grid">'
            f'<div class="wpc-metric {cls}"><span>Slate</span><b>{state_text}</b></div>'
            f'<div class="wpc-metric"><span>Games</span><b>{games}</b></div>'
            f'<div class="wpc-metric"><span>Current players</span><b>{players}</b></div>'
            f'<div class="wpc-metric"><span>Lineups confirmed</span><b>{lineups}/{teams}</b></div>'
            '</div></div>',
            unsafe_allow_html=True,
        )

    with st.expander("⚙️ Advanced diagnostics", expanded=False):
        st.write({
            "selected_date": day_str,
            "schedule": sdiag,
            "player_pool": pdiag,
            "matchup_context": cdiag,
            "availability": adiag,
            "minutes_role": role_diag,
            "presentation_only_cleanup": True,
        })


def _clean_slate_tab(day: Any, schedule: Any, stats: Any) -> Any:
    if schedule is None or getattr(schedule, "empty", True):
        return None
    return _ORIGINAL_SLATE_TAB(day, schedule, stats)


def _clean_market_panel(day: Any) -> None:
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")
    snap = api_market.market_snapshot(day_str)
    state = str(snap.get("state") or "CHECK")
    if state == "NO_WNBA_GAMES":
        return

    props = snap.get("player_props")
    rows = 0 if props is None else len(props)
    matched = int(snap.get("matched_games") or 0)
    scheduled = int(snap.get("schedule_games") or 0)

    st.markdown("### 💹 Market Data")
    if state == "CONNECTED":
        c1, c2, c3 = st.columns(3)
        c1.metric("Status", "Connected")
        c2.metric("Games matched", f"{matched}/{scheduled}")
        c3.metric("Player prop rows", rows)
    elif state == "NO_STORED_MARKETS":
        st.info("Market data has not been stored for this slate yet. Projections remain available; no sportsbook lines are fabricated.")
    elif state == "MATCH_FAILURE":
        st.warning("Market data was received but could not be safely matched to the verified WNBA slate. The page is failing closed.")
    else:
        st.warning("Market data is temporarily unavailable from Kyre Sports API. Projection outputs remain isolated from missing sportsbook data.")

    with st.expander("Market diagnostics", expanded=False):
        st.write({
            "selected_date": snap.get("selected_date"),
            "api": snap.get("provider"),
            "snapshot_id": snap.get("snapshot_id"),
            "provider_id": snap.get("provider_id"),
            "source": snap.get("market_source"),
            "state": state,
            "matched_games": matched,
            "schedule_games": scheduled,
            "player_prop_rows": rows,
            "direct_provider_called": snap.get("direct_provider_called"),
        })


def _clean_market_grade(day: Any) -> None:
    graded, meta = market.grade_pra_markets(day)
    snap = meta.get("snapshot") or {}
    if str(snap.get("state") or "") == "NO_WNBA_GAMES":
        return

    st.markdown("### 🎯 PRA Market Analysis")
    if graded is None or graded.empty:
        st.info("No exact two-sided PRA market match is available right now. No line or pick is being forced.")
        if meta.get("unmatched_players"):
            with st.expander("Identity diagnostics", expanded=False):
                st.caption("Unmatched player identities: " + " • ".join(meta["unmatched_players"][:12]))
        return

    qualified = graded.loc[graded["eligible"].eq(True)].copy() if "eligible" in graded.columns else graded.iloc[0:0].copy()
    c1, c2, c3 = st.columns(3)
    c1.metric("Exact matches", len(graded))
    c2.metric("Qualified overs", len(qualified))
    c3.metric("Projection coverage", int(meta.get("projections") or 0))

    if qualified.empty:
        st.info("No PRA overs currently clear the probability, no-vig and freshness gates. That is a valid result.")
    else:
        best = (
            qualified.sort_values(["market_grade", "edge", "over_odds"], ascending=[False, False, False])
            .drop_duplicates("player", keep="first")
            .head(5)
        )
        st.markdown("#### 🏆 Best qualified PRA overs")
        for rank, (_, row) in enumerate(best.iterrows(), start=1):
            st.markdown(
                f"**#{rank} {row['player']} — OVER {row['line']:g}**  \n"
                f"{row['team']} vs {row['opponent']} • **{row['book']} {market._fmt_odds(row['over_odds'])}**  \n"
                f"Projection **{row['projection']:.1f}** • Model Over **{market._pct(row['model_over'])}** • "
                f"No-vig **{market._pct(row['no_vig_over'])}** • Edge **{100.0*row['edge']:+.1f} pp**"
            )

    with st.expander("All exact PRA matches", expanded=False):
        show = graded.copy()
        show["Model Over"] = show["model_over"].map(market._pct)
        show["No-vig Over"] = show["no_vig_over"].map(market._pct)
        show["Edge"] = show["edge"].map(lambda x: "—" if pd.isna(x) else f"{100*x:+.1f} pp")
        show["Price"] = show["over_odds"].map(market._fmt_odds)
        st.dataframe(
            show[["player", "book", "line", "projection", "Model Over", "No-vig Over", "Edge", "Price", "freshness", "eligible"]]
            .rename(columns={
                "player": "Player", "book": "Book", "line": "Line", "projection": "Proj PRA",
                "freshness": "Freshness", "eligible": "Qualified",
            }),
            use_container_width=True,
            hide_index=True,
        )


def _clean_matchup_grade(day: Any) -> None:
    snap = api_market.market_snapshot(day)
    if str(snap.get("state") or "") == "NO_WNBA_GAMES":
        return

    graded, meta = matchup.grade_matchup_pra(day)
    st.markdown("### 🧭 Matchup & Pace")
    if graded is None or graded.empty:
        st.info("No matchup-adjusted PRA market matches are available yet.")
        return

    adiag = meta.get("availability_diag") or {}
    teams = int(adiag.get("teams") or 0)
    confirmed = int(adiag.get("lineups_confirmed") or 0)
    eligible = graded.loc[graded["eligible"].eq(True)].copy() if "eligible" in graded.columns else graded.iloc[0:0].copy()

    c1, c2, c3 = st.columns(3)
    c1.metric("Adjusted matches", len(graded))
    c2.metric("Qualified overs", len(eligible))
    c3.metric("Lineups confirmed", f"{confirmed}/{teams}")

    if teams and confirmed < teams:
        st.warning("Starting fives are still pending for part of this slate. Rankings remain fail-closed to explicit lineup status.")

    if eligible.empty:
        st.info("No PRA overs clear the matchup, probability, no-vig and freshness gates.")
    else:
        best = (
            eligible.sort_values(["matchup_grade", "edge"], ascending=[False, False])
            .drop_duplicates("player", keep="first")
            .head(5)
        )
        st.markdown("#### 🏆 Best matchup-adjusted PRA overs")
        for rank, (_, row) in enumerate(best.iterrows(), start=1):
            st.markdown(
                f"**#{rank} {row['player']} — OVER {row['line']:.1f} ({row['book']})**  \n"
                f"Raw **{row['raw_projection']:.1f}** → Adjusted **{row['projection']:.1f}** "
                f"({row['matchup_delta']:+.1f}) • Model **{matchup._pct(row['model_over'])}** • "
                f"Edge **{100.0*row['edge']:+.1f} pp**"
            )

    with st.expander("All matchup-adjusted matches", expanded=False):
        show = graded.copy()
        show["Model Over"] = show["model_over"].map(matchup._pct)
        show["No-vig Over"] = show["no_vig_over"].map(matchup._pct)
        show["Edge"] = show["edge"].map(lambda x: "—" if pd.isna(x) else f"{100.0*x:+.1f} pp")
        st.dataframe(
            show[["player", "book", "line", "raw_projection", "projection", "matchup_delta", "Model Over", "No-vig Over", "Edge", "status"]]
            .rename(columns={
                "player": "Player", "book": "Book", "line": "Line",
                "raw_projection": "Raw PRA", "projection": "Adj PRA", "matchup_delta": "Matchup Δ",
                "status": "Status",
            }),
            use_container_width=True,
            hide_index=True,
        )


def begin_render() -> dict[str, Any]:
    hub = v28.v27.v25.v24.v23.hub
    hub._hero = _clean_hero
    hub._slate_tab = _clean_slate_tab
    v28.v27.v25.v24.v23._slate_tab = _clean_slate_tab

    # Step 1 API ownership installs first; cleanup changes presentation only.
    legacy_market.render_market_panel = _clean_market_panel
    market.render_pra_market_grade = _clean_market_grade
    matchup.render_matchup_grade = _clean_matchup_grade

    return {
        "installed": True,
        "model_version": MODEL_VERSION,
        **CLEANUP_CONTRACT,
    }


@contextmanager
def presentation_scope():
    original_caption = st.caption
    original_markdown = st.markdown

    def clean_caption(body: Any, *args: Any, **kwargs: Any):
        text = str(body)
        if any(marker in text for marker in _TECHNICAL_CAPTION_MARKERS):
            return None
        return original_caption(body, *args, **kwargs)

    def clean_markdown(body: Any, *args: Any, **kwargs: Any):
        if isinstance(body, str):
            for old, new in _MARKDOWN_REPLACEMENTS:
                body = body.replace(old, new)
        return original_markdown(body, *args, **kwargs)

    st.caption = clean_caption
    st.markdown = clean_markdown
    try:
        yield
    finally:
        st.caption = original_caption
        st.markdown = original_markdown


__all__ = [
    "CLEANUP_CONTRACT",
    "MODEL_VERSION",
    "begin_render",
    "presentation_scope",
]
