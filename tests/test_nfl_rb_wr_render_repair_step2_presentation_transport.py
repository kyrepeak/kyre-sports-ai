import ast
from pathlib import Path


def _src(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _has_call(source: str, owner: str, method: str, first_arg: str) -> bool:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        target = node.func.value
        if not isinstance(target, ast.Name) or target.id != owner or node.func.attr != method:
            continue
        if not node.args or not isinstance(node.args[0], ast.Name):
            continue
        if node.args[0].id == first_arg:
            return True
    return False


RUSH = _src("nfl_rushing_yards_hub_v4.py")
RECV = _src("nfl_receiving_yards_hub_v13.py")
HARDENED = _src("nfl_prop_analytics_page2_responsive_polish_v1.py")


def test_rushing_cards_use_hardened_html_transport() -> None:
    assert _has_call(RUSH, "st", "html", "_COMPACT_CSS")
    assert not _has_call(RUSH, "st", "markdown", "_COMPACT_CSS")
    assert _has_call(RUSH, "compact_slot", "html", "board")
    assert not _has_call(RUSH, "compact_slot", "markdown", "board")


def test_receiving_step13_css_uses_hardened_html_transport() -> None:
    assert _has_call(RECV, "st", "html", "_STEP13_CSS")
    assert not _has_call(RECV, "st", "markdown", "_STEP13_CSS")


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
