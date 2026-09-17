from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[1] / "devsystem" / "production_verify_v2.py"
    spec = importlib.util.spec_from_file_location("devsystem_production_verify_v2", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v2_uses_final_v39_marker_as_production_readiness_sentinel():
    module = _load_module()

    assert module.FROZEN_VERIFIER == "devsystem.production_verify_v1"
    assert module.CFB_REQUIRED_MARKERS == (
        "Steps 11–12 • current form + certification",
        "CFB O/U • CLEAN PAGE V39 ACTIVE",
        "COMPACT EVIDENCE RENDERER",
        "VERIFIED IDENTITY ≠ MISSING STEP METRIC",
        "0.0% SPORTSBOOK PROJECTION INFLUENCE",
        "Matchup Foundation",
        "Steps 1–4 • compact verified evidence",
        "Frozen O/U math • Mutation OFF • Sportsbook 0.0%",
        "Step 5 • Explosive Plays",
        "Step 10 • Historical Matchup",
    )
    assert "CFB O/U • CLEAN PAGE V30 ACTIVE" not in module.CFB_REQUIRED_MARKERS
    assert "CFB O/U • CLEAN PAGE V38 ACTIVE" not in module.CFB_REQUIRED_MARKERS


def test_v2_preserves_frozen_production_browser_and_swaps_only_marker_order(monkeypatch, tmp_path):
    module = _load_module()
    original_browser = module.frozen._browser_verify
    original_markers = module.frozen.CFB_REQUIRED_MARKERS
    observed: dict[str, object] = {}

    def fake_frozen_run(*, artifact_dir: str | Path):
        observed["artifact_dir"] = Path(artifact_dir)
        observed["markers"] = module.frozen.CFB_REQUIRED_MARKERS
        observed["browser"] = module.frozen._browser_verify
        return {"status": "GREEN"}

    monkeypatch.setattr(module.frozen, "run", fake_frozen_run)

    result = module.run(artifact_dir=str(tmp_path))

    assert result["status"] == "GREEN"
    assert observed["artifact_dir"] == tmp_path
    assert observed["markers"] == module.CFB_REQUIRED_MARKERS
    assert observed["browser"] is original_browser
    assert module.frozen.CFB_REQUIRED_MARKERS is original_markers
    assert module.frozen._browser_verify is original_browser


def test_v2_delegates_everything_to_frozen_v1_except_marker_readiness_order():
    module = _load_module()
    source = inspect.getsource(module.run)

    assert "original_markers = frozen.CFB_REQUIRED_MARKERS" in source
    assert "frozen.CFB_REQUIRED_MARKERS = CFB_REQUIRED_MARKERS" in source
    assert "return frozen.run" in source
    assert "finally:" in source
    assert "frozen.CFB_REQUIRED_MARKERS = original_markers" in source
    assert "frozen._browser_verify =" not in source
