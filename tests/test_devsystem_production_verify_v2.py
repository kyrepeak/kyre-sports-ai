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


def test_v2_production_browser_uses_exact_fast_route_and_waits_for_full_v39():
    module = _load_module()
    source = inspect.getsource(module._browser_verify_v39)

    assert "run_browser_qa" not in source
    assert "_read_sport_options" not in source
    assert "certified_browser._choose(" not in source
    assert "certified_browser._cfb_over_under_url(streamlit_url)" in source
    assert "certified_browser._find_app_frame" in source
    assert "certified_browser.CFB_MARKET_LABEL" in source
    assert "ROUTE_TARGET_MISMATCH" in source
    assert "certified_browser._wait_for_either_text(" in source
    assert "certified_browser.CFB_NO_GAMES_MARKER" in source
    assert "CFB_REQUIRED_MARKERS[-1]" in source
    assert "required_markers" in source


def test_v2_preserves_frozen_v1_run_and_restores_browser_hook(monkeypatch, tmp_path):
    module = _load_module()
    original_browser = module.frozen._browser_verify
    calls: dict[str, object] = {}

    def fake_browser(streamlit_url: str, artifact_dir: Path):
        calls["streamlit_url"] = streamlit_url
        calls["artifact_dir"] = Path(artifact_dir)
        return {
            "cfb_route": "College Football -> Over/Under",
            "cfb_markers": list(module.CFB_REQUIRED_MARKERS),
        }

    def fake_frozen_run(*, artifact_dir: str | Path):
        assert module.frozen._browser_verify is fake_browser
        browser = module.frozen._browser_verify(
            "https://example.streamlit.app",
            Path(artifact_dir),
        )
        return {"status": "GREEN", **browser}

    monkeypatch.setattr(module, "_browser_verify_v39", fake_browser)
    monkeypatch.setattr(module.frozen, "run", fake_frozen_run)

    result = module.run(artifact_dir=str(tmp_path))

    assert result["status"] == "GREEN"
    assert calls["streamlit_url"] == "https://example.streamlit.app"
    assert calls["artifact_dir"] == tmp_path
    assert module.frozen._browser_verify is original_browser
