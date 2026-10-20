import math

import cfb_player_props_model_v1 as frozen


def test_market_bounds_are_exact_half_point_contract():
    import cfb_player_props_page3_line_lab_v1 as lab
    assert lab.LINE_BOUNDS == {
        'passing_yards': (0.5, 500.5, 0.5),
        'rushing_yards': (0.5, 250.5, 0.5),
        'receiving_yards': (0.5, 250.5, 0.5),
        'receiving_receptions': (0.5, 20.5, 0.5),
        'passing_touchdowns': (0.5, 6.5, 0.5),
        'touchdowns': (0.5, 4.5, 0.5),
    }


def test_normalize_line_clamps_and_rounds_to_half_point():
    import cfb_player_props_page3_line_lab_v1 as lab
    assert lab.normalize_line('passing_yards', 202.26) == 202.5
    assert lab.normalize_line('passing_yards', -10) == 0.5
    assert lab.normalize_line('passing_yards', 999) == 500.5
    assert lab.normalize_line('passing_touchdowns', 1.24) == 1.0
    assert lab.normalize_line('made_up', 10) is None


def test_evaluate_custom_line_matches_frozen_normal_distribution_semantics():
    import cfb_player_props_page3_line_lab_v1 as lab
    projection={'model_ready':True,'projection':210.0,'uncertainty':20.0,'sample_count':8}
    out=lab.evaluate_line(projection, 202.5, 'passing_yards')
    consensus={'line':202.5,'market_probability':{'over':None,'under':None}}
    grade=frozen.grade_market_line(projection, consensus)
    assert out['model_ready'] is True
    assert math.isclose(out['model_probability'], grade['model_probability'], rel_tol=1e-12)
    assert out['side'] == grade['side']
    assert math.isclose(out['over_probability'] + out['under_probability'], 1.0, rel_tol=1e-12)
    assert out['margin'] == 7.5
    assert out['sportsbook_projection_influence'] == 0.0


def test_model_not_ready_or_zero_uncertainty_never_emits_probability():
    import cfb_player_props_page3_line_lab_v1 as lab
    for projection in (
        {'model_ready':False,'projection':210.0,'uncertainty':20.0,'sample_count':3},
        {'model_ready':True,'projection':210.0,'uncertainty':0.0,'sample_count':8},
        {'model_ready':True,'projection':None,'uncertainty':20.0,'sample_count':8},
    ):
        out=lab.evaluate_line(projection, 202.5, 'passing_yards')
        assert out['model_ready'] is False
        assert out['over_probability'] is None
        assert out['under_probability'] is None
        assert out['model_probability'] is None


def test_probability_curve_is_bounded_and_over_probability_decreases_with_line():
    import cfb_player_props_page3_line_lab_v1 as lab
    projection={'model_ready':True,'projection':210.0,'uncertainty':25.0,'sample_count':8}
    curve=lab.build_probability_curve(projection, 210.5, 'passing_yards', points=21)
    assert len(curve) == 21
    assert all(0.5 <= row['line'] <= 500.5 for row in curve)
    assert all(curve[i]['line'] < curve[i+1]['line'] for i in range(len(curve)-1))
    assert all(curve[i]['over_probability'] >= curve[i+1]['over_probability'] for i in range(len(curve)-1))


def test_default_line_prefers_consensus_then_handoff_then_midpoint():
    import cfb_player_props_page3_line_lab_v1 as lab
    assert lab.default_line('passing_yards', consensus_line=202.5, handoff_line=199.5) == 202.5
    assert lab.default_line('passing_yards', consensus_line=None, handoff_line=199.5) == 199.5
    assert lab.default_line('passing_touchdowns', consensus_line=None, handoff_line=None) == 3.5
