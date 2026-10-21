from __future__ import annotations


def test_line_steps_are_half_point_and_centered():
    from nba_pra_page2_line_lab_v1 import line_steps
    values = line_steps(32.5, width=2.0)
    assert values == (30.5,31.0,31.5,32.0,32.5,33.0,33.5,34.0,34.5)
    assert all(round((b-a)*2) == 1 for a,b in zip(values,values[1:]))


def test_probability_is_monotonic_and_complementary_as_line_moves():
    from nba_pra_page2_line_lab_v1 import evaluate_line
    low = evaluate_line(32.0, 5.0, 28.5)
    mid = evaluate_line(32.0, 5.0, 32.5)
    high = evaluate_line(32.0, 5.0, 36.5)
    assert low['over_probability'] > mid['over_probability'] > high['over_probability']
    for result in (low,mid,high):
        assert abs(result['over_probability'] + result['under_probability'] - 1.0) < 1e-9


def test_line_lab_changes_threshold_not_projection_and_can_flip_lean():
    from nba_pra_page2_line_lab_v1 import evaluate_line, SPORTSBOOK_PROJECTION_INFLUENCE
    low = evaluate_line(32.0, 4.0, 25.5)
    high = evaluate_line(32.0, 4.0, 38.5)
    assert low['projection'] == high['projection'] == 32.0
    assert low['edge'] > 0 and low['lean'] == 'OVER'
    assert high['edge'] < 0 and high['lean'] == 'UNDER'
    assert SPORTSBOOK_PROJECTION_INFLUENCE == 0.0


def test_no_sigma_keeps_probability_score_and_decision_unavailable():
    from nba_pra_page2_line_lab_v1 import evaluate_line
    result = evaluate_line(32.0, None, 30.5)
    assert result['edge'] == 1.5
    assert result['over_probability'] is None
    assert result['under_probability'] is None
    assert result['lean'] == 'PASS'
    assert result['score'] is None
    assert result['tier'] == 'UNAVAILABLE'
