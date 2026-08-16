import streamlit as st
import requests
import pandas as pd
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
    p_zero = (1 - avg) ** expected_ab
    p_one_plus = 1 - p_zero
    p_exact_one = (
        expected_ab
        * avg
        * ((1 - avg) ** (expected_ab - 1))
    )
    p_two_plus = max(0.0, p_one_plus - p_exact_one)
    expected_hits = avg * expected_ab

    return {
        "p_zero": p_zero,
        "p_one_plus": p_one_plus,
        "p_exact_one": p_exact_one,
        "p_two_plus": p_two_plus,
        "expected_hits": expected_hits,
    }


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


def find_player_matchup(games_df, team_id):
    if games_df.empty or team_id is None:
        return None

    for _, game in games_df.iterrows():
        if game["away_team_id"] == team_id:
            return {
                "opponent": game["home_team"],
                "location": "Away",
                "pitcher_id": game["home_pitcher_id"],
                "pitcher": game["home_pitcher"],
                "first_pitch": game["first_pitch_et"],
                "status": game["status"],
            }

        if game["home_team_id"] == team_id:
            return {
                "opponent": game["away_team"],
                "location": "Home",
                "pitcher_id": game["away_pitcher_id"],
                "pitcher": game["away_pitcher"],
                "first_pitch": game["first_pitch_et"],
                "status": game["status"],
            }

    return None


# -----------------------------
# V6 MODEL LAYERS
# -----------------------------

def build_handedness_avg(season_avg, hand_split):
    if not hand_split:
        return season_avg, 0.0

    split_avg = safe_float(hand_split.get("avg"))
    split_ab = safe_float(hand_split.get("at_bats"), 0.0) or 0.0

    if split_avg is None or split_ab <= 0:
        return season_avg, 0.0

    # Empirical-Bayes-style shrinkage: 200 AB of prior weight on full-season AVG.
    split_weight = split_ab / (split_ab + 200.0)
    blended_avg = (
        season_avg * (1 - split_weight)
        + split_avg * split_weight
    )

    return blended_avg, split_weight


