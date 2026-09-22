"""WNBA Points V1.9.8.4.32 — decouple Top-5 audit cards from sportsbook availability.

This is the actual cards-first repair over V1.9.8.4.31.

Root cause
----------
The Step-2 foundation (`wnba_points_hub_v194._history_context_rows`) returned an
empty frame whenever exact SportsGameOdds Points pairs were empty. Every later
Step 3-12 card deliberately reuses that same Top-5 handoff, so one missing market
made the ENTIRE already-built card/evidence stack disappear. The renderer was
not broken; its candidate source was incorrectly hard-gated by sportsbook data.

Repair
------
1. Keep the original exact-market candidate path completely unchanged whenever
   at least one verified exact Points market is available.
2. When exact markets are genuinely unavailable, build a DISPLAY-ONLY Top-5
   preview from the verified protected Points projection frame. These rows carry
   no fabricated line, odds, edge, probability or sportsbook. They are ordered
   only by verified projected Points for preview display and are explicitly
   labelled PRE-MARKET PREVIEW.
3. The existing Step 2-12 renderers consume that same preview handoff, so the
   player photo, H2H, opportunity, recent-form, defense/position, pace,
   shot-profile, availability/rotation, scoring-method, rest/fatigue, game-script
   and final evidence sections stay on the same cards before markets arrive.
4. The production 5M simulation/readiness path is NOT changed. It still requires
   real same-player + same-book + same-line Over/Under pairs and remains locked
   if SportsGameOdds has none.
5. Harden the Points-only SportsGameOdds request: use the documented `oddIDs`
   player-prop filter first, request the opposing side, and do not treat HTTP 200
   as success unless actual full-game player Points odds are present. Fall back
   through compatible request shapes before declaring the market empty.

No projection, minutes, matchup factor, Monte Carlo, calibration, qualification,
no-vig, production ranking, H2H math or Steps 2-12 scoring is altered. No market
line is invented. PRA/Rebounds/Assists/Spread/MLB/NFL are untouched.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import requests
import streamlit as st

import wnba_points_hub_v198431 as prior
import wnba_points_hub_v194 as h2h
import wnba_sportsgameodds_v1 as sgo1

base = prior.base
v171 = base.v171
ui = base.ui
points = base.points

MODEL_VERSION = "WNBA POINTS V1.9.8.4.32 • PRE-MARKET TOP-5 CARD HANDOFF REPAIR"
PRA_FROZEN_BRANCH = base.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = base.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = base.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = base.POINTS_FROZEN_COMMIT

# Save genuine functions once across Streamlit hot reloads.
_ORIGINAL_HISTORY_CONTEXT = getattr(
    h2h,
    "_kyre_v198432_original_history_context",
    h2h._history_context_rows,
)
setattr(h2h, "_kyre_v198432_original_history_context", _ORIGINAL_HISTORY_CONTEXT)

_ORIGINAL_CANDIDATE_ORDER = getattr(
    h2h,
    "_kyre_v198432_original_candidate_order",
    h2h._candidate_order,
)
setattr(h2h, "_kyre_v198432_original_candidate_order", _ORIGINAL_CANDIDATE_ORDER)


def _num(value, default=np.nan):
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _projection_frame(day: str) -> pd.DataFrame:
    """Read the protected Points projection without requiring a sportsbook pair."""
    try:
        # `_prepare` returns projections before the exact-market pairing gate.
        projections, _pairs, _snap, _meta, _lineups = points._prepare(str(day))
    except Exception:
        try:
            projections, _meta = points.matchup.matchup_projection_frame(str(day))
        except Exception:
            return pd.DataFrame()
    if not isinstance(projections, pd.DataFrame) or projections.empty:
        return pd.DataFrame()
    return projections.copy()


def _premarket_history_context(day: str) -> pd.DataFrame:
    """Five verified projection rows for card display only; never production picks."""
    p = _projection_frame(day)
    if p.empty:
        return pd.DataFrame()

    text_cols = {
        "game_id", "player_key", "PLAYER_NAME", "team_name", "opponent", "POSITION",
        "DESIGNATION", "ROLE_LABEL",
    }
    keep = [
        "game_id", "player_key", "PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "team_name",
        "opponent_team_id", "opponent", "PROJ_PTS", "PROJ_MIN", "POSITION",
        "DESIGNATION", "ROLE_LABEL",
    ]
    for col in keep:
        if col not in p.columns:
            p[col] = "" if col in text_cols else np.nan

    p["game_id"] = p["game_id"].astype(str)
    p["player_key"] = p["player_key"].astype(str)
    p["PROJ_PTS"] = pd.to_numeric(p["PROJ_PTS"], errors="coerce")
    p["PROJ_MIN"] = pd.to_numeric(p["PROJ_MIN"], errors="coerce")

    # Keep only plausible active projection rows. This is presentation hygiene,
    # not a model/qualification gate and does not touch production ranking.
    status = p["DESIGNATION"].astype(str).str.upper().str.strip()
    bad = status.isin({"OUT", "INACTIVE", "DOUBTFUL"})
    p = p.loc[~bad & p["PROJ_PTS"].notna() & p["PROJ_PTS"].gt(0)].copy()
    if p.empty:
        return pd.DataFrame()

    # Deterministic PRE-MARKET DISPLAY order only. Once exact pairs exist the
    # original production candidate path below takes over unchanged.
    p = p.sort_values(
        ["PROJ_PTS", "PROJ_MIN", "PLAYER_NAME"],
        ascending=[False, False, True],
        kind="mergesort",
    ).drop_duplicates(["game_id", "player_key"], keep="first").head(5)

    out = p[keep].copy()
    out["player"] = out["PLAYER_NAME"].astype(str)
    out["line"] = np.nan
    out["books"] = ""
    out["book_count"] = 0
    out["Proj PTS"] = out["PROJ_PTS"]
    out["Proj MIN"] = out["PROJ_MIN"]
    out["Delta"] = np.nan
    out["Player"] = out["PLAYER_NAME"].astype(str)
    out["Decision"] = "PRE-MARKET PREVIEW"
    out["_premarket_preview"] = True
    out["_display_rank"] = np.arange(len(out), 0, -1, dtype=float)
    return out.reset_index(drop=True)


def _history_context_market_optional(day: str) -> pd.DataFrame:
    """Use exact-market cards when available; otherwise verified preview cards."""
    try:
        exact = _ORIGINAL_HISTORY_CONTEXT(day)
    except Exception:
        exact = pd.DataFrame()
    if isinstance(exact, pd.DataFrame) and not exact.empty:
        exact = exact.copy()
        exact["_premarket_preview"] = False
        return exact
    return _premarket_history_context(day)


def _candidate_order_market_optional(day: str, context: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(context, pd.DataFrame) or context.empty:
        return pd.DataFrame()
    preview = False
    if "_premarket_preview" in context.columns:
        preview = bool(context["_premarket_preview"].fillna(False).astype(bool).all())
    if not preview:
        return _ORIGINAL_CANDIDATE_ORDER(day, context)

    work = context.copy()
    work["Decision"] = "PRE-MARKET PREVIEW"
    work["_rank"] = pd.to_numeric(work.get("Proj PTS"), errors="coerce").fillna(-999.0)
    return work.sort_values(
        ["_rank", "Proj MIN", "Player"],
        ascending=[False, False, True],
        kind="mergesort",
    )


def _iter_odds(event):
    odds = (event or {}).get("odds") or {}
    if isinstance(odds, dict):
        return list(odds.values())
    if isinstance(odds, list):
        return odds
    return []


def _contains_player_points(events) -> bool:
    for event in events or []:
        for odd in _iter_odds(event):
            if not isinstance(odd, dict):
                continue
            stat = str(odd.get("statID") or "").lower().strip()
            period = str(odd.get("periodID") or "").lower().strip()
            bet = str(odd.get("betTypeID") or "").lower().strip()
            entity = str(odd.get("playerID") or odd.get("statEntityID") or "").lower().strip()
            if stat == "points" and period == "game" and bet == "ou" and entity not in {"", "all", "home", "away"}:
                return True
    return False


@st.cache_data(ttl=90, show_spinner=False, max_entries=16)
def _fetch_points_events_verified(api_key: str, starts_after: str, starts_before: str):
    """Do not accept a 200 response until actual player Points odds are present."""
    headers = {"x-api-key": str(api_key)}
    common = {
        "leagueID": "WNBA",
        "oddsAvailable": "true",
        "startsAfter": str(starts_after),
        "startsBefore": str(starts_before),
        "includeAltLines": "false",
        "limit": 100,
        # bookmakerID intentionally omitted so a restricted book cannot reject
        # the entire request. The V1.9.8.4.31 parser filters target books locally.
    }
    over = "points-PLAYER_ID-game-ou-over"
    both = "points-PLAYER_ID-game-ou-over,points-PLAYER_ID-game-ou-under"
    attempts = (
        {**common, "oddIDs": over, "includeOpposingOdds": "true"},
        {**common, "oddIDs": both},
        {**common, "oddID": both, "includeOpposingOdds": "true"},
        common,
    )

    last_data = []
    last_response = None
    for params in attempts:
        response = requests.get(
            f"{sgo1.SGO_BASE}/events",
            params=params,
            headers=headers,
            timeout=20,
        )
        last_response = response
        if response.status_code != 200:
            if response.status_code in {400, 403, 404, 422, 504}:
                continue
            response.raise_for_status()

        try:
            payload = response.json()
        except Exception:
            payload = {}
        data = payload.get("data") if isinstance(payload, dict) else None
        data = data if isinstance(data, list) else []
        last_data = data
        if _contains_player_points(data):
            return data

    # A valid event response with zero Points props means the market may truly be
    # absent/closed. Return it fail-closed so readiness correctly remains locked.
    if last_data:
        return last_data
    if last_response is not None and last_response.status_code != 200:
        last_response.raise_for_status()
    return []


def _install() -> None:
    # This is the key fix: the Top-5 audit-card candidate source is no longer
    # sportsbook-gated. All later Step 3-12 modules dynamically reuse these h2h
    # functions, so one patch restores the complete existing same-card stack.
    h2h._history_context_rows = _history_context_market_optional
    h2h._candidate_order = _candidate_order_market_optional

    # Harden only the Points-private market fetch used by V1.9.8.4.31.
    prior._fetch_points_events_tier_safe = _fetch_points_events_verified


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    st.caption(
        "🧩 Points V1.9.8.4.32 • Top-5 Steps 2–12 no longer depend on sportsbook availability • "
        "PRE-MARKET cards use verified Points projections only • no fake line/odds/edge • "
        "5M remains locked until real exact pairs pass every production gate"
    )
    return prior.render_wnba_points_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    try:
        return getattr(prior, name)
    except AttributeError:
        return getattr(base, name)


__all__ = [
    "MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH",
    "POINTS_FROZEN_BRANCH", "POINTS_FROZEN_COMMIT", "v171", "ui", "points",
    "render_wnba_points_hub",
]
