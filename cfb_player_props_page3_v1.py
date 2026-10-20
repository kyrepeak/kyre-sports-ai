"""CFB Player Props Page 3 V1 — Player Prop Intelligence Lab."""
from __future__ import annotations

from html import escape
from typing import Any

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
#cfbpp3-top{position:absolute;top:0}.cfbpp3-shell{border:1px solid rgba(125,211,252,.18);background:linear-gradient(145deg,rgba(2,8,23,.98),rgba(8,22,39,.98));border-radius:22px;padding:18px;margin-bottom:14px;box-shadow:0 18px 48px rgba(0,0,0,.22)}
.cfbpp3-kicker{font-size:.68rem;font-weight:950;letter-spacing:.16em;color:#7dd3fc}.cfbpp3-title{font-size:clamp(1.55rem,4vw,2.45rem);font-weight:950;letter-spacing:-.04em;color:#f8fafc;margin:.25rem 0}.cfbpp3-sub{font-size:.78rem;color:#8fa9bf}.cfbpp3-hero{display:flex;gap:14px;align-items:center;margin-top:12px}.cfbpp3-face,.cfbpp3-logo{width:62px;height:62px;border-radius:18px;object-fit:cover;border:1px solid rgba(125,211,252,.22);background:#07111f}.cfbpp3-logo{object-fit:contain;padding:6px}.cfbpp3-name{font-size:1.18rem;font-weight:950;color:#f8fafc}.cfbpp3-meta{font-size:.72rem;color:#93a9bc}.cfbpp3-chip{display:inline-flex;margin:7px 6px 0 0;border:1px solid rgba(125,211,252,.2);border-radius:999px;padding:5px 8px;font-size:.64rem;font-weight:850;color:#d8f2ff;background:rgba(14,165,233,.05)}
.cfbpp3-section{font-size:.72rem;font-weight:950;letter-spacing:.12em;color:#7dd3fc;margin:18px 0 8px}.cfbpp3-note{font-size:.72rem;color:#8fa9bf}.cfbpp3-top-btn{position:fixed;right:18px;bottom:22px;z-index:99999;text-decoration:none!important;background:#081727;border:1px solid rgba(125,211,252,.42);color:#e6f7ff!important;border-radius:999px;padding:10px 13px;font-size:.72rem;font-weight:950;box-shadow:0 10px 30px rgba(0,0,0,.3)}
@media(max-width:760px){.cfbpp3-shell{padding:14px;border-radius:17px}.cfbpp3-face,.cfbpp3-logo{width:52px;height:52px}.cfbpp3-top-btn{right:10px;bottom:14px;padding:9px 11px}}
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
        book=_text(getattr(row,"sportsbook","")) or "Unknown"
        item=books.setdefault(book,{"Sportsbook":book,"Over Line":None,"Over Price":None,"Under Line":None,"Under Price":None,"Updated":""})
        side=_text(getattr(row,"side","")).lower()
        if side in {"over","under"}:
            label=side.title()
            item[f"{label} Line"]=float(row.line)
            item[f"{label} Price"]=_price(row.price)
        stamp=_text(getattr(row,"observed_at_utc",""))
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
    st.markdown(f'''<div class="cfbpp3-shell"><div class="cfbpp3-kicker">CFB • PLAYER PROPS • PLAYER PROP INTELLIGENCE LAB</div><div class="cfbpp3-title">{escape(player.canonical_name)} • {escape(market)}</div><div class="cfbpp3-sub">Deep analysis for one verified player and one exact market.</div><div class="cfbpp3-hero">{images}<div><div class="cfbpp3-name">{escape(player.canonical_name)}</div><div class="cfbpp3-meta">{escape(player.position)} • {escape(player.team_name)} vs {escape(_text(opponent))}</div><span class="cfbpp3-chip">{escape(availability)}</span><span class="cfbpp3-chip">{escape(_text(context.get("kickoff_phoenix")) or _text(context.get("kickoff_iso")))}</span><span class="cfbpp3-chip">{escape(_text(context.get("venue")) or "Venue unavailable")}</span></div></div></div>''',unsafe_allow_html=True)


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
    _hero(context,packet)

    current=context["market_key"]
    options=list(dict.fromkeys([current,*list(packet.get("available_markets") or ())]))
    if len(options) > 1:
        selected_market=st.radio("Market",options,index=options.index(current),horizontal=True,format_func=lambda key:MARKET_LABELS.get(key,key),key="cfbpp3_market_selector")
        if selected_market != current and page3_context.switch_page3_market(st.session_state,st.query_params,selected_market):
            st.rerun()

    projection=packet.get("projection") or {}; market=packet.get("market") or {}
    st.markdown('<div class="cfbpp3-section">KYRE PROJECTION VS CURRENT MARKET</div>',unsafe_allow_html=True)
    a,b,c,d=st.columns(4)
    a.metric("Kyre Projection",_fmt(projection.get("projection")))
    b.metric("Market Consensus",_fmt(market.get("consensus_line")))
    diff=None
    if projection.get("projection") is not None and market.get("consensus_line") is not None:
        diff=float(projection["projection"])-float(market["consensus_line"])
    c.metric("Projection − Market",_fmt(diff))
    d.metric("Verified Books",str(int(market.get("book_count") or 0)))

    identity=f"{context['official_game_id']}:{context['official_player_id']}:{current}"
    initial=packet.get("line_lab",{}).get("line") or line_lab.default_line(current,consensus_line=market.get("consensus_line"),handoff_line=context.get("handoff_line"))
    if st.session_state.get("cfbpp3_line_identity") != identity:
        st.session_state["cfbpp3_line_identity"]=identity
        st.session_state["cfbpp3_line"]=initial
    low,high,step=line_lab.LINE_BOUNDS[current]
    st.markdown('<div class="cfbpp3-section">LINE LAB</div>',unsafe_allow_html=True)
    selected_line=st.slider("Move the line",min_value=float(low),max_value=float(high),value=float(st.session_state.get("cfbpp3_line") or initial),step=float(step),key=f"cfbpp3_slider_{identity}")
    st.session_state["cfbpp3_line"]=selected_line
    packet=page3_analysis.reline_page3_analysis(packet,selected_line)
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

    st.markdown('<div class="cfbpp3-section">SPORTSBOOK BOARD</div>',unsafe_allow_html=True)
    book_rows=_book_rows(market.get("observations"))
    if book_rows:
        st.dataframe(pd.DataFrame(book_rows),use_container_width=True,hide_index=True)
        bo=market.get("best_over") or {}; bu=market.get("best_under") or {}
        st.caption(f"Best Over: {_text(bo.get('sportsbook')) or '—'} • {_fmt(bo.get('line'))} • {_price(bo.get('price'))}   |   Best Under: {_text(bu.get('sportsbook')) or '—'} • {_fmt(bu.get('line'))} • {_price(bu.get('price'))}")
    else:
        st.info("Current verified sportsbook market unavailable. Player/market identity remains unchanged.")

    movement=packet.get("movement") or {}
    st.markdown('<div class="cfbpp3-section">MARKET MOVEMENT</div>',unsafe_allow_html=True)
    if movement.get("available"):
        st.write(f"{_fmt(movement.get('opening_line'))} → {_fmt(movement.get('current_line'))} ({float(movement.get('delta') or 0):+.1f})")
    else:
        st.caption("Verified opening movement unavailable.")

    st.markdown('<div class="cfbpp3-section">RECENT PRODUCTION</div>',unsafe_allow_html=True)
    history=packet.get("history") or {}
    h1,h2,h3=st.columns(3)
    for col,key,label in ((h1,"last5","L5"),(h2,"last8","L8"),(h3,"season","Season")):
        part=history.get(key) or {}; rate=part.get("hit_rate")
        col.metric(label,f"{_pct(rate)} • {int(part.get('hits') or 0)}/{int(part.get('sample_size') or 0)}" if rate is not None else f"n={int(part.get('sample_size') or 0)}")
    chart=history.get("chart") or []
    if chart:
        frame=pd.DataFrame([{"Game":r.get("game_date") or r.get("event_id"),"Production":r.get("value"),"Selected Line":r.get("comparison_line")} for r in reversed(chart)])
        st.line_chart(frame.set_index("Game"))

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

    st.markdown('<div class="cfbpp3-section">PLAYER VS OPPONENT</div>',unsafe_allow_html=True)
    prior=packet.get("prior_opponent") or {}
    if prior.get("available"):
        st.dataframe(pd.DataFrame(list(prior.get("rows") or ())),use_container_width=True,hide_index=True)
    else:
        st.caption("No verified prior matchup sample.")

    st.markdown('<div class="cfbpp3-section">GAME ENVIRONMENT</div>',unsafe_allow_html=True)
    st.write(f"Status: **{_text(context.get('status')) or 'Unverified'}** • Venue: **{_text(context.get('venue')) or 'Unavailable'}** • Broadcast: **{_text(context.get('broadcast')) or 'Unavailable'}**")

    st.markdown('<div class="cfbpp3-section">WHY THE MODEL SEES IT THIS WAY</div>',unsafe_allow_html=True)
    reasoning=packet.get("reasoning") or {}
    for item in reasoning.get("why") or []: st.write(f"• {item}")
    r1,r2=st.columns(2)
    r1.markdown(f"**Bull Case**  \n{_text(reasoning.get('bull_case'))}")
    r2.markdown(f"**Bear Case**  \n{_text(reasoning.get('bear_case'))}")

    st.markdown('<div class="cfbpp3-section">EVIDENCE QUALITY</div>',unsafe_allow_html=True)
    quality=packet.get("quality") or {}
    q1,q2,q3,q4=st.columns(4)
    q1.metric("Model Sample",str(int(quality.get("model_sample_count") or 0)))
    q2.metric("Books",str(int(quality.get("verified_book_count") or 0)))
    q3.metric("Availability",_text(quality.get("availability_state")) or "UNVERIFIED")
    q4.metric("Movement","Verified" if quality.get("movement_available") else "Unavailable")
    st.caption(f"Latest verified market observation: {_text(quality.get('latest_market_timestamp')) or 'Unavailable'} • Sportsbook projection influence: {SPORTSBOOK_PROJECTION_INFLUENCE:.1f}")


__all__=["MARKET_LABELS","SPORTSBOOK_PROJECTION_INFLUENCE","render_cfb_player_props_page3"]
