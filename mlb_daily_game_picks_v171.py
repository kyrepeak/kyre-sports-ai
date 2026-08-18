"""MLB Daily Game Picks V1.7.1 — full-slate H+R+RBI connector.

Preserves the existing H+R+RBI V1.0 joint-event production model, including
three finalists per game and 250K simulations per finalist. This layer changes
only orchestration: profile work is visible, bounded, resumable, and partial
profiles are preserved. Production probability math is unchanged.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
import streamlit as st

import mlb_daily_game_picks_v17 as base
import mlb_hrrbi_hub_v10 as hrr

VERSION = "MLB Daily Game Picks V1.7.1 • FULL-SLATE H+R+RBI CONNECTOR"
_ACTIVE_GAMES = None


def _day(games):
    return base._day(games)


def _key(games):
    # Keep V1.7's original key so its production-candidate bridge reads our rows.
    return base._key(games)


def _ckey(c):
    try:
        gpk = int(c.get("game_pk"))
    except Exception:
        gpk = str(c.get("game_pk") or "")
    try:
        pid = int(c.get("player_id"))
    except Exception:
        pid = str(c.get("player_id") or "")
    return (gpk, pid)


def _is_transient(text):
    t = str(text or "").lower()
    return any(x in t for x in (
        "connecttimeout", "connectiontimeout", "connection timed out",
        "readtimeout", "max retries exceeded", "connectionerror",
        "temporary failure", "safety limit",
    ))


def _profile_one(c):
    try:
        r = hrr._profile_candidate(c)
        return "ok" if r else "skip", r, ""
    except Exception as exc:
        return "error", None, f"{type(exc).__name__}: {exc}"


def _simulate_finalists(profiles):
    by_game = {}
    for r in profiles:
        by_game.setdefault(str(r.get("game_pk") or ""), []).append(r)

    finalists = []
    for _, rows in by_game.items():
        rows = sorted(
            rows,
            key=lambda x: float(x.get("expected_total") or 0),
            reverse=True,
        )[:3]
        finalists.extend(rows)

    deep = []
    errors = []
    total = len(finalists)
    bar = st.progress(0, text=f"H+R+RBI: 250K simulations 0/{total}") if total else None
    for i, r in enumerate(finalists, 1):
        try:
            rr = dict(r)
            rr["sim"] = hrr._simulate(rr, 250_000)
            deep.append(rr)
        except Exception as exc:
            errors.append(
                f"{r.get('player_name') or 'Hitter'}: simulation {type(exc).__name__}: {exc}"
            )
        if bar:
            bar.progress(i / max(total, 1), text=f"H+R+RBI: 250K simulations {i}/{total}")
    if bar:
        bar.empty()
    return deep, errors, total


def _build(games, previous=None):
    try:
        candidates, meta = hrr._candidate_pool(games, False)
    except Exception as exc:
        return {
            "rows": [], "profiles": [], "profile_count": 0,
            "candidate_count": 0, "remaining_count": 0,
            "skipped_count": 0, "complete": False,
            "finalist_count": 0, "meta": {"error": f"{type(exc).__name__}: {exc}"},
            "errors": [f"Candidate pool: {type(exc).__name__}: {exc}"],
            "sim_depth": 250_000,
        }

    candidates = list(candidates or [])
    total = len(candidates)
    if not total:
        return {
            "rows": [], "profiles": [], "profile_count": 0,
            "candidate_count": 0, "remaining_count": 0,
            "skipped_count": 0, "complete": False,
            "finalist_count": 0, "meta": dict(meta or {}),
            "errors": ["No eligible H+R+RBI hitter candidates were available."],
            "sim_depth": 250_000,
        }

    kept = {}
    skipped = set()
    errors = []
    if previous and not previous.get("complete"):
        for r in previous.get("profiles", []) or []:
            kept[_ckey(r)] = r
        for raw in previous.get("skipped_keys", []) or []:
            try:
                skipped.add(tuple(raw))
            except Exception:
                pass
        for err in previous.get("errors", []) or []:
            if not _is_transient(err):
                errors.append(str(err))

    pending = [c for c in candidates if _ckey(c) not in kept and _ckey(c) not in skipped]
    timed_out = False

    if pending:
        done0 = len(kept) + len(skipped)
        bar = st.progress(
            done0 / max(total, 1),
            text=f"H+R+RBI: player profiles {done0}/{total}",
        )
        pool = ThreadPoolExecutor(max_workers=min(12, len(pending)))
        futs = {pool.submit(_profile_one, c): c for c in pending}
        try:
            for fut in as_completed(futs, timeout=120):
                c = futs[fut]
                key = _ckey(c)
                status, result, err = fut.result()
                if status == "ok" and result:
                    kept[key] = result
                elif status == "skip":
                    skipped.add(key)
                else:
                    errors.append(
                        f"{c.get('player_name') or 'Hitter'}: {err or 'profile failed'}"
                    )
                finished = len(kept) + len(skipped)
                bar.progress(
                    min(1.0, finished / max(total, 1)),
                    text=f"H+R+RBI: player profiles {finished}/{total}",
                )
        except TimeoutError:
            timed_out = True
            remaining = max(0, total - len(kept) - len(skipped))
            errors.append(
                f"H+R+RBI profile phase reached the 120-second safety limit with {remaining} hitter(s) remaining. Tap CONTINUE H+R+RBI to finish only the missing profiles; completed profiles are preserved."
            )
            for fut in futs:
                if not fut.done():
                    fut.cancel()
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
            bar.empty()

    profiles = list(kept.values())
    remaining = max(0, total - len(kept) - len(skipped))
    complete = remaining == 0

    rows = []
    sim_errors = []
    finalist_count = 0
    if complete:
        rows, sim_errors, finalist_count = _simulate_finalists(profiles)
        errors.extend(sim_errors)

    return {
        "rows": rows,
        "profiles": profiles,
        "profile_count": len(profiles),
        "candidate_count": total,
        "remaining_count": remaining,
        "skipped_count": len(skipped),
        "skipped_keys": [list(x) for x in skipped],
        "complete": complete,
        "timed_out": timed_out,
        "finalist_count": finalist_count,
        "meta": dict(meta or {}),
        "errors": errors,
        "sim_depth": 250_000,
    }


def render_daily_game_picks(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    global _ACTIVE_GAMES
    _ACTIVE_GAMES = games_df

    # Preserve V1.7's candidate bridge and all lower connectors.
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
                f"🧮 H+R+RBI production connector ready • {pack.get('profile_count',0)}/{pack.get('candidate_count',0)} hitter profiles complete • {len(pack.get('rows',[]))} per-game finalists simulated • 250K sims each • {day}"
            )
        elif pack and (pack.get("profile_count") or pack.get("skipped_count")):
            st.warning(
                f"🧮 H+R+RBI partial slate saved • {pack.get('profile_count',0)} profiles built • {pack.get('remaining_count',0)} remaining • completed profiles preserved"
            )
        else:
            st.info(
                "🧮 H+R+RBI connector is ready to build. Tap CONNECT once; visible full-slate profile progress will begin immediately."
            )

    with c2:
        if pack and not pack.get("complete") and (pack.get("profile_count") or pack.get("skipped_count")):
            label = "▶ CONTINUE H+R+RBI"
        elif pack and pack.get("complete") and pack.get("rows"):
            label = "↻ REFRESH H+R+RBI"
        else:
            label = "🧮 CONNECT H+R+RBI"

        if st.button(label, use_container_width=True, key=f"dgp_hrrbi_connect_v171::{day}"):
            resume = pack if pack and not pack.get("complete") else None
            st.toast(
                "🧮 H+R+RBI build started"
                if resume is None
                else "🧮 Resuming remaining H+R+RBI profiles"
            )
            status = st.status("H+R+RBI connector is working…", expanded=True)
            status.write(
                "Building V1.0 production hitter profiles. Once all eligible profiles finish, the top three finalists per game receive the unchanged 250K joint-event simulation."
            )
            try:
                st.session_state[key] = _build(games_df, resume)
                built = st.session_state[key]
                if built.get("complete"):
                    status.update(
                        label=f"H+R+RBI complete — {len(built.get('rows',[]))} finalists simulated",
                        state="complete",
                        expanded=False,
                    )
                elif built.get("profile_count"):
                    status.update(
                        label=f"H+R+RBI partial — {built.get('remaining_count',0)} profiles remaining",
                        state="complete",
                        expanded=True,
                    )
                else:
                    status.update(
                        label="H+R+RBI finished with no completed profiles",
                        state="error",
                        expanded=True,
                    )
            except Exception as exc:
                st.session_state[key] = {
                    "rows": [], "profiles": [], "profile_count": 0,
                    "candidate_count": 0, "remaining_count": 0,
                    "complete": False,
                    "errors": [f"{type(exc).__name__}: {exc}"],
                }
                status.update(
                    label=f"H+R+RBI error: {type(exc).__name__}",
                    state="error",
                    expanded=True,
                )
            st.rerun()

    if pack and pack.get("skipped_count"):
        st.caption(
            f"ℹ️ {pack.get('skipped_count',0)} hitter candidate(s) had no usable production profile and were safely excluded rather than fabricated."
        )
    if pack and pack.get("errors"):
        with st.expander(f"⚠️ H+R+RBI connector diagnostics ({len(pack['errors'])})"):
            for err in pack["errors"]:
                st.caption(str(err))

    st.caption(
        "🔌 Step 4C V1.7.1: H+R+RBI still uses the existing V1.0 joint-event engine. All eligible hitter profiles are completed first; then three finalists per game are simulated at the unchanged 250K Quick depth. Profile work is bounded to 120 seconds per pass and resumable, so completed profiles are never discarded."
    )

    # Skip V1.7's older H+R+RBI UI and continue into V1.6 lower connectors.
    return base.base.render_daily_game_picks(
        games_df, section_header, status_info, team_logo, h
    )
