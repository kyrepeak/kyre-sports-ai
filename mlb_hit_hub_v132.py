"""MLB 1+ Hit UI V13.2 — isolated verified-slate wrapper.

MLB 1+ HIT ONLY.
- Does not modify Moneyline, Run Line, Totals, Live Game, or WNBA.
- Reloads the selected MLB slate directly through MLB Schedule V3.2 instead of
  trusting the shared/global games dataframe.
- Preserves the existing V13 hit probability engine and V13.1 scanner/analyzer.
- Exposes schedule-source diagnostics if the hit page cannot obtain a slate.
"""
from __future__ import annotations

import streamlit as st

import hit_hub_v131 as base
import mlb_schedule_v32 as schedule

UI_VERSION = "V13.2"


def _schedule_banner(frame, diag):
    games = int(len(frame)) if frame is not None else 0
    source = str((diag or {}).get("source") or "unknown")
    day = str((diag or {}).get("date") or schedule.current_selected_date())
    if games:
        st.success(f"⚾ 1+ Hit slate verified • {day} • {games} game(s) • {source}")
        if "ESPN" in source.upper():
            st.warning(
                "Schedule recovery is currently using ESPN. Top-5 lineup/gamePk layers may be partial until the official MLB feed reconnects."
            )
    else:
        st.error(f"1+ Hit could not load a verified MLB slate for {day}.")
        attempts = (diag or {}).get("attempts") or []
        if attempts:
            with st.expander("🔧 MLB 1+ Hit schedule diagnostics", expanded=True):
                for item in attempts:
                    provider = item.get("provider", "provider")
                    http = item.get("http")
                    count = item.get("games", 0)
                    size = item.get("bytes", 0)
                    err = item.get("error") or ""
                    st.write(
                        f"**{provider}** • HTTP {http if http is not None else '—'} • "
                        f"{count} games • {size} bytes" + (f" • `{err}`" if err else "")
                    )


def render_hit_hub(games_df, section_header, status_info, team_logo, h):
    """Render 1+ Hit using a fresh MLB-only slate, ignoring stale shared slate data."""
    try:
        day = schedule.current_selected_date()
        fresh_games, diag = schedule.load_with_diagnostics(day)
    except Exception as exc:
        fresh_games = games_df
        diag = {
            "date": str(schedule.current_selected_date()),
            "source": "shared fallback",
            "games": int(len(games_df)) if games_df is not None else 0,
            "attempts": [{"provider": "V13.2 wrapper", "error": f"{type(exc).__name__}: {exc}"}],
        }

    # Only use the incoming dataframe if the isolated loader itself failed and
    # the caller actually supplied a non-empty MLB slate.
    if (fresh_games is None or fresh_games.empty) and games_df is not None and not games_df.empty:
        fresh_games = games_df.copy()
        diag = dict(diag or {})
        diag["source"] = "verified shared MLB fallback"
        diag["games"] = len(fresh_games)

    _schedule_banner(fresh_games, diag)

    # Keep the underlying probability engine untouched.
    base.render_hit_hub(fresh_games, section_header, status_info, team_logo, h)
