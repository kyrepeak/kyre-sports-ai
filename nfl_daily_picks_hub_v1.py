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

MODEL_VERSION = "NFL DAILY PICKS V2 • PREMIUM BEST PICKS • SIX-MARKET ACCESS"
ET = ZoneInfo("America/New_York")
ZERO_STATE = "No qualified pregame picks are currently available."

_CSS = r"""
<style>
.kdp-shell{margin:8px 0 14px;padding:18px;border:1px solid rgba(96,165,250,.36);border-radius:22px;background:radial-gradient(circle at 88% 0%,rgba(56,189,248,.15),transparent 34%),radial-gradient(circle at 8% 100%,rgba(34,197,94,.08),transparent 32%),linear-gradient(145deg,#07131f,#071019);box-shadow:0 18px 44px rgba(0,0,0,.22)}
.kdp-eyebrow{font-size:.61rem;font-weight:950;letter-spacing:.13em;color:#7dd3fc;text-transform:uppercase}.kdp-title{font-size:1.62rem;font-weight:950;color:#f8fafc;margin-top:4px;line-height:1.08}.kdp-title span{color:#7dd3fc}.kdp-sub{color:#93a8bb;font-size:.72rem;line-height:1.55;margin-top:6px;max-width:880px}.kdp-chiprow{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}.kdp-chip{border:1px solid #315269;background:#0a1b28;color:#9bdcf4;border-radius:999px;padding:4px 8px;font-size:.45rem;font-weight:950}.kdp-chip.green{border-color:#315e47;background:#0b2118;color:#8fe4ad}
.kdp-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin:10px 0 11px}.kdp-summary>div{border:1px solid #263f53;border-radius:12px;background:#081521;padding:9px}.kdp-summary b{display:block;color:#f2f8fc;font-size:.92rem}.kdp-summary span{display:block;color:#6f8799;font-size:.42rem;text-transform:uppercase;font-weight:950;margin-top:2px}
.kdp-status-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin:10px 0 13px}.kdp-status{border:1px solid #294157;border-radius:12px;background:#091621;padding:8px 9px;min-width:0}.kdp-status b{display:block;color:#e8f3fb;font-size:.58rem}.kdp-status span{display:block;font-size:.47rem;margin-top:3px;font-weight:950}.kdp-status.ready span{color:#86efac}.kdp-status.connected span{color:#93c5fd}.kdp-status.stale span{color:#fcd34d}.kdp-status.error span{color:#fda4af}.kdp-status em{display:block;font-style:normal;color:#667d90;font-size:.38rem;margin-top:3px}
.kdp-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:11px;margin:10px 0}.kdp-card{position:relative;overflow:hidden;border:1px solid #2b5068;border-radius:18px;background:radial-gradient(circle at 94% 7%,rgba(59,130,246,.11),transparent 28%),linear-gradient(160deg,#091724,#08111b);padding:13px;min-width:0;box-shadow:0 10px 28px rgba(0,0,0,.16)}.kdp-card.top1{border-color:#8a6a2e;box-shadow:0 0 0 1px rgba(250,204,21,.06),0 12px 30px rgba(0,0,0,.18)}.kdp-card.top2{border-color:#526a7d}.kdp-card.top3{border-color:#78513b}.kdp-top{display:flex;justify-content:space-between;gap:8px;align-items:flex-start}.kdp-rank{font-size:.50rem;font-weight:950;letter-spacing:.05em;color:#7dd3fc;text-transform:uppercase}.kdp-rank.gold{color:#f4d06f}.kdp-market{font-size:.47rem;color:#7992a6;font-weight:900;text-transform:uppercase}.kdp-ident{display:grid;grid-template-columns:54px minmax(0,1fr) 38px;gap:9px;align-items:center;margin-top:9px}.kdp-face{width:52px;height:52px;border-radius:50%;object-fit:cover;object-position:center top;border:1px solid #35566c;background:#101a23}.kdp-team-logo{width:36px;height:36px;object-fit:contain;justify-self:end}.kdp-subject{font-size:.98rem;font-weight:950;color:#f8fbff;line-height:1.15}.kdp-matchup{color:#8299ab;font-size:.52rem;margin-top:3px}.kdp-pick{color:#bfe9f8;font-size:.62rem;font-weight:950;margin-top:5px}
.kdp-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:10px}.kdp-metric{border:1px solid #20384b;border-radius:10px;background:#07131d;padding:7px;min-width:0}.kdp-metric b{display:block;color:#f5f9fc;font-size:.78rem;white-space:nowrap}.kdp-metric span{display:block;color:#667f93;font-size:.35rem;text-transform:uppercase;font-weight:950;margin-top:2px}
.kdp-why{margin-top:9px;border-left:3px solid #38bdf8;background:#0a1b27;border-radius:9px;padding:9px 10px}.kdp-why b{display:block;color:#bcecff;font-size:.55rem}.kdp-why span{display:block;color:#99adbc;font-size:.49rem;line-height:1.5;margin-top:3px}.kdp-risk{margin-top:7px;border-left:3px solid #7b6a3d;background:#17170f;border-radius:9px;padding:8px 10px}.kdp-risk b{display:block;color:#e8d38c;font-size:.50rem}.kdp-risk span{display:block;color:#aaa184;font-size:.45rem;line-height:1.45;margin-top:3px}.kdp-foot{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;border-top:1px solid #1b3040;margin-top:9px;padding-top:7px;color:#70889a;font-size:.42rem}.kdp-foot strong{color:#91d3e9}.kdp-empty{border:1px dashed #365064;border-radius:14px;padding:15px;color:#8fa4b8;background:#08141e;text-align:center;font-size:.65rem}
@media(max-width:760px){.kdp-summary{grid-template-columns:repeat(2,minmax(0,1fr))}.kdp-status-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.kdp-grid{grid-template-columns:1fr}.kdp-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.kdp-ident{grid-template-columns:48px minmax(0,1fr) 32px}.kdp-face{width:46px;height:46px}.kdp-team-logo{width:30px;height:30px}.kdp-shell{padding:14px}.kdp-title{font-size:1.35rem}}
</style>
"""


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _selected_day() -> date:
    if st is not None:
        value = getattr(st, "session_state", {}).get("nfl_v1_date")
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value[:10])
            except ValueError:
                pass
    return datetime.now(ET).date()


