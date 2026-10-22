"""CFB Top Picks V12 — Kyre Sports API decision intelligence surface."""
from __future__ import annotations

from datetime import datetime
from html import escape
import json
import os
from typing import Any, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import streamlit as st

MODEL_VERSION = "CFB TOP PICKS V12 • S-TIER KYRE API PAGE1"
PAGE_MARKER = "CFB_TOP_PICKS_V12_STIER_KYRE_API_PAGE1_ACTIVE"
PAGE1_ENDPOINT = "/api/v1/cfb/top-picks/page1"
KYRE_SPORTS_API_BASE_URL = os.getenv(
    "KYRE_SPORTS_API_BASE_URL", "https://kyre-sports-api.vercel.app"
).rstrip("/")

CSS = r"""
<style id="cfb-top-picks-v12-css">
:root{--tp-blue:#23adff;--tp-cyan:#78dcff;--tp-bg:#050c14;--tp-panel:#071522;--tp-border:rgba(86,194,255,.18);--tp-muted:#7994a8;--tp-green:#71e6b0;--tp-gold:#ffd071;--tp-red:#ff7d8e}
[data-testid="stAppViewContainer"]{background:radial-gradient(circle at 70% -10%,rgba(24,133,209,.13),transparent 36%),#060b12}
[data-testid="cfb-top-picks-v12-root"]{max-width:1180px;margin:0 auto;padding:10px 2px 48px;color:#edf8ff;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.tp12-shell{border:1px solid var(--tp-border);border-radius:22px;background:linear-gradient(145deg,rgba(8,27,43,.96),rgba(4,13,23,.98));box-shadow:0 22px 70px rgba(0,0,0,.22);overflow:hidden}
.tp12-head{padding:23px 24px 18px;border-bottom:1px solid rgba(255,255,255,.06)}
.tp12-brand{display:flex;align-items:center;justify-content:space-between;gap:18px;margin-bottom:18px}.tp12-brand b{font-size:.76rem;letter-spacing:.16em}.tp12-live{display:inline-flex;align-items:center;gap:7px;color:#a8c5d8;font-size:.62rem;font-weight:800}.tp12-live:before{content:"";width:7px;height:7px;border-radius:50%;background:var(--tp-green);box-shadow:0 0 14px rgba(113,230,176,.8)}
.tp12-title-row{display:flex;align-items:flex-end;justify-content:space-between;gap:20px}.tp12-title h1{margin:0;font-size:2.35rem;line-height:1;letter-spacing:-.055em;font-weight:950}.tp12-title h1 span{color:var(--tp-blue)}.tp12-title p{margin:8px 0 0;color:#93acc0;font-size:.82rem}.tp12-date{border:1px solid rgba(99,205,255,.22);border-radius:12px;padding:9px 12px;background:rgba(7,25,39,.78);font-size:.70rem;font-weight:900;white-space:nowrap}
.tp12-tabs{display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px;margin-top:18px;padding:4px;border:1px solid rgba(94,191,246,.14);background:rgba(2,10,18,.56);border-radius:13px}.tp12-tab{padding:9px 10px;text-align:center;border-radius:9px;color:#708b9f;font-size:.67rem;font-weight:900}.tp12-tab.active{color:white;background:linear-gradient(180deg,#1c9ff1,#0d77c9);box-shadow:0 5px 22px rgba(20,151,232,.22)}
.tp12-integrity{display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:11px 24px;border-bottom:1px solid rgba(255,255,255,.055);background:rgba(5,18,29,.88)}.tp12-integrity b{font-size:.64rem;letter-spacing:.075em;color:#87ddff}.tp12-pill{border:1px solid rgba(99,205,255,.15);border-radius:999px;padding:4px 8px;color:#8ba9bc;font-size:.53rem;font-weight:850}.tp12-pill.good{color:var(--tp-green);border-color:rgba(113,230,176,.25);background:rgba(44,148,104,.08)}
.tp12-intel{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;padding:14px 24px 3px}.tp12-kpi{padding:12px;border:1px solid rgba(83,185,244,.13);border-radius:12px;background:rgba(6,22,35,.74)}.tp12-kpi span{display:block;color:#718da1;font-size:.49rem;font-weight:900;letter-spacing:.07em;text-transform:uppercase}.tp12-kpi b{display:block;margin-top:5px;color:#f1f9ff;font-size:.91rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.tp12-kpi em{display:block;margin-top:3px;color:#6fa2bf;font-style:normal;font-size:.52rem}
.tp12-board{padding:14px 24px 24px}.tp12-board-head{display:flex;justify-content:space-between;align-items:center;gap:14px;margin:2px 0 10px}.tp12-board-head h3{margin:0;font-size:.79rem;letter-spacing:.03em}.tp12-board-head span{color:#728da0;font-size:.55rem}
.tp12-card{margin-top:8px;border:1px solid rgba(75,183,246,.14);border-radius:14px;background:linear-gradient(140deg,rgba(7,24,38,.97),rgba(5,17,28,.98));overflow:hidden}.tp12-card.top{border-color:rgba(42,178,255,.39);box-shadow:0 10px 35px rgba(0,105,177,.08)}.tp12-card-head{display:grid;grid-template-columns:46px minmax(0,1.35fr) minmax(0,.78fr) 80px;gap:10px;align-items:center;padding:13px 14px}.tp12-rank{width:34px;height:34px;border:2px solid var(--tp-blue);border-radius:50%;display:flex;align-items:center;justify-content:center;color:white;font-size:.72rem;font-weight:950}.tp12-match{min-width:0}.tp12-match b{display:block;font-size:.80rem;color:#f2f8fc;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.tp12-match span{display:block;margin-top:3px;color:#6f8da3;font-size:.54rem}.tp12-pick{min-width:0}.tp12-market{display:inline-block;border:1px solid rgba(42,178,255,.55);border-radius:7px;padding:3px 7px;color:#9ee5ff;font-size:.46rem;font-weight:950;letter-spacing:.08em}.tp12-pick b{display:block;margin-top:6px;font-size:.76rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.tp12-model{text-align:right}.tp12-model strong{display:block;color:white;font-size:1rem}.tp12-model span{color:#65cfff;font-size:.49rem;font-weight:900;text-transform:uppercase;letter-spacing:.055em}
.tp12-metrics{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));border-top:1px solid rgba(255,255,255,.055);border-bottom:1px solid rgba(255,255,255,.045)}.tp12-metric{padding:9px 11px;border-right:1px solid rgba(255,255,255,.045)}.tp12-metric:last-child{border-right:0}.tp12-metric span{display:block;color:#6c879b;font-size:.45rem;font-weight:900;letter-spacing:.065em;text-transform:uppercase}.tp12-metric b{display:block;margin-top:4px;color:#eaf7ff;font-size:.66rem}.tp12-edge-positive{color:var(--tp-green)!important}.tp12-edge-negative{color:var(--tp-red)!important}
.tp12-reason{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:9px 12px}.tp12-reason-copy{min-width:0}.tp12-reason-copy small{display:block;color:#63cfff;font-size:.45rem;font-weight:950;letter-spacing:.075em}.tp12-reason-copy p{margin:4px 0 0;color:#9eb5c5;font-size:.58rem;line-height:1.38}.tp12-tier{align-self:center;border-radius:999px;padding:4px 8px;border:1px solid rgba(113,230,176,.27);color:var(--tp-green);font-size:.45rem;font-weight:950;white-space:nowrap}.tp12-tier.watch{color:var(--tp-gold);border-color:rgba(255,208,113,.28)}.tp12-source{color:#587589;font-size:.47rem;margin-top:4px}
.tp12-empty{margin:14px 24px 24px;padding:16px;border:1px solid rgba(255,125,142,.24);border-radius:12px;background:rgba(93,22,36,.12);color:#ffb2bd;font-size:.7rem;line-height:1.45}
@media(max-width:760px){.tp12-head{padding:18px 14px 14px}.tp12-title-row{align-items:flex-start;flex-direction:column}.tp12-title h1{font-size:1.95rem}.tp12-tabs{margin-top:14px}.tp12-integrity,.tp12-intel,.tp12-board{padding-left:14px;padding-right:14px}.tp12-intel{grid-template-columns:1fr 1fr}.tp12-card-head{grid-template-columns:38px minmax(0,1fr) 65px}.tp12-pick{grid-column:2/4}.tp12-metrics{grid-template-columns:1fr 1fr}.tp12-metric{border-bottom:1px solid rgba(255,255,255,.04)}.tp12-metric:nth-child(5){grid-column:1/3}.tp12-reason{align-items:flex-start;flex-direction:column}.tp12-board-head{align-items:flex-start;flex-direction:column}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any) -> float | None:
    try:
        n = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return n if n == n else None


def _money(value: Any) -> str:
    n = _number(value)
    if n is None:
        return "—"
    value_i = int(round(n))
    return f"+{value_i}" if value_i > 0 else str(value_i)


def _pct(value: Any) -> str:
    n = _number(value)
    if n is None:
        return "—"
    if 0 <= n <= 1:
        n *= 100.0
    return f"{n:.1f}%"


def _edge(value: Any) -> str:
    n = _number(value)
    return "—" if n is None else f"{n:+.1f} pp"


def _stamp(value: Any) -> str:
    text = _clean(value)
    if not text:
        return "Fresh timestamp unavailable"
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt.strftime("Updated %b %d • %I:%M %p UTC").replace(" 0", " ")
    except Exception:
        return f"Updated {text}"


def _query_date() -> str | None:
    try:
        raw = st.query_params.get("top_pick_date")
    except Exception:
        raw = None
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    text = _clean(raw)
    return text or None


@st.cache_data(ttl=75, show_spinner=False)
def _load_page_payload(game_date: str | None = None) -> dict[str, Any]:
    query: dict[str, str] = {"limit": "10"}
    if game_date:
        query["game_date"] = game_date
    url = f"{KYRE_SPORTS_API_BASE_URL}{PAGE1_ENDPOINT}?{urlencode(query)}"
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "KyreSportsAI/1.0"})
    with urlopen(request, timeout=45) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if _clean(payload.get("service")) != "Kyre Sports API":
        raise RuntimeError("Top Picks gateway returned an invalid service contract.")
    return dict(payload)


def _tier_class(tier: str) -> str:
    return "watch" if tier in {"MARKET PENDING", "MARKET AHEAD", "LEAN"} else ""


def _card_html(row: Mapping[str, Any]) -> str:
    rank = int(row.get("rank") or 0)
    away = escape(_clean(row.get("away")) or "Away")
    home = escape(_clean(row.get("home")) or "Home")
    pick = escape(_clean(row.get("pick")) or "Verified selection")
    kickoff = escape(_stamp(row.get("kickoff_iso")).replace("Updated ", "Kickoff "))
    probability = escape(_pct(row.get("model_probability")))
    reliability = escape(_pct(row.get("model_reliability")))
    fair = escape(_money(row.get("model_fair_price")))
    implied = escape(_pct(row.get("market_implied_probability")))
    edge_value = _number(row.get("model_edge_pp"))
    edge = escape(_edge(edge_value))
    edge_class = "tp12-edge-positive" if edge_value is not None and edge_value >= 0 else "tp12-edge-negative"
    best = row.get("best_price") if isinstance(row.get("best_price"), Mapping) else None
    best_text = escape(_money(best.get("price"))) if best else "—"
    book = escape(_clean(best.get("sportsbook"))) if best else "Market unavailable"
    updated = escape(_stamp(best.get("updated_at"))) if best else "No quote fabricated"
    tier = escape(_clean(row.get("edge_tier")) or "MARKET PENDING")
    tier_class = _tier_class(_clean(row.get("edge_tier")))
    reason = escape(_clean(row.get("why")) or "No unsupported quick reason was generated.")
    quote_count = int(row.get("sportsbook_quote_count") or 0)
    top_class = " top" if rank <= 3 else ""
    return f"""
    <article class="tp12-card{top_class}" data-testid="cfb-top-picks-v12-card-{rank}" data-event-id="{escape(_clean(row.get('event_id')))}">
      <div class="tp12-card-head">
        <div class="tp12-rank">{rank}</div>
        <div class="tp12-match"><b>{away} <span style="color:#58798f">@</span> {home}</b><span>{kickoff}</span></div>
        <div class="tp12-pick"><span class="tp12-market">MONEYLINE</span><b>{pick}</b></div>
        <div class="tp12-model"><strong>{probability}</strong><span>Model</span></div>
      </div>
      <div class="tp12-metrics">
        <div class="tp12-metric"><span>Best Price</span><b>{best_text} • {book}</b></div>
        <div class="tp12-metric"><span>Market Implied</span><b>{implied}</b></div>
        <div class="tp12-metric"><span>Market Edge</span><b class="{edge_class}">{edge}</b></div>
        <div class="tp12-metric"><span>Model Fair</span><b>{fair}</b></div>
        <div class="tp12-metric"><span>Reliability</span><b>{reliability}</b></div>
      </div>
      <div class="tp12-reason">
        <div class="tp12-reason-copy"><small>WHY THIS PICK</small><p>{reason}</p><div class="tp12-source">{quote_count} exact sportsbook quote(s) • {updated}</div></div>
        <span class="tp12-tier {tier_class}">{tier}</span>
      </div>
    </article>
    """


def _page_html(payload: Mapping[str, Any]) -> str:
    picks = [dict(row) for row in list(payload.get("picks") or []) if isinstance(row, Mapping)]
    diag = dict(payload.get("diagnostics") or {})
    slate_day = escape(_clean(payload.get("selected_date")) or "Verified slate")
    generated = _stamp(payload.get("generated_at_utc"))
    complete = bool(diag.get("complete_top_ten")) and len(picks) == 10
    integrity = "10/10 UNIQUE • VERIFIED" if complete else f"{len(picks)}/10 QUALIFIED"

    top = picks[0] if picks else {}
    top_pick = escape(_clean(top.get("pick")) or "—")
    top_prob = escape(_pct(top.get("model_probability")))
    edge_rows = [row for row in picks if _number(row.get("model_edge_pp")) is not None]
    best_edge_row = max(edge_rows, key=lambda row: float(row.get("model_edge_pp"))) if edge_rows else {}
    best_edge = escape(_edge(best_edge_row.get("model_edge_pp"))) if best_edge_row else "—"
    best_edge_pick = escape(_clean(best_edge_row.get("pick")) or "No market edge available")
    priced = sum(1 for row in picks if isinstance(row.get("best_price"), Mapping))
    cards = "".join(_card_html(row) for row in picks)

    return f"""
    <section data-testid="cfb-top-picks-v12-root" data-page-marker="{PAGE_MARKER}">
      <div class="tp12-shell">
        <header class="tp12-head">
          <div class="tp12-brand"><b>KYRE SPORTS AI</b><span class="tp12-live">KYRE SPORTS API LIVE</span></div>
          <div class="tp12-title-row"><div class="tp12-title"><h1>Top <span>Picks</span></h1><p>10 strongest verified College Football moneyline decisions</p></div><div class="tp12-date">◫ {slate_day}</div></div>
          <div class="tp12-tabs"><div class="tp12-tab active">Moneyline</div><div class="tp12-tab">Spread</div><div class="tp12-tab">Over/Under</div></div>
        </header>
        <div class="tp12-integrity"><b>SLATE INTEGRITY</b><span class="tp12-pill {'good' if complete else ''}">{integrity}</span><span class="tp12-pill">Canonical NCAA game identity</span><span class="tp12-pill">No blended sportsbook prices</span><span class="tp12-pill">Missing data stays missing</span></div>
        <div class="tp12-intel">
          <div class="tp12-kpi"><span>Highest Model</span><b>{top_pick} • {top_prob}</b><em>Rank #1</em></div>
          <div class="tp12-kpi"><span>Best Market Edge</span><b>{best_edge}</b><em>{best_edge_pick}</em></div>
          <div class="tp12-kpi"><span>Market Coverage</span><b>{priced}/{len(picks) if picks else 10} priced</b><em>Exact book-specific quotes</em></div>
          <div class="tp12-kpi"><span>Last Refresh</span><b>{escape(generated.replace('Updated ', ''))}</b><em>Fresh Kyre gateway payload</em></div>
        </div>
        <main class="tp12-board"><div class="tp12-board-head"><h3>Top 10 Decision Board</h3><span>Model probability • market value • price provenance</span></div>{cards}</main>
        {'' if picks else '<div class="tp12-empty">No fully verified Top Picks are available for this slate. The page will not invent replacement games, prices, or probabilities.</div>'}
      </div>
    </section>
    """


def render_top_picks_page() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    try:
        with st.spinner("Loading verified CFB Top Picks from Kyre Sports API..."):
            payload = _load_page_payload(_query_date())
    except Exception as exc:
        st.error(f"Kyre Sports API Top Picks is temporarily unavailable ({type(exc).__name__}). No fallback data was substituted.")
        return
    st.markdown(_page_html(payload), unsafe_allow_html=True)
    diagnostics = dict(payload.get("diagnostics") or {})
    if not diagnostics.get("complete_top_ten"):
        st.warning("The current slate has fewer than 10 fully model-ready unique selections. Missing entries are intentionally not fabricated.")


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if _clean(market) != "Top Picks":
        raise RuntimeError("CFB Top Picks V12 owns only the Top Picks route.")
    render_top_picks_page()


__all__ = [
    "KYRE_SPORTS_API_BASE_URL",
    "MODEL_VERSION",
    "PAGE1_ENDPOINT",
    "PAGE_MARKER",
    "render_cfb_hub",
    "render_top_picks_page",
]
