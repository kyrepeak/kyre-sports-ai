"""CFB Over/Under Intelligence V2 — Upgrade Step 3 matchup-engine UI.

Additive wrapper over permanently frozen Upgrade Step 2.

Step 3 activates the first post-freeze projection adjustment:
- offense vs opponent defense is evaluated across eight NCAA categories,
- adjustments are bounded and coverage-gated,
- frozen Step-9 final selection thresholds remain unchanged,
- the user-entered analysis line still has 0% projection/matchup weight.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import streamlit as st

import cfb_over_under_matchup_engine_v1 as engine
import cfb_over_under_matchup_ui_v2 as frozen_v2
import cfb_over_under_slate_v2 as upgraded_slate

MODEL_VERSION = "CFB OVER/UNDER INTELLIGENCE V2 • UPGRADE STEP 3 OFFENSE VS DEFENSE"
FROZEN_UPGRADE = "cfb_over_under_matchup_ui_v2"
MARKET = "Over/Under"

_FROZEN_STEP2_HERO = frozen_v2._enhanced_hero_v2
_HUB3 = frozen_v2.frozen_v1.frozen_v3
_HUB2 = _HUB3.frozen_v2
_FROZEN_MODEL_CARD = _HUB2._model_card
_FROZEN_COMPONENTS_PANEL = _HUB2._components_panel
_FROZEN_FINAL_CARD = _HUB3._final_card

_CSS = r"""
<style>
.cfbou3-engine{margin:9px 0 2px;border:1px solid rgba(238,107,90,.28);border-radius:18px;
background:linear-gradient(145deg,#1a0d0b,#111b25 55%,#071720);overflow:hidden}
.cfbou3-head{display:flex;justify-content:space-between;gap:8px;align-items:center;padding:10px 12px;
border-bottom:1px solid rgba(238,107,90,.14);background:rgba(30,10,8,.33)}
.cfbou3-head b{color:#ff9c8e;font-size:.54rem;font-weight:950;letter-spacing:.08em}
.cfbou3-head span{border:1px solid #6d392f;border-radius:999px;padding:4px 7px;background:#301813;
color:#ffb0a4;font-size:.39rem;font-weight:950}
.cfbou3-sub{padding:7px 12px;color:#8da0aa;font-size:.43rem;line-height:1.5;border-bottom:1px solid rgba(238,107,90,.08)}
.cfbou3-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding:10px}
.cfbou3-side{border:1px solid rgba(144,189,216,.15);border-radius:14px;background:rgba(4,16,25,.66);overflow:hidden}
.cfbou3-side-top{display:flex;justify-content:space-between;gap:8px;align-items:flex-start;padding:9px 10px;
border-bottom:1px solid rgba(144,189,216,.10)}
.cfbou3-side-top b{color:#f3fbff;font-size:.76rem;font-weight:950;line-height:1.25}
.cfbou3-side-top small{display:block;color:#6f8997;font-size:.34rem;margin-top:3px;font-weight:850}
.cfbou3-adj{text-align:right}.cfbou3-adj strong{display:block;color:#7be6b0;font-size:.76rem}
.cfbou3-adj span{display:block;color:#607884;font-size:.30rem;text-transform:uppercase;font-weight:900;margin-top:2px}
.cfbou3-dims{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px;padding:8px}
.cfbou3-dim{border:1px solid rgba(102,157,188,.12);border-radius:9px;background:#081823;padding:7px;min-width:0}
.cfbou3-dim strong{display:block;color:#d8e9f1;font-size:.46rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cfbou3-dim span{display:block;color:#668493;font-size:.31rem;margin-top:3px;line-height:1.3}
.cfbou3-dim em{display:block;font-style:normal;font-size:.32rem;font-weight:950;margin-top:4px}
.cfbou3-dim.over em{color:#7de3ad}.cfbou3-dim.under em{color:#ff9a8b}.cfbou3-dim.neutral em{color:#d5c77c}
.cfbou3-foot{padding:8px 11px;border-top:1px solid rgba(238,107,90,.08);color:#687e89;font-size:.37rem;line-height:1.45}
.cfbou3-gate{margin:10px;border:1px solid #6c5720;border-radius:10px;background:#2b240d;color:#d9c477;
padding:9px;font-size:.43rem;line-height:1.45}
.cfbou3-model{margin-top:10px;border:1px solid rgba(89,221,162,.28);border-radius:17px;
background:linear-gradient(145deg,#071912,#0b1822);overflow:hidden}
.cfbou3-model-head{display:flex;justify-content:space-between;gap:8px;padding:10px 11px;border-bottom:1px solid rgba(89,221,162,.13)}
.cfbou3-model-head b{color:#8ce9bb;font-size:.52rem;font-weight:950;letter-spacing:.07em}.cfbou3-model-head span{color:#6d9982;font-size:.39rem;font-weight:900}
.cfbou3-model-main{display:grid;grid-template-columns:1.25fr 1fr;gap:8px;padding:10px}
.cfbou3-total,.cfbou3-prob{border:1px solid rgba(116,185,155,.13);border-radius:11px;background:#081a16;padding:9px}
.cfbou3-total small,.cfbou3-prob small{display:block;color:#668779;font-size:.35rem;text-transform:uppercase;font-weight:900}
.cfbou3-total strong{display:block;color:#f1fff8;font-size:1.35rem;margin-top:3px}.cfbou3-total b{display:block;color:#90b6a5;font-size:.42rem;margin-top:4px}
.cfbou3-prob strong{display:block;color:#d8f5e7;font-size:.70rem;margin-top:5px}.cfbou3-prob b{display:block;color:#78988a;font-size:.38rem;margin-top:4px}
.cfbou3-model-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;padding:0 10px 10px}
.cfbou3-m{border:1px solid rgba(108,171,144,.12);border-radius:9px;background:#071611;padding:7px}
.cfbou3-m b{display:block;color:#cceadd;font-size:.57rem}.cfbou3-m span{display:block;color:#627f73;font-size:.30rem;text-transform:uppercase;margin-top:2px}
.cfbou3-audit{margin-top:8px;border:1px solid rgba(122,181,210,.17);border-radius:12px;background:#08141c;padding:9px}
.cfbou3-audit b{color:#9bcce2;font-size:.46rem}.cfbou3-audit span{display:block;color:#6e8792;font-size:.37rem;line-height:1.45;margin-top:4px}
@media(max-width:760px){
 .cfbou3-grid{grid-template-columns:1fr}.cfbou3-model-main{grid-template-columns:1fr}
 .cfbou3-model-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
}
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


def _dimension_html(row: Mapping[str, Any]) -> str:
    edge = row.get("edge")
    try:
        x = float(edge)
    except Exception:
        x = None
    if x is None:
        klass = "neutral"
    elif x > 0.10:
        klass = "over"
    elif x < -0.10:
        klass = "under"
    else:
        klass = "neutral"

    offense_rank = row.get("offense_rank")
    defense_rank = row.get("defense_rank")
    off_text = f"#{int(offense_rank)}" if offense_rank is not None else "—"
    def_text = f"#{int(defense_rank)}" if defense_rank is not None else "—"
    return f"""
<div class="cfbou3-dim {klass}">
  <strong>{escape(_clean(row.get('label')) or 'Matchup')}</strong>
  <span>OFF {off_text} vs DEF {def_text}</span>
  <em>{escape(_clean(row.get('edge_label')) or 'UNAVAILABLE')}</em>
</div>
"""


def _side_html(side: Mapping[str, Any]) -> str:
    dims = side.get("dimensions") or {}
    rows = "".join(
        _dimension_html(dims.get(key) or {})
        for key, *_ in engine._DIMENSIONS
    )
    adjustment = float(side.get("points_adjustment") or 0.0)
    sign = "+" if adjustment > 0 else ""
    return f"""
<div class="cfbou3-side">
  <div class="cfbou3-side-top">
    <div>
      <b>{escape(_clean(side.get('offense_team')) or 'Offense')} offense<br>vs {escape(_clean(side.get('defense_team')) or 'Defense')} defense</b>
      <small>{escape(_clean(side.get('overall')) or 'BALANCED')} • {100.0 * float(side.get('coverage') or 0.0):.0f}% weighted coverage</small>
    </div>
    <div class="cfbou3-adj">
      <strong>{sign}{adjustment:.2f}</strong>
      <span>projected pts adj</span>
    </div>
  </div>
  <div class="cfbou3-dims">{rows}</div>
</div>
"""


def _engine_panel(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> str:
    result = engine.build_matchup_engine(game, away, home)
    if not result.get("model_ready"):
        reason = escape(
            _clean(result.get("reason"))
            or "required matchup categories are below the minimum evidence threshold"
        )
        return f"""
<div class="cfbou3-engine">
  <div class="cfbou3-head">
    <b>⚔️ UPGRADE STEP 3 • OFFENSE VS DEFENSE ENGINE</b>
    <span>NO INVENTED MATCHUP ADJUSTMENT</span>
  </div>
  <div class="cfbou3-gate">
    Step-3 adjustment is gated: {reason}. Frozen Step-8 projection remains active for this matchup.
  </div>
</div>
"""

    return f"""
<div class="cfbou3-engine">
  <div class="cfbou3-head">
    <b>⚔️ UPGRADE STEP 3 • OFFENSE VS DEFENSE ENGINE</b>
    <span>ACTIVE • MAX ±{engine.MAX_TEAM_MATCHUP_ADJUSTMENT:.1f} PTS / TEAM</span>
  </div>
  <div class="cfbou3-sub">
    Each offense is compared directly with the opposing defense across scoring, total yards,
    passing, rushing, third down, red zone, sack pressure, and turnover pressure.
    Missing categories contribute zero. The analysis line has 0% matchup weight.
  </div>
  <div class="cfbou3-grid">
    {_side_html(result.get('away_offense') or {})}
    {_side_html(result.get('home_offense') or {})}
  </div>
  <div class="cfbou3-foot">
    EPA/play and success rate are not fabricated from incomplete evidence; they remain unavailable
    until a later verified derivation/source is certified. This engine is same-division only so
    FBS and FCS ranking pools are never compared as if they were equivalent.
  </div>
</div>
"""


def _enhanced_hero_v3(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> str:
    return _FROZEN_STEP2_HERO(game, away, home) + _engine_panel(game, away, home)


def _model_card_v3(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    output: Mapping[str, Any],
) -> str:
    if not output.get("ready"):
        return _FROZEN_MODEL_CARD(game, away, home, output)

    applied = bool(output.get("upgrade_step3_applied"))
    badge = "MATCHUP ENGINE APPLIED" if applied else "FROZEN STEP-8 FALLBACK"
    base_total = output.get("base_projected_total")
    if base_total is None:
        base_total = output.get("projected_total")
    components = output.get("components") or {}
    away_adj = components.get("step3_away_matchup_adjustment")
    home_adj = components.get("step3_home_matchup_adjustment")

    return f"""
<div class="cfbou3-model">
  <div class="cfbou3-model-head">
    <b>STEP 3 • MATCHUP-ADJUSTED OVER/UNDER MODEL</b>
    <span>{escape(badge)} • LINE WEIGHT 0%</span>
  </div>
  <div class="cfbou3-model-main">
    <div class="cfbou3-total">
      <small>Projected game total</small>
      <strong>{_num(output.get('projected_total'))}</strong>
      <b>Frozen base {_num(base_total)} → matchup adjusted {_num(output.get('projected_total'))}</b>
    </div>
    <div class="cfbou3-prob">
      <small>Current O/U probabilities at analysis line {_num(output.get('analysis_line'))}</small>
      <strong>OVER {_pct(output.get('over_probability'))} • UNDER {_pct(output.get('under_probability'))}</strong>
      <b>{escape(_clean(output.get('model_lean')) or 'PASS')} lean • push {_pct(output.get('push_probability'))}</b>
    </div>
  </div>
  <div class="cfbou3-model-grid">
    <div class="cfbou3-m"><b>{_num(output.get('projected_away_points'))}</b><span>{escape(_clean(away.get('team')) or 'Away')} points</span></div>
    <div class="cfbou3-m"><b>{_num(output.get('projected_home_points'))}</b><span>{escape(_clean(home.get('team')) or 'Home')} points</span></div>
    <div class="cfbou3-m"><b>{_num(away_adj, 2)}</b><span>Away matchup adj</span></div>
    <div class="cfbou3-m"><b>{_num(home_adj, 2)}</b><span>Home matchup adj</span></div>
    <div class="cfbou3-m"><b>{_pct(output.get('matchup_engine_coverage'))}</b><span>Matchup coverage</span></div>
    <div class="cfbou3-m"><b>{_pct(output.get('reliability'))}</b><span>Frozen reliability</span></div>
    <div class="cfbou3-m"><b>{_num(output.get('structural_total_sigma'), 2)}</b><span>Frozen sigma</span></div>
    <div class="cfbou3-m"><b>0%</b><span>Analysis-line model weight</span></div>
  </div>
</div>
"""


def _components_panel_v3(output: Mapping[str, Any]) -> str:
    frozen = _FROZEN_COMPONENTS_PANEL(output)
    if not output.get("ready"):
        return frozen
    c = output.get("components") or {}
    return frozen + f"""
<div class="cfbou3-audit">
  <b>⚔️ STEP 3 MATCHUP AUDIT</b>
  <span>
    Away matchup adjustment {_num(c.get('step3_away_matchup_adjustment'), 2)} •
    Home matchup adjustment {_num(c.get('step3_home_matchup_adjustment'), 2)} •
    Total matchup adjustment {_num(c.get('step3_total_matchup_adjustment'), 2)} •
    matchup coverage {_pct(output.get('matchup_engine_coverage'))}.
    Frozen reliability and structural sigma are intentionally not inflated by Step 3.
  </span>
</div>
"""


def _final_card_v3(
    game: Mapping[str, Any],
    final: Mapping[str, Any],
) -> str:
    html = _FROZEN_FINAL_CARD(game, final)
    html = html.replace(
        "STEP 9 • FINAL OVER/UNDER SELECTION",
        "STEP 9 FINAL RULES • STEP 3 MATCHUP-ADJUSTED PROJECTION",
    )
    html = html.replace(
        "The final rule does not change Step-8 projection math.",
        "The Step-9 qualification thresholds remain frozen; Step 3 adjusts the projection before those rules are applied.",
    )
    return html


def _clear_stale_scan_state() -> None:
    marker = "cfb_ou_upgrade_step3_scan_state_reset"
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
    st.caption("⚔️ CFB O/U INTELLIGENCE V2 • Upgrade Step 3 • offense-vs-defense engine ACTIVE")
    st.markdown(_CSS, unsafe_allow_html=True)
    _clear_stale_scan_state()

    original_hero = frozen_v2._enhanced_hero_v2
    original_slate = _HUB3.slate
    original_model_card = _HUB2._model_card
    original_components = _HUB2._components_panel
    original_final_card = _HUB3._final_card

    frozen_v2._enhanced_hero_v2 = _enhanced_hero_v3
    _HUB3.slate = upgraded_slate
    _HUB2._model_card = _model_card_v3
    _HUB2._components_panel = _components_panel_v3
    _HUB3._final_card = _final_card_v3
    try:
        return frozen_v2.render_over_under_hub(
            section_header,
            status_info,
            team_logo,
            h,
        )
    finally:
        frozen_v2._enhanced_hero_v2 = original_hero
        _HUB3.slate = original_slate
        _HUB2._model_card = original_model_card
        _HUB2._components_panel = original_components
        _HUB3._final_card = original_final_card


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Upgrade Step 3 Over/Under UI received unsupported market: {market}")
    return render_over_under_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_UPGRADE",
    "MARKET",
    "MODEL_VERSION",
    "_components_panel_v3",
    "_engine_panel",
    "_enhanced_hero_v3",
    "_final_card_v3",
    "_model_card_v3",
    "render_cfb_hub",
    "render_over_under_hub",
]
