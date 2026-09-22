"""NFL Passing Yards V13 — cleanup step 1: mobile-first final-page shell.

Presentation-only wrapper over certified V12. It removes stale build-state chrome
that accumulated while Steps 8–10 were layered additively, replaces the old
Step-7-era page header with one final 10/10 header, and improves the slate/stat
layout on phones. All data loaders, model math, probabilities, market math,
guardrails, and the V12 verified-slate resolver remain untouched.
"""
from __future__ import annotations

import streamlit as st

import nfl_passing_yards_hub_v12 as prior

MODEL_VERSION = "NFL PASSING YARDS V13 • CLEANUP STEP 1 • MOBILE-FIRST FINAL SHELL"

_CLEANUP_CSS = r"""
<style>
/* Retire build-time banners and the stale Step-7-era header. */
.kpy8-active,.kpy9-active,.kpy10-active,.kpy-head{display:none!important}

/* Final production header. */
.kpy-final-head{border:1px solid #2d506b;background:linear-gradient(135deg,#081421,#0b1c2c);border-radius:16px;padding:13px 14px;margin:4px 0 10px;box-shadow:0 10px 28px rgba(0,0,0,.18)}
.kpy-final-row{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
.kpy-final-title{font-size:1.28rem;font-weight:950;color:#f8fbff;letter-spacing:-.025em;line-height:1.05}
.kpy-final-title span{color:#7ff2c2}
.kpy-final-sub{color:#8599ac;font-size:.64rem;line-height:1.45;margin-top:5px;max-width:760px}
.kpy-final-badge{border:1px solid #34795b;background:#0a2b1f;color:#86f0bb;border-radius:999px;padding:5px 8px;font-size:.52rem;font-weight:950;white-space:nowrap}
.kpy-final-chips{display:flex;gap:5px;flex-wrap:wrap;margin-top:9px}
.kpy-final-chip{border:1px solid #29475f;background:#071725;border-radius:999px;padding:4px 7px;color:#9bc8e6;font-size:.49rem;font-weight:900;white-space:nowrap}
.kpy-final-chip.good{border-color:#2f7458;background:#09251b;color:#82eab6}

/* Cleaner verified-slate strip. */
.kpy-strip{display:grid!important;grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:7px!important;margin:7px 0 11px!important}
.kpy-stat{min-width:0!important;padding:8px 9px!important;border-radius:11px!important}
.kpy-stat:last-child{grid-column:1/-1!important}
.kpy-stat b{font-size:.96rem!important}.kpy-stat span{font-size:.48rem!important}

/* Give each analytical step a consistent visual rhythm without changing content. */
.kpy-step{margin:13px 0 7px!important;border-radius:12px!important}
.kpy-step-title{line-height:1.25!important}.kpy-step-sub{line-height:1.45!important}

/* Slightly calmer card spacing on the production page. */
.kpy-qbgrid,.kpy-pgrid,.kpy-dgrid,.kpy-xgrid,.kpy-igrid,.kpy-projgrid,.kpy8-grid,.kpy9-grid,.kpy10-grid{gap:7px!important}

@media(max-width:700px){
  .kpy-final-head{padding:12px 11px;margin-top:2px}
  .kpy-final-row{gap:8px}
  .kpy-final-title{font-size:1.12rem}
  .kpy-final-sub{font-size:.6rem}
  .kpy-final-badge{font-size:.47rem;padding:4px 7px}
  .kpy-final-chips{gap:4px;margin-top:8px}
  .kpy-final-chip{font-size:.45rem;padding:4px 6px}
  .kpy-strip{grid-template-columns:repeat(2,minmax(0,1fr))!important}
  .kpy-stat:last-child{grid-column:1/-1!important}
  .kpy-step{margin-top:11px!important}
}
</style>
"""

_FINAL_HEADER = """
<section class="kpy-final-head">
  <div class="kpy-final-row">
    <div>
      <div class="kpy-final-title">🏈 NFL <span>Passing Yards</span></div>
      <div class="kpy-final-sub">Verified QB identity → passing profile → opponent matchup → context → projection → probability → market edge.</div>
    </div>
    <div class="kpy-final-badge">10 / 10 COMPLETE</div>
  </div>
  <div class="kpy-final-chips">
    <span class="kpy-final-chip good">VERIFIED SLATE</span>
    <span class="kpy-final-chip">MODEL + PROBABILITY</span>
    <span class="kpy-final-chip">MARKET EDGE</span>
    <span class="kpy-final-chip">SPORTSBOOK PROJECTION 0%</span>
    <span class="kpy-final-chip">STAKE SIZING OFF</span>
  </div>
</section>
"""


def render_nfl_passing_yards_hub() -> None:
    """Render certified V12 with production-only visual cleanup."""
    # !important rules intentionally load before predecessors so stale build
    # chrome stays retired even when older step CSS is injected later.
    st.markdown(_CLEANUP_CSS, unsafe_allow_html=True)
    st.markdown(_FINAL_HEADER, unsafe_allow_html=True)
    return prior.render_nfl_passing_yards_hub()


__all__ = ["MODEL_VERSION", "render_nfl_passing_yards_hub"]
