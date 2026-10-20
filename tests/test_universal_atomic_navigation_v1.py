from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import importlib
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
HELPER = ROOT / "universal_atomic_navigation_v1.py"


def _required_source(path: Path) -> str:
    assert path.exists(), f"required Atomic Navigation V1 file missing: {path.name}"
    return path.read_text(encoding="utf-8")


def test_route_identity_detects_only_canonical_route_changes():
    _required_source(HELPER)
    helper = importlib.import_module("universal_atomic_navigation_v1")

    before = SimpleNamespace(sport_id="cfb", market_id="moneyline", params={"date": "2026-10-20"})
    same = SimpleNamespace(sport_id="cfb", market_id="moneyline", params={"date": "2026-10-20"})
    market = SimpleNamespace(sport_id="cfb", market_id="game-total", params={"date": "2026-10-20"})
    sport = SimpleNamespace(sport_id="nba", market_id="spread", params={"date": "2026-10-20"})
    params = SimpleNamespace(sport_id="cfb", market_id="moneyline", params={"date": "2026-10-21"})

    assert helper.is_route_transition(before, same) is False
    assert helper.is_route_transition(before, market) is True
    assert helper.is_route_transition(before, sport) is True
    assert helper.is_route_transition(before, params) is True


def test_transition_markup_is_opaque_and_route_specific():
    _required_source(HELPER)
    helper = importlib.import_module("universal_atomic_navigation_v1")
    route = SimpleNamespace(sport_id="nba", market_id="spread", params={})
    markup = helper.transition_markup(route)

    assert "KYRE SPORTS AI" in markup
    assert "NBA" in markup.upper()
    assert "SPREAD" in markup.upper()
    assert "position:fixed" in markup.replace(" ", "").lower()
    assert "background:" in markup.lower()
    assert "pointer-events:all" in markup.replace(" ", "").lower()
