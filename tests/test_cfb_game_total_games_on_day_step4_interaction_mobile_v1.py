from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUBJECT = ROOT / "cfb_game_total_games_on_day_step4_interaction_mobile_v1.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py"


def _load_subject():
    import importlib.util
    spec = importlib.util.spec_from_file_location("games_on_day_step4", SUBJECT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_step4_owner_exists_and_is_interaction_only() -> None:
    assert SUBJECT.exists(), "Step-4 interaction owner is not implemented yet"
    text = SUBJECT.read_text(encoding="utf-8")
    assert 'MODEL_VERSION = "CFB GAME TOTAL • GAMES ON THIS DAY • STEP 4 INTERACTION MOBILE V1"' in text
    assert "MAY_MODIFY_MODEL = False" in text
    assert "MAY_MODIFY_PROJECTION = False" in text
    assert "MAY_MODIFY_PROBABILITY = False" in text
    assert "MAY_MODIFY_OTHER_SPORTS = False" in text
    assert "DIRECT_NETWORK_ENDPOINTS_ADDED = 0" in text


def test_step4_preserves_href_selected_state_and_adds_accessible_details() -> None:
    module = _load_subject()
    base = (
        '<a class="gt163-game-link gt2-game-card selected" data-event-id="401760001" '
        'href="?ks_cfb_game_total_date=2026-10-10&amp;ks_cfb_game_total_event_id=401760001" '
        'target="_self" aria-label="4:00 PM MST: Oklahoma at Texas" aria-current="true">'
        '<span class="gt3-status-chip gt3-status-upcoming">UPCOMING</span>'
        '<span class="gt3-rank">#6</span><span class="gt3-conference">SEC</span>'
        '<span class="gt3-rank">#9</span><span class="gt3-conference">SEC</span></a>'
    )
    game = {
        "status": "scheduled",
        "away_team": "Oklahoma",
        "home_team": "Texas",
        "away_rank": 6,
        "home_rank": 9,
        "away_conference": "SEC",
        "home_conference": "SEC",
    }
    html = module.augment_interaction_html(base, game)
    assert 'href="?ks_cfb_game_total_date=2026-10-10&amp;ks_cfb_game_total_event_id=401760001"' in html
    assert 'aria-current="true"' in html
    assert 'data-event-id="401760001"' in html
    assert 'data-step4-interaction="v1"' in html
    assert 'UPCOMING' in html
    assert '#6 Oklahoma SEC' in html
    assert '#9 Texas SEC' in html


def test_step4_mobile_contract_has_touch_focus_and_no_horizontal_scroll_owner() -> None:
    assert SUBJECT.exists(), "Step-4 interaction owner is not implemented yet"
    text = SUBJECT.read_text(encoding="utf-8")
    assert ".gt2-game-card{touch-action:manipulation" in text
    assert ".gt2-game-card:focus-visible" in text
    assert "min-height:44px" in text
    assert "max-width:100%" in text
    assert "overflow-x:clip" in text
    assert "@media(max-width:760px)" in text
    assert "grid-template-columns" not in text, "Step 4 must not reopen Step-1 layout ownership"


def test_step4_installer_wraps_after_step3_and_is_idempotent() -> None:
    assert SUBJECT.exists(), "Step-4 interaction owner is not implemented yet"
    text = SUBJECT.read_text(encoding="utf-8")
    assert 'importlib.import_module("cfb_game_total_games_on_day_step3_details_v1")' in text
    assert 'importlib.import_module("cfb_game_total_games_on_day_step2_visual_v1")' in text
    assert "install_games_on_day_step3_details()" in text
    assert "if getattr(current, _INSTALL_ATTR, False):" in text


def test_step4_active_router_installs_only_on_page1() -> None:
    router = ROUTER.read_text(encoding="utf-8")
    assert "cfb_game_total_games_on_day_step4_interaction_mobile_v1" in router
    assert "install_games_on_day_step4_interaction_mobile" in router
    assert "if not _selected_game_total():" in router
