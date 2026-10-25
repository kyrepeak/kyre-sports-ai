from nba_pra_page2_v1 import build_page2_html


def test_insights_must_render_between_verdict_and_fast_line_lab():
    html = build_page2_html(
        {"player": {}, "player_name": "Test Player", "team": "MEM", "opponent": "SAC", "quotes": []},
        {"projection": 20.5, "current": {"sample": 0}},
        {"lean": "OVER", "edge": 5.0, "over_probability": 0.89, "score": 10.0, "tier": "ELITE"},
        {},
        active_line=15.5,
    )
    assert "KYRE AI VERDICT" in html
    assert "INSIGHTS" in html
    assert "FAST LINE LAB" in html
    assert html.index("KYRE AI VERDICT") < html.index("INSIGHTS") < html.index("FAST LINE LAB")
