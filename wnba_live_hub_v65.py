"""WNBA Live Games V6.5 — Q4-specific robustness and promotion audit.

Renders V6.4 unchanged, then appends a fail-closed Q4-only audit. Halftime stays
on production Step-6 V1. The Q4 candidate uses the same bounded PBP-rich model
form from Step 6.4; no parameter bound is loosened and no candidate is promoted
automatically.
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
MODEL_VERSION = "WNBA LIVE GAMES V6.5 • Q4 ROBUSTNESS + FRESH HOLDOUT"


def _contract_html(contract: dict, title: str) -> str:
    safe = bool(contract.get("pass"))
    reasons = list(contract.get("reasons") or [])
    warnings = list(contract.get("warnings") or [])
    items = "".join(f"<li>{escape(str(x))}</li>" for x in reasons)
    if not items:
        items = "<li>All hard gates passed.</li>"
    items += "".join(f"<li>WARNING • {escape(str(x))}</li>" for x in warnings)
    status = str(contract.get("status") or ("PASS" if safe else "HOLD"))
    return f'''<div class="kwl64-contract {'pass' if safe else 'fail'}"><div><small>{escape(title)}</small><b>{escape(status)}</b></div><span>{'PASS' if safe else 'HOLD'}</span><ul>{items}</ul></div>'''


def _folds_html(folds: list[dict]) -> str:
    cards = []
    for fold in folds:
        b = fold.get("baseline") or {}
        c = fold.get("candidate") or {}
        p = fold.get("params") or {}
        ok = bool((fold.get("contract") or {}).get("pass"))
        hits = ", ".join(p.get("bound_hits") or []) or "none"
        cards.append(f'''<div class="kwl65-fold {'ok' if ok else 'hold'}">
<div class="kwl65-foldhead"><b>FOLD {int(fold.get('fold') or 0)}</b><span>{'PASS' if ok else 'HOLD'}</span></div>
<div class="kwl65-dates">train {escape(str(fold.get('train_start') or ''))[:10]} → {escape(str(fold.get('train_end') or ''))[:10]} • validate {escape(str(fold.get('validation_start') or ''))[:10]} → {escape(str(fold.get('validation_end') or ''))[:10]}</div>
<div class="kwl65-mini"><span>COMPOSITE</span><b>{v64._num(b.get('composite'),4)} → {v64._num(c.get('composite'),4)}</b></div>
<div class="kwl65-mini"><span>BRIER</span><b>{v64._num(b.get('brier'),4)} → {v64._num(c.get('brier'),4)}</b></div>
<div class="kwl65-mini"><span>MARGIN MAE</span><b>{v64._num(b.get('margin_mae'),2)} → {v64._num(c.get('margin_mae'),2)} pts</b></div>
<div class="kwl65-mini"><span>WINNER ACC.</span><b>{v64._pct(b.get('winner_accuracy'))} → {v64._pct(c.get('winner_accuracy'))}</b></div>
<div class="kwl65-mini"><span>DIFF SCALE</span><b>{v64._num(p.get('remaining_diff_scale'),3)}×</b></div>
<div class="kwl65-mini"><span>BOUND HITS</span><b>{escape(hits)}</b></div>
</div>''')
    return '<div class="kwl65-foldgrid">' + ''.join(cards) + '</div>'


def _params_html(fitted: dict) -> str:
    p = ((fitted.get("checkpoints") or {}).get(q4.CHECKPOINT) or {})
    hits = ", ".join(p.get("bound_hits") or []) or "none"
    return f'''<div class="kwl64-block"><div class="kwl64-blockhead"><b>FINAL Q4 FIT • DEVELOPMENT POOL ONLY</b><span>{int(p.get('sample') or 0)} Q4 TRAIN STATE(S)</span></div><div class="kwl64-grid">
{v64._metric('REMAINING TOTAL SCALE', v64._num(p.get('remaining_total_scale'),3)+'×', 'identity 1.000')}
{v64._metric('REMAINING DIFF SCALE', v64._num(p.get('remaining_diff_scale'),3)+'×', 'hard floor remains 0.800')}
{v64._metric('LEAD PERSISTENCE', v64._num(p.get('lead_persistence'),3,True), 'identity +0.000')}
{v64._metric('HOME BIAS / 10 MIN', v64._num(p.get('home_bias_per10'),3,True)+' pts', 'identity +0.000')}
{v64._metric('SD SCALE', v64._num(p.get('sd_scale'),3)+'×', 'identity 1.000')}
{v64._metric('BOUND HITS', hits, 'bounds were NOT expanded')}
</div></div>'''


def _design_html(audit: dict) -> str:
    d = audit.get("dataset") or {}
    design = audit.get("design") or {}
    return f'''<div class="kwl64-grid">
{v64._metric('RECENT GAMES DISCOVERED', str(int(d.get('games_discovered') or 0)))}
{v64._metric('CLEAN Q4 PBP-RICH GAMES', str(int(d.get('clean_q4_games') or 0)))}
{v64._metric('DEVELOPMENT GAMES', str(int(design.get('development_games') or 0)), 'never includes final tail holdout')}
{v64._metric('FRESH FINAL HOLDOUT', str(int(design.get('fresh_final_holdout_games') or 0)), 'newest games • never fit')}
{v64._metric('ROLLING ROBUSTNESS FOLDS', str(int(design.get('robust_folds') or 0)))}
{v64._metric('ROBUST OOS Q4 STATES', str(int(design.get('robust_validation_states') or 0)), 'disjoint validation blocks')}
{v64._metric('HALFTIME POLICY', 'V1 FROZEN', 'no halftime candidate is tested here')}
{v64._metric('PARAMETER BOUNDS', 'UNCHANGED', 'no 0.800 floor expansion')}
{v64._metric('FINAL BOXSCORE IN PROJECTION', 'NO')}
{v64._metric('SPORTSBOOK USED', 'NO')}
</div>'''


def _confirmation_html(result: dict) -> str:
    contract = result.get("contract") or {}
    failures = result.get("convergence_failures") or []
    convergence = (
        '<div class="kwl64-ok">All Q4 baseline/candidate 5M runs passed the existing convergence contract.</div>'
        if not failures else
        '<div class="kwl64-bad">Convergence failures: ' + escape(' • '.join(failures)) + '</div>'
    )
    return (
        f'<div class="kwl64-confirm"><b>🎲 Q4-ONLY PAIRED 5M FRESH HOLDOUT</b><span>{int(result.get("validation_states") or 0)} states • {int(result.get("total_simulations") or 0):,} total draws</span></div>'
        + v64._metric_block("Q4 5M FRESH HOLDOUT", result.get("baseline") or {}, result.get("candidate") or {})
        + convergence
        + _contract_html(contract, "Q4 5M PROMOTION CONTRACT")
        + f'<div class="kwl64-note">Paired deterministic seeds: YES • simulator runtime {v64._num(result.get("runtime_seconds"),2)} s • halftime remains V1 • candidate is still review-only.</div>'
    )


def _css():
    st.markdown(r'''<style>
.kwl65-hero{border:1px dashed #8a722a;border-radius:22px;padding:20px;margin:34px 0 14px;background:linear-gradient(145deg,#171707,#081522)}
.kwl65-eye{font-size:.7rem;font-weight:950;letter-spacing:.08em;color:#ead879}.kwl65-hero h3{font-size:1.5rem;color:#f7fbff;margin:8px 0}.kwl65-hero p{color:#aeb7ba;line-height:1.6;margin:0}.kwl65-hero b{color:#fff}
.kwl65-freeze{border:1px solid #2d8257;background:#0d2d21;color:#9cf0bd;border-radius:14px;padding:12px;margin:10px 0;font-size:.68rem;line-height:1.5}
.kwl65-foldgrid{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin:10px 0}.kwl65-fold{border:1px solid #35536a;background:#081522;border-radius:16px;padding:11px}.kwl65-fold.ok{border-color:#2d8257}.kwl65-fold.hold{border-color:#8a722a}.kwl65-foldhead{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #213b4e;padding-bottom:7px}.kwl65-foldhead b{color:#eaf4f8;font-size:.7rem}.kwl65-foldhead span{font-size:.56rem;font-weight:950;color:#9eeabf}.kwl65-fold.hold .kwl65-foldhead span{color:#ead879}.kwl65-dates{color:#7f96a6;font-size:.52rem;line-height:1.4;padding:7px 0}.kwl65-mini{display:flex;justify-content:space-between;gap:7px;padding:5px 0;border-bottom:1px solid #172b38}.kwl65-mini:last-child{border-bottom:0}.kwl65-mini span{color:#8298a7;font-size:.52rem;font-weight:850}.kwl65-mini b{color:#edf3f6;font-size:.6rem;text-align:right}
@media(max-width:640px){.kwl65-hero{padding:16px}.kwl65-foldgrid{grid-template-columns:1fr}}
</style>''', unsafe_allow_html=True)


def render_wnba_live_hub(section_header=None, status_info=None, team_logo=None, h=None):
    v64.render_wnba_live_hub(section_header, status_info, team_logo, h)

    now = datetime.now(ET)
    day_str = now.strftime("%Y-%m-%d")
    live_games, _, _ = v2._verified_live_games(day_str)
    if live_games:
        return

    _css()
    st.markdown(f'''<div class="kwl65-hero"><div class="kwl65-eye">🧭 {MODEL_VERSION}</div><h3>Step 6.5 • Q4-Specific Robustness + Fresh Holdout</h3><p>This is not another parameter-search experiment. Step 6.4 already showed the useful signal was <b>checkpoint-specific</b>: Q4 improved while halftime did not clear promotion. Step 6.5 therefore freezes halftime at production V1, keeps the exact Step-6.4 Q4 model form and hard bounds, tests it across multiple chronological folds, then reserves the newest games as a separate final holdout. Only if both layers pass can the existing 5M simulator be used for Q4 confirmation.</p></div>''', unsafe_allow_html=True)
    st.markdown('<div class="kwl65-freeze">🔒 HALFTIME IS FROZEN AT PRODUCTION V1. No halftime calibration, no wider parameter search, no relaxed 0.800 remaining-differential floor, and no sportsbook input are allowed in Step 6.5.</div>', unsafe_allow_html=True)

    audit_key = "wnba_step65_q4_audit"
    confirm_key = "wnba_step65_q4_confirm"
    day_key = "wnba_step65_q4_day"
    if st.session_state.get(day_key) != day_str:
        st.session_state.pop(audit_key, None)
        st.session_state.pop(confirm_key, None)
        st.session_state[day_key] = day_str

    c1, c2 = st.columns(2)
    with c1:
        run = st.button("🧭 Run Q4 robustness + fresh holdout audit", use_container_width=True, key="wnba_step65_run")
    with c2:
        clear = st.button("♻️ Clear Step 6.5 cache", use_container_width=True, key="wnba_step65_clear")

    if clear:
        q4.clear_cache()
        st.session_state.pop(audit_key, None)
        st.session_state.pop(confirm_key, None)
        st.rerun()
    if run:
        with st.spinner("Building Q4-only PBP-rich robustness folds and preserving the newest tail holdout…"):
            st.session_state[audit_key] = q4.robustness_audit(day_str)
        st.session_state.pop(confirm_key, None)
        st.rerun()

    audit = st.session_state.get(audit_key)
    if not audit:
        st.info("Run Step 6.5 only. Do not rerun 6.2/6.3/6.4. This audit independently rebuilds the Q4 evidence set; production Step 6 remains unchanged.")
        return

    st.markdown(_design_html(audit), unsafe_allow_html=True)
    if not audit.get("ready"):
        st.error("Step 6.5 could not construct the required Q4 robustness/fresh-holdout design. " + str(audit.get("error") or ""))
        errors = (audit.get("dataset") or {}).get("errors") or []
        if errors:
            with st.expander("Step 6.5 transport diagnostics"):
                for x in errors:
                    st.write(x)
        return

    st.markdown("### Chronological Q4 robustness folds")
    st.markdown(_folds_html(audit.get("folds") or []), unsafe_allow_html=True)
    robust = audit.get("robustness") or {}
    st.markdown(v64._metric_block("ROLLING-FOLD Q4 OUT-OF-SAMPLE • AGGREGATE", robust.get("baseline") or {}, robust.get("candidate") or {}), unsafe_allow_html=True)
    st.markdown(_contract_html(robust.get("contract") or {}, "Q4 ROBUSTNESS CONTRACT"), unsafe_allow_html=True)

    st.markdown("### Final Q4 candidate fit")
    st.markdown(_params_html(audit.get("final_fitted") or {}), unsafe_allow_html=True)
    fresh = audit.get("fresh_holdout") or {}
    st.markdown("### Fresh newest-game Q4 holdout")
    st.markdown(v64._metric_block("FRESH Q4 HOLDOUT • NEVER FIT", fresh.get("baseline") or {}, fresh.get("candidate") or {}), unsafe_allow_html=True)
    st.markdown(_contract_html(fresh.get("contract") or {}, "FRESH Q4 ANALYTIC CONTRACT"), unsafe_allow_html=True)

    if not audit.get("safe_for_5m"):
        st.warning("Step 6.5 remains blocked. We will not spend 5M confirmation draws unless both the rolling robustness layer and the separate fresh Q4 holdout pass. Production Step 6 V1 remains untouched.")
        return

    st.success("Both Q4 analytic evidence layers passed. The candidate is eligible for paired 5M confirmation only; it is NOT promoted.")
    if st.button("🎲 Run paired 5M Q4 fresh-holdout confirmation", use_container_width=True, key="wnba_step65_5m"):
        with st.spinner("Running paired baseline/candidate 5M simulations on the fresh Q4 holdout…"):
            st.session_state[confirm_key] = q4.run_5m_confirmation(audit)
        st.rerun()

    result = st.session_state.get(confirm_key)
    if result:
        if not result.get("ready"):
            st.error(str(result.get("error") or "Q4 5M confirmation unavailable"))
        else:
            st.markdown(_confirmation_html(result), unsafe_allow_html=True)
            if (result.get("contract") or {}).get("pass"):
                st.info("Step 6.5 has produced a Q4-only V2 REVIEW CANDIDATE. Nothing has been promoted yet. The next action would be to hard-code that exact Q4 parameter set in a separate production V2 implementation and rerun the same holdout contract against the exact production code path.")
            else:
                st.warning("Q4 5M confirmation failed. The candidate stays rejected and production Step 6 V1 remains active.")
