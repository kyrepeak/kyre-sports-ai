"""MLB Daily Game Picks V1.3 — Step 4 production-input bridge.

Connects REAL production-engine outputs when they already exist in Streamlit session
state or are embedded on the verified game row. No model is reimplemented here and
no probability is fabricated. Missing engines remain explicitly UNCONNECTED.
"""
from __future__ import annotations
import math
import streamlit as st
import mlb_daily_game_picks_v12 as base

VERSION="MLB Daily Game Picks V1.3 • STEP 4"

ALIASES={
 "1+ Hit":("hit","1+ hit","1_hit","hits"),
 "Home Run":("home run","hr","homer"),
 "H+R+RBI":("h+r+rbi","hrrbi","hits+runs+rbis"),
 "Pitcher Strikeouts":("pitcher strikeouts","strikeouts","pitcher k","k"),
 "Moneyline":("moneyline","ml"),"Run Line":("run line","spread","rl"),"Total":("total","totals","over under")}

def _num(v):
 try:
  x=float(v); return x if math.isfinite(x) else None
 except Exception:return None

def _prob(v):
 x=_num(v)
 if x is None:return None
 if x>1 and x<=100:x/=100
 return x if 0<x<1 else None

def _gamepk(row): return str(base.base.base._txt(row,"game_pk","gamePk",default=""))

def _matches_market(obj,market):
 s=" ".join(str(obj.get(k) or "") for k in ("market","market_name","type","prop_type")).lower()
 return any(a in s for a in ALIASES[market]) if s.strip() else False

def _matches_game(obj,gpk):
 ids=[obj.get(k) for k in ("game_pk","gamePk","game_id","gameId")]
 ids=[str(x) for x in ids if x not in (None,"")]
 return (not ids) or gpk in ids

def _candidate_from_obj(obj,market,gpk,confirmed):
 if not isinstance(obj,dict) or not _matches_game(obj,gpk):return None
 if not _matches_market(obj,market) and obj.get("market") is not None:return None
 p=None
 for k in ("win_prob","probability","model_probability","true_probability","p","fair_probability","cover_probability","over_probability","under_probability"):
  p=_prob(obj.get(k))
  if p is not None:break
 if p is None:return None
 rel=None
 for k in ("reliability","model_reliability","confidence","data_reliability"):
  rel=_prob(obj.get(k));
  if rel is not None:break
 dq=None
 for k in ("data_quality","data_quality_score","quality"):
  dq=_prob(obj.get(k));
  if dq is not None:break
 # A missing quality dimension is not guessed: candidate remains unscored.
 if rel is None or dq is None:return None
 name=obj.get("player_name") or obj.get("player") or obj.get("team") or obj.get("selection") or obj.get("side") or "Candidate"
 line=obj.get("line")
 side=obj.get("side") or obj.get("pick") or obj.get("selection") or ""
 unc=_num(obj.get("uncertainty"))
 if unc is not None and unc>1:unc/=100
 norm=base.normalize_candidate(market=market,probability=p,reliability=rel,data_quality=dq,confirmed=bool(obj.get("confirmed",confirmed)),uncertainty=unc,stale=bool(obj.get("stale",False)))
 if norm.get("status")!="SCORED":return None
 return {"market":market,"name":str(name),"side":str(side),"line":line,"probability":p,"reliability":rel,"data_quality":dq,"score":norm["score"],"source":"production state","normalization":norm}

def _walk(value,market,gpk,confirmed,out,depth=0):
 if depth>4:return
 if isinstance(value,dict):
  c=_candidate_from_obj(value,market,gpk,confirmed)
  if c:out.append(c)
  for v in value.values():_walk(v,market,gpk,confirmed,out,depth+1)
 elif isinstance(value,(list,tuple)):
  for v in value[:300]:_walk(v,market,gpk,confirmed,out,depth+1)

def _production_candidates(row,market):
 gpk=_gamepk(row); confirmed=base.base.base._confirmed_flag(row); out=[]
 # Read-only bridge: discover outputs already computed by production pages.
 for key,value in list(st.session_state.items()):
  lk=str(key).lower()
  if any(a.replace(" ","") in lk.replace("_","").replace(" ","") for a in ALIASES[market]) or "rank" in lk or "model" in lk:
   _walk(value,market,gpk,confirmed,out)
 # Also inspect explicit structured payloads attached to the schedule row.
 try:
  for v in row.to_dict().values():
   if isinstance(v,(dict,list,tuple)):_walk(v,market,gpk,confirmed,out)
 except Exception:pass
 # de-dupe without changing model values
 uniq={}
 for c in out:
  k=(c["market"],c["name"],c["side"],str(c["line"]),round(c["probability"],6)); uniq[k]=c
 return sorted(uniq.values(),key=lambda x:x["score"],reverse=True)

