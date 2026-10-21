from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_FILES = (
    ROOT / "nba_pra_page2_v1.py",
    ROOT / "nba_pra_page2_api_only_v1.py",
    ROOT / "nba_pra_player_context_api_v1.py",
    ROOT / "runless_v2" / "nba_pra_player_context_enrichment_v2.py",
    ROOT / "runless_v2" / "nba_pra_usage_v1.py",
)


def test_page2_v2_active_path_has_no_sgo_or_espn_dependencies() -> None:
    combined = "\n".join(path.read_text(encoding="utf-8") for path in ACTIVE_FILES).casefold()
    assert "sportsgameodds" not in combined
    assert re.search(r"\bsgo\b", combined) is None
    assert re.search(r"\bespn\b", combined) is None
    assert "espn bet" not in combined


def test_page2_v2_keeps_kyre_gateway_ownership_explicit() -> None:
    client = (ROOT / "nba_pra_player_context_api_v1.py").read_text(encoding="utf-8")
    page = (ROOT / "nba_pra_page2_v1.py").read_text(encoding="utf-8")
    usage = (ROOT / "runless_v2" / "nba_pra_usage_v1.py").read_text(encoding="utf-8")

    assert "/api/v1/nba/pra/player-context" in client
    assert "load_page2_snapshot_v1" in page
    assert "stats.nba.com" in usage
    assert "Application pages never call this provider directly" in usage
