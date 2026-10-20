"""Professional NBA PRA Page 1 V2 presentation helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Any, Mapping, Sequence

TEAM_LOGO_BASE = "https://a.espncdn.com/i/teamlogos/nba/500/{code}.png"
FILTER_OPTIONS = ("BEST EDGES", "ALL PLAYERS", "OVER", "UNDER", "HIGH CONFIDENCE")
SESSION_PLAYER = "ks_nba_pra_selected_player"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _fmt(value: Any, digits: int = 1, missing: str = "—") -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return missing


def _price(value: Any) -> str:
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return "—"
    return f"+{number}" if number > 0 else str(number)


def _parse_utc(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def freshness_label(observed_at_utc: Any, now_utc: datetime) -> tuple[str, str]:
    observed = _parse_utc(observed_at_utc)
    if observed is None:
        return "Timestamp unavailable", "unknown"
    now = now_utc if now_utc.tzinfo is not None else now_utc.replace(tzinfo=timezone.utc)
    seconds = max(0, int((now.astimezone(timezone.utc) - observed).total_seconds()))
    if seconds < 60:
        label = f"Updated {seconds} sec ago"
    elif seconds < 3600:
        label = f"Updated {seconds // 60} min ago"
    else:
        label = f"Updated {seconds // 3600} hr ago"
    return label, "fresh" if seconds <= 120 else "stale"


def _probability_text(grade: Mapping[str, Any]) -> str:
    try:
        over = float(grade.get("over_probability"))
    except (TypeError, ValueError):
        return "—"
    shown = 1.0 - over if _text(grade.get("lean")).upper() == "UNDER" else over
    return f"{shown * 100:.0f}%"


def _why_text(item: Mapping[str, Any]) -> str:
    q, model, grade = item.get("featured_quote") or {}, item.get("model") or {}, item.get("grade") or {}
    current = model.get("current") or {}
    pieces: list[str] = []
    lean = _text(grade.get("lean")).upper()
    if lean in {"OVER", "UNDER"}:
        pieces.append(f"{lean} lean")
    if model.get("projection") is not None and q.get("line") is not None:
        edge = float(model["projection"]) - float(q["line"])
        pieces.append(f"Model is {abs(edge):.1f} PRA {'above' if edge > 0 else 'below' if edge < 0 else 'at'} {q.get('sportsbook') or 'market'} line")
    if current.get("l5") is not None:
        pieces.append(f"L5 PRA {_fmt(current.get('l5'))}")
    if current.get("minutes") is not None:
        pieces.append(f"current minutes avg {_fmt(current.get('minutes'))}")
    return " • ".join(pieces[:4]) or "Model/history evidence is still building"


def build_game_card_html(game: Mapping[str, Any]) -> str:
    away, home = _text(game.get("away_tricode")) or "—", _text(game.get("home_tricode")) or "—"
    tip = _text(game.get("tip_phoenix") or game.get("game_time_phoenix") or game.get("tip_local")) or "Time pending"
    venue = _text(game.get("venue") or game.get("arena"))
    away_logo, home_logo = TEAM_LOGO_BASE.format(code=away.lower()), TEAM_LOGO_BASE.format(code=home.lower())
    meta = escape(tip) + (f" • {escape(venue)}" if venue else "")
    return (
        '<div class="np2-game-card"><div class="np2-game-state">UPCOMING</div><div class="np2-matchup">'
        f'<div class="np2-team"><img src="{escape(away_logo)}" alt="{escape(away)}"><b>{escape(away)}</b></div>'
        '<span class="np2-at">@</span>'
        f'<div class="np2-team"><img src="{escape(home_logo)}" alt="{escape(home)}"><b>{escape(home)}</b></div>'
        f'</div><div class="np2-game-meta">{meta}</div></div>'
    )


def build_player_card_html(item: Mapping[str, Any], *, rank: int | None = None, now_utc: datetime | None = None) -> str:
    now = now_utc or datetime.now(timezone.utc)
    name, team, position = _text(item.get("player_name")) or "Player", _text(item.get("team")) or "NBA", _text(item.get("position"))
    headshot, stats_source = _text(item.get("headshot")), _text(item.get("stats_source")) or "History unavailable"
    availability = _text(item.get("availability")) or "No verified injury flag"
    featured, quotes, model, grade = item.get("featured_quote") or {}, list(item.get("quotes") or []), item.get("model") or {}, item.get("grade") or {}
    current = model.get("current") or {}
    lean = _text(grade.get("lean")).upper() or "PASS"
    confidence = _text(grade.get("confidence")).upper() or "UNAVAILABLE"
    freshness, fresh_state = freshness_label(featured.get("observed_at_utc"), now)
    accent = "over" if lean == "OVER" else "under" if lean == "UNDER" else "neutral"
    image = f'<img class="np2-headshot" src="{escape(headshot)}" alt="{escape(name)}">' if headshot else '<div class="np2-headshot np2-headshot-fallback">NBA</div>'
    rank_html = f'<span class="np2-rank">#{rank}</span>' if rank else ""
    quote_html = []
    for q in quotes:
        q_fresh, q_state = freshness_label(q.get("observed_at_utc"), now)
        quote_html.append('<div class="np2-book">'
            f'<div><b>{escape(_text(q.get("sportsbook")))}</b><span>{_fmt(q.get("line"))}</span></div>'
            f'<small>O {_price(q.get("over_price"))} • U {_price(q.get("under_price"))}</small>'
            f'<em class="np2-{q_state}">{escape(q_fresh)}</em></div>')
    books = "".join(quote_html) or '<div class="np2-book-empty">No verified sportsbook quote</div>'
    meta = " • ".join(v for v in (team, position, stats_source) if v)
    return f'''<div class="np2-player-card np2-{accent}">
<div class="np2-player-top">{rank_html}{image}<div class="np2-player-id"><div class="np2-player-name">{escape(name)}</div><div class="np2-player-meta">{escape(meta)}</div></div><div class="np2-lean-badge">{escape(lean)}</div></div>
<div class="np2-primary-grid">
<div class="np2-metric"><small>PRA LINE • {escape(_text(featured.get('sportsbook')) or '—')}</small><strong>{_fmt(featured.get('line'))}</strong><span>O {_price(featured.get('over_price'))} / U {_price(featured.get('under_price'))}</span></div>
<div class="np2-metric"><small>KYRE AI</small><strong>{_fmt(model.get('projection'), 1, 'BUILDING')}</strong><span>projection</span></div>
<div class="np2-metric"><small>{escape(lean if lean in {'OVER','UNDER'} else 'MODEL')} PROBABILITY</small><strong>{_probability_text(grade)}</strong><span>{escape(confidence)} confidence</span></div>
<div class="np2-metric"><small>MODEL EDGE</small><strong>{_fmt(grade.get('edge'))}</strong><span>PRA vs featured line</span></div>
</div>
<div class="np2-support-row"><span><b>L5</b> {_fmt(current.get('l5'))}</span><span><b>L10</b> {_fmt(current.get('l10'))}</span><span><b>MIN</b> {_fmt(current.get('minutes'))}</span><span><b>AVAILABILITY</b> {escape(availability)}</span></div>
<div class="np2-books-label">SPORTSBOOK MARKET • quotes are never averaged</div><div class="np2-books">{books}</div>
<div class="np2-why"><b>WHY THE MODEL LIKES IT</b><span>{escape(_why_text(item))}</span></div>
<div class="np2-card-foot"><span class="np2-{fresh_state}">● {escape(freshness)}</span><span>Sportsbook projection influence 0.0%</span></div></div>'''


def dashboard_kpis(items: Sequence[Mapping[str, Any]], *, now_utc: datetime | None = None) -> dict[str, Any]:
    now = now_utc or datetime.now(timezone.utc)
    over_edges = [float((x.get("grade") or {})["edge"]) for x in items if (x.get("grade") or {}).get("lean") == "OVER" and (x.get("grade") or {}).get("edge") is not None]
    under_edges = [float((x.get("grade") or {})["edge"]) for x in items if (x.get("grade") or {}).get("lean") == "UNDER" and (x.get("grade") or {}).get("edge") is not None]
    fresh = sum(freshness_label((x.get("featured_quote") or {}).get("observed_at_utc"), now)[1] == "fresh" for x in items)
    return {"players_tracked": len(items), "best_over_edge": max(over_edges) if over_edges else None, "best_under_edge": min(under_edges) if under_edges else None, "fresh_quotes": fresh}


def css() -> str:
    return r'''<style>
.np2-hero{padding:18px 20px;border:1px solid #1f516b;border-radius:22px;background:radial-gradient(circle at 90% 0,#0c3a52 0,#071520 42%,#03080d 100%);margin:8px 0 12px;box-shadow:0 12px 36px rgba(0,0,0,.24)}
.np2-kicker{color:#73dcff;font-size:.73rem;font-weight:900;letter-spacing:.16em}.np2-title{font-size:2rem;font-weight:950;color:#fff;line-height:1.05;margin:7px 0}.np2-sub{color:#9cb2c1;font-size:.92rem;line-height:1.5}.np2-status{display:flex;gap:7px;flex-wrap:wrap;margin-top:11px}.np2-status span{border:1px solid #1d4054;border-radius:999px;padding:5px 9px;color:#ccefff;background:#07131d;font-size:.72rem}
.np2-kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:10px 0 15px}.np2-kpi{background:#06111a;border:1px solid #16384b;border-radius:14px;padding:11px}.np2-kpi small{display:block;color:#7290a3;font-size:.63rem;letter-spacing:.08em}.np2-kpi b{display:block;color:#f4fbff;font-size:1.25rem;margin-top:3px}.np2-kpi em{font-style:normal;color:#7adfff;font-size:.68rem}.np2-sec{display:flex;justify-content:space-between;align-items:end;margin:18px 1px 8px}.np2-sec b{color:#eafaff;font-size:.86rem;letter-spacing:.12em}.np2-sec span{color:#6f899b;font-size:.7rem}
.np2-games{display:flex;gap:8px;overflow-x:auto;padding:2px 0 10px}.np2-game-card{min-width:210px;border:1px solid #173c51;border-radius:16px;padding:12px;background:linear-gradient(145deg,#07131e,#03080d)}.np2-game-state{font-size:.61rem;color:#70e7b1;font-weight:900;letter-spacing:.12em}.np2-matchup{display:flex;align-items:center;justify-content:center;gap:9px;margin:8px 0}.np2-team{display:flex;align-items:center;gap:5px;color:#fff}.np2-team img{width:32px;height:32px;object-fit:contain}.np2-at{color:#567183}.np2-game-meta{color:#8da5b5;font-size:.7rem}
.np2-player-card{border:1px solid #173f55;border-radius:19px;padding:14px;background:linear-gradient(152deg,#071621 0,#040b11 58%,#03070b 100%);margin:0 0 11px;box-shadow:0 10px 28px rgba(0,0,0,.16)}.np2-player-card.np2-over{border-color:#176648}.np2-player-card.np2-under{border-color:#6b2a35}.np2-player-top{display:flex;align-items:center;gap:9px}.np2-rank{font-size:.68rem;font-weight:900;color:#7de2ff;background:#092334;border:1px solid #1d526d;border-radius:999px;padding:4px 6px}.np2-headshot{width:50px;height:50px;border-radius:14px;object-fit:cover;background:#0a1720}.np2-headshot-fallback{display:flex;align-items:center;justify-content:center;color:#74dfff;font-size:.7rem;font-weight:900}.np2-player-id{flex:1;min-width:0}.np2-player-name{color:#fff;font-size:1.05rem;font-weight:950}.np2-player-meta{color:#7f9aac;font-size:.7rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.np2-lean-badge{font-weight:950;font-size:.72rem;border-radius:999px;padding:5px 8px;color:#fff;background:#123345}.np2-over .np2-lean-badge{background:#0d4a35}.np2-under .np2-lean-badge{background:#54232d}
.np2-primary-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin:11px 0}.np2-metric{border:1px solid #123448;border-radius:12px;padding:8px;background:#071925;min-width:0}.np2-metric small{display:block;color:#7893a5;font-size:.57rem;letter-spacing:.04em}.np2-metric strong{display:block;color:#f4fbff;font-size:1.25rem}.np2-metric span{display:block;color:#7893a5;font-size:.6rem}.np2-support-row{display:flex;gap:6px;flex-wrap:wrap}.np2-support-row span{border-radius:999px;background:#081824;border:1px solid #123447;padding:5px 7px;color:#9eb4c3;font-size:.64rem}.np2-support-row b{color:#d7f4ff}.np2-books-label{color:#6f91a5;font-size:.59rem;font-weight:900;letter-spacing:.09em;margin:10px 0 5px}.np2-books{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}.np2-book{border:1px solid #15384c;border-radius:11px;padding:7px;background:#06131d}.np2-book div{display:flex;justify-content:space-between;color:#dff7ff;font-size:.69rem}.np2-book small{display:block;color:#8da4b3;font-size:.62rem}.np2-book em{display:block;font-style:normal;font-size:.54rem;margin-top:3px}.np2-why{border-top:1px solid #102a38;margin-top:10px;padding-top:8px}.np2-why b{display:block;color:#75dcff;font-size:.6rem;letter-spacing:.09em}.np2-why span{color:#adc1ce;font-size:.69rem}.np2-card-foot{display:flex;justify-content:space-between;gap:8px;color:#698397;font-size:.58rem;margin-top:7px}.np2-fresh{color:#65dda3!important}.np2-stale{color:#f0bd6c!important}.np2-unknown{color:#8697a3!important}.np2-book-empty{color:#8499a7;font-size:.68rem}
@media(max-width:720px){.np2-title{font-size:1.55rem}.np2-kpis{grid-template-columns:repeat(2,1fr)}.np2-primary-grid{grid-template-columns:repeat(2,1fr)}.np2-books{grid-template-columns:1fr}.np2-player-card{padding:12px}.np2-card-foot{flex-direction:column}.np2-game-card{min-width:190px}}
</style>'''
