"""Readable presentation-only adapter for frozen CFB O/U Step 12 certification.

The certified Step-12 result already contains integrity checks, the projection
fingerprint, and the frozen-contract flags. This module only renders that
payload. It never certifies again, recomputes a projection, changes selection
math, or consumes sportsbook values.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

MODEL_VERSION = "CFB O/U READABLE STEP 12 V1 • FINAL CERTIFICATION"
FROZEN_CERTIFIER = "cfb_over_under_certification_v1"
PROJECTION_WEIGHT = 0.0
ANALYSIS_LINE_WEIGHT = 0.0
SELECTION_WEIGHT = 0.0
MAY_MODIFY_PROJECTION = False
CERTIFIED_UPGRADE_COUNT = 12


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _int(value: Any) -> str:
    try:
        return str(int(float(value)))
    except Exception:
        return "—"


def _bool_word(value: Any, *, default: bool = False) -> str:
    if value is None:
        value = default
    return "YES" if bool(value) else "NO"


def _status(cert: Mapping[str, Any]) -> tuple[str, str]:
    raw = _clean(cert.get("status")).upper()
    if raw == "CERTIFIED":
        return "CERTIFIED", "PASS"
    if raw == "INTEGRITY_FAIL":
        return "INTEGRITY FAIL", "FAIL"
    if raw == "DATA_GATED":
        return "DATA GATED", "GATED"
    return raw or "PENDING", "GATED"


def _failure_html(cert: Mapping[str, Any]) -> str:
    failures = cert.get("blocking_failures") or []
    names = [
        _clean(row.get("name"))
        for row in failures
        if isinstance(row, Mapping) and _clean(row.get("name"))
    ]
    if not names:
        return ""
    return (
        '<div class="cert12-fail"><b>FAIL CLOSED</b> • blocking check(s): '
        + escape(" • ".join(names[:5]))
        + "</div>"
    )


def _certificate_payload(result: Mapping[str, Any]) -> Mapping[str, Any]:
    direct = _mapping(result.get("certification"))
    if direct:
        return direct
    raw = _mapping(result.get("raw"))
    return _mapping(raw.get("upgrade_step12_certification"))


def render_step12(result: Mapping[str, Any]) -> str:
    """Render a frozen Step-12 certificate without re-running any checks."""
    if not isinstance(result, Mapping):
        result = {}
    cert = _certificate_payload(result)
    if not cert:
        return f"""
<div class="cert12-wrap">
<style>{_CSS}</style>
<div class="cert12-title"><b>🏁 STEP 12 • FINAL CERTIFICATION</b><span class="cert12-gated">PENDING</span></div>
<div class="cert12-gate"><b>CERTIFICATION PENDING</b> • No frozen certificate payload is attached; no certification claim is made and the prior result remains untouched.</div>
<div class="cert12-foot">Read-only certification layer • projection mutation: <b>OFF</b> • sportsbook projection weight: <b>0.0%</b> • official ESPN event IDs only • no fuzzy matching • no synthetic IDs.</div>
</div>
"""
    status, status_class = _status(cert)
    steps = cert.get("certified_upgrade_steps")
    try:
        step_count = len(steps) if isinstance(steps, (list, tuple)) else int(cert.get("completed_upgrade_count") or 0)
    except Exception:
        step_count = 0
    passed = _int(cert.get("checks_passed"))
    failed = _int(cert.get("checks_failed"))
    skipped = _int(cert.get("checks_skipped"))
    fingerprint = escape(_clean(cert.get("projection_fingerprint")) or "—")
    status_class_name = {
        "PASS": "cert12-pass",
        "FAIL": "cert12-fail",
        "GATED": "cert12-gated",
    }.get(status_class, "cert12-gated")
    ready_note = (
        "All blocking integrity checks passed; the frozen result is safe to display."
        if status_class == "PASS"
        else "The pipeline is safely data-gated; no projection is forced and prior certified output remains available."
        if status_class == "GATED"
        else "A blocking integrity check failed; this result is fail-closed and must not be treated as certified."
    )
    raw = _mapping(result.get("raw"))
    final = _mapping(result.get("final"))
    identity = _clean(
        (_mapping(result.get("game"))).get("identity_key")
        or (_mapping(result.get("game"))).get("game_id")
    )
    return f"""
