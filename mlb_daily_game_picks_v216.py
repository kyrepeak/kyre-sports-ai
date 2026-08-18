"""MLB Daily Game Picks V2.1.6 — finished command-center shell.

Presentation/workflow layer only. Keeps V2.1.5 SportsGameOdds-primary transport,
Odds-API.io fallback, all seven production model formulas and simulation depths,
verified-market gates, persistent completed-card snapshots, live-risk checks,
Step 3 normalization, Step 5/6 selection rules, team logos and identity firewalls
unchanged.

Adds a compact mobile command-center header that makes slate/provider/build state
obvious before the user runs the One-Tap Full MLB Card:
- slate game count and sportsbook cache coverage;
- SportsGameOdds primary / Odds-API.io fallback health without exposing API keys;
- seven-connector readiness and current BUILD / RESUME / REVIEW next action;
- configured sportsbook count and cache freshness when available.
No API request is made by this status layer.
"""
from __future__ import annotations

from datetime import datetime
from html import escape

import streamlit as st

import mlb_daily_game_picks_v215 as previous
import mlb_daily_game_picks_v204 as market_bridge
import mlb_daily_game_picks_v209 as ui
import sportsbook_multi_provider_v1 as multi_odds

controller = previous.controller
VERSION = "MLB Daily Game Picks V2.1.6 • FINISHED COMMAND CENTER"

_BASE_INJECT_CSS = ui._inject_css


def _safe_secret(name, default=""):
    try:
        return str(st.secrets.get(name, default) or default)
    except Exception:
        return str(default or "")


def _game_count(games_df):
    try:
        return int(len(games_df))
    except Exception:
        return 0


def _done_count(games_df):
    try:
        return int(controller._completed_count(games_df))
    except Exception:
        done = 0
        for stage, _label, _icon in getattr(controller, "STAGES", []):
            try:
                done += int(bool(controller._complete(controller._pack(games_df, stage))))
            except Exception:
                pass
        return done


def _provider_status(day):
    primary = bool(multi_odds.get_sgo_api_key())
    fallback = bool(multi_odds.get_legacy_api_key())
    used = st.session_state.get(previous._provider_name_key(day))
    if used:
        active = str(used)
    elif primary:
        active = "SportsGameOdds primary"
    elif fallback:
        active = "Odds-API.io fallback"
    else:
        active = "Not connected"
    return active, primary, fallback


def _bookmakers():
    raw = _safe_secret(
        "SPORTSGAMEODDS_BOOKMAKERS",
        "draftkings,fanduel,betmgm,caesars",
    )
    names = [x.strip() for x in raw.split(",") if x.strip()]
    pretty = {
        "draftkings": "DraftKings",
        "fanduel": "FanDuel",
        "betmgm": "BetMGM",
        "caesars": "Caesars",
    }
    return [pretty.get(x.lower(), x) for x in names]


def _cache_status(games_df, day):
    try:
        snaps = st.session_state.get(market_bridge._odds_key(day)) or {}
        matched = len(snaps) if isinstance(snaps, dict) else 0
    except Exception:
        matched = 0

    stamp = st.session_state.get(previous._provider_stamp_key(day))
    age_text = "not fetched on this page yet"
    if stamp:
        try:
            age = max(0, int(datetime.now().timestamp() - float(stamp)))
            if age < 60:
                age_text = f"{age}s old"
            elif age < 3600:
                age_text = f"{age // 60}m old"
            else:
                age_text = f"{age // 3600}h {(age % 3600) // 60}m old"
        except Exception:
            pass
    return matched, age_text


def _next_action(done, active):
    if active:
        return "BUILDING", "The One-Tap controller is working. Let the current stage finish; completed connectors stay cached.", "building"
    if done >= 7:
        return "CARD READY", "Review the Final Card below. Refresh only when lineup, starter, weather, or market freshness requires it.", "ready"
    if done > 0:
        left = max(0, 7 - done)
        return "RESUME", f"{done}/7 connectors are preserved. Resume the Full MLB Card to finish only the remaining {left}.", "resume"
    return "READY TO BUILD", "Tap BUILD TODAY'S FULL MLB CARD once. The seven production connectors will run in order and feed the Final Card automatically.", "start"


