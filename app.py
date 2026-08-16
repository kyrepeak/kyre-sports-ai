import re
from collections import Counter
from datetime import datetime
from io import StringIO
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Kyre Sports AI", page_icon="🧠", layout="wide")

ET = ZoneInfo("America/New_York")
MLB_API = "https://statsapi.mlb.com/api/v1"
MLB_LIVE_API = "https://statsapi.mlb.com/api/v1.1"
SAVANT = "https://baseballsavant.mlb.com"
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 KyreSportsAI/1.0"}


# ---------- helpers ----------

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
    p0 = (1 - avg) ** expected_ab
    p1plus = 1 - p0
    p1 = clamp(expected_ab * avg * ((1 - avg) ** max(expected_ab - 1, 0)), 0, 1)
    return {
        "p_zero": p0,
        "p_one_plus": p1plus,
        "p_exact_one": min(p1, p1plus),
        "p_two_plus": max(0.0, p1plus - min(p1, p1plus)),
        "expected_hits": avg * expected_ab,
    }


def combined_exposure_projection(starter_rate, bullpen_rate, starter_ab, bullpen_ab):
    starter_ab = max(float(starter_ab), 0.0)
    bullpen_ab = max(float(bullpen_ab), 0.0)
    total_ab = starter_ab + bullpen_ab
    p0 = ((1 - clamp(starter_rate, 0, .999)) ** starter_ab) * (
        (1 - clamp(bullpen_rate, 0, .999)) ** bullpen_ab
    )
    expected_hits = starter_rate * starter_ab + bullpen_rate * bullpen_ab
    effective_avg = expected_hits / total_ab if total_ab > 0 else 0.0
    smooth = probability_from_avg(effective_avg, total_ab)
    return {
        "p_zero": p0,
        "p_one_plus": 1 - p0,
        "p_exact_one": smooth["p_exact_one"],
        "p_two_plus": smooth["p_two_plus"],
        "expected_hits": expected_hits,
        "effective_avg": effective_avg,
    }


def lineup_expected_ab(position):
    return {1: 4.60, 2: 4.50, 3: 4.40, 4: 4.30, 5: 4.20,
            6: 4.10, 7: 4.00, 8: 3.90, 9: 3.80}.get(position, 4.10)


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
    return default if pd.isna(value) else value


def metric_grid(items, columns=4):
    for start in range(0, len(items), columns):
        cols = st.columns(min(columns, len(items) - start))
        for col, item in zip(cols, items[start:start + columns]):
            label, value = item[:2]
            delta = item[2] if len(item) > 2 else None
            with col:
                st.metric(label, value, delta=delta)


def american_odds(prob):
    p = clamp(float(prob), 1e-6, 1 - 1e-6)
    if p >= .5:
        return f"{-100 * p / (1 - p):.0f}"
    return f"+{100 * (1 - p) / p:.0f}"


# ---------- MLB data ----------

@st.cache_data(ttl=300)
def get_today_mlb_games():
    today = datetime.now(ET).strftime("%Y-%m-%d")
    r = requests.get(
        f"{MLB_API}/schedule",
        params={"sportId": 1, "date": today, "hydrate": "probablePitcher,team"},
        timeout=15,
    )
    r.raise_for_status()
    games = []
    for block in r.json().get("dates", []):
        for game in block.get("games", []):
            away, home = game["teams"]["away"], game["teams"]["home"]
            ap, hp = away.get("probablePitcher", {}), home.get("probablePitcher", {})
            gt = datetime.fromisoformat(game["gameDate"].replace("Z", "+00:00")).astimezone(ET)
            venue = game.get("venue", {}) or {}
            games.append({
                "game_pk": game.get("gamePk"),
                "venue_name": venue.get("name", "Unknown"),
                "away_team_id": away["team"].get("id"),
                "away_team": away["team"].get("name", "Unknown"),
                "home_team_id": home["team"].get("id"),
                "home_team": home["team"].get("name", "Unknown"),
                "away_pitcher_id": ap.get("id"),
                "away_pitcher": ap.get("fullName", "TBD"),
                "home_pitcher_id": hp.get("id"),
                "home_pitcher": hp.get("fullName", "TBD"),
                "first_pitch_et": gt.strftime("%I:%M %p").lstrip("0"),
                "status": game.get("status", {}).get("detailedState", "Unknown"),
            })
    return pd.DataFrame(games), today


@st.cache_data(ttl=3600)
def find_mlb_player(player_name):
    r = requests.get(f"{MLB_API}/people/search", params={"names": player_name}, timeout=15)
    r.raise_for_status()
    people = r.json().get("people", [])
    if not people:
        return None
    player_id = people[0].get("id")
    r = requests.get(
        f"{MLB_API}/people/{player_id}", params={"hydrate": "currentTeam"}, timeout=15
    )
    r.raise_for_status()
    people = r.json().get("people", [])
    if not people:
        return None
    p = people[0]
    team = p.get("currentTeam", {}) or {}
    return {
        "id": p.get("id"),
        "name": p.get("fullName", player_name),
        "team_id": team.get("id"),
        "team_name": team.get("name", "Unknown"),
        "bat_side": p.get("batSide", {}).get("code", "?"),
    }


@st.cache_data(ttl=600)
def get_player_hitting_stats(player_id):
    r = requests.get(
        f"{MLB_API}/people/{player_id}/stats",
        params={"stats": "season", "group": "hitting", "season": current_season()},
        timeout=15,
    )
    r.raise_for_status()
    groups = r.json().get("stats", [])
    if not groups or not groups[0].get("splits"):
        return None
    s = groups[0]["splits"][0].get("stat", {})
    return {
        "season": current_season(),
        "games": s.get("gamesPlayed", 0),
        "plate_appearances": s.get("plateAppearances", 0),
        "at_bats": s.get("atBats", 0),
        "hits": s.get("hits", 0),
        "home_runs": s.get("homeRuns", 0),
        "walks": s.get("baseOnBalls", 0),
        "strikeouts": s.get("strikeOuts", 0),
        "avg": s.get("avg", ".000"),
        "obp": s.get("obp", ".000"),
        "slg": s.get("slg", ".000"),
        "ops": s.get("ops", ".000"),
    }


