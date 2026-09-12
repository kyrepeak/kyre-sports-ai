from __future__ import annotations

import pytest

from sports_api.collectors import nfl_fanduel_passing_yards as base
from sports_api.collectors import nfl_passing_yards_render_espn_v2 as hosted


def test_summary_transport_falls_back_to_official_site_web_domain(monkeypatch):
    calls: list[str] = []
    expected = {"header": {"id": "401872925"}}

    def fake_get(url, params=None, *, headers=None, timeout=20):
        calls.append(url)
        if url.startswith("https://site.api.espn.com/"):
            raise base.NFLPassingYardsCollectorError("read-only upstream GET failed: HTTPError")
        if url.startswith("https://site.web.api.espn.com/"):
            return expected
        raise AssertionError(url)

    monkeypatch.setattr(base, "_get_json", fake_get)
    payload, source = hosted.fetch_espn_event_summary_hosted("401872925")
    assert payload is expected
    assert source.startswith("https://site.web.api.espn.com/")
    assert calls == [
        "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary",
        "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/summary",
    ]


def test_roster_transport_falls_back_to_official_site_web_domain(monkeypatch):
    calls: list[str] = []
    expected = {"athletes": []}

    def fake_get(url, params=None, *, headers=None, timeout=20):
        calls.append(url)
        if url.startswith("https://site.api.espn.com/"):
            raise base.NFLPassingYardsCollectorError("read-only upstream GET failed: HTTPError")
        if url.startswith("https://site.web.api.espn.com/"):
            return expected
        raise AssertionError(url)

    monkeypatch.setattr(base, "_get_json", fake_get)
    payload, source = hosted.fetch_espn_team_roster_hosted("27")
    assert payload is expected
    assert source.startswith("https://site.web.api.espn.com/")
    assert calls == [
        "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/27/roster",
        "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/teams/27/roster",
    ]


def test_both_official_espn_transports_fail_closed(monkeypatch):
    def fail(*args, **kwargs):
        raise base.NFLPassingYardsCollectorError("read-only upstream GET failed: HTTPError")

    monkeypatch.setattr(base, "_get_json", fail)
    with pytest.raises(base.NFLPassingYardsCollectorError, match="official ESPN transport failed closed"):
        hosted.fetch_espn_event_summary_hosted("401872925")


def test_non_numeric_identity_never_reaches_transport(monkeypatch):
    monkeypatch.setattr(base, "_get_json", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not fetch")))
    with pytest.raises(base.NFLPassingYardsCollectorError, match="numeric"):
        hosted.fetch_espn_event_summary_hosted("TB-CIN")
    with pytest.raises(base.NFLPassingYardsCollectorError, match="numeric"):
        hosted.fetch_espn_team_roster_hosted("TB")
