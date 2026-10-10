from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUBJECT = ROOT / "cfb_game_total_games_on_day_step2_visual_v1.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py"


def _load_subject():
    import importlib.util

    spec = importlib.util.spec_from_file_location("games_on_day_step2", SUBJECT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_step2_additive_visual_owner_exists_and_is_presentation_only() -> None:
    assert SUBJECT.exists(), "Step-2 game-card visual owner is not implemented yet"
    text = SUBJECT.read_text(encoding="utf-8")
    assert 'MODEL_VERSION = "CFB GAME TOTAL • GAMES ON THIS DAY • STEP 2 VISUAL V1"' in text
    assert "MAY_MODIFY_PROJECTION = False" in text
    assert "MAY_MODIFY_PROBABILITY = False" in text
    assert "MAY_MODIFY_MODEL = False" in text
    assert "MAY_MODIFY_OTHER_SPORTS = False" in text
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in text
    assert 'PHOENIX_TZ = ZoneInfo("America/Phoenix")' in text


def test_step2_card_html_has_exact_team_logos_phoenix_time_and_selected_state() -> None:
    assert SUBJECT.exists(), "Step-2 game-card visual owner is not implemented yet"
    module = _load_subject()

    game = {
        "espn_event_id": "401760001",
        "away_team": "Oklahoma",
        "home_team": "Texas",
        "away_espn_team_id": "201",
        "home_espn_team_id": "251",
        "kickoff_iso": "2026-10-10T23:00:00Z",
        "away_color": "#841617",
        "home_color": "#BF5700",
    }
    html = module.build_game_card_html(
        game,
        selected_day="2026-10-10",
        selected=True,
        href="?ks_cfb_game_total_event_id=401760001",
    )
    assert "401760001" in html
    assert "https://a.espncdn.com/i/teamlogos/ncaa/500/201.png" in html
    assert "https://a.espncdn.com/i/teamlogos/ncaa/500/251.png" in html
    assert "Oklahoma" in html and "Texas" in html
    assert "4:00 PM MST" in html
    assert "SELECTED" in html
    assert 'aria-current="true"' in html
    assert "#841617" in html and "#BF5700" in html


def test_step2_css_makes_cards_more_visual_without_reopening_step1_layout() -> None:
    assert SUBJECT.exists(), "Step-2 game-card visual owner is not implemented yet"
    text = SUBJECT.read_text(encoding="utf-8")
    assert ".gt2-team-logo" in text
    assert ".gt2-team-row" in text
    assert ".gt2-kickoff" in text
    assert ".gt2-selected-pill" in text
    assert ".gt2-game-card.selected" in text
    assert "grid-template-columns:1fr" not in text, "Step 2 must not reopen Step-1 layout ownership"


def test_step2_rebinds_visual_renderer_after_exact_route_purge() -> None:
    assert SUBJECT.exists(), "Step-2 game-card visual owner is not implemented yet"
    text = SUBJECT.read_text(encoding="utf-8")
    assert 'TARGET_PAGE = "cfb_game_total_clean_page_v38"' in text
    assert 'importlib.import_module("streamlit_memory_lazy_router_v1")' in text
    assert 'importlib.import_module("streamlit_memory_lazy_router_v160")' in text
    assert 'importlib.import_module("streamlit_memory_lazy_router_v181")' in text
    assert 'fresh_owner = importlib.import_module("cfb_game_total_clean_page_v14")' in text
    assert "fresh_owner._render_game_strip = enhanced_render_game_strip" in text
    assert "fresh_owner._render_game_strip = original_strip" in text


def test_step2_installer_does_not_stack_when_step1_wraps_step2() -> None:
    module = _load_subject()
    assert hasattr(module, "_render_chain_has_step2"), "Step-2 installer has no chain-aware idempotence guard"

    def base():
        return None

    def step2_wrapper():
        return None

    setattr(step2_wrapper, "_cfb_games_on_day_step2_original", base)

    def step1_wrapper():
        return None

    setattr(step1_wrapper, "_cfb_games_on_day_step1_original", step2_wrapper)
    assert module._render_chain_has_step2(step1_wrapper) is True
    assert module._render_chain_has_step2(base) is False


def test_step2_active_router_installs_visual_upgrade_only_for_page1_path() -> None:
    router = ROUTER.read_text(encoding="utf-8")
    assert "cfb_game_total_games_on_day_step2_visual_v1" in router
    assert "install_games_on_day_step2_visual" in router
    assert "if not _selected_game_total():" in router