@st.cache_data(ttl=600)
def get_pitcher_stats(pitcher_id):
    pr = requests.get(f"{MLB_API}/people/{pitcher_id}", timeout=15)
    pr.raise_for_status()
    people = pr.json().get("people", [])
    if not people:
        return None
    person = people[0]

    sr = requests.get(
        f"{MLB_API}/people/{pitcher_id}/stats",
        params={"stats": "season", "group": "pitching", "season": current_season()},
        timeout=15,
    )
    sr.raise_for_status()
    groups = sr.json().get("stats", [])
    s = groups[0]["splits"][0].get("stat", {}) if groups and groups[0].get("splits") else {}

    innings_text = s.get("inningsPitched", "0.0")
    ip = innings_to_float(innings_text)
    k = safe_float(s.get("strikeOuts"), 0.0) or 0.0
    games = int(safe_float(s.get("gamesPlayed"), 0) or 0)
    starts = int(safe_float(s.get("gamesStarted"), 0) or 0)
    return {
        "id": int(pitcher_id),
        "name": person.get("fullName", "Unknown"),
        "hand": person.get("pitchHand", {}).get("code", "?"),
        "era": s.get("era", "N/A"),
        "whip": s.get("whip", "N/A"),
        "wins": s.get("wins", 0),
        "losses": s.get("losses", 0),
        "games": games,
        "games_started": starts,
        "innings": innings_text,
        "true_innings": ip,
        "hits_allowed": safe_float(s.get("hits"), 0.0) or 0.0,
        "walks": safe_float(s.get("baseOnBalls"), 0.0) or 0.0,
        "earned_runs": safe_float(s.get("earnedRuns"), 0.0) or 0.0,
        "strikeouts": k,
        "k9": k * 9 / ip if ip > 0 else None,
    }


@st.cache_data(ttl=600)
def get_hitter_vs_hand_stats(player_id, pitcher_hand):
    hand = str(pitcher_hand or "").upper()
    if hand not in {"R", "L"}:
        return None
    sit = "vr" if hand == "R" else "vl"
    label = "vs RHP" if hand == "R" else "vs LHP"
    for stat_type in ["statSplits", "season"]:
        r = requests.get(
            f"{MLB_API}/people/{player_id}/stats",
            params={"stats": stat_type, "group": "hitting", "season": current_season(), "sitCodes": sit},
            timeout=15,
        )
        if r.status_code >= 400:
            continue
        for group in r.json().get("stats", []):
            for split in group.get("splits", []):
                info = split.get("split", {}) or {}
                desc = str(info.get("description", "")).lower()
                explicit = str(info.get("code", "")).lower() == sit or (
                    hand == "R" and "right" in desc
                ) or (hand == "L" and "left" in desc)
                if stat_type == "statSplits" or explicit:
                    s = split.get("stat", {})
                    if s:
                        return {
                            "label": label,
                            "at_bats": s.get("atBats", 0),
                            "hits": s.get("hits", 0),
                            "home_runs": s.get("homeRuns", 0),
                            "strikeouts": s.get("strikeOuts", 0),
                            "avg": s.get("avg", ".000"),
                            "obp": s.get("obp", ".000"),
                            "slg": s.get("slg", ".000"),
                            "ops": s.get("ops", ".000"),
                        }
    return None


@st.cache_data(ttl=600)
def get_recent_form(player_id, games=10):
    r = requests.get(
        f"{MLB_API}/people/{player_id}/stats",
        params={"stats": "gameLog", "group": "hitting", "season": current_season()},
        timeout=15,
    )
    r.raise_for_status()
    groups = r.json().get("stats", [])
    if not groups or not groups[0].get("splits"):
        return None
    splits = groups[0]["splits"][-games:]
    total_ab = total_hits = total_hr = total_bb = total_so = 0
    hit_games, game_pks = 0, []
    for split in splits:
        s = split.get("stat", {}) or {}
        ab = int(safe_float(s.get("atBats"), 0) or 0)
        hits = int(safe_float(s.get("hits"), 0) or 0)
        total_ab += ab
        total_hits += hits
        total_hr += int(safe_float(s.get("homeRuns"), 0) or 0)
        total_bb += int(safe_float(s.get("baseOnBalls"), 0) or 0)
        total_so += int(safe_float(s.get("strikeOuts"), 0) or 0)
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
        "avg": total_hits / total_ab if total_ab else None,
        "hit_games": hit_games,
        "game_pks": game_pks,
    }


@st.cache_data(ttl=180)
def get_lineup_position(game_pk, player_id, team_side):
    if not game_pk or team_side not in {"home", "away"}:
        return None
    r = requests.get(f"{MLB_API}/game/{game_pk}/boxscore", timeout=15)
    if r.status_code >= 400:
        return None
    team = r.json().get("teams", {}).get(team_side, {}) or {}
    order = [int(x) for x in team.get("battingOrder", []) if str(x).isdigit()]
    if int(player_id) in order:
        return order.index(int(player_id)) + 1
    p = (team.get("players", {}) or {}).get(f"ID{player_id}", {}) or {}
    value = str(p.get("battingOrder", ""))
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
    count = counts.most_common(1)[0][1]
    tied = [p for p, c in counts.items() if c == count]
    projected = tied[0] if len(tied) == 1 else int(round(sum(positions) / len(positions)))
    return {"position": int(clamp(projected, 1, 9)), "sample_games": len(positions)}


@st.cache_data(ttl=180)
def get_game_environment(game_pk):
    if not game_pk:
        return None
    r = requests.get(f"{MLB_LIVE_API}/game/{game_pk}/feed/live", timeout=15)
    if r.status_code >= 400:
        return None
    gd = r.json().get("gameData", {}) or {}
    venue, weather = gd.get("venue", {}) or {}, gd.get("weather", {}) or {}
    field = venue.get("fieldInfo", {}) or {}
    return {
        "venue_name": venue.get("name", "Unknown"),
        "roof_type": field.get("roofType", "Unknown"),
        "temperature": safe_float(weather.get("temp")),
        "condition": weather.get("condition", "Unknown"),
        "wind": weather.get("wind", "Unknown"),
    }


