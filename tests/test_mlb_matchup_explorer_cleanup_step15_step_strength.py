from pathlib import Path

import mlb_matchup_hub_v55 as step15


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _card(step: int, body: str) -> str:
    return (
        f'<div class="mxv2-step mxv2-step{step}">'
        '<div class="mxv2-top"><div class="mxv2-kicker">STEP</div>'
        '<div class="mxv2-badge">DATA • 90/100</div></div>'
        f'{body}</div>'
    )


def test_router_points_to_step15_strength_presentation():
    source = _text("mlb_matchup_hub_v27.py")
    assert "from mlb_matchup_hub_v55 import" in source
    assert "mlb_matchup_hub_v54" not in source


def test_step15_builds_on_frozen_step14_and_step13_only():
    source = _text("mlb_matchup_hub_v55.py")
    assert "import mlb_matchup_hub_v54 as current" in source
    assert "import mlb_matchup_hub_v53 as scouting" in source
    assert 'FROZEN_STEP14_PRESENTATION = "mlb_matchup_hub_v54"' in source
    assert 'FROZEN_STEP13_PRESENTATION = "mlb_matchup_hub_v53"' in source
    assert "return current.render_matchup_hub" in source


def test_every_certified_step_has_a_strength_rule():
    samples = {
        1: _card(1, '<div class="mxv2-status">CONFIRMED • READY</div>'),
        2: _card(2, '<span>Neutral skill</span><b>0.285</b>'),
        3: _card(3, '<div><b>Starter quality index</b> • STRONG • 78/100 • descriptive</div>'),
        4: _card(4, '<div><b>Platoon/BvP context index</b> • FAVORABLE • 72/100 • descriptive</div>'),
        5: _card(5, '<div><b>Pitch-mix verdict</b> • FAVORABLE • 69/100 • descriptive</div>'),
        6: _card(6, '<div><b>Batted-ball verdict</b> • STRONG • 76/100 • descriptive</div>'),
        7: _card(7, '<div><b>Environment verdict</b> • HITTER FRIENDLY • 67/100 • descriptive</div>'),
        8: _card(8, '<div><b>Relief-path verdict</b> • TOUGH • 74/100 • descriptive</div>'),
        9: _card(9, '<span>Expected PA</span><b>4.62</b>'),
        10: _card(10, '<div><b>Recent-form verdict</b> • HOT • 81/100 • descriptive</div>'),
        11: _card(11, '<span>RAW P(1+ HIT)</span><b>69.4%</b>'),
        12: _card(12, '<span>FINAL P(1+ HIT)</span><b>71.2%</b>'),
    }
    for number, html in samples.items():
        edge = step15._strength_for_step(html)
        assert edge["label"] != "EDGE PENDING", f"Step {number} did not resolve"
        assert edge["kind"] in {"batter", "pitcher", "neutral"}


def test_starter_and_bullpen_strength_are_inverted_toward_pitcher():
    starter = _card(3, '<div><b>Starter quality index</b> • ELITE • 82/100 • descriptive</div>')
    bullpen = _card(8, '<div><b>Relief-path verdict</b> • STRONG • 78/100 • descriptive</div>')
    assert step15._strength_for_step(starter)["label"] == "ELITE PITCHER EDGE"
    assert step15._strength_for_step(bullpen)["label"] == "ELITE PITCHER EDGE"


def test_batter_facing_context_indices_keep_high_score_as_batter_edge():
    for step, label in (
        (4, "Platoon/BvP context index"),
        (5, "Pitch-mix verdict"),
        (6, "Batted-ball verdict"),
        (7, "Environment verdict"),
        (10, "Recent-form verdict"),
    ):
        html = _card(step, f'<div><b>{label}</b> • STRONG • 80/100 • descriptive</div>')
        assert step15._strength_for_step(html)["label"] == "ELITE BATTER EDGE"


def test_foundation_is_neutral_because_step1_is_gating_not_directional():
    ready = _card(1, '<div class="mxv2-status">CONFIRMED • READY</div>')
    partial = _card(1, '<div class="mxv2-status">PROJECTED • PARTIAL</div>')
    assert step15._strength_for_step(ready) == {"label": "NEUTRAL • VERIFIED", "kind": "neutral"}
    assert step15._strength_for_step(partial) == {"label": "NEUTRAL • PARTIAL", "kind": "neutral"}


def test_step_strength_badge_is_added_beside_existing_badge():
    source = _card(4, '<div><b>Platoon/BvP context index</b> • FAVORABLE • 70/100 • descriptive</div>')
    decorated = step15._decorate_step(source)
    assert decorated.count("mxv2-badge") == 1
    assert decorated.count("mx55-edge") == 1
    assert "STRONG BATTER EDGE" in decorated
    assert "DATA • 90/100" in decorated


def test_strength_legend_matches_requested_batter_pitcher_neutral_language():
    source = _text("mlb_matchup_hub_v55.py")
    assert "GREEN = BATTER EDGE" in source
    assert "RED = PITCHER EDGE" in source
    assert "GOLD = NEUTRAL" in source
    assert "ELITE BATTER EDGE" in source
    assert "STRONG PITCHER EDGE" in source


def test_step15_restores_scouting_renderer_after_temporary_decoration():
    source = _text("mlb_matchup_hub_v55.py")
    assert "original_scouting = scouting._scouting_html" in source
    assert "scouting._scouting_html = _strength_scouting_wrapper(original_scouting)" in source
    assert "finally:" in source
    assert "scouting._scouting_html = original_scouting" in source


def test_step15_is_presentation_only_and_does_not_reimplement_model_math():
    source = _text("mlb_matchup_hub_v55.py")
    for forbidden in (
        "build_probability_profile(",
        "build_final_intelligence(",
        "monte_carlo_distribution(",
        "5_000_000",
        "np.random",
        "default_rng",
        "render_daily_rankings(",
        "mlb_moneyline_hub",
    ):
        assert forbidden not in source


def test_historical_step14_workflow_is_scoped_to_original_branch():
    source = _text(".github/workflows/mlb-matchup-explorer-cleanup-step14-selection-lock.yml")
    assert "Historical exact-scope certification belongs only to Cleanup Step 14." in source
    assert "github.head_ref == 'mlb-matchup-explorer-cleanup-step14-selection-lock'" in source
