"""CFB Top Picks V11 — professional decision-first presentation.

Additive presentation successor above V10. It keeps the frozen model, ranking,
probability, source data, market weighting, matchup research and market tabs
unchanged while reorganizing the customer surface into a fast decision layer
and a collapsed deep-research layer.
"""
from __future__ import annotations

from html import escape, unescape
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode

import streamlit as st

import cfb_top_picks_page_v10 as prior

MODEL_VERSION = "CFB TOP PICKS V11 • PROFESSIONAL DECISION SURFACE R1"
PAGE_MARKER = "CFB_TOP_PICKS_V11_PROFESSIONAL_DECISION_SURFACE_R1_ACTIVE"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
HISTORY_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SOURCE_DATA = False
MAY_MODIFY_OTHER_SPORTS = False

CSS = prior.CSS + r"""
<style id="cfb-top-picks-v11-professional-css">
[data-testid="cfb-top-picks-step4-root"]{max-width:1180px!important;padding-bottom:42px!important}
.tp1-hero{gap:14px!important;margin-bottom:12px!important}
.tp1-title{letter-spacing:-.035em!important}
.tp3-live{padding:10px 13px!important;border-radius:12px!important;background:rgba(4,18,29,.82)!important}
.tp2-board{gap:7px!important;margin-top:10px!important}
.tp2-card{border-color:rgba(109,198,255,.13)!important;box-shadow:none!important}
.tp2-card:hover{border-color:rgba(42,180,255,.42)!important}

.tp11-overview{margin:11px 0 13px;border:1px solid rgba(87,199,255,.20);border-radius:14px;background:linear-gradient(145deg,rgba(5,20,32,.94),rgba(5,14,24,.94));overflow:hidden}
.tp11-overview-head{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:11px 13px;border-bottom:1px solid rgba(255,255,255,.055)}
.tp11-overview-head h3{margin:0;color:#eef8ff;font-size:.82rem;letter-spacing:.02em}
.tp11-overview-head span{color:#7793a8;font-size:.61rem}
.tp11-rank-list{display:grid;grid-template-columns:1fr 1fr}
.tp11-rank-row{display:grid;grid-template-columns:38px minmax(0,1fr) 58px 78px;align-items:center;gap:8px;padding:9px 12px;color:inherit;text-decoration:none;border-bottom:1px solid rgba(255,255,255,.045);transition:background .14s ease}
.tp11-rank-row:nth-child(odd){border-right:1px solid rgba(255,255,255,.045)}
.tp11-rank-row:hover{background:rgba(23,139,205,.09)}
.tp11-rank{font-weight:950;color:#58caff;font-size:.78rem}
.tp11-rank-copy{min-width:0}
.tp11-rank-pick{display:block;color:#edf8ff;font-size:.73rem;font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tp11-rank-match{display:block;color:#7894a9;font-size:.56rem;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tp11-rank-prob{justify-self:end;color:#fff;font-size:.72rem;font-weight:950}
.tp11-tier{justify-self:end;border-radius:999px;padding:3px 6px;border:1px solid rgba(80,203,255,.25);color:#a7def8;font-size:.49rem;font-weight:950;letter-spacing:.04em;white-space:nowrap}
.tp11-tier.elite{color:#8cf0c4;border-color:rgba(89,231,171,.30);background:rgba(39,156,110,.10)}
.tp11-tier.strong{color:#a6ddff;background:rgba(35,145,205,.10)}
.tp11-tier.moderate{color:#ffe193;border-color:rgba(255,205,75,.28);background:rgba(160,120,24,.09)}

.tp11-decision{margin-bottom:11px;border:1px solid rgba(73,190,255,.25);border-radius:13px;background:linear-gradient(150deg,rgba(7,28,43,.96),rgba(5,18,29,.96));padding:12px}
.tp11-kicker{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:9px;color:#72d8ff;font-size:.61rem;font-weight:950;letter-spacing:.08em;text-transform:uppercase}
.tp11-kicker span:last-child{color:#6e8ba1;font-weight:800;letter-spacing:.02em;text-transform:none}
.tp11-metrics{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:7px}
.tp11-metric{min-width:0;padding:9px 7px;border:1px solid rgba(100,196,247,.13);border-radius:9px;background:rgba(9,28,42,.76);text-align:center}
.tp11-metric b{display:block;color:#fff;font-size:.87rem;line-height:1.1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tp11-metric span{display:block;color:#7290a6;font-size:.49rem;font-weight:850;letter-spacing:.035em;text-transform:uppercase;margin-top:5px}
.tp11-summary-grid{display:grid;grid-template-columns:1.35fr .85fr;gap:8px;margin-top:9px}
.tp11-summary-box{border:1px solid rgba(109,198,255,.11);border-radius:10px;background:rgba(6,19,30,.72);padding:10px}
.tp11-summary-box h4{margin:0 0 7px;color:#8fe2ff;font-size:.60rem;letter-spacing:.065em;text-transform:uppercase}
.tp11-reason{display:flex;gap:7px;color:#c9dce9;font-size:.67rem;line-height:1.38;margin-top:5px}
.tp11-reason:first-of-type{margin-top:0}.tp11-reason i{font-style:normal;color:#45cfff;font-weight:950}
.tp11-risk{color:#d8e1e8;font-size:.67rem;line-height:1.42;border-left:3px solid #f0ba49;padding-left:8px}
.tp11-sourcebar{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}
.tp11-source-pill{border:1px solid rgba(87,199,255,.17);border-radius:999px;padding:4px 7px;color:#89aabd;font-size:.54rem;background:rgba(10,32,46,.55)}
.tp11-change{margin-top:9px;padding:9px 10px;border-radius:9px;border:1px solid rgba(255,255,255,.07);background:rgba(7,18,28,.75)}
.tp11-change b{display:block;color:#dff6ff;font-size:.59rem;letter-spacing:.06em;text-transform:uppercase;margin-bottom:4px}
.tp11-change span{display:block;color:#849fb2;font-size:.62rem;line-height:1.4}
.tp11-history-note{margin:0 0 8px;padding:7px 9px;border-radius:8px;background:rgba(38,69,91,.18);color:#91a9bb;font-size:.59rem;line-height:1.35}
.tp11-deep{margin-top:8px;border:1px solid rgba(109,198,255,.12);border-radius:10px;background:rgba(3,13,22,.74);overflow:hidden}
.tp11-deep>summary{list-style:none;cursor:pointer;padding:11px 12px;color:#c8e8f8;font-size:.68rem;font-weight:900;display:flex;justify-content:space-between;align-items:center;gap:8px}
.tp11-deep>summary::-webkit-details-marker{display:none}.tp11-deep>summary:after{content:'+';font-size:1rem;color:#70cfff}.tp11-deep[open]>summary:after{content:'−'}
.tp11-deep-body{padding:0 2px 2px}.tp11-deep-body .tp4-grid{margin-top:0}
.tp11-marker{position:absolute;width:1px;height:1px;overflow:hidden;opacity:.001;pointer-events:none}

@media(max-width:900px){
 .tp11-rank-list{grid-template-columns:1fr}.tp11-rank-row:nth-child(odd){border-right:0}
 .tp11-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.tp11-metric:first-child{grid-column:span 2}
 .tp11-summary-grid{grid-template-columns:1fr}
}
@media(max-width:520px){
 .tp11-overview-head{align-items:flex-start;flex-direction:column}.tp11-rank-row{grid-template-columns:34px minmax(0,1fr) 48px}.tp11-tier{display:none}
 .tp11-decision{padding:10px}.tp11-metrics{gap:6px}.tp11-metric{padding:8px 5px}
 .tp4-panel{padding:8px!important;margin-left:2px!important;margin-right:2px!important}
 .tp8-source{padding:7px 0!important}
}
</style>
"""