@st.cache_data(ttl=1800)
def get_statcast_profile(player_id):
    year = current_season()
    urls = [
        f"{SAVANT}/leaderboard/expected_statistics?type=batter&year={year}&position=&team=&filterType=pa&min=1&csv=true",
        f"{SAVANT}/leaderboard/statcast?type=batter&year={year}&position=&team=&min=1&csv=true",
    ]
    responses = [requests.get(u, headers=HTTP_HEADERS, timeout=20) for u in urls]
    for r in responses:
        r.raise_for_status()
    expected_df = pd.read_csv(StringIO(responses[0].text))
    contact_df = pd.read_csv(StringIO(responses[1].text))
    exp_id = first_existing_column(expected_df, ["player_id", "id"])
    con_id = first_existing_column(contact_df, ["player_id", "id"])
    if exp_id is None or con_id is None:
        return None
    exp_rows = expected_df[pd.to_numeric(expected_df[exp_id], errors="coerce") == int(player_id)]
    con_rows = contact_df[pd.to_numeric(contact_df[con_id], errors="coerce") == int(player_id)]
    if exp_rows.empty and con_rows.empty:
        return None
    er = exp_rows.iloc[0] if not exp_rows.empty else pd.Series(dtype=object)
    cr = con_rows.iloc[0] if not con_rows.empty else pd.Series(dtype=object)
    return {
        "source": "Baseball Savant / Statcast",
        "year": year,
        "xba": safe_float(value_from_row(er, expected_df, ["est_ba", "xba"])) if not exp_rows.empty else None,
        "xslg": safe_float(value_from_row(er, expected_df, ["est_slg", "xslg"])) if not exp_rows.empty else None,
        "xwoba": safe_float(value_from_row(er, expected_df, ["est_woba", "xwoba"])) if not exp_rows.empty else None,
        "pa": safe_float(value_from_row(er, expected_df, ["pa", "plate_appearances"], 0), 0.0) if not exp_rows.empty else 0.0,
        "bip": safe_float(value_from_row(er, expected_df, ["bip", "batted_ball"], 0), 0.0) if not exp_rows.empty else 0.0,
        "bbe": safe_float(value_from_row(cr, contact_df, ["batted_ball", "bbe"], 0), 0.0) if not con_rows.empty else 0.0,
        "avg_ev": safe_float(value_from_row(cr, contact_df, ["exit_velocity_avg", "avg_exit_velocity"])) if not con_rows.empty else None,
        "launch_angle": safe_float(value_from_row(cr, contact_df, ["launch_angle_avg", "avg_launch_angle"])) if not con_rows.empty else None,
        "hard_hit_rate": percent_to_rate(value_from_row(cr, contact_df, ["hard_hit_percent", "hard_hit_pct"])) if not con_rows.empty else None,
        "barrel_rate": percent_to_rate(value_from_row(cr, contact_df, ["barrel_batted_rate", "barrel_percent", "brl_percent"])) if not con_rows.empty else None,
    }


@st.cache_data(ttl=900)
def get_team_bullpen_profile(team_id, opposing_starter_id=None):
    if not team_id:
        return None
    r = requests.get(
        f"{MLB_API}/teams/{int(team_id)}/roster", params={"rosterType": "active"}, timeout=15
    )
    r.raise_for_status()
    pitcher_ids = [
        int(e["person"]["id"]) for e in r.json().get("roster", [])
        if e.get("position", {}).get("abbreviation") == "P" and e.get("person", {}).get("id")
    ]
    relievers = []
    for pid in pitcher_ids[:16]:
        if opposing_starter_id and pid == int(opposing_starter_id):
            continue
        try:
            p = get_pitcher_stats(pid)
        except requests.RequestException:
            continue
        if not p or p.get("true_innings", 0) <= 0:
            continue
        games, starts = p.get("games", 0), p.get("games_started", 0)
        if starts <= 3 or starts / max(games, 1) <= .35:
            relievers.append(p)
    if not relievers:
        return None
    ip = sum(p["true_innings"] for p in relievers)
    if ip <= 0:
        return None
    er = sum(p["earned_runs"] for p in relievers)
    hits = sum(p["hits_allowed"] for p in relievers)
    walks = sum(p["walks"] for p in relievers)
    k = sum(p["strikeouts"] for p in relievers)
    r_ip = sum(p["true_innings"] for p in relievers if str(p.get("hand")).upper() == "R")
    l_ip = sum(p["true_innings"] for p in relievers if str(p.get("hand")).upper() == "L")
    hand_ip = r_ip + l_ip
    r_share = r_ip / hand_ip if hand_ip else .60
    return {
        "reliever_count": len(relievers),
        "innings": ip,
        "era": er * 9 / ip,
        "whip": (hits + walks) / ip,
        "k9": k * 9 / ip,
        "right_share": clamp(r_share, 0, 1),
        "left_share": clamp(1 - r_share, 0, 1),
        "source": "Active-roster relief aggregate",
    }


def find_player_matchup(games_df, team_id):
    if games_df.empty or team_id is None:
        return None
    for _, g in games_df.iterrows():
        if g["away_team_id"] == team_id:
            return {
                "game_pk": g["game_pk"], "team_side": "away",
                "venue_name": g.get("venue_name", "Unknown"),
                "opponent_team_id": g["home_team_id"], "opponent": g["home_team"],
                "location": "Away", "pitcher_id": g["home_pitcher_id"],
                "pitcher": g["home_pitcher"], "first_pitch": g["first_pitch_et"],
                "status": g["status"],
            }
        if g["home_team_id"] == team_id:
            return {
                "game_pk": g["game_pk"], "team_side": "home",
                "venue_name": g.get("venue_name", "Unknown"),
                "opponent_team_id": g["away_team_id"], "opponent": g["away_team"],
                "location": "Home", "pitcher_id": g["away_pitcher_id"],
                "pitcher": g["away_pitcher"], "first_pitch": g["first_pitch_et"],
                "status": g["status"],
            }
    return None


