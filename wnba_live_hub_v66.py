"""WNBA Live Games V6.6 — structural Q4 repair + iPad-responsive audit UI.

V6.6 intentionally does not keep iterating the failed Step-6.4/6.5 parameter
family. It renders the proven live/replay/PBP foundation through V6.3, then adds
one simplified Q4 residual-shrink audit whose design follows directly from the
Step-6.5.1 failure diagnosis.

Production Step 6 remains V1. Halftime remains V1. No candidate is promoted.
"""
from __future__ import annotations

from datetime import datetime
import gc
from html import escape
from zoneinfo import ZoneInfo

import streamlit as st

import wnba_live_hub_v2 as v2
import wnba_live_hub_v63 as v63
import wnba_live_hub_v64 as v64
import wnba_live_step6_q4_shrinkage_v1 as shrink

ET = ZoneInfo("America/New_York")
MODEL_VERSION = "WNBA LIVE GAMES V6.6 • Q4 STRUCTURAL REPAIR"


def _ipad_css():
    st.markdown(r'''<style>
/* Route-scoped tablet/desktop repair. The Live Games route itself now renders
   outside the navigation columns; these rules only control responsive sizing. */
@media (min-width: 768px) {
  [data-testid="stMainBlockContainer"],
  .stMainBlockContainer,
  main .block-container {
    width: calc(100vw - 32px) !important;
    max-width: 1320px !important;
    margin-left: auto !important;
    margin-right: auto !important;
    padding-left: 16px !important;
    padding-right: 16px !important;
  }
  [data-testid="stMainBlockContainer"] > div,
  .stMainBlockContainer > div,
  main .block-container > div {
    width:100% !important;
    max-width: none !important;
  }
  .kwl66-grid {grid-template-columns: repeat(4,minmax(0,1fr)) !important;}
  .kwl66-foldgrid {grid-template-columns: repeat(2,minmax(0,1fr)) !important;}
  .kwl64-grid {grid-template-columns: repeat(2,minmax(0,1fr)) !important;}
  .kwl64-block,.kwl66-card,.kwl66-hero,.kwl66-note {width:100% !important;max-width:none !important;}
}
@media (min-width:768px) and (max-width:1100px) {
  [data-testid="stMainBlockContainer"],
  .stMainBlockContainer,
  main .block-container {
    width: calc(100vw - 24px) !important;
    max-width: none !important;
    padding-left: 12px !important;
    padding-right: 12px !important;
  }
  .kwl66-grid {grid-template-columns: repeat(2,minmax(0,1fr)) !important;}
}
@media (max-width:767px) {
  .kwl66-grid,.kwl66-foldgrid{grid-template-columns:1fr !important;}
}
.kwl66-hero{border:1px solid #37627b;border-radius:22px;padding:20px;margin:34px 0 14px;background:linear-gradient(145deg,#071a24,#081522)}
.kwl66-eye{font-size:.72rem;font-weight:950;letter-spacing:.08em;color:#9ddcff}
.kwl66-hero h3{font-size:1.55rem;color:#f7fbff;margin:8px 0}
.kwl66-hero p{color:#a7b6c2;line-height:1.6;margin:0}.kwl66-hero b{color:#fff}
.kwl66-note{border:1px solid #477386;background:#0a1b27;color:#b8d7e6;border-radius:15px;padding:13px;margin:10px 0;font-size:.72rem;line-height:1.55}
.kwl66-ok{border-color:#2d8257;background:#0d2d21;color:#a0efbf}.kwl66-warn{border-color:#8a722a;background:#2a240d;color:#ead879}
.kwl66-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}
.kwl66-card{border:1px solid #345469;background:#081522;border-radius:16px;padding:13px;min-width:0}
.kwl66-card span{display:block;color:#8399a8;font-size:.6rem;font-weight:900;letter-spacing:.03em}.kwl66-card b{display:block;color:#f3f8fb;font-size:1.04rem;margin-top:6px}.kwl66-card small{display:block;color:#8399a8;font-size:.58rem;margin-top:4px;line-height:1.35}
.kwl66-foldgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:10px 0}
.kwl66-fold{border:1px solid #345469;background:#081522;border-radius:16px;padding:12px;min-width:0}.kwl66-fold.pass{border-color:#2d8257}.kwl66-fold.hold{border-color:#8a722a}
.kwl66-foldhead{display:flex;justify-content:space-between;gap:8px;align-items:center;padding-bottom:8px;border-bottom:1px solid #20394a}.kwl66-foldhead b{font-size:.72rem;color:#edf5f9}.kwl66-foldhead span{font-size:.58rem;font-weight:950;color:#a0efbf}.kwl66-fold.hold .kwl66-foldhead span{color:#ead879}
.kwl66-folddate{font-size:.55rem;color:#8297a5;line-height:1.45;padding:7px 0}.kwl66-mini{display:flex;justify-content:space-between;gap:10px;border-bottom:1px solid #182e3c;padding:6px 0}.kwl66-mini:last-child{border-bottom:0}.kwl66-mini span{font-size:.55rem;color:#8297a5;font-weight:850}.kwl66-mini b{font-size:.63rem;color:#eef4f7;text-align:right}
</style>''', unsafe_allow_html=True)