<div class="cert12-wrap">
<style>{_CSS}</style>
<div class="cert12-title"><b>🏁 STEP 12 • FINAL CERTIFICATION</b><span class="{status_class_name}">{escape(status)}</span></div>
<div class="cert12-summary"><b>{step_count}/{CERTIFIED_UPGRADE_COUNT} upgrade stack checked</b> • {escape(ready_note)}</div>
<div class="cert12-grid">
 <div><strong>{escape(passed)}</strong><small>checks passed</small></div>
 <div><strong>{escape(failed)}</strong><small>checks failed</small></div>
 <div><strong>{escape(skipped)}</strong><small>checks skipped</small></div>
 <div><strong>{fingerprint}</strong><small>projection fingerprint</small></div>
</div>
<div class="cert12-audit">
 <b>🧾 FINAL INTEGRITY AUDIT</b>
 <span>Projection math changed: <strong>{_bool_word(cert.get("projection_math_changed"))}</strong> • selection math changed: <strong>{_bool_word(cert.get("selection_math_changed"))}</strong> • structural σ changed: <strong>{_bool_word(cert.get("structural_sigma_changed"))}</strong> • reliability changed: <strong>{_bool_word(cert.get("reliability_changed"))}</strong> • qualification thresholds changed: <strong>{_bool_word(cert.get("qualification_thresholds_changed"))}</strong>.</span>
 <span>Sportsbook input used: <strong>{_bool_word(cert.get("sportsbook_input_used"))}</strong> • market price/probability/EV/Monte Carlo inputs: <strong>OFF</strong> • sportsbook projection weight: <strong>0.0%</strong> • analysis-line/direct-selection weights: <strong>0.0%</strong>.</span>
 <span>Frozen certifier: <strong>{escape(FROZEN_CERTIFIER)}</strong> • game identity: <strong>{escape(identity or "not attached")}</strong> • raw ready: <strong>{_bool_word(raw.get("ready"))}</strong> • final ready: <strong>{_bool_word(final.get("ready"))}</strong>.</span>
</div>
{_failure_html(cert)}
<div class="cert12-foot">Official ESPN event IDs only • exact identity gates • no fuzzy matching • no synthetic IDs • frozen Schedule V5 and Steps 3–12 projection contracts preserved.</div>
</div>
"""


_CSS = r"""
.cert12-wrap{margin:10px 0;border:1px solid rgba(255,211,86,.30);border-radius:16px;background:#14130f;overflow:hidden;color:#fff9df}
.cert12-title{display:flex;justify-content:space-between;gap:8px;align-items:center;padding:10px 12px;border-bottom:1px solid rgba(255,211,86,.14)}
.cert12-title b{color:#f5e6a7;font-size:.58rem;letter-spacing:.07em}.cert12-title span{font-size:.44rem;font-weight:950;letter-spacing:.06em}
.cert12-pass{border:1px solid #2a774c;border-radius:999px;padding:4px 8px;color:#b8f5cb;background:#0b2918}.cert12-fail{border:1px solid #8c3636;border-radius:999px;padding:4px 8px;color:#ffb0b0;background:#331414}.cert12-gated{border:1px solid #80682b;border-radius:999px;padding:4px 8px;color:#f0d98b;background:#2c250e}
.cert12-summary,.cert12-foot{padding:9px 12px;color:#b8ad82;font-size:.72rem;line-height:1.5}.cert12-summary{border-bottom:1px solid rgba(255,211,86,.08)}
.cert12-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;padding:10px}.cert12-grid div{border:1px solid rgba(255,211,86,.13);border-radius:9px;background:#1d1b12;padding:8px}.cert12-grid strong{display:block;color:#f2df94;font-size:.78rem;word-break:break-word}.cert12-grid small{display:block;color:#978d6b;font-size:.58rem;margin-top:3px}
.cert12-audit{margin:0 10px 10px;border:1px solid rgba(255,211,86,.15);border-radius:11px;background:#1c1a11;padding:9px}.cert12-audit>b{display:block;color:#f1dd90;font-size:.70rem}.cert12-audit span{display:block;color:#b0a57c;font-size:.66rem;line-height:1.5;margin-top:4px}
.cert12-fail,.cert12-gate{margin:0 10px 10px;border-radius:9px;padding:9px;font-size:.68rem;line-height:1.5}.cert12-fail{border:1px solid #8c3636;background:#321414;color:#ffb0b0}.cert12-gate{border:1px solid #80682b;background:#2b240d;color:#eed891}
.cert12-foot{border-top:1px solid rgba(255,211,86,.10)}
@media(max-width:760px){.cert12-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
"""

__all__ = [
    "ANALYSIS_LINE_WEIGHT",
    "CERTIFIED_UPGRADE_COUNT",
    "FROZEN_CERTIFIER",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "PROJECTION_WEIGHT",
    "SELECTION_WEIGHT",
    "render_step12",
]
