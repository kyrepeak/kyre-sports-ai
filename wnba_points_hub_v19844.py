"""WNBA Points V1.9.8.4.4 — unified 5M readiness + hardened roster fallback.

Preflight-only wrapper over V1.9.8.4.3. Projection, SportsGameOdds transport,
Monte Carlo, grading, calibration, persistence, PRA, Rebounds, Assists, Spread
and MLB math are unchanged.

Repairs two readiness deadlocks:
1) the button and diagnostics could consult different inherited gate objects;
   V1.9.8.4.4 installs one readiness contract into the exact V1.7 renderer that
   owns the production button;
2) the old roster gate required an ESPN CURRENT_ROSTER result for every slate
   team even though the Points player-pool code already has a hard-gated
   RECENT_ACTIVE_PROXY fallback built from the last three completed WNBA games.
   Expansion/new-provider teams can therefore be fully covered yet permanently
   fail preflight.

The proxy is accepted only when ALL slate teams are covered, every proxy team has
at least five effective roster players, every simulatable market+projection player
is in the effective roster, and the source mode is explicitly CURRENT_ROSTER or
RECENT_ACTIVE_PROXY. Missing teams or unmatched simulated players still block 5M.

The V1.9 positional matchup gate is also restored into the explainable history
contract so this repair does not weaken matchup verification.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_hub_v19843 as prior

MODEL_VERSION = "WNBA POINTS V1.9.8.4.4 • UNIFIED 5M READINESS"
PRA_FROZEN_BRANCH = prior.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = prior.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = prior.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = prior.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = prior.POINTS_FROZEN_COMMIT

v171 = prior.v171
ui = prior.ui
points = ui.points
v19 = prior.prior.v19


def _num(value, default=np.nan):
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _key_pairs(frame: pd.DataFrame) -> set[tuple[int, int]]:
    out = set()
    if frame is None or frame.empty or not {"TEAM_ID", "PLAYER_ID"}.issubset(frame.columns):
        return out
    for _, r in frame.iterrows():
        try:
            out.add((int(float(r.get("TEAM_ID"))), int(float(r.get("PLAYER_ID")))))
        except Exception:
            continue
    return out


def _matched_projection_rows(day: str) -> pd.DataFrame:
    try:
        projections, pairs, _snap, _meta, _lineups = points._prepare(day)
    except Exception:
        return pd.DataFrame()
    if not isinstance(projections, pd.DataFrame) or projections.empty:
        return pd.DataFrame()
    if not isinstance(pairs, pd.DataFrame) or pairs.empty:
        return pd.DataFrame()
    if not {"game_id", "player_key"}.issubset(projections.columns) or not {"game_id", "player_key"}.issubset(pairs.columns):
        return pd.DataFrame()
    p = projections.copy()
    q = pairs[["game_id", "player_key"]].drop_duplicates().copy()
    p["game_id"] = p["game_id"].astype(str)
    p["player_key"] = p["player_key"].astype(str)
    q["game_id"] = q["game_id"].astype(str)
    q["player_key"] = q["player_key"].astype(str)
    return q.merge(p, on=["game_id", "player_key"], how="inner").drop_duplicates(["game_id", "player_key"])


def _roster_gate(day: str, supplied_diag=None) -> dict:
    try:
        pool, pdiag = points.corrected_player_pool(day)
    except Exception as exc:
        return {
            "ready": False, "state": "ERROR", "reason": f"{type(exc).__name__}: {exc}",
            "teams": 0, "official": 0, "proxy": 0, "missing": 0,
            "matched_players": 0, "unverified_matched": 0, "proxy_short_teams": 0,
        }
    pool = pool if isinstance(pool, pd.DataFrame) else pd.DataFrame()
    pdiag = pdiag if isinstance(pdiag, dict) else (supplied_diag if isinstance(supplied_diag, dict) else {})

    teams = int(pdiag.get("teams") or 0)
    official = int(pdiag.get("official_roster_teams") or 0)
    proxy = int(pdiag.get("proxy_roster_teams") or 0)
    missing = int(pdiag.get("missing_roster_teams") or 0)
    modes_raw = pdiag.get("team_modes") or {}
    modes = {}
    for k, v in modes_raw.items():
        try:
            modes[int(k)] = str(v or "").upper()
        except Exception:
            continue

    matched = _matched_projection_rows(day)
    matched_keys = _key_pairs(matched)
    pool_keys = _key_pairs(pool)
    unverified_matched = len(matched_keys - pool_keys)

    counts = {}
    if not pool.empty and "TEAM_ID" in pool.columns:
        tids = pd.to_numeric(pool["TEAM_ID"], errors="coerce").dropna().astype(int)
        counts = tids.value_counts().to_dict()

    allowed_modes = {"CURRENT_ROSTER", "RECENT_ACTIVE_PROXY"}
    all_modes_safe = bool(teams > 0 and len(modes) >= teams and all(m in allowed_modes for m in modes.values()))
    proxy_short = sum(1 for tid, mode in modes.items() if mode == "RECENT_ACTIVE_PROXY" and int(counts.get(tid, 0)) < 5)
    full_team_coverage = bool(teams > 0 and missing == 0 and official + proxy == teams)
    ready = bool(
        full_team_coverage
        and all_modes_safe
        and proxy_short == 0
        and len(matched_keys) > 0
        and unverified_matched == 0
    )
    state = "VERIFIED_CURRENT" if ready and proxy == 0 else ("VERIFIED_RECENT_ACTIVE" if ready else "CHECK")
    return {
        "ready": ready,
        "state": state,
        "teams": teams,
        "official": official,
        "proxy": proxy,
        "missing": missing,
        "matched_players": len(matched_keys),
        "unverified_matched": int(unverified_matched),
        "proxy_short_teams": int(proxy_short),
        "team_modes": modes,
        "source": str(pdiag.get("source") or "—"),
    }


def _history_gate_with_position(day):
    h = dict(prior._history_gate_explainable(day) or {})
    try:
        pg = v19._position_gate(day)
    except Exception as exc:
        pg = {"ready": False, "error": f"{type(exc).__name__}: {exc}"}
    h["position_gate"] = pg
    h["ready"] = bool(h.get("ready") and pg.get("ready"))
    return h


def _readiness_snapshot_unified(day, pdiag):
    info = dict(prior.prior._readiness_snapshot_safe(day) or {})
    roster = _roster_gate(str(day), pdiag)
    history = _history_gate_with_position(day)
    info["roster_gate"] = roster
    info["roster_ready"] = bool(roster.get("ready"))
    info["history_gate"] = history
    info["ready"] = bool(info.get("ready") and roster.get("ready") and history.get("ready"))
    return info


def _render_readiness_unified(info):
    st.markdown("### 🧪 Pre-Simulation Readiness")
    h = info.get("history_gate") or {}
    r = info.get("roster_gate") or {}
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Eligible games", info.get("active_games", 0))
    c2.metric("Projection coverage", f"{info.get('matched_players',0)}/{info.get('market_players',0)} raw")
    c3.metric("Exact eligible pairs", info.get("eligible_pairs", 0))
    c4.metric("Verified history", f"{h.get('verified',0)}/{h.get('expected',0)} established")

    if info.get("error"):
        st.error(f"Preflight could not complete: {info['error']}")
        return

    if not r.get("ready"):
        st.error(
            "⛔ ROSTER HANDOFF NOT READY • "
            f"official {r.get('official',0)} + recent-active {r.get('proxy',0)} / {r.get('teams',0)} teams • "
            f"missing {r.get('missing',0)} • unmatched simulatable players {r.get('unverified_matched',0)}."
        )
    elif r.get("proxy", 0):
        st.warning(
            f"⚠️ VERIFIED RECENT-ACTIVE ROSTER FALLBACK • {r.get('proxy',0)} team(s) are using the hard-gated last-3-game active roster because the current-roster endpoint is unavailable. "
            "Every simulatable Points player is roster-matched; 5M may run."
        )
    else:
        st.success("✅ CURRENT ROSTER HANDOFF VERIFIED • every simulatable Points player is on a current roster.")

    if h.get("missing", 0):
        st.error(f"⛔ HISTORY NOT READY • {h.get('missing',0)} established matched player(s) lack verified ≥5-game scoring logs.")
    elif h.get("sanity_count", 0):
        st.warning(f"⚠️ REVIEW REQUIRED • {h.get('sanity_count',0)} unexplained extreme projection deviation(s) still block 5M.")
    elif info.get("ready"):
        confirmed = int(info.get("lineups_confirmed", 0))
        games = int(info.get("active_games", 0))
        if confirmed < games:
            st.warning(
                f"⚠️ PRE-LINEUP READY • {confirmed}/{games} upcoming starting fives confirmed. 5M may run; qualified plays remain MONITOR until explicit starters publish."
            )
        else:
            st.success("✅ PRODUCTION READY • the exact button gate is fully satisfied.")
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


def _render_integrity_unified(info):
    prior._render_integrity_explainable(info)
    pg = ((info or {}).get("history_gate") or {}).get("position_gate") or {}
    st.markdown("### 🎯 Position Matchup Integrity")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Matched players", pg.get("expected", 0))
    c2.metric("Position verified", f"{pg.get('verified',0)}/{pg.get('expected',0)}")
    c3.metric("Opponent teams", pg.get("teams", 0))
    c4.metric("Neutral fallbacks", pg.get("neutral", 0))
    if pg.get("error"):
        st.error(f"⛔ Position matchup gate could not complete: {pg['error']}")
    elif pg.get("ready"):
        lo = _num(pg.get("min_factor"), 1.0)
        hi = _num(pg.get("max_factor"), 1.0)
        st.success(
            f"✅ POSITION MATCHUP GATE PASSED • every matched Points player has a verified opponent L10 positional scoring sample. Current factor range {lo:.3f}×–{hi:.3f}×."
        )
    else:
        st.error(
            f"⛔ POSITION MATCHUP NOT READY • {pg.get('neutral',0)} matched player(s) still require a neutral fallback. 5M remains locked."
        )


def _diagnostics_unified(day):
    try:
        _pool, pdiag = points.corrected_player_pool(day)
        info = _readiness_snapshot_unified(day, pdiag)
        h = info.get("history_gate") or {}
        r = info.get("roster_gate") or {}
        pg = h.get("position_gate") or {}
        return {
            "active_games": int(info.get("active_games") or 0),
            "matched_games": int(info.get("matched_games") or 0),
            "market_players": int(info.get("market_players") or 0),
            "matched_players": int(info.get("matched_players") or 0),
            "excluded_market_players": int(info.get("unmatched_market_players") or 0),
            "eligible_pairs": int(info.get("eligible_pairs") or 0),
            "coverage_ready": bool(prior.prior._readiness_snapshot_safe(day).get("ready")),
            "roster_ready": bool(r.get("ready")),
            "roster_state": str(r.get("state") or "CHECK"),
            "roster_official": int(r.get("official") or 0),
            "roster_proxy": int(r.get("proxy") or 0),
            "roster_teams": int(r.get("teams") or 0),
            "history_ready": bool(h.get("ready")),
            "history_verified": int(h.get("verified") or 0),
            "history_expected": int(h.get("expected") or 0),
            "history_missing": int(h.get("missing") or 0),
            "sanity_holds": int(h.get("sanity_count") or 0),
            "position_ready": bool(pg.get("ready")),
            "button_ready": bool(info.get("ready")),
        }
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def _install_unified():
    # Patch the exact V1.7 module object that owns readiness construction and the
    # exact UI module object that owns the disabled= production button.
    v171._history_gate = _history_gate_with_position
    v171._render_readiness = _render_readiness_unified
    v171._render_integrity = _render_integrity_unified
    v171.base._readiness_snapshot = _readiness_snapshot_unified
    prior.prior._diagnostics = _diagnostics_unified


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    # Install V1.9.8.4.3's explainable-sanity hooks first, then replace only the
    # readiness objects above with the unified contract. Delegate directly to the
    # preserved V1.9.8.4.2 renderer so prior._install() cannot overwrite us again.
    prior._install()
    _install_unified()
    st.caption("🛡️ Points V1.9.8.4.4 • unified 5M button gate + hardened roster fallback ACTIVE")
    return prior.prior.render_wnba_points_hub(section_header, status_info, team_logo, h)


__all__ = [
    "MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH",
    "POINTS_FROZEN_BRANCH", "POINTS_FROZEN_COMMIT", "render_wnba_points_hub",
]
