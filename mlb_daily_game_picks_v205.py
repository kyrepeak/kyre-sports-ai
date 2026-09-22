"""MLB Daily Game Picks V2.0.5 — quota-safe sportsbook bridge.

Preserves V2.0.4 production model math and all seven market families while making
Run Line + Total share the same sportsbook snapshot. Prevents duplicate refreshes,
respects provider 429 cooldown/reset hints, and redacts API keys from diagnostics.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
import time

import requests
import streamlit as st

import mlb_daily_game_picks_v204 as previous

VERSION = "MLB Daily Game Picks V2.0.5 • QUOTA-SAFE SHARED ODDS CACHE"
CACHE_TTL_SECONDS = 300
DEFAULT_429_COOLDOWN_SECONDS = 60


def _redact(value):
    text = str(value or "")
    text = re.sub(r"(?i)(apiKey=)[^&\s]+", r"\1***", text)
    text = re.sub(r"(?i)(api_key=)[^&\s]+", r"\1***", text)
    return text


def _stamp_key(day):
    return f"dgp_prod_market_odds_v205_stamp::{day}"


def _cooldown_key(day):
    return f"dgp_prod_market_odds_v205_cooldown::{day}"


def _parse_reset_epoch(headers):
    headers = headers or {}
    retry_after = headers.get("Retry-After") or headers.get("retry-after")
    if retry_after:
        try:
            return time.time() + max(1.0, float(retry_after))
        except Exception:
            pass
    reset = headers.get("x-ratelimit-reset") or headers.get("X-RateLimit-Reset")
    if reset:
        try:
            dt = datetime.fromisoformat(str(reset).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except Exception:
            pass
    return None


def _fmt_reset(epoch):
    try:
        dt = datetime.fromtimestamp(float(epoch), tz=timezone.utc).astimezone()
        return dt.strftime("%I:%M:%S %p %Z").lstrip("0")
    except Exception:
        return "the provider reset"


def _get_odds(games_df, force=False):
    """One shared sportsbook fetch for Run Line + Total, with 429 protection."""
    day = previous._day(games_df)
    state_key = previous._odds_key(day)
    stamp_key = _stamp_key(day)
    cooldown_key = _cooldown_key(day)

    cached = st.session_state.get(state_key)
    stamp = st.session_state.get(stamp_key)
    if cached:
        # Existing V2.0.4 cache has no stamp; trust it for this current session.
        if stamp is None or (time.time() - float(stamp)) <= CACHE_TTL_SECONDS:
            return cached, ""

    cooldown_until = st.session_state.get(cooldown_key)
    if cooldown_until:
        try:
            cooldown_until = float(cooldown_until)
        except Exception:
            cooldown_until = None
    if cooldown_until and time.time() < cooldown_until:
        return {}, (
            "Sportsbook provider rate limit is still cooling down. "
            f"Try again after {_fmt_reset(cooldown_until)}. No sportsbook line was fabricated."
        )
    elif cooldown_until:
        st.session_state.pop(cooldown_key, None)

    key = previous._clean_key(previous.get_api_key())
    if not key:
        return {}, (
            "Sportsbook odds are not connected. Run Line and Total require a real "
            "posted full-game line; add ODDS_API_IO_KEY in Streamlit Secrets. "
            "No line was fabricated."
        )

    try:
        snaps = previous.slate_snapshots_for_games_v205(
            games_df, key, previous.get_bookmakers()
        ) or {}
    except requests.HTTPError as exc:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
        if status == 429:
            reset_epoch = _parse_reset_epoch(getattr(response, "headers", {}) or {})
            if reset_epoch is None:
                reset_epoch = time.time() + DEFAULT_429_COOLDOWN_SECONDS
            st.session_state[cooldown_key] = float(reset_epoch)
            return {}, (
                "Sportsbook provider returned HTTP 429 (rate limit reached). "
                f"Retry after {_fmt_reset(reset_epoch)}. Run Line and Total will share one cached fetch once available."
            )
        return {}, f"Sportsbook market sync: HTTP {status or 'error'}: {_redact(exc)}"
    except Exception as exc:
        return {}, f"Sportsbook market sync: {type(exc).__name__}: {_redact(exc)}"

    if not snaps:
        return {}, "Sportsbook market sync returned no matched MLB games for this slate."

    st.session_state[state_key] = snaps
    st.session_state[stamp_key] = time.time()
    st.session_state.pop(cooldown_key, None)
    return snaps, ""


def _scrub_pack(key):
    pack = st.session_state.get(key)
    if not isinstance(pack, dict):
        return
    changed = False
    clean = dict(pack)
    for field in ("errors", "notes"):
        vals = clean.get(field)
        if isinstance(vals, list):
            new_vals = [_redact(v) for v in vals]
            if new_vals != vals:
                clean[field] = new_vals
                changed = True
    if changed:
        st.session_state[key] = clean


def _scrub_existing_diagnostics(games_df):
    day = previous._day(games_df)
    _scrub_pack(previous._runline_key(day))
    _scrub_pack(previous._total_key(day))


# Install the quota-safe fetch at the module where V2.0.4 connector functions
# resolve their globals. Production simulation/scoring math remains untouched.
previous._get_odds = _get_odds


def render_daily_game_picks(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    previous._get_odds = _get_odds
    _scrub_existing_diagnostics(games_df)
    st.caption("🔐 V2.0.5 sportsbook bridge: Run Line + Total share one 5-minute odds snapshot • 429 cooldown respected • API keys redacted from diagnostics.")
    return previous.render_daily_game_picks(games_df, section_header, status_info, team_logo, h)
