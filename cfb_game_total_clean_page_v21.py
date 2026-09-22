"""CFB Game Total clean page V21 — page cleanup Step 2 presentation.

Additive presentation-only successor to V20. Step 1 data routing and frozen
Step-11/Step-12 math remain untouched. V21 only replaces the visible Game Total
Analysis hero with explicit READY/PENDING states and responsive status cards.
"""
from __future__ import annotations

from html import escape
from threading import RLock
from typing import Any, Mapping

import streamlit as st

import cfb_game_total_clean_page_v20 as prior

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V21 • PAGE CLEANUP STEP 2 PRESENTATION"
MARKET = prior.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v20"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ACTIVE_MARKER = "CFB GAME TOTAL • PAGE CLEANUP STEP 2 PRESENTATION ACTIVE"
STEP2_PRESENTATION_MARKER = "CFB_GAME_TOTAL_PAGE_CLEANUP_STEP2_PRESENTATION_ACTIVE"

STEP5_PRESENTATION_MARKER = prior.STEP5_PRESENTATION_MARKER
STEP5_DATA_MARKER = prior.STEP5_DATA_MARKER
STEP5_VISUAL_MARKER = prior.STEP5_VISUAL_MARKER
STEP6_PRESENTATION_MARKER = prior.STEP6_PRESENTATION_MARKER
STEP6_DATA_MARKER = prior.STEP6_DATA_MARKER
STEP6_VISUAL_MARKER = prior.STEP6_VISUAL_MARKER
STEP6_DEPLOYMENT_MARKER = prior.STEP6_DEPLOYMENT_MARKER
STEP6_VISUAL_PARITY_MARKER = prior.STEP6_VISUAL_PARITY_MARKER
STEP6_CERT_SURFACE_MARKER = prior.STEP6_CERT_SURFACE_MARKER

_step6_snapshot_row = prior._step6_snapshot_row
_step6_snapshot_bundle = prior._step6_snapshot_bundle
compact_owner = prior.compact_owner

_PRESENTATION_LOCK = RLock()

STEP2_PRESENTATION_CSS = r"""
<style>
.gt202-total{position:relative;overflow:hidden}
.gt202-total::before{content:"";position:absolute;inset:0 auto 0 0;width:3px;background:linear-gradient(180deg,var(--gt159-green),var(--gt159-purple));opacity:.95}
.gt202-totalgrid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:10px}
.gt202-metric{position:relative;min-width:0;padding:10px 11px;border:1px solid rgba(86,160,202,.24);border-radius:11px;background:linear-gradient(180deg,rgba(14,40,57,.94),rgba(8,28,42,.94))}
.gt202-metric[data-state="READY"]{border-color:rgba(98,239,182,.28)}
.gt202-metric[data-state="PENDING"]{border-color:rgba(244,206,99,.30);background:linear-gradient(180deg,rgba(53,43,17,.36),rgba(17,31,42,.94))}
.gt202-label{display:block;color:#8fa2b5;font-size:.27rem;text-transform:uppercase;font-weight:900;letter-spacing:.06em}
.gt202-value{display:block;margin-top:5px;color:#f6fbff;font-size:.86rem;line-height:1.05;font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.gt202-metric.projected .gt202-value{font-size:1.18rem;color:var(--gt159-green)}
.gt202-metric.lean .gt202-value{font-size:.68rem;color:var(--gt159-green)}
.gt202-metric[data-state="PENDING"] .gt202-value{color:var(--gt159-amber)}
.gt202-sub{display:block;margin-top:4px;color:#8096aa;font-size:.23rem;line-height:1.35}
.gt202-state{display:inline-flex;align-items:center;gap:4px;margin-top:7px;padding:3px 7px;border-radius:999px;border:1px solid rgba(98,239,182,.30);background:rgba(20,105,73,.16);color:var(--gt159-green);font-size:.20rem;font-weight:950;letter-spacing:.04em}
.gt202-state.pending{border-color:rgba(244,206,99,.32);background:rgba(113,84,9,.18);color:var(--gt159-amber)}
.gt202-grade{display:inline-block;margin-top:5px;color:#d6e3ed;font-size:.24rem;font-weight:850}
.gt202-badges{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin-top:9px}
.gt202-check[data-state="READY"]{border-color:rgba(98,239,182,.42);background:rgba(24,111,76,.20)}
.gt202-check[data-state="PENDING"]{border-color:rgba(244,206,99,.36);background:rgba(116,85,15,.15)}
@media (max-width:900px){
  .gt202-totalgrid{grid-template-columns:repeat(2,minmax(0,1fr))}
}
@media (max-width:600px){
  .gt202-totalgrid,.gt202-badges{grid-template-columns:1fr}
  .gt202-value{white-space:normal}
}
</style>
"""


def _clean(value: Any) -> str:
    return compact_owner._clean(value)


