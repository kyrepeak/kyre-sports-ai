"""WNBA Points V1.9.8.4.29 — pre-market readiness semantics repair.

Presentation/readiness-only wrapper over V1.9.8.4.28.

The production Points model is intentionally unchanged. This repair fixes a UI /
preflight deadlock exposed when the WNBA schedule and current rosters are healthy
but SportsGameOdds has not posted any exact player Points pairs yet.

Previously V1.9.8.4.4 made the roster gate depend on at least one matched
projection+market player, so a slate with 6/6 verified current-roster teams but
zero posted Points props displayed ROSTER HANDOFF NOT READY. The position and
history panels also rendered 0/0 as a hard failure/pass even though there was no
player market sample to evaluate.

V1.9.8.4.29 separates those states:
- roster verification is market-independent;
- zero exact Points props is shown as MARKET PENDING, not a roster failure;
- history and positional matchup gates are PENDING until exact player matches
  exist, rather than falsely PASSING or FAILING at 0/0;
- the actual 5M readiness contract remains fail-closed and still requires exact
  market pairs, matched projections, verified history, positional verification,
  sanity checks and all inherited production gates.

No projection, minutes, matchup factor, empirical variance, SportsGameOdds
transport, no-vig math, Monte Carlo, calibration, quarantine, ranking, Top-5
ordering, PRA, Rebounds, Assists, Spread, MLB or NFL logic is changed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_hub_v198428 as prior
import wnba_points_hub_v19844 as readiness

base = prior.base
v171 = base.v171
ui = base.ui
points = base.points

MODEL_VERSION = "WNBA POINTS V1.9.8.4.29 • PRE-MARKET READINESS SEMANTICS REPAIR"
PRA_FROZEN_BRANCH = base.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = base.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = base.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = base.POINTS_FROZEN_COMMIT

# Keep stable references across Streamlit hot reloads.
_ORIG_ROSTER_GATE = getattr(
    readiness, "_kyre_v198429_orig_roster_gate", readiness._roster_gate
)
_ORIG_HISTORY_GATE = getattr(
    readiness, "_kyre_v198429_orig_history_gate", readiness._history_gate_with_position
)
setattr(readiness, "_kyre_v198429_orig_roster_gate", _ORIG_ROSTER_GATE)
setattr(readiness, "_kyre_v198429_orig_history_gate", _ORIG_HISTORY_GATE)


def _num(value, default=0):
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _roster_gate_market_independent(day: str, supplied_diag=None) -> dict:
    """Verify roster transport without requiring a sportsbook player prop first."""
    out = dict(_ORIG_ROSTER_GATE(day, supplied_diag) or {})

    pool = pd.DataFrame()
    pdiag = supplied_diag if isinstance(supplied_diag, dict) else {}
    try:
        p, d = readiness.points.corrected_player_pool(day)
        pool = p if isinstance(p, pd.DataFrame) else pd.DataFrame()
        if isinstance(d, dict):
            pdiag = d
    except Exception:
        pass

    teams = int(out.get("teams") or pdiag.get("teams") or 0)
    official = int(out.get("official") or pdiag.get("official_roster_teams") or 0)
    proxy = int(out.get("proxy") or pdiag.get("proxy_roster_teams") or 0)
    missing = int(out.get("missing") or pdiag.get("missing_roster_teams") or 0)
    unmatched = int(out.get("unverified_matched") or 0)
    proxy_short = int(out.get("proxy_short_teams") or 0)
    matched_players = int(out.get("matched_players") or 0)

    modes_raw = out.get("team_modes") or pdiag.get("team_modes") or {}
    modes = {}
    for k, v in dict(modes_raw).items():
        try:
            modes[int(k)] = str(v or "").upper()
        except Exception:
            continue

    allowed = {"CURRENT_ROSTER", "RECENT_ACTIVE_PROXY"}
    all_modes_safe = bool(
        teams > 0 and len(modes) >= teams and all(mode in allowed for mode in modes.values())
    )
    full_team_coverage = bool(teams > 0 and missing == 0 and official + proxy == teams)

    # Roster readiness is about roster identity/coverage. If the market has not
    # posted a Points prop yet, matched_players can legitimately be zero and must
    # not turn a healthy 6/6 roster feed red. Once matched players exist, the
    # inherited unmatched-player firewall still applies unchanged.
    roster_ready = bool(
        full_team_coverage
        and all_modes_safe
        and proxy_short == 0
        and unmatched == 0
    )

    pool_players = int(len(pool)) if not pool.empty else int(pdiag.get("players") or 0)
    pool_teams = 0
    if not pool.empty and "TEAM_ID" in pool.columns:
        pool_teams = int(pd.to_numeric(pool["TEAM_ID"], errors="coerce").dropna().nunique())

    out.update({
        "ready": roster_ready,
        "state": (
            "VERIFIED_CURRENT" if roster_ready and proxy == 0
            else "VERIFIED_RECENT_ACTIVE" if roster_ready
            else "CHECK"
        ),
        "teams": teams,
        "official": official,
        "proxy": proxy,
        "missing": missing,
        "unverified_matched": unmatched,
        "proxy_short_teams": proxy_short,
        "matched_players": matched_players,
        "team_modes": modes,
        "pool_players": pool_players,
        "pool_teams": pool_teams,
        "market_pending": matched_players == 0,
    })
    return out


def _history_gate_market_aware(day):
    """Preserve the real history/position gates, but label the no-market state pending."""
    h = dict(_ORIG_HISTORY_GATE(day) or {})
    pg = dict(h.get("position_gate") or {})
    expected = int(h.get("expected") or 0)
    position_expected = int(pg.get("expected") or 0)
    pending = bool(expected == 0 and position_expected == 0)
    h["market_pending"] = pending
    pg["market_pending"] = pending
    h["position_gate"] = pg
    # Do not claim verification at 0/0. The final readiness snapshot below will
    # keep the 5M button locked until real matched market players exist.
    if pending:
        h["ready"] = False
        pg["ready"] = False
    return h


def _readiness_snapshot_market_aware(day, pdiag):
    # Use the same inherited coverage snapshot V1.9.8.4.4 used, then attach the
    # repaired roster/history semantics. No projection or market values change.
    info = dict(readiness.prior.prior._readiness_snapshot_safe(day) or {})
    roster = _roster_gate_market_independent(str(day), pdiag)
    history = _history_gate_market_aware(day)

    active_games = int(info.get("active_games") or 0)
    market_players = int(info.get("market_players") or 0)
    matched_players = int(info.get("matched_players") or 0)
    eligible_pairs = int(info.get("eligible_pairs") or 0)
    market_ready = bool(
        active_games > 0
        and market_players > 0
        and matched_players > 0
        and eligible_pairs > 0
    )

    info["roster_gate"] = roster
    info["roster_ready"] = bool(roster.get("ready"))
    info["history_gate"] = history
    info["market_ready"] = market_ready
    info["market_pending"] = bool(market_players == 0)

    # Fail closed. Pending history is never sufficient to run 5M; it only stops
    # the page from misdiagnosing an absent sportsbook market as bad roster data.
    info["ready"] = bool(
        info.get("ready")
        and market_ready
        and roster.get("ready")
        and history.get("ready")
    )
    return info


def _render_readiness_market_aware(info):
    st.markdown("### 🧪 Pre-Simulation Readiness")
    h = info.get("history_gate") or {}
    r = info.get("roster_gate") or {}
    pg = h.get("position_gate") or {}

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Eligible games", info.get("active_games", 0))
    c2.metric(
        "Projection ↔ market matches",
        f"{info.get('matched_players',0)}/{info.get('market_players',0)}",
    )
    c3.metric("Exact eligible pairs", info.get("eligible_pairs", 0))
    c4.metric("Verified history", f"{h.get('verified',0)}/{h.get('expected',0)}")

    if info.get("error"):
        st.error(f"Preflight could not complete: {info['error']}")
        return

    if r.get("ready"):
        if int(r.get("proxy") or 0) > 0:
            st.warning(
                "⚠️ VERIFIED RECENT-ACTIVE ROSTER FALLBACK • "
                f"{r.get('official',0)} official + {r.get('proxy',0)} proxy / {r.get('teams',0)} teams • "
                f"{r.get('pool_players',0)} effective roster players."
            )
        else:
            st.success(
                "✅ CURRENT ROSTER HANDOFF VERIFIED • "
                f"{r.get('official',0)}/{r.get('teams',0)} slate teams • "
                f"{r.get('pool_players',0)} current roster players."
            )
    else:
        st.error(
            "⛔ ROSTER HANDOFF NOT READY • "
            f"official {r.get('official',0)} + recent-active {r.get('proxy',0)} / {r.get('teams',0)} teams • "
            f"missing {r.get('missing',0)} • unmatched simulatable players {r.get('unverified_matched',0)}."
        )

    market_players = int(info.get("market_players") or 0)
    matched_players = int(info.get("matched_players") or 0)
    eligible_pairs = int(info.get("eligible_pairs") or 0)

    if market_players == 0:
        st.warning(
            "⏳ EXACT POINTS MARKET PENDING • schedule and roster transport are healthy, "
            "but SportsGameOdds currently has no exact player Points O/U pairs matched to this upcoming slate. "
            "The 5M button correctly stays locked until real sportsbook lines arrive."
        )
        st.info(
            "ℹ️ HISTORY + POSITION CHECKS ARE WAITING FOR MARKET PLAYERS • 0/0 is PENDING, not a failure. "
            "Those player-level integrity gates activate automatically as soon as exact Points pairs are available."
        )
    elif matched_players == 0 or eligible_pairs == 0:
        st.error(
            "⛔ POINTS MARKET / PROJECTION HANDOFF NOT READY • sportsbook player rows exist, "
            "but no exact eligible projection+line pairs survived reconciliation. 5M remains locked."
        )
    else:
        if h.get("missing", 0):
            st.error(
                f"⛔ HISTORY NOT READY • {h.get('missing',0)} established matched player(s) lack verified ≥5-game scoring logs."
            )
        elif h.get("sanity_count", 0):
            st.warning(
                f"⚠️ REVIEW REQUIRED • {h.get('sanity_count',0)} unexplained extreme projection deviation(s) still block 5M."
            )
        elif not pg.get("ready"):
            st.error(
                f"⛔ POSITION MATCHUP NOT READY • {pg.get('neutral',0)} matched player(s) still require a neutral fallback."
            )
        elif info.get("ready"):
            confirmed = int(info.get("lineups_confirmed", 0))
            games = int(info.get("active_games", 0))
            if confirmed < games:
                st.warning(
                    f"⚠️ PRE-LINEUP READY • {confirmed}/{games} upcoming starting fives confirmed. "
                    "5M may run; qualified plays remain MONITOR until explicit starters publish."
                )
            else:
                st.success("✅ PRODUCTION READY • every protected Points gate is satisfied.")
        else:
            st.warning("⚠️ NOT READY FOR 5M • one or more displayed production gates remain unresolved.")

    if h.get("explained_count", 0):
        st.info(
            f"ℹ️ {h.get('explained_count',0)} extreme raw PTS deviation(s) are minute-explained and non-blocking because projected points/minute remains inside the verified ±30% band."
        )

    preview = info.get("preview")
    if isinstance(preview, pd.DataFrame) and not preview.empty:
        with st.expander("📋 Exact Points line + projection preview", expanded=False):
            cols = [c for c in preview.columns if c != "Hist GP"]
            st.dataframe(preview[cols], use_container_width=True, hide_index=True)


def _render_integrity_market_aware(info):
    h = (info or {}).get("history_gate") or {}
    pg = h.get("position_gate") or {}
    pending = bool(h.get("market_pending"))

    st.markdown("### 🧬 Points History Integrity")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Established players", h.get("expected", 0))
    c2.metric("Verified ≥5 GP logs", f"{h.get('verified',0)}/{h.get('expected',0)}")
    c3.metric("Legit short samples", h.get("short_sample", 0))
    c4.metric("History misses", h.get("missing", 0))

    if pending:
        st.info(
            "⏳ HISTORY CHECK PENDING • there are no matched exact Points market players yet, "
            "so there is no player sample to verify. This is not a history pass or failure."
        )
    elif h.get("missing", 0):
        st.error("⛔ EMPIRICAL HISTORY GATE NOT READY • do not run 5M.")
    else:
        st.success(
            "✅ EMPIRICAL HISTORY GATE PASSED • all established matched players have verified prior-game scoring logs."
        )
        if h.get("sanity_count", 0):
            st.warning(
                f"⚠️ PROJECTION SANITY BLOCK • {h.get('sanity_count',0)} unexplained player deviation(s) remain. 5M stays locked."
            )
        else:
            st.success("✅ EXPLAINABLE PROJECTION SANITY GATE PASSED • no unexplained extreme scoring deviations.")
        if h.get("explained_count", 0):
            st.info(
                f"ℹ️ {h.get('explained_count',0)} large raw deviation(s) are explained by verified minutes changes and remain non-blocking."
            )

    st.markdown("### 🎯 Position Matchup Integrity")
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Matched players", pg.get("expected", 0))
    p2.metric("Position verified", f"{pg.get('verified',0)}/{pg.get('expected',0)}")
    p3.metric("Opponent teams", pg.get("teams", 0))
    p4.metric("Neutral fallbacks", pg.get("neutral", 0))

    if pending:
        st.info(
            "⏳ POSITION MATCHUP CHECK PENDING • this gate activates only after an exact Points market player is matched to a projection."
        )
    elif pg.get("error"):
        st.error(f"⛔ Position matchup gate could not complete: {pg['error']}")
    elif pg.get("ready"):
        lo = float(_num(pg.get("min_factor"), 1.0))
        hi = float(_num(pg.get("max_factor"), 1.0))
        st.success(
            "✅ POSITION MATCHUP GATE PASSED • every matched Points player has a verified opponent L10 positional scoring sample. "
            f"Current factor range {lo:.3f}×–{hi:.3f}×."
        )
    else:
        st.error(
            f"⛔ POSITION MATCHUP NOT READY • {pg.get('neutral',0)} matched player(s) still require a neutral fallback. 5M remains locked."
        )


def _install() -> None:
    # V1.9.8.4.4 installs these module-level callables into the exact production
    # renderer each run. Replacing only the callables keeps every downstream
    # projection/MC object identical while fixing the misleading no-market state.
    readiness._roster_gate = _roster_gate_market_independent
    readiness._history_gate_with_position = _history_gate_market_aware
    readiness._readiness_snapshot_unified = _readiness_snapshot_market_aware
    readiness._render_readiness_unified = _render_readiness_market_aware
    readiness._render_integrity_unified = _render_integrity_market_aware


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    st.caption(
        "🧭 Points V1.9.8.4.29 • pre-market readiness semantics repaired • roster verification no longer depends on sportsbook prop availability • model math unchanged"
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
