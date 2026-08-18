"""MLB Daily Game Picks V2.0.8 — one-tap full-card builder.

Adds a state-driven orchestration layer above the existing V2.0.7 seven-market
production system. One button walks the selected MLB slate through all seven
connectors without changing any model math:

1. Run Line
2. Total
3. Moneyline
4. Pitcher Strikeouts
5. H+R+RBI
6. Home Run
7. 1+ Hit

Only incomplete connectors are executed. Each stage uses its existing bounded,
resumable production builder and preserves completed work. The controller runs
one connector per Streamlit rerun so a phone/browser is not held inside one giant
multi-minute request. A stage may receive up to three automatic resumable passes;
if it still cannot complete (rate limit, transient provider failure, etc.), it is
marked blocked for this pass and the remaining connectors continue. Re-pressing
the build button later retries only still-incomplete stages.

Step 3 V2.0.7 normalization, Step 5 per-game ranking, Step 6 Daily Master Card,
sportsbook verification gates, matchup identity firewalls, and all simulation
models remain unchanged.
"""
from __future__ import annotations

import streamlit as st

import mlb_daily_game_picks_v207 as previous
import mlb_daily_game_picks_v19 as moneyline
import mlb_daily_game_picks_v182 as pitcherk
import mlb_daily_game_picks_v171 as hrrbi
import mlb_daily_game_picks_v162 as hrpatch
import mlb_daily_game_picks_v152 as hitone

# V2.0.7 -> V2.0.6 -> V2.0.5 -> V2.0.4.
bridge = previous.bridge
hrbase = hrpatch.base

VERSION = "MLB Daily Game Picks V2.0.8 • ONE-TAP FULL-CARD BUILDER"
MAX_AUTO_PASSES_PER_STAGE = 3

STAGES = (
    ("runline", "Run Line", "🏃"),
    ("total", "Total", "🧾"),
    ("moneyline", "Moneyline", "💰"),
    ("pitcherk", "Pitcher K", "🔥"),
    ("hrrbi", "H+R+RBI", "🧮"),
    ("homerun", "Home Run", "💣"),
    ("onehit", "1+ Hit", "⚡"),
)


def _day(games_df):
    try:
        if games_df is None or games_df.empty:
            return ""
        return str(games_df.iloc[0].get("game_date") or "")[:10]
    except Exception:
        return ""


def _state_key(day):
    return f"dgp_full_card_builder_v208::{day}"


def _pack_key(games_df, stage):
    day = _day(games_df)
    if stage == "runline":
        return bridge._runline_key(day)
    if stage == "total":
        return bridge._total_key(day)
    if stage == "moneyline":
        return moneyline._key(games_df)
    if stage == "pitcherk":
        return pitcherk._key(games_df)
    if stage == "hrrbi":
        return hrrbi._key(games_df)
    if stage == "homerun":
        return hrbase._key(games_df)
    if stage == "onehit":
        return hitone._key(games_df)
    return ""


def _pack(games_df, stage):
    key = _pack_key(games_df, stage)
    return st.session_state.get(key) if key else None


def _complete(pack):
    return bool(isinstance(pack, dict) and pack.get("complete"))


def _metric(stage, pack):
    if not isinstance(pack, dict):
        return 0
    if stage in {"runline", "total"}:
        return int(len(pack.get("rows", []) or []) + int(pack.get("skipped_count", 0) or 0))
    if stage == "moneyline":
        return int(pack.get("modeled_count", 0) or 0)
    if stage == "pitcherk":
        return int(pack.get("projected_count", 0) or 0)
    if stage == "hrrbi":
        return int(pack.get("profile_count", 0) or 0) + int(pack.get("skipped_count", 0) or 0)
    if stage == "homerun":
        return int(pack.get("profile_count", 0) or 0) + int(pack.get("skipped_count", 0) or 0)
    if stage == "onehit":
        return int(pack.get("modeled_count", 0) or 0)
    return 0


