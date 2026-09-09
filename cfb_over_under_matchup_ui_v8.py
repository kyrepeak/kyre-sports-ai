"""CFB Over/Under Intelligence V2 — Upgrade Step 8 turnover-volatility UI.

Additive wrapper over permanently frozen Upgrade Step 7.

Step 8 adds direct first-party NCAA turnover evidence:
- giveaways/game,
- takeaways/game,
- turnover margin context,
- FBS/FCS baseline normalization,
- completed-game sample shrinkage,
- bounded structural-uncertainty adjustment.

Because verified field-position / return data is not present in the certified
source, Step 8 does not fabricate a projected-points adjustment.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import streamlit as st

import cfb_over_under_matchup_ui_v7 as frozen_v7
import cfb_over_under_slate_v7 as upgraded_slate
import cfb_over_under_turnover_engine_v1 as turnover_engine

MODEL_VERSION = "CFB OVER/UNDER INTELLIGENCE V2 • UPGRADE STEP 8 TURNOVER VOLATILITY"
FROZEN_UPGRADE = "cfb_over_under_matchup_ui_v7"
MARKET = "Over/Under"

_FROZEN_STEP7_HERO = frozen_v7._hero_v7
_FROZEN_STEP7_MODEL_CARD = frozen_v7._model_card_v7
_FROZEN_STEP7_COMPONENTS_PANEL = frozen_v7._components_panel_v7
_FROZEN_STEP7_FINAL_CARD = frozen_v7._final_card_v7

_CSS = r"""
<style>
.cfbou8-to{margin:10px 0 2px;border:1px solid rgba(255,187,72,.34);border-radius:18px;
background:linear-gradient(145deg,#1b1306,#0b1620 58%,#0b1518);overflow:hidden}
.cfbou8-head{display:flex;justify-content:space-between;gap:8px;align-items:center;padding:10px 12px;
border-bottom:1px solid rgba(255,187,72,.15)}
.cfbou8-head b{color:#ffd28a;font-size:.54rem;font-weight:950;letter-spacing:.08em}
.cfbou8-head span{border:1px solid #74511b;border-radius:999px;padding:4px 7px;background:#251a08;
color:#ffdc9e;font-size:.39rem;font-weight:950}
.cfbou8-sub{padding:7px 12px;color:#87959d;font-size:.42rem;line-height:1.5;border-bottom:1px solid rgba(255,187,72,.08)}
.cfbou8-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding:10px}
.cfbou8-side{border:1px solid rgba(255,187,72,.15);border-radius:13px;background:#091720;overflow:hidden}
.cfbou8-side-top{display:flex;justify-content:space-between;gap:8px;padding:9px 10px;border-bottom:1px solid rgba(255,187,72,.10)}
.cfbou8-side-top b{display:block;color:#f4f9fb;font-size:.67rem}.cfbou8-side-top small{display:block;color:#738792;font-size:.34rem;margin-top:3px}
.cfbou8-sig{text-align:right}.cfbou8-sig strong{display:block;color:#ffd28a;font-size:.76rem}.cfbou8-sig span{display:block;color:#6f7e85;font-size:.30rem;text-transform:uppercase;margin-top:2px}
.cfbou8-rategrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;padding:8px}
.cfbou8-box{border:1px solid rgba(255,187,72,.10);border-radius:9px;background:#07131b;padding:7px}
.cfbou8-box b{display:block;color:#e7f0f4;font-size:.49rem}.cfbou8-box span{display:block;color:#6e818b;font-size:.31rem;line-height:1.4;margin-top:3px}
.cfbou8-box strong{display:block;color:#ffd28a;font-size:.54rem;margin-top:4px}
.cfbou8-main{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;padding:0 10px 10px}
.cfbou8-m{border:1px solid rgba(255,187,72,.10);border-radius:9px;background:#08131a;padding:7px}
.cfbou8-m b{display:block;color:#eef7fa;font-size:.61rem}.cfbou8-m span{display:block;color:#687c86;font-size:.30rem;text-transform:uppercase;margin-top:2px}
.cfbou8-foot{padding:8px 11px;border-top:1px solid rgba(255,187,72,.08);color:#70838c;font-size:.37rem;line-height:1.48}
.cfbou8-gate{margin:10px;border:1px solid #6c5720;border-radius:10px;background:#2b240d;color:#d9c477;padding:9px;font-size:.43rem;line-height:1.45}
.cfbou8-model{margin-top:10px;border:1px solid rgba(255,187,72,.25);border-radius:16px;background:linear-gradient(145deg,#181006,#071924,#101611);overflow:hidden}
.cfbou8-model-head{display:flex;justify-content:space-between;gap:8px;padding:10px 11px;border-bottom:1px solid rgba(255,187,72,.12)}
.cfbou8-model-head b{color:#ffd28a;font-size:.52rem;font-weight:950;letter-spacing:.07em}.cfbou8-model-head span{color:#a78a5b;font-size:.38rem;font-weight:900}
.cfbou8-model-main{display:grid;grid-template-columns:1.2fr 1fr;gap:8px;padding:10px}
.cfbou8-total,.cfbou8-prob{border:1px solid rgba(255,187,72,.12);border-radius:11px;background:#11140f;padding:9px}
.cfbou8-total small,.cfbou8-prob small{display:block;color:#847675;font-size:.35rem;text-transform:uppercase;font-weight:900}
.cfbou8-total strong{display:block;color:#fff7f7;font-size:1.35rem;margin-top:3px}.cfbou8-total b{display:block;color:#b69595;font-size:.42rem;margin-top:4px}
.cfbou8-prob strong{display:block;color:#f7e8e8;font-size:.70rem;margin-top:5px}.cfbou8-prob b{display:block;color:#918181;font-size:.38rem;margin-top:4px}
.cfbou8-model-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;padding:0 10px 10px}
.cfbou8-audit{margin-top:8px;border:1px solid rgba(255,187,72,.17);border-radius:12px;background:#10141a;padding:9px}
.cfbou8-audit b{color:#ffd28a;font-size:.46rem}.cfbou8-audit span{display:block;color:#7d858b;font-size:.37rem;line-height:1.45;margin-top:4px}
@media(max-width:760px){.cfbou8-grid{grid-template-columns:1fr}.cfbou8-main{grid-template-columns:repeat(2,minmax(0,1fr))}
.cfbou8-model-main{grid-template-columns:1fr}.cfbou8-model-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
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
<div class="cfbou8-box">
  <b>{escape(title)}</b>
  <span>Direct NCAA turnover row unavailable.</span>
  <strong>UNAVAILABLE</strong>
</div>
"""
    primary = metrics.get("takeaways_per_game") if defense else metrics.get("giveaways_per_game")
    label = "Takeaways/game" if defense else "Giveaways/game"
    return f"""
<div class="cfbou8-box">
  <b>{escape(title)}</b>
  <span>
    {label} {_num(primary)}<br>
    gained {_num(metrics.get('turnovers_gained'),0)} • lost {_num(metrics.get('turnovers_lost'),0)} • margin {_num(metrics.get('turnover_margin'),0)}
  </span>
  <strong>{_num(metrics.get('games'),0)} verified games</strong>
</div>
"""


def _side_html(side: Mapping[str, Any]) -> str:
    signal = float(side.get("shrunk_signal") or 0.0)
    return f"""
<div class="cfbou8-side">
  <div class="cfbou8-side-top">
    <div>
      <b>{escape(_clean(side.get('offense_team')) or 'Offense')} ball security vs {escape(_clean(side.get('defense_team')) or 'Defense')} takeaways</b>
      <small>{escape(_clean(side.get('offense_division')))} offense • {escape(_clean(side.get('defense_division')))} defense • {escape(_clean(side.get('label')) or 'NEUTRAL')}</small>
    </div>
    <div class="cfbou8-sig">
      <strong>{signal:+.2f}</strong>
      <span>shrunk volatility signal</span>
    </div>
  </div>
  <div class="cfbou8-rategrid">
    {_metrics_box('Offense turnover profile', side.get('offense') or {}, False)}
    {_metrics_box('Opponent takeaway profile', side.get('defense') or {}, True)}
  </div>
  <div class="cfbou8-main">
    <div class="cfbou8-m"><b>{_num(side.get('expected_giveaways_per_game'))}</b><span>Expected giveaways</span></div>
    <div class="cfbou8-m"><b>{_num(side.get('baseline_expected_giveaways_per_game'))}</b><span>Division baseline</span></div>
    <div class="cfbou8-m"><b>{_pct(side.get('coverage'))}</b><span>Direct coverage</span></div>
    <div class="cfbou8-m"><b>{_pct(side.get('sample_factor'))}</b><span>Sample weight</span></div>
  </div>
</div>
"""


def _turnover_panel(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> str:
    engine = turnover_engine.build_turnover_engine(game, away, home)
    if not engine.get("model_ready"):
        return f"""
<div class="cfbou8-to">
  <div class="cfbou8-head">
    <b>🟧 UPGRADE STEP 8 • TURNOVER-POSSESSION VOLATILITY</b>
    <span>TURNOVER ADJUSTMENT GATED</span>
  </div>
  <div class="cfbou8-gate">
    {escape(_clean(engine.get('reason')) or 'Verified direct turnover evidence is incomplete')}.
    Step 7 remains the active uncertainty profile for this matchup.
  </div>
</div>
"""

    away_side = engine.get("away_offense") or {}
    home_side = engine.get("home_offense") or {}
    sigma_adj = float(engine.get("sigma_adjustment") or 0.0)
    return f"""
<div class="cfbou8-to">
  <div class="cfbou8-head">
    <b>🟧 UPGRADE STEP 8 • TURNOVER-POSSESSION VOLATILITY</b>
    <span>SIGMA ADJ {sigma_adj:+.2f} • MAX ±{turnover_engine.MAX_TOTAL_SIGMA_ADJUSTMENT:.2f}</span>
  </div>
  <div class="cfbou8-sub">
    NCAA direct giveaways and takeaways estimate possession volatility. Because certified field-position/return data is unavailable,
    Step 8 changes uncertainty only — it does not invent a points adjustment or move the Step-7 projected total.
  </div>
  <div class="cfbou8-grid">
    {_side_html(away_side)}
    {_side_html(home_side)}
  </div>
  <div class="cfbou8-foot">
    Offense giveaway rate and opponent takeaway rate are blended 50/50, normalized inside FBS/FCS baselines, and shrunk by completed-game sample.
    Analysis-line weight is 0%, cross-division ranks are never compared, and field-position points are not fabricated.
  </div>
</div>
"""


def _hero_v8(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> str:
    return _FROZEN_STEP7_HERO(game, away, home) + _turnover_panel(game, away, home)


def _model_card_v8(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    output: Mapping[str, Any],
) -> str:
    if not output.get("ready"):
        return _FROZEN_STEP7_MODEL_CARD(game, away, home, output)

    applied = bool(output.get("upgrade_step8_applied"))
    badge = "TURNOVER VOLATILITY APPLIED" if applied else "STEP 7 FALLBACK"
    base_total = output.get("step8_base_projected_total")
    if base_total is None:
        base_total = output.get("projected_total")
    base_sigma = output.get("step8_base_structural_total_sigma")
    if base_sigma is None:
        base_sigma = output.get("structural_total_sigma")
    components = output.get("components") or {}

    return f"""
<div class="cfbou8-model">
  <div class="cfbou8-model-head">
    <b>STEP 8 • TURNOVER-ADJUSTED UNCERTAINTY MODEL</b>
    <span>{escape(badge)} • PROJECTED-TOTAL WEIGHT 0%</span>
  </div>
  <div class="cfbou8-model-main">
    <div class="cfbou8-total">
      <small>Projected game total</small>
      <strong>{_num(output.get('projected_total'),1)}</strong>
      <b>Step 7 {_num(base_total,1)} → Step 8 {_num(output.get('projected_total'),1)} • total unchanged</b>
    </div>
    <div class="cfbou8-prob">
      <small>Structural uncertainty</small>
      <strong>σ {_num(base_sigma,2)} → {_num(output.get('structural_total_sigma'),2)}</strong>
      <b>OVER {_pct(output.get('over_probability'))} • UNDER {_pct(output.get('under_probability'))}</b>
    </div>
  </div>
  <div class="cfbou8-model-grid">
    <div class="cfbou8-m"><b>{_num(output.get('projected_away_points'),1)}</b><span>{escape(_clean(away.get('team')) or 'Away')} points</span></div>
    <div class="cfbou8-m"><b>{_num(output.get('projected_home_points'),1)}</b><span>{escape(_clean(home.get('team')) or 'Home')} points</span></div>
    <div class="cfbou8-m"><b>{_num(components.get('step8_turnover_sigma_adjustment'))}</b><span>Turnover sigma adj</span></div>
    <div class="cfbou8-m"><b>{_num(components.get('step8_turnover_volatility_signal'))}</b><span>Volatility signal</span></div>
    <div class="cfbou8-m"><b>{_pct(output.get('turnover_engine_coverage'))}</b><span>Turnover coverage</span></div>
    <div class="cfbou8-m"><b>{_pct(output.get('reliability'))}</b><span>Frozen reliability</span></div>
    <div class="cfbou8-m"><b>0.00</b><span>Projected-total adj</span></div>
    <div class="cfbou8-m"><b>0%</b><span>Analysis-line model weight</span></div>
  </div>
</div>
"""


def _components_panel_v8(output: Mapping[str, Any]) -> str:
    frozen = _FROZEN_STEP7_COMPONENTS_PANEL(output)
    if not output.get("ready"):
        return frozen
    c = output.get("components") or {}
    return frozen + f"""
<div class="cfbou8-audit">
  <b>🟧 STEP 8 TURNOVER-VOLATILITY AUDIT</b>
  <span>
    Sigma adjustment {_num(c.get('step8_turnover_sigma_adjustment'))} •
    volatility signal {_num(c.get('step8_turnover_volatility_signal'))} •
    coverage {_pct(c.get('step8_turnover_coverage'))} •
    projected-total adjustment {_num(c.get('step8_projected_total_adjustment'))}.
    Step-7 projected points are preserved exactly; field-position points are not fabricated.
  </span>
</div>
"""


def _final_card_v8(
    game: Mapping[str, Any],
    final: Mapping[str, Any],
) -> str:
    html = _FROZEN_STEP7_FINAL_CARD(game, final)
    html = html.replace(
        "STEP 9 FINAL RULES • STEP 7 THIRD-DOWN-ADJUSTED PROJECTION",
        "STEP 9 FINAL RULES • STEP 8 TURNOVER-VOLATILITY-ADJUSTED UNCERTAINTY",
    )
    html = html.replace(
        "The Step-9 qualification thresholds remain frozen; Step 3 matchup, Step 4 pace, Step 5 explosive, Step 6 red-zone, and Step 7 third-down adjustments occur before those rules are applied.",
        "The Step-9 qualification thresholds remain frozen; Steps 3-7 shape the projection, while Step 8 turnover evidence adjusts uncertainty without moving the projected total.",
    )
    return html


def _clear_stale_scan_state() -> None:
    marker = "cfb_ou_upgrade_step8_scan_state_reset"
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
    st.caption("🟧 CFB O/U INTELLIGENCE V2 • Upgrade Step 8 • turnover-possession volatility ACTIVE")
    st.markdown(_CSS, unsafe_allow_html=True)
    _clear_stale_scan_state()

    original_hero = frozen_v7._hero_v7
    original_slate = frozen_v7.upgraded_slate
    original_model = frozen_v7._model_card_v7
    original_components = frozen_v7._components_panel_v7
    original_final = frozen_v7._final_card_v7

    frozen_v7._hero_v7 = _hero_v8
    frozen_v7.upgraded_slate = upgraded_slate
    frozen_v7._model_card_v7 = _model_card_v8
    frozen_v7._components_panel_v7 = _components_panel_v8
    frozen_v7._final_card_v7 = _final_card_v8
    try:
        return frozen_v7.render_over_under_hub(
            section_header,
            status_info,
            team_logo,
            h,
        )
    finally:
        frozen_v7._hero_v7 = original_hero
        frozen_v7.upgraded_slate = original_slate
        frozen_v7._model_card_v7 = original_model
        frozen_v7._components_panel_v7 = original_components
        frozen_v7._final_card_v7 = original_final


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Upgrade Step 8 Over/Under UI received unsupported market: {market}")
    return render_over_under_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_UPGRADE",
    "MARKET",
    "MODEL_VERSION",
    "_components_panel_v8",
    "_final_card_v8",
    "_hero_v8",
    "_model_card_v8",
    "_turnover_panel",
    "render_cfb_hub",
    "render_over_under_hub",
]
