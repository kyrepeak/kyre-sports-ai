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


def test_v2_uses_full_certified_cfb_v39_marker_contract():
    module = _load_module()

    assert module.FROZEN_VERIFIER == "devsystem.production_verify_v1"
    assert module.CFB_REQUIRED_MARKERS == (
        "CFB O/U • CLEAN PAGE V39 ACTIVE",
        "COMPACT EVIDENCE RENDERER",
        "VERIFIED IDENTITY ≠ MISSING STEP METRIC",
        "0.0% SPORTSBOOK PROJECTION INFLUENCE",
        "Matchup Foundation",
        "Steps 1–4 • compact verified evidence",
        "Frozen O/U math • Mutation OFF • Sportsbook 0.0%",
        "Step 5 • Explosive Plays",
        "Step 10 • Historical Matchup",
        "Steps 11–12 • current form + certification",
    )
    assert "CFB O/U • CLEAN PAGE V30 ACTIVE" not in module.CFB_REQUIRED_MARKERS
    assert "CFB O/U • CLEAN PAGE V38 ACTIVE" not in module.CFB_REQUIRED_MARKERS
    assert "FUTURE SLATE COVERAGE ACTIVE" not in module.CFB_REQUIRED_MARKERS
    assert "READABLE STEPS 4-12 ACTIVE" not in module.CFB_REQUIRED_MARKERS


def test_v2_delegates_full_production_verification_to_frozen_v1():
    module = _load_module()
    source = inspect.getsource(module.run)

    assert "frozen.CFB_REQUIRED_MARKERS = CFB_REQUIRED_MARKERS" in source
    assert "return frozen.run" in source
    assert "finally:" in source
    assert "frozen.CFB_REQUIRED_MARKERS = original_markers" in source
