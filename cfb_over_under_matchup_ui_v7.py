"""CFB Over/Under Intelligence V2 — Upgrade Step 7 third-down drive-sustain UI.

Additive wrapper over permanently frozen Upgrade Step 6.

Step 7 adds direct first-party NCAA third-down evidence:
- offensive third-down attempts + conversions,
- opponent third-down attempts + conversions,
- direct conversion rates,
- FBS/FCS baseline normalization,
- attempt-count sample shrinkage,
- bounded per-team drive-sustain adjustments.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import streamlit as st

import cfb_over_under_matchup_ui_v6 as frozen_v6
import cfb_over_under_slate_v6 as upgraded_slate
import cfb_over_under_third_down_engine_v1 as third_down_engine

MODEL_VERSION = "CFB OVER/UNDER INTELLIGENCE V2 • UPGRADE STEP 7 THIRD DOWN"
FROZEN_UPGRADE = "cfb_over_under_matchup_ui_v6"
MARKET = "Over/Under"

_FROZEN_STEP6_HERO = frozen_v6._hero_v6
_FROZEN_STEP6_MODEL_CARD = frozen_v6._model_card_v6
_FROZEN_STEP6_COMPONENTS_PANEL = frozen_v6._components_panel_v6
_FROZEN_STEP6_FINAL_CARD = frozen_v6._final_card_v6

_CSS = r"""
<style>
.cfbou7-td{margin:10px 0 2px;border:1px solid rgba(155,126,255,.34);border-radius:18px;
background:linear-gradient(145deg,#100b20,#0b1620 58%,#0b1518);overflow:hidden}
.cfbou7-head{display:flex;justify-content:space-between;gap:8px;align-items:center;padding:10px 12px;
border-bottom:1px solid rgba(155,126,255,.15)}
.cfbou7-head b{color:#c4b5ff;font-size:.54rem;font-weight:950;letter-spacing:.08em}
.cfbou7-head span{border:1px solid #4f3f87;border-radius:999px;padding:4px 7px;background:#1b1530;
color:#cfc5ff;font-size:.39rem;font-weight:950}
.cfbou7-sub{padding:7px 12px;color:#87959d;font-size:.42rem;line-height:1.5;border-bottom:1px solid rgba(155,126,255,.08)}
.cfbou7-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding:10px}
.cfbou7-side{border:1px solid rgba(155,126,255,.15);border-radius:13px;background:#091720;overflow:hidden}
.cfbou7-side-top{display:flex;justify-content:space-between;gap:8px;padding:9px 10px;border-bottom:1px solid rgba(155,126,255,.10)}
.cfbou7-side-top b{display:block;color:#f4f9fb;font-size:.67rem}.cfbou7-side-top small{display:block;color:#738792;font-size:.34rem;margin-top:3px}
.cfbou7-adj{text-align:right}.cfbou7-adj strong{display:block;color:#c9bcff;font-size:.76rem}.cfbou7-adj span{display:block;color:#6f7e85;font-size:.30rem;text-transform:uppercase;margin-top:2px}
.cfbou7-rategrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;padding:8px}
.cfbou7-box{border:1px solid rgba(155,126,255,.10);border-radius:9px;background:#07131b;padding:7px}
.cfbou7-box b{display:block;color:#e7f0f4;font-size:.49rem}.cfbou7-box span{display:block;color:#6e818b;font-size:.31rem;line-height:1.4;margin-top:3px}
.cfbou7-box strong{display:block;color:#cabfff;font-size:.54rem;margin-top:4px}
.cfbou7-main{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;padding:0 10px 10px}
.cfbou7-m{border:1px solid rgba(155,126,255,.10);border-radius:9px;background:#08131a;padding:7px}
.cfbou7-m b{display:block;color:#eef7fa;font-size:.61rem}.cfbou7-m span{display:block;color:#687c86;font-size:.30rem;text-transform:uppercase;margin-top:2px}
.cfbou7-foot{padding:8px 11px;border-top:1px solid rgba(155,126,255,.08);color:#70838c;font-size:.37rem;line-height:1.48}
.cfbou7-gate{margin:10px;border:1px solid #6c5720;border-radius:10px;background:#2b240d;color:#d9c477;padding:9px;font-size:.43rem;line-height:1.45}
.cfbou7-model{margin-top:10px;border:1px solid rgba(155,126,255,.25);border-radius:16px;background:linear-gradient(145deg,#100b20,#071924,#101611);overflow:hidden}
.cfbou7-model-head{display:flex;justify-content:space-between;gap:8px;padding:10px 11px;border-bottom:1px solid rgba(155,126,255,.12)}
.cfbou7-model-head b{color:#c9bcff;font-size:.52rem;font-weight:950;letter-spacing:.07em}.cfbou7-model-head span{color:#8e83b7;font-size:.38rem;font-weight:900}
.cfbou7-model-main{display:grid;grid-template-columns:1.2fr 1fr;gap:8px;padding:10px}
.cfbou7-total,.cfbou7-prob{border:1px solid rgba(155,126,255,.12);border-radius:11px;background:#11140f;padding:9px}
.cfbou7-total small,.cfbou7-prob small{display:block;color:#847675;font-size:.35rem;text-transform:uppercase;font-weight:900}
.cfbou7-total strong{display:block;color:#fff7f7;font-size:1.35rem;margin-top:3px}.cfbou7-total b{display:block;color:#b69595;font-size:.42rem;margin-top:4px}
.cfbou7-prob strong{display:block;color:#f7e8e8;font-size:.70rem;margin-top:5px}.cfbou7-prob b{display:block;color:#918181;font-size:.38rem;margin-top:4px}
.cfbou7-model-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;padding:0 10px 10px}
.cfbou7-audit{margin-top:8px;border:1px solid rgba(155,126,255,.17);border-radius:12px;background:#10141a;padding:9px}
.cfbou7-audit b{color:#c9bcff;font-size:.46rem}.cfbou7-audit span{display:block;color:#7d858b;font-size:.37rem;line-height:1.45;margin-top:4px}
@media(max-width:760px){.cfbou7-grid{grid-template-columns:1fr}.cfbou7-main{grid-template-columns:repeat(2,minmax(0,1fr))}
.cfbou7-model-main{grid-template-columns:1fr}.cfbou7-model-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return "—"


def _pct(value: Any) -> str:
    try:
        return f"{100.0 * float(value):.1f}%"
    except Exception:
        return "—"


def _metrics_box(title: str, metrics: Mapping[str, Any], defense: bool) -> str:
    if not metrics.get("ready"):
        return f"""
<div class="cfbou7-box">
  <b>{escape(title)}</b>
  <span>Direct NCAA third-down row unavailable.</span>
  <strong>UNAVAILABLE</strong>
</div>
"""
    prefix = "Allowed " if defense else ""
    return f"""
<div class="cfbou7-box">
  <b>{escape(title)}</b>
  <span>
    {prefix}conversion {_pct(metrics.get('conversion_rate'))}<br>
    attempts {_num(metrics.get('attempts'),0)} • conversions {_num(metrics.get('conversions'),0)}
  </span>
  <strong>{_num(metrics.get('attempts_per_game'))} 3rd downs/game</strong>
</div>
"""


def _side_html(side: Mapping[str, Any]) -> str:
    adjustment = float(side.get("points_adjustment") or 0.0)
    sign = "+" if adjustment > 0 else ""
    return f"""
<div class="cfbou7-side">
  <div class="cfbou7-side-top">
    <div>
      <b>{escape(_clean(side.get('offense_team')) or 'Offense')} offense vs {escape(_clean(side.get('defense_team')) or 'Defense')} defense</b>
      <small>{escape(_clean(side.get('offense_division')))} offense • {escape(_clean(side.get('defense_division')))} defense • {escape(_clean(side.get('label')) or 'BALANCED')}</small>
    </div>
    <div class="cfbou7-adj">
      <strong>{sign}{adjustment:.2f}</strong>
      <span>projected pts adj</span>
    </div>
  </div>
  <div class="cfbou7-rategrid">
    {_metrics_box('3rd-down offense', side.get('offense') or {}, False)}
    {_metrics_box('Opponent 3rd-down defense', side.get('defense') or {}, True)}
  </div>
  <div class="cfbou7-main">
    <div class="cfbou7-m"><b>{_pct(side.get('matchup_conversion_rate'))}</b><span>Blended matchup conversion</span></div>
    <div class="cfbou7-m"><b>{_num(side.get('expected_third_down_attempts_per_game'))}</b><span>Expected 3rd-down tries</span></div>
    <div class="cfbou7-m"><b>{_num(side.get('expected_third_down_conversions_per_game'))}</b><span>Expected conversions</span></div>
    <div class="cfbou7-m"><b>{_pct(side.get('sample_factor'))}</b><span>Attempt sample weight</span></div>
  </div>
</div>
"""


def _third_down_panel(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> str:
    engine = third_down_engine.build_third_down_engine(game, away, home)
    if not engine.get("model_ready"):
        return f"""
<div class="cfbou7-td">
  <div class="cfbou7-head">
    <b>🟪 UPGRADE STEP 7 • THIRD-DOWN DRIVE-SUSTAIN ENGINE</b>
    <span>THIRD-DOWN ADJUSTMENT GATED</span>
  </div>
  <div class="cfbou7-gate">
    {escape(_clean(engine.get('reason')) or 'Verified direct third-down evidence is incomplete')}.
    Step 6 remains the active projection for this matchup.
  </div>
</div>
"""

    away_side = engine.get("away_offense") or {}
    home_side = engine.get("home_offense") or {}
    return f"""
<div class="cfbou7-td">
  <div class="cfbou7-head">
    <b>🟪 UPGRADE STEP 7 • THIRD-DOWN DRIVE-SUSTAIN ENGINE</b>
    <span>ACTIVE • MAX ±{third_down_engine.MAX_TEAM_THIRD_DOWN_ADJUSTMENT:.2f} PTS / TEAM</span>
  </div>
  <div class="cfbou7-sub">
    NCAA third-down attempts and conversions measure whether an offense can extend drives against the opponent's verified third-down defense.
    Rates are normalized inside each team's FBS/FCS pool and the analysis line has 0% third-down weight.
  </div>
  <div class="cfbou7-grid">
    {_side_html(away_side)}
    {_side_html(home_side)}
  </div>
  <div class="cfbou7-foot">
    Offensive conversion quality and opponent allowed conversion quality are blended 50/50.
    Confidence is shrunk by the smaller verified third-down attempt sample. Cross-division ranking numbers are never compared.
  </div>
</div>
"""


def _hero_v7(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> str:
    return _FROZEN_STEP6_HERO(game, away, home) + _third_down_panel(game, away, home)


def _model_card_v7(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    output: Mapping[str, Any],
) -> str:
    if not output.get("ready"):
        return _FROZEN_STEP6_MODEL_CARD(game, away, home, output)

    applied = bool(output.get("upgrade_step7_applied"))
    badge = "THIRD-DOWN ENGINE APPLIED" if applied else "STEP 6 FALLBACK"
    base_total = output.get("step7_base_projected_total")
    if base_total is None:
        base_total = output.get("projected_total")
    components = output.get("components") or {}

    return f"""
<div class="cfbou7-model">
  <div class="cfbou7-model-head">
    <b>STEP 7 • THIRD-DOWN-ADJUSTED OVER/UNDER MODEL</b>
    <span>{escape(badge)} • LINE WEIGHT 0%</span>
  </div>
  <div class="cfbou7-model-main">
    <div class="cfbou7-total">
      <small>Projected game total</small>
      <strong>{_num(output.get('projected_total'),1)}</strong>
      <b>Step 6 {_num(base_total,1)} → third-down adjusted {_num(output.get('projected_total'),1)}</b>
    </div>
    <div class="cfbou7-prob">
      <small>Current O/U probabilities at analysis line {_num(output.get('analysis_line'),1)}</small>
      <strong>OVER {_pct(output.get('over_probability'))} • UNDER {_pct(output.get('under_probability'))}</strong>
      <b>{escape(_clean(output.get('model_lean')) or 'PASS')} lean • push {_pct(output.get('push_probability'))}</b>
    </div>
  </div>
  <div class="cfbou7-model-grid">
    <div class="cfbou7-m"><b>{_num(output.get('projected_away_points'),1)}</b><span>{escape(_clean(away.get('team')) or 'Away')} points</span></div>
    <div class="cfbou7-m"><b>{_num(output.get('projected_home_points'),1)}</b><span>{escape(_clean(home.get('team')) or 'Home')} points</span></div>
    <div class="cfbou7-m"><b>{_num(components.get('step7_away_third_down_adjustment'))}</b><span>Away 3rd-down adj</span></div>
    <div class="cfbou7-m"><b>{_num(components.get('step7_home_third_down_adjustment'))}</b><span>Home 3rd-down adj</span></div>
    <div class="cfbou7-m"><b>{_num(components.get('step7_total_third_down_adjustment'))}</b><span>Total 3rd-down adj</span></div>
    <div class="cfbou7-m"><b>{_pct(output.get('third_down_engine_coverage'))}</b><span>Third-down coverage</span></div>
    <div class="cfbou7-m"><b>{_pct(output.get('reliability'))}</b><span>Frozen reliability</span></div>
    <div class="cfbou7-m"><b>0%</b><span>Analysis-line model weight</span></div>
  </div>
</div>
"""


def _components_panel_v7(output: Mapping[str, Any]) -> str:
    frozen = _FROZEN_STEP6_COMPONENTS_PANEL(output)
    if not output.get("ready"):
        return frozen
    c = output.get("components") or {}
    return frozen + f"""
<div class="cfbou7-audit">
  <b>🟪 STEP 7 THIRD-DOWN AUDIT</b>
  <span>
    Away adjustment {_num(c.get('step7_away_third_down_adjustment'))} •
    home adjustment {_num(c.get('step7_home_third_down_adjustment'))} •
    total adjustment {_num(c.get('step7_total_third_down_adjustment'))} •
    engine coverage {_pct(c.get('step7_third_down_coverage'))}.
    Frozen reliability and structural sigma are intentionally unchanged.
  </span>
</div>
"""


def _final_card_v7(
    game: Mapping[str, Any],
    final: Mapping[str, Any],
) -> str:
    html = _FROZEN_STEP6_FINAL_CARD(game, final)
    html = html.replace(
        "STEP 9 FINAL RULES • STEP 6 RED-ZONE-ADJUSTED PROJECTION",
        "STEP 9 FINAL RULES • STEP 7 THIRD-DOWN-ADJUSTED PROJECTION",
    )
    html = html.replace(
        "The Step-9 qualification thresholds remain frozen; Step 3 matchup, Step 4 pace, Step 5 explosive, and Step 6 red-zone adjustments occur before those rules are applied.",
        "The Step-9 qualification thresholds remain frozen; Step 3 matchup, Step 4 pace, Step 5 explosive, Step 6 red-zone, and Step 7 third-down adjustments occur before those rules are applied.",
    )
    return html


def _clear_stale_scan_state() -> None:
    marker = "cfb_ou_upgrade_step7_scan_state_reset"
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
    st.caption("🟪 CFB O/U INTELLIGENCE V2 • Upgrade Step 7 • third-down drive-sustain engine ACTIVE")
    st.markdown(_CSS, unsafe_allow_html=True)
    _clear_stale_scan_state()

    original_hero = frozen_v6._hero_v6
    original_slate = frozen_v6.upgraded_slate
    original_model = frozen_v6._model_card_v6
    original_components = frozen_v6._components_panel_v6
    original_final = frozen_v6._final_card_v6

    frozen_v6._hero_v6 = _hero_v7
    frozen_v6.upgraded_slate = upgraded_slate
    frozen_v6._model_card_v6 = _model_card_v7
    frozen_v6._components_panel_v6 = _components_panel_v7
    frozen_v6._final_card_v6 = _final_card_v7
    try:
        return frozen_v6.render_over_under_hub(
            section_header,
            status_info,
            team_logo,
            h,
        )
    finally:
        frozen_v6._hero_v6 = original_hero
        frozen_v6.upgraded_slate = original_slate
        frozen_v6._model_card_v6 = original_model
        frozen_v6._components_panel_v6 = original_components
        frozen_v6._final_card_v6 = original_final


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Upgrade Step 7 Over/Under UI received unsupported market: {market}")
    return render_over_under_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_UPGRADE",
    "MARKET",
    "MODEL_VERSION",
    "_components_panel_v7",
    "_final_card_v7",
    "_hero_v7",
    "_model_card_v7",
    "_third_down_panel",
    "render_cfb_hub",
    "render_over_under_hub",
]