def _game_total_hero_html_v21(
    raw: Mapping[str, Any],
    final: Mapping[str, Any],
    display_game: Mapping[str, Any],
    statuses: Mapping[int, str],
    ready_count: int,
) -> str:
    del statuses

    projected_value = (
        final.get("projected_combined_total")
        if final.get("ready")
        else raw.get("projected_combined_total")
    )
    market = compact_owner._market_total(display_game)

    projected_ready = projected_value is not None
    market_ready = market is not None
    final_ready = bool(
        final.get("ready")
        and final.get("forecast_strength") is not None
    )

    projected_text = (
        compact_owner._num(projected_value)
        if projected_ready else "Pending"
    )
    market_text = (
        compact_owner._num(market)
        if market_ready else "Not posted"
    )

    if projected_ready and market_ready:
        edge = float(projected_value) - float(market)
        if edge > 0:
            lean_text = f"Over +{abs(edge):.1f}"
            lean_sub = "Slight Over Lean" if abs(edge) < 2 else "Over Lean"
        elif edge < 0:
            lean_text = f"Under -{abs(edge):.1f}"
            lean_sub = "Slight Under Lean" if abs(edge) < 2 else "Under Lean"
        else:
            lean_text = "Even 0.0"
            lean_sub = "No directional edge"
        lean_ready = True
    elif not projected_ready:
        lean_text = "Waiting on projection"
        lean_sub = (
            "Market verified • model projection pending"
            if market_ready
            else "Projection and market are still pending"
        )
        lean_ready = False
    else:
        lean_text = "Waiting on market"
        lean_sub = "Model ready • no verified market line posted"
        lean_ready = False

    confidence_text = (
        compact_owner._pct(final.get("forecast_strength"))
        if final_ready else "Pending"
    )
    grade_text = (
        _clean(final.get("grade")) or "Pending"
        if final_ready
        else "Pending"
    )

    checked = max(0, min(12, int(ready_count)))
    pending = max(0, 12 - checked)
    check_ready = checked == 12
    check_copy = (
        "All 12 required checks ready"
        if check_ready
        else f"{pending} required check{'s' if pending != 1 else ''} pending"
    )

    def metric(
        key: str,
        label: str,
        value: str,
        sub: str,
        ready: bool,
        extra_class: str = "",
        grade: str = "",
    ) -> str:
        state = "READY" if ready else "PENDING"
        state_class = "" if ready else " pending"
        grade_html = (
            f'<span class="gt202-grade">Grade: {escape(grade)}</span>'
            if grade else ""
        )
        return (
            f'<div class="gt202-metric {escape(extra_class)}" '
            f'data-metric="{escape(key)}" data-state="{state}">'
            f'<span class="gt202-label">{escape(label)}</span>'
            f'<b class="gt202-value">{escape(value)}</b>'
            f'<span class="gt202-sub">{escape(sub)}</span>'
            f'{grade_html}'
            f'<span class="gt202-state{state_class}">{state}</span>'
            f'</div>'
        )

    projected_card = metric(
        "projected-total",
        "Projected Total",
        projected_text,
        "Independent model projection",
        projected_ready,
        "projected",
    )
    market_card = metric(
        "market-total",
        "Market Total",
        market_text,
        "Verified sportsbook total" if market_ready else "No verified line currently posted",
        market_ready,
    )
    lean_card = metric(
        "lean",
        "Over / Under Lean",
        lean_text,
        lean_sub,
        lean_ready,
        "lean",
    )
    confidence_card = metric(
        "confidence",
        "Confidence",
        confidence_text,
        "Final synthesis confidence" if final_ready else "Final synthesis pending",
        final_ready,
        grade=grade_text,
    )

    check_state = "READY" if check_ready else "PENDING"
    return f"""
<div class="gt159-total gt202-total" data-testid="gt159-game-total-hero"
     data-step2-presentation="{STEP2_PRESENTATION_MARKER}"
     data-ready-count="{checked}" data-total-checks="12"
     data-analysis-state="{check_state}">
  <div class="gt159-totalhead">
    <span>⬢ GAME TOTAL ANALYSIS</span>
    <span class="gt159-cert">🛡 5M CERTIFIED</span>
  </div>
  <div class="gt202-totalgrid">
    {projected_card}
    {market_card}
    {lean_card}
    {confidence_card}
  </div>
  <div class="gt202-badges">
    <div class="gt159-badge">⭐ <strong>5M Certified</strong><br>Model validated • Real data only</div>
    <div class="gt159-badge purple">▥ <strong>0.0% sportsbook projection influence</strong><br>Independent analysis</div>
    <div class="gt159-badge gt202-check" data-state="{check_state}">
      ✓ <strong>{checked}/12 Data Check</strong><br>{escape(check_copy)}
    </div>
  </div>
</div>"""


def _render_with_v21_presentation(callback, *args, **kwargs):
    with _PRESENTATION_LOCK:
        original_hero = prior._game_total_hero_html_v20
        prior._game_total_hero_html_v20 = _game_total_hero_html_v21
        try:
            return callback(*args, **kwargs)
        finally:
            prior._game_total_hero_html_v20 = original_hero


def render_step6_cert_surface() -> None:
    # Frozen Step 6 production certification remains delegated through V20/V19.
    return prior.render_step6_cert_surface()


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown(STEP2_PRESENTATION_CSS, unsafe_allow_html=True)
    result = _render_with_v21_presentation(
        prior.render_game_total_hub,
        section_header,
        status_info,
        team_logo,
        h,
    )
    st.markdown(STEP2_PRESENTATION_CSS, unsafe_allow_html=True)
    return result


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(
            f"Page V21 received unsupported market: {market}"
        )
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP2_PRESENTATION_CSS",
    "STEP2_PRESENTATION_MARKER",
    "STEP5_DATA_MARKER",
    "STEP5_PRESENTATION_MARKER",
    "STEP5_VISUAL_MARKER",
    "STEP6_CERT_SURFACE_MARKER",
    "STEP6_DATA_MARKER",
    "STEP6_DEPLOYMENT_MARKER",
    "STEP6_PRESENTATION_MARKER",
    "STEP6_VISUAL_MARKER",
    "STEP6_VISUAL_PARITY_MARKER",
    "_game_total_hero_html_v21",
    "_step6_snapshot_bundle",
    "_step6_snapshot_row",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_step6_cert_surface",
]
