from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "CFB_GAME_TOTAL_PAGE1_V2_STEP1_AUDIT_CONTRACT.md"


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_step1_audit_contract_exists_before_freeze() -> None:
    assert CONTRACT.is_file(), "Step-1 Page-1 audit contract must exist before GREEN/FROZEN"


def test_step1_contract_locks_user_requirements() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    required = (
        "CFB Game Total Page 1 V2",
        "America/Phoenix",
        "tomorrow and beyond",
        "Kyre Sports API",
        "multi-source",
        "DATA LIMITED",
        "371f05b940369c3378ceea8f12fb02e52e5f7f11",
        "cfb_game_total_clean_page_v34.py",
        "streamlit_memory_lazy_router_v190.py",
        "cfb_game_total_clean_page_v11.py",
        "cfb_game_total_clean_page_v14.py",
    )
    for token in required:
        assert token in text, f"missing Step-1 contract token: {token}"

    lowered = text.lower()
    assert "today is excluded" in lowered
    assert "no product runtime mutation" in lowered
    assert "generic data limited" in lowered
    assert "espn-only" in lowered


def test_current_page_owner_and_date_root_cause_are_audited_from_real_code() -> None:
    v34 = _text("cfb_game_total_clean_page_v34.py")
    router = _text("streamlit_memory_lazy_router_v190.py")
    day_owner = _text("cfb_game_total_clean_page_v11.py")
    selector = _text("cfb_game_total_clean_page_v14.py")

    assert 'FROZEN_PRESENTATION = "cfb_game_total_clean_page_v33"' in v34
    assert 'GAME_TOTAL_PAGE = "cfb_game_total_clean_page_v34"' in router
    assert 'ZoneInfo("America/Phoenix")' in day_owner
    assert 'return datetime.now(ZoneInfo("America/Phoenix")).date()' in day_owner
    assert "start = selected - timedelta(days=2)" in day_owner
    assert "games = _load_games(selected_day)" in selector
    assert "return 0" in selector.split("def _selected_game_index", 1)[1].split("def _team_name", 1)[0]


def test_current_kyre_api_is_partial_not_full_page1_ownership() -> None:
    day_owner = _text("cfb_game_total_clean_page_v11.py")
    selector = _text("cfb_game_total_clean_page_v14.py")
    evidence = _text("cfb_game_total_game_evidence_v1.py")
    multi = _text("cfb_game_total_step4_multisource_v1.py")

    assert 'ODDS_API_BASE_DEFAULT = "https://kyre-sports-api.onrender.com"' in day_owner
    assert 'SELECTOR_IDENTITY_SOURCE = "Kyre Sports API full-slate verified identity"' in selector
    assert "cfb_over_under_environment_engine_v1" in evidence
    assert 'SOURCE = "cfbstats.com"' in multi


def test_step1_is_audit_only_and_preserves_frozen_analytics() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    protected = (
        "projection math",
        "probability",
        "qualification",
        "ranking",
        "sportsbook projection influence",
        "frozen Steps 1–12",
    )
    for token in protected:
        assert token in text
