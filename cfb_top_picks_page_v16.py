"""CFB Top Picks V16 — adaptive Page 2 analytics lab."""
from __future__ import annotations
from html import escape
import json, os
from textwrap import dedent
from typing import Any, Mapping, Sequence
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import streamlit as st
import cfb_top_picks_page_v15 as page1

MODEL_VERSION="CFB TOP PICKS V16 • ADAPTIVE ANALYTICS LAB V1"
PAGE_MARKER="CFB_TOP_PICKS_PAGE2_ANALYTICS_LAB_V1_ACTIVE"
PAGE2_ENDPOINT="/api/v1/cfb/top-picks/page2"
KYRE_SPORTS_API_BASE_URL=os.getenv("KYRE_SPORTS_API_BASE_URL","https://kyre-sports-api.vercel.app").rstrip("/")

CSS=r'''<style id="cfb-top-picks-v16-css">
:root{--b:#050c13;--p:#071725;--p2:#0a1d2d;--l:rgba(80,193,255,.2);--x:#4dc9ff;--t:#f4fbff;--m:#8099aa;--g:#73e5b5;--y:#ffd274;--r:#ff9797}
[data-testid="cfb-top-picks-page2-v1-root"]{max-width:1180px;margin:auto;padding:8px 2px 48px;color:var(--t);font-family:Inter,system-ui,sans-serif}.p2-back{display:inline-block;margin-bottom:10px;padding:7px 10px;border:1px solid var(--l);border-radius:9px;color:#9bdcff!important;text-decoration:none!important;font-size:.65rem;font-weight:900}.p2-shell{border:1px solid rgba(79,195,255,.25);border-radius:22px;overflow:hidden;background:radial-gradient(circle at 75% -10%,rgba(33,170,233,.14),transparent 30%),linear-gradient(150deg,#071725,#040c14);box-shadow:0 24px 70px rgba(0,0,0,.3)}.p2-hero{padding:20px 22px;border-bottom:1px solid rgba(255,255,255,.06)}.p2-brand{display:flex;justify-content:space-between;color:#8ba6b7;font-size:.58rem;font-weight:900;letter-spacing:.08em}.p2-live:before{content:"";display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--g);margin-right:6px}.p2-title{display:flex;justify-content:space-between;gap:16px;align-items:end;margin-top:14px}.p2-title h1{margin:0;font-size:2rem;letter-spacing:-.045em}.p2-title p{margin:5px 0 0;color:var(--m);font-size:.72rem}.p2-pick{padding:12px 14px;border:1px solid var(--l);border-radius:13px;background:rgba(15,54,78,.28);text-align:right}.p2-pick b{display:block;font-size:1rem}.p2-pick span{font-size:.58rem;color:#9ab6c7}.p2-grid{display:grid;grid-template-columns:1.05fr 1.05fr;gap:12px;padding:14px 18px}.p2-card{border:1px solid rgba(81,188,245,.14);border-radius:14px;background:linear-gradient(150deg,rgba(8,27,43,.96),rgba(6,18,29,.98));padding:14px}.p2-wide{grid-column:1/-1}.p2-card h2{margin:0 0 9px;font-size:.78rem;letter-spacing:.03em}.p2-kicker{font-size:.5rem;font-weight:950;color:var(--x);letter-spacing:.08em;margin-bottom:4px}.p2-metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.p2-metric{padding:9px;border-radius:10px;background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.05)}.p2-metric b{display:block;font-size:1.05rem}.p2-metric span{font-size:.49rem;color:var(--m);font-weight:900}.p2-verdict{font-size:1.25rem;font-weight:950;color:var(--g)}.p2-verdict.pass{color:var(--y)}.p2-list{display:grid;gap:7px}.p2-row{display:grid;grid-template-columns:1.2fr repeat(3,.7fr);gap:8px;padding:8px;border-radius:9px;background:rgba(255,255,255,.022);font-size:.6rem}.p2-row b{font-size:.64rem}.p2-note{color:var(--m);font-size:.62rem;line-height:1.45}.p2-badge{display:inline-block;padding:3px 6px;border-radius:6px;background:rgba(77,201,255,.11);color:#74d6ff;font-size:.5rem;font-weight:950}.p2-unavail{padding:9px;border-radius:9px;border:1px solid rgba(255,210,116,.15);background:rgba(83,61,18,.1);color:#d8bd73;font-size:.6rem}.p2-source{display:flex;justify-content:space-between;gap:10px;padding:7px 0;border-bottom:1px solid rgba(255,255,255,.04);font-size:.58rem}.p2-source:last-child{border:0}.p2-foot{padding:12px 18px 18px;text-align:center;color:#587387;font-size:.52rem}
@media(max-width:850px){.p2-grid{grid-template-columns:1fr}.p2-wide{grid-column:auto}.p2-metrics{grid-template-columns:repeat(2,1fr)}}@media(max-width:600px){.p2-title{align-items:flex-start;flex-direction:column}.p2-pick{text-align:left}.p2-grid{padding:10px}.p2-hero{padding:16px 14px}.p2-row{grid-template-columns:1fr 1fr}.p2-title h1{font-size:1.65rem}}
</style>'''