# ---------- model layers ----------

def build_handedness_avg(season_avg, split):
    if not split:
        return season_avg, 0.0
    split_avg = safe_float(split.get("avg"))
    split_ab = safe_float(split.get("at_bats"), 0.0) or 0.0
    if split_avg is None or split_ab <= 0:
        return season_avg, 0.0
    w = split_ab / (split_ab + 200.0)
    return season_avg * (1 - w) + split_avg * w, w


def calculate_pitcher_quality(pitcher, bullpen=False):
    if not pitcher:
        return None
    era, whip, k9 = safe_float(pitcher.get("era")), safe_float(pitcher.get("whip")), safe_float(pitcher.get("k9"))
    innings = safe_float(pitcher.get("innings" if bullpen else "true_innings"), 0.0) or 0.0
    if era is None or whip is None:
        return None
    raw = .40 * ((4.20 - era) / 4.20) + .40 * ((1.30 - whip) / 1.30) + .20 * (((k9 - 8.50) / 8.50) if k9 is not None else 0)
    reliability = innings / (innings + (120.0 if bullpen else 60.0)) if innings > 0 else 0
    q = raw * reliability
    adj = clamp((-0.18 if bullpen else -0.25) * q, -.05 if bullpen else -.08, .05 if bullpen else .08)
    grade = "Very Tough" if q >= .10 else "Tough" if q >= .04 else "Very Favorable" if q <= -.10 else "Favorable" if q <= -.04 else "Near Neutral"
    return {"reliability": reliability, "rate_adjustment": adj, "difficulty": grade}


def apply_recent_form(base_avg, recent):
    if not recent or recent.get("avg") is None:
        return base_avg, 0.0, None
    recent_avg, recent_ab = recent["avg"], recent.get("at_bats", 0) or 0
    if recent_ab <= 0:
        return base_avg, 0.0, recent_avg
    w = clamp(.22 * (recent_ab / (recent_ab + 45.0)), 0, .22)
    return base_avg * (1 - w) + recent_avg * w, w, recent_avg


PARK_HIT_ADJUSTMENTS = {
    "coors field": .035, "fenway park": .018, "kauffman stadium": .012,
    "chase field": .010, "great american ball park": .010, "citizens bank park": .008,
    "wrigley field": .006, "yankee stadium": .005, "daikin park": .004,
    "minute maid park": .004, "globe life field": .003, "camden yards": .002,
    "rogers centre": .002, "truist park": .002, "target field": .001,
    "busch stadium": 0, "progressive field": 0, "comerica park": 0,
    "loandepot park": -.003, "dodger stadium": -.004, "american family field": -.004,
    "citi field": -.006, "angel stadium": -.006, "nationals park": -.006,
    "rate field": -.007, "sutter health park": -.007, "petco park": -.010,
    "t-mobile park": -.016, "oracle park": -.018,
}


def parse_wind_speed(text):
    m = re.search(r"(\d+(?:\.\d+)?)\s*mph", str(text or ""), flags=re.I)
    return safe_float(m.group(1)) if m else None


def calculate_environment_adjustment(environment, fallback_venue="Unknown"):
    env = environment or {}
    venue = env.get("venue_name") or fallback_venue or "Unknown"
    park = PARK_HIT_ADJUSTMENTS.get(venue.lower().strip(), 0)
    temp = env.get("temperature")
    condition, wind, roof = (str(env.get("condition") or "Unknown"),
                             str(env.get("wind") or "Unknown"),
                             str(env.get("roof_type") or "Unknown"))
    indoor = any(x in condition.lower() for x in ["dome", "indoor", "roof closed", "closed roof"])
    temp_adj = clamp(((temp - 72) / 10) * .004, -.015, .015) if temp is not None and not indoor else 0
    wind_adj = 0
    speed = parse_wind_speed(wind)
    if speed is not None and not indoor:
        scale = clamp(speed / 15, 0, 1.5)
        lower = wind.lower()
        if "out to" in lower or "blowing out" in lower:
            wind_adj = clamp(.012 * scale, 0, .018)
        elif "in from" in lower or "blowing in" in lower:
            wind_adj = clamp(-.012 * scale, -.018, 0)
    total = clamp(park + temp_adj + wind_adj, -.05, .05)
    grade = "Strong Hitter Boost" if total >= .025 else "Hitter Friendly" if total >= .008 else "Strong Pitcher Boost" if total <= -.025 else "Pitcher Friendly" if total <= -.008 else "Near Neutral"
    return {"venue_name": venue, "temperature": temp, "condition": condition, "wind": wind,
            "roof_type": roof, "park_adjustment": park, "temperature_adjustment": temp_adj,
            "wind_adjustment": wind_adj, "total_adjustment": total, "grade": grade}


def apply_statcast_quality(base_avg, statcast):
    if not statcast:
        return base_avg, {"available": False, "reliability": 0, "xba_weight": 0,
                          "quality_adjustment": 0, "pre_quality_avg": base_avg,
                          "final_avg": base_avg, "grade": "Unavailable"}
    xba = statcast.get("xba")
    sample = max(safe_float(statcast.get("bbe"), 0) or 0, (safe_float(statcast.get("pa"), 0) or 0) * .65)
    rel = sample / (sample + 120) if sample > 0 else 0
    w = clamp(.22 * rel, 0, .22) if xba is not None and .05 <= xba <= .5 else 0
    blend = base_avg * (1 - w) + (xba if xba is not None else base_avg) * w
    comps = []
    if statcast.get("avg_ev") is not None:
        comps.append(.35 * clamp((statcast["avg_ev"] - 88.5) / 7, -1.5, 1.5))
    if statcast.get("hard_hit_rate") is not None:
        comps.append(.35 * clamp((statcast["hard_hit_rate"] - .40) / .20, -1.5, 1.5))
    if statcast.get("barrel_rate") is not None:
        comps.append(.30 * clamp((statcast["barrel_rate"] - .08) / .09, -1.5, 1.5))
    q = sum(comps) if comps else 0
    adj = clamp(.025 * q * rel, -.04, .04)
    final = clamp(blend * (1 + adj), .05, .5)
    grade = "Elite Contact" if adj >= .020 else "Strong Contact" if adj >= .007 else "Weak Contact" if adj <= -.020 else "Below-Average Contact" if adj <= -.007 else "Near Neutral"
    return final, {"available": True, "reliability": rel, "xba_weight": w,
                   "quality_adjustment": adj, "pre_quality_avg": blend,
                   "final_avg": final, "grade": grade}


