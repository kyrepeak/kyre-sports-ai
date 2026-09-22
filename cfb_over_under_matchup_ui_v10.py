"""CFB Over/Under Intelligence V2 — Upgrade Step 10 historical context UI.

Additive wrapper over permanently frozen Upgrade Step 9.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import streamlit as st

import cfb_over_under_history_engine_v1 as history_engine
import cfb_over_under_matchup_ui_v9 as frozen_v9
import cfb_over_under_slate_v9 as upgraded_slate

MODEL_VERSION = "CFB OVER/UNDER INTELLIGENCE V2 • UPGRADE STEP 10 HISTORY"
FROZEN_UPGRADE = "cfb_over_under_matchup_ui_v9"
MARKET = "Over/Under"

_FROZEN_STEP9_HERO = frozen_v9._hero_v9
_FROZEN_STEP9_MODEL_CARD = frozen_v9._model_card_v9
_FROZEN_STEP9_COMPONENTS_PANEL = frozen_v9._components_panel_v9
_FROZEN_STEP9_FINAL_CARD = frozen_v9._final_card_v9

_CSS10 = r"""
<style>
.cfbou10{margin:10px 0 2px;border:1px solid rgba(196,155,255,.35);border-radius:18px;background:linear-gradient(145deg,#151021,#101722 58%,#101718);overflow:hidden}
.cfbou10-head{display:flex;justify-content:space-between;gap:8px;align-items:center;padding:10px 12px;border-bottom:1px solid rgba(196,155,255,.15)}
.cfbou10-head b{color:#d9c0ff;font-size:.54rem;font-weight:950;letter-spacing:.08em}.cfbou10-head span{border:1px solid #5a4478;border-radius:999px;padding:4px 7px;background:#21172f;color:#e5d5ff;font-size:.39rem;font-weight:950}
.cfbou10-sub{padding:7px 12px;color:#94909d;font-size:.42rem;line-height:1.5;border-bottom:1px solid rgba(196,155,255,.08)}
.cfbou10-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px;padding:10px}.cfbou10-card{border:1px solid rgba(196,155,255,.14);border-radius:12px;background:#12131b;padding:9px}
.cfbou10-card b{display:block;color:#f7f4fb;font-size:.58rem}.cfbou10-card small{display:block;color:#817d8a;font-size:.34rem;margin-top:3px;line-height:1.45}
.cfbou10-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px;margin-top:8px}.cfbou10-m{border:1px solid rgba(196,155,255,.10);border-radius:9px;background:#0e1017;padding:7px}
.cfbou10-m strong{display:block;color:#e2d3f9;font-size:.58rem}.cfbou10-m span{display:block;color:#76717e;font-size:.30rem;text-transform:uppercase;margin-top:3px}
.cfbou10-h2h{margin:0 10px 10px;border:1px solid rgba(196,155,255,.14);border-radius:12px;background:#11131a;padding:9px}.cfbou10-h2h b{color:#f7f3fb;font-size:.52rem}.cfbou10-h2h span{display:block;color:#817b88;font-size:.36rem;line-height:1.5;margin-top:4px}
.cfbou10-warn{margin:0 10px 10px;border:1px solid #65521e;border-radius:9px;background:#2a230d;color:#dec97b;padding:8px;font-size:.37rem;line-height:1.48}
.cfbou10-audit{margin-top:8px;border:1px solid rgba(196,155,255,.18);border-radius:12px;background:#15131a;padding:9px}.cfbou10-audit b{color:#d9c0ff;font-size:.46rem}.cfbou10-audit span{display:block;color:#85808a;font-size:.37rem;line-height:1.45;margin-top:4px}
@media(max-width:760px){.cfbou10-grid{grid-template-columns:1fr}.cfbou10-metrics{grid-template-columns:repeat(3,minmax(0,1fr))}}
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


def _recent_card(summary: Mapping[str, Any], label: str) -> str:
    if not summary.get("games"):
        return f'<div class="cfbou10-card"><b>{escape(label)}</b><small>Completed pre-kickoff history unavailable.</small></div>'
    return f'''<div class="cfbou10-card"><b>📚 {escape(label)} • last {int(summary.get("games") or 0)}</b><small>Only completed games before this kickoff are included.</small>
<div class="cfbou10-metrics">
<div class="cfbou10-m"><strong>{_num(summary.get("avg_points_for"),1)}</strong><span>Avg PF</span></div>
<div class="cfbou10-m"><strong>{_num(summary.get("avg_points_against"),1)}</strong><span>Avg PA</span></div>
<div class="cfbou10-m"><strong>{_num(summary.get("avg_combined_total"),1)}</strong><span>Avg total</span></div>
</div></div>'''


def _h2h(engine: Mapping[str, Any], away: Mapping[str, Any], home: Mapping[str, Any]) -> str:
    h2h = engine.get("head_to_head") or {}
    if not h2h.get("meetings"):
        return '<div class="cfbou10-h2h"><b>🤝 Head-to-head history</b><span>No verified ESPN head-to-head meeting was found inside the six-season lookback. Nothing is fabricated.</span></div>'
    latest = h2h.get("latest") or {}
    date = _clean(latest.get("date"))[:10] or "date unavailable"
    away_name = _clean(away.get("team")) or "Away"
    home_name = _clean(home.get("team")) or "Home"
    score = f'{_num(latest.get("points_for"),0)}–{_num(latest.get("points_against"),0)}'
    return f'''<div class="cfbou10-h2h"><b>🤝 Head-to-head history • {int(h2h.get("meetings") or 0)} verified meeting(s)</b><span>Latest: {escape(date)} • {escape(away_name)} {escape(score)} {escape(home_name)} • average combined total {_num(h2h.get("avg_combined_total"),1)}.</span></div>'''


def _history_panel(game: Mapping[str, Any], away: Mapping[str, Any], home: Mapping[str, Any]) -> str:
    e = history_engine.build_history_engine(game, away, home)
    if not e.get("model_ready"):
        return f'''<div class="cfbou10"><div class="cfbou10-head"><b>🟪 UPGRADE STEP 10 • HISTORICAL MATCHUP CONTEXT</b><span>HISTORY GATED</span></div><div class="cfbou10-warn" style="margin-top:10px">{escape(_clean(e.get("reason")) or "Verified pre-kickoff history is incomplete")}. Step 9 model math remains active and unchanged.</div></div>'''
    return f'''
<div class="cfbou10">
 <div class="cfbou10-head"><b>🟪 UPGRADE STEP 10 • HISTORICAL MATCHUP CONTEXT</b><span>CONTEXT ONLY • 0% MODEL WEIGHT</span></div>
 <div class="cfbou10-sub">ESPN completed-game history is filtered strictly to events before this kickoff. We show recent scoring shape and true team-vs-team history without letting old rosters masquerade as current predictive evidence.</div>
 <div class="cfbou10-grid">{_recent_card(e.get("away_recent") or {}, _clean(away.get("team")) or "Away")}{_recent_card(e.get("home_recent") or {}, _clean(home.get("team")) or "Home")}</div>
 {_h2h(e, away, home)}
 <div class="cfbou10-warn">Historical projection weight 0% • selection weight 0% • analysis-line weight 0%. Roster continuity and opponent-strength normalization are not certified yet, so Step 10 cannot move the projection or final pick.</div>
</div>'''


def _hero_v10(game, away, home):
    return _FROZEN_STEP9_HERO(game, away, home) + _history_panel(game, away, home)


def _model_card_v10(game, away, home, output):
    base = _FROZEN_STEP9_MODEL_CARD(game, away, home, output)
    if not output.get("ready"):
        return base
    return base + f'''<div class="cfbou10-audit"><b>STEP 10 • HISTORY CONTEXT CERTIFIED</b><span>Projected total {_num(output.get("projected_total"),1)} • σ {_num(output.get("structural_total_sigma"),2)} • reliability {_pct(output.get("reliability"))}. All are inherited unchanged from Step 9; history weight is 0%.</span></div>'''


def _components_panel_v10(output):
    frozen = _FROZEN_STEP9_COMPONENTS_PANEL(output)
    if not output.get("ready"):
        return frozen
    c = output.get("components") or {}
    return frozen + f'''<div class="cfbou10-audit"><b>🟪 STEP 10 HISTORY AUDIT</b><span>History coverage {_pct(c.get("step10_history_coverage"))} • away recent games {int(c.get("step10_away_recent_games") or 0)} • home recent games {int(c.get("step10_home_recent_games") or 0)} • verified H2H meetings {int(c.get("step10_h2h_meetings") or 0)} • projected-total adjustment {_num(c.get("step10_projected_total_adjustment"),2)}.</span></div>'''


def _final_card_v10(game, final):
    html = _FROZEN_STEP9_FINAL_CARD(game, final)
    html = html.replace(
        "STEP 9 FINAL RULES • UPGRADE STEP 9 ENVIRONMENT-ADJUSTED UNCERTAINTY",
        "STEP 9 FINAL RULES • UPGRADE STEP 10 HISTORY-CONTEXT CERTIFIED • MODEL MATH UNCHANGED",
    )
    return html


def _clear_stale_scan_state():
    marker = "cfb_ou_upgrade_step10_scan_state_reset"
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
    st.caption("🟪 CFB O/U INTELLIGENCE V2 • Upgrade Step 10 • historical context ACTIVE")
    st.markdown(frozen_v9._CSS + _CSS10, unsafe_allow_html=True)
    _clear_stale_scan_state()
    host = frozen_v9.frozen_v8
    originals = (
        host._hero_v8,
        host.upgraded_slate,
        host._model_card_v8,
        host._components_panel_v8,
        host._final_card_v8,
    )
    host._hero_v8 = _hero_v10
    host.upgraded_slate = upgraded_slate
    host._model_card_v8 = _model_card_v10
    host._components_panel_v8 = _components_panel_v10
    host._final_card_v8 = _final_card_v10
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
        raise ValueError(f"Upgrade Step 10 Over/Under UI received unsupported market: {market}")
    return render_over_under_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_UPGRADE",
    "MARKET",
    "MODEL_VERSION",
    "_components_panel_v10",
    "_final_card_v10",
    "_hero_v10",
    "_history_panel",
    "_model_card_v10",
    "render_cfb_hub",
    "render_over_under_hub",
]
