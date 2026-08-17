"""MLB Totals V17.3 — isolated verified-slate intake + scan health.

This wrapper changes only the Totals page bootstrap behavior. The V17.2 live
sportsbook total sync and V17.1 projected-score / Over-Under probability math
remain unchanged. Sportsbook totals remain settlement inputs, not projection
features.
"""

import streamlit as st

import mlb_schedule_v32 as schedule
import totals_hub_v172 as base

MODEL_VERSION = "V17.3"


def _render_schedule_status(diag, games_df):
    games = int(len(games_df)) if games_df is not None else 0
    source = str((diag or {}).get("source") or "verified MLB loader")
    day = str((diag or {}).get("date") or schedule.current_selected_date())
    if games:
        st.success(f"⚾ Totals slate verified • {day} • {games} games • {source}")
    else:
        st.error(f"⚠️ Totals schedule unavailable for {day}.")
        attempts = (diag or {}).get("attempts") or []
        if attempts:
            with st.expander("MLB Totals schedule diagnostics"):
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


def _render_scan_health(games_df):
    results = st.session_state.get("v171_ou_results") or []
    if not results:
        return
    errors = int(st.session_state.get("v171_ou_errors", 0) or 0)
    modeled = len(results)

    verified_count = 0
    try:
        if games_df is not None and not games_df.empty:
            if "verified" in games_df.columns:
                verified_count = int(games_df["verified"].fillna(False).astype(bool).sum())
            else:
                verified_count = int(len(games_df))
    except Exception:
        verified_count = 0

    available_count = max(modeled + errors, modeled)
    if errors == 0 and modeled == available_count:
        st.success(f"✅ Totals scan health • {modeled}/{available_count} actionable games modeled • 0 errors")
    else:
        st.warning(
            f"⚠️ Totals scan health • {modeled}/{available_count} actionable games modeled • {errors} error(s). "
            f"Verified slate contains {verified_count} game(s)."
        )


def render_totals_hub(games_df, section_header, status_info, team_logo, h):
    """Render Totals with its own fresh verified MLB slate."""
    try:
        day = schedule.current_selected_date()
        fresh_games, diag = schedule.load_with_diagnostics(day)
    except Exception as exc:
        fresh_games = games_df
        diag = {
            "date": str(schedule.current_selected_date()),
            "source": "shared fallback",
            "games": int(len(games_df)) if games_df is not None else 0,
            "attempts": [{"provider": "V17.3 wrapper", "error": f"{type(exc).__name__}: {exc}"}],
        }

    if (fresh_games is None or fresh_games.empty) and games_df is not None and not games_df.empty:
        fresh_games = games_df.copy()
        diag = dict(diag or {})
        diag["source"] = "shared verified slate fallback"
        diag["games"] = int(len(fresh_games))

    _render_schedule_status(diag, fresh_games)
    if fresh_games is None or fresh_games.empty:
        st.info("No verified MLB games are available for the selected Totals slate.")
        return

    st.caption(
        "🔒 Totals V17.3 isolation: this page owns its MLB schedule intake. "
        "V17.2 sportsbook-line sync and V17.1 scoring/O-U probability math remain unchanged; "
        "sportsbook totals do not drive the projected score."
    )

    base.render_totals_hub(fresh_games, section_header, status_info, team_logo, h)
    _render_scan_health(fresh_games)
