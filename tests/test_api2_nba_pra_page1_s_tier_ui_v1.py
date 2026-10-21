from datetime import date, datetime, timezone
from pathlib import Path


def _rows(provider="FanDuel"):
    base = {
        "provider": provider,
        "provider_event_id": "phx-lal",
        "provider_player_id": "devin-booker",
        "player_name": "Devin Booker",
        "sportsbook": "FanDuel",
        "line": 38.5,
        "observed_at_utc": "2026-10-21T03:40:00Z",
        "away_team": "Phoenix Suns",
        "home_team": "Los Angeles Lakers",
    }
    return [
        {**base, "side": "over", "price": -110},
        {**base, "side": "under", "price": -110},
    ]


def _item():
    return {
        "key": "devinbooker",
        "player_name": "Devin Booker",
        "team": "PHX",
        "position": "G",
        "headshot": "https://cdn.nba.com/headshots/nba/latest/1040x760/1626164.png",
        "stats_source": "NBA Stats",
        "availability": "AVAILABLE",
        "quotes": [
            {
                "sportsbook": "FanDuel",
                "line": 38.5,
                "over_price": -110,
                "under_price": -110,
                "provider": "FanDuel",
                "observed_at_utc": "2026-10-21T03:40:00Z",
            },
            {
                "sportsbook": "DraftKings",
                "line": 39.5,
                "over_price": -105,
                "under_price": -115,
                "provider": "Kyre Sports API",
                "observed_at_utc": "2026-10-21T03:39:30Z",
            },
        ],
        "featured_quote": {
            "sportsbook": "FanDuel",
            "line": 38.5,
            "over_price": -110,
            "under_price": -110,
            "provider": "FanDuel",
            "observed_at_utc": "2026-10-21T03:40:00Z",
        },
        "model": {
            "projection": 42.1,
            "current": {"sample": 8, "l5": 42.3, "l10": 40.6, "minutes": 36.4},
            "prior": {"sample": 70, "l10": 39.8},
            "basis": "CURRENT_PLUS_PRIOR",
        },
        "grade": {"edge": 3.6, "over_probability": 0.64, "lean": "OVER", "confidence": "HIGH"},
    }


def test_player_card_has_headshot_team_logo_and_kyre_edge_score():
    from nba_pra_page1_ui_v2 import build_player_card_html

    html = build_player_card_html(
        _item(),
        rank=1,
        now_utc=datetime(2026, 10, 21, 3, 40, 30, tzinfo=timezone.utc),
    )

    assert "1626164.png" in html
    assert "teamlogos/nba/500/phx.png" in html
    assert "KYRE EDGE SCORE" in html
    assert "8.2" in html
    assert "STRONG" in html
    assert "FanDuel" in html and "38.5" in html and "-110" in html
    assert "DraftKings" in html and "39.5" in html and "-105" in html and "-115" in html
    assert "39.0" not in html


def test_source_diagnostics_surface_only_kyre_sports_api():
    from nba_pra_page1_v2 import source_diagnostic_summary

    snapshot = {
        "sources": {
            "kyre_sports_api": {"verification": "VERIFIED", "diagnostic_state": "OK"},
            "sgo": {"verification": "VERIFIED", "diagnostic_state": "SHOULD_NOT_SURFACE"},
            "odds_api": {"verification": "VERIFIED", "diagnostic_state": "SHOULD_NOT_SURFACE"},
        }
    }
    assert source_diagnostic_summary(snapshot) == {
        "runtime_marker": "NBA_PRA_SOURCE_DIAGNOSTICS_V1",
        "kyre_sports_api": "VERIFIED • OK",
    }


def test_live_page_imports_api_only_router_not_legacy_market_router():
    source = Path("nba_pra_page1_v2.py").read_text(encoding="utf-8")
    assert "from nba_pra_page1_api_only_v1 import load_page1_snapshot_v2" in source
    assert "from nba_pra_page1_data_v2 import load_page1_snapshot_v2" not in source


def test_streamlit_client_never_sends_sgo_credential_even_if_argument_is_supplied():
    import nba_pra_market_api_v1 as client

    seen = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "service": "Kyre Sports API — Vercel",
                "ready": True,
                "observations": _rows(),
                "projection_weight": 0.0,
                "consensus_averaging": False,
            }

    def fake_post(url, **kwargs):
        seen["url"] = url
        seen["json"] = dict(kwargs["json"])
        return Response()

    result = client.load_kyre_sports_api_pra_observations(
        date(2026, 10, 21), api_key="must-not-leave-streamlit", request_post=fake_post
    )

    assert seen["url"].endswith("/api/v1/nba/pra/market")
    assert seen["json"] == {"date": "2026-10-21"}
    assert result["verification"] == "VERIFIED"


def test_page1_does_not_call_direct_sgo_or_direct_odds_when_kyre_api_is_unavailable():
    import nba_pra_page1_api_only_v1 as data

    game = {
        "away_tricode": "PHX",
        "home_tricode": "LAL",
        "away_name": "Phoenix Suns",
        "home_name": "Los Angeles Lakers",
        "status": "UPCOMING",
        "gameStatus": 1,
        "tip_utc": "2026-10-22T02:00:00Z",
        "game_date_phoenix": "2026-10-21",
    }

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Page 1 must use Kyre Sports API only")

    snapshot = data.load_page1_snapshot_v2(
        now=datetime(2026, 10, 21, 20, 0, tzinfo=timezone.utc),
        schedule_loader=lambda **_kwargs: {"verification": "VERIFIED", "games": [game]},
        api_loader=lambda _day: {
            "source": "Kyre Sports API — Vercel",
            "verification": "UNAVAILABLE",
            "diagnostic_state": "NO_PRA",
            "observations": [],
        },
        sgo_loader=forbidden,
        odds_loader=forbidden,
        official_profile_loader=lambda _day: {},
        backup_profile_loader=lambda *_args: {},
        injury_loader=lambda *_args, **_kwargs: {"verification": "VERIFIED", "features": []},
    )

    assert snapshot.get("market") == {}
    assert snapshot["sources"]["kyre_sports_api"]["verification"] == "UNAVAILABLE"


def test_active_kyre_api_request_path_never_reaches_sgo_without_provider_key(monkeypatch):
    import runless_v2.nba_pra_market_v1 as api

    monkeypatch.setattr(api, "_fetch_fanduel_pra_observations", lambda _day: ([], "FANDUEL_NO_PRA"))

    def forbidden(*_args, **_kwargs):
        raise AssertionError("SGO fallback is forbidden on the active Page 1 request path")

    monkeypatch.setattr(api, "_fetch_sgo_events", forbidden)
    payload = api.collect_nba_pra_market(date(2026, 10, 21), api_key=None)

    assert payload["observations"] == []
    assert payload["verification"] == "UNAVAILABLE"
    assert payload["diagnostic_state"] == "FANDUEL_NO_PRA"
    assert payload["projection_weight"] == 0.0
    assert payload["consensus_averaging"] is False
