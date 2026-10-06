from __future__ import annotations

from pathlib import Path

from devsystem.api2_task16_final_mobile_system_cert_v1 import EXPECTED_BLOBS, audit


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _healthy_fixture(tmp_path: Path) -> Path:
    _write(tmp_path, "sports_api/nfl_game_totals_total_projection_v1.py", "sportsbook-free projection\n")
    _write(tmp_path, "nfl_hub_v18.py", "from nfl_moneyline_hub_v9 import render_nfl_moneyline_hub\n")
    _write(
        tmp_path,
        "nfl_game_totals_hub_v8_1.py",
        '''AUTO_ADVANCE_EMPTY_TODAY = True\nNEXT_SLATE_LOOKAHEAD_DAYS = 14\nSPORTSBOOK_PROJECTION_INFLUENCE = 0.0\nSTAKE_SIZING_ENABLED = False\nWAGER_ACTIONS_ENABLED = False\nclear_router_caches()\nst.button("➡️ Next Game Day", use_container_width=True)\nst.button("🔄 Reload Data", use_container_width=True)\n''',
    )
    _write(
        tmp_path,
        "nfl_game_totals_hub_v9.py",
        '''PAGE_BUILD_STEP = 9\nPAGE_BUILD_TOTAL = 10\nMARKET_COMPARISON_ENABLED = True\nSPORTSBOOK_PROJECTION_INFLUENCE = 0.0\nSTAKE_SIZING_ENABLED = False\nWAGER_ACTIONS_ENABLED = False\n@media(max-width:760px){.kgt-read-grid{grid-template-columns:1fr 1fr}}\nbuild_market_final_read(\n''',
    )
    _write(
        tmp_path,
        "nfl_game_totals_hub_v10.py",
        '''PAGE_BUILD_STEP = 10\nPAGE_BUILD_TOTAL = 10\nFINAL_CERTIFICATION_ENABLED = True\nMARKET_COMPARISON_ENABLED = True\nSPORTSBOOK_PROJECTION_INFLUENCE = 0.0\nSTAKE_SIZING_ENABLED = False\nWAGER_ACTIONS_ENABLED = False\n("10", "FINAL CERTIFICATION", True)\n''',
    )
    _write(
        tmp_path,
        "nfl_game_totals_market_read_v1.py",
        '''SPORTSBOOK_PROJECTION_WEIGHT = 0.0\nSTAKE_SIZING_ENABLED = False\nWAGER_ACTIONS_ENABLED = False\n"comparison_only": True\n''',
    )
    _write(
        tmp_path,
        "nfl_hub_v36.py",
        '''import nfl_hub_v35 as base\nif market == "Game Total":\n    from nfl_game_totals_hub_v10 import render_nfl_game_totals_hub\nreturn base.render_nfl_hub(market)\n''',
    )
    _write(
        tmp_path,
        "streamlit_memory_lazy_router_v97.py",
        '''ACTIVE_NFL_HUB = "nfl_hub_v36"\nPASSING_YARDS_MARKET = "Passing Yards"\nGAME_TOTAL_MARKET = "Game Total"\nif market not in {PASSING_YARDS_MARKET, GAME_TOTAL_MARKET}:\n''',
    )
    manifest = [f".github/workflows/fallback-{index:02d}.yml" for index in range(29)]
    manifest.append(".github/workflows/nfl-passing-yards-live-source-cert-v1.yml")
    _write(tmp_path, "devsystem/runless_legacy_proof_workflows_v1.txt", "\n".join(manifest) + "\n")
    _write(
        tmp_path,
        "devsystem/production_targets_v1.json",
        '{"streamlit":{"url":"https://pickvault.streamlit.app","health_path":"/_stcore/health"}}\n',
    )
    return tmp_path


def _expected_blob_resolver(path: str) -> str:
    return EXPECTED_BLOBS[path]


def test_task16_certifies_exact_frozen_mobile_system(tmp_path: Path) -> None:
    root = _healthy_fixture(tmp_path)
    report = audit(root, blob_resolver=_expected_blob_resolver)

    assert report["ready"] is True
    assert report["failures"] == []
    assert report["sportsbook_projection_influence"] == 0.0
    assert report["stake_sizing_enabled"] is False
    assert report["wager_actions_enabled"] is False
    assert report["fallback_workflow_count"] == 30
    assert report["production_url"] == "https://pickvault.streamlit.app"
    assert report["certification_marker"] == "API2_TASK16_FINAL_MOBILE_SYSTEM_CERT_GREEN"


def test_task16_fails_closed_on_wager_or_mobile_recovery_drift(tmp_path: Path) -> None:
    root = _healthy_fixture(tmp_path)
    v10 = root / "nfl_game_totals_hub_v10.py"
    v10.write_text(v10.read_text(encoding="utf-8").replace("WAGER_ACTIONS_ENABLED = False", "WAGER_ACTIONS_ENABLED = True"), encoding="utf-8")
    mobile = root / "nfl_game_totals_hub_v8_1.py"
    mobile.write_text(mobile.read_text(encoding="utf-8").replace("NEXT_SLATE_LOOKAHEAD_DAYS = 14", "NEXT_SLATE_LOOKAHEAD_DAYS = 0"), encoding="utf-8")

    report = audit(root, blob_resolver=_expected_blob_resolver)

    assert report["ready"] is False
    assert any("WAGER_ACTIONS_ENABLED" in item for item in report["failures"])
    assert any("NEXT_SLATE_LOOKAHEAD_DAYS" in item for item in report["failures"])
