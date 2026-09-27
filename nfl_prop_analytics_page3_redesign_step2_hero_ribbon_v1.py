"""NFL Prop Analytics Page 3 Redesign Step 2 — premium hero + quick-stat ribbon.

Presentation-only visual upgrade layered after frozen Redesign Step 1. This file
styles the existing frozen hero and verified historical-stat surfaces; it does
not own player identity, team logos, history values, controls, navigation,
markets, projections, or any sports-analysis behavior.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

MODEL_VERSION = "NFL PROP ANALYTICS PAGE 3 REDESIGN STEP 2 • HERO + QUICK STATS V1"
PAGE3_REDESIGN_STEP = 2
PAGE3_REDESIGN_STEP2_VERSION = "v1"
PRESENTATION_ONLY = True
FROZEN_PAGE3_STEPS_1_TO_8_PROTECTED = True
FROZEN_FUN_POLISH_STEPS_1_TO_5_PROTECTED = True
FROZEN_REDESIGN_STEP1_PROTECTED = True
INTERACTION_BEHAVIOR_CHANGED = False
DATA_OWNERSHIP_CHANGED = False
PROJECTION_LOGIC = False
PROBABILITY_LOGIC = False
RECOMMENDATION_LOGIC = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS = False
CERTIFIED_VIEWPORTS = (390, 768, 1440)


def render_redesign_step2_hero_ribbon() -> dict[str, Any]:
    """Upgrade the frozen hero and stat strip without changing their data."""
    st.markdown(
        f"""
<div class="ks-pa3-redesign-step2-marker"
     data-prop-page3-redesign-step2="{PAGE3_REDESIGN_STEP2_VERSION}"
     data-prop-page3-redesign-step2-state="ready"
     data-prop-page3-redesign-step2-presentation-only="true"
     data-prop-page3-redesign-step2-frozen-page3-steps="1-8"
     data-prop-page3-redesign-step2-frozen-fun-polish="1-5"
     data-prop-page3-redesign-step2-frozen-redesign-step1="true"
     data-prop-page3-redesign-step2-interaction-change="false"
     data-prop-page3-redesign-step2-data-owner-change="false"
     data-prop-page3-redesign-step2-projection-weight="0.0"></div>

<style data-prop-page3-redesign-step2-css="{PAGE3_REDESIGN_STEP2_VERSION}">
.ks-pa3-redesign-step2-marker{{display:none!important}}

/* ================================================================
   HERO — stronger matchup identity, same frozen content/semantics.
   ================================================================ */
