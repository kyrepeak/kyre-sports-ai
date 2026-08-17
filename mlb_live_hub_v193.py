"""MLB Live Game V19.3 — isolated official slate + live-feed health.

This wrapper changes only the Live Game bootstrap. The existing V19.2.1 live
state UI, pitch-by-pitch game feed, state-aware V19 simulation and live sportsbook
market dashboard remain intact.

Deep live state requires a real positive MLB gamePk. ESPN/synthetic schedule IDs
are never presented as if they were official MLB live-feed identifiers.
"""

import pandas as pd
import streamlit as st

import mlb_schedule_v32 as schedule
import live_game_hub_v1921 as base
import live_game_hub_v182 as live_feed

MODEL_VERSION = "V19.3"


def _real_gamepk_frame(frame):
    if frame is None or frame.empty or "game_pk" not in frame.columns:
        return pd.DataFrame(columns=getattr(frame, "columns", []))
    out = frame.copy()
    pks = pd.to_numeric(out["game_pk"], errors="coerce")
    out = out[pks.notna() & (pks > 0)].copy()
    if out.empty:
        return out
    out["game_pk"] = pd.to_numeric(out["game_pk"], errors="coerce").astype(int)
    if "verified" in out.columns:
        out = out[out["verified"].fillna(False).astype(bool)].copy()
    return out.reset_index(drop=True)


def _schedule_banner(diag, frame, official_count):
    day = str((diag or {}).get("date") or schedule.current_selected_date())
    source = str((diag or {}).get("source") or "verified MLB loader")
    total = int(len(frame)) if frame is not None else 0
    if official_count:
        st.success(
            f"🔴 Live Game slate verified • {day} • {official_count} official MLB game IDs • {source}"
        )
    elif total:
        st.warning(
            f"⚠️ {total} schedule game(s) were found for {day}, but none has a real MLB gamePk. "
            "Pitch-by-pitch live state will not use synthetic IDs."
        )
    else:
        st.error(f"⚠️ Live Game schedule unavailable for {day}.")


def _schedule_diagnostics(diag):
    attempts = (diag or {}).get("attempts") or []
    if not attempts:
        return
    with st.expander("MLB Live schedule diagnostics"):
        for item in attempts:
            provider = str(item.get("provider") or "provider")
            status = item.get("http", item.get("status"))
            count = item.get("games")
            error = item.get("error")
            bits = [provider]
            if status is not None:
                bits.append(f"HTTP {status}")
            if count is not None:
                bits.append(f"{count} games")
            if error:
                bits.append(str(error))
            st.caption(" • ".join(bits))


def _live_feed_health(frame, day):
    if frame is None or frame.empty:
        return None
    allowed = tuple(sorted(pd.to_numeric(frame["game_pk"], errors="coerce").dropna().astype(int).tolist()))
    if not allowed:
        return None
    try:
        fresh = live_feed.fetch_live_slate(str(day), allowed)
    except Exception as exc:
        st.warning(
            f"⚠️ MLB live-state refresh could not connect right now: {type(exc).__name__}: {exc}"
        )
        return None

    refreshed = len(fresh or {})
    labels = []
    for item in (fresh or {}).values():
        state = live_feed._state_label(item.get("status"))
        labels.append(state)
    live_n = sum(1 for x in labels if x == "LIVE")
    delayed_n = sum(1 for x in labels if x == "DELAYED")
    pre_n = sum(1 for x in labels if x == "PREGAME")
    final_n = sum(1 for x in labels if x == "FINAL")

    if refreshed == len(allowed):
        st.success(
            f"📡 MLB live-state feed connected • {refreshed}/{len(allowed)} games refreshed • "
            f"🔴 {live_n} live • ⚠️ {delayed_n} delayed • ⏳ {pre_n} upcoming • 🏁 {final_n} final"
        )
    else:
        st.warning(
            f"📡 MLB live-state feed partial • {refreshed}/{len(allowed)} games refreshed • "
            f"🔴 {live_n} live • ⚠️ {delayed_n} delayed • ⏳ {pre_n} upcoming • 🏁 {final_n} final"
        )
    return fresh


def render_live_hub(games_df, section_header, status_info, team_logo, h):
    """Render Live Game using an isolated, real-gamePk MLB slate."""
    day = schedule.current_selected_date()
    try:
        fresh_games, diag = schedule.load_with_diagnostics(day)
    except Exception as exc:
        fresh_games = pd.DataFrame()
        diag = {
            "date": str(day),
            "source": "none",
            "attempts": [{"provider": "V19.3 schedule wrapper", "error": f"{type(exc).__name__}: {exc}"}],
        }

    official = _real_gamepk_frame(fresh_games)

    # If the direct loader had to use a synthetic recovery slate, prefer the
    # already-loaded shared official slate when it contains real MLB IDs.
    if official.empty:
        shared_official = _real_gamepk_frame(games_df)
        if not shared_official.empty:
            official = shared_official
            diag = dict(diag or {})
            diag["source"] = "shared official MLB slate fallback"

    _schedule_banner(diag, fresh_games, len(official))
    if official.empty:
        _schedule_diagnostics(diag)
        st.info(
            "Live Game requires official MLB game IDs for score, inning, outs, bases, batter, pitcher and pitch-by-pitch data."
        )
        return

    st.caption(
        "🔒 Live Game V19.3 isolation: schedule + live state are owned by this page. "
        "V19.2.1 state-aware simulation and sportsbook ML/run-line/total sync remain unchanged."
    )
    _live_feed_health(official, day)

    # V19.2.1 handles the game selector, 10-second live fragment, scoreboard,
    # batter/pitcher/count/bases/recent plays, simulations and live market board.
    base.render_live_hub(official, section_header, status_info, team_logo, h)
