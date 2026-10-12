from __future__ import annotations

import importlib
from pathlib import Path


MODULE_PATH = Path("nba_spread_most_bet_v1.py")
PAGE_PATH = Path("nba_spread_page_v1.py")


def _module():
    assert MODULE_PATH.is_file(), "Step 4 RED: nba_spread_most_bet_v1.py must be implemented"
    return importlib.import_module("nba_spread_most_bet_v1")


def _verified_schedule():
    return [
        {
            "away_tricode": "BOS",
            "home_tricode": "NYK",
            "away_name": "Boston Celtics",
            "home_name": "New York Knicks",
            "game_date_phoenix": "2026-10-13",
            "tip_phoenix": "4:30 PM",
            "status": "UPCOMING",
        },
        {
            "away_tricode": "LAL",
            "home_tricode": "PHX",
            "away_name": "Los Angeles Lakers",
            "home_name": "Phoenix Suns",
            "game_date_phoenix": "2026-10-14",
            "tip_phoenix": "7:00 PM",
            "status": "UPCOMING",
        },
        {
            "away_tricode": "DEN",
            "home_tricode": "GSW",
            "away_name": "Denver Nuggets",
            "home_name": "Golden State Warriors",
            "game_date_phoenix": "2026-10-15",
            "tip_phoenix": "7:30 PM",
            "status": "FINAL",
        },
    ]


def _valid_lakers_rows(count: int = 12500):
    return [
        {
            "away": "Los Angeles Lakers",
            "home": "Phoenix Suns",
            "bet_count": count,
            "away_bet_pct": 67,
            "home_bet_pct": 33,
            "away_money_pct": 62,
            "home_money_pct": 38,
        }
    ]


def test_parses_action_network_documented_public_table_shape():
    module = _module()
    html = """
    <table>
      <thead><tr>
        <th>Scheduled</th><th>Open</th><th>Best Odds</th><th>% of Bets</th>
        <th>% of Money</th><th>Diff</th><th>Bets</th>
      </tr></thead>
      <tbody><tr>
        <td>7:00 PM Lakers LAL 1 Suns PHX 2</td><td>-1.5 +1.5</td><td>-2.5 -110 +2.5 -110</td>
        <td>67%33%</td><td>62%38%</td><td>+5%</td><td>12,500</td>
      </tr></tbody>
    </table>
    """
    assert module.parse_action_network_html(html) == [
        {
            "away": "Los Angeles Lakers",
            "home": "Phoenix Suns",
            "away_tricode": "LAL",
            "home_tricode": "PHX",
            "bet_count": 12500,
            "away_bet_pct": 67,
            "home_bet_pct": 33,
            "away_money_pct": 62,
            "home_money_pct": 38,
        }
    ]


def test_selects_highest_tracked_bet_count_only_from_verified_upcoming_schedule():
    module = _module()
    rows = [
        {
            "away": "Boston Celtics",
            "home": "New York Knicks",
            "bet_count": 8200,
            "away_bet_pct": 44,
            "home_bet_pct": 56,
            "away_money_pct": 41,
            "home_money_pct": 59,
        },
        {
            "away": "Los Angeles Lakers",
            "home": "Phoenix Suns",
            "bet_count": 12500,
            "away_bet_pct": 67,
            "home_bet_pct": 33,
            "away_money_pct": 62,
            "home_money_pct": 38,
        },
        {
            "away": "Denver Nuggets",
            "home": "Golden State Warriors",
            "bet_count": 25000,
            "away_bet_pct": 51,
            "home_bet_pct": 49,
            "away_money_pct": 48,
            "home_money_pct": 52,
        },
    ]
    feature = module.select_most_bet_game(rows, _verified_schedule())
    assert feature["verification"] == "VERIFIED"
    assert feature["away_tricode"] == "LAL"
    assert feature["home_tricode"] == "PHX"
    assert feature["bet_count"] == 12500
    assert feature["tip_phoenix"] == "7:00 PM"
    assert feature["game_date_phoenix"] == "2026-10-14"


