"""CFB Game Total clean page V26 — visual redesign Step 3 Game Total Analysis.

Presentation-only successor to V25. The certified data/model/runtime contracts
remain frozen. V26 replaces only the Game Total Analysis summary renderer while
delegating matchup hero, Team Evidence, provenance, and Steps 1-12 to V25.
"""
from __future__ import annotations

from html import escape
from threading import RLock
from typing import Any, Mapping

import streamlit as st

import cfb_game_total_clean_page_v9 as analysis_owner
import cfb_game_total_clean_page_v25 as prior

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V26 • VISUAL REDESIGN STEP 3 GAME TOTAL ANALYSIS"
MARKET = prior.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v25"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ACTIVE_MARKER = "CFB GAME TOTAL • VISUAL REDESIGN STEP 3 GAME TOTAL ANALYSIS ACTIVE"
STEP3_GAME_TOTAL_ANALYSIS_MARKER = "CFB_GAME_TOTAL_VISUAL_REDESIGN_STEP3_GAME_TOTAL_ANALYSIS_ACTIVE"

_PRESENTATION_LOCK = RLock()

STEP3_GAME_TOTAL_ANALYSIS_CSS = r"""
<style>
.gt226-wrap{
  margin-top:14px;
  padding:18px;
  border:1px solid rgba(39,216,208,.46);
  border-left:3px solid #27d8d0;
  border-right:2px solid rgba(169,104,255,.75);
  border-radius:22px;
  background:
    radial-gradient(circle at 12% 0%,rgba(39,216,208,.10),transparent 34%),
    radial-gradient(circle at 92% 0%,rgba(169,104,255,.10),transparent 32%),
    linear-gradient(145deg,#061823,#071522 58%,#0b1125);
  box-shadow:0 0 32px rgba(39,216,208,.07),0 16px 38px rgba(0,0,0,.20);
  color:#f7fbff;
}
.gt226-head{
  display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px;
}
.gt226-title{display:flex;align-items:center;gap:10px;min-width:0}
.gt226-title .icon{
  width:32px;height:32px;display:grid;place-items:center;border-radius:10px;
  border:1px solid rgba(69,240,173,.35);background:rgba(24,111,76,.14);color:#45f0ad;font-weight:950;
}
.gt226-title b{display:block;font-size:17px;letter-spacing:.04em;color:#f7fbff}
.gt226-title span{display:block;margin-top:3px;color:#7f99ad;font-size:10px}
.gt226-cert{
  flex:0 0 auto;padding:6px 11px;border-radius:999px;border:1px solid rgba(69,240,173,.46);
  background:rgba(18,112,76,.16);color:#45f0ad;font-size:10px;font-weight:950;
}
.gt226-grid{
  display:grid;grid-template-columns:1.15fr .82fr 1.1fr;gap:12px;
}
.gt226-card{
  position:relative;min-width:0;padding:15px;border:1px solid rgba(86,160,202,.24);
  border-radius:16px;background:linear-gradient(150deg,#091b28,#0a1b29 64%,#0a1728);
  overflow:hidden;
}
.gt226-card:after{
  content:"";position:absolute;inset:0;pointer-events:none;
  background:radial-gradient(circle at 88% 0%,rgba(86,183,255,.08),transparent 38%);
}
.gt226-card.primary{border-color:rgba(69,240,173,.42);box-shadow:inset 0 0 24px rgba(69,240,173,.035)}
.gt226-card.lean{border-color:rgba(69,240,173,.38)}
.gt226-label{position:relative;z-index:1;color:#8ca3b8;font-size:10px;font-weight:900;letter-spacing:.06em;text-transform:uppercase}
.gt226-value{position:relative;z-index:1;margin-top:8px;color:#f7fbff;font-size:30px;line-height:1;font-weight:1000}
.gt226-card.primary .gt226-value{font-size:54px;color:#dffdf1;text-shadow:0 0 20px rgba(69,240,173,.12)}
.gt226-sub{position:relative;z-index:1;margin-top:7px;color:#76d6b1;font-size:11px;font-weight:800}
.gt226-wave{
  position:relative;z-index:1;height:28px;margin-top:12px;border-bottom:1px solid rgba(69,240,173,.20);
  background:
    linear-gradient(165deg,transparent 0 35%,rgba(69,240,173,.18) 36% 38%,transparent 39% 52%,rgba(69,240,173,.28) 53% 55%,transparent 56%);
  opacity:.8;
}
.gt226-leanrow{position:relative;z-index:1;display:flex;align-items:center;justify-content:space-between;gap:10px}
.gt226-leanrow .gt226-value{color:#45f0ad;font-size:27px}
.gt226-arrow{
  width:48px;height:48px;display:grid;place-items:center;border-radius:14px;
  border:1px solid rgba(69,240,173,.30);background:linear-gradient(145deg,rgba(69,240,173,.18),rgba(39,216,208,.07));
  color:#45f0ad;font-size:24px;font-weight:1000;box-shadow:0 0 18px rgba(69,240,173,.08);
}
.gt226-strong{
  position:relative;z-index:1;margin-top:12px;padding-top:10px;border-top:1px solid rgba(86,160,202,.16);
  color:#45f0ad;font-size:10px;font-weight:950;letter-spacing:.08em;
}
.gt226-confidence{
  display:grid;grid-template-columns:132px minmax(0,1fr);gap:14px;align-items:center;margin-top:12px;
}
.gt226-gauge{
  --gt226-confidence:0deg;
  width:118px;height:118px;border-radius:50%;display:grid;place-items:center;
  background:
    radial-gradient(circle at center,#081724 0 56%,transparent 57%),
    conic-gradient(#45f0ad 0 var(--gt226-confidence),rgba(73,112,139,.22) var(--gt226-confidence) 360deg);
  box-shadow:0 0 22px rgba(69,240,173,.10);
}
.gt226-gauge-inner{text-align:center}
.gt226-gauge-inner b{display:block;color:#f7fbff;font-size:24px;line-height:1;font-weight:1000}
.gt226-gauge-inner span{display:block;margin-top:4px;color:#7f99ad;font-size:8px;text-transform:uppercase}
.gt226-confcopy b{display:block;color:#f7fbff;font-size:14px}
.gt226-confcopy span{display:block;margin-top:5px;color:#7f99ad;font-size:10px;line-height:1.35}
.gt226-grade{display:inline-block;margin-top:9px;padding:4px 9px;border-radius:999px;border:1px solid rgba(255,210,77,.34);background:rgba(113,84,9,.15);color:#ffd24d;font-size:9px;font-weight:900}
.gt226-progressrow{
  display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px;
}
.gt226-progress{
  padding:14px;border:1px solid rgba(86,160,202,.22);border-radius:15px;background:#091a27;
}
.gt226-progresshead{display:flex;justify-content:space-between;gap:10px;color:#8ca3b8;font-size:10px;font-weight:900}
.gt226-progresshead b{color:#f7fbff;font-size:15px}
.gt226-bars{display:grid;grid-template-columns:repeat(12,1fr);gap:4px;margin-top:12px}
.gt226-bar{height:7px;border-radius:999px;background:rgba(75,112,138,.22)}
.gt226-bar.ready{background:linear-gradient(90deg,#27d8d0,#45f0ad);box-shadow:0 0 8px rgba(69,240,173,.12)}
.gt226-progress small{display:block;margin-top:9px;color:#7f99ad;font-size:9px}
.gt226-badges{
  display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;
}
.gt226-badge{
  padding:14px;border:1px solid rgba(86,160,202,.22);border-radius:15px;background:#091a27;color:#8fa7bd;font-size:9px;line-height:1.4;
}
.gt226-badge strong{display:block;margin-bottom:4px;color:#f7fbff;font-size:11px}
.gt226-badge.green{border-color:rgba(69,240,173,.28);background:rgba(24,111,76,.09)}
.gt226-badge.purple{border-color:rgba(169,104,255,.30);background:rgba(86,51,127,.10)}
@media(max-width:760px){
  .gt226-wrap{padding:13px;border-radius:18px}.gt226-grid{grid-template-columns:1fr 1fr}.gt226-card.lean{grid-column:1/-1}
  .gt226-card.primary .gt226-value{font-size:42px}.gt226-value{font-size:25px}.gt226-confidence{grid-template-columns:105px 1fr}
  .gt226-gauge{width:96px;height:96px}.gt226-gauge-inner b{font-size:20px}
}
@media(max-width:520px){
  .gt226-head{align-items:flex-start}.gt226-title b{font-size:14px}.gt226-title span{font-size:8px}.gt226-cert{font-size:8px;padding:5px 8px}
  .gt226-grid,.gt226-progressrow,.gt226-badges{grid-template-columns:1fr}
  .gt226-card.lean{grid-column:auto}.gt226-card.primary .gt226-value{font-size:38px}
  .gt226-confidence{grid-template-columns:88px 1fr}.gt226-gauge{width:82px;height:82px}.gt226-gauge-inner b{font-size:17px}
}
</style>
"""