def _fmt_number(value: Any, digits: int = 1) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return "—"


def _risk(candidate) -> str:
    uncertainty = max(0.0, float(candidate.uncertainty))
    if uncertainty >= 0.20:
        return "HIGH"
    if uncertainty >= 0.10:
        return "MEDIUM"
    return "LOW"


def _kickoff_text(candidate) -> str:
    try:
        return candidate.kickoff_at.astimezone(ET).strftime("%a %-I:%M %p ET")
    except Exception:
        return str(candidate.kickoff_at)


def _metadata(candidate) -> dict[str, Any]:
    try:
        return {str(key): value for key, value in tuple(candidate.metadata or ())}
    except Exception:
        return {}


def _abbr(value: Any) -> str:
    text = str(value or "").strip().upper()
    return text if text.isalpha() and 2 <= len(text) <= 4 else ""


def _team_logo_url(abbr: Any) -> str:
    team = _abbr(abbr)
    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{team.lower()}.png" if team else ""


def _headshot_url(athlete_id: Any) -> str:
    athlete = str(athlete_id or "").strip()
    return f"https://a.espncdn.com/i/headshots/nfl/players/full/{athlete}.png" if athlete.isdigit() else ""


def _rank_label(rank: int) -> str:
    return {1: "BEST PICK TODAY", 2: "STRONG EDGE", 3: "TOP VALUE"}.get(rank, f"TOP {rank} PICK")


