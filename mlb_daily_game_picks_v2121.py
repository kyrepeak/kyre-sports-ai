"""MLB Daily Game Picks V2.1.2.1 — live-risk correctness hotfix.

Keeps V2.1.2 intact while correcting lineup relevance:
- Pitcher K checks the opponent batting order, not the pitcher's own lineup.
- game markets with incomplete lineups inside 60 minutes receive a monitor flag.
No production model or Pick Strength math changes.
"""
from __future__ import annotations

import streamlit as st

import mlb_daily_game_picks_v212 as previous

ui = previous.ui
controller = previous.controller
master = previous.master
bridge = previous.bridge
VERSION = "MLB Daily Game Picks V2.1.2.1 • LIVE-RISK CORRECTNESS"


def _lineup_context(c, games_df, snap):
    if not snap or not snap.get("ok"):
        return ("🕒 Lineup check unavailable", "neutral", "Official MLB lineup check could not be refreshed.")

    away_n = int(snap.get("away_lineup_count") or 0)
    home_n = int(snap.get("home_lineup_count") or 0)
    row = previous._game_row(games_df, c.get("game_pk"))
    away_team = str(row.get("away_team") or "") if row is not None else ""
    home_team = str(row.get("home_team") or "") if row is not None else ""

    market = str(c.get("market") or "")
    if market in previous.PLAYER_MARKETS:
        # Hitter props need the hitter's lineup. Pitcher K needs the opponent batting order.
        team = str(c.get("opponent") or "") if market == "Pitcher Strikeouts" else str(c.get("team") or "")
        if team == away_team:
            n, who = away_n, away_team
        elif team == home_team:
            n, who = home_n, home_team
        else:
            n, who = min(away_n, home_n), "Relevant team"
        if n >= 9:
            label = "✅ Opponent lineup confirmed" if market == "Pitcher Strikeouts" else "✅ Player lineup confirmed"
            return (label, "safe", f"{who} has a confirmed 9-player batting order in the official MLB feed.")
        if n > 0:
            label = "🟡 Opponent lineup partial" if market == "Pitcher Strikeouts" else "🟡 Player lineup partial"
            return (label, "warn", f"{who} has only {n}/9 batting-order spots posted.")
        label = "🕒 Opponent lineup pending" if market == "Pitcher Strikeouts" else "🕒 Player lineup pending"
        return (label, "warn", f"{who} has not posted a full official batting order yet.")

    if away_n >= 9 and home_n >= 9:
        return ("✅ Both lineups confirmed", "safe", "Both teams have confirmed 9-player batting orders in the official MLB feed.")
    if away_n >= 9 or home_n >= 9:
        return ("🟡 One lineup confirmed", "warn", f"Official batting orders: away {away_n}/9 • home {home_n}/9.")
    if away_n or home_n:
        return ("🟡 Lineups partial", "warn", f"Official batting orders: away {away_n}/9 • home {home_n}/9.")
    return ("🕒 Lineups pending", "warn", "Neither team has a complete official batting order posted yet.")


def _risk_context(c, games_df, snap, ts, baseline):
    warnings = []
    starter = previous._starter_change(c, games_df, snap, baseline)
    if starter:
        warnings.append(("critical", starter))

    lineup_label, lineup_cls, lineup_detail = _lineup_context(c, games_df, snap)
    weather_label, weather_cls, weather_detail = previous._weather_context(snap)
    if weather_cls == "warn":
        warnings.append(("warn", weather_detail))

    mins = previous._minutes_to_pitch(snap)
    age = previous._build_age_minutes(ts)
    if mins is not None:
        if mins <= 0:
            warnings.append(("critical", "Game has started or reached its scheduled start; this pregame card should no longer be treated as fresh."))
        elif mins <= 30 and age is not None and age > 5:
            warnings.append(("critical", f"First pitch is about {mins:.0f} minutes away and the card is {age:.0f} minutes old. Refresh before using it."))
        elif mins <= 90 and age is not None and age > 15:
            warnings.append(("warn", f"First pitch is about {mins:.0f} minutes away and the card is {age:.0f} minutes old. A refresh is recommended."))

        if lineup_cls == "warn":
            market = str(c.get("market") or "")
            if mins <= 90 and market in previous.PLAYER_MARKETS:
                warnings.append(("warn", f"{lineup_detail} First pitch is about {mins:.0f} minutes away."))
            elif mins <= 60 and market not in previous.PLAYER_MARKETS:
                warnings.append(("warn", f"{lineup_detail} First pitch is about {mins:.0f} minutes away; game-market inputs should be refreshed once lineups post."))

    if any(level == "critical" for level, _ in warnings):
        badge = ("🚨 REFRESH NOW", "critical")
    elif warnings:
        badge = ("⚠️ MONITOR", "warn")
    else:
        badge = ("✅ PREGAME CHECKS OK", "safe")

    return {
        "badge": badge,
        "warnings": warnings,
        "lineup": (lineup_label, lineup_cls, lineup_detail),
        "weather": (weather_label, weather_cls, weather_detail),
        "minutes_to_pitch": mins,
        "build_age": age,
    }


# V2.1.2 functions resolve these names from their module globals at runtime.
previous._lineup_context = _lineup_context
previous._risk_context = _risk_context


def render_daily_game_picks(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    previous._lineup_context = _lineup_context
    previous._risk_context = _risk_context
    st.caption("✅ V2.1.2.1 live-risk check: Pitcher K tracks opponent lineups; late incomplete game lineups trigger monitor status.")
    return previous.render_daily_game_picks(games_df, section_header, status_info, team_logo, h)
