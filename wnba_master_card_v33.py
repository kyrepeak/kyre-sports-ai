"""WNBA V3.3 unified Daily Master Card.

Consumes completed production outputs only. PRA + Points can compete on the same
card. Future Rebounds/Assists/Spread/Moneyline/Total connectors can plug into the
same contract later. Never forces five picks; one pick per game; no repeated
player. Sportsbook prices are grading inputs only.
"""
from __future__ import annotations

from html import escape
import numpy as np
import pandas as pd
import streamlit as st

import wnba_pra_final_v32 as pra_final
import wnba_points_v10 as points

MAX_CARD = 5


def _num(v, default=np.nan):
    try:
        x=float(v); return default if pd.isna(x) else x
    except Exception:return default


def _fmt_pct(v):
    try:return f"{100*float(v):.1f}%"
    except Exception:return "—"


def _fmt_pp(v):
    try:return f"{100*float(v):+.1f} pp"
    except Exception:return "—"


def _fmt_odds(v):
    try:return f"{int(round(float(v))):+d}"
    except Exception:return "—"


def _source_rows(day):
    frames=[]; sources=[]
    pra,_meta=pra_final._stored_rows(day)
    if isinstance(pra,pd.DataFrame) and not pra.empty:
        p=pra.copy(); p["market"]="PRA"; frames.append(p); sources.append("PRA")
    pts=points.combined_rows(day)
    if isinstance(pts,pd.DataFrame) and not pts.empty:
        p=pts.copy(); p["market"]="Points"; frames.append(p); sources.append("Points")
    if not frames:return pd.DataFrame(),sources
    cols=set().union(*(set(f.columns) for f in frames))
    aligned=[]
    for f in frames:
        g=f.copy()
        for c in cols:
            if c not in g.columns:g[c]=np.nan
        aligned.append(g[list(cols)])
    return pd.concat(aligned,ignore_index=True),sources


def _decision_strength(r):
    p=float(np.clip(_num(r.get("model_over"),0),0,1)); edge=float(np.clip(_num(r.get("edge"),-.5),-.5,.5))
    data=float(np.clip(_num(r.get("data_quality"),0),0,1)); ctx=float(np.clip(_num(r.get("context_quality"),0),0,1)); fresh=float(np.clip(_num(r.get("fresh_score"),0),0,1)); conv=1.0 if bool(r.get("converged")) else 0.0
    score=100*(.46*p+.24*float(np.clip(.50+edge,0,1))+.10*data+.08*ctx+.07*fresh+.05*conv)
    if not bool(r.get("lineup_ready")):score-=4
    if str(r.get("freshness") or "").upper()=="AGING":score-=2
    return float(np.clip(score,0,100))


def _decision(r):
    if not bool(r.get("converged")):return "⛔ AVOID","avoid","Monte Carlo convergence failed."
    if str(r.get("freshness") or "").upper()=="STALE":return "⛔ AVOID","avoid","Sportsbook quote is stale."
    if str(r.get("role_label") or "").upper()=="OUT":return "⛔ AVOID","avoid","Player status is OUT."
    if not bool(r.get("model_qualified")):return "⛔ NO EDGE","avoid","Production probability/no-vig edge gates were not cleared."
    reasons=[]
    if not bool(r.get("lineup_ready")):reasons.append("confirmed starting five pending")
    if str(r.get("freshness") or "").upper()=="AGING":reasons.append("sportsbook quote aging")
    if reasons:return "⚠️ MONITOR","monitor","; ".join(reasons)
    strength=_decision_strength(r)
    if bool(r.get("final_ready")) and _num(r.get("model_over"),0)>=.60 and _num(r.get("edge"),0)>=.05 and strength>=78:
        return "🔥 BEST BET","best","Elite qualified production edge with confirmed pregame checks."
    return "✅ STRONG","strong","Qualified production edge with confirmed pregame checks."


def _best_offers(rows):
    if rows.empty:return rows
    f=rows.copy(); f["_price"]=pd.to_numeric(f["over_odds"],errors="coerce").fillna(-100000); f["_fresh"]=pd.to_numeric(f["fresh_score"],errors="coerce").fillna(0)
    f=f.sort_values(["market","game_id","player_key","line","edge","_price","_fresh"],ascending=[True,True,True,True,False,False,False])
    return f.drop_duplicates(["market","game_id","player_key","line"],keep="first").drop(columns=["_price","_fresh"])


def select_master_card(rows,limit=MAX_CARD):
    offers=_best_offers(rows); candidates=[]
    for _,r in offers.iterrows():
        label,cls,reason=_decision(r)
        if cls=="avoid":continue
        o=r.to_dict(); o.update({"decision_label":label,"decision_class":cls,"decision_reason":reason,"decision_strength":_decision_strength(r)}); candidates.append(o)
    candidates.sort(key=lambda x:(1 if x["decision_class"] in {"best","strong"} else 0,x["decision_strength"],_num(x.get("model_over"),0),_num(x.get("edge"),-1)),reverse=True)
    selected=[]; games=set(); players=set()
    for r in candidates:
        gid=str(r.get("game_id") or ""); pk=str(r.get("player_key") or r.get("player") or "").lower()
        if not gid or gid in games or pk in players:continue
        selected.append(r); games.add(gid); players.add(pk)
        if len(selected)>=limit:break
    return pd.DataFrame(selected)


