"""Regression guard for V157 Hit-style evidence cards.

This suite is intentionally presentation-only. It verifies that every visible
Step 1–12 card can be populated from existing display/model evidence while the
frozen Game Total math boundary stays unchanged.
"""

import cfb_game_total_clean_page_v9 as page


def _sample_bundle():
    identity = {
        "away": {"team": "Syracuse", "logo": "away.png"},
        "home": {"team": "Pittsburgh", "logo": "home.png"},
    }
    away = {
        "team": "Syracuse",
        "record": "2-0",
        "ppg": 31.5,
        "allowed_pg": 20.0,
        "point_diff_pg": 11.5,
        "official_stats": {
            "plays_per_game": {"label": "Plays per game", "value": "72.1"},
            "yards_per_play": {"label": "Yards per play", "value": "6.8"},
            "red_zone": {"label": "Red Zone TD %", "value": "71%"},
            "third_down": {"label": "3rd Down %", "value": "48%"},
            "turnovers": {"label": "Turnovers", "value": "2"},
        },
    }
    home = {
        "team": "Pittsburgh",
        "record": "1-1",
        "ppg": 27.0,
        "allowed_pg": 24.5,
        "point_diff_pg": 2.5,
        "official_stats": {
            "plays_per_game": {"label": "Plays per game", "value": "68.4"},
            "yards_per_play": {"label": "Yards per play", "value": "5.9"},
            "red_zone": {"label": "Red Zone TD %", "value": "64%"},
            "third_down": {"label": "3rd Down %", "value": "42%"},
            "turnovers": {"label": "Turnovers", "value": "4"},
        },
    }
    game = {
        "weather": "78°F • clear",
        "wind_mph": 7,
        "series_history": "Pittsburgh leads 45-33-3 • 82nd meeting",
    }
    raw = {
        "ready": True,
        "projected_combined_total": 55.2,
        "sigma": 10.4,
    }
    final = {
        "ready": True,
        "projected_combined_total": 54.7,
        "core_50_range": {"low": 48, "high": 61},
        "most_likely_band": {"label": "50-59"},
        "grade": "A",
        "forecast_strength": 0.78,
    }
    statuses = {step: "READY" for step in range(1, 11)}
    return identity, away, home, game, raw, final, statuses


def test_v157_builds_real_evidence_for_every_step_without_touching_math():
    identity, away, home, game, raw, final, statuses = _sample_bundle()

    cards = page._build_step_evidence_v157(
        identity,
        away,
        home,
        game,
        raw,
        final,
        statuses,
    )

    assert set(cards) == set(range(1, 13))
    assert all(cards[step]["facts"] for step in range(1, 13))
    assert all(
        fact["tone"] in {"SUPPORT", "CONCERN", "NEUTRAL"}
        for step in cards
        for fact in cards[step]["facts"]
    )

    assert any("72.1" in fact["value"] for fact in cards[4]["facts"])
    assert any("Yards per play" in fact["label"] for fact in cards[5]["facts"])
    assert any("78°F" in fact["value"] for fact in cards[9]["facts"])
    assert any("45-33-3" in fact["value"] for fact in cards[10]["facts"])
    assert any("55.2" in fact["value"] for fact in cards[11]["facts"])
    assert any("54.7" in fact["value"] for fact in cards[12]["facts"])

    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.MAY_MODIFY_PROJECTION is False
    assert page.FROZEN_PRESENTATION == "cfb_game_total_clean_page_v8"


def test_v157_missing_verified_rows_become_concerns_not_fake_data():
    identity, away, home, game, raw, final, statuses = _sample_bundle()
    away["official_stats"] = {}
    home["official_stats"] = {}
    statuses.update({4: "CHECK", 5: "CHECK", 6: "CHECK", 7: "CHECK", 8: "CHECK"})

    cards = page._build_step_evidence_v157(
        identity,
        away,
        home,
        game,
        raw,
        final,
        statuses,
    )

    for step in (4, 5, 6, 7, 8):
        assert any(fact["tone"] == "CONCERN" for fact in cards[step]["facts"])
        assert any("verified" in fact["value"].lower() for fact in cards[step]["facts"])
