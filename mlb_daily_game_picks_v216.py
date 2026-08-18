"""MLB Daily Game Picks V2.1.6 — finished command-center shell.

Presentation/workflow layer only. Keeps V2.1.5 SportsGameOdds-primary transport,
Odds-API.io fallback, all seven production model formulas and simulation depths,
verified-market gates, persistent completed-card snapshots, live-risk checks,
Step 3 normalization, Step 5/6 selection rules, team logos and identity firewalls
unchanged.

Adds a compact mobile command-center header that makes slate/provider/build state
obvious before the user runs the One-Tap Full MLB Card. The V2.1.6b display
hotfix uses inline styles for Safari/Streamlit reliability and suppresses only
redundant inherited version captions; real warnings, errors and diagnostics still
render normally. No API request is made by this status layer.
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
VERSION = "MLB Daily Game Picks V2.1.6b • MOBILE UI HOTFIX"

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
        return (
            "BUILDING",
            "The One-Tap controller is working. Let the current stage finish; completed connectors stay cached.",
            "#68dcff",
            "#09263b",
            "#315e83",
        )
    if done >= 7:
        return (
            "CARD READY",
            "Review the Final Card below. Refresh only when lineup, starter, weather, or market freshness requires it.",
            "#6be8ae",
            "#0a3027",
            "#2a6d57",
        )
    if done > 0:
        left = max(0, 7 - done)
        return (
            "RESUME",
            f"{done}/7 connectors are preserved. Resume the Full MLB Card to finish only the remaining {left}.",
            "#f2d66c",
            "#332d0c",
            "#7d6b28",
        )
    return (
        "READY TO BUILD",
        "Tap BUILD TODAY'S FULL MLB CARD once. The seven production connectors will run in order and feed the Final Card automatically.",
        "#68dcff",
        "#09263b",
        "#315e83",
    )


def _inject_css_v216():
    # Keep all proven V2.0.9 CSS for stage pills, Final Card and market cards.
    # V2.1.6 command-center styling itself is inline because Safari/iPad Streamlit
    # did not consistently retain the second style block across reruns.
    _BASE_INJECT_CSS()


def _metric(label, value_html, note, value_color="#ffffff"):
    return (
        '<div style="border:1px solid #29475f;background:#081725;border-radius:12px;'
        'padding:10px;min-width:0;box-sizing:border-box">'
        f'<div style="font-size:8px;letter-spacing:.8px;text-transform:uppercase;font-weight:900;color:#7895aa">{escape(str(label))}</div>'
        f'<div style="font-size:14px;font-weight:950;color:{value_color};margin-top:4px;line-height:1.2;overflow-wrap:anywhere">{value_html}</div>'
        f'<div style="font-size:9px;color:#7894aa;margin-top:4px;line-height:1.35">{escape(str(note))}</div>'
        '</div>'
    )


def _render_top_status_v216(games_df):
    day = ui._day(games_df)
    done = _done_count(games_df)
    total_games = _game_count(games_df)
    state = st.session_state.get(controller._state_key(day)) or {}
    active_build = bool(state.get("active"))
    action, action_text, action_color, action_bg, action_border = _next_action(done, active_build)
    provider, primary, fallback = _provider_status(day)
    matched, cache_age = _cache_status(games_df, day)
    books = _bookmakers()

    try:
        ts = ui._record_ready_timestamp(games_df)
        last_build = ui._fmt_ts(ts)
    except Exception:
        last_build = "Not built in this session"

    provider_value = "SportsGameOdds PRIMARY" if primary else "Odds-API.io FALLBACK" if fallback else "Not connected"
    provider_color = "#67e4aa" if primary else "#f0cf65" if fallback else "#ff9090"
    fallback_note = "Odds-API.io fallback armed" if fallback and primary else ("primary provider only" if primary else provider)
    coverage_value = f"{matched}/{total_games}" if matched or total_games else "0/0"
    books_value = f"{len(books)} books" if books else "0 books"
    books_note = ", ".join(books[:4]) if books else "waiting for sportsbook configuration"

    metrics = "".join([
        _metric("Slate", f"{total_games} games", "official verified schedule"),
        _metric("Production", f"{done}/7 ready", "completed connectors stay cached", "#68dcff" if done < 7 else "#67e4aa"),
        _metric("Sportsbook feed", escape(provider_value), fallback_note, provider_color),
        _metric("Market cache", f"{escape(coverage_value)} games", f"shared normalized cache • {cache_age}", "#67e4aa" if matched else "#ffffff"),
        _metric("Books requested", escape(books_value), books_note),
        _metric("Model math", "UNCHANGED", "existing probabilities + simulation depths", "#67e4aa"),
        _metric("Final Card", "LIVE" if done >= 7 else "WAITING", "real scored outputs only • no fabricated picks", "#67e4aa" if done >= 7 else "#f0cf65"),
        _metric("Fallback", "READY" if fallback else "OFF", "used only if primary is unavailable", "#67e4aa" if fallback else "#9aa8b5"),
    ])

    shell_style = (
        "border:1px solid #315b7a;background:linear-gradient(145deg,#0a1d31,#06131f);"
        "border-radius:20px;padding:15px;margin:8px 0 10px;box-sizing:border-box"
    )
    head_style = "display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap"
    grid_style = (
        "display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));"
        "gap:8px;margin-top:13px;width:100%"
    )
    state_style = (
        f"border:1px solid {action_border};background:{action_bg};color:{action_color};"
        "border-radius:999px;padding:7px 11px;font-size:9px;font-weight:950;white-space:nowrap"
    )
    action_box_style = (
        "border:1px solid #294f6b;border-left:4px solid #55d9ff;background:#071d2b;"
        "border-radius:12px;padding:10px 12px;margin:9px 0 11px;color:#bdd0de;"
        "font-size:10px;line-height:1.5"
    )

    st.markdown(
        f'''<div style="{shell_style}">
          <div style="{head_style}">
            <div style="min-width:220px;flex:1 1 420px">
              <div style="font-size:9px;letter-spacing:1.25px;font-weight:950;color:#60dcff;text-transform:uppercase">KYRE SPORTS AI • MLB DAILY COMMAND CENTER • V2.1.6b</div>
              <div style="font-size:20px;font-weight:950;color:#ffffff;margin-top:4px">⚾ Today's MLB Card Control</div>
              <div style="font-size:10px;color:#8fa8bd;margin-top:5px;line-height:1.45">Slate {escape(str(day or '—'))} • Last full build: {escape(str(last_build))} • status layer makes no sportsbook requests</div>
            </div>
            <div style="{state_style}">● {escape(action)}</div>
          </div>
          <div style="{grid_style}">{metrics}</div>
        </div>
        <div style="{action_box_style}"><b style="color:#ffffff">Next:</b> {escape(action_text)}</div>''',
        unsafe_allow_html=True,
    )
    ui._render_stage_pills(games_df)


def _is_redundant_version_caption(body):
    text = str(body or "").strip()
    if not text:
        return False
    version_markers = (
        "V2.1.6 page finish",
        "V2.1.5 multi-provider sportsbook bridge",
        "V2.1.4b 429 quarantine",
        "V2.1.3 persistent card storage",
        "V2.1.2.5 retry handoff",
        "V2.1.2.4 resume controller",
        "V2.1.2.3 reload-safe risk check",
        "V2.1.2 live-risk layer",
        "V2.1.1 decision screen",
        "V2.1.0 sportsbook-resume hotfix",
    )
    return any(marker in text for marker in version_markers)


def render_daily_game_picks(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    # Patch only presentation hooks resolved by the inherited V2.0.9 renderer.
    ui._inject_css = _inject_css_v216
    ui._render_top_status = _render_top_status_v216

    # The inherited wrappers each publish a version-history caption. They were
    # useful during development but now crowd the production page. Filter only
    # those known banners during this render; all other captions still pass through.
    original_caption = st.caption

    def clean_caption(body, *args, **kwargs):
        if _is_redundant_version_caption(body):
            return None
        return original_caption(body, *args, **kwargs)

    st.caption = clean_caption
    try:
        return previous.render_daily_game_picks(
            games_df, section_header, status_info, team_logo, h
        )
    finally:
        st.caption = original_caption
