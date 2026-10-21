'''Professional NBA PRA Page 1 V2 presentation helpers.'''
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


def _signed(value: Any, digits: int = 1, missing: str = "—") -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return missing
    return f"{number:+.{digits}f}"


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


def _edge_score(grade: Mapping[str, Any]) -> tuple[str, str]:
    lean = _text(grade.get("lean")).upper()
    if lean not in {"OVER", "UNDER"}:
        return "—", "PASS"
    try:
        edge = abs(float(grade.get("edge")))
        over_probability = float(grade.get("over_probability"))
    except (TypeError, ValueError):
        return "—", "PASS"
    shown_probability = 1.0 - over_probability if lean == "UNDER" else over_probability
    if not 0.0 <= shown_probability <= 1.0:
        return "—", "PASS"
    score = min(10.0, max(0.0, 5.0 + edge * 0.5 + (shown_probability - 0.5) * 10.0))
    tier = "ELITE" if score >= 9.0 else "STRONG" if score >= 7.5 else "LEAN" if score >= 6.5 else "PASS"
    return f"{score:.1f}", tier


def _why_text(item: Mapping[str, Any]) -> str:
    q, model, grade = item.get("featured_quote") or {}, item.get("model") or {}, item.get("grade") or {}
    current = model.get("current") or {}
    pieces: list[str] = []
    lean = _text(grade.get("lean")).upper()
    if lean in {"OVER", "UNDER"}:
        pieces.append(f"{lean} lean")
    if model.get("projection") is not None and q.get("line") is not None:
        edge = float(model["projection"]) - float(q["line"])
        pieces.append(f"Model {abs(edge):.1f} PRA {'above' if edge > 0 else 'below' if edge < 0 else 'at'} line")
    if current.get("l5") is not None:
        pieces.append(f"L5 {_fmt(current.get('l5'))}")
    if current.get("minutes") is not None:
        pieces.append(f"{_fmt(current.get('minutes'))} min")
    return " • ".join(pieces[:4]) or "Model/history evidence pending"


def _identity_html(item: Mapping[str, Any], *, compact: bool = False) -> str:
    name = _text(item.get("player_name")) or "Player"
    team = _text(item.get("team")) or "NBA"
    position = _text(item.get("position"))
    headshot = _text(item.get("headshot"))
    stats_source = _text(item.get("stats_source")) or "History unavailable"
    avatar_class = "np3-avatar np3-avatar-sm" if compact else "np3-avatar"
    image = (
        f'<img class="{avatar_class}" src="{escape(headshot)}" alt="{escape(name)}">'
        if headshot
        else f'<div class="{avatar_class} np3-avatar-fallback">NBA</div>'
    )
    logo = ""
    if len(team) == 3 and team.isalpha():
        logo_url = TEAM_LOGO_BASE.format(code=team.lower())
        logo = f'<img class="np3-team-badge" src="{escape(logo_url)}" alt="{escape(team)} logo">'
    meta = " • ".join(v for v in (team, position, stats_source) if v)
    return (
        f'<div class="np3-id"><div class="np3-avatar-wrap">{image}{logo}</div>'
        f'<div class="np3-id-copy"><strong>{escape(name)}</strong><span>{escape(meta)}</span></div></div>'
    )


def build_game_card_html(game: Mapping[str, Any]) -> str:
    away = _text(game.get("away_tricode")) or "—"
    home = _text(game.get("home_tricode")) or "—"
    tip = _text(game.get("tip_phoenix") or game.get("game_time_phoenix") or game.get("tip_local")) or "Time pending"
    venue = _text(game.get("venue") or game.get("arena"))
    away_logo = TEAM_LOGO_BASE.format(code=away.lower())
    home_logo = TEAM_LOGO_BASE.format(code=home.lower())
    meta = escape(tip) + (f" • {escape(venue)}" if venue else "")
    return (
        '<div class="np3-game-card np2-game-card"><div class="np3-game-state">UPCOMING</div>'
        '<div class="np3-matchup">'
        f'<div class="np3-team"><img src="{escape(away_logo)}" alt="{escape(away)}"><b>{escape(away)}</b></div>'
        '<span class="np3-at">@</span>'
        f'<div class="np3-team"><img src="{escape(home_logo)}" alt="{escape(home)}"><b>{escape(home)}</b></div>'
        f'</div><div class="np3-game-meta">{meta}</div></div>'
    )


