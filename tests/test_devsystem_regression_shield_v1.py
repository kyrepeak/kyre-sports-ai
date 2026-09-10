from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[1] / "devsystem" / "regression_shield_v1.py"
    spec = importlib.util.spec_from_file_location("devsystem_regression_shield_v1", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_regression_shield_is_green():
    module = _load_module()
    result = module.run()

    assert result["status"] == "GREEN"
    assert result["frozen_manifests"] == 4
    assert result["frozen_blobs_verified"] >= 40
    assert result["critical_files_verified"] >= 10
    assert result["critical_tests_verified"] >= 10
    assert result["cfb_snapshot_games"] > 0
    assert result["cfb_snapshot_unique_event_ids"] == result["cfb_snapshot_games"]
    assert result["cfb_market_projection_weight"] == 0.0
    assert result["cfb_matching_method"] == "official ESPN event_id only"
    assert result["cfb_fuzzy_matching"] is False
    assert result["cfb_synthetic_ids"] is False
    assert result["cfb_freshness_firewall_active"] is True
    assert result["cfb_max_market_age_seconds"] == 300.0