def _inject_css_v216():
    _BASE_INJECT_CSS()
    st.markdown(
        """
<style>
.k216-shell{border:1px solid #315b7a;background:linear-gradient(145deg,#0a1d31,#06131f);border-radius:20px;padding:14px 15px;margin:8px 0 10px}
.k216-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap}.k216-kicker{font-size:9px;letter-spacing:1.25px;font-weight:950;color:#60dcff;text-transform:uppercase}.k216-title{font-size:18px;font-weight:1000;color:#fff;margin-top:3px}.k216-sub{font-size:9px;color:#8fa8bd;margin-top:4px;line-height:1.45}.k216-state{border:1px solid #2a6d57;background:#0a3027;color:#6be8ae;border-radius:999px;padding:6px 10px;font-size:8px;font-weight:950;white-space:nowrap}.k216-state.building{border-color:#315e83;background:#09263b;color:#68dcff}.k216-state.resume{border-color:#7d6b28;background:#332d0c;color:#f2d66c}.k216-state.start{border-color:#315e83;background:#09263b;color:#68dcff}
.k216-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin-top:12px}.k216-metric{border:1px solid #29475f;background:#081725;border-radius:12px;padding:9px}.k216-label{font-size:7px;letter-spacing:.8px;text-transform:uppercase;font-weight:900;color:#7895aa}.k216-value{font-size:13px;font-weight:1000;color:#fff;margin-top:3px;line-height:1.2}.k216-note{font-size:8px;color:#7894aa;margin-top:3px;line-height:1.35}.k216-action{border:1px solid #294f6b;border-left:4px solid #55d9ff;background:#071d2b;border-radius:12px;padding:9px 11px;margin:9px 0 11px;color:#bdd0de;font-size:9px;line-height:1.5}.k216-action b{color:#fff}.k216-provider{color:#67e4aa}.k216-fallback{color:#f0cf65}
@media(max-width:780px){.k216-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:480px){.k216-title{font-size:16px}.k216-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.k216-value{font-size:12px}}
</style>
""",
        unsafe_allow_html=True,
    )


def _render_top_status_v216(games_df):
    day = ui._day(games_df)
    done = _done_count(games_df)
    total_games = _game_count(games_df)
    state = st.session_state.get(controller._state_key(day)) or {}
    active_build = bool(state.get("active"))
    action, action_text, action_cls = _next_action(done, active_build)
    provider, primary, fallback = _provider_status(day)
    matched, cache_age = _cache_status(games_df, day)
    books = _bookmakers()

    try:
        ts = ui._record_ready_timestamp(games_df)
        last_build = ui._fmt_ts(ts)
    except Exception:
        last_build = "Not built in this session"

    if primary:
        provider_html = '<span class="k216-provider">SportsGameOdds PRIMARY</span>'
    elif fallback:
        provider_html = '<span class="k216-fallback">Odds-API.io FALLBACK</span>'
    else:
        provider_html = "Not connected"

    fallback_note = "fallback armed" if fallback and primary else ("only provider" if primary else "")
    coverage_value = f"{matched}/{total_games}" if matched or total_games else "0/0"
    coverage_note = f"shared normalized cache • {escape(cache_age)}"
    books_value = f"{len(books)} books" if books else "0 books"
    books_note = ", ".join(books[:4]) if books else "waiting for sportsbook configuration"

    st.markdown(
        f'''<div class="k216-shell">
          <div class="k216-head">
            <div>
              <div class="k216-kicker">KYRE SPORTS AI • MLB DAILY COMMAND CENTER • V2.1.6</div>
              <div class="k216-title">⚾ Today's MLB Card Control</div>
              <div class="k216-sub">Slate {escape(str(day or '—'))} • Last full build: {escape(str(last_build))} • status layer makes no sportsbook requests</div>
            </div>
            <div class="k216-state {action_cls}">● {escape(action)}</div>
          </div>
          <div class="k216-metrics">
            <div class="k216-metric"><div class="k216-label">Slate</div><div class="k216-value">{total_games} games</div><div class="k216-note">official verified schedule</div></div>
            <div class="k216-metric"><div class="k216-label">Production</div><div class="k216-value">{done}/7 ready</div><div class="k216-note">completed connectors stay cached</div></div>
            <div class="k216-metric"><div class="k216-label">Sportsbook feed</div><div class="k216-value">{provider_html}</div><div class="k216-note">{escape(fallback_note or provider)}</div></div>
            <div class="k216-metric"><div class="k216-label">Market cache</div><div class="k216-value">{escape(coverage_value)} games</div><div class="k216-note">{coverage_note}</div></div>
            <div class="k216-metric"><div class="k216-label">Books requested</div><div class="k216-value">{escape(books_value)}</div><div class="k216-note">{escape(books_note)}</div></div>
            <div class="k216-metric"><div class="k216-label">Model math</div><div class="k216-value">UNCHANGED</div><div class="k216-note">existing probabilities + simulation depths</div></div>
            <div class="k216-metric"><div class="k216-label">Final Card</div><div class="k216-value">{'LIVE' if done >= 7 else 'WAITING'}</div><div class="k216-note">real scored outputs only • no fabricated picks</div></div>
            <div class="k216-metric"><div class="k216-label">Fallback</div><div class="k216-value">{'READY' if fallback else 'OFF'}</div><div class="k216-note">Odds-API.io used only if primary is unavailable</div></div>
          </div>
        </div>
        <div class="k216-action"><b>Next:</b> {escape(action_text)}</div>''',
        unsafe_allow_html=True,
    )
    ui._render_stage_pills(games_df)


def render_daily_game_picks(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    # Patch only presentation hooks resolved by the inherited V2.0.9 renderer.
    # Production builders, sportsbook transport, model probabilities and ranking
    # functions remain owned by V2.1.5 and earlier proven modules.
    ui._inject_css = _inject_css_v216
    ui._render_top_status = _render_top_status_v216

    st.caption(
        "✨ V2.1.6 page finish: command-center readiness + provider/cache visibility + clearer next action • no production model math changed."
    )
    return previous.render_daily_game_picks(
        games_df, section_header, status_info, team_logo, h
    )
