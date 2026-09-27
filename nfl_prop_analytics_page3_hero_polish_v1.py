"""NFL Prop Analytics Page 3 Fun Polish Step 2 — premium hero upgrade.

Presentation-only hero styling layered after frozen Page 3 Steps 1-8 and
Fun Polish Step 1. No data ownership or sports-analysis semantics change.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

MODEL_VERSION = "NFL PROP ANALYTICS PAGE 3 FUN POLISH STEP 2 • HERO V1"
PAGE3_FUN_POLISH_STEP = 2
PAGE3_HERO_POLISH_VERSION = "v1"
PRESENTATION_ONLY = True
FROZEN_PAGE3_STEPS_1_TO_8_PROTECTED = True
FROZEN_POLISH_STEP1_PROTECTED = True
PROJECTION_LOGIC = False
PROBABILITY_LOGIC = False
RECOMMENDATION_LOGIC = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS = False

TEAM_ACCENTS = {
    "ARI": "#97233F", "ATL": "#A71930", "BAL": "#241773", "BUF": "#00338D",
    "CAR": "#0085CA", "CHI": "#0B162A", "CIN": "#FB4F14", "CLE": "#FF3C00",
    "DAL": "#003594", "DEN": "#FB4F14", "DET": "#0076B6", "GB": "#203731",
    "HOU": "#03202F", "IND": "#002C5F", "JAX": "#006778", "KC": "#E31837",
    "LV": "#A5ACAF", "LAC": "#0080C6", "LAR": "#003594", "MIA": "#008E97",
    "MIN": "#4F2683", "NE": "#002244", "NO": "#D3BC8D", "NYG": "#0B2265",
    "NYJ": "#125740", "PHI": "#004C54", "PIT": "#FFB612", "SEA": "#69BE28",
    "SF": "#AA0000", "TB": "#D50A0A", "TEN": "#4B92DB", "WAS": "#5A1414",
}


def _team_css() -> str:
    rules: list[str] = []
    for team, color in TEAM_ACCENTS.items():
        rules.append(
            f'[data-prop-page3-step1-hero="v1"][data-prop-page3-player-team="{team}"]'
            f'{{--ks-pa3-team-accent:{color};}}'
        )
        rules.append(
            f'[data-prop-page3-step1-hero="v1"][data-prop-page3-opponent="{team}"]'
            f'{{--ks-pa3-opp-accent:{color};}}'
        )
    return "\n".join(rules)


def render_hero_polish() -> dict[str, Any]:
    """Apply presentation-only premium hero styling and emit proof marker."""
    team_css = _team_css()
    st.markdown(
        f"""
<div class="ks-pa3-fun-polish-step2-marker"
     data-prop-page3-fun-polish-step2="{PAGE3_HERO_POLISH_VERSION}"
     data-prop-page3-fun-polish-step2-state="ready"
     data-prop-page3-fun-polish-step2-presentation-only="true"
     data-prop-page3-fun-polish-step2-frozen-steps-1-8="true"
     data-prop-page3-fun-polish-step2-frozen-polish-step1="true"
     data-prop-page3-fun-polish-step2-projection-weight="0.0"></div>

<style data-prop-page3-fun-polish-step2-css="{PAGE3_HERO_POLISH_VERSION}">
.ks-pa3-fun-polish-step2-marker{{display:none!important}}
{team_css}

