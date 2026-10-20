"""NFL Daily Picks V4 — Premium Smart Live Intelligence Terminal.

Presentation/live-market overlay only.  The frozen V3 candidate/model/parlay
contracts remain the source of model truth; sportsbook data never changes them.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Any, Iterable, Mapping

try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:  # pragma: no cover
    st_autorefresh = None

import nfl_daily_picks_command_center_v3 as v3
from nfl_daily_picks_live_v4 import (
    fetch_live_market_observations,
    live_market_firewall,
    matchup_teams,
    nfl_team_logo_url,
    session_line_history,
    session_line_movement,
    smart_refresh_seconds,
    update_session_line_history,
)
from nfl_daily_picks_parlay_v3 import estimate_parlay_probability
from nfl_daily_picks_ranking_v1 import normalized_pick_score

MODEL_VERSION = "NFL DAILY PICKS V4 • PREMIUM SMART LIVE INTELLIGENCE TERMINAL"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

_CSS = r"""
<style>
:root{--ice:#7dd3fc;--ice2:#38bdf8;--ink:#050b12;--panel:#081521;--panel2:#0b1b29;--line:#25465d;--muted:#91a7b8;--good:#5ee5a8;--warn:#e7c96b;--bad:#ff7b7b}
.nit-hero{border:1px solid #34617b;border-radius:24px;padding:22px;background:radial-gradient(circle at 88% 2%,rgba(56,189,248,.22),transparent 34%),linear-gradient(145deg,#071724,#050d15);box-shadow:0 20px 55px rgba(0,0,0,.28)}
.nit-kicker{font-size:.78rem;font-weight:950;letter-spacing:.14em;color:var(--ice)}.nit-title{font-size:2rem;line-height:1.08;font-weight:950;color:#f8fbff;margin-top:6px}.nit-sub{font-size:.82rem;line-height:1.55;color:#a7bac7;margin-top:8px;max-width:900px}
.nit-feed{display:flex;align-items:center;justify-content:space-between;gap:10px;border:1px solid #29536b;border-radius:14px;background:#07131e;padding:11px 13px;margin:12px 0}.nit-feed b{font-size:.78rem;color:#d9f4ff;letter-spacing:.05em}.nit-feed span{font-size:.72rem;color:#91a7b8}.nit-dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#5ee5a8;box-shadow:0 0 14px rgba(94,229,168,.75);margin-right:7px}
.nit-summary{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:11px 0}.nit-stat{border:1px solid #29485d;border-radius:14px;background:#081622;padding:12px}.nit-stat b{display:block;color:#f7fbff;font-size:1.12rem}.nit-stat span{font-size:.69rem;color:#8399aa;font-weight:850;text-transform:uppercase;letter-spacing:.06em}
.nit-section{margin:18px 0 8px;font-size:.74rem;font-weight:950;letter-spacing:.12em;color:var(--ice)}.nit-featured{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.nit-feature{border:1px solid #315970;border-radius:16px;background:linear-gradient(155deg,#0b1e2d,#07131d);padding:13px}.nit-feature em{font-style:normal;font-size:.68rem;color:var(--warn);font-weight:950;letter-spacing:.06em}.nit-feature strong{display:block;color:#fbfdff;font-size:.95rem;margin:6px 0}.nit-feature span{display:block;color:#91a7b8;font-size:.74rem;line-height:1.45}
.nit-game{border:1px solid #2b526a;border-radius:20px;background:linear-gradient(160deg,#091a27,#07111a);padding:15px;margin:11px 0;box-shadow:0 10px 24px rgba(0,0,0,.14)}.nit-head{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:12px;padding-bottom:12px;border-bottom:1px solid #19354a}.nit-team{display:flex;align-items:center;gap:10px}.nit-team.right{justify-content:flex-end;text-align:right}.team-logo{width:48px;height:48px;object-fit:contain;filter:drop-shadow(0 6px 10px rgba(0,0,0,.3))}.nit-team b{color:#f8fbff;font-size:1.05rem}.nit-center{text-align:center}.nit-badge{display:inline-block;border:1px solid #3a6b86;border-radius:999px;padding:4px 8px;color:#bfeeff;font-size:.68rem;font-weight:950;letter-spacing:.07em}.nit-badge.live{border-color:#a64d58;color:#ffb2b8;background:#311018}.nit-kick{font-size:.68rem;color:#859cac;margin-top:5px}
.nit-live-alert{margin:10px 0;border:1px solid #87434c;border-radius:11px;background:#251015;padding:9px 11px;color:#ffb5bb;font-size:.75rem;font-weight:850}.nit-live-ok{border-color:#2d7359;background:#092319;color:#aef4cf}.nit-markets{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin-top:12px}.nit-market{border:1px solid #223f53;border-radius:14px;background:#06131d;padding:12px}.nit-market h4{margin:0;color:#8ee4ff;font-size:.74rem;letter-spacing:.05em}.nit-pick{display:flex;justify-content:space-between;align-items:end;gap:8px;margin-top:7px}.nit-pick strong{font-size:1rem;color:#f8fbff}.nit-prob{font-size:1.05rem;color:#dff7ff;font-weight:950}.nit-meter{height:6px;border-radius:999px;background:#162b3a;overflow:hidden;margin:7px 0 9px}.nit-meter i{display:block;height:100%;background:linear-gradient(90deg,#38bdf8,#7dd3fc);border-radius:999px}.nit-row{display:flex;justify-content:space-between;gap:8px;font-size:.72rem;color:#90a6b7;margin-top:5px}.nit-row b{color:#d6e4ed}.nit-move{margin-top:7px;border-radius:9px;background:#0a1c29;padding:7px 8px;color:#a8dff2;font-size:.7rem}.nit-why,.nit-risk{margin-top:8px;border-radius:9px;padding:8px;font-size:.7rem;line-height:1.42}.nit-why{background:#0a1d29;border-left:3px solid var(--ice2);color:#aac0ce}.nit-risk{background:#18160d;border-left:3px solid var(--warn);color:#bdb398}.nit-why b{color:#c9f0ff}.nit-risk b{color:#f0dda0}
.nit-slip{position:sticky;bottom:8px;z-index:8;border:1px solid #447891;border-radius:16px;background:rgba(4,15,24,.97);padding:12px;box-shadow:0 14px 36px rgba(0,0,0,.35)}.nit-slip b{color:#d5f4ff;font-size:.85rem}.nit-slip span{color:#97acbb;font-size:.73rem;margin-left:7px}
@media(max-width:800px){.nit-summary{grid-template-columns:repeat(2,1fr)}.nit-featured,.nit-markets{grid-template-columns:1fr}.nit-title{font-size:1.65rem}.nit-head{grid-template-columns:1fr auto 1fr;gap:6px}.team-logo{width:40px;height:40px}.nit-team b{font-size:.82rem}.nit-feed{align-items:flex-start;flex-direction:column}}
</style>
"""


def _safe(value: Any, fallback: str = "—") -> str:
    return v3._safe(value, fallback)


def _pct(value: Any) -> str:
    return v3._pct(value)


def _line(value: Any) -> str:
    return v3._line(value)


def _american(value: Any) -> str:
    try:
        number = int(round(float(value)))
        return f"+{number}" if number > 0 else str(number)
    except Exception:
        return "—"


def _featured_html(featured: Iterable[Any]) -> str:
    labels = ("BEST PICK", "STRONG EDGE", "TOP VALUE")
    cards = []
    for index, candidate in enumerate(tuple(featured)[:3]):
        reasons = [str(item).strip() for item in tuple(candidate.reason_components or ()) if str(item).strip()]
        cards.append(
            '<div class="nit-feature">'
            f'<em>{labels[index]}</em><strong>{escape(candidate.subject_label)} • {escape(candidate.market_label)}</strong>'
            f'<span>{escape(candidate.side)} • {_pct(candidate.model_probability)} model probability • score {normalized_pick_score(candidate):.3f}</span>'
            f'<span>{escape(reasons[0] if reasons else "Source-owned qualified signal.")}</span></div>'
        )
    return '<div class="nit-featured">' + ''.join(cards) + '</div>' if cards else ''


def _current_live_observation(rows: Iterable[Mapping[str, Any]], market_id: str, preferred_side: Any = None) -> dict[str, Any] | None:
    values = [dict(row) for row in rows if str(row.get("market_id")) == str(market_id)]
    if not values:
        return None
    wanted = str(preferred_side or "").strip().upper()
    if wanted:
        exact = [row for row in values if str(row.get("side") or "").strip().upper() == wanted]
        if exact:
            values = exact
    values.sort(key=lambda row: (float(row.get("age_seconds") or 10**9), str(row.get("book") or "")))
    return values[0]


def _session_move_text(observation: Mapping[str, Any] | None) -> str:
    if not observation or st is None:
        return "Since page opened: waiting for a verified change"
    movement = session_line_movement(session_line_history(st.session_state, observation))
    if movement.get("ready") is not True:
        return "Since page opened: waiting for a verified change"
    return f"Since page opened: {_line(movement.get('previous_line'))} → {_line(movement.get('current_line'))} ({float(movement.get('delta')):+.1f})"


def _market_html(market_id: str, payload: Mapping[str, Any], live_status: Mapping[str, Any], state: str) -> str:
    probability = payload.get("probability") if payload.get("probability_state") == "CERTIFIED" else None
    probability_text = _pct(probability) if probability is not None else "Source probability unavailable"
    try:
        meter = max(0.0, min(100.0, 100.0 * float(probability))) if probability is not None else 0.0
    except Exception:
        meter = 0.0
    live_observation = _current_live_observation(live_status.get("observations") or (), market_id, payload.get("side")) if state == "live" else None
    best = dict(payload.get("best_book") or {})
    if state == "live":
        market_line = live_observation.get("line") if live_observation else None
        book = live_observation.get("book") if live_observation else "LIVE ODDS UNAVAILABLE"
        price = _american(live_observation.get("price")) if live_observation else "—"
        freshness = v3._freshness(live_observation.get("age_seconds")) if live_observation else "Unavailable"
        movement = _session_move_text(live_observation)
        model_label = "PREGAME MODEL"
    else:
        market_line = payload.get("market_line")
        book = _safe(best.get("book"), "No verified current book") if best.get("ready") else "No verified current book"
        price = _american(best.get("price")) if best.get("ready") else "—"
        freshness = v3._freshness(payload.get("freshness_seconds"))
        movement = "Provider movement: " + v3._movement_text(payload)
        model_label = "MODEL"
    return (
        f'<div class="nit-market"><h4>{escape(v3.MARKET_LABELS[market_id])}</h4>'
        f'<div class="nit-pick"><strong>{escape(_safe(payload.get("side"), "Connected"))}</strong><span class="nit-prob">{escape(probability_text)}</span></div>'
        f'<div class="nit-meter"><i style="width:{meter:.1f}%"></i></div>'
        f'<div class="nit-row"><span>{model_label}</span><b>{escape(probability_text)}</b></div>'
        f'<div class="nit-row"><span>Model projection</span><b>{escape(v3._number(payload.get("projection")))}</b></div>'
        f'<div class="nit-row"><span>Verified market</span><b>{escape(_line(market_line))}</b></div>'
        f'<div class="nit-row"><span>Best/current book</span><b>{escape(str(book))} {escape(price)}</b></div>'
        f'<div class="nit-row"><span>Freshness</span><b>{escape(freshness)}</b></div>'
        f'<div class="nit-move">{escape(movement)}</div>'
        f'<div class="nit-why"><b>WHY THE MODEL LIKES IT</b><br>{escape(_safe(payload.get("why")))}</div>'
        f'<div class="nit-risk"><b>RISK</b><br>{escape(_safe(payload.get("risk")))}</div></div>'
    )


def render_nfl_daily_picks_command_center() -> None:
    if st is None:
        return
    from nfl_daily_picks_hub_v1 import _selected_day

    now_utc = datetime.now(timezone.utc)
    day = _selected_day()
    candidates, states, pregame_observations = v3._collect_runtime_context(day, now_utc)
    live_observations = fetch_live_market_observations(states, day_str=day.isoformat(), now_utc=now_utc)
    all_observations = tuple(pregame_observations) + tuple(live_observations)
    update_session_line_history(st.session_state, all_observations, now_utc=now_utc)

    refresh_seconds = smart_refresh_seconds(payload.get("state") for payload in states.values())
    if st_autorefresh is not None:
        st_autorefresh(interval=refresh_seconds * 1000, key="nfl_daily_picks_v4_smart_live_tick")

    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(
        '<section class="nit-hero"><div class="nit-kicker">KYRE SPORTS AI • NFL INTELLIGENCE TERMINAL</div>'
        '<div class="nit-title">NFL Daily Picks <span style="color:#7dd3fc">Live Decision Intelligence</span></div>'
        '<div class="nit-sub">Certified model truth, verified multi-book pricing, team identity and Smart Live movement. Sportsbook prices can move continuously; they never rewrite model projection or probability.</div></section>',
        unsafe_allow_html=True,
    )
    freshest_live = min((float(row.get("age_seconds")) for row in live_observations if row.get("verified") and row.get("age_seconds") is not None), default=None)
    feed_age = "awaiting verified live quote" if freshest_live is None else f"freshest live quote {freshest_live:.0f}s old"
    st.markdown(
        f'<div class="nit-feed"><b><span class="nit-dot"></span>LIVE MARKET FEED</b><span>Smart refresh {refresh_seconds}s • {escape(feed_age)} • exact-pair firewall active</span></div>',
        unsafe_allow_html=True,
    )

    risk_mode = st.radio("Risk profile", v3.RISK_MODES, index=v3.RISK_MODES.index(v3.DEFAULT_RISK_MODE), horizontal=True, key="nfl_daily_picks_v4_risk")
    board = v3.build_command_center_board(candidates, now_utc=now_utc, game_states=states, observations=pregame_observations, risk_mode=risk_mode)
    summary = board["summary"]
    freshest = "—" if summary["freshest_age_seconds"] is None else f"{summary['freshest_age_seconds']:.0f}s"
    st.markdown(
        '<div class="nit-summary">'
        f'<div class="nit-stat"><b>{summary["games_tracked"]}</b><span>Games tracked</span></div>'
        f'<div class="nit-stat"><b>{summary["qualified_markets"]}</b><span>Qualified signals</span></div>'
        f'<div class="nit-stat"><b>{summary["verified_books"]}</b><span>Verified books</span></div>'
        f'<div class="nit-stat"><b>{freshest}</b><span>Pregame source age</span></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="nit-section">FEATURED INTELLIGENCE</div>' + _featured_html(board["featured"]), unsafe_allow_html=True)
    bucket_name = st.radio("Slate view", ("LIVE NOW", "NEXT GAMES", "ALL NFL"), horizontal=True, key="nfl_daily_picks_v4_bucket")
    rows = board["buckets"][bucket_name]
    if not rows:
        st.info("No games are currently in this view. The next authoritative NFL slate will surface automatically.")

    for row in rows:
        state = str(row.get("state") or "scheduled")
        away, home = matchup_teams(row.get("matchup"))
        live_status = live_market_firewall(state, live_observations, game_id=str(row["game_id"]), now_utc=now_utc)
        badge_class = "nit-badge live" if state == "live" else "nit-badge"
        kickoff_text = row["kickoff_at"].strftime("%a %I:%M %p")
        status_note = ""
        if state == "live":
            if live_status.get("observations"):
                status_note = '<div class="nit-live-alert nit-live-ok">LIVE MARKET VERIFIED • exact-pair quotes passed freshness + timestamp-skew gates • model remains PREGAME MODEL.</div>'
            else:
                status_note = '<div class="nit-live-alert">LIVE ODDS UNAVAILABLE • no trustworthy in-game pair passed verification. Pregame prices are not being shown as live.</div>'
        cards = ''.join(_market_html(market_id, row["markets"][market_id], live_status, state) for market_id in v3.MARKET_IDS)
        st.markdown(
            '<article class="nit-game"><div class="nit-head">'
            f'<div class="nit-team"><img class="team-logo" src="{escape(nfl_team_logo_url(away))}" alt="{escape(away)} logo"><b>{escape(away or "AWAY")}</b></div>'
            f'<div class="nit-center"><span class="{badge_class}">{escape(state.upper())}</span><div class="nit-kick">{escape(kickoff_text)} {v3.ET_LABEL}</div></div>'
            f'<div class="nit-team right"><b>{escape(home or "HOME")}</b><img class="team-logo" src="{escape(nfl_team_logo_url(home))}" alt="{escape(home)} logo"></div>'
            f'</div>{status_note}<div class="nit-markets">{cards}</div></article>',
            unsafe_allow_html=True,
        )

    generated = board["generated_parlay"]
    active_key, trim_key = "nfl_daily_picks_v4_slip_active", "nfl_daily_picks_v4_slip_trim"
    st.session_state.setdefault(active_key, False)
    st.session_state.setdefault(trim_key, 0)
    c1, c2, c3 = st.columns(3)
    if c1.button("Build Me a Parlay", key="nfl_daily_picks_v4_build_parlay", use_container_width=True):
        st.session_state[active_key] = True
        st.session_state[trim_key] = 0
    if c2.button("Remove Last Leg", key="nfl_daily_picks_v4_remove_leg", use_container_width=True):
        st.session_state[active_key] = True
        st.session_state[trim_key] = int(st.session_state.get(trim_key, 0)) + 1
    if c3.button("Reset Slip", key="nfl_daily_picks_v4_reset_slip", use_container_width=True):
        st.session_state[active_key] = False
        st.session_state[trim_key] = 0

    if st.session_state.get(active_key) and generated.get("allowed"):
        base_legs = tuple(generated.get("legs") or ())
        trim = max(0, int(st.session_state.get(trim_key, 0)))
        legs = base_legs[: max(0, len(base_legs) - trim)]
        estimate = estimate_parlay_probability(legs) if len(legs) >= 2 else {"allowed": False}
        if estimate.get("allowed"):
            st.markdown(
                f'<div class="nit-slip"><b>KYRE AI PARLAY • {escape(risk_mode)}</b><span>{len(legs)} legs • {escape(_safe(estimate.get("correlation_grade")))} correlation • {_pct(estimate.get("estimated_probability"))} estimated probability</span></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown('<div class="nit-slip"><b>KYRE AI PARLAY</b><span>Add at least 2 qualified, non-conflicting legs.</span></div>', unsafe_allow_html=True)
    elif generated.get("allowed"):
        st.markdown('<div class="nit-slip"><b>KYRE AI PARLAY READY</b><span>Tap Build Me a Parlay to load the current risk-profile combination.</span></div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="nit-slip"><b>KYRE AI PARLAY • {escape(risk_mode)}</b><span>{escape(str(generated.get("reason") or "Waiting for enough qualified legs"))}</span></div>', unsafe_allow_html=True)

    st.caption(f"{MODEL_VERSION} • sportsbook projection influence {SPORTSBOOK_PROJECTION_INFLUENCE:.1f}% • Game Total probability fails closed unless source-certified • live model remains pregame unless separately certified")


def render_nfl_hub(market: str = "Daily Picks") -> None:
    if str(market or "Daily Picks") != "Daily Picks":
        raise ValueError("NFL Daily Picks V4 only owns the Daily Picks market.")
    render_nfl_daily_picks_command_center()


__all__ = ["MAY_MODIFY_PROJECTION", "MODEL_VERSION", "SPORTSBOOK_PROJECTION_INFLUENCE", "render_nfl_daily_picks_command_center", "render_nfl_hub"]
