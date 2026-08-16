import streamlit as st

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

player = st.text_input("Player / Team")

line = st.number_input(
    "Sportsbook Line",
    value=0.5,
    step=0.5
)

if st.button("🔥 RUN AI ANALYSIS", use_container_width=True):

    st.success("Projection engine is working!")

    st.write("### Analysis")

    st.write(f"**Sport:** {sport}")
    st.write(f"**Market:** {market}")
    st.write(f"**Player / Team:** {player}")
    st.write(f"**Line:** {line}")

    st.info(
        "The advanced projection model will be added next."
    )

st.divider()

st.caption("Kyre Sports AI • Projection Engine V1")