def _why_detail(candidate, rank: int) -> str:
    probability = 100.0 * float(candidate.model_probability)
    line = candidate.market_line
    projection = candidate.model_projection
    parts = [f"The source-owned model gives this {candidate.side} position a {probability:.1f}% probability."]
    if line is not None and projection is not None:
        try:
            gap = abs(float(projection) - float(line))
            unit = "yards" if candidate.market_id.endswith("yards") else "points"
            parts.append(
                f"The market line is {_fmt_number(line)} and the model projection is {_fmt_number(projection)}, a {gap:.1f}-{unit} line-to-projection gap."
            )
        except Exception:
            pass
    elif candidate.market_id == "moneyline":
        parts.append(f"Its certified source edge metric is {_fmt_number(candidate.edge_value, 3)}.")
    reasons = [str(item).strip() for item in tuple(candidate.reason_components or ()) if str(item).strip()]
    if reasons:
        parts.append(reasons[0].rstrip(".") + ".")
    if rank <= 3:
        parts.append("It ranks above the other qualified future-game candidates after probability, edge, data quality, freshness, uncertainty and correlation checks.")
    return " ".join(parts)


def _risk_detail(candidate) -> str:
    risk = _risk(candidate)
    age = max(0.0, float(candidate.source_age_seconds))
    limit = max(1.0, float(candidate.freshness_limit_seconds))
    if risk == "HIGH":
        return "Model uncertainty is elevated, so normal game variance can erase the projected edge faster than usual."
    if age / limit >= 0.70:
        return "The source snapshot is nearing its freshness limit; line movement or new availability information could materially change the value."
    return "The main risk is normal game variance plus late line, injury or availability movement before kickoff; re-check the live market if the number changes."


def _card_payload(candidate, rank: int) -> dict[str, Any]:
    meta = _metadata(candidate)
    reasons = tuple(candidate.reason_components or ())
    team_abbr = _abbr(meta.get("team_abbr")) or _abbr(candidate.team_id)
    opponent_abbr = _abbr(meta.get("opponent_abbr")) or _abbr(candidate.opponent_team_id)
    line = candidate.market_line
    projection = candidate.model_projection
    gap = None
    if line is not None and projection is not None:
        try:
            gap = abs(float(projection) - float(line))
        except Exception:
            pass
    return {
        "rank": rank,
        "rank_label": _rank_label(rank),
        "market": candidate.market_label,
        "market_id": candidate.market_id,
        "subject": candidate.subject_label,
        "matchup": candidate.matchup_label,
        "line": line,
        "side": candidate.side,
        "probability": candidate.model_probability,
        "projection": projection,
        "edge": candidate.edge_value,
        "projection_gap": gap,
        "confidence": candidate.source_grade or "QUALIFIED",
        "why": " • ".join(str(item) for item in reasons[:3] if str(item).strip()) or "Source-owned eligible result.",
        "why_title": f"Why this is #{rank}",
        "why_detail": _why_detail(candidate, rank),
        "risk": _risk(candidate),
        "risk_detail": _risk_detail(candidate),
        "freshness": f"{max(0.0, float(candidate.source_age_seconds)):.0f}s old",
        "kickoff": _kickoff_text(candidate),
        "quality": candidate.data_quality,
        "score": normalized_pick_score(candidate),
        "source_version": candidate.source_version,
        "team_logo_url": _team_logo_url(team_abbr),
        "opponent_logo_url": _team_logo_url(opponent_abbr),
        "headshot_url": _headshot_url(candidate.athlete_id),
        "athlete_id": candidate.athlete_id,
        "team_abbr": team_abbr,
        "opponent_abbr": opponent_abbr,
    }


def _access_state(raw_state: Any) -> str:
    state = str(raw_state or "").upper()
    if state == "READY":
        return "READY"
    if state == "ERROR":
        return "ERROR"
    if state == "STALE":
        return "STALE"
    return "CONNECTED"


