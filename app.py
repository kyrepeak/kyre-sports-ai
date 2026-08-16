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

ET = ZoneInfo("America/New_York")


@st.cache_data(ttl=300)
def get_today_mlb_games():
    today_et = datetime.now(ET).strftime("%Y-%m-%d")

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

            away_block = game["teams"]["away"]
            home_block = game["teams"]["home"]

            away_team = away_block["team"]
            home_team = home_block["team"]

            away_pitcher = away_block.get(
                "probablePitcher",
                {}
            )

            home_pitcher = home_block.get(
                "probablePitcher",
                {}
            )

            game_time = datetime.fromisoformat(
                game["gameDate"].replace(
                    "Z",
                    "+00:00"
                )
            ).astimezone(ET)

            games.append({
                "game_pk": game.get("gamePk"),

                "away_team_id":
                    away_team.get("id"),

                "away_team":
                    away_team.get(
                        "name",
                        "Unknown"
                    ),

                "home_team_id":
                    home_team.get("id"),

                "home_team":
                    home_team.get(
                        "name",
                        "Unknown"
                    ),

                "away_pitcher_id":
                    away_pitcher.get("id"),

                "away_pitcher":
                    away_pitcher.get(
                        "fullName",
                        "TBD"
                    ),

                "home_pitcher_id":
                    home_pitcher.get("id"),

                "home_pitcher":
                    home_pitcher.get(
                        "fullName",
                        "TBD"
                    ),

                "first_pitch_et":
                    game_time.strftime(
                        "%I:%M %p"
                    ).lstrip("0"),

                "status":
                    game.get(
                        "status",
                        {}
                    ).get(
                        "detailedState",
                        "Unknown"
                    )
            })

    return pd.DataFrame(games), today_et


@st.cache_data(ttl=3600)
def find_mlb_player(player_name):

    search_url = (
        "https://statsapi.mlb.com/"
        "api/v1/people/search"
    )

    response = requests.get(
        search_url,
        params={
            "names": player_name
        },
        timeout=15
    )

    response.raise_for_status()

    people = response.json().get(
        "people",
        []
    )

    if not people:
        return None

    player_id = people[0].get("id")

    detail_url = (
        f"https://statsapi.mlb.com/"
        f"api/v1/people/{player_id}"
    )

    detail_response = requests.get(
        detail_url,
        timeout=15
    )

    detail_response.raise_for_status()

    detail_people = (
        detail_response
        .json()
        .get("people", [])
    )

    if not detail_people:
        return None

    person = detail_people[0]

    current_team = person.get(
        "currentTeam",
        {}
    )

    return {
        "id":
            person.get("id"),

        "name":
            person.get(
                "fullName",
                player_name
            ),

        "team_id":
            current_team.get("id"),

        "team_name":
            current_team.get(
                "name",
                "Unknown"
            )
    }


