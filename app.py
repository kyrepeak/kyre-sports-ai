import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

st.set_page_config(
    page_title="Kyre Sports AI",
    page_icon="🧠",
    layout="wide"
)

# ---------------------------------
# LIVE MLB SCHEDULE
# ---------------------------------

@st.cache_data(ttl=300)
def get_today_mlb_games():

    today_et = datetime.now(
        ZoneInfo("America/New_York")
    ).strftime("%Y-%m-%d")

    url = "https://statsapi.mlb.com/api/v1/schedule"

    params = {
        "sportId": 1,
        "date": today_et,
        "hydrate": "probablePitcher,team"
    }

    response = requests.get(
        url,
        params=params,
        timeout=15
    )

    response.raise_for_status()

    data = response.json()

    games = []

    for date_block in data.get("dates", []):

        for game in date_block.get("games", []):

            away = game["teams"]["away"]["team"]["name"]
            home = game["teams"]["home"]["team"]["name"]

            away_pitcher = (
                game["teams"]["away"]
                .get("probablePitcher", {})
                .get("fullName", "TBD")
            )

            home_pitcher = (
                game["teams"]["home"]
                .get("probablePitcher", {})
                .get("fullName", "TBD")
            )

            game_time = datetime.fromisoformat(
                game["gameDate"].replace("Z", "+00:00")
            ).astimezone(
                ZoneInfo("America/New_York")
            )

            games.append({
                "Away": away,
                "Home": home,
                "First Pitch (ET)": game_time.strftime(
                    "%I:%M %p"
                ).lstrip("0"),
                "Away Probable Pitcher": away_pitcher,
                "Home Probable Pitcher": home_pitcher,
                "Status": game["status"]["detailedState"]
            })

    return pd.DataFrame(games), today_et


# ---------------------------------
# FIND MLB PLAYER
# ---------------------------------

@st.cache_data(ttl=3600)
def find_mlb_player(player_name):

    url = "https://statsapi.mlb.com/api/v1/people/search"

    params = {
        "names": player_name
    }

    response = requests.get(
        url,
        params=params,
        timeout=15
    )

    response.raise_for_status()

    data = response.json()

    people = data.get("people", [])

    if not people:
        return None

    player = people[0]

    return {
        "id": player.get("id"),
        "name": player.get("fullName", player_name)
    }


# ---------------------------------
# GET PLAYER SEASON HITTING STATS
# ---------------------------------

@st.cache_data(ttl=600)
def get_player_hitting_stats(player_id):

    season = datetime.now(
        ZoneInfo("America/New_York")
    ).year

    url = (
        f"https://statsapi.mlb.com/api/v1/"
        f"people/{player_id}/stats"
    )

    params = {
        "stats": "season",
        "group": "hitting",
        "season": season
    }

    response = requests.get(
        url,
        params=params,
        timeout=15
    )

    response.raise_for_status()

    data = response.json()

    stats_groups = data.get("stats", [])

    if not stats_groups:
        return None

    splits = stats_groups[0].get("splits", [])

    if not splits:
        return None

    stat = splits[0].get("stat", {})

    return {
        "season": season,
        "games": stat.get("gamesPlayed", 0),
        "at_bats": stat.get("atBats", 0),
        "hits": stat.get("hits", 0),
        "home_runs": stat.get("homeRuns", 0),
        "runs": stat.get("runs", 0),
        "rbi": stat.get("rbi", 0),
        "walks": stat.get("baseOnBalls", 0),
        "strikeouts": stat.get("strikeOuts", 0),
        "avg": stat.get("avg", ".000"),
        "obp": stat.get("obp", ".000"),
        "slg": stat.get("slg", ".000"),
        "ops": stat.get("ops", ".000")
    }


# ---------------------------------
# WEBSITE
# ---------------------------------

st.title("🧠 KYRE SPORTS AI")

st.subheader(
    "Sports Projection & Analytics Engine"
)

st.divider()

sport = st.selectbox(
    "Choose Sport",
    ["MLB", "WNBA"]
)


# =================================
# MLB
# =================================

