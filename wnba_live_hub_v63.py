"""WNBA Live Games V6.3 — replay-fidelity diagnostic.

Renders V6.2 unchanged, then appends a validation-only batch audit that checks
whether ESPN play-by-play can reconstruct halftime and start-Q4 partial box
metrics without future leakage. No production model parameter is changed here.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import streamlit as st

import wnba_live_hub_v2 as v2
import wnba_live_hub_v62 as v62
import wnba_live_step5_preview_v1 as preview
import wnba_live_step6_pbp_v1 as pbp
import wnba_live_step6_replay_v1 as replay

ET = ZoneInfo("America/New_York")
MODEL_VERSION = "WNBA LIVE GAMES V6.3 • STEP-6 REPLAY FIDELITY AUDIT"
CHECKPOINTS = ("HALFTIME", "Q4_START")
AUDIT_GAMES = 8


def _metric(label: str, value: str, sub: str = "") -> str:
    extra = f"<small>{escape(str(sub))}</small>" if sub else ""
    return f'<div class="kwl63-m"><span>{escape(label)}</span><b>{escape(str(value))}</b>{extra}</div>'


def _cpmap(bundle: dict) -> dict:
    out = {}
    for state in bundle.get("checkpoints") or []:
        cid = str(state.get("replay_checkpoint_id") or "")
        if cid:
            out[cid] = state
    return out


def _run_batch(day_str: str) -> dict:
    games, discovery = preview.recent_completed_previews(day_str, limit=AUDIT_GAMES, lookback_days=30)
    rows = []
    errors = []
    for game in games:
        bundle = replay.replay_bundle(game)
        if bundle.get("error"):
            errors.append(f"{game.get('espn_event_id')}: {bundle.get('error')}")
            continue
        cpmap = _cpmap(bundle)
        for cid in CHECKPOINTS:
            state = cpmap.get(cid)
            if not state:
                errors.append(f"{game.get('espn_event_id')}: missing {cid}")
                continue
            rec = pbp.reconstruct(state)
            checks = pbp.audit(state, rec)
            rows.append({
                "event_id": str(game.get("espn_event_id") or ""),
                "away_team": str(game.get("away_team") or "Away"),
                "home_team": str(game.get("home_team") or "Home"),
                "date": str(game.get("game_date_et") or ""),
                "checkpoint": cid,
                "quality": str(rec.get("quality") or "CHECK"),
                "score_reconciled": bool(rec.get("score_reconciled")),
                "included_plays": int(rec.get("included_plays") or 0),
                "future_plays_excluded": int(rec.get("future_plays_excluded") or 0),
                "unmapped_stat_plays": int(rec.get("unmapped_stat_plays") or 0),
                "pace40": rec.get("pace40"),
                "away_fga": float((rec.get("away_stats") or {}).get("fga") or 0.0),
                "home_fga": float((rec.get("home_stats") or {}).get("fga") or 0.0),
                "hard_pass": all(bool(x.get("pass")) for x in checks),
                "checks": checks,
            })

    total = len(rows)
    hard = sum(1 for r in rows if r["hard_pass"])
    score_ok = sum(1 for r in rows if r["score_reconciled"])
    high = sum(1 for r in rows if r["quality"] == "HIGH")
    future_excluded = sum(int(r["future_plays_excluded"]) for r in rows)
    return {
        "games": len(games),
        "states": total,
        "hard_pass_states": hard,
        "score_reconciled_states": score_ok,
        "high_quality_states": high,
        "future_plays_excluded": future_excluded,
        "pass_rate": (hard / total) if total else 0.0,
        "rows": rows,
        "errors": errors,
        "discovery": discovery,
        "ready_for_calibration_v2": bool(total >= 12 and hard / max(1, total) >= 0.85),
    }


def _row_html(row: dict) -> str:
    good = bool(row.get("hard_pass"))
    pace = row.get("pace40")
    pace_text = f"{float(pace):.1f}" if pace is not None else "—"
    cp = "HALFTIME" if row.get("checkpoint") == "HALFTIME" else "START Q4"
    return f'''<div class="kwl63-row"><div><b>{escape(str(row.get('away_team')))} @ {escape(str(row.get('home_team')))}</b><small>{escape(str(row.get('date')))} • {escape(cp)}</small></div><div><strong>{'PASS' if good else 'CHECK'}</strong><small>PBP {int(row.get('included_plays') or 0)} • pace {escape(pace_text)} • FGA {int(row.get('away_fga') or 0)}/{int(row.get('home_fga') or 0)}</small></div></div>'''


def _css():
    st.markdown(r'''<style>
.kwl63-hero{border:1px dashed #6c7540;border-radius:22px;padding:18px;margin:30px 0 14px;background:linear-gradient(145deg,#121809,#071522)}.kwl63-eye{font-size:.7rem;font-weight:950;letter-spacing:.08em;color:#c8df82}.kwl63-hero h3{font-size:1.45rem;color:#f7fbff;margin:8px 0}.kwl63-hero p{color:#9fb0bb;line-height:1.58;margin:0}.kwl63-hero b{color:#fff}.kwl63-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}.kwl63-m{border:1px solid #2b4a5f;border-radius:14px;padding:10px;background:#07111d;min-height:76px;display:flex;flex-direction:column;justify-content:center}.kwl63-m span{font-size:.57rem;color:#839aaa;font-weight:900}.kwl63-m b{font-size:1rem;color:#f5f8fb;margin-top:5px}.kwl63-m small{font-size:.56rem;color:#899fac;margin-top:3px}.kwl63-panel{border:1px solid #344f62;border-radius:18px;padding:13px;margin:12px 0;background:#081522}.kwl63-row{display:grid;grid-template-columns:1.35fr .9fr;gap:10px;padding:10px 2px;border-bottom:1px solid #1d3342}.kwl63-row:last-child{border-bottom:0}.kwl63-row>div{display:flex;flex-direction:column}.kwl63-row b{color:#eef7fb;font-size:.72rem}.kwl63-row strong{color:#93efbc;font-size:.7rem}.kwl63-row small{color:#8399a8;font-size:.58rem;margin-top:3px}.kwl63-ok,.kwl63-hold{border-radius:16px;padding:13px;margin:12px 0;font-size:.7rem;line-height:1.5}.kwl63-ok{border:1px solid #2d8257;background:#0d2d21;color:#93efbc}.kwl63-hold{border:1px solid #8a722a;background:#2a240d;color:#ead879}
@media(max-width:640px){.kwl63-grid{grid-template-columns:1fr 1fr}.kwl63-row{grid-template-columns:1fr}}
</style>''', unsafe_allow_html=True)


def render_wnba_live_hub(section_header=None, status_info=None, team_logo=None, h=None):
    v62.render_wnba_live_hub(section_header, status_info, team_logo, h)

    now = datetime.now(ET)
    day_str = now.strftime("%Y-%m-%d")
    live_games, _, _ = v2._verified_live_games(day_str)
    if live_games:
        return

    _css()
    st.markdown(f'''<div class="kwl63-hero"><div class="kwl63-eye">🔬 {MODEL_VERSION}</div><h3>Step 6.3 • Replay Fidelity Before More Calibration</h3><p>The Step-6.2 candidate correctly failed promotion. Before changing model weights again, this audit checks the real structural limitation: our old replay used <b>score/clock only</b>, while a true live Step-6 state also has partial possession/efficiency information. We now reconstruct that historical partial state from ESPN play-by-play <b>only through each checkpoint</b>. Future plays and the final boxscore remain blocked.</p></div>''', unsafe_allow_html=True)

    key = "wnba_step63_pbp_audit"
    day_key = "wnba_step63_day"
    if st.session_state.get(day_key) != day_str:
        st.session_state.pop(key, None)
        st.session_state[day_key] = day_str

    c1, c2 = st.columns(2)
    with c1:
        run = st.button("🔬 Run checkpoint PBP fidelity audit", use_container_width=True, key="wnba_step63_run")
    with c2:
        clear = st.button("♻️ Clear PBP audit cache", use_container_width=True, key="wnba_step63_clear")
    if clear:
        pbp.clear_cache()
        st.session_state.pop(key, None)
        st.rerun()
    if run:
        with st.spinner("Reconstructing historical halftime and Q4-start states from checkpoint-only play-by-play…"):
            st.session_state[key] = _run_batch(day_str)
        st.rerun()

    result = st.session_state.get(key)
    if not result:
        st.info("Run this fidelity audit before we fit another Step-6 candidate. Production Step 6 remains unchanged.")
        return

    st.markdown(f'''<div class="kwl63-grid">
{_metric('GAMES TESTED', str(int(result.get('games') or 0)))}
{_metric('REPLAY STATES', str(int(result.get('states') or 0)), 'halftime + start Q4')}
{_metric('FULL HARD PASSES', str(int(result.get('hard_pass_states') or 0)))}
{_metric('PASS RATE', f"{float(result.get('pass_rate') or 0)*100:.1f}%")}
{_metric('SCORE RECONCILED', str(int(result.get('score_reconciled_states') or 0)))}
{_metric('HIGH PBP QUALITY', str(int(result.get('high_quality_states') or 0)))}
{_metric('FUTURE PLAYS EXCLUDED', f"{int(result.get('future_plays_excluded') or 0):,}")}
{_metric('FINAL BOXSCORE USED', 'NO')}
</div>''', unsafe_allow_html=True)

    ready = bool(result.get("ready_for_calibration_v2"))
    if ready:
        st.markdown('<div class="kwl63-ok"><b>FIDELITY GATE • PASS.</b> At least 85% of a 12+ state batch reconstructed cleanly. This transport is strong enough to become the input to the next calibration version.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="kwl63-hold"><b>FIDELITY GATE • HOLD.</b> Do not refit or promote Step 6 yet. The PBP parser/transport needs repair until the historical partial-game state reconciles reliably.</div>', unsafe_allow_html=True)

    st.markdown('<div class="kwl63-panel">' + ''.join(_row_html(r) for r in result.get("rows") or []) + '</div>', unsafe_allow_html=True)

    if result.get("errors"):
        with st.expander("PBP fidelity transport diagnostics"):
            for item in result.get("errors") or []:
                st.write("•", item)

    st.caption("Step 6.3 is validation-only. The rejected Step-6.2 candidate is not promoted, production Step 6 remains V1, and no sportsbook/model output is changed.")
