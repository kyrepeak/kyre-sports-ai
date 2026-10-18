from __future__ import annotations

from datetime import date, datetime, timezone
from html import escape
from typing import Any, Callable, Mapping
from zoneinfo import ZoneInfo

try:
    import streamlit as st
except Exception:
    st = None

from nfl_daily_picks_sources_v1 import MARKET_LABELS, MARKET_ORDER, load_all_market_candidates
from nfl_daily_picks_ranking_v1 import normalized_pick_score, rank_daily_picks

MODEL_VERSION = "NFL DAILY PICKS V1 • PURE BEST 10 • READ-ONLY SOURCE AGGREGATION"
ET = ZoneInfo("America/New_York")
ZERO_STATE = "No qualified pregame picks are currently available."

_CSS = r'''
<style>
.kdp-shell{margin:8px 0 14px;padding:18px;border:1px solid rgba(96,165,250,.34);border-radius:22px;background:radial-gradient(circle at 85% 0%,rgba(56,189,248,.12),transparent 32%),linear-gradient(145deg,#081421,#07101a);box-shadow:0 18px 42px rgba(0,0,0,.20)}
.kdp-eyebrow{font-size:.62rem;font-weight:950;letter-spacing:.12em;color:#7dd3fc;text-transform:uppercase}.kdp-title{font-size:1.55rem;font-weight:950;color:#f8fafc;margin-top:4px}.kdp-sub{color:#8fa4b8;font-size:.72rem;line-height:1.55;margin-top:5px}.kdp-status-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin:10px 0 13px}.kdp-status{border:1px solid #2a4156;border-radius:12px;background:#091621;padding:8px 9px;min-width:0}.kdp-status b{display:block;color:#e6f4ff;font-size:.58rem}.kdp-status span{display:block;font-size:.48rem;margin-top:3px;font-weight:900}.kdp-status.ready span{color:#86efac}.kdp-status.gated span{color:#fcd34d}.kdp-status.error span{color:#fda4af}.kdp-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:11px;margin:10px 0}.kdp-card{border:1px solid #2b5068;border-radius:17px;background:linear-gradient(160deg,#091724,#08111b);padding:12px;min-width:0;box-shadow:0 10px 28px rgba(0,0,0,.14)}.kdp-top{display:flex;justify-content:space-between;gap:8px;align-items:flex-start}.kdp-rank{color:#7dd3fc;font-size:.72rem;font-weight:950}.kdp-market{color:#c7dff1;font-size:.52rem;font-weight:950;letter-spacing:.06em;text-transform:uppercase}.kdp-subject{color:#f8fafc;font-size:.92rem;font-weight:950;margin-top:8px}.kdp-matchup{color:#71899e;font-size:.54rem;margin-top:2px}.kdp-hero{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin-top:9px}.kdp-metric{border:1px solid #20394a;border-radius:10px;background:#07131d;padding:7px}.kdp-metric b{display:block;color:#eef8ff;font-size:.8rem}.kdp-metric span{display:block;color:#678096;font-size:.42rem;text-transform:uppercase;margin-top:2px;font-weight:900}.kdp-why{margin-top:8px;color:#a8bdcd;font-size:.52rem;line-height:1.5}.kdp-meta{display:flex;flex-wrap:wrap;gap:5px;margin-top:8px}.kdp-pill{border:1px solid #2d4d63;border-radius:999px;padding:3px 6px;color:#8fb4ca;font-size:.43rem;font-weight:900}.kdp-pill.good{color:#86efac;border-color:#2c6747}.kdp-pill.watch{color:#fcd34d;border-color:#705c2f}.kdp-diag{color:#6f8598;font-size:.48rem;line-height:1.5;margin-top:6px}
@media(max-width:760px){.kdp-status-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.kdp-grid{grid-template-columns:1fr}.kdp-shell{padding:14px}.kdp-title{font-size:1.3rem}}
</style>
'''


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _selected_day() -> date:
    if st is None:
        return datetime.now(ET).date()
    value = st.session_state.get("nfl_v1_date", datetime.now(ET).date())
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return datetime.now(ET).date()


def _fmt_number(value: Any, digits: int = 1) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.{digits}f}".rstrip("0").rstrip(".")
    except Exception:
        return "—"


def _risk(candidate) -> str:
    if candidate.data_quality >= 0.90 and candidate.uncertainty <= 0.12:
        return "LOW"
    if candidate.data_quality >= 0.75 and candidate.uncertainty <= 0.25:
        return "MEDIUM"
    return "HIGH"


def _kickoff_text(candidate) -> str:
    try:
        return candidate.kickoff_at.astimezone(ET).strftime("%a %-I:%M %p ET")
    except Exception:
        return str(candidate.kickoff_at)


def _card_payload(candidate, rank: int) -> dict[str, Any]:
    reasons = tuple(candidate.reason_components or ())
    return {
        "rank": rank,
        "market": candidate.market_label,
        "market_id": candidate.market_id,
        "subject": candidate.subject_label,
        "matchup": candidate.matchup_label,
        "line": candidate.market_line,
        "side": candidate.side,
        "probability": candidate.model_probability,
        "projection": candidate.model_projection,
        "confidence": candidate.source_grade or "QUALIFIED",
        "why": " • ".join(str(item) for item in reasons[:3] if str(item).strip()) or "Source-owned eligible result.",
        "risk": _risk(candidate),
        "freshness": f"{max(0.0, float(candidate.source_age_seconds)):.0f}s old",
        "kickoff": _kickoff_text(candidate),
        "quality": candidate.data_quality,
        "score": normalized_pick_score(candidate),
        "source_version": candidate.source_version,
    }