def build_daily_picks_board(
    day: date,
    *,
    now_utc: datetime,
    loaders: Mapping[str, Callable] | None = None,
) -> dict[str, Any]:
    results = load_all_market_candidates(day, now_utc=now_utc, loaders=loaders)
    by_market = {result.market_id: result for result in results}
    statuses = {market_id: (by_market.get(market_id).status if by_market.get(market_id) else "UNAVAILABLE") for market_id in MARKET_ORDER}
    access_statuses = {market_id: _access_state(statuses[market_id]) for market_id in MARKET_ORDER}
    diagnostics = {
        market_id: (by_market.get(market_id).diagnostic if by_market.get(market_id) else "No source result returned.")
        for market_id in MARKET_ORDER
    }
    candidates = tuple(
        candidate
        for result in results
        if str(result.status or "").upper() == "READY"
        for candidate in result.candidates
    )
    ranked = rank_daily_picks(candidates, now_utc=now_utc, limit=10)
    cards = tuple(_card_payload(candidate, index) for index, candidate in enumerate(ranked, start=1))
    return {
        "market_statuses": statuses,
        "market_access_statuses": access_statuses,
        "ranked_picks": cards,
        "picks": ranked,
        "healthy_market_count": sum(1 for state in statuses.values() if str(state).upper() == "READY"),
        "connected_market_count": len(MARKET_ORDER),
        "candidate_count": len(candidates),
        "qualified_game_count": len({str(candidate.game_id) for candidate in candidates}),
        "diagnostics": diagnostics,
        "day": day,
    }


def _status_html(board: Mapping[str, Any]) -> str:
    access = dict(board.get("market_access_statuses") or {})
    blocks = []
    for market_id in MARKET_ORDER:
        state = str(access.get(market_id) or _access_state((board.get("market_statuses") or {}).get(market_id))).upper()
        css = state.lower() if state.lower() in {"ready", "connected", "stale", "error"} else "connected"
        detail = {
            "READY": "Qualified picks available",
            "CONNECTED": "Daily Picks access live • scanning",
            "STALE": "Connected • waiting for fresh data",
            "ERROR": "Connected • source temporarily unavailable",
        }.get(state, "Daily Picks access live")
        blocks.append(
            f'<div class="kdp-status {css}"><b>{escape(MARKET_LABELS[market_id])}</b><span>{escape(state)}</span><em>{escape(detail)}</em></div>'
        )
    return '<div class="kdp-status-grid">' + ''.join(blocks) + '</div>'


def _img(url: Any, css: str, alt: str) -> str:
    value = str(url or "").strip()
    if not value.startswith("https://"):
        return f'<span class="{css}" aria-hidden="true"></span>' if css == "kdp-face" else ""
    return f'<img class="{css}" src="{escape(value, quote=True)}" alt="{escape(alt, quote=True)}" loading="lazy" decoding="async" />'


def _card_html(card: Mapping[str, Any]) -> str:
    rank = int(card.get("rank") or 0)
    top_class = f" top{rank}" if rank in {1, 2, 3} else ""
    rank_class = " gold" if rank == 1 else ""
    probability = f"{100.0 * float(card.get('probability') or 0.0):.1f}%"
    line = _fmt_number(card.get("line"))
    projection = _fmt_number(card.get("projection"))
    edge = _fmt_number(card.get("edge"), 2)
    face = _img(card.get("headshot_url"), "kdp-face", f"{card.get('subject','Player')} headshot")
    team_logo = _img(card.get("team_logo_url"), "kdp-team-logo", f"{card.get('team_abbr','Team')} logo")
    opponent_logo = _img(card.get("opponent_logo_url"), "kdp-team-logo", f"{card.get('opponent_abbr','Opponent')} logo")
    right_logo = team_logo or opponent_logo
    return (
        f'<article class="kdp-card{top_class}">'
        '<div class="kdp-top">'
        f'<div><div class="kdp-rank{rank_class}">#{rank} • {escape(str(card.get("rank_label") or "TOP PICK"))}</div><div class="kdp-market">{escape(str(card.get("market") or ""))}</div></div>'
        f'<div class="kdp-market">{escape(str(card.get("confidence") or "QUALIFIED"))}</div>'
        '</div>'
        '<div class="kdp-ident">'
        f'{face}<div><div class="kdp-subject">{escape(str(card.get("subject") or ""))}</div>'
        f'<div class="kdp-matchup">{escape(str(card.get("matchup") or ""))}</div>'
        f'<div class="kdp-pick">{escape(str(card.get("side") or ""))}{(" • " + line) if line != "—" else ""}</div></div>{right_logo}'
        '</div>'
        '<div class="kdp-metrics">'
        f'<div class="kdp-metric"><b>{probability}</b><span>Model Probability</span></div>'
        f'<div class="kdp-metric"><b>{line}</b><span>Market Line</span></div>'
        f'<div class="kdp-metric"><b>{projection}</b><span>Model Projection</span></div>'
        f'<div class="kdp-metric"><b>{edge}</b><span>Source Edge</span></div>'
        '</div>'
        f'<div class="kdp-why"><b>💡 {escape(str(card.get("why_title") or "Why this pick"))}</b><span>{escape(str(card.get("why_detail") or card.get("why") or ""))}</span></div>'
        f'<div class="kdp-risk"><b>⚠️ What could go wrong?</b><span>{escape(str(card.get("risk_detail") or "Normal game variance can beat any projection."))}</span></div>'
        '<div class="kdp-foot">'
        f'<span><strong>✓ Multi-source / source-owned</strong> • updated {escape(str(card.get("freshness") or ""))}</span>'
        f'<span>{escape(str(card.get("kickoff") or ""))} • risk {escape(str(card.get("risk") or ""))}</span>'
        '</div></article>'
    )


