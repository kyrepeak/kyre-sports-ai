"""Totals V17.2: V17.1 probability scanner plus live sportsbook line sync."""

import pandas as pd
import streamlit as st

import totals_hub_v171 as base
from live_odds_feed import get_api_key, get_bookmakers, render_live_slate_board, snapshots_for_games

MODEL_VERSION = "V17.2"
_ORIGINAL_DEFAULT_LINES = base._default_market_lines


def _synced_default_market_lines(rows):
    df = _ORIGINAL_DEFAULT_LINES(rows)
    key = get_api_key()
    if not key or df.empty:
        return df

    game_records = []
    for row in rows:
        if hasattr(row, "to_dict"):
            game_records.append(row.to_dict())
        elif isinstance(row, dict):
            game_records.append(dict(row))
    if not game_records:
        return df

    try:
        snaps = snapshots_for_games(pd.DataFrame(game_records), key, get_bookmakers())
    except Exception:
        return df

    for idx, item in df.iterrows():
        try:
            pk = int(item["game_pk"])
        except Exception:
            continue
        snap = snaps.get(pk)
        line = (snap or {}).get("total_line")
        if line is not None:
            df.at[idx, "Total Line"] = float(line)
    return df


def render_totals_hub(games_df, section_header, status_info, team_logo, h):
    st.caption("📡 V17.2 can auto-fill the current live total from the sportsbook feed. The V19.1 Live Game page is the state-aware in-play model.")
    render_live_slate_board(games_df, title="Live MLB Moneyline • Run Line • Total")

    old_default = base._default_market_lines
    try:
        base._default_market_lines = _synced_default_market_lines
        base.render_totals_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        base._default_market_lines = old_default
