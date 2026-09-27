"""NFL Prop Analytics Page 3 Redesign Step 5 — premium results + chart.

Presentation-only visual layer for historical results, game-by-game chart,
supporting stats, and market/insight surfaces. Frozen values and behavior remain
owned by the certified Page 3 product.
"""
from __future__ import annotations
from typing import Any
import streamlit as st

MODEL_VERSION="NFL PROP ANALYTICS PAGE 3 REDESIGN STEP 5 • RESULTS + CHART V1"
PAGE3_REDESIGN_STEP=5
PAGE3_REDESIGN_STEP5_VERSION="v1"
PRESENTATION_ONLY=True
FROZEN_PAGE3_STEPS_1_TO_8_PROTECTED=True
FROZEN_FUN_POLISH_STEPS_1_TO_5_PROTECTED=True
FROZEN_REDESIGN_STEPS_1_TO_4_PROTECTED=True
INTERACTION_BEHAVIOR_CHANGED=False
DATA_OWNERSHIP_CHANGED=False
PROJECTION_LOGIC=False
PROBABILITY_LOGIC=False
RECOMMENDATION_LOGIC=False
SPORTSBOOK_PROJECTION_INFLUENCE=0.0
STAKE_SIZING_ENABLED=False
WAGER_ACTIONS=False
CERTIFIED_VIEWPORTS=(390,768,1440)

