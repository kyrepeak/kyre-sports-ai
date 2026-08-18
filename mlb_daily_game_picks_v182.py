"""MLB Daily Game Picks V1.8.2 — full-slate Pitcher K connector.

Preserves the existing Pitcher K V1.0.x workload/opponent-K/Monte-Carlo math at
250K simulations per modeled starter. Adds visible full-slate progress, a longer
bounded profile window, more parallel profile workers, and resumable partial-slate
caching. Only verified posted K lines are graded; no sportsbook threshold is
fabricated and no simulation depth is reduced.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
import streamlit as st
import mlb_daily_game_picks_v18 as base

engine = base.engine
VERSION = "MLB Daily Game Picks V1.8.2 • FULL-SLATE PITCHER K CONNECTOR"
_ACTIVE_GAMES = None


def _day(games):
    return base._day(games)


def _key(games):
    return base._key(games)


def _candidate_key(r):
    try:
        game_pk = int(r.get("game_pk"))
    except Exception:
        game_pk = str(r.get("game_pk") or "")
    try:
        player_id = int(r.get("player_id"))
    except Exception:
        player_id = str(r.get("player_id") or "")
    name = str(r.get("player_name") or "").strip().lower()
    return (game_pk, player_id, name)


def _build(games, previous=None):
    active = base._active_rows(games)
    try:
        ctx = engine.build_slate_player_context(games)
    except Exception:
        ctx = {}

    candidates = []
    for row in active:
        for side in ("away", "home"):
            try:
                c = engine._build_pitcher_candidate(row, side, ctx)
            except Exception:
                c = None
            if c:
                candidates.append(c)

    total = len(candidates)
    if not total:
        return {
            "rows": [], "projected": [], "projected_count": 0,
            "candidate_count": 0, "remaining_count": 0, "complete": False,
            "unposted_count": 0, "market_meta": {"connected": False},
            "errors": ["No eligible verified pregame starting pitchers were available."],
            "sim_depth": 250_000,
        }

    kept = {}
    errors = []
    if previous and not previous.get("complete"):
        for r in previous.get("projected", []) or []:
            try:
                kept[_candidate_key(r)] = r
            except Exception:
                pass
        for err in previous.get("errors", []) or []:
            text = str(err)
            if "safety limit" not in text.lower():
                errors.append(text)

    pending = [c for c in candidates if _candidate_key(c) not in kept]
    retained = len(kept)
    profile_timeout = False

    if pending:
        bar = st.progress(
            retained / max(total, 1),
            text=f"Pitcher K: starter profiles {retained}/{total}",
        )
        pool = ThreadPoolExecutor(max_workers=min(12, len(pending)))
        futs = {pool.submit(engine._project_pitcher, c): c for c in pending}
        try:
            for fut in as_completed(futs, timeout=100):
                c = futs[fut]
                try:
                    r = fut.result()
                    if r:
                        kept[_candidate_key(r)] = r
                except Exception as exc:
                    errors.append(
                        f"{c.get('player_name') or 'Starter'}: {type(exc).__name__}: {exc}"
                    )
                bar.progress(
                    min(1.0, len(kept) / max(total, 1)),
                    text=f"Pitcher K: starter profiles {len(kept)}/{total}",
                )
        except TimeoutError:
            profile_timeout = True
            remaining = max(0, total - len(kept))
            errors.append(
                f"Pitcher K starter-profile phase reached the 100-second safety limit with {remaining} starter(s) remaining. Tap CONTINUE PITCHER K to finish only the missing profiles; completed profiles are preserved."
            )
            for fut in futs:
                if not fut.done():
                    fut.cancel()
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
            bar.empty()

    projected = list(kept.values())
    projected.sort(key=lambda x: x.get("projected_k", 0), reverse=True)

    market_lines = {}
    market_meta = {"connected": False}
    if projected:
        try:
            with st.spinner("Pitcher K: checking verified posted sportsbook lines..."):
                market_lines, market_meta = engine._fetch_market_lines(games, projected)
        except Exception as exc:
            market_meta = {
                "connected": False,
                "error": f"{type(exc).__name__}: {exc}",
            }

    graded = []
    unposted = 0
    if projected:
        bar = st.progress(0, text=f"Pitcher K: 250K simulations 0/{len(projected)}")
        for i, r in enumerate(projected, 1):
            if not r.get("sim"):
                try:
                    seed = 281000 + int(r["game_pk"]) % 100000 + int(r["player_id"]) % 10000
                    r["sim"] = engine._simulate_distribution(r, 250_000, seed)
                except Exception as exc:
                    errors.append(
                        f"{r.get('player_name') or 'Starter'}: simulation {type(exc).__name__}: {exc}"
                    )
                    bar.progress(i / max(len(projected), 1))
                    continue

            market = market_lines.get(
                (int(r["game_pk"]), engine._norm_name(r.get("player_name")))
            )
            r["market"] = market
            line = (market or {}).get("line")
            if line is None:
                unposted += 1
            else:
                try:
                    g = engine._grade_line(r["sim"], line)
                except Exception as exc:
                    errors.append(
                        f"{r.get('player_name') or 'Starter'}: grading {type(exc).__name__}: {exc}"
                    )
                    g = None
                if g:
                    rr = dict(r)
                    rr["grade"] = g
                    graded.append(rr)
            bar.progress(
                i / max(len(projected), 1),
                text=f"Pitcher K: 250K simulations {i}/{len(projected)}",
            )
        bar.empty()

    remaining = max(0, total - len(projected))
    return {
        "rows": graded,
        "projected": projected,
        "projected_count": len(projected),
        "candidate_count": total,
        "remaining_count": remaining,
        "complete": remaining == 0,
        "profile_timed_out": profile_timeout,
        "unposted_count": unposted,
        "market_meta": dict(market_meta or {}),
        "errors": errors,
        "sim_depth": 250_000,
    }


def render_daily_game_picks(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    global _ACTIVE_GAMES
    _ACTIVE_GAMES = games_df

    # Keep the original V1.8 candidate bridge alive through the inheritance chain.
    base._ACTIVE_GAMES = games_df
    base.base._ACTIVE_GAMES = games_df
    base.base.base._ACTIVE_GAMES = games_df
    base.base.base.base._ACTIVE_GAMES = games_df

    day = _day(games_df)
    key = _key(games_df)
    pack = st.session_state.get(key)

    c1, c2 = st.columns([4, 1])
    with c1:
        if pack and pack.get("projected_count") and pack.get("complete"):
            st.success(
                f"🔥 Pitcher K production connector ready • {pack.get('projected_count',0)}/{pack.get('candidate_count',0)} starters modeled • {len(pack.get('rows',[]))} posted K lines graded • 250K sims each • {day}"
            )
        elif pack and pack.get("projected_count"):
            st.warning(
                f"🔥 Pitcher K partial slate saved • {pack.get('projected_count',0)}/{pack.get('candidate_count',0)} starters modeled • {pack.get('remaining_count',0)} remaining • completed profiles preserved"
            )
        else:
            st.info(
                "🔥 Pitcher Strikeouts connector is ready to build. Tap CONNECT once; visible full-slate progress will begin immediately."
            )

    with c2:
        if pack and pack.get("projected_count") and not pack.get("complete"):
            label = "▶ CONTINUE PITCHER K"
        elif pack and pack.get("projected_count"):
            label = "↻ REFRESH PITCHER K"
        else:
            label = "🔥 CONNECT PITCHER K"

        if st.button(
            label,
            use_container_width=True,
            key=f"dgp_pitcherk_connect_v182::{day}",
        ):
            resume = pack if pack and pack.get("projected_count") and not pack.get("complete") else None
            st.toast(
                "🔥 Pitcher K build started"
                if resume is None
                else "🔥 Resuming remaining Pitcher K starters"
            )
            status = st.status("Pitcher K connector is working…", expanded=True)
            status.write(
                "Building production starter profiles, checking real posted K lines, and running 250K Monte Carlo distributions per modeled starter."
            )
            try:
                st.session_state[key] = _build(games_df, resume)
                built = st.session_state[key]
                if built.get("complete"):
                    status.update(
                        label=f"Pitcher K complete — {built.get('projected_count',0)}/{built.get('candidate_count',0)} starters modeled",
                        state="complete",
                        expanded=False,
                    )
                elif built.get("projected_count"):
                    status.update(
                        label=f"Pitcher K partial — {built.get('projected_count',0)}/{built.get('candidate_count',0)} modeled; {built.get('remaining_count',0)} remaining",
                        state="complete",
                        expanded=True,
                    )
                else:
                    status.update(
                        label="Pitcher K finished with no completed starter models",
                        state="error",
                        expanded=True,
                    )
            except Exception as exc:
                st.session_state[key] = {
                    "rows": [], "projected": [], "projected_count": 0,
                    "candidate_count": 0, "remaining_count": 0,
                    "complete": False,
                    "errors": [f"{type(exc).__name__}: {exc}"],
                }
                status.update(
                    label=f"Pitcher K error: {type(exc).__name__}",
                    state="error",
                    expanded=True,
                )
            st.rerun()

    if pack and pack.get("unposted_count"):
        st.caption(
            f"🎯 {pack['unposted_count']} modeled starter(s) have no verified posted K line, so they remain projection-only and are not promoted into cross-market scoring."
        )
    if pack and pack.get("errors"):
        with st.expander(f"⚠️ Pitcher K connector diagnostics ({len(pack['errors'])})"):
            for err in pack["errors"]:
                st.caption(str(err))

    st.caption(
        "🔌 Step 4D V1.8.2: Pitcher Strikeouts keeps the existing workload + opponent-K + Monte Carlo production engine at 250K simulations per modeled starter. Full-slate profile builds use up to 12 workers, a 100-second bounded window, and resumable caching. Only real posted K lines are graded; no threshold is fabricated."
    )

    # Skip V1.8's older Pitcher-K UI and continue directly into V1.7's lower connectors.
    return base.base.render_daily_game_picks(
        games_df, section_header, status_info, team_logo, h
    )
