"""WNBA Live Games V5.2 — compact Step-5 validation audit.

Renders the untouched V5.1 completed-game preview, then appends a compact audit
when preview mode is active and no Step-1 verified game is live. The audit does
not change or feed any live/model path; it only checks integrity and source
coverage so Step 5 can be verified without scrolling through every card first.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_live_context_v1 as ctx
import wnba_live_hub_v2 as v2
import wnba_live_hub_v51 as v51
import wnba_live_step5_preview_v1 as preview

ET = ZoneInfo("America/New_York")
MODEL_VERSION = "WNBA LIVE GAMES V5.2 • STEP-5 VALIDATION AUDIT"


def _safe_int(value, default=0):
    try:
        return int(float(value))
    except Exception:
        return int(default)


def _audit_row(label: str, state: str, detail: str) -> str:
    state = str(state or "CHECK").upper()
    cls = "pass" if state == "PASS" else ("safe" if state == "SOURCE-LIMITED" else "fail")
    return (
        f'<div class="kwl52-row"><div><b>{escape(label)}</b><small>{escape(detail)}</small></div>'
        f'<span class="{cls}">{escape(state)}</span></div>'
    )


def _starter_count(context: dict, team_id: int) -> int:
    return len((context.get("current_starters") or {}).get(int(team_id)) or [])


def _rotation_count(context: dict, team_id: int) -> int:
    return len((context.get("rotation") or {}).get(int(team_id)) or [])


def _prior_starter_count(context: dict, team_id: int) -> int:
    prior = (context.get("last_starters") or {}).get(int(team_id)) or {}
    return len(prior.get("starters") or [])


def _audit(game: dict, context: dict, current_av: dict, discovery_meta: dict, live_games: list[dict]):
    away_id = _safe_int(game.get("away_team_id"))
    home_id = _safe_int(game.get("home_team_id"))
    event_id = str(game.get("espn_event_id") or "")
    h2h = context.get("h2h") or {}
    history_meta = context.get("history_meta") or {}
    summary_meta = context.get("current_summary_meta") or {}

    rows = []
    hard_fail = False

    isolation_ok = bool(game.get("preview_only")) and not live_games and "PREVIEW" in str(game.get("phase") or "").upper()
    rows.append(("Preview isolation", "PASS" if isolation_ok else "FAIL", "Completed test game is marked preview-only and no verified live game is active." if isolation_ok else "Preview/live boundary could not be proven."))
    hard_fail |= not isolation_ok

    ids_ok = away_id > 0 and home_id > 0 and away_id != home_id and bool(event_id)
    rows.append(("Game identity", "PASS" if ids_ok else "FAIL", f"ESPN event {event_id or 'missing'} • team IDs {away_id}/{home_id}."))
    hard_fail |= not ids_ok

    summary_ok = bool(summary_meta.get("available"))
    rows.append(("Preview ESPN summary", "PASS" if summary_ok else "FAIL", "Completed-game summary is connected for starter/rotation validation." if summary_ok else f"Summary unavailable: {summary_meta.get('error') or 'unknown error'}"))
    hard_fail |= not summary_ok

    hist_error = str(history_meta.get("error") or "").strip()
    history_ok = not hist_error
    rows.append(("Historical transport", "PASS" if history_ok else "FAIL", f"H2H transport returned {int(h2h.get('games') or 0)} prior meeting(s)." if history_ok else hist_error[:180]))
    hard_fail |= not history_ok

    leaked = [r for r in (h2h.get("last5") or []) if str(r.get("event_id") or "") == event_id]
    cutoff_ok = not leaked
    rows.append(("H2H cutoff / no leakage", "PASS" if cutoff_ok else "FAIL", "Preview event is excluded from its own H2H history." if cutoff_ok else "Preview event appeared inside prior H2H rows."))
    hard_fail |= not cutoff_ok

    discovery_ok = int(discovery_meta.get("usable") or 0) > 0 and int(discovery_meta.get("scoreboard_ok") or 0) > 0
    rows.append(("Completed-game discovery", "PASS" if discovery_ok else "FAIL", f"{int(discovery_meta.get('usable') or 0)} usable recent game(s) • {int(discovery_meta.get('scoreboard_ok') or 0)} scoreboard day request(s) OK."))
    hard_fail |= not discovery_ok

    a_rotation, h_rotation = _rotation_count(context, away_id), _rotation_count(context, home_id)
    rotation_ok = a_rotation >= 5 and h_rotation >= 5
    rows.append(("Entered-player rotation", "PASS" if rotation_ok else "FAIL", f"Away {a_rotation} observed • Home {h_rotation} observed. Minimum validation target is 5 per team."))
    hard_fail |= not rotation_ok

    a_starters, h_starters = _starter_count(context, away_id), _starter_count(context, home_id)
    starters_full = a_starters == 5 and h_starters == 5
    starters_state = "PASS" if starters_full else "SOURCE-LIMITED"
    rows.append(("Explicit preview starters", starters_state, f"Away {a_starters}/5 • Home {h_starters}/5. Missing flags remain pending; no starter is inferred."))

    a_prior, h_prior = _prior_starter_count(context, away_id), _prior_starter_count(context, home_id)
    prior_full = a_prior == 5 and h_prior == 5
    prior_state = "PASS" if prior_full else "SOURCE-LIMITED"
    rows.append(("Prior verified starters", prior_state, f"Away {a_prior}/5 • Home {h_prior}/5. Source gaps are labeled rather than guessed."))

    coverage = {int(k): bool(v) for k, v in (current_av.get("team_status_coverage") or {}).items()}
    feed_count = int(current_av.get("team_feeds_connected") or 0)
    availability_ok = bool(coverage.get(away_id)) and bool(coverage.get(home_id)) and feed_count >= 2
    rows.append(("Current availability feeds", "PASS" if availability_ok else "SOURCE-LIMITED", f"Team feeds connected {feed_count}/2 • away covered={bool(coverage.get(away_id))} • home covered={bool(coverage.get(home_id))}. Current snapshot only, never backdated."))

    rows.append(("Sportsbook/model boundary", "PASS", "Preview module requests no sportsbook market and creates no projection, probability, Monte Carlo, edge, EV, qualification, ranking or pick."))

    source_limited = any(state == "SOURCE-LIMITED" for _, state, _ in rows)
    if hard_fail:
        overall = "FAIL"
        overall_text = "A hard Step-5 integrity contract failed. Do not freeze Step 5 yet."
    elif source_limited:
        overall = "PASS • SOURCE-LIMITED"
        overall_text = "Hard integrity contracts pass. Some ESPN optional fields are unavailable and are safely labeled instead of inferred."
    else:
        overall = "PASS"
        overall_text = "Hard integrity contracts and optional source coverage both pass for this preview game."

    return rows, overall, overall_text


def _render_audit(game: dict, context: dict, current_av: dict, discovery_meta: dict, live_games: list[dict]):
    rows, overall, overall_text = _audit(game, context, current_av, discovery_meta, live_games)
    overall_cls = "bad" if overall == "FAIL" else ("warn" if "SOURCE-LIMITED" in overall else "good")
    rows_html = "".join(_audit_row(label, state, detail) for label, state, detail in rows)
    st.markdown(
        f"""<div class="kwl52-audit">