def build_leaderboard_row_html(
    item: Mapping[str, Any], *, rank: int, now_utc: datetime | None = None
) -> str:
    now = now_utc or datetime.now(timezone.utc)
    featured = item.get("featured_quote") or {}
    model = item.get("model") or {}
    grade = item.get("grade") or {}
    current = model.get("current") or {}
    lean = _text(grade.get("lean")).upper() if _text(grade.get("lean")) else "PASS"
    confidence = _text(grade.get("confidence")).upper() or "UNAVAILABLE"
    score, tier = _edge_score(grade)
    fresh, fresh_state = freshness_label(featured.get("observed_at_utc"), now)
    accent = "over" if lean == "OVER" else "under" if lean == "UNDER" else "neutral"
    projection = _fmt(model.get("projection"), 1, "—")
    probability = _probability_text(grade)
    edge = _signed(grade.get("edge"))
    return f'''<article class="np3-leader-row np3-{accent}">
<div class="np3-rank">#{rank}</div>
{_identity_html(item)}
<div class="np3-decision"><small>LINE</small><b>{_fmt(featured.get("line"))}</b><span>{escape(_text(featured.get("sportsbook")) or "—")}</span></div>
<div class="np3-decision"><small>PROJ</small><b>{projection}</b><span>Kyre AI</span></div>
<div class="np3-decision"><small>EDGE</small><b>{edge}</b><span>PRA</span></div>
<div class="np3-decision"><small>PROB</small><b>{probability}</b><span>{escape(confidence)}</span></div>
<div class="np3-form"><small>FORM</small><span><b>L5</b> {_fmt(current.get("l5"))}</span><span><b>L10</b> {_fmt(current.get("l10"))}</span></div>
<div class="np3-edge-score"><small>KYRE EDGE</small><b>{escape(score)}</b><span>{escape(tier)}</span></div>
<div class="np3-side np3-side-{accent}">{escape(lean)}</div>
<div class="np3-row-fresh np2-{fresh_state}">{escape(fresh)}</div>
</article>'''


def _quote_pills(quotes: Sequence[Mapping[str, Any]], now: datetime) -> str:
    rows = []
    for quote in quotes:
        fresh, state = freshness_label(quote.get("observed_at_utc"), now)
        sportsbook = _text(quote.get("sportsbook")) or "Book"
        rows.append(
            '<span class="np3-book-pill">'
            f'<b>{escape(sportsbook)}</b>'
            f'<strong>{_fmt(quote.get("line"))}</strong>'
            f'<em>O {_price(quote.get("over_price"))} · U {_price(quote.get("under_price"))}</em>'
            f'<i class="np2-{state}">{escape(fresh)}</i></span>'
        )
    return "".join(rows) or '<span class="np3-book-empty">No verified sportsbook quote</span>'


def build_market_row_html(item: Mapping[str, Any], *, now_utc: datetime | None = None) -> str:
    now = now_utc or datetime.now(timezone.utc)
    featured = item.get("featured_quote") or {}
    model = item.get("model") or {}
    grade = item.get("grade") or {}
    current = model.get("current") or {}
    lean = _text(grade.get("lean")).upper() if _text(grade.get("lean")) else "PASS"
    confidence = _text(grade.get("confidence")).upper() or "UNAVAILABLE"
    score, tier = _edge_score(grade)
    accent = "over" if lean == "OVER" else "under" if lean == "UNDER" else "neutral"
    projection = _fmt(model.get("projection"), 1, "—")
    edge = _signed(grade.get("edge"))
    probability = _probability_text(grade)
    availability = _text(item.get("availability")) or "No verified injury flag"
    books = _quote_pills(list(item.get("quotes") or []), now)
    return f'''<article class="np3-market-row np2-player-card np3-{accent}">
<div class="np3-market-main">
{_identity_html(item, compact=True)}
<div class="np3-market-metrics">
<span><small>LINE</small><b>{_fmt(featured.get("line"))}</b><em>{escape(_text(featured.get("sportsbook")) or "—")}</em></span>
<span><small>PROJ</small><b>{projection}</b><em>Kyre AI</em></span>
<span><small>EDGE</small><b>{edge}</b><em>PRA</em></span>
<span><small>PROB</small><b>{probability}</b><em>{escape(confidence)}</em></span>
<span><small>SCORE</small><b>{escape(score)}</b><em>{escape(tier)}</em></span>
</div>
<div class="np3-side np3-side-{accent}">{escape(lean)}</div>
</div>
<div class="np3-market-sub">
<span><b>L5</b> {_fmt(current.get("l5"))}</span>
<span><b>L10</b> {_fmt(current.get("l10"))}</span>
<span><b>MIN</b> {_fmt(current.get("minutes"))}</span>
<span><b>STATUS</b> {escape(availability)}</span>
<span class="np3-evidence">{escape(_why_text(item))}</span>
</div>
<div class="np3-book-strip">{books}</div>
</article>'''


