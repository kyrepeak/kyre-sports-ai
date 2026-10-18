from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V89 = ROOT / "nfl_passing_yards_hub_v89.py"
LOADER = ROOT / "universal_runtime_v5_loader_v11.py"
RUNTIME = ROOT / "streamlit_memory_lazy_router_universal_runtime_v5.py"


def _text(path: Path) -> str:
    assert path.exists(), f"missing implementation: {path.name}"
    return path.read_text(encoding="utf-8")


def _captured():
    return {
        "identity": ["QB1-ID", "QB2-ID"],
        "profile": ["QB1-PROFILE", "QB2-PROFILE"],
        "defense": ["QB1-DEFENSE", "QB2-DEFENSE"],
        "pressure": ["QB1-PRESSURE", "QB2-PRESSURE"],
        "personnel": ["QB1-WEAPONS", "QB2-WEAPONS"],
        "environment": ["GAME-ENV"],
        "projection": ["QB1-PROJECTION", "QB2-PROJECTION"],
        "context": ["QB1-CONTEXT", "QB2-CONTEXT"],
        "distribution": ["QB1-DISTRIBUTION", "QB2-DISTRIBUTION"],
        "market": ["QB1-MARKET", "QB2-MARKET"],
    }


def test_v89_is_strictly_presentation_only():
    src = _text(V89)
    for token in (
        "PRESENTATION_ONLY = True", "DISPLAY_ONLY = True",
        "MAY_MODIFY_PROJECTION = False", "MAY_MODIFY_PROBABILITY = False",
        "MAY_MODIFY_MARKET_MATH = False", "MAY_MODIFY_DATA_PROVIDER_BEHAVIOR = False",
        "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0", "STAKE_SIZING_ENABLED = False",
    ):
        assert token in src
    assert 'CERTIFIED_CAPTURE_OWNER = "nfl_passing_yards_hub_v43"' in src


def test_dashboard_has_synchronized_two_qb_rows_and_top_overview():
    import importlib.util
    spec = importlib.util.spec_from_file_location("py_v89_contract", V89)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    html = mod._comparison_dashboard_html(_captured())
    assert 'data-passing-yards-comparison="v89"' in html
    assert 'grid-template-columns:repeat(2,minmax(0,1fr))' in html
    assert 'Final Projection + Market' in html
    for section in ("py-profile","py-defense","py-pressure","py-weapons","py-projection","py-probability","py-market"):
        assert f'id="{section}"' in html
    for marker in ("QB1-ID","QB2-ID","QB1-PROJECTION","QB2-PROJECTION","QB1-MARKET","QB2-MARKET"):
        assert html.count(marker) >= 1


def test_game_environment_is_shared_once_not_duplicated_per_qb():
    import importlib.util
    spec = importlib.util.spec_from_file_location("py_v89_env", V89)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    html = mod._comparison_dashboard_html(_captured())
    assert html.count("GAME-ENV") == 1
    assert 'id="py-environment"' in html


def test_navigation_is_sticky_and_mobile_collapses_cleanly():
    src = _text(V89)
    assert "position:sticky" in src
    assert "@media(max-width:760px)" in src
    assert "grid-template-columns:1fr" in src
    for label in ("Overview","Profile","Defense","Pressure","Weapons","Environment","Projection","Probability","Market"):
        assert f">{label}<" in src


def test_v89_uses_certified_capture_seam_and_suppresses_legacy_visible_stack():
    src = _text(V89)
    assert "composition._combined_player_cards_html = _comparison_dashboard_html" in src
    assert "st.markdown = capture_only_markdown" in src
    assert "legacy_visual._matchup_html" in src
    assert "legacy_visual._why_html" in src
    assert "prior.render_nfl_passing_yards_hub()" in src


def test_current_v11_loader_routes_nfl_passing_yards_to_v89():
    src = _text(LOADER)
    assert 'route.sport_id == "nfl" and route.market_id == "passing-yards"' in src
    assert '"nfl_passing_yards_hub_v89"' in src
    assert "return prior.resolve_destination(route)" in src


def test_universal_runtime_keeps_current_v11_loader_owner():
    src = _text(RUNTIME)
    assert "from universal_runtime_v5_loader_v11 import choose_prefetch, load_destination, resolve_destination" in src
    assert "from universal_runtime_v5_loader_v12 import choose_prefetch, load_destination, resolve_destination" not in src
