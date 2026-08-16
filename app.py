import streamlit as st
import requests
import pandas as pd
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

st.set_page_config(
    page_title="Kyre Sports AI",
    page_icon="🧠",
    layout="wide",
)

ET = ZoneInfo("America/New_York")
MLB_API = "https://statsapi.mlb.com/api/v1"


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


def innings_to_float(value):
    """Convert baseball innings like 132.1 to true innings (132 + 1/3)."""
    text = str(value or "0.0")
    if "." not in text:
        return safe_float(text, 0.0) or 0.0

    whole, outs = text.split(".", 1)
    whole_num = safe_float(whole, 0.0) or 0.0
    outs_num = int(outs[:1]) if outs[:1].isdigit() else 0
    outs_num = min(max(outs_num, 0), 2)
    return whole_num + (outs_num / 3.0)


def probability_from_avg(avg, expected_ab):
    avg = clamp(avg, 0.0, 0.999)
    expected_ab = max(float(expected_ab), 0.0)

    p_zero = (1 - avg) ** expected_ab
    p_one_plus = 1 - p_zero

    # Fractional expected AB makes a literal binomial "exactly one" imperfect.
    # We still use this smooth approximation for the prototype display.
    p_exact_one = (
        expected_ab
        * avg
        * ((1 - avg) ** max(expected_ab - 1, 0))
    )
    p_exact_one = clamp(p_exact_one, 0.0, 1.0)

    p_two_plus = max(0.0, p_one_plus - p_exact_one)
    expected_hits = avg * expected_ab

    return {
        "p_zero": p_zero,
        "p_one_plus": p_one_plus,
        "p_exact_one": p_exact_one,
        "p_two_plus": p_two_plus,
        "expected_hits": expected_hits,
    }


def lineup_expected_ab(position):
    """Simple baseline AB expectation by batting-order slot."""
    mapping = {
        1: 4.60,
        2: 4.50,
        3: 4.40,
        4: 4.30,
        5: 4.20,
        6: 4.10,
        7: 4.00,
        8: 3.90,
        9: 3.80,
    }
    return mapping.get(position, 4.10)


# -----------------------------
# LIVE MLB DATA
# -----------------------------

