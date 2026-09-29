"""CFB Top Picks Step 4 — tap-to-load Why / History / Benefits.

Additive over frozen Step 3. Ranked picks, probability, toughness, and market
selection remain owned by the frozen Step-3 engine. The initial Top-10 board
renders without any historical network request. Tapping one matchup selects that
exact ESPN event through the existing route query and loads only that game's
read-only explanation/history context.
"""
from __future__ import annotations

from html import escape
from urllib.parse import urlencode

import streamlit as st

import cfb_top_picks_details_v1 as details
import cfb_top_picks_engine_v1 as engine
import cfb_top_picks_page_v2 as cards
import cfb_top_picks_page_v3 as prior

MODEL_VERSION = "CFB TOP PICKS V4 • STEP 4 WHY HISTORY BENEFITS"
PAGE_MARKER = "CFB_TOP_PICKS_STEP4_DETAILS_ACTIVE"
LAYOUT_PREVIEW = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
HISTORY_PROJECTION_INFLUENCE = 0.0
TOP_PICK_DETAIL_QUERY = "top_pick_detail"
ROUTE_QUERY_SPORT = "ks_sport"
ROUTE_QUERY_MARKET = "ks_cfb_market"
CFB_SPORT_LABEL = "College Football"
TOP_PICKS_MARKET = "Top Picks"

CSS = prior.CSS + r"""
<style>
[data-testid="cfb-top-picks-step4-root"]{width:100%;max-width:1500px;margin:0 auto;padding:4px 2px 18px;color:#f7fbff}
.tp4-card-link{display:block;color:inherit;text-decoration:none}
.tp4-card-link:hover{text-decoration:none}
.tp4-details{display:block;margin:0;padding:0}
.tp4-details>summary{list-style:none;cursor:pointer;outline:none}
.tp4-details>summary::-webkit-details-marker{display:none}
.tp4-details>summary .tp2-card{transition:border-color .16s ease,box-shadow .16s ease}
.tp4-details[open]>summary .tp2-card{border-color:rgba(17,157,255,.52);box-shadow:0 0 0 1px rgba(17,157,255,.10),0 10px 30px rgba(0,0,0,.20)}
.tp4-details[open] .tp2-chevron{transform:rotate(180deg)}
.tp4-panel{margin:-1px 8px 2px;padding:12px;border:1px solid rgba(109,198,255,.16);border-top:0;border-radius:0 0 13px 13px;background:linear-gradient(180deg,rgba(5,14,23,.98),rgba(4,11,18,.98))}
.tp4-grid{display:grid;grid-template-columns:1.15fr 1.35fr 1.15fr;gap:10px}
.tp4-box{min-width:0;border:1px solid rgba(109,198,255,.12);border-radius:11px;background:#08131e;padding:11px}
.tp4-box h4{margin:0 0 7px;color:#78d3ff;font-size:.72rem;letter-spacing:.04em;text-transform:uppercase}
.tp4-box p{margin:0;color:#c3d1df;font-size:.78rem;line-height:1.48}
.tp4-history-head{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:7px;color:#91a8bc;font-size:.66rem}
.tp4-history-list{display:flex;flex-direction:column;gap:6px}
.tp4-history-row{display:flex;justify-content:space-between;gap:10px;padding:7px 8px;border-radius:8px;background:#0c1a28;border:1px solid rgba(109,198,255,.08);font-size:.72rem;color:#d9e6f1}
.tp4-history-row span:last-child{font-weight:900;color:#fff}
.tp4-audit{margin-top:9px;color:#698298;font-size:.62rem;line-height:1.45}
.tp4-audit strong{color:#7bcfff}
.tp4-nohist{padding:8px;border-radius:8px;background:#111923;color:#a9bac9;font-size:.72rem;line-height:1.45}
.tp4-loading{padding:9px;border-radius:8px;background:#0d1823;color:#8fb0c8;font-size:.72rem;line-height:1.45}
@media(max-width:900px){.tp4-grid{grid-template-columns:1fr}.tp4-panel{margin-left:4px;margin-right:4px}}
</style>
"""


def _query_value(key: str) -> str:
    try:
        raw = st.query_params.get(key)
    except Exception:
        return ""
    if isinstance(raw, (list, tuple)):
        raw = raw[-1] if raw else ""
    return str(raw or "").strip()