if sport == "MLB":

    st.header("📡 Live MLB Data")

    if st.button(
        "🔄 LOAD TODAY'S MLB GAMES",
        use_container_width=True
    ):

        try:

            games_df, game_date = get_today_mlb_games()

            if games_df.empty:

                st.warning(
                    f"No MLB games found for {game_date}."
                )

            else:

                st.success(
                    f"Live MLB schedule loaded for {game_date}."
                )

                st.dataframe(
                    games_df,
                    use_container_width=True,
                    hide_index=True
                )

        except requests.RequestException as error:

            st.error(
                f"Could not load MLB schedule: {error}"
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
            "Game Total"
        ]
    )

    # -----------------------------
    # 1+ HIT
    # -----------------------------

    if market == "1+ Hit":

        st.header("⚾ MLB 1+ Hit Projection")

        player_name = st.text_input(
            "Player Name",
            placeholder="Example: Yordan Alvarez"
        )

        if st.button(
            "📡 LOAD PLAYER STATS",
            use_container_width=True
        ):

            if not player_name.strip():

                st.error(
                    "Enter a player name first."
                )

            else:

                try:

                    player = find_mlb_player(
                        player_name.strip()
                    )

                    if player is None:

                        st.error(
                            "Player could not be found."
                        )

                    else:

                        stats = get_player_hitting_stats(
                            player["id"]
                        )

                        if stats is None:

                            st.error(
                                "No current season hitting stats were found."
                            )

                        else:

                            st.session_state["player_data"] = {
                                "player": player,
                                "stats": stats
                            }

                except requests.RequestException as error:

                    st.error(
                        f"Could not load player data: {error}"
                    )


        # ---------------------------------
        # DISPLAY PLAYER DATA
        # ---------------------------------

        if "player_data" in st.session_state:

            player = st.session_state[
                "player_data"
            ]["player"]

            stats = st.session_state[
                "player_data"
            ]["stats"]

            st.success(
                f"Live stats loaded for {player['name']}"
            )

            st.subheader(
                f"📊 {player['name']} — {stats['season']}"
            )

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric(
                    "AVG",
                    stats["avg"]
                )

            with col2:
                st.metric(
                    "Hits",
                    stats["hits"]
                )

            with col3:
                st.metric(
                    "At-Bats",
                    stats["at_bats"]
                )

            with col4:
                st.metric(
                    "Games",
                    stats["games"]
                )

            col5, col6, col7, col8 = st.columns(4)

            with col5:
                st.metric(
                    "HR",
                    stats["home_runs"]
                )

            with col6:
                st.metric(
                    "OBP",
                    stats["obp"]
                )

            with col7:
                st.metric(
                    "SLG",
                    stats["slg"]
                )

            with col8:
                st.metric(
                    "OPS",
                    stats["ops"]
                )

            st.divider()

            expected_ab = st.number_input(
                "Projected At-Bats Today",
                min_value=1,
                max_value=7,
                value=4,
                step=1
            )

            sportsbook_line = st.number_input(
                "Sportsbook Hit Line",
                value=0.5,
                step=0.5
            )

            if st.button(
                "🔥 RUN HIT PROJECTION",
                use_container_width=True
            ):

                try:

                    batting_average = float(
                        stats["avg"]
                    )

                except:

                    batting_average = 0.0

                probability_zero_hits = (
                    1 - batting_average
                ) ** expected_ab

                probability_one_plus = (
                    1 - probability_zero_hits
                )

                probability_exactly_one = (
                    expected_ab
                    * batting_average
                    * (
                        (1 - batting_average)
                        ** (expected_ab - 1)
                    )
                )

                probability_two_plus = max(
                    0,
                    probability_one_plus
                    - probability_exactly_one
                )

                expected_hits = (
                    batting_average
                    * expected_ab
                )

                st.success(
                    f"Projection completed for {player['name']}"
                )

                st.header(
                    "📊 Projection Results"
                )

                col1, col2, col3 = st.columns(3)

                with col1:

                    st.metric(
                        "Expected Hits",
                        f"{expected_hits:.2f}"
                    )

                with col2:

                    st.metric(
                        "1+ Hit Probability",
                        f"{probability_one_plus * 100:.1f}%"
                    )

                with col3:

                    st.metric(
                        "0 Hit Probability",
                        f"{probability_zero_hits * 100:.1f}%"
                    )

                col4, col5 = st.columns(2)

                with col4:

                    st.metric(
                        "Exactly 1 Hit",
                        f"{probability_exactly_one * 100:.1f}%"
                    )

                with col5:

                    st.metric(
                        "2+ Hit Probability",
                        f"{probability_two_plus * 100:.1f}%"
                    )

                st.divider()

                if probability_one_plus >= 0.75:
                    grade = "A+"

                elif probability_one_plus >= 0.70:
                    grade = "A"

                elif probability_one_plus >= 0.65:
                    grade = "B+"

                elif probability_one_plus >= 0.60:
                    grade = "B"

                elif probability_one_plus >= 0.55:
                    grade = "C+"

                else:
                    grade = "C"

                st.subheader(
                    "🧠 Model Grade"
                )

                st.metric(
                    "1+ Hit Grade",
                    grade
                )

                st.info(
                    "This is still a baseline probability model. "
                    "The player's live season statistics are now automatic. "
                    "Starting pitcher, Statcast, recent form, lineup position, "
                    "park, weather and bullpen adjustments come next."
                )

    else:

        st.info(
            f"The MLB {market} engine will be added later."
        )


# =================================
# WNBA
# =================================

else:

    market = st.selectbox(
        "Choose Market",
        [
            "Points",
            "Rebounds",
            "Assists",
            "PRA",
            "Spread",
            "Game Total"
        ]
    )

    st.info(
        f"The WNBA {market} model will be added later."
    )


st.divider()

st.caption(
    "Kyre Sports AI • Projection Engine V2"
)
