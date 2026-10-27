from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_vercel_api_runtime_recovery_remains_present() -> None:
    source = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"pypdf"' in source


def test_additive_role_runtime_falls_back_to_verified_recent_minutes() -> None:
    import nba_pra_page2_role_runtime_v4 as page2

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
    assert "ROLE & USAGE" in html
    assert "CORE ROTATION ROLE" in html
    assert "USG% PENDING" in html
    assert "Usage / team role not currently verified" not in html
    assert "PLAYER AVAILABILITY" in html


def test_existing_verified_usage_card_is_preserved() -> None:
    import nba_pra_page2_role_runtime_v4 as page2

    context = {
        "team": "BOS",
        "opponent": "NYK",
        "player": {
            "usage_pct": 24.5,
            "usage_rank": 2,
            "usage_period": "Last 10 games",
            "usage_source": "NBA Stats",
        },
        "availability": "AVAILABLE",
        "availability_verification": "VERIFIED",
        "availability_source": "NBA Official Injury Report",
        "teammate_injuries": [],
    }
    games = [{"game_date": "2026-10-24", "opponent": "NYK", "minutes": 35.0, "pra": 31.0}]
    html = page2._role_availability_html(context, games)
    assert "24.5%" in html
    assert "HIGH-USAGE CORE ROLE" in html
    assert "USG% PENDING" not in html


def test_app_installs_additive_successor_before_render() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    import_pos = source.index("from nba_pra_page2_role_runtime_v4 import install as install_nba_pra_page2_role_runtime_v4")
    install_pos = source.index("install_nba_pra_page2_role_runtime_v4()")
    render_pos = source.index("render_app()")
    assert import_pos < install_pos < render_pos


def test_frozen_v3_and_model_ownership_remain_unchanged() -> None:
    source = (ROOT / "nba_pra_page2_command_center_v3.py").read_text(encoding="utf-8")
    assert 'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0' in source
    assert "Usage / team role not currently verified" in source
    assert "USG% PENDING" not in source
    successor = (ROOT / "nba_pra_page2_role_runtime_v4.py").read_text(encoding="utf-8")
    assert 'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0' in successor
    assert "Verified recent game minutes" in successor


def test_step2g_freezes_feature_artifacts_not_shared_app_entrypoint() -> None:
    plan = json.loads(
        (ROOT / "devsystem/runless_proof_plans/api2-nba-pra-page2-role-opp-runtime-v3.json")
        .read_text(encoding="utf-8")
    )
    assert "app.py" not in plan["artifacts"]
    assert "app.py" in plan["dependencies"]
    assert "nba_pra_page2_role_runtime_v4.py" in plan["artifacts"]
    assert "tests/test_api2_nba_pra_page2_role_opp_runtime_v3.py" in plan["artifacts"]