def _connector(name,state,live=False,armed=False):
    fg="#66e5ac" if live else ("#ffe178" if armed else "#8aa0b2"); border="#276b52" if live else ("#726322" if armed else "#30495d")
    return f'<div style="border:1px solid {border};background:#071827;border-radius:12px;padding:9px;text-align:center;margin:3px 0"><div style="font-size:9px;color:#7895aa;font-weight:900">{escape(name)}</div><div style="font-size:10px;color:{fg};font-weight:1000;margin-top:3px">{escape(state)}</div></div>'


def _render_connectors(day,sources):
    pts_live="Points" in sources
    items=[("PRA","✅ LIVE","PRA" in sources,False),("Points","✅ LIVE" if pts_live else "ARMED",pts_live,not pts_live),("Rebounds","NEXT",False,False),("Assists","NEXT",False,False),("Spread","NEXT",False,False),("Moneyline","NEXT",False,False),("Total","NEXT",False,False)]
    cols=st.columns(4)
    for i,(n,s,l,a) in enumerate(items):cols[i%4].markdown(_connector(n,s,l,a),unsafe_allow_html=True)


def _card_html(r,rank,day):
    market_name=str(r.get("market") or "Prop"); logo=pra_final._team_logo(day,r.get("team")); logo_html=f'<img src="{escape(logo)}" style="width:36px;height:36px;object-fit:contain;margin-right:8px">' if logo else ""
    cls=str(r.get("decision_class") or "strong"); label=str(r.get("decision_label") or ""); sims=int(_num(r.get("sims"),0))
    return f'''<div style="border:1px solid #315a78;background:linear-gradient(145deg,#071a2b,#061420);border-radius:18px;padding:16px;margin:7px 0 4px;min-height:300px"><div style="font-size:9px;letter-spacing:1.1px;color:#65dfff;font-weight:900">🏆 DAILY #{rank} • {escape(market_name.upper())} OVER</div><div style="margin:8px 0"><span style="{pra_final._badge_style(cls)}">{escape(label)}</span></div><div style="display:flex;align-items:center;margin-top:8px">{logo_html}<div style="font-size:22px;font-weight:1000;color:#fff">{escape(str(r.get('player') or 'Player'))}</div></div><div style="font-size:11px;color:#8ca6ba;margin-top:4px">{escape(str(r.get('team') or ''))} vs {escape(str(r.get('opponent') or ''))}</div><div style="font-size:13px;color:#fff;margin-top:10px">OVER {float(_num(r.get('line'),0)):g} {escape(market_name)} • {escape(str(r.get('book') or ''))} {_fmt_odds(r.get('over_odds'))}</div><div style="font-size:34px;font-weight:1000;color:#62dcff;margin-top:12px">{_fmt_pct(r.get('model_over'))}</div><div style="font-size:8px;color:#7d9aaf;font-weight:800">TRUE MC OVER PROBABILITY</div><div style="border-left:4px solid #55d8ff;background:#062033;border-radius:8px;padding:9px 10px;margin-top:10px;font-size:11px;color:#c1d2df">Adjusted {escape(market_name)} {_num(r.get('projection'),0):.2f} • MC mean {_num(r.get('sim_mean'),0):.2f} • Median {_num(r.get('sim_median'),0):g} • 10–90 {_num(r.get('p10'),0):g}–{_num(r.get('p90'),0):g}</div><div style="border:1px solid #31536a;border-radius:10px;padding:9px 10px;margin-top:9px;font-size:10px;color:#c2d2df">No-vig {_fmt_pct(r.get('no_vig_over'))} • Edge {_fmt_pp(r.get('edge'))} • Fair {_fmt_odds(r.get('fair_over'))}</div><div style="font-size:30px;font-weight:1000;color:#fff;margin-top:12px">{_decision_strength(r):.1f}<span style="font-size:8px;color:#7895aa"> /100 FINAL CARD STRENGTH</span></div><div style="font-size:9px;color:#7f9aaf;margin-top:8px">{sims:,} sims • {int(_num(r.get('batches'),0))} batches • MC SE {100*_num(r.get('mc_se'),0):.4f} pp • {escape(str(r.get('pass_source') or '5M'))}</div></div>'''


