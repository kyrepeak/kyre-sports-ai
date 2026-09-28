"""NFL Prop Analytics Page 3 Visual Composition V2 Step 4 — Analysis Settings.

Presentation-only composition for the approved Analysis Settings deck. The
frozen Page 3 owner continues to own the real Streamlit segmented controls,
their widget keys, query semantics, selected values, and downstream behavior.
"""
from __future__ import annotations

import html as html_lib
from typing import Any

import streamlit as st

MODEL_VERSION = "NFL PROP ANALYTICS PAGE 3 VISUAL COMPOSITION V2 • STEP 4 ANALYSIS SETTINGS V1"
VISUAL_SERIES = "v2"
VISUAL_STEP = 4
VISUAL_VERSION = "v1"
PRESENTATION_ONLY = True
REAL_COMPOSITION_REBUILD = True
FROZEN_STEP2_HERO_PROTECTED = True
FROZEN_STEP3_RIBBON_PROTECTED = True
FROZEN_WIDGET_KEYS_PROTECTED = True
DATA_OWNERSHIP_CHANGED = False
INTERACTION_BEHAVIOR_CHANGED = False
QUERY_SEMANTICS_CHANGED = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MIN_TOUCH_TARGET_PX = 44
CERTIFIED_VIEWPORTS = (390, 768, 1440)
CONTAINER_KEY = "nfl_prop_visual_v2_step4_analysis_settings_v1"


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def render_visual_v2_analysis_settings_header(
    *,
    history_label: Any,
    market_label: Any,
    target: Any | None = None,
) -> dict[str, Any]:
    """Render only the V2 deck header/marker/styles into the supplied container."""
    history = _text(history_label) or "L10"
    market = _text(market_label) or "Selected market"

    html = f"""
<div class="ks-v2-analysis-settings-head"
 data-page3-visual-v2-step4="{VISUAL_VERSION}"
 data-page3-visual-v2-step4-state="ready"
 data-page3-visual-v2-step4-real-composition="true"
 data-page3-visual-v2-step4-presentation-only="true"
 data-page3-visual-v2-step4-interaction-change="false"
 data-page3-visual-v2-step4-query-change="false"
 data-page3-visual-v2-step4-min-touch-target="{MIN_TOUCH_TARGET_PX}"
 data-page3-visual-v2-step4-history="{html_lib.escape(history)}"
 data-page3-visual-v2-step4-market="{html_lib.escape(market)}">
  <div>
    <span>ANALYSIS SETTINGS</span>
    <strong>Historical context &amp; prop category</strong>
    <small>Live controls • existing behavior preserved</small>
  </div>
  <div class="ks-v2-analysis-line-cue" aria-label="Manual Line Lab is directly below Analysis Settings">
    <span>MANUAL LINE LAB</span>
    <strong>BELOW ↓</strong>
  </div>
</div>

<style data-page3-visual-v2-step4-css="{VISUAL_VERSION}">
/* Retire only the older Analysis Settings presentation when V2 Step 4 exists. */
[data-testid="stMainBlockContainer"]:has([data-page3-visual-v2-step4="{VISUAL_VERSION}"])
  .ks-pa3-nav-marker{{
  display:none!important;
}}

/* One parent deck containing the two real Streamlit control cards. */
.st-key-{CONTAINER_KEY}{{
  position:relative;
  width:100%;max-width:100%;min-width:0;
  margin:0 0 14px!important;
  padding:14px!important;
  border:1px solid rgba(125,211,252,.42)!important;
  border-radius:14px!important;
  background:
    radial-gradient(circle at 93% 0%,rgba(14,165,233,.14),transparent 18rem),
    linear-gradient(145deg,rgba(6,18,31,.99),rgba(3,11,20,.99))!important;
  box-shadow:
    0 16px 40px rgba(0,0,0,.24),
    inset 0 1px 0 rgba(255,255,255,.035),
    0 0 0 1px rgba(56,189,248,.04)!important;
  overflow:visible!important;
}}

.ks-v2-analysis-settings-head{{
  display:flex;align-items:center;justify-content:space-between;gap:16px;
  min-width:0;margin:0 0 11px;padding:0 1px 10px;
  border-bottom:1px solid rgba(148,163,184,.13);
}}
.ks-v2-analysis-settings-head>div:first-child{{
  min-width:0;display:flex;flex-direction:column;gap:2px;
}}
.ks-v2-analysis-settings-head>div:first-child>span{{
  color:#7dd3fc;font-size:.58rem;font-weight:950;letter-spacing:.13em;
}}
.ks-v2-analysis-settings-head>div:first-child>strong{{
  color:#f3f9ff;font-size:.96rem;line-height:1.12;letter-spacing:-.015em;
}}
.ks-v2-analysis-settings-head>div:first-child>small{{
  color:#71879c;font-size:.53rem;font-weight:750;letter-spacing:.02em;
}}

.ks-v2-analysis-line-cue{{
  flex:0 0 auto;min-height:34px;
  display:flex;align-items:center;gap:7px;
  padding:7px 10px;
  border:1px solid rgba(56,189,248,.34);border-radius:999px;
  background:rgba(14,165,233,.08);
  box-shadow:inset 0 1px 0 rgba(255,255,255,.035);
}}
.ks-v2-analysis-line-cue span{{
  color:#8fa9bf;font-size:.49rem;font-weight:900;letter-spacing:.075em;
}}
.ks-v2-analysis-line-cue strong{{
  color:#bcecff;font-size:.53rem;font-weight:950;letter-spacing:.055em;
}}

/* The existing controls remain real; only their composition changes. */
.st-key-{CONTAINER_KEY} [data-testid="stHorizontalBlock"]{{
  gap:10px!important;
  align-items:stretch!important;
}}
.st-key-{CONTAINER_KEY} [data-testid="stSegmentedControl"]{{
  min-width:0!important;
  margin:0!important;
  padding:10px 11px 11px!important;
  border:1px solid rgba(125,211,252,.18)!important;
  border-radius:12px!important;
  background:
    linear-gradient(180deg,rgba(8,24,40,.92),rgba(4,14,25,.97))!important;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.025)!important;
}}
.st-key-{CONTAINER_KEY} [data-testid="stSegmentedControl"] label{{
  color:#d8edf9!important;
  font-size:.61rem!important;
  font-weight:900!important;
  letter-spacing:.055em!important;
  text-transform:uppercase!important;
}}
.st-key-{CONTAINER_KEY} [data-testid="stSegmentedControl"] [role="radiogroup"]{{
  display:flex!important;
  width:100%!important;
  gap:5px!important;
}}
.st-key-{CONTAINER_KEY} [data-testid="stSegmentedControl"] button{{
  min-height:{MIN_TOUCH_TARGET_PX}px!important;
  flex:1 1 0!important;
  min-width:0!important;
  padding:.42rem .46rem!important;
  border:1px solid rgba(125,211,252,.17)!important;
  border-radius:9px!important;
  background:rgba(2,10,18,.76)!important;
  color:#8fa8bd!important;
  font-size:.56rem!important;
  font-weight:900!important;
  letter-spacing:.025em!important;
  transition:
    border-color .15s ease,
    background-color .15s ease,
    box-shadow .15s ease,
    color .15s ease,
    transform .12s ease!important;
}}
.st-key-{CONTAINER_KEY} [data-testid="stSegmentedControl"] button[aria-pressed="true"],
.st-key-{CONTAINER_KEY} [data-testid="stSegmentedControl"] button[aria-selected="true"]{{
  color:#e8fbff!important;
  border-color:rgba(125,211,252,.9)!important;
  background:
    linear-gradient(180deg,rgba(14,165,233,.34),rgba(2,132,199,.18))!important;
  box-shadow:
    inset 0 0 0 1px rgba(186,230,253,.18),
    0 0 16px rgba(14,165,233,.24)!important;
}}
.st-key-{CONTAINER_KEY} [data-testid="stSegmentedControl"] button:focus-visible{{
  outline:2px solid rgba(125,211,252,.95)!important;
  outline-offset:2px!important;
  box-shadow:0 0 0 4px rgba(56,189,248,.15)!important;
}}

@media(hover:hover){{
  .st-key-{CONTAINER_KEY} [data-testid="stSegmentedControl"] button:hover{{
    color:#d8f4ff!important;
    border-color:rgba(125,211,252,.5)!important;
    transform:translateY(-1px);
  }}
}}

@media(max-width:700px){{
  .ks-v2-analysis-settings-head{{
    align-items:flex-start;gap:10px;
  }}
  .ks-v2-analysis-line-cue{{
    min-height:32px;padding:6px 8px;
  }}
  .st-key-{CONTAINER_KEY} [data-testid="stHorizontalBlock"]{{
    flex-direction:column!important;
    gap:8px!important;
  }}
  .st-key-{CONTAINER_KEY} [data-testid="stSegmentedControl"] [role="radiogroup"]{{
    overflow-x:auto!important;
    justify-content:flex-start!important;
    scrollbar-width:thin;
  }}
  .st-key-{CONTAINER_KEY} [data-testid="stSegmentedControl"] button{{
    flex:0 0 auto!important;
    min-width:58px!important;
    min-height:46px!important;
  }}
}}

@media(max-width:430px){{
  .st-key-{CONTAINER_KEY}{{padding:11px!important}}
  .ks-v2-analysis-settings-head{{
    flex-direction:column;
  }}
  .ks-v2-analysis-line-cue{{
    align-self:flex-start;
  }}
}}

@media(prefers-reduced-motion:reduce){{
  .st-key-{CONTAINER_KEY} *{{
    transition:none!important;
    animation:none!important;
  }}
}}
</style>
"""
    sink = target if target is not None else st
    sink.markdown(html, unsafe_allow_html=True)

    return {
        "ready": True,
        "state": "ready",
        "version": VISUAL_VERSION,
        "real_composition_rebuild": True,
        "presentation_only": True,
        "history_label": history,
        "market_label": market,
        "container_key": CONTAINER_KEY,
        "minimum_touch_target_px": MIN_TOUCH_TARGET_PX,
        "certified_viewports": CERTIFIED_VIEWPORTS,
        "data_ownership_changed": False,
        "interaction_behavior_changed": False,
        "query_semantics_changed": False,
        "projection_weight": 0.0,
    }


__all__ = [
    "CERTIFIED_VIEWPORTS",
    "CONTAINER_KEY",
    "DATA_OWNERSHIP_CHANGED",
    "FROZEN_STEP2_HERO_PROTECTED",
    "FROZEN_STEP3_RIBBON_PROTECTED",
    "FROZEN_WIDGET_KEYS_PROTECTED",
    "INTERACTION_BEHAVIOR_CHANGED",
    "MIN_TOUCH_TARGET_PX",
    "MODEL_VERSION",
    "PRESENTATION_ONLY",
    "QUERY_SEMANTICS_CHANGED",
    "REAL_COMPOSITION_REBUILD",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "VISUAL_SERIES",
    "VISUAL_STEP",
    "VISUAL_VERSION",
    "render_visual_v2_analysis_settings_header",
]
