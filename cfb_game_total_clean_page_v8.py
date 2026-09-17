"""CFB Game Total Clean Page V8 — compact Steps 11–12 final summary.

Presentation-only wrapper over frozen V7. V8 replaces only the visible model
status block with compact Step 11 / Step 12 cards and one connected final model
summary. Frozen Game Total analysis, qualification, distribution, final math,
and Top-5 behavior remain owned by the inherited V7/V6 path.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import cfb_game_total_clean_page_v1 as status_owner
import cfb_game_total_clean_page_v7 as prior

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V8 • V156 COMPACT FINAL SUMMARY"
MARKET = prior.MARKET
FROZEN_GAME_TOTAL_HUB = prior.FROZEN_GAME_TOTAL_HUB
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v7"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

frozen_page = prior.frozen_page
logo_v3 = prior.logo_v3
runtime_display = prior.runtime_display

_V156_CSS = r"""
<style>
.gt156-model{margin:9px 0 2px;padding-top:8px;border-top:1px solid rgba(121,146,169,.12)}
.gt156-head{display:flex;align-items:flex-end;justify-content:space-between;gap:8px;margin:0 2px 6px}.gt156-head b{color:#edf4fa;font-size:.50rem;font-weight:950;letter-spacing:.06em}.gt156-head span{color:var(--gt-gray);font-size:.27rem}
.gt156-model-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.gt156-model-card{border:1px solid rgba(116,145,170,.15);border-radius:11px;background:#0a1823;padding:8px 9px;min-width:0}.gt156-model-card.ready{border-color:rgba(60,207,137,.24);background:linear-gradient(145deg,rgba(17,72,51,.17),#0a1823)}.gt156-model-card.gated{border-color:rgba(244,191,77,.23);background:linear-gradient(145deg,rgba(101,72,18,.13),#0a1823)}
.gt156-cardtop{display:flex;align-items:center;justify-content:space-between;gap:7px}.gt156-cardtop small{color:var(--gt-gray);font-size:.24rem;font-weight:950;letter-spacing:.05em}.gt156-badge{padding:3px 6px;border-radius:999px;font-size:.25rem;font-weight:950;white-space:nowrap}.gt156-badge.ready{background:rgba(34,197,94,.13);color:var(--gt-green)}.gt156-badge.gated{background:rgba(245,158,11,.13);color:var(--gt-amber)}
.gt156-main{display:flex;align-items:baseline;gap:6px;margin-top:5px}.gt156-main b{color:#f5f9fc;font-size:.78rem;font-weight:950}.gt156-main span{color:var(--gt-gray);font-size:.25rem}.gt156-reason{margin-top:4px;color:#8396a7;font-size:.27rem;line-height:1.4}
.gt156-final{margin-top:6px;border:1px solid rgba(160,112,255,.22);border-radius:11px;background:linear-gradient(145deg,rgba(75,41,127,.18),#0a1723);padding:8px 9px}.gt156-finaltop{display:flex;align-items:center;justify-content:space-between;gap:8px}.gt156-finaltop b{color:#d9c8ff;font-size:.34rem;font-weight:950;letter-spacing:.06em}.gt156-finaltop span{color:var(--gt-purple);font-size:.25rem;font-weight:950}.gt156-finalgrid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:4px;margin-top:6px}.gt156-metric{background:#102330;border-radius:7px;padding:5px;min-width:0}.gt156-metric b{display:block;color:#edf4f9;font-size:.40rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.gt156-metric span{display:block;color:var(--gt-gray);font-size:.19rem;font-weight:850;text-transform:uppercase;margin-top:2px}
.gt156-note{margin-top:6px;color:#7f91a1;font-size:.23rem;line-height:1.4}.gt156-note strong{color:var(--gt-purple)}
@media(max-width:760px){.gt156-model-grid{grid-template-columns:1fr}.gt156-finalgrid{grid-template-columns:repeat(2,minmax(0,1fr))}.gt156-finalgrid .gt156-metric:first-child{grid-column:1/-1}.gt156-head{align-items:flex-start;flex-direction:column;gap:2px}}
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


def _compact_model_summary(raw: Mapping[str, Any], final: Mapping[str, Any]) -> str:
    """Re-present existing frozen Step 11/12 fields without changing truth."""
    step11_ready = bool(raw.get("ready"))
    step12_ready = bool(final.get("ready"))

    step11_reason = (
        "Distribution ready • frozen model output preserved"
        if step11_ready
        else " • ".join(str(x) for x in raw.get("reasons") or ["Distribution inputs incomplete"])
    )
    step12_reason = (
        "Final synthesis ready • frozen qualification preserved"
        if step12_ready
        else " • ".join(str(x) for x in final.get("reasons") or ["Final qualification unavailable"])
    )

    projected = final.get("projected_combined_total") if step12_ready else raw.get("projected_combined_total")
    core = final.get("core_50_range") or {}
    band = final.get("most_likely_band") or {}
    grade = _clean(final.get("grade")) if step12_ready else "—"
    strength = _pct(final.get("forecast_strength")) if step12_ready else "—"
    core_text = (
        f"{int(core.get('low') or 0)}–{int(core.get('high') or 0)}"
        if step12_ready and core
        else "—"
    )
    band_text = _clean(band.get("label")) if step12_ready else "—"
    final_state = "FINAL READY" if step12_ready else ("DISTRIBUTION READY" if step11_ready else "GATED")

    return _V156_CSS + f"""
<div class="gt156-model" data-testid="gt156-model-flow">
  <div class="gt156-head"><b>🧠 MODEL EVIDENCE</b><span>Frozen Step 11 → Step 12 • compact presentation only</span></div>
  <div class="gt156-model-grid">
    <div class="gt156-model-card {'ready' if step11_ready else 'gated'}" data-testid="gt156-step11-card">
      <div class="gt156-cardtop"><small>STEP 11 • DISTRIBUTION</small><span class="gt156-badge {'ready' if step11_ready else 'gated'}">{'READY' if step11_ready else 'GATED'}</span></div>
      <div class="gt156-main"><b>{escape(_num(raw.get('projected_combined_total')))}</b><span>projected combined total</span></div>
      <div class="gt156-reason">{escape(step11_reason)}</div>
    </div>
    <div class="gt156-model-card {'ready' if step12_ready else 'gated'}" data-testid="gt156-step12-card">
      <div class="gt156-cardtop"><small>STEP 12 • FINAL SYNTHESIS</small><span class="gt156-badge {'ready' if step12_ready else 'gated'}">{'READY' if step12_ready else 'GATED'}</span></div>
      <div class="gt156-main"><b>{escape(_num(projected))}</b><span>{'qualified forecast' if step12_ready else 'final forecast gated'}</span></div>
      <div class="gt156-reason">{escape(step12_reason)}</div>
    </div>
  </div>
  <div class="gt156-final" data-testid="gt156-final-summary">
    <div class="gt156-finaltop"><b>FINAL • MODEL SUMMARY</b><span>{escape(final_state)}</span></div>
    <div class="gt156-finalgrid">
      <div class="gt156-metric"><b>{escape(_num(projected))}</b><span>Projection</span></div>
      <div class="gt156-metric"><b>{escape(core_text)}</b><span>Core 50%</span></div>
      <div class="gt156-metric"><b>{escape(band_text or '—')}</b><span>Likely band</span></div>
      <div class="gt156-metric"><b>{escape(grade or '—')}</b><span>Grade</span></div>
      <div class="gt156-metric"><b>{escape(strength)}</b><span>Strength</span></div>
    </div>
    <div class="gt156-note"><strong>0.0% sportsbook projection influence.</strong> Deep Step 11 and Step 12 evidence remains available in the inherited collapsed expanders below.</div>
  </div>
</div>
"""


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    """Run frozen V7 while swapping only the visible model-status presenter."""
    original_status_cards = status_owner._status_cards
    status_owner._status_cards = _compact_model_summary
    try:
        return prior.render_game_total_hub(section_header, status_info, team_logo, h)
    finally:
        status_owner._status_cards = original_status_cards


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"V156 Game Total V8 page received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "render_cfb_hub",
    "render_game_total_hub",
]