def _why(r):
    label,_,reason=_decision(r); m=str(r.get("market") or "Prop")
    st.markdown(f"**🎯 Model case**  \nAdjusted {m}: {_num(r.get('projection'),0):.2f} vs line {_num(r.get('line'),0):g}. MC mean {_num(r.get('sim_mean'),0):.2f}, median {_num(r.get('sim_median'),0):g}, 10–90 {_num(r.get('p10'),0):g}–{_num(r.get('p90'),0):g}. True Over {_fmt_pct(r.get('model_over'))}.")
    st.markdown(f"**📈 Market context**  \n{r.get('book','')} {_fmt_odds(r.get('over_odds'))}; no-vig {_fmt_pct(r.get('no_vig_over'))}; edge {_fmt_pp(r.get('edge'))}; fair {_fmt_odds(r.get('fair_over'))}; freshness {r.get('freshness','UNKNOWN')}.")
    st.markdown(f"**🧪 Simulation verification**  \n{int(_num(r.get('sims'),0)):,} sims • {int(_num(r.get('batches'),0))} batches • seed {int(_num(r.get('seed'),0))} • MC SE {100*_num(r.get('mc_se'),0):.4f} pp • converged={'YES' if bool(r.get('converged')) else 'NO'} • variance {r.get('variance_source','unknown')}.")
    st.markdown(f"**🛰 Pregame decision**  \nStarting five {'confirmed' if bool(r.get('lineup_ready')) else 'pending'} • role {r.get('role_label','ACTIVE')} • decision {label}. {reason}")


def render_master_card(day):
    rows,sources=_source_rows(day)
    st.markdown("## 🏆 WNBA Final Decision + Daily Master Card")
    st.caption("Slate-wide production selector • completed simulations only • no forced five • one pick per game • no repeated player.")
    _render_connectors(day,sources)
    if rows.empty:
        st.info("Run a production connector's 5M pass. The WNBA Master Card will populate automatically from completed outputs."); return
    offers=_best_offers(rows); selected=select_master_card(rows)
    qualified=int(offers["model_qualified"].fillna(False).sum()) if "model_qualified" in offers else 0
    ready=int(offers["final_ready"].fillna(False).sum()) if "final_ready" in offers else 0
    monitors=sum(1 for _,r in offers.iterrows() if bool(r.get("model_qualified")) and _decision(r)[1]=="monitor")
    active_games=int(rows["game_id"].astype(str).nunique()) if "game_id" in rows else 0
    confirmed=int(rows.groupby("game_id")["lineup_ready"].first().sum()) if "lineup_ready" in rows else 0
    st.markdown(f'''<div style="border:1px solid #315b7a;background:linear-gradient(145deg,#0b1d31,#07131f);border-radius:20px;padding:16px;margin:12px 0"><div style="font-size:9px;letter-spacing:1.2px;color:#67ddff;font-weight:950">KYRE SPORTS AI • WNBA DAILY MASTER CARD • V3.3</div><div style="font-size:28px;font-weight:1000;color:#fff;margin-top:4px">🏆 Daily Master Card — Top 5 WNBA Picks</div><div style="font-size:10px;color:#8da5b8;margin-top:5px">Live production sources: {escape(', '.join(sources) or 'none')}</div><div style="display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:7px;margin-top:14px"><div style="border:1px solid #29475f;border-radius:11px;padding:9px"><div style="font-size:7px;color:#7995aa">LIVE CONNECTORS</div><div style="font-size:15px;color:#fff;font-weight:1000">{len(sources)}/7</div></div><div style="border:1px solid #29475f;border-radius:11px;padding:9px"><div style="font-size:7px;color:#7995aa">QUALIFIED</div><div style="font-size:15px;color:#66e5ac;font-weight:1000">{qualified}</div></div><div style="border:1px solid #29475f;border-radius:11px;padding:9px"><div style="font-size:7px;color:#7995aa">FINAL READY</div><div style="font-size:15px;color:#66e5ac;font-weight:1000">{ready}</div></div><div style="border:1px solid #29475f;border-radius:11px;padding:9px"><div style="font-size:7px;color:#7995aa">MONITOR</div><div style="font-size:15px;color:#ffe178;font-weight:1000">{monitors}</div></div><div style="border:1px solid #29475f;border-radius:11px;padding:9px"><div style="font-size:7px;color:#7995aa">CARD</div><div style="font-size:15px;color:#fff;font-weight:1000">{len(selected)}/5</div><div style="font-size:7px;color:#7895aa">Lineups {confirmed}/{active_games}</div></div></div></div>''',unsafe_allow_html=True)
    if selected.empty:
        st.warning("🏆 NO QUALIFIED WNBA PICKS from the currently completed production connectors. The card is intentionally empty; nothing is forced.")
        with st.expander("👀 Closest model-vs-market results — NOT Final Card picks",expanded=False):
            watch=offers.sort_values(["model_over","edge"],ascending=[False,False]).head(8)
            st.dataframe(pd.DataFrame({"Market":watch["market"],"Player":watch["player"],"Book":watch["book"],"Line":watch["line"],"P(Over)":watch["model_over"].map(_fmt_pct),"No-vig":watch["no_vig_over"].map(_fmt_pct),"Edge":watch["edge"].map(_fmt_pp),"Status":[_decision(r)[0] for _,r in watch.iterrows()]}),use_container_width=True,hide_index=True)
        return
    records=selected.to_dict("records")
    for i in range(0,len(records),2):
        cols=st.columns(2)
        for j in range(2):
            idx=i+j
            if idx>=len(records):continue
            r=records[idx]
            with cols[j]:
                st.markdown(_card_html(r,idx+1,day),unsafe_allow_html=True)
                with st.expander("🧠 Why this pick?",expanded=False):_why(r)


__all__=["render_master_card","select_master_card"]
