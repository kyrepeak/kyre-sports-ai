"""CFB Over/Under Intelligence V2 — Upgrade Step 12 final certification UI.

Presentation-only wrapper over permanently frozen Upgrade Step 11.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import streamlit as st

import cfb_over_under_matchup_ui_v11 as frozen_v11
import cfb_over_under_slate_v11 as upgraded_slate

MODEL_VERSION = "CFB OVER/UNDER INTELLIGENCE V2 • UPGRADE STEP 12 FINAL CERTIFICATION"
FROZEN_UPGRADE = "cfb_over_under_matchup_ui_v11"
MARKET = "Over/Under"

_FROZEN_STEP11_HERO = frozen_v11._hero_v11
_FROZEN_STEP11_MODEL_CARD = frozen_v11._model_card_v11
_FROZEN_STEP11_COMPONENTS_PANEL = frozen_v11._components_panel_v11
_FROZEN_STEP11_FINAL_CARD = frozen_v11._final_card_v11

_CSS12 = r"""
<style>
.cfbou12-strip{margin:9px 0 2px;border:1px solid rgba(255,211,86,.26);border-radius:12px;background:linear-gradient(90deg,#211c0d,#15140f);padding:8px 10px;color:#e6d487;font-size:.40rem;font-weight:900;letter-spacing:.04em}
.cfbou12{margin-top:9px;border:1px solid rgba(255,211,86,.28);border-radius:15px;background:#14130f;overflow:hidden}
.cfbou12-head{display:flex;justify-content:space-between;gap:9px;align-items:center;padding:9px 11px;border-bottom:1px solid rgba(255,211,86,.10)}
.cfbou12-head b{color:#f1df93;font-size:.50rem;font-weight:950;letter-spacing:.06em}.cfbou12-badge{border-radius:999px;padding:4px 8px;font-size:.36rem;font-weight:950}
.cfbou12-pass{background:#0d2a1b;border:1px solid #286644;color:#a8f0c6}.cfbou12-gate{background:#2a230d;border:1px solid #6a5720;color:#e6cf79}.cfbou12-fail{background:#321313;border:1px solid #7a3030;color:#ffaaaa}
.cfbou12-body{padding:9px 11px;color:#8f8a79;font-size:.37rem;line-height:1.5}.cfbou12-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin-top:8px}
.cfbou12-m{border:1px solid rgba(255,211,86,.10);border-radius:8px;background:#0f0f0d;padding:6px}.cfbou12-m strong{display:block;color:#eadb9f;font-size:.50rem}.cfbou12-m span{display:block;color:#736f61;font-size:.29rem;text-transform:uppercase;margin-top:2px}
.cfbou12-note{margin-top:7px;color:#777263;font-size:.33rem}.cfbou12-failtext{margin-top:7px;color:#e39191;font-size:.34rem}
@media(max-width:760px){.cfbou12-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _cert_panel(output: Mapping[str, Any]) -> str:
    cert = output.get("upgrade_step12_certification") or {}
    if not cert:
        return '''<div class="cfbou12"><div class="cfbou12-head"><b>🏁 STEP 12 • FINAL SYSTEM CERTIFICATION</b><span class="cfbou12-badge cfbou12-gate">PENDING</span></div><div class="cfbou12-body">Certification metadata is not available for this result yet.</div></div>'''

    status = _clean(cert.get("status")) or "DATA_GATED"
    if status == "CERTIFIED":
        badge_class = "cfbou12-pass"
        badge = "CERTIFIED"
    elif status == "INTEGRITY_FAIL":
        badge_class = "cfbou12-fail"
        badge = "INTEGRITY FAIL"
    else:
        badge_class = "cfbou12-gate"
        badge = "DATA GATED"

    passed = int(cert.get("checks_passed") or 0)
    failed = int(cert.get("checks_failed") or 0)
    skipped = int(cert.get("checks_skipped") or 0)
    fingerprint = escape(_clean(cert.get("projection_fingerprint")) or "—")
    failures = cert.get("blocking_failures") or []
    fail_html = ""
    if failures:
        text = " • ".join(
            escape(_clean(row.get("name")))
            for row in failures[:3]
            if isinstance(row, Mapping)
        )
        fail_html = f'<div class="cfbou12-failtext">Blocking failure(s): {text}</div>'

    note = (
        "Projection and selection math are frozen; Step 12 only verifies integrity."
        if status != "DATA_GATED"
        else "The pipeline is behaving safely, but one or more model inputs are gated."
    )
    return f'''
<div class="cfbou12">
 <div class="cfbou12-head"><b>🏁 STEP 12 • FINAL SYSTEM CERTIFICATION</b><span class="cfbou12-badge {badge_class}">{badge}</span></div>
 <div class="cfbou12-body">12/12 upgrade stack checked • no new model weight added.
  <div class="cfbou12-grid">
   <div class="cfbou12-m"><strong>{passed}</strong><span>Checks passed</span></div>
   <div class="cfbou12-m"><strong>{failed}</strong><span>Checks failed</span></div>
   <div class="cfbou12-m"><strong>{skipped}</strong><span>Checks skipped</span></div>
   <div class="cfbou12-m"><strong>{fingerprint}</strong><span>Projection fingerprint</span></div>
  </div>
  <div class="cfbou12-note">{escape(note)} • sportsbook/market/EV/Monte Carlo firewall remains active.</div>
  {fail_html}
 </div>
</div>'''


def _hero_v12(game, away, home):
    return _FROZEN_STEP11_HERO(game, away, home) + (
        '<div class="cfbou12-strip">🏁 UPGRADE STEP 12 • FINAL CERTIFICATION LAYER ACTIVE • 0% NEW PROJECTION WEIGHT</div>'
    )


def _model_card_v12(game, away, home, output):
    return _FROZEN_STEP11_MODEL_CARD(game, away, home, output) + _cert_panel(output)


def _components_panel_v12(output):
    frozen = _FROZEN_STEP11_COMPONENTS_PANEL(output)
    cert = output.get("upgrade_step12_certification") or {}
    if not cert:
        return frozen
    return frozen + f'''<div class="cfbou12-note">Step 12 audit • status {escape(_clean(cert.get("status")))} • integrity passed {str(bool(cert.get("integrity_passed"))).lower()} • projection math changed false • selection math changed false.</div>'''


def _final_card_v12(game, final):
    html = _FROZEN_STEP11_FINAL_CARD(game, final)
    html = html.replace(
        "STEP 9 FINAL RULES • UPGRADE STEP 11 CURRENT-FORM NORMALIZED PROJECTION",
        "FINAL RULES • UPGRADE STEP 12 CERTIFICATION LAYER • 12/12 STACK",
    )
    return html


def _clear_stale_scan_state():
    marker = "cfb_ou_upgrade_step12_scan_state_reset"
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
    st.caption("🏁 CFB O/U INTELLIGENCE V2 • Upgrade Step 12 • FINAL CERTIFICATION ACTIVE")
    st.markdown(
        frozen_v11.frozen_v10.frozen_v9._CSS
        + frozen_v11.frozen_v10._CSS10
        + frozen_v11._CSS11
        + _CSS12,
        unsafe_allow_html=True,
    )
    _clear_stale_scan_state()
    host = frozen_v11.frozen_v10.frozen_v9.frozen_v8
    originals = (
        host._hero_v8,
        host.upgraded_slate,
        host._model_card_v8,
        host._components_panel_v8,
        host._final_card_v8,
    )
    host._hero_v8 = _hero_v12
    host.upgraded_slate = upgraded_slate
    host._model_card_v8 = _model_card_v12
    host._components_panel_v8 = _components_panel_v12
    host._final_card_v8 = _final_card_v12
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
        raise ValueError(f"Upgrade Step 12 Over/Under UI received unsupported market: {market}")
    return render_over_under_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_UPGRADE",
    "MARKET",
    "MODEL_VERSION",
    "_cert_panel",
    "_components_panel_v12",
    "_final_card_v12",
    "_hero_v12",
    "_model_card_v12",
    "render_cfb_hub",
    "render_over_under_hub",
]
