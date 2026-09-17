"""CFB Game Total Clean Page V9 — connected all-steps flow.

Presentation-only wrapper over frozen V8. V9 removes only the duplicate visible
Steps 1–10 rail and re-presents the already-existing Step 1–10 readiness truth
beside frozen Step 11 distribution and Step 12 final synthesis in one connected
flow. Team evidence, raw evidence drawers, deep model evidence, final summary,
and the Top-5 scanner remain owned by the inherited V8/V7/V6 path.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import streamlit as st

import cfb_game_total_clean_page_v1 as status_owner
import cfb_game_total_clean_page_v6 as step_owner
import cfb_game_total_clean_page_v7 as evidence_owner
import cfb_game_total_clean_page_v8 as prior

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V9 • V157 CONNECTED ALL-STEPS FLOW"
MARKET = prior.MARKET
FROZEN_GAME_TOTAL_HUB = prior.FROZEN_GAME_TOTAL_HUB
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v8"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

frozen_page = prior.frozen_page
logo_v3 = prior.logo_v3
runtime_display = prior.runtime_display

_FLOW_CONTEXT_KEY = "cfb_game_total_v157_connected_flow_context"

_V157_CSS = r"""
<style>
.gt157-flow{margin:9px 0 3px;padding:10px;border:1px solid rgba(153,112,255,.22);border-radius:15px;background:linear-gradient(180deg,rgba(11,24,36,.98),rgba(7,17,27,.98))}
.gt157-head{display:flex;align-items:flex-end;justify-content:space-between;gap:8px;margin-bottom:8px}.gt157-head b{color:#eee8ff;font-size:.56rem;font-weight:950;letter-spacing:.06em}.gt157-head span{color:var(--gt-gray);font-size:.27rem;text-align:right}
.gt157-progress{display:flex;align-items:center;gap:5px;flex-wrap:wrap;margin-bottom:8px}.gt157-progress span{padding:4px 7px;border-radius:999px;background:rgba(93,63,145,.16);border:1px solid rgba(189,152,255,.17);color:#cdb9f3;font-size:.25rem;font-weight:900}.gt157-progress strong{color:#f2ecff}
.gt157-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px}.gt157-step{display:grid;grid-template-columns:28px minmax(0,1fr) auto;gap:7px;align-items:center;min-height:48px;padding:7px 8px;border:1px solid rgba(116,145,170,.14);border-radius:10px;background:#0a1823;position:relative;overflow:hidden}.gt157-step:before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--gt-blue)}.gt157-step.ready:before{background:var(--gt-green)}.gt157-step.check:before,.gt157-step.gated:before{background:var(--gt-amber)}
.gt157-num{display:flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:8px;background:rgba(119,185,232,.10);color:var(--gt-blue);font-size:.37rem;font-weight:950}.gt157-step.ready .gt157-num{background:rgba(38,111,77,.15);color:var(--gt-green)}.gt157-copy{min-width:0}.gt157-copy b{display:block;color:#edf4f9;font-size:.44rem;font-weight:950}.gt157-copy span{display:block;color:var(--gt-gray);font-size:.26rem;line-height:1.35;margin-top:2px;white-space:normal}.gt157-state{padding:3px 6px;border-radius:999px;font-size:.24rem;font-weight:950;white-space:nowrap}.gt157-state.ready{background:rgba(34,197,94,.13);color:var(--gt-green)}.gt157-state.check,.gt157-state.gated{background:rgba(245,158,11,.13);color:var(--gt-amber)}
.gt157-model{margin-top:7px;padding-top:7px;border-top:1px solid rgba(121,146,169,.13)}.gt157-final{margin-top:6px;border:1px solid rgba(160,112,255,.20);border-radius:11px;background:linear-gradient(145deg,rgba(75,41,127,.17),#0a1723);padding:8px}.gt157-finaltop{display:flex;align-items:center;justify-content:space-between;gap:8px}.gt157-finaltop b{color:#d9c8ff;font-size:.33rem;font-weight:950;letter-spacing:.05em}.gt157-finaltop span{color:var(--gt-purple);font-size:.24rem;font-weight:950}.gt157-finalgrid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:4px;margin-top:6px}.gt157-metric{background:#102330;border-radius:7px;padding:5px;min-width:0}.gt157-metric b{display:block;color:#edf4f9;font-size:.39rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.gt157-metric span{display:block;color:var(--gt-gray);font-size:.19rem;font-weight:850;text-transform:uppercase;margin-top:2px}
.gt157-top5{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:6px;padding:7px 8px;border:1px dashed rgba(119,185,232,.22);border-radius:9px;background:rgba(18,38,54,.38)}.gt157-top5 b{color:var(--gt-blue);font-size:.31rem;font-weight:950}.gt157-top5 span{color:var(--gt-gray);font-size:.24rem;text-align:right}.gt157-note{margin-top:6px;color:#7f91a1;font-size:.22rem;line-height:1.4}.gt157-note strong{color:var(--gt-purple)}
@media(max-width:760px){.gt157-grid{grid-template-columns:1fr}.gt157-head{align-items:flex-start;flex-direction:column}.gt157-head span{text-align:left}.gt157-finalgrid{grid-template-columns:repeat(2,minmax(0,1fr))}.gt157-finalgrid .gt157-metric:first-child{grid-column:1/-1}.gt157-top5{align-items:flex-start;flex-direction:column}.gt157-top5 span{text-align:left}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any) -> str:
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return "—"


def _pct(value: Any) -> str:
    try:
        return f"{100.0 * float(value):.1f}%"
    except (TypeError, ValueError):
        return "—"


def _capture_steps_1_10_context(
    identity: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    display_game: Mapping[str, Any],
) -> None:
    """Capture existing display truth and suppress only the old visible rail."""
    st.session_state[_FLOW_CONTEXT_KEY] = {
        "identity": dict(identity),
        "away": dict(away),
        "home": dict(home),
        "display_game": dict(display_game),
    }
    # Keep V7's compact team evidence exactly where it already lives.
    evidence_owner._render_compact_team_cards(away, home)


def _step_row(number: int, title: str, status: str, detail: str) -> str:
    state = "ready" if status == "READY" else ("gated" if status == "GATED" else "check")
    return f"""
<div class="gt157-step {state}" data-testid="gt157-step-{number}">
  <div class="gt157-num">{number}</div>
  <div class="gt157-copy"><b>STEP {number} • {escape(title)}</b><span>{escape(detail)}</span></div>
  <span class="gt157-state {state}">{escape(status)}</span>
</div>
"""


def _combined_flow_html(
    statuses: Mapping[int, str],
    details: Mapping[int, str],
    raw: Mapping[str, Any],
    final: Mapping[str, Any],
) -> str:
    """Build one presentation-only 1→12 flow from existing frozen truth."""
    rows: list[str] = []
    for number, title, _test_id in step_owner._STEP_1_10:
        rows.append(
            _step_row(
                number,
                title,
                _clean(statuses.get(number)) or "CHECK",
                _clean(details.get(number)) or "Verified evidence check",
            )
        )

    step11_ready = bool(raw.get("ready"))
    step12_ready = bool(final.get("ready"))
    step11_status = "READY" if step11_ready else "GATED"
    step12_status = "READY" if step12_ready else "GATED"
    step11_detail = (
        "Distribution ready • frozen model output preserved"
        if step11_ready
        else " • ".join(str(x) for x in raw.get("reasons") or ["Distribution inputs incomplete"])
    )
    step12_detail = (
        "Final synthesis ready • frozen qualification preserved"
        if step12_ready
        else " • ".join(str(x) for x in final.get("reasons") or ["Final qualification unavailable"])
    )
    rows.append(_step_row(11, "Distribution", step11_status, step11_detail))
    rows.append(_step_row(12, "Final Synthesis", step12_status, step12_detail))

    ready_count = sum(1 for number in range(1, 11) if statuses.get(number) == "READY")
    ready_count += int(step11_ready) + int(step12_ready)
    attention_count = 12 - ready_count

    projected = final.get("projected_combined_total") if step12_ready else raw.get("projected_combined_total")
    core = final.get("core_50_range") or {}
    band = final.get("most_likely_band") or {}
    core_text = (
        f"{int(core.get('low') or 0)}–{int(core.get('high') or 0)}"
        if step12_ready and core
        else "—"
    )
    band_text = _clean(band.get("label")) if step12_ready else "—"
    grade = _clean(final.get("grade")) if step12_ready else "—"
    strength = _pct(final.get("forecast_strength")) if step12_ready else "—"
    final_state = "FINAL READY" if step12_ready else ("DISTRIBUTION READY" if step11_ready else "GATED")

    return _V157_CSS + f"""
<div class="gt157-flow" data-testid="gt157-connected-all-steps">
  <div class="gt157-head">
    <b>🧩 CONNECTED GAME TOTAL FLOW • ALL STEPS</b>
    <span>Evidence → Distribution → Final → Top-5 • one scan</span>
  </div>
  <div class="gt157-progress">
    <span><strong>{ready_count}/12</strong> READY</span>
    <span><strong>{attention_count}</strong> CHECK / GATED</span>
    <span>0.0% sportsbook projection influence</span>
  </div>
  <div class="gt157-grid">{''.join(rows)}</div>
  <div class="gt157-model">
    <div class="gt157-final" data-testid="gt157-final-summary">
      <div class="gt157-finaltop"><b>FINAL • MODEL SUMMARY</b><span>{escape(final_state)}</span></div>
      <div class="gt157-finalgrid">
        <div class="gt157-metric"><b>{escape(_num(projected))}</b><span>Projection</span></div>
        <div class="gt157-metric"><b>{escape(core_text)}</b><span>Core 50%</span></div>
        <div class="gt157-metric"><b>{escape(band_text or '—')}</b><span>Likely band</span></div>
        <div class="gt157-metric"><b>{escape(grade or '—')}</b><span>Grade</span></div>
        <div class="gt157-metric"><b>{escape(strength)}</b><span>Strength</span></div>
      </div>
    </div>
    <div class="gt157-top5" data-testid="gt157-top5-connector">
      <b>TOP-5 • SLATE SCANNER</b><span>Frozen ranking unchanged • full scanner remains in the inherited drawer below</span>
    </div>
    <div class="gt157-note"><strong>Presentation only.</strong> Steps 1–10 reuse existing evidence readiness; Steps 11–12 reuse frozen model outputs. No projection, probability, qualification, or Top-5 calculation is changed.</div>
  </div>
</div>
"""


def _combined_model_summary(raw: Mapping[str, Any], final: Mapping[str, Any]) -> str:
    context = st.session_state.get(_FLOW_CONTEXT_KEY)
    if not isinstance(context, Mapping):
        return prior._compact_model_summary(raw, final)

    identity = context.get("identity") or {}
    away = context.get("away") or {}
    home = context.get("home") or {}
    display_game = context.get("display_game") or {}
    statuses = step_owner._existing_step_status(identity, away, home, display_game)
    details = step_owner._step_details(identity, away, home, statuses)
    return _combined_flow_html(statuses, details, raw, final)


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    """Run frozen V7 while V9 replaces V8's visible presenter deterministically."""
    original_steps = evidence_owner._render_steps_1_10_with_team_cards
    original_status_cards = status_owner._status_cards
    evidence_owner._render_steps_1_10_with_team_cards = _capture_steps_1_10_context
    status_owner._status_cards = _combined_model_summary
    try:
        # V8 adds presentation only. V9 supersedes that presenter, so delegate to
        # V7's frozen evidence path while keeping every V6/V5 model call intact.
        return evidence_owner.render_game_total_hub(section_header, status_info, team_logo, h)
    finally:
        evidence_owner._render_steps_1_10_with_team_cards = original_steps
        status_owner._status_cards = original_status_cards
        st.session_state.pop(_FLOW_CONTEXT_KEY, None)


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"V157 Game Total V9 page received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_combined_flow_html",
    "_combined_model_summary",
    "_capture_steps_1_10_context",
    "render_cfb_hub",
    "render_game_total_hub",
]
