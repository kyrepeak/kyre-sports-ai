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


def current_season():
    return datetime.now(ET).year


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


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
            away = game["teams"]["away"]
            home = game["teams"]["home"]
            away_team = away["team"]
            home_team = home["team"]
            away_pitcher = away.get("probablePitcher", {})
            home_pitcher = home.get("probablePitcher", {})

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
    search = requests.get(
        f"{MLB_API}/people/search",
        params={"names": player_name},
        timeout=15,
    )
    search.raise_for_status()
    people = search.json().get("people", [])
    if not people:
        return None

    player_id = people[0].get("id")
    detail = requests.get(
        f"{MLB_API}/people/{player_id}",
        params={"hydrate": "currentTeam"},
        timeout=15,
    )
    detail.raise_for_status()
    detail_people = detail.json().get("people", [])
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
        params={"stats": "season", "group": "hitting", "season": season},
        timeout=15,
    )
    response.raise_for_status()
    groups = response.json().get("stats", [])
    if not groups or not groups[0].get("splits", []):
        return None

    stat = groups[0]["splits"][0].get("stat", {})
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
        params={"stats": "season", "group": "pitching", "season": season},
        timeout=15,
    )
    stats_response.raise_for_status()
    groups = stats_response.json().get("stats", [])
    stat = {}
    if groups and groups[0].get("splits", []):
        stat = groups[0]["splits"][0].get("stat", {})

    return {
        "name": person.get("fullName", "Unknown"),
        "hand": hand,
        "era": stat.get("era", "N/A"),
        "whip": stat.get("whip", "N/A"),
        "wins": stat.get("wins", 0),
        "losses": stat.get("losses", 0),
        "games_started": stat.get("gamesStarted", 0),
        "innings": stat.get("inningsPitched", "0.0"),
        "strikeouts": stat.get("strikeOuts", 0),
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

        for group in response.json().get("stats", []):
            for split in group.get("splits", []):
                split_info = split.get("split", {}) or {}
                code = str(split_info.get("code", "")).lower()
                desc = str(split_info.get("description", "")).lower()
                explicit_match = (
                    code == sit_code
                    or (hand == "R" and "right" in desc)
                    or (hand == "L" and "left" in desc)
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


def build_hit_projection(season_avg, hand_split, expected_ab):
    """Blend season AVG with handedness split, shrinking small split samples."""
    season_avg = max(0.0, min(1.0, safe_float(season_avg)))
    adjusted_avg = season_avg
    split_avg = None
    split_ab = 0
    split_weight = 0.0

    if hand_split:
        split_avg = max(0.0, min(1.0, safe_float(hand_split.get("avg"))))
        split_ab = int(hand_split.get("at_bats", 0) or 0)

        # Empirical-Bayes style shrinkage: large split samples matter more,
        # but the split is capped at 70% so full-season performance still matters.
        split_weight = min(0.70, split_ab / (split_ab + 200.0)) if split_ab > 0 else 0.0
        adjusted_avg = (
            split_weight * split_avg
            + (1.0 - split_weight) * season_avg
        )

    p_zero = (1.0 - adjusted_avg) ** expected_ab
    p_one_plus = 1.0 - p_zero
    p_exact_one = (
        expected_ab
        * adjusted_avg
        * ((1.0 - adjusted_avg) ** (expected_ab - 1))
    )
    p_two_plus = max(0.0, p_one_plus - p_exact_one)
    expected_hits = adjusted_avg * expected_ab

    baseline_zero = (1.0 - season_avg) ** expected_ab
    baseline_one_plus = 1.0 - baseline_zero

    return {
        "season_avg": season_avg,
        "split_avg": split_avg,
        "split_ab": split_ab,
        "split_weight": split_weight,
        "adjusted_avg": adjusted_avg,
        "expected_hits": expected_hits,
        "p_zero": p_zero,
        "p_one_plus": p_one_plus,
        "p_exact_one": p_exact_one,
        "p_two_plus": p_two_plus,
        "baseline_one_plus": baseline_one_plus,
    }


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
                        matchup = find_player_matchup(games_df, player["team_id"])

                        pitcher_stats = None
                        hand_split = None
                        if matchup and pd.notna(matchup.get("pitcher_id")):
                            pitcher_stats = get_pitcher_stats(int(matchup["pitcher_id"]))
                            if pitcher_stats:
                                hand_split = get_hitter_vs_hand_stats(
                                    player["id"], pitcher_stats["hand"]
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
                st.caption(f"Team: {player['team_name']} • Bats: {player['bat_side']}")

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
                            st.metric("Strikeouts", pitcher["strikeouts"])

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
                    projection = build_hit_projection(
                        stats["avg"],
                        hand_split,
                        expected_ab,
                    )

                    st.header("🧠 Handedness-Adjusted Projection")
                    a1, a2, a3, a4 = st.columns(4)
                    with a1:
                        st.metric("Season AVG", f"{projection['season_avg']:.3f}")
                    with a2:
                        split_value = (
                            f"{projection['split_avg']:.3f}"
                            if projection["split_avg"] is not None
                            else "N/A"
                        )
                        st.metric("Hand Split AVG", split_value)
                    with a3:
                        st.metric("Model AVG", f"{projection['adjusted_avg']:.3f}")
                    with a4:
                        st.metric(
                            "Split Weight",
                            f"{projection['split_weight'] * 100:.0f}%",
                        )

                    st.header("📊 Projection Results")
                    r1, r2, r3 = st.columns(3)
                    with r1:
                        st.metric("Expected Hits", f"{projection['expected_hits']:.2f}")
                    with r2:
                        delta = (
                            projection["p_one_plus"]
                            - projection["baseline_one_plus"]
                        ) * 100
                        st.metric(
                            "1+ Hit Probability",
                            f"{projection['p_one_plus'] * 100:.1f}%",
                            delta=f"{delta:+.1f} pts vs season-only",
                        )
                    with r3:
                        st.metric(
                            "0 Hit Probability",
                            f"{projection['p_zero'] * 100:.1f}%",
                        )

                    r4, r5, r6 = st.columns(3)
                    with r4:
                        st.metric(
                            "Exactly 1 Hit",
                            f"{projection['p_exact_one'] * 100:.1f}%",
                        )
                    with r5:
                        st.metric(
                            "2+ Hit Probability",
                            f"{projection['p_two_plus'] * 100:.1f}%",
                        )
                    with r6:
                        st.metric(
                            "Season-Only 1+",
                            f"{projection['baseline_one_plus'] * 100:.1f}%",
                        )

                    if hand_split:
                        st.success(
                            f"V5 is now using {hand_split['label']} in the probability model. "
                            f"The split is automatically shrunk toward season AVG based on its "
                            f"{projection['split_ab']} at-bat sample, so small samples cannot take over the model."
                        )
                    else:
                        st.info(
                            "No handedness split was available, so V5 fell back to season AVG."
                        )

                    st.caption(
                        "Current model inputs: season hitting rate + pitcher-handedness split + projected AB. "
                        "Pitcher ERA/WHIP are displayed but are not yet used mathematically."
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
st.caption("Kyre Sports AI • Projection Engine V5")
