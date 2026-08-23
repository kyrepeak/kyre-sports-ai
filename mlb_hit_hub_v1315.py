"""MLB 1+ Hit UI V13.15 — Step 12 final production audit + freeze.

Final presentation/audit wrapper around verified V13.14. No source-model feature,
probability, Monte Carlo, candidate-pool, lineup, ranking, confidence, calibration
or persistence logic is changed.

Step 12 verifies the already-rendered production path instead of adding a new model
input. It audits:
1) the V13 engine / V13.3 candidate-pool / history bindings,
2) simulation payload validity and convergence,
3) descending 1+ probability order,
4) explicit CONFIRMED/PROJECTED lineup labeling,
5) all eleven previously verified card-context layers, and
6) that card presentation does not mutate the modeled result payload.

The audit is fail closed. A failed check reports CHECK and never rewrites a result,
reranks a player, reruns Monte Carlo, fills missing data, or forces a pick.
"""
from __future__ import annotations

from html import escape
import math

import streamlit as st

import mlb_hit_hub_v1314 as prior

active = prior.active          # verified V13.3 full-slate scanner module
core = prior.core              # hit_hub_v131, whose model functions come from engine
visual = prior.visual

UI_VERSION = "V13.15"
_BASE_PICK_HTML = prior._pick_html_v1314

_LAYER_MARKERS = [
    (1, "Batter + team identity", "MLB BATTER + TEAM IDENTITY"),
    (2, "Opposing probable starter", "OPPOSING PROBABLE STARTER"),
    (3, "Official batter-vs-pitcher history", "BATTER VS PITCHER"),
    (4, "Pitch mix + platoon matchup", "STEP 4"),
    (5, "Park/weather + bullpen environment", "STEP 5"),
    (6, "Hit opportunity / PA context", "STEP 6"),
    (7, "Recent form + contact quality", "STEP 7"),
    (8, "Opponent run prevention + fielding", "STEP 8"),
    (9, "Bullpen arms + handedness pressure", "STEP 9"),
    (10, "Starter workload + TTO", "STEP 10"),
    (11, "Home-plate umpire + zone context", "STEP 11"),
]


def _num(value, default=None):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError, OverflowError):
        return default


def _result_key(result, rank):
    r = result or {}
    return f"{rank}:{r.get('game_pk')}:{r.get('player_id')}"


def _fingerprint(result):
    """Fingerprint only fields owned by the modeled/ranked result contract."""
    r = result or {}
    s = r.get("sim") or {}
    return (
        r.get("player_id"), r.get("game_pk"), r.get("position"),
        r.get("lineup_confirmed"), r.get("lineup_source"),
        r.get("confidence"), r.get("data_score"),
        r.get("starter_rate"), r.get("bullpen_rate"), r.get("expected_ab"),
        s.get("simulations"), s.get("batches"), s.get("seed"),
        s.get("p_zero"), s.get("p_one_plus"), s.get("p_exact_one"),
        s.get("p_two_plus"), s.get("p_three_plus"), s.get("expected_hits"),
        s.get("median_hits"), s.get("mode_hits"), s.get("mc_se"),
        s.get("scenario_low"), s.get("scenario_high"), s.get("batch_range"),
        s.get("converged"),
    )


def _pick_html_v1315(result, rank):
    before = _fingerprint(result if isinstance(result, dict) else {})
    html = _BASE_PICK_HTML(result, rank)
    if not isinstance(html, str):
        html = str(html or "")
    after = _fingerprint(result if isinstance(result, dict) else {})

    upper = html.upper()
    layers = {step: (marker.upper() in upper) for step, _, marker in _LAYER_MARKERS}
    audit = st.session_state.setdefault("hit1315_card_audit", {})
    audit[_result_key(result if isinstance(result, dict) else {}, rank)] = {
        "rank": int(rank),
        "player": str((result or {}).get("player_name") or "Unknown") if isinstance(result, dict) else "Unknown",
        "layers": layers,
        "mutation_free": before == after,
    }
    return html


# Patch only V13.3's module-global card renderer. The scanner/model pipeline remains
# the verified source path and resolves this renderer only when drawing Top-5 cards.
active._pick_html = _pick_html_v1315


