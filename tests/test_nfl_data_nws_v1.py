from __future__ import annotations

from datetime import datetime, timezone

import pytest

from sports_api.nfl_data_nws_v1 import extract_grid_weather, fetch_environment
from sports_api.nfl_stadium_coordinates_v1 import STADIUMS, lookup_stadium


def test_stadium_table_covers_all_32_teams_with_valid_coordinates():
    teams = {entry["team"] for entry in STADIUMS}

    assert len(teams) == 32
    assert all(-90.0 <= float(entry["latitude"]) <= 90.0 for entry in STADIUMS)
    assert all(-180.0 <= float(entry["longitude"]) <= 180.0 for entry in STADIUMS)
    assert all(isinstance(entry["indoor"], bool) for entry in STADIUMS)


def test_shared_stadiums_resolve_to_identical_coordinates():
    jets = lookup_stadium("MetLife Stadium", "NYJ")
    giants = lookup_stadium("MetLife Stadium", "NYG")
    chargers = lookup_stadium("SoFi Stadium", "LAC")
    rams = lookup_stadium("SoFi Stadium", "LAR")

    assert jets is not None and giants is not None
    assert chargers is not None and rams is not None
    assert (jets["latitude"], jets["longitude"]) == (
        giants["latitude"],
        giants["longitude"],
    )
    assert (chargers["latitude"], chargers["longitude"]) == (
        rams["latitude"],
        rams["longitude"],
    )


def test_indoor_stadium_skips_nws_transport():
    def forbidden_network_call(url, **kwargs):
        raise AssertionError(f"indoor venue must not call NWS: {url}")

    result = fetch_environment(
        {
            "event_id": "x",
            "home_abbr": "DAL",
            "venue_name": "AT&T Stadium",
            "kickoff_utc": "2026-09-20T20:25:00Z",
        },
        get_json=forbidden_network_call,
    )

    assert result["ready"] is True
    assert result["provider"] == "NWS + canonical NFL stadium registry"
    assert result["data"]["indoor"] is True
    assert result["data"]["weather_applies"] is False
    assert result["data"]["weather_pressure"] == "INDOOR"


def _grid_payload() -> dict:
    return {
        "properties": {
            "temperature": {
                "uom": "wmoUnit:degC",
                "values": [
                    {
                        "validTime": "2026-09-20T18:00:00+00:00/PT2H",
                        "value": 30.0,
                    },
                    {
                        "validTime": "2026-09-20T20:00:00+00:00/PT1H",
                        "value": 22.2222222222,
                    },
                ],
            },
            "probabilityOfPrecipitation": {
                "uom": "wmoUnit:percent",
                "values": [
                    {
                        "validTime": "2026-09-20T20:00:00+00:00/PT1H",
                        "value": 20.0,
                    }
                ],
            },
            "windGust": {
                "uom": "wmoUnit:km_h-1",
                "values": [
                    {
                        "validTime": "2026-09-20T20:00:00+00:00/PT1H",
                        "value": 28.968192,
                    }
                ],
            },
        }
    }


def test_nws_grid_values_are_selected_for_kickoff_interval_and_converted():
    result = extract_grid_weather(
        _grid_payload(),
        datetime(2026, 9, 20, 20, 25, tzinfo=timezone.utc),
    )

    assert result["ready"] is True
    assert result["temperature"] == pytest.approx(72.0, abs=0.1)
    assert result["precipitation"] == pytest.approx(20.0, abs=0.1)
    assert result["gust"] == pytest.approx(18.0, abs=0.1)


def test_nws_grid_extraction_fails_closed_when_required_outdoor_field_missing():
    payload = _grid_payload()
    del payload["properties"]["windGust"]

    result = extract_grid_weather(
        payload,
        datetime(2026, 9, 20, 20, 25, tzinfo=timezone.utc),
    )

    assert result["ready"] is False
    assert result["gust"] is None
    assert any("gust" in item.lower() for item in result["diagnostics"])


def test_outdoor_environment_follows_points_forecast_grid_data_and_keeps_provenance():
    calls: list[str] = []

    def fake_get_json(url, **kwargs):
        calls.append(url)
        if url.startswith("https://api.weather.gov/points/"):
            return {
                "properties": {
                    "forecastGridData": "https://api.weather.gov/gridpoints/PHI/50,75"
                }
            }
        if url == "https://api.weather.gov/gridpoints/PHI/50,75":
            return _grid_payload()
        raise AssertionError(f"unexpected URL {url}")

    result = fetch_environment(
        {
            "event_id": "phi-test",
            "home_abbr": "PHI",
            "venue_name": "Lincoln Financial Field",
            "kickoff_utc": "2026-09-20T20:25:00Z",
        },
        get_json=fake_get_json,
    )

    assert result["ready"] is True
    assert result["provider"] == "NWS + canonical NFL stadium registry"
    assert result["quality"] == "HIGH"
    assert result["data"]["indoor"] is False
    assert result["data"]["weather_applies"] is True
    assert result["data"]["temperature"] == pytest.approx(72.0, abs=0.1)
    assert result["fields_verified"] == [
        "venue_name",
        "indoor",
        "temperature",
        "precipitation",
        "gust",
    ]
    assert len(calls) == 2
    assert calls[0].startswith("https://api.weather.gov/points/")
    assert calls[1] == "https://api.weather.gov/gridpoints/PHI/50,75"


def test_outdoor_environment_fails_closed_when_kickoff_weather_is_incomplete():
    def fake_get_json(url, **kwargs):
        if url.startswith("https://api.weather.gov/points/"):
            return {
                "properties": {
                    "forecastGridData": "https://api.weather.gov/gridpoints/PHI/50,75"
                }
            }
        payload = _grid_payload()
        del payload["properties"]["probabilityOfPrecipitation"]
        return payload

    result = fetch_environment(
        {
            "event_id": "phi-test",
            "home_abbr": "PHI",
            "venue_name": "Lincoln Financial Field",
            "kickoff_utc": "2026-09-20T20:25:00Z",
        },
        get_json=fake_get_json,
    )

    assert result["ready"] is False
    assert result["data"] == {}
    assert any("precipitation" in item.lower() for item in result["diagnostics"])
