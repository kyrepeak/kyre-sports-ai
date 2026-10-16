import cfb_game_total_page2_stage6_tough_favorable_v1 as stage6


def _battle(team, tone, title, note, verified=6):
    return {"offense_team": team, "read_tone": tone, "read_title": title, "read_note": note, "verified_tiles": verified}


def test_step7_uses_verified_tough_and_favorable_reads_only():
    contract = {
        "away_offense_vs_home_defense": _battle("Away", "tough", "Tough offensive matchup", "Defense owns multiple verified edges"),
        "home_offense_vs_away_defense": _battle("Home", "fav", "Favorable offensive matchup", "Offense owns multiple verified edges"),
    }
    row = stage6.build_tough_favorable_contract(contract)
    assert row["tough_team"] == "Away"
    assert row["favorable_team"] == "Home"
    assert row["sportsbook_projection_influence"] == 0.0
    html = stage6.build_tough_favorable_html(contract)
    assert "Tough Matchup + Favorable Team" in html
    assert "Away" in html and "Home" in html


def test_step7_fails_soft_when_verified_matchup_is_not_established():
    contract = {
        "away_offense_vs_home_defense": _battle("Away", "mixed", "Balanced matchup", "Mixed", verified=2),
        "home_offense_vs_away_defense": _battle("Home", "mixed", "Balanced matchup", "Mixed", verified=2),
    }
    row = stage6.build_tough_favorable_contract(contract)
    assert row["ready"] is False
    assert row["tough_team"] is None
    assert row["favorable_team"] is None
    assert "no side is invented" in stage6.build_tough_favorable_html(contract)


def test_step7_has_no_model_or_network_authority():
    assert stage6.MAY_MODIFY_MODEL is False
    assert stage6.MAY_MODIFY_PROJECTION is False
    assert stage6.MAY_MODIFY_PROBABILITY is False
    assert stage6.NETWORK_CALLS_ADDED == 0
    assert stage6.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
