from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUBJECT = ROOT / "cfb_game_total_games_on_day_step3_details_v1.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py"


def _load_subject():
    import importlib.util

    spec = importlib.util.spec_from_file_location("games_on_day_step3", SUBJECT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_step3_additive_owner_exists_and_is_presentation_only() -> None:
    assert SUBJECT.exists(), "Step-3 details owner is not implemented yet"
    text = SUBJECT.read_text(encoding="utf-8")
    assert 'MODEL_VERSION = "CFB GAME TOTAL • GAMES ON THIS DAY • STEP 3 DETAILS V1"' in text
    assert "DIRECT_NETWORK_ENDPOINTS_ADDED = 0" in text
    assert "MAY_MODIFY_MODEL = False" in text
    assert "MAY_MODIFY_PROJECTION = False" in text
    assert "MAY_MODIFY_PROBABILITY = False" in text
    assert "MAY_MODIFY_OTHER_SPORTS = False" in text


def test_step3_augments_card_with_live_status_rank_and_conference() -> None:
    module = _load_subject()
    game = {
        "status": "In Progress",
        "away_team": "Oklahoma",
        "home_team": "Texas",
        "away_rank": 8,
        "home_rank": 12,
        "away_conference": "SEC",
        "home_conference": "SEC",
    }
    base = (
        '<a class="gt163-game-link gt2-game-card selected" aria-current="true">'
        '<div class="gt2-card-top"><span class="gt2-kickoff">4:00 PM MST</span>'
        '<span class="gt2-selected-pill">✓ SELECTED</span></div>'
        '<div class="gt2-team-row"><span class="gt2-team-name">Oklahoma</span></div>'
        '<div class="gt2-at">AT</div>'
        '<div class="gt2-team-row"><span class="gt2-team-name">Texas</span></div>'
        '</a>'
    )
    html = module.augment_game_card_html(base, game)
    assert 'data-step3-details="v1"' in html
    assert '>LIVE<' in html
    assert '#8' in html and '#12' in html
    assert html.count('>SEC<') == 2
    assert 'gt3-team-meta' in html
    assert 'gt3-status-live' in html


def test_step3_scheduled_and_final_states_are_normalized_without_guessing() -> None:
    module = _load_subject()
    assert module.status_label({"status": "Scheduled"}) == "UPCOMING"
    assert module.status_label({"status": "Final"}) == "FINAL"
    assert module.status_label({"status": "Status unavailable"}) == ""


def test_step3_hides_missing_rank_and_unavailable_conference() -> None:
    module = _load_subject()
    game = {
        "status": "Scheduled",
        "away_team": "Away Team",
        "home_team": "Home Team",
        "away_rank": None,
        "home_rank": 0,
        "away_conference": "Conference unavailable",
        "home_conference": "",
    }
    base = (
        '<a class="gt2-game-card">'
        '<div class="gt2-card-top"><span class="gt2-kickoff">7:30 PM MST</span></div>'
        '<div class="gt2-team-row"><span class="gt2-team-name">Away Team</span></div>'
        '<div class="gt2-team-row"><span class="gt2-team-name">Home Team</span></div>'
        '</a>'
    )
    html = module.augment_game_card_html(base, game)
    assert '>UPCOMING<' in html
    assert 'Conference unavailable' not in html
    assert '#0' not in html


def test_step3_css_adds_detail_hierarchy_without_reopening_step1_or_step2() -> None:
    assert SUBJECT.exists(), "Step-3 details owner is not implemented yet"
    text = SUBJECT.read_text(encoding="utf-8")
    assert ".gt3-status-chip" in text
    assert ".gt3-team-copy" in text
    assert ".gt3-team-meta" in text
    assert ".gt3-rank" in text
    assert ".gt3-conference" in text
    assert "grid-template-columns:1fr" not in text
    assert "ESPN_LOGO_CDN_TEMPLATE" not in text


def test_step3_active_router_installs_details_only_on_page1() -> None:
    router = ROUTER.read_text(encoding="utf-8")
    assert "cfb_game_total_games_on_day_step3_details_v1" in router
    assert "install_games_on_day_step3_details" in router
    assert "if not _selected_game_total():" in router