def test_fails_closed_when_action_row_does_not_match_verified_schedule():
    module = _module()
    rows = [
        {
            "away": "Miami Heat",
            "home": "Orlando Magic",
            "bet_count": 99999,
            "away_bet_pct": 55,
            "home_bet_pct": 45,
            "away_money_pct": 53,
            "home_money_pct": 47,
        }
    ]
    feature = module.select_most_bet_game(rows, _verified_schedule())
    assert feature == {
        "verification": "UNAVAILABLE",
        "diagnostic_state": "NO_VERIFIED_SCHEDULE_MATCH",
    }


def test_fails_closed_on_incomplete_or_impossible_split_percentages():
    module = _module()
    bad_rows = [
        {
            "away": "Los Angeles Lakers",
            "home": "Phoenix Suns",
            "bet_count": 12500,
            "away_bet_pct": 80,
            "home_bet_pct": 30,
            "away_money_pct": 60,
            "home_money_pct": 40,
        }
    ]
    feature = module.select_most_bet_game(bad_rows, _verified_schedule())
    assert feature["verification"] == "UNAVAILABLE"
    assert feature["diagnostic_state"] == "INVALID_BETTING_SPLITS"


def test_equal_top_volume_is_ambiguous_and_fails_closed_instead_of_guessing():
    module = _module()
    rows = [
        {
            "away": "Boston Celtics",
            "home": "New York Knicks",
            "bet_count": 12500,
            "away_bet_pct": 44,
            "home_bet_pct": 56,
            "away_money_pct": 41,
            "home_money_pct": 59,
        },
        {
            "away": "Los Angeles Lakers",
            "home": "Phoenix Suns",
            "bet_count": 12500,
            "away_bet_pct": 67,
            "home_bet_pct": 33,
            "away_money_pct": 62,
            "home_money_pct": 38,
        },
    ]
    feature = module.select_most_bet_game(rows, _verified_schedule())
    assert feature["verification"] == "UNAVAILABLE"
    assert feature["diagnostic_state"] == "AMBIGUOUS_MOST_BET_GAME"


def test_multisource_contract_is_explicit_and_never_treats_percentages_as_raw_volume():
    module = _module()
    ownership = module.source_ownership_manifest()
    sources = ownership["betting_volume"]["sources"]
    assert [source["role"] for source in sources] == ["PRIMARY", "SECONDARY", "TERTIARY"]
    assert sources[0]["name"] == "Action Network"
    assert module.REQUIRED_VOLUME_METRIC in sources[0]["capabilities"]
    assert sources[0]["selection_capable"] is True
    assert sources[1]["name"] == "SportsDataIO"
    assert sources[2]["name"] == "VSiN / DraftKings"
    for source in sources[1:]:
        assert module.REQUIRED_VOLUME_METRIC not in source["capabilities"]
        assert source["selection_capable"] is False
        assert source["incompatibility"] == "ABSOLUTE_GAME_BET_COUNT_NOT_EXPOSED"