def render_nfl_daily_picks_hub() -> None:
    if st is None:
        raise RuntimeError("Streamlit is required to render NFL Daily Picks.")
    day = _selected_day()
    now = _now_utc()
    board = build_daily_picks_board(day, now_utc=now)
    ranked = tuple(board.get("ranked_picks") or ())
    st.markdown(
        _CSS
        + '<section class="kdp-shell">'
        + '<div class="kdp-eyebrow">NFL • DAILY PICKS • PREMIUM INTELLIGENCE</div>'
        + '<div class="kdp-title">🏆 NFL Daily Picks <span>Premium</span></div>'
        + '<div class="kdp-sub">The strongest qualified opportunities across Moneyline, Spread, Game Total, Passing Yards, Rushing Yards and Receiving Yards. Every card explains why it ranked, the biggest risk, and the exact future-game signal behind it.</div>'
        + '<div class="kdp-chiprow"><span class="kdp-chip green">6 MARKETS CONNECTED</span><span class="kdp-chip">FUTURE GAMES ONLY</span><span class="kdp-chip">NO FILLER</span><span class="kdp-chip">EXACT-ID DATA</span></div>'
        + '</section>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="kdp-summary">'
        f'<div><b>{int(board.get("connected_market_count") or 0)}/6</b><span>Markets Connected</span></div>'
        f'<div><b>{int(board.get("candidate_count") or 0)}</b><span>Qualified Candidates</span></div>'
        f'<div><b>{len(ranked)}</b><span>Best Picks Published</span></div>'
        f'<div><b>{escape(str(day))}</b><span>Pregame Slate</span></div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown(_status_html(board), unsafe_allow_html=True)
    if not ranked:
        st.info(ZERO_STATE + " All six market families remain connected and scanning; weak or incomplete signals are never used as filler.")
        st.markdown('<div class="kdp-empty">No source-owned candidate cleared probability, freshness, identity and correlation guardrails yet.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="kdp-grid">' + ''.join(_card_html(card) for card in ranked) + '</div>', unsafe_allow_html=True)
    st.caption(
        f"{MODEL_VERSION} • {board.get('connected_market_count', 0)}/6 market families connected • future kickoffs only • no synthetic probabilities • no filler • sportsbook data never changes model projections"
    )


def render_nfl_hub(market: str = "Daily Picks") -> None:
    if str(market or "Daily Picks") != "Daily Picks":
        raise ValueError("NFL Daily Picks V2 only renders the Daily Picks market.")
    return render_nfl_daily_picks_hub()


__all__ = [
    "ET", "MARKET_LABELS", "MARKET_ORDER", "MODEL_VERSION", "ZERO_STATE",
    "_card_html", "_card_payload", "_status_html", "build_daily_picks_board",
    "render_nfl_daily_picks_hub", "render_nfl_hub",
]
