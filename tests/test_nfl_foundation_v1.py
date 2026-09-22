from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_nfl_foundation_keeps_verified_espn_slate_and_fail_closed_behavior() -> None:
    source = _read("nfl_hub_v1.py")

    assert 'ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"' in source
    assert 'timeout=8' in source
    assert 'if event_day and event_day != day:' in source
    assert 'return pd.DataFrame(), diag' in source
    assert 'No NFL games were returned for this selected ET calendar date.' in source
    assert 'no fake games are created' in source.lower()


def test_existing_nfl_moneyline_wrapper_stays_preserved() -> None:
    source = _read("nfl_hub_v18.py")

    assert 'if market == "Moneyline":' in source
    assert 'from nfl_moneyline_hub_v8 import render_nfl_moneyline_hub' in source
    assert 'return base.render_nfl_hub(market)' in source
