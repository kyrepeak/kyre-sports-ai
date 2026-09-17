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


def test_v2_delegates_production_browser_to_certified_v39_driver(monkeypatch, tmp_path):
    module = _load_module()
    original_browser = module.frozen._browser_verify
    calls: dict[str, object] = {}

    def fake_v39_browser(*, base_url: str, artifact_dir: str | Path):
        calls["base_url"] = base_url
        calls["artifact_dir"] = Path(artifact_dir)
        return {
            "status": "GREEN",
            "cfb_route": "College Football -> Over/Under",
            "cfb_markers": list(module.CFB_REQUIRED_MARKERS),
        }

    def fake_frozen_run(*, artifact_dir: str | Path):
        assert module.frozen._browser_verify is not original_browser
        browser = module.frozen._browser_verify(
            "https://example.streamlit.app",
            Path(artifact_dir),
        )
        return {"status": "GREEN", **browser}

    monkeypatch.setattr(module.certified_browser, "run_browser_qa", fake_v39_browser)
    monkeypatch.setattr(module.frozen, "run", fake_frozen_run)

    result = module.run(artifact_dir=str(tmp_path))

    assert result["status"] == "GREEN"
    assert calls["base_url"] == "https://example.streamlit.app"
    assert calls["artifact_dir"] == tmp_path
    assert module.frozen._browser_verify is original_browser


def test_v2_browser_delegate_reuses_v39_readiness_contract():
    module = _load_module()
    source = inspect.getsource(module._browser_verify_v39)

    assert "certified_browser.run_browser_qa" in source
    assert "base_url=streamlit_url" in source
    assert "artifact_dir=artifact_dir" in source


def test_v2_preserves_frozen_v1_run_and_restores_browser_hook():
    module = _load_module()
    source = inspect.getsource(module.run)

    assert "original_browser = frozen._browser_verify" in source
    assert "frozen._browser_verify = _browser_verify_v39" in source
    assert "return frozen.run" in source
    assert "finally:" in source
    assert "frozen._browser_verify = original_browser" in source
