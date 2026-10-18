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
.kdp-shell{margin:8px 0 14px;padding:18px;border:1px solid #31536a;border-radius:22px;background:radial-gradient(circle at 88% 0%,rgba(56,189,248,.15),transparent 34%),linear-gradient(145deg,#07131f,#071019);box-shadow:0 18px 44px rgba(0,0,0,.22)}
.kdp-eyebrow{font-size:.61rem;font-weight:950;letter-spacing:.13em;color:#7dd3fc;text-transform:uppercase}.kdp-title{font-size:1.62rem;font-weight:950;color:#f8fafc;margin-top:4px}.kdp-title span{color:#7dd3fc}.kdp-sub{color:#93a8bb;font-size:.72rem;line-height:1.55;margin-top:6px}.kdp-chiprow{display:flex;gap:6px;flex-wrap:wrap;margin-top:9px}.kdp-chip{border:1px solid #315269;background:#0a1b28;color:#9bdcf4;border-radius:999px;padding:4px 8px;font-size:.44rem;font-weight:950}
.kdp-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin:10px 0}.kdp-summary>div,.kdp-status{border:1px solid #294157;border-radius:12px;background:#091621;padding:9px}.kdp-summary b{display:block;color:#f2f8fc;font-size:.92rem}.kdp-summary span{color:#6f8799;font-size:.4rem;text-transform:uppercase;font-weight:950}.kdp-status-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin:10px 0 13px}.kdp-status b{display:block;color:#e8f3fb;font-size:.58rem}.kdp-status span{display:block;font-size:.46rem;margin-top:3px;font-weight:950}.kdp-status.ready span{color:#86efac}.kdp-status.connected span{color:#93c5fd}.kdp-status.stale span{color:#fcd34d}.kdp-status.error span{color:#fda4af}.kdp-status em{display:block;font-style:normal;color:#667d90;font-size:.37rem;margin-top:3px}
.kdp-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:11px}.kdp-card{border:1px solid #2b5068;border-radius:18px;background:radial-gradient(circle at 94% 7%,rgba(59,130,246,.11),transparent 28%),linear-gradient(160deg,#091724,#08111b);padding:13px;box-shadow:0 10px 28px rgba(0,0,0,.16)}.kdp-card.top1{border-color:#8a6a2e}.kdp-card.top2{border-color:#526a7d}.kdp-card.top3{border-color:#78513b}.kdp-top{display:flex;justify-content:space-between;gap:8px}.kdp-rank{font-size:.5rem;font-weight:950;color:#7dd3fc}.kdp-rank.gold{color:#f4d06f}.kdp-market{font-size:.46rem;color:#7992a6;font-weight:900;text-transform:uppercase}.kdp-ident{display:grid;grid-template-columns:52px minmax(0,1fr) 74px;gap:9px;align-items:center;margin-top:9px}.kdp-face{width:50px;height:50px;border-radius:50%;object-fit:cover;object-position:center top;border:1px solid #35566c;background:#101a23}.kdp-logos{display:flex;gap:4px;justify-content:flex-end}.kdp-team-logo{width:33px;height:33px;object-fit:contain}.kdp-subject{font-size:.98rem;font-weight:950;color:#f8fbff}.kdp-matchup{color:#8299ab;font-size:.52rem;margin-top:3px}.kdp-pick{color:#bfe9f8;font-size:.62rem;font-weight:950;margin-top:5px}
.kdp-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:10px}.kdp-metric{border:1px solid #20384b;border-radius:10px;background:#07131d;padding:7px}.kdp-metric b{display:block;color:#f5f9fc;font-size:.78rem}.kdp-metric span{display:block;color:#667f93;font-size:.35rem;text-transform:uppercase;font-weight:950}.kdp-why,.kdp-risk{margin-top:8px;border-radius:9px;padding:9px 10px}.kdp-why{border-left:3px solid #38bdf8;background:#0a1b27}.kdp-risk{border-left:3px solid #7b6a3d;background:#17170f}.kdp-why b,.kdp-risk b{display:block;font-size:.53rem}.kdp-why b{color:#bcecff}.kdp-risk b{color:#e8d38c}.kdp-why span,.kdp-risk span{display:block;font-size:.46rem;line-height:1.45;margin-top:3px}.kdp-why span{color:#99adbc}.kdp-risk span{color:#aaa184}.kdp-foot{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;border-top:1px solid #1b3040;margin-top:9px;padding-top:7px;color:#70889a;font-size:.41rem}.kdp-foot strong{color:#91d3e9}
@media(max-width:760px){.kdp-summary,.kdp-status-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.kdp-grid{grid-template-columns:1fr}.kdp-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.kdp-shell{padding:14px}}
</style>
"""


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _selected_day() -> date:
    if st is not None:
        value = getattr(st, "session_state", {}).get("nfl_v1_date")
        if isinstance(value, datetime): return value.date()
        if isinstance(value, date): return value
        if isinstance(value, str):
            try: return date.fromisoformat(value[:10])
            except ValueError: pass
    return datetime.now(ET).date()


def _fmt(value: Any, digits: int = 1) -> str:
    try: return f"{float(value):.{digits}f}"
    except Exception: return "—"


def _risk(candidate) -> str:
    value = max(0.0, float(candidate.uncertainty))
    return "HIGH" if value >= .20 else "MEDIUM" if value >= .10 else "LOW"


def _kickoff_text(candidate) -> str:
    try: return candidate.kickoff_at.astimezone(ET).strftime("%a %-I:%M %p ET")
    except Exception: return str(candidate.kickoff_at)


def _metadata(candidate) -> dict[str, Any]:
    try: return {str(k): v for k, v in tuple(candidate.metadata or ())}
    except Exception: return {}


def _abbr(value: Any) -> str:
    text = str(value or "").strip().upper()
    return text if text.isalpha() and 2 <= len(text) <= 4 else ""


def _team_logo_url(abbr: Any) -> str:
    team = _abbr(abbr)
    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{team.lower()}.png" if team else ""


def _player_headshot_url(athlete_id: Any) -> str:
    athlete = str(athlete_id or "").strip()
    return f"https://a.espncdn.com/i/headshots/nfl/players/full/{athlete}.png" if athlete.isdigit() else ""


def _rank_badge(rank: int) -> str:
    label = {1: "BEST PICK TODAY", 2: "STRONG EDGE", 3: "TOP VALUE"}.get(int(rank))
    return f"#{int(rank)} • {label}" if label else f"#{int(rank)}"


def _display_market_state(raw_state: Any) -> tuple[str, str]:
    state = str(raw_state or "").upper()
    if state == "READY": return "QUALIFIED NOW", "ready"
    if state == "STALE": return "REFRESHING", "stale"
    if state == "ERROR": return "SOURCE CHECK", "error"
    return "CONNECTED • NO QUALIFIED PICK", "connected"


def _why_detail(candidate, rank: int) -> str:
    probability = 100.0 * float(candidate.model_probability)
    parts = [f"The source-owned model gives this {candidate.side} position a {probability:.1f}% probability."]
    if candidate.market_line is not None and candidate.model_projection is not None:
        gap = abs(float(candidate.model_projection) - float(candidate.market_line))
        unit = "yards" if candidate.market_id.endswith("yards") else "points"
        parts.append(f"Market {_fmt(candidate.market_line)} vs model {_fmt(candidate.model_projection)} creates a {gap:.1f}-{unit} projection edge.")
    reasons = [str(x).strip() for x in tuple(candidate.reason_components or ()) if str(x).strip()]
    if reasons: parts.append(reasons[0].rstrip(".") + ".")
    if rank <= 3: parts.append("It ranks above other qualified future-game candidates after probability, edge, quality, freshness, uncertainty and correlation checks.")
    return " ".join(parts)


def _default_risk(candidate) -> str:
    age = max(0.0, float(candidate.source_age_seconds)); limit = max(1.0, float(candidate.freshness_limit_seconds))
    if _risk(candidate) == "HIGH": return "Model uncertainty is elevated, so normal game variance can erase the projected edge faster than usual."
    if age / limit >= .70: return "The snapshot is nearing its freshness limit; a new line or availability update could change the value."
    return "Normal game variance plus late line, injury or availability movement can change the edge before kickoff."


def _card_payload(candidate, rank: int) -> dict[str, Any]:
    meta = _metadata(candidate)
    team = _abbr(meta.get("team_abbr")) or _abbr(candidate.team_id)
    opp = _abbr(meta.get("opponent_abbr")) or _abbr(candidate.opponent_team_id)
    line, projection = candidate.market_line, candidate.model_projection
    gap = round(abs(float(projection) - float(line)), 1) if line is not None and projection is not None else None
    edge_label = "Projection Edge" if gap is not None else "Model Edge"
    edge_value = gap if gap is not None else round(abs(float(candidate.edge_value)), 3)
    line_open = meta.get("line_open")
    line_move = f"{float(line_open):.1f} → {float(line):.1f}" if line_open is not None and line is not None else ""
    context_tags = tuple(str(meta[k]).strip() for k in ("weather", "availability", "matchup_edge") if str(meta.get(k) or "").strip())
    reasons = tuple(str(x).strip() for x in tuple(candidate.reason_components or ()) if str(x).strip())
    why_points = [f"{100*float(candidate.model_probability):.1f}% source-owned model probability"]
    if gap is not None:
        unit = "yards" if candidate.market_id.endswith("yards") else "points"
        why_points.append(f"{gap:.1f}-{unit} model-to-market projection edge")
    why_points.extend(reasons[:3])
    risk_reason = str(meta.get("risk_reason") or "").strip() or _default_risk(candidate)
    return {
        "rank":rank,"rank_badge":_rank_badge(rank),"rank_label":_rank_badge(rank).split("•")[-1].strip(),
        "market":candidate.market_label,"market_id":candidate.market_id,"subject":candidate.subject_label,"matchup":candidate.matchup_label,
        "line":line,"side":candidate.side,"probability":candidate.model_probability,"projection":projection,
        "edge":candidate.edge_value,"edge_label":edge_label,"edge_value":edge_value,"projection_gap":gap,"line_movement":line_move,
        "confidence":candidate.source_grade or "QUALIFIED","why":" • ".join(reasons) or "Source-owned eligible result.",
        "why_title":f"Why this is #{rank}","why_detail":_why_detail(candidate,rank),"why_points":tuple(why_points),
        "risk":_risk(candidate),"risk_detail":risk_reason,"risk_reason":risk_reason,"freshness":f"{max(0.0,float(candidate.source_age_seconds)):.0f}s old",
        "kickoff":_kickoff_text(candidate),"quality":candidate.data_quality,"score":normalized_pick_score(candidate),"source_version":candidate.source_version,
        "team_logo_url":_team_logo_url(team),"opponent_logo_url":_team_logo_url(opp),"player_headshot_url":_player_headshot_url(candidate.athlete_id),
        "headshot_url":_player_headshot_url(candidate.athlete_id),"team_abbr":team,"opponent_abbr":opp,"athlete_id":candidate.athlete_id,"context_tags":context_tags,
    }


def _access_state(raw: Any) -> str:
    state = str(raw or "").upper()
    return state if state in {"READY","STALE","ERROR"} else "CONNECTED"


def build_daily_picks_board(day: date, *, now_utc: datetime, loaders: Mapping[str, Callable] | None = None) -> dict[str, Any]:
    results = load_all_market_candidates(day, now_utc=now_utc, loaders=loaders)
    by_market = {r.market_id:r for r in results}
    statuses = {m:(by_market[m].status if m in by_market else "UNAVAILABLE") for m in MARKET_ORDER}
    candidates = tuple(c for r in results if str(r.status or "").upper()=="READY" for c in r.candidates)
    ranked = rank_daily_picks(candidates, now_utc=now_utc, limit=10)
    return {
        "market_statuses":statuses,"market_access_statuses":{m:_access_state(statuses[m]) for m in MARKET_ORDER},
        "ranked_picks":tuple(_card_payload(c,i) for i,c in enumerate(ranked,1)),"picks":ranked,
        "healthy_market_count":sum(str(v).upper()=="READY" for v in statuses.values()),"connected_market_count":len(MARKET_ORDER),
        "candidate_count":len(candidates),"qualified_game_count":len({str(c.game_id) for c in candidates}),
        "diagnostics":{m:(by_market[m].diagnostic if m in by_market else "No source result returned.") for m in MARKET_ORDER},"day":day,
    }


def _status_html(board: Mapping[str, Any]) -> str:
    statuses = dict(board.get("market_statuses") or {})
    blocks=[]
    detail={"ready":"Qualified future-game picks available","connected":"Daily Picks access live • scanning source-owned signals","stale":"Connected • waiting for fresh data","error":"Connected • source temporarily unavailable"}
    for market_id in MARKET_ORDER:
        label,css=_display_market_state(statuses.get(market_id))
        blocks.append(f'<div class="kdp-status {css}"><b>{escape(MARKET_LABELS[market_id])}</b><span>{escape(label)}</span><em>{escape(detail[css])}</em></div>')
    return '<div class="kdp-status-grid">'+''.join(blocks)+'</div>'


def _img(url: Any, css: str, alt: str) -> str:
    value=str(url or "").strip()
    if not value.startswith("https://"): return f'<span class="{css}" aria-hidden="true"></span>' if css=="kdp-face" else ""
    return f'<img class="{css}" src="{escape(value,quote=True)}" alt="{escape(alt,quote=True)}" loading="lazy" decoding="async" />'


def _card_html(card: Mapping[str, Any]) -> str:
    rank=int(card.get("rank") or 0); top=f" top{rank}" if rank in {1,2,3} else ""; gold=" gold" if rank==1 else ""
    probability=f"{100*float(card.get('probability') or 0):.1f}%"; line=_fmt(card.get("line")); projection=_fmt(card.get("projection")); edge=_fmt(card.get("edge_value"),1)
    face=_img(card.get("player_headshot_url"),"kdp-face",f"{card.get('subject','Player')} headshot")
    logos='<div class="kdp-logos">'+_img(card.get("team_logo_url"),"kdp-team-logo",f"{card.get('team_abbr','Team')} logo")+_img(card.get("opponent_logo_url"),"kdp-team-logo",f"{card.get('opponent_abbr','Opponent')} logo")+'</div>'
    tags=''.join(f'<span class="kdp-chip">{escape(str(x))}</span>' for x in tuple(card.get("context_tags") or ()))
    why=''.join(f'<span>• {escape(str(x))}</span>' for x in tuple(card.get("why_points") or ())[:4])
    move=str(card.get("line_movement") or "").strip(); move_html=f'<span>Line move <strong>{escape(move)}</strong></span>' if move else ""
    return (
        f'<article class="kdp-card{top}"><div class="kdp-top"><div><div class="kdp-rank{gold}">{escape(str(card.get("rank_badge") or _rank_badge(rank)))}</div><div class="kdp-market">{escape(str(card.get("market") or ""))}</div></div><div class="kdp-market">{escape(str(card.get("confidence") or "QUALIFIED"))}</div></div>'
        f'<div class="kdp-ident">{face}<div><div class="kdp-subject">{escape(str(card.get("subject") or ""))}</div><div class="kdp-matchup">{escape(str(card.get("matchup") or ""))}</div><div class="kdp-pick">{escape(str(card.get("side") or ""))}{(" • "+line) if line!="—" else ""}</div></div>{logos}</div>'
        + (f'<div class="kdp-chiprow">{tags}</div>' if tags else '')
        + f'<div class="kdp-metrics"><div class="kdp-metric"><b>{probability}</b><span>Model Probability</span></div><div class="kdp-metric"><b>{line}</b><span>Market Line</span></div><div class="kdp-metric"><b>{projection}</b><span>Model Projection</span></div><div class="kdp-metric"><b>{edge}</b><span>{escape(str(card.get("edge_label") or "Model Edge"))}</span></div></div>'
        f'<div class="kdp-why"><b>💡 Why this is a top pick</b>{why}<span>{escape(str(card.get("why_detail") or card.get("why") or ""))}</span></div>'
        f'<div class="kdp-risk"><b>⚠️ What could go wrong?</b><span>{escape(str(card.get("risk_reason") or "Normal game variance can beat any projection."))}</span></div>'
        f'<div class="kdp-foot"><span><strong>✓ Source verified</strong> • updated {escape(str(card.get("freshness") or ""))}</span>{move_html}<span>{escape(str(card.get("kickoff") or ""))} • risk {escape(str(card.get("risk") or ""))}</span></div></article>'
    )


def render_nfl_daily_picks_hub() -> None:
    if st is None: raise RuntimeError("Streamlit is required to render NFL Daily Picks.")
    day=_selected_day(); board=build_daily_picks_board(day,now_utc=_now_utc()); cards=tuple(board.get("ranked_picks") or ())
    st.markdown(_CSS+'<section class="kdp-shell"><div class="kdp-eyebrow">NFL • DAILY PICKS • PREMIUM INTELLIGENCE</div><div class="kdp-title">🏆 NFL Daily Picks <span>Premium</span></div><div class="kdp-sub">Best qualified opportunities across all six NFL markets. Every card explains why it ranked and what can go wrong.</div><div class="kdp-chiprow"><span class="kdp-chip">6 MARKETS CONNECTED</span><span class="kdp-chip">FUTURE GAMES ONLY</span><span class="kdp-chip">NO FILLER</span><span class="kdp-chip">EXACT-ID DATA</span></div></section>',unsafe_allow_html=True)
    st.markdown(f'<div class="kdp-summary"><div><b>{board["connected_market_count"]}/6</b><span>Markets Connected</span></div><div><b>{board["candidate_count"]}</b><span>Qualified Candidates</span></div><div><b>{len(cards)}</b><span>Best Picks Published</span></div><div><b>{escape(str(day))}</b><span>Pregame Slate</span></div></div>',unsafe_allow_html=True)
    st.markdown(_status_html(board),unsafe_allow_html=True)
    if cards: st.markdown('<div class="kdp-grid">'+''.join(_card_html(c) for c in cards)+'</div>',unsafe_allow_html=True)
    else: st.info(ZERO_STATE+" All six market families remain connected and scanning; weak or incomplete signals are never used as filler.")
    st.caption(f"{MODEL_VERSION} • 6/6 market families connected • future kickoffs only • no synthetic probabilities • no filler")


def render_nfl_hub(market: str = "Daily Picks") -> None:
    if str(market or "Daily Picks")!="Daily Picks": raise ValueError("NFL Daily Picks V2 only renders the Daily Picks market.")
    return render_nfl_daily_picks_hub()


__all__=["ET","MARKET_LABELS","MARKET_ORDER","MODEL_VERSION","ZERO_STATE","_card_html","_card_payload","_display_market_state","_player_headshot_url","_rank_badge","_status_html","_team_logo_url","build_daily_picks_board","render_nfl_daily_picks_hub","render_nfl_hub"]
