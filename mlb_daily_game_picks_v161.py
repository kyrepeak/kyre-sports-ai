"""MLB Daily Game Picks V1.6.1 — full-slate Home Run connector.

Preserves the calibrated HR V1.1 production probability model exactly. This layer
changes orchestration only: hitter profile work is visible, bounded, retryable,
and resumable so transient MLB Stats API failures cannot silently drop hitters.
No HR probability math, ranking math, or sportsbook logic is changed.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
import time
import streamlit as st

import mlb_daily_game_picks_v16 as base
import mlb_hr_hub_v11 as hrprod
import mlb_hr_hub_v10 as hrcore

VERSION = "MLB Daily Game Picks V1.6.1 • FULL-SLATE HOME RUN CONNECTOR"
_ACTIVE_GAMES = None


def _day(games):
    return base._day(games)


def _key(games):
    # Keep V1.6's original cache key so its production-candidate bridge reads us.
    return base._hr_key(games)


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
        "temporary failure", "safety limit", "remote disconnected",
    ))


def _profile_one(c, attempts=2):
    last = None
    for attempt in range(int(attempts)):
        try:
            r = hrprod._model_candidate(c, deep=False)
            return "ok" if r else "skip", r, ""
        except Exception as exc:
            last = exc
            if attempt + 1 < attempts:
                time.sleep(1.25 * (attempt + 1))
    return "error", None, f"{type(last).__name__}: {last}" if last else "profile failed"


def _build_hr(games, previous=None):
    try:
        candidates, meta = hrcore._candidate_pool(games, False)
    except Exception as exc:
        return {
            "rows": [], "profile_count": 0, "candidate_count": 0,
            "remaining_count": 0, "skipped_count": 0, "complete": False,
            "meta": {"error": f"{type(exc).__name__}: {exc}"},
            "errors": [f"Candidate pool: {type(exc).__name__}: {exc}"],
        }

    candidates = list(candidates or [])
    total = len(candidates)
    if not total:
        return {
            "rows": [], "profile_count": 0, "candidate_count": 0,
            "remaining_count": 0, "skipped_count": 0, "complete": False,
            "meta": dict(meta or {}),
            "errors": ["No eligible Home Run hitter candidates were available."],
        }

    kept = {}
    skipped = set()
    errors = []
    if previous and not previous.get("complete"):
        for r in previous.get("rows", []) or []:
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
            text=f"Home Run: calibrated profiles {done0}/{total}",
        )
        # Initial pass is moderately parallel; resume passes are deliberately gentler
        # on MLB Stats API to improve recovery from connection saturation.
        workers = 4 if previous else 8
        pool = ThreadPoolExecutor(max_workers=min(workers, len(pending)))
        futs = {pool.submit(_profile_one, c, 2): c for c in pending}
        try:
            for fut in as_completed(futs, timeout=120):
                c = futs[fut]
                key = _ckey(c)
                try:
                    status, result, err = fut.result()
                except Exception as exc:
                    status, result, err = "error", None, f"{type(exc).__name__}: {exc}"
                if status == "ok" and result:
                    kept[key] = result
                elif status == "skip":
                    skipped.add(key)
                else:
                    errors.append(f"{c.get('player_name') or 'Hitter'}: {err or 'profile failed'}")
                finished = len(kept) + len(skipped)
                bar.progress(
                    min(1.0, finished / max(total, 1)),
                    text=f"Home Run: calibrated profiles {finished}/{total}",
                )
        except TimeoutError:
            timed_out = True
            remaining = max(0, total - len(kept) - len(skipped))
            errors.append(
                f"Home Run profile phase reached the 120-second safety limit with {remaining} hitter(s) remaining. Tap CONTINUE HOME RUN to finish only the missing profiles; completed profiles are preserved."
            )
            for fut in futs:
                if not fut.done():
                    fut.cancel()
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
            bar.empty()

    rows = list(kept.values())
    rows.sort(key=lambda x: float(x.get("p_hr") or 0), reverse=True)
    remaining = max(0, total - len(kept) - len(skipped))
    complete = remaining == 0

    return {
        "rows": rows,
        "profile_count": len(rows),
        "candidate_count": total,
        "remaining_count": remaining,
        "skipped_count": len(skipped),
        "skipped_keys": [list(x) for x in skipped],
        "complete": complete,
        "timed_out": timed_out,
        "meta": dict(meta or {}),
        "errors": errors,
    }


def render_daily_game_picks(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    global _ACTIVE_GAMES
    _ACTIVE_GAMES = games_df

    # Preserve V1.6's Home Run candidate bridge and all lower connectors.
    base._ACTIVE_GAMES = games_df
    base.base._ACTIVE_GAMES = games_df

    day = _day(games_df)
    key = _key(games_df)
    pack = st.session_state.get(key)

    c1, c2 = st.columns([4, 1])
    with c1:
        if pack and pack.get("complete") and pack.get("rows"):
            st.success(
                f"💣 Home Run production connector ready • {pack.get('profile_count',0)}/{pack.get('candidate_count',0)} calibrated hitter profiles complete • HR V1.1 • {day}"
            )
        elif pack and (pack.get("profile_count") or pack.get("skipped_count")):
            st.warning(
                f"💣 Home Run partial slate saved • {pack.get('profile_count',0)} profiles built • {pack.get('remaining_count',0)} remaining • completed profiles preserved"
            )
        else:
            st.info(
                "💣 Home Run connector is ready to build. Tap CONNECT once; visible full-slate profile progress will begin immediately."
            )

    with c2:
        if pack and not pack.get("complete") and (pack.get("profile_count") or pack.get("skipped_count")):
            label = "▶ CONTINUE HOME RUN"
        elif pack and pack.get("complete") and pack.get("rows"):
            label = "↻ REFRESH HOME RUN"
        else:
            label = "💣 CONNECT HOME RUN"

        if st.button(label, use_container_width=True, key=f"dgp_hr_connect_v161::{day}"):
            resume = pack if pack and not pack.get("complete") else None
            st.toast("💣 Home Run build started" if resume is None else "💣 Resuming missing Home Run profiles")
            status = st.status("Home Run connector is working…", expanded=True)
            status.write(
                "Running the existing calibrated HR V1.1 production model. Completed hitter profiles are cached during partial builds."
            )
            try:
                st.session_state[key] = _build_hr(games_df, resume)
                built = st.session_state[key]
                if built.get("complete"):
                    status.update(
                        label=f"Home Run complete — {built.get('profile_count',0)}/{built.get('candidate_count',0)} profiles built",
                        state="complete",
                        expanded=False,
                    )
                elif built.get("profile_count"):
                    status.update(
                        label=f"Home Run partial — {built.get('remaining_count',0)} profiles remaining",
                        state="complete",
                        expanded=True,
                    )
                else:
                    status.update(label="Home Run finished with no completed profiles", state="error", expanded=True)
            except Exception as exc:
                st.session_state[key] = {
                    "rows": [], "profile_count": 0, "candidate_count": 0,
                    "remaining_count": 0, "complete": False,
                    "errors": [f"{type(exc).__name__}: {exc}"],
                }
                status.update(label=f"Home Run error: {type(exc).__name__}", state="error", expanded=True)
            st.rerun()

    if pack and pack.get("skipped_count"):
        st.caption(
            f"ℹ️ {pack.get('skipped_count',0)} hitter candidate(s) had no usable HR production profile and were excluded rather than fabricated."
        )
    if pack and pack.get("errors"):
        with st.expander(f"⚠️ Home Run connector diagnostics ({len(pack['errors'])})"):
            for err in pack["errors"]:
                st.caption(str(err))

    st.caption(
        "🔌 Step 4B V1.6.1: Home Run still uses calibrated HR V1.1 probability math unchanged. Full-slate profile work is visible, bounded to 120 seconds per pass, retryable, and resumable; completed hitter profiles are preserved and missing profiles can be continued without silently dropping players."
    )

    # Skip V1.6's older Home Run UI and continue into V1.5's lower connector.
    return base.base.render_daily_game_picks(
        games_df, section_header, status_info, team_logo, h
    )
