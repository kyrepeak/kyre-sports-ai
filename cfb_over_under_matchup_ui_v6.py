"""CFB Over/Under Intelligence V2 — Upgrade Step 6 red-zone UI.

Additive wrapper over permanently frozen Upgrade Step 5.

Step 6 adds direct first-party NCAA red-zone evidence:
- red-zone attempts,
- rush/pass touchdowns,
- field goals,
- scoring rate,
- touchdown conversion rate,
- estimated points per red-zone trip,
- FBS/FCS baseline normalization,
- attempt-count sample shrinkage,
- bounded per-team projection adjustments.

Tied NCAA ranks are parsed safely instead of being discarded.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import streamlit as st

import cfb_over_under_matchup_ui_v5 as frozen_v5
import cfb_over_under_red_zone_engine_v1 as red_zone_engine
import cfb_over_under_slate_v5 as upgraded_slate

MODEL_VERSION = "CFB OVER/UNDER INTELLIGENCE V2 • UPGRADE STEP 6 RED ZONE"
FROZEN_UPGRADE = "cfb_over_under_matchup_ui_v5"
MARKET = "Over/Under"

_FROZEN_STEP5_HERO = frozen_v5._hero_v5
_FROZEN_STEP5_MODEL_CARD = frozen_v5._model_card_v5
_FROZEN_STEP5_COMPONENTS_PANEL = frozen_v5._components_panel_v5
_FROZEN_STEP5_FINAL_CARD = frozen_v5._final_card_v5

_CSS = r"""
<style>
.cfbou6-rz{margin:10px 0 2px;border:1px solid rgba(255,102,102,.30);border-radius:18px;
background:linear-gradient(145deg,#180b0b,#101820 58%,#0b1518);overflow:hidden}
.cfbou6-head{display:flex;justify-content:space-between;gap:8px;align-items:center;padding:10px 12px;
border-bottom:1px solid rgba(255,102,102,.14)}
.cfbou6-head b{color:#ff9a9a;font-size:.54rem;font-weight:950;letter-spacing:.08em}
.cfbou6-head span{border:1px solid #713131;border-radius:999px;padding:4px 7px;background:#281010;
color:#ffb0b0;font-size:.39rem;font-weight:950}
.cfbou6-sub{padding:7px 12px;color:#87959d;font-size:.42rem;line-height:1.5;border-bottom:1px solid rgba(255,102,102,.08)}
.cfbou6-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding:10px}
.cfbou6-side{border:1px solid rgba(255,102,102,.14);border-radius:13px;background:#091720;overflow:hidden}
.cfbou6-side-top{display:flex;justify-content:space-between;gap:8px;padding:9px 10px;border-bottom:1px solid rgba(255,102,102,.10)}
.cfbou6-side-top b{display:block;color:#f4f9fb;font-size:.67rem}.cfbou6-side-top small{display:block;color:#738792;font-size:.34rem;margin-top:3px}
.cfbou6-adj{text-align:right}.cfbou6-adj strong{display:block;color:#ffaaaa;font-size:.76rem}.cfbou6-adj span{display:block;color:#6f7e85;font-size:.30rem;text-transform:uppercase;margin-top:2px}
.cfbou6-rategrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;padding:8px}
.cfbou6-box{border:1px solid rgba(255,102,102,.10);border-radius:9px;background:#07131b;padding:7px}
.cfbou6-box b{display:block;color:#e7f0f4;font-size:.49rem}.cfbou6-box span{display:block;color:#6e818b;font-size:.31rem;line-height:1.4;margin-top:3px}
.cfbou6-box strong{display:block;color:#ffb4b4;font-size:.54rem;margin-top:4px}
.cfbou6-main{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;padding:0 10px 10px}
.cfbou6-m{border:1px solid rgba(255,102,102,.10);border-radius:9px;background:#08131a;padding:7px}
.cfbou6-m b{display:block;color:#eef7fa;font-size:.61rem}.cfbou6-m span{display:block;color:#687c86;font-size:.30rem;text-transform:uppercase;margin-top:2px}
.cfbou6-foot{padding:8px 11px;border-top:1px solid rgba(255,102,102,.08);color:#70838c;font-size:.37rem;line-height:1.48}
.cfbou6-gate{margin:10px;border:1px solid #6c5720;border-radius:10px;background:#2b240d;color:#d9c477;padding:9px;font-size:.43rem;line-height:1.45}
.cfbou6-model{margin-top:10px;border:1px solid rgba(255,116,116,.25);border-radius:16px;background:linear-gradient(145deg,#160b0b,#071924,#101611);overflow:hidden}
.cfbou6-model-head{display:flex;justify-content:space-between;gap:8px;padding:10px 11px;border-bottom:1px solid rgba(255,116,116,.12)}
.cfbou6-model-head b{color:#ffaaaa;font-size:.52rem;font-weight:950;letter-spacing:.07em}.cfbou6-model-head span{color:#9c7373;font-size:.38rem;font-weight:900}
.cfbou6-model-main{display:grid;grid-template-columns:1.2fr 1fr;gap:8px;padding:10px}
.cfbou6-total,.cfbou6-prob{border:1px solid rgba(255,116,116,.12);border-radius:11px;background:#11140f;padding:9px}
.cfbou6-total small,.cfbou6-prob small{display:block;color:#847675;font-size:.35rem;text-transform:uppercase;font-weight:900}
.cfbou6-total strong{display:block;color:#fff7f7;font-size:1.35rem;margin-top:3px}.cfbou6-total b{display:block;color:#b69595;font-size:.42rem;margin-top:4px}
.cfbou6-prob strong{display:block;color:#f7e8e8;font-size:.70rem;margin-top:5px}.cfbou6-prob b{display:block;color:#918181;font-size:.38rem;margin-top:4px}
.cfbou6-model-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;padding:0 10px 10px}
.cfbou6-audit{margin-top:8px;border:1px solid rgba(255,116,116,.17);border-radius:12px;background:#10141a;padding:9px}
.cfbou6-audit b{color:#ffb4b4;font-size:.46rem}.cfbou6-audit span{display:block;color:#7d858b;font-size:.37rem;line-height:1.45;margin-top:4px}
@media(max-width:760px){.cfbou6-grid{grid-template-columns:1fr}.cfbou6-main{grid-template-columns:repeat(2,minmax(0,1fr))}
.cfbou6-model-main{grid-template-columns:1fr}.cfbou6-model-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
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
<div class="cfbou6-box">
  <b>{escape(title)}</b>
  <span>Direct NCAA red-zone row unavailable.</span>
  <strong>UNAVAILABLE</strong>
</div>
"""
    prefix = "Allowed " if defense else ""
    return f"""
<div class="cfbou6-box">
  <b>{escape(title)}</b>
  <span>
    {prefix}TD rate {_pct(metrics.get('touchdown_rate'))} •
    {prefix}score rate {_pct(metrics.get('scoring_rate'))}<br>
    {prefix}points/trip {_num(metrics.get('points_per_trip'))} •
    attempts {_num(metrics.get('attempts'),0)}
  </span>
  <strong>{_num(metrics.get('attempts_per_game'))} RZ trips/game</strong>
</div>
"""


def _side_html(side: Mapping[str, Any]) -> str:
    adjustment = float(side.get("points_adjustment") or 0.0)
    sign = "+" if adjustment > 0 else ""
    return f"""
<div class="cfbou6-side">
  <div class="cfbou6-side-top">
    <div>
      <b>{escape(_clean(side.get('offense_team')) or 'Offense')} offense vs {escape(_clean(side.get('defense_team')) or 'Defense')} defense</b>
      <small>{escape(_clean(side.get('offense_division')))} offense • {escape(_clean(side.get('defense_division')))} defense • {escape(_clean(side.get('label')) or 'BALANCED')}</small>
    </div>
    <div class="cfbou6-adj">
      <strong>{sign}{adjustment:.2f}</strong>
      <span>projected pts adj</span>
    </div>
  </div>
  <div class="cfbou6-rategrid">
    {_metrics_box('Red-zone offense', side.get('offense') or {}, False)}
    {_metrics_box('Opponent red-zone defense', side.get('defense') or {}, True)}
  </div>
</div>
"""


def _red_zone_panel(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> str:
    engine = red_zone_engine.build_red_zone_engine(game, away, home)
    if not engine.get("model_ready"):
        return f"""
<div class="cfbou6-rz">
  <div class="cfbou6-head">
    <b>🟥 UPGRADE STEP 6 • RED-ZONE ENGINE</b>
    <span>RED-ZONE ADJUSTMENT GATED</span>
  </div>
  <div class="cfbou6-gate">
    {escape(_clean(engine.get('reason')) or 'Verified direct red-zone evidence is incomplete')}.
    Step 5 remains the active projection for this matchup.
  </div>
</div>
"""

    away_side = engine.get("away_offense") or {}
    home_side = engine.get("home_offense") or {}
    return f"""
<div class="cfbou6-rz">
  <div class="cfbou6-head">
    <b>🟥 UPGRADE STEP 6 • RED-ZONE ENGINE</b>
    <span>ACTIVE • MAX ±{red_zone_engine.MAX_TEAM_RED_ZONE_ADJUSTMENT:.2f} PTS / TEAM</span>
  </div>
  <div class="cfbou6-sub">
    NCAA red-zone attempts and outcomes are converted into touchdown rate and estimated points per trip.
    Offense and opponent-allowed rates are normalized inside the correct FBS/FCS pool, while the analysis line has 0% red-zone weight.
  </div>
  <div class="cfbou6-grid">
    {_side_html(away_side)}
    {_side_html(home_side)}
  </div>
  <div class="cfbou6-main">
    <div class="cfbou6-m"><b>{_pct(away_side.get('coverage'))}</b><span>Away direct coverage</span></div>
    <div class="cfbou6-m"><b>{_pct(home_side.get('coverage'))}</b><span>Home direct coverage</span></div>
    <div class="cfbou6-m"><b>{_pct(away_side.get('sample_factor'))}</b><span>Away RZ sample weight</span></div>
    <div class="cfbou6-m"><b>{_pct(home_side.get('sample_factor'))}</b><span>Home RZ sample weight</span></div>
  </div>
  <div class="cfbou6-foot">
    Touchdown conversion carries 65% of the red-zone signal and points per trip carries 35%.
    Sample confidence uses verified red-zone attempt counts, not just games played. NCAA tied-rank rows are parsed directly so blank rank cells do not erase valid team data.
  </div>
</div>
"""


def _hero_v6(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> str:
    return _FROZEN_STEP5_HERO(game, away, home) + _red_zone_panel(game, away, home)


def _model_card_v6(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    output: Mapping[str, Any],
) -> str:
    if not output.get("ready"):
        return _FROZEN_STEP5_MODEL_CARD(game, away, home, output)

    applied = bool(output.get("upgrade_step6_applied"))
    badge = "RED-ZONE ENGINE APPLIED" if applied else "STEP 5 FALLBACK"
    base_total = output.get("step6_base_projected_total")
    if base_total is None:
        base_total = output.get("projected_total")
    components = output.get("components") or {}

    return f"""
<div class="cfbou6-model">
  <div class="cfbou6-model-head">
    <b>STEP 6 • RED-ZONE-ADJUSTED OVER/UNDER MODEL</b>
    <span>{escape(badge)} • LINE WEIGHT 0%</span>
  </div>
  <div class="cfbou6-model-main">
    <div class="cfbou6-total">
      <small>Projected game total</small>
      <strong>{_num(output.get('projected_total'),1)}</strong>
      <b>Step 5 {_num(base_total,1)} → red-zone adjusted {_num(output.get('projected_total'),1)}</b>
    </div>
    <div class="cfbou6-prob">
      <small>Current O/U probabilities at analysis line {_num(output.get('analysis_line'),1)}</small>
      <strong>OVER {_pct(output.get('over_probability'))} • UNDER {_pct(output.get('under_probability'))}</strong>
      <b>{escape(_clean(output.get('model_lean')) or 'PASS')} lean • push {_pct(output.get('push_probability'))}</b>
    </div>
  </div>
  <div class="cfbou6-model-grid">
    <div class="cfbou6-m"><b>{_num(output.get('projected_away_points'),1)}</b><span>{escape(_clean(away.get('team')) or 'Away')} points</span></div>
    <div class="cfbou6-m"><b>{_num(output.get('projected_home_points'),1)}</b><span>{escape(_clean(home.get('team')) or 'Home')} points</span></div>
    <div class="cfbou6-m"><b>{_num(components.get('step6_away_red_zone_adjustment'))}</b><span>Away red-zone adj</span></div>
    <div class="cfbou6-m"><b>{_num(components.get('step6_home_red_zone_adjustment'))}</b><span>Home red-zone adj</span></div>
    <div class="cfbou6-m"><b>{_num(components.get('step6_total_red_zone_adjustment'))}</b><span>Total red-zone adj</span></div>
    <div class="cfbou6-m"><b>{_pct(output.get('red_zone_engine_coverage'))}</b><span>Red-zone coverage</span></div>
    <div class="cfbou6-m"><b>{_pct(output.get('reliability'))}</b><span>Frozen reliability</span></div>
    <div class="cfbou6-m"><b>0%</b><span>Analysis-line model weight</span></div>
  </div>
</div>
"""


def _components_panel_v6(output: Mapping[str, Any]) -> str:
    frozen = _FROZEN_STEP5_COMPONENTS_PANEL(output)
    if not output.get("ready"):
        return frozen
    c = output.get("components") or {}
    return frozen + f"""
<div class="cfbou6-audit">
  <b>🟥 STEP 6 RED-ZONE AUDIT</b>
  <span>
    Away adjustment {_num(c.get('step6_away_red_zone_adjustment'))} •
    home adjustment {_num(c.get('step6_home_red_zone_adjustment'))} •
    total adjustment {_num(c.get('step6_total_red_zone_adjustment'))} •
    engine coverage {_pct(c.get('step6_red_zone_coverage'))}.
    Frozen reliability and structural sigma are intentionally unchanged.
  </span>
</div>
"""


def _final_card_v6(
    game: Mapping[str, Any],
    final: Mapping[str, Any],
) -> str:
    html = _FROZEN_STEP5_FINAL_CARD(game, final)
    html = html.replace(
        "STEP 9 FINAL RULES • STEP 5 EXPLOSIVE-ADJUSTED PROJECTION",
        "STEP 9 FINAL RULES • STEP 6 RED-ZONE-ADJUSTED PROJECTION",
    )
    html = html.replace(
        "The Step-9 qualification thresholds remain frozen; Step 3 matchup, Step 4 pace, and Step 5 explosive adjustments occur before those rules are applied.",
        "The Step-9 qualification thresholds remain frozen; Step 3 matchup, Step 4 pace, Step 5 explosive, and Step 6 red-zone adjustments occur before those rules are applied.",
    )
    return html


def _clear_stale_scan_state() -> None:
    marker = "cfb_ou_upgrade_step6_scan_state_reset"
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
    st.caption("🟥 CFB O/U INTELLIGENCE V2 • Upgrade Step 6 • red-zone engine ACTIVE")
    st.markdown(_CSS, unsafe_allow_html=True)
    _clear_stale_scan_state()

    original_hero = frozen_v5._hero_v5
    original_slate = frozen_v5.upgraded_slate
    original_model = frozen_v5._model_card_v5
    original_components = frozen_v5._components_panel_v5
    original_final = frozen_v5._final_card_v5

    frozen_v5._hero_v5 = _hero_v6
    frozen_v5.upgraded_slate = upgraded_slate
    frozen_v5._model_card_v5 = _model_card_v6
    frozen_v5._components_panel_v5 = _components_panel_v6
    frozen_v5._final_card_v5 = _final_card_v6
    try:
        return frozen_v5.render_over_under_hub(
            section_header,
            status_info,
            team_logo,
            h,
        )
    finally:
        frozen_v5._hero_v5 = original_hero
        frozen_v5.upgraded_slate = original_slate
        frozen_v5._model_card_v5 = original_model
        frozen_v5._components_panel_v5 = original_components
        frozen_v5._final_card_v5 = original_final


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Upgrade Step 6 Over/Under UI received unsupported market: {market}")
    return render_over_under_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_UPGRADE",
    "MARKET",
    "MODEL_VERSION",
    "_components_panel_v6",
    "_final_card_v6",
    "_hero_v6",
    "_model_card_v6",
    "_red_zone_panel",
    "render_cfb_hub",
    "render_over_under_hub",
]