def calculate_pitcher_quality(pitcher):
    """
    Controlled V6 heuristic.

    Positive quality_score = tougher-than-neutral pitcher.
    Negative quality_score = more favorable-than-neutral pitcher.
    """
    if not pitcher:
        return None

    era = safe_float(pitcher.get("era"))
    whip = safe_float(pitcher.get("whip"))
    k9 = pitcher.get("k9")
    innings = pitcher.get("true_innings", 0.0) or 0.0

    if era is None or whip is None:
        return None

    # Transparent neutral anchors for this prototype layer.
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

    # Shrink small pitcher samples strongly toward neutral.
    reliability = innings / (innings + 60.0) if innings > 0 else 0.0
    shrunk_quality = raw_quality * reliability

    # Translate quality into a conservative hit-rate adjustment.
    # Tougher pitcher -> negative adjustment; weaker pitcher -> positive.
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

            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
            )

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
                        matchup = find_player_matchup(
                            games_df,
                            player["team_id"],
                        )

                        pitcher_stats = None
                        hand_split = None

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
                            "matchup": matchup,
                            "pitcher": pitcher_stats,
                            "hand_split": hand_split,
                        }

                except requests.RequestException as error:
                    st.error(f"Could not load MLB data: {error}")

        if "player_data" in st.session_state:
            data = st.session_state["player_data"]
            player = data["player"]
            stats = data["stats"]
            matchup = data["matchup"]
            pitcher = data["pitcher"]
            hand_split = data.get("hand_split")

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

                    st.write(
                        f"**Probable opposing starter:** {matchup['pitcher']}"
                    )

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
                            st.metric(
                                "W-L",
                                f"{pitcher['wins']}-{pitcher['losses']}",
                            )
                        with p6:
                            st.metric("Starts", pitcher["games_started"])
                        with p7:
                            st.metric("IP", pitcher["innings"])
                        with p8:
                            k9_text = (
                                f"{pitcher['k9']:.2f}"
                                if pitcher.get("k9") is not None
                                else "N/A"
                            )
                            st.metric("K/9", k9_text)

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

                            h5, h6, h7, h8 = st.columns(4)
                            with h5:
                                st.metric("Split OBP", hand_split["obp"])
                            with h6:
                                st.metric("Split SLG", hand_split["slg"])
                            with h7:
                                st.metric("Split HR", hand_split["home_runs"])
                            with h8:
                                st.metric("Split K", hand_split["strikeouts"])
                        else:
                            st.info(
                                "Handedness split was not available from MLB for this matchup."
                            )

                st.divider()

                expected_ab = st.number_input(
                    "Projected At-Bats Today",
                    min_value=1,
                    max_value=7,
                    value=4,
                    step=1,
                )

                sportsbook_line = st.number_input(
                    "Sportsbook Hit Line",
                    value=0.5,
                    step=0.5,
                )

                if st.button("🔥 RUN HIT PROJECTION", use_container_width=True):
                    season_avg = safe_float(stats.get("avg"), 0.0) or 0.0

                    handed_avg, split_weight = build_handedness_avg(
                        season_avg,
                        hand_split,
                    )

                    pitcher_model = calculate_pitcher_quality(pitcher)
                    pitcher_adjustment = 0.0

                    if pitcher_model:
                        pitcher_adjustment = pitcher_model["rate_adjustment"]

                    final_avg = clamp(
                        handed_avg * (1 + pitcher_adjustment),
                        0.050,
                        0.500,
                    )

                    season_result = probability_from_avg(
                        season_avg,
                        expected_ab,
                    )
                    hand_result = probability_from_avg(
                        handed_avg,
                        expected_ab,
                    )
                    final_result = probability_from_avg(
                        final_avg,
                        expected_ab,
                    )

                    st.header("🧠 V6 Model Stack")

                    a1, a2, a3, a4 = st.columns(4)
                    with a1:
                        st.metric("Season AVG", f"{season_avg:.3f}")
                    with a2:
                        split_avg = (
                            safe_float(hand_split.get("avg"), season_avg)
                            if hand_split
                            else season_avg
                        )
                        st.metric("Hand Split AVG", f"{split_avg:.3f}")
                    with a3:
                        st.metric("Handedness AVG", f"{handed_avg:.3f}")
                    with a4:
                        st.metric("Split Weight", f"{split_weight * 100:.0f}%")

                    st.subheader("🎯 Pitcher Quality Adjustment")

                    if pitcher_model:
                        q1, q2, q3, q4 = st.columns(4)
                        with q1:
                            st.metric(
                                "Pitcher Difficulty",
                                pitcher_model["difficulty"],
                            )
                        with q2:
                            st.metric(
                                "Pitcher Sample Weight",
                                f"{pitcher_model['reliability'] * 100:.0f}%",
                            )
                        with q3:
                            st.metric(
                                "Hit-Rate Adjustment",
                                f"{pitcher_adjustment * 100:+.1f}%",
                            )
                        with q4:
                            st.metric("Final Model AVG", f"{final_avg:.3f}")

                        st.caption(
                            "V6 pitcher layer uses ERA, WHIP and K/9, shrinks the effect by innings pitched, "
                            "and caps the hit-rate adjustment at ±8%. Neutral prototype anchors: "
                            f"ERA {pitcher_model['neutral_era']:.2f}, WHIP {pitcher_model['neutral_whip']:.2f}, "
                            f"K/9 {pitcher_model['neutral_k9']:.1f}."
                        )
                    else:
                        st.info(
                            "Pitcher quality data was incomplete, so no pitcher adjustment was applied."
                        )
                        st.metric("Final Model AVG", f"{final_avg:.3f}")

                    st.header("📊 Projection Results")

                    r1, r2, r3 = st.columns(3)
                    with r1:
                        st.metric(
                            "Expected Hits",
                            f"{final_result['expected_hits']:.2f}",
                        )
                    with r2:
                        vs_hand_delta = (
                            final_result["p_one_plus"]
                            - hand_result["p_one_plus"]
                        ) * 100
                        st.metric(
                            "1+ Hit Probability",
                            f"{final_result['p_one_plus'] * 100:.1f}%",
                            delta=f"{vs_hand_delta:+.1f} pts vs hand-only",
                        )
                    with r3:
                        st.metric(
                            "0 Hit Probability",
                            f"{final_result['p_zero'] * 100:.1f}%",
                        )

                    r4, r5, r6 = st.columns(3)
                    with r4:
                        st.metric(
                            "Exactly 1 Hit",
                            f"{final_result['p_exact_one'] * 100:.1f}%",
                        )
                    with r5:
                        st.metric(
                            "2+ Hit Probability",
                            f"{final_result['p_two_plus'] * 100:.1f}%",
                        )
                    with r6:
                        total_delta = (
                            final_result["p_one_plus"]
                            - season_result["p_one_plus"]
                        ) * 100
                        st.metric(
                            "Season-Only 1+",
                            f"{season_result['p_one_plus'] * 100:.1f}%",
                            delta=f"{total_delta:+.1f} pts final vs season",
                        )

                    st.success(
                        "V6 now uses season hitting + pitcher-handedness split + pitcher ERA/WHIP/K/9 + pitcher sample size."
                    )

                    st.caption(
                        "V6 is still a prototype heuristic, not a calibrated betting model. Next layers should add recent form, "
                        "lineup position, park/weather, Statcast quality of contact, bullpen exposure and simulation."
                    )

    else:
        st.info(f"The MLB {market} engine will be added later.")


else:
    market = st.selectbox(
        "Choose Market",
        ["Points", "Rebounds", "Assists", "PRA", "Spread", "Game Total"],
    )

    st.info(f"The WNBA {market} model will be added later.")


st.divider()
st.caption("Kyre Sports AI • Projection Engine V6")
