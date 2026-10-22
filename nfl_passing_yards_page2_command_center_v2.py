"""NFL Passing Yards Page 2 V2 — compact verified analytics command center.

Presentation-only successor over the frozen V1 data contract. It performs no
provider calls; Kyre Sports API remains the only application-facing gateway.
"""
from __future__ import annotations

from html import escape
from typing import Any
import nfl_passing_yards_page2_command_center_v1 as v1

CSS = r"""
<style>
:root{--k2:#09131d;--k2b:#0d1a26;--k2l:#294156;--k2t:#f4f8fc;--k2m:#9fb1c2;--k2g:#72e0a4;--k2r:#ff7d7d;--k2a:#ffc766;--k2bue:#6bcaff}
.kpy2v2{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:var(--k2t);max-width:1120px;margin:0 auto;padding:4px 0 34px}.kpy2v2 *{box-sizing:border-box}.k2hero,.k2sec{background:var(--k2b);border:1px solid #21394d;border-radius:18px;padding:15px;margin-top:12px;min-width:0}.k2hero{background:linear-gradient(145deg,#102233,#09131d 72%);border-color:#31536e}.k2head{display:grid;grid-template-columns:auto 1fr auto;gap:13px;align-items:center;min-width:0}.k2face{width:72px;height:72px;border-radius:50%;object-fit:cover;border:3px solid #3c789f}.k2logo{width:46px;height:46px;object-fit:contain}.k2kick,.k2title,.k2label{letter-spacing:.12em;font-weight:900}.k2kick{font-size:11px;color:var(--k2bue)}.k2name{font-size:29px;line-height:1.05;font-weight:950;margin:3px 0}.k2sub{font-size:13px;color:#b7c5d2}.k2title{font-size:13px;margin-bottom:10px}.k2grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin-top:12px}.k2grid.two{grid-template-columns:repeat(2,minmax(0,1fr))}.k2metric{background:#07111a;border:1px solid var(--k2l);border-radius:14px;padding:11px;min-width:0}.k2label{font-size:9px;color:var(--k2m)}.k2value{font-size:21px;font-weight:950;margin-top:4px;white-space:normal;word-break:normal}.k2note{font-size:11px;color:var(--k2m);margin-top:4px;line-height:1.35}.k2semantic{border:1px dashed #4a5f72;border-radius:12px;padding:10px 12px;background:#09121a;color:#c1ccd6;font-size:12px}.k2semantic strong{color:#e6f1f9}.k2history{width:100%;border-collapse:collapse;min-width:620px}.k2history th,.k2history td{padding:9px;border-bottom:1px solid #1f3446;text-align:left;font-size:12px}.k2history th{color:#91a6b8;font-size:9px;letter-spacing:.08em}.k2table{overflow-x:auto;border:1px solid #223c50;border-radius:13px}.k2risk{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.k2risk>div{border-left:3px solid var(--k2a);background:#17140c;border-radius:8px;padding:10px;color:#efd39b;font-size:12px}.k2chips{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px}.k2chip{border:1px solid #36566e;border-radius:999px;padding:6px 9px;font-size:11px;font-weight:850}.k2decision{border:1px solid #39765e;background:linear-gradient(135deg,#0b211b,#0b1722);border-radius:16px;padding:14px}.k2side{font-size:30px;font-weight:1000}.k2muted{color:var(--k2m)}
@media(max-width:760px){.k2hero,.k2sec{padding:12px}.k2head{grid-template-columns:58px 1fr auto}.k2face{width:58px;height:58px}.k2logo{width:38px;height:38px}.k2name{font-size:23px}.k2grid{grid-template-columns:repeat(2,minmax(0,1fr))}.k2risk{grid-template-columns:1fr}.k2value{font-size:18px}}
</style>
"""


def _text(v: Any) -> str:
    return str(v if v is not None else "").strip()


def _num(v: Any) -> float | None:
    try: n=float(v)
    except (TypeError, ValueError): return None
    return None if n != n else n


def _e(v: Any) -> str:
    return escape(_text(v), quote=True)


def _fmt(v: Any, digits: int=1, empty: str="Pending") -> str:
    n=_num(v)
    return empty if n is None else f"{n:.{digits}f}"