def _remaining(pack):
    if not isinstance(pack, dict):
        return None
    try:
        return int(pack.get("remaining_count", 0) or 0)
    except Exception:
        return None


def _last_error(pack):
    if not isinstance(pack, dict):
        return ""
    errors = [str(x) for x in (pack.get("errors") or []) if str(x).strip()]
    return errors[-1] if errors else ""


def _summary(games_df):
    out = []
    for stage, label, icon in STAGES:
        pack = _pack(games_df, stage)
        if _complete(pack):
            out.append(f"✅ {label}")
        elif pack and _metric(stage, pack) > 0:
            rem = _remaining(pack)
            out.append(f"🟡 {label}{f' ({rem} left)' if rem is not None else ''}")
        elif pack and _last_error(pack):
            out.append(f"⛔ {label}")
        else:
            out.append(f"⚪ {label}")
    return " • ".join(out)


def _completed_count(games_df):
    return sum(1 for stage, _, _ in STAGES if _complete(_pack(games_df, stage)))


def _all_complete(games_df):
    return _completed_count(games_df) == len(STAGES)


def _initial_state(day):
    return {
        "active": False,
        "cursor": 0,
        "attempts": {},
        "last_metric": {},
        "blocked": {},
        "day": day,
        "runs": 0,
    }


def _build_stage(games_df, stage):
    """Invoke the existing production builder for one market and save its native pack."""
    key = _pack_key(games_df, stage)
    current = st.session_state.get(key) or None
    resume = current if current and not current.get("complete") else None

    if stage == "runline":
        built = bridge._build_market(
            games_df, "runline", resume,
            force_odds=(resume is None),
        )
    elif stage == "total":
        # Reuse Run Line's quota-safe shared sportsbook snapshot whenever available.
        built = bridge._build_market(
            games_df, "total", resume,
            force_odds=False,
        )
    elif stage == "moneyline":
        built = moneyline._build(games_df, resume)
    elif stage == "pitcherk":
        built = pitcherk._build(games_df, resume)
    elif stage == "hrrbi":
        built = hrrbi._build(games_df, resume)
    elif stage == "homerun":
        # V1.6.2 patched V1.6.1's builder in-place with resilient lineup intake.
        built = hrbase._build_hr(games_df, resume)
    elif stage == "onehit":
        built = hitone._build(games_df, resume)
    else:
        raise ValueError(f"Unknown full-card stage: {stage}")

    st.session_state[key] = built
    return built


def _advance_past_complete(games_df, state):
    cursor = int(state.get("cursor", 0) or 0)
    while cursor < len(STAGES):
        stage = STAGES[cursor][0]
        if not _complete(_pack(games_df, stage)):
            break
        cursor += 1
    state["cursor"] = cursor
    return state