def build_daily_picks_board(
    day: date,
    *,
    now_utc: datetime,
    loaders: Mapping[str, Callable] | None = None,
) -> dict[str, Any]:
    results = load_all_market_candidates(day, now_utc=now_utc, loaders=loaders)
    by_market = {result.market_id: result for result in results}
    statuses = {market_id: (by_market.get(market_id).status if by_market.get(market_id) else "UNAVAILABLE") for market_id in MARKET_ORDER}
    diagnostics = {
        market_id: (by_market.get(market_id).diagnostic if by_market.get(market_id) else "No source result returned.")
        for market_id in MARKET_ORDER
    }
    candidates = tuple(candidate for result in results for candidate in result.candidates)
    ranked = rank_daily_picks(candidates, now_utc=now_utc, limit=10)
    cards = tuple(_card_payload(candidate, index) for index, candidate in enumerate(ranked, start=1))
    return {
        "market_statuses": statuses,
        "ranked_picks": cards,
        "healthy_market_count": sum(1 for state in statuses.values() if state == "READY"),
        "candidate_count": len(candidates),
        "diagnostics": diagnostics,
        "day": day,
    }


def _status_html(board: Mapping[str, Any]) -> str:
    cards = []
    for market_id in MARKET_ORDER:
        state = str(board["market_statuses"].get(market_id, "UNAVAILABLE")).upper()
        css = "ready" if state == "READY" else ("error" if state == "ERROR" else "gated")
        cards.append(f'<div class="kdp-status {css}"><b>{escape(MARKET_LABELS[market_id])}</b><span>{escape(state)}</span></div>')
    return '<div class="kdp-status-grid">' + "".join(cards) + '</div>'


def _card_html(card: Mapping[str, Any]) -> str:
    probability = f"{100.0 * float(card['probability']):.1f}%"
    line = _fmt_number(card.get("line"))
    projection = _fmt_number(card.get("projection"))
    risk = str(card.get("risk") or "MEDIUM")
    risk_css = "good" if risk == "LOW" else "watch"
    return (
        '<article class="kdp-card">'
        '<div class="kdp-top">'
        f'<div><div class="kdp-rank">#{int(card["rank"])} • {escape(str(card["market"]))}</div>'
        f'<div class="kdp-market">PURE BEST 10 • {escape(str(card["side"]))}</div></div>'
        f'<span class="kdp-pill good">{escape(str(card["confidence"]))}</span></div>'
        f'<div class="kdp-subject">{escape(str(card["subject"]))}</div>'
        f'<div class="kdp-matchup">{escape(str(card["matchup"]))}</div>'
        '<div class="kdp-hero">'
        f'<div class="kdp-metric"><b>{escape(probability)}</b><span>Model Probability</span></div>'
        f'<div class="kdp-metric"><b>{escape(line)}</b><span>Market Line</span></div>'
        f'<div class="kdp-metric"><b>{escape(projection)}</b><span>Projection</span></div>'
        '</div>'
        f'<div class="kdp-why"><b>Why:</b> {escape(str(card["why"]))}</div>'
        '<div class="kdp-meta">'
        f'<span class="kdp-pill {risk_css}">RISK {escape(risk)}</span>'
        f'<span class="kdp-pill">{escape(str(card["freshness"]))}</span>'
        f'<span class="kdp-pill">{escape(str(card["kickoff"]))}</span>'
        '</div>'
        f'<div class="kdp-diag">Source {escape(str(card["source_version"]))} • Daily Picks score {float(card["score"]):.3f}</div>'
        '</article>'
    )


def render_nfl_daily_picks_hub() -> None:
    if st is None:
        raise RuntimeError("Streamlit is required to render NFL Daily Picks.")
    now = _now_utc()
    day = _selected_day()
    board = build_daily_picks_board(day, now_utc=now)
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(
        '<section class="kdp-shell">'
        '<div class="kdp-eyebrow">KYRE SPORTS AI • NFL</div>'
        '<div class="kdp-title">🎯 NFL Daily Picks</div>'
        '<div class="kdp-sub">Pure Best 10 from fresh, exact-identity, pregame source-owned NFL outputs. No second prediction engine, no filler, and no hidden market-page rendering.</div>'
        f'<div class="kdp-diag">Slate {escape(day.isoformat())} • {int(board["healthy_market_count"])}/6 source families ready • {int(board["candidate_count"])} eligible candidate(s)</div>'
        '</section>',
        unsafe_allow_html=True,
    )
    st.markdown(_status_html(board), unsafe_allow_html=True)
    cards = board["ranked_picks"]
    if not cards:
        st.info(ZERO_STATE)
        for market_id in MARKET_ORDER:
            diagnostic = board["diagnostics"].get(market_id) or ""
            if diagnostic:
                st.caption(f"{MARKET_LABELS[market_id]} • {board['market_statuses'][market_id]} • {diagnostic}")
        return
    st.markdown('<div class="kdp-grid">' + "".join(_card_html(card) for card in cards) + '</div>', unsafe_allow_html=True)
    gated = [MARKET_LABELS[mid] for mid, state in board["market_statuses"].items() if state != "READY"]
    if gated:
        st.caption("Fail-closed source families: " + ", ".join(gated) + ". Their missing picks are not backfilled or fabricated.")
    st.caption(f"{MODEL_VERSION} • pregame only • exact identity • correlation safety • sportsbook projection influence unchanged in every source model")


def render_nfl_hub(market: str = "Daily Picks") -> None:
    if str(market or "Daily Picks") != "Daily Picks":
        raise ValueError("NFL Daily Picks V1 only renders the Daily Picks market.")
    return render_nfl_daily_picks_hub()


__all__ = ["MODEL_VERSION", "ZERO_STATE", "build_daily_picks_board", "render_nfl_daily_picks_hub", "render_nfl_hub"]
