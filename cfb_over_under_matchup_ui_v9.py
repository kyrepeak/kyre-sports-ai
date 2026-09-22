"""CFB Over/Under Intelligence V2 — Upgrade Step 9 environment UI.

Additive wrapper over permanently frozen Upgrade Step 8.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import streamlit as st

import cfb_over_under_environment_engine_v1 as environment_engine
import cfb_over_under_matchup_ui_v8 as frozen_v8
import cfb_over_under_slate_v8 as upgraded_slate

MODEL_VERSION = "CFB OVER/UNDER INTELLIGENCE V2 • UPGRADE STEP 9 ENVIRONMENT"
FROZEN_UPGRADE = "cfb_over_under_matchup_ui_v8"
MARKET = "Over/Under"

_FROZEN_STEP8_HERO = frozen_v8._hero_v8
_FROZEN_STEP8_MODEL_CARD = frozen_v8._model_card_v8
_FROZEN_STEP8_COMPONENTS_PANEL = frozen_v8._components_panel_v8
_FROZEN_STEP8_FINAL_CARD = frozen_v8._final_card_v8

_CSS=r"""
<style>
.cfbou9{margin:10px 0 2px;border:1px solid rgba(93,200,255,.34);border-radius:18px;background:linear-gradient(145deg,#071623,#0b1620 58%,#0b1518);overflow:hidden}
.cfbou9-head{display:flex;justify-content:space-between;gap:8px;align-items:center;padding:10px 12px;border-bottom:1px solid rgba(93,200,255,.15)}
.cfbou9-head b{color:#9bdcff;font-size:.54rem;font-weight:950;letter-spacing:.08em}.cfbou9-head span{border:1px solid #285d78;border-radius:999px;padding:4px 7px;background:#0b2432;color:#b8e6ff;font-size:.39rem;font-weight:950}
.cfbou9-sub{padding:7px 12px;color:#87959d;font-size:.42rem;line-height:1.5;border-bottom:1px solid rgba(93,200,255,.08)}
.cfbou9-grid{display:grid;grid-template-columns:1.1fr .9fr;gap:8px;padding:10px}.cfbou9-card{border:1px solid rgba(93,200,255,.14);border-radius:13px;background:#091720;padding:9px}
.cfbou9-card b{display:block;color:#f4f9fb;font-size:.62rem}.cfbou9-card small{display:block;color:#738792;font-size:.34rem;margin-top:3px;line-height:1.45}
.cfbou9-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:8px}.cfbou9-m{border:1px solid rgba(93,200,255,.10);border-radius:9px;background:#07131b;padding:7px}
.cfbou9-m strong{display:block;color:#b8e6ff;font-size:.62rem}.cfbou9-m span{display:block;color:#6e818b;font-size:.30rem;text-transform:uppercase;margin-top:3px}
.cfbou9-rosters{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:8px}.cfbou9-r{border:1px solid rgba(93,200,255,.10);border-radius:9px;background:#07131b;padding:8px}
.cfbou9-r strong{display:block;color:#eef7fa;font-size:.52rem}.cfbou9-r span{display:block;color:#72858e;font-size:.32rem;line-height:1.45;margin-top:4px}
.cfbou9-warn{margin-top:8px;border:1px solid #6c5720;border-radius:9px;background:#2b240d;color:#d9c477;padding:8px;font-size:.37rem;line-height:1.45}
.cfbou9-foot{padding:8px 11px;border-top:1px solid rgba(93,200,255,.08);color:#70838c;font-size:.37rem;line-height:1.48}
.cfbou9-gate{margin:10px;border:1px solid #6c5720;border-radius:10px;background:#2b240d;color:#d9c477;padding:9px;font-size:.43rem;line-height:1.45}
.cfbou9-model{margin-top:10px;border:1px solid rgba(93,200,255,.24);border-radius:16px;background:linear-gradient(145deg,#071623,#071924,#101611);overflow:hidden}
.cfbou9-model-head{display:flex;justify-content:space-between;gap:8px;padding:10px 11px;border-bottom:1px solid rgba(93,200,255,.12)}
.cfbou9-model-head b{color:#9bdcff;font-size:.52rem;font-weight:950}.cfbou9-model-head span{color:#779bac;font-size:.38rem;font-weight:900}
.cfbou9-model-main{display:grid;grid-template-columns:1.2fr 1fr;gap:8px;padding:10px}.cfbou9-total,.cfbou9-prob{border:1px solid rgba(93,200,255,.12);border-radius:11px;background:#11140f;padding:9px}
.cfbou9-total small,.cfbou9-prob small{display:block;color:#847675;font-size:.35rem;text-transform:uppercase}.cfbou9-total strong{display:block;color:#fff7f7;font-size:1.35rem;margin-top:3px}.cfbou9-total b,.cfbou9-prob b{display:block;color:#b69595;font-size:.42rem;margin-top:4px}.cfbou9-prob strong{display:block;color:#f7e8e8;font-size:.70rem;margin-top:5px}
.cfbou9-model-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;padding:0 10px 10px}.cfbou9-audit{margin-top:8px;border:1px solid rgba(93,200,255,.17);border-radius:12px;background:#10141a;padding:9px}
.cfbou9-audit b{color:#9bdcff;font-size:.46rem}.cfbou9-audit span{display:block;color:#7d858b;font-size:.37rem;line-height:1.45;margin-top:4px}
@media(max-width:760px){.cfbou9-grid{grid-template-columns:1fr}.cfbou9-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.cfbou9-rosters{grid-template-columns:1fr}.cfbou9-model-main{grid-template-columns:1fr}.cfbou9-model-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""


def _clean(v:Any)->str:return str(v or "").strip()
def _num(v:Any,d:int=1)->str:
    try:return f"{float(v):.{d}f}"
    except Exception:return "—"
def _pct(v:Any)->str:
    try:return f"{100*float(v):.1f}%"
    except Exception:return "—"


def _roster(side:Mapping[str,Any],label:str)->str:
    if not side.get("ready"):
        return f'<div class="cfbou9-r"><strong>{escape(label)}</strong><span>Roster audit unavailable.</span></div>'
    return f'''<div class="cfbou9-r"><strong>{escape(label)}</strong><span>{int(side.get("roster_total") or 0)} rostered • {int(side.get("flagged_count") or 0)} reported flags<br>Snapshot {escape(_clean(side.get("timestamp")) or "timestamp unavailable")}</span></div>'''


def _environment_panel(game:Mapping[str,Any],away:Mapping[str,Any],home:Mapping[str,Any])->str:
    e=environment_engine.build_environment_engine(game,away,home)
    if not e.get("model_ready"):
        return f'''<div class="cfbou9"><div class="cfbou9-head"><b>🟦 UPGRADE STEP 9 • GAME-DAY ENVIRONMENT + AVAILABILITY AUDIT</b><span>ENVIRONMENT GATED</span></div><div class="cfbou9-gate">{escape(_clean(e.get("reason")) or "Verified exact-event environment evidence is incomplete")}. Step 8 remains active.</div></div>'''
    w=e.get("weather") or {}; v=e.get("venue") or {}; s=e.get("weather_stress") or {}
    return f'''
<div class="cfbou9">
 <div class="cfbou9-head"><b>🟦 UPGRADE STEP 9 • GAME-DAY ENVIRONMENT + AVAILABILITY AUDIT</b><span>ESPN EVENT {escape(_clean(e.get("event_id")))}</span></div>
 <div class="cfbou9-sub">Exact same-date event identity unlocks venue, game-time weather, and timestamped roster auditing. Weather may widen uncertainty, but Step-8 projected points remain untouched.</div>
 <div class="cfbou9-grid">
  <div class="cfbou9-card"><b>🌦️ {escape(_clean(v.get("name")) or "Venue unavailable")}</b><small>{escape(", ".join(x for x in (_clean(v.get("city")),_clean(v.get("state"))) if x))} • {"Indoor" if v.get("indoor") else "Outdoor / not marked indoor"}</small>
   <div class="cfbou9-metrics">
    <div class="cfbou9-m"><strong>{_num(w.get("temperature_f"),0)}°F</strong><span>Temperature</span></div>
    <div class="cfbou9-m"><strong>{_num(w.get("gust_mph"),0)} mph</strong><span>Gust</span></div>
    <div class="cfbou9-m"><strong>{_num(w.get("precipitation_pct"),0)}%</strong><span>Precip chance</span></div>
    <div class="cfbou9-m"><strong>+{_num(e.get("sigma_adjustment"),2)}</strong><span>Sigma adj</span></div>
   </div>
  </div>
  <div class="cfbou9-card"><b>🩺 Availability audit</b><small>Roster schema is monitored, but injury-report completeness is not certified; injury model weight is 0%.</small>
   <div class="cfbou9-rosters">{_roster(e.get("away_availability") or {},_clean(away.get("team")) or "Away")}{_roster(e.get("home_availability") or {},_clean(home.get("team")) or "Home")}</div>
   <div class="cfbou9-warn">Zero reported flags ≠ confirmed healthy roster. We refuse to manufacture an injury advantage from an incomplete college-football feed.</div>
  </div>
 </div>
 <div class="cfbou9-foot">Weather stress: gust 55% • precipitation 30% • temperature 15%. Stress begins above 15 mph gusts, above 50% precipitation, below 35°F, or above 95°F. These are conservative structural thresholds, not empirical calibration.</div>
</div>'''


def _hero_v9(game,away,home): return _FROZEN_STEP8_HERO(game,away,home)+_environment_panel(game,away,home)


def _model_card_v9(game,away,home,output):
    if not output.get("ready"): return _FROZEN_STEP8_MODEL_CARD(game,away,home,output)
    base_total=output.get("step9_base_projected_total",output.get("projected_total"))
    base_sigma=output.get("step9_base_structural_total_sigma",output.get("structural_total_sigma"))
    c=output.get("components") or {}
    return f'''<div class="cfbou9-model">
<div class="cfbou9-model-head"><b>STEP 9 • ENVIRONMENT-ADJUSTED UNCERTAINTY</b><span>{"ENVIRONMENT APPLIED" if output.get("upgrade_step9_applied") else "STEP 8 FALLBACK"} • TOTAL WEIGHT 0%</span></div>
<div class="cfbou9-model-main"><div class="cfbou9-total"><small>Projected game total</small><strong>{_num(output.get("projected_total"),1)}</strong><b>Step 8 {_num(base_total,1)} → Step 9 {_num(output.get("projected_total"),1)} • unchanged</b></div>
<div class="cfbou9-prob"><small>Structural uncertainty</small><strong>σ {_num(base_sigma,2)} → {_num(output.get("structural_total_sigma"),2)}</strong><b>OVER {_pct(output.get("over_probability"))} • UNDER {_pct(output.get("under_probability"))}</b></div></div>
<div class="cfbou9-model-grid">
<div class="cfbou9-m"><strong>{_num(c.get("step9_environment_sigma_adjustment"),2)}</strong><span>Weather sigma adj</span></div>
<div class="cfbou9-m"><strong>{_pct(c.get("step9_weather_stress"))}</strong><span>Weather stress</span></div>
<div class="cfbou9-m"><strong>{_pct(output.get("environment_engine_coverage"))}</strong><span>Environment coverage</span></div>
<div class="cfbou9-m"><strong>{_pct(output.get("roster_audit_coverage"))}</strong><span>Roster audit coverage</span></div>
<div class="cfbou9-m"><strong>0.00</strong><span>Total points adj</span></div>
<div class="cfbou9-m"><strong>0%</strong><span>Injury model weight</span></div>
<div class="cfbou9-m"><strong>0%</strong><span>Analysis-line weight</span></div>
<div class="cfbou9-m"><strong>{_pct(output.get("reliability"))}</strong><span>Frozen reliability</span></div>
</div></div>'''


def _components_panel_v9(output):
    frozen=_FROZEN_STEP8_COMPONENTS_PANEL(output)
    if not output.get("ready"): return frozen
    c=output.get("components") or {}
    return frozen+f'''<div class="cfbou9-audit"><b>🟦 STEP 9 ENVIRONMENT AUDIT</b><span>Weather sigma adjustment {_num(c.get("step9_environment_sigma_adjustment"),2)} • environment coverage {_pct(c.get("step9_environment_coverage"))} • roster audit coverage {_pct(c.get("step9_roster_audit_coverage"))} • projected-total adjustment {_num(c.get("step9_projected_total_adjustment"),2)} • injury adjustment {_num(c.get("step9_injury_points_adjustment"),2)}.</span></div>'''


def _final_card_v9(game,final):
    html=_FROZEN_STEP8_FINAL_CARD(game,final)
    html=html.replace("STEP 9 FINAL RULES • STEP 8 TURNOVER-VOLATILITY-ADJUSTED UNCERTAINTY","STEP 9 FINAL RULES • UPGRADE STEP 9 ENVIRONMENT-ADJUSTED UNCERTAINTY")
    return html


def _clear_stale_scan_state():
    marker="cfb_ou_upgrade_step9_scan_state_reset"
    if st.session_state.get(marker): return
    for key in list(st.session_state.keys()):
        if str(key).startswith("cfb_step9_top5_") or str(key).startswith("cfb_step9_scan_diag_"):
            try: del st.session_state[key]
            except Exception: pass
    st.session_state[marker]=True


def render_over_under_hub(section_header=None,status_info=None,team_logo=None,h=None):
    st.caption("🟦 CFB O/U INTELLIGENCE V2 • Upgrade Step 9 • game-day environment ACTIVE")
    st.markdown(_CSS,unsafe_allow_html=True); _clear_stale_scan_state()
    originals=(frozen_v8._hero_v8,frozen_v8.upgraded_slate,frozen_v8._model_card_v8,frozen_v8._components_panel_v8,frozen_v8._final_card_v8)
    frozen_v8._hero_v8=_hero_v9; frozen_v8.upgraded_slate=upgraded_slate; frozen_v8._model_card_v8=_model_card_v9; frozen_v8._components_panel_v8=_components_panel_v9; frozen_v8._final_card_v8=_final_card_v9
    try:return frozen_v8.render_over_under_hub(section_header,status_info,team_logo,h)
    finally:
        frozen_v8._hero_v8,frozen_v8.upgraded_slate,frozen_v8._model_card_v8,frozen_v8._components_panel_v8,frozen_v8._final_card_v8=originals


def render_cfb_hub(market,section_header=None,status_info=None,team_logo=None,h=None):
    if market!=MARKET: raise ValueError(f"Upgrade Step 9 Over/Under UI received unsupported market: {market}")
    return render_over_under_hub(section_header,status_info,team_logo,h)


__all__=["FROZEN_UPGRADE","MARKET","MODEL_VERSION","_components_panel_v9","_environment_panel","_final_card_v9","_hero_v9","_model_card_v9","render_cfb_hub","render_over_under_hub"]