def build_bullpen_rate(season_avg, split_r, split_l, bullpen, recent, environment, statcast, fallback_venue="Unknown"):
    if not bullpen:
        return None
    r_avg, _ = build_handedness_avg(season_avg, split_r)
    l_avg, _ = build_handedness_avg(season_avg, split_l)
    handed = r_avg * bullpen.get("right_share", .60) + l_avg * bullpen.get("left_share", .40)
    quality = calculate_pitcher_quality(bullpen, bullpen=True)
    adj = quality["rate_adjustment"] if quality else 0
    x = clamp(handed * (1 + adj), .05, .5)
    x, recent_weight, _ = apply_recent_form(x, recent)
    env = calculate_environment_adjustment(environment, fallback_venue)
    x = clamp(x * (1 + env["total_adjustment"]), .05, .5)
    rate, sc = apply_statcast_quality(x, statcast)
    return {"rate": rate, "handed_avg": handed, "quality": quality,
            "quality_adjustment": adj, "recent_weight": recent_weight,
            "environment": env, "statcast": sc}


def estimate_starter_exposure(pitcher, expected_ab):
    if not pitcher:
        ip = 5.0
    else:
        starts, innings = pitcher.get("games_started", 0) or 0, pitcher.get("true_innings", 0) or 0
        ip = innings / starts if starts > 0 else 5.0
    ip = clamp(ip, 4.0, 6.5)
    share = clamp(ip / 9, .44, .72)
    return {"starter_ip": ip, "starter_share": share,
            "starter_ab": expected_ab * share, "bullpen_ab": expected_ab * (1 - share)}


# ---------- V11 simulation ----------

def simulation_seed(player_id, game_pk):
    day = int(datetime.now(ET).strftime("%Y%m%d"))
    return int((int(player_id) * 1009 + int(game_pk or 0) * 17 + day) % (2**32 - 1))


def confidence_summary(stats, pitcher, starter_split, recent, confirmed, environment, statcast, bullpen, sim):
    flags = [bool(stats), bool(pitcher), bool(starter_split), bool(recent),
             bool(confirmed), bool(environment), bool(statcast), bool(bullpen)]
    data_score = sum(flags)
    width = sim["scenario_high"] - sim["scenario_low"]
    if data_score >= 7 and width <= .18 and sim["converged"]:
        grade = "HIGH"
    elif data_score >= 5 and width <= .25 and sim["converged"]:
        grade = "MEDIUM-HIGH"
    elif data_score >= 4:
        grade = "MEDIUM"
    else:
        grade = "LOW"
    return grade, data_score


@st.cache_data(ttl=600, show_spinner=False)
def run_monte_carlo(
    starter_rate, bullpen_rate, expected_ab, starter_share,
    split_weight, statcast_reliability, pitcher_reliability,
    bullpen_reliability, simulations, seed
):
    simulations = int(simulations)
    batch_size = 250_000
    rng = np.random.default_rng(int(seed))

    starter_conc = 130 + 220 * split_weight + 180 * statcast_reliability + 140 * pitcher_reliability
    bullpen_conc = 100 + 150 * statcast_reliability + 180 * bullpen_reliability
    starter_conc = max(starter_conc, 60)
    bullpen_conc = max(bullpen_conc, 50)

    s_alpha = max(starter_rate * starter_conc, .5)
    s_beta = max((1 - starter_rate) * starter_conc, .5)
    b_alpha = max(bullpen_rate * bullpen_conc, .5)
    b_beta = max((1 - bullpen_rate) * bullpen_conc, .5)

    hist = np.zeros(8, dtype=np.int64)
    batch_probs = []
    scenario_samples = []
    total_hits_sum = 0.0
    completed = 0
    batches = 0

    while completed < simulations:
        n = min(batch_size, simulations - completed)
        ab = np.rint(rng.normal(expected_ab, .55, n)).astype(np.int8)
        ab = np.clip(ab, 2, 7)

        share = np.clip(rng.normal(starter_share, .075, n), .25, .90)
        s_ab = rng.binomial(ab.astype(np.int16), share)
        b_ab = ab.astype(np.int16) - s_ab

        sr = rng.beta(s_alpha, s_beta, n)
        br = rng.beta(b_alpha, b_beta, n)

        s_hits = rng.binomial(s_ab, sr)
        b_hits = rng.binomial(b_ab, br)
        hits = s_hits + b_hits

        counts = np.bincount(np.minimum(hits, 7), minlength=8)
        hist += counts[:8]
        total_hits_sum += float(hits.sum())
        batch_probs.append(float(np.mean(hits >= 1)))

        scenario_p = 1 - np.power(1 - sr, s_ab) * np.power(1 - br, b_ab)
        take = min(10_000, n)
        if take:
            idx = rng.choice(n, size=take, replace=False)
            scenario_samples.append(scenario_p[idx].astype(np.float32))

        completed += n
        batches += 1

    p0 = hist[0] / completed
    p1 = 1 - p0
    p_exact1 = hist[1] / completed
    p2plus = hist[2:].sum() / completed
    p3plus = hist[3:].sum() / completed
    mean_hits = total_hits_sum / completed

    cdf = np.cumsum(hist) / completed
    median_hits = int(np.searchsorted(cdf, .50))
    mode_hits = int(np.argmax(hist))
    se = float(np.sqrt(p1 * (1 - p1) / completed))

    samples = np.concatenate(scenario_samples) if scenario_samples else np.array([p1])
    scenario_low, scenario_high = [float(x) for x in np.percentile(samples, [5, 95])]
    batch_range = (max(batch_probs) - min(batch_probs)) if batch_probs else 0.0
    converged = batch_range <= .005

    return {
        "simulations": completed,
        "batches": batches,
        "seed": int(seed),
        "p_zero": float(p0),
        "p_one_plus": float(p1),
        "p_exact_one": float(p_exact1),
        "p_two_plus": float(p2plus),
        "p_three_plus": float(p3plus),
        "expected_hits": float(mean_hits),
        "median_hits": median_hits,
        "mode_hits": mode_hits,
        "mc_se": se,
        "scenario_low": scenario_low,
        "scenario_high": scenario_high,
        "batch_range": float(batch_range),
        "converged": bool(converged),
        "starter_concentration": float(starter_conc),
        "bullpen_concentration": float(bullpen_conc),
    }


