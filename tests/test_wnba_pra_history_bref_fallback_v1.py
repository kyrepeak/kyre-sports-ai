from __future__ import annotations

import importlib
import sys
from types import ModuleType

try:
    import requests as _requests  # noqa: F401
except ModuleNotFoundError:
    requests_stub = ModuleType("requests")

    class _RequestException(Exception):
        pass

    requests_stub.RequestException = _RequestException
    sys.modules["requests"] = requests_stub


PLAYER_HTML = """
<html><body><h1>Breanna Stewart</h1></body></html>
"""

INDEX_HTML = """
<html><body>
<a href="/wnba/players/s/stewabr01w.html">Breanna Stewart</a>
<a href="/wnba/players/s/smithna01w.html">NaLyssa Smith</a>
</body></html>
"""

BREF_HTML = """
<html><body>
<table>
<thead><tr>
<th>Date</th><th>Team</th><th></th><th>Opp</th><th>Result</th><th>GS</th><th>MP</th>
<th>FG</th><th>FGA</th><th>FG%</th><th>3P</th><th>3PA</th><th>3P%</th>
<th>FT</th><th>FTA</th><th>FT%</th><th>ORB</th><th>DRB</th><th>TRB</th>
<th>AST</th><th>STL</th><th>BLK</th><th>TOV</th><th>PF</th><th>PTS</th>
</tr></thead>
<tbody>
<tr><td>2026-10-04</td><td>NYL</td><td>@</td><td>ATL</td><td>L</td><td>*</td><td>40</td><td>6</td><td>13</td><td>.462</td><td>1</td><td>3</td><td>.333</td><td>6</td><td>6</td><td>1.000</td><td>0</td><td>2</td><td>2</td><td>3</td><td>3</td><td>3</td><td>2</td><td>3</td><td>19</td></tr>
<tr><td>2026-09-29</td><td>NYL</td><td></td><td>MIN</td><td>W</td><td>*</td><td>40</td><td>6</td><td>16</td><td>.375</td><td>0</td><td>4</td><td>.000</td><td>9</td><td>9</td><td>1.000</td><td>1</td><td>4</td><td>5</td><td>4</td><td>2</td><td>2</td><td>2</td><td>0</td><td>21</td></tr>
<tr><td>2026-09-27</td><td>NYL</td><td>@</td><td>MIN</td><td>W</td><td>*</td><td>38</td><td>11</td><td>18</td><td>.611</td><td>2</td><td>3</td><td>.667</td><td>10</td><td>12</td><td>.833</td><td>1</td><td>11</td><td>12</td><td>6</td><td>2</td><td>2</td><td>5</td><td>3</td><td>34</td></tr>
<tr><td>2026-09-21</td><td>NYL</td><td></td><td>ATL</td><td>L</td><td>*</td><td>37</td><td>11</td><td>19</td><td>.579</td><td>0</td><td>1</td><td>.000</td><td>5</td><td>8</td><td>.625</td><td>2</td><td>12</td><td>14</td><td>4</td><td>1</td><td>0</td><td>4</td><td>3</td><td>27</td></tr>
<tr><td>2026-09-20</td><td>NYL</td><td>@</td><td>TOR</td><td>W</td><td>*</td><td>22</td><td>10</td><td>14</td><td>.714</td><td>0</td><td>2</td><td>.000</td><td>7</td><td>7</td><td>1.000</td><td>1</td><td>7</td><td>8</td><td>4</td><td>2</td><td>1</td><td>1</td><td>2</td><td>27</td></tr>
</tbody>
</table>
</body></html>
"""


def _module():
    return importlib.import_module("sports_api.wnba_pra_history_multisource_v1")


def _teams(monkeypatch, module):
    monkeypatch.setattr(
        module,
        "get_wnba_teams",
        lambda season: [
            {"team_key": "new-york-liberty", "abbreviation": "NYL"},
            {"team_key": "atlanta-dream", "abbreviation": "ATL"},
            {"team_key": "minnesota-lynx", "abbreviation": "MIN"},
            {"team_key": "toronto-tempo", "abbreviation": "TOR"},
        ],
    )


def test_bref_resolver_and_parser_recover_recent_pra(monkeypatch):
    module = _module()
    _teams(monkeypatch, module)
    assert module.extract_official_wnba_player_name(PLAYER_HTML) == "Breanna Stewart"
    assert module.resolve_basketball_reference_player_href(INDEX_HTML, "Breanna Stewart") == "/wnba/players/s/stewabr01w.html"
    result = module.normalize_basketball_reference_player_html(
        BREF_HTML,
        player_id=1627668,
        player_name="Breanna Stewart",
        season=2026,
        source_url="https://www.basketball-reference.com/wnba/players/s/stewabr01w.html",
    )
    games = result["games"]
    pras = [row["points"] + row["rebounds"] + row["assists"] for row in games]
    assert pras == [24, 30, 52, 45, 39]
    assert round(sum(pras) / 5, 1) == 38.0
    atl = [row for row in games if row["matchup"]["opponent_team_key"] == "atlanta-dream"]
    assert len(atl) == 2
    assert round(sum(row["points"] + row["rebounds"] + row["assists"] for row in atl) / 2, 1) == 34.5


def test_multisource_uses_bref_when_primary_providers_fail(monkeypatch):
    module = _module()
    _teams(monkeypatch, module)
    bref = module.normalize_basketball_reference_player_html(
        BREF_HTML,
        player_id=1627668,
        player_name="Breanna Stewart",
        season=2026,
        source_url="https://www.basketball-reference.com/wnba/players/s/stewabr01w.html",
    )
    monkeypatch.setattr(module, "get_step3_espn_player_game_log_dataset", lambda *args: (_ for _ in ()).throw(RuntimeError("espn down")))
    monkeypatch.setattr(module, "get_official_wnba_profile_history", lambda *args: (_ for _ in ()).throw(RuntimeError("wnba down")))
    monkeypatch.setattr(module, "get_basketball_reference_player_history", lambda *args: bref)
    result = module.get_multisource_player_game_log_dataset(1627668, 2026)
    assert result["source"] == "Basketball-Reference WNBA Player Page"
    assert result["verification"]["provider_policy"] == "multi_source"
    assert result["verification"]["basketball_reference_fallback"] is True
    assert result["games"][0]["points"] == 19
