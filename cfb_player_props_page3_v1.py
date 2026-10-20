"""CFB Player Props Page 3 V1 — Player Prop Intelligence Lab."""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import pandas as pd
import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    def st_autorefresh(*args, **kwargs):
        return 0

import cfb_over_under_logo_resolver_v3 as logo_exact
import cfb_player_props_model_v1 as frozen_model
import cfb_player_props_page3_analysis_v1 as page3_analysis
import cfb_player_props_page3_context_v1 as page3_context
import cfb_player_props_page3_line_lab_v1 as line_lab
import cfb_player_props_page3_professional_v1 as professional

SPORTSBOOK_PROJECTION_INFLUENCE = frozen_model.SPORTSBOOK_PROJECTION_INFLUENCE
MARKET_LABELS = {
    "passing_yards": "Passing Yards",
    "rushing_yards": "Rushing Yards",
    "receiving_yards": "Receiving Yards",
    "receiving_receptions": "Receptions",
    "passing_touchdowns": "Passing TDs",
    "touchdowns": "Touchdowns",
}

CSS = """
<style>
#cfbpp3-top{position:absolute;top:0}
.cfbpp3-shell{border:1px solid rgba(125,211,252,.2);background:radial-gradient(circle at 88% 6%,rgba(14,165,233,.14),transparent 31%),linear-gradient(145deg,rgba(2,8,23,.99),rgba(7,20,36,.99));border-radius:24px;padding:20px;margin-bottom:14px;box-shadow:0 20px 55px rgba(0,0,0,.3)}
.cfbpp3-kicker{font-size:.69rem;font-weight:950;letter-spacing:.16em;color:#7dd3fc}.cfbpp3-title{font-size:clamp(1.65rem,4.2vw,2.65rem);font-weight:950;letter-spacing:-.045em;color:#f8fafc;margin:.28rem 0}.cfbpp3-sub{font-size:.82rem;color:#99b1c5;max-width:820px}.cfbpp3-hero{display:flex;gap:15px;align-items:center;margin-top:15px}.cfbpp3-face,.cfbpp3-logo{width:68px;height:68px;border-radius:19px;object-fit:cover;border:1px solid rgba(125,211,252,.27);background:#07111f;box-shadow:0 8px 24px rgba(0,0,0,.2)}.cfbpp3-logo{object-fit:contain;padding:7px}.cfbpp3-name{font-size:1.28rem;font-weight:950;color:#f8fafc}.cfbpp3-meta{font-size:.78rem;color:#a7bacb}.cfbpp3-chip{display:inline-flex;margin:8px 6px 0 0;border:1px solid rgba(125,211,252,.22);border-radius:999px;padding:6px 9px;font-size:.66rem;font-weight:900;color:#daf4ff;background:rgba(14,165,233,.06)}
.cfbpp3-section{font-size:.74rem;font-weight:950;letter-spacing:.13em;color:#7dd3fc;margin:20px 0 9px}.cfbpp3-note{font-size:.74rem;color:#8fa9bf}
.cfbpp3-decision{border:1px solid rgba(125,211,252,.24);background:linear-gradient(135deg,rgba(6,18,33,.98),rgba(8,29,49,.98));border-radius:20px;padding:16px 17px;margin:9px 0 14px;box-shadow:0 14px 38px rgba(0,0,0,.18)}
.cfbpp3-decision-label{font-size:.65rem;font-weight:950;letter-spacing:.14em;color:#7dd3fc}.cfbpp3-decision-main{font-size:1.2rem;font-weight:950;color:#f8fafc;margin-top:5px}.cfbpp3-decision-sub{font-size:.75rem;color:#a8bdce;margin-top:5px}.cfbpp3-lean{display:inline-flex;border:1px solid rgba(125,211,252,.3);border-radius:999px;padding:6px 10px;margin-top:10px;font-size:.7rem;font-weight:950;color:#e4f7ff;background:rgba(14,165,233,.08)}
.cfbpp3-top-btn{position:fixed;right:18px;bottom:22px;z-index:99999;text-decoration:none!important;background:#081727;border:1px solid rgba(125,211,252,.42);color:#e6f7ff!important;border-radius:999px;padding:10px 13px;font-size:.72rem;font-weight:950;box-shadow:0 10px 30px rgba(0,0,0,.3)}
@media(max-width:760px){.cfbpp3-shell{padding:15px;border-radius:18px}.cfbpp3-face,.cfbpp3-logo{width:56px;height:56px}.cfbpp3-title{font-size:1.62rem}.cfbpp3-name{font-size:1.08rem}.cfbpp3-meta{font-size:.74rem}.cfbpp3-chip{font-size:.64rem}.cfbpp3-top-btn{right:10px;bottom:14px;padding:9px 11px}.cfbpp3-decision{padding:14px;border-radius:17px}}
</style>
"""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _fmt(value: Any, digits: int = 1, suffix: str = "") -> str:
    try:
        return f"{float(value):.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return "—"


