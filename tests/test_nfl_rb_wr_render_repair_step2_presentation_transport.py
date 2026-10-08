from pathlib import Path


def _src(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


RUSH = _src("nfl_rushing_yards_hub_v4.py")
RECV = _src("nfl_receiving_yards_hub_v13.py")
HARDENED = _src("nfl_prop_analytics_page2_responsive_polish_v1.py")


def test_rushing_cards_use_hardened_html_transport() -> None:
    assert "st.html(_COMPACT_CSS)" in RUSH
    assert "st.markdown(_COMPACT_CSS, unsafe_allow_html=True)" not in RUSH
    assert "compact_slot.html(board)" in RUSH
    assert "compact_slot.markdown(board, unsafe_allow_html=True)" not in RUSH


def test_receiving_step13_css_uses_hardened_html_transport() -> None:
    assert "st.html(_STEP13_CSS)" in RECV
    assert "st.markdown(_STEP13_CSS, unsafe_allow_html=True)" not in RECV


def test_hardened_transport_matches_existing_certified_precedent() -> None:
    assert "st.html(" in HARDENED
    assert 'data-prop-page2-responsive-polish-css="v1"' in HARDENED


def test_projection_and_card_semantics_remain_unchanged() -> None:
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in RECV
    assert "sportsbook projection influence <strong>0.0%</strong>" in RUSH
    for token in (
        "Projected Rush Yards",
        "FanDuel Line",
        "Projection − Line",
        "Expected Carries",
        "Expected YPC",
        "Over Price",
    ):
        assert token in RUSH
    for token in (
        "CERTIFIED PROJECTION",
        "Projected Rec Yds",
        "FanDuel Rec Yds",
        "frozen V9 matchup classification",
        "projection influence 0.0%",
    ):
        assert token in RECV