def build_kpi_strip_html(kpis: Mapping[str, Any]) -> str:
    over = f"+{float(kpis['best_over_edge']):.1f}" if kpis.get("best_over_edge") is not None else "—"
    under = f"{float(kpis['best_under_edge']):.1f}" if kpis.get("best_under_edge") is not None else "—"
    players = int(kpis.get("players_tracked") or 0)
    freshness = f"{int(kpis.get('fresh_quotes') or 0)}/{players}" if players else "0/0"
    return (
        '<div class="np3-kpi-strip">'
        f'<div><small>PLAYERS</small><b>{players}</b><span>tracked</span></div>'
        f'<div><small>MARKETS</small><b>{players}</b><span>verified PRA</span></div>'
        f'<div><small>BEST OVER</small><b>{over}</b><span>model edge</span></div>'
        f'<div><small>BEST UNDER</small><b>{under}</b><span>model edge</span></div>'
        f'<div><small>FRESH</small><b>{freshness}</b><span>≤120 sec</span></div>'
        '</div>'
    )


def build_player_card_html(item: Mapping[str, Any], *, rank: int | None = None, now_utc: datetime | None = None) -> str:
    now = now_utc or datetime.now(timezone.utc)
    featured = item.get("featured_quote") or {}
    model = item.get("model") or {}
    grade = item.get("grade") or {}
    current = model.get("current") or {}
    lean = _text(grade.get("lean")).upper() or "PASS"
    confidence = _text(grade.get("confidence")).upper() or "UNAVAILABLE"
    freshness, fresh_state = freshness_label(featured.get("observed_at_utc"), now)
    score, tier = _edge_score(grade)
    quotes = _quote_pills(list(item.get("quotes") or []), now)
    rank_html = f'<span class="np2-rank">#{rank}</span>' if rank else ""
    return f'''<div class="np2-player-card">
<div class="np2-player-top">{rank_html}{_identity_html(item)}<div class="np2-edge-badge"><small>KYRE EDGE SCORE</small><strong>{escape(score)}</strong><span>{escape(tier)}</span></div><div class="np2-lean-badge">{escape(lean)}</div></div>
<div class="np2-primary-grid">
<div class="np2-metric"><small>PRA LINE • {escape(_text(featured.get("sportsbook")) or "—")}</small><strong>{_fmt(featured.get("line"))}</strong><span>O {_price(featured.get("over_price"))} / U {_price(featured.get("under_price"))}</span></div>
<div class="np2-metric"><small>KYRE AI PROJECTION</small><strong>{_fmt(model.get("projection"), 1, "—")}</strong><span>projected PRA</span></div>
<div class="np2-metric"><small>{escape(lean if lean in {"OVER", "UNDER"} else "MODEL")} PROBABILITY</small><strong>{_probability_text(grade)}</strong><span>{escape(confidence)} confidence</span></div>
<div class="np2-metric"><small>MODEL EDGE</small><strong>{_fmt(grade.get("edge"))}</strong><span>PRA vs featured line</span></div>
</div>
<div class="np2-support-row"><span><b>L5</b> {_fmt(current.get("l5"))}</span><span><b>L10</b> {_fmt(current.get("l10"))}</span><span><b>MIN</b> {_fmt(current.get("minutes"))}</span></div>
<div class="np2-books-label">LIVE SPORTSBOOK MARKET • quotes stay separate — never averaged</div><div class="np2-books">{quotes}</div>
<div class="np2-why"><b>WHY THE MODEL LIKES IT</b><span>{escape(_why_text(item))}</span></div>
<div class="np2-card-foot"><span class="np2-{fresh_state}">● {escape(freshness)}</span><span>Sportsbook projection influence 0.0%</span></div></div>'''


