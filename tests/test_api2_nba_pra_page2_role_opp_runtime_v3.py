from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_vercel_api_declares_pypdf_runtime_dependency() -> None:
    source = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"pypdf"' in source


def test_role_card_falls_back_to_verified_recent_minutes() -> None:
    import nba_pra_page2_command_center_v3 as page2

    context = {
        "team": "MEM",
        "opponent": "UTA",
        "player": {"usage_pct": None, "usage_rank": None},
        "availability": "NO OFFICIAL INJURY DESIGNATION",
        "availability_verification": "VERIFIED",
        "availability_source": "NBA Official Injury Report",
        "teammate_injuries": [],
    }
    games = [
        {"game_date": "2026-10-25", "opponent": "SAC", "minutes": 33.0, "pra": 24.0},
        {"game_date": "2026-10-23", "opponent": "GSW", "minutes": 25.0, "pra": 24.0},
        {"game_date": "2026-10-21", "opponent": "UTA", "minutes": 28.0, "pra": 17.0},
    ]
    html = page2._role_availability_html(context, games)
    assert "ROLE &amp; USAGE" in html or "ROLE & USAGE" in html
    assert "CORE ROTATION ROLE" in html
    assert "Usage / team role not currently verified" not in html
    assert "PLAYER AVAILABILITY" in html


def test_model_ownership_remains_frozen() -> None:
    source = (ROOT / "nba_pra_page2_command_center_v3.py").read_text(encoding="utf-8")
    assert 'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0' in source
