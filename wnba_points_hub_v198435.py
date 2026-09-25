"""WNBA Points V1.9.8.4.35 — bounded first-paint market transport.

Performance-only wrapper over V1.9.8.4.34.

The V1.9.8.4.34 display-line transport can serially attempt several discovery
and detail SportsGameOdds requests, each with a 20-second timeout. When the
provider is slow or rejects a request shape, those display-only retries can
block the entire WNBA Points first render even though the existing PRE-MARKET
Points path is explicitly allowed to render without sportsbook availability.

This wrapper keeps the exact same event/odd parsing and fail-closed semantics,
but gives the display/current-line lookup one small wall-clock budget. If the
provider does not return a usable Points market inside that budget, the route
continues with the inherited PRE-MARKET presentation and every production
market/readiness gate remains locked.

No projection, minutes, matchup, calibration, Monte Carlo, no-vig, EV, ranking,
qualification, or production 5M logic is modified.
"""
from __future__ import annotations

import time

import pandas as pd
import requests
import streamlit as st

import wnba_api_schedule_bridge_v1 as schedule_bridge
import wnba_points_hub_v1983 as calibration
import wnba_points_hub_v198421 as usage_bridge
import wnba_points_hub_v198434 as prior
import wnba_schedule_v25 as schedule25
from wnba_api_client_v1 import KyreWNBAAPIClient, SUPPORTED_SEASON

base = prior.base
v171 = base.v171
ui = base.ui
points = base.points

MODEL_VERSION = "WNBA POINTS V1.9.8.4.35 • BOUNDED FIRST-PAINT MARKET TRANSPORT"
PRA_FROZEN_BRANCH = base.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = base.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = base.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = base.POINTS_FROZEN_COMMIT

# Display/current-line transport only. The inherited production readiness gates
# still require real exact pairs; timing out here can never manufacture market data.
DISPLAY_MARKET_BUDGET_SECONDS = 8.0
PER_REQUEST_CAP_SECONDS = 2.5
SCHEDULE_API_TIMEOUT_SECONDS = 2.5
SCHEDULE_API_ATTEMPTS = 1
USAGE_REQUEST_CAP_SECONDS = 1.5
USAGE_WINDOW_BUDGET_SECONDS = 2.5
HISTORY_OPT_IN_KEY = "_wnba_points_history_context_opt_in_v198435"

_V432 = prior.v432
_BASE_HISTORY_OPTIONAL = getattr(
    _V432,
    "_kyre_v198435_original_history_context_optional",
    _V432._history_context_market_optional,
)
setattr(_V432, "_kyre_v198435_original_history_context_optional", _BASE_HISTORY_OPTIONAL)


_POINTS_API = KyreWNBAAPIClient(
    timeout_seconds=SCHEDULE_API_TIMEOUT_SECONDS,
    attempts=SCHEDULE_API_ATTEMPTS,
)
_POINTS_LEGACY_SCHEDULE = getattr(
    schedule25,
    "_kyre_step7f_original_schedule_for_date",
    schedule25.schedule_for_date,
)
_POINTS_LEGACY_DIAGNOSTICS = getattr(
    schedule25,
    "_kyre_step7f_original_schedule_diagnostics",
    schedule25.schedule_diagnostics,
)


@st.cache_data(ttl=60, show_spinner=False, max_entries=16)
def _points_api_schedule_attempt(day_str: str) -> dict:
    try:
        payload = _POINTS_API.games_for_date(day_str, SUPPORTED_SEASON)
        return {"ok": True, "payload": payload}
    except Exception as exc:
        return {
            "ok": False,
            "error_type": type(exc).__name__,
            "error": str(exc)[:240],
        }


def _schedule_for_date_bounded(day):
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")
    attempt = _points_api_schedule_attempt(day_str)
    if attempt.get("ok"):
        try:
            return schedule_bridge.api_schedule_frame(
                attempt.get("payload") or {},
                day_str,
                schedule25,
            )
        except Exception:
            pass
    return _POINTS_LEGACY_SCHEDULE(day)


def _schedule_diagnostics_bounded(day):
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")
    attempt = _points_api_schedule_attempt(day_str)
    if attempt.get("ok"):
        try:
            payload = attempt.get("payload") or {}
            frame = schedule_bridge.api_schedule_frame(payload, day_str, schedule25)
            teams = 0
            if len(frame):
                teams = len(
                    set(frame.get("away_team_id", pd.Series(dtype=int)).tolist())
                    | set(frame.get("home_team_id", pd.Series(dtype=int)).tolist())
                )
            return {
                "selected_date": day_str,
                "state": "VERIFIED_API" if len(frame) else "VERIFIED_API_OFF_DAY",
                "games": int(len(frame)),
                "teams": int(teams),
                "chosen_source": schedule_bridge.API_SOURCE_LABEL,
                "confirming_sources": ["Kyre Sports API"],
                "season_sources_ok": 1,
                "attempts": [{
                    "provider": "Kyre Sports API",
                    "status": "ok",
                    "selected_games": int(len(frame)),
                    "source_variant": payload.get("source_variant"),
                    "source_url": payload.get("source_url"),
                }],
                "source_selected_counts": {"Kyre Sports API": int(len(frame))},
                "rejected_single_source_matchups": 0,
                "timezone_rule": "America/New_York slate date",
                "step7f_api_first": True,
                "fallback_used": False,
                "points_first_paint_bounded": True,
            }
        except Exception:
            pass

    legacy = _POINTS_LEGACY_DIAGNOSTICS(day)
    result = dict(legacy or {})
    result.update({
        "step7f_api_first": True,
        "fallback_used": True,
        "points_first_paint_bounded": True,
        "api_error_type": attempt.get("error_type"),
    })
    return result


