"""MLB 1+ Hit UI V13.16 — step grades + final evidence summary.

Presentation-only wrapper over certified V13.15. No probability, simulation,
candidate-pool, ranking, calibration, confidence or persistence math is changed.
"""
from __future__ import annotations

from html import escape, unescape
import math
import re
import streamlit as st
import mlb_hit_hub_v1315 as prior

active, core, visual = prior.active, prior.core, prior.visual
UI_VERSION = "V13.16"
_BASE_PICK_HTML = prior._pick_html_v1315
MARKERS = {1:"MLB BATTER + TEAM IDENTITY",2:"OPPOSING PROBABLE STARTER",3:"BATTER VS PITCHER",4:"STEP 4",5:"STEP 5",6:"STEP 6",7:"STEP 7",8:"STEP 8",9:"STEP 9",10:"STEP 10",11:"STEP 11"}


def _num(v, default=None):
    try:
        x=float(v); return x if math.isfinite(x) else default
    except Exception: return default


def _plain(s):
    return " ".join(unescape(re.sub(r"<[^>]+>"," ",str(s or ""))).split())


def _segments(html):
    src=str(html or ""); up=src.upper(); pts=[]
    for step, marker in MARKERS.items():
        i=up.find(marker)
        if i>=0: pts.append((i,step))
    pts.sort(); out={}
    for n,(i,step) in enumerate(pts):
        j=pts[n+1][0] if n+1<len(pts) else len(src)
        out[step]=_plain(src[i:j])
    return out


def _find(pattern,text):
    m=re.search(pattern,str(text or ""),re.I)
    return _num(m.group(1)) if m else None


def _grade(step,result,text):
    u=str(text or "").upper(); r=result or {}
    if step==1: return "CONFIRMED" if r.get("lineup_confirmed") else "PROJECTED"
    if step==2:
        era=_find(r"\bERA\s*([0-9.]+)",text); whip=_find(r"\bWHIP\s*([0-9.]+)",text); kp=_find(r"\bK%\s*([0-9.]+)",text)
        if era is None and whip is None and kp is None: return "DATA LIMITED"
        if (era is not None and era<=3.35) or (whip is not None and whip<=1.12) or (kp is not None and kp>=27): return "TOUGH"
        if era is not None and era>=4.75 and (whip is None or whip>=1.30): return "FAVORABLE"
        return "NEUTRAL"
    if step==3:
        if "NO RECORDED MLB BVP" in u or "NO PRIOR BATTER" in u: return "NO HISTORY"
        avg=_find(r"\((\.\d{3})\)",text)
        return "DATA LIMITED" if avg is None else "FAVORABLE" if avg>=.300 else "TOUGH" if avg<=.220 else "NEUTRAL"
    if step==4:
        ba=_find(r"BATTER VS [RL]HP.*?AVG\s*([0-9.]+)",text); pa=_find(r"SP VS [RL]HB.*?AVG\s*([0-9.]+)",text)
        vals=[x-.250 for x in (ba,pa) if x is not None]
        if not vals: return "DATA LIMITED"
        edge=sum(vals)/len(vals); return "FAVORABLE" if edge>=.035 else "TOUGH" if edge<=-.035 else "BALANCED"
    if step==5:
        if "HITTER FRIENDLY" in u: return "HITTER FRIENDLY"
        if "PITCHER FRIENDLY" in u: return "PITCHER FRIENDLY"
        adj=_find(r"COMBINED\s*([+-]?[0-9.]+)%",text)
        return "DATA LIMITED" if adj is None else "HITTER FRIENDLY" if adj>=1.5 else "PITCHER FRIENDLY" if adj<=-1.5 else "NEAR NEUTRAL"
    if step==6:
        ab=_num(r.get("expected_ab")); spot=int(_num(r.get("position"),0) or 0)
        if ab is None: ab=_find(r"(?:DISPLAY PA EST\.|MODEL PROJECTED PA)\s*([0-9.]+)",text)
        if ab is None: return "DATA LIMITED"
        if r.get("lineup_confirmed") and 1<=spot<=5 and ab>=4: return "ELITE OPPORTUNITY"
        return "STRONG OPPORTUNITY" if ab>=4 else "MEDIUM OPPORTUNITY" if ab>=3.6 else "LIMITED OPPORTUNITY"
    if step==7:
        rates=[]
        for h,g in re.findall(r"1\+\s*HIT\s*(\d+)\s*/\s*(\d+)",u):
            if int(g)>0: rates.append(int(h)/int(g))
        if not rates: return "DATA LIMITED"
        x=sum(rates[:2])/min(2,len(rates)); return "ELITE RECENT FORM" if x>=.60 else "STRONG RECENT FORM" if x>=.50 else "COLD RECENT FORM" if x<=.30 else "MIXED RECENT FORM"
    if step==8:
        if "SUPPORTS HITTER" in u: return "WEAK"
        if "HURTS HITTER" in u: return "STRONG"
        return "DATA LIMITED" if "UNAVAILABLE" in u else "NEUTRAL"
    if step==9:
        if "SUPPORTS HITTER" in u: return "FAVORABLE"
        if "HURTS HITTER" in u or "VERY TOUGH" in u: return "TOUGH"
        return "DATA LIMITED" if "UNAVAILABLE" in u else "NEUTRAL"
    if step==10:
        if "DEEPER-START LEAN" in u or "LONG LEASH" in u: return "TOUGH"
        return "DATA LIMITED" if "UNAVAILABLE" in u else "NEUTRAL"
    if step==11:
        if "NOT POSTED" in u or "HAS NOT POSTED" in u: return "NOT YET PUBLISHED"
        if "PITCHER-LEAN" in u: return "TOUGH"
        if "HITTER-LEAN" in u: return "HITTER FRIENDLY"
        if "SAMPLE LIMITED" in u or "UNAVAILABLE" in u: return "DATA LIMITED"
        return "NEUTRAL"
    return "DATA LIMITED"


