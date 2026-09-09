"""CFB Over/Under Intelligence V2 — Upgrade Step 11 form + schedule-strength UI.

Additive wrapper over permanently frozen Upgrade Step 10.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import streamlit as st

import cfb_over_under_form_strength_engine_v1 as form_engine
import cfb_over_under_matchup_ui_v10 as frozen_v10
import cfb_over_under_slate_v10 as upgraded_slate

MODEL_VERSION = "CFB OVER/UNDER INTELLIGENCE V2 • UPGRADE STEP 11 FORM + SCHEDULE STRENGTH"
FROZEN_UPGRADE = "cfb_over_under_matchup_ui_v10"
MARKET = "Over/Under"

_FROZEN_STEP10_HERO = frozen_v10._hero_v10
_FROZEN_STEP10_MODEL_CARD = frozen_v10._model_card_v10
_FROZEN_STEP10_COMPONENTS_PANEL = frozen_v10._components_panel_v10
_FROZEN_STEP10_FINAL_CARD = frozen_v10._final_card_v10

_CSS11 = r"""
<style>
.cfbou11{margin:10px 0 2px;border:1px solid rgba(87,232,166,.32);border-radius:18px;background:linear-gradient(145deg,#081b16,#0c1718 58%,#111814);overflow:hidden}
.cfbou11-head{display:flex;justify-content:space-between;gap:8px;align-items:center;padding:10px 12px;border-bottom:1px solid rgba(87,232,166,.14)}
.cfbou11-head b{color:#9af1c7;font-size:.54rem;font-weight:950;letter-spacing:.08em}.cfbou11-head span{border:1px solid #2f6c50;border-radius:999px;padding:4px 7px;background:#0f2a20;color:#b8f5d7;font-size:.39rem;font-weight:950}
.cfbou11-sub{padding:7px 12px;color:#86978f;font-size:.42rem;line-height:1.5;border-bottom:1px solid rgba(87,232,166,.08)}
.cfbou11-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px;padding:10px}.cfbou11-card{border:1px solid rgba(87,232,166,.13);border-radius:12px;background:#0d1715;padding:9px}
.cfbou11-card b{display:block;color:#f1faf5;font-size:.58rem}.cfbou11-card small{display:block;color:#789087;font-size:.34rem;margin-top:3px;line-height:1.45}
.cfbou11-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px;margin-top:8px}.cfbou11-m{border:1px solid rgba(87,232,166,.10);border-radius:9px;background:#0a1311;padding:7px}
.cfbou11-m strong{display:block;color:#bdf3d9;font-size:.58rem}.cfbou11-m span{display:block;color:#6f8179;font-size:.30rem;text-transform:uppercase;margin-top:3px}
.cfbou11-warn{margin:0 10px 10px;border:1px solid #65521e;border-radius:9px;background:#2a230d;color:#dec97b;padding:8px;font-size:.37rem;line-height:1.48}
.cfbou11-ok{margin:0 10px 10px;border:1px solid rgba(87,232,166,.16);border-radius:10px;background:#0c1713;padding:8px;color:#87a899;font-size:.38rem;line-height:1.48}
.cfbou11-audit{margin-top:8px;border:1px solid rgba(87,232,166,.18);border-radius:12px;background:#101815;padding:9px}.cfbou11-audit b{color:#9af1c7;font-size:.46rem}.cfbou11-audit span{display:block;color:#7e9087;font-size:.37rem;line-height:1.45;margin-top:4px}
@media(max-width:760px){.cfbou11-grid{grid-template-columns:1fr}.cfbou11-metrics{grid-template-columns:repeat(3,minmax(0,1fr))}}
</style>
"""


def _clean(v: Any) -> str:
    return str(v or "").strip()


def _num(v: Any, d: int = 1) -> str:
    try:
        return f"{float(v):.{d}f}"
    except Exception:
        return "—"


def _pct(v: Any) -> str:
    try:
        return f"{100 * float(v):.1f}%"
    except Exception:
        return "—"


def _form_card(form: Mapping[str, Any], label: str) -> str:
    return f'''<div class="cfbou11-card"><b>📈 {escape(label)} • current season</b><small>{int(form.get("games") or 0)} completed games • opponent-record coverage {_pct(form.get("opponent_record_coverage"))}</small>
<div class="cfbou11-metrics">
<div class="cfbou11-m"><strong>{_num(form.get("avg_points_for"),1)}</strong><span>Recent PF</span></div>
<div class="cfbou11-m"><strong>{_num(form.get("avg_points_against"),1)}</strong><span>Recent PA</span></div>
<div class="cfbou11-m"><strong>{_pct(form.get("avg_opponent_win_pct"))}</strong><span>Opp win %</span></div>
<div class="cfbou11-m"><strong>{_num(form.get("sos_adjusted_points_for"),1)}</strong><span>SOS-adj PF</span></div>
<div class="cfbou11-m"><strong>{_num(form.get("sos_adjusted_points_against"),1)}</strong><span>SOS-adj PA</span></div>
<div class="cfbou11-m"><strong>{_pct(form.get("quality_factor"))}</strong><span>Signal quality</span></div>
</div></div>'''


def _form_panel(game: Mapping[str, Any], away: Mapping[str, Any], home: Mapping[str, Any]) -> str:
    e = form_engine.build_form_strength_engine(game, away, home)
    if not e.get("model_ready"):
        return f'''<div class="cfbou11"><div class="cfbou11-head"><b>🟩 UPGRADE STEP 11 • CURRENT FORM + SCHEDULE STRENGTH</b><span>FORM GATED</span></div><div class="cfbou11-warn" style="margin-top:10px">{escape(_clean(e.get("reason")) or "Current-season form evidence is incomplete")}. Step 10 remains active; no projection is forced.</div></div>'''
    away_form = e.get("away_form") or {}
    home_form = e.get("home_form") or {}
    return f'''
<div class="cfbou11">
 <div class="cfbou11-head"><b>🟩 UPGRADE STEP 11 • CURRENT FORM + SCHEDULE STRENGTH</b><span>CURRENT SEASON ONLY</span></div>
 <div class="cfbou11-sub">Recent scoring is normalized by verified opponent records, then shrunk by sample size and coverage. Previous-season history stays display-only and cannot move the projection.</div>
 <div class="cfbou11-grid">{_form_card(away_form,_clean(away.get("team")) or "Away")}{_form_card(home_form,_clean(home.get("team")) or "Home")}</div>
 <div class="cfbou11-ok">Projection blend 18% before shrinkage • max ±1.25 points per team • max ±2.00 game-total adjustment • analysis-line weight 0% • direct selection weight 0%.</div>
</div>'''


def _hero_v11(game, away, home):
    return _FROZEN_STEP10_HERO(game, away, home) + _form_panel(game, away, home)


def _model_card_v11(game, away, home, output):
    base = _FROZEN_STEP10_MODEL_CARD(game, away, home, output)
    if not output.get("ready"):
        return base
    c = output.get("components") or {}
    if not output.get("upgrade_step11_applied"):
        return base + f'''<div class="cfbou11-audit"><b>STEP 11 • FORM SIGNAL GATED</b><span>{escape(_clean(output.get("form_strength_reason")) or "Current-season evidence below minimum coverage")}. Step 10 projected total {_num(output.get("projected_total"),1)} remains unchanged.</span></div>'''
    return base + f'''<div class="cfbou11-audit"><b>STEP 11 • BOUNDED CURRENT-FORM ADJUSTMENT</b><span>Step 10 total {_num(output.get("step11_base_projected_total"),1)} → Step 11 {_num(output.get("projected_total"),1)} • delta {_num(c.get("step11_total_form_adjustment"),2)}. Away {_num(c.get("step11_away_form_adjustment"),2)} • Home {_num(c.get("step11_home_form_adjustment"),2)} • σ and reliability unchanged.</span></div>'''


def _components_panel_v11(output):
    frozen = _FROZEN_STEP10_COMPONENTS_PANEL(output)
    if not output.get("ready"):
        return frozen
    c = output.get("components") or {}
    return frozen + f'''<div class="cfbou11-audit"><b>🟩 STEP 11 FORM/STRENGTH AUDIT</b><span>Coverage {_pct(c.get("step11_form_strength_coverage"))} • away expectation {_num(c.get("step11_away_recent_matchup_expectation"),1)} • home expectation {_num(c.get("step11_home_recent_matchup_expectation"),1)} • total adjustment {_num(c.get("step11_total_form_adjustment"),2)} • sigma adjustment {_num(c.get("step11_structural_sigma_adjustment"),2)} • reliability adjustment {_num(c.get("step11_reliability_adjustment"),2)}.</span></div>'''


def _final_card_v11(game, final):
    html = _FROZEN_STEP10_FINAL_CARD(game, final)
    html = html.replace(
        "STEP 9 FINAL RULES • UPGRADE STEP 10 HISTORY-CONTEXT CERTIFIED • MODEL MATH UNCHANGED",
        "STEP 9 FINAL RULES • UPGRADE STEP 11 CURRENT-FORM NORMALIZED PROJECTION",
    )
    return html


def _clear_stale_scan_state():
    marker = "cfb_ou_upgrade_step11_scan_state_reset"
    if st.session_state.get(marker):
        return
    for key in list(st.session_state.keys()):
        if str(key).startswith("cfb_step9_top5_") or str(key).startswith("cfb_step9_scan_diag_"):
            try:
                del st.session_state[key]
            except Exception:
                pass
    st.session_state[marker] = True


def render_over_under_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.caption("🟩 CFB O/U INTELLIGENCE V2 • Upgrade Step 11 • current form + schedule strength ACTIVE")
    st.markdown(frozen_v10.frozen_v9._CSS + frozen_v10._CSS10 + _CSS11, unsafe_allow_html=True)
    _clear_stale_scan_state()
    host = frozen_v10.frozen_v9.frozen_v8
    originals = (
        host._hero_v8,
        host.upgraded_slate,
        host._model_card_v8,
        host._components_panel_v8,
        host._final_card_v8,
    )
    host._hero_v8 = _hero_v11
    host.upgraded_slate = upgraded_slate
    host._model_card_v8 = _model_card_v11
    host._components_panel_v8 = _components_panel_v11
    host._final_card_v8 = _final_card_v11
    try:
        return host.render_over_under_hub(section_header, status_info, team_logo, h)
    finally:
        (
            host._hero_v8,
            host.upgraded_slate,
            host._model_card_v8,
            host._components_panel_v8,
            host._final_card_v8,
        ) = originals


def render_cfb_hub(market, section_header=None, status_info=None, team_logo=None, h=None):
    if market != MARKET:
        raise ValueError(f"Upgrade Step 11 Over/Under UI received unsupported market: {market}")
    return render_over_under_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_UPGRADE",
    "MARKET",
    "MODEL_VERSION",
    "_components_panel_v11",
    "_final_card_v11",
    "_form_panel",
    "_hero_v11",
    "_model_card_v11",
    "render_cfb_hub",
    "render_over_under_hub",
]
