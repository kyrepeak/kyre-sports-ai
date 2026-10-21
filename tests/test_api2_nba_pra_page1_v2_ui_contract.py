from datetime import datetime, timezone
from pathlib import Path

from nba_pra_page1_ui_v2 import build_game_card_html, build_player_card_html, dashboard_kpis, freshness_label

NOW = datetime(2026, 10, 20, 20, 45, tzinfo=timezone.utc)


def sample_item():
    return {
        "key":"devinbooker","player_name":"Devin Booker","team":"PHX","position":"G",
        "headshot":"https://cdn.nba.com/headshots/nba/latest/1040x760/201.png","stats_source":"NBA Stats","availability":"AVAILABLE",
        "quotes":[
            {"sportsbook":"FanDuel","line":38.5,"over_price":-110,"under_price":-110,"provider":"SportsGameOdds","observed_at_utc":"2026-10-20T20:44:20Z"},
            {"sportsbook":"DraftKings","line":39.5,"over_price":-105,"under_price":-115,"provider":"Odds-API.io","observed_at_utc":"2026-10-20T20:44:10Z"},
        ],
        "featured_quote":{"sportsbook":"FanDuel","line":38.5,"over_price":-110,"under_price":-110,"provider":"SportsGameOdds","observed_at_utc":"2026-10-20T20:44:20Z"},
        "model":{"projection":41.2,"current":{"sample":8,"l5":42.3,"l10":40.6,"minutes":36.4},"prior":{"sample":70,"l10":39.8},"basis":"CURRENT_PLUS_PRIOR"},
        "grade":{"edge":2.7,"over_probability":0.67,"lean":"OVER","confidence":"HIGH"},
    }


def test_player_card_is_professional_and_preserves_each_book_quote():
    html=build_player_card_html(sample_item(),rank=1,now_utc=NOW)
    for text in ("Devin Booker","PHX","PRA LINE","38.5","KYRE AI","41.2","67%","OVER","HIGH","NBA Stats","WHY THE MODEL LIKES IT"):
        assert text in html
    assert "FanDuel" in html and "38.5" in html and "-110" in html
    assert "DraftKings" in html and "39.5" in html and "-105" in html and "-115" in html
    assert "39.0" not in html
    assert "Updated 40 sec ago" in html


def test_game_card_is_compact_upcoming_matchup_with_team_logos():
    html=build_game_card_html({"away_tricode":"LAL","home_tricode":"PHX","tip_phoenix":"7:00 PM MST","venue":"Footprint Center","gameStatus":1,"gameStatusText":"Scheduled"})
    assert "LAL" in html and "PHX" in html and "UPCOMING" in html and "7:00 PM MST" in html and "Footprint Center" in html
    assert "teamlogos/nba/500/lal.png" in html and "teamlogos/nba/500/phx.png" in html


def test_dashboard_kpis_surface_market_quality_not_decorative_numbers():
    items=[sample_item(),{**sample_item(),"key":"kevindurant","player_name":"Kevin Durant","grade":{"edge":-3.1,"over_probability":0.35,"lean":"UNDER","confidence":"HIGH"}}]
    kpis=dashboard_kpis(items,now_utc=NOW)
    assert kpis == {"players_tracked":2,"best_over_edge":2.7,"best_under_edge":-3.1,"fresh_quotes":2}


def test_freshness_is_explicit_and_missing_timestamp_never_guessed():
    assert freshness_label("2026-10-20T20:44:20Z",NOW) == ("Updated 40 sec ago","fresh")
    assert freshness_label("2026-10-20T20:35:00Z",NOW) == ("Updated 10 min ago","stale")
    assert freshness_label("",NOW) == ("Timestamp unavailable","unknown")


def test_runtime_terminal_hands_nba_pra_to_v2_without_changing_other_routes():
    text=Path("streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1.py").read_text()
    assert "nba_pra_page1_v2" in text
    assert "render_nba_pra_page1_v2" in text
    assert 'route.sport_id == "nba" and route.market_id == "pra"' in text
    assert "return _v1_resolve_destination(route)" in text