def _history_context_on_demand(day: str) -> pd.DataFrame:
    """Keep descriptive H2H/Top-5 enrichment off the critical first-paint path."""
    if not bool(st.session_state.get(HISTORY_OPT_IN_KEY, False)):
        return pd.DataFrame()
    try:
        return _BASE_HISTORY_OPTIONAL(day)
    except Exception:
        return pd.DataFrame()


def _calibration_schedule_for_bounded(day: str):
    """Resolve calibration finals from schedule data without running Points projections."""
    try:
        frame = schedule25.schedule_for_date(day)
        return frame if isinstance(frame, pd.DataFrame) else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=900, show_spinner=False, max_entries=18)
def _advanced_usage_fetch_bounded(season: int, last_n: int = 0):
    """Points-only bounded copy of the existing WNBA Advanced usage fetch."""
    rb = usage_bridge.role.base
    params = rb._advanced_params(int(season), int(last_n))
    deadline = time.monotonic() + USAGE_WINDOW_BUDGET_SECONDS
    for host in rb.resilient.PLAYER_HOSTS:
        remaining = max(0.0, deadline - time.monotonic())
        if remaining <= 0:
            break
        try:
            payload = rb.resilient._json_response(
                host,
                params=params,
                headers=rb.resilient._player_headers(host),
                timeout=max(0.35, min(USAGE_REQUEST_CAP_SECONDS, remaining)),
            )
            frame = rb.resilient.transport.base._frame_from_result(payload)
            if frame is None or frame.empty:
                continue
            frame.columns = [str(col).upper() for col in frame.columns]
            if "PLAYER_ID" not in frame.columns or "TEAM_ID" not in frame.columns:
                continue
            keep = [
                col for col in ("PLAYER_ID", "TEAM_ID", "PLAYER_NAME", "MIN", "USG_PCT", "PIE")
                if col in frame.columns
            ]
            frame = frame[keep].copy()
            frame["PLAYER_ID"] = pd.to_numeric(frame["PLAYER_ID"], errors="coerce")
            frame["TEAM_ID"] = pd.to_numeric(frame["TEAM_ID"], errors="coerce")
            if "USG_PCT" in frame.columns:
                frame["USG_PCT"] = frame["USG_PCT"].map(rb._normalize_usage)
            source = (
                "WNBA Stats Advanced"
                if "wnba.com" in host
                else "NBA Stats LeagueID=10 Advanced fallback"
            )
            frame["USG_SOURCE"] = source
            return frame.dropna(subset=["PLAYER_ID", "TEAM_ID"]).reset_index(drop=True), source
        except Exception:
            continue
    return pd.DataFrame(), "unavailable"


def _remaining(deadline: float) -> float:
    return max(0.0, float(deadline) - time.monotonic())


def _request_timeout(deadline: float):
    remaining = _remaining(deadline)
    if remaining <= 0:
        raise TimeoutError("WNBA_POINTS_DISPLAY_MARKET_BUDGET_EXHAUSTED")
    # Requests accepts a scalar timeout. Keep enough room for subsequent fallback
    # to fail closed instead of letting one provider attempt own the whole render.
    return max(0.35, min(PER_REQUEST_CAP_SECONDS, remaining))


