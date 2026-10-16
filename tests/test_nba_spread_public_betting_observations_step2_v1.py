from __future__ import annotations

import importlib


MODULE_NAME = "nba_spread_public_betting_observations_v1"


def _module():
    return importlib.import_module(MODULE_NAME)


def _schedule():
    return [
        {
            "away_tricode": "LAL",
            "home_tricode": "PHX",
            "away_name": "Los Angeles Lakers",
            "home_name": "Phoenix Suns",
            "status": "UPCOMING",
        },
        {
            "away_tricode": "BOS",
            "home_tricode": "NYK",
            "away_name": "Boston Celtics",
            "home_name": "New York Knicks",
            "status": "FINAL",
        },
    ]


class _Response:
    def __init__(self, text: str, *, status_code: int = 200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _html(*, bets: str = "67%33%", money: str = "62%38%", count: str = "12,500") -> str:
    return f"""
    <table>
      <thead><tr>
        <th>Scheduled</th><th>Open</th><th>Best Odds</th><th>% of Bets</th>
        <th>% of Money</th><th>Diff</th><th>Bets</th>
      </tr></thead>
      <tbody>
        <tr>
          <td>7:00 PM Lakers LAL 1 Suns PHX 2</td><td>-1.5 +1.5</td><td>-2.5 -110 +2.5 -110</td>
          <td>{bets}</td><td>{money}</td><td>+5%</td><td>{count}</td>
        </tr>
        <tr>
          <td>7:30 PM Celtics BOS 1 Knicks NYK 2</td><td>-2 +2</td><td>-2 -110 +2 -110</td>
          <td>55%45%</td><td>52%48%</td><td>+3%</td><td>99,999</td>
        </tr>
      </tbody>
    </table>
    """


def test_loads_only_exact_verified_upcoming_schedule_match_with_absolute_volume():
    module = _module()
    calls = []

    def fake_get(url, *, headers, timeout):
        calls.append((url, headers, timeout))
        return _Response(_html())

    result = module.load_verified_public_betting_observations(_schedule(), request_get=fake_get)

    assert result["verification"] == "VERIFIED"
    assert result["source"] == "Action Network"
    assert result["page_wide_source_authority"] is False
    assert result["fabrication"] is False
    assert result["observations"] == [
        {
            "away_tricode": "LAL",
            "home_tricode": "PHX",
            "bet_count": 12500,
            "away_bet_pct": 67,
            "home_bet_pct": 33,
            "away_money_pct": 62,
            "home_money_pct": 38,
        }
    ]
    assert calls and calls[0][0] == module.ACTION_PUBLIC_BETTING_URL


def test_rejects_invalid_percentage_pairs_instead_of_normalizing_or_guessing():
    module = _module()

    def fake_get(url, *, headers, timeout):
        return _Response(_html(bets="80%30%"))

    result = module.load_verified_public_betting_observations(_schedule(), request_get=fake_get)
    assert result["verification"] == "UNAVAILABLE"
    assert result["diagnostic_state"] == "ACTION_NETWORK_NO_VERIFIED_PUBLIC_BETTING_ROWS"
    assert result["observations"] == []


def test_rejects_missing_or_nonpositive_absolute_bet_count():
    module = _module()

    for count in ("", "0"):
        def fake_get(url, *, headers, timeout, _count=count):
            return _Response(_html(count=_count))

        result = module.load_verified_public_betting_observations(_schedule(), request_get=fake_get)
        assert result["verification"] == "UNAVAILABLE"
        assert result["diagnostic_state"] == "ACTION_NETWORK_NO_VERIFIED_PUBLIC_BETTING_ROWS"
        assert result["observations"] == []


def test_provider_failure_fails_closed_without_fabrication():
    module = _module()

    def fake_get(url, *, headers, timeout):
        raise TimeoutError("boom")

    result = module.load_verified_public_betting_observations(_schedule(), request_get=fake_get)
    assert result == {
        "source": "Action Network",
        "verification": "UNAVAILABLE",
        "diagnostic_state": "ACTION_NETWORK_PROVIDER_ERROR:TimeoutError",
        "observations": [],
        "fabrication": False,
        "page_wide_source_authority": False,
        "sportsbook_projection_influence": 0.0,
    }


def test_contract_never_activates_decision_layers():
    module = _module()
    assert module.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert module.MAY_MODIFY_MODEL is False
    assert module.MAY_MODIFY_PROJECTION is False
    assert module.MAY_MODIFY_PROBABILITY is False
    assert module.MAY_ACTIVATE_RANKING is False