_EXTRA_CSS = r"""
<style>
.hit1315-audit{margin:18px 0 12px;padding:15px 16px;border:1px solid #2c5f72;background:linear-gradient(145deg,#0a1c28,#07141d);border-radius:18px}
.hit1315-kicker{font-size:.58rem;letter-spacing:.11em;color:#57d9ff;font-weight:950;text-transform:uppercase}
.hit1315-title{font-size:1.15rem;color:#f4fbff;font-weight:950;margin-top:4px}
.hit1315-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:12px}
.hit1315-stat{border:1px solid #264758;background:#081722;border-radius:12px;padding:10px}
.hit1315-stat span{display:block;color:#7897a8;font-size:.52rem;text-transform:uppercase;font-weight:900;letter-spacing:.06em}
.hit1315-stat b{display:block;color:#f5fbff;font-size:1rem;margin-top:4px}.hit1315-stat .pass{color:#72efb4}.hit1315-stat .check{color:#ffe07d}
.hit1315-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;padding:7px 0;border-top:1px solid #193442;font-size:.68rem;color:#a9bdc8}
.hit1315-row:first-child{border-top:0}.hit1315-row b{color:#eef7fb}.hit1315-pass{color:#72efb4;font-weight:950}.hit1315-check{color:#ffe07d;font-weight:950}
.hit1315-note{font-size:.57rem;color:#76909e;line-height:1.5;margin-top:10px}
@media(max-width:700px){.hit1315-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.hit1315-row{font-size:.62rem}}
</style>
"""

if "hit1315-audit" not in core.HIT_CSS:
    core.HIT_CSS = core.HIT_CSS + _EXTRA_CSS


def _engine_bindings_ok():
    required = ["deep_scan", "prescreen", "monte", "model_inputs", "confidence"]
    return all(getattr(getattr(core, name, None), "__module__", "") == "engine" for name in required)


def _candidate_binding_ok():
    fn = getattr(active, "_candidate_pool", None)
    return getattr(fn, "__module__", "") == "mlb_hit_hub_v133"


def _history_binding_ok():
    fn = getattr(core, "save_top5_snapshot", None)
    return getattr(fn, "__module__", "") == "history"


def _sim_row_ok(result):
    s = (result or {}).get("sim") or {}
    p0 = _num(s.get("p_zero"))
    p1 = _num(s.get("p_one_plus"))
    p2 = _num(s.get("p_two_plus"))
    p3 = _num(s.get("p_three_plus"))
    xh = _num(s.get("expected_hits"))
    sims = _num(s.get("simulations"), 0) or 0
    if None in (p0, p1, p2, p3, xh):
        return False
    return (
        sims > 0
        and bool(s.get("converged"))
        and 0 <= p0 <= 1 and 0 <= p1 <= 1
        and 0 <= p3 <= p2 <= p1 <= 1
        and abs((p0 + p1) - 1.0) <= 0.002
        and xh >= 0
    )


def _rank_order_ok(results):
    probs = [_num(((r or {}).get("sim") or {}).get("p_one_plus")) for r in results]
    if not probs or any(p is None for p in probs):
        return False
    return all(probs[i] >= probs[i + 1] for i in range(len(probs) - 1))


def _lineup_labels_ok(results):
    if not results:
        return False
    for r in results:
        if not isinstance(r.get("lineup_confirmed"), bool):
            return False
        if not str(r.get("lineup_source") or "").strip():
            return False
    return True


def _status_html(label, ok):
    cls = "hit1315-pass" if ok else "hit1315-check"
    text = "✅ PASS" if ok else "⚠️ CHECK"
    return f'<div class="hit1315-row"><b>{escape(label)}</b><span class="{cls}">{text}</span></div>'


