from __future__ import annotations

import pandas as pd

from wnba_data_completeness_repair_v1_step2_stats_gate import gate_primary_production


NYL = 1611661313
ATL = 1611661330


def _production() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "PLAYER_ID": 1001,
                "PLAYER_NAME": "Same ID Star",
                "TEAM_ID": NYL,
                "MIN": 31.0,
                "PTS": 20.0,
                "REB": 5.0,
                "AST": 6.0,
                "DATA_SOURCE": "WNBA Stats",
            },
            {
                "PLAYER_ID": 2002,
                "PLAYER_NAME": "Different ID Star",
                "TEAM_ID": NYL,
                "MIN": 29.5,
                "PTS": 18.5,
                "REB": 4.5,
                "AST": 7.0,
                "DATA_SOURCE": "WNBA Stats",
            },
            {
                "PLAYER_ID": 4004,
                "PLAYER_NAME": "Waived Historical Player",
                "TEAM_ID": NYL,
                "MIN": 12.0,
                "PTS": 4.0,
                "REB": 2.0,
                "AST": 1.0,
                "DATA_SOURCE": "WNBA Stats",
            },
            {
                "PLAYER_ID": 3003,
                "PLAYER_NAME": "Atlanta Verified Player",
                "TEAM_ID": ATL,
                "MIN": 30.0,
                "PTS": 16.0,
                "REB": 8.0,
                "AST": 3.0,
                "DATA_SOURCE": "WNBA Stats",
            },
        ]
    )


def _roster() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "PLAYER_ID": 1001,
                "PLAYER_NAME": "Same ID Star",
                "TEAM_ID": NYL,
                "PLAYER_ID_SOURCE": "ESPN",
            },
            {
                # Same current player, different provider ID namespace.
                "PLAYER_ID": 999002,
                "PLAYER_NAME": "Different ID Star",
                "TEAM_ID": NYL,
                "PLAYER_ID_SOURCE": "ESPN",
            },
        ]
    )


def test_partial_provider_id_overlap_preserves_name_matched_production_and_stats():
    result = gate_primary_production(_production(), _roster(), {NYL, ATL})

    names = set(result["PLAYER_NAME"].astype(str))
    assert "Same ID Star" in names
    assert "Different ID Star" in names
    assert "Waived Historical Player" not in names

    mixed_id = result[result["PLAYER_NAME"].eq("Different ID Star")].iloc[0]
    assert int(mixed_id["PLAYER_ID"]) == 2002
    assert float(mixed_id["MIN"]) == 29.5
    assert float(mixed_id["PTS"]) == 18.5
    assert float(mixed_id["REB"]) == 4.5
    assert float(mixed_id["AST"]) == 7.0
    assert mixed_id["DATA_SOURCE"] == "WNBA Stats"


def test_missing_team_roster_feed_preserves_league_guarded_production():
    result = gate_primary_production(_production(), _roster(), {NYL, ATL})

    atlanta = result[result["PLAYER_NAME"].eq("Atlanta Verified Player")]
    assert len(atlanta) == 1
    row = atlanta.iloc[0]
    assert int(row["PLAYER_ID"]) == 3003
    assert float(row["PTS"]) == 16.0
    assert float(row["REB"]) == 8.0
    assert float(row["AST"]) == 3.0


def test_gate_never_introduces_a_new_slate_team():
    result = gate_primary_production(_production(), _roster(), {NYL})
    assert set(pd.to_numeric(result["TEAM_ID"], errors="coerce").dropna().astype(int)) == {NYL}
