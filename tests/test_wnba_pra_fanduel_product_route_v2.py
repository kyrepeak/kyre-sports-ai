from __future__ import annotations

from pathlib import Path
import inspect


ROOT = Path(__file__).resolve().parents[1]


def test_v3616_orchestration_requires_fanduel_gated_views():
    import wnba_pra_hub_v3616 as hub

    source = inspect.getsource(hub.render_wnba_pra_hub)
    assert "api_market.install()" in source
    assert "playoff.resolve_playoff_context" in source
    assert "snapshot.build_product_snapshot" in source
    assert "consensus.build_market_consensus" in source
    assert "require_fanduel=True" in source
    assert "wnba_pra_product_view_v2" in (ROOT / "wnba_pra_hub_v3616.py").read_text(encoding="utf-8")


def test_historical_v3612_boundary_forwards_only_to_v3616():
    source = (ROOT / "wnba_pra_hub_v3612.py").read_text(encoding="utf-8")
    assert "import wnba_pra_hub_v3616 as active" in source
    assert "wnba_pra_hub_v3615 as active" not in source
    assert "universal_runtime_v5" not in source


def test_v3616_contract_preserves_model_and_market_math():
    import wnba_pra_hub_v3616 as hub

    contract = hub.FANDUEL_PRODUCT_CONTRACT
    assert contract["fanduel_primary_board_eligibility"] is True
    assert contract["kyre_api_market_transport"] is True
    assert contract["multi_source_context"] is True
    assert contract["projection_math_changed"] is False
    assert contract["monte_carlo_changed"] is False
    assert contract["qualification_changed"] is False
    assert contract["ranking_changed"] is False
    assert contract["selection_changed"] is False
    assert contract["sportsbook_projection_influence"] == 0.0