# ---------- UI ----------

st.title("🧠 KYRE SPORTS AI")
st.subheader("Sports Projection & Analytics Engine")
st.divider()

sport = st.selectbox("Choose Sport", ["MLB", "WNBA"])

if sport == "MLB":
    try:
        games_df, game_date = get_today_mlb_games()
    except requests.RequestException:
        games_df, game_date = pd.DataFrame(), datetime.now(ET).strftime("%Y-%m-%d")

    st.header("📡 Live MLB Data")
    if st.button("🔄 LOAD TODAY'S MLB GAMES", use_container_width=True):
        if games_df.empty:
            st.warning("No MLB games found.")
        else:
            st.success(f"Schedule loaded for {game_date}")
            display = games_df[["away_team", "home_team", "first_pitch_et", "away_pitcher", "home_pitcher", "status"]].rename(
                columns={"away_team": "Away", "home_team": "Home", "first_pitch_et": "First Pitch (ET)",
                         "away_pitcher": "Away Pitcher", "home_pitcher": "Home Pitcher", "status": "Status"}
            )
            st.dataframe(display, use_container_width=True, hide_index=True)

    st.divider()
    market = st.selectbox("Choose Market", ["1+ Hit", "2+ Hits", "Home Run", "Hits + Runs + RBIs", "Moneyline", "Run Line", "Game Total"])

    if market == "1+ Hit":
        st.header("⚾ MLB 1+ Hit Projection")
        player_name = st.text_input("Player Name", placeholder="Example: Yordan Alvarez")

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
                        pitcher = split_r = split_l = environment = statcast = bullpen = None
                        confirmed = recent_lineup = None
                        warnings = []

                        if matchup:
                            confirmed = get_lineup_position(matchup["game_pk"], player["id"], matchup["team_side"])
                            environment = get_game_environment(matchup["game_pk"])
                            if pd.notna(matchup.get("pitcher_id")):
                                pitcher = get_pitcher_stats(int(matchup["pitcher_id"]))

                        if recent:
                            recent_lineup = estimate_recent_lineup_position(player["id"], recent.get("game_pks", []), 5)

                        split_r = get_hitter_vs_hand_stats(player["id"], "R")
                        split_l = get_hitter_vs_hand_stats(player["id"], "L")

                        if matchup:
                            try:
                                bullpen = get_team_bullpen_profile(matchup.get("opponent_team_id"), matchup.get("pitcher_id"))
                            except Exception as exc:
                                warnings.append(f"Bullpen profile unavailable: {exc}")
                        try:
                            statcast = get_statcast_profile(player["id"])
                        except Exception as exc:
                            warnings.append(f"Statcast profile unavailable: {exc}")

                        st.session_state["player_data"] = {
                            "player": player, "stats": stats, "recent": recent, "matchup": matchup,
                            "pitcher": pitcher, "split_r": split_r, "split_l": split_l,
                            "confirmed_lineup": confirmed, "recent_lineup": recent_lineup,
                            "environment": environment, "statcast": statcast, "bullpen": bullpen,
                            "warnings": warnings,
                        }
                except requests.RequestException as exc:
                    st.error(f"Could not load MLB data: {exc}")

        if "player_data" in st.session_state:
            d = st.session_state["player_data"]
            player, stats, recent = d["player"], d["stats"], d.get("recent")
            matchup, pitcher, bullpen = d.get("matchup"), d.get("pitcher"), d.get("bullpen")
            split_r, split_l = d.get("split_r"), d.get("split_l")
            environment, statcast = d.get("environment"), d.get("statcast")

            if stats:
                st.success(f"Live data loaded for {player['name']}")
                st.subheader(f"📊 {player['name']} — {stats['season']}")
                st.caption(f"Team: {player['team_name']} • Bats: {player['bat_side']}")
                metric_grid([
                    ("AVG", stats["avg"]), ("Hits", stats["hits"]), ("At-Bats", stats["at_bats"]), ("Games", stats["games"]),
                    ("HR", stats["home_runs"]), ("OBP", stats["obp"]), ("SLG", stats["slg"]), ("OPS", stats["ops"])
                ])

                st.divider()
                st.subheader("🔥 Recent Form — Last 10 Games")
                if recent and recent.get("avg") is not None:
                    metric_grid([
                        ("Recent AVG", f"{recent['avg']:.3f}"), ("Hits", recent["hits"]),
                        ("Recent AB", recent["at_bats"]), ("Hit Games", f"{recent['hit_games']}/{recent['games']}")
                    ])
                else:
                    st.info("Recent game-log data was not available.")

                st.divider()
                st.subheader("📡 Statcast Contact Quality")
                if statcast:
                    metric_grid([
                        ("xBA", f"{statcast['xba']:.3f}" if statcast.get("xba") is not None else "N/A"),
                        ("Avg Exit Velo", f"{statcast['avg_ev']:.1f} mph" if statcast.get("avg_ev") is not None else "N/A"),
                        ("Hard-Hit %", f"{statcast['hard_hit_rate']*100:.1f}%" if statcast.get("hard_hit_rate") is not None else "N/A"),
                        ("Barrel %", f"{statcast['barrel_rate']*100:.1f}%" if statcast.get("barrel_rate") is not None else "N/A"),
                        ("xSLG", f"{statcast['xslg']:.3f}" if statcast.get("xslg") is not None else "N/A"),
                        ("xwOBA", f"{statcast['xwoba']:.3f}" if statcast.get("xwoba") is not None else "N/A"),
                        ("Launch Angle", f"{statcast['launch_angle']:.1f}°" if statcast.get("launch_angle") is not None else "N/A"),
                    ])
                else:
                    st.warning("Statcast data unavailable — model fallback is active.")

                st.divider()
                st.subheader("⚔️ Today's Matchup")
                starter_split = None
                if matchup:
                    metric_grid([
                        ("Opponent", matchup["opponent"]), ("Home/Away", matchup["location"]),
                        ("First Pitch", matchup["first_pitch"]), ("Status", matchup["status"])
                    ])
                    st.write(f"**Probable opposing starter:** {matchup['pitcher']}")
                    if pitcher:
                        metric_grid([
                            ("Pitcher", pitcher["name"]), ("Throws", pitcher["hand"]), ("ERA", pitcher["era"]), ("WHIP", pitcher["whip"]),
                            ("W-L", f"{pitcher['wins']}-{pitcher['losses']}"), ("Starts", pitcher["games_started"]),
                            ("IP", pitcher["innings"]), ("K/9", f"{pitcher['k9']:.2f}" if pitcher.get("k9") is not None else "N/A")
                        ])
                    starter_hand = pitcher.get("hand") if pitcher else None
                    starter_split = split_r if starter_hand == "R" else split_l if starter_hand == "L" else None
                    if starter_split:
                        st.subheader("↔️ Batter vs Starter Hand")
                        metric_grid([
                            ("Split AVG", starter_split["avg"]), ("Split Hits", starter_split["hits"]),
                            ("Split AB", starter_split["at_bats"]), ("Split OPS", starter_split["ops"])
                        ])

                    st.subheader("🧯 Opponent Bullpen")
                    if bullpen:
                        metric_grid([
                            ("Bullpen ERA", f"{bullpen['era']:.2f}"), ("Bullpen WHIP", f"{bullpen['whip']:.2f}"),
                            ("Bullpen K/9", f"{bullpen['k9']:.2f}"), ("Relievers", bullpen["reliever_count"]),
                            ("RHP Exposure", f"{bullpen['right_share']*100:.0f}%"), ("LHP Exposure", f"{bullpen['left_share']*100:.0f}%"),
                            ("Bullpen IP Sample", f"{bullpen['innings']:.1f}")
                        ])
                    else:
                        st.info("Bullpen profile unavailable — starter-only fallback will be used.")

                    st.subheader("🏟️ Park + Weather")
                    env_view = calculate_environment_adjustment(environment, matchup.get("venue_name", "Unknown"))
                    metric_grid([
                        ("Ballpark", env_view["venue_name"]),
                        ("Temperature", f"{env_view['temperature']:.0f}°F" if env_view["temperature"] is not None else "N/A"),
                        ("Condition", env_view["condition"]), ("Wind", env_view["wind"]),
                        ("Roof Type", env_view["roof_type"]), ("Environment Grade", env_view["grade"]),
                        ("Prototype Park Adj", f"{env_view['park_adjustment']*100:+.1f}%")
                    ])
                else:
                    st.warning("No game found today for this player's team.")

                st.divider()
                st.subheader("📋 Lineup Position")
                confirmed, estimated = d.get("confirmed_lineup"), d.get("recent_lineup")
                projected = int(confirmed) if confirmed else int(estimated["position"]) if estimated else None
                source = "Confirmed today's lineup" if confirmed else f"Recent lineup estimate ({estimated['sample_games']} games)" if estimated else "Manual fallback"
                if projected:
                    metric_grid([
                        ("Projected Batting Spot", f"#{projected}"), ("Lineup Source", source),
                        ("Baseline Expected AB", f"{lineup_expected_ab(projected):.1f}")
                    ], 3)
                default_position = projected or 4
                manual_position = st.selectbox("Batting Order Used by Model", list(range(1, 10)), index=default_position - 1)
                expected_ab = st.number_input("Projected At-Bats Today", 2.5, 6.0, float(lineup_expected_ab(manual_position)), .1)
                sportsbook_line = st.number_input("Sportsbook Hit Line", value=.5, step=.5)

                sim_mode = st.selectbox(
                    "Monte Carlo Simulation Size",
                    ["Quick — 500,000", "Standard — 5,000,000", "Deep — 10,000,000"],
                    index=1,
                    help="Standard runs 5 million bat/game scenarios in batches. Deep doubles that for close comparisons."
                )
                sim_count = {"Quick — 500,000": 500_000, "Standard — 5,000,000": 5_000_000, "Deep — 10,000,000": 10_000_000}[sim_mode]

                if st.button("🔥 RUN V11 PROJECTION + MONTE CARLO", use_container_width=True):
                    season_avg = safe_float(stats["avg"], 0.0) or 0.0
                    starter_hand = pitcher.get("hand") if pitcher else None
                    starter_split = split_r if starter_hand == "R" else split_l if starter_hand == "L" else None
                    hand_avg, split_weight = build_handedness_avg(season_avg, starter_split)
                    pq = calculate_pitcher_quality(pitcher)
                    pitcher_adj = pq["rate_adjustment"] if pq else 0
                    pitcher_avg = clamp(hand_avg * (1 + pitcher_adj), .05, .5)
                    recent_model, recent_weight, recent_avg = apply_recent_form(pitcher_avg, recent)
                    env_model = calculate_environment_adjustment(environment, (matchup or {}).get("venue_name", "Unknown"))
                    v8_avg = clamp(recent_model * (1 + env_model["total_adjustment"]), .05, .5)
                    starter_rate, sc_model = apply_statcast_quality(v8_avg, statcast)

                    bp_model = build_bullpen_rate(
                        season_avg, split_r, split_l, bullpen, recent, environment, statcast,
                        (matchup or {}).get("venue_name", "Unknown")
                    )
                    bullpen_rate = bp_model["rate"] if bp_model else starter_rate
                    exposure = estimate_starter_exposure(pitcher, expected_ab)
                    deterministic = combined_exposure_projection(
                        starter_rate, bullpen_rate, exposure["starter_ab"], exposure["bullpen_ab"]
                    )
                    v9_projection = probability_from_avg(starter_rate, expected_ab)
                    season_only = probability_from_avg(season_avg, expected_ab)

                    bpq = bp_model["quality"] if bp_model else None
                    seed = simulation_seed(player["id"], (matchup or {}).get("game_pk", 0))
                    with st.spinner(f"Running {sim_count:,} Monte Carlo simulations..."):
                        sim = run_monte_carlo(
                            starter_rate, bullpen_rate, expected_ab, exposure["starter_share"],
                            split_weight, sc_model.get("reliability", 0),
                            pq.get("reliability", 0) if pq else 0,
                            bpq.get("reliability", 0) if bpq else 0,
                            sim_count, seed
                        )

                    grade, data_score = confidence_summary(
                        stats, pitcher, starter_split, recent, confirmed, environment, statcast, bullpen, sim
                    )

                    st.header("🧠 V11 Model Stack")
                    metric_grid([
                        ("Season AVG", f"{season_avg:.3f}"), ("Handedness AVG", f"{hand_avg:.3f}"),
                        ("Post-Pitcher AVG", f"{pitcher_avg:.3f}"), ("Post-Recent AVG", f"{recent_model:.3f}")
                    ])
                    st.subheader("🌦️ Environment + Statcast")
                    metric_grid([
                        ("Environment Adj", f"{env_model['total_adjustment']*100:+.1f}%"),
                        ("V8 Core AVG", f"{v8_avg:.3f}"),
                        ("Contact Adj", f"{sc_model['quality_adjustment']*100:+.1f}%"),
                        ("Starter-Facing Rate", f"{starter_rate:.3f}")
                    ])

                    st.subheader("🧯 Bullpen Exposure")
                    metric_grid([
                        ("Bullpen Difficulty", bpq["difficulty"] if bpq else "N/A"),
                        ("Bullpen Hit-Rate Adj", f"{bp_model['quality_adjustment']*100:+.1f}%" if bp_model else "0.0%"),
                        ("Bullpen-Facing Rate", f"{bullpen_rate:.3f}"),
                        ("Starter Exposure", f"{exposure['starter_share']*100:.0f}%"),
                        ("Expected Starter IP", f"{exposure['starter_ip']:.1f}"),
                        ("Starter-Facing AB", f"{exposure['starter_ab']:.2f}"),
                        ("Bullpen-Facing AB", f"{exposure['bullpen_ab']:.2f}"),
                        ("V10 Deterministic 1+", f"{deterministic['p_one_plus']*100:.1f}%"),
                    ])

                    st.subheader("🎲 Monte Carlo — Uncertainty Engine")
                    metric_grid([
                        ("Simulations", f"{sim['simulations']:,}"), ("Batches", sim["batches"]),
                        ("Random Seed", sim["seed"]), ("Convergence", "PASS" if sim["converged"] else "CHECK"),
                        ("MC Standard Error", f"{sim['mc_se']*100:.3f} pts"),
                        ("Max Batch Spread", f"{sim['batch_range']*100:.2f} pts"),
                        ("Scenario 90% Range", f"{sim['scenario_low']*100:.1f}%–{sim['scenario_high']*100:.1f}%"),
                        ("Confidence Grade", grade),
                    ])

                    st.header("📊 V11 Simulation Results")
                    delta_v10 = (sim["p_one_plus"] - deterministic["p_one_plus"]) * 100
                    metric_grid([
                        ("Expected Hits", f"{sim['expected_hits']:.2f}"),
                        ("1+ Hit Probability", f"{sim['p_one_plus']*100:.1f}%", f"{delta_v10:+.1f} pts vs V10 deterministic"),
                        ("0 Hit Probability", f"{sim['p_zero']*100:.1f}%"),
                        ("Exactly 1 Hit", f"{sim['p_exact_one']*100:.1f}%"),
                        ("2+ Hit Probability", f"{sim['p_two_plus']*100:.1f}%"),
                        ("3+ Hit Probability", f"{sim['p_three_plus']*100:.1f}%"),
                        ("Median Hits", sim["median_hits"]), ("Mode Hits", sim["mode_hits"]),
                        ("Fair Odds — 1+", american_odds(sim["p_one_plus"])),
                        ("Season-Only 1+", f"{season_only['p_one_plus']*100:.1f}%"),
                        ("Data Layers", f"{data_score}/8"), ("Model Version", "V11"),
                    ])

                    st.success(
                        "V11 runs an actual bat/game Monte Carlo model. It varies at-bat count, starter-vs-bullpen exposure, "
                        "and uncertainty around the starter/bullpen hit rates instead of treating the V10 point estimate as certain."
                    )
                    st.caption(
                        "Scenario 90% Range is an input/model-uncertainty band, not a guarantee that the true probability lies inside it. "
                        "Monte Carlo standard error measures simulation noise only. V11 is still a prototype and has not yet been backtested/calibrated."
                    )
                    for warning in d.get("warnings", []):
                        st.warning(warning)

    else:
        st.info(f"The MLB {market} engine will be added later.")

else:
    market = st.selectbox("Choose Market", ["Points", "Rebounds", "Assists", "PRA", "Spread", "Game Total"])
    st.info(f"The WNBA {market} model will be added later.")

st.divider()
st.caption("Kyre Sports AI • Projection Engine V11")