def _pct(value: Any) -> str:
    try:
        return f"{float(value)*100:.1f}%"
    except (TypeError, ValueError):
        return "—"


def _price(value: Any) -> str:
    try:
        n=int(value); return f"+{n}" if n > 0 else str(n)
    except (TypeError, ValueError):
        return "—"


def _team_logo(context: dict[str, Any], player: Any) -> str:
    try:
        visuals=logo_exact.resolve_visuals(context.get("game") or context)
        side="away" if _text(getattr(player,"official_team_id","")) == _text(context.get("away_team_id")) else "home"
        return _text((visuals.get(side) or {}).get("logo"))
    except Exception:
        return ""


def _book_rows(observations) -> list[dict[str, Any]]:
    books={}
    for row in observations or []:
        if isinstance(row, Mapping):
            get=row.get
        else:
            get=lambda key, default=None, obj=row: getattr(obj,key,default)
        book=_text(get("sportsbook")) or "Unknown"
        item=books.setdefault(book,{"Sportsbook":book,"Over Line":None,"Over Price":None,"Under Line":None,"Under Price":None,"Updated":""})
        side=_text(get("side")).lower()
        line=get("line")
        if side in {"over","under"} and line is not None:
            label=side.title()
            try: item[f"{label} Line"]=float(line)
            except (TypeError,ValueError): pass
            item[f"{label} Price"]=_price(get("price"))
        stamp=_text(get("observed_at_utc"))
        if stamp > item["Updated"]: item["Updated"]=stamp
    return [books[key] for key in sorted(books,key=str.casefold)]


def _hero(context: dict[str, Any], packet: dict[str, Any]) -> None:
    player=context["player"]
    face=_text(getattr(player,"headshot_url","")); logo=_team_logo(context,player)
    images=""
    if face: images += f'<img class="cfbpp3-face" src="{escape(face)}" alt="player">'
    if logo: images += f'<img class="cfbpp3-logo" src="{escape(logo)}" alt="team">'
    availability=_text((packet.get("availability") or {}).get("state")) or "UNVERIFIED"
    opponent=context.get("home_team") if _text(player.official_team_id)==_text(context.get("away_team_id")) else context.get("away_team")
    market=MARKET_LABELS.get(context["market_key"],context["market_key"])
    line=_fmt((packet.get("line_lab") or {}).get("line"))
    freshness=_text((packet.get("quality") or {}).get("latest_market_timestamp")) or "Market timestamp unavailable"
    st.markdown(f'''<div class="cfbpp3-shell"><div class="cfbpp3-kicker">CFB • PLAYER PROPS • PLAYER PROP INTELLIGENCE LAB</div><div class="cfbpp3-title">{escape(player.canonical_name)} • {escape(market)}</div><div class="cfbpp3-sub">Professional player-prop decision support with verified history, opponent context, and book-specific market evidence.</div><div class="cfbpp3-hero">{images}<div><div class="cfbpp3-name">{escape(player.canonical_name)}</div><div class="cfbpp3-meta">{escape(player.position)} • {escape(player.team_name)} vs {escape(_text(opponent))}</div><span class="cfbpp3-chip">{escape(availability)}</span><span class="cfbpp3-chip">LINE {escape(line)}</span><span class="cfbpp3-chip">{escape(_text(context.get("kickoff_phoenix")) or _text(context.get("kickoff_iso")))}</span><span class="cfbpp3-chip">{escape(freshness)}</span></div></div></div>''',unsafe_allow_html=True)