def _detail_href(event_id: str = "") -> str:
    params = {
        ROUTE_QUERY_SPORT: CFB_SPORT_LABEL,
        ROUTE_QUERY_MARKET: TOP_PICKS_MARKET,
    }
    if str(event_id or "").strip():
        params[TOP_PICK_DETAIL_QUERY] = str(event_id).strip()
    return "?" + urlencode(params)


def _history_html(row: dict, detail: dict) -> str:
    if detail.get("loading") is True:
        return '<div class="tp4-loading">Loading verified matchup history for this game only…</div>'
    history_rows = detail.get("history_rows") or []
    source = escape(str(detail.get("history_source") or "Verified history unavailable"))
    meetings = int(detail.get("meetings") or 0)
    if not history_rows:
        return (
            '<div class="tp4-nohist">No verified head-to-head game history is available '
            'for this matchup, so no historical result is being invented.</div>'
        )
    rendered = []
    away = escape(str(row.get("away") or "Away"))
    home = escape(str(row.get("home") or "Home"))
    for item in history_rows:
        date = escape(str(item.get("date") or "Date unavailable"))
        away_points = int(item.get("away_points") or 0)
        home_points = int(item.get("home_points") or 0)
        rendered.append(
            f'<div class="tp4-history-row"><span>{date} • {away} vs {home}</span>'
            f'<span>{away_points}-{home_points}</span></div>'
        )
    return (
        f'<div class="tp4-history-head"><span>{source}</span><span>{meetings} verified meetings</span></div>'
        f'<div class="tp4-history-list">{"".join(rendered)}</div>'
    )


def _loading_detail(row: dict) -> dict:
    return {
        "loading": True,
        "event_id": str(row.get("event_id") or ""),
        "why": details._why(row),
        "history_rows": [],
        "meetings": 0,
        "benefit": "Loading verified historical context for this selected matchup only.",
    }


def _detail_card(row: dict, detail: dict) -> str:
    rank = int(row["rank"])
    base_card = cards._card(row)
    why = escape(str(detail.get("why") or "Model explanation unavailable."))
    benefit = escape(str(detail.get("benefit") or "No verified historical benefit is claimed."))
    history = _history_html(row, detail)
    event_id = escape(str(detail.get("event_id") or row.get("event_id") or ""))
    collapse_href = escape(_detail_href(), quote=True)
    return f"""
    <details class="tp4-details" open data-testid="cfb-top-picks-details-{rank}" data-expanded="true">
      <summary aria-label="Close details for ranked pick {rank}">
        <a class="tp4-card-link" href="{collapse_href}" target="_self">{base_card}</a>
      </summary>
      <div class="tp4-panel" data-testid="cfb-top-picks-detail-panel-{rank}">
        <div class="tp4-grid">
          <div class="tp4-box">
            <h4>Why This Pick</h4>
            <p>{why}</p>
          </div>
          <div class="tp4-box">
            <h4>Actual Matchup History</h4>
            {history}
          </div>
          <div class="tp4-box">
            <h4>Benefits</h4>
            <p>{benefit}</p>
          </div>
        </div>
        <div class="tp4-audit">
          ESPN event <strong>{event_id or "unavailable"}</strong> • history projection weight <strong>0.0%</strong> •
          sportsbook projection weight <strong>0.0%</strong> • history cannot create, remove, or rerank a pick.
        </div>
      </div>
    </details>
    """


def _collapsed_card(row: dict) -> str:
    rank = int(row["rank"])
    event_id = str(row.get("event_id") or "").strip()
    href = escape(_detail_href(event_id), quote=True)
    base_card = cards._card(row)
    return (
        f'<a class="tp4-card-link" data-testid="cfb-top-picks-open-{rank}" '
        f'aria-label="Open Why History Benefits for ranked pick {rank}" '
        f'href="{href}" target="_self">{base_card}</a>'
    )


def _cards_html(picks: list[dict], selected_event: str = "", selected_detail: dict | None = None) -> str:
    selected_event = str(selected_event or "").strip()
    rendered = []
    for row in picks:
        event_id = str(row.get("event_id") or "").strip()
        if selected_event and event_id == selected_event and selected_detail is not None:
            rendered.append(_detail_card(row, selected_detail))
        else:
            rendered.append(_collapsed_card(row))
    return "".join(rendered)


