from pathlib import Path
import sys
import types

ACTIVATION = Path("cfb_game_total_page1_v2_step4_activation.py")
V38 = Path("cfb_game_total_clean_page_v38.py")


def _fake_module(name: str, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


def test_step4_activation_converges_all_live_game_total_owners(monkeypatch) -> None:
    router190 = _fake_module("streamlit_memory_lazy_router_v190", GAME_TOTAL_PAGE="old-v190")
    owner181 = _fake_module("streamlit_memory_lazy_router_v181", ACTIVE_PAGE="old-v181")
    owner160 = _fake_module("streamlit_memory_lazy_router_v160", ACTIVE_PAGE="old-v160")
    monkeypatch.setitem(sys.modules, router190.__name__, router190)
    monkeypatch.setitem(sys.modules, owner181.__name__, owner181)
    monkeypatch.setitem(sys.modules, owner160.__name__, owner160)

    namespace = {"__name__": "step4_activation_contract"}
    exec(compile(ACTIVATION.read_text(encoding="utf-8"), str(ACTIVATION), "exec"), namespace)
    target = namespace["activate_step4_page"]()

    assert target == "cfb_game_total_clean_page_v38"
    assert router190.GAME_TOTAL_PAGE == target
    assert owner181.ACTIVE_PAGE == target
    assert owner160.ACTIVE_PAGE == target


def test_step4_live_owner_repair_is_cfb_only_and_model_safe() -> None:
    source = ACTIVATION.read_text(encoding="utf-8")
    assert 'STEP4_REPAIR_PAGE = "cfb_game_total_clean_page_v38"' in source
    assert "MAY_MODIFY_OTHER_SPORTS = False" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "live_owner.ACTIVE_PAGE = STEP4_REPAIR_PAGE" in source
    assert "render_owner.ACTIVE_PAGE = STEP4_REPAIR_PAGE" in source


def test_step4_keeps_proven_v38_prediction_market_owner() -> None:
    source = V38.read_text(encoding="utf-8")
    assert "cfb_game_total_page1_step4_prediction_market_v1" in source
    assert "cfb_game_total_page1_step4_side_market_v1" in source
    assert "cfb_over_under_market_adapter_v1" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
