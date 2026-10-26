from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SYNC = ROOT / "nba_pra_page2_sync_v1.py"
FROZEN = {
    "nba_pra_page2_v1.py": "799a1711fa4f7818c6c09a9f8c422f960b434c48",
    "nba_pra_page2_core_v2.py": "0176f6238da73e9b5f73d6f31e083e05948dd48e",
    "nba_pra_page2_insights_v1.py": "f1b09aed0a8c10ad94d97f3a167c06f8a6eb15bb",
}


def _git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def test_live_sync_uses_successor_presentation_but_frozen_model_helpers() -> None:
    source = SYNC.read_text(encoding="utf-8")
    assert "from nba_pra_page2_v1 import _baseline_model, default_line_for_context" in source
    assert "from nba_pra_page2_command_center_v2 import _css, build_page2_html" in source
    assert "from nba_pra_page2_command_center_v1 import _css, build_page2_html" not in source
    assert "from nba_pra_page2_v1 import _baseline_model, _css, build_page2_html, default_line_for_context" not in source


def test_line_lab_fragment_still_recalculates_locally_without_provider_fetch() -> None:
    source = SYNC.read_text(encoding="utf-8")
    assert "@st.fragment" in source
    fragment = source.split("@st.fragment", 1)[1]
    assert "evaluate_line(" in fragment
    assert "load_page2_snapshot_v1(" not in fragment
    assert "load_kyre_sports_api_nba_pra_matchup(" not in fragment
    assert "0 external fetches per slider move" in fragment


def test_prior_frozen_page2_artifacts_remain_byte_identical() -> None:
    for relative, expected in FROZEN.items():
        assert _git_blob_sha(ROOT / relative) == expected, relative