_PANEL_RE = re.compile(
    r'(<div class="tp4-panel" data-testid="cfb-top-picks-detail-panel-(\d+)">)(.*?)(</div>\s*</details>)',
    re.IGNORECASE | re.DOTALL,
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _canonical_top_picks_href(href: Any) -> str:
    text = unescape(_clean(href))
    if not text.startswith("?"):
        return text
    pairs = parse_qsl(text[1:], keep_blank_values=True)
    params: list[tuple[str, str]] = [("sport", "cfb"), ("market", "top-picks")]
    for key, value in pairs:
        if key in {"sport", "market", "ks_sport", "ks_cfb_market"}:
            continue
        params.append((key, value))
    return "?" + urlencode(params)


def _canonicalize_top_picks_routes(html: str) -> str:
    def replace_href(match: re.Match[str]) -> str:
        href = unescape(match.group(1))
        if "ks_sport=" not in href and "ks_cfb_market=" not in href:
            return match.group(0)
        canonical = _canonical_top_picks_href(href)
        return f'href="{escape(canonical, quote=True)}"'

    return re.sub(r'href="([^"]+)"', replace_href, html)


def _build_pick_detail(row: dict, slate_day: str) -> dict:
    import cfb_top_picks_details_v5 as detail_provider

    return detail_provider.build_pick_detail(row, slate_day)


def _probability(row: dict) -> float:
    raw = row.get("probability_value")
    try:
        p = float(raw)
    except (TypeError, ValueError, OverflowError):
        try:
            p = float(row.get("probability") or 0) / 100.0
        except (TypeError, ValueError, OverflowError):
            p = 0.0
    return max(0.0, min(1.0, p))


def _pct(value: Any) -> str:
    try:
        n = float(value)
    except (TypeError, ValueError, OverflowError):
        return "—"
    if 0 <= n <= 1:
        n *= 100.0
    return f"{int(round(n))}%"


def _fair_price(probability: float) -> str:
    p = max(0.001, min(0.999, float(probability)))
    if abs(p - 0.5) < 1e-9:
        return "+100"
    if p > 0.5:
        price = -100.0 * p / (1.0 - p)
    else:
        price = 100.0 * (1.0 - p) / p
    value = int(round(price))
    return f"+{value}" if value > 0 else str(value)


def _market_implied(quote: Any) -> float | None:
    text = _clean(quote)
    if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", text):
        return None
    try:
        odds = float(text)
    except Exception:
        return None
    if odds == 0:
        return None
    if odds < 0:
        return (-odds) / ((-odds) + 100.0)
    return 100.0 / (odds + 100.0)


def _edge_text(row: dict) -> str:
    market_p = _market_implied(row.get("odds"))
    if market_p is None:
        return "Context only"
    edge = (_probability(row) - market_p) * 100.0
    return f"{edge:+.1f} pp"


def _tier(probability: float) -> tuple[str, str]:
    if probability >= 0.75:
        return "ELITE EDGE", "elite"
    if probability >= 0.65:
        return "STRONG EDGE", "strong"
    if probability >= 0.58:
        return "MODERATE", "moderate"
    return "WATCH", "watch"


def _top10_overview_html(picks: list[dict], selected_market: Any) -> str:
    market = prior._normalize_market(selected_market)
    rows: list[str] = []
    for row in picks[:10]:
        rank = int(row.get("rank") or 0)
        event_id = _clean(row.get("event_id"))
        href = escape(_canonical_top_picks_href(prior._detail_href_for_market(event_id, market)), quote=True)
        pick = escape(_clean(row.get("pick")) or "Verified pick")
        matchup = escape(f"{_clean(row.get('away'))} @ {_clean(row.get('home'))}")
        prob = _probability(row)
        tier, tier_cls = _tier(prob)
        rows.append(
            f'<a class="tp11-rank-row" href="{href}" target="_self" data-rank="{rank}">'
            f'<span class="tp11-rank">#{rank}</span><span class="tp11-rank-copy">'
            f'<span class="tp11-rank-pick">{pick}</span><span class="tp11-rank-match">{matchup}</span></span>'
            f'<span class="tp11-rank-prob">{int(round(prob * 100))}%</span>'
            f'<span class="tp11-tier {tier_cls}">{tier}</span></a>'
        )
    return (
        '<section class="tp11-overview" data-testid="cfb-top-picks-professional-overview">'
        '<div class="tp11-overview-head"><h3>Top 10 Decision Board</h3>'
        '<span>Scan first • tap any matchup for verified detail</span></div>'
        f'<div class="tp11-rank-list">{"".join(rows)}</div></section>'
    )


def _evidence_texts(detail: dict, key: str, limit: int) -> list[str]:
    result = detail.get("benefits_risks") or {}
    values = []
    for item in list(result.get(key) or []):
        text = _clean(item.get("text") if isinstance(item, dict) else item)
        if text:
            values.append(text)
        if len(values) >= limit:
            break
    return values


def _decision_snapshot_html(row: dict, detail: dict) -> str:
    rank = int(row.get("rank") or 0)
    prob = _probability(row)
    probability = f"{int(round(prob * 100))}%"
    reliability = _pct(row.get("reliability"))
    fair = _fair_price(prob)
    market_quote = _clean(row.get("odds")) or "—"
    edge = _edge_text(row)
    benefits = _evidence_texts(detail, "benefits", 3)
    if not benefits:
        benefits = ["Verified research is available below; no unsupported quick reason is being invented."]
    risks = _evidence_texts(detail, "risks", 1)
    risk = risks[0] if risks else "No additional verified risk claim is available in the current payload."
    reason_html = "".join(
        f'<div class="tp11-reason"><i>✓</i><span>{escape(text)}</span></div>' for text in benefits
    )
    audit = detail.get("source_freshness_audit") or {}
    fact_count = int(audit.get("material_fact_count") or 0)
    sources = list(audit.get("sources") or [])
    source_count = len(sources)
    tier, _ = _tier(prob)
    return f"""
    <section class="tp11-decision" data-testid="cfb-top-picks-decision-snapshot-{rank}">
      <div class="tp11-kicker"><span>Decision Snapshot</span><span>{escape(tier)} • verified model output</span></div>
      <div class="tp11-metrics">
        <div class="tp11-metric"><b>{probability}</b><span>Model Win Probability</span></div>
        <div class="tp11-metric"><b>{escape(reliability)}</b><span>Model Reliability</span></div>
        <div class="tp11-metric"><b>{escape(fair)}</b><span>Model Fair Price</span></div>
        <div class="tp11-metric"><b>{escape(market_quote)}</b><span>Market Quote</span></div>
        <div class="tp11-metric"><b>{escape(edge)}</b><span>Model vs Market Edge</span></div>
      </div>
      <div class="tp11-summary-grid">
        <div class="tp11-summary-box"><h4>3 Quick Reasons</h4>{reason_html}</div>
        <div class="tp11-summary-box"><h4>Key Risk</h4><div class="tp11-risk">{escape(risk)}</div></div>
      </div>
      <div class="tp11-sourcebar">
        <span class="tp11-source-pill">{fact_count} verified facts</span>
        <span class="tp11-source-pill">{source_count} source groups</span>
        <span class="tp11-source-pill">sportsbook projection weight 0.0%</span>
        <span class="tp11-source-pill">history projection weight 0.0%</span>
      </div>
      <div class="tp11-change"><b>What Would Change This Pick?</b>
        <span>A material change in verified team availability, updated model probability/reliability, or the applicable market threshold requires a fresh evaluation. Historical series and sportsbook context remain descriptive and cannot create or rerank this pick.</span>
      </div>
    </section>
    """


def _professionalize_detail(html: str, row: dict, detail: dict) -> str:
    rank = int(row.get("rank") or 0)
    match = _PANEL_RE.search(html)
    if match is None:
        raise RuntimeError("Top Picks V11 could not find the existing verified detail panel.")
    found_rank = int(match.group(2) or 0)
    if found_rank != rank:
        raise RuntimeError("Top Picks V11 detail panel identity mismatch.")
    legacy = match.group(3)
    replacement = (
        match.group(1)
        + _decision_snapshot_html(row, detail)
        + '<div class="tp11-history-note">Historical context is descriptive only • low predictive value for older meetings • projection weight 0.0%.</div>'
        + f'<details class="tp11-deep" data-testid="cfb-top-picks-deep-research-{rank}">'
        + '<summary><span>Deep verified research</span><span>Offense • Defense + Pace • History • Risks • Reasoning • Sources</span></summary>'
        + '<div class="tp11-deep-body">'
        + legacy
        + '</div></details>'
        + match.group(4)
    )
    return html[:match.start()] + replacement + html[match.end():]


def _page_html(
    picks: list[dict],
    diag: dict,
    slate_day: str,
    selected_event: str = "",
    selected_detail: dict | None = None,
    *,
    selected_market: Any = "MONEYLINE",
) -> str:
    market = prior._normalize_market(selected_market)
    html = prior._page_html(
        picks, diag, slate_day, selected_event, selected_detail,
        selected_market=market,
    )
    html = _canonicalize_top_picks_routes(html)
    board = '<div class="tp2-board" data-testid="cfb-top-picks-card-board">'
    if board not in html:
        raise RuntimeError("Top Picks V11 could not find the existing Top-10 board boundary.")
    html = html.replace(board, _top10_overview_html(picks, market) + board, 1)

    if selected_event and selected_detail is not None:
        selected = next(
            (row for row in picks if _clean(row.get("event_id")) == _clean(selected_event)),
            None,
        )
        if selected is not None:
            html = _professionalize_detail(html, selected, selected_detail)

    root = 'data-cfb-top-picks-visual="v5">'
    if root in html:
        html = html.replace(
            root,
            root + f'<div class="tp11-marker" data-testid="cfb-top-picks-v11-marker">{PAGE_MARKER}</div>',
            1,
        )
    elif PAGE_MARKER not in html:
        html = html.replace(
            '<section ',
            f'<section data-v11-marker="{PAGE_MARKER}" ',
            1,
        )
    return html


def render_top_picks_page() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    selected_market = prior._normalize_market(prior.base._query_value(prior.MARKET_QUERY))
    label = prior.MARKET_LABELS[selected_market]
    with st.spinner(f"Building the verified College Football {label} Top 10..."):
        picks, diag = prior.build_market_top_picks(selected_market, limit=10)

    slate_day = str(diag.get("slate_date") or "Today")
    selected_event = prior.base._query_value(prior.base.TOP_PICK_DETAIL_QUERY)
    selected_row = next((row for row in picks if _clean(row.get("event_id")) == selected_event), None)

    board = st.empty()
    initial = prior._loading_detail(selected_row) if selected_row is not None else None
    board.html(_page_html(picks, diag, slate_day, selected_event, initial, selected_market=selected_market))

    if selected_row is not None:
        with st.spinner("Loading verified matchup research..."):
            selected_detail = _build_pick_detail(selected_row, slate_day)
        board.html(_page_html(picks, diag, slate_day, selected_event, selected_detail, selected_market=selected_market))

    if not picks:
        st.markdown(
            f'<div class="tp3-empty">No verified {escape(label)} Top Picks are available for the current seven-day CFB slate window. Nothing was fabricated.</div>',
            unsafe_allow_html=True,
        )


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if _clean(market) != "Top Picks":
        raise RuntimeError("CFB Top Picks V11 owns only the Top Picks route.")
    render_top_picks_page()


__all__ = [
    "CSS", "HISTORY_PROJECTION_INFLUENCE", "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROBABILITY", "MAY_MODIFY_PROJECTION", "MAY_MODIFY_RANKING",
    "MAY_MODIFY_SOURCE_DATA", "MODEL_VERSION", "PAGE_MARKER",
    "SPORTSBOOK_PROJECTION_INFLUENCE", "_decision_snapshot_html", "_edge_text",
    "_fair_price", "_page_html", "_professionalize_detail", "_tier",
    "_top10_overview_html", "render_cfb_hub", "render_top_picks_page",
]