def _render_final_audit():
    results = list(st.session_state.get("hit133_results") or [])
    top5 = results[:5]
    card_audit = st.session_state.get("hit1315_card_audit") or {}

    if not top5:
        st.info("🏁 Step 12 audit is armed. Run the full selected-slate scanner to verify and freeze the production output.")
        return

    current_card_rows = []
    for rank, r in enumerate(top5, 1):
        row = card_audit.get(_result_key(r, rank)) or {}
        current_card_rows.append(row)

    expected_layer_checks = len(top5) * len(_LAYER_MARKERS)
    passed_layer_checks = sum(
        1 for row in current_card_rows for ok in (row.get("layers") or {}).values() if ok
    )
    cards_audited = sum(1 for row in current_card_rows if row)
    mutation_ok = cards_audited == len(top5) and all(bool(row.get("mutation_free")) for row in current_card_rows)
    layers_ok = expected_layer_checks > 0 and passed_layer_checks == expected_layer_checks
    engine_ok = _engine_bindings_ok()
    candidate_ok = _candidate_binding_ok()
    history_ok = _history_binding_ok()
    sims_ok = bool(results) and all(_sim_row_ok(r) for r in results)
    rank_ok = _rank_order_ok(results)
    lineup_ok = _lineup_labels_ok(results)

    checks = [
        ("V13 engine functions still bound to engine.py", engine_ok),
        ("Full-slate candidate pool still bound to V13.3", candidate_ok),
        ("Calibration save contract still bound to history.py", history_ok),
        ("All finalist Monte Carlo payloads valid + converged", sims_ok),
        ("1+ Hit results remain descending probability order", rank_ok),
        ("CONFIRMED / PROJECTED lineup labeling intact", lineup_ok),
        ("Top-5 card rendering did not mutate model results", mutation_ok),
        ("Steps 1–11 present on every visible Top-5 card", layers_ok),
    ]
    all_ok = all(ok for _, ok in checks)

    sim_total = int(sum(_num(((r or {}).get("sim") or {}).get("simulations"), 0) or 0 for r in results))
    confirmed = sum(1 for r in top5 if r.get("lineup_confirmed"))
    slate = "—"
    try:
        slate = str(active.schedule.current_selected_date())
    except Exception:
        pass

    state = "PRODUCTION FROZEN" if all_ok else "AUDIT CHECK"
    state_cls = "pass" if all_ok else "check"
    st.markdown(
        '<div class="hit1315-audit">'
        '<div class="hit1315-kicker">STEP 12 • FINAL PRODUCTION AUDIT + FREEZE</div>'
        '<div class="hit1315-title">🏁 MLB 1+ Hit V13 Production Verification</div>'
        '<div class="hit1315-grid">'
        f'<div class="hit1315-stat"><span>Audit state</span><b class="{state_cls}">{escape(state)}</b></div>'
        f'<div class="hit1315-stat"><span>Top-5 cards audited</span><b>{cards_audited}/5</b></div>'
        f'<div class="hit1315-stat"><span>Layer checks</span><b>{passed_layer_checks}/{expected_layer_checks}</b></div>'
        f'<div class="hit1315-stat"><span>Finalist simulations</span><b>{sim_total:,}</b></div>'
        f'<div class="hit1315-stat"><span>Slate</span><b>{escape(slate)}</b></div>'
        f'<div class="hit1315-stat"><span>Top-5 confirmed</span><b>{confirmed}/5</b></div>'
        f'<div class="hit1315-stat"><span>Model</span><b>V13 FROZEN</b></div>'
        f'<div class="hit1315-stat"><span>UI</span><b>V13.15 FINAL</b></div>'
        '</div><div style="margin-top:12px">'
        + ''.join(_status_html(label, ok) for label, ok in checks)
        + '</div>'
        '<div class="hit1315-note">Step 12 performs no new simulation, no network/model feature write, no reranking and no calibration write. It audits the already-produced V13 result contract and the eleven verified presentation layers. A CHECK state never repairs or fabricates a result automatically.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    if all_ok:
        st.success(
            "✅ STEP 12 PASSED • MLB 1+ Hit V13 / UI V13.15 is production-frozen. "
            "Steps 1–11 are intact, the model/ranking/calibration contracts remain native, "
            "and the presentation layer did not mutate the modeled Top-5 payload."
        )
    else:
        st.warning("⚠️ STEP 12 CHECK • One or more production audit contracts did not pass. No output was changed or forced.")



def render_hit_hub(games_df, section_header, status_info, team_logo, h):
    # Clear only the ephemeral Step-12 card audit; never touch model/scanner state.
    st.session_state["hit1315_card_audit"] = {}
    st.caption(
        "🏁 Hit UI V13.15 FINAL • Step 12 production audit + freeze ACTIVE • "
        "audit only • Hit Model V13 unchanged"
    )
    out = prior.render_hit_hub(games_df, section_header, status_info, team_logo, h)
    _render_final_audit()
    return out