def _pct(v: Any) -> str:
    n=_num(v)
    if n is None: return "Pending"
    if -1 <= n <= 1: n *= 100
    return f"{n:.0f}%"


def _metric(label: str, value: Any, note: str="") -> str:
    nh=f'<div class="k2note">{_e(note)}</div>' if note else ''
    return f'<div class="k2metric"><div class="k2label">{_e(label)}</div><div class="k2value">{_e(value)}</div>{nh}</div>'


def _semantic(label: str, detail: str="") -> str:
    tail=f' <span>{_e(detail)}</span>' if detail else ''
    return f'<div class="k2semantic"><strong>{_e(label)}</strong>{tail}</div>'


def _history(detail: dict[str, Any]) -> str:
    h=detail.get("qb_vs_team_history") or {}
    if not h.get("available"):
        state=_text(h.get("state") or h.get("semantic_state")).upper()
        labels={
            "FIRST_CAREER_MATCHUP":"First career matchup",
            "NO_PREVIOUS_MEETINGS":"No previous meetings",
            "NO_QUALIFYING_GAMES":"No qualifying games",
        }
        if state in labels: return _semantic(labels[state])
        message=_text(h.get("message"))
        if "no verified prior" in message.casefold() or "no prior" in message.casefold():
            return _semantic("No previous meetings", "No verified prior QB-vs-defense game exists for this identity.")
        return _semantic("Matchup history pending verification", message or "Fallback/history verification is still in progress.")
    games=[r for r in (h.get("games_detail") or []) if isinstance(r,dict)]
    summary='<div class="k2grid">'+''.join([
        _metric("PRIOR GAMES", _fmt(h.get("games"),0,"0")),
        _metric("YDS / GAME", _fmt(h.get("avg_passing_yards"))),
        _metric("ATT / GAME", _fmt(h.get("avg_attempts"))),
        _metric("CMP%", _fmt(h.get("completion_pct"))+('%' if _num(h.get("completion_pct")) is not None else '')),
    ])+'</div>'
    if not games:
        return summary + _semantic("Verified matchup summary", "Game-level detail rows are still being enriched.")
    rows=[]
    for r in reversed(games):
        rows.append('<tr>'+''.join([
            f'<td>{_e(r.get("date") or r.get("game_date") or "Verified prior game")}</td>',
            f'<td>{_e(r.get("season") or "")}</td>',
            f'<td>{_e(r.get("opponent") or "")}</td>',
            f'<td>{_fmt(r.get("passing_yards"),0)}</td>',
            f'<td>{_fmt(r.get("attempts"),0)}</td>',
            f'<td>{_fmt(r.get("completions"),0)}</td>',
            f'<td>{_fmt(r.get("pass_tds"),0)}</td>',
            f'<td>{_fmt(r.get("interceptions"),0)}</td>',
        ])+'</tr>')
    table='<div class="k2table" style="margin-top:10px"><table class="k2history"><thead><tr><th>DATE</th><th>SEASON</th><th>OPP</th><th>YDS</th><th>ATT</th><th>CMP</th><th>TD</th><th>INT</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'
    return summary+table


def _conditions(detail: dict[str, Any]) -> str:
    g=detail.get("game_environment") or {}
    if not g.get("verified"):
        return _semantic("Game conditions pending verification", _text(g.get("reason")) or "Approved fallback verification is still in progress.")
    roof=_text(g.get("roof")).lower()
    indoor=roof in {"dome","closed","indoors","indoor","retractable closed"}
    temp="NOT APPLICABLE" if indoor else (_fmt(g.get("temperature_f"),0)+"°F" if _num(g.get("temperature_f")) is not None else "Weather pending")
    wind="NOT APPLICABLE" if indoor else (_fmt(g.get("wind_mph"),0)+" mph" if _num(g.get("wind_mph")) is not None else "Weather pending")
    return '<div class="k2grid">'+''.join([
        _metric("VENUE", _text(g.get("venue")) or "Venue pending"),
        _metric("ROOF", "INDOOR" if indoor else (_text(g.get("roof")) or "Roof pending")),
        _metric("SURFACE", _text(g.get("surface")) or "Surface pending"),
        _metric("TEMPERATURE", temp),
        _metric("WIND", wind),
        _metric("REST DAYS", _fmt(g.get("rest_days"),0,"Schedule pending")),
    ])+'</div>'


