"""WNBA Live Games V6.4 — PBP-rich Step-6 calibration lab.

Renders V6.3 unchanged, then appends an isolated walk-forward calibration lab
that uses the checkpoint-only PBP transport proven by Step 6.3. Production Step
6 remains V1 until an analytic holdout AND paired 5M holdout both pass.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import streamlit as st

import wnba_live_hub_v2 as v2
import wnba_live_hub_v63 as v63
import wnba_live_step6_calibration_v2 as cal

ET = ZoneInfo("America/New_York")
MODEL_VERSION = "WNBA LIVE GAMES V6.4 • PBP-RICH WALK-FORWARD CALIBRATION"


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
    return f'<div class="kwl64-m"><span>{escape(label)}</span><b>{escape(str(value))}</b>{extra}</div>'


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
            f'<div class="kwl64-row"><span>{escape(label)}</span><b>{escape(bv)}</b><strong>{escape(cv)}</strong></div>'
        )
    return f'''<div class="kwl64-block"><div class="kwl64-blockhead"><b>{escape(title)}</b><span>PBP-RICH V1 BASELINE → CALIBRATED CANDIDATE</span></div><div class="kwl64-table"><div class="kwl64-row head"><span>METRIC</span><b>BASELINE</b><strong>CANDIDATE</strong></div>{''.join(rows)}</div></div>'''


def _params_html(fitted: dict) -> str:
    pieces = []
    labels = {"HALFTIME": "HALFTIME / SECOND-HALF START", "Q4_START": "START OF Q4"}
    for cid in cal.CHECKPOINTS:
        p = ((fitted.get("checkpoints") or {}).get(cid) or {})
        hits = p.get("bound_hits") or []
        hit_text = ("BOUND HIT • " + ", ".join(hits)) if hits else "No hard parameter bound hit"
        pieces.append(f'''<div class="kwl64-block"><div class="kwl64-blockhead"><b>{escape(labels.get(cid,cid))}</b><span>{int(p.get('sample') or 0)} TRAIN STATE(S)</span></div><div class="kwl64-grid">
{_metric('REMAINING TOTAL SCALE', _num(p.get('remaining_total_scale'),3)+'×', 'identity 1.000')}
{_metric('REMAINING DIFF SCALE', _num(p.get('remaining_diff_scale'),3)+'×', 'identity 1.000')}
{_metric('LEAD PERSISTENCE', _num(p.get('lead_persistence'),3,True), 'identity +0.000')}
{_metric('HOME BIAS / 10 MIN', _num(p.get('home_bias_per10'),3,True)+' pts', 'identity +0.000')}
{_metric('SD SCALE', _num(p.get('sd_scale'),3)+'×', 'identity 1.000')}
{_metric('FIT STATUS', str(p.get('fit_status') or '—'), hit_text)}
</div></div>''')
    return "".join(pieces)


def _contract_html(contract: dict, title: str) -> str:
    safe = bool(contract.get("safe_candidate"))
    reasons = list(contract.get("reasons") or [])
    warnings = list(contract.get("warnings") or [])
    lis = "".join(f"<li>{escape(str(x))}</li>" for x in reasons)
    if not lis:
        lis = "<li>All hard gates passed.</li>"
    warn_html = "".join(f"<li>WARNING • {escape(str(x))}</li>" for x in warnings)
    return f'''<div class="kwl64-contract {'pass' if safe else 'fail'}"><div><small>{escape(title)}</small><b>{escape(str(contract.get('status') or 'CHECK'))}</b></div><span>{'PASS' if safe else 'HOLD'}</span><ul>{lis}{warn_html}</ul></div>'''


def _dataset_html(d: dict) -> str:
    discovery = d.get("discovery") or {}
    return f'''<div class="kwl64-grid">
{_metric('RECENT GAMES DISCOVERED', str(int(d.get('games_discovered') or 0)))}
{_metric('GAMES SELECTED', str(int(d.get('games_selected') or 0)))}
{_metric('CLEAN PBP-RICH GAMES', str(int(d.get('games_ready') or 0)))}
{_metric('TRAIN GAMES', str(int(d.get('train_games') or 0)), 'older games only')}
{_metric('VALIDATION GAMES', str(int(d.get('validation_games') or 0)), 'newest games • never fit')}
{_metric('TRAIN STATES', str(int(d.get('train_states') or 0)), 'halftime + start Q4')}
{_metric('VALIDATION STATES', str(int(d.get('validation_states') or 0)), 'held out from parameter fit')}
{_metric('FINAL BOXSCORE IN PROJECTION', 'NO')}
{_metric('SPORTSBOOK USED', 'NO')}
{_metric('DISCOVERY SUMMARY ERRORS', str(int(discovery.get('summary_errors') or 0)))}
</div>'''


def _checkpoint_blocks(validation: dict, prefix: str = "OUT-OF-SAMPLE") -> str:
    bmap = validation.get("baseline_by_checkpoint") or {}
    cmap = validation.get("candidate_by_checkpoint") or {}
    out = []
    for cid in cal.CHECKPOINTS:
        label = "HALFTIME" if cid == "HALFTIME" else "START Q4"
        out.append(_metric_block(f"{prefix} • {label}", bmap.get(cid) or {}, cmap.get(cid) or {}))
    return "".join(out)


def _confirmation_html(result: dict) -> str:
    contract = result.get("contract") or {}
    total_sims = int(result.get("total_simulations") or 0)
    states = int(result.get("validation_states") or 0)
    failures = result.get("convergence_failures") or []
    convergence = (
        '<div class="kwl64-ok">All paired baseline/candidate 5M runs passed the existing convergence contract.</div>'
        if not failures else
        '<div class="kwl64-bad">Convergence failures: ' + escape(" • ".join(failures)) + '</div>'
    )
    validation = {
        "baseline_by_checkpoint": result.get("baseline_by_checkpoint") or {},
        "candidate_by_checkpoint": result.get("candidate_by_checkpoint") or {},
    }
    return (
        f'<div class="kwl64-confirm"><b>🎲 PAIRED 5M PBP-RICH HOLDOUT</b><span>{states} states • {total_sims:,} total draws</span></div>'
        + _metric_block("5M HOLDOUT • ALL VALIDATION STATES", result.get("baseline") or {}, result.get("candidate") or {})
        + _checkpoint_blocks(validation, "5M HOLDOUT")
        + convergence
        + _contract_html(contract, "5M PROMOTION CONTRACT")
        + f'<div class="kwl64-note">Paired deterministic seeds: YES • simulator runtime {_num(result.get("runtime_seconds"),2)} s • production model remains unchanged until an explicit V2 promotion build.</div>'
    )


def _css():
    st.markdown(r'''<style>
.kwl64-hero{border:1px dashed #487f8d;border-radius:22px;padding:20px;margin:32px 0 14px;background:linear-gradient(145deg,#07191c,#071522)}.kwl64-eye{font-size:.7rem;font-weight:950;letter-spacing:.08em;color:#8edee8}.kwl64-hero h3{font-size:1.5rem;color:#f7fbff;margin:8px 0}.kwl64-hero p{color:#9fb0bb;line-height:1.58;margin:0}.kwl64-hero b{color:#fff}.kwl64-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}.kwl64-m{border:1px solid #2b4a5f;border-radius:14px;padding:10px;background:#07111d;min-height:76px;display:flex;flex-direction:column;justify-content:center}.kwl64-m span{font-size:.57rem;color:#839aaa;font-weight:900}.kwl64-m b{font-size:1rem;color:#f5f8fb;margin-top:5px}.kwl64-m small{font-size:.56rem;color:#899fac;margin-top:3px}.kwl64-block{border:1px solid #344f62;border-radius:18px;padding:13px;margin:12px 0;background:#081522}.kwl64-blockhead,.kwl64-confirm{display:flex;justify-content:space-between;gap:10px;align-items:center;border-bottom:1px solid #213b4e;padding-bottom:9px}.kwl64-blockhead b,.kwl64-confirm b{color:#e9f4fa;font-size:.72rem}.kwl64-blockhead span,.kwl64-confirm span{color:#8299aa;font-size:.56rem;font-weight:850}.kwl64-table{margin-top:6px}.kwl64-row{display:grid;grid-template-columns:1.25fr .8fr .8fr;gap:8px;padding:8px 2px;border-bottom:1px solid #1d3342;align-items:center}.kwl64-row:last-child{border-bottom:0}.kwl64-row span{color:#8399a8;font-size:.58rem;font-weight:900}.kwl64-row b{color:#c7d5de;font-size:.7rem}.kwl64-row strong{color:#f5f9fb;font-size:.7rem}.kwl64-row.head span,.kwl64-row.head b,.kwl64-row.head strong{color:#8fcff5;font-size:.54rem}.kwl64-contract{border-radius:18px;padding:14px;margin:13px 0;border:1px solid}.kwl64-contract>div{display:flex;flex-direction:column}.kwl64-contract small{font-size:.58rem;font-weight:900}.kwl64-contract b{font-size:1.02rem}.kwl64-contract>span{float:right;border:1px solid;border-radius:999px;padding:6px 9px;font-size:.6rem;font-weight:950}.kwl64-contract ul{margin:10px 0 0 18px;padding:0;font-size:.65rem;line-height:1.45}.kwl64-contract.pass{border-color:#2d8257;background:#0d2d21;color:#93efbc}.kwl64-contract.fail{border-color:#8a722a;background:#2a240d;color:#ead879}.kwl64-ok,.kwl64-bad,.kwl64-note{border-radius:13px;padding:10px;margin:9px 0;font-size:.64rem;line-height:1.45}.kwl64-ok{border:1px solid #2d8257;background:#0d2d21;color:#93efbc}.kwl64-bad{border:1px solid #884b4b;background:#321616;color:#ffb3b3}.kwl64-note{border:1px solid #35536a;background:#0a1823;color:#9fb4c2}.kwl64-confirm{margin:18px 0 8px}
@media(max-width:640px){.kwl64-hero{padding:16px}.kwl64-grid{grid-template-columns:1fr 1fr}.kwl64-row{grid-template-columns:1.2fr .75fr .75fr}.kwl64-blockhead,.kwl64-confirm{align-items:flex-start;flex-direction:column}}
</style>''', unsafe_allow_html=True)


def render_wnba_live_hub(section_header=None, status_info=None, team_logo=None, h=None):
    v63.render_wnba_live_hub(section_header, status_info, team_logo, h)

    now = datetime.now(ET)
    day_str = now.strftime("%Y-%m-%d")
    live_games, _, _ = v2._verified_live_games(day_str)
    if live_games:
        return

    _css()
    st.markdown(f'''<div class="kwl64-hero"><div class="kwl64-eye">🧠 {MODEL_VERSION}</div><h3>Step 6.4 • PBP-Rich Walk-Forward Calibration</h3><p>Step 6.3 proved checkpoint play-by-play reconstruction at 100% on its fidelity batch. This lab now uses those <b>partial possessions, pace and efficiency metrics</b> to replay the production Step-6 structure instead of score/clock-only data. Older games fit a strongly regularized candidate; the newest games remain untouched holdouts. The rejected Step-6.2 candidate stays rejected.</p></div>''', unsafe_allow_html=True)

    audit_key = "wnba_step64_pbp_calibration_audit"
    confirm_key = "wnba_step64_pbp_calibration_confirm"
    day_key = "wnba_step64_pbp_calibration_day"
    if st.session_state.get(day_key) != day_str:
        st.session_state.pop(audit_key, None)
        st.session_state.pop(confirm_key, None)
        st.session_state[day_key] = day_str

    c1, c2 = st.columns(2)
    with c1:
        run = st.button("🧠 Run PBP-rich calibration audit", use_container_width=True, key="wnba_step64_run")
    with c2:
        reset = st.button("♻️ Clear Step 6.4 cache", use_container_width=True, key="wnba_step64_clear")
    if reset:
        cal.clear_cache()
        st.session_state.pop(audit_key, None)
        st.session_state.pop(confirm_key, None)
        st.rerun()
    if run:
        with st.spinner("Building 24-game PBP-rich walk-forward set and fitting conservative candidate…"):
            st.session_state[audit_key] = cal.calibration_audit(day_str)
        st.session_state.pop(confirm_key, None)
        st.rerun()

    audit = st.session_state.get(audit_key)
    if not audit:
        st.info("Run Step 6.4 only. Earlier Step 5/6.1/6.2 audits do not need to be rerun. Production Step 6 remains V1 while this lab is idle.")
        return

    dataset = audit.get("dataset") or {}
    st.markdown(_dataset_html(dataset), unsafe_allow_html=True)
    if not audit.get("ready"):
        st.error("Step 6.4 dataset is not clean enough to calibrate safely. " + str(audit.get("error") or ""))
        if dataset.get("errors"):
            with st.expander("Step 6.4 transport diagnostics"):
                for item in dataset.get("errors") or []:
                    st.write("•", item)
        return

    fitted = audit.get("fitted") or {}
    st.markdown("### PBP-rich fitted candidate parameters")
    st.markdown(_params_html(fitted), unsafe_allow_html=True)
    st.markdown("### Older-game fitting check")
    st.markdown(_metric_block("TRAINING STATES • DIAGNOSTIC ONLY", (audit.get("train") or {}).get("baseline") or {}, (audit.get("train") or {}).get("candidate") or {}), unsafe_allow_html=True)

    validation = audit.get("validation") or {}
    st.markdown("### Newer-game out-of-sample validation")
    st.markdown(_metric_block("ALL HELD-OUT PBP-RICH STATES", validation.get("baseline") or {}, validation.get("candidate") or {}), unsafe_allow_html=True)
    st.markdown(_checkpoint_blocks(validation), unsafe_allow_html=True)
    contract = audit.get("contract") or {}
    st.markdown(_contract_html(contract, "ANALYTIC PBP-RICH HOLDOUT CONTRACT"), unsafe_allow_html=True)

    if not contract.get("safe_candidate"):
        st.warning("Candidate remains blocked. We will not spend paired 5M confirmation draws on a candidate that already failed the PBP-rich analytic holdout.")
        return

    st.success("Analytic PBP-rich holdout passed. The candidate is eligible for paired 5M confirmation, but is still NOT production.")
    if st.button("🎲 Run paired 5M PBP-rich holdout confirmation", use_container_width=True, key="wnba_step64_5m"):
        with st.spinner("Running baseline and candidate through paired 5,000,000-draw holdouts…"):
            st.session_state[confirm_key] = cal.run_5m_confirmation(audit)
        st.rerun()

    confirmation = st.session_state.get(confirm_key)
    if confirmation:
        if not confirmation.get("ready"):
            st.error(str(confirmation.get("error") or "5M confirmation unavailable"))
        else:
            st.markdown(_confirmation_html(confirmation), unsafe_allow_html=True)

    st.caption("Step 6.4 is calibration/validation only. No live model parameter, sportsbook probability, edge, EV, qualification, ranking or pick is changed here.")