@st.cache_data(ttl=600)
def get_player_hitting_stats(
    player_id
):

    season = datetime.now(
        ET
    ).year

    url = (
        f"https://statsapi.mlb.com/"
        f"api/v1/people/"
        f"{player_id}/stats"
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

    stats_groups = (
        response
        .json()
        .get("stats", [])
    )

    if not stats_groups:
        return None

    splits = (
        stats_groups[0]
        .get("splits", [])
    )

    if not splits:
        return None

    stat = splits[0].get(
        "stat",
        {}
    )

    return {
        "season":
            season,

        "games":
            stat.get(
                "gamesPlayed",
                0
            ),

        "at_bats":
            stat.get(
                "atBats",
                0
            ),

        "hits":
            stat.get(
                "hits",
                0
            ),

        "home_runs":
            stat.get(
                "homeRuns",
                0
            ),

        "avg":
            stat.get(
                "avg",
                ".000"
            ),

        "obp":
            stat.get(
                "obp",
                ".000"
            ),

        "slg":
            stat.get(
                "slg",
                ".000"
            ),

        "ops":
            stat.get(
                "ops",
                ".000"
            )
    }


@st.cache_data(ttl=600)
def get_pitcher_stats(
    pitcher_id
):

    season = datetime.now(
        ET
    ).year

    person_url = (
        f"https://statsapi.mlb.com/"
        f"api/v1/people/"
        f"{pitcher_id}"
    )

    response = requests.get(
        person_url,
        timeout=15
    )

    response.raise_for_status()

    people = response.json().get(
        "people",
        []
    )

    if not people:
        return None

    person = people[0]

    hand = (
        person.get(
            "pitchHand",
            {}
        ).get(
            "code",
            "?"
        )
    )

    stats_url = (
        f"https://statsapi.mlb.com/"
        f"api/v1/people/"
        f"{pitcher_id}/stats"
    )

    stats_response = requests.get(
        stats_url,
        params={
            "stats": "season",
            "group": "pitching",
            "season": season
        },
        timeout=15
    )

    stats_response.raise_for_status()

    stats_groups = (
        stats_response
        .json()
        .get("stats", [])
    )

    stat = {}

    if stats_groups:

        splits = (
            stats_groups[0]
            .get("splits", [])
        )

        if splits:

            stat = (
                splits[0]
                .get("stat", {})
            )

    return {
        "name":
            person.get(
                "fullName",
                "Unknown"
            ),

        "hand":
            hand,

        "era":
            stat.get(
                "era",
                "N/A"
            ),

        "whip":
            stat.get(
                "whip",
                "N/A"
            ),

        "wins":
            stat.get(
                "wins",
                0
            ),

        "losses":
            stat.get(
                "losses",
                0
            ),

        "games_started":
            stat.get(
                "gamesStarted",
                0
            ),

        "innings":
            stat.get(
                "inningsPitched",
                "0.0"
            ),

        "strikeouts":
            stat.get(
                "strikeOuts",
                0
            )
    }


def find_player_matchup(
    games_df,
    team_id
):

    if (
        games_df.empty
        or team_id is None
    ):
        return None

    for _, game in games_df.iterrows():

        if (
            game["away_team_id"]
            == team_id
        ):

            return {
                "opponent":
                    game["home_team"],

                "location":
                    "Away",

                "pitcher_id":
                    game[
                        "home_pitcher_id"
                    ],

                "pitcher":
                    game[
                        "home_pitcher"
                    ],

                "first_pitch":
                    game[
                        "first_pitch_et"
                    ],

                "status":
                    game["status"]
            }

        if (
            game["home_team_id"]
            == team_id
        ):

            return {
                "opponent":
                    game["away_team"],

                "location":
                    "Home",

                "pitcher_id":
                    game[
                        "away_pitcher_id"
                    ],

                "pitcher":
                    game[
                        "away_pitcher"
                    ],

                "first_pitch":
                    game[
                        "first_pitch_et"
                    ],

                "status":
                    game["status"]
            }

    return None


st.title(
    "🧠 KYRE SPORTS AI"
)

st.subheader(
    "Sports Projection & Analytics Engine"
)

st.divider()

sport = st.selectbox(
    "Choose Sport",
    [
        "MLB",
        "WNBA"
    ]
)


if sport == "MLB":

    try:

        games_df, game_date = (
            get_today_mlb_games()
        )

    except:

        games_df = pd.DataFrame()

        game_date = (
            datetime.now(
                ET
            ).strftime(
                "%Y-%m-%d"
            )
        )


    st.header(
        "📡 Live MLB Data"
    )

    if st.button(
        "🔄 LOAD TODAY'S MLB GAMES",
        use_container_width=True
    ):

        if games_df.empty:

            st.warning(
                "No MLB games found."
            )

        else:

            st.success(
                f"Schedule loaded for "
                f"{game_date}"
            )

            display_df = (
                games_df[
                    [
                        "away_team",
                        "home_team",
                        "first_pitch_et",
                        "away_pitcher",
                        "home_pitcher",
                        "status"
                    ]
                ]
                .rename(
                    columns={
                        "away_team":
                            "Away",

                        "home_team":
                            "Home",

                        "first_pitch_et":
                            "First Pitch (ET)",

                        "away_pitcher":
                            "Away Pitcher",

                        "home_pitcher":
                            "Home Pitcher",

                        "status":
                            "Status"
                    }
                )
            )

            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True
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

        player_name = st.text_input(
            "Player Name",
            placeholder=(
                "Example: "
                "Yordan Alvarez"
            )
        )


        if st.button(
            "📡 LOAD PLAYER + MATCHUP",
            use_container_width=True
        ):

            if not player_name.strip():

                st.error(
                    "Enter a player name."
                )

            else:

                try:

                    player = (
                        find_mlb_player(
                            player_name
                        )
                    )

                    if player is None:

                        st.error(
                            "Player not found."
                        )

                    else:

                        stats = (
                            get_player_hitting_stats(
                                player["id"]
                            )
                        )

                        matchup = (
                            find_player_matchup(
                                games_df,
                                player["team_id"]
                            )
                        )

                        pitcher_stats = None

                        if (
                            matchup
                            and matchup[
                                "pitcher_id"
                            ]
                        ):

                            pitcher_stats = (
                                get_pitcher_stats(
                                    int(
                                        matchup[
                                            "pitcher_id"
                                        ]
                                    )
                                )
                            )

                        st.session_state[
                            "player_data"
                        ] = {
                            "player":
                                player,

                            "stats":
                                stats,

                            "matchup":
                                matchup,

                            "pitcher":
                                pitcher_stats
                        }

                except (
                    requests
                    .RequestException
                ) as error:

                    st.error(
                        f"Could not load "
                        f"MLB data: {error}"
                    )


        if (
            "player_data"
            in st.session_state
        ):

            data = (
                st.session_state[
                    "player_data"
                ]
            )

            player = data["player"]
            stats = data["stats"]
            matchup = data["matchup"]
            pitcher = data["pitcher"]


            if stats is not None:

                st.success(
                    f"Live data loaded "
                    f"for {player['name']}"
                )

                st.subheader(
                    f"📊 "
                    f"{player['name']} "
                    f"— "
                    f"{stats['season']}"
                )

                st.caption(
                    f"Team: "
                    f"{player['team_name']}"
                )

                c1, c2, c3, c4 = (
                    st.columns(4)
                )

                with c1:
                    st.metric(
                        "AVG",
                        stats["avg"]
                    )

                with c2:
                    st.metric(
                        "Hits",
                        stats["hits"]
                    )

                with c3:
                    st.metric(
                        "At-Bats",
                        stats["at_bats"]
                    )

                with c4:
                    st.metric(
                        "Games",
                        stats["games"]
                    )


                c5, c6, c7, c8 = (
                    st.columns(4)
                )

                with c5:
                    st.metric(
                        "HR",
                        stats["home_runs"]
                    )

                with c6:
                    st.metric(
                        "OBP",
                        stats["obp"]
                    )

                with c7:
                    st.metric(
                        "SLG",
                        stats["slg"]
                    )

                with c8:
                    st.metric(
                        "OPS",
                        stats["ops"]
                    )


                st.divider()

                st.subheader(
                    "⚔️ Today's Matchup"
                )


                if matchup is None:

                    st.warning(
                        "No game found today "
                        "for this player's team."
                    )

                else:

                    m1, m2, m3, m4 = (
                        st.columns(4)
                    )

                    with m1:
                        st.metric(
                            "Opponent",
                            matchup[
                                "opponent"
                            ]
                        )

                    with m2:
                        st.metric(
                            "Home/Away",
                            matchup[
                                "location"
                            ]
                        )

                    with m3:
                        st.metric(
                            "First Pitch",
                            matchup[
                                "first_pitch"
                            ]
                        )

                    with m4:
                        st.metric(
                            "Status",
                            matchup[
                                "status"
                            ]
                        )


                    st.write(
                        "**Probable opposing "
                        "starter:** "
                        f"{matchup['pitcher']}"
                    )


                    if pitcher:

                        st.subheader(
                            "🎯 Opposing Starter"
                        )

                        p1, p2, p3, p4 = (
                            st.columns(4)
                        )

                        with p1:
                            st.metric(
                                "Pitcher",
                                pitcher[
                                    "name"
                                ]
                            )

                        with p2:
                            st.metric(
                                "Throws",
                                pitcher[
                                    "hand"
                                ]
                            )

                        with p3:
                            st.metric(
                                "ERA",
                                pitcher[
                                    "era"
                                ]
                            )

                        with p4:
                            st.metric(
                                "WHIP",
                                pitcher[
                                    "whip"
                                ]
                            )


                        p5, p6, p7, p8 = (
                            st.columns(4)
                        )

                        with p5:
                            st.metric(
                                "W-L",
                                f"{pitcher['wins']}"
                                f"-"
                                f"{pitcher['losses']}"
                            )

                        with p6:
                            st.metric(
                                "Starts",
                                pitcher[
                                    "games_started"
                                ]
                            )

                        with p7:
                            st.metric(
                                "IP",
                                pitcher[
                                    "innings"
                                ]
                            )

                        with p8:
                            st.metric(
                                "Strikeouts",
                                pitcher[
                                    "strikeouts"
                                ]
                            )


                st.divider()

                expected_ab = (
                    st.number_input(
                        "Projected At-Bats Today",
                        min_value=1,
                        max_value=7,
                        value=4,
                        step=1
                    )
                )

                sportsbook_line = (
                    st.number_input(
                        "Sportsbook Hit Line",
                        value=0.5,
                        step=0.5
                    )
                )


                if st.button(
                    "🔥 RUN HIT PROJECTION",
                    use_container_width=True
                ):

                    try:

                        batting_average = (
                            float(
                                stats[
                                    "avg"
                                ]
                            )
                        )

                    except:

                        batting_average = 0


                    p_zero = (
                        1
                        - batting_average
                    ) ** expected_ab

                    p_one_plus = (
                        1
                        - p_zero
                    )

                    p_exact_one = (
                        expected_ab
                        * batting_average
                        * (
                            (
                                1
                                - batting_average
                            )
                            ** (
                                expected_ab
                                - 1
                            )
                        )
                    )

                    p_two_plus = max(
                        0,
                        p_one_plus
                        - p_exact_one
                    )

                    expected_hits = (
                        batting_average
                        * expected_ab
                    )


                    st.header(
                        "📊 Projection Results"
                    )

                    r1, r2, r3 = (
                        st.columns(3)
                    )

                    with r1:
                        st.metric(
                            "Expected Hits",
                            f"{expected_hits:.2f}"
                        )

                    with r2:
                        st.metric(
                            "1+ Hit Probability",
                            f"{p_one_plus * 100:.1f}%"
                        )

                    with r3:
                        st.metric(
                            "0 Hit Probability",
                            f"{p_zero * 100:.1f}%"
                        )


                    r4, r5 = (
                        st.columns(2)
                    )

                    with r4:
                        st.metric(
                            "Exactly 1 Hit",
                            f"{p_exact_one * 100:.1f}%"
                        )

                    with r5:
                        st.metric(
                            "2+ Hit Probability",
                            f"{p_two_plus * 100:.1f}%"
                        )


                    st.warning(
                        "Pitcher and matchup data "
                        "are now live. "
                        "The next version will "
                        "actually use pitcher "
                        "quality, handedness, "
                        "recent form and Statcast "
                        "to adjust the probability."
                    )


    else:

        st.info(
            f"The MLB {market} "
            f"engine will be added later."
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
        f"The WNBA {market} "
        f"model will be added later."
    )


st.divider()

st.caption(
    "Kyre Sports AI • Projection Engine V3"
)