def _availability(detail: dict[str, Any]) -> str:
    a=detail.get("availability") or {}
    if a.get("verified"):
        status=_text(a.get("status") or a.get("designation"))
        if status.upper() in {"CLEAR","NONE","NO_INJURY_DESIGNATION","ACTIVE"}:
            return _semantic("No injury designation")
        return _semantic(status or "Availability verified", _text(a.get("reason")))
    return _semantic("Availability verification pending", _text(a.get("reason")) or "Official NFL/team availability verification is still in progress.")


def _movement(detail: dict[str, Any]) -> str:
    m=(detail.get("market") or {}).get("line_movement") or {}
    if not m.get("ready"):
        return _semantic("Same-book line history building", "Current sportsbook observation remains valid while opening-line history is enriched.")
    d=_num(m.get("delta")); direction="UP" if (d or 0)>0 else ("DOWN" if (d or 0)<0 else "FLAT")
    return '<div class="k2grid">'+''.join([
        _metric("SPORTSBOOK", _text(m.get("sportsbook")) or "Verified book"),
        _metric("OPEN", _fmt(m.get("open_line"))),
        _metric("CURRENT", _fmt(m.get("current_line"))),
        _metric("MOVE", f"{d:+.1f}" if d is not None else "Flat", direction),
    ])+'</div>'


def _risk_panel(detail: dict[str, Any]) -> str:
    risks=list(((detail.get("page1_decision_support") or {}).get("risk_flags") or []))
    sigma=_num((detail.get("distribution") or {}).get("sigma_yards"))
    if sigma is not None: risks.append(f"Model variance: {sigma:.1f} yd sigma")
    roof=_text((detail.get("game_environment") or {}).get("roof")).lower()
    if roof in {"dome","closed","indoors","indoor","retractable closed"}: risks.append("Indoor environment removes wind/weather volatility")
    if not risks: return _semantic("No additional verified risk flags")
    return '<div class="k2risk">'+''.join(f'<div>{_e(r)}</div>' for r in risks)+'</div>'


def _hero(card: dict[str, Any], detail: dict[str, Any]) -> str:
    market=detail.get("market") or card.get("market") or {}
    line=market.get("line"); side=_text(card.get("favored_side") or (detail.get("market_evaluation") or {}).get("lean") or "CHECK").upper()
    projection=card.get("projection_yards") if card.get("projection_yards") is not None else (detail.get("context_projection") or {}).get("context_projection_yards")
    edge=card.get("edge_yards"); prob=card.get("over_probability") if side=="OVER" else card.get("under_probability")
    face=_text(card.get("headshot_url") or (detail.get("identity_visuals") or {}).get("headshot_url")); logo=_text(card.get("team_logo_url") or (detail.get("identity_visuals") or {}).get("team_logo_url"))
    face_html=f'<img class="k2face" src="{_e(face)}" alt="">' if face else '<div class="k2face"></div>'
    logo_html=f'<img class="k2logo" src="{_e(logo)}" alt="">' if logo else ''
    book=_text(market.get("sportsbook")) or "Market pending"
    observed=_text(market.get("source_timestamp") or market.get("timestamp"))
    return '<div class="k2hero"><div class="k2head">'+face_html+f'<div><div class="k2kick">QB ANALYSIS COMMAND CENTER</div><div class="k2name">{_e(card.get("qb_name"))}</div><div class="k2sub">{_e(card.get("team_name") or card.get("team_abbr"))} · vs {_e(card.get("opponent_abbr"))} · {_e(card.get("home_away"))}</div></div>'+logo_html+'</div><div class="k2grid">'+''.join([
        _metric("PICK", f"{side} {_fmt(line)}", book),
        _metric("KYRE PROJECTION", _fmt(projection), f"{_fmt(edge)} yd edge" if _num(edge) is not None else "Edge pending"),
        _metric("PROBABILITY", _pct(prob), _text(card.get("confidence")) or "Confidence pending"),
        _metric("MARKET", f"{_fmt(line)}", observed or "Freshness timestamp pending"),
    ])+'</div></div>'


