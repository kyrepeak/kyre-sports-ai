"""WNBA Live Games V6.5.1 — selection-aware Q4 robustness audit.

This wrapper supersedes the first V6.5 presentation before it is used. During
review we identified an important statistical issue: the newest eight games in
the Step-6.5 tail were already exposed by Step 6.4 and therefore cannot honestly
serve as a brand-new final promotion holdout after Q4 was selected from those
results.

V6.5.1 keeps the Q4 robustness machinery, but treats all current historical
results as retrospective evidence only. It will NEVER expose a paired-5M
promotion button from those already-seen games. If robustness is strong, the
next legitimate step is to freeze the exact bounded Q4 candidate and validate it
prospectively on games completed after the freeze timestamp.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import streamlit as st

import wnba_live_hub_v2 as v2
import wnba_live_hub_v64 as v64
import wnba_live_step6_q4_promotion_v1 as q4

ET = ZoneInfo("America/New_York")
MODEL_VERSION = "WNBA LIVE GAMES V6.5.1 • Q4 SELECTION-AWARE ROBUSTNESS"


def _contract_html(contract: dict, title: str, allow_pass=True) -> str:
    raw_pass = bool(contract.get("pass"))
    safe = bool(raw_pass and allow_pass)
    reasons = list(contract.get("reasons") or [])
    warnings = list(contract.get("warnings") or [])
    items = "".join(f"<li>{escape(str(x))}</li>" for x in reasons)
    if not items:
        items = "<li>All retrospective hard gates passed.</li>"
    items += "".join(f"<li>WARNING • {escape(str(x))}</li>" for x in warnings)
    if raw_pass and not allow_pass:
        items += "<li>NOT A PROMOTION PASS • this sample was already exposed during Step 6.4 model selection.</li>"
    status = str(contract.get("status") or ("PASS" if raw_pass else "HOLD"))
    if raw_pass and not allow_pass:
        status = "RETROSPECTIVE CHECK ONLY"
    return f'''<div class="kwl64-contract {'pass' if safe else 'fail'}"><div><small>{escape(title)}</small><b>{escape(status)}</b></div><span>{'PASS' if safe else 'HOLD'}</span><ul>{items}</ul></div>'''


def _folds_html(folds: list[dict]) -> str:
    cards = []
    for fold in folds:
        b = fold.get("baseline") or {}
        c = fold.get("candidate") or {}
        p = fold.get("params") or {}
        ok = bool((fold.get("contract") or {}).get("pass"))
        hits = ", ".join(p.get("bound_hits") or []) or "none"
        cards.append(f'''<div class="kwl651-fold {'ok' if ok else 'hold'}">
<div class="kwl651-head"><b>FOLD {int(fold.get('fold') or 0)}</b><span>{'PASS' if ok else 'HOLD'}</span></div>
<div class="kwl651-dates">train {escape(str(fold.get('train_start') or ''))[:10]} → {escape(str(fold.get('train_end') or ''))[:10]} • validate {escape(str(fold.get('validation_start') or ''))[:10]} → {escape(str(fold.get('validation_end') or ''))[:10]}</div>
<div class="kwl651-mini"><span>COMPOSITE</span><b>{v64._num(b.get('composite'),4)} → {v64._num(c.get('composite'),4)}</b></div>
<div class="kwl651-mini"><span>BRIER</span><b>{v64._num(b.get('brier'),4)} → {v64._num(c.get('brier'),4)}</b></div>
<div class="kwl651-mini"><span>MARGIN MAE</span><b>{v64._num(b.get('margin_mae'),2)} → {v64._num(c.get('margin_mae'),2)} pts</b></div>
<div class="kwl651-mini"><span>WINNER ACC.</span><b>{v64._pct(b.get('winner_accuracy'))} → {v64._pct(c.get('winner_accuracy'))}</b></div>
<div class="kwl651-mini"><span>DIFF SCALE</span><b>{v64._num(p.get('remaining_diff_scale'),3)}×</b></div>
<div class="kwl651-mini"><span>BOUND HITS</span><b>{escape(hits)}</b></div>
</div>''')
    return '<div class="kwl651-foldgrid">' + ''.join(cards) + '</div>'


def _params_html(fitted: dict) -> str:
    p = ((fitted.get("checkpoints") or {}).get(q4.CHECKPOINT) or {})
    hits = ", ".join(p.get("bound_hits") or []) or "none"
    return f'''<div class="kwl64-block"><div class="kwl64-blockhead"><b>Q4 SHADOW-CANDIDATE PARAMETER SNAPSHOT</b><span>{int(p.get('sample') or 0)} DEVELOPMENT Q4 STATE(S)</span></div><div class="kwl64-grid">
{v64._metric('REMAINING TOTAL SCALE', v64._num(p.get('remaining_total_scale'),3)+'×', 'Step 6.4 model form')}
{v64._metric('REMAINING DIFF SCALE', v64._num(p.get('remaining_diff_scale'),3)+'×', '0.800 hard floor unchanged')}
{v64._metric('LEAD PERSISTENCE', v64._num(p.get('lead_persistence'),3,True), 'same bounded coefficient')}
{v64._metric('HOME BIAS / 10 MIN', v64._num(p.get('home_bias_per10'),3,True)+' pts', 'same bounded coefficient')}
{v64._metric('SD SCALE', v64._num(p.get('sd_scale'),3)+'×', 'same bounded coefficient')}
{v64._metric('BOUND HITS', hits, 'no bounds were expanded')}
</div></div>'''


def _design_html(audit: dict) -> str:
    d = audit.get("dataset") or {}
    design = audit.get("design") or {}
    return f'''<div class="kwl64-grid">
{v64._metric('GAMES DISCOVERED', str(int(d.get('games_discovered') or 0)))}
{v64._metric('CLEAN Q4 PBP-RICH', str(int(d.get('clean_q4_games') or 0)))}
{v64._metric('ROLLING FOLDS', str(int(design.get('robust_folds') or 0)), 'chronological retrospective robustness')}
{v64._metric('ROLLING OOS Q4 STATES', str(int(design.get('robust_validation_states') or 0)), 'disjoint fold validation blocks')}
{v64._metric('TAIL RECHECK GAMES', str(int(design.get('fresh_final_holdout_games') or 0)), 'selection-exposed in Step 6.4')}
{v64._metric('HALFTIME', 'V1 FROZEN', 'not recalibrated')}
{v64._metric('PARAMETER BOUNDS', 'UNCHANGED', 'no lower-floor expansion')}
{v64._metric('SPORTSBOOK USED', 'NO')}
{v64._metric('FINAL BOXSCORE IN PROJECTION', 'NO')}
{v64._metric('PROSPECTIVE PROMOTION DATA', '0', 'must occur after candidate freeze')}
</div>'''


def _css():
    st.markdown(r'''<style>
.kwl651-hero{border:1px dashed #8a722a;border-radius:22px;padding:20px;margin:34px 0 14px;background:linear-gradient(145deg,#171707,#081522)}.kwl651-eye{font-size:.7rem;font-weight:950;letter-spacing:.08em;color:#ead879}.kwl651-hero h3{font-size:1.45rem;color:#f7fbff;margin:8px 0}.kwl651-hero p{color:#aeb7ba;line-height:1.6;margin:0}.kwl651-hero b{color:#fff}.kwl651-lock{border:1px solid #2d8257;background:#0d2d21;color:#9cf0bd;border-radius:14px;padding:12px;margin:10px 0;font-size:.68rem;line-height:1.5}.kwl651-warning{border:1px solid #8a722a;background:#2a240d;color:#ead879;border-radius:14px;padding:12px;margin:10px 0;font-size:.68rem;line-height:1.5}.kwl651-foldgrid{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin:10px 0}.kwl651-fold{border:1px solid #35536a;background:#081522;border-radius:16px;padding:11px}.kwl651-fold.ok{border-color:#2d8257}.kwl651-fold.hold{border-color:#8a722a}.kwl651-head{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #213b4e;padding-bottom:7px}.kwl651-head b{color:#eaf4f8;font-size:.7rem}.kwl651-head span{font-size:.56rem;font-weight:950;color:#9eeabf}.kwl651-fold.hold .kwl651-head span{color:#ead879}.kwl651-dates{color:#7f96a6;font-size:.52rem;line-height:1.4;padding:7px 0}.kwl651-mini{display:flex;justify-content:space-between;gap:7px;padding:5px 0;border-bottom:1px solid #172b38}.kwl651-mini:last-child{border-bottom:0}.kwl651-mini span{color:#8298a7;font-size:.52rem;font-weight:850}.kwl651-mini b{color:#edf3f6;font-size:.6rem;text-align:right}@media(max-width:640px){.kwl651-hero{padding:16px}.kwl651-foldgrid{grid-template-columns:1fr}}
</style>''', unsafe_allow_html=True)


def render_wnba_live_hub(section_header=None, status_info=None, team_logo=None, h=None):
    v64.render_wnba_live_hub(section_header, status_info, team_logo, h)

    now = datetime.now(ET)
    day_str = now.strftime("%Y-%m-%d")
    live_games, _, _ = v2._verified_live_games(day_str)
    if live_games:
        return

    _css()
    st.markdown(f'''<div class="kwl651-hero"><div class="kwl651-eye">🧭 {MODEL_VERSION}</div><h3>Step 6.5 • Q4 Robustness Before Prospective Validation</h3><p>I tightened this step before using it. The Step-6.4 screenshots already exposed the newest eight-game Q4 holdout and that evidence is what led us to isolate Q4. Calling those same games a new “fresh” promotion holdout would create <b>model-selection leakage</b>. Step 6.5 therefore uses current history only for retrospective robustness. A real promotion will require future games that occur after the exact Q4 candidate is frozen.</p></div>''', unsafe_allow_html=True)
    st.markdown('<div class="kwl651-lock">🔒 PRODUCTION FIREWALL • Halftime stays Step-6 V1. Q4 production also stays V1. No parameter bounds are loosened, no sportsbook input enters the projection, and no retrospective result can auto-promote a candidate.</div>', unsafe_allow_html=True)

    audit_key = "wnba_step651_q4_audit"
    day_key = "wnba_step651_q4_day"
    if st.session_state.get(day_key) != day_str:
        st.session_state.pop(audit_key, None)
        st.session_state[day_key] = day_str

    c1, c2 = st.columns(2)
    with c1:
        run = st.button("🧭 Run selection-aware Q4 robustness audit", use_container_width=True, key="wnba_step651_run")
    with c2:
        clear = st.button("♻️ Clear Step 6.5 cache", use_container_width=True, key="wnba_step651_clear")
    if clear:
        q4.clear_cache()
        st.session_state.pop(audit_key, None)
        st.rerun()
    if run:
        with st.spinner("Rebuilding Q4 PBP-rich history and running chronological robustness checks…"):
            st.session_state[audit_key] = q4.robustness_audit(day_str)
        st.rerun()

    audit = st.session_state.get(audit_key)
    if not audit:
        st.info("Run Step 6.5 only. Earlier Steps 6.2–6.4 do not need to be rerun. This step will not offer a 5M promotion button from already-exposed historical games.")
        return

    st.markdown(_design_html(audit), unsafe_allow_html=True)
    if not audit.get("ready"):
        st.error("The Q4 robustness design could not be constructed cleanly. " + str(audit.get("error") or ""))
        errors = (audit.get("dataset") or {}).get("errors") or []
        if errors:
            with st.expander("Step 6.5 transport diagnostics"):
                for x in errors:
                    st.write(x)
        return

    st.markdown("### Chronological Q4 robustness folds")
    st.markdown(_folds_html(audit.get("folds") or []), unsafe_allow_html=True)
    robust = audit.get("robustness") or {}
    st.markdown(v64._metric_block("ROLLING-FOLD Q4 OOS • RETROSPECTIVE", robust.get("baseline") or {}, robust.get("candidate") or {}), unsafe_allow_html=True)
    st.markdown(_contract_html(robust.get("contract") or {}, "Q4 ROBUSTNESS CONTRACT", allow_pass=True), unsafe_allow_html=True)

    st.markdown("### Step-6.4-exposed tail recheck")
    st.markdown('<div class="kwl651-warning">⚠️ SELECTION-AWARE LABEL • These newest games remain useful as a consistency recheck because they were never used to fit this final parameter snapshot, but they are NOT a fresh promotion holdout: their Q4 behavior was already visible in Step 6.4 and influenced the decision to pursue Q4.</div>', unsafe_allow_html=True)
    tail = audit.get("fresh_holdout") or {}
    st.markdown(v64._metric_block("Q4 TAIL RECHECK • NOT FINAL PROMOTION EVIDENCE", tail.get("baseline") or {}, tail.get("candidate") or {}), unsafe_allow_html=True)
    st.markdown(_contract_html(tail.get("contract") or {}, "TAIL CONSISTENCY CHECK", allow_pass=False), unsafe_allow_html=True)

    st.markdown("### Candidate snapshot for prospective shadow testing")
    st.markdown(_params_html(audit.get("final_fitted") or {}), unsafe_allow_html=True)

    robust_ok = bool((robust.get("contract") or {}).get("pass"))
    tail_ok = bool((tail.get("contract") or {}).get("pass"))
    if robust_ok and tail_ok:
        st.success("Retrospective evidence is strong enough to FREEZE a Q4 shadow candidate — not to promote it. The next build will hard-code this exact bounded parameter set with a freeze timestamp and grade only games occurring after that timestamp.")
        st.markdown('<div class="kwl651-lock">NEXT HARD GATE • Prospective shadow validation. No historical game already visible today can satisfy it. We will require a minimum future sample before paired 5M promotion confirmation is allowed.</div>', unsafe_allow_html=True)
    else:
        st.warning("The Q4 candidate is not stable enough even for prospective shadow freezing. Production Step 6 V1 remains unchanged and no further simulation confirmation should be run.")
