from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "devsystem" / "failure_fingerprint_v1.py"
    spec = importlib.util.spec_from_file_location("failure_fingerprint_v1", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_same_failure_identity_is_stable_across_noisy_values():
    module = _load()
    a = {
        "job": "browser-qa",
        "layer": "ui-browser",
        "evidence_signal": "browser-selector-race",
        "evidence_match": "Playwright timeout 30000ms waiting for /tmp/run-123/combobox line 88",
    }
    b = {
        "job": "browser-qa",
        "layer": "ui-browser",
        "evidence_signal": "browser-selector-race",
        "evidence_match": "Playwright timeout 45000ms waiting for /tmp/run-999/combobox line 104",
    }
    assert module.failure_fingerprint(a) == module.failure_fingerprint(b)
    assert module.failure_fingerprint(a).startswith("KYRE-CI-")


def test_different_failure_signals_do_not_collapse_together():
    module = _load()
    base = {"job": "cfb-critical", "layer": "cfb", "evidence_match": "failure"}
    assertion = {**base, "evidence_signal": "test-assertion"}
    network = {**base, "evidence_signal": "network-upstream"}
    assert module.failure_fingerprint(assertion) != module.failure_fingerprint(network)


def test_attach_fingerprints_populates_primary_and_all_failures():
    module = _load()
    failure = {
        "job": "core-smoke",
        "layer": "shared-core",
        "evidence_signal": "syntax-compile",
        "diagnosis": "Python syntax/compile failure",
    }
    report = {"primary": dict(failure), "failures": [dict(failure)]}
    module.attach_fingerprints(report)
    assert report["primary"]["failure_fingerprint"].startswith("KYRE-CI-")
    assert report["failures"][0]["failure_fingerprint"] == report["primary"]["failure_fingerprint"]