def _page_html(
    picks: list[dict],
    diag: dict,
    slate_day: str,
    selected_event: str = "",
    selected_detail: dict | None = None,
) -> str:
    rendered = _cards_html(picks, selected_event, selected_detail)
    return f"""
    <section data-testid="cfb-top-picks-step4-root">
      <div class="tp2-step-marker" data-testid="cfb-top-picks-step1-marker">CFB_TOP_PICKS_STEP1_SHELL_ACTIVE</div>
      <div class="tp2-step-marker" data-testid="cfb-top-picks-step2-marker">CFB_TOP_PICKS_STEP2_COMPACT_CARDS_ACTIVE</div>
      <div class="tp2-step-marker" data-testid="cfb-top-picks-step3-marker">CFB_TOP_PICKS_STEP3_LIVE_RANKING_ACTIVE</div>
      <div class="tp2-step-marker" data-testid="cfb-top-picks-step4-marker">{PAGE_MARKER}</div>
      <div class="tp1-hero">
        <div>
          <h1 class="tp1-title">Top <span>Picks</span></h1>
          <div class="tp1-subtitle">10 Best Daily College Football Picks</div>
        </div>
        <div class="tp1-actions">
          <div class="tp1-segmented" data-testid="cfb-top-picks-market-tabs">
            <div class="tp1-chip active">Moneyline</div>
            <div class="tp1-chip">Spread</div>
            <div class="tp1-chip">Over/Under</div>
          </div>
          <div class="tp1-date" data-testid="cfb-top-picks-date">
            <span class="tp1-date-icon">▣</span><span>{escape(slate_day)}</span><span>⌄</span>
          </div>
        </div>
      </div>
      <div class="tp3-live" data-testid="cfb-top-picks-live-status">
        <span><strong>LIVE MODEL BOARD</strong> • {int(diag.get("games_analyzed") or 0)} games analyzed • {len(picks)} picks ranked</span>
        <span>Tap a matchup for Why • History • Benefits</span>
      </div>
      <div class="tp2-board" data-testid="cfb-top-picks-card-board">{rendered}</div>
    </section>
    """


def render_top_picks_page() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    with st.spinner("Building the verified College Football Top 10..."):
        picks, diag = engine.build_top_picks(limit=10)

    slate_day = str(diag.get("slate_date") or "Today")
    selected_event = _query_value(TOP_PICK_DETAIL_QUERY)
    selected_row = next(
        (row for row in picks if str(row.get("event_id") or "").strip() == selected_event),
        None,
    )

    board = st.empty()
    initial_detail = _loading_detail(selected_row) if selected_row is not None else None
    board.markdown(
        _page_html(picks, diag, slate_day, selected_event, initial_detail),
        unsafe_allow_html=True,
    )

    # Critical Step-4 performance contract: no history network request exists on
    # the initial board. Only an explicit tapped/selected event may fetch history.
    if selected_row is not None:
        with st.spinner("Loading verified matchup history..."):
            selected_detail = details.build_pick_detail(selected_row, slate_day)
        board.markdown(
            _page_html(picks, diag, slate_day, selected_event, selected_detail),
            unsafe_allow_html=True,
        )

    if not picks:
        st.markdown(
            '<div class="tp3-empty">No verified Top Picks are available for the current seven-day CFB slate window. Nothing was fabricated.</div>',
            unsafe_allow_html=True,
        )


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if str(market or "").strip() != "Top Picks":
        raise RuntimeError("CFB Top Picks Step 4 owns only the Top Picks route.")
    render_top_picks_page()


__all__ = [
    "CFB_SPORT_LABEL",
    "CSS",
    "HISTORY_PROJECTION_INFLUENCE",
    "LAYOUT_PREVIEW",
    "MODEL_VERSION",
    "PAGE_MARKER",
    "ROUTE_QUERY_MARKET",
    "ROUTE_QUERY_SPORT",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "TOP_PICK_DETAIL_QUERY",
    "TOP_PICKS_MARKET",
    "_cards_html",
    "_collapsed_card",
    "_detail_card",
    "_detail_href",
    "_history_html",
    "_loading_detail",
    "_page_html",
    "_query_value",
    "render_cfb_hub",
    "render_top_picks_page",
]