def _run_controller(games_df, state_key, state):
    state = _advance_past_complete(games_df, state)
    cursor = int(state.get("cursor", 0) or 0)
    if cursor >= len(STAGES):
        state["active"] = False
        st.session_state[state_key] = state
        return

    stage, label, icon = STAGES[cursor]
    attempts = dict(state.get("attempts") or {})
    prior_metric = _metric(stage, _pack(games_df, stage))
    attempt = int(attempts.get(stage, 0) or 0) + 1
    attempts[stage] = attempt
    state["attempts"] = attempts
    st.session_state[state_key] = state

    overall_done = _completed_count(games_df)
    status = st.status(
        f"{icon} Full-card build • {label} • stage {cursor + 1}/7",
        expanded=True,
    )
    status.write(
        f"Automatic pass {attempt}/{MAX_AUTO_PASSES_PER_STAGE}. Completed connectors are skipped and never rerun."
    )
    st.progress(
        overall_done / len(STAGES),
        text=f"Full MLB Card: {overall_done}/7 connectors complete • building {label}",
    )

    try:
        built = _build_stage(games_df, stage)
    except Exception as exc:
        built = {
            "complete": False,
            "rows": [],
            "remaining_count": 0,
            "errors": [f"{type(exc).__name__}: {exc}"],
        }
        key = _pack_key(games_df, stage)
        if key:
            st.session_state[key] = built

    after_metric = _metric(stage, built)
    if _complete(built):
        state["cursor"] = cursor + 1
        state.setdefault("blocked", {}).pop(stage, None)
        status.update(
            label=f"✅ {label} complete • moving to stage {cursor + 2}/7" if cursor + 1 < len(STAGES) else f"✅ {label} complete",
            state="complete",
            expanded=False,
        )
    else:
        made_progress = after_metric > prior_metric
        should_retry = made_progress and attempt < MAX_AUTO_PASSES_PER_STAGE
        if should_retry:
            status.update(
                label=f"🟡 {label} partial • saved progress • continuing automatically",
                state="complete",
                expanded=False,
            )
        else:
            error = _last_error(built) or f"{label} did not complete in this pass."
            blocked = dict(state.get("blocked") or {})
            blocked[stage] = error
            state["blocked"] = blocked
            state["cursor"] = cursor + 1
            status.update(
                label=f"⛔ {label} paused for this full-card run • continuing with the next connector",
                state="error",
                expanded=True,
            )
            status.caption(error)

    if int(state.get("cursor", 0) or 0) >= len(STAGES):
        state["active"] = False
    st.session_state[state_key] = state
    st.rerun()


def _render_full_builder(games_df):
    day = _day(games_df)
    if not day:
        return
    key = _state_key(day)
    state = st.session_state.get(key)
    if not isinstance(state, dict) or state.get("day") != day:
        state = _initial_state(day)
        st.session_state[key] = state

    st.markdown("### 🚀 One-Tap Full MLB Card")
    done = _completed_count(games_df)
    st.caption(
        "Runs all seven existing production connectors in order, skips completed work, resumes partial work, and automatically feeds Step 5 + the Daily Master Card. No model math is changed."
    )
    st.progress(done / len(STAGES), text=f"Full MLB Card • {done}/7 connectors complete")
    st.caption(_summary(games_df))

    if state.get("active"):
        _run_controller(games_df, key, state)
        return

    if _all_complete(games_df):
        st.success("✅ FULL MLB CARD READY • 7/7 production connectors complete • Step 5 and Daily Master Card are live below.")
        return

    blocked = dict(state.get("blocked") or {})
    if blocked:
        st.warning(
            f"{done}/7 connectors are complete. Re-run the full-card builder to retry only the {len(STAGES) - done} unfinished connector(s); completed connectors will be skipped."
        )
        with st.expander(f"⚠️ Full-card blocked-stage notes ({len(blocked)})"):
            for stage, message in blocked.items():
                label = next((x[1] for x in STAGES if x[0] == stage), stage)
                st.caption(f"• {label}: {message}")

    label = "▶ RESUME FULL MLB CARD" if done else "🚀 BUILD TODAY'S FULL MLB CARD"
    if st.button(label, type="primary", use_container_width=True, key=f"dgp_fullcard_start_v208::{day}"):
        # Start at the first incomplete connector. Completed connector packs remain intact.
        fresh = _initial_state(day)
        fresh["active"] = True
        fresh["runs"] = int(state.get("runs", 0) or 0) + 1
        st.session_state[key] = fresh
        st.rerun()


def render_daily_game_picks(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    # Keep V2.0.7 market-neutral scoring installed defensively before any cached
    # outputs are rendered into Step 5/Step 6.
    previous.step3.normalize_candidate = previous.normalize_candidate
    st.caption(
        "🚀 V2.0.8 full-card controller: one tap • 7 production connectors • completed stages skipped • partial work resumed • blocked providers do not erase other markets."
    )
    _render_full_builder(games_df)
    return previous.render_daily_game_picks(games_df, section_header, status_info, team_logo, h)