def _metric(label: str, value: str, sub: str = "") -> str:
    return f'<div class="kwl66-card"><span>{escape(label)}</span><b>{escape(str(value))}</b>{f"<small>{escape(sub)}</small>" if sub else ""}</div>'


def _folds_html(folds: list[dict]) -> str:
    cards = []
    for fold in folds:
        base = fold.get("baseline") or {}
        cand = fold.get("candidate") or {}
        params = fold.get("params") or {}
        ok = bool((fold.get("contract") or {}).get("pass"))
        cards.append(f'''<div class="kwl66-fold {'pass' if ok else 'hold'}">
<div class="kwl66-foldhead"><b>FOLD {int(fold.get('fold') or 0)}</b><span>{'PASS' if ok else 'HOLD'}</span></div>
<div class="kwl66-folddate">train {escape(str(fold.get('train_start') or ''))[:10]} → {escape(str(fold.get('train_end') or ''))[:10]}<br>validate {escape(str(fold.get('validation_start') or ''))[:10]} → {escape(str(fold.get('validation_end') or ''))[:10]}</div>
<div class="kwl66-mini"><span>COMPOSITE</span><b>{v64._num(base.get('composite'),4)} → {v64._num(cand.get('composite'),4)}</b></div>
<div class="kwl66-mini"><span>BRIER</span><b>{v64._num(base.get('brier'),4)} → {v64._num(cand.get('brier'),4)}</b></div>
<div class="kwl66-mini"><span>MARGIN MAE</span><b>{v64._num(base.get('margin_mae'),2)} → {v64._num(cand.get('margin_mae'),2)} pts</b></div>
<div class="kwl66-mini"><span>WINNER ACC.</span><b>{v64._pct(base.get('winner_accuracy'))} → {v64._pct(cand.get('winner_accuracy'))}</b></div>
<div class="kwl66-mini"><span>ALPHA</span><b>{v64._num(params.get('alpha'),3)} (raw {v64._num(params.get('raw_alpha'),3)})</b></div>
<div class="kwl66-mini"><span>BETA</span><b>{v64._num(params.get('beta'),3,True)}</b></div>
</div>''')
    return '<div class="kwl66-foldgrid">' + ''.join(cards) + '</div>'


def _contract_html(contract: dict, title: str, retrospective=False) -> str:
    ok = bool(contract.get("pass"))
    reasons = list(contract.get("reasons") or [])
    warnings = list(contract.get("warnings") or [])
    items = "".join(f"<li>{escape(str(x))}</li>" for x in reasons)
    if not items:
        items = "<li>All defined stability gates passed.</li>"
    items += "".join(f"<li>NOTE • {escape(str(x))}</li>" for x in warnings)
    if retrospective:
        items += "<li>RETROSPECTIVE ONLY • not promotion evidence.</li>"
    cls = "kwl66-ok" if ok else "kwl66-warn"
    return f'<div class="kwl66-note {cls}"><b>{escape(title)} • {escape(str(contract.get("status") or ("PASS" if ok else "HOLD")))}</b><ul>{items}</ul></div>'