def _clean(value: Any) -> str:
    return analysis_owner._clean(value)


def _confidence_fraction(final: Mapping[str, Any]) -> float | None:
    if not final.get("ready"):
        return None
    try:
        return max(0.0, min(1.0, float(final.get("forecast_strength"))))
    except (TypeError, ValueError):
        return None


def _game_total_analysis_html_v26(
    raw: Mapping[str, Any],
    final: Mapping[str, Any],
    display_game: Mapping[str, Any],
    statuses: Mapping[int, str],
    ready_count: int,
) -> str:
    projected_value = final.get("projected_combined_total") if final.get("ready") else raw.get("projected_combined_total")
    projected = analysis_owner._num(projected_value)
    market = analysis_owner._market_total(display_game)
    grade = _clean(final.get("grade")) if final.get("ready") else "—"
    confidence_fraction = _confidence_fraction(final)
    strength = analysis_owner._pct(final.get("forecast_strength")) if final.get("ready") else "—"
    confidence_degrees = 0.0 if confidence_fraction is None else confidence_fraction * 360.0

    if market is None:
        market_text = "—"
        lean = "Market total unavailable"
        lean_sub = "No verified line • model remains independent"
        arrow = "↔"
    else:
        market_text = analysis_owner._num(market)
        try:
            edge = float(projected_value) - market
            if edge > 0:
                lean = f"Over +{abs(edge):.1f}"
                lean_sub = "Slight Over Lean" if abs(edge) < 2 else "Over Lean"
                arrow = "↗"
            elif edge < 0:
                lean = f"Under -{abs(edge):.1f}"
                lean_sub = "Slight Under Lean" if abs(edge) < 2 else "Under Lean"
                arrow = "↘"
            else:
                lean, lean_sub, arrow = "Even 0.0", "No directional edge", "↔"
        except (TypeError, ValueError):
            lean, lean_sub, arrow = "Market total unavailable", "No verified line • model remains independent", "↔"

    ready_count = max(0, min(12, int(ready_count)))
    pending_count = 12 - ready_count
    bars = "".join(
        f'<span class="gt226-bar{" ready" if index < ready_count else ""}"></span>'
        for index in range(12)
    )

    return f"""
<div class="gt226-wrap" data-testid="gt226-game-total-analysis"
     data-step3-presentation="{STEP3_GAME_TOTAL_ANALYSIS_MARKER}">
  <div class="gt226-head">
    <div class="gt226-title">
      <span class="icon">⬢</span>
      <div><b>GAME TOTAL ANALYSIS</b><span>AI-powered analysis • frozen math • premium presentation</span></div>
    </div>
    <span class="gt226-cert">🛡 5M CERTIFIED</span>
  </div>

  <div class="gt226-grid">
    <div class="gt226-card primary">
      <div class="gt226-label">Projected Total</div>
      <div class="gt226-value">{escape(projected)}</div>
      <div class="gt226-sub">Model projection</div>
      <div class="gt226-wave"></div>
    </div>

    <div class="gt226-card">
      <div class="gt226-label">Market Total</div>
      <div class="gt226-value">{escape(market_text)}</div>
      <div class="gt226-sub">Current verified line</div>
    </div>

    <div class="gt226-card lean">
      <div class="gt226-label">Over / Under Lean</div>
      <div class="gt226-leanrow">
        <div>
          <div class="gt226-value">{escape(lean)}</div>
          <div class="gt226-sub">{escape(lean_sub)}</div>
        </div>
        <div class="gt226-arrow">{escape(arrow)}</div>
      </div>
      <div class="gt226-strong">MODEL LEAN • MARKET-INDEPENDENT</div>
    </div>
  </div>

  <div class="gt226-progressrow">
    <div class="gt226-progress">
      <div class="gt226-label">Confidence</div>
      <div class="gt226-confidence">
        <div class="gt226-gauge" style="--gt226-confidence:{confidence_degrees:.1f}deg">
          <div class="gt226-gauge-inner"><b>{escape(strength)}</b><span>confidence</span></div>
        </div>
        <div class="gt226-confcopy">
          <b>Model conviction</b>
          <span>Uses the existing certified forecast-strength value. Presentation only.</span>
          <span class="gt226-grade">Grade: {escape(grade or "—")}</span>
        </div>
      </div>
    </div>

    <div class="gt226-progress">
      <div class="gt226-progresshead"><span>Data Check Progress</span><b>{ready_count}/12 ready</b></div>
      <div class="gt226-bars">{bars}</div>
      <small>{pending_count} pending • existing Step readiness only</small>
    </div>
  </div>

  <div class="gt226-badges">
    <div class="gt226-badge green"><strong>⭐ 5M Certified</strong>Model validated • real data only</div>
    <div class="gt226-badge purple"><strong>▥ 0.0% sportsbook projection influence</strong>Independent analysis remains frozen</div>
  </div>
</div>"""


def _render_with_step3_game_total_analysis(callback, *args, **kwargs):
    with _PRESENTATION_LOCK:
        original = analysis_owner._game_total_hero_html
        analysis_owner._game_total_hero_html = _game_total_analysis_html_v26
        try:
            return callback(*args, **kwargs)
        finally:
            analysis_owner._game_total_hero_html = original


def render_step6_cert_surface() -> None:
    return prior.render_step6_cert_surface()


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown(STEP3_GAME_TOTAL_ANALYSIS_CSS, unsafe_allow_html=True)
    result = _render_with_step3_game_total_analysis(
        prior.render_game_total_hub,
        section_header,
        status_info,
        team_logo,
        h,
    )
    st.markdown(STEP3_GAME_TOTAL_ANALYSIS_CSS, unsafe_allow_html=True)
    return result


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Page V26 received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP3_GAME_TOTAL_ANALYSIS_CSS",
    "STEP3_GAME_TOTAL_ANALYSIS_MARKER",
    "_confidence_fraction",
    "_game_total_analysis_html_v26",
    "_render_with_step3_game_total_analysis",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_step6_cert_surface",
]