def dashboard_kpis(items: Sequence[Mapping[str, Any]], *, now_utc: datetime | None = None) -> dict[str, Any]:
    now = now_utc or datetime.now(timezone.utc)
    over_edges = [
        float((x.get("grade") or {})["edge"])
        for x in items
        if (x.get("grade") or {}).get("lean") == "OVER" and (x.get("grade") or {}).get("edge") is not None
    ]
    under_edges = [
        float((x.get("grade") or {})["edge"])
        for x in items
        if (x.get("grade") or {}).get("lean") == "UNDER" and (x.get("grade") or {}).get("edge") is not None
    ]
    fresh = sum(
        freshness_label((x.get("featured_quote") or {}).get("observed_at_utc"), now)[1] == "fresh"
        for x in items
    )
    return {
        "players_tracked": len(items),
        "best_over_edge": max(over_edges) if over_edges else None,
        "best_under_edge": min(under_edges) if under_edges else None,
        "fresh_quotes": fresh,
    }


def css() -> str:
    return r'''<style>
:root{--np3-bg:#05090f;--np3-panel:#08121c;--np3-panel2:#0b1823;--np3-line:#173448;--np3-blue:#79ddff;--np3-text:#f3f9fc;--np3-muted:#7890a2;--np3-green:#46d69a;--np3-red:#ed6f80}
.np3-command{display:grid;grid-template-columns:1.3fr auto;gap:18px;align-items:end;padding:18px 20px;border:1px solid #1b4158;border-radius:20px;background:linear-gradient(135deg,#07131e 0,#091b28 55%,#071018 100%);box-shadow:0 14px 38px rgba(0,0,0,.25);margin:6px 0 10px}.np3-kicker{color:var(--np3-blue);font-size:.68rem;font-weight:900;letter-spacing:.16em}.np3-command h1{color:#fff;font-size:2rem;line-height:1;margin:5px 0 6px}.np3-command p{color:#91a7b6;margin:0;font-size:.82rem;max-width:720px}.np3-command-meta{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}.np3-command-meta span{border:1px solid #1d4257;border-radius:999px;padding:6px 9px;color:#ccefff;background:#071620;font-size:.62rem;font-weight:800}
.np3-section{display:flex;align-items:end;justify-content:space-between;gap:12px;margin:16px 2px 7px}.np3-section b{color:#eafaff;font-size:.76rem;letter-spacing:.12em}.np3-section span{color:#657f91;font-size:.65rem}.np3-games{display:flex;gap:8px;overflow-x:auto;padding:1px 0 9px;scroll-snap-type:x mandatory;-webkit-overflow-scrolling:touch}.np3-game-card{min-width:178px;scroll-snap-align:start;border:1px solid #173a4f;border-radius:14px;padding:10px 11px;background:#07131d}.np3-game-state{color:#67dca4;font-size:.54rem;font-weight:900;letter-spacing:.12em}.np3-matchup{display:flex;align-items:center;justify-content:center;gap:7px;margin:7px 0 5px}.np3-team{display:flex;align-items:center;gap:4px;color:#fff;font-size:.82rem}.np3-team img{width:29px;height:29px;object-fit:contain}.np3-at{color:#527083;font-size:.72rem}.np3-game-meta{color:#7d95a5;font-size:.6rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.np3-kpi-strip{display:grid;grid-template-columns:repeat(5,1fr);border:1px solid #17384d;border-radius:15px;background:#06111a;overflow:hidden;margin:4px 0 12px}.np3-kpi-strip>div{padding:10px 12px;border-right:1px solid #123045;min-width:0}.np3-kpi-strip>div:last-child{border-right:0}.np3-kpi-strip small{display:block;color:#668499;font-size:.52rem;font-weight:900;letter-spacing:.08em}.np3-kpi-strip b{display:block;color:#f5fbff;font-size:1.12rem;margin:1px 0}.np3-kpi-strip span{display:block;color:#6fa8bf;font-size:.54rem;white-space:nowrap}
div[data-testid="stRadio"]{position:sticky;top:.4rem;z-index:20;background:rgba(5,9,15,.96);backdrop-filter:blur(12px);border:1px solid #17384d;border-radius:13px;padding:5px 8px;margin:8px 0 12px}div[data-testid="stRadio"] label{font-size:.72rem!important;font-weight:800!important}
.np3-leaderboard{display:flex;flex-direction:column;gap:6px}.np3-leader-row{display:grid;grid-template-columns:34px minmax(180px,1.55fr) repeat(4,minmax(64px,.6fr)) minmax(100px,.8fr) 74px 68px;gap:9px;align-items:center;border:1px solid #17384d;border-radius:14px;background:linear-gradient(90deg,#07131d,#081824);padding:9px 11px;position:relative}.np3-leader-row:before,.np3-market-row:before{content:"";position:absolute;left:0;top:8px;bottom:8px;width:3px;border-radius:4px;background:#2e7899}.np3-leader-row.np3-over:before,.np3-market-row.np3-over:before{background:var(--np3-green)}.np3-leader-row.np3-under:before,.np3-market-row.np3-under:before{background:var(--np3-red)}
.np3-rank{color:#8de5ff;font-weight:950;font-size:.78rem;text-align:center}.np3-id{display:flex;align-items:center;gap:9px;min-width:0}.np3-avatar-wrap{position:relative;flex:0 0 auto}.np3-avatar{width:48px;height:48px;border-radius:12px;object-fit:cover;background:#0b1d2a;border:1px solid #1c455e}.np3-avatar-sm{width:42px;height:42px;border-radius:10px}.np3-avatar-fallback{display:flex;align-items:center;justify-content:center;color:#7ce1ff;font-size:.62rem;font-weight:900}.np3-team-badge{position:absolute;right:-4px;bottom:-4px;width:20px;height:20px;object-fit:contain;background:#07131d;border:1px solid #2a5369;border-radius:50%;padding:2px}.np3-id-copy{min-width:0}.np3-id-copy strong{display:block;color:#fff;font-size:.88rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.np3-id-copy span{display:block;color:#738c9d;font-size:.57rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px}.np3-decision small,.np3-form small,.np3-edge-score small{display:block;color:#607f94;font-size:.48rem;font-weight:900;letter-spacing:.08em}.np3-decision b,.np3-edge-score b{display:block;color:#f6fbff;font-size:.98rem;line-height:1.1}.np3-decision span,.np3-edge-score span{display:block;color:#7892a5;font-size:.52rem}.np3-form span{display:block;color:#9eb4c3;font-size:.55rem}.np3-form b{color:#dff6ff}.np3-edge-score{border:1px solid #1c4f69;background:#071b29;border-radius:9px;padding:5px 6px;text-align:center}.np3-edge-score span{color:#72ddff;font-weight:900}.np3-side{font-size:.59rem;font-weight:950;border-radius:999px;padding:5px 7px;text-align:center;background:#183245;color:#fff}.np3-side-over{background:#0e4d39}.np3-side-under{background:#5a2630}.np3-row-fresh{position:absolute;right:10px;bottom:4px;font-size:.46rem}
.np3-market-list{display:flex;flex-direction:column;gap:7px}.np3-market-row{position:relative;border:1px solid #153549;border-radius:14px;background:#06111a;padding:9px 10px 8px 12px;margin:0}.np3-market-main{display:grid;grid-template-columns:minmax(185px,1.25fr) minmax(360px,2fr) 68px;gap:11px;align-items:center}.np3-market-metrics{display:grid;grid-template-columns:repeat(5,1fr);gap:6px}.np3-market-metrics span{padding:3px 6px;border-left:1px solid #133349;min-width:0}.np3-market-metrics small{display:block;color:#627f91;font-size:.46rem;font-weight:900;letter-spacing:.07em}.np3-market-metrics b{display:block;color:#f7fbff;font-size:.9rem}.np3-market-metrics em{display:block;color:#718b9d;font-size:.48rem;font-style:normal;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.np3-market-sub{display:flex;gap:12px;align-items:center;flex-wrap:wrap;border-top:1px solid #102b3a;margin-top:7px;padding-top:6px;color:#7f98a9;font-size:.53rem}.np3-market-sub b{color:#d6f3ff}.np3-evidence{margin-left:auto;color:#83cdea}.np3-book-strip{display:flex;gap:5px;overflow-x:auto;margin-top:6px;padding-bottom:1px}.np3-book-pill{display:grid;grid-template-columns:auto auto auto;align-items:center;gap:7px;min-width:max-content;border:1px solid #17394d;border-radius:999px;padding:4px 7px;background:#071722}.np3-book-pill b{color:#dff7ff;font-size:.54rem}.np3-book-pill strong{color:#fff;font-size:.6rem}.np3-book-pill em{color:#8ca5b4;font-size:.49rem;font-style:normal}.np3-book-pill i{font-size:.44rem;font-style:normal}.np3-book-empty{color:#7f94a2;font-size:.55rem}.np2-player-card{border:1px solid #173f55;border-radius:16px;padding:12px;background:#07131d;margin:0 0 10px}.np2-player-top{display:flex;align-items:center;gap:8px}.np2-rank{font-size:.64rem;font-weight:900;color:#7de2ff}.np2-edge-badge{margin-left:auto;border:1px solid #1d526d;border-radius:10px;padding:5px 7px;text-align:center}.np2-edge-badge small,.np2-edge-badge span{display:block;font-size:.48rem;color:#77bfdc}.np2-edge-badge strong{color:#fff}.np2-lean-badge{font-size:.6rem;font-weight:900}.np2-primary-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin:9px 0}.np2-metric{border:1px solid #123448;border-radius:9px;padding:7px}.np2-metric small,.np2-metric span{display:block;font-size:.52rem;color:#7893a5}.np2-metric strong{display:block;color:#fff}.np2-support-row{display:flex;gap:6px}.np2-support-row span{font-size:.53rem;color:#8ca5b4}.np2-books-label,.np2-why,.np2-card-foot{font-size:.52rem;color:#7690a2;margin-top:7px}.np2-books{margin-top:5px}.np2-fresh{color:#5bd59a!important}.np2-stale{color:#efbd6b!important}.np2-unknown{color:#8496a2!important}
@media(max-width:900px){.np3-command{grid-template-columns:1fr}.np3-command-meta{justify-content:flex-start}.np3-leader-row{grid-template-columns:30px minmax(150px,1.4fr) repeat(4,60px) 72px 62px}.np3-form{display:none}.np3-market-main{grid-template-columns:minmax(160px,1fr) minmax(300px,2fr) 62px}.np3-evidence{display:none}}
@media(max-width:720px){.np3-command{padding:14px 14px;border-radius:16px}.np3-command h1{font-size:1.45rem}.np3-command p{font-size:.72rem}.np3-command-meta span{font-size:.54rem;padding:5px 7px}.np3-section{margin-top:13px}.np3-game-card{min-width:164px;padding:9px}.np3-kpi-strip{grid-template-columns:repeat(5,minmax(82px,1fr));overflow-x:auto}.np3-kpi-strip>div{padding:8px 9px}.np3-kpi-strip b{font-size:1rem}.np3-leaderboard{overflow-x:auto}.np3-leader-row{min-width:720px;padding:8px 9px}.np3-market-row{padding:8px 9px 7px 11px}.np3-market-main{grid-template-columns:1fr 64px}.np3-market-metrics{grid-column:1 / -1;grid-row:2;grid-template-columns:repeat(5,1fr);border-top:1px solid #102b3a;padding-top:6px}.np3-market-sub{gap:8px}.np3-market-sub span:nth-child(4){flex-basis:100%}.np3-book-strip{margin-top:5px}.np3-avatar-sm{width:38px;height:38px}.np3-id-copy strong{font-size:.82rem}.np3-side{align-self:start}.np2-primary-grid{grid-template-columns:repeat(2,1fr)}}
</style>'''