def _compact_audit(audit: dict) -> dict:
    """Keep only presentation/decision fields in session state.

    The raw audit dataset is useful while calculating folds, but the UI never
    needs its 56 per-game rows after the metrics are computed. Removing them
    prevents Streamlit from serializing and retaining a second copy of the
    historical replay dataset in session state.
    """
    dataset = dict((audit or {}).get("dataset") or {})
    dataset.pop("rows", None)
    return {
        "model_version": (audit or {}).get("model_version"),
        "ready": bool((audit or {}).get("ready")),
        "error": (audit or {}).get("error", ""),
        "dataset": dataset,
        "design": (audit or {}).get("design") or {},
        "folds": (audit or {}).get("folds") or [],
        "robustness": (audit or {}).get("robustness") or {},
        "tail": (audit or {}).get("tail") or {},
        "final_params": (audit or {}).get("final_params") or {},
        "shadow_freeze_eligible": bool((audit or {}).get("shadow_freeze_eligible")),
        "tail_consistent": bool((audit or {}).get("tail_consistent")),
        "sportsbook_used": bool((audit or {}).get("sportsbook_used")),
        "production_changed": bool((audit or {}).get("production_changed")),
        "prospective_games_used": int((audit or {}).get("prospective_games_used") or 0),
        "created_at": (audit or {}).get("created_at"),
    }


def _release_audit_memory():
    try:
        shrink.clear_cache()
    except Exception:
        pass
    gc.collect()


