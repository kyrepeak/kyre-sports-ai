import re
from collections import Counter
from datetime import datetime
from io import StringIO
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Kyre Sports AI",
    page_icon="🧠",
    layout="wide",
)

ET = ZoneInfo("America/New_York")
MLB_API = "https://statsapi.mlb.com/api/v1"
MLB_LIVE_API = "https://statsapi.mlb.com/api/v1.1"
SAVANT = "https://baseballsavant.mlb.com"
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 KyreSportsAI/1.0"}


# -----------------------------
# HELPERS
# -----------------------------

def current_season():
    return datetime.now(ET).year


def safe_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp(value, low, high):
    return max(low, min(high, value))


def percent_to_rate(value):
    number = safe_float(value)
    if number is None:
        return None
    return number / 100.0 if abs(number) > 1.0 else number


def innings_to_float(value):
    text = str(value or "0.0")
    if "." not in text:
        return safe_float(text, 0.0) or 0.0
    whole, outs = text.split(".", 1)
    whole_num = safe_float(whole, 0.0) or 0.0
    outs_num = int(outs[:1]) if outs[:1].isdigit() else 0
    return whole_num + min(max(outs_num, 0), 2) / 3.0


def probability_from_avg(avg, expected_ab):
    avg = clamp(avg, 0.0, 0.999)
    expected_ab = max(float(expected_ab), 0.0)
    p_zero = (1 - avg) ** expected_ab
    p_one_plus = 1 - p_zero
    p_exact_one = expected_ab * avg * ((1 - avg) ** max(expected_ab - 1, 0))
    p_exact_one = clamp(p_exact_one, 0.0, 1.0)
    return {
        "p_zero": p_zero,
        "p_one_plus": p_one_plus,
        "p_exact_one": p_exact_one,
        "p_two_plus": max(0.0, p_one_plus - p_exact_one),
        "expected_hits": avg * expected_ab,
    }


def combined_exposure_projection(starter_rate, bullpen_rate, starter_ab, bullpen_ab):
    starter_ab = max(float(starter_ab), 0.0)
    bullpen_ab = max(float(bullpen_ab), 0.0)
    total_ab = starter_ab + bullpen_ab

    p_zero = (
        ((1 - clamp(starter_rate, 0.0, 0.999)) ** starter_ab)
        * ((1 - clamp(bullpen_rate, 0.0, 0.999)) ** bullpen_ab)
    )
    p_one_plus = 1 - p_zero
    expected_hits = starter_rate * starter_ab + bullpen_rate * bullpen_ab
    effective_avg = expected_hits / total_ab if total_ab > 0 else 0.0
    smooth = probability_from_avg(effective_avg, total_ab)

    return {
        "p_zero": p_zero,
        "p_one_plus": p_one_plus,
        "p_exact_one": min(smooth["p_exact_one"], p_one_plus),
        "p_two_plus": max(0.0, p_one_plus - min(smooth["p_exact_one"], p_one_plus)),
        "expected_hits": expected_hits,
        "effective_avg": effective_avg,
    }


def lineup_expected_ab(position):
    return {
        1: 4.60,
        2: 4.50,
        3: 4.40,
        4: 4.30,
        5: 4.20,
        6: 4.10,
        7: 4.00,
        8: 3.90,
        9: 3.80,
    }.get(position, 4.10)


def first_existing_column(df, names):
    lookup = {str(c).strip().lower(): c for c in df.columns}
    for name in names:
        if name.lower() in lookup:
            return lookup[name.lower()]
    return None


def value_from_row(row, df, names, default=None):
    col = first_existing_column(df, names)
    if col is None:
        return default
    value = row.get(col, default)
    if pd.isna(value):
        return default
    return value


# -----------------------------
# LIVE MLB DATA
# -----------------------------

@st.cache_data(ttl=300)
def get_today_mlb_games():
    today_et = datetime.now(ET).strftime("%Y-%m-%d")
    response = requests.get(
        f"{MLB_API}/schedule",
        params={"sportId": 1, "date": today_et, "hydrate": "probablePitcher,team"},
        timeout=15,
    )
    response.raise_for_status()

    games = []
    for date_block in response.json().get("dates", []):
        for game in date_block.get("games", []):
            away_block = game["teams"]["away"]
            home_block = game["teams"]["home"]
            away_team = away_block["team"]
            home_team = home_block["team"]
            away_pitcher = away_block.get("probablePitcher", {})
            home_pitcher = home_block.get("probablePitcher", {})
            game_time = datetime.fromisoformat(
                game["gameDate"].replace("Z", "+00:00")
            ).astimezone(ET)
            venue = game.get("venue", {}) or {}

            games.append(
                {
                    "game_pk": game.get("gamePk"),
                    "venue_name": venue.get("name", "Unknown"),
                    "away_team_id": away_team.get("id"),
                    "away_team": away_team.get("name", "Unknown"),
                    "home_team_id": home_team.get("id"),
                    "home_team": home_team.get("name", "Unknown"),
                    "away_pitcher_id": away_pitcher.get("id"),
                    "away_pitcher": away_pitcher.get("fullName", "TBD"),
                    "home_pitcher_id": home_pitcher.get("id"),
                    "home_pitcher": home_pitcher.get("fullName", "TBD"),
                    "first_pitch_et": game_time.strftime("%I:%M %p").lstrip("0"),
                    "status": game.get("status", {}).get("detailedState", "Unknown"),
                }
            )
    return pd.DataFrame(games), today_et


@st.cache_data(ttl=3600)
def find_mlb_player(player_name):
    response = requests.get(
        f"{MLB_API}/people/search",
        params={"names": player_name},
        timeout=15,
    )
    response.raise_for_status()
    people = response.json().get("people", [])
    if not people:
        return None

    player_id = people[0].get("id")
    detail = requests.get(
        f"{MLB_API}/people/{player_id}",
        params={"hydrate": "currentTeam"},
        timeout=15,
    )
    detail.raise_for_status()
    people = detail.json().get("people", [])
    if not people:
        return None

    person = people[0]
    team = person.get("currentTeam", {}) or {}
    return {
        "id": person.get("id"),
        "name": person.get("fullName", player_name),
        "team_id": team.get("id"),
        "team_name": team.get("name", "Unknown"),
        "bat_side": person.get("batSide", {}).get("code", "?"),
    }