def _css():
 st.markdown("""<style>.dgp-bridge-title{font-size:11px;letter-spacing:1.4px;font-weight:900;color:#9eb3c8;text-transform:uppercase;margin:12px 0 8px}.dgp-bridgegrid{display:grid;grid-template-columns:repeat(7,1fr);gap:7px}.dgp-bridge{border:1px solid #29435e;border-radius:12px;background:#0c1b2d;padding:9px 8px;min-height:80px}.dgp-bridge b{display:block;font-size:10px;color:#54dbff}.dgp-bridge span{font-size:10px;font-weight:850;color:#dbe7f4}.dgp-bridge small{display:block;color:#748aa1;font-size:9px;margin-top:5px}@media(max-width:900px){.dgp-bridgegrid{grid-template-columns:repeat(4,1fr)}}@media(max-width:620px){.dgp-bridgegrid{grid-template-columns:repeat(2,1fr)}}</style>""",unsafe_allow_html=True)

def _render_game(row,idx):
 # Reuse Step 3 visual shell, then add a separate auditable Step 4 bridge below it.
 base._render_game(row,idx)
 gamepk=_gamepk(row); allc=[]; cells=[]
 for m in base.base.MARKETS:
  cs=_production_candidates(row,m); allc.extend(cs)
  if cs:
   best=cs[0]; state="CONNECTED"; detail=f"{len(cs)} scored • best {best['score']:.1f}/100"
  else: state="UNCONNECTED"; detail="No complete verified production payload found"
  cells.append(f'<div class="dgp-bridge"><span>{base.base._esc(m)}</span><b>{state}</b><small>{base.base._esc(detail)}</small></div>')
 st.markdown('<div class="dgp-bridge-title">Step 4 • Production model bridge</div><div class="dgp-bridgegrid">'+''.join(cells)+'</div>',unsafe_allow_html=True)
 with st.expander(f"🔌 Step 4 production-input audit • Game {idx} • MLB ID {gamepk}",expanded=False):
  if allc:
   rows=[{"Market":c["market"],"Candidate":c["name"],"Side":c["side"],"Line":c["line"],"Model probability":f"{c['probability']*100:.1f}%","Reliability":f"{c['reliability']*100:.0f}%","Data quality":f"{c['data_quality']*100:.0f}%","Pick Strength":f"{c['score']:.1f}"} for c in sorted(allc,key=lambda x:x["score"],reverse=True)]
   st.dataframe(rows,use_container_width=True,hide_index=True)
   st.caption("Audit only. Step 4 does not choose the game's Top 3; Step 5 will apply final eligibility/diversification rules.")
  else:st.info("No complete production payload is connected for this game yet. Nothing was estimated or imputed.")

def render_daily_game_picks(games_df,section_header=None,status_info=None,team_logo=None,h=None):
 base.base.base._css();base.base._step2_css();base._css();_css()
 if games_df is None or games_df.empty:st.info("No verified MLB games are available for the selected date.");return
 frame=base.base.base._sort_games(games_df);day=base.base.base._txt(frame.iloc[0],"game_date",default="")[:10]
 st.markdown('''<div class="dgp-hero"><div class="dgp-kicker">KYRE SPORTS AI • DAILY GAME PICKS • STEP 4</div><div class="dgp-title">🏆 Top 3 Picks — Every MLB Game</div><div class="dgp-sub">Step 4 bridges verified outputs already produced by the seven production engines into the Step 3 normalization contract. It is read-only: production model math stays untouched, missing probability/reliability/data-quality inputs remain unconnected, and no Top 3 is selected yet.</div></div>''',unsafe_allow_html=True)
 st.success(f"🔌 Step 4 production bridge active • {day or 'selected date'} • {len(frame)} games • no synthetic model inputs")
 for i,(_,row) in enumerate(frame.iterrows(),1):_render_game(row,i)
 st.markdown(f'<div class="dgp-foot">{VERSION} • read-only production bridge • complete probability + reliability + data-quality required • no fabricated inputs • Step 5 Top-3 selection still disabled</div>',unsafe_allow_html=True)