def render_redesign_step5_results_chart()->dict[str,Any]:
    st.markdown(f"""
<div class="ks-pa3-redesign-step5-marker"
 data-prop-page3-redesign-step5="{PAGE3_REDESIGN_STEP5_VERSION}"
 data-prop-page3-redesign-step5-state="ready"
 data-prop-page3-redesign-step5-presentation-only="true"
 data-prop-page3-redesign-step5-frozen-page3-steps="1-8"
 data-prop-page3-redesign-step5-frozen-fun-polish="1-5"
 data-prop-page3-redesign-step5-frozen-redesign="1-4"
 data-prop-page3-redesign-step5-interaction-change="false"
 data-prop-page3-redesign-step5-data-owner-change="false"
 data-prop-page3-redesign-step5-projection-weight="0.0"></div>
<style data-prop-page3-redesign-step5-css="{PAGE3_REDESIGN_STEP5_VERSION}">
.ks-pa3-redesign-step5-marker{{display:none!important}}
.ks-pa5-chart,.ks-pa6-support,.ks-pa7mi{{position:relative;overflow:hidden;border-color:rgba(125,211,252,.23)!important;background:radial-gradient(circle at 94% 2%,rgba(56,189,248,.09),transparent 18rem),linear-gradient(180deg,rgba(5,16,28,.98),rgba(2,9,17,.995))!important;box-shadow:0 20px 46px rgba(0,0,0,.20),inset 0 1px 0 rgba(255,255,255,.03)!important}}
.ks-pa5-chart::before,.ks-pa6-support::before,.ks-pa7mi::before{{content:"";position:absolute;left:15px;right:15px;top:0;height:2px;background:linear-gradient(90deg,transparent,#38bdf8,rgba(125,211,252,.25),transparent)}}
.ks-pa5-head,.ks-pa6-head,.ks-pa7mi-head{{padding-bottom:10px!important;border-bottom:1px solid rgba(125,211,252,.08)!important}}
.ks-pa5-head span,.ks-pa6-head span,.ks-pa7mi-head span{{color:#76d8ff!important;letter-spacing:.13em!important}}
.ks-pa5-head strong,.ks-pa6-head strong,.ks-pa7mi-head strong{{font-size:.92rem!important;letter-spacing:-.01em!important}}
.ks-pa5-legend{{gap:7px!important;flex-wrap:wrap!important}}
.ks-pa5-legend span{{padding:5px 8px!important;border:1px solid rgba(125,211,252,.10);border-radius:999px;background:rgba(15,23,42,.38);color:#8ca2b8!important}}
.ks-pa5-scroll{{margin-top:8px;padding:10px 8px 5px!important;border:1px solid rgba(125,211,252,.08);border-radius:14px;background:repeating-linear-gradient(0deg,rgba(125,211,252,.025) 0 1px,transparent 1px 32px),linear-gradient(180deg,rgba(3,12,22,.65),rgba(3,9,17,.36))}}
.ks-pa5-plot{{border-radius:12px!important}}
.ks-pa5-bar{{border-radius:7px 7px 3px 3px!important;box-shadow:0 8px 18px rgba(0,0,0,.18)}}
.ks-pa5-over{{box-shadow:0 0 16px rgba(56,189,248,.20)!important}}
.ks-pa5-line span{{padding:3px 6px!important;border-radius:999px!important;background:rgba(248,250,252,.06)!important;border:1px solid rgba(248,250,252,.10)!important}}
.ks-pa5-game{{padding-inline:2px}}
.ks-pa5-value{{color:#dcecff!important;font-size:.56rem!important}}
.ks-pa5-opp{{color:#dff4ff!important}}
.ks-pa5-foot{{padding-top:8px!important;border-top:1px solid rgba(125,211,252,.06)!important}}

.ks-pa6-grid{{gap:9px!important}}
.ks-pa6-grid article{{position:relative;overflow:hidden;min-height:92px;padding:13px 12px!important;border-radius:14px!important;border-color:rgba(125,211,252,.11)!important;background:radial-gradient(circle at 90% 10%,rgba(56,189,248,.06),transparent 45%),linear-gradient(180deg,rgba(13,27,44,.70),rgba(7,16,28,.88))!important}}
.ks-pa6-grid article::before{{content:"";position:absolute;left:0;top:13px;bottom:13px;width:2px;border-radius:999px;background:linear-gradient(180deg,#38bdf8,rgba(56,189,248,.06))}}
.ks-pa6-grid article strong{{font-size:1.34rem!important;letter-spacing:-.025em}}
.ks-pa6-grid article span{{color:#8196ad!important}}
.ks-pa6-note{{margin-top:11px!important;padding:8px 9px!important;border:1px solid rgba(148,163,184,.07);border-radius:9px;background:rgba(15,23,42,.22)}}

.ks-pa7mi-selected,.ks-pa7mi-market,.ks-pa7mi-grid,.ks-pa7mi-insights{{gap:9px!important}}
.ks-pa7mi-selected>div,.ks-pa7mi-market>div,.ks-pa7mi-grid article,.ks-pa7mi-insights article{{position:relative;overflow:hidden;border-radius:13px!important;border-color:rgba(125,211,252,.11)!important;background:linear-gradient(180deg,rgba(10,25,41,.76),rgba(5,15,26,.90))!important}}
.ks-pa7mi-selected>div::before,.ks-pa7mi-market>div::before,.ks-pa7mi-grid article::before,.ks-pa7mi-insights article::before{{content:"";position:absolute;left:0;top:10px;bottom:10px;width:2px;border-radius:999px;background:linear-gradient(180deg,#38bdf8,transparent)}}
.ks-pa7mi-section{{margin-top:13px!important;padding-top:11px!important}}
.ks-pa7mi-insights article{{padding:12px!important}}
.ks-pa7mi-insights strong{{font-size:.84rem!important;color:#e9f9ff!important}}
.ks-pa7mi-notes p{{border-color:rgba(125,211,252,.08)!important;background:rgba(7,17,29,.45)!important}}
.ks-pa7mi-foot{{padding-top:9px;border-top:1px solid rgba(125,211,252,.06)}}

@media(hover:hover){{.ks-pa6-grid article,.ks-pa7mi-grid article,.ks-pa7mi-insights article{{transition:transform .14s ease,border-color .16s ease}}.ks-pa6-grid article:hover,.ks-pa7mi-grid article:hover,.ks-pa7mi-insights article:hover{{transform:translateY(-2px);border-color:rgba(125,211,252,.24)!important}}}}
@media(max-width:560px){{.ks-pa5-chart,.ks-pa6-support,.ks-pa7mi{{border-radius:15px!important}}.ks-pa5-scroll{{padding:8px 5px 4px!important}}.ks-pa6-grid{{grid-template-columns:repeat(2,minmax(0,1fr))!important}}.ks-pa7mi-selected,.ks-pa7mi-market,.ks-pa7mi-grid{{grid-template-columns:repeat(2,minmax(0,1fr))!important}}}}
@media(prefers-reduced-motion:reduce){{.ks-pa6-grid article,.ks-pa7mi-grid article,.ks-pa7mi-insights article{{transition:none!important;transform:none!important}}}}
</style>
""",unsafe_allow_html=True)
    return {"ready":True,"state":"ready","version":PAGE3_REDESIGN_STEP5_VERSION,"presentation_only":True,"frozen_page3_steps_1_to_8":True,"frozen_fun_polish_steps_1_to_5":True,"frozen_redesign_steps_1_to_4":True,"interaction_behavior_changed":False,"data_ownership_changed":False,"certified_viewports":CERTIFIED_VIEWPORTS,"projection_weight":0.0}