def _state(step,label):
    x=str(label or "").upper()
    if step==8: return "support" if x=="WEAK" else "concern" if x=="STRONG" else "na" if "LIMITED" in x else "neutral"
    if any(k in x for k in ("ELITE","STRONG OPPORTUNITY","FAVORABLE","HITTER FRIENDLY")): return "support"
    if any(k in x for k in ("TOUGH","PITCHER FRIENDLY","COLD","LIMITED OPPORTUNITY")): return "concern"
    if any(k in x for k in ("DATA LIMITED","NO HISTORY","NOT YET")): return "na"
    return "neutral"


def _pill_class(label):
    s=_state(0,label)
    if str(label).upper()=="CONFIRMED": return "good"
    if str(label).upper()=="PROJECTED": return "limited"
    return {"support":"good","concern":"bad","na":"limited"}.get(s,"neutral")


def _insert(html,marker,label):
    i=html.upper().find(marker.upper())
    if i<0: return html
    j=html.find("</div>",i)
    if j<0: return html
    pill=f'<span class="hit1316-grade {_pill_class(label)}">{escape(label)}</span>'
    return html[:j]+pill+html[j:]


def _summary(result,grades):
    sim=(result or {}).get("sim") or {}; p=_num(sim.get("p_one_plus"))
    model="na" if p is None else "support" if p>=.70 else "neutral" if p>=.60 else "concern"
    conf=str((result or {}).get("confidence") or "").upper(); dq="support" if conf in {"HIGH","MEDIUM-HIGH"} else "neutral" if conf=="MEDIUM" else "concern" if conf else "na"
    rows=[("Model",model,28),("Data quality",dq,12),("Opportunity",_state(6,grades.get(6)),14),("Recent form",_state(7,grades.get(7)),12),("Pitch/platoon",_state(4,grades.get(4)),10),("Environment",_state(5,grades.get(5)),6),("Opponent defense",_state(8,grades.get(8)),8),("Bullpen path",_state(9,grades.get(9)),5),("Starter exposure",_state(10,grades.get(10)),5),("Umpire tendency","na",0)]
    sc=[x for x in rows if x[2]>0]; avail=[x for x in sc if x[1]!="na"]; total=sum(x[2] for x in sc) or 1; aw=sum(x[2] for x in avail)
    vals={"support":1.0,"neutral":.55,"concern":.10}; coverage=aw/total if aw else 0; align=sum(w*vals.get(s,0) for _,s,w in avail)/aw if aw else 0; score=round(100*(.75*align+.25*coverage)) if aw else 0
    context=[x for x in rows if x[0] in {"Pitch/platoon","Environment","Opponent defense","Bullpen path","Starter exposure"} and x[1]!="na"]; net=sum(1 if s=="support" else -1 if s=="concern" else 0 for _,s,_ in context)
    matchup="DATA LIMITED" if len(context)<3 else "ELITE" if net>=4 else "STRONG" if net>=2 else "HARD" if net<=-2 else "MEDIUM"
    op=str(grades.get(6) or "DATA LIMITED").split()[0]; op=op if op in {"ELITE","STRONG","MEDIUM","LIMITED"} else "DATA LIMITED"
    confirmed=bool((result or {}).get("lineup_confirmed")); pick="ELITE" if p is not None and p>=.78 and score>=80 and conf=="HIGH" and confirmed else "STRONG" if p is not None and p>=.68 and score>=65 else "MEDIUM" if p is not None and p>=.60 else "LOW"
    groups={k:[n for n,s,_ in rows if s==k] for k in ("support","concern","neutral","na")}; join=lambda xs:" • ".join(xs) if xs else "None"; cls=lambda x:"strong" if x in {"ELITE","STRONG"} else "hard" if x in {"HARD","LOW"} else "limited" if "LIMITED" in x else "medium"
    return ('<div class="hit1316-final"><div class="hit1316-head"><span>FINAL • TOP-5 EVIDENCE SUMMARY</span><b>RANKING UNCHANGED</b></div><div class="hit1316-badges">'
        f'<span class="{cls(pick)}">PICK STRENGTH • {escape(pick)}</span><span class="{cls(matchup)}">MATCHUP • {escape(matchup)}</span><span class="{cls(op)}">OPPORTUNITY • {escape(op)}</span><span class="evidence">EVIDENCE • {score}/100</span></div>'
        f'<div class="hit1316-reasons"><div class="support"><strong>✅ Supports:</strong> {escape(join(groups["support"]))}</div><div class="concern"><strong>⚠️ Concerns:</strong> {escape(join(groups["concern"]))}</div></div>'
        f'<div class="hit1316-small"><strong>Neutral:</strong> {escape(join(groups["neutral"]))}</div><div class="hit1316-small"><strong>N/A / not scored:</strong> {escape(join(groups["na"]))}</div><div class="hit1316-coverage">Evidence coverage {len(avail)}/{len(sc)} weighted signals • {coverage*100:.0f}% weighted coverage</div><div class="hit1316-note">Audit synthesis only • does not change 1+ Hit probability, Monte Carlo, confidence, candidate pool, calibration or Top-5 order.</div></div>')


