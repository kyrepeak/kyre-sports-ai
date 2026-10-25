import pytest


def test_posted_source_data_cannot_become_false_blank():
    from devsystem.api2_step2d_data_truth_gate_v1 import evaluate_field
    result = evaluate_field({
        "requested_field": "nfl.player.rushing_yards",
        "source_observations": [{"provider": "fanduel", "reachable": True, "parsed": True, "matched": True, "fresh": True, "present": True, "value": 37.5}],
        "api_value": 37.5,
        "frontend_value": 37.5,
    })
    assert result["allowed"] is True
    assert result["state"] == "AVAILABLE"


def test_fetch_or_parser_failure_never_means_market_not_posted():
    from devsystem.api2_step2d_data_truth_gate_v1 import evaluate_field
    for observation, expected in [
        ({"provider":"fanduel","reachable":False}, "PROVIDER_FETCH_FAILURE"),
        ({"provider":"fanduel","reachable":True,"parsed":False}, "PARSER_FAILURE"),
        ({"provider":"fanduel","reachable":True,"parsed":True,"matched":False}, "MAPPING_FAILURE"),
    ]:
        result=evaluate_field({"requested_field":"nfl.player.rushing_yards","source_observations":[observation],"api_state":"MARKET_NOT_POSTED","frontend_state":"LINE_PENDING"})
        assert result["allowed"] is False
        assert result["state"] == expected


def test_verified_not_posted_requires_successful_reach_parse_match_and_freshness():
    from devsystem.api2_step2d_data_truth_gate_v1 import evaluate_field
    good={"provider":"fanduel","reachable":True,"parsed":True,"matched":True,"fresh":True,"present":False}
    result=evaluate_field({"requested_field":"nfl.player.rushing_yards","source_observations":[good],"api_state":"VERIFIED_NOT_POSTED","frontend_state":"LINE_PENDING"})
    assert result["allowed"] is True
    assert result["state"] == "VERIFIED_NOT_POSTED"


def test_primary_failure_requires_approved_fallback_before_empty_state():
    from devsystem.api2_step2d_data_truth_gate_v1 import evaluate_field
    result=evaluate_field({
        "requested_field":"nfl.player.rushing_yards",
        "source_observations":[{"provider":"fanduel","reachable":False},{"provider":"draftkings","approved_fallback":True,"reachable":True,"parsed":True,"matched":True,"fresh":True,"present":True,"value":38.5}],
        "api_value":38.5,"frontend_value":38.5,
    })
    assert result["allowed"] is True
    assert result["state"] == "AVAILABLE"
    assert result["resolved_provider"] == "draftkings"


def test_failure_or_unverified_negative_must_not_be_negative_cached():
    from devsystem.api2_step2d_data_truth_gate_v1 import negative_cache_allowed
    assert negative_cache_allowed("PROVIDER_FETCH_FAILURE") is False
    assert negative_cache_allowed("PARSER_FAILURE") is False
    assert negative_cache_allowed("VERIFIED_NOT_POSTED") is True


def test_no_fabrication_and_end_to_end_value_must_match():
    from devsystem.api2_step2d_data_truth_gate_v1 import evaluate_field
    source={"provider":"fanduel","reachable":True,"parsed":True,"matched":True,"fresh":True,"present":True,"value":37.5}
    result=evaluate_field({"requested_field":"nfl.player.rushing_yards","source_observations":[source],"api_value":40.5,"frontend_value":40.5})
    assert result["allowed"] is False
    assert result["state"] == "DATA_TRUTH_MISMATCH"
