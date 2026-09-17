"""CFB Game Total Clean Page V11 — V161 visible game-day navigation.

Additive successor to frozen V160. V161 preserves the complete V160/V159 data,
model, distribution, qualification, ranking, and evidence flow. It only adds a
visible seven-day slate selector and removes the V160 Monster masthead from the
Game Total surface.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Mapping

import streamlit as st

import cfb_game_total_clean_page_v10 as prior

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V11 • V161 GAME-DAY NAVIGATION"
MARKET = prior.MARKET
FROZEN_GAME_TOTAL_HUB = prior.FROZEN_GAME_TOTAL_HUB
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v10"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

ACTIVE_MARKER = "CFB GAME TOTAL • CLEAN PAGE V161 ACTIVE"
V161_GAME_DAY = "cfb_game_total_v161_game_day"
V161_REQUIRED_MARKERS = (
    ACTIVE_MARKER,
    "GAME TOTAL ANALYSIS",
    "TEAM EVIDENCE",
    "GAME TOTAL EVIDENCE • STEPS 1–12",
    "FINAL MODEL SUMMARY",
    "TOP-5 SLATE SCANNER",
)

_V161_DAY_CSS = r"""
<style>
.gt161-daybar{margin:0 auto 8px;max-width:900px;padding:2px 2px 0}
.gt161-daybar-label{color:#8fa7bd;font-size:9px;font-weight:900;letter-spacing:.11em;margin:0 0 5px 2px;text-transform:uppercase}
.gt161-identity{display:none!important}
div[data-testid="stHorizontalBlock"] button[kind="secondary"]{min-height:42px!important;padding:5px 3px!important;border:1px solid rgba(79,153,194,.34)!important;border-radius:9px!important;background:#071824!important;color:#b8c9d7!important;font-size:11px!important;font-weight:900!important}
div[data-testid="stHorizontalBlock"] button[kind="primary"]{min-height:42px!important;padding:5px 3px!important;border:1px solid rgba(69,240,173,.70)!important;border-radius:9px!important;background:linear-gradient(145deg,rgba(19,105,76,.70),rgba(7,35,40,.95))!important;color:#f7fbff!important;font-size:11px!important;font-weight:950!important;box-shadow:0 0 14px rgba(69,240,173,.12)!important}
@media(max-width:760px){
  .gt161-daybar{padding:0 5px;margin-bottom:6px}.gt161-daybar-label{font-size:8px;margin-bottom:4px}
  div[data-testid="stHorizontalBlock"]{gap:3px!important}
  div[data-testid="stHorizontalBlock"] button[kind="secondary"],div[data-testid="stHorizontalBlock"] button[kind="primary"]{min-height:38px!important;padding:3px 1px!important;font-size:9px!important;border-radius:7px!important}
}
</style>
"""


def _default_game_day():
    return datetime.now().date()


def _render_game_day_strip():
    selected_date = st.session_state.get(V161_GAME_DAY, _default_game_day())
    if isinstance(selected_date, datetime):
        selected_date = selected_date.date()

    # Keep the chosen day inside the visible rolling seven-day window.
    start_date = _default_game_day()
    if selected_date < start_date or selected_date > start_date + timedelta(days=6):
        start_date = selected_date

    st.markdown(
        '<div class="gt161-daybar"><div class="gt161-daybar-label">Game day</div></div>',
        unsafe_allow_html=True,
    )
    columns = st.columns(7)
    for offset in range(7):
        game_day = start_date + timedelta(days=offset)
        label = f"{game_day.strftime('%a')}  {game_day.month}/{game_day.day}"
        with columns[offset]:
            if st.button(
                label,
                key=f"gt161-day-{game_day.isoformat()}",
                type="primary" if game_day == selected_date else "secondary",
                use_container_width=True,
            ):
                st.session_state[V161_GAME_DAY] = game_day
                selected_date = game_day
    st.session_state[V161_GAME_DAY] = selected_date
    return selected_date


def _render_v161_identity() -> None:
    st.markdown(
        '<div class="gt161-identity" data-testid="cfb-game-total-v161-active">'
        f'<b>{ACTIVE_MARKER}</b><span>V160 presentation inherited • V159 math frozen • sportsbook 0.0%</span></div>',
        unsafe_allow_html=True,
    )


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    # V161 owns only the visible day control and masthead suppression. The frozen
    # V159 renderer still owns schedule lookup, evidence, model, and Top-5 logic.
    st.markdown(prior._V160_CSS, unsafe_allow_html=True)
    st.markdown(_V161_DAY_CSS, unsafe_allow_html=True)
    selected_date = _render_game_day_strip()
    _render_v161_identity()

    frozen = prior.prior
    captured: dict[str, Mapping[str, Any]] = {}
    original_date_input = frozen.st.date_input
    original_selectbox = frozen.st.selectbox
    original_expander = frozen.st.expander
    original_matchup = frozen._matchup_header_html
    original_team_evidence = frozen._team_evidence_html
    diagnostic_owner = frozen.frozen_page.frozen_v2.frozen_v1.identity_ui
    original_diagnostics = diagnostic_owner._diagnostic_badges

    def date_input_wrapper(*_args, **_kwargs):
        return selected_date

    def matchup_wrapper(identity, away, home, display_game):
        captured["identity"] = identity
        return prior._target_matchup_header_html(identity, away, home, display_game)

    def team_evidence_wrapper(away, home):
        return prior._target_team_evidence_html(captured.get("identity", {}), away, home)

    frozen.st.date_input = date_input_wrapper
    frozen.st.selectbox = st.sidebar.selectbox
    frozen.st.expander = st.sidebar.expander
    frozen._matchup_header_html = matchup_wrapper
    frozen._team_evidence_html = team_evidence_wrapper
    diagnostic_owner._diagnostic_badges = lambda _diag: ""
    try:
        result = frozen.render_game_total_hub(section_header, status_info, team_logo, h)
    finally:
        frozen.st.date_input = original_date_input
        frozen.st.selectbox = original_selectbox
        frozen.st.expander = original_expander
        frozen._matchup_header_html = original_matchup
        frozen._team_evidence_html = original_team_evidence
        diagnostic_owner._diagnostic_badges = original_diagnostics

    # Frozen V9 emits its own stylesheet during render. Re-emit V160 + V161 last
    # so presentation parity wins the cascade without mutating either frozen file.
    st.markdown(prior._V160_CSS, unsafe_allow_html=True)
    st.markdown(_V161_DAY_CSS, unsafe_allow_html=True)
    return result


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"V161 Game Total V11 page received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "MODEL_VERSION",
    "MARKET",
    "FROZEN_GAME_TOTAL_HUB",
    "FROZEN_PRESENTATION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "MAY_MODIFY_PROJECTION",
    "ACTIVE_MARKER",
    "V161_GAME_DAY",
    "V161_REQUIRED_MARKERS",
    "render_game_total_hub",
    "render_cfb_hub",
]
