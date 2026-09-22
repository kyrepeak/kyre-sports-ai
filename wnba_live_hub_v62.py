"""WNBA Live Games V6.2 — walk-forward Step-6 calibration lab.

Production V6.1 renders unchanged. When no verified live game exists, an opt-in
calibration lab evaluates the production Step-6 structure across multiple recent
completed games with a chronological train/validation split. No candidate is
automatically promoted into production.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import streamlit as st

import wnba_live_hub_v2 as v2
import wnba_live_hub_v61 as v61
import wnba_live_step6_calibration_v1 as cal

ET = ZoneInfo("America/New_York")
MODEL_VERSION = "WNBA LIVE GAMES V6.2 • STEP-6 WALK-FORWARD CALIBRATION"


def _pct(value, digits=1):
    try:
        return f"{float(value) * 100:.{digits}f}%"
    except Exception:
        return "—"


def _num(value, digits=2, signed=False):
    try:
        x = float(value)
        return f"{x:+.{digits}f}" if signed else f"{x:.{digits}f}"
    except Exception:
        return "—"


def _metric(label: str, value: str, sub: str = "") -> str:
    extra = f"<small>{escape(str(sub))}</small>" if sub else ""
    return f'<div class="kwl62-m"><span>{escape(label)}</span><b>{escape(str(value))}</b>{extra}</div>'


def _metric_block(title: str, baseline: dict, candidate: dict) -> str:
    fields = [
        ("WINNER ACCURACY", "winner_accuracy", "pct"),
        ("ACTUAL-WINNER PROB.", "avg_actual_winner_probability", "pct"),
        ("BRIER", "brier", "num"),
        ("TEAM MAE", "team_mae", "pts"),
        ("TOTAL MAE", "total_mae", "pts"),
        ("MARGIN MAE", "margin_mae", "pts"),
        ("TOTAL BIAS", "total_bias", "signed"),
        ("MARGIN BIAS", "margin_bias", "signed"),
        ("COMPOSITE", "composite", "num"),
    ]
    rows = []
    for label, key, fmt in fields:
        b = baseline.get(key)
        c = candidate.get(key)
        if fmt == "pct":
            bv, cv = _pct(b), _pct(c)
        elif fmt == "pts":
            bv, cv = _num(b, 2) + " pts", _num(c, 2) + " pts"
        elif fmt == "signed":
            bv, cv = _num(b, 2, True) + " pts", _num(c, 2, True) + " pts"
        else:
            bv, cv = _num(b, 4), _num(c, 4)
        rows.append(
            f'<div class="kwl62-row"><span>{escape(label)}</span><b>{escape(bv)}</b><strong>{escape(cv)}</strong></div>'
        )
    return f'''<div class="kwl62-block"><div class="kwl62-blockhead"><b>{escape(title)}</b><span>V1 BASELINE → CALIBRATED CANDIDATE</span></div><div class="kwl62-table"><div class="kwl62-row head"><span>METRIC</span><b>BASELINE</b><strong>CANDIDATE</strong></div>{''.join(rows)}</div></div>'''


def _params_html(fitted: dict) -> str:
    cards = []
    labels = {"HALFTIME": "HALFTIME / SECOND-HALF START", "Q4_START": "START OF Q4"}
    for cid in cal.CHECKPOINTS:
        p = ((fitted.get("checkpoints") or {}).get(cid) or {})
        cards.append(f'''<div class="kwl62-param"><div class="kwl62-paramhead"><b>{escape(labels.get(cid,cid))}</b><span>{int(p.get('sample') or 0)} TRAIN STATE(S)</span></div><div class="kwl62-grid">
{_metric('REMAINING TOTAL SCALE', _num(p.get('remaining_total_scale'),3) + '×', 'identity 1.000')}
{_metric('REMAINING DIFF SCALE', _num(p.get('remaining_diff_scale'),3) + '×', 'identity 1.000')}
{_metric('LEAD PERSISTENCE', _num(p.get('lead_persistence'),3,True), 'identity +0.000')}
{_metric('SD SCALE', _num(p.get('sd_scale'),3) + '×', 'identity 1.000')}
</div></div>''')
    return "".join(cards)


def _contract_html(contract: dict, title: str) -> str:
    safe = bool(contract.get("safe_candidate"))
    reasons = contract.get("reasons") or []
    reason_html = "".join(f"<li>{escape(str(x))}</li>" for x in reasons)
    if not reason_html:
        reason_html = "<li>All current promotion gates passed.</li>"
    return f'''<div class="kwl62-contract {'pass' if safe else 'fail'}"><div><small>{escape(title)}</small><b>{escape(str(contract.get('status') or 'CHECK'))}</b></div><span>{'PASS' if safe else 'HOLD'}</span><ul>{reason_html}</ul></div>'''


def _dataset_html(dataset: dict) -> str:
    discovery = dataset.get("discovery") or {}
    return f'''<div class="kwl62-grid">
{_metric('RECENT GAMES DISCOVERED', str(int(dataset.get('games_discovered') or 0)))}
{_metric('GAMES WITH CLEAN REPLAYS', str(int(dataset.get('games_ready') or 0)))}
{_metric('TRAIN GAMES', str(int(dataset.get('train_games') or 0)), 'older games only')}
{_metric('VALIDATION GAMES', str(int(dataset.get('validation_games') or 0)), 'newest games • never fit')}
{_metric('TRAIN STATES', str(int(dataset.get('train_states') or 0)), 'halftime + start Q4')}
{_metric('VALIDATION STATES', str(int(dataset.get('validation_states') or 0)), 'held out from parameter fit')}
{_metric('SCOREBOARD DAYS OK', str(int(discovery.get('scoreboard_ok') or 0)))}
{_metric('SUMMARY ERRORS', str(int(discovery.get('summary_errors') or 0)))}
</div>'''


def _checkpoint_html(validation: dict) -> str:
    pieces = []
    bmap = validation.get("baseline_by_checkpoint") or {}
    cmap = validation.get("candidate_by_checkpoint") or {}
    for cid in cal.CHECKPOINTS:
        label = "HALFTIME" if cid == "HALFTIME" else "START Q4"
        pieces.append(_metric_block(f"OUT-OF-SAMPLE • {label}", bmap.get(cid) or {}, cmap.get(cid) or {}))
    return "".join(pieces)


def _confirmation_html(result: dict) -> str:
    contract = result.get("contract") or {}
    total_sims = int(result.get("total_simulations") or 0)
    states = int(result.get("validation_states") or 0)
    failures = result.get("convergence_failures") or []
    intro = f'''<div class="kwl62-confirmhead"><b>🎲 EXACT 5M HOLDOUT CONFIRMATION</b><span>{states} validation states • {total_sims:,} total draws</span></div>'''
    convergence = (
        '<div class="kwl62-ok">All baseline and calibrated 5M runs passed the existing convergence contract.</div>'
        if not failures
        else '<div class="kwl62-bad">Convergence check: ' + escape(" • ".join(failures)) + '</div>'
    )
    groups = {
        "baseline_by_checkpoint": result.get("baseline_by_checkpoint") or {},
        "candidate_by_checkpoint": result.get("candidate_by_checkpoint") or {},
    }
    cp_html = []
    for cid in cal.CHECKPOINTS:
        label = "HALFTIME" if cid == "HALFTIME" else "START Q4"
        cp_html.append(
            _metric_block(
                f"5M HOLDOUT • {label}",
                groups["baseline_by_checkpoint"].get(cid) or {},
                groups["candidate_by_checkpoint"].get(cid) or {},
            )
        )
    return (
        intro
        + _metric_block("5M HOLDOUT • ALL VALIDATION STATES", result.get("baseline") or {}, result.get("candidate") or {})
        + "".join(cp_html)
        + convergence
        + _contract_html(contract, "5M PROMOTION CONTRACT")
        + f'<div class="kwl62-note">Paired deterministic seeds: YES • reported simulator runtime {_num(result.get("runtime_seconds"),2)} s • candidate is still NOT promoted automatically.</div>'
    )


def _css():
    st.markdown(r'''<style>
.kwl62-hero{border:1px dashed #806f2d;border-radius:22px;padding:20px;margin:30px 0 14px;background:linear-gradient(145deg,#171507,#081622)}.kwl62-eye{font-size:.7rem;font-weight:950;letter-spacing:.08em;color:#ead879}.kwl62-hero h3{font-size:1.5rem;color:#f7fbff;margin:8px 0}.kwl62-hero p{color:#9fb0bb;line-height:1.58;margin:0}.kwl62-hero b{color:#fff}.kwl62-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}.kwl62-m{border:1px solid #2b4a5f;border-radius:14px;padding:10px;background:#07111d;min-height:76px;display:flex;flex-direction:column;justify-content:center}.kwl62-m span{font-size:.57rem;color:#839aaa;font-weight:900}.kwl62-m b{font-size:1rem;color:#f5f8fb;margin-top:5px}.kwl62-m small{font-size:.56rem;color:#899fac;margin-top:3px}.kwl62-block,.kwl62-param{border:1px solid #344f62;border-radius:18px;padding:13px;margin:12px 0;background:#081522}.kwl62-blockhead,.kwl62-paramhead,.kwl62-confirmhead{display:flex;justify-content:space-between;gap:10px;align-items:center;border-bottom:1px solid #213b4e;padding-bottom:9px}.kwl62-blockhead b,.kwl62-paramhead b,.kwl62-confirmhead b{color:#e9f4fa;font-size:.72rem}.kwl62-blockhead span,.kwl62-paramhead span,.kwl62-confirmhead span{color:#8299aa;font-size:.56rem;font-weight:850}.kwl62-table{margin-top:6px}.kwl62-row{display:grid;grid-template-columns:1.25fr .8fr .8fr;gap:8px;padding:8px 2px;border-bottom:1px solid #1d3342;align-items:center}.kwl62-row:last-child{border-bottom:0}.kwl62-row span{color:#8399a8;font-size:.58rem;font-weight:900}.kwl62-row b{color:#c7d5de;font-size:.7rem}.kwl62-row strong{color:#f5f9fb;font-size:.7rem}.kwl62-row.head span,.kwl62-row.head b,.kwl62-row.head strong{color:#8fcff5;font-size:.54rem}.kwl62-paramhead{margin-bottom:10px}.kwl62-contract{border-radius:18px;padding:14px;margin:13px 0;border:1px solid}.kwl62-contract>div{display:flex;flex-direction:column}.kwl62-contract small{font-size:.58rem;font-weight:900}.kwl62-contract b{font-size:1.05rem}.kwl62-contract>span{float:right;border:1px solid;border-radius:999px;padding:6px 9px;font-size:.6rem;font-weight:950}.kwl62-contract ul{margin:10px 0 0 18px;padding:0;font-size:.65rem;line-height:1.45}.kwl62-contract.pass{border-color:#2d8257;background:#0d2d21;color:#93efbc}.kwl62-contract.fail{border-color:#8a722a;background:#2a240d;color:#ead879}.kwl62-confirmhead{margin:18px 0 8px}.kwl62-ok,.kwl62-bad,.kwl62-note{border-radius:13px;padding:10px;margin:9px 0;font-size:.64rem;line-height:1.45}.kwl62-ok{border:1px solid #2d8257;background:#0d2d21;color:#93efbc}.kwl62-bad{border:1px solid #884b4b;background:#321616;color:#ffb3b3}.kwl62-note{border:1px solid #35536a;background:#0a1823;color:#9fb4c2}
@media(max-width:640px){.kwl62-hero{padding:16px}.kwl62-grid{grid-template-columns:1fr 1fr}.kwl62-row{grid-template-columns:1.2fr .75fr .75fr}.kwl62-blockhead,.kwl62-paramhead,.kwl62-confirmhead{align-items:flex-start;flex-direction:column}}
</style>''', unsafe_allow_html=True)


def render_wnba_live_hub(section_header=None, status_info=None, team_logo=None, h=None):
    # Existing production + single-game replay render unchanged first.
    v61.render_wnba_live_hub(section_header, status_info, team_logo, h)

    now = datetime.now(ET)
    day_str = now.strftime("%Y-%m-%d")
    live_games, _, _ = v2._verified_live_games(day_str)
    if live_games:
        return

    _css()
    st.markdown(f'''<div class="kwl62-hero"><div class="kwl62-eye">🧪 {MODEL_VERSION}</div><h3>Step 6.2 • Multi-Game Walk-Forward Calibration</h3><p>Instead of tuning Step 6 to one miss, this lab fits a small, strongly-shrunk calibration candidate on <b>older completed replay games</b> and grades it on the <b>newest games it never used for fitting</b>. Halftime and start-Q4 are evaluated separately. No historical sportsbook price is requested, and nothing is automatically promoted into the live model.</p></div>''', unsafe_allow_html=True)

    audit_key = "wnba_step62_calibration_audit"
    confirm_key = "wnba_step62_calibration_confirmation"
    day_key = "wnba_step62_calibration_day"
    if st.session_state.get(day_key) != day_str:
        st.session_state.pop(audit_key, None)
        st.session_state.pop(confirm_key, None)
        st.session_state[day_key] = day_str

    c1, c2 = st.columns(2)
    with c1:
        run = st.button("🧪 Run walk-forward calibration audit", use_container_width=True, key="wnba_step62_run")
    with c2:
        reset = st.button("♻️ Clear calibration cache", use_container_width=True, key="wnba_step62_clear")
    if reset:
        cal.clear_cache()
        st.session_state.pop(audit_key, None)
        st.session_state.pop(confirm_key, None)
        st.rerun()

    if run:
        with st.spinner("Building older-train/newer-validation replay set and fitting conservative calibration…"):
            st.session_state[audit_key] = cal.calibration_audit(day_str)
        st.session_state.pop(confirm_key, None)
        st.rerun()

    audit = st.session_state.get(audit_key)
    if not audit:
        st.info("Run the calibration audit first. Production Step 6 remains unchanged while this lab is idle.")
        return

    dataset = audit.get("dataset") or {}
    st.markdown(_dataset_html(dataset), unsafe_allow_html=True)
    if not audit.get("ready"):
        st.error(
            "Calibration dataset is not clean enough to fit safely. "
            + str(audit.get("error") or "")
        )
        errors = dataset.get("errors") or []
        if errors:
            with st.expander("Calibration transport diagnostics"):
                for item in errors:
                    st.write("•", item)
        return

    fitted = audit.get("fitted") or {}
    st.markdown("### Fitted candidate parameters")
    st.markdown(_params_html(fitted), unsafe_allow_html=True)

    st.markdown("### Older-game fitting check")
    st.markdown(
        _metric_block("TRAINING STATES • DIAGNOSTIC ONLY", (audit.get("train") or {}).get("baseline") or {}, (audit.get("train") or {}).get("candidate") or {}),
        unsafe_allow_html=True,
    )

    validation = audit.get("validation") or {}
    st.markdown("### Newer-game out-of-sample validation")
    st.markdown(
        _metric_block("ALL HELD-OUT VALIDATION STATES", validation.get("baseline") or {}, validation.get("candidate") or {}),
        unsafe_allow_html=True,
    )
    st.markdown(_checkpoint_html(validation), unsafe_allow_html=True)
    st.markdown(_contract_html(audit.get("contract") or {}, "ANALYTIC HOLDOUT CONTRACT"), unsafe_allow_html=True)

    st.caption(
        "The analytic pass uses a Normal margin approximation only to screen the candidate cheaply. "
        "The production simulator itself has not been changed. Exact 5M confirmation below runs baseline and candidate with paired deterministic seeds."
    )

    if st.button("🎲 Run paired 5M holdout confirmation", use_container_width=True, key="wnba_step62_confirm"):
        with st.spinner("Running baseline + calibrated candidate across every held-out replay state at 5,000,000 draws each…"):
            st.session_state[confirm_key] = cal.run_5m_confirmation(audit)
        st.rerun()

    confirmation = st.session_state.get(confirm_key)
    if confirmation:
        if not confirmation.get("ready"):
            st.error(str(confirmation.get("error") or "5M confirmation unavailable"))
        else:
            st.markdown(_confirmation_html(confirmation), unsafe_allow_html=True)

    st.markdown('<div class="kwl62-note"><b>STEP 6.2 BOUNDARY.</b> This lab can recommend a calibration candidate, but it cannot silently change production. Promotion requires a clean out-of-sample contract plus exact 5M confirmation. Steps 1–6 remain untouched until that evidence exists.</div>', unsafe_allow_html=True)
