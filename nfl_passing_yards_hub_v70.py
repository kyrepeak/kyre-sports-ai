"""NFL Passing Yards V70 — Mobile Cleanup Steps 2-3.

Additive presentation-only wrapper over frozen V69. Step 2 restores the missing
presentation contract for the six surfaces locked by Step 1. Step 3 applies that
single CSS layer to the frozen Game Center plus the five frozen Deep Evidence
payloads re-embedded by V67.

No analytical value is recomputed or mutated. No data, model, probability,
market math, sportsbook logic, widget state, query state, or navigation state
changes are allowed.
"""
from __future__ import annotations

import streamlit as st

import nfl_passing_yards_hub_v69 as prior

MODEL_VERSION = "NFL PASSING YARDS V70 • MOBILE CLEANUP STEPS 2-3"
FROZEN_PRIOR = "nfl_passing_yards_hub_v69"
MOBILE_CLEANUP_VERSION = "v70"
MOBILE_CLEANUP_STEP_2 = 2
MOBILE_CLEANUP_STEP_3 = 3
PRESENTATION_ONLY = True
DISPLAY_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_CONTEXT = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_WIDGET_KEYS = False
MAY_MODIFY_DATA = False
MAY_MODIFY_NAVIGATION_STATE = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_MOBILE_CLEANUP_CSS = r"""
<style data-passing-yards-mobile-cleanup-css="v70">
/* ---------------------------------------------------------
   Shared safety: presentation-only, no content mutation.
   --------------------------------------------------------- */
.kpy15-center,
.kpy15-center *,
.ks-py67-deep,
.ks-py67-deep *{
  box-sizing:border-box;
}

/* ---------------------------------------------------------
   Surface 1 — Game Center / V15
   --------------------------------------------------------- */
.kpy15-center{
  width:100%;
  max-width:100%;
  min-width:0;
  overflow:hidden;
  margin:8px 0 12px!important;
  padding:14px!important;
  border:1px solid var(--kyre-sem-border-medium)!important;
  border-radius:var(--kyre-sem-radius-card)!important;
  background:
    radial-gradient(circle at 100% 0%,var(--kyre-sem-accent-wash-soft),transparent 34%),
    linear-gradient(155deg,var(--kyre-sem-surface-panel-alt),var(--kyre-sem-surface-panel))!important;
  box-shadow:var(--kyre-sem-shadow-card)!important;
}
.kpy15-centerhead{
  display:flex!important;
  align-items:flex-start!important;
  justify-content:space-between!important;
  gap:12px!important;
  margin-bottom:12px!important;
}
.kpy15-centertitle{
  color:var(--kyre-sem-text-primary)!important;
  font-size:1rem!important;
  font-weight:950!important;
  line-height:1.15!important;
}
.kpy15-centersub{
  margin-top:4px!important;
  color:var(--kyre-sem-text-muted)!important;
  font-size:.66rem!important;
  line-height:1.45!important;
}
.kpy15-modeltag,
.kpy15-conf,
.kpy15-grade{
  display:inline-flex!important;
  align-items:center!important;
  justify-content:center!important;
  width:max-content!important;
  max-width:100%!important;
  min-height:26px!important;
  padding:5px 8px!important;
  border:1px solid var(--kyre-sem-border-medium)!important;
  border-radius:999px!important;
  background:var(--kyre-sem-accent-wash-soft)!important;
  color:var(--kyre-sem-text-accent-soft)!important;
  font-size:.56rem!important;
  font-weight:950!important;
  line-height:1.15!important;
  white-space:nowrap!important;
}
.kpy15-center .kpy15-conf,
.kpy15-center .kpy15-grade,
.kpy15-center .kpy15-modeltag{
  display:inline-flex!important;
}
.kpy15-grid{
  display:grid!important;
  grid-template-columns:repeat(2,minmax(0,1fr))!important;
  gap:10px!important;
}
.kpy15-qb{
  min-width:0!important;
  padding:12px!important;
  border:1px solid var(--kyre-sem-border-soft)!important;
  border-radius:12px!important;
  background:rgba(255,255,255,.018)!important;
}
.kpy15-qbtop{
  display:flex!important;
  align-items:flex-start!important;
  justify-content:space-between!important;
  gap:10px!important;
  margin-bottom:10px!important;
}
.kpy15-name{
  min-width:0!important;
  color:var(--kyre-sem-text-primary)!important;
  font-size:.96rem!important;
  font-weight:950!important;
  line-height:1.2!important;
  white-space:normal!important;
  overflow:visible!important;
  text-overflow:clip!important;
}
.kpy15-hero{
  display:grid!important;
  grid-template-columns:repeat(3,minmax(0,1fr))!important;
  gap:8px!important;
}
.kpy15-metric{
  min-width:0!important;
  padding:10px!important;
  border:1px solid var(--kyre-sem-border-soft)!important;
  border-radius:10px!important;
  background:var(--kyre-sem-surface-panel-alt)!important;
}
.kpy15-metric b{
  display:block!important;
  margin:0 0 5px!important;
  color:var(--kyre-sem-text-primary)!important;
  font-size:1rem!important;
  font-weight:950!important;
  line-height:1.1!important;
  white-space:normal!important;
  overflow:visible!important;
  text-overflow:clip!important;
  overflow-wrap:anywhere!important;
}
.kpy15-metric span{
  display:block!important;
  margin:0!important;
  color:var(--kyre-sem-text-muted)!important;
  font-size:.58rem!important;
  font-weight:900!important;
  line-height:1.3!important;
  letter-spacing:.035em!important;
  text-transform:uppercase!important;
  white-space:normal!important;
  overflow-wrap:anywhere!important;
}
.kpy15-market{
  display:flex!important;
  align-items:flex-start!important;
  justify-content:space-between!important;
  gap:10px!important;
  margin-top:10px!important;
  padding-top:10px!important;
  border-top:1px solid var(--kyre-sem-border-soft)!important;
}
.kpy15-marketlead{
  color:var(--kyre-sem-text-primary)!important;
  font-size:.7rem!important;
  font-weight:950!important;
  line-height:1.35!important;
}
.kpy15-marketmeta,
.kpy15-foot{
  color:var(--kyre-sem-text-muted)!important;
  font-size:.58rem!important;
  line-height:1.5!important;
}
.kpy15-foot{margin-top:10px!important}

/* ---------------------------------------------------------
   Surfaces 2-6 — frozen payloads re-embedded by V67.
   The captured HTML arrives without owner CSS; V70 restores
   the missing display hierarchy inside Deep Evidence only.
   --------------------------------------------------------- */
.ks-py67-deep .kpass30-profile,
.ks-py67-deep .kpy-defense,
.ks-py67-deep .kpy-pressure,
.ks-py67-deep .kpy-personnel,
.ks-py67-deep .kpy-env{
  width:100%!important;
  max-width:100%!important;
  min-width:0!important;
  margin:0!important;
  padding:0!important;
  border:0!important;
  border-radius:0!important;
  background:transparent!important;
  box-shadow:none!important;
  overflow:visible!important;
}

/* headers */
.ks-py67-deep .kpass30-head,
.ks-py67-deep .kpy-dhead,
.ks-py67-deep .kpy-xhead,
.ks-py67-deep .kpy-ihead,
.ks-py67-deep .kpy-envtop{
  display:flex!important;
  align-items:flex-start!important;
  justify-content:space-between!important;
  gap:10px!important;
  margin:0 0 10px!important;
  padding:0 0 10px!important;
  border-bottom:1px solid var(--kyre-sem-border-soft)!important;
}
.ks-py67-deep .kpass30-name,
.ks-py67-deep .kpy-dname,
.ks-py67-deep .kpy-xname,
.ks-py67-deep .kpy-iname,
.ks-py67-deep .kpy-envtitle{
  color:var(--kyre-sem-text-primary)!important;
  font-size:.86rem!important;
  font-weight:950!important;
  line-height:1.25!important;
  white-space:normal!important;
  overflow-wrap:anywhere!important;
}
.ks-py67-deep .kpass30-sub,
.ks-py67-deep .kpy-dsub,
.ks-py67-deep .kpy-xsub,
.ks-py67-deep .kpy-isub,
.ks-py67-deep .kpy-envsub{
  margin-top:4px!important;
  color:var(--kyre-sem-text-muted)!important;
  font-size:.58rem!important;
  line-height:1.5!important;
  white-space:normal!important;
  overflow-wrap:anywhere!important;
}

/* status badges */
.ks-py67-deep .kpass30-state,
.ks-py67-deep .kpy-grade,
.ks-py67-deep .kpy-xgrade,
.ks-py67-deep .kpy-ilabel,
.ks-py67-deep .kpy-envlabel{
  display:inline-flex!important;
  align-items:center!important;
  justify-content:center!important;
  flex:0 0 auto!important;
  width:max-content!important;
  max-width:100%!important;
  min-height:26px!important;
  padding:5px 8px!important;
  border:1px solid var(--kyre-sem-border-medium)!important;
  border-radius:999px!important;
  background:var(--kyre-sem-accent-wash-soft)!important;
  color:var(--kyre-sem-text-accent-soft)!important;
  font-size:.54rem!important;
  font-weight:950!important;
  line-height:1.15!important;
  white-space:nowrap!important;
}

/* metric grids */
.ks-py67-deep .kpass30-hero,
.ks-py67-deep .kpass30-season,
.ks-py67-deep .kpass30-form,
.ks-py67-deep .kpy-dmetrics,
.ks-py67-deep .kpy-xmetrics,
.ks-py67-deep .kpy-imetrics,
.ks-py67-deep .kpy-envmetrics,
.ks-py67-deep .kpy-envrow{
  display:grid!important;
  grid-template-columns:repeat(2,minmax(0,1fr))!important;
  gap:8px!important;
  margin:0!important;
}
.ks-py67-deep .kpass30-season,
.ks-py67-deep .kpass30-form,
.ks-py67-deep .kpy-envteams{
  margin-top:8px!important;
}
.ks-py67-deep .kpass30-herostat:first-child{
  grid-column:1/-1!important;
}

/* all metric tiles */
.ks-py67-deep .kpass30-herostat,
.ks-py67-deep .kpass30-mini,
.ks-py67-deep .kpass30-formcell,
.ks-py67-deep .kpy-dmetric,
.ks-py67-deep .kpy-xmetric,
.ks-py67-deep .kpy-imetric,
.ks-py67-deep .kpy-envmetric,
.ks-py67-deep .kpy-envcell{
  min-width:0!important;
  min-height:66px!important;
  padding:10px!important;
  border:1px solid var(--kyre-sem-border-soft)!important;
  border-radius:10px!important;
  background:rgba(255,255,255,.018)!important;
}

/* force value above label */
.ks-py67-deep .kpass30-herostat b,
.ks-py67-deep .kpass30-mini b,
.ks-py67-deep .kpass30-formcell b,
.ks-py67-deep .kpy-dmetric b,
.ks-py67-deep .kpy-xmetric b,
.ks-py67-deep .kpy-imetric b,
.ks-py67-deep .kpy-envmetric b,
.ks-py67-deep .kpy-envcell b{
  display:block!important;
  margin:0 0 5px!important;
  color:var(--kyre-sem-text-primary)!important;
  font-size:.82rem!important;
  font-weight:950!important;
  line-height:1.15!important;
  white-space:normal!important;
  overflow:visible!important;
  text-overflow:clip!important;
  overflow-wrap:anywhere!important;
}
.ks-py67-deep .kpass30-herostat span,
.ks-py67-deep .kpass30-mini span,
.ks-py67-deep .kpass30-formcell span,
.ks-py67-deep .kpy-dmetric span,
.ks-py67-deep .kpy-xmetric span,
.ks-py67-deep .kpy-imetric span,
.ks-py67-deep .kpy-envmetric span{
  display:block!important;
  margin:0!important;
  color:var(--kyre-sem-text-muted)!important;
  font-size:.54rem!important;
  font-weight:900!important;
  line-height:1.3!important;
  letter-spacing:.03em!important;
  text-transform:uppercase!important;
  white-space:normal!important;
  overflow-wrap:anywhere!important;
}
/* environment cells use a raw text node after <b>; flex makes it its own label row */
.ks-py67-deep .kpy-envcell{
  display:flex!important;
  flex-direction:column!important;
  gap:0!important;
  color:var(--kyre-sem-text-muted)!important;
  font-size:.56rem!important;
  font-weight:850!important;
  line-height:1.3!important;
}

/* supporting evidence */
.ks-py67-deep .kpass30-formtitle{
  margin:10px 0 6px!important;
  color:var(--kyre-sem-text-accent-soft)!important;
  font-size:.58rem!important;
  font-weight:950!important;
  letter-spacing:.04em!important;
  text-transform:uppercase!important;
}
.ks-py67-deep .kpass30-foot,
.ks-py67-deep .kpy-drecent,
.ks-py67-deep .kpy-xrecent,
.ks-py67-deep .kpy-inote,
.ks-py67-deep .kpy-blitz,
.ks-py67-deep .kpy28-weapons,
.ks-py67-deep .kpy28-source{
  margin-top:9px!important;
  padding-top:9px!important;
  border-top:1px solid var(--kyre-sem-border-soft)!important;
  color:var(--kyre-sem-text-muted)!important;
  font-size:.58rem!important;
  line-height:1.55!important;
  white-space:normal!important;
  overflow-wrap:anywhere!important;
}
.ks-py67-deep .kpy28-source{
  margin-top:7px!important;
  padding-top:0!important;
  border-top:0!important;
}
.ks-py67-deep .kpy28-weapons>b{
  display:block!important;
  margin-bottom:6px!important;
  color:var(--kyre-sem-text-primary)!important;
}
.ks-py67-deep .kpy28-weapon-pill{
  display:inline-flex!important;
  align-items:center!important;
  margin:3px 4px 0 0!important;
  padding:5px 7px!important;
  border:1px solid var(--kyre-sem-border-soft)!important;
  border-radius:999px!important;
  background:var(--kyre-sem-accent-wash-soft)!important;
  color:var(--kyre-sem-text-accent-soft)!important;
  font-size:.54rem!important;
  font-weight:850!important;
  line-height:1.25!important;
  white-space:normal!important;
}

/* environment teams */
.ks-py67-deep .kpy-envteams{
  display:grid!important;
  grid-template-columns:1fr!important;
  gap:8px!important;
}
.ks-py67-deep .kpy-envteam{
  min-width:0!important;
  padding:10px!important;
  border:1px solid var(--kyre-sem-border-soft)!important;
  border-radius:10px!important;
  background:rgba(255,255,255,.014)!important;
}
.ks-py67-deep .kpy-envteam h4{
  margin:0 0 8px!important;
  color:var(--kyre-sem-text-primary)!important;
  font-size:.72rem!important;
  font-weight:950!important;
  line-height:1.3!important;
  white-space:normal!important;
  overflow-wrap:anywhere!important;
}

/* ---------------------------------------------------------
   Tablet + phone
   --------------------------------------------------------- */
@media(max-width:820px){
  /* Keep the confidence pill out of flex-item blockification on phone/tablet.
     The badge remains inline-flex and gets its own clean row below the QB name. */
  .kpy15-qbtop{
    display:block!important;
  }
  .kpy15-qbtop .kpy15-conf{
    display:inline-flex!important;
    margin-top:7px!important;
  }
}

@media(max-width:760px){
  .kpy15-grid{
    grid-template-columns:1fr!important;
  }
  .kpy15-centerhead{
    flex-direction:column!important;
  }
  .kpy15-modeltag{
    align-self:flex-start!important;
  }
}

@media(max-width:560px){
  .kpy15-center{
    padding:10px!important;
  }
  .kpy15-qb{
    padding:10px!important;
  }
  .kpy15-qbtop,
  .kpy15-market,
  .ks-py67-deep .kpass30-head,
  .ks-py67-deep .kpy-dhead,
  .ks-py67-deep .kpy-xhead,
  .ks-py67-deep .kpy-ihead,
  .ks-py67-deep .kpy-envtop{
    flex-direction:column!important;
    align-items:flex-start!important;
  }
  .kpy15-hero{
    grid-template-columns:repeat(2,minmax(0,1fr))!important;
  }
  .kpy15-hero>.kpy15-metric:first-child{
    grid-column:1/-1!important;
  }
  .ks-py67-deep .kpass30-state,
  .ks-py67-deep .kpy-grade,
  .ks-py67-deep .kpy-xgrade,
  .ks-py67-deep .kpy-ilabel,
  .ks-py67-deep .kpy-envlabel{
    align-self:flex-start!important;
  }
  .ks-py67-deep .ks-py67-card{
    padding:10px!important;
  }
}
</style>
"""


def render_nfl_passing_yards_hub() -> None:
    st.markdown(
        _MOBILE_CLEANUP_CSS
        + '<span data-passing-yards-mobile-cleanup-runtime="v70" '
          'data-passing-yards-mobile-cleanup-step2="green" '
          'data-passing-yards-mobile-cleanup-step3="green" '
          'style="display:none" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )
    return prior.render_nfl_passing_yards_hub()


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V70 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_PRIOR",
    "MAY_MODIFY_CONTEXT",
    "MAY_MODIFY_DATA",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_NAVIGATION_STATE",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_WIDGET_KEYS",
    "MOBILE_CLEANUP_STEP_2",
    "MOBILE_CLEANUP_STEP_3",
    "MOBILE_CLEANUP_VERSION",
    "MODEL_VERSION",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_MOBILE_CLEANUP_CSS",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
