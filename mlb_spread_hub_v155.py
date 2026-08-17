"""MLB Spread / Run Line V15.5 — isolated verified-slate intake.

This wrapper changes only the Spread page's schedule/bootstrap behavior and scan
visibility. The V15.4/V15.3/V15.2 spread model, simulation math, H2H context,
backtest logic and sportsbook independence remain unchanged.
"""

import streamlit as st

import mlb_schedule_v32 as schedule
import spread_hub_v154 as base

MODEL_VERSION = "V15.5"


def _render_schedule_status(diag, games_df):
    games = int(len(games_df)) if games_df is not None else 0
    source = str((diag or {}).get("source") or "verified MLB loader")
    day = str((diag or {}).get("date") or schedule.current_selected_date())

    if games:
        st.success(f"⚾ Spread slate verified • {day} • {games} games • {source}")
    else:
        st.error(f"⚠️ Spread schedule unavailable for {day}.")
        attempts = (diag or {}).get("attempts") or []
        if attempts:
            with st.expander("MLB Spread schedule diagnostics"):
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
    """Show how much of the verified slate actually survived the spread engine."""
    if games_df is None or games_df.empty:
        return

    verified = games_df
    if "verified" in verified.columns:
        verified = verified[verified["verified"].fillna(False).astype(bool)]

    expected = int(len(verified))
    results = st.session_state.get("v152_spread_slate") or []
    errors = int(st.session_state.get("v152_spread_errors") or 0)
    if not results and not errors:
        return

    modeled_pks = set()
    for result in results:
        try:
            modeled_pks.add(int(result.get("game_pk")))
        except Exception:
            continue

    modeled = len(modeled_pks)
    if modeled == expected and errors == 0:
        st.success(f"✅ Spread scan health • {modeled}/{expected} verified games modeled • 0 errors")
    else:
        st.warning(
            f"⚠️ Spread scan health • {modeled}/{expected} verified games modeled • {errors} model error(s). "
            "Results remain limited to successfully modeled verified games."
        )


def render_spread_hub(games_df, section_header, status_info, team_logo, h):
    """Render Spread with its own fresh verified MLB slate."""
    try:
        day = schedule.current_selected_date()
        fresh_games, diag = schedule.load_with_diagnostics(day)
    except Exception as exc:
        fresh_games = games_df
        diag = {
            "date": str(schedule.current_selected_date()),
            "source": "shared fallback",
            "games": int(len(games_df)) if games_df is not None else 0,
            "attempts": [{"provider": "V15.5 wrapper", "error": f"{type(exc).__name__}: {exc}"}],
        }

    if (fresh_games is None or fresh_games.empty) and games_df is not None and not games_df.empty:
        fresh_games = games_df.copy()
        diag = dict(diag or {})
        diag["source"] = "shared verified slate fallback"
        diag["games"] = int(len(fresh_games))

    _render_schedule_status(diag, fresh_games)
    if fresh_games is None or fresh_games.empty:
        st.info("No verified MLB games are available for the selected Spread slate.")
        return

    st.caption(
        "🔒 Spread V15.5 isolation: this page owns its MLB schedule intake. "
        "Run-line probability math, H2H overlay and backtest logic remain unchanged."
    )

    base.render_spread_hub(fresh_games, section_header, status_info, team_logo, h)
    _render_scan_health(fresh_games)
