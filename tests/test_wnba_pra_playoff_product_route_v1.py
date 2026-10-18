from __future__ import annotations
from pathlib import Path
from types import SimpleNamespace, ModuleType
import sys
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]

def _stub_local_storage(monkeypatch):
    module=ModuleType("streamlit_local_storage")
    module.LocalStorage=None
    monkeypatch.setitem(sys.modules,"streamlit_local_storage",module)


def test_compatibility_boundary_advances_to_current_successor():
    source=(ROOT/"wnba_pra_hub_v3612.py").read_text(encoding="utf-8")
    assert "import wnba_pra_hub_v3616 as active" in source
    current=(ROOT/"wnba_pra_hub_v3616.py").read_text(encoding="utf-8")
    assert "require_fanduel=True" in current
    predecessor=(ROOT/"wnba_pra_hub_v3615.py").read_text(encoding="utf-8")
    assert "PLAYOFF_PRODUCT_CONTRACT" in predecessor


def test_universal_runtime_keeps_existing_step9_adapter():
    from universal_runtime_v5_loader import resolve_destination
    from universal_runtime_v5_state import RuntimeRoute
    adapter=resolve_destination(RuntimeRoute("wnba","pra",{}))
    assert adapter.source_version == "streamlit_memory_lazy_router_wnba_pra_speed_v3_step9_duplicate_key_guard"
    assert adapter.route_key == ("wnba","pra")


def test_successor_owns_product_sequence_without_legacy_render(monkeypatch):
    _stub_local_storage(monkeypatch)
    import wnba_pra_hub_v3615 as hub
    calls=[]
    fake_context=SimpleNamespace(effective_date="2026-10-19")
    fake_snapshot=SimpleNamespace(market_rows=pd.DataFrame())
    fake_consensus=pd.DataFrame()
    fake_views=()
    monkeypatch.setattr(hub,"_selected_date",lambda: "2026-10-18")
    monkeypatch.setattr(hub.api_market,"install",lambda: calls.append("install"))
    monkeypatch.setattr(hub.playoff,"resolve_playoff_context",lambda day: calls.append(("context",day)) or fake_context)
    monkeypatch.setattr(hub.snapshot,"build_product_snapshot",lambda day: calls.append(("snapshot",day)) or fake_snapshot)
    monkeypatch.setattr(hub.consensus,"build_market_consensus",lambda rows: calls.append("consensus") or fake_consensus)
    monkeypatch.setattr(hub.view_model,"build_player_views",lambda snap,ctx,market: calls.append("views") or fake_views)
    monkeypatch.setattr(hub.product,"render_pra_product",lambda snap,ctx,views,market: calls.append("render"))
    monkeypatch.setattr(hub.previous,"render_wnba_pra_hub",lambda *a,**k: (_ for _ in ()).throw(AssertionError("legacy renderer must not run")))
    hub.render_wnba_pra_hub()
    assert calls == ["install",("context","2026-10-18"),("snapshot","2026-10-19"),"consensus","views","render"]


def test_successor_date_control_reuses_existing_wnba_key(monkeypatch):
    _stub_local_storage(monkeypatch)
    import wnba_pra_hub_v3615 as hub
    seen={}
    class ST:
        session_state={"wnba_pra_v2_date":"2026-10-20"}
        @staticmethod
        def date_input(label, **kwargs):
            seen.update({"label":label,**kwargs}); return pd.Timestamp("2026-10-20").date()
    monkeypatch.setattr(hub,"st",ST)
    assert hub._selected_date() == "2026-10-20"
    assert seen["key"] == "wnba_pra_v2_date"
    assert "Sport" not in seen["label"] and "Market" not in seen["label"]
