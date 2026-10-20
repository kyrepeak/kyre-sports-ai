from pathlib import Path
import importlib.util
import math

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    path = ROOT / f"{name}.py"
    assert path.exists(), f"missing production module: {path.name}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_market_loaders_fail_closed_without_credentials_and_do_not_call_network():
    from datetime import date
    data = _load("nba_pra_page1_data_v1")
    def forbidden(*args, **kwargs):
        raise AssertionError("network must not be called without credentials")
    sgo = data.load_sgo_pra_observations(date(2026,10,20), request_get=forbidden, secret_getter=lambda _: None)
    odds = data.load_odds_api_pra_observations(date(2026,10,20), request_get=forbidden, secret_getter=lambda _: None)
    assert sgo["verification"] == "UNAVAILABLE"
    assert odds["verification"] == "UNAVAILABLE"
    assert sgo["observations"] == [] and odds["observations"] == []


def test_odds_api_parser_ignores_non_pra_markets():
    data = _load("nba_pra_page1_data_v1")
    payload = {"data":[
        {"market":"Player Points Rebounds Assists","playerName":"Test Guard","bookmaker":"FanDuel","outcomes":[{"name":"Over","point":39.5,"price":-110},{"name":"Under","point":39.5,"price":-110}]},
        {"market":"Player Points","playerName":"Test Guard","bookmaker":"FanDuel","outcomes":[{"name":"Over","point":25.5,"price":-110}]},
    ]}
    rows = data.normalize_odds_api_pra(payload)
    assert len(rows) == 2
    assert {r["side"] for r in rows} == {"over","under"}
    assert all(r["provider"] == "Odds-API.io" for r in rows)


def test_sgo_filter_uses_documented_combo_stat_and_oddids_shape():
    data = _load("nba_pra_page1_data_v1")
    assert data.build_sgo_odd_id_filter() == (
        "points+rebounds+assists-PLAYER_ID-game-ou-over,"
        "points+rebounds+assists-PLAYER_ID-game-ou-under"
    )


def test_odds_api_nested_player_props_shape_normalizes_pra_and_decimal_prices():
    data = _load("nba_pra_page1_data_v1")
    payload = {"bookmakers":{"DraftKings":[{"name":"Player Props","updatedAt":"2026-10-20T15:00:00Z","odds":[
        {"label":"Test Guard - Points + Rebounds + Assists","hdp":39.5,"over":"1.91","under":"1.91"},
        {"label":"Test Guard - Points","hdp":25.5,"over":"1.91","under":"1.91"},
    ]}]}}
    rows = data.normalize_odds_api_pra(payload)
    assert len(rows) == 2
    assert {r["side"] for r in rows} == {"over","under"}
    assert {r["sportsbook"] for r in rows} == {"DraftKings"}
    assert {r["line"] for r in rows} == {39.5}
    assert {r["price"] for r in rows} == {-110}
    assert {r["player_name"] for r in rows} == {"Test Guard"}


def test_odds_api_loader_uses_per_event_player_props_endpoint():
    from datetime import date
    data = _load("nba_pra_page1_data_v1")
    calls=[]
    class Resp:
        def __init__(self,payload): self.payload=payload
        def raise_for_status(self): pass
        def json(self): return self.payload
    def fake_get(url, params=None, timeout=None, **kwargs):
        calls.append((url,dict(params or {})))
        if url.endswith('/events'):
            return Resp({"data":[{"id":"evt1"}]})
        assert url.endswith('/odds')
        return Resp({"bookmakers":{"FanDuel":[{"name":"Player Props","odds":[{"label":"Test Guard - Points + Rebounds + Assists","hdp":39.5,"over":"1.91","under":"1.91"}]}]}})
    result=data.load_odds_api_pra_observations(date(2026,10,20),request_get=fake_get,secret_getter=lambda _:"x")
    assert result["verification"] == "VERIFIED"
    assert len(result["observations"]) == 2
    assert calls[1][0].endswith('/odds')
    assert calls[1][1]["eventId"] == "evt1"
    assert calls[1][1]["markets"] == "Player Props"


def test_phoenix_date_controls_automatic_slate_boundary():
    from datetime import datetime, timezone
    data = _load("nba_pra_page1_data_v1")
    assert data.phoenix_date(datetime(2026,10,20,6,0,tzinfo=timezone.utc)).isoformat() == "2026-10-19"
    assert data.phoenix_date(datetime(2026,10,20,8,0,tzinfo=timezone.utc)).isoformat() == "2026-10-20"


def test_page1_has_tap_filters_and_horizontal_game_strip():
    source=(ROOT/'nba_pra_page1_v1.py').read_text(encoding='utf-8') + (ROOT/'nba_pra_page1_ui_v1.py').read_text(encoding='utf-8')
    for label in ('ALL PLAYERS','TOP EDGES','OVER','UNDER','HIGH CONFIDENCE'):
        assert label in source
    assert 'horizontal=True' in source
    assert 'overflow-x:auto' in source