@st.cache_data(ttl=600)
def get_player_hitting_stats(player_id):
    response = requests.get(
        f"{MLB_API}/people/{player_id}/stats",
        params={"stats": "season", "group": "hitting", "season": current_season()},
        timeout=15,
    )
    response.raise_for_status()
    groups = response.json().get("stats", [])
    if not groups or not groups[0].get("splits"):
        return None
    stat = groups[0]["splits"][0].get("stat", {})
    return {
        "season": current_season(),
        "games": stat.get("gamesPlayed", 0),
        "plate_appearances": stat.get("plateAppearances", 0),
        "at_bats": stat.get("atBats", 0),
        "hits": stat.get("hits", 0),
        "home_runs": stat.get("homeRuns", 0),
        "walks": stat.get("baseOnBalls", 0),
        "strikeouts": stat.get("strikeOuts", 0),
        "avg": stat.get("avg", ".000"),
        "obp": stat.get("obp", ".000"),
        "slg": stat.get("slg", ".000"),
        "ops": stat.get("ops", ".000"),
    }


@st.cache_data(ttl=600)
def get_pitcher_stats(pitcher_id):
    person_res = requests.get(f"{MLB_API}/people/{pitcher_id}", timeout=15)
    person_res.raise_for_status()
    people = person_res.json().get("people", [])
    if not people:
        return None
    person = people[0]

    stat_res = requests.get(
        f"{MLB_API}/people/{pitcher_id}/stats",
        params={"stats": "season", "group": "pitching", "season": current_season()},
        timeout=15,
    )
    stat_res.raise_for_status()
    groups = stat_res.json().get("stats", [])
    stat = {}
    if groups and groups[0].get("splits"):
        stat = groups[0]["splits"][0].get("stat", {})

    innings_text = stat.get("inningsPitched", "0.0")
    true_innings = innings_to_float(innings_text)
    strikeouts = safe_float(stat.get("strikeOuts"), 0.0) or 0.0
    games = int(safe_float(stat.get("gamesPlayed"), 0) or 0)
    starts = int(safe_float(stat.get("gamesStarted"), 0) or 0)

    return {
        "id": int(pitcher_id),
        "name": person.get("fullName", "Unknown"),
        "hand": person.get("pitchHand", {}).get("code", "?"),
        "era": stat.get("era", "N/A"),
        "whip": stat.get("whip", "N/A"),
        "wins": stat.get("wins", 0),
        "losses": stat.get("losses", 0),
        "games": games,
        "games_started": starts,
        "innings": innings_text,
        "true_innings": true_innings,
        "hits_allowed": safe_float(stat.get("hits"), 0.0) or 0.0,
        "walks": safe_float(stat.get("baseOnBalls"), 0.0) or 0.0,
        "earned_runs": safe_float(stat.get("earnedRuns"), 0.0) or 0.0,
        "strikeouts": strikeouts,
        "k9": strikeouts * 9 / true_innings if true_innings > 0 else None,
    }


@st.cache_data(ttl=600)
def get_hitter_vs_hand_stats(player_id, pitcher_hand):
    hand = str(pitcher_hand or "").upper()
    if hand not in {"R", "L"}:
        return None
    sit_code = "vr" if hand == "R" else "vl"
    label = "vs RHP" if hand == "R" else "vs LHP"

    for stat_type in ["statSplits", "season"]:
        response = requests.get(
            f"{MLB_API}/people/{player_id}/stats",
            params={
                "stats": stat_type,
                "group": "hitting",
                "season": current_season(),
                "sitCodes": sit_code,
            },
            timeout=15,
        )
        if response.status_code >= 400:
            continue
        for group in response.json().get("stats", []):
            for split in group.get("splits", []):
                info = split.get("split", {}) or {}
                code = str(info.get("code", "")).lower()
                desc = str(info.get("description", "")).lower()
                explicit = (
                    code == sit_code
                    or (hand == "R" and "right" in desc)
                    or (hand == "L" and "left" in desc)
                )
                if stat_type == "statSplits" or explicit:
                    stat = split.get("stat", {})
                    if stat:
                        return {
                            "label": label,
                            "at_bats": stat.get("atBats", 0),
                            "hits": stat.get("hits", 0),
                            "home_runs": stat.get("homeRuns", 0),
                            "strikeouts": stat.get("strikeOuts", 0),
                            "avg": stat.get("avg", ".000"),
                            "obp": stat.get("obp", ".000"),
                            "slg": stat.get("slg", ".000"),
                            "ops": stat.get("ops", ".000"),
                        }
    return None


@st.cache_data(ttl=600)
def get_recent_form(player_id, games=10):
    response = requests.get(
        f"{MLB_API}/people/{player_id}/stats",
        params={"stats": "gameLog", "group": "hitting", "season": current_season()},
        timeout=15,
    )
    response.raise_for_status()
    groups = response.json().get("stats", [])
    if not groups or not groups[0].get("splits"):
        return None

    splits = groups[0]["splits"][-games:]
    total_ab = total_hits = total_hr = total_bb = total_so = 0
    hit_games = 0
    game_pks = []
    for split in splits:
        stat = split.get("stat", {}) or {}
        ab = int(safe_float(stat.get("atBats"), 0) or 0)
        hits = int(safe_float(stat.get("hits"), 0) or 0)
        total_ab += ab
        total_hits += hits
        total_hr += int(safe_float(stat.get("homeRuns"), 0) or 0)
        total_bb += int(safe_float(stat.get("baseOnBalls"), 0) or 0)
        total_so += int(safe_float(stat.get("strikeOuts"), 0) or 0)
        hit_games += 1 if hits > 0 else 0
        game_pk = split.get("game", {}).get("gamePk")
        if game_pk:
            game_pks.append(game_pk)

    return {
        "games": len(splits),
        "at_bats": total_ab,
        "hits": total_hits,
        "home_runs": total_hr,
        "walks": total_bb,
        "strikeouts": total_so,
        "avg": total_hits / total_ab if total_ab > 0 else None,
        "hit_games": hit_games,
        "game_pks": game_pks,
    }