def _c(v:Any)->str:return str(v or "").strip()
def _pct(v:Any)->str:
    try:return f"{float(v)*100:.1f}%"
    except Exception:return "—"
def _num(v:Any,d=1)->str:
    try:return f"{float(v):.{d}f}"
    except Exception:return "—"
def _odds(v:Any)->str:
    try:x=int(v);return f"+{x}" if x>0 else str(x)
    except Exception:return "—"
def _qp(name:str)->str:
    try:v=st.query_params.get(name)
    except Exception:v=None
    if isinstance(v,list):v=v[0] if v else None
    return _c(v)
def _safe(s:str)->str:return dedent(s).strip()

def _page1_handoff(row:Mapping[str,Any],kind:str)->str:
    q={"top_pick_id":_c(row.get("candidate_id")),"top_pick_kind":kind,"top_pick_date":_c(row.get("selected_date") or _c(row.get("kickoff_iso"))[:10])}
    return "?"+urlencode({k:v for k,v in q.items() if v})

def _back_href(snapshot:Mapping[str,Any])->str:
    day=_c(snapshot.get("selected_date"));return "?"+(urlencode({"top_pick_date":day}) if day else "")

@st.cache_data(ttl=30,show_spinner=False)
def _load_page2(candidate_id:str,kind:str,date_:str)->dict[str,Any]:
    q={"candidate_id":candidate_id}
    if kind:q["kind"]=kind
    if date_:q["game_date"]=date_
    req=Request(f"{KYRE_SPORTS_API_BASE_URL}{PAGE2_ENDPOINT}?{urlencode(q)}",headers={"Accept":"application/json","User-Agent":"KyreSportsAI/TopPicksPage2"})
    with urlopen(req,timeout=45) as r:p=json.loads(r.read().decode("utf-8"))
    if _c(p.get("service"))!="Kyre Sports API":raise RuntimeError("Invalid Kyre Sports API Page 2 contract")
    return dict(p)

def _module(payload:Mapping[str,Any],key:str)->Mapping[str,Any]:
    v=payload.get(key);return v if isinstance(v,Mapping) else {"status":"DATA_UNAVAILABLE"}
def _unavailable(m:Mapping[str,Any])->str:return f'<div class="p2-unavail">{escape(_c(m.get("reason")) or "Verified data is not currently available for this module.")}</div>'
def _metric(label:str,value:str)->str:return f'<div class="p2-metric"><b>{escape(value)}</b><span>{escape(label)}</span></div>'

def _hero(snapshot:Mapping[str,Any])->str:
    prop=_c(snapshot.get("kind"))=="player-prop"
    title=_c(snapshot.get("player_name")) if prop else f"{_c(snapshot.get('away_team'))} @ {_c(snapshot.get('home_team'))}"
    selection=_c(snapshot.get("selection")) or f"{_c(snapshot.get('side'))} {_c(snapshot.get('line'))}"
    market=_c(snapshot.get("market_label") or snapshot.get("market_type") or snapshot.get("market_key")).replace("_"," ").upper()
    subtitle=f"{market} • {_c(snapshot.get('sportsbook'))} {_odds(snapshot.get('american_odds'))}"
    if prop:subtitle+=f" • {_c(snapshot.get('player_team'))} vs {_c(snapshot.get('opponent'))}"
    return f'<div class="p2-hero"><div class="p2-brand"><b>KYRE SPORTS AI • TOP PICKS LAB</b><span class="p2-live">KYRE SPORTS API LIVE</span></div><div class="p2-title"><div><h1>{escape(title)}</h1><p>{escape(subtitle)}</p></div><div class="p2-pick"><span>SELECTED PICK</span><b>{escape(selection)}</b><span>{_pct(snapshot.get("probability"))} HIT PROBABILITY</span></div></div></div>'

