"""WNBA Live Games V6.1 — isolated Step-6 replay validation UI.

Production Steps 1-6 render unchanged first. When NO Step-1 verified game is
live, an opt-in completed-game replay panel appears below Step 6. The replay uses
exact quarter-boundary score states, blocks future full-game boxscore data, uses
no historical sportsbook line, and runs the unchanged Step-6 5M simulator.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_live_hub_v2 as v2
import wnba_live_hub_v6 as v6
import wnba_live_projection_v1 as model
import wnba_live_step5_preview_v1 as preview
import wnba_live_step6_replay_v1 as replay

ET = ZoneInfo("America/New_York")
MODEL_VERSION = "WNBA LIVE GAMES V6.1 • STEP-6 REPLAY VALIDATION"


def _pct(value, digits=1):
    try:
        return f"{float(value) * 100:.{digits}f}%"
    except Exception:
        return "—"


def _num(value, digits=1, signed=False):
    try:
        x = float(value)
        return f"{x:+.{digits}f}" if signed else f"{x:.{digits}f}"
    except Exception:
        return "—"


def _odds(value):
    try:
        x = int(value)
        return f"+{x}" if x > 0 else str(x)
    except Exception:
        return "—"


def _date(value):
    try:
        return pd.to_datetime(value, utc=True).tz_convert(ET).strftime("%b %-d, %Y • %-I:%M %p ET")
    except Exception:
        return str(value or "—")


def _game_label(game: dict) -> str:
    return (
        f"{_date(game.get('captured_at')).split(' • ')[0]} • "
        f"{game.get('away_team','Away')} {game.get('away_score','—')}–"
        f"{game.get('home_score','—')} {game.get('home_team','Home')}"
    )


def _metric(label: str, value: str, sub: str = "") -> str:
    extra = f"<small>{escape(str(sub))}</small>" if sub else ""
    return f'<div class="kwl61-m"><span>{escape(label)}</span><b>{escape(str(value))}</b>{extra}</div>'


def _audit_html(checks: list[dict]) -> str:
    rows = []
    for item in checks:
        ok = bool(item.get("pass"))
        rows.append(
            f'<div class="kwl61-auditrow"><div><b>{escape(str(item.get("name") or "Check"))}</b>'
            f'<small>{escape(str(item.get("detail") or ""))}</small></div>'
            f'<span class="{"good" if ok else "bad"}">{"PASS" if ok else "FAIL"}</span></div>'
        )
    overall = all(bool(x.get("pass")) for x in checks)
    return f'''<div class="kwl61-audit"><div class="kwl61-audithead"><b>🔬 REPLAY ANTI-LEAKAGE AUDIT</b><span class="{'good' if overall else 'bad'}">{'PASS' if overall else 'FAIL'}</span></div>{''.join(rows)}</div>'''


def _projection_html(state: dict, projection: dict, audit: list[dict]) -> str:
    away = str(state.get("away_team") or "Away")
    home = str(state.get("home_team") or "Home")
    score = f"{state.get('away_score','—')}–{state.get('home_score','—')}"
    label = str(state.get("replay_checkpoint_label") or "Replay checkpoint")
    segments = []
    for row in projection.get("segments") or []:
        p = int(row.get("period") or 1)
        plabel = f"Q{p}" if p <= 4 else ("OT" if p == 5 else f"{p-4}OT")
        segments.append(
            f"{plabel} {float(row.get('minutes') or 0):.1f}m: "
            f"{away} {float(row.get('away_points') or 0):.1f} / "
            f"{home} {float(row.get('home_points') or 0):.1f}"
        )
    audit_ok = all(bool(x.get("pass")) for x in audit)
    return f'''<div class="kwl61-card">
<div class="kwl61-head"><div><small>🧪 EXACT HISTORICAL CHECKPOINT • NOT LIVE</small><b>{escape(away)} @ {escape(home)}</b></div><div><strong>{escape(score)}</strong><small>{escape(label)}</small></div></div>
<div class="kwl61-badges"><span class="{'good' if projection.get('ready') else 'bad'}">MODEL READY • {'YES' if projection.get('ready') else 'NO'}</span><span class="warn">DATA MODE • SCORE/CLOCK ONLY</span><span class="{'good' if audit_ok else 'bad'}">ANTI-LEAKAGE • {'PASS' if audit_ok else 'FAIL'}</span><span>HISTORICAL MARKET • NONE</span></div>
<div class="kwl61-holdout"><b>🔒 ACTUAL FINAL HELD OUT.</b> The completed game's final score exists only in the separate validation truth object. It is not passed into the replay projection or 5M simulation.</div>
<div class="kwl61-title">REPLAY PROJECTION • BEFORE HELD-OUT TRUTH IS REVEALED</div>
<div class="kwl61-grid">
{_metric('PROJECTED REMAINING • ' + away, _num(projection.get('projected_remaining_away')) + ' pts')}
{_metric('PROJECTED REMAINING • ' + home, _num(projection.get('projected_remaining_home')) + ' pts')}
{_metric('BASE PROJECTED SCORE', f"{_num(projection.get('projected_base_final_away'))}–{_num(projection.get('projected_base_final_home'))}")}
{_metric('BASE PROJECTED TOTAL', _num(projection.get('projected_base_total')))}
{_metric('BASE HOME MARGIN', _num(projection.get('projected_base_home_margin'),1,True) + ' pts')}
{_metric('UNCERTAINTY', _num(projection.get('uncertainty_multiplier'),3) + '×')}
{_metric('HISTORY SAMPLE', f"A {int(projection.get('away_history_games') or 0)} / H {int(projection.get('home_history_games') or 0)}", f"{projection.get('away_history_reliability','THIN')} / {projection.get('home_history_reliability','THIN')}")}
{_metric('RESIDUAL CORRELATION', _num(projection.get('residual_correlation'),3))}
</div>
<div class="kwl61-segments"><small>REMAINING-TIME CONSTRUCTION</small><p>{escape(' • '.join(segments) if segments else 'No competitive time remaining.')}</p></div>
<div class="kwl61-source"><b>REPLAY SOURCE LIMITATION.</b> Historical quarter-boundary score is exact. Historical partial-game possession/eFG/turnover/rebound box data and historical injury state are not verified by this transport, so replay intentionally does not use them. This makes the replay more conservative than a fully connected live Step-6 state.</div>
{_audit_html(audit)}
</div>'''


def _result_html(state: dict, result: dict, evaluation: dict) -> str:
    away = str(state.get("away_team") or "Away")
    home = str(state.get("home_team") or "Home")
    actual = f"{evaluation.get('actual_away','—')}–{evaluation.get('actual_home','—')}"
    predicted = f"{_num(result.get('expected_final_away'))}–{_num(result.get('expected_final_home'))}"
    correct = bool(evaluation.get("winner_call_correct"))
    conv = str(result.get("convergence") or "CHECK")
    return f'''<div class="kwl61-result">
<div class="kwl61-resulthead"><div><small>5,000,000-DRAW HOLDOUT REPLAY</small><b>{escape(away)} @ {escape(home)}</b></div><span class="{'good' if conv == 'PASS' else 'warn'}">CONVERGENCE • {escape(conv)}</span></div>
<div class="kwl61-biggrid"><div><small>{escape(away)} WIN</small><strong>{_pct(result.get('away_win_probability'))}</strong><span>FAIR {_odds(result.get('away_fair_odds'))}</span></div><div><small>{escape(home)} WIN</small><strong>{_pct(result.get('home_win_probability'))}</strong><span>FAIR {_odds(result.get('home_fair_odds'))}</span></div></div>
<div class="kwl61-truth"><div><small>MC EXPECTED FINAL</small><b>{escape(predicted)}</b></div><div><small>HELD-OUT ACTUAL FINAL</small><b>{escape(actual)}</b></div><div><small>WINNER CALL</small><b class="{'pos' if correct else 'neg'}">{'CORRECT' if correct else 'MISS'}</b></div></div>
<div class="kwl61-grid">
{_metric('ACTUAL-WINNER PROBABILITY', _pct(evaluation.get('actual_winner_probability')))}
{_metric('MEAN TEAM ABS ERROR', _num(evaluation.get('mean_team_abs_error')) + ' pts')}
{_metric('TOTAL ERROR', _num(evaluation.get('total_error'),1,True) + ' pts')}
{_metric('MARGIN ERROR', _num(evaluation.get('margin_error'),1,True) + ' pts')}
{_metric('BRIER SCORE', _num(evaluation.get('brier_score'),4), 'single-game diagnostic only')}
{_metric('OVERTIME PROBABILITY', _pct(result.get('extra_period_probability')))}
{_metric('SIMULATIONS', f"{int(result.get('simulations') or 0):,}")}
{_metric('MAX BATCH RANGE', _num(result.get('max_batch_range_pp'),2) + ' pp', f"PASS ≤ {_num(result.get('convergence_threshold_pp'),2)} pp")}
{_metric('HOME ML MC SE', _pct(result.get('home_ml_mc_se'),2))}
{_metric('RANDOM SEED', str(result.get('seed') or '—'))}
{_metric('RUNTIME', _num(result.get('runtime_seconds'),2) + ' s')}
{_metric('HISTORICAL MARKET', 'NOT USED')}
</div>
<div class="kwl61-contract"><b>VALIDATION ONLY.</b> One replay cannot establish calibration. This panel checks state construction, future-data isolation, simulation mechanics, OT resolution and convergence. It does not create a recommendation or alter the production Step-6 model.</div>
</div>'''


def _css():
    st.markdown(r'''<style>
.kwl61-hero{border:1px dashed #81702f;border-radius:22px;padding:20px;margin:28px 0 14px;background:linear-gradient(145deg,#161506,#091722)}.kwl61-eyebrow{font-size:.7rem;font-weight:950;letter-spacing:.08em;color:#ead879}.kwl61-hero h3{font-size:1.48rem;margin:8px 0;color:#f7fbff}.kwl61-hero p{color:#9fb0bb;line-height:1.58;margin:0}.kwl61-hero b{color:#fff}
.kwl61-card,.kwl61-result{border:1px solid #6d6131;border-radius:22px;padding:16px;margin:14px 0;background:#081522}.kwl61-head,.kwl61-resulthead{display:flex;justify-content:space-between;align-items:end;gap:12px;border-bottom:1px solid #3a3926;padding-bottom:12px}.kwl61-head>div,.kwl61-resulthead>div{display:flex;flex-direction:column;gap:4px}.kwl61-head>div:last-child{text-align:right}.kwl61-head small,.kwl61-resulthead small{font-size:.6rem;color:#99956f;font-weight:900;letter-spacing:.06em}.kwl61-head b,.kwl61-resulthead b{color:#f6f9fb;font-size:1rem}.kwl61-head strong{color:#fff;font-size:1.35rem}.kwl61-badges{display:flex;flex-wrap:wrap;gap:7px;margin:12px 0}.kwl61-badges span,.kwl61-resulthead>span,.kwl61-audithead>span,.kwl61-auditrow>span{border:1px solid #4c5260;border-radius:999px;padding:6px 8px;font-size:.57rem;color:#aab3ba;font-weight:900}.kwl61-badges .good,.kwl61-resulthead .good,.kwl61-audit .good{border-color:#2d8257;color:#93efbc;background:#0d2d21}.kwl61-badges .warn,.kwl61-resulthead .warn{border-color:#8a722a;color:#ead879;background:#2a240d}.kwl61-badges .bad,.kwl61-audit .bad{border-color:#884b4b;color:#ffb3b3;background:#321616}
.kwl61-holdout,.kwl61-source,.kwl61-contract{border:1px solid #705f1f;background:#2b260c;color:#e9d875;border-radius:14px;padding:12px;margin:12px 0;font-size:.66rem;line-height:1.52}.kwl61-source{border-color:#3b5669;background:#0b1b27;color:#a9becb}.kwl61-contract{border-color:#38566a;background:#0a1823;color:#9eb2bf}.kwl61-title{font-size:.69rem;color:#a8ddff;letter-spacing:.07em;font-weight:950;margin:15px 0 8px}.kwl61-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}.kwl61-m{border:1px solid #29495d;border-radius:14px;padding:10px;background:#07111d;min-height:76px;display:flex;flex-direction:column;justify-content:center}.kwl61-m span{font-size:.58rem;color:#7f98aa;font-weight:900}.kwl61-m b{font-size:1rem;color:#f6f9fb;margin-top:5px}.kwl61-m small{color:#899fac;font-size:.56rem;margin-top:3px}.kwl61-segments{border:1px solid #29495d;border-radius:14px;padding:11px;margin-top:10px}.kwl61-segments small{color:#8fcff5;font-size:.59rem;font-weight:950}.kwl61-segments p{color:#d5e1e8;font-size:.69rem;line-height:1.5;margin:5px 0 0}
.kwl61-audit{border:1px solid #40576a;border-radius:16px;padding:12px;margin-top:12px}.kwl61-audithead,.kwl61-auditrow{display:flex;justify-content:space-between;gap:10px;align-items:center}.kwl61-audithead{padding-bottom:9px;border-bottom:1px solid #263e50}.kwl61-audithead b{font-size:.72rem;color:#dce8ef}.kwl61-auditrow{padding:9px 0;border-bottom:1px solid #1c3140}.kwl61-auditrow:last-child{border-bottom:0}.kwl61-auditrow>div{display:flex;flex-direction:column;gap:2px}.kwl61-auditrow b{color:#e8eef2;font-size:.67rem}.kwl61-auditrow small{color:#879cab;font-size:.57rem;line-height:1.35}
.kwl61-biggrid{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin:12px 0}.kwl61-biggrid>div{border:1px solid #36566c;border-radius:16px;padding:14px;background:#07111d;display:flex;flex-direction:column}.kwl61-biggrid small{color:#8fa4b4;font-size:.61rem;font-weight:900}.kwl61-biggrid strong{font-size:2rem;color:#fff;margin-top:5px}.kwl61-biggrid span{font-size:.65rem;color:#9ab1bf}.kwl61-truth{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin:10px 0 12px}.kwl61-truth>div{border:1px solid #5f5730;border-radius:14px;padding:10px;background:#131508;display:flex;flex-direction:column}.kwl61-truth small{color:#a69d70;font-size:.56rem;font-weight:900}.kwl61-truth b{color:#fff;margin-top:4px}.kwl61-truth .pos{color:#93efbc}.kwl61-truth .neg{color:#ffb3b3}
@media(max-width:640px){.kwl61-hero,.kwl61-card,.kwl61-result{padding:14px}.kwl61-grid{grid-template-columns:1fr 1fr}.kwl61-truth{grid-template-columns:1fr}.kwl61-head{align-items:center}}
</style>''', unsafe_allow_html=True)


def render_wnba_live_hub(section_header=None, status_info=None, team_logo=None, h=None):
    # Production Steps 1-6 stay exactly on their existing V6 path.
    v6.render_wnba_live_hub(section_header, status_info, team_logo, h)

    now = datetime.now(ET)
    day_str = now.strftime("%Y-%m-%d")
    live_games, _diag, _meta = v2._verified_live_games(day_str)
    if live_games:
        return

    _css()
    st.markdown(f'''<div class="kwl61-hero"><div class="kwl61-eyebrow">🧪 {MODEL_VERSION}</div><h3>Step 6 Replay Validation Mode</h3><p>With no verified WNBA game live, this optional harness can replay a <b>recent completed game from an exact quarter boundary</b>. Future quarter scoring, the completed full-game box score, current injury data and sportsbook markets are blocked from the projection. The actual final is held out until after the 5M run.</p></div>''', unsafe_allow_html=True)

    enabled = bool(st.session_state.get("wnba_live_step6_replay_enabled", False))
    if not enabled:
        if st.button("🧪 Load Step 6 replay validation", use_container_width=True, key="wnba_live_v61_load"):
            st.session_state["wnba_live_step6_replay_enabled"] = True
            st.rerun()
        st.caption("Replay is OFF by default and automatically disappears whenever a Step-1 verified live game exists.")
        return

    a, b = st.columns(2)
    with a:
        if st.button("🔄 Refresh replay data", use_container_width=True, key="wnba_live_v61_refresh"):
            replay.clear_cache()
            st.session_state.pop("wnba_live_v61_results", None)
            st.rerun()
    with b:
        if st.button("✖ Exit replay mode", use_container_width=True, key="wnba_live_v61_exit"):
            st.session_state["wnba_live_step6_replay_enabled"] = False
            st.rerun()

    games, discovery = preview.recent_completed_previews(day_str)
    if not games:
        st.warning("No recent completed regular-season game is available for replay. " + str(discovery.get("error") or ""))
        return

    game_idx = st.selectbox(
        "Completed game used for Step-6 replay",
        options=list(range(len(games))),
        format_func=lambda i: _game_label(games[int(i)]),
        key="wnba_live_v61_game",
    )
    base_game = games[int(game_idx)]
    bundle = replay.replay_bundle(base_game)
    if bundle.get("error") or not bundle.get("checkpoints"):
        st.warning("Replay state construction failed: " + str(bundle.get("error") or "no checkpoint"))
        return

    checkpoints = bundle["checkpoints"]
    checkpoint_idx = st.selectbox(
        "Exact replay checkpoint",
        options=list(range(len(checkpoints))),
        format_func=lambda i: str(checkpoints[int(i)].get("replay_checkpoint_label") or "Checkpoint"),
        key="wnba_live_v61_checkpoint",
    )
    state = checkpoints[int(checkpoint_idx)]

    with st.spinner("Building future-safe replay projection…"):
        projection = replay.projection_for_replay(state)
        audit = replay.replay_audit(state, projection, bundle.get("truth") or {})

    st.markdown(_projection_html(state, projection, audit), unsafe_allow_html=True)

    audit_ok = all(bool(x.get("pass")) for x in audit)
    can_run = bool(projection.get("ready")) and audit_ok
    result_key = model.state_key(state) + "||REPLAY_NO_MARKET"
    store = st.session_state.setdefault("wnba_live_v61_results", {})

    if st.button(
        "🎲 Run 5,000,000 replay simulations",
        use_container_width=True,
        disabled=not can_run,
        key=f"wnba_live_v61_run_{state.get('espn_event_id')}_{state.get('replay_checkpoint_id')}",
    ):
        with st.spinner("Running 5,000,000 future-safe replay simulations…"):
            store[result_key] = replay.run_replay_5m(state, projection)
        st.rerun()

    result = store.get(result_key)
    if result:
        evaluation = replay.evaluate_holdout(result, bundle.get("truth") or {})
        st.markdown(_result_html(state, result, evaluation), unsafe_allow_html=True)
    else:
        st.info("The held-out actual final remains hidden here until the 5M replay run completes.")

    st.markdown('<div class="kwl61-contract"><b>REPLAY BOUNDARY.</b> This harness never creates a live state, never attaches a sportsbook market, never feeds held-out final truth into the model and never changes production Step-6 probabilities. It is validation only.</div>', unsafe_allow_html=True)


__all__ = ["MODEL_VERSION", "render_wnba_live_hub"]