@st.cache_data(ttl=180)
def get_lineup_position(game_pk, player_id, team_side):
    if not game_pk or team_side not in {"home", "away"}:
        return None
    response = requests.get(f"{MLB_API}/game/{game_pk}/boxscore", timeout=15)
    if response.status_code >= 400:
        return None
    team = response.json().get("teams", {}).get(team_side, {}) or {}
    order = [int(x) for x in team.get("battingOrder", []) if str(x).isdigit()]
    if int(player_id) in order:
        return order.index(int(player_id)) + 1
    player = (team.get("players", {}) or {}).get(f"ID{player_id}", {}) or {}
    value = str(player.get("battingOrder", ""))
    if value.isdigit():
        num = int(value)
        return int(clamp(num // 100 if num >= 100 else num, 1, 9))
    return None


@st.cache_data(ttl=1800)
def estimate_recent_lineup_position(player_id, game_pks, max_games=5):
    positions = []
    for game_pk in list(game_pks)[-max_games:]:
        for side in ("home", "away"):
            pos = get_lineup_position(game_pk, player_id, side)
            if pos:
                positions.append(pos)
                break
    if not positions:
        return None
    counts = Counter(positions)
    top_count = counts.most_common(1)[0][1]
    tied = [p for p, c in counts.items() if c == top_count]
    projected = tied[0] if len(tied) == 1 else int(round(sum(positions) / len(positions)))
    return {"position": int(clamp(projected, 1, 9)), "sample_games": len(positions)}


@st.cache_data(ttl=180)
def get_game_environment(game_pk):
    if not game_pk:
        return None
    response = requests.get(f"{MLB_LIVE_API}/game/{game_pk}/feed/live", timeout=15)
    if response.status_code >= 400:
        return None
    game_data = response.json().get("gameData", {}) or {}
    venue = game_data.get("venue", {}) or {}
    weather = game_data.get("weather", {}) or {}
    field_info = venue.get("fieldInfo", {}) or {}
    return {
        "venue_name": venue.get("name", "Unknown"),
        "roof_type": field_info.get("roofType", "Unknown"),
        "temperature": safe_float(weather.get("temp")),
        "condition": weather.get("condition", "Unknown"),
        "wind": weather.get("wind", "Unknown"),
    }


@st.cache_data(ttl=1800)
def get_statcast_profile(player_id):
    year = current_season()

    expected_url = (
        f"{SAVANT}/leaderboard/expected_statistics"
        f"?type=batter&year={year}&position=&team=&filterType=pa&min=1&csv=true"
    )
    contact_url = (
        f"{SAVANT}/leaderboard/statcast"
        f"?type=batter&year={year}&position=&team=&min=1&csv=true"
    )

    expected_res = requests.get(expected_url, headers=HTTP_HEADERS, timeout=20)
    contact_res = requests.get(contact_url, headers=HTTP_HEADERS, timeout=20)
    expected_res.raise_for_status()
    contact_res.raise_for_status()

    expected_df = pd.read_csv(StringIO(expected_res.text))
    contact_df = pd.read_csv(StringIO(contact_res.text))

    exp_id_col = first_existing_column(expected_df, ["player_id", "id"])
    con_id_col = first_existing_column(contact_df, ["player_id", "id"])
    if exp_id_col is None or con_id_col is None:
        return None

    exp_rows = expected_df[
        pd.to_numeric(expected_df[exp_id_col], errors="coerce") == int(player_id)
    ]
    con_rows = contact_df[
        pd.to_numeric(contact_df[con_id_col], errors="coerce") == int(player_id)
    ]
    if exp_rows.empty and con_rows.empty:
        return None

    exp_row = exp_rows.iloc[0] if not exp_rows.empty else pd.Series(dtype=object)
    con_row = con_rows.iloc[0] if not con_rows.empty else pd.Series(dtype=object)

    return {
        "source": "Baseball Savant / Statcast",
        "year": year,
        "xba": safe_float(value_from_row(exp_row, expected_df, ["est_ba", "xba"])) if not exp_rows.empty else None,
        "xslg": safe_float(value_from_row(exp_row, expected_df, ["est_slg", "xslg"])) if not exp_rows.empty else None,
        "xwoba": safe_float(value_from_row(exp_row, expected_df, ["est_woba", "xwoba"])) if not exp_rows.empty else None,
        "pa": safe_float(value_from_row(exp_row, expected_df, ["pa", "plate_appearances"], 0), 0.0) if not exp_rows.empty else 0.0,
        "bip": safe_float(value_from_row(exp_row, expected_df, ["bip", "batted_ball"], 0), 0.0) if not exp_rows.empty else 0.0,
        "bbe": safe_float(value_from_row(con_row, contact_df, ["batted_ball", "bbe"], 0), 0.0) if not con_rows.empty else 0.0,
        "avg_ev": safe_float(value_from_row(con_row, contact_df, ["exit_velocity_avg", "avg_exit_velocity"])) if not con_rows.empty else None,
        "launch_angle": safe_float(value_from_row(con_row, contact_df, ["launch_angle_avg", "avg_launch_angle"])) if not con_rows.empty else None,
        "hard_hit_rate": percent_to_rate(value_from_row(con_row, contact_df, ["hard_hit_percent", "hard_hit_pct"])) if not con_rows.empty else None,
        "barrel_rate": percent_to_rate(value_from_row(con_row, contact_df, ["barrel_batted_rate", "barrel_percent", "brl_percent"])) if not con_rows.empty else None,
    }


@st.cache_data(ttl=900)
def get_team_bullpen_profile(team_id, opposing_starter_id=None):
    """Build a current-season relief profile from the opponent's active pitching staff."""
    if not team_id:
        return None

    roster_response = requests.get(
        f"{MLB_API}/teams/{int(team_id)}/roster",
        params={"rosterType": "active"},
        timeout=15,
    )
    roster_response.raise_for_status()

    pitcher_ids = []
    for entry in roster_response.json().get("roster", []):
        person = entry.get("person", {}) or {}
        position = entry.get("position", {}) or {}
        if position.get("abbreviation") == "P" and person.get("id"):
            pitcher_ids.append(int(person["id"]))

    relievers = []
    for pitcher_id in pitcher_ids[:16]:
        if opposing_starter_id and int(pitcher_id) == int(opposing_starter_id):
            continue

        try:
            profile = get_pitcher_stats(pitcher_id)
        except requests.RequestException:
            continue

        if not profile or profile.get("true_innings", 0.0) <= 0:
            continue

        games = profile.get("games", 0) or 0
        starts = profile.get("games_started", 0) or 0
        start_share = starts / max(games, 1)

        # Keep pitchers whose usage is predominantly relief work.
        if starts <= 3 or start_share <= 0.35:
            relievers.append(profile)

    if not relievers:
        return None

    total_ip = sum(p.get("true_innings", 0.0) or 0.0 for p in relievers)
    if total_ip <= 0:
        return None

    earned_runs = sum(p.get("earned_runs", 0.0) or 0.0 for p in relievers)
    hits = sum(p.get("hits_allowed", 0.0) or 0.0 for p in relievers)
    walks = sum(p.get("walks", 0.0) or 0.0 for p in relievers)
    strikeouts = sum(p.get("strikeouts", 0.0) or 0.0 for p in relievers)

    r_ip = sum(
        p.get("true_innings", 0.0) or 0.0
        for p in relievers
        if str(p.get("hand", "")).upper() == "R"
    )
    l_ip = sum(
        p.get("true_innings", 0.0) or 0.0
        for p in relievers
        if str(p.get("hand", "")).upper() == "L"
    )
    hand_ip = r_ip + l_ip
    r_share = r_ip / hand_ip if hand_ip > 0 else 0.60

    return {
        "reliever_count": len(relievers),
        "innings": total_ip,
        "era": earned_runs * 9 / total_ip,
        "whip": (hits + walks) / total_ip,
        "k9": strikeouts * 9 / total_ip,
        "right_share": clamp(r_share, 0.0, 1.0),
        "left_share": clamp(1 - r_share, 0.0, 1.0),
        "source": "Active-roster relief aggregate",
    }


def find_player_matchup(games_df, team_id):
    if games_df.empty or team_id is None:
        return None
    for _, game in games_df.iterrows():
        if game["away_team_id"] == team_id:
            return {
                "game_pk": game["game_pk"],
                "team_side": "away",
                "venue_name": game.get("venue_name", "Unknown"),
                "opponent_team_id": game["home_team_id"],
                "opponent": game["home_team"],
                "location": "Away",
                "pitcher_id": game["home_pitcher_id"],
                "pitcher": game["home_pitcher"],
                "first_pitch": game["first_pitch_et"],
                "status": game["status"],
            }
        if game["home_team_id"] == team_id:
            return {
                "game_pk": game["game_pk"],
                "team_side": "home",
                "venue_name": game.get("venue_name", "Unknown"),
                "opponent_team_id": game["away_team_id"],
                "opponent": game["away_team"],
                "location": "Home",
                "pitcher_id": game["away_pitcher_id"],
                "pitcher": game["away_pitcher"],
                "first_pitch": game["first_pitch_et"],
                "status": game["status"],
            }
    return None


# -----------------------------
# MODEL LAYERS
# -----------------------------

def build_handedness_avg(season_avg, hand_split):
    if not hand_split:
        return season_avg, 0.0
    split_avg = safe_float(hand_split.get("avg"))
    split_ab = safe_float(hand_split.get("at_bats"), 0.0) or 0.0
    if split_avg is None or split_ab <= 0:
        return season_avg, 0.0
    weight = split_ab / (split_ab + 200.0)
    return season_avg * (1 - weight) + split_avg * weight, weight


def calculate_pitcher_quality(pitcher):
    if not pitcher:
        return None
    era = safe_float(pitcher.get("era"))
    whip = safe_float(pitcher.get("whip"))
    k9 = pitcher.get("k9")
    innings = pitcher.get("true_innings", 0.0) or 0.0
    if era is None or whip is None:
        return None

    raw = (
        0.40 * ((4.20 - era) / 4.20)
        + 0.40 * ((1.30 - whip) / 1.30)
        + 0.20 * (((k9 - 8.50) / 8.50) if k9 is not None else 0.0)
    )
    reliability = innings / (innings + 60.0) if innings > 0 else 0.0
    quality = raw * reliability
    adjustment = clamp(-0.25 * quality, -0.08, 0.08)

    if quality >= 0.10:
        difficulty = "Very Tough"
    elif quality >= 0.04:
        difficulty = "Tough"
    elif quality <= -0.10:
        difficulty = "Very Favorable"
    elif quality <= -0.04:
        difficulty = "Favorable"
    else:
        difficulty = "Near Neutral"

    return {
        "reliability": reliability,
        "rate_adjustment": adjustment,
        "difficulty": difficulty,
    }


def calculate_bullpen_quality(bullpen):
    if not bullpen:
        return None

    era = safe_float(bullpen.get("era"))
    whip = safe_float(bullpen.get("whip"))
    k9 = safe_float(bullpen.get("k9"))
    innings = safe_float(bullpen.get("innings"), 0.0) or 0.0
    if era is None or whip is None:
        return None

    raw = (
        0.40 * ((4.20 - era) / 4.20)
        + 0.40 * ((1.30 - whip) / 1.30)
        + 0.20 * (((k9 - 8.50) / 8.50) if k9 is not None else 0.0)
    )
    reliability = innings / (innings + 120.0) if innings > 0 else 0.0
    quality = raw * reliability
    adjustment = clamp(-0.18 * quality, -0.05, 0.05)

    if quality >= 0.10:
        difficulty = "Very Tough"
    elif quality >= 0.04:
        difficulty = "Tough"
    elif quality <= -0.10:
        difficulty = "Very Favorable"
    elif quality <= -0.04:
        difficulty = "Favorable"
    else:
        difficulty = "Near Neutral"

    return {
        "reliability": reliability,
        "rate_adjustment": adjustment,
        "difficulty": difficulty,
    }


def apply_recent_form(base_avg, recent_form):
    if not recent_form or recent_form.get("avg") is None:
        return base_avg, 0.0, None
    recent_avg = recent_form["avg"]
    recent_ab = recent_form.get("at_bats", 0) or 0
    if recent_ab <= 0:
        return base_avg, 0.0, recent_avg
    weight = clamp(0.22 * (recent_ab / (recent_ab + 45.0)), 0.0, 0.22)
    return base_avg * (1 - weight) + recent_avg * weight, weight, recent_avg


PARK_HIT_ADJUSTMENTS = {
    "coors field": 0.035,
    "fenway park": 0.018,
    "kauffman stadium": 0.012,
    "chase field": 0.010,
    "great american ball park": 0.010,
    "citizens bank park": 0.008,
    "wrigley field": 0.006,
    "yankee stadium": 0.005,
    "daikin park": 0.004,
    "minute maid park": 0.004,
    "globe life field": 0.003,
    "camden yards": 0.002,
    "rogers centre": 0.002,
    "truist park": 0.002,
    "target field": 0.001,
    "busch stadium": 0.000,
    "progressive field": 0.000,
    "comerica park": 0.000,
    "loandepot park": -0.003,
    "dodger stadium": -0.004,
    "american family field": -0.004,
    "citi field": -0.006,
    "angel stadium": -0.006,
    "nationals park": -0.006,
    "rate field": -0.007,
    "sutter health park": -0.007,
    "petco park": -0.010,
    "t-mobile park": -0.016,
    "oracle park": -0.018,
}


def parse_wind_speed(text):
    match = re.search(r"(\d+(?:\.\d+)?)\s*mph", str(text or ""), flags=re.I)
    return safe_float(match.group(1)) if match else None


def calculate_environment_adjustment(environment, fallback_venue="Unknown"):
    env = environment or {}
    venue = env.get("venue_name") or fallback_venue or "Unknown"
    park = PARK_HIT_ADJUSTMENTS.get(venue.lower().strip(), 0.0)
    temp = env.get("temperature")
    condition = str(env.get("condition") or "Unknown")
    wind = str(env.get("wind") or "Unknown")
    roof = str(env.get("roof_type") or "Unknown")
    indoor = any(
        x in condition.lower()
        for x in ["dome", "indoor", "roof closed", "closed roof"]
    )

    temp_adj = 0.0
    if temp is not None and not indoor:
        temp_adj = clamp(((temp - 72.0) / 10.0) * 0.004, -0.015, 0.015)

    wind_adj = 0.0
    speed = parse_wind_speed(wind)
    if speed is not None and not indoor:
        scale = clamp(speed / 15.0, 0.0, 1.5)
        lower = wind.lower()
        if "out to" in lower or "blowing out" in lower:
            wind_adj = clamp(0.012 * scale, 0.0, 0.018)
        elif "in from" in lower or "blowing in" in lower:
            wind_adj = clamp(-0.012 * scale, -0.018, 0.0)

    total = clamp(park + temp_adj + wind_adj, -0.05, 0.05)
    if total >= 0.025:
        grade = "Strong Hitter Boost"
    elif total >= 0.008:
        grade = "Hitter Friendly"
    elif total <= -0.025:
        grade = "Strong Pitcher Boost"
    elif total <= -0.008:
        grade = "Pitcher Friendly"
    else:
        grade = "Near Neutral"

    return {
        "venue_name": venue,
        "temperature": temp,
        "condition": condition,
        "wind": wind,
        "roof_type": roof,
        "park_adjustment": park,
        "temperature_adjustment": temp_adj,
        "wind_adjustment": wind_adj,
        "total_adjustment": total,
        "grade": grade,
    }


def apply_statcast_quality(base_avg, statcast):
    if not statcast:
        return base_avg, {
            "available": False,
            "reliability": 0.0,
            "xba_weight": 0.0,
            "quality_adjustment": 0.0,
            "pre_quality_avg": base_avg,
            "final_avg": base_avg,
            "grade": "Unavailable",
        }

    xba = statcast.get("xba")
    bbe = safe_float(statcast.get("bbe"), 0.0) or 0.0
    pa = safe_float(statcast.get("pa"), 0.0) or 0.0
    sample = max(bbe, pa * 0.65)
    reliability = sample / (sample + 120.0) if sample > 0 else 0.0

    xba_weight = 0.0
    xba_blend = base_avg
    if xba is not None and 0.050 <= xba <= 0.500:
        xba_weight = clamp(0.22 * reliability, 0.0, 0.22)
        xba_blend = base_avg * (1 - xba_weight) + xba * xba_weight

    components = []
    avg_ev = statcast.get("avg_ev")
    hard_hit = statcast.get("hard_hit_rate")
    barrel = statcast.get("barrel_rate")
    if avg_ev is not None:
        components.append(0.35 * clamp((avg_ev - 88.5) / 7.0, -1.5, 1.5))
    if hard_hit is not None:
        components.append(0.35 * clamp((hard_hit - 0.40) / 0.20, -1.5, 1.5))
    if barrel is not None:
        components.append(0.30 * clamp((barrel - 0.08) / 0.09, -1.5, 1.5))

    quality_score = sum(components) if components else 0.0
    quality_adjustment = clamp(
        0.025 * quality_score * reliability,
        -0.04,
        0.04,
    )
    final_avg = clamp(xba_blend * (1 + quality_adjustment), 0.050, 0.500)

    if quality_adjustment >= 0.020:
        grade = "Elite Contact"
    elif quality_adjustment >= 0.007:
        grade = "Strong Contact"
    elif quality_adjustment <= -0.020:
        grade = "Weak Contact"
    elif quality_adjustment <= -0.007:
        grade = "Below-Average Contact"
    else:
        grade = "Near Neutral"

    return final_avg, {
        "available": True,
        "reliability": reliability,
        "xba_weight": xba_weight,
        "quality_adjustment": quality_adjustment,
        "pre_quality_avg": xba_blend,
        "final_avg": final_avg,
        "grade": grade,
    }


def build_bullpen_rate(
    season_avg,
    split_r,
    split_l,
    bullpen,
    recent,
    environment,
    statcast,
    fallback_venue="Unknown",
):
    if not bullpen:
        return None

    r_avg, _ = build_handedness_avg(season_avg, split_r)
    l_avg, _ = build_handedness_avg(season_avg, split_l)
    r_share = bullpen.get("right_share", 0.60)
    handed_avg = r_avg * r_share + l_avg * (1 - r_share)

    bullpen_quality = calculate_bullpen_quality(bullpen)
    bullpen_adj = (
        bullpen_quality["rate_adjustment"]
        if bullpen_quality
        else 0.0
    )
    post_bullpen = clamp(handed_avg * (1 + bullpen_adj), 0.050, 0.500)
    post_recent, recent_weight, _ = apply_recent_form(post_bullpen, recent)

    env_model = calculate_environment_adjustment(environment, fallback_venue)
    post_env = clamp(
        post_recent * (1 + env_model["total_adjustment"]),
        0.050,
        0.500,
    )
    final_rate, statcast_model = apply_statcast_quality(post_env, statcast)

    return {
        "rate": final_rate,
        "handed_avg": handed_avg,
        "quality": bullpen_quality,
        "quality_adjustment": bullpen_adj,
        "recent_weight": recent_weight,
        "environment": env_model,
        "statcast": statcast_model,
    }


def estimate_starter_exposure(pitcher, expected_ab):
    if not pitcher:
        return {
            "starter_ip": 5.0,
            "starter_share": 0.56,
            "starter_ab": expected_ab * 0.56,
            "bullpen_ab": expected_ab * 0.44,
        }

    starts = pitcher.get("games_started", 0) or 0
    innings = pitcher.get("true_innings", 0.0) or 0.0
    avg_ip = innings / starts if starts > 0 else 5.0
    starter_ip = clamp(avg_ip, 4.0, 6.5)
    starter_share = clamp(starter_ip / 9.0, 0.44, 0.72)

    return {
        "starter_ip": starter_ip,
        "starter_share": starter_share,
        "starter_ab": expected_ab * starter_share,
        "bullpen_ab": expected_ab * (1 - starter_share),
    }


# -----------------------------
# UI
# -----------------------------

st.title("🧠 KYRE SPORTS AI")
st.subheader("Sports Projection & Analytics Engine")
st.divider()

sport = st.selectbox("Choose Sport", ["MLB", "WNBA"])

if sport == "MLB":
    try:
        games_df, game_date = get_today_mlb_games()
    except requests.RequestException:
        games_df = pd.DataFrame()
        game_date = datetime.now(ET).strftime("%Y-%m-%d")

    st.header("📡 Live MLB Data")
    if st.button("🔄 LOAD TODAY'S MLB GAMES", use_container_width=True):
        if games_df.empty:
            st.warning("No MLB games found.")
        else:
            st.success(f"Schedule loaded for {game_date}")
            display = games_df[
                [
                    "away_team",
                    "home_team",
                    "first_pitch_et",
                    "away_pitcher",
                    "home_pitcher",
                    "status",
                ]
            ].rename(
                columns={
                    "away_team": "Away",
                    "home_team": "Home",
                    "first_pitch_et": "First Pitch (ET)",
                    "away_pitcher": "Away Pitcher",
                    "home_pitcher": "Home Pitcher",
                    "status": "Status",
                }
            )
            st.dataframe(display, use_container_width=True, hide_index=True)

    st.divider()
    market = st.selectbox(
        "Choose Market",
        [
            "1+ Hit",
            "2+ Hits",
            "Home Run",
            "Hits + Runs + RBIs",
            "Moneyline",
            "Run Line",
            "Game Total",
        ],
    )

    if market == "1+ Hit":
        st.header("⚾ MLB 1+ Hit Projection")
        player_name = st.text_input(
            "Player Name",
            placeholder="Example: Yordan Alvarez",
        )

        if st.button("📡 LOAD PLAYER + MATCHUP", use_container_width=True):
            st.session_state.pop("player_data", None)

            if not player_name.strip():
                st.error("Enter a player name.")
            else:
                try:
                    player = find_mlb_player(player_name.strip())

                    if not player:
                        st.error("Player not found.")
                    else:
                        stats = get_player_hitting_stats(player["id"])
                        recent = get_recent_form(player["id"], 10)
                        matchup = find_player_matchup(games_df, player["team_id"])

                        pitcher = None
                        split_r = None
                        split_l = None
                        confirmed_lineup = None
                        recent_lineup = None
                        environment = None
                        statcast = None
                        bullpen = None
                        data_warnings = []

                        if matchup:
                            confirmed_lineup = get_lineup_position(
                                matchup["game_pk"],
                                player["id"],
                                matchup["team_side"],
                            )
                            environment = get_game_environment(matchup["game_pk"])

                        if recent:
                            recent_lineup = estimate_recent_lineup_position(
                                player["id"],
                                recent.get("game_pks", []),
                                5,
                            )

                        if matchup and pd.notna(matchup.get("pitcher_id")):
                            pitcher = get_pitcher_stats(int(matchup["pitcher_id"]))

                        split_r = get_hitter_vs_hand_stats(player["id"], "R")
                        split_l = get_hitter_vs_hand_stats(player["id"], "L")

                        if matchup:
                            try:
                                bullpen = get_team_bullpen_profile(
                                    matchup.get("opponent_team_id"),
                                    matchup.get("pitcher_id"),
                                )
                            except Exception as exc:
                                data_warnings.append(
                                    f"Bullpen profile unavailable: {exc}"
                                )

                        try:
                            statcast = get_statcast_profile(player["id"])
                        except Exception as exc:
                            data_warnings.append(
                                f"Statcast profile unavailable: {exc}"
                            )

                        st.session_state["player_data"] = {
                            "player": player,
                            "stats": stats,
                            "recent": recent,
                            "matchup": matchup,
                            "pitcher": pitcher,
                            "split_r": split_r,
                            "split_l": split_l,
                            "confirmed_lineup": confirmed_lineup,
                            "recent_lineup": recent_lineup,
                            "environment": environment,
                            "statcast": statcast,
                            "bullpen": bullpen,
                            "warnings": data_warnings,
                        }

                except requests.RequestException as exc:
                    st.error(f"Could not load MLB data: {exc}")

        if "player_data" in st.session_state:
            data = st.session_state["player_data"]
            player = data["player"]
            stats = data["stats"]
            recent = data.get("recent")
            matchup = data.get("matchup")
            pitcher = data.get("pitcher")
            split_r = data.get("split_r")
            split_l = data.get("split_l")
            environment = data.get("environment")
            statcast = data.get("statcast")
            bullpen = data.get("bullpen")

            if stats:
                st.success(f"Live data loaded for {player['name']}")
                st.subheader(f"📊 {player['name']} — {stats['season']}")
                st.caption(
                    f"Team: {player['team_name']} • Bats: {player['bat_side']}"
                )

                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.metric("AVG", stats["avg"])
                with c2:
                    st.metric("Hits", stats["hits"])
                with c3:
                    st.metric("At-Bats", stats["at_bats"])
                with c4:
                    st.metric("Games", stats["games"])

                c5, c6, c7, c8 = st.columns(4)
                with c5:
                    st.metric("HR", stats["home_runs"])
                with c6:
                    st.metric("OBP", stats["obp"])
                with c7:
                    st.metric("SLG", stats["slg"])
                with c8:
                    st.metric("OPS", stats["ops"])

                st.divider()
                st.subheader("🔥 Recent Form — Last 10 Games")
                if recent and recent.get("avg") is not None:
                    r1, r2, r3, r4 = st.columns(4)
                    with r1:
                        st.metric("Recent AVG", f"{recent['avg']:.3f}")
                    with r2:
                        st.metric("Hits", recent["hits"])
                    with r3:
                        st.metric("Recent AB", recent["at_bats"])
                    with r4:
                        st.metric(
                            "Hit Games",
                            f"{recent['hit_games']}/{recent['games']}",
                        )
                else:
                    st.info("Recent game-log data was not available.")

                st.divider()
                st.subheader("📡 Statcast Contact Quality")
                if statcast:
                    s1, s2, s3, s4 = st.columns(4)
                    with s1:
                        st.metric(
                            "xBA",
                            f"{statcast['xba']:.3f}"
                            if statcast.get("xba") is not None
                            else "N/A",
                        )
                    with s2:
                        st.metric(
                            "Avg Exit Velo",
                            f"{statcast['avg_ev']:.1f} mph"
                            if statcast.get("avg_ev") is not None
                            else "N/A",
                        )
                    with s3:
                        st.metric(
                            "Hard-Hit %",
                            f"{statcast['hard_hit_rate'] * 100:.1f}%"
                            if statcast.get("hard_hit_rate") is not None
                            else "N/A",
                        )
                    with s4:
                        st.metric(
                            "Barrel %",
                            f"{statcast['barrel_rate'] * 100:.1f}%"
                            if statcast.get("barrel_rate") is not None
                            else "N/A",
                        )

                    s5, s6, s7 = st.columns(3)
                    with s5:
                        st.metric(
                            "xSLG",
                            f"{statcast['xslg']:.3f}"
                            if statcast.get("xslg") is not None
                            else "N/A",
                        )
                    with s6:
                        st.metric(
                            "xwOBA",
                            f"{statcast['xwoba']:.3f}"
                            if statcast.get("xwoba") is not None
                            else "N/A",
                        )
                    with s7:
                        st.metric(
                            "Launch Angle",
                            f"{statcast['launch_angle']:.1f}°"
                            if statcast.get("launch_angle") is not None
                            else "N/A",
                        )
                else:
                    st.warning(
                        "Statcast data is unavailable right now. "
                        "The model will fall back automatically."
                    )

                st.divider()
                st.subheader("⚔️ Today's Matchup")

                if matchup:
                    m1, m2, m3, m4 = st.columns(4)
                    with m1:
                        st.metric("Opponent", matchup["opponent"])
                    with m2:
                        st.metric("Home/Away", matchup["location"])
                    with m3:
                        st.metric("First Pitch", matchup["first_pitch"])
                    with m4:
                        st.metric("Status", matchup["status"])

                    st.write(
                        f"**Probable opposing starter:** {matchup['pitcher']}"
                    )

                    if pitcher:
                        p1, p2, p3, p4 = st.columns(4)
                        with p1:
                            st.metric("Pitcher", pitcher["name"])
                        with p2:
                            st.metric("Throws", pitcher["hand"])
                        with p3:
                            st.metric("ERA", pitcher["era"])
                        with p4:
                            st.metric("WHIP", pitcher["whip"])

                        p5, p6, p7, p8 = st.columns(4)
                        with p5:
                            st.metric(
                                "W-L",
                                f"{pitcher['wins']}-{pitcher['losses']}",
                            )
                        with p6:
                            st.metric("Starts", pitcher["games_started"])
                        with p7:
                            st.metric("IP", pitcher["innings"])
                        with p8:
                            st.metric(
                                "K/9",
                                f"{pitcher['k9']:.2f}"
                                if pitcher.get("k9") is not None
                                else "N/A",
                            )

                    starter_hand = (
                        pitcher.get("hand")
                        if pitcher
                        else None
                    )
                    starter_split = (
                        split_r
                        if starter_hand == "R"
                        else split_l
                        if starter_hand == "L"
                        else None
                    )
                    if starter_split:
                        st.subheader("↔️ Batter vs Starter Hand")
                        h1, h2, h3, h4 = st.columns(4)
                        with h1:
                            st.metric("Split AVG", starter_split["avg"])
                        with h2:
                            st.metric("Split Hits", starter_split["hits"])
                        with h3:
                            st.metric("Split AB", starter_split["at_bats"])
                        with h4:
                            st.metric("Split OPS", starter_split["ops"])

                    st.subheader("🧯 Opponent Bullpen")
                    if bullpen:
                        b1, b2, b3, b4 = st.columns(4)
                        with b1:
                            st.metric("Bullpen ERA", f"{bullpen['era']:.2f}")
                        with b2:
                            st.metric("Bullpen WHIP", f"{bullpen['whip']:.2f}")
                        with b3:
                            st.metric("Bullpen K/9", f"{bullpen['k9']:.2f}")
                        with b4:
                            st.metric(
                                "Relievers",
                                bullpen["reliever_count"],
                            )

                        b5, b6, b7 = st.columns(3)
                        with b5:
                            st.metric(
                                "RHP Exposure",
                                f"{bullpen['right_share'] * 100:.0f}%",
                            )
                        with b6:
                            st.metric(
                                "LHP Exposure",
                                f"{bullpen['left_share'] * 100:.0f}%",
                            )
                        with b7:
                            st.metric(
                                "Bullpen IP Sample",
                                f"{bullpen['innings']:.1f}",
                            )

                        st.caption(
                            "V10 bullpen profile aggregates active-roster relievers "
                            "and excludes the listed starter. It does not yet model "
                            "which individual relievers are rested or unavailable."
                        )
                    else:
                        st.info(
                            "Bullpen profile unavailable — V10 will fall back to "
                            "the starter-only V9 rate for the full projected at-bats."
                        )

                    st.subheader("🏟️ Park + Weather")
                    env_view = calculate_environment_adjustment(
                        environment,
                        matchup.get("venue_name", "Unknown"),
                    )
                    e1, e2, e3, e4 = st.columns(4)
                    with e1:
                        st.metric("Ballpark", env_view["venue_name"])
                    with e2:
                        st.metric(
                            "Temperature",
                            f"{env_view['temperature']:.0f}°F"
                            if env_view["temperature"] is not None
                            else "N/A",
                        )
                    with e3:
                        st.metric("Condition", env_view["condition"])
                    with e4:
                        st.metric("Wind", env_view["wind"])

                    e5, e6, e7 = st.columns(3)
                    with e5:
                        st.metric("Roof Type", env_view["roof_type"])
                    with e6:
                        st.metric("Environment Grade", env_view["grade"])
                    with e7:
                        st.metric(
                            "Prototype Park Adj",
                            f"{env_view['park_adjustment'] * 100:+.1f}%",
                        )
                else:
                    st.warning("No game found today for this player's team.")

                st.divider()
                st.subheader("📋 Lineup Position")
                confirmed = data.get("confirmed_lineup")
                estimated = data.get("recent_lineup")
                projected_position = (
                    int(confirmed)
                    if confirmed
                    else int(estimated["position"])
                    if estimated
                    else None
                )
                lineup_source = (
                    "Confirmed today's lineup"
                    if confirmed
                    else f"Recent lineup estimate ({estimated['sample_games']} games)"
                    if estimated
                    else "Manual fallback"
                )

                if projected_position:
                    l1, l2, l3 = st.columns(3)
                    with l1:
                        st.metric(
                            "Projected Batting Spot",
                            f"#{projected_position}",
                        )
                    with l2:
                        st.metric("Lineup Source", lineup_source)
                    with l3:
                        st.metric(
                            "Baseline Expected AB",
                            f"{lineup_expected_ab(projected_position):.1f}",
                        )

                default_position = projected_position or 4
                manual_position = st.selectbox(
                    "Batting Order Used by Model",
                    list(range(1, 10)),
                    index=default_position - 1,
                )

                expected_ab = st.number_input(
                    "Projected At-Bats Today",
                    min_value=2.5,
                    max_value=6.0,
                    value=float(lineup_expected_ab(manual_position)),
                    step=0.1,
                )

                sportsbook_line = st.number_input(
                    "Sportsbook Hit Line",
                    value=0.5,
                    step=0.5,
                )

                if st.button("🔥 RUN HIT PROJECTION", use_container_width=True):
                    season_avg = safe_float(stats["avg"], 0.0) or 0.0

                    starter_hand = (
                        pitcher.get("hand")
                        if pitcher
                        else None
                    )
                    starter_split = (
                        split_r
                        if starter_hand == "R"
                        else split_l
                        if starter_hand == "L"
                        else None
                    )

                    hand_avg, split_weight = build_handedness_avg(
                        season_avg,
                        starter_split,
                    )
                    pitcher_quality = calculate_pitcher_quality(pitcher)
                    pitcher_adj = (
                        pitcher_quality["rate_adjustment"]
                        if pitcher_quality
                        else 0.0
                    )
                    pitcher_avg = clamp(
                        hand_avg * (1 + pitcher_adj),
                        0.050,
                        0.500,
                    )

                    recent_avg_model, recent_weight, recent_avg = apply_recent_form(
                        pitcher_avg,
                        recent,
                    )
                    env_model = calculate_environment_adjustment(
                        environment,
                        (matchup or {}).get("venue_name", "Unknown"),
                    )
                    v8_avg = clamp(
                        recent_avg_model * (1 + env_model["total_adjustment"]),
                        0.050,
                        0.500,
                    )
                    starter_rate, sc_model = apply_statcast_quality(
                        v8_avg,
                        statcast,
                    )

                    bullpen_model = build_bullpen_rate(
                        season_avg,
                        split_r,
                        split_l,
                        bullpen,
                        recent,
                        environment,
                        statcast,
                        (matchup or {}).get("venue_name", "Unknown"),
                    )

                    exposure = estimate_starter_exposure(
                        pitcher,
                        expected_ab,
                    )

                    v9_projection = probability_from_avg(
                        starter_rate,
                        expected_ab,
                    )

                    if bullpen_model:
                        bullpen_rate = bullpen_model["rate"]
                        final_projection = combined_exposure_projection(
                            starter_rate,
                            bullpen_rate,
                            exposure["starter_ab"],
                            exposure["bullpen_ab"],
                        )
                    else:
                        bullpen_rate = starter_rate
                        final_projection = v9_projection

                    season_only = probability_from_avg(
                        season_avg,
                        expected_ab,
                    )

                    st.header("🧠 V10 Model Stack")
                    a1, a2, a3, a4 = st.columns(4)
                    with a1:
                        st.metric("Season AVG", f"{season_avg:.3f}")
                    with a2:
                        st.metric("Handedness AVG", f"{hand_avg:.3f}")
                    with a3:
                        st.metric("Post-Pitcher AVG", f"{pitcher_avg:.3f}")
                    with a4:
                        st.metric(
                            "Post-Recent AVG",
                            f"{recent_avg_model:.3f}",
                        )

                    st.subheader("🌦️ Environment + Statcast")
                    v1, v2, v3, v4 = st.columns(4)
                    with v1:
                        st.metric(
                            "Environment Adj",
                            f"{env_model['total_adjustment'] * 100:+.1f}%",
                        )
                    with v2:
                        st.metric("V8 Core AVG", f"{v8_avg:.3f}")
                    with v3:
                        st.metric(
                            "Contact Adj",
                            f"{sc_model['quality_adjustment'] * 100:+.1f}%",
                        )
                    with v4:
                        st.metric(
                            "Starter-Facing Rate",
                            f"{starter_rate:.3f}",
                        )

                    st.subheader("🧯 Bullpen Exposure Adjustment")
                    if bullpen_model:
                        bp_quality = bullpen_model["quality"]

                        bp1, bp2, bp3, bp4 = st.columns(4)
                        with bp1:
                            st.metric(
                                "Bullpen Difficulty",
                                bp_quality["difficulty"]
                                if bp_quality
                                else "N/A",
                            )
                        with bp2:
                            st.metric(
                                "Bullpen Hit-Rate Adj",
                                f"{bullpen_model['quality_adjustment'] * 100:+.1f}%",
                            )
                        with bp3:
                            st.metric(
                                "Bullpen-Facing Rate",
                                f"{bullpen_rate:.3f}",
                            )
                        with bp4:
                            st.metric(
                                "Bullpen R/L Mix",
                                f"{bullpen['right_share'] * 100:.0f}% R / "
                                f"{bullpen['left_share'] * 100:.0f}% L",
                            )

                        ex1, ex2, ex3, ex4 = st.columns(4)
                        with ex1:
                            st.metric(
                                "Expected Starter IP",
                                f"{exposure['starter_ip']:.1f}",
                            )
                        with ex2:
                            st.metric(
                                "Starter-Facing AB",
                                f"{exposure['starter_ab']:.2f}",
                            )
                        with ex3:
                            st.metric(
                                "Bullpen-Facing AB",
                                f"{exposure['bullpen_ab']:.2f}",
                            )
                        with ex4:
                            st.metric(
                                "Starter Exposure",
                                f"{exposure['starter_share'] * 100:.0f}%",
                            )
                    else:
                        st.info(
                            "Bullpen data unavailable — V10 used the V9 rate "
                            "across all projected at-bats."
                        )

                    st.header("📊 Projection Results")
                    o1, o2, o3 = st.columns(3)
                    with o1:
                        st.metric(
                            "Expected Hits",
                            f"{final_projection['expected_hits']:.2f}",
                        )
                    with o2:
                        delta_v9 = (
                            final_projection["p_one_plus"]
                            - v9_projection["p_one_plus"]
                        ) * 100
                        st.metric(
                            "1+ Hit Probability",
                            f"{final_projection['p_one_plus'] * 100:.1f}%",
                            delta=f"{delta_v9:+.1f} pts vs V9",
                        )
                    with o3:
                        st.metric(
                            "0 Hit Probability",
                            f"{final_projection['p_zero'] * 100:.1f}%",
                        )

                    o4, o5, o6 = st.columns(3)
                    with o4:
                        st.metric(
                            "Exactly 1 Hit",
                            f"{final_projection['p_exact_one'] * 100:.1f}%",
                        )
                    with o5:
                        st.metric(
                            "2+ Hit Probability",
                            f"{final_projection['p_two_plus'] * 100:.1f}%",
                        )
                    with o6:
                        season_delta = (
                            final_projection["p_one_plus"]
                            - season_only["p_one_plus"]
                        ) * 100
                        st.metric(
                            "Season-Only 1+",
                            f"{season_only['p_one_plus'] * 100:.1f}%",
                            delta=f"{season_delta:+.1f} pts final vs season",
                        )

                    st.success(
                        "V10 adds opponent bullpen quality, bullpen R/L mix, "
                        "estimated starter innings, and starter-vs-bullpen exposure "
                        "to the V9 season + splits + pitcher + recent form + lineup "
                        "+ park/weather + Statcast stack."
                    )
                    st.caption(
                        "V10 remains a prototype heuristic, not a calibrated betting "
                        "model. Bullpen numbers are season aggregates for active-roster "
                        "relievers; individual reliever rest, injuries, warm-up status, "
                        "and exact in-game usage are not yet modeled."
                    )

                    for warning in data.get("warnings", []):
                        st.warning(warning)

    else:
        st.info(f"The MLB {market} engine will be added later.")

else:
    market = st.selectbox(
        "Choose Market",
        ["Points", "Rebounds", "Assists", "PRA", "Spread", "Game Total"],
    )
    st.info(f"The WNBA {market} model will be added later.")

st.divider()
st.caption("Kyre Sports AI • Projection Engine V10")
