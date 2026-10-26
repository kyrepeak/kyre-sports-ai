from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "devsystem" / "monster_step2g_live_convergence_probe_v1.py"


def _load():
    spec = importlib.util.spec_from_file_location("monster_step2g_live_convergence_probe_v1", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_live_probe_has_no_separate_urllib_health_preflight():
    text = MODULE.read_text(encoding="utf-8")
    assert "urllib.request" not in text
    assert "urlopen(" not in text


def test_browser_document_status_is_the_stable_alias_health_proof():
    mod = _load()
    health = mod.browser_health_evidence(document_status=200, document_url="https://pickvault.streamlit.app/")
    assert health == {
        "source": "browser_document",
        "status": 200,
        "url": "https://pickvault.streamlit.app/",
        "healthy": True,
    }


def test_browser_health_rejects_error_status():
    mod = _load()
    try:
        mod.browser_health_evidence(document_status=503, document_url="https://pickvault.streamlit.app/")
    except RuntimeError as exc:
        assert "stable alias" in str(exc).lower()
    else:
        raise AssertionError("503 browser document must fail closed")
