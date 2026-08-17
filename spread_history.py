from datetime import datetime, timedelta

import numpy as np
import requests
import streamlit as st

from engine import ET, MLB_API, clamp, sf


@st.cache_data(ttl=1800, show_spinner=False)
def h2h_last10(team_id, opponent_id, max_games=10, years_back=4):
    """Completed H2H games before today, always from team_id's perspective."""
    team_id = int(team_id)
    opponent_id = int(opponent_id)
    today = datetime.now(ET).date()
    end = today - timedelta(days=1)
    start = today.replace(year=today.year - int(years_back), month=1, day=1)

    r = requests.get(
        f"{MLB_API}/schedule",
        params={
            "sportId": 1,
            "teamId": team_id,
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
        },
        timeout=20,
    )
    r.raise_for_status()

    games = []
    for block in r.json().get("dates", []):
        for game in block.get("games", []):
            status = str((game.get("status") or {}).get("detailedState", ""))
            if "final" not in status.lower() and "game over" not in status.lower():
                continue

            teams = game.get("teams", {}) or {}
            away = teams.get("away", {}) or {}
            home = teams.get("home", {}) or {}
            away_id = int(((away.get("team") or {}).get("id") or 0))
            home_id = int(((home.get("team") or {}).get("id") or 0))
            if {away_id, home_id} != {team_id, opponent_id}:
                continue

            away_score = sf(away.get("score"))
            home_score = sf(home.get("score"))
            if away_score is None or home_score is None:
                continue

            if away_id == team_id:
                team_runs, opp_runs = float(away_score), float(home_score)
                location = "away"
            else:
                team_runs, opp_runs = float(home_score), float(away_score)
                location = "home"

            date_text = str(game.get("gameDate") or block.get("date") or "")[:10]
            try:
                game_date = datetime.fromisoformat(date_text).date()
            except Exception:
                game_date = today - timedelta(days=3650)

            games.append(
                {
                    "game_pk": game.get("gamePk"),
                    "date": game_date.isoformat(),
                    "year": game_date.year,
                    "team_runs": team_runs,
                    "opponent_runs": opp_runs,
                    "margin": team_runs - opp_runs,
                    "location": location,
                    "home_team_id": home_id,
                    "venue": (game.get("venue") or {}).get("name", "Unknown"),
                }
            )

    games.sort(key=lambda x: x["date"], reverse=True)
    return games[: int(max_games)]


def _weighted_rate(values, weights):
    if not values:
        return None
    w = np.asarray(weights, dtype=float)
    v = np.asarray(values, dtype=float)
    if w.sum() <= 0:
        return float(v.mean())
    return float(np.average(v, weights=w))