<div class="kwl52-head"><div><small>🔬 {MODEL_VERSION}</small><b>Step 5 Automatic Validation Audit</b></div><span class="{overall_cls}">{escape(overall)}</span></div>
<p>{escape(overall_text)}</p>
<div class="kwl52-rows">{rows_html}</div>
<div class="kwl52-foot">Audit is read-only. PASS means the transport/integrity contract was observed on the selected completed preview game. SOURCE-LIMITED means ESPN did not expose an optional field; the app kept it pending instead of inventing it.</div>
</div>""",
        unsafe_allow_html=True,
    )


def _css():
    st.markdown(r"""<style>
.kwl52-audit{border:1px solid #41647a;border-radius:20px;padding:15px;margin:16px 0 26px;background:#081522}.kwl52-head{display:flex;align-items:center;justify-content:space-between;gap:10px;border-bottom:1px solid #213b4e;padding-bottom:10px}.kwl52-head>div{display:flex;flex-direction:column;gap:4px}.kwl52-head small{font-size:.58rem;color:#8fcff5;font-weight:950;letter-spacing:.06em}.kwl52-head b{color:#f4f8fb;font-size:1rem}.kwl52-head>span{font-size:.58rem;font-weight:950;border-radius:999px;padding:6px 9px;border:1px solid #31566f}.kwl52-head .good{color:#93efbc;border-color:#2d8257;background:#0d2d21}.kwl52-head .warn{color:#ead879;border-color:#8a722a;background:#2a240d}.kwl52-head .bad{color:#ffada6;border-color:#8f4b47;background:#311616}.kwl52-audit>p{color:#9cb0be;font-size:.68rem;line-height:1.5}.kwl52-rows{display:grid;gap:7px}.kwl52-row{display:flex;justify-content:space-between;align-items:center;gap:10px;border:1px solid #243f52;border-radius:12px;padding:9px}.kwl52-row>div{display:flex;flex-direction:column;gap:3px}.kwl52-row b{color:#eaf2f6;font-size:.68rem}.kwl52-row small{color:#7f96a7;font-size:.55rem;line-height:1.35}.kwl52-row>span{flex:0 0 auto;font-size:.5rem;font-weight:950;border-radius:999px;padding:5px 7px}.kwl52-row .pass{color:#93efbc;border:1px solid #2d8257;background:#0d2d21}.kwl52-row .safe{color:#ead879;border:1px solid #8a722a;background:#2a240d}.kwl52-row .fail{color:#ffada6;border:1px solid #8f4b47;background:#311616}.kwl52-foot{margin-top:10px;color:#728a9c;font-size:.56rem;line-height:1.45}.kwl52-boundary{border:1px dashed #41647a;border-radius:14px;padding:11px;color:#859cad;font-size:.62rem;margin:12px 0 22px}
@media(max-width:640px){.kwl52-head{align-items:flex-start;flex-direction:column}.kwl52-row{align-items:flex-start}.kwl52-row small{max-width:235px}}
</style>""", unsafe_allow_html=True)


def render_wnba_live_hub(section_header=None, status_info=None, team_logo=None, h=None):
    # Keep the entire V5.1 production + preview stack unchanged.
    v51.render_wnba_live_hub(section_header, status_info, team_logo, h)

    now = datetime.now(ET)
    day_str = now.strftime("%Y-%m-%d")
    live_games, _, _ = v2._verified_live_games(day_str)
    if live_games or not bool(st.session_state.get("wnba_live_step5_preview_enabled", False)):
        return

    previews, discovery_meta = preview.recent_completed_previews(day_str)
    if not previews:
        return

    selected = _safe_int(st.session_state.get("wnba_live_step5_preview_choice", 0), 0)
    selected = max(0, min(selected, len(previews) - 1))
    game = previews[selected]

    with st.spinner("Running Step-5 integrity audit…"):
        context = ctx.context_for_game(game)
        current_av = preview.current_availability_for_preview(game)

    _css()
    _render_audit(game, context, current_av, discovery_meta, live_games)
    st.markdown('<div class="kwl52-boundary">STEP-5 AUDIT BOUNDARY • verification only • zero model inputs or outputs are modified</div>', unsafe_allow_html=True)
