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


st.title("🧠 KYRE SPORTS AI")

st.subheader(
    "Sports Projection & Analytics Engine"
)

st.divider()

sport = st.selectbox(
    "Choose Sport",
    ["MLB", "WNBA"]
)


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
                    f"No MLB games were found for {game_date}."
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
                f"Could not load MLB data: {error}"
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

    if market == "1+ Hit":

        st.header(
            "⚾ MLB 1+ Hit Projection"
        )

        player = st.text_input(
            "Player Name",
            placeholder="Example: Yordan Alvarez"
        )

        opponent = st.text_input(
            "Opponent",
            placeholder="Example: Seattle Mariners"
        )

        batting_average = st.number_input(
            "Player Batting Average",
            min_value=0.000,
            max_value=1.000,
            value=0.280,
            step=0.001,
            format="%.3f"
        )

        expected_ab = st.number_input(
            "Expected At-Bats",
            min_value=1.0,
            max_value=7.0,
            value=4.0,
            step=0.1
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

            if player.strip() == "":

                st.error(
                    "Enter a player name."
                )

            else:

                probability_zero_hits = (
                    1 - batting_average
                ) ** expected_ab

                probability_one_plus = (
                    1 - probability_zero_hits
                )

                expected_hits = (
                    batting_average * expected_ab
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

                st.success(
                    f"Projection completed for {player}"
                )

                st.divider()

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

                if probability_one_plus >= 0.70:
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
                    "Hit Probability Grade",
                    grade
                )

                st.warning(
                    "Live MLB schedule data is now connected. "
                    "Player stats, pitcher stats, Statcast, weather, "
                    "park and lineup adjustments will be added next."
                )

    else:

        st.info(
            f"The MLB {market} model is coming next."
        )


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
    "Kyre Sports AI • Projection Engine V1"
)