.ks-pa3-hero{{
  --ks-r2-cyan:#38bdf8;
  --ks-r2-ice:#7dd3fc;
  --ks-r2-deep:#020711;
  isolation:isolate;
  border:1px solid rgba(125,211,252,.28)!important;
  border-radius:20px!important;
  padding:20px 18px 16px!important;
  background:
    linear-gradient(105deg,
      color-mix(in srgb,var(--ks-pa3-team-accent,#38bdf8) 18%,transparent) 0%,
      rgba(2,8,18,.88) 28%,
      rgba(2,8,18,.96) 51%,
      rgba(2,8,18,.90) 72%,
      color-mix(in srgb,var(--ks-pa3-opp-accent,#7dd3fc) 16%,transparent) 100%),
    radial-gradient(circle at 50% -10%,rgba(56,189,248,.20),transparent 42%),
    #020812!important;
  box-shadow:
    0 24px 60px rgba(0,0,0,.34),
    0 0 0 1px rgba(56,189,248,.035),
    inset 0 1px 0 rgba(255,255,255,.055)!important;
}}

.ks-pa3-hero::before{{
  content:"";
  position:absolute;
  z-index:3;
  left:18px;
  right:18px;
  top:0;
  height:3px;
  border-radius:0 0 999px 999px;
  background:
    linear-gradient(90deg,
      var(--ks-pa3-team-accent,#38bdf8) 0 30%,
      #38bdf8 46% 54%,
      var(--ks-pa3-opp-accent,#7dd3fc) 70% 100%);
  box-shadow:0 0 22px rgba(56,189,248,.40);
}}

.ks-pa3-hero::after{{
  content:"";
  position:absolute;
  z-index:-1;
  inset:0;
  pointer-events:none;
  background:
    radial-gradient(circle at 13% 52%,color-mix(in srgb,var(--ks-pa3-team-accent,#38bdf8) 10%,transparent),transparent 24%),
    radial-gradient(circle at 87% 52%,color-mix(in srgb,var(--ks-pa3-opp-accent,#7dd3fc) 10%,transparent),transparent 24%);
}}

.ks-pa3-team{{
  min-width:0;
  padding:9px 10px!important;
  border-radius:16px;
  background:linear-gradient(180deg,rgba(255,255,255,.025),rgba(15,23,42,.10));
}}

.ks-pa3-team-left{{
  border-left:2px solid color-mix(in srgb,var(--ks-pa3-team-accent,#38bdf8) 78%,transparent);
}}

.ks-pa3-team-right{{
  border-right:2px solid color-mix(in srgb,var(--ks-pa3-opp-accent,#7dd3fc) 78%,transparent);
}}

.ks-pa3-team-logo{{
  width:68px!important;
  height:68px!important;
  flex-basis:68px!important;
  padding:8px!important;
  border-radius:19px!important;
  background:
    radial-gradient(circle at 50% 24%,rgba(255,255,255,.08),transparent 50%),
    rgba(2,8,18,.58)!important;
  border:1px solid rgba(255,255,255,.10)!important;
  filter:drop-shadow(0 10px 18px rgba(0,0,0,.36))!important;
}}

.ks-pa3-team-left .ks-pa3-team-logo{{
  box-shadow:
    inset 3px 0 0 color-mix(in srgb,var(--ks-pa3-team-accent,#38bdf8) 88%,white 4%),
    0 0 22px color-mix(in srgb,var(--ks-pa3-team-accent,#38bdf8) 10%,transparent)!important;
}}

.ks-pa3-team-right .ks-pa3-team-logo{{
  box-shadow:
    inset -3px 0 0 color-mix(in srgb,var(--ks-pa3-opp-accent,#7dd3fc) 88%,white 4%),
    0 0 22px color-mix(in srgb,var(--ks-pa3-opp-accent,#7dd3fc) 10%,transparent)!important;
}}

.ks-pa3-team-copy span{{
  color:#9fdcf5!important;
  letter-spacing:.13em!important;
}}

.ks-pa3-team-copy strong{{
  color:#f8fafc!important;
  font-size:.94rem!important;
  letter-spacing:-.01em;
}}

.ks-pa3-player{{
  gap:18px!important;
}}

.ks-pa3-headshot-wrap{{
  width:104px!important;
  height:104px!important;
  flex-basis:104px!important;
  padding:5px!important;
  background:
    conic-gradient(
      from 215deg,
      var(--ks-pa3-team-accent,#38bdf8),
      #38bdf8 34%,
      #7dd3fc 58%,
      var(--ks-pa3-opp-accent,#7dd3fc) 84%,
      var(--ks-pa3-team-accent,#38bdf8)
    )!important;
  box-shadow:
    0 0 0 6px rgba(14,165,233,.065),
    0 0 42px rgba(56,189,248,.28),
    0 16px 30px rgba(0,0,0,.38)!important;
}}

.ks-pa3-headshot-logo{{
  width:39px!important;
  height:39px!important;
  right:-9px!important;
  bottom:-6px!important;
  filter:drop-shadow(0 5px 8px rgba(0,0,0,.35));
}}

.ks-pa3-player-line{{
  align-items:center!important;
  gap:9px!important;
}}

.ks-pa3-player-line h1{{
  font-size:clamp(1.8rem,3.6vw,2.75rem)!important;
  line-height:.96!important;
  letter-spacing:-.045em!important;
  text-shadow:0 0 22px rgba(125,211,252,.13);
}}

.ks-pa3-player-line>span{{
  padding:5px 8px!important;
  border-radius:999px!important;
  border:1px solid rgba(125,211,252,.24)!important;
  background:rgba(14,165,233,.08)!important;
  color:#d8f3ff!important;
  font-size:.63rem!important;
  font-weight:900!important;
}}

.ks-pa3-player-copy p{{
  margin-top:8px!important;
  padding:6px 10px!important;
  border:1px solid rgba(56,189,248,.20)!important;
  border-radius:999px!important;
  background:linear-gradient(180deg,rgba(14,165,233,.10),rgba(14,165,233,.035))!important;
  color:#aee6fb!important;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.035);
}}

.ks-pa3-player-meta{{
  gap:7px!important;
  margin-top:10px!important;
}}

.ks-pa3-player-meta span{{
  padding:5px 9px!important;
  border-color:rgba(148,163,184,.13)!important;
  background:rgba(15,23,42,.62)!important;
  color:#9db0c6!important;
}}

.ks-pa3-player-meta .ks-pa3-gate-pill{{
  color:#c9f1ff!important;
  border-color:rgba(56,189,248,.30)!important;
  background:linear-gradient(180deg,rgba(14,165,233,.15),rgba(14,165,233,.055))!important;
  box-shadow:0 0 18px rgba(14,165,233,.08);
}}

.ks-pa3-matchup-strip{{
  margin-top:10px!important;
  padding-top:13px!important;
  border-top:1px solid rgba(125,211,252,.09)!important;
}}

.ks-pa3-matchup-strip span,
.ks-pa3-matchup-strip strong{{
  border:1px solid rgba(148,163,184,.09)!important;
  border-radius:999px!important;
  background:rgba(15,23,42,.42)!important;
  padding:5px 9px!important;
}}

.ks-pa3-matchup-strip strong{{
  color:#c8efff!important;
  border-color:rgba(56,189,248,.18)!important;
}}

/* =================================================================
   VERIFIED QUICK-STATS RIBBON — same frozen values, stronger glance UI.
   ================================================================= */
.ks-pa3-stats{{
  border:1px solid rgba(125,211,252,.20)!important;
  border-radius:18px!important;
  padding:12px 12px 13px!important;
  background:
    linear-gradient(180deg,rgba(6,18,31,.90),rgba(3,10,19,.97)),
    #030a13!important;
  box-shadow:
    0 16px 40px rgba(0,0,0,.22),
    inset 0 1px 0 rgba(255,255,255,.025)!important;
}}

.ks-pa3-stats-head{{
  margin-bottom:8px!important;
  padding:0 3px!important;
  align-items:center!important;
}}

.ks-pa3-stats-head>div{{
  flex-direction:row!important;
  align-items:center!important;
  gap:7px!important;
}}

.ks-pa3-stats-head span{{
  color:#61ccf8!important;
  font-size:.50rem!important;
  letter-spacing:.14em!important;
}}

.ks-pa3-stats-head strong{{
  color:#dff6ff!important;
  font-size:.72rem!important;
}}

.ks-pa3-stats-head em{{
  color:#71869d!important;
  font-size:.46rem!important;
}}

.ks-pa3-stat-grid{{
  display:grid!important;
  grid-template-columns:repeat(6,minmax(0,1fr))!important;
  gap:8px!important;
}}

.ks-pa3-stat-grid article{{
  position:relative;
  min-height:88px;
  padding:12px 11px 10px 13px!important;
  border:1px solid rgba(125,211,252,.10)!important;
  border-radius:14px!important;
  overflow:hidden;
  background:
    radial-gradient(circle at 12% 12%,rgba(56,189,248,.055),transparent 38%),
    linear-gradient(180deg,rgba(15,28,45,.76),rgba(8,17,30,.88))!important;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.025);
}}

.ks-pa3-stat-grid article::before{{
  content:"";
  position:absolute;
  left:0;
  top:12px;
  bottom:12px;
  width:2px;
  border-radius:999px;
  background:linear-gradient(180deg,#38bdf8,rgba(56,189,248,.08));
  opacity:.78;
}}

.ks-pa3-stat-grid article::after{{
  position:absolute;
  right:9px;
  top:8px;
  color:rgba(125,211,252,.55);
  font-size:.78rem;
  line-height:1;
  font-weight:900;
}}

.ks-pa3-stat-grid article:nth-child(1)::after{{content:"◆"}}
.ks-pa3-stat-grid article:nth-child(2)::after{{content:"◎"}}
.ks-pa3-stat-grid article:nth-child(3)::after{{content:"◈"}}
.ks-pa3-stat-grid article:nth-child(4)::after{{content:"↑"}}
.ks-pa3-stat-grid article:nth-child(5)::after{{content:"↓"}}
.ks-pa3-stat-grid article:nth-child(6)::after{{content:"↗"}}

.ks-pa3-stat-grid article>span{{
  color:#8096ae!important;
  font-size:.48rem!important;
  letter-spacing:.11em!important;
}}

.ks-pa3-stat-grid article>strong{{
  margin-top:3px;
  color:#f8fafc!important;
  font-size:1.38rem!important;
  line-height:.96!important;
  letter-spacing:-.025em;
}}

.ks-pa3-stat-grid article>small{{
  margin-top:2px;
  color:#657b93!important;
  font-size:.44rem!important;
  letter-spacing:.02em;
}}

.ks-pa3-stat-grid .ks-pa3-hit-card{{
  border-color:rgba(56,189,248,.28)!important;
  background:
    radial-gradient(circle at 90% 15%,rgba(56,189,248,.14),transparent 42%),
    linear-gradient(180deg,rgba(6,31,49,.90),rgba(5,18,31,.96))!important;
  box-shadow:
    0 0 0 1px rgba(56,189,248,.035),
    0 0 24px rgba(14,165,233,.06),
    inset 0 1px 0 rgba(255,255,255,.04)!important;
}}

.ks-pa3-stat-grid .ks-pa3-hit-card>strong{{
  color:#7dd3fc!important;
}}

@media(hover:hover){{
  .ks-pa3-hero,
  .ks-pa3-stat-grid article,
  .ks-pa3-team-logo,
  .ks-pa3-headshot-wrap{{
    transition:transform .16s ease,border-color .16s ease,box-shadow .16s ease;
  }}
  .ks-pa3-hero:hover{{
    border-color:rgba(125,211,252,.36)!important;
  }}
  .ks-pa3-stat-grid article:hover{{
    transform:translateY(-2px);
    border-color:rgba(125,211,252,.24)!important;
    box-shadow:0 10px 24px rgba(0,0,0,.15),inset 0 1px 0 rgba(255,255,255,.035)!important;
  }}
}}

@media(max-width:900px){{
  .ks-pa3-headshot-wrap{{
    width:92px!important;
    height:92px!important;
    flex-basis:92px!important;
  }}
  .ks-pa3-team-logo{{
    width:60px!important;
    height:60px!important;
    flex-basis:60px!important;
  }}
  .ks-pa3-stat-grid{{
    grid-template-columns:repeat(3,minmax(0,1fr))!important;
  }}
}}

@media(max-width:560px){{
  .ks-pa3-hero{{
    border-radius:16px!important;
    padding:15px 11px 13px!important;
  }}
  .ks-pa3-player{{
    gap:13px!important;
  }}
  .ks-pa3-headshot-wrap{{
    width:78px!important;
    height:78px!important;
    flex-basis:78px!important;
  }}
  .ks-pa3-team-logo{{
    width:44px!important;
    height:44px!important;
    flex-basis:44px!important;
    padding:5px!important;
    border-radius:14px!important;
  }}
  .ks-pa3-player-line h1{{
    font-size:1.58rem!important;
  }}
  .ks-pa3-stats{{
    padding:10px!important;
    border-radius:15px!important;
  }}
  .ks-pa3-stats-head{{
    align-items:flex-start!important;
  }}
  .ks-pa3-stats-head>div{{
    flex-wrap:wrap;
  }}
  .ks-pa3-stat-grid{{
    display:flex!important;
    gap:7px!important;
    overflow-x:auto!important;
    overscroll-behavior-inline:contain;
    scroll-snap-type:x proximity;
    scrollbar-width:none;
    padding-bottom:2px;
  }}
  .ks-pa3-stat-grid::-webkit-scrollbar{{display:none}}
  .ks-pa3-stat-grid article{{
    flex:0 0 min(156px,43vw)!important;
    min-height:82px;
    scroll-snap-align:start;
  }}
}}

@media(prefers-reduced-motion:reduce){{
  .ks-pa3-hero,
  .ks-pa3-stat-grid article,
  .ks-pa3-team-logo,
  .ks-pa3-headshot-wrap{{
    transition:none!important;
    transform:none!important;
  }}
}}
</style>
""",
        unsafe_allow_html=True,
    )
    return {
        "ready": True,
        "state": "ready",
        "version": PAGE3_REDESIGN_STEP2_VERSION,
        "presentation_only": True,
        "frozen_page3_steps_1_to_8": True,
        "frozen_fun_polish_steps_1_to_5": True,
        "frozen_redesign_step1": True,
        "interaction_behavior_changed": False,
        "data_ownership_changed": False,
        "certified_viewports": CERTIFIED_VIEWPORTS,
        "projection_weight": 0.0,
    }


__all__ = [
    "CERTIFIED_VIEWPORTS",
    "DATA_OWNERSHIP_CHANGED",
    "FROZEN_FUN_POLISH_STEPS_1_TO_5_PROTECTED",
    "FROZEN_PAGE3_STEPS_1_TO_8_PROTECTED",
    "FROZEN_REDESIGN_STEP1_PROTECTED",
    "INTERACTION_BEHAVIOR_CHANGED",
    "MODEL_VERSION",
    "PAGE3_REDESIGN_STEP",
    "PAGE3_REDESIGN_STEP2_VERSION",
    "PRESENTATION_ONLY",
    "PROBABILITY_LOGIC",
    "PROJECTION_LOGIC",
    "RECOMMENDATION_LOGIC",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "WAGER_ACTIONS",
    "render_redesign_step2_hero_ribbon",
]
