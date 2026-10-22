"""CFB Top Picks V13 — S-tier decision intelligence over frozen V1 ranking."""
from __future__ import annotations

from datetime import datetime
from html import escape
import json
import os
from typing import Any, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import streamlit as st

MODEL_VERSION = "CFB TOP PICKS V13 • S-TIER DECISION INTELLIGENCE"
PAGE_MARKER = "CFB_TOP_PICKS_V13_STIER_DECISION_INTELLIGENCE_ACTIVE"
PAGE1_ENDPOINT = "/api/v2/cfb/top-picks/page1"
KYRE_SPORTS_API_BASE_URL = os.getenv(
    "KYRE_SPORTS_API_BASE_URL", "https://kyre-sports-api.vercel.app"
).rstrip("/")

FILTERS = (
    ("all", "All"),
    ("value", "Value"),
    ("high-confidence", "High Confidence"),
    ("market-movers", "Market Movers"),
)

CSS = r"""
<style id="cfb-top-picks-v13-css">
:root{--tp-blue:#27afff;--tp-cyan:#7de0ff;--tp-bg:#050c14;--tp-panel:#071522;--tp-border:rgba(86,194,255,.19);--tp-muted:#7994a8;--tp-green:#71e6b0;--tp-gold:#ffd071;--tp-red:#ff7d8e}
[data-testid="stAppViewContainer"]{background:radial-gradient(circle at 70% -10%,rgba(24,133,209,.14),transparent 36%),#060b12}
[data-testid="cfb-top-picks-v13-root"]{max-width:1180px;margin:0 auto;padding:10px 2px 48px;color:#edf8ff;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.tp13-shell{border:1px solid var(--tp-border);border-radius:22px;background:linear-gradient(145deg,rgba(8,27,43,.97),rgba(4,13,23,.99));box-shadow:0 22px 70px rgba(0,0,0,.25);overflow:hidden}
.tp13-head{padding:23px 24px 18px;border-bottom:1px solid rgba(255,255,255,.06)}
.tp13-brand{display:flex;align-items:center;justify-content:space-between;gap:18px;margin-bottom:18px}.tp13-brand b{font-size:.76rem;letter-spacing:.16em}.tp13-live{display:inline-flex;align-items:center;gap:7px;color:#a8c5d8;font-size:.62rem;font-weight:800}.tp13-live:before{content:"";width:7px;height:7px;border-radius:50%;background:var(--tp-green);box-shadow:0 0 14px rgba(113,230,176,.8)}
.tp13-title-row{display:flex;align-items:flex-end;justify-content:space-between;gap:20px}.tp13-title h1{margin:0;font-size:2.35rem;line-height:1;letter-spacing:-.055em;font-weight:950}.tp13-title h1 span{color:var(--tp-blue)}.tp13-title p{margin:8px 0 0;color:#93acc0;font-size:.82rem}.tp13-date{border:1px solid rgba(99,205,255,.22);border-radius:12px;padding:9px 12px;background:rgba(7,25,39,.78);font-size:.70rem;font-weight:900;white-space:nowrap}
.tp13-tabs{display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px;margin-top:18px;padding:4px;border:1px solid rgba(94,191,246,.14);background:rgba(2,10,18,.56);border-radius:13px}.tp13-tab{padding:9px 10px;text-align:center;border-radius:9px;color:#708b9f;font-size:.67rem;font-weight:900}.tp13-tab.active{color:white;background:linear-gradient(180deg,#1c9ff1,#0d77c9);box-shadow:0 5px 22px rgba(20,151,232,.22)}
.tp13-integrity{display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:11px 24px;border-bottom:1px solid rgba(255,255,255,.055);background:rgba(5,18,29,.88)}.tp13-integrity b{font-size:.64rem;letter-spacing:.075em;color:#87ddff}.tp13-pill{border:1px solid rgba(99,205,255,.15);border-radius:999px;padding:4px 8px;color:#8ba9bc;font-size:.53rem;font-weight:850}.tp13-pill.good{color:var(--tp-green);border-color:rgba(113,230,176,.25);background:rgba(44,148,104,.08)}
.tp13-filter{display:flex;flex-wrap:wrap;gap:7px;padding:12px 24px 0}.tp13-filter a{text-decoration:none;border:1px solid rgba(99,205,255,.15);border-radius:999px;padding:6px 10px;color:#7f9caf;font-size:.55rem;font-weight:900}.tp13-filter a.active{color:#fff;border-color:rgba(44,178,255,.55);background:rgba(21,137,210,.22)}
.tp13-intel{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;padding:14px 24px 3px}.tp13-kpi{padding:12px;border:1px solid rgba(83,185,244,.13);border-radius:12px;background:rgba(6,22,35,.74)}.tp13-kpi span{display:block;color:#718da1;font-size:.49rem;font-weight:900;letter-spacing:.07em;text-transform:uppercase}.tp13-kpi b{display:block;margin-top:5px;color:#f1f9ff;font-size:.91rem}.tp13-kpi em{display:block;margin-top:3px;color:#6fa2bf;font-style:normal;font-size:.52rem}
.tp13-board{padding:14px 24px 24px}.tp13-board-head{display:flex;justify-content:space-between;align-items:center;gap:14px;margin:2px 0 10px}.tp13-board-head h3{margin:0;font-size:.79rem;letter-spacing:.03em}.tp13-board-head span{color:#728da0;font-size:.55rem}
.tp13-card{margin-top:10px;border:1px solid rgba(75,183,246,.15);border-radius:16px;background:linear-gradient(140deg,rgba(7,24,38,.98),rgba(5,17,28,.99));overflow:hidden}.tp13-card.top{border-color:rgba(42,178,255,.42);box-shadow:0 10px 35px rgba(0,105,177,.09)}
.tp13-card-head{display:grid;grid-template-columns:42px minmax(0,1.25fr) minmax(0,.9fr) 94px;gap:11px;align-items:center;padding:14px}.tp13-rank{width:34px;height:34px;border:2px solid var(--tp-blue);border-radius:50%;display:flex;align-items:center;justify-content:center;color:white;font-size:.72rem;font-weight:950}
.tp13-match{min-width:0}.tp13-teamline{display:flex;align-items:center;gap:7px}.team-logo{width:24px;height:24px;object-fit:contain;border-radius:50%;background:rgba(255,255,255,.04)}.tp13-match b{font-size:.79rem;color:#f2f8fc}.tp13-match small{display:block;margin:4px 0;color:#4e6c80}.tp13-match span{display:block;color:#6f8da3;font-size:.54rem}
.tp13-pick{min-width:0}.tp13-market{display:inline-block;border:1px solid rgba(42,178,255,.55);border-radius:7px;padding:3px 7px;color:#9ee5ff;font-size:.46rem;font-weight:950;letter-spacing:.08em}.tp13-pick b{display:block;margin-top:6px;font-size:.76rem}.tp13-score{text-align:right}.tp13-score strong{display:block;color:#fff;font-size:1.14rem}.tp13-score span{color:#65cfff;font-size:.45rem;font-weight:900;letter-spacing:.055em}
.tp13-status{margin-top:4px;display:inline-block;border-radius:999px;padding:4px 7px;font-size:.43rem;font-weight:950}.tp13-status.value{color:var(--tp-green);border:1px solid rgba(113,230,176,.3)}.tp13-status.fair{color:var(--tp-cyan);border:1px solid rgba(125,224,255,.28)}.tp13-status.expensive{color:var(--tp-red);border:1px solid rgba(255,125,142,.28)}.tp13-status.pending{color:var(--tp-gold);border:1px solid rgba(255,208,113,.28)}
.tp13-metrics{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));border-top:1px solid rgba(255,255,255,.055);border-bottom:1px solid rgba(255,255,255,.045)}.tp13-metric{padding:9px 11px;border-right:1px solid rgba(255,255,255,.045)}.tp13-metric:last-child{border-right:0}.tp13-metric span{display:block;color:#6c879b;font-size:.45rem;font-weight:900;letter-spacing:.065em;text-transform:uppercase}.tp13-metric b{display:block;margin-top:4px;color:#eaf7ff;font-size:.66rem}.tp13-edge-positive{color:var(--tp-green)!important}.tp13-edge-negative{color:var(--tp-red)!important}
.tp13-grid{display:grid;grid-template-columns:1.1fr .9fr;gap:8px;padding:10px 12px;border-bottom:1px solid rgba(255,255,255,.045)}.tp13-panel{border:1px solid rgba(82,181,238,.11);border-radius:10px;padding:10px;background:rgba(4,15,25,.6)}.tp13-panel h4{margin:0 0 7px;color:#76d8ff;font-size:.47rem;letter-spacing:.08em}.tp13-panel p{margin:0;color:#97afbf;font-size:.56rem;line-height:1.45}.tp13-books{display:flex;flex-wrap:wrap;gap:5px}.tp13-book{border:1px solid rgba(99,205,255,.13);border-radius:8px;padding:5px 7px;color:#c4d9e6;font-size:.50rem}.tp13-book.best{border-color:rgba(113,230,176,.35);color:var(--tp-green)}
.tp13-snapshot{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}.tp13-snap{padding:6px;border-radius:8px;background:rgba(255,255,255,.025)}.tp13-snap span{display:block;color:#66849a;font-size:.42rem;font-weight:900}.tp13-snap b{display:block;margin-top:3px;color:#dceef8;font-size:.55rem}
.tp13-reason{padding:11px 12px 13px}.tp13-reason small{display:block;color:#63cfff;font-size:.46rem;font-weight:950;letter-spacing:.075em}.tp13-factors{display:flex;flex-wrap:wrap;gap:5px;margin:7px 0}.tp13-factor{border-radius:999px;border:1px solid rgba(99,205,255,.15);padding:4px 7px;color:#a6c3d4;font-size:.45rem;font-weight:850}.tp13-reason p{margin:5px 0 0;color:#a1b8c7;font-size:.59rem;line-height:1.48}.tp13-source{margin-top:6px;color:#587589;font-size:.47rem}
.tp13-empty{margin:14px 24px 24px;padding:16px;border:1px solid rgba(255,125,142,.24);border-radius:12px;background:rgba(93,22,36,.12);color:#ffb2bd;font-size:.7rem;line-height:1.45}
@media(max-width:760px){.tp13-head{padding:18px 14px 14px}.tp13-title-row{align-items:flex-start;flex-direction:column}.tp13-title h1{font-size:1.95rem}.tp13-integrity,.tp13-filter,.tp13-intel,.tp13-board{padding-left:14px;padding-right:14px}.tp13-intel{grid-template-columns:1fr 1fr}.tp13-card-head{grid-template-columns:38px minmax(0,1fr) 80px}.tp13-pick{grid-column:2/4}.tp13-metrics{grid-template-columns:1fr 1fr}.tp13-metric:nth-child(5){grid-column:1/3}.tp13-grid{grid-template-columns:1fr}.tp13-snapshot{grid-template-columns:1fr 1fr}.tp13-board-head{align-items:flex-start;flex-direction:column}}
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
        return "Timestamp unavailable"
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt.strftime("%b %d • %I:%M %p UTC").replace(" 0", " ")
    except Exception:
        return text


def _query_date() -> str | None:
    try:
        raw = st.query_params.get("top_pick_date")
    except Exception:
        raw = None
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    return _clean(raw) or None


def _query_filter() -> str:
    try:
        raw = st.query_params.get("top_pick_filter")
    except Exception:
        raw = None
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    value = _clean(raw).lower()
    allowed = {key for key, _ in FILTERS}
    return value if value in allowed else "all"


@st.cache_data(ttl=60, show_spinner=False)
def _load_page_payload(game_date: str | None = None) -> dict[str, Any]:
    query: dict[str, str] = {"limit": "10"}
    if game_date:
        query["game_date"] = game_date
    url = f"{KYRE_SPORTS_API_BASE_URL}{PAGE1_ENDPOINT}?{urlencode(query)}"
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "KyreSportsAI/1.0"})
    with urlopen(request, timeout=45) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if _clean(payload.get("service")) != "Kyre Sports API":
        raise RuntimeError("Top Picks V2 gateway returned an invalid service contract.")
    return dict(payload)


def _filter_picks(rows: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    if mode == "value":
        return [row for row in rows if _clean(row.get("value_status")) == "MODEL VALUE"]
    if mode == "high-confidence":
        return [row for row in rows if (_number(row.get("confidence_score")) or 0) >= 80]
    if mode == "market-movers":
        return [row for row in rows if isinstance(row.get("line_movement"), Mapping)]
    return rows


def _filter_href(key: str, slate_day: str) -> str:
    query = {"top_pick_filter": key}
    if slate_day and slate_day != "Verified slate":
        query["top_pick_date"] = slate_day
    return "?" + urlencode(query)


def _logo(url: Any, team: str) -> str:
    src = _clean(url)
    if not src:
        return ""
    return f'<img class="team-logo" src="{escape(src)}" alt="{escape(team)} logo">'


def _value_class(status: str) -> str:
    if status == "MODEL VALUE":
        return "value"
    if status == "FAIR MARKET":
        return "fair"
    if status == "PRICE TOO EXPENSIVE":
        return "expensive"
    return "pending"


def _books_html(row: Mapping[str, Any]) -> str:
    books = [dict(item) for item in list(row.get("book_prices") or []) if isinstance(item, Mapping)]
    best = row.get("best_price") if isinstance(row.get("best_price"), Mapping) else {}
    best_book = _clean(best.get("sportsbook"))
    if not books:
        return '<p>No verified sportsbook quote is available. Missing prices stay missing.</p>'
    parts = []
    for item in books:
        book = _clean(item.get("sportsbook"))
        price = _money(item.get("price"))
        cls = "tp13-book best" if book and book == best_book else "tp13-book"
        parts.append(f'<span class="{cls}">{escape(book)} {escape(price)}</span>')
    return '<div class="tp13-books">' + "".join(parts) + "</div>"


def _movement_text(row: Mapping[str, Any]) -> str:
    movement = row.get("line_movement")
    if not isinstance(movement, Mapping):
        return "No verified opener is available, so line movement is not fabricated."
    return (
        f"{escape(_clean(movement.get('sportsbook')))} "
        f"{escape(_money(movement.get('open_price')))} → "
        f"{escape(_money(movement.get('current_price')))} • "
        f"{escape(_clean(movement.get('direction')))} "
        f"({escape(_edge(movement.get('implied_move_pp')))})"
    )


def _availability_text(row: Mapping[str, Any]) -> str:
    availability = row.get("availability")
    if not isinstance(availability, Mapping):
        return "No verified availability report is attached to this matchup."
    status = _clean(availability.get("status")) or "VERIFIED"
    summary = _clean(availability.get("summary"))
    source = _clean(availability.get("source"))
    parts = [status]
    if summary:
        parts.append(summary)
    if source:
        parts.append(source)
    return " • ".join(escape(part) for part in parts)


def _snapshot_html(row: Mapping[str, Any]) -> str:
    snap = row.get("matchup_snapshot") if isinstance(row.get("matchup_snapshot"), Mapping) else {}
    items = [
        ("Pick Record", _clean(snap.get("pick_record")) or "—"),
        ("Opponent", _clean(snap.get("opponent_record")) or "—"),
        ("Recent", _clean(snap.get("pick_recent")) or "—"),
        ("Location Split", _clean(snap.get("location_split")) or "—"),
        ("Pick PPG", f"{_number(snap.get('pick_ppg')):.1f}" if _number(snap.get("pick_ppg")) is not None else "—"),
        ("Point Diff", f"{_number(snap.get('pick_point_diff_pg')):+.1f}" if _number(snap.get("pick_point_diff_pg")) is not None else "—"),
    ]
    return '<div class="tp13-snapshot">' + "".join(
        f'<div class="tp13-snap"><span>{escape(label)}</span><b>{escape(value)}</b></div>'
        for label, value in items
    ) + "</div>"


def _factor_html(row: Mapping[str, Any]) -> str:
    factors = [dict(item) for item in list(row.get("reason_factors") or []) if isinstance(item, Mapping)]
    if not factors:
        return '<span class="tp13-factor">Verified detail limited</span>'
    return "".join(
        f'<span class="tp13-factor">{escape(_clean(item.get("label")) or "Verified edge")}</span>'
        for item in factors
    )


def _card_html(row: Mapping[str, Any]) -> str:
    rank = int(row.get("rank") or 0)
    away = _clean(row.get("away")) or "Away"
    home = _clean(row.get("home")) or "Home"
    pick = _clean(row.get("pick")) or "Verified selection"
    kickoff = _stamp(row.get("kickoff_iso"))
    probability = _pct(row.get("model_probability"))
    confidence = int(round(_number(row.get("confidence_score")) or 0))
    reliability = _pct(row.get("model_reliability"))
    fair = _money(row.get("model_fair_price"))
    implied = _pct(row.get("market_implied_probability"))
    edge_value = _number(row.get("model_edge_pp"))
    edge = _edge(edge_value)
    edge_class = "tp13-edge-positive" if edge_value is not None and edge_value >= 0 else "tp13-edge-negative"
    best = row.get("best_price") if isinstance(row.get("best_price"), Mapping) else None
    best_text = _money(best.get("price")) if best else "—"
    book = _clean(best.get("sportsbook")) if best else "Market unavailable"
    status = _clean(row.get("value_status")) or "MARKET PENDING"
    source = row.get("source_health") if isinstance(row.get("source_health"), Mapping) else {}
    factors = int(source.get("verified_matchup_factors") or 0)
    quotes = int(source.get("sportsbook_quotes") or 0)
    reason = _clean(row.get("why")) or "No unsupported reason was generated."
    top_class = " top" if rank <= 3 else ""
    return f"""
    <article class="tp13-card{top_class}" data-testid="cfb-top-picks-v13-card-{rank}" data-event-id="{escape(_clean(row.get('event_id')))}">
      <div class="tp13-card-head">
        <div class="tp13-rank">{rank}</div>
        <div class="tp13-match">
          <div class="tp13-teamline">{_logo(row.get('away_logo'), away)}<b>{escape(away)}</b></div>
          <small>@</small>
          <div class="tp13-teamline">{_logo(row.get('home_logo'), home)}<b>{escape(home)}</b></div>
          <span>Kickoff {escape(kickoff)}</span>
        </div>
        <div class="tp13-pick"><span class="tp13-market">MONEYLINE</span><b>{escape(pick)}</b><span class="tp13-status {_value_class(status)}">{escape(status)}</span></div>
        <div class="tp13-score"><strong>{confidence}/100</strong><span>CONFIDENCE SCORE</span></div>
      </div>
      <div class="tp13-metrics">
        <div class="tp13-metric"><span>Best Price</span><b>{escape(best_text)} • {escape(book)}</b></div>
        <div class="tp13-metric"><span>Model</span><b>{escape(probability)}</b></div>
        <div class="tp13-metric"><span>Market Implied</span><b>{escape(implied)}</b></div>
        <div class="tp13-metric"><span>Market Edge</span><b class="{edge_class}">{escape(edge)}</b></div>
        <div class="tp13-metric"><span>Model Fair</span><b>{escape(fair)} • {escape(reliability)} rel.</b></div>
      </div>
      <div class="tp13-grid">
        <div class="tp13-panel"><h4>BOOK COMPARISON</h4>{_books_html(row)}</div>
        <div class="tp13-panel"><h4>LINE MOVEMENT</h4><p>{_movement_text(row)}</p></div>
        <div class="tp13-panel"><h4>MATCHUP SNAPSHOT</h4>{_snapshot_html(row)}</div>
        <div class="tp13-panel"><h4>AVAILABILITY</h4><p>{_availability_text(row)}</p></div>
      </div>
      <div class="tp13-reason">
        <small>WHY THIS PICK</small>
        <div class="tp13-factors">{_factor_html(row)}</div>
        <p>{escape(reason)}</p>
        <div class="tp13-source">SOURCE HEALTH • {factors} verified matchup factor(s) • {quotes} exact sportsbook quote(s)</div>
      </div>
    </article>
    """


def _page_html(payload: Mapping[str, Any], mode: str) -> str:
    all_picks = [dict(row) for row in list(payload.get("picks") or []) if isinstance(row, Mapping)]
    picks = _filter_picks(all_picks, mode)
    diag = dict(payload.get("diagnostics") or {})
    health = dict(payload.get("source_health") or {})
    slate_day = _clean(payload.get("selected_date")) or "Verified slate"
    generated = _stamp(payload.get("generated_at_utc"))
    complete = bool(diag.get("complete_top_ten")) and len(all_picks) == 10
    integrity = "10/10 UNIQUE • VERIFIED" if complete else f"{len(all_picks)}/10 QUALIFIED"

    top = all_picks[0] if all_picks else {}
    top_pick = _clean(top.get("pick")) or "—"
    top_prob = _pct(top.get("model_probability"))
    edge_rows = [row for row in all_picks if _number(row.get("model_edge_pp")) is not None]
    best_edge_row = max(edge_rows, key=lambda row: float(row.get("model_edge_pp"))) if edge_rows else {}
    best_edge = _edge(best_edge_row.get("model_edge_pp")) if best_edge_row else "—"
    provider_count = int(health.get("provider_count") or 0)
    reason_ready = int(health.get("verified_reason_picks") or 0)
    cards = "".join(_card_html(row) for row in picks)

    filter_html = "".join(
        f'<a class="{"active" if key == mode else ""}" href="{escape(_filter_href(key, slate_day))}">{escape(label)}</a>'
        for key, label in FILTERS
    )

    return f"""
    <section data-testid="cfb-top-picks-v13-root" data-page-marker="{PAGE_MARKER}">
      <div class="tp13-shell">
        <header class="tp13-head">
          <div class="tp13-brand"><b>KYRE SPORTS AI</b><span class="tp13-live">KYRE SPORTS API LIVE</span></div>
          <div class="tp13-title-row">
            <div class="tp13-title"><h1>Top <span>Picks</span></h1><p>{len(all_picks)} strongest verified College Football moneyline decisions • confidence and bet value separated</p></div>
            <div class="tp13-date">◫ {escape(slate_day)}</div>
          </div>
          <div class="tp13-tabs"><div class="tp13-tab active">Moneyline</div><div class="tp13-tab">Spread</div><div class="tp13-tab">Over/Under</div></div>
        </header>
        <div class="tp13-integrity"><b>SLATE INTEGRITY</b><span class="tp13-pill {'good' if complete else ''}">{escape(integrity)}</span><span class="tp13-pill">Canonical NCAA game identity</span><span class="tp13-pill">No blended sportsbook prices</span><span class="tp13-pill">Missing data stays missing</span></div>
        <div class="tp13-filter">{filter_html}</div>
        <div class="tp13-intel">
          <div class="tp13-kpi"><span>Highest Model</span><b>{escape(top_pick)} • {escape(top_prob)}</b><em>Win-confidence leader</em></div>
          <div class="tp13-kpi"><span>Best Market Edge</span><b>{escape(best_edge)}</b><em>Value is separate from winner confidence</em></div>
          <div class="tp13-kpi"><span>SOURCE HEALTH</span><b>{provider_count} provider(s)</b><em>{reason_ready}/{len(all_picks) if all_picks else 0} picks with verified matchup evidence</em></div>
          <div class="tp13-kpi"><span>Last Refresh</span><b>{escape(generated)}</b><em>Fresh Kyre gateway payload</em></div>
        </div>
        <main class="tp13-board">
          <div class="tp13-board-head"><h3>Decision Board • {escape(dict(FILTERS).get(mode, "All"))}</h3><span>Model probability • value • exact market provenance • matchup evidence</span></div>
          {cards if cards else '<div class="tp13-empty">No picks match this filter. The page will not invent replacement games, prices, movement, injuries, or reasons.</div>'}
        </main>
      </div>
    </section>
    """


def render_top_picks_page() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    try:
        with st.spinner("Loading verified CFB Top Picks from Kyre Sports API..."):
            payload = _load_page_payload(_query_date())
    except Exception as exc:
        st.error(
            f"Kyre Sports API Top Picks V2 is temporarily unavailable ({type(exc).__name__}). "
            "No fallback data was substituted."
        )
        return
    st.markdown(_page_html(payload, _query_filter()), unsafe_allow_html=True)
    diagnostics = dict(payload.get("diagnostics") or {})
    if not diagnostics.get("complete_top_ten"):
        st.warning(
            "The current slate has fewer than 10 fully model-ready unique selections. "
            "Missing entries are intentionally not fabricated."
        )


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if _clean(market) != "Top Picks":
        raise RuntimeError("CFB Top Picks V13 owns only the Top Picks route.")
    render_top_picks_page()


__all__ = [
    "KYRE_SPORTS_API_BASE_URL",
    "MODEL_VERSION",
    "PAGE1_ENDPOINT",
    "PAGE_MARKER",
    "render_cfb_hub",
    "render_top_picks_page",
]
