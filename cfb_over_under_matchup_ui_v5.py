"""CFB Over/Under Intelligence V2 — Upgrade Step 5 explosive-play UI.

Additive wrapper over permanently frozen Upgrade Step 4.

Step 5 adds a first-party NCAA explosive-efficiency proxy:
- pass yards/attempt and yards/completion,
- opponent pass yards/attempt and yards/completion allowed,
- rush yards/carry and opponent rush yards/carry allowed,
- FBS/FCS division normalization,
- early-season shrinkage,
- bounded per-team projection adjustments.

True 20+ pass / 10+ rush play rates remain explicitly unavailable rather than
being fabricated.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import streamlit as st

import cfb_over_under_explosive_engine_v1 as explosive_engine
import cfb_over_under_matchup_ui_v4 as frozen_v4
import cfb_over_under_slate_v4 as upgraded_slate

MODEL_VERSION = "CFB OVER/UNDER INTELLIGENCE V2 • UPGRADE STEP 5 EXPLOSIVE"
FROZEN_UPGRADE = "cfb_over_under_matchup_ui_v4"
MARKET = "Over/Under"

_FROZEN_STEP4_HERO = frozen_v4._hero_v4
_FROZEN_STEP4_MODEL_CARD = frozen_v4._model_card_v4
_FROZEN_STEP4_COMPONENTS_PANEL = frozen_v4._components_panel_v4
_FROZEN_STEP4_FINAL_CARD = frozen_v4._final_card_v4

_CSS = r"""
<style>
.cfbou5-exp{margin:10px 0 2px;border:1px solid rgba(255,157,74,.30);border-radius:18px;
background:linear-gradient(145deg,#1a1008,#111923 58%,#0d1418);overflow:hidden}
.cfbou5-head{display:flex;justify-content:space-between;gap:8px;align-items:center;padding:10px 12px;
border-bottom:1px solid rgba(255,157,74,.14)}
.cfbou5-head b{color:#ffb26f;font-size:.54rem;font-weight:950;letter-spacing:.08em}
.cfbou5-head span{border:1px solid #70431f;border-radius:999px;padding:4px 7px;background:#2a180b;
color:#ffc18d;font-size:.39rem;font-weight:950}
.cfbou5-sub{padding:7px 12px;color:#8c989f;font-size:.42rem;line-height:1.5;border-bottom:1px solid rgba(255,157,74,.08)}
.cfbou5-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding:10px}
.cfbou5-side{border:1px solid rgba(255,157,74,.14);border-radius:13px;background:#0a1720;overflow:hidden}
.cfbou5-side-top{display:flex;justify-content:space-between;gap:8px;padding:9px 10px;border-bottom:1px solid rgba(255,157,74,.10)}
.cfbou5-side-top b{display:block;color:#f3f9fc;font-size:.68rem}.cfbou5-side-top small{display:block;color:#738792;font-size:.34rem;margin-top:3px}
.cfbou5-adj{text-align:right}.cfbou5-adj strong{display:block;color:#ffc18d;font-size:.76rem}.cfbou5-adj span{display:block;color:#6e7d84;font-size:.30rem;text-transform:uppercase;margin-top:2px}
.cfbou5-dims{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;padding:8px}
.cfbou5-dim{border:1px solid rgba(255,157,74,.11);border-radius:9px;background:#07131b;padding:7px}
.cfbou5-dim b{display:block;color:#dceaf0;font-size:.46rem}.cfbou5-dim span{display:block;color:#6c818c;font-size:.31rem;line-height:1.4;margin-top:3px}
.cfbou5-dim strong{display:block;color:#ffc28f;font-size:.47rem;margin-top:4px}
.cfbou5-main{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;padding:0 10px 10px}
.cfbou5-m{border:1px solid rgba(255,157,74,.11);border-radius:9px;background:#08131a;padding:7px}
.cfbou5-m b{display:block;color:#eef7fa;font-size:.61rem}.cfbou5-m span{display:block;color:#687c86;font-size:.30rem;text-transform:uppercase;margin-top:2px}
.cfbou5-foot{padding:8px 11px;border-top:1px solid rgba(255,157,74,.08);color:#6e8089;font-size:.37rem;line-height:1.48}
.cfbou5-gate{margin:10px;border:1px solid #6c5720;border-radius:10px;background:#2b240d;color:#d9c477;padding:9px;font-size:.43rem;line-height:1.45}
.cfbou5-model{margin-top:10px;border:1px solid rgba(255,170,92,.25);border-radius:16px;background:linear-gradient(145deg,#171008,#071924,#101612);overflow:hidden}
.cfbou5-model-head{display:flex;justify-content:space-between;gap:8px;padding:10px 11px;border-bottom:1px solid rgba(255,170,92,.12)}
.cfbou5-model-head b{color:#ffbd83;font-size:.52rem;font-weight:950;letter-spacing:.07em}.cfbou5-model-head span{color:#9a7c62;font-size:.38rem;font-weight:900}
.cfbou5-model-main{display:grid;grid-template-columns:1.2fr 1fr;gap:8px;padding:10px}
.cfbou5-total,.cfbou5-prob{border:1px solid rgba(255,170,92,.12);border-radius:11px;background:#11150f;padding:9px}
.cfbou5-total small,.cfbou5-prob small{display:block;color:#7f806a;font-size:.35rem;text-transform:uppercase;font-weight:900}
.cfbou5-total strong{display:block;color:#fff8ef;font-size:1.35rem;margin-top:3px}.cfbou5-total b{display:block;color:#b59b83;font-size:.42rem;margin-top:4px}
.cfbou5-prob strong{display:block;color:#f6e9da;font-size:.70rem;margin-top:5px}.cfbou5-prob b{display:block;color:#8f8273;font-size:.38rem;margin-top:4px}
.cfbou5-model-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;padding:0 10px 10px}
.cfbou5-audit{margin-top:8px;border:1px solid rgba(255,170,92,.17);border-radius:12px;background:#10141a;padding:9px}
.cfbou5-audit b{color:#ffc18b;font-size:.46rem}.cfbou5-audit span{display:block;color:#7a858c;font-size:.37rem;line-height:1.45;margin-top:4px}
@media(max-width:760px){.cfbou5-grid{grid-template-columns:1fr}.cfbou5-main{grid-template-columns:repeat(2,minmax(0,1fr))}
.cfbou5-model-main{grid-template-columns:1fr}.cfbou5-model-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
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


def _dimension_html(title: str, dim: Mapping[str, Any], kind: str) -> str:
    ready = bool(dim.get("ready"))
    if kind == "pass":
        details = (
            f"Y/A {_num(dim.get('offense_yards_per_attempt'))} vs allowed "
            f"{_num(dim.get('defense_yards_per_attempt_allowed'))}<br>"
            f"Y/C {_num(dim.get('offense_yards_per_completion'))} vs allowed "
            f"{_num(dim.get('defense_yards_per_completion_allowed'))}"
        )
    else:
        details = (
            f"Y/Rush {_num(dim.get('offense_yards_per_rush'))} vs allowed "
            f"{_num(dim.get('defense_yards_per_rush_allowed'))}"
        )
    signal = _num(dim.get("signal"), 3) if ready else "—"
    return f"""
<div class="cfbou5-dim">
  <b>{escape(title)}</b>
  <span>{details}</span>
  <strong>{'SIGNAL ' + signal if ready else 'UNAVAILABLE'}</strong>
</div>
"""


def _side_html(side: Mapping[str, Any]) -> str:
    adjustment = float(side.get("points_adjustment") or 0.0)
    sign = "+" if adjustment > 0 else ""
    return f"""
<div class="cfbou5-side">
  <div class="cfbou5-side-top">
    <div>
      <b>{escape(_clean(side.get('offense_team')) or 'Offense')} offense vs {escape(_clean(side.get('defense_team')) or 'Defense')} defense</b>
      <small>{escape(_clean(side.get('offense_division')))} offense • {escape(_clean(side.get('defense_division')))} defense • {escape(_clean(side.get('label')) or 'BALANCED')}</small>
    </div>
    <div class="cfbou5-adj">
      <strong>{sign}{adjustment:.2f}</strong>
      <span>projected pts adj</span>
    </div>
  </div>
  <div class="cfbou5-dims">
    {_dimension_html('Pass chunk efficiency', side.get('pass') or {}, 'pass')}
    {_dimension_html('Rush chunk efficiency', side.get('rush') or {}, 'rush')}
  </div>
</div>
"""


def _explosive_panel(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> str:
    engine = explosive_engine.build_explosive_engine(game, away, home)
    if not engine.get("model_ready"):
        return f"""
<div class="cfbou5-exp">
  <div class="cfbou5-head">
    <b>💥 UPGRADE STEP 5 • EXPLOSIVE-PLAY ENGINE</b>
    <span>EXPLOSIVE ADJUSTMENT GATED</span>
  </div>
  <div class="cfbou5-gate">
    {escape(_clean(engine.get('reason')) or 'Verified explosive proxy evidence is below the minimum threshold')}.
    Step 4 remains the active projection for this matchup.
  </div>
</div>
"""

    away_side = engine.get("away_offense") or {}
    home_side = engine.get("home_offense") or {}
    return f"""
<div class="cfbou5-exp">
  <div class="cfbou5-head">
    <b>💥 UPGRADE STEP 5 • EXPLOSIVE-PLAY ENGINE</b>
    <span>ACTIVE • MAX ±{explosive_engine.MAX_TEAM_EXPLOSIVE_ADJUSTMENT:.2f} PTS / TEAM</span>
  </div>
  <div class="cfbou5-sub">
    First-party NCAA pass Y/A, pass Y/C and rush Y/carry are matched against opponent allowed rates,
    normalized to each team's FBS/FCS baseline, and shrunk for early samples. The analysis line has 0% explosive weight.
  </div>
  <div class="cfbou5-grid">
    {_side_html(away_side)}
    {_side_html(home_side)}
  </div>
  <div class="cfbou5-main">
    <div class="cfbou5-m"><b>{_pct(away_side.get('coverage'))}</b><span>Away proxy coverage</span></div>
    <div class="cfbou5-m"><b>{_pct(home_side.get('coverage'))}</b><span>Home proxy coverage</span></div>
    <div class="cfbou5-m"><b>{_pct(away_side.get('sample_factor'))}</b><span>Away sample weight</span></div>
    <div class="cfbou5-m"><b>{_pct(home_side.get('sample_factor'))}</b><span>Home sample weight</span></div>
  </div>
  <div class="cfbou5-foot">
    True 20+ yard pass-play and 10+ yard run-play rates are not exposed in the certified NCAA team selector,
    so Step 5 does not invent them. This is an explicit explosive-efficiency proxy using per-attempt/per-completion evidence.
    Mixed FBS/FCS games are normalized within each team's own division instead of comparing rank pools.
  </div>
</div>
"""


def _hero_v5(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> str:
    return _FROZEN_STEP4_HERO(game, away, home) + _explosive_panel(game, away, home)


def _model_card_v5(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    output: Mapping[str, Any],
) -> str:
    if not output.get("ready"):
        return _FROZEN_STEP4_MODEL_CARD(game, away, home, output)

    applied = bool(output.get("upgrade_step5_applied"))
    badge = "EXPLOSIVE ENGINE APPLIED" if applied else "STEP 4 FALLBACK"
    base_total = output.get("step5_base_projected_total")
    if base_total is None:
        base_total = output.get("projected_total")
    components = output.get("components") or {}

    return f"""
<div class="cfbou5-model">
  <div class="cfbou5-model-head">
    <b>STEP 5 • EXPLOSIVE-ADJUSTED OVER/UNDER MODEL</b>
    <span>{escape(badge)} • LINE WEIGHT 0%</span>
  </div>
  <div class="cfbou5-model-main">
    <div class="cfbou5-total">
      <small>Projected game total</small>
      <strong>{_num(output.get('projected_total'),1)}</strong>
      <b>Step 4 {_num(base_total,1)} → explosive adjusted {_num(output.get('projected_total'),1)}</b>
    </div>
    <div class="cfbou5-prob">
      <small>Current O/U probabilities at analysis line {_num(output.get('analysis_line'),1)}</small>
      <strong>OVER {_pct(output.get('over_probability'))} • UNDER {_pct(output.get('under_probability'))}</strong>
      <b>{escape(_clean(output.get('model_lean')) or 'PASS')} lean • push {_pct(output.get('push_probability'))}</b>
    </div>
  </div>
  <div class="cfbou5-model-grid">
    <div class="cfbou5-m"><b>{_num(output.get('projected_away_points'),1)}</b><span>{escape(_clean(away.get('team')) or 'Away')} points</span></div>
    <div class="cfbou5-m"><b>{_num(output.get('projected_home_points'),1)}</b><span>{escape(_clean(home.get('team')) or 'Home')} points</span></div>
    <div class="cfbou5-m"><b>{_num(components.get('step5_away_explosive_adjustment'))}</b><span>Away explosive adj</span></div>
    <div class="cfbou5-m"><b>{_num(components.get('step5_home_explosive_adjustment'))}</b><span>Home explosive adj</span></div>
    <div class="cfbou5-m"><b>{_num(components.get('step5_total_explosive_adjustment'))}</b><span>Total explosive adj</span></div>
    <div class="cfbou5-m"><b>{_pct(output.get('explosive_engine_coverage'))}</b><span>Explosive coverage</span></div>
    <div class="cfbou5-m"><b>{_pct(output.get('reliability'))}</b><span>Frozen reliability</span></div>
    <div class="cfbou5-m"><b>0%</b><span>Analysis-line model weight</span></div>
  </div>
</div>
"""


def _components_panel_v5(output: Mapping[str, Any]) -> str:
    frozen = _FROZEN_STEP4_COMPONENTS_PANEL(output)
    if not output.get("ready"):
        return frozen
    c = output.get("components") or {}
    return frozen + f"""
<div class="cfbou5-audit">
  <b>💥 STEP 5 EXPLOSIVE AUDIT</b>
  <span>
    Away adjustment {_num(c.get('step5_away_explosive_adjustment'))} •
    home adjustment {_num(c.get('step5_home_explosive_adjustment'))} •
    total adjustment {_num(c.get('step5_total_explosive_adjustment'))} •
    engine coverage {_pct(c.get('step5_explosive_coverage'))}.
    Frozen reliability and structural sigma are intentionally unchanged.
  </span>
</div>
"""


def _final_card_v5(
    game: Mapping[str, Any],
    final: Mapping[str, Any],
) -> str:
    html = _FROZEN_STEP4_FINAL_CARD(game, final)
    html = html.replace(
        "STEP 9 FINAL RULES • STEP 4 PACE-ADJUSTED PROJECTION",
        "STEP 9 FINAL RULES • STEP 5 EXPLOSIVE-ADJUSTED PROJECTION",
    )
    html = html.replace(
        "The Step-9 qualification thresholds remain frozen; Step 3 matchup and Step 4 pace adjustments occur before those rules are applied.",
        "The Step-9 qualification thresholds remain frozen; Step 3 matchup, Step 4 pace, and Step 5 explosive adjustments occur before those rules are applied.",
    )
    return html


def _clear_stale_scan_state() -> None:
    marker = "cfb_ou_upgrade_step5_scan_state_reset"
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
    st.caption("💥 CFB O/U INTELLIGENCE V2 • Upgrade Step 5 • explosive-play engine ACTIVE")
    st.markdown(_CSS, unsafe_allow_html=True)
    _clear_stale_scan_state()

    original_hero = frozen_v4._hero_v4
    original_slate = frozen_v4.upgraded_slate
    original_model = frozen_v4._model_card_v4
    original_components = frozen_v4._components_panel_v4
    original_final = frozen_v4._final_card_v4

    frozen_v4._hero_v4 = _hero_v5
    frozen_v4.upgraded_slate = upgraded_slate
    frozen_v4._model_card_v4 = _model_card_v5
    frozen_v4._components_panel_v4 = _components_panel_v5
    frozen_v4._final_card_v4 = _final_card_v5
    try:
        return frozen_v4.render_over_under_hub(
            section_header,
            status_info,
            team_logo,
            h,
        )
    finally:
        frozen_v4._hero_v4 = original_hero
        frozen_v4.upgraded_slate = original_slate
        frozen_v4._model_card_v4 = original_model
        frozen_v4._components_panel_v4 = original_components
        frozen_v4._final_card_v4 = original_final


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Upgrade Step 5 Over/Under UI received unsupported market: {market}")
    return render_over_under_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_UPGRADE",
    "MARKET",
    "MODEL_VERSION",
    "_components_panel_v5",
    "_explosive_panel",
    "_final_card_v5",
    "_hero_v5",
    "_model_card_v5",
    "render_cfb_hub",
    "render_over_under_hub",
]