@st.cache_data(ttl=300)
def get_today_mlb_games():
    today_et = datetime.now(ET).strftime("%Y-%m-%d")

    response = requests.get(
        f"{MLB_API}/schedule",
        params={
            "sportId": 1,
            "date": today_et,
            "hydrate": "probablePitcher,team",
        },
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()

    games = []

    for date_block in data.get("dates", []):
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

            games.append(
                {
                    "game_pk": game.get("gamePk"),
                    "away_team_id": away_team.get("id"),
                    "away_team": away_team.get("name", "Unknown"),
                    "home_team_id": home_team.get("id"),
                    "home_team": home_team.get("name", "Unknown"),
                    "away_pitcher_id": away_pitcher.get("id"),
                    "away_pitcher": away_pitcher.get("fullName", "TBD"),
                    "home_pitcher_id": home_pitcher.get("id"),
                    "home_pitcher": home_pitcher.get("fullName", "TBD"),
                    "first_pitch_et": game_time.strftime("%I:%M %p").lstrip("0"),
                    "status": game.get("status", {}).get(
                        "detailedState", "Unknown"
                    ),
                }
            )

    return pd.DataFrame(games), today_et


@st.cache_data(ttl=3600)
def find_mlb_player(player_name):
    search_response = requests.get(
        f"{MLB_API}/people/search",
        params={"names": player_name},
        timeout=15,
    )
    search_response.raise_for_status()

    people = search_response.json().get("people", [])
    if not people:
        return None

    player_id = people[0].get("id")

    detail_response = requests.get(
        f"{MLB_API}/people/{player_id}",
        params={"hydrate": "currentTeam"},
        timeout=15,
    )
    detail_response.raise_for_status()

    detail_people = detail_response.json().get("people", [])
    if not detail_people:
        return None

    person = detail_people[0]
    current_team = person.get("currentTeam", {})

    return {
        "id": person.get("id"),
        "name": person.get("fullName", player_name),
        "team_id": current_team.get("id"),
        "team_name": current_team.get("name", "Unknown"),
        "bat_side": person.get("batSide", {}).get("code", "?"),
    }


@st.cache_data(ttl=600)
def get_player_hitting_stats(player_id):
    season = current_season()

    response = requests.get(
        f"{MLB_API}/people/{player_id}/stats",
        params={
            "stats": "season",
            "group": "hitting",
            "season": season,
        },
        timeout=15,
    )
    response.raise_for_status()

    stats_groups = response.json().get("stats", [])
    if not stats_groups:
        return None

    splits = stats_groups[0].get("splits", [])
    if not splits:
        return None

    stat = splits[0].get("stat", {})

    return {
        "season": season,
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
    season = current_season()

    person_response = requests.get(
        f"{MLB_API}/people/{pitcher_id}",
        timeout=15,
    )
    person_response.raise_for_status()

    people = person_response.json().get("people", [])
    if not people:
        return None

    person = people[0]
    hand = person.get("pitchHand", {}).get("code", "?")

    stats_response = requests.get(
        f"{MLB_API}/people/{pitcher_id}/stats",
        params={
            "stats": "season",
            "group": "pitching",
            "season": season,
        },
        timeout=15,
    )
    stats_response.raise_for_status()

    stats_groups = stats_response.json().get("stats", [])
    stat = {}

    if stats_groups:
        splits = stats_groups[0].get("splits", [])
        if splits:
            stat = splits[0].get("stat", {})

    innings_text = stat.get("inningsPitched", "0.0")
    true_innings = innings_to_float(innings_text)
    strikeouts = stat.get("strikeOuts", 0)
    strikeouts_num = safe_float(strikeouts, 0.0) or 0.0
    k9 = (strikeouts_num * 9 / true_innings) if true_innings > 0 else None

    return {
        "name": person.get("fullName", "Unknown"),
        "hand": hand,
        "era": stat.get("era", "N/A"),
        "whip": stat.get("whip", "N/A"),
        "wins": stat.get("wins", 0),
        "losses": stat.get("losses", 0),
        "games_started": stat.get("gamesStarted", 0),
        "innings": innings_text,
        "true_innings": true_innings,
        "strikeouts": strikeouts,
        "k9": k9,
    }


@st.cache_data(ttl=600)
def get_hitter_vs_hand_stats(player_id, pitcher_hand):
    hand = str(pitcher_hand or "").upper()
    if hand not in {"R", "L"}:
        return None

    season = current_season()
    sit_code = "vr" if hand == "R" else "vl"
    label = "vs RHP" if hand == "R" else "vs LHP"

    for stat_type in ["statSplits", "season"]:
        response = requests.get(
            f"{MLB_API}/people/{player_id}/stats",
            params={
                "stats": stat_type,
                "group": "hitting",
                "season": season,
                "sitCodes": sit_code,
            },
            timeout=15,
        )

        if response.status_code >= 400:
            continue

        stats_groups = response.json().get("stats", [])

        for group in stats_groups:
            for split in group.get("splits", []):
                split_info = split.get("split", {}) or {}
                split_code = str(split_info.get("code", "")).lower()
                split_desc = str(split_info.get("description", "")).lower()

                explicit_match = (
                    split_code == sit_code
                    or (hand == "R" and "right" in split_desc)
                    or (hand == "L" and "left" in split_desc)
                )

                if stat_type == "statSplits" or explicit_match:
                    stat = split.get("stat", {})
                    if not stat:
                        continue

                    return {
                        "season": season,
                        "label": label,
                        "pitcher_hand": hand,
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

    return None


@st.cache_data(ttl=600)
def get_recent_form(player_id, games=10):
    """Aggregate the hitter's most recent completed game logs."""
    season = current_season()

    response = requests.get(
        f"{MLB_API}/people/{player_id}/stats",
        params={
            "stats": "gameLog",
            "group": "hitting",
            "season": season,
        },
        timeout=15,
    )
    response.raise_for_status()

    stats_groups = response.json().get("stats", [])
    if not stats_groups:
        return None

    splits = stats_groups[0].get("splits", [])
    if not splits:
        return None

    recent_splits = splits[-games:]

    total_ab = 0
    total_hits = 0
    total_pa = 0
    total_hr = 0
    total_bb = 0
    total_so = 0
    hit_games = 0
    game_pks = []

    for split in recent_splits:
        stat = split.get("stat", {}) or {}

        ab = int(safe_float(stat.get("atBats"), 0) or 0)
        hits = int(safe_float(stat.get("hits"), 0) or 0)
        pa = int(safe_float(stat.get("plateAppearances"), 0) or 0)

        total_ab += ab
        total_hits += hits
        total_pa += pa
        total_hr += int(safe_float(stat.get("homeRuns"), 0) or 0)
        total_bb += int(safe_float(stat.get("baseOnBalls"), 0) or 0)
        total_so += int(safe_float(stat.get("strikeOuts"), 0) or 0)

        if hits > 0:
            hit_games += 1

        game_pk = split.get("game", {}).get("gamePk")
        if game_pk:
            game_pks.append(game_pk)

    recent_avg = (total_hits / total_ab) if total_ab > 0 else None
    hit_game_rate = (
        hit_games / len(recent_splits)
        if recent_splits
        else None
    )

    return {
        "games": len(recent_splits),
        "at_bats": total_ab,
        "plate_appearances": total_pa,
        "hits": total_hits,
        "home_runs": total_hr,
        "walks": total_bb,
        "strikeouts": total_so,
        "avg": recent_avg,
        "hit_games": hit_games,
        "hit_game_rate": hit_game_rate,
        "game_pks": game_pks,
    }


@st.cache_data(ttl=180)
def get_lineup_position(game_pk, player_id, team_side):
    """Return confirmed batting-order slot if today's boxscore has one."""
    if not game_pk or team_side not in {"home", "away"}:
        return None

    response = requests.get(
        f"{MLB_API}/game/{game_pk}/boxscore",
        timeout=15,
    )

    if response.status_code >= 400:
        return None

    data = response.json()
    team = data.get("teams", {}).get(team_side, {}) or {}

    batting_order = team.get("battingOrder", []) or []
    normalized_order = []

    for item in batting_order:
        if isinstance(item, int):
            normalized_order.append(item)
        elif isinstance(item, str) and item.isdigit():
            normalized_order.append(int(item))

    if int(player_id) in normalized_order:
        return normalized_order.index(int(player_id)) + 1

    players = team.get("players", {}) or {}
    player_data = players.get(f"ID{player_id}", {}) or {}
    order_value = player_data.get("battingOrder")

    if order_value is not None:
        order_text = str(order_value)
        if order_text.isdigit():
            order_num = int(order_text)
            if order_num >= 100:
                return clamp(order_num // 100, 1, 9)
            return clamp(order_num, 1, 9)

    return None


@st.cache_data(ttl=1800)
def estimate_recent_lineup_position(player_id, game_pks, max_games=5):
    """Use recent boxscores to estimate the hitter's normal lineup slot."""
    positions = []

    for game_pk in list(game_pks)[-max_games:]:
        response = requests.get(
            f"{MLB_API}/game/{game_pk}/boxscore",
            timeout=15,
        )

        if response.status_code >= 400:
            continue

        data = response.json()

        for side in ("home", "away"):
            team = data.get("teams", {}).get(side, {}) or {}
            batting_order = team.get("battingOrder", []) or []

            normalized_order = []
            for item in batting_order:
                if isinstance(item, int):
                    normalized_order.append(item)
                elif isinstance(item, str) and item.isdigit():
                    normalized_order.append(int(item))

            if int(player_id) in normalized_order:
                positions.append(normalized_order.index(int(player_id)) + 1)
                break

            players = team.get("players", {}) or {}
            player_data = players.get(f"ID{player_id}", {}) or {}
            order_value = player_data.get("battingOrder")

            if order_value is not None:
                order_text = str(order_value)
                if order_text.isdigit():
                    order_num = int(order_text)
                    if order_num >= 100:
                        positions.append(int(clamp(order_num // 100, 1, 9)))
                    else:
                        positions.append(int(clamp(order_num, 1, 9)))
                    break

    if not positions:
        return None

    counts = Counter(positions)
    most_common_count = counts.most_common(1)[0][1]
    tied = [pos for pos, count in counts.items() if count == most_common_count]

    if len(tied) == 1:
        projected = tied[0]
    else:
        projected = int(round(sum(positions) / len(positions)))

    return {
        "position": int(clamp(projected, 1, 9)),
        "sample_games": len(positions),
        "positions": positions,
    }


def find_player_matchup(games_df, team_id):
    if games_df.empty or team_id is None:
        return None

    for _, game in games_df.iterrows():
        if game["away_team_id"] == team_id:
            return {
                "game_pk": game["game_pk"],
                "team_side": "away",
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

    split_weight = split_ab / (split_ab + 200.0)
    blended_avg = (
        season_avg * (1 - split_weight)
        + split_avg * split_weight
    )

    return blended_avg, split_weight


def calculate_pitcher_quality(pitcher):
    if not pitcher:
        return None

    era = safe_float(pitcher.get("era"))
    whip = safe_float(pitcher.get("whip"))
    k9 = pitcher.get("k9")
    innings = pitcher.get("true_innings", 0.0) or 0.0

    if era is None or whip is None:
        return None

    neutral_era = 4.20
    neutral_whip = 1.30
    neutral_k9 = 8.50

    era_skill = (neutral_era - era) / neutral_era
    whip_skill = (neutral_whip - whip) / neutral_whip
    k9_skill = 0.0

    if k9 is not None:
        k9_skill = (k9 - neutral_k9) / neutral_k9

    raw_quality = (
        0.40 * era_skill
        + 0.40 * whip_skill
        + 0.20 * k9_skill
    )

    reliability = innings / (innings + 60.0) if innings > 0 else 0.0
    shrunk_quality = raw_quality * reliability
    rate_adjustment = clamp(-0.25 * shrunk_quality, -0.08, 0.08)

    if shrunk_quality >= 0.10:
        difficulty = "Very Tough"
    elif shrunk_quality >= 0.04:
        difficulty = "Tough"
    elif shrunk_quality <= -0.10:
        difficulty = "Very Favorable"
    elif shrunk_quality <= -0.04:
        difficulty = "Favorable"
    else:
        difficulty = "Near Neutral"

    return {
        "era": era,
        "whip": whip,
        "k9": k9,
        "innings": innings,
        "neutral_era": neutral_era,
        "neutral_whip": neutral_whip,
        "neutral_k9": neutral_k9,
        "raw_quality": raw_quality,
        "reliability": reliability,
        "quality_score": shrunk_quality,
        "rate_adjustment": rate_adjustment,
        "difficulty": difficulty,
    }


def apply_recent_form(base_avg, recent_form):
    if not recent_form:
        return base_avg, 0.0, None

    recent_avg = recent_form.get("avg")
    recent_ab = recent_form.get("at_bats", 0) or 0

    if recent_avg is None or recent_ab <= 0:
        return base_avg, 0.0, None

    recent_weight = 0.22 * (recent_ab / (recent_ab + 45.0))
    recent_weight = clamp(recent_weight, 0.0, 0.22)

    adjusted_avg = (
        base_avg * (1 - recent_weight)
        + recent_avg * recent_weight
    )

    return adjusted_avg, recent_weight, recent_avg


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
            display_df = games_df[
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
            st.dataframe(display_df, use_container_width=True, hide_index=True)

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

                    if player is None:
                        st.error("Player not found.")
                    else:
                        stats = get_player_hitting_stats(player["id"])
                        recent_form = get_recent_form(player["id"], games=10)
                        matchup = find_player_matchup(games_df, player["team_id"])

                        pitcher_stats = None
                        hand_split = None
                        confirmed_lineup = None
                        recent_lineup = None

                        if matchup:
                            confirmed_lineup = get_lineup_position(
                                matchup["game_pk"],
                                player["id"],
                                matchup["team_side"],
                            )

                        if recent_form:
                            recent_lineup = estimate_recent_lineup_position(
                                player["id"],
                                recent_form.get("game_pks", []),
                                max_games=5,
                            )

                        if matchup and pd.notna(matchup.get("pitcher_id")):
                            pitcher_stats = get_pitcher_stats(
                                int(matchup["pitcher_id"])
                            )

                            if pitcher_stats:
                                hand_split = get_hitter_vs_hand_stats(
                                    player["id"],
                                    pitcher_stats["hand"],
                                )

                        st.session_state["player_data"] = {
                            "player": player,
                            "stats": stats,
                            "recent_form": recent_form,
                            "matchup": matchup,
                            "pitcher": pitcher_stats,
                            "hand_split": hand_split,
                            "confirmed_lineup": confirmed_lineup,
                            "recent_lineup": recent_lineup,
                        }

                except requests.RequestException as error:
                    st.error(f"Could not load MLB data: {error}")

        if "player_data" in st.session_state:
            data = st.session_state["player_data"]

            player = data["player"]
            stats = data["stats"]
            recent_form = data.get("recent_form")
            matchup = data["matchup"]
            pitcher = data["pitcher"]
            hand_split = data.get("hand_split")
            confirmed_lineup = data.get("confirmed_lineup")
            recent_lineup = data.get("recent_lineup")

            if stats is not None:
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

                if recent_form and recent_form.get("avg") is not None:
                    rf1, rf2, rf3, rf4 = st.columns(4)
                    with rf1:
                        st.metric("Recent AVG", f"{recent_form['avg']:.3f}")
                    with rf2:
                        st.metric("Hits", recent_form["hits"])
                    with rf3:
                        st.metric("Recent AB", recent_form["at_bats"])
                    with rf4:
                        st.metric(
                            "Hit Games",
                            f"{recent_form['hit_games']}/{recent_form['games']}",
                        )

                    rf5, rf6, rf7, rf8 = st.columns(4)
                    with rf5:
                        st.metric("HR", recent_form["home_runs"])
                    with rf6:
                        st.metric("BB", recent_form["walks"])
                    with rf7:
                        st.metric("K", recent_form["strikeouts"])
                    with rf8:
                        rate = recent_form.get("hit_game_rate")
                        st.metric(
                            "1+ Hit Game Rate",
                            f"{rate * 100:.0f}%" if rate is not None else "N/A",
                        )
                else:
                    st.info("Recent game-log data was not available.")

                st.divider()
                st.subheader("⚔️ Today's Matchup")

                if matchup is None:
                    st.warning("No game found today for this player's team.")
                else:
                    m1, m2, m3, m4 = st.columns(4)
                    with m1:
                        st.metric("Opponent", matchup["opponent"])
                    with m2:
                        st.metric("Home/Away", matchup["location"])
                    with m3:
                        st.metric("First Pitch", matchup["first_pitch"])
                    with m4:
                        st.metric("Status", matchup["status"])

                    st.write(f"**Probable opposing starter:** {matchup['pitcher']}")

                    if pitcher:
                        st.subheader("🎯 Opposing Starter")

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
                            st.metric("W-L", f"{pitcher['wins']}-{pitcher['losses']}")
                        with p6:
                            st.metric("Starts", pitcher["games_started"])
                        with p7:
                            st.metric("IP", pitcher["innings"])
                        with p8:
                            st.metric(
                                "K/9",
                                f"{pitcher['k9']:.2f}" if pitcher["k9"] is not None else "N/A",
                            )

                        st.divider()
                        st.subheader("↔️ Batter vs Pitcher Hand")

                        if hand_split:
                            st.caption(
                                f"{player['name']} {hand_split['label']} in {hand_split['season']}"
                            )

                            h1, h2, h3, h4 = st.columns(4)
                            with h1:
                                st.metric("Split AVG", hand_split["avg"])
                            with h2:
                                st.metric("Split Hits", hand_split["hits"])
                            with h3:
                                st.metric("Split AB", hand_split["at_bats"])
                            with h4:
                                st.metric("Split OPS", hand_split["ops"])
                        else:
                            st.info("Handedness split was not available for this matchup.")

                st.divider()
                st.subheader("📋 Lineup Position")

                lineup_source = "Manual fallback"
                projected_position = None

                if confirmed_lineup:
                    projected_position = int(confirmed_lineup)
                    lineup_source = "Confirmed today's lineup"
                elif recent_lineup:
                    projected_position = int(recent_lineup["position"])
                    lineup_source = (
                        f"Recent lineup estimate ({recent_lineup['sample_games']} games)"
                    )

                if projected_position:
                    l1, l2, l3 = st.columns(3)
                    with l1:
                        st.metric("Projected Batting Spot", f"#{projected_position}")
                    with l2:
                        st.metric("Lineup Source", lineup_source)
                    with l3:
                        st.metric(
                            "Baseline Expected AB",
                            f"{lineup_expected_ab(projected_position):.1f}",
                        )
                else:
                    st.info(
                        "Today's batting order is not confirmed and recent lineup position could not be estimated."
                    )

                default_position = projected_position or 4

                manual_position = st.selectbox(
                    "Batting Order Used by Model",
                    options=list(range(1, 10)),
                    index=default_position - 1,
                    help=(
                        "Confirmed lineup is used automatically when available. You can override it here."
                    ),
                )

                default_expected_ab = lineup_expected_ab(manual_position)

                expected_ab = st.number_input(
                    "Projected At-Bats Today",
                    min_value=2.5,
                    max_value=6.0,
                    value=float(default_expected_ab),
                    step=0.1,
                    help=(
                        "V7 sets this from batting-order slot, but you can adjust it for game context."
                    ),
                )

                sportsbook_line = st.number_input(
                    "Sportsbook Hit Line",
                    value=0.5,
                    step=0.5,
                )

                if st.button("🔥 RUN HIT PROJECTION", use_container_width=True):
                    season_avg = safe_float(stats["avg"], 0.0) or 0.0

                    hand_avg, split_weight = build_handedness_avg(
                        season_avg,
                        hand_split,
                    )

                    pitcher_quality = calculate_pitcher_quality(pitcher)

                    pitcher_adjustment = (
                        pitcher_quality["rate_adjustment"] if pitcher_quality else 0.0
                    )

                    pitcher_avg = clamp(
                        hand_avg * (1 + pitcher_adjustment),
                        0.050,
                        0.500,
                    )

                    final_avg, recent_weight, recent_avg = apply_recent_form(
                        pitcher_avg,
                        recent_form,
                    )

                    season_only = probability_from_avg(season_avg, expected_ab)
                    hand_only = probability_from_avg(hand_avg, expected_ab)
                    pitcher_only = probability_from_avg(pitcher_avg, expected_ab)
                    final_projection = probability_from_avg(final_avg, expected_ab)

                    st.header("🧠 V7 Model Stack")

                    ms1, ms2, ms3, ms4 = st.columns(4)
                    with ms1:
                        st.metric("Season AVG", f"{season_avg:.3f}")
                    with ms2:
                        st.metric(
                            "Hand Split AVG",
                            f"{safe_float(hand_split['avg'], 0):.3f}" if hand_split else "N/A",
                        )
                    with ms3:
                        st.metric("Handedness AVG", f"{hand_avg:.3f}")
                    with ms4:
                        st.metric("Split Weight", f"{split_weight * 100:.0f}%")

                    st.subheader("🎯 Pitcher Quality Adjustment")

                    pq1, pq2, pq3, pq4 = st.columns(4)
                    with pq1:
                        st.metric(
                            "Pitcher Difficulty",
                            pitcher_quality["difficulty"] if pitcher_quality else "N/A",
                        )
                    with pq2:
                        st.metric(
                            "Pitcher Sample Weight",
                            f"{pitcher_quality['reliability'] * 100:.0f}%" if pitcher_quality else "N/A",
                        )
                    with pq3:
                        st.metric("Hit-Rate Adjustment", f"{pitcher_adjustment * 100:+.1f}%")
                    with pq4:
                        st.metric("Post-Pitcher AVG", f"{pitcher_avg:.3f}")

                    st.subheader("🔥 Recent Form Adjustment")

                    rc1, rc2, rc3, rc4 = st.columns(4)
                    with rc1:
                        st.metric(
                            "Recent AVG",
                            f"{recent_avg:.3f}" if recent_avg is not None else "N/A",
                        )
                    with rc2:
                        st.metric("Recent Weight", f"{recent_weight * 100:.0f}%")
                    with rc3:
                        st.metric("Final Model AVG", f"{final_avg:.3f}")
                    with rc4:
                        st.metric("Batting Spot / AB", f"#{manual_position} / {expected_ab:.1f}")

                    st.header("📊 Projection Results")

                    r1, r2, r3 = st.columns(3)
                    with r1:
                        st.metric("Expected Hits", f"{final_projection['expected_hits']:.2f}")
                    with r2:
                        delta_vs_v6 = (
                            final_projection["p_one_plus"] - pitcher_only["p_one_plus"]
                        ) * 100

                        st.metric(
                            "1+ Hit Probability",
                            f"{final_projection['p_one_plus'] * 100:.1f}%",
                            delta=f"{delta_vs_v6:+.1f} pts vs V6 core",
                        )
                    with r3:
                        st.metric("0 Hit Probability", f"{final_projection['p_zero'] * 100:.1f}%")

                    r4, r5, r6 = st.columns(3)
                    with r4:
                        st.metric("Exactly 1 Hit", f"{final_projection['p_exact_one'] * 100:.1f}%")
                    with r5:
                        st.metric("2+ Hit Probability", f"{final_projection['p_two_plus'] * 100:.1f}%")
                    with r6:
                        season_delta = (
                            final_projection["p_one_plus"] - season_only["p_one_plus"]
                        ) * 100

                        st.metric(
                            "Season-Only 1+",
                            f"{season_only['p_one_plus'] * 100:.1f}%",
                            delta=f"{season_delta:+.1f} pts final vs season",
                        )

                    st.success(
                        "V7 now uses season hitting + pitcher-handedness split + pitcher quality + recent 10-game form + batting-order position to set expected at-bats."
                    )

                    st.caption(
                        "V7 remains a prototype heuristic, not a calibrated betting model. Recent form is intentionally capped at a small weight, and lineup position affects opportunity through projected at-bats."
                    )

    else:
        st.info(f"The MLB {market} engine will be added later.")

else:
    market = st.selectbox(
        "Choose Market",
        [
            "Points",
            "Rebounds",
            "Assists",
            "PRA",
            "Spread",
            "Game Total",
        ],
    )

    st.info(f"The WNBA {market} model will be added later.")

st.divider()
st.caption("Kyre Sports AI • Projection Engine V7")
