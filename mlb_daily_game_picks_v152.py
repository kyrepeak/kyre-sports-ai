"""MLB Daily Game Picks V1.5.2 — bounded game-batched 1+ Hit connector.

Preserves the existing MLB Daily Rankings V2.1 / 1+ Hit production fast scanner
at 20K simulations per eligible hitter. This layer changes orchestration only:
- eligible hitter pool and probability/calibration math are unchanged
- each MLB game is scanned through the same V2.1 fast_scan path
- up to 3 games are processed concurrently
- completed game outputs are saved as they finish
- each pass is bounded to 95 seconds
- CONTINUE retries only games containing still-missing eligible hitters
No hit probability, calibration, reliability, matchup, environment, bullpen,
or sportsbook logic is reimplemented or weakened.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
import streamlit as st

import mlb_daily_game_picks_v151 as base

hitprod = base.hitprod
VERSION = "MLB Daily Game Picks V1.5.2 • BOUNDED GAME-BATCHED 1+ HIT CONNECTOR"
_ACTIVE_GAMES = None


def _day(games):
    return base._day(games)


def _key(games):
    return base._key(games)


def _safe_int(v):
    return base._safe_int(v)


def _ckey(row):
    return base._ckey(row)


def _subset_games(games, game_pks):
    return base._subset_games(games, game_pks)


def _scan_one_game(games, game_pk):
    one = _subset_games(games, [game_pk])
    rows, diag = hitprod.fast_scan(one, "1+ Hit", 20_000, True)
    return [dict(r) for r in (rows or [])], dict(diag or {})


def _build(games, previous=None):
    pool, pool_meta = base._candidate_pool_resilient(games, include_live=True)
    pool = list(pool or [])
    expected = {_ckey(c): c for c in pool if all(x is not None for x in _ckey(c))}

    if not expected:
        msg = (
            "1+ Hit lineup context is temporarily unavailable from MLB after verified retries. "
            "No hitter was excluded or fabricated; retry CONNECT 1+ HIT when MLB data responds."
            if dict(pool_meta or {}).get("lineup_context_unavailable")
            else "No eligible verified/projected 1+ Hit hitter candidates were available."
        )
        return {
            "rows": [], "candidate_count": 0, "modeled_count": 0,
            "remaining_count": 0, "complete": False, "completed_games": 0,
            "total_games": 0, "diag": {"pool_info": dict(pool_meta or {})},
            "missing": [], "errors": [msg], "sim_depth": 20_000,
        }

    kept = {}
    prior_errors = []
    if previous and not previous.get("complete"):
        for r in previous.get("rows", []) or []:
            key = _ckey(r)
            if key in expected:
                kept[key] = dict(r)
        for err in previous.get("errors", []) or []:
            text = str(err)
            if "bounded pass" not in text.lower() and "production profile error" not in text.lower():
                prior_errors.append(text)

    missing_keys = [k for k in expected if k not in kept]
    pending_game_pks = sorted({int(k[0]) for k in missing_keys if k[0] is not None})
    all_game_pks = sorted({int(k[0]) for k in expected if k[0] is not None})

    errors = list(prior_errors)
    game_diags = {}
    timed_out = False

    if pending_game_pks:
        completed_game_set = {int(k[0]) for k in kept if k[0] is not None}
        bar = st.progress(
            len(completed_game_set) / max(len(all_game_pks), 1),
            text=f"1+ Hit V2.1: games completed {len(completed_game_set)}/{len(all_game_pks)}",
        )
        pool_exec = ThreadPoolExecutor(max_workers=min(3, len(pending_game_pks)))
        futures = {pool_exec.submit(_scan_one_game, games, pk): pk for pk in pending_game_pks}
        try:
            for fut in as_completed(futures, timeout=95):
                pk = futures[fut]
                try:
                    rows, diag = fut.result()
                    game_diags[str(pk)] = diag
                    for r in rows:
                        key = _ckey(r)
                        if key in expected:
                            kept[key] = r
                    scan_errors = int(diag.get("errors", 0) or 0)
                    if scan_errors:
                        errors.append(
                            f"MLB Game ID {pk}: V2.1 reported {scan_errors} production profile error(s) in this pass."
                        )
                except Exception as exc:
                    errors.append(f"MLB Game ID {pk}: {type(exc).__name__}: {exc}")

                completed_game_set = {
                    int(k[0]) for k in kept if k[0] is not None
                }
                bar.progress(
                    min(1.0, len(completed_game_set) / max(len(all_game_pks), 1)),
                    text=f"1+ Hit V2.1: games completed {len(completed_game_set)}/{len(all_game_pks)}",
                )
        except TimeoutError:
            timed_out = True
            for fut in futures:
                if not fut.done():
                    fut.cancel()
        finally:
            pool_exec.shutdown(wait=False, cancel_futures=True)
            bar.empty()

    remaining_keys = [k for k in expected if k not in kept]
    remaining_game_pks = sorted({int(k[0]) for k in remaining_keys if k[0] is not None})
    completed_games = len(all_game_pks) - len(remaining_game_pks)

    if timed_out and remaining_keys:
        errors.append(
            f"1+ Hit bounded pass ended after 95 seconds with {len(remaining_keys)} hitter(s) across "
            f"{len(remaining_game_pks)} game(s) still missing. Tap CONTINUE 1+ HIT; completed outputs are preserved."
        )
    elif remaining_keys:
        errors.append(
            f"V2.1 still has {len(remaining_keys)} eligible hitter(s) across {len(remaining_game_pks)} game(s) missing. "
            "Tap CONTINUE 1+ HIT to retry only those games; completed outputs are preserved."
        )

    missing = []
    for key in remaining_keys[:40]:
        c = expected.get(key) or {}
        missing.append({
            "game_pk": key[0], "player_id": key[1],
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

    return {
        "rows": merged,
        "candidate_count": len(expected),
        "modeled_count": len(merged),
        "remaining_count": len(remaining_keys),
        "complete": len(remaining_keys) == 0,
        "completed_games": completed_games,
        "total_games": len(all_game_pks),
        "remaining_games": len(remaining_game_pks),
        "timed_out": timed_out,
        "diag": {
            "pool_info": dict(pool_meta or {}),
            "game_diags": game_diags,
            "eligible_full_slate": len(expected),
            "modeled_saved": len(merged),
            "remaining": len(remaining_keys),
        },
        "missing": missing,
        "errors": errors,
        "sim_depth": 20_000,
    }


def render_daily_game_picks(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    global _ACTIVE_GAMES
    _ACTIVE_GAMES = games_df
    base._ACTIVE_GAMES = games_df
    base.base._ACTIVE_GAMES = games_df
    base.base.base._ACTIVE_GAMES = games_df

    day = _day(games_df)
    key = _key(games_df)
    pack = st.session_state.get(key)

    c1, c2 = st.columns([4, 1])
    with c1:
        if pack and pack.get("complete") and pack.get("rows"):
            st.success(
                f"⚡ 1+ Hit production connector ready • {pack.get('modeled_count',0)}/{pack.get('candidate_count',0)} eligible hitters modeled • "
                f"{pack.get('completed_games',0)}/{pack.get('total_games',0)} games complete • V2.1 • 20K sims/hitter • {day}"
            )
        elif pack and pack.get("modeled_count"):
            st.warning(
                f"⚡ 1+ Hit partial slate saved • {pack.get('modeled_count',0)}/{pack.get('candidate_count',0)} hitters modeled • "
                f"{pack.get('completed_games',0)}/{pack.get('total_games',0)} games complete • "
                f"{pack.get('remaining_count',0)} hitters remaining • completed outputs preserved"
            )
        else:
            st.info(
                "⚡ 1+ Hit connector is ready. V2.1 now runs in bounded game batches with visible progress; production probability math is unchanged."
            )

    with c2:
        if pack and pack.get("modeled_count") and not pack.get("complete"):
            label = "▶ CONTINUE 1+ HIT"
        elif pack and pack.get("complete") and pack.get("rows"):
            label = "↻ REFRESH 1+ HIT"
        else:
            label = "⚡ CONNECT 1+ HIT"

        if st.button(label, use_container_width=True, key=f"dgp_hit_connect_v152::{day}"):
            resume = pack if pack and pack.get("modeled_count") and not pack.get("complete") else None
            st.toast("⚡ 1+ Hit V2.1 batched scan started" if resume is None else "⚡ Resuming missing 1+ Hit games")
            status = st.status("1+ Hit connector is working…", expanded=True)
            status.write(
                "Running the unchanged V2.1 production fast scanner at 20K simulations per eligible hitter, game by game. "
                "Completed game outputs are preserved immediately and each pass is bounded to 95 seconds."
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
                        label=f"1+ Hit partial — {built.get('remaining_count',0)} hitters in {built.get('remaining_games',0)} games remaining",
                        state="complete", expanded=True,
                    )
                else:
                    status.update(label="1+ Hit pass ended with no completed hitter models", state="error", expanded=True)
            except Exception as exc:
                st.session_state[key] = {
                    "rows": [], "candidate_count": 0, "modeled_count": 0,
                    "remaining_count": 0, "complete": False,
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
        "🔌 Step 4A V1.5.2: 1+ Hit remains directly connected to V2.1 at 20K simulations per eligible hitter. "
        "Execution is now game-batched (up to 3 games concurrently), bounded to 95 seconds per pass, and resumable. "
        "Probability, calibration, reliability, matchup, environment, bullpen, and sportsbook logic are unchanged."
    )

    return base.base.base.render_daily_game_picks(
        games_df, section_header, status_info, team_logo, h
    )