@st.cache_data(ttl=90, show_spinner=False, max_entries=16)
def _fetch_points_events_bounded(api_key: str, starts_after: str, starts_before: str):
    deadline = time.monotonic() + DISPLAY_MARKET_BUDGET_SECONDS
    headers = {"x-api-key": str(api_key)}
    endpoint = f"{prior.sgo1.SGO_BASE}/events"

    discovery_attempts = (
        {"leagueID": "WNBA", "type": "match", "finalized": "false", "startsAfter": str(starts_after), "startsBefore": str(starts_before), "oddsPresent": "true", "limit": 100},
        {"leagueID": "WNBA", "startsAfter": str(starts_after), "startsBefore": str(starts_before), "oddsAvailable": "true", "limit": 100},
        {"leagueID": "WNBA", "startsAfter": str(starts_after), "startsBefore": str(starts_before), "limit": 100},
    )

    discovered = []
    for params in discovery_attempts:
        if _remaining(deadline) <= 0:
            break
        try:
            response = requests.get(
                endpoint,
                params=params,
                headers=headers,
                timeout=_request_timeout(deadline),
            )
            if response.status_code != 200:
                if response.status_code in {400, 403, 404, 422, 429, 500, 502, 503, 504}:
                    continue
                response.raise_for_status()
            data = prior._events_from_response(response)
            if data:
                discovered = data
                break
        except Exception:
            continue

    if prior._has_points(discovered):
        return discovered

    event_ids = []
    for event in discovered:
        eid = str((event or {}).get("eventID") or (event or {}).get("id") or "").strip()
        if eid and eid not in event_ids:
            event_ids.append(eid)

    last_detail = []
    if event_ids:
        ids = ",".join(event_ids[:100])
        over = "points-PLAYER_ID-game-ou-over"
        both = "points-PLAYER_ID-game-ou-over,points-PLAYER_ID-game-ou-under"
        detail_attempts = (
            {"eventIDs": ids, "oddID": over, "includeOpposingOdds": "true", "includeAltLines": "false"},
            {"eventIDs": ids, "oddIDs": over, "includeOpposingOdds": "true", "includeAltLines": "false"},
            {"eventIDs": ids, "oddID": both, "includeAltLines": "false"},
            {"eventIDs": ids, "oddIDs": both, "includeAltLines": "false"},
            {"eventIDs": ids, "includeAltLines": "false"},
        )
        for params in detail_attempts:
            if _remaining(deadline) <= 0:
                break
            try:
                response = requests.get(
                    endpoint,
                    params=params,
                    headers=headers,
                    timeout=_request_timeout(deadline),
                )
                if response.status_code != 200:
                    if response.status_code in {400, 403, 404, 422, 429, 500, 502, 503, 504}:
                        continue
                    response.raise_for_status()
                data = prior._events_from_response(response)
                last_detail = data
                if prior._has_points(data):
                    return data
            except Exception:
                continue

    # Do not run the inherited multi-attempt fallback after the budget expires.
    # PRE-MARKET Points rendering is market-optional; returning the best verified
    # provider payload (or []) preserves fail-closed production behavior.
    if last_detail:
        return last_detail
    if discovered:
        return discovered
    return []


def _install() -> None:
    # V1.9.8.4.34's display helper and V1.9.8.4.32 exact-market bridge both
    # reference this module-global function at render time.
    prior._fetch_points_events_two_stage = _fetch_points_events_bounded


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    original_schedule = schedule25.schedule_for_date
    original_diagnostics = schedule25.schedule_diagnostics
    role_base = usage_bridge.role.base
    original_usage_fetch = role_base._advanced_usage_fetch
    original_calibration_schedule = calibration._schedule_for
    original_history_optional = _V432._history_context_market_optional
    original_captured_history_optional = prior._BASE_HISTORY_OPTIONAL
    original_h2h_history = _V432.h2h._history_context_rows
    schedule25.schedule_for_date = _schedule_for_date_bounded
    schedule25.schedule_diagnostics = _schedule_diagnostics_bounded
    role_base._advanced_usage_fetch = _advanced_usage_fetch_bounded
    calibration._schedule_for = _calibration_schedule_for_bounded
    _V432._history_context_market_optional = _history_context_on_demand
    prior._BASE_HISTORY_OPTIONAL = _history_context_on_demand
    st.markdown(
        '<span data-wnba-points-first-paint="v198435" '
        'style="display:none" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )
    if not bool(st.session_state.get(HISTORY_OPT_IN_KEY, False)):
        if st.button(
            "📚 Load detailed Top-5 history evidence",
            key="wnba_points_history_context_load_v198435",
            help="Loads descriptive H2H/Top-5 evidence after the main Points page is ready.",
        ):
            st.session_state[HISTORY_OPT_IN_KEY] = True
            st.rerun()
        st.caption(
            "Detailed H2H/Top-5 evidence is optional and loads on demand so it cannot block the Points page first render."
        )
    try:
        return prior.render_wnba_points_hub(section_header, status_info, team_logo, h)
    finally:
        schedule25.schedule_for_date = original_schedule
        schedule25.schedule_diagnostics = original_diagnostics
        role_base._advanced_usage_fetch = original_usage_fetch
        calibration._schedule_for = original_calibration_schedule
        _V432._history_context_market_optional = original_history_optional
        prior._BASE_HISTORY_OPTIONAL = original_captured_history_optional
        _V432.h2h._history_context_rows = original_h2h_history


def __getattr__(name):
    return getattr(prior, name)


__all__ = [
    "DISPLAY_MARKET_BUDGET_SECONDS",
    "MLB_FROZEN_BRANCH",
    "MODEL_VERSION",
    "PER_REQUEST_CAP_SECONDS",
    "SCHEDULE_API_ATTEMPTS",
    "SCHEDULE_API_TIMEOUT_SECONDS",
    "USAGE_REQUEST_CAP_SECONDS",
    "USAGE_WINDOW_BUDGET_SECONDS",
    "HISTORY_OPT_IN_KEY",
    "POINTS_FROZEN_BRANCH",
    "POINTS_FROZEN_COMMIT",
    "PRA_FROZEN_BRANCH",
    "PRA_FROZEN_COMMIT",
    "_calibration_schedule_for_bounded",
    "_history_context_on_demand",
    "_fetch_points_events_bounded",
    "points",
    "render_wnba_points_hub",
    "ui",
    "v171",
]
