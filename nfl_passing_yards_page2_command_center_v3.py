"""NFL Passing Yards Page 2 S-tier V3 presentation successor.

Presentation-only renderer over the verified Kyre Sports API payload. It does
not fetch providers or alter projections, probabilities, markets, identities,
history, or source routing.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Any

import nfl_passing_yards_page2_command_center_v2 as v2

v1 = v2.v1
_e = escape

CSS = r"""
<style>
/* Keep the site-wide shell TOP control; suppress the second native TOP link. */
a[data-kyre-universal-top="v2"]{display:none!important}
.kpy3{max-width:1180px;margin:0 auto;padding:2px 4px 34px;color:#edf6fb}.k3hero,.k3sec{border:1px solid #21465d;background:#0a1a27;border-radius:18px}.k3hero{padding:16px;margin-bottom:12px}.k3sec{padding:15px 17px;margin:0 0 12px}.k3head{display:flex;align-items:center;gap:12px}.k3face{width:58px;height:58px;border:3px solid #347ea7;border-radius:50%;object-fit:cover;background:#07131d}.k3logo{width:44px;height:44px;object-fit:contain;margin-left:auto}.k3kick,.k3title,.k3label{font-weight:950;letter-spacing:.13em}.k3kick{font-size:.68rem;color:#64c7f5}.k3name{font-size:1.52rem;font-weight:950;line-height:1.04}.k3sub{font-size:.78rem;color:#aabcc9;margin-top:4px}.k3title{font-size:.78rem;margin-bottom:12px}.k3herogrid{display:grid;grid-template-columns:1.3fr 1fr 1fr 1fr;gap:9px;margin-top:13px}.k3metric,.k3tile{min-width:0;border:1px solid #2a4c62;background:#071520;border-radius:13px;padding:10px 11px}.k3label{font-size:.55rem;color:#9bb0bf}.k3value{font-size:1.1rem;font-weight:950;margin-top:4px;line-height:1.12}.k3note{font-size:.69rem;color:#9fb2c0;margin-top:4px;line-height:1.35}.k3good{color:#7de2b2}.k3warn{color:#f5c76f}.k3muted{color:#9fb2c0}.k3tablewrap{overflow-x:auto;border:1px solid #28485d;border-radius:12px}.k3table{width:100%;border-collapse:collapse;min-width:720px;font-size:.78rem}.k3table th{font-size:.58rem;letter-spacing:.08em;color:#9db1bf;text-align:left;background:#0d202e}.k3table th,.k3table td{padding:8px 9px;border-bottom:1px solid #263f50;white-space:nowrap}.k3table tr:last-child td{border-bottom:0}.k3res{font-weight:900}.k3res[data-result="OVER"]{color:#75e0ad}.k3res[data-result="UNDER"]{color:#ff9191}.k3-yardcell{min-width:105px}.k3-yardbar{height:4px;background:#1b3343;border-radius:99px;margin-top:4px;position:relative;overflow:visible}.k3-yardfill{height:100%;border-radius:99px;background:#6bc8f3}.k3-linemark{position:absolute;top:-3px;width:2px;height:10px;background:#f5c76f}.k3-hitstrip{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;margin-top:10px}.k3-hit{border:1px solid #29495d;border-radius:12px;padding:9px;background:#081722}.k3-hit .k3value{font-size:.9rem}.k3-progress{height:5px;background:#172d3b;border-radius:99px;overflow:hidden;margin-top:7px}.k3-progress>i{display:block;height:100%;background:#63c8f5}.k3-matchupgrid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.k3panel{border:1px solid #294b60;background:#081823;border-radius:14px;padding:12px}.k3panelhead{font-size:.67rem;font-weight:950;letter-spacing:.1em;color:#7dd3fc;margin-bottom:9px}.k3tiles{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px}.k3tile{padding:8px 9px}.k3tile .k3value{font-size:.95rem}.k3-history-one{display:flex;align-items:center;justify-content:space-between;gap:12px;border:1px solid #2a4b60;border-radius:13px;padding:11px 12px;background:#081722}.k3-history-main{font-size:.84rem;font-weight:900}.k3-history-stats{font-size:.76rem;color:#c8d8e2;text-align:right}.k3status{display:inline-flex;align-items:center;gap:6px;border:1px solid #4d5360;border-radius:999px;padding:6px 9px;font-size:.68rem;font-weight:850}.k3status.pending{border-color:#7a632d;color:#f1cc7b;background:#211b0c}.k3book{display:flex;align-items:center;justify-content:space-between;gap:10px;border:1px solid #294b60;border-radius:12px;padding:10px 11px;margin-top:8px}.k3bookname{font-size:.86rem;font-weight:950}.k3bookvals{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}.k3chip{display:inline-flex;border:1px solid #31536a;border-radius:999px;padding:5px 8px;font-size:.66rem;font-weight:850}.k3-envstrip{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:7px}.k3-env{border:1px solid #29495d;border-radius:12px;padding:9px;background:#081722}.k3-env strong{display:block;font-size:.78rem;margin-top:3px}.k3-whyhead{font-size:1.02rem;font-weight:950;margin-bottom:8px}.k3-evidence{display:flex;flex-wrap:wrap;gap:7px;margin:9px 0}.k3risk{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.k3risk>div{border:1px solid #4a4f58;border-left-width:4px;border-radius:10px;padding:9px 11px;font-size:.72rem}.k3risk>[data-severity="high"]{border-left-color:#ff8a65;background:#24140f}.k3risk>[data-severity="pending"]{border-left-color:#f3c453;background:#211b0c}.k3risk>[data-severity="good"]{border-left-color:#70dca9;background:#0d2119}.k3decision{border:1px solid #3b886b;background:#071f1d;border-radius:15px;padding:14px}.k3decision.pass{border-color:#b19347;background:#211d0e}.k3-decisionmain{font-size:1.45rem;font-weight:950;margin-top:4px}.k3-decisionchips{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px}.k3foot{text-align:center;font-size:.65rem;color:#8ca0ae;margin-top:10px}.k3availability{margin-top:8px}.k3-time{white-space:nowrap}
@media(max-width:900px){.k3herogrid{grid-template-columns:repeat(2,1fr)}.k3-hitstrip{grid-template-columns:repeat(5,minmax(110px,1fr));overflow-x:auto;padding-bottom:3px}.k3tiles{grid-template-columns:repeat(2,1fr)}.k3-envstrip{grid-template-columns:repeat(3,1fr)}}
@media(max-width:640px){.k3sec{padding:12px}.k3hero{padding:13px}.k3-matchupgrid{grid-template-columns:1fr}.k3-envstrip{grid-template-columns:repeat(2,1fr)}.k3risk{grid-template-columns:1fr}.k3-history-one{align-items:flex-start;flex-direction:column}.k3-history-stats{text-align:left}.k3name{font-size:1.3rem}.k3value{font-size:1rem}}
</style>
"""


def _num(value: Any) -> float | None:
    try:
        if value is None or value == "": return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt(value: Any, digits: int = 1) -> str:
    n=_num(value)
    if n is None: return "Pending"
    return f"{n:.{digits}f}"


def _pct(value: Any) -> str:
    n=_num(value)
    return "Pending" if n is None else f"{round(n*100):d}%"


def _odds(value: Any) -> str:
    n=_num(value)
    if n is None: return "Pending"
    return f"{int(n):+d}"


def _human_time(value: Any) -> str:
    text=str(value or "").strip()
    if not text: return "Freshness pending"
    try:
        dt=datetime.fromisoformat(text.replace("Z","+00:00")).astimezone(timezone.utc)
        return f"Updated {dt:%H:%M} UTC"
    except Exception:
        return "Updated · verified market observation"


def _metric(label: str, value: Any, note: str = "") -> str:
    return f'<div class="k3metric"><div class="k3label">{_e(label)}</div><div class="k3value">{_e(value)}</div>'+(f'<div class="k3note">{_e(note)}</div>' if note else '')+'</div>'


def _semantic(title: str, detail: str = "", cls: str = "pending") -> str:
    return f'<div class="k3status {_e(cls)}"><b>{_e(title)}</b>'+(f'<span>{_e(detail)}</span>' if detail else '')+'</div>'


def _decision(card: dict[str, Any], detail: dict[str, Any]) -> dict[str, Any]:
    market=detail.get("market") or card.get("market") or {}
    ev=detail.get("market_evaluation") or {}
    thesis=(detail.get("page1_decision_support") or {}).get("thesis") or {}
    side=str(card.get("favored_side") or ev.get("lean") or thesis.get("side") or "CHECK").upper()
    line=market.get("line")
    edge=_num(card.get("edge_yards"))
    over=_num(ev.get("model_over_probability") if ev.get("model_over_probability") is not None else card.get("over_probability"))
    under=_num(ev.get("model_under_probability") if ev.get("model_under_probability") is not None else card.get("under_probability"))
    prob=over if side=="OVER" else under if side=="UNDER" else None
    strength=str(thesis.get("strength") or ev.get("grade") or "CHECK").upper()
    weak_strength=strength in {"CHECK","PASS","NO BET","NO_BET","LOW","WEAK"}
    actionable=side in {"OVER","UNDER"} and prob is not None and prob>=.55 and edge is not None and abs(edge)>=3.0 and not weak_strength
    return {"actionable":actionable,"side":side,"line":line,"edge":edge,"prob":prob,"strength":strength,"over":over,"under":under}


def _hero(card: dict[str, Any], detail: dict[str, Any]) -> str:
    d=_decision(card,detail); market=detail.get("market") or card.get("market") or {}
    projection=card.get("projection_yards") if card.get("projection_yards") is not None else (detail.get("context_projection") or {}).get("context_projection_yards")
    face=str(card.get("headshot_url") or ""); logo=str(card.get("team_logo_url") or "")
    face_html=f'<img class="k3face" src="{_e(face)}" alt="">' if face else '<div class="k3face"></div>'
    logo_html=f'<img class="k3logo" src="{_e(logo)}" alt="">' if logo else ''
    pick=(f"{d['side']} {_fmt(d['line'])}" if d['actionable'] else "PASS")
    pick_note=(str(market.get("sportsbook") or "Verified market") if d['actionable'] else f"Model direction: slight {d['side']}")
    return '<div class="k3hero"><div class="k3head">'+face_html+f'<div><div class="k3kick">QB ANALYSIS COMMAND CENTER</div><div class="k3name">{_e(card.get("qb_name") or "Quarterback")}</div><div class="k3sub">{_e(card.get("team_name") or card.get("team_abbr") or "NFL")} · vs {_e(card.get("opponent_abbr") or "Opponent")} · {_e(card.get("home_away") or "")}</div></div>'+logo_html+'</div><div class="k3herogrid">'+''.join([
        _metric("ACTION",pick,pick_note),
        _metric("KYRE PROJECTION",_fmt(projection),f"{d['edge']:+.1f} yd edge" if d['edge'] is not None else "Edge pending"),
        _metric("PROBABILITY",_pct(d['prob']),str(card.get("confidence") or "CHECK")),
        _metric("MARKET",_fmt(d['line']),f"{market.get('sportsbook') or 'Verified book'} · {_human_time(market.get('source_timestamp') or market.get('timestamp'))}"),
    ])+'</div></div>'


def _game_table(detail: dict[str, Any], line: Any) -> str:
    rows,_=v1._game_rows(detail)
    if not rows: return _semantic("No qualifying games","No verified game rows qualify for the current season window.")
    max_y=max([_num(r.get("passing_yards")) or 0 for r in rows]+[_num(line) or 0,1])*1.12
    line_pct=min(100,((_num(line) or 0)/max_y)*100)
    body=[]
    for row in rows:
        y=_num(row.get("passing_yards")); result=v1._market_result(y,line)
        week=row.get("week"); week_text=f"W{int(float(week))}" if _num(week) is not None else "—"
        width=min(100,((y or 0)/max_y)*100)
        body.append('<tr>'+f'<td>{_e(week_text)}</td><td>{_e(row.get("home_away") or "—")}</td><td>{_e(row.get("opponent") or "—")}</td>'+f'<td class="k3-yardcell"><b>{_fmt(y,0)}</b><div class="k3-yardbar"><span class="k3-yardfill" style="display:block;width:{width:.1f}%"></span><i class="k3-linemark" style="left:{line_pct:.1f}%"></i></div></td>'+f'<td>{_fmt(row.get("attempts"),0)}</td><td>{_fmt(row.get("completions"),0)}</td><td>{_fmt(row.get("pass_tds"),0)}</td><td>{_fmt(row.get("interceptions"),0)}</td><td><span class="k3res" data-result="{_e(result)}">{_e(result)}</span></td></tr>')
    return '<div class="k3note" style="margin-bottom:7px">Verified current-season production · gold marker = current line.</div><div class="k3tablewrap"><table class="k3table"><thead><tr><th>WEEK</th><th>H/A</th><th>OPP</th><th>YDS</th><th>ATT</th><th>CMP</th><th>TD</th><th>INT</th><th>VS LINE</th></tr></thead><tbody>'+''.join(body)+'</tbody></table></div>'


def _hit_strip(detail: dict[str, Any], line: Any) -> str:
    season=[dict(r) for r in (detail.get("season_game_log") or []) if isinstance(r,dict)]
    fallback=[dict(r) for r in ((detail.get("profile") or {}).get("recent_games") or []) if isinstance(r,dict)]
    source=season or list(reversed(fallback))
    groups=[("LAST 5",source[-5:]),("LAST 10",source[-10:] if season else []),("SEASON",season),("HOME",[r for r in season if str(r.get("home_away") or "").upper()=="HOME"]),("AWAY",[r for r in season if str(r.get("home_away") or "").upper()=="AWAY"])]
    cells=[]
    for label,rows in groups:
        over,under,push,sample=v1._hit_counts(rows,line)
        if not sample:
            cells.append(f'<div class="k3-hit"><div class="k3label">{label}</div><div class="k3value">No qualifying games</div></div>'); continue
        rate=round(over/sample*100)
        push_text=f" · {push} push" if push else ""
        cells.append(f'<div class="k3-hit"><div class="k3label">{label}</div><div class="k3value">{over}/{sample} O · {rate}%</div><div class="k3note">{under}/{sample} U{push_text}</div><div class="k3-progress"><i style="width:{rate}%"></i></div></div>')
    return '<div class="k3-hitstrip">'+''.join(cells)+'</div>'


def _tile(label: str, value: str, note: str="") -> str:
    return f'<div class="k3tile"><div class="k3label">{_e(label)}</div><div class="k3value">{_e(value)}</div>'+(f'<div class="k3note">{_e(note)}</div>' if note else '')+'</div>'


def _matchup(detail: dict[str, Any], opponent: str) -> str:
    p=detail.get("profile") or {}; c=detail.get("context_projection") or {}; dist=detail.get("distribution") or {}; d=detail.get("pass_defense") or {}
    qb=[("YDS / GAME",_fmt(p.get("passing_yards_per_game"))),("ATT / GAME",_fmt(p.get("attempts_per_game"))),("CMP%",_fmt(p.get("completion_pct"))+"%" if _num(p.get("completion_pct")) is not None else "Pending"),("YARDS / ATT",_fmt(p.get("yards_per_attempt"),2)),("TD / INT",f'{_fmt(p.get("pass_tds"),0)} / {_fmt(p.get("interceptions"),0)}'),("PRESSURE ADJ",f'{_num(c.get("pressure_adjustment_yards")):+.1f} yd' if _num(c.get("pressure_adjustment_yards")) is not None else "Pending"),("MODEL SIGMA",f'{_fmt(dist.get("sigma_yards"))} yd',str(dist.get("confidence") or "CHECK"))]
    de=[("PASS-YDS RANK",f'#{_fmt(d.get("rank"),0)}',str(d.get("grade") or "CHECK")),("YDS / GAME",_fmt(d.get("pass_yards_allowed_per_game"))),("ATT / GAME",_fmt(d.get("passing_attempts_allowed_per_game"))),("CMP% ALLOWED",_fmt(d.get("completion_pct_allowed"))+"%" if _num(d.get("completion_pct_allowed")) is not None else "Pending"),("YPA ALLOWED",_fmt(d.get("yards_per_attempt_allowed"),2)),("RECENT 3 YDS",_fmt(d.get("recent3_pass_yards_allowed"))),("SACK RATE",_fmt(d.get("sack_rate_generated"))+"%" if _num(d.get("sack_rate_generated")) is not None else "Pending")]
    def panel(title,items):
        return '<div class="k3panel"><div class="k3panelhead">'+_e(title)+'</div><div class="k3tiles">'+''.join(_tile(a,b,c if len(item)==3 else "") for item in items for a,b,*rest in [item] for c in [rest[0] if rest else ""])+'</div></div>'
    return '<div class="k3-matchupgrid">'+panel("QB FORM",qb)+panel(f"{opponent} PASS DEFENSE",de)+'</div>'


def _history(detail: dict[str, Any]) -> str:
    h=detail.get("qb_vs_team_history") or {}
    if not h.get("available"):
        state=str(h.get("state") or "").upper()
        title="First career matchup" if state=="FIRST_CAREER_MATCHUP" else "No previous meetings" if state=="NO_PREVIOUS_MEETINGS" else "No verified prior matchup"
        return _semantic(title,str(h.get("message") or ""))
    games=[r for r in (h.get("games_detail") or []) if isinstance(r,dict)]
    if len(games)==1:
        r=games[0]; opp=str(r.get("opponent") or "opponent")
        return f'<div class="k3-history-one"><div><div class="k3label">PRIOR GAME</div><div class="k3-history-main">Previous matchup vs {_e(opp)}</div></div><div class="k3-history-stats">{_fmt(r.get("passing_yards"),0)} YDS · {_fmt(r.get("completions"),0)}/{_fmt(r.get("attempts"),0)} · {_fmt(r.get("pass_tds"),0)} TD · {_fmt(r.get("interceptions"),0)} INT</div></div>'
    return v2._history(detail)


def _market_board(detail: dict[str, Any]) -> str:
    market=detail.get("market") or {}; movement=market.get("line_movement") or {}
    status="" if movement.get("ready") else _semantic("Opening line history building","Current sportsbook observation remains verified.")
    books=[b for b in (market.get("books") or []) if isinstance(b,dict)]
    if not books: return status+_semantic("Market not posted yet")
    rows=[]
    for b in books:
        rows.append(f'<div class="k3book"><div><div class="k3bookname">{_e(b.get("sportsbook") or b.get("provider") or "Verified sportsbook")}</div><div class="k3note k3-time">{_human_time(b.get("source_timestamp"))}</div></div><div class="k3bookvals"><span class="k3chip">Line {_fmt(b.get("line"))}</span><span class="k3chip">O {_odds(b.get("over_odds"))}</span><span class="k3chip">U {_odds(b.get("under_odds"))}</span></div></div>')
    return status+''.join(rows)


def _environment(detail: dict[str, Any]) -> str:
    g=detail.get("game_environment") or {}
    if not g.get("verified"): return _semantic("Game conditions verification pending",str(g.get("reason") or ""))
    roof=str(g.get("roof") or "").lower(); indoor=roof in {"dome","closed","indoors","indoor","retractable closed"}
    temp=("Indoor · not applicable" if indoor else f'{_fmt(g.get("temperature_f"),0)}°F' if _num(g.get("temperature_f")) is not None else "Weather pending")
    wind=("Indoor · not applicable" if indoor else f'{_fmt(g.get("wind_mph"),0)} mph' if _num(g.get("wind_mph")) is not None else "Weather pending")
    items=[("VENUE",str(g.get("venue") or "Venue pending")),("ROOF",str(g.get("roof") or "Roof pending")),("SURFACE",str(g.get("surface") or "Surface pending")),("TEMPERATURE",temp),("WIND",wind),("REST",f'{_fmt(g.get("rest_days"),0)} rest days' if _num(g.get("rest_days")) is not None else "Rest pending")]
    return '<div class="k3-envstrip">'+''.join(f'<div class="k3-env"><div class="k3label">{_e(a)}</div><strong>{_e(b)}</strong></div>' for a,b in items)+'</div>'


def _availability(detail: dict[str, Any]) -> str:
    a=detail.get("availability") or {}
    if not a.get("verified"): return '<div class="k3availability">'+_semantic("Availability not yet verified",str(a.get("reason") or "Official team availability verification is pending."))+'</div>'
    return '<div class="k3availability">'+_semantic(str(a.get("status") or "Availability verified"),str(a.get("reason") or ""),"good")+'</div>'


def _why(card: dict[str, Any], detail: dict[str, Any]) -> str:
    d=_decision(card,detail); thesis=(detail.get("page1_decision_support") or {}).get("thesis") or {}; factors=[f for f in (thesis.get("factors") or []) if isinstance(f,dict)]
    heading=("PASS / NO STRONG EDGE" if not d['actionable'] else f"LEAN: {d['side']} {_fmt(d['line'])}")
    chips=[]
    if d['edge'] is not None: chips.append(f"{d['edge']:+.1f} yd projection edge")
    for f in factors[:3]:
        text=str(f.get("detail") or f.get("label") or "").strip()
        if text and text not in chips: chips.append(text)
    narrative=str(thesis.get("narrative") or "Decision uses verified Kyre Sports API evidence.")
    if not d['actionable'] and d['line'] is not None: narrative=f"No actionable edge at {_fmt(d['line'])}. "+narrative
    return f'<div class="k3-whyhead">{_e(heading)}</div><div class="k3-evidence">'+''.join(f'<span class="k3chip">{_e(x)}</span>' for x in chips)+'</div><div class="k3note" style="font-size:.78rem;color:#c9d8e1">{_e(narrative)}</div>'


def _risks(detail: dict[str, Any]) -> str:
    risks=[str(x).strip() for x in ((detail.get("page1_decision_support") or {}).get("risk_flags") or []) if str(x).strip()]
    sigma=_num((detail.get("distribution") or {}).get("sigma_yards"))
    if sigma is not None and not any("sigma" in r.lower() for r in risks): risks.append(f"Model variance: {sigma:.1f} yd sigma")
    if not risks: return _semantic("No additional verified risk flags","","good")
    def severity(r):
        low=r.lower()
        if "variance" in low or "sigma" in low: return "high"
        if "pending" in low or "building" in low or "verification" in low: return "pending"
        if "indoor" in low or "favorable" in low: return "good"
        return "pending"
    return '<div class="k3risk">'+''.join(f'<div data-severity="{severity(r)}">{_e(r)}</div>' for r in risks)+'</div>'


def _final(card: dict[str, Any], detail: dict[str, Any]) -> str:
    d=_decision(card,detail); m=detail.get("market") or card.get("market") or {}; projection=card.get("projection_yards")
    if d['actionable']:
        main=f"{d['side']} {_fmt(d['line'])}"; sub=str(((detail.get("page1_decision_support") or {}).get("thesis") or {}).get("narrative") or "Verified evidence supports this directional lean."); cls=""
    else:
        main="PASS — NO ACTIONABLE EDGE"; sub=f"No actionable edge at {_fmt(d['line'])}. Model direction: slight {d['side']}."; cls=" pass"
    chips=[str(m.get("sportsbook") or "Verified sportsbook"),f"{_pct(d['prob'])} probability",f"{card.get('confidence') or 'CHECK'} confidence",f"{d['strength']} strength",f"Projection {_fmt(projection)}",f"Edge {d['edge']:+.1f} yd" if d['edge'] is not None else "Edge pending"]
    return f'<div class="k3decision{cls}"><div class="k3label">FINAL DECISION</div><div class="k3-decisionmain">{_e(main)}</div><div class="k3-decisionchips">'+''.join(f'<span class="k3chip">{_e(x)}</span>' for x in chips)+f'</div><div class="k3note" style="margin-top:10px">{_e(sub)}</div></div>'


def build_page2_html(card: dict[str, Any]) -> str:
    detail=card.get("detail") or {}; market=detail.get("market") or card.get("market") or {}; line=market.get("line")
    return '<div class="kpy3">'+_hero(card,detail)+f'<div class="k3sec"><div class="k3title">RECENT PERFORMANCE</div>{_game_table(detail,line)}{_hit_strip(detail,line)}</div>'+f'<div class="k3sec"><div class="k3title">QB FORM VS OPPONENT DEFENSE</div>{_matchup(detail,str(card.get("opponent_abbr") or "OPP"))}</div>'+f'<div class="k3sec"><div class="k3title">QB VS DEFENSE HISTORY</div>{_history(detail)}</div>'+f'<div class="k3sec"><div class="k3title">LINE MOVEMENT & SPORTSBOOKS</div>{_market_board(detail)}</div>'+f'<div class="k3sec"><div class="k3title">GAME ENVIRONMENT & AVAILABILITY</div>{_environment(detail)}{_availability(detail)}</div>'+f'<div class="k3sec"><div class="k3title">WHY KYRE LEANS</div>{_why(card,detail)}</div>'+f'<div class="k3sec"><div class="k3title">RISK PANEL</div>{_risks(detail)}</div>'+f'<div class="k3sec"><div class="k3title">FINAL DECISION</div>{_final(card,detail)}</div><div class="k3foot">Kyre Sports API · canonical identity · field-level fallback · semantic empty states · no missing-to-zero conversion</div></div>'


def render_page2(st: Any, card: dict[str, Any]) -> None:
    st.markdown(CSS,unsafe_allow_html=True)
    st.markdown('<a class="kpy2-back" href="?sport=nfl&market=passing-yards">← All Quarterbacks</a>',unsafe_allow_html=True)
    st.markdown(build_page2_html(card),unsafe_allow_html=True)

__all__=["CSS","build_page2_html","render_page2"]
