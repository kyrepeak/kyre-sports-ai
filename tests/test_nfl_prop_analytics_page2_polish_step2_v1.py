from nfl_prop_analytics_page2_unified_roster_v1 import _player_card

def test_unified_player_card_has_single_identity_plus_truth():
    row={
        "espn_id":"4361259","name":"Bryce Young","team":"CAR","position":"QB",
        "jersey_number":"9","verified":True,"source_count":2,
        "depth_verified":True,"depth_rank":1,"depth_role":"QB1 • STARTER",
        "availability_state":"PENDING","availability_label":"GAME-DAY PENDING",
    }
    html=_player_card(row)
    assert html.count('data-prop-page2-unified-player-id="4361259"')==1
    assert 'data-prop-page2-unified-roster-verified="true"' in html
    assert 'data-prop-page2-unified-source-count="2"' in html
    assert 'data-prop-page2-unified-depth-verified="true"' in html
    assert 'data-prop-page2-unified-depth-rank="1"' in html
    assert 'data-prop-page2-unified-availability="PENDING"' in html
    assert "Bryce Young" in html
    assert "QB1 • STARTER" in html
    assert "GAME-DAY PENDING" in html
    assert "VERIFIED • ESPN + NFLVERSE" in html
