from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_passing_yards_layered_phase1_step1_baseline_contract():
    contract = json.loads(
        (ROOT / "devsystem/task_ledgers/passing-yards-layered-phase1-step1-baseline-v1.json").read_text(encoding="utf-8")
    )
    assert contract["baseline_product_sha"] == "794f19326e78dd94b2f0663cb007aee9d673ec6a"
    assert contract["streamlit_entrypoint"] == "app.py"
    assert contract["active_router"] == "streamlit_memory_lazy_router_v187"
    assert contract["passing_yards_presentation_owner"] == "nfl_passing_yards_hub_v16.py"
    assert contract["rebuild_scope"] == "presentation and navigation architecture only"
    assert "projection math" in contract["frozen_behavior"]
    assert "market logic" in contract["frozen_behavior"]
    assert "data routing" in contract["frozen_behavior"]