def render_wnba_live_hub(section_header=None, status_info=None, team_logo=None, h=None):
    # Preserve the verified live foundation and PBP fidelity audit, but stop
    # re-rendering the failed 6.4/6.5 model-search panels on every visit.
    v63.render_wnba_live_hub(section_header, status_info, team_logo, h)

    _ipad_css()

    now = datetime.now(ET)
    day_str = now.strftime("%Y-%m-%d")
    live_games, _, _ = v2._verified_live_games(day_str)
    if live_games:
        return

    st.markdown(f'''<div class="kwl66-hero"><div class="kwl66-eye">🧠 {MODEL_VERSION}</div><h3>Step 6.6 • Q4 Structural Repair Audit</h3><p>The Step-6.5.1 result identified the actual problem: this was <b>not a broken data feed</b>. The old calibration family was structurally forcing the production remaining-differential signal to stay at least 80% alive even though every rolling fit wanted it near zero or negative. It also changed total scale, home bias and uncertainty at the same time, which made the small sample noisier. Step 6.6 removes those extra degrees of freedom. Total and uncertainty stay exactly on production V1; only Q4 margin redistribution is tested with two strongly regularized terms.</p></div>''', unsafe_allow_html=True)
    st.markdown('<div class="kwl66-note kwl66-ok">🔒 PRODUCTION FIREWALL • Production Step 6 V1 is unchanged. Halftime is unchanged. No sportsbook input, no final-score leakage, no wider parameter search and no automatic promotion.</div>', unsafe_allow_html=True)

    key = "wnba_step66_q4_shrinkage_audit"
    day_key = "wnba_step66_q4_day"
    if st.session_state.get(day_key) != day_str:
        st.session_state.pop(key, None)
        st.session_state[day_key] = day_str

    c1, c2 = st.columns(2)
    with c1:
        run = st.button("🧠 Run Step 6.6 structural Q4 audit", use_container_width=True, key="wnba_step66_run")
    with c2:
        clear = st.button("♻️ Clear Step 6.6 cache", use_container_width=True, key="wnba_step66_clear")

    if clear:
        st.session_state.pop(key, None)
        _release_audit_memory()
        st.rerun()
    if run:
        with st.spinner("Building the 56-game Q4 PBP-rich audit and running four chronological folds…"):
            raw_audit = shrink.robustness_audit(day_str)
            st.session_state[key] = _compact_audit(raw_audit)
            del raw_audit
            _release_audit_memory()
        st.rerun()

    audit = st.session_state.get(key)
    if not audit:
        st.info("Run Step 6.6 only. Do not rerun the rejected Step 6.4/6.5 calibration panels. This is one structurally motivated repair, not another widening parameter experiment.")
        return

    dataset = audit.get("dataset") or {}
    design = audit.get("design") or {}
    st.markdown('<div class="kwl66-grid">' + ''.join([
        _metric('GAMES DISCOVERED', str(int(dataset.get('games_discovered') or 0))),
        _metric('CLEAN Q4 PBP-RICH', str(int(dataset.get('clean_q4_games') or 0)), f"required {int(dataset.get('required_clean_games') or 0)}"),
        _metric('CLEAN GAMES USED', str(int(design.get('clean_games_used') or 0))),
        _metric('DEVELOPMENT GAMES', str(int(design.get('development_games') or 0))),
        _metric('ROLLING OOS STATES', str(int(design.get('robust_validation_states') or 0))),
        _metric('TAIL RECHECK', str(int(design.get('tail_recheck_games') or 0)), 'retrospective only'),
        _metric('TOTAL MODEL', 'V1 EXACT', 'no total-scale calibration'),
        _metric('UNCERTAINTY MODEL', 'V1 EXACT', 'no SD calibration'),
        _metric('SPORTSBOOK USED', 'NO'),
        _metric('PRODUCTION CHANGED', 'NO'),
    ]) + '</div>', unsafe_allow_html=True)

    if not audit.get("ready"):
        st.error("Step 6.6 could not construct its predeclared 56-game design. " + str(audit.get("error") or ""))
        errors = dataset.get("errors") or []
        if errors:
            with st.expander("Step 6.6 transport diagnostics"):
                for error in errors:
                    st.write(error)
        return

    st.markdown("### Four chronological Q4 folds")
    st.markdown(_folds_html(audit.get("folds") or []), unsafe_allow_html=True)

    robust = audit.get("robustness") or {}
    st.markdown(v64._metric_block("ROLLING Q4 OOS • PRODUCTION V1 → TWO-PARAMETER REPAIR", robust.get("baseline") or {}, robust.get("candidate") or {}), unsafe_allow_html=True)
    st.markdown(_contract_html(robust.get("contract") or {}, "STRUCTURAL ROBUSTNESS CONTRACT"), unsafe_allow_html=True)

    tail = audit.get("tail") or {}
    st.markdown("### Recent-tail consistency recheck")
    st.markdown('<div class="kwl66-note kwl66-warn">⚠️ This tail is deliberately labeled retrospective. It can expose a bad repair, but it cannot prove promotion because these games were already visible during development.</div>', unsafe_allow_html=True)
    st.markdown(v64._metric_block("TAIL RECHECK • NOT PROMOTION EVIDENCE", tail.get("baseline") or {}, tail.get("candidate") or {}), unsafe_allow_html=True)
    st.markdown(_contract_html(tail.get("contract") or {}, "TAIL DEGRADATION GUARD", retrospective=True), unsafe_allow_html=True)

    params = audit.get("final_params") or {}
    st.markdown("### Structural candidate snapshot")
    st.markdown('<div class="kwl66-grid">' + ''.join([
        _metric('Q4 DIFF RETENTION α', v64._num(params.get('alpha'),3), f"raw {v64._num(params.get('raw_alpha'),3)} • allowed 0.000–1.000"),
        _metric('CURRENT-MARGIN TERM β', v64._num(params.get('beta'),3,True), f"raw {v64._num(params.get('raw_beta'),3,True)} • bounded -0.200–+0.100"),
        _metric('REMAINING TOTAL SCALE', '1.000×', 'hard-frozen to production V1'),
        _metric('SD SCALE', '1.000×', 'hard-frozen to production V1'),
        _metric('HOME BIAS TERM', 'REMOVED', 'no free home intercept'),
        _metric('FIT SAMPLE', str(int(params.get('sample') or 0))),
    ]) + '</div>', unsafe_allow_html=True)

    if audit.get("shadow_freeze_eligible"):
        st.success("The simplified Q4 structure cleared the rolling out-of-sample robustness contract. This is enough to freeze this exact two-parameter candidate for FUTURE shadow testing — not enough to promote it to production.")
        if not audit.get("tail_consistent"):
            st.warning("The already-seen recent tail triggered the degradation guard. Because it is retrospective, it is not a promotion holdout, but I would keep the candidate in shadow-only status and demand a larger prospective sample before any production consideration.")
    else:
        st.warning("The simplified repair did not clear the rolling robustness contract. If this happens, the correct conclusion is to keep Q4 on production V1 rather than keep tuning historical games until something passes.")