def test_source_diagnostics_are_specific_and_never_expose_secret_material():
    from nba_pra_page1_v2 import source_diagnostic_summary
    snapshot={"sources":{
        "kyre_sports_api":{"verification":"UNAVAILABLE","diagnostic_state":"KYRE_VERCEL_SGO_CREDENTIAL_UNAVAILABLE","api_key":"DO-NOT-LEAK"},
        "sgo":{"verification":"UNAVAILABLE","diagnostic_state":"SGO_CREDENTIAL_UNAVAILABLE","credential":"DO-NOT-LEAK"},
        "odds_api":{"verification":"VERIFIED","diagnostic_state":"OK","secret":"DO-NOT-LEAK"},
    }}
    diag=source_diagnostic_summary(snapshot)
    assert diag == {
        "runtime_marker":"NBA_PRA_SOURCE_DIAGNOSTICS_V1",
        "kyre_sports_api":"UNAVAILABLE • KYRE_VERCEL_SGO_CREDENTIAL_UNAVAILABLE",
        "sgo":"UNAVAILABLE • SGO_CREDENTIAL_UNAVAILABLE",
        "odds_api":"VERIFIED • OK",
    }
    assert "DO-NOT-LEAK" not in repr(diag)


def test_all_upcoming_markets_render_when_best_edges_is_empty(monkeypatch):
    import sys
    import types
    import nba_pra_page1_v2 as page

    snapshot = {
        "games": [{"away_tricode": "ATL", "home_tricode": "ORL", "tip_phoenix": "7:00 PM MST"}],
        "slate_date": "2026-10-21",
        "market": {
            "testplayer": {
                "player_name": "Test Player",
                "featured_quote": {
                    "sportsbook": "FanDuel",
                    "line": 25.5,
                    "over_price": -110,
                    "under_price": -110,
                    "provider": "FanDuel",
                    "observed_at_utc": "2026-10-21T03:00:00Z",
                },
                "quotes": [{
                    "sportsbook": "FanDuel",
                    "line": 25.5,
                    "over_price": -110,
                    "under_price": -110,
                    "provider": "FanDuel",
                    "observed_at_utc": "2026-10-21T03:00:00Z",
                }],
            }
        },
        "profiles": {"testplayer": {"player_name": "Test Player", "team": "ATL"}},
        "injury_players": {},
        "sources": {},
    }

    monkeypatch.setattr(page, "load_page1_snapshot_v2", lambda now: snapshot)
    monkeypatch.setattr(page, "project_pra", lambda *_args, **_kwargs: {
        "projection": None, "sigma": None, "current": {}, "prior": {}, "basis": "UNAVAILABLE"
    })
    monkeypatch.setattr(page, "grade_market", lambda *_args, **_kwargs: {
        "edge": None, "over_probability": None, "lean": "HOLD", "confidence": "LOW"
    })

    rendered = []

    class _Context:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False

    fake = types.SimpleNamespace()
    fake.session_state = {}
    fake.markdown = lambda html, **_kwargs: rendered.append(str(html))
    fake.spinner = lambda *_args, **_kwargs: _Context()
    fake.expander = lambda *_args, **_kwargs: _Context()
    fake.columns = lambda count: [_Context() for _ in range(count)]
    fake.radio = lambda *_args, **_kwargs: "BEST EDGES"
    fake.button = lambda *_args, **_kwargs: False
    fake.caption = lambda *_args, **_kwargs: None
    fake.write = lambda *_args, **_kwargs: None
    fake.warning = lambda *_args, **_kwargs: None
    fake.info = lambda *_args, **_kwargs: None
    monkeypatch.setitem(sys.modules, "streamlit", fake)

    page.render_nba_pra_page1_v2()

    assert any("np2-player-card" in html and "Test Player" in html for html in rendered)
