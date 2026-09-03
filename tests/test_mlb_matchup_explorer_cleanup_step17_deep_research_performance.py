from pathlib import Path

import mlb_matchup_hub_v57 as step17


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_router_points_to_step17_performance_layer():
    source = _text("mlb_matchup_hub_v27.py")
    assert "from mlb_matchup_hub_v57 import" in source
    assert "mlb_matchup_hub_v56" not in source


def test_step17_builds_only_on_frozen_step16_presentation():
    source = _text("mlb_matchup_hub_v57.py")
    assert "import mlb_matchup_hub_v56 as current" in source
    assert 'FROZEN_STEP16_PRESENTATION = "mlb_matchup_hub_v56"' in source
    assert "return current.render_matchup_hub" in source


def test_all_ten_certified_profile_builders_are_memoized():
    expected = {
        ("_build_foundation", "step1"),
        ("_build_profile", "step2"),
        ("_build_step3", "step3"),
        ("_build_step4", "step4"),
        ("_build_step5", "step5"),
        ("_build_step6", "step6"),
        ("_build_step7", "step7"),
        ("_build_step8", "step8"),
        ("_build_step9", "step9"),
        ("_build_step10", "step10"),
    }
    actual = {(attr, name) for _, attr, name in step17._BUILDER_SPECS}
    assert actual == expected


def test_builder_reuses_same_profile_inside_one_render(monkeypatch):
    calls = {"n": 0}

    def original(_games_df):
        calls["n"] += 1
        return {"value": 42}

    monkeypatch.setattr(step17, "_cache_get", lambda *args, **kwargs: None)
    monkeypatch.setattr(step17, "_cache_put", lambda *args, **kwargs: None)
    render_cache = {}
    perf = {}
    identity = lambda _gdf: {"fingerprint": (123, 456)}
    wrapped = step17._memoized_builder("step5", original, render_cache, perf, identity)

    assert wrapped(object()) == {"value": 42}
    assert wrapped(object()) == {"value": 42}
    assert calls["n"] == 1
    assert perf["step5"]["calls"] == 2
    assert perf["step5"]["render_hits"] == 1


def test_builder_can_reuse_short_lived_session_profile(monkeypatch):
    calls = {"n": 0}

    def original(_games_df):
        calls["n"] += 1
        return {"value": "computed"}

    monkeypatch.setattr(step17, "_cache_get", lambda *args, **kwargs: {"value": "cached"})
    monkeypatch.setattr(step17, "_cache_put", lambda *args, **kwargs: None)
    perf = {}
    wrapped = step17._memoized_builder(
        "step2",
        original,
        {},
        perf,
        lambda _gdf: {"fingerprint": (7, 8)},
    )

    assert wrapped(object()) == {"value": "cached"}
    assert calls["n"] == 0
    assert perf["step2"]["session_hits"] == 1


def test_result_cache_is_short_lived_and_identity_keyed():
    source = _text("mlb_matchup_hub_v57.py")
    assert "PROFILE_CACHE_TTL_SECONDS = 300" in source
    assert "RESULT_CACHE_TTL_SECONDS = 300" in source
    for token in (
        'row.get("game_pk")',
        'st.session_state.get("mx56_active_player_id")',
        'row.get("away_pitcher_id")',
        'row.get("home_pitcher_id")',
        'player.get("source")',
        'player.get("slot")',
        'player.get("opponent_pitcher_id")',
    ):
        assert token in source


def test_step11_cache_never_changes_explicit_simulation_override():
    source = _text("mlb_matchup_hub_v57.py")
    assert "if simulations is not None:" in source
    assert "original(games_df, simulations=simulations)" in source
    assert "final_layer._build_step11_fallback = _cached_step11" in source


def test_step12_cache_requires_same_raw_signature_and_identity():
    source = _text("mlb_matchup_hub_v57.py")
    assert "tuple(entry.get(\"raw_signature\") or ()) == signature" in source
    assert "and _profile_matches(raw, context)" in source
    assert "calibration.build_final_intelligence = _cached_final" in source


def test_legacy_and_rankings_are_true_load_on_demand():
    source = _text("mlb_matchup_hub_v57.py")
    assert 'st.button("Load Legacy V1 audit"' in source
    assert 'perf["legacy_v1"] = "deferred"' in source
    assert 'st.button("Load Daily Top 5 rankings"' in source
    assert 'perf["rankings"] = "deferred"' in source
    assert "legacy_v1.render_player_layer = _lazy_legacy" in source
    assert "rankings.render_daily_rankings = _lazy_rankings" in source


def test_performance_timings_are_recorded_without_new_model_math():
    source = _text("mlb_matchup_hub_v57.py")
    assert "time.perf_counter()" in source
    assert 'st.session_state[_PERF_KEY] = perf' in source
    for forbidden in (
        "MONTE_CARLO_SIMS =",
        "MONTE_CARLO_BATCH =",
        "np.random",
        "default_rng(",
        "monte_carlo_distribution(",
        "build_probability_profile(",
        "render_daily_rankings(games_df)",
    ):
        assert forbidden not in source


def test_every_runtime_patch_is_restored_in_finally():
    source = _text("mlb_matchup_hub_v57.py")
    assert "finally:" in source
    assert "rankings.render_daily_rankings = original_rankings" in source
    assert "legacy_v1.render_player_layer = original_legacy" in source
    assert "calibration.build_final_intelligence = original_final" in source
    assert "final_layer._build_step11_fallback = original_step11" in source
    assert "for module, attr, original in reversed(originals):" in source
    assert "setattr(module, attr, original)" in source


def test_historical_step16_workflow_is_scoped_to_original_branch():
    source = _text(".github/workflows/mlb-matchup-explorer-cleanup-step16-tight-cards-identity.yml")
    assert "Historical exact-scope certification belongs only to Cleanup Step 16." in source
    assert "github.head_ref == 'mlb-matchup-explorer-cleanup-step16-tight-cards-identity'" in source
