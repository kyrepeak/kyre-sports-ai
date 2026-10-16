from __future__ import annotations

import importlib


def _schedule():
    return [
        {
            "game_key": "LAL@PHX:2026-10-20",
            "away_tricode": "LAL",
            "home_tricode": "PHX",
            "away_name": "Los Angeles Lakers",
            "home_name": "Phoenix Suns",
            "game_date_phoenix": "2026-10-20",
            "tip_phoenix": "7:00 PM",
            "status": "UPCOMING",
        }
    ]


def _public_payload():
    return {
        "verification": "VERIFIED",
        "diagnostic_state": "OK",
        "source": "Action Network",
        "observations": [
            {
                "away_tricode": "LAL",
                "home_tricode": "PHX",
                "bet_count": 12500,
                "away_bet_pct": 41,
                "home_bet_pct": 59,
                "away_money_pct": 62,
                "home_money_pct": 38,
            }
        ],
        "fabrication": False,
        "page_wide_source_authority": False,
    }


def _market_payload():
    return {
        "verification": "VERIFIED",
        "diagnostic_state": "OK",
        "source": "SportsGameOdds",
        "observations": [
            {"away_tricode": "LAL", "home_tricode": "PHX", "sportsbook": "DraftKings", "away_spread": 2.5, "home_spread": -2.5},
            {"away_tricode": "LAL", "home_tricode": "PHX", "sportsbook": "FanDuel", "away_spread": 3.0, "home_spread": -3.0},
        ],
        "fabrication": False,
        "page_wide_source_authority": False,
    }


def test_one_verified_public_payload_drives_most_bet_and_sharp_money_without_substitution():
    repair = importlib.import_module("nba_spread_live_data_repair_v1")
    bundle = repair.build_public_betting_features(_schedule(), payload=_public_payload())

    assert bundle["most_bet"]["verification"] == "VERIFIED"
    assert bundle["most_bet"]["bet_count"] == 12500
    assert bundle["most_bet"]["source"] == "Action Network"
    assert bundle["sharp_money"]["verification"] == "VERIFIED"
    assert bundle["sharp_money"]["sharp_side_tricode"] == "LAL"
    assert bundle["sharp_money"]["sharp_gap_pct"] == 21
    assert bundle["sharp_money"]["bet_count"] == 12500
    assert bundle["fabrication"] is False
    assert bundle["metric_substitution"] is False


def test_public_provider_failure_fails_closed_for_both_features():
    repair = importlib.import_module("nba_spread_live_data_repair_v1")
    bundle = repair.build_public_betting_features(
        _schedule(),
        payload={
            "verification": "UNAVAILABLE",
            "diagnostic_state": "ACTION_NETWORK_PROVIDER_ERROR:TimeoutError",
            "source": "Action Network",
            "observations": [],
        },
    )

    assert bundle["most_bet"]["verification"] == "UNAVAILABLE"
    assert bundle["sharp_money"]["verification"] == "UNAVAILABLE"
    assert bundle["fabrication"] is False
    assert bundle["metric_substitution"] is False


def test_verified_multi_book_market_payload_builds_consensus_context():
    repair = importlib.import_module("nba_spread_live_data_repair_v1")
    result = repair.build_market_feature(_schedule(), payload=_market_payload())

    assert result["verification"] == "VERIFIED"
    assert result["sportsbook_count"] == 2
    assert result["consensus_home_spread"] == -2.75
    assert result["consensus_away_spread"] == 2.75
    assert result["source"] == "SportsGameOdds"
    assert result["fabrication"] is False


def test_market_provider_failure_fails_closed_without_guessing():
    repair = importlib.import_module("nba_spread_live_data_repair_v1")
    result = repair.build_market_feature(
        _schedule(),
        payload={
            "verification": "UNAVAILABLE",
            "diagnostic_state": "SPORTSGAMEODDS_CREDENTIAL_UNAVAILABLE",
            "source": "SportsGameOdds",
            "observations": [],
        },
    )

    assert result["verification"] == "UNAVAILABLE"
    assert result["diagnostic_state"] == "SPORTSGAMEODDS_CREDENTIAL_UNAVAILABLE"
    assert result["fabrication"] is False


def test_page_v6_is_additive_over_frozen_step10_and_router_targets_it():
    page = importlib.import_module("nba_spread_page_v6")
    router = importlib.import_module("streamlit_memory_lazy_router_nba_spread_step2_activation_v1")

    assert page.FROZEN_PARENT_PAGE == "nba_spread_page_v5"
    assert page.MAY_MODIFY_MODEL is False
    assert page.MAY_MODIFY_PROJECTION is False
    assert page.MAY_MODIFY_PROBABILITY is False
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router.STEP10_REPAIRED_PAGE == "nba_spread_page_v6"


def test_runtime_secret_discovery_supports_streamlit_secret_and_env_paths():
    repair = importlib.import_module("nba_spread_live_data_repair_v1")

    class _Secrets(dict):
        pass

    class _Session(dict):
        pass

    assert repair.resolve_sgo_api_key(
        session_state=_Session({"ks_sportsgameodds_key": "session-key"}),
        secrets=_Secrets({"SPORTSGAMEODDS_API_KEY": "secret-key"}),
        environ={"SPORTSGAMEODDS_API_KEY": "env-key"},
    ) == "session-key"
    assert repair.resolve_sgo_api_key(
        session_state=_Session(),
        secrets=_Secrets({"SPORTSGAMEODDS_API_KEY": "secret-key"}),
        environ={"SPORTSGAMEODDS_API_KEY": "env-key"},
    ) == "secret-key"
    assert repair.resolve_sgo_api_key(
        session_state=_Session(),
        secrets=_Secrets(),
        environ={"SPORTSGAMEODDS_KEY": "env-alias"},
    ) == "env-alias"