def _verdict(payload:Mapping[str,Any])->str:
    v=_module(payload,"kyre_verdict")
    if v.get("status")!="READY":return _unavailable(v)
    verdict=_c(v.get("verdict"));cls="pass" if "PASS" in verdict else ""
    return f'<div class="p2-card"><div class="p2-kicker">KYRE VERDICT</div><div class="p2-verdict {cls}">{escape(verdict)}</div><div class="p2-metrics" style="margin-top:10px">{_metric("OUTCOME CONFIDENCE",_pct(v.get("outcome_confidence")))}{_metric("MARKET IMPLIED",_pct(v.get("market_implied_probability")))}{_metric("VALUE EDGE",_pct(v.get("market_value_edge")))}{_metric("MODEL FAIR PRICE",_odds(v.get("model_fair_price")))}</div></div>'

def _lab(payload:Mapping[str,Any])->str:
    m=_module(payload,"line_lab")
    if m.get("status")!="READY":return f'<div class="p2-card"><h2>LINE / PRICE LAB</h2>{_unavailable(m)}</div>'
    rows=[]
    for r in m.get("scenarios") or []:
        if m.get("lab_type")=="PRICE":rows.append(f'<div class="p2-row"><b>{_odds(r.get("american_odds"))}</b><span>Implied {_pct(r.get("implied_probability"))}</span><span>Model {_pct(r.get("model_probability"))}</span><span>Edge {_pct(r.get("market_value_edge"))}</span></div>')
        else:
            p=r.get("selected_side_probability") if r.get("selected_side_probability") is not None else r.get("over_probability")
            rows.append(f'<div class="p2-row"><b>Line {_num(r.get("line"))}</b><span>Hit {_pct(p)}</span><span>{escape(_c(r.get("model_owner")))}</span><span>MODEL OWNED</span></div>')
    return f'<div class="p2-card"><div class="p2-kicker">{escape(_c(m.get("lab_type")))} LAB</div><h2>LINE / PRICE LAB</h2><div class="p2-list">{"".join(rows)}</div></div>'

def _projection(payload:Mapping[str,Any])->str:
    p=_module(payload,"projection")
    if p.get("status") not in {"READY","PARTIAL"}:return f'<div class="p2-card"><h2>MODEL PROJECTION</h2>{_unavailable(p)}</div>'
    metrics=[]
    for label,key,fmt in (("HOME POINTS","projected_home_points",_num),("AWAY POINTS","projected_away_points",_num),("HOME MARGIN","projected_margin_home",_num),("PROJECTED TOTAL","projected_total",_num),("SELECTED HIT","selected_hit_probability",_pct)):
        if p.get(key) is not None:metrics.append(_metric(label,fmt(p.get(key))))
    if not metrics:metrics=[_metric("SELECTED HIT",_pct(p.get("selected_probability")))]
    return f'<div class="p2-card"><div class="p2-kicker">MODEL</div><h2>PROJECTION</h2><div class="p2-metrics">{"".join(metrics)}</div><p class="p2-note">{escape(_c(p.get("reason") or p.get("model_owner")))}</p></div>'

def _drivers(payload:Mapping[str,Any])->str:
    d=_module(payload,"drivers");items=d.get("items") or []
    if not items:return f'<div class="p2-card"><h2>WHY THIS PICK</h2>{_unavailable(d)}</div>'
    body=[]
    for x in items[:8]:
        val=_c(x.get("value")) or f"Away {_num(x.get('away'))} • Home {_num(x.get('home'))}"
        body.append(f'<div class="p2-source"><b>{escape(_c(x.get("title")))}</b><span>{escape(val)}</span></div>')
    return f'<div class="p2-card"><div class="p2-kicker">DEEP WHY</div><h2>WHY THIS PICK</h2>{"".join(body)}</div>'

