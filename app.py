import streamlit as st
import math

st.set_page_config(
    page_title="Kyre Sports AI",
    page_icon="🧠",
    layout="wide"
)

st.title("🧠 KYRE SPORTS AI")
st.subheader("Sports Projection & Analytics Engine")

st.divider()

sport = st.selectbox(
    "Choose Sport",
    ["MLB", "WNBA"]
)

# -----------------------------
# MLB
# -----------------------------

if sport == "MLB":

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

        st.header("⚾ MLB 1+ Hit Projection")

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
                st.error("Enter a player name.")

            else:

                # Simple baseline hit model
                hit_probability_per_ab = batting_average

                probability_zero_hits = (
                    1 - hit_probability_per_ab
                ) ** expected_ab

                probability_one_plus = (
                    1 - probability_zero_hits
                )

                expected_hits = (
                    batting_average * expected_ab
                )

                # Approximate probability of exactly one hit
                probability_exactly_one = (
                    expected_ab
                    * batting_average
                    * ((1 - batting_average) ** (expected_ab - 1))
                )

                probability_two_plus = max(
                    0,
                    probability_one_plus - probability_exactly_one
                )

                st.success(
                    f"Projection completed for {player}"
                )

                st.divider()

                st.header("📊 Projection Results")

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

                st.subheader("⚾ Matchup")

                st.write(
                    f"**Player:** {player}"
                )

                st.write(
                    f"**Opponent:** {opponent}"
                )

                st.write(
                    f"**Batting Average:** {batting_average:.3f}"
                )

                st.write(
                    f"**Projected At-Bats:** {expected_ab:.1f}"
                )

                st.write(
                    f"**Sportsbook Line:** {sportsbook_line}"
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

                st.subheader("🧠 Model Grade")

                st.metric(
                    "Hit Probability Grade",
                    grade
                )

                st.warning(
                    "This is the Version 1 baseline model. "
                    "It currently uses batting average and expected at-bats. "
                    "Pitcher matchup, Statcast, lineup, weather, park, "
                    "bullpen and recent-form adjustments will be added next."
                )

    else:

        st.info(
            f"The MLB {market} model is coming next."
        )

# -----------------------------
# WNBA
# -----------------------------

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
        f"The WNBA {market} projection engine will be added after "
        f"the MLB engine is working."
    )

st.divider()

st.caption(
    "Kyre Sports AI • Projection Engine V1"
)
