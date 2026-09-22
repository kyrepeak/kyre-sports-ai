"""MLB Daily Game Picks V1.5.1 — resilient full-slate 1+ Hit connector.

Preserves the existing MLB Daily Rankings V2.1 / 1+ Hit production fast scanner
at 20K simulations per eligible hitter. This layer changes orchestration only:
- resilient confirmed/projected lineup intake with stale-empty cache recovery
- successful production outputs are preserved in session state
- partial scans expose modeled / eligible / remaining counts
- CONTINUE retries only games containing still-missing eligible hitters
- no hit probability, calibration, reliability, matchup, environment, bullpen,
  or sportsbook logic is reimplemented or weakened.
"""
from __future__ import annotations

import time
import streamlit as st

import mlb_daily_game_picks_v15 as base
import mlb_hit_hub_v133 as hit133
import slate_lineup_v204 as lineup

hitprod = base.base.hitprod
VERSION = "MLB Daily Game Picks V1.5.1 • FULL-SLATE 1+ HIT CONNECTOR"
_ACTIVE_GAMES = None
_orig_pool = hit133._candidate_pool


def _day(games):
    return base._day(games)


def _key(games):
    # Keep V1.5's original key because V1.4's production candidate bridge reads it.
    return base._key(games)


def _safe_int(v):
    try:
        return int(v)
    except Exception:
        return None


def _ckey(row):
    return (_safe_int(row.get("game_pk")), _safe_int(row.get("player_id")))


def _clear_lineup_caches():
    for fn_name in ("_fetch_lineups_bulk", "_fetch_game_feed", "_recent_team_games"):
        fn = getattr(lineup, fn_name, None)
        clear = getattr(fn, "clear", None)
        if callable(clear):
            try:
                clear()
            except Exception:
                pass


def _candidate_pool_resilient(games, include_live=False):
    """Retry only the impossible actionable-games / zero-lineup state."""
    last_meta = {}
    for attempt in range(3):
        candidates, meta = _orig_pool(games, include_live=bool(include_live))
        candidates = list(candidates or [])
        meta = dict(meta or {})
        meta["lineup_intake_attempt"] = attempt + 1
        last_meta = meta
        if candidates:
            meta["lineup_context_unavailable"] = False
            return candidates, meta

        checked = int(meta.get("checked", 0) or 0)
        usable = int(meta.get("usable_games", 0) or 0)
        if checked == 0:
            return candidates, meta
        if usable == 0 and attempt < 2:
            _clear_lineup_caches()
            time.sleep(1.5 * (attempt + 1))
            continue
        break

    last_meta = dict(last_meta or {})
    if int(last_meta.get("checked", 0) or 0) > 0 and int(last_meta.get("usable_games", 0) or 0) == 0:
        last_meta["lineup_context_unavailable"] = True
    return [], last_meta


# The V2.1 production scanner eventually resolves this shared module function.
# Patching intake here changes only data recovery, not any probability math.
hit133._candidate_pool = _candidate_pool_resilient


def _subset_games(games, game_pks):
    wanted = {int(x) for x in game_pks if x is not None}
    if games is None or getattr(games, "empty", True) or not wanted:
        return games
    try:
        mask = games["game_pk"].apply(lambda x: _safe_int(x) in wanted)
        return games.loc[mask].copy()
    except Exception:
        return games


def _run_scan(games):
    rows, diag = hitprod.fast_scan(games, "1+ Hit", 20_000, True)
    return [dict(r) for r in (rows or [])], dict(diag or {})


def _build(games, previous=None):
    pool, pool_meta = _candidate_pool_resilient(games, include_live=True)
    pool = list(pool or [])
    expected = {_ckey(c): c for c in pool if all(x is not None for x in _ckey(c))}

    if not expected:
        msg = (
            "1+ Hit lineup context is temporarily unavailable from MLB after 3 verified retries. "
            "No hitter was excluded or fabricated; retry CONNECT 1+ HIT when MLB data responds."
            if dict(pool_meta or {}).get("lineup_context_unavailable")
            else "No eligible verified/projected 1+ Hit hitter candidates were available."
        )
        return {
            "rows": [], "candidate_count": 0, "modeled_count": 0,
            "remaining_count": 0, "complete": False,
            "diag": {"pool_info": dict(pool_meta or {}), "errors": 0},
            "missing": [], "errors": [msg], "sim_depth": 20_000,
        }

    kept = {}
    if previous and not previous.get("complete"):
        for r in previous.get("rows", []) or []:
            key = _ckey(r)
            if key in expected:
                kept[key] = dict(r)

    missing_keys = [k for k in expected if k not in kept]
    if previous and missing_keys:
        scan_games = _subset_games(games, [k[0] for k in missing_keys])
    else:
        scan_games = games

    rows, diag = _run_scan(scan_games)
    missing_set = set(missing_keys)
    for r in rows:
        key = _ckey(r)
        if key not in expected:
            continue
        if previous and missing_set and key not in missing_set:
            # Preserve the already-completed production output exactly as saved.
            continue
        kept[key] = r

    remaining_keys = [k for k in expected if k not in kept]
    missing = []
    for key in remaining_keys[:40]:
        c = expected.get(key) or {}
        missing.append({
            "game_pk": key[0],
            "player_id": key[1],
            "player": str(c.get("player_name") or f"Player {key[1]}"),
            "team": str(c.get("team") or ""),
        })

    merged = list(kept.values())
    merged.sort(
        key=lambda x: (
            float(x.get("p") or 0),
            float(x.get("reliability") or 0),
            1 if x.get("confirmed") else 0,
        ),
        reverse=True,
    )

    out_diag = dict(diag or {})
    out_diag["pool_info"] = dict(pool_meta or {})
    out_diag["eligible_full_slate"] = len(expected)
    out_diag["modeled_saved"] = len(merged)
    out_diag["remaining"] = len(remaining_keys)

    errors = []
    scan_errors = int(diag.get("errors", 0) or 0)
    if remaining_keys:
        errors.append(
            f"V2.1 production scan still has {len(remaining_keys)} eligible hitter(s) missing after this pass. "
            "Tap CONTINUE 1+ HIT to retry only games containing the missing hitters; completed outputs are preserved."
        )
    if scan_errors:
        errors.append(f"V2.1 reported {scan_errors} production profile error(s) during the latest pass.")

    return {
        "rows": merged,
        "candidate_count": len(expected),
        "modeled_count": len(merged),
        "remaining_count": len(remaining_keys),
        "complete": len(remaining_keys) == 0,
        "diag": out_diag,
        "missing": missing,
        "errors": errors,
        "sim_depth": 20_000,
    }


