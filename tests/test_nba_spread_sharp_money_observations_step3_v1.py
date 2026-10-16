from pathlib import Path
import importlib


MODULE_PATH = Path("nba_spread_sharp_money_observations_v1.py")


def _module():
    return importlib.import_module("nba_spread_sharp_money_observations_v1")


def _schedule(*, status="UPCOMING"):
    return [
        {
            "away_tricode": "LAL",
            "home_tricode": "PHX",
            "away_name": "Los Angeles Lakers",
            "home_name": "Phoenix Suns",
            "game_date_phoenix": "2026-10-20",
            "tip_phoenix": "7:00 PM",
            "status": status,
        }
    ]


def _verified_payload(**overrides):
    row = {
        "away_tricode": "LAL",
        "home_tricode": "PHX",
        "bet_count": 1420,
        "away_bet_pct": 64,
        "home_bet_pct": 36,
        "away_money_pct": 48,
        "home_money_pct": 52,
    }
    row.update(overrides)
    return {
        "verification": "VERIFIED",
        "diagnostic_state": "OK",
        "source": "Action Network",
        "observations": [row],
        "fabrication": False,
        "page_wide_source_authority": False,
        "sportsbook_projection_influence": 0.0,
    }


def test_step3_sharp_money_observation_adapter_exists():
    assert MODULE_PATH.exists(), "Step 3 sharp-money observation adapter does not exist yet"


def test_valid_verified_observation_yields_positive_sharp_side_without_threshold():
    module = _module()
    result = module.derive_verified_sharp_money_observations(_verified_payload(), _schedule())

    assert result["verification"] == "VERIFIED"
    assert result["diagnostic_state"] == "OK"
    assert result["source"] == "Action Network"
    assert result["sportsbook_projection_influence"] == 0.0
    assert result["page_wide_source_authority"] is False
    assert result["fabrication"] is False
    assert result["observations"] == [
        {
            "away_tricode": "LAL",
            "home_tricode": "PHX",
            "away_name": "Los Angeles Lakers",
            "home_name": "Phoenix Suns",
            "game_date_phoenix": "2026-10-20",
            "tip_phoenix": "7:00 PM",
            "status": "UPCOMING",
            "sharp_side_tricode": "PHX",
            "sharp_side_name": "Phoenix Suns",
            "public_bet_pct": 36,
            "money_pct": 52,
            "sharp_gap_pct": 16,
            "bet_count": 1420,
        }
    ]


def test_invalid_percentage_pair_fails_closed():
    module = _module()
    result = module.derive_verified_sharp_money_observations(
        _verified_payload(away_bet_pct=60, home_bet_pct=35), _schedule()
    )

    assert result["verification"] == "UNAVAILABLE"
    assert result["diagnostic_state"] == "INVALID_BETTING_SPLITS"
    assert result["observations"] == []


def test_missing_positive_absolute_volume_fails_closed():
    module = _module()
    result = module.derive_verified_sharp_money_observations(
        _verified_payload(bet_count=0), _schedule()
    )

    assert result["verification"] == "UNAVAILABLE"
    assert result["diagnostic_state"] == "SHARP_VOLUME_UNVERIFIED"
    assert result["observations"] == []


def test_completed_or_unmatched_games_are_not_eligible():
    module = _module()
    completed = module.derive_verified_sharp_money_observations(
        _verified_payload(), _schedule(status="FINAL")
    )
    unmatched_payload = _verified_payload(home_tricode="BOS")
    unmatched = module.derive_verified_sharp_money_observations(unmatched_payload, _schedule())

    assert completed["verification"] == "UNAVAILABLE"
    assert completed["diagnostic_state"] == "NO_VERIFIED_SCHEDULE_MATCH"
    assert unmatched["verification"] == "UNAVAILABLE"
    assert unmatched["diagnostic_state"] == "NO_VERIFIED_SCHEDULE_MATCH"


def test_no_positive_money_minus_bets_divergence_fails_closed():
    module = _module()
    result = module.derive_verified_sharp_money_observations(
        _verified_payload(
            away_bet_pct=50,
            home_bet_pct=50,
            away_money_pct=50,
            home_money_pct=50,
        ),
        _schedule(),
    )

    assert result["verification"] == "UNAVAILABLE"
    assert result["diagnostic_state"] == "NO_POSITIVE_SHARP_MONEY_DIVERGENCE"
    assert result["observations"] == []


def test_loader_reuses_step2_verified_transport_and_propagates_upstream_unavailable():
    module = _module()

    def unavailable_loader(schedule_games):
        assert schedule_games == _schedule()
        return {
            "verification": "UNAVAILABLE",
            "diagnostic_state": "ACTION_NETWORK_PROVIDER_ERROR:Timeout",
            "source": "Action Network",
            "observations": [],
            "fabrication": False,
            "page_wide_source_authority": False,
            "sportsbook_projection_influence": 0.0,
        }

    result = module.load_verified_sharp_money_observations(
        _schedule(), public_betting_loader=unavailable_loader
    )

    assert result["verification"] == "UNAVAILABLE"
    assert result["diagnostic_state"] == "UPSTREAM_PUBLIC_BETTING_UNAVAILABLE"
    assert result["observations"] == []
    assert result["upstream_diagnostic_state"] == "ACTION_NETWORK_PROVIDER_ERROR:Timeout"


def test_step3_preserves_zero_decision_layer_influence():
    module = _module()

    assert module.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert module.MAY_MODIFY_MODEL is False
    assert module.MAY_MODIFY_PROJECTION is False
    assert module.MAY_MODIFY_PROBABILITY is False
    assert module.MAY_ACTIVATE_RANKING is False
