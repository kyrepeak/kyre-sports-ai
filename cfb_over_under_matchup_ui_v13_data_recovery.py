"""CFB O/U post-12 multi-source data recovery UI hotfix.

The frozen 12/12 stack remains intact. This wrapper replaces blank gated audit
panels with recovered/partial verified data while using the recovered slate for
actual frozen Step-9/10/11 orchestration.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import streamlit as st

import cfb_over_under_data_recovery_v1 as recovery
import cfb_over_under_form_strength_engine_v1 as form_engine
import cfb_over_under_matchup_ui_v12 as frozen_v12
import cfb_over_under_slate_v12_data_recovery as recovered_slate

MODEL_VERSION = "CFB O/U UI V13 • POST-12 MULTI-SOURCE DATA RECOVERY HOTFIX"
FROZEN_STEP12_UI = "cfb_over_under_matchup_ui_v12"
MARKET = "Over/Under"

v11 = frozen_v12.frozen_v11
v10 = v11.frozen_v10
v9 = v10.frozen_v9
v8 = v9.frozen_v8

_CSS13 = r"""
<style>
.cfbou13{margin:10px 0 2px;border:1px solid rgba(72,216,199,.34);border-radius:16px;background:linear-gradient(145deg,#071a1a,#0a1518);overflow:hidden}
.cfbou13-head{display:flex;justify-content:space-between;gap:8px;align-items:center;padding:9px 11px;border-bottom:1px solid rgba(72,216,199,.13)}
.cfbou13-head b{color:#9cf1e6;font-size:.50rem;font-weight:950;letter-spacing:.06em}.cfbou13-head span{border:1px solid #276b64;border-radius:999px;padding:4px 7px;background:#0b2925;color:#b8f5ed;font-size:.36rem;font-weight:950}
.cfbou13-body{padding:9px 11px;color:#839591;font-size:.38rem;line-height:1.52}.cfbou13-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin-top:8px}
.cfbou13-m{border:1px solid rgba(72,216,199,.11);border-radius:8px;background:#091311;padding:7px}.cfbou13-m strong{display:block;color:#c1f3ec;font-size:.54rem}.cfbou13-m small{display:block;color:#6d817d;font-size:.28rem;text-transform:uppercase;margin-top:2px}
.cfbou13-note{margin-top:8px;border:1px solid rgba(72,216,199,.10);border-radius:9px;background:#0a1211;padding:7px;color:#71847f;font-size:.34rem;line-height:1.45}
.cfbou13-warn{margin-top:8px;border:1px solid #6b5721;border-radius:9px;background:#2a230e;padding:7px;color:#dec879;font-size:.34rem;line-height:1.45}
@media(max-width:760px){.cfbou13-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
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
        return f"{100*float(value):.1f}%"
    except Exception:
        return "—"


def _environment_panel(game: Mapping[str, Any], away: Mapping[str, Any], home: Mapping[str, Any]) -> str:
    e = recovery.build_environment_engine(game, away, home)
    if e.get("model_ready"):
        w = e.get("weather") or {}
        v = e.get("venue") or {}
        return f'''
<div class="cfbou13">
 <div class="cfbou13-head"><b>🟦 STEP 9 • ENVIRONMENT + IDENTITY RECOVERY</b><span>{"RECOVERED" if e.get("recovery_used") else "PRIMARY VERIFIED"}</span></div>
 <div class="cfbou13-body">Source: {escape(_clean(e.get("recovery_source")) or "ESPN exact event")}.
  <div class="cfbou13-grid">
   <div class="cfbou13-m"><strong>{escape(_clean(e.get("event_id")) or "—")}</strong><small>ESPN event</small></div>
   <div class="cfbou13-m"><strong>{escape(_clean(v.get("name")) or "—")}</strong><small>Venue</small></div>
   <div class="cfbou13-m"><strong>{_num(w.get("temperature_f"),0)}°F</strong><small>Temperature</small></div>
   <div class="cfbou13-m"><strong>{_num(w.get("precipitation_pct"),0)}%</strong><small>Precip chance</small></div>
  </div>
  <div class="cfbou13-note">Away ESPN ID {escape(_clean(e.get("away_espn_team_id")))} • Home ESPN ID {escape(_clean(e.get("home_espn_team_id")))} • weather sigma adjustment {_num(e.get("sigma_adjustment"),2)}. Injury model weight remains 0%.</div>
 </div>
</div>'''

    pieces = []
    if e.get("away_espn_team_id"):
        pieces.append(f"Away ESPN ID {escape(_clean(e.get('away_espn_team_id')))}")
    if e.get("home_espn_team_id"):
        pieces.append(f"Home ESPN ID {escape(_clean(e.get('home_espn_team_id')))}")
    if e.get("event_id"):
        pieces.append(f"Event {escape(_clean(e.get('event_id')))}")
    detail = " • ".join(pieces) or "No provider identity recovered yet"
    return f'''
<div class="cfbou13">
 <div class="cfbou13-head"><b>🟦 STEP 9 • ENVIRONMENT + IDENTITY RECOVERY</b><span>PARTIAL VERIFIED</span></div>
 <div class="cfbou13-body">{detail}<div class="cfbou13-warn">{escape(_clean(e.get("reason")) or "Game-time environment still incomplete")}. Verified partial fields remain visible; missing fields receive 0% model influence.</div></div>
</div>'''


def _all_time_h2h(external: Mapping[str, Any]) -> str:
    if not external.get("ready"):
        return '<div class="cfbou13-note">All-time external series fallback unavailable.</div>'
    latest = external.get("latest") or {}
    return f'''
<div class="cfbou13">
 <div class="cfbou13-head"><b>🤝 ALL-TIME SERIES • EXTERNAL VERIFIED FALLBACK</b><span>{escape(_clean(external.get("source")) or "External")}</span></div>
 <div class="cfbou13-body">
  <div class="cfbou13-grid">
   <div class="cfbou13-m"><strong>{int(external.get("meetings") or 0)}</strong><small>Meetings</small></div>
   <div class="cfbou13-m"><strong>{int(external.get("away_wins") or 0)}–{int(external.get("home_wins") or 0)}</strong><small>Away–home wins</small></div>
   <div class="cfbou13-m"><strong>{_num(external.get("avg_combined_total"),1)}</strong><small>Avg combined</small></div>
   <div class="cfbou13-m"><strong>{_num(latest.get("combined_total"),0)}</strong><small>Latest total</small></div>
  </div>
  <div class="cfbou13-note">Latest verified meeting: {escape(_clean(latest.get("date")) or "—")} • score {_num(latest.get("away_points"),0)}–{_num(latest.get("home_points"),0)}. This all-time series is context-only: projection weight 0%, selection weight 0%.</div>
 </div>
</div>'''


def _history_panel(game: Mapping[str, Any], away: Mapping[str, Any], home: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    e = recovery.build_history_engine(game, away, home)
    away_recent = e.get("away_recent") or {}
    home_recent = e.get("home_recent") or {}
    external = e.get("all_time_head_to_head") or {}

    recent_html = ""
    if away_recent.get("games") or home_recent.get("games"):
        recent_html = f'''
<div class="cfbou13">
 <div class="cfbou13-head"><b>🟪 STEP 10 • RECENT TEAM HISTORY</b><span>MULTI-SOURCE CONTEXT</span></div>
 <div class="cfbou13-body">
  <div class="cfbou13-grid">
   <div class="cfbou13-m"><strong>{int(away_recent.get("games") or 0)}</strong><small>Away recent games</small></div>
   <div class="cfbou13-m"><strong>{_num(away_recent.get("avg_combined_total"),1)}</strong><small>Away avg total</small></div>
   <div class="cfbou13-m"><strong>{int(home_recent.get("games") or 0)}</strong><small>Home recent games</small></div>
   <div class="cfbou13-m"><strong>{_num(home_recent.get("avg_combined_total"),1)}</strong><small>Home avg total</small></div>
  </div>
  <div class="cfbou13-note">Completed pre-kickoff games only. Older-roster history remains descriptive and does not directly move the pick.</div>
 </div>
</div>'''
    else:
        recent_html = f'''<div class="cfbou13"><div class="cfbou13-head"><b>🟪 STEP 10 • RECENT TEAM HISTORY</b><span>LIMITED</span></div><div class="cfbou13-body"><div class="cfbou13-warn">{escape(_clean(e.get("reason")) or "Recent ESPN history is incomplete")}.</div></div></div>'''

    return recent_html + _all_time_h2h(external), e


def _form_panel(game: Mapping[str, Any], away: Mapping[str, Any], home: Mapping[str, Any], history: Mapping[str, Any]) -> str:
    e = form_engine.build_form_strength_engine(
        game,
        away,
        home,
        step10_history=history,
    )
    af = e.get("away_form") or {}
    hf = e.get("home_form") or {}
    badge = "FORM READY" if e.get("model_ready") else "FORM LIMITED"
    body = f'''
<div class="cfbou13">
 <div class="cfbou13-head"><b>🟩 STEP 11 • CURRENT FORM + SCHEDULE STRENGTH</b><span>{badge}</span></div>
 <div class="cfbou13-body">
  <div class="cfbou13-grid">
   <div class="cfbou13-m"><strong>{int(af.get("games") or 0)}</strong><small>Away games</small></div>
   <div class="cfbou13-m"><strong>{_pct(af.get("opponent_record_coverage"))}</strong><small>Away opp coverage</small></div>
   <div class="cfbou13-m"><strong>{int(hf.get("games") or 0)}</strong><small>Home games</small></div>
   <div class="cfbou13-m"><strong>{_pct(hf.get("opponent_record_coverage"))}</strong><small>Home opp coverage</small></div>
  </div>'''
    if e.get("model_ready"):
        body += '<div class="cfbou13-note">Current-season sample and opponent-record coverage pass the Step-11 gates. Frozen bounded adjustment rules may apply.</div>'
    else:
        body += f'<div class="cfbou13-warn">{escape(_clean(e.get("reason")) or "Current-season sample is below the safe weighting gate")}. The verified data stays visible, but it cannot force an adjustment yet.</div>'
    return body + "</div></div>"


def _hero_v13(game, away, home):
    base = v9._FROZEN_STEP8_HERO(game, away, home)
    history_html, history = _history_panel(game, away, home)
    return (
        base
        + _environment_panel(game, away, home)
        + history_html
        + _form_panel(game, away, home, history)
        + '<div class="cfbou12-strip">🏁 STEP 12 FINAL CERTIFICATION REMAINS ACTIVE • POST-12 DATA RECOVERY HOTFIX</div>'
    )


def _model_card_v13(game, away, home, output):
    return frozen_v12._model_card_v12(game, away, home, output)


def _components_panel_v13(output):
    base = frozen_v12._components_panel_v12(output)
    summary = output.get("recovery_summary") or {}
    return base + f'''<div class="cfbou13-note">Post-12 recovery audit • environment recovered {str(bool(summary.get("environment_recovered"))).lower()} • source {escape(_clean(summary.get("environment_source")) or "primary")} • external H2H ready {str(bool(summary.get("external_h2h_ready"))).lower()} • H2H source {escape(_clean(summary.get("external_h2h_source")) or "none")}.</div>'''


def _final_card_v13(game, final):
    return frozen_v12._final_card_v12(game, final)


def _clear_stale_scan_state():
    marker = "cfb_ou_post12_data_recovery_scan_reset"
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
    st.caption("🔄 CFB O/U • POST-12 MULTI-SOURCE DATA RECOVERY HOTFIX ACTIVE")
    st.markdown(
        v9._CSS + v10._CSS10 + v11._CSS11 + frozen_v12._CSS12 + _CSS13,
        unsafe_allow_html=True,
    )
    _clear_stale_scan_state()
    host = v8
    originals = (
        host._hero_v8,
        host.upgraded_slate,
        host._model_card_v8,
        host._components_panel_v8,
        host._final_card_v8,
    )
    host._hero_v8 = _hero_v13
    host.upgraded_slate = recovered_slate
    host._model_card_v8 = _model_card_v13
    host._components_panel_v8 = _components_panel_v13
    host._final_card_v8 = _final_card_v13
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
        raise ValueError(f"Post-12 recovery UI received unsupported market: {market}")
    return render_over_under_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_STEP12_UI",
    "MARKET",
    "MODEL_VERSION",
    "_environment_panel",
    "_form_panel",
    "_hero_v13",
    "_history_panel",
    "render_cfb_hub",
    "render_over_under_hub",
]
