"""CFB Game Total clean page V37 — Page 1 V2 Step 4 prediction + market comparison.

Presentation-only successor to frozen Step-3 Page V36. V37 replaces only the
legacy Game Total Analysis summary seam while delegating the Phoenix-time matchup
hero, multi-source data, and frozen analytics to V36.
"""
from __future__ import annotations

from threading import RLock
from typing import Any, Mapping

import streamlit as st

import cfb_game_total_clean_page_v26 as analysis_owner
import cfb_game_total_clean_page_v36 as prior
import cfb_game_total_page1_step4_prediction_market_v1 as prediction
import cfb_game_total_page1_step4_side_market_v1 as side_market

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V37 • PAGE1 V2 STEP4 PREDICTION MARKET"
MARKET = prior.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v36"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ACTIVE_MARKER = "CFB GAME TOTAL • PAGE1 V2 STEP4 PREDICTION MARKET ACTIVE"
STEP4_MARKER = prediction.STEP4_MARKER

_LOCK = RLock()

STEP4_CSS = r"""
<style>
.gt237-wrap{margin:12px auto 15px;padding:17px;border:1px solid rgba(80,199,255,.43);border-radius:20px;background:radial-gradient(circle at 12% 0%,rgba(48,213,255,.10),transparent 30%),radial-gradient(circle at 92% 0%,rgba(68,125,255,.12),transparent 28%),linear-gradient(145deg,#061725,#071421 60%,#081120);box-shadow:0 18px 42px rgba(0,0,0,.26),0 0 30px rgba(57,187,255,.06);color:#f7fbff}
.gt237-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:13px}.gt237-kicker{display:block;color:#55cffd;font-size:9px;font-weight:950;letter-spacing:.14em}.gt237-head h3{margin:3px 0 0;color:#f8fcff;font-size:17px;letter-spacing:.025em}.gt237-cert{flex:0 0 auto;padding:6px 10px;border:1px solid rgba(69,240,173,.38);border-radius:999px;background:rgba(24,111,76,.13);color:#45f0ad;font-size:9px;font-weight:950}
.gt237-primary{display:grid;grid-template-columns:1.08fr 1.12fr .72fr;gap:10px}.gt237-primary>div,.gt237-market>div{position:relative;min-width:0;padding:14px;border:1px solid rgba(83,164,205,.22);border-radius:14px;background:linear-gradient(150deg,#091b29,#081724)}.gt237-primary span,.gt237-market span{display:block;color:#8da6ba;font-size:9px;font-weight:900;letter-spacing:.065em;text-transform:uppercase}.gt237-primary strong{display:block;margin-top:7px;color:#f8fcff;font-size:25px;line-height:1.05;font-weight:1000}.gt237-projection strong{font-size:42px;color:#dff8ff;text-shadow:0 0 18px rgba(75,204,255,.13)}.gt237-primary small{display:block;margin-top:6px;color:#79a0b9;font-size:9px;line-height:1.3}.gt237-lean strong{color:#45f0ad}.gt237-lean b{position:absolute;right:12px;bottom:10px;color:#45f0ad;font-size:24px}.gt237-confidence strong{color:#71d7ff}.gt237-confidence small{color:#ffd35c;font-weight:850}
.gt237-market{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:10px}.gt237-market strong{display:block;margin-top:7px;color:#f3f9fd;font-size:13px;line-height:1.35;font-weight:950;white-space:normal}.gt237-foot{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-top:10px;padding:10px 12px;border-top:1px solid rgba(83,164,205,.16);color:#7693a8;font-size:8px;font-weight:850;letter-spacing:.035em}.gt237-foot span:first-child{color:#45f0ad}.gt237-foot span:nth-child(2){color:#a58cff}
@media(max-width:760px){.gt237-wrap{padding:12px;border-radius:17px}.gt237-primary{grid-template-columns:1fr 1fr}.gt237-confidence{grid-column:1/-1}.gt237-projection strong{font-size:36px}.gt237-market{grid-template-columns:1fr}.gt237-head h3{font-size:14px}}
@media(max-width:500px){.gt237-primary{grid-template-columns:1fr}.gt237-confidence{grid-column:auto}.gt237-projection strong{font-size:34px}.gt237-primary strong{font-size:22px}.gt237-head{align-items:flex-start}.gt237-cert{font-size:8px}.gt237-foot{display:grid;grid-template-columns:1fr}}
</style>
"""


def _step4_prediction_market_html(
    raw: Mapping[str, Any],
    final: Mapping[str, Any],
    display_game: Mapping[str, Any],
    statuses: Mapping[int, str],
    ready_count: int,
) -> str:
    enriched = side_market.enrich_verified_side_market(display_game)
    return prediction.build_prediction_market_html(
        raw,
        final,
        enriched,
        statuses,
        ready_count,
    )


def _render_with_step4_prediction_market(callback, *args, **kwargs):
    # V26 is the last owner of this renderer in the frozen V36 -> V35 -> ... chain.
    # Patching V9 directly is ineffective because V26 overwrites that seam later.
    with _LOCK:
        original = analysis_owner._game_total_analysis_html_v26
        analysis_owner._game_total_analysis_html_v26 = _step4_prediction_market_html
        try:
            return callback(*args, **kwargs)
        finally:
            analysis_owner._game_total_analysis_html_v26 = original


def render_step6_cert_surface() -> None:
    return prior.render_step6_cert_surface()


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown(STEP4_CSS, unsafe_allow_html=True)
    result = _render_with_step4_prediction_market(
        prior.render_game_total_hub,
        section_header,
        status_info,
        team_logo,
        h,
    )
    st.markdown(STEP4_CSS, unsafe_allow_html=True)
    return result


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"Page V37 received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP4_CSS",
    "STEP4_MARKER",
    "_render_with_step4_prediction_market",
    "_step4_prediction_market_html",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_step6_cert_surface",
]
