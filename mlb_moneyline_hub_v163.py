"""MLB Moneyline V16.3 — isolated verified-slate intake.

This wrapper changes only the Moneyline page's schedule/bootstrap behavior.
The V16.2/V16.1/V16 probability model, H2H overlay, simulation math and sportsbook
independence remain unchanged.
"""

import streamlit as st

import mlb_schedule_v32 as schedule
import moneyline_hub_v162 as base

MODEL_VERSION = "V16.3"


def _render_schedule_status(diag, games_df):
    games = int(len(games_df)) if games_df is not None else 0
    source = str((diag or {}).get("source") or "verified MLB loader")
    day = str((diag or {}).get("date") or schedule.current_selected_date())
    if games:
        st.success(f"⚾ Moneyline slate verified • {day} • {games} games • {source}")
    else:
        st.error(f"⚠️ Moneyline schedule unavailable for {day}.")
        attempts = (diag or {}).get("attempts") or []
        if attempts:
            with st.expander("MLB Moneyline schedule diagnostics"):
                for item in attempts:
                    provider = item.get("provider") or "provider"
                    status = item.get("status")
                    count = item.get("games")
                    error = item.get("error")
                    bits = [str(provider)]
                    if status is not None:
                        bits.append(f"HTTP {status}")
                    if count is not None:
                        bits.append(f"{count} games")
                    if error:
                        bits.append(str(error))
                    st.caption(" • ".join(bits))


def render_moneyline_hub(games_df, section_header, status_info, team_logo, h):
    """Render Moneyline with its own fresh verified MLB slate."""
    try:
        day = schedule.current_selected_date()
        fresh_games, diag = schedule.load_with_diagnostics(day)
    except Exception as exc:
        fresh_games = games_df
        diag = {
            "date": str(schedule.current_selected_date()),
            "source": "shared fallback",
            "games": int(len(games_df)) if games_df is not None else 0,
            "attempts": [{"provider": "V16.3 wrapper", "error": f"{type(exc).__name__}: {exc}"}],
        }

    if (fresh_games is None or fresh_games.empty) and games_df is not None and not games_df.empty:
        fresh_games = games_df.copy()
        diag = dict(diag or {})
        diag["source"] = "shared verified slate fallback"
        diag["games"] = int(len(fresh_games))

    _render_schedule_status(diag, fresh_games)
    if fresh_games is None or fresh_games.empty:
        st.info("No verified MLB games are available for the selected Moneyline slate.")
        return

    st.caption(
        "🔒 Moneyline V16.3 isolation: this page owns its MLB schedule intake. "
        "Moneyline probability math remains V16.2/V16.1/V16 and sportsbook prices are still not model inputs."
    )
    return base.render_moneyline_hub(fresh_games, section_header, status_info, team_logo, h)
