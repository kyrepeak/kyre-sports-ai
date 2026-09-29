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
RESEARCH_STEP5_MARKER = "CFB_TOP_PICKS_RESEARCH_V2_STEP5_DEFENSE_PACE_ACTIVE"

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
.tp4-offense{margin-top:10px;border:1px solid rgba(76,211,255,.22);border-radius:11px;background:linear-gradient(145deg,#071827,#07121d);padding:11px}
.tp4-offense-head{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:9px}
.tp4-offense-head h4{margin:0;color:#72ddff;font-size:.74rem;letter-spacing:.04em;text-transform:uppercase}
.tp4-offense-head span{color:#6e879c;font-size:.61rem}
.tp4-offense-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.tp4-team-offense{border:1px solid rgba(109,198,255,.12);border-radius:9px;background:#0a1723;padding:9px}
.tp4-team-offense h5{margin:0 0 7px;color:#fff;font-size:.78rem}
.tp4-metric-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px}
.tp4-metric{min-width:0;padding:6px 4px;border:1px solid rgba(83,166,216,.18);border-radius:7px;background:#0d1e2c;text-align:center}
.tp4-metric b{display:block;color:#f5fbff;font-size:.75rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tp4-metric span{display:block;margin-top:3px;color:#7894aa;font-size:.54rem;text-transform:uppercase}
.tp4-reasoning{margin-top:8px;display:flex;flex-direction:column;gap:5px}
.tp4-reason{padding:6px 8px;border-left:3px solid #39d7ff;border-radius:6px;background:rgba(18,83,115,.16);color:#bed5e5;font-size:.7rem;line-height:1.35}
@media(max-width:900px){.tp4-offense-grid{grid-template-columns:1fr}.tp4-metric-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:900px){.tp4-grid{grid-template-columns:1fr}.tp4-panel{margin-left:4px;margin-right:4px}}
.tp5-defense{margin-top:10px;border:1px solid rgba(129,108,255,.25);border-radius:11px;background:linear-gradient(145deg,#111126,#09131e);padding:11px}
.tp5-defense-head{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:9px}
.tp5-defense-head h4{margin:0;color:#a9a2ff;font-size:.74rem;letter-spacing:.04em;text-transform:uppercase}
.tp5-defense-head span{color:#76899c;font-size:.61rem}
.tp5-defense-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.tp5-team{border:1px solid rgba(142,129,255,.14);border-radius:9px;background:#0d1723;padding:9px}
.tp5-team h5{margin:0 0 7px;color:#fff;font-size:.78rem}
.tp5-pace-chip{display:inline-block;margin-top:6px;padding:3px 7px;border-radius:999px;background:#151d31;border:1px solid rgba(160,151,255,.22);color:#b9b4ff;font-size:.55rem;font-weight:900;letter-spacing:.03em}
.tp5-reason{padding:6px 8px;border-left:3px solid #8f85ff;border-radius:6px;background:rgba(73,63,140,.16);color:#c9d1e0;font-size:.7rem;line-height:1.35}
@media(max-width:900px){.tp5-defense-grid{grid-template-columns:1fr}}
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
        status = str(detail.get("history_status") or "").strip()
        attempted = int(detail.get("source_count_attempted") or 0)
        if status == "VERIFIED_NO_HISTORY_AFTER_SOURCE_EXHAUSTION":
            return (
                '<div class="tp4-nohist" data-history-status="VERIFIED_NO_HISTORY_AFTER_SOURCE_EXHAUSTION">'
                f'No prior meeting was found after {attempted} independent history sources were checked. '
                'Nothing is being invented.</div>'
            )
        return (
            '<div class="tp4-nohist" data-history-status="SOURCE_CONFLICT_REVIEW">'
            'Matchup-history verification is incomplete or the sources could not verify a series. '
            '<strong>No “these teams never played” claim is being made.</strong></div>'
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
    verified_sources = int(detail.get("source_count_verified") or 0)
    attempted_sources = int(detail.get("source_count_attempted") or 0)
    return (
        f'<div class="tp4-history-head" data-history-status="VERIFIED_HISTORY">'
        f'<span>{source}</span><span>{meetings} verified meetings • {verified_sources}/{attempted_sources} sources verified</span></div>'
        f'<div class="tp4-history-list">{"".join(rendered)}</div>'
    )


def _metric_number(profile: dict, key: str):
    metrics = profile.get("metrics") or {}
    item = metrics.get(key) or {}
    return item.get("value") if isinstance(item, dict) else None


def _fmt_metric(value, *, pct: bool = False, digits: int = 1) -> str:
    try:
        number = float(value)
    except Exception:
        return "—"
    if pct:
        return f"{number * 100:.{digits}f}%"
    return f"{number:.{digits}f}"


def _offense_team_html(profile: dict, rank: int, side: str) -> str:
    team = escape(str(profile.get("team") or side.title()))
    ppg = _fmt_metric(_metric_number(profile, "points_per_game"))
    recent = _fmt_metric(_metric_number(profile, "recent_scoring_avg"))
    ypp = _fmt_metric(_metric_number(profile, "yards_per_play"), digits=2)
    pass_ypg = _fmt_metric(_metric_number(profile, "pass_yards_per_game"))
    rush_ypg = _fmt_metric(_metric_number(profile, "rush_yards_per_game"))
    rz = _fmt_metric(_metric_number(profile, "red_zone_td_rate"), pct=True)
    metrics = profile.get("metrics") or {}
    explosive = metrics.get("explosive_efficiency_proxy") or {}
    explosive_label = escape(str(explosive.get("label") or "UNAVAILABLE"))
    return f"""
    <div class="tp4-team-offense" data-testid="cfb-top-picks-offense-{side}-{rank}">
      <h5>{team}</h5>
      <div class="tp4-metric-grid">
        <div class="tp4-metric"><b>{ppg}</b><span>PPG</span></div>
        <div class="tp4-metric"><b>{recent}</b><span>Recent PPG</span></div>
        <div class="tp4-metric"><b>{ypp}</b><span>Yards / Play</span></div>
        <div class="tp4-metric"><b>{pass_ypg}</b><span>Pass YPG</span></div>
        <div class="tp4-metric"><b>{rush_ypg}</b><span>Rush YPG</span></div>
        <div class="tp4-metric"><b>{rz}</b><span>RZ TD Rate</span></div>
        <div class="tp4-metric"><b>{explosive_label}</b><span>Explosive-Eff Proxy</span></div>
      </div>
    </div>
    """


def _offense_html(row: dict, detail: dict) -> str:
    research = detail.get("offense_research") or {}
    rank = int(row.get("rank") or 0)
    if not research or research.get("status") == "IDENTITY_UNAVAILABLE":
        return (
            '<div class="tp4-offense" data-testid="cfb-top-picks-offense-research-unavailable">'
            '<div class="tp4-offense-head"><h4>Offensive Scoring Research</h4>'
            '<span>Verified offense data unavailable</span></div></div>'
        )
    away = research.get("away") or {}
    home = research.get("home") or {}
    reasoning = list(research.get("reasoning") or detail.get("offense_reasoning") or [])
    reason_html = "".join(
        f'<div class="tp4-reason">{escape(str(item))}</div>'
        for item in reasoning
        if str(item or "").strip()
    )
    status = escape(str(research.get("status") or "PARTIAL"))
    return f"""
    <div class="tp4-offense" data-testid="cfb-top-picks-offense-research-{rank}" data-offense-status="{status}">
      <div class="tp4-offense-head">
        <h4>Offensive Scoring Research</h4>
        <span>ESPN exact-ID + NCAA field router • projection weight 0.0%</span>
      </div>
      <div class="tp4-offense-grid">
        {_offense_team_html(away, rank, "away")}
        {_offense_team_html(home, rank, "home")}
      </div>
      <div class="tp4-reasoning">{reason_html}</div>
    </div>
    """


def _defense_pace_team_html(profile: dict, rank: int, side: str) -> str:
    team = escape(str(profile.get("team") or side.title()))
    pa = _fmt_metric(_metric_number(profile, "points_allowed_per_game"))
    recent_pa = _fmt_metric(_metric_number(profile, "recent_points_allowed_avg"))
    yppa = _fmt_metric(_metric_number(profile, "yards_per_play_allowed"), digits=2)
    pass_allowed = _fmt_metric(_metric_number(profile, "pass_yards_allowed_per_game"))
    rush_allowed = _fmt_metric(_metric_number(profile, "rush_yards_allowed_per_game"))
    rz_allowed = _fmt_metric(_metric_number(profile, "red_zone_td_rate_allowed"), pct=True)
    plays = _fmt_metric(_metric_number(profile, "plays_per_game"))
    spp = _fmt_metric(_metric_number(profile, "seconds_per_play"), digits=2)
    metrics = profile.get("metrics") or {}
    pace = metrics.get("pace_index") or {}
    pace_label = escape(str(pace.get("label") or "DATA LIMITED"))
    explosive = metrics.get("explosive_susceptibility_proxy") or {}
    explosive_label = escape(str(explosive.get("label") or "UNAVAILABLE"))
    return f"""
    <div class="tp5-team" data-testid="cfb-top-picks-defense-pace-{side}-{rank}">
      <h5>{team}</h5>
      <div class="tp4-metric-grid">
        <div class="tp4-metric"><b>{pa}</b><span>Allowed / Game</span></div>
        <div class="tp4-metric"><b>{recent_pa}</b><span>Recent Allowed</span></div>
        <div class="tp4-metric"><b>{yppa}</b><span>YPP Allowed</span></div>
        <div class="tp4-metric"><b>{pass_allowed}</b><span>Pass YPG Allowed</span></div>
        <div class="tp4-metric"><b>{rush_allowed}</b><span>Rush YPG Allowed</span></div>
        <div class="tp4-metric"><b>{rz_allowed}</b><span>RZ TD Allowed</span></div>
        <div class="tp4-metric"><b>{plays}</b><span>Plays / Game</span></div>
        <div class="tp4-metric"><b>{spp}</b><span>Seconds / Play</span></div>
        <div class="tp4-metric"><b>{explosive_label}</b><span>Explosive Suscept.</span></div>
      </div>
      <span class="tp5-pace-chip">{pace_label} PACE</span>
    </div>
    """


def _defense_pace_html(row: dict, detail: dict) -> str:
    research = detail.get("defense_pace_research") or {}
    rank = int(row.get("rank") or 0)
    if detail.get("loading") is True:
        return (
            '<div class="tp5-defense" data-testid="cfb-top-picks-defense-pace-loading">'
            '<div class="tp5-defense-head"><h4>Defense + Pace Research</h4>'
            '<span>Loading verified selected-game research…</span></div></div>'
        )
    if not research or research.get("status") == "IDENTITY_UNAVAILABLE":
        return (
            '<div class="tp5-defense" data-testid="cfb-top-picks-defense-pace-unavailable">'
            '<div class="tp5-defense-head"><h4>Defense + Pace Research</h4>'
            '<span>Verified defense/pace data unavailable</span></div></div>'
        )
    away = research.get("away") or {}
    home = research.get("home") or {}
    reasoning = list(research.get("reasoning") or detail.get("defense_pace_reasoning") or [])
    reason_html = "".join(
        f'<div class="tp5-reason">{escape(str(item))}</div>'
        for item in reasoning
        if str(item or "").strip()
    )
    status = escape(str(research.get("status") or "PARTIAL"))
    return f"""
    <div class="tp5-defense" data-testid="cfb-top-picks-defense-pace-research-{rank}" data-defense-pace-status="{status}">
      <div class="tp5-defense-head">
        <h4>Defense + Pace Research</h4>
        <span>ESPN exact-ID + NCAA field router • projection weight 0.0%</span>
      </div>
      <div class="tp5-defense-grid">
        {_defense_pace_team_html(away, rank, "away")}
        {_defense_pace_team_html(home, rank, "home")}
      </div>
      <div class="tp4-reasoning">{reason_html}</div>
    </div>
    """


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
    offense = _offense_html(row, detail)
    defense_pace = _defense_pace_html(row, detail)
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
        {offense}
        {defense_pace}
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
      <div class="tp2-step-marker" data-testid="cfb-top-picks-research-v2-step5-marker">{RESEARCH_STEP5_MARKER}</div>
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
        <span>Tap a matchup for Why • Research • History • Benefits</span>
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
    "RESEARCH_STEP5_MARKER",
    "ROUTE_QUERY_SPORT",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "TOP_PICK_DETAIL_QUERY",
    "TOP_PICKS_MARKET",
    "_cards_html",
    "_collapsed_card",
    "_detail_card",
    "_detail_href",
    "_defense_pace_html",
    "_defense_pace_team_html",
    "_history_html",
    "_loading_detail",
    "_page_html",
    "_query_value",
    "render_cfb_hub",
    "render_top_picks_page",
]
