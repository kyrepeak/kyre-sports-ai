"""CFB Over/Under Intelligence V2 — Upgrade Step 4 pace UI.

Additive wrapper over permanently frozen multi-source logo hotfix V4 and
Upgrade Step 3.

Step 4 activates:
- NCAA offensive plays/game,
- NCAA Time of Possession -> seconds/offensive play,
- division-aware expected combined plays,
- small-sample shrinkage,
- bounded pace adjustment to the Step-3 projected total.

Direct possession/drive counts are displayed as unavailable rather than
fabricated until a certified source is added.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import streamlit as st

import cfb_over_under_matchup_ui_v3 as step3
import cfb_over_under_matchup_ui_v3_logo_hotfix_v4 as frozen_logo_v4
import cfb_over_under_pace_engine_v1 as pace_engine
import cfb_over_under_slate_v3 as upgraded_slate

MODEL_VERSION = "CFB OVER/UNDER INTELLIGENCE V2 • UPGRADE STEP 4 PACE"
FROZEN_UPGRADE = "cfb_over_under_matchup_ui_v3_logo_hotfix_v4"
MARKET = "Over/Under"

_FROZEN_LOGO_HERO = frozen_logo_v4._hero_with_multisource_logos
_FROZEN_STEP3_MODEL_CARD = step3._model_card_v3
_FROZEN_STEP3_COMPONENTS_PANEL = step3._components_panel_v3
_FROZEN_STEP3_FINAL_CARD = step3._final_card_v3

_CSS = r"""
<style>
.cfbou4-pace{margin:10px 0 2px;border:1px solid rgba(113,183,255,.28);border-radius:18px;
background:linear-gradient(145deg,#07131f,#0b1820 56%,#0c1716);overflow:hidden}
.cfbou4-head{display:flex;justify-content:space-between;gap:8px;align-items:center;padding:10px 12px;
border-bottom:1px solid rgba(113,183,255,.13)}
.cfbou4-head b{color:#82c9ff;font-size:.54rem;font-weight:950;letter-spacing:.08em}
.cfbou4-head span{border:1px solid #285572;border-radius:999px;padding:4px 7px;background:#0c2637;
color:#9dd7ff;font-size:.39rem;font-weight:950}
.cfbou4-sub{padding:7px 12px;color:#8195a0;font-size:.42rem;line-height:1.5;border-bottom:1px solid rgba(113,183,255,.08)}
.cfbou4-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding:10px}
.cfbou4-team{border:1px solid rgba(113,183,255,.14);border-radius:12px;background:#081721;padding:9px}
.cfbou4-team b{display:block;color:#edf8ff;font-size:.68rem}.cfbou4-team small{display:block;color:#6e8998;font-size:.34rem;margin-top:2px}
.cfbou4-team-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px;margin-top:7px}
.cfbou4-m{border:1px solid rgba(113,183,255,.10);border-radius:8px;background:#07131b;padding:6px}
.cfbou4-m strong{display:block;color:#cceeff;font-size:.57rem}.cfbou4-m span{display:block;color:#607b89;font-size:.30rem;text-transform:uppercase;margin-top:2px}
.cfbou4-main{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;padding:0 10px 10px}
.cfbou4-big{border:1px solid rgba(114,224,177,.15);border-radius:10px;background:#071913;padding:8px}
.cfbou4-big b{display:block;color:#dcfff0;font-size:.72rem}.cfbou4-big span{display:block;color:#719282;font-size:.31rem;text-transform:uppercase;margin-top:2px}
.cfbou4-foot{padding:8px 11px;border-top:1px solid rgba(113,183,255,.08);color:#687e89;font-size:.37rem;line-height:1.45}
.cfbou4-gate{margin:10px;border:1px solid #6c5720;border-radius:10px;background:#2b240d;color:#d9c477;padding:9px;font-size:.43rem;line-height:1.45}
.cfbou4-model{margin-top:10px;border:1px solid rgba(114,224,177,.25);border-radius:16px;background:linear-gradient(145deg,#071811,#071924,#091914);overflow:hidden}
.cfbou4-model-head{display:flex;justify-content:space-between;gap:8px;padding:10px 11px;border-bottom:1px solid rgba(114,224,177,.12)}
.cfbou4-model-head b{color:#8ee7bb;font-size:.52rem;font-weight:950;letter-spacing:.07em}.cfbou4-model-head span{color:#6c9681;font-size:.38rem;font-weight:900}
.cfbou4-model-main{display:grid;grid-template-columns:1.2fr 1fr;gap:8px;padding:10px}
.cfbou4-total,.cfbou4-prob{border:1px solid rgba(114,224,177,.12);border-radius:11px;background:#071713;padding:9px}
.cfbou4-total small,.cfbou4-prob small{display:block;color:#668779;font-size:.35rem;text-transform:uppercase;font-weight:900}
.cfbou4-total strong{display:block;color:#f3fff8;font-size:1.35rem;margin-top:3px}.cfbou4-total b{display:block;color:#90b6a5;font-size:.42rem;margin-top:4px}
.cfbou4-prob strong{display:block;color:#d8f5e7;font-size:.70rem;margin-top:5px}.cfbou4-prob b{display:block;color:#78988a;font-size:.38rem;margin-top:4px}
.cfbou4-model-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;padding:0 10px 10px}
.cfbou4-audit{margin-top:8px;border:1px solid rgba(113,183,255,.17);border-radius:12px;background:#08141c;padding:9px}
.cfbou4-audit b{color:#9bcce2;font-size:.46rem}.cfbou4-audit span{display:block;color:#6e8792;font-size:.37rem;line-height:1.45;margin-top:4px}
@media(max-width:760px){.cfbou4-grid{grid-template-columns:1fr}.cfbou4-main{grid-template-columns:repeat(2,minmax(0,1fr))}
.cfbou4-model-main{grid-template-columns:1fr}.cfbou4-model-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any, digits: int = 1) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return "—"


def _pct(value: Any) -> str:
    try:
        return f"{100.0 * float(value):.1f}%"
    except Exception:
        return "—"


def _seconds(value: Any) -> str:
    try:
        return f"{float(value):.1f}s"
    except Exception:
        return "—"


def _team_pace_html(team: Mapping[str, Any]) -> str:
    return f"""
<div class="cfbou4-team">
  <b>{escape(_clean(team.get('team')) or 'Team')}</b>
  <small>{escape(_clean(team.get('division')) or 'Division unavailable')} • NCAA pace evidence</small>
  <div class="cfbou4-team-grid">
    <div class="cfbou4-m"><strong>{_num(team.get('plays_per_game'))}</strong><span>Plays / game</span></div>
    <div class="cfbou4-m"><strong>{_seconds(team.get('seconds_per_offensive_play'))}</strong><span>TOP sec / play</span></div>
    <div class="cfbou4-m"><strong>{_num(team.get('pace_index'),2)}</strong><span>Division pace index</span></div>
  </div>
</div>
"""


def _pace_panel(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> str:
    pace = pace_engine.build_pace_engine(game, away, home)
    if not pace.get("model_ready"):
        return f"""
<div class="cfbou4-pace">
  <div class="cfbou4-head">
    <b>⏱️ UPGRADE STEP 4 • PACE / EXPECTED POSSESSIONS</b>
    <span>PACE ADJUSTMENT GATED</span>
  </div>
  <div class="cfbou4-gate">
    {escape(_clean(pace.get('reason')) or 'Verified pace evidence is below the minimum threshold')}.
    Step 3 remains the active projection for this matchup.
  </div>
</div>
"""

    adjustment = float(pace.get("total_points_adjustment") or 0.0)
    sign = "+" if adjustment > 0 else ""
    direct = (
        _num(pace.get("expected_combined_possessions"))
        if pace.get("direct_possessions_available")
        else "—"
    )
    return f"""
<div class="cfbou4-pace">
  <div class="cfbou4-head">
    <b>⏱️ UPGRADE STEP 4 • PACE / EXPECTED POSSESSIONS</b>
    <span>{escape(_clean(pace.get('pace_label')) or 'NEUTRAL')} • MAX ±{pace_engine.MAX_TOTAL_PACE_ADJUSTMENT:.2f} TOTAL PTS</span>
  </div>
  <div class="cfbou4-sub">
    NCAA Total Offense supplies offensive plays; NCAA Time of Possession supplies a clock/tempo check.
    Early-season pace is shrunk toward the correct FBS/FCS baseline. The analysis line has 0% pace weight.
  </div>
  <div class="cfbou4-grid">
    {_team_pace_html(pace.get('away') or {})}
    {_team_pace_html(pace.get('home') or {})}
  </div>
  <div class="cfbou4-main">
    <div class="cfbou4-big"><b>{_num(pace.get('expected_combined_plays'))}</b><span>Expected combined plays</span></div>
    <div class="cfbou4-big"><b>{_num(pace.get('division_baseline_combined_plays'))}</b><span>Division baseline plays</span></div>
    <div class="cfbou4-big"><b>{direct}</b><span>Direct expected possessions</span></div>
    <div class="cfbou4-big"><b>{sign}{adjustment:.2f}</b><span>Total pace adjustment</span></div>
  </div>
  <div class="cfbou4-foot">
    Historical combined plays {_num(pace.get('historical_combined_plays_per_game'))} •
    clock-implied combined plays {_num(pace.get('clock_implied_combined_plays'))} •
    sample factor {_pct(pace.get('sample_factor'))} • coverage {_pct(pace.get('coverage'))}.
    Direct possession/drive counts are not fabricated; they remain unavailable until a certified source is added.
  </div>
</div>
"""


def _hero_v4(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> str:
    return _FROZEN_LOGO_HERO(game, away, home) + _pace_panel(game, away, home)


def _model_card_v4(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    output: Mapping[str, Any],
) -> str:
    if not output.get("ready"):
        return _FROZEN_STEP3_MODEL_CARD(game, away, home, output)

    applied = bool(output.get("upgrade_step4_applied"))
    badge = "PACE ENGINE APPLIED" if applied else "STEP 3 FALLBACK"
    base_total = output.get("step4_base_projected_total")
    if base_total is None:
        base_total = output.get("projected_total")
    components = output.get("components") or {}

    return f"""
<div class="cfbou4-model">
  <div class="cfbou4-model-head">
    <b>STEP 4 • PACE-ADJUSTED OVER/UNDER MODEL</b>
    <span>{escape(badge)} • LINE WEIGHT 0%</span>
  </div>
  <div class="cfbou4-model-main">
    <div class="cfbou4-total">
      <small>Projected game total</small>
      <strong>{_num(output.get('projected_total'))}</strong>
      <b>Step 3 {_num(base_total)} → pace adjusted {_num(output.get('projected_total'))}</b>
    </div>
    <div class="cfbou4-prob">
      <small>Current O/U probabilities at analysis line {_num(output.get('analysis_line'))}</small>
      <strong>OVER {_pct(output.get('over_probability'))} • UNDER {_pct(output.get('under_probability'))}</strong>
      <b>{escape(_clean(output.get('model_lean')) or 'PASS')} lean • push {_pct(output.get('push_probability'))}</b>
    </div>
  </div>
  <div class="cfbou4-model-grid">
    <div class="cfbou4-m"><strong>{_num(output.get('projected_away_points'))}</strong><span>{escape(_clean(away.get('team')) or 'Away')} points</span></div>
    <div class="cfbou4-m"><strong>{_num(output.get('projected_home_points'))}</strong><span>{escape(_clean(home.get('team')) or 'Home')} points</span></div>
    <div class="cfbou4-m"><strong>{_num(output.get('expected_combined_plays'))}</strong><span>Expected plays</span></div>
    <div class="cfbou4-m"><strong>{_num(components.get('step4_total_pace_adjustment'),2)}</strong><span>Pace adjustment</span></div>
    <div class="cfbou4-m"><strong>{_num(components.get('step4_pace_ratio'),3)}</strong><span>Pace ratio</span></div>
    <div class="cfbou4-m"><strong>{_pct(output.get('pace_engine_coverage'))}</strong><span>Pace coverage</span></div>
    <div class="cfbou4-m"><strong>{_pct(output.get('reliability'))}</strong><span>Frozen reliability</span></div>
    <div class="cfbou4-m"><strong>0%</strong><span>Analysis-line model weight</span></div>
  </div>
</div>
"""


def _components_panel_v4(output: Mapping[str, Any]) -> str:
    frozen = _FROZEN_STEP3_COMPONENTS_PANEL(output)
    if not output.get("ready"):
        return frozen
    c = output.get("components") or {}
    return frozen + f"""
<div class="cfbou4-audit">
  <b>⏱️ STEP 4 PACE AUDIT</b>
  <span>
    Expected combined plays {_num(c.get('step4_expected_combined_plays'))} •
    division baseline {_num(c.get('step4_division_baseline_combined_plays'))} •
    pace ratio {_num(c.get('step4_pace_ratio'),3)} •
    sample factor {_pct(c.get('step4_sample_factor'))} •
    total pace adjustment {_num(c.get('step4_total_pace_adjustment'),2)}.
    Frozen reliability and structural sigma are intentionally unchanged.
  </span>
</div>
"""


def _final_card_v4(
    game: Mapping[str, Any],
    final: Mapping[str, Any],
) -> str:
    html = _FROZEN_STEP3_FINAL_CARD(game, final)
    html = html.replace(
        "STEP 9 FINAL RULES • STEP 3 MATCHUP-ADJUSTED PROJECTION",
        "STEP 9 FINAL RULES • STEP 4 PACE-ADJUSTED PROJECTION",
    )
    html = html.replace(
        "The Step-9 qualification thresholds remain frozen; Step 3 adjusts the projection before those rules are applied.",
        "The Step-9 qualification thresholds remain frozen; Step 3 matchup and Step 4 pace adjustments occur before those rules are applied.",
    )
    return html


def _clear_stale_scan_state() -> None:
    marker = "cfb_ou_upgrade_step4_scan_state_reset"
    if st.session_state.get(marker):
        return
    for key in list(st.session_state.keys()):
        if str(key).startswith("cfb_step9_top5_") or str(key).startswith("cfb_step9_scan_diag_"):
            try:
                del st.session_state[key]
            except Exception:
                pass
    st.session_state[marker] = True


def render_over_under_hub(
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    st.caption("⏱️ CFB O/U INTELLIGENCE V2 • Upgrade Step 4 • pace / expected possessions ACTIVE")
    st.markdown(_CSS, unsafe_allow_html=True)
    _clear_stale_scan_state()

    original_logo_hero = frozen_logo_v4._hero_with_multisource_logos
    original_slate = step3.upgraded_slate
    original_model_card = step3._model_card_v3
    original_components = step3._components_panel_v3
    original_final_card = step3._final_card_v3

    frozen_logo_v4._hero_with_multisource_logos = _hero_v4
    step3.upgraded_slate = upgraded_slate
    step3._model_card_v3 = _model_card_v4
    step3._components_panel_v3 = _components_panel_v4
    step3._final_card_v3 = _final_card_v4
    try:
        return frozen_logo_v4.render_over_under_hub(
            section_header,
            status_info,
            team_logo,
            h,
        )
    finally:
        frozen_logo_v4._hero_with_multisource_logos = original_logo_hero
        step3.upgraded_slate = original_slate
        step3._model_card_v3 = original_model_card
        step3._components_panel_v3 = original_components
        step3._final_card_v3 = original_final_card


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Upgrade Step 4 Over/Under UI received unsupported market: {market}")
    return render_over_under_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_UPGRADE",
    "MARKET",
    "MODEL_VERSION",
    "_components_panel_v4",
    "_final_card_v4",
    "_hero_v4",
    "_model_card_v4",
    "_pace_panel",
    "render_cfb_hub",
    "render_over_under_hub",
]
