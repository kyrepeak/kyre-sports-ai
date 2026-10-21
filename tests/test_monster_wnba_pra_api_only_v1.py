from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _offer(book="FanDuel", *, player="Allisha Gray", side="over", line=31.5, odds=-110, teams=True):
    row = {
        "sportsbook": book,
        "player_name": player,
        "stat": "pra",
        "side": side,
        "line": line,
        "american_odds": odds,
        "market_captured_at_utc": "2026-10-21T15:00:00+00:00",
        "source_event_id": "evt-1",
    }
    if teams:
        row.update({"away_team": "Golden State Valkyries", "home_team": "Atlanta Dream"})
    return row


def test_draftkings_transport_is_lazy_optional_fallback_dependency():
    source = (ROOT / "sports_api/wnba_pra_market_gateway_v1.py").read_text(encoding="utf-8")
    marker = "from sports_api.wnba_step19a_draftkings_sportscontent import build_step19a_draftkings_snapshot"
    assert marker in source
    assert source.index("def _default_draftkings") < source.index(marker)


def test_gateway_uses_fanduel_first_without_unnecessary_secondary_call():
    from sports_api import wnba_pra_market_gateway_v1 as gateway

    calls = []

    def fd(**kwargs):
        calls.append("fd")
        return {"raw_feed": {"offers": [_offer(), _offer(side="under", odds=-112)]}}

    def dk(**kwargs):
        calls.append("dk")
        raise AssertionError("secondary source must not be called when primary is usable")

    result = gateway.build_pra_market_board(
        date="2026-10-21", season=2026, fanduel_collector=fd, draftkings_collector=dk
    )
    assert calls == ["fd"]
    assert result["state"] == "READY"
    assert result["selected_provider"] == "fanduel"
    assert len(result["offers"]) == 2
    assert result["offers"][0]["sportsbook"] == "FanDuel"


def test_gateway_falls_back_to_draftkings_when_fanduel_has_no_pra_and_enriches_identity():
    from sports_api import wnba_pra_market_gateway_v1 as gateway

    calls = []

    def fd(**kwargs):
        calls.append("fd")
        return {"raw_feed": {"offers": []}}

    def dk(**kwargs):
        calls.append("dk")
        return {
            "offers": [
                _offer("DraftKings", line=30.5, odds=-105, teams=False),
                _offer("DraftKings", side="under", line=30.5, odds=-115, teams=False),
            ],
            "source_events": [{
                "source_event_id": "evt-1",
                "event_name": "GS Valkyries @ ATL Dream",
                "participants": ["ATL Dream", "GS Valkyries"],
            }],
        }

    result = gateway.build_pra_market_board(
        date="2026-10-21", season=2026, fanduel_collector=fd, draftkings_collector=dk
    )
    assert calls == ["fd", "dk"]
    assert result["state"] == "READY"
    assert result["selected_provider"] == "draftkings"
    assert result["provider_health"][0]["state"] == "EMPTY"
    quote = result["offers"][0]
    assert quote["sportsbook"] == "DraftKings"
    assert quote["line"] == 30.5
    assert quote["american_odds"] == -105
    assert quote["market_captured_at_utc"] == "2026-10-21T15:00:00+00:00"
    assert quote["away_team"] == "GS Valkyries"
    assert quote["home_team"] == "ATL Dream"


def test_gateway_marks_primary_degraded_and_keeps_fallback_alive():
    from sports_api import wnba_pra_market_gateway_v1 as gateway

    def fd(**kwargs):
        raise RuntimeError("provider unavailable")

    def dk(**kwargs):
        return {"offers": [_offer("DraftKings"), _offer("DraftKings", side="under")]}

    result = gateway.build_pra_market_board(
        date="2026-10-21", season=2026, fanduel_collector=fd, draftkings_collector=dk
    )
    assert result["selected_provider"] == "draftkings"
    assert result["provider_health"][0]["provider_id"] == "fanduel"
    assert result["provider_health"][0]["state"] == "DEGRADED"


def test_gateway_never_averages_or_reprices_sportsbook_quotes():
    from sports_api import wnba_pra_market_gateway_v1 as gateway

    original = [
        _offer("DraftKings", line=29.5, odds=101),
        _offer("DraftKings", side="under", line=29.5, odds=-121),
    ]
    result = gateway.build_pra_market_board(
        date="2026-10-21",
        season=2026,
        fanduel_collector=lambda **kwargs: {"raw_feed": {"offers": []}},
        draftkings_collector=lambda **kwargs: {"offers": original},
    )
    assert [(x["line"], x["american_odds"], x["side"]) for x in result["offers"]] == [
        (29.5, 101, "over"), (29.5, -121, "under")
    ]


def test_active_successor_files_do_not_import_prohibited_providers():
    paths = [
        "sports_api/wnba_pra_market_gateway_v1.py",
        "sports_api/api/wnba_pra_market_gateway_v1.py",
        "sports_api/api/wnba_draftkings_direct.py",
        "wnba_pra_api_market_bridge_v2.py",
        "wnba_pra_hub_v3617.py",
        "wnba_pra_product_view_v3.py",
    ]
    for rel in paths:
        source = (ROOT / rel).read_text(encoding="utf-8").casefold()
        assert "import sports_api.collectors.wnba_sportsgameodds" not in source
        assert "import wnba_sportsgameodds_v1" not in source
        assert "espn" not in source
        assert "espn bet" not in source


def test_streamlit_bridge_uses_one_kyre_api_market_board_endpoint():
    source = (ROOT / "wnba_pra_api_market_bridge_v2.py").read_text(encoding="utf-8")
    assert '/api/v1/wnba/pra/market-board' in source
    assert 'collection-store/snapshots' not in source
    assert 'collect/failover/line-board' not in source
    assert 'requests.post' not in source


def test_api_router_is_mounted_through_existing_wnba_market_router():
    route_source = (ROOT / "sports_api/api/wnba_pra_market_gateway_v1.py").read_text(encoding="utf-8")
    carrier_source = (ROOT / "sports_api/api/wnba_draftkings_direct.py").read_text(encoding="utf-8")
    assert '@router.get("/pra/market-board")' in route_source
    assert 'APIRouter(tags=["wnba"])' in route_source
    assert "wnba_pra_market_gateway_router" in carrier_source
    assert "router.include_router(wnba_pra_market_gateway_router)" in carrier_source


def test_compatibility_boundary_advances_to_api_only_successor():
    source = (ROOT / "wnba_pra_hub_v3612.py").read_text(encoding="utf-8")
    assert "import wnba_pra_hub_v3617 as active" in source


def test_successor_installs_api_only_shim_before_preserved_model_imports():
    source = (ROOT / "wnba_pra_hub_v3617.py").read_text(encoding="utf-8")
    install_pos = source.index("api_market.install()")
    snapshot_pos = source.index("importlib.import_module(\"wnba_pra_product_snapshot_v1\")")
    assert install_pos < snapshot_pos
    assert "require_fanduel=False" in source
    assert "wnba_pra_hub_v3616" not in source
    assert "def __getattr__" not in source


def test_product_view_labels_actual_selected_sportsbook():
    source = (ROOT / "wnba_pra_product_view_v3.py").read_text(encoding="utf-8")
    assert "selected_sportsbook" in source
    assert "market-qualified" in source.lower()
    assert "substitute another sportsbook" not in source.lower()
