"""Regression checks for College Football Step 1 hub foundation."""

import cfb_hub_v1 as cfb


def test_step1_exposes_exact_three_cfb_pages():
    assert cfb.CFB_MARKETS == ["Moneyline", "Over/Under", "Game Total"]


def test_step1_is_navigation_foundation_only():
    source = open("cfb_hub_v1.py", encoding="utf-8").read()
    assert "Step 1 contract" in source
    assert "projection/model math" in source
    assert "probabilities, picks, totals, sportsbook prices, or simulations" in source
    forbidden = (
        "numpy",
        "np.random",
        "monte_carlo",
        "fair_odds",
        "sportsbook_price",
        "win_probability",
        "projected_total =",
    )
    for token in forbidden:
        assert token not in source


def test_each_page_has_distinct_purpose():
    moneyline = cfb._page_card("Moneyline")
    over_under = cfb._page_card("Over/Under")
    game_total = cfb._page_card("Game Total")

    assert "Winner probability" in moneyline
    assert "Sportsbook total-line analysis" in over_under
    assert "Independent projected combined score" in game_total