def summarize_h2h(games, line, current_home_team_id=None):
    n = len(games)
    if not n:
        return {
            "games": 0,
            "wins": 0,
            "losses": 0,
            "weighted_cover_rate": None,
            "raw_cover_rate": None,
            "avg_team_runs": None,
            "avg_opponent_runs": None,
            "avg_margin": None,
            "one_run_rate": None,
            "current_season_games": 0,
            "current_season_record": "0-0",
            "venue_games": 0,
            "venue_record": "0-0",
            "venue_cover_rate": None,
        }

    current_year = datetime.now(ET).year
    weights = []
    covers = []
    wins = []
    for i, game in enumerate(games):
        recency = 0.91 ** i
        season_boost = 1.35 if game["year"] == current_year else 1.08 if game["year"] == current_year - 1 else 0.92
        weights.append(recency * season_boost)
        covers.append(1.0 if game["margin"] + float(line) > 0 else 0.0)
        wins.append(1.0 if game["margin"] > 0 else 0.0)

    margins = [g["margin"] for g in games]
    team_runs = [g["team_runs"] for g in games]
    opp_runs = [g["opponent_runs"] for g in games]
    one_run = [1.0 if abs(g["margin"]) == 1 else 0.0 for g in games]

    current = [g for g in games if g["year"] == current_year]
    cw = sum(1 for g in current if g["margin"] > 0)
    cl = len(current) - cw

    venue = []
    if current_home_team_id is not None:
        venue = [g for g in games if int(g["home_team_id"]) == int(current_home_team_id)]
    vw = sum(1 for g in venue if g["margin"] > 0)
    vl = len(venue) - vw
    venue_cover = None
    if venue:
        venue_cover = float(np.mean([1.0 if g["margin"] + float(line) > 0 else 0.0 for g in venue]))

    total_wins = int(sum(1 for g in games if g["margin"] > 0))
    return {
        "games": n,
        "wins": total_wins,
        "losses": n - total_wins,
        "weighted_cover_rate": _weighted_rate(covers, weights),
        "raw_cover_rate": float(np.mean(covers)),
        "weighted_win_rate": _weighted_rate(wins, weights),
        "avg_team_runs": _weighted_rate(team_runs, weights),
        "avg_opponent_runs": _weighted_rate(opp_runs, weights),
        "avg_margin": _weighted_rate(margins, weights),
        "one_run_rate": _weighted_rate(one_run, weights),
        "current_season_games": len(current),
        "current_season_record": f"{cw}-{cl}",
        "venue_games": len(venue),
        "venue_record": f"{vw}-{vl}",
        "venue_cover_rate": venue_cover,
    }


def history_adjustment(
    team_id,
    opponent_id,
    line,
    current_home_team_id,
    selected_recent=None,
    opponent_recent=None,
):
    """Small, shrinkage-heavy context layer. Total effect is capped at +/-5 pts."""
    try:
        games = h2h_last10(team_id, opponent_id, 10, 4)
    except Exception:
        games = []
    summary = summarize_h2h(games, line, current_home_team_id)

    n = summary["games"]
    h2h_adj = 0.0
    if n and summary["weighted_cover_rate"] is not None:
        shrink = n / (n + 12.0)
        cover_edge = (summary["weighted_cover_rate"] - 0.50) * shrink
        margin_edge = float(summary["avg_margin"] or 0.0) + float(line)
        h2h_adj = 0.30 * cover_edge + 0.012 * clamp(margin_edge / 4.0, -1.0, 1.0)
        h2h_adj = clamp(h2h_adj, -0.038, 0.038)

    venue_adj = 0.0
    vg = int(summary.get("venue_games") or 0)
    vc = summary.get("venue_cover_rate")
    if vg >= 2 and vc is not None:
        venue_adj = (float(vc) - 0.50) * (vg / (vg + 6.0)) * 0.05
        venue_adj = clamp(venue_adj, -0.008, 0.008)

    # Recent form is already part of V15's core score model, so this is only a
    # tiny tie-breaker rather than a second full recent-form layer.
    recent_adj = 0.0
    if selected_recent and opponent_recent:
        rd_team = sf(selected_recent.get("run_diff_per_game"))
        rd_opp = sf(opponent_recent.get("run_diff_per_game"))
        wp_team = sf(selected_recent.get("win_pct"))
        wp_opp = sf(opponent_recent.get("win_pct"))
        if rd_team is not None and rd_opp is not None:
            recent_adj += clamp((rd_team - rd_opp) * 0.0025, -0.008, 0.008)
        if wp_team is not None and wp_opp is not None:
            recent_adj += clamp((wp_team - wp_opp) * 0.006, -0.004, 0.004)
        recent_adj = clamp(recent_adj, -0.010, 0.010)

    total = clamp(h2h_adj + venue_adj + recent_adj, -0.05, 0.05)
    return {
        "adjustment": total,
        "h2h_adjustment": h2h_adj,
        "venue_adjustment": venue_adj,
        "recent_tiebreaker": recent_adj,
        "summary": summary,
        "games": games,
    }


def adjusted_probability(core_probability, context):
    return clamp(float(core_probability) + float((context or {}).get("adjustment", 0.0)), 0.03, 0.97)