def _pick_html_v1316(result,rank):
    html=str(_BASE_PICK_HTML(result,rank) or ""); seg=_segments(html); grades={s:_grade(s,result,seg.get(s,"")) for s in MARKERS}; out=html
    for s,m in MARKERS.items(): out=_insert(out,m,grades[s])
    marker='<div class="hit-pick-prob">'
    return out.replace(marker,_summary(result,grades)+marker,1) if marker in out else out


active._pick_html=_pick_html_v1316

_CSS=r'''<style>
.hit1316-grade{float:right;margin:-2px 0 0 8px;padding:4px 7px;border-radius:999px;border:1px solid #756019;background:#392f0c;color:#f4d66d;font-size:.43rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase;white-space:nowrap}.hit1316-grade.good{border-color:#1f6b4f;background:#0a3326;color:#79edb7}.hit1316-grade.bad{border-color:#7b3c39;background:#361615;color:#ff9f9a}.hit1316-grade.limited{border-color:#465564;background:#16202a;color:#a8b4c0}
.hit1316-final{margin:8px 0 6px;padding:10px;border:1px solid #6b5b22;background:linear-gradient(145deg,#17140a,#08131d);border-radius:13px;box-shadow:inset 3px 0 #d6ab18}.hit1316-head{display:flex;justify-content:space-between;gap:8px}.hit1316-head span{font-size:.44rem;letter-spacing:.09em;color:#ffd86d;font-weight:1000}.hit1316-head b{font-size:.40rem;color:#9caec0}.hit1316-badges{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}.hit1316-badges span{border:1px solid #465564;background:#111d29;color:#cbd8e5;border-radius:999px;padding:5px 8px;font-size:.47rem;font-weight:950}.hit1316-badges .strong{border-color:#1f6b4f;background:#0a3326;color:#79edb7}.hit1316-badges .medium{border-color:#756019;background:#392f0c;color:#f4d66d}.hit1316-badges .hard{border-color:#7b3c39;background:#361615;color:#ff9f9a}.hit1316-badges .limited{background:#16202a;color:#a8b4c0}.hit1316-badges .evidence{border-color:#385b72;background:#0b1d29;color:#9edbff}.hit1316-reasons{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:8px}.hit1316-reasons>div{border-radius:10px;padding:8px 9px;font-size:.52rem;line-height:1.45;font-weight:800}.hit1316-reasons .support{border:1px solid #1c6449;background:#0a2a20;color:#8ce9bc}.hit1316-reasons .concern{border:1px solid #76581b;background:#30270d;color:#ffe087}.hit1316-small{font-size:.46rem;color:#98a8b7;margin-top:5px}.hit1316-coverage{font-size:.45rem;color:#88c4df;font-weight:850;margin-top:6px}.hit1316-note{font-size:.42rem;color:#7e8994;line-height:1.4;margin-top:5px}@media(max-width:700px){.hit1316-reasons{grid-template-columns:1fr}.hit1316-grade{float:none;display:inline-block;margin:5px 0 0 6px;font-size:.40rem}}
</style>'''
if "hit1316-final" not in core.HIT_CSS: core.HIT_CSS += _CSS


def render_hit_hub(games_df,section_header,status_info,team_logo,h):
    st.caption("🏆 Hit UI V13.16 • step grades + Final Top-5 Evidence Summary ACTIVE • presentation only • Hit Model V13 unchanged")
    return prior.render_hit_hub(games_df,section_header,status_info,team_logo,h)