def _decision(view: Mapping[str,Any]) -> None:
    decision=view.get("decision") or {}
    lean=_text(decision.get("lean")) or "NO LEAN"
    st.markdown('<div class="cfbpp3-section">MODEL DECISION</div>',unsafe_allow_html=True)
    st.markdown(
        f'''<div class="cfbpp3-decision"><div class="cfbpp3-decision-label">KYRE SPORTS AI • FROZEN MODEL</div><div class="cfbpp3-decision-main">Projection {_fmt(decision.get("projection"))} • Selected Line {_fmt(decision.get("selected_line"))} • Margin {_fmt(decision.get("margin"))}</div><div class="cfbpp3-decision-sub">Over {_pct(decision.get("over_probability"))} • Under {_pct(decision.get("under_probability"))} • {escape(_text(decision.get("evidence_state")) or "LIMITED SAMPLE")}</div><span class="cfbpp3-lean">MODEL LEAN • {escape(lean)}</span></div>''',
        unsafe_allow_html=True,
    )


def _recent_table(block: Mapping[str,Any]) -> pd.DataFrame:
    rows=[]
    for row in block.get("rows") or ():
        item={"Date":row.get("game_date") or row.get("event_id"),"Opponent":row.get("opponent_name") or row.get("opponent_team_id") or "—","Result":row.get("value")}
        for key,label in (("pass_attempts","ATT"),("completions","CMP"),("completion_percentage","CMP%"),("yards_per_attempt","Y/A"),("passing_touchdowns","TD"),("interceptions","INT")):
            if row.get(key) is not None: item[label]=row.get(key)
        rows.append(item)
    return pd.DataFrame(rows)