def _final_decision(card: dict[str, Any], detail: dict[str, Any]) -> str:
    m=detail.get("market") or card.get("market") or {}; ev=detail.get("market_evaluation") or {}; thesis=(detail.get("page1_decision_support") or {}).get("thesis") or {}
    side=_text(card.get("favored_side") or ev.get("lean") or thesis.get("side") or "CHECK").upper(); line=m.get("line"); prob=card.get("over_probability") if side=="OVER" else card.get("under_probability")
    projection=card.get("projection_yards") if card.get("projection_yards") is not None else (detail.get("context_projection") or {}).get("context_projection_yards")
    edge=card.get("edge_yards"); strength=_text(thesis.get("strength") or ev.get("grade") or "CHECK")
    narrative=_text(thesis.get("narrative")) or "Decision uses only verified Kyre Sports API evidence."
    return '<div class="k2decision"><div class="k2label">FINAL DECISION</div><div class="k2side">'+_e(f"{side} {_fmt(line)}")+'</div><div class="k2chips">'+''.join([
        f'<span class="k2chip">{_e(_text(m.get("sportsbook")) or "Verified sportsbook")}</span>',
        f'<span class="k2chip">{_e(_pct(prob))} probability</span>',
        f'<span class="k2chip">{_e(_text(card.get("confidence")) or "CHECK")} confidence</span>',
        f'<span class="k2chip">{_e(strength)} strength</span>',
        f'<span class="k2chip">Projection {_e(_fmt(projection))}</span>',
        f'<span class="k2chip">Edge {_e(_fmt(edge))} yd</span>',
    ])+'</div><div class="k2note" style="margin-top:10px">'+_e(narrative)+'</div></div>'


def build_page2_html(card: dict[str, Any]) -> str:
    detail=card.get("detail") or {}; market=detail.get("market") or card.get("market") or {}; line=market.get("line")
    rows,_=v1._game_rows(detail)
    recent=(v1._game_table(detail,line)+v1._hit_rate_lab(detail,line)) if rows else _semantic("No qualifying games", "No verified game rows qualify for the current season window.")
    qb_vs_def='<div class="k2grid two"><div>'+v1._volume(detail)+'</div><div>'+v1._defense(detail)+'</div></div>'
    why=v1._why(detail)
    books=v1._books(detail)
    return (
        '<div class="kpy2v2">'
        + _hero(card,detail)
        + '<div class="k2sec"><div class="k2title">RECENT PERFORMANCE</div>'+recent+'</div>'
        + '<div class="k2sec"><div class="k2title">QB FORM VS OPPONENT DEFENSE</div>'+qb_vs_def+'</div>'
        + '<div class="k2sec"><div class="k2title">QB VS DEFENSE HISTORY</div>'+_history(detail)+'</div>'
        + '<div class="k2sec"><div class="k2title">LINE MOVEMENT & SPORTSBOOKS</div>'+_movement(detail)+'<div style="height:9px"></div>'+books+'</div>'
        + '<div class="k2sec"><div class="k2title">GAME ENVIRONMENT & AVAILABILITY</div>'+_conditions(detail)+'<div style="height:9px"></div>'+_availability(detail)+'</div>'
        + '<div class="k2sec"><div class="k2title">WHY KYRE LEANS</div>'+why+'</div>'
        + '<div class="k2sec"><div class="k2title">RISK PANEL</div>'+_risk_panel(detail)+'</div>'
        + '<div class="k2sec"><div class="k2title">FINAL DECISION</div>'+_final_decision(card,detail)+'</div>'
        + '<div class="k2note" style="text-align:center;margin-top:12px">Kyre Sports API · canonical identity · field-level fallback · semantic empty states · no missing-to-zero conversion</div></div>'
    )


def render_page2(st: Any, card: dict[str, Any]) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown('<a class="kpy2-back" href="?sport=nfl&market=passing-yards">← All Quarterbacks</a>', unsafe_allow_html=True)
    st.markdown(build_page2_html(card), unsafe_allow_html=True)


__all__=["CSS","_conditions","_history","build_page2_html","render_page2"]
