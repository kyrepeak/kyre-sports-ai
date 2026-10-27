from __future__ import annotations

import importlib
from pathlib import Path
import sys
import types


def _parser():
    import sports_api as sports_api_pkg
    root = Path(__file__).resolve().parents[1]
    api_pkg = types.ModuleType("sports_api.api")
    api_pkg.__path__ = [str(root / "sports_api" / "api")]  # type: ignore[attr-defined]
    api_pkg.__package__ = "sports_api.api"
    sys.modules["sports_api.api"] = api_pkg
    setattr(sports_api_pkg, "api", api_pkg)
    sys.modules.pop("sports_api.api.nfl_game_totals_page2_context_v2", None)
    module = importlib.import_module("sports_api.api.nfl_game_totals_page2_context_v2")
    return module.parse_targeted_official_injury_html


def test_targeted_official_injury_parser_segments_nickname_tables_without_team_bleed():
    parse_targeted_official_injury_html = _parser()
    html = """
    <section><div>DAL Cowboys (2-4) PHI Eagles (2-4)</div><h3>Cowboys</h3>
      <table><tr><th>Player</th><th>Position</th><th>Injuries</th><th>Practice Status</th><th>Game Status</th></tr>
        <tr><td>Dallas Receiver</td><td>WR</td><td>Knee</td><td>Limited Participation in Practice</td><td>QUESTIONABLE</td></tr>
      </table>
      <h3>Eagles</h3>
      <table><tr><th>Player</th><th>Position</th><th>Injuries</th><th>Practice Status</th><th>Game Status</th></tr>
        <tr><td>Philly Tackle</td><td>T</td><td>Ankle</td><td>Did Not Participate In Practice</td><td>OUT</td></tr>
      </table>
    </section>
    """
    out = parse_targeted_official_injury_html(html, {"DAL", "PHI"})
    assert set(out) == {"DAL", "PHI"}
    assert out["DAL"]["verified"] is True
    assert out["PHI"]["verified"] is True
    assert [row["player_name"] for row in out["DAL"]["rows"]] == ["Dallas Receiver"]
    assert [row["player_name"] for row in out["PHI"]["rows"]] == ["Philly Tackle"]


def test_targeted_parser_ignores_unrequested_team_tables():
    parse_targeted_official_injury_html = _parser()
    html = """
    <h3>Giants</h3><table><tr><th>Player</th><th>Position</th></tr><tr><td>Other Player</td><td>WR</td></tr></table>
    <h3>Cowboys</h3><table><tr><th>Player</th><th>Position</th><th>Injuries</th><th>Practice Status</th><th>Game Status</th></tr><tr><td>Dallas Guard</td><td>G</td><td>Foot</td><td>Limited</td><td>QUESTIONABLE</td></tr></table>
    """
    out = parse_targeted_official_injury_html(html, {"DAL"})
    assert set(out) == {"DAL"}
    assert out["DAL"]["rows"][0]["player_name"] == "Dallas Guard"
