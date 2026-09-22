"""CFB Game Total clean page V28 — visual redesign Step 5 system polish.

CSS-only successor to V27. V28 does not replace any render helper and does not
change data, model, market, confidence, team evidence, or Steps 1-12 behavior.
It only unifies the already-certified Step 2-4 presentation surfaces.
"""
from __future__ import annotations

import streamlit as st

import cfb_game_total_clean_page_v27 as prior

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V28 • VISUAL REDESIGN STEP 5 SYSTEM POLISH"
MARKET = prior.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v27"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ACTIVE_MARKER = "CFB GAME TOTAL • VISUAL REDESIGN STEP 5 SYSTEM POLISH ACTIVE"
STEP5_SYSTEM_POLISH_MARKER = "CFB_GAME_TOTAL_VISUAL_REDESIGN_STEP5_SYSTEM_POLISH_ACTIVE"

STEP5_SYSTEM_POLISH_CSS = r"""
<style>
:root{
  --gt228-radius-section:22px;
  --gt228-radius-card:16px;
  --gt228-gap-major:14px;
  --gt228-gap-card:12px;
  --gt228-border:rgba(83,166,205,.28);
  --gt228-teal:#27d8d0;
  --gt228-green:#45f0ad;
  --gt228-blue:#56b7ff;
  --gt228-purple:#a968ff;
  --gt228-text:#f7fbff;
  --gt228-muted:#89a1b5;
}

.gt225-hero,
.gt226-wrap,
.gt227-section{
  width:100%;
  box-sizing:border-box;
  margin-top:var(--gt228-gap-major)!important;
  border-radius:var(--gt228-radius-section)!important;
  backdrop-filter:blur(3px);
  -webkit-backdrop-filter:blur(3px);
}

.gt225-hero{
  margin-top:0!important;
  box-shadow:
    0 0 32px rgba(39,216,208,.08),
    0 18px 44px rgba(0,0,0,.22)!important;
}

.gt226-wrap,
.gt227-section{
  box-shadow:
    0 0 26px rgba(39,216,208,.045),
    0 15px 36px rgba(0,0,0,.18)!important;
}

.gt226-card,
.gt226-progress,
.gt226-badge,
.gt227-card,
.gt227-stat{
  border-radius:var(--gt228-radius-card)!important;
  transition:
    transform .16s ease,
    border-color .16s ease,
    box-shadow .16s ease,
    background .16s ease;
}

.gt226-card:hover,
.gt226-progress:hover,
.gt227-card:hover,
.gt227-stat:hover{
  transform:translateY(-1px);
  border-color:rgba(83,190,221,.38)!important;
  box-shadow:0 10px 24px rgba(0,0,0,.12);
}

.gt226-card:focus-within,
.gt226-progress:focus-within,
.gt227-card:focus-within{
  outline:2px solid rgba(69,240,173,.42);
  outline-offset:2px;
}

.gt225-name,
.gt226-title b,
.gt227-name,
.gt227-head b{
  text-rendering:optimizeLegibility;
  -webkit-font-smoothing:antialiased;
}

.gt225-name,
.gt226-value,
.gt227-stat b{
  font-variant-numeric:tabular-nums;
}

.gt225-topline,
.gt226-label,
.gt227-meta,
.gt227-stat label{
  letter-spacing:.055em!important;
}

.gt225-facts,
.gt226-progressrow,
.gt226-badges,
.gt227-stats{
  gap:var(--gt228-gap-card)!important;
}

.gt226-head,
.gt227-head{
  min-height:36px;
}

.gt226-title span,
.gt227-head span,
.gt225-record,
.gt227-meta,
.gt227-foot{
  color:var(--gt228-muted)!important;
}

.gt226-card.primary,
.gt226-card.lean{
  background:
    radial-gradient(circle at 88% 0%,rgba(69,240,173,.05),transparent 38%),
    linear-gradient(150deg,#091b28,#0a1b29 64%,#0a1728)!important;
}

.gt227-card.away{
  background:
    radial-gradient(circle at 5% 0%,rgba(255,174,64,.075),transparent 36%),
    linear-gradient(150deg,#0a1a27,#091925 68%,#0a1727)!important;
}

.gt227-card.home{
  background:
    radial-gradient(circle at 95% 0%,rgba(77,151,255,.085),transparent 36%),
    linear-gradient(150deg,#091a28,#091925 68%,#091728)!important;
}

.gt226-gauge,
.gt227-vs,
.gt225-vs{
  box-shadow:
    0 0 0 5px rgba(5,18,28,.24),
    0 0 22px rgba(39,216,208,.08)!important;
}

.gt226-bars .gt226-bar,
.gt227-track{
  overflow:hidden;
}

.gt226-cert,
.gt225-conf,
.gt227-record,
.gt226-grade{
  box-shadow:inset 0 0 0 1px rgba(255,255,255,.015);
}

.gt160-masthead{
  border-radius:0 0 14px 14px;
  box-shadow:0 10px 30px rgba(0,0,0,.24)!important;
}

@media(max-width:760px){
  .gt225-hero,
  .gt226-wrap,
  .gt227-section{
    border-radius:18px!important;
    margin-top:11px!important;
  }
  .gt225-hero{margin-top:0!important}
  .gt226-card,
  .gt226-progress,
  .gt226-badge,
  .gt227-card,
  .gt227-stat{
    border-radius:14px!important;
  }
}

@media(max-width:560px){
  .gt226-card:hover,
  .gt226-progress:hover,
  .gt227-card:hover,
  .gt227-stat:hover{
    transform:none;
  }
}
</style>
"""


def render_step6_cert_surface() -> None:
    return prior.render_step6_cert_surface()


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown(STEP5_SYSTEM_POLISH_CSS, unsafe_allow_html=True)
    result = prior.render_game_total_hub(section_header, status_info, team_logo, h)
    st.markdown(STEP5_SYSTEM_POLISH_CSS, unsafe_allow_html=True)
    return result


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Page V28 received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP5_SYSTEM_POLISH_CSS",
    "STEP5_SYSTEM_POLISH_MARKER",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_step6_cert_surface",
]
