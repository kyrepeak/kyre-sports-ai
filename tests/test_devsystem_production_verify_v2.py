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


def test_v2_advances_only_cfb_active_page_marker_to_v39():
    module = _load_module()

    assert module.FROZEN_VERIFIER == "devsystem.production_verify_v1"
    assert module.CFB_REQUIRED_MARKERS[0] == "CFB O/U • CLEAN PAGE V39 ACTIVE"
    assert "CFB O/U • CLEAN PAGE V30 ACTIVE" not in module.CFB_REQUIRED_MARKERS
    assert "CFB O/U • CLEAN PAGE V38 ACTIVE" not in module.CFB_REQUIRED_MARKERS
    assert module.CFB_REQUIRED_MARKERS[1:] == module.frozen.CFB_REQUIRED_MARKERS[1:]


def test_v2_delegates_full_production_verification_to_frozen_v1():
    module = _load_module()
    source = inspect.getsource(module.run)

    assert "frozen.CFB_REQUIRED_MARKERS = CFB_REQUIRED_MARKERS" in source
    assert "return frozen.run" in source
    assert "finally:" in source
    assert "frozen.CFB_REQUIRED_MARKERS = original_markers" in source
