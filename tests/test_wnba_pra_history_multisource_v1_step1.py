from __future__ import annotations

import importlib
import sys
from types import ModuleType


# Runless proof workers intentionally install only the proof-plane dependency set.
# The production app already pins requests in requirements.lock, but this focused
# parser/merge test does not perform real HTTP. Keep the proof isolated from that
# unrelated runtime package while preserving the production import contract.
try:
    import requests as _requests  # noqa: F401
except ModuleNotFoundError:
    requests_stub = ModuleType("requests")

    class _RequestException(Exception):
        pass

    requests_stub.RequestException = _RequestException
    sys.modules["requests"] = requests_stub


OFFICIAL_HTML = """
<html><body>
<table>
  <thead><tr>
    <th>Date</th><th>Matchup</th><th>Result</th><th>MIN</th><th>PTS</th>
    <th>FGM</th><th>FGA</th><th>FGM-3</th><th>FGA-3</th>
    <th>OREB</th><th>DREB</th><th>REB</th><th>AST</th><th>STL</th><th>BLK</th><th>TO</th><th>PF</th>
  </tr></thead>
  <tbody>
    <tr><td>10.04.2026</td><td>NYL @ ATL</td><td>L</td><td>40</td><td>19</td><td>6</td><td>13</td><td>1</td><td>3</td><td>0</td><td>2</td><td>2</td><td>3</td><td>3</td><td>3</td><td>2</td><td>3</td></tr>
    <tr><td>09.29.2026</td><td>NYL vs. MIN</td><td>W</td><td>40</td><td>21</td><td>6</td><td>16</td><td>0</td><td>4</td><td>1</td><td>4</td><td>5</td><td>4</td><td>2</td><td>2</td><td>2</td><td>0</td></tr>
    <tr><td>09.27.2026</td><td>NYL @ MIN</td><td>W</td><td>38</td><td>34</td><td>11</td><td>18</td><td>2</td><td>3</td><td>1</td><td>11</td><td>12</td><td>6</td><td>2</td><td>2</td><td>5</td><td>3</td></tr>
    <tr><td>09.21.2026</td><td>NYL vs. ATL</td><td>L</td><td>37</td><td>27</td><td>11</td><td>19</td><td>0</td><td>1</td><td>2</td><td>12</td><td>14</td><td>4</td><td>1</td><td>0</td><td>4</td><td>3</td></tr>
    <tr><td>09.20.2026</td><td>NYL @ TOR</td><td>W</td><td>22</td><td>27</td><td>10</td><td>14</td><td>0</td><td>2</td><td>1</td><td>7</td><td>8</td><td>4</td><td>2</td><td>1</td><td>1</td><td>2</td></tr>
  </tbody>
</table>
</body></html>
"""


def _module():
    return importlib.import_module("sports_api.wnba_pra_history_multisource_v1")


def test_official_wnba_profile_parser_recovers_real_recent_pra(monkeypatch):
    module = _module()
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
    result = module.normalize_official_wnba_profile_html(
        OFFICIAL_HTML,
        player_id=1627668,
        season=2026,
    )

    assert result["source"] == "WNBA.com Player Profile"
    assert result["game_count"] == 5
    games = result["games"]
    assert [game["points"] + game["rebounds"] + game["assists"] for game in games] == [24, 30, 52, 45, 39]
    assert round(sum(game["points"] + game["rebounds"] + game["assists"] for game in games) / 5, 1) == 38.0
    atl = [game for game in games if game["matchup"]["opponent_team_key"] == "atlanta-dream"]
    assert len(atl) == 2
    assert round(sum(game["points"] + game["rebounds"] + game["assists"] for game in atl) / 2, 1) == 34.5


def test_official_profile_url_forces_server_rendered_recent_stats():
    module = _module()
    assert module._official_profile_url(1627668) == "https://www.wnba.com/player/1627668/profile?os=win"


def test_merge_backfills_missing_stats_by_exact_date_and_opponent_without_overwrite():
    module = _module()
    espn = {
        "source": "ESPN WNBA Athlete Gamelog",
        "games": [
            {
                "game_date": "2026-10-04",
                "minutes": 40.0,
                "points": None,
                "rebounds": None,
                "assists": None,
                "matchup": {"opponent_team_key": "atlanta-dream"},
            },
            {
                "game_date": "2026-09-21",
                "minutes": 36.0,
                "points": 99,
                "rebounds": None,
                "assists": None,
                "matchup": {"opponent_team_key": "atlanta-dream"},
            },
        ],
        "verification": {},
    }
    official = {
        "source": "WNBA.com Player Profile",
        "games": [
            {"game_date": "2026-10-04", "minutes": 40.0, "points": 19, "rebounds": 2, "assists": 3, "matchup": {"opponent_team_key": "atlanta-dream"}},
            {"game_date": "2026-09-21", "minutes": 37.0, "points": 27, "rebounds": 14, "assists": 4, "matchup": {"opponent_team_key": "atlanta-dream"}},
        ],
        "verification": {},
    }

    result = module.merge_verified_histories(espn, official)
    first, second = result["games"]
    assert (first["points"], first["rebounds"], first["assists"]) == (19, 2, 3)
    assert second["points"] == 99
    assert (second["rebounds"], second["assists"]) == (14, 4)
    assert result["verification"]["official_wnba_backfill_fields"] == 5


def test_multisource_returns_official_when_espn_provider_fails(monkeypatch):
    module = _module()
    official = {
        "source": "WNBA.com Player Profile",
        "source_url": "https://www.wnba.com/player/1627668/profile?os=win",
        "game_count": 1,
        "games": [{"game_date": "2026-10-04", "points": 19, "rebounds": 2, "assists": 3, "minutes": 40.0, "matchup": {"opponent_team_key": "atlanta-dream"}}],
        "verification": {"official_wnba_profile": True},
    }

    monkeypatch.setattr(module, "get_step3_espn_player_game_log_dataset", lambda player_id, season: (_ for _ in ()).throw(RuntimeError("espn down")))
    monkeypatch.setattr(module, "get_official_wnba_profile_history", lambda player_id, season: official)

    result = module.get_multisource_player_game_log_dataset(1627668, 2026)
    assert result["source"] == "WNBA.com Player Profile"
    assert result["games"][0]["points"] == 19
    assert result["verification"]["provider_policy"] == "multi_source"


def test_multisource_returns_espn_when_official_provider_fails(monkeypatch):
    module = _module()
    espn = {
        "source": "ESPN WNBA Athlete Gamelog",
        "game_count": 1,
        "games": [{"game_date": "2026-10-04", "points": 19, "rebounds": 2, "assists": 3, "minutes": 40.0, "matchup": {"opponent_team_key": "atlanta-dream"}}],
        "verification": {},
    }

    monkeypatch.setattr(module, "get_step3_espn_player_game_log_dataset", lambda player_id, season: espn)
    monkeypatch.setattr(module, "get_official_wnba_profile_history", lambda player_id, season: (_ for _ in ()).throw(RuntimeError("wnba down")))

    result = module.get_multisource_player_game_log_dataset(1627668, 2026)
    assert result["source"] == "ESPN WNBA Athlete Gamelog"
    assert result["games"][0]["rebounds"] == 2
    assert result["verification"]["provider_policy"] == "multi_source"