def render_daily_game_picks(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    global _ACTIVE_GAMES
    _ACTIVE_GAMES = games_df
    # V1.5's cached lookup and V1.4's bridge each own an active-game pointer.
    base._ACTIVE_GAMES = games_df
    base.base._ACTIVE_GAMES = games_df

    day = _day(games_df)
    key = _key(games_df)
    pack = st.session_state.get(key)

    c1, c2 = st.columns([4, 1])
    with c1:
        if pack and pack.get("complete") and pack.get("rows"):
            st.success(
                f"⚡ 1+ Hit production connector ready • {pack.get('modeled_count',0)}/{pack.get('candidate_count',0)} eligible hitters modeled • V2.1 • 20K sims/hitter • {day}"
            )
        elif pack and pack.get("modeled_count"):
            st.warning(
                f"⚡ 1+ Hit partial slate saved • {pack.get('modeled_count',0)}/{pack.get('candidate_count',0)} hitters modeled • {pack.get('remaining_count',0)} remaining • completed outputs preserved"
            )
        else:
            st.info(
                "⚡ 1+ Hit connector is ready to build. Tap CONNECT once; the existing V2.1 full-slate production fast scan will run on demand."
            )

    with c2:
        if pack and pack.get("modeled_count") and not pack.get("complete"):
            label = "▶ CONTINUE 1+ HIT"
        elif pack and pack.get("complete") and pack.get("rows"):
            label = "↻ REFRESH 1+ HIT"
        else:
            label = "⚡ CONNECT 1+ HIT"

        if st.button(label, use_container_width=True, key=f"dgp_hit_connect_v151::{day}"):
            resume = pack if pack and pack.get("modeled_count") and not pack.get("complete") else None
            st.toast("⚡ 1+ Hit V2.1 scan started" if resume is None else "⚡ Resuming missing 1+ Hit hitters")
            status = st.status("1+ Hit connector is working…", expanded=True)
            status.write(
                "Running the unchanged V2.1 production fast scanner at 20K simulations per eligible hitter. Successful outputs are preserved across partial retries."
            )
            try:
                st.session_state[key] = _build(games_df, resume)
                built = st.session_state[key]
                if built.get("complete"):
                    status.update(
                        label=f"1+ Hit complete — {built.get('modeled_count',0)}/{built.get('candidate_count',0)} hitters modeled",
                        state="complete", expanded=False,
                    )
                elif built.get("modeled_count"):
                    status.update(
                        label=f"1+ Hit partial — {built.get('remaining_count',0)} hitters remaining",
                        state="complete", expanded=True,
                    )
                else:
                    status.update(label="1+ Hit finished with no completed hitter models", state="error", expanded=True)
            except Exception as exc:
                st.session_state[key] = {
                    "rows": [], "candidate_count": 0, "modeled_count": 0,
                    "remaining_count": 0, "complete": False,
                    "diag": {"error": f"{type(exc).__name__}: {exc}"},
                    "errors": [f"{type(exc).__name__}: {exc}"],
                }
                status.update(label=f"1+ Hit error: {type(exc).__name__}", state="error", expanded=True)
            st.rerun()

    if pack and pack.get("errors"):
        with st.expander(f"⚠️ 1+ Hit connector diagnostics ({len(pack['errors'])})"):
            for err in pack["errors"]:
                st.caption(str(err))
            if pack.get("missing"):
                st.caption("Missing eligible hitters (first 40):")
                for item in pack["missing"]:
                    st.caption(f"• {item.get('player')} • {item.get('team')} • MLB Game ID {item.get('game_pk')}")

    st.caption(
        "🔌 Step 4A V1.5.1: 1+ Hit remains directly connected to the existing V2.1 production fast scanner at 20K simulations per eligible hitter. The connector now validates full-slate eligible coverage and preserves successful outputs across retries; probability and calibration math are unchanged."
    )

    # Skip V1.5's older one-shot UI and continue directly into V1.4's candidate bridge.
    return base.base.render_daily_game_picks(
        games_df, section_header, status_info, team_logo, h
    )
