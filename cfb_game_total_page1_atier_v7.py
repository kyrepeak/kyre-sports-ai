"""CFB Game Total Page 1 A-tier V7 — readability and visual hierarchy pass.

Presentation-only successor over V6. It preserves the existing horizontal
matchup rail and Decision Card structure while increasing logos, typography,
spacing, and action-control size for tablet/mobile readability.
"""
from __future__ import annotations

import streamlit as st

import cfb_game_total_page1_atier_v6 as prior

MODEL_VERSION = "CFB GAME TOTAL PAGE1 A-TIER V7 • S-TIER READABILITY R1"
MARKET = prior.MARKET
PAGE1_ENDPOINT = prior.PAGE1_ENDPOINT
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
MAY_MODIFY_SELECTED_GAME_RUNTIME = False

_READABILITY_CSS = r"""
<style>
/* Matchup rail: preserve horizontal swipe behavior while making identity readable. */
.cfbgt5-rail{gap:12px!important;padding-top:6px!important;padding-bottom:14px!important}
.cfbgt5-chip{flex-basis:228px!important;width:228px!important;height:104px!important;gap:10px!important;padding:12px 14px!important;border-radius:16px!important}
.cfbgt5-matchrow{gap:9px!important}
.cfbgt5-team-logo{width:46px!important;height:46px!important;flex-basis:46px!important;font-size:12px!important}
.cfbgt5-team-logo img{inset:2px!important;width:42px!important;height:42px!important}
.cfbgt5-abbr{font-size:17px!important;max-width:58px!important;line-height:1.05!important}
.cfbgt5-at{font-size:14px!important}
.cfbgt5-time{font-size:13px!important;line-height:1.1!important}
.cfbgt5-selected-label{font-size:12px!important;margin-top:7px!important}

/* Selected matchup header. */
.cfbgt6-head{gap:14px!important;padding:16px 18px!important}
.cfbgt6-match{gap:10px!important}
.cfbgt6-team-logo{width:52px!important;height:52px!important;flex-basis:52px!important;font-size:13px!important}
.cfbgt6-team-logo img{inset:3px!important;width:46px!important;height:46px!important}
.cfbgt6-team{font-size:20px!important;max-width:210px!important;line-height:1.1!important}
.cfbgt6-at{font-size:15px!important}
.cfbgt6-kick{font-size:13px!important;margin-top:6px!important}
.cfbgt6-badge{font-size:11px!important;padding:7px 10px!important}

/* Primary decision metrics. */
.cfbgt6-primary{gap:10px!important;padding:14px!important}
.cfbgt6-metric{min-height:92px!important;padding:13px!important;border-radius:14px!important}
.cfbgt6-metric small{font-size:12px!important;letter-spacing:.055em!important}
.cfbgt6-metric strong{font-size:28px!important;margin-top:8px!important;line-height:1.05!important}
.cfbgt6-metric em{font-size:12px!important;margin-top:5px!important;line-height:1.25!important}
.cfbgt6-prob strong{font-size:22px!important;line-height:1.25!important}

/* Model tilt and supporting market context. */
.cfbgt6-tilt{margin:0 14px 11px!important;padding:12px 13px!important;border-radius:13px!important}
.cfbgt6-tilt small{font-size:11px!important}
.cfbgt6-tilt b{font-size:14px!important}
.cfbgt6-modelbar{height:8px!important;margin-top:9px!important}
.cfbgt6-tilt-note{font-size:12px!important;margin-top:7px!important;line-height:1.45!important}
.cfbgt6-secondary{gap:9px!important;margin:0 14px 11px!important}
.cfbgt6-secondary>div{padding:10px 11px!important;border-radius:11px!important}
.cfbgt6-secondary small{font-size:11px!important}
.cfbgt6-secondary strong{font-size:14px!important;margin-top:5px!important;line-height:1.25!important}
.cfbgt6-foot{gap:12px!important;padding:0 14px 14px!important}
.cfbgt6-proof{font-size:11px!important}
.cfbgt6-open{display:inline-flex!important;min-width:150px!important;min-height:42px!important;padding:0 16px!important;font-size:12px!important;letter-spacing:.045em!important}

/* Tablet/mobile floors: scale down gently, never back to microscopic type. */
@media(max-width:620px){
  .cfbgt5-chip{flex-basis:214px!important;width:214px!important;height:100px!important;padding:11px 12px!important}
  .cfbgt5-team-logo{width:42px!important;height:42px!important;flex-basis:42px!important}
  .cfbgt5-team-logo img{width:38px!important;height:38px!important}
  .cfbgt5-abbr{font-size:16px!important;max-width:55px!important}
  .cfbgt5-at{font-size:13px!important}
  .cfbgt5-time{font-size:13px!important}
  .cfbgt6-head{padding:14px 12px!important}
  .cfbgt6-team-logo{width:48px!important;height:48px!important;flex-basis:48px!important}
  .cfbgt6-team-logo img{width:42px!important;height:42px!important}
  .cfbgt6-team{font-size:18px!important;max-width:125px!important}
  .cfbgt6-at{font-size:14px!important}
  .cfbgt6-kick{font-size:13px!important}
  .cfbgt6-badge{font-size:10px!important}
  .cfbgt6-primary{gap:7px!important;padding:10px!important}
  .cfbgt6-metric{min-height:84px!important;padding:10px 8px!important}
  .cfbgt6-metric small{font-size:11px!important}
  .cfbgt6-metric strong{font-size:24px!important}
  .cfbgt6-metric em{font-size:11px!important}
  .cfbgt6-prob strong{font-size:18px!important}
  .cfbgt6-tilt{margin:0 10px 9px!important;padding:11px!important}
  .cfbgt6-tilt small{font-size:10px!important}
  .cfbgt6-tilt b{font-size:13px!important}
  .cfbgt6-tilt-note{font-size:11px!important}
  .cfbgt6-secondary{grid-template-columns:1fr!important;gap:7px!important;margin:0 10px 9px!important}
  .cfbgt6-secondary small{font-size:11px!important}
  .cfbgt6-secondary strong{font-size:14px!important}
  .cfbgt6-proof{font-size:10px!important}
  .cfbgt6-open{min-width:142px!important;min-height:42px!important;font-size:12px!important}
}
@media(max-width:390px){
  .cfbgt5-chip{flex-basis:202px!important;width:202px!important}
  .cfbgt6-team{font-size:17px!important;max-width:96px!important}
  .cfbgt6-primary{grid-template-columns:1fr 1fr!important}
  .cfbgt6-prob{grid-column:1/-1!important}
  .cfbgt6-foot{align-items:flex-start!important;flex-direction:column!important}
  .cfbgt6-open{width:100%!important;box-sizing:border-box!important}
}
</style>
"""


def render_game_total_page1() -> None:
    st.markdown(_READABILITY_CSS, unsafe_allow_html=True)
    prior.render_game_total_page1()


def render_cfb_hub(market: str, *args, **kwargs) -> None:
    del args, kwargs
    if market != MARKET:
        raise ValueError(f"CFB Game Total A-tier V7 cannot render market={market!r}")
    render_game_total_page1()


__all__ = [
    "MARKET",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_RANKING",
    "MAY_MODIFY_SELECTION",
    "MODEL_VERSION",
    "PAGE1_ENDPOINT",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "render_cfb_hub",
    "render_game_total_page1",
]