def render_cfb_player_props_page3() -> None:
    st.markdown('<div id="cfbpp3-top"></div>',unsafe_allow_html=True)
    st.markdown(CSS,unsafe_allow_html=True)
    st.markdown('<a class="cfbpp3-top-btn" href="#cfbpp3-top">↑ TOP</a>',unsafe_allow_html=True)
    st_autorefresh(interval=30_000,key="cfbpp3_live_market_refresh")

    if st.button("← Back to Game Props",key="cfbpp3_back_to_page2",use_container_width=False):
        page3_context.clear_page3_selection(st.session_state,st.query_params)
        st.rerun()

    context=page3_context.resolve_page3_context(st.session_state,st.query_params)
    if _text(context.get("state")) != "ready":
        st.error(_text(context.get("reason")) or "Selected player prop is unavailable.")
        return

    packet=page3_analysis.build_page3_analysis(context,selected_line=None)
    current=context["market_key"]
    options=list(dict.fromkeys([current,*list(packet.get("available_markets") or ())]))
    if len(options) > 1:
        selected_market=st.radio("Market",options,index=options.index(current),horizontal=True,format_func=lambda key:MARKET_LABELS.get(key,key),key="cfbpp3_market_selector")
        if selected_market != current and page3_context.switch_page3_market(st.session_state,st.query_params,selected_market):
            st.rerun()

    market=packet.get("market") or {}
    identity=f"{context['official_game_id']}:{context['official_player_id']}:{current}"
    initial=packet.get("line_lab",{}).get("line") or line_lab.default_line(current,consensus_line=market.get("consensus_line"),handoff_line=context.get("handoff_line"))
    if st.session_state.get("cfbpp3_line_identity") != identity:
        st.session_state["cfbpp3_line_identity"]=identity
        st.session_state["cfbpp3_line"]=initial
    active_line=float(st.session_state.get("cfbpp3_line") or initial)
    packet=page3_analysis.reline_page3_analysis(packet,active_line)
    view=professional.build_professional_view(context,packet,selected_line=active_line)

    _hero(context,packet)
    _decision(view)

    projection=packet.get("projection") or {}; market=packet.get("market") or {}
    st.markdown('<div class="cfbpp3-section">KYRE PROJECTION VS CURRENT MARKET</div>',unsafe_allow_html=True)
    a,b,c,d=st.columns(4)
    a.metric("Kyre Projection",_fmt(projection.get("projection")))
    b.metric("Market Consensus",_fmt(market.get("consensus_line")))
    c.metric("Projection − Market",_fmt((view.get("decision") or {}).get("margin")))
    d.metric("Verified Books",str(int(market.get("book_count") or 0)))

    low,high,step=line_lab.LINE_BOUNDS[current]
    st.markdown('<div class="cfbpp3-section">LINE LAB</div>',unsafe_allow_html=True)
    st.caption(f"Model projection marker: {_fmt(projection.get('projection'))} • Current market marker: {_fmt(market.get('consensus_line'))}")
    selected_line=st.slider("Move the line",min_value=float(low),max_value=float(high),value=active_line,step=float(step),key=f"cfbpp3_slider_{identity}")
    st.session_state["cfbpp3_line"]=selected_line
    packet=page3_analysis.reline_page3_analysis(packet,selected_line)
    view=professional.build_professional_view(context,packet,selected_line=selected_line)
    lab=packet["line_lab"]
    x,y,z=st.columns(3)
    x.metric("Over Probability",_pct(lab.get("over_probability")))
    y.metric("Under Probability",_pct(lab.get("under_probability")))
    z.metric("Projection Margin",_fmt(lab.get("margin")))
    if not lab.get("model_ready"):
        st.info(f"Model probability unavailable • verified sample {int(lab.get('sample_count') or 0)}/{frozen_model.MIN_SAMPLE} required.")

    curve=packet.get("probability_curve") or []
    if curve and curve[0].get("over_probability") is not None:
        df=pd.DataFrame([{"Line":r["line"],"Over":r["over_probability"],"Under":r["under_probability"]} for r in curve]).set_index("Line")
        st.line_chart(df)

    st.markdown('<div class="cfbpp3-section">LAST 3 • LAST 5 • RECENT PRODUCTION</div>',unsafe_allow_html=True)
    last3=view.get("last3") or {}; last5=view.get("last5") or {}; season=(packet.get("history") or {}).get("season") or {}
    h1,h2,h3=st.columns(3)
    for col,part,label in ((h1,last3,"LAST 3"),(h2,last5,"LAST 5"),(h3,season,"Season")):
        rate=part.get("hit_rate")
        hits=part.get("hits")
        sample=int(part.get("sample_size") or 0)
        col.metric(label,f"{_pct(rate)} • {hits}/{sample}" if rate is not None else f"n={sample}")
        if label in {"LAST 3","LAST 5"} and part.get("average") is not None: col.caption(f"Average {_fmt(part.get('average'))}")
    recent_frame=_recent_table(last5)
    if not recent_frame.empty:
        st.dataframe(recent_frame,use_container_width=True,hide_index=True)
    else:
        st.caption("Verified recent player history unavailable.")
    chart=(packet.get("history") or {}).get("chart") or []
    if chart:
        frame=pd.DataFrame([{"Game":r.get("game_date") or r.get("event_id"),"Production":r.get("value"),"Selected Line":r.get("comparison_line")} for r in reversed(chart)])
        st.line_chart(frame.set_index("Game"))

    st.markdown('<div class="cfbpp3-section">DIRECT PLAYER VS OPPONENT</div>',unsafe_allow_html=True)
    direct=view.get("direct_opponent") or {}
    if direct.get("available"):
        d1,d2,d3=st.columns(3)
        d1.metric("Direct H2H Games",str(int(direct.get("sample_size") or 0)))
        d2.metric("Direct H2H Average",_fmt(direct.get("average")))
        d3.metric("Selected-Line Hit Rate",_pct(direct.get("hit_rate")))
        st.dataframe(_recent_table(direct),use_container_width=True,hide_index=True)
    else:
        st.caption("No verified prior matchup sample. No verified prior player-vs-opponent matchup.")

    st.markdown('<div class="cfbpp3-section">TEAM MATCHUP HISTORY</div>',unsafe_allow_html=True)
    team=view.get("team_matchup") or {}
    if team.get("available"):
        st.caption("Historical team meetings are shown separately and are not labeled as player H2H.")
        st.dataframe(pd.DataFrame(list(team.get("rows") or ())),use_container_width=True,hide_index=True)
    else:
        st.caption("Verified team matchup history unavailable for this exact opponent identity.")

    st.markdown('<div class="cfbpp3-section">OPPONENT VS ROLE</div>',unsafe_allow_html=True)
    role=view.get("opponent_vs_role") or {}
    if role.get("available"):
        st.write(_text(role.get("detail")) or f"Verified comparable-player sample: {int(role.get('sample_size') or 0)}")
    else:
        st.caption("Verified opponent-vs-role sample unavailable; no directional claim is made.")

    st.markdown('<div class="cfbpp3-section">OPPORTUNITY</div>',unsafe_allow_html=True)
    opportunity=packet.get("opportunity") or {}
    if opportunity.get("available"):
        rows=[{"Metric":name.replace('_',' ').title(),"Average":round(float(data['average']),1),"Sample":int(data['sample_size'])} for name,data in opportunity.get("metrics",{}).items()]
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    else:
        st.caption("Verified opportunity fields unavailable for this market.")

    st.markdown('<div class="cfbpp3-section">OPPONENT DEFENSE</div>',unsafe_allow_html=True)
    matchup=packet.get("matchup") or {}
    st.write(f"**{_text(matchup.get('label')) or 'CHECK'}** — {_text(matchup.get('detail')) or 'Defense data unavailable'}")

    st.markdown('<div class="cfbpp3-section">SPORTSBOOK MARKET • SPORTSBOOK BOARD</div>',unsafe_allow_html=True)
    book_rows=_book_rows(market.get("observations"))
    if book_rows:
        st.dataframe(pd.DataFrame(book_rows),use_container_width=True,hide_index=True)
        bo=market.get("best_over") or {}; bu=market.get("best_under") or {}
        st.caption(f"Best Over: {_text(bo.get('sportsbook')) or '—'} • {_fmt(bo.get('line'))} • {_price(bo.get('price'))}   |   Best Under: {_text(bu.get('sportsbook')) or '—'} • {_fmt(bu.get('line'))} • {_price(bu.get('price'))}")
    else:
        st.info("Current verified sportsbook market unavailable. Player/market identity remains unchanged.")

    movement=view.get("market_movement") or {}
    st.markdown('<div class="cfbpp3-section">MARKET MOVEMENT</div>',unsafe_allow_html=True)
    if movement.get("available"):
        st.write(f"{_fmt(movement.get('opening_line'))} → {_fmt(movement.get('current_line'))} ({float(movement.get('delta') or 0):+.1f}) • {_text(movement.get('sportsbook')) or _text(movement.get('source'))}")
    else:
        st.caption("Verified opening movement unavailable.")

    st.markdown('<div class="cfbpp3-section">GAME ENVIRONMENT</div>',unsafe_allow_html=True)
    st.write(f"Status: **{_text(context.get('status')) or 'Unverified'}** • Venue: **{_text(context.get('venue')) or 'Unavailable'}** • Broadcast: **{_text(context.get('broadcast')) or 'Unavailable'}**")

    st.markdown('<div class="cfbpp3-section">WHY THE MODEL SEES IT THIS WAY</div>',unsafe_allow_html=True)
    reasoning=view.get("reasoning") or packet.get("reasoning") or {}
    for item in reasoning.get("why") or []: st.write(f"• {item}")
    r1,r2=st.columns(2)
    r1.markdown(f"**Supportive Evidence**  \n{_text(reasoning.get('bull_case'))}")
    r2.markdown(f"**Risk Evidence**  \n{_text(reasoning.get('bear_case'))}")

    st.markdown('<div class="cfbpp3-section">DATA QUALITY & SOURCES • EVIDENCE QUALITY</div>',unsafe_allow_html=True)
    quality=view.get("quality") or packet.get("quality") or {}
    q1,q2,q3,q4=st.columns(4)
    q1.metric("Model Sample",str(int(quality.get("model_sample_count") or 0)))
    q2.metric("Books",str(int(quality.get("verified_book_count") or 0)))
    q3.metric("Availability",_text(quality.get("availability_state")) or "UNVERIFIED")
    q4.metric("History Sample",str(int(quality.get("history_sample_size") or 0)))
    history_sources=", ".join(quality.get("history_sources") or ()) or "Unavailable"
    st.caption(f"History sources actually used: {history_sources} • Latest history: {_text(quality.get('latest_history_timestamp')) or 'Unavailable'}")
    st.caption(f"Latest verified market observation: {_text(quality.get('latest_market_timestamp')) or 'Unavailable'} • Sportsbook projection influence: {SPORTSBOOK_PROJECTION_INFLUENCE:.1f}")


__all__=["MARKET_LABELS","SPORTSBOOK_PROJECTION_INFLUENCE","render_cfb_player_props_page3"]