.ks-pa3-hero{{
  --ks-pa3-team-accent:#38bdf8;
  --ks-pa3-opp-accent:#7dd3fc;
  border-color:rgba(125,211,252,.30)!important;
  background:
    radial-gradient(circle at 12% 18%,color-mix(in srgb,var(--ks-pa3-team-accent) 16%,transparent),transparent 27%),
    radial-gradient(circle at 88% 18%,color-mix(in srgb,var(--ks-pa3-opp-accent) 14%,transparent),transparent 27%),
    radial-gradient(circle at 50% -15%,rgba(56,189,248,.18),transparent 38%),
    linear-gradient(180deg,rgba(4,12,23,.94),rgba(2,8,15,.99))!important;
  box-shadow:
    0 18px 48px rgba(0,0,0,.28),
    0 0 0 1px rgba(56,189,248,.035),
    inset 0 1px 0 rgba(255,255,255,.055)!important;
}}
.ks-pa3-hero::before{{
  content:"";position:absolute;z-index:2;left:18px;right:18px;top:0;height:2px;
  border-radius:0 0 999px 999px;
  background:linear-gradient(90deg,var(--ks-pa3-team-accent),#38bdf8 50%,var(--ks-pa3-opp-accent));
  box-shadow:0 0 18px rgba(56,189,248,.32);
  opacity:.92;
}}
.ks-pa3-hero-glow{{height:5px!important;opacity:.75;filter:blur(3px)!important}}

.ks-pa3-team-logo{{
  width:64px!important;height:64px!important;flex-basis:64px!important;
  padding:7px;border:1px solid rgba(255,255,255,.08);border-radius:18px;
  background:linear-gradient(180deg,rgba(255,255,255,.045),rgba(15,23,42,.32));
  filter:drop-shadow(0 9px 15px rgba(0,0,0,.34))!important;
}}
.ks-pa3-team-left .ks-pa3-team-logo{{
  box-shadow:inset 3px 0 0 var(--ks-pa3-team-accent),0 8px 22px rgba(0,0,0,.16);
}}
.ks-pa3-team-right .ks-pa3-team-logo{{
  box-shadow:inset -3px 0 0 var(--ks-pa3-opp-accent),0 8px 22px rgba(0,0,0,.16);
}}
.ks-pa3-team-copy span{{color:#a6e5ff!important}}
.ks-pa3-team-copy strong{{font-size:.86rem!important}}

.ks-pa3-headshot-wrap{{
  flex-basis:88px!important;width:88px!important;height:88px!important;padding:4px!important;
  background:conic-gradient(
    from 205deg,
    var(--ks-pa3-team-accent),
    #38bdf8 34%,
    #7dd3fc 58%,
    var(--ks-pa3-opp-accent) 82%,
    var(--ks-pa3-team-accent)
  )!important;
  box-shadow:
    0 0 0 5px rgba(14,165,233,.07),
    0 0 34px rgba(56,189,248,.24),
    0 12px 24px rgba(0,0,0,.24)!important;
}}
.ks-pa3-headshot-logo{{
  width:35px!important;height:35px!important;right:-8px!important;bottom:-4px!important;
}}
.ks-pa3-player{{gap:16px!important}}
.ks-pa3-player-line h1{{
  text-shadow:0 0 20px rgba(125,211,252,.12);
}}
.ks-pa3-player-line>span{{
  padding:4px 7px;border:1px solid rgba(125,211,252,.14);border-radius:999px;
  color:#d7ecf8!important;background:rgba(14,165,233,.06);
  font-size:.66rem!important;line-height:1!important;
}}
.ks-pa3-player-copy p{{
  display:inline-flex;align-items:center;
  margin-top:7px!important;padding:5px 8px;border-radius:999px;
  border:1px solid rgba(56,189,248,.13);
  color:#9fdcf5!important;background:rgba(14,165,233,.045);
  font-size:.67rem!important;font-weight:800;
}}
.ks-pa3-player-meta{{gap:6px!important;margin-top:9px!important}}
.ks-pa3-player-meta span{{
  padding:5px 8px!important;border-color:rgba(125,211,252,.15)!important;
  color:#9aacc0!important;background:rgba(15,23,42,.55)!important;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.025);
}}
.ks-pa3-player-meta .ks-pa3-gate-pill{{
  color:#c7efff!important;border-color:rgba(56,189,248,.28)!important;
  background:linear-gradient(180deg,rgba(14,165,233,.12),rgba(14,165,233,.05))!important;
  box-shadow:0 0 15px rgba(14,165,233,.06);
}}

.ks-pa3-matchup-strip{{
  gap:7px!important;margin-top:7px!important;padding-top:12px!important;
}}
.ks-pa3-matchup-strip span,.ks-pa3-matchup-strip strong{{
  padding:5px 8px!important;border:1px solid rgba(148,163,184,.07);
}}
.ks-pa3-matchup-strip strong{{
  border-color:rgba(56,189,248,.16)!important;
  box-shadow:0 0 14px rgba(56,189,248,.05);
}}

@media(hover:hover){{
  .ks-pa3-headshot-wrap,.ks-pa3-team-logo{{transition:transform .16s ease,filter .16s ease}}
  .ks-pa3-hero:hover .ks-pa3-headshot-wrap{{transform:translateY(-2px)}}
  .ks-pa3-team-logo:hover{{transform:translateY(-1px)}}
}}

@media(max-width:760px){{
  .ks-pa3-headshot-wrap{{flex-basis:82px!important;width:82px!important;height:82px!important}}
  .ks-pa3-team-logo{{width:58px!important;height:58px!important;flex-basis:58px!important}}
}}
@media(max-width:560px){{
  .ks-pa3-headshot-wrap{{flex-basis:76px!important;width:76px!important;height:76px!important}}
  .ks-pa3-player-copy p{{max-width:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
  .ks-pa3-player-meta span{{padding:4px 7px!important}}
}}
@media(prefers-reduced-motion:reduce){{
  .ks-pa3-headshot-wrap,.ks-pa3-team-logo{{transition:none!important;transform:none!important}}
}}
</style>
""",
        unsafe_allow_html=True,
    )
    return {
        "ready": True,
        "state": "ready",
        "version": PAGE3_HERO_POLISH_VERSION,
        "presentation_only": True,
        "frozen_steps_1_to_8": True,
        "frozen_polish_step1": True,
        "team_accent_count": len(TEAM_ACCENTS),
        "projection_weight": 0.0,
    }


__all__ = [
    "FROZEN_PAGE3_STEPS_1_TO_8_PROTECTED",
    "FROZEN_POLISH_STEP1_PROTECTED",
    "MODEL_VERSION",
    "PAGE3_FUN_POLISH_STEP",
    "PAGE3_HERO_POLISH_VERSION",
    "PRESENTATION_ONLY",
    "PROBABILITY_LOGIC",
    "PROJECTION_LOGIC",
    "RECOMMENDATION_LOGIC",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "TEAM_ACCENTS",
    "WAGER_ACTIONS",
    "render_hero_polish",
]
