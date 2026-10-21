from datetime import date

from nba_pra_page1_model_v1 import grade_market
from nba_pra_team_identity_v1 import resolve_nba_team_logo
from runless_v2.nba_pra_player_context_v1 import (
    NbaPraPlayerContextRequest,
    _parse_cbs_roster_html,
)


def test_official_nba_logo_path_is_complete_and_non_espn():
    logo = resolve_nba_team_logo("PHX")
    assert logo == "https://cdn.nba.com/logos/nba/1610612756/global/L/logo.svg"
    assert "espn" not in logo.casefold()
    assert resolve_nba_team_logo("UNKNOWN") is None


def test_cbs_roster_identity_fallback_builds_player_card_fields():
    document = '''
    <table><tbody><tr class="TableBase-bodyTr">
      <td>13</td>
      <td><span class="CellPlayerName--long"><a href="/nba/players/2844706/bam-adebayo/">Bam Adebayo</a></span></td>
      <td>PF</td><td>6-9</td><td>255</td>
    </tr></tbody></table>
    '''
    row = _parse_cbs_roster_html(document, "MIA")["bamadebayo"]
    assert row["team"] == "MIA"
    assert row["position"] == "PF"
    assert row["provider_ids"]["cbs_sports"] == "2844706"
    assert row["headshot"] == "https://sportshub.cbsistatic.com/i/sports/player/headshot/2844706.png?width=160"
    assert row["stats_source"] == "CBS Sports roster verification"


def test_player_context_contract_accepts_full_121_player_slate():
    request = NbaPraPlayerContextRequest(
        date=date(2026, 10, 21),
        player_names=[f"Player {i}" for i in range(121)],
        team_codes=["MIA", "LAL"],
    )
    assert len(request.player_names) == 121
    assert request.team_codes == ["MIA", "LAL"]


def test_edge_remains_available_without_fabricating_probability():
    grade = grade_market(21.3, 17.5, None)
    assert grade["edge"] == 3.8
    assert grade["over_probability"] is None
    assert grade["lean"] == "PASS"
    assert grade["confidence"] == "UNAVAILABLE"