def _market(payload:Mapping[str,Any])->str:
    m=_module(payload,"market_board");quotes=m.get("quotes") or []
    if not quotes:return f'<div class="p2-card p2-wide"><h2>LIVE MARKET BOARD</h2>{_unavailable(m)}</div>'
    rows=[]
    for q in quotes[:12]:rows.append(f'<div class="p2-row"><b>{escape(_c(q.get("sportsbook")))}</b><span>{escape(_c(q.get("side")))} {_num(q.get("line")) if q.get("line") is not None else ""}</span><span>{_odds(q.get("american_odds"))}</span><span>{escape(_c(q.get("observed_at_utc"))[-8:] or "LIVE")}</span></div>')
    return f'<div class="p2-card p2-wide"><div class="p2-kicker">EXACT BOOKS • NEVER AVERAGED</div><h2>LIVE MARKET BOARD</h2><div class="p2-list">{"".join(rows)}</div></div>'

def _notes(payload:Mapping[str,Any],key:str,title:str)->str:
    m=_module(payload,key);items=m.get("items") or []
    if not items:return f'<div class="p2-card"><h2>{escape(title)}</h2>{_unavailable(m)}</div>'
    return f'<div class="p2-card"><h2>{escape(title)}</h2>'+"".join(f'<div class="p2-source"><b>{escape(_c(x.get("title")))}</b><span>{escape(_c(x.get("text") or x.get("value")))}</span></div>' for x in items)+"</div>"

def _sources(payload:Mapping[str,Any])->str:
    s=_module(payload,"sources");mods=s.get("modules") or {}
    body="".join(f'<div class="p2-source"><b>{escape(str(k).replace("_"," ").upper())}</b><span>{escape(_c(v))}</span></div>' for k,v in mods.items())
    return f'<div class="p2-card p2-wide"><div class="p2-kicker">SOURCE + FRESHNESS AUDIT</div><h2>KYRE SPORTS API ROUTING</h2>{body}<p class="p2-note">No SGO. No ESPN / ESPN BET. Null is never treated as zero. Sportsbook projection influence: 0.0.</p></div>'

def render_page2_html(payload:Mapping[str,Any])->str:
    s=payload.get("selection_snapshot") or {}
    if not s:return '<div data-testid="cfb-top-picks-page2-v1-root"><div class="p2-unavail">The selected Page 1 candidate could not be verified. Return to Top Picks and tap a current card.</div></div>'
    return _safe(f'''<div data-testid="cfb-top-picks-page2-v1-root"><a class="p2-back" href="{escape(_back_href(s))}">← Back to Top Picks</a><div class="p2-shell">{_hero(s)}<div class="p2-grid">{_verdict(payload)}{_lab(payload)}{_projection(payload)}{_drivers(payload)}{_market(payload)}{_notes(payload,"risks","RISKS / WHAT COULD GO WRONG")}{_notes(payload,"flip_conditions","WHAT WOULD FLIP THE PICK")}{_sources(payload)}</div><div class="p2-foot">PAGE 2 ANALYTICS LAB • MODEL OUTPUTS OWNED BY KYRE SPORTS API • SPORTSBOOKS PROVIDE MARKET CONTEXT ONLY</div></div></div>''')

def render_cfb_hub(market_name:str="Top Picks")->None:
    candidate=_qp("top_pick_id")
    if not candidate:
        original=page1._handoff
        page1._handoff=_page1_handoff
        try:return page1.render_cfb_hub(market_name)
        finally:page1._handoff=original
    st.markdown(CSS,unsafe_allow_html=True)
    try:p=_load_page2(candidate,_qp("top_pick_kind"),_qp("top_pick_date"))
    except Exception as exc:
        st.error(f"Top Picks Page 2 could not load: {type(exc).__name__}");return
    st.markdown(render_page2_html(p),unsafe_allow_html=True)

__all__=["MODEL_VERSION","PAGE_MARKER","PAGE2_ENDPOINT","render_cfb_hub","render_page2_html"]