def test_equivalent_secondary_is_used_when_primary_fails_without_duplicate_work():
    module = _module()
    calls = []

    def primary():
        calls.append("primary")
        raise RuntimeError("primary unavailable")

    def secondary():
        calls.append("secondary")
        return _valid_lakers_rows(13000)

    contracts = (
        {
            "role": "PRIMARY",
            "name": "Primary Count Feed",
            "url": "https://primary.invalid",
            "capabilities": (module.REQUIRED_VOLUME_METRIC, "spread_bet_pct", "spread_money_pct"),
            "selection_capable": True,
            "incompatibility": None,
        },
        {
            "role": "SECONDARY",
            "name": "Secondary Count Feed",
            "url": "https://secondary.invalid",
            "capabilities": (module.REQUIRED_VOLUME_METRIC, "spread_bet_pct", "spread_money_pct"),
            "selection_capable": True,
            "incompatibility": None,
        },
        {
            "role": "TERTIARY",
            "name": "Split Only Feed",
            "url": "https://tertiary.invalid",
            "capabilities": ("spread_bet_pct", "spread_money_pct"),
            "selection_capable": False,
            "incompatibility": "ABSOLUTE_GAME_BET_COUNT_NOT_EXPOSED",
        },
    )
    feature = module.load_most_bet_feature(
        _verified_schedule(),
        provider_contracts=contracts,
        provider_fetchers={
            "Primary Count Feed": primary,
            "Secondary Count Feed": secondary,
        },
    )
    assert calls == ["primary", "secondary"]
    assert feature["verification"] == "VERIFIED"
    assert feature["source"] == "Secondary Count Feed"
    assert feature["bet_count"] == 13000
    assert feature["provider_health"]["Primary Count Feed"] == "DEGRADED"
    assert feature["provider_health"]["Secondary Count Feed"] == "HEALTHY"


def test_exhausted_incompatible_fallbacks_degrade_feature_not_page(monkeypatch):
    module = _module()

    def unavailable(*, timeout_seconds=12.0):
        del timeout_seconds
        raise RuntimeError("source unavailable")

    monkeypatch.setattr(module, "fetch_action_network_rows", unavailable)
    feature = module.load_most_bet_feature(_verified_schedule())
    assert feature["verification"] == "UNAVAILABLE"
    assert feature["diagnostic_state"] == "NO_COMPARABLE_VOLUME_FALLBACK"
    assert feature["page_impact"] == "FEATURE_ONLY"
    assert feature["provider_health"]["Action Network"] == "DEGRADED"
    assert feature["provider_health"]["SportsDataIO"] == "NOT_QUERIED_CAPABILITY_MISMATCH"
    assert feature["provider_health"]["VSiN / DraftKings"] == "NOT_QUERIED_CAPABILITY_MISMATCH"
    assert feature["consensus_status"] == "FALLBACKS_EXHAUSTED_NO_FALSE_SUBSTITUTION"


def test_verified_feature_carries_canonical_ids_and_truthful_provenance():
    module = _module()
    feature = module.select_most_bet_game(_valid_lakers_rows(), _verified_schedule())
    assert feature["verification"] == "VERIFIED"
    assert feature["kyre_game_id"] == "KYRE:NBA:GAME:LAL@PHX:2026-10-14"
    assert feature["kyre_away_team_id"] == "KYRE:NBA:TEAM:LAL"
    assert feature["kyre_home_team_id"] == "KYRE:NBA:TEAM:PHX"
    assert feature["source_metric"] == module.REQUIRED_VOLUME_METRIC
    assert feature["source_timestamp_status"] == "NOT_EXPOSED"
    assert feature["source_observed_at_utc"] == ""


def test_step4_keeps_later_decision_layers_disabled():
    module = _module()
    assert module.SOURCE_NAME == "Action Network"
    assert module.MAY_MODIFY_MODEL is False
    assert module.MAY_MODIFY_PROJECTION is False
    assert module.MAY_MODIFY_PROBABILITY is False
    assert module.MAY_ACTIVATE_SHARP_MONEY is False
    assert module.MAY_ACTIVATE_INJURIES is False
    assert module.MAY_ACTIVATE_RANKING is False
    assert module.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0


def test_page_owns_exact_step4_feature_marker_without_step5_leakage():
    _module()
    page = PAGE_PATH.read_text()
    assert 'data-testid="nba-spread-step4-most-bet-active"' in page
    assert "🔥 Most Bet Game" in page
    assert "nba-spread-step3-schedule-active" in page
    assert "Sharp Money Game" not in page
    assert "Kyre Fair Spread" not in page
    assert "Cover Probability" not in page
