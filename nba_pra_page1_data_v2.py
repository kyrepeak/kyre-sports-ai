"""NBA PRA Page 1 V2 live-market routing overlay.

Preserves the frozen/current Page-1 snapshot implementation in
``nba_pra_page1_data_core_v2`` while fixing sportsbook credential reuse,
Phoenix-local market windows, and primary-to-secondary routing.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Any, Mapping

import nba_pra_page1_data_core_v2 as _core
import nba_pra_page1_sgo_v1 as _sgo
from nba_pra_page1_common_v1 import PHOENIX_TZ
from nba_pra_page1_sources_v2 import load_approved_odds_api_pra_observations

# Preserve the existing module surface, including private helpers used by tests.
globals().update({k: v for k, v in vars(_core).items() if not k.startswith("__")})


def _connected_secret(name: str) -> str | None:
    session_key = {
        "SPORTSGAMEODDS_API_KEY": "ks_sportsgameodds_key",
        "SGO_API_KEY": "ks_sportsgameodds_key",
        "ODDS_API_IO_KEY": "ks_odds_api_key",
        "ODDS_API_KEY": "ks_odds_api_key",
    }.get(str(name or "").strip())
    try:
        import streamlit as st
        if session_key:
            value = st.session_state.get(session_key)
            if value:
                return str(value).strip() or None
        value = st.secrets.get(name)
        if value:
            return str(value).strip() or None
    except Exception:
        pass
    import os
    value = os.getenv(name)
    return str(value).strip() if value else None


def _phoenix_window(slate_date):
    start = datetime.combine(slate_date, time.min, tzinfo=PHOENIX_TZ)
    end = start + timedelta(days=1)
    fmt = lambda value: value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return fmt(start), fmt(end)


def _load_sgo_primary(slate_date, *, request_get=None, secret_getter=None, timeout: float = 6.0):
    upstream = request_get or _sgo._default_get
    starts_after, starts_before = _phoenix_window(slate_date)

    def phoenix_get(url, **kwargs):
        params = dict(kwargs.get("params") or {})
        params["startsAfter"] = starts_after
        params["startsBefore"] = starts_before
        kwargs["params"] = params
        return upstream(url, **kwargs)

    return _sgo.load_sgo_pra_observations(
        slate_date,
        request_get=phoenix_get,
        secret_getter=secret_getter or _connected_secret,
        timeout=timeout,
    )


def _load_odds_secondary(slate_date):
    return load_approved_odds_api_pra_observations(slate_date, secret_getter=_connected_secret)


def _primary_market_covers_games(payload: Mapping[str, Any], games) -> bool:
    rows = [row for row in (payload.get("observations") or []) if isinstance(row, Mapping)]
    if not rows:
        return False
    event_ids = {str(row.get("provider_event_id") or "").strip() for row in rows} - {""}
    if len(event_ids) >= len(games):
        return True
    matchups = {
        (
            "".join(ch for ch in str(row.get("away_team") or "").casefold() if ch.isalnum()),
            "".join(ch for ch in str(row.get("home_team") or "").casefold() if ch.isalnum()),
        )
        for row in rows
        if str(row.get("away_team") or "").strip() and str(row.get("home_team") or "").strip()
    }
    return len(matchups) >= len(games)


def _skipped_secondary():
    return {
        "source": "Odds-API.io",
        "verification": "SKIPPED_PRIMARY_COMPLETE",
        "diagnostic_state": "SKIPPED_PRIMARY_COMPLETE",
        "observations": [],
        "fabrication": False,
        "sportsbook_projection_influence": 0.0,
    }


def load_page1_snapshot_v2(
    *, now=None, schedule_loader=None, sgo_loader=None, odds_loader=None,
    official_profile_loader=None, backup_profile_loader=None, injury_loader=None,
):
    now_utc = now or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    schedule_impl = schedule_loader or _core._default_schedule_loader
    primary_impl = sgo_loader or _load_sgo_primary
    secondary_impl = odds_loader or _load_odds_secondary
    state = {}

    def schedule_proxy(**kwargs):
        result = dict(schedule_impl(**kwargs) or {})
        _, games = _core.select_next_upcoming_slate(list(result.get("games") or []), now_utc)
        state["games"] = games
        return result

    def primary_proxy(day):
        result = dict(primary_impl(day) or {})
        state["primary"] = result
        return result

    def secondary_proxy(day):
        if _primary_market_covers_games(state.get("primary", {}), state.get("games", [])):
            return _skipped_secondary()
        return dict(secondary_impl(day) or {})

    return _core.load_page1_snapshot_v2(
        now=now_utc,
        schedule_loader=schedule_proxy,
        sgo_loader=primary_proxy,
        odds_loader=secondary_proxy,
        official_profile_loader=official_profile_loader,
        backup_profile_loader=backup_profile_loader,
        injury_loader=injury_loader,
    )
