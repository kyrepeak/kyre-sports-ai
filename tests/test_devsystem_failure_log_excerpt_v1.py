from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "devsystem" / "failure_log_excerpt_v1.py"
    spec = importlib.util.spec_from_file_location("failure_log_excerpt_v1", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_extract_log_excerpt_keeps_failure_signal_and_context():
    module = _load()
    raw = "\n".join([
        "setup complete",
        "streamlit ready",
        "opening page",
        "Playwright TimeoutError: waiting for locator combobox",
        "cleanup starts",
        "cleanup done",
    ])
    excerpt = module.extract_log_excerpt(raw)
    assert "Playwright TimeoutError" in excerpt
    assert "opening page" in excerpt
    assert "cleanup starts" in excerpt


def test_extract_log_excerpt_redacts_common_secrets():
    module = _load()
    raw = (
        "Authorization: Bearer abc123\n"
        "token=secret-token\n"
        "password: hunter2\n"
        "AssertionError: protected invariant failed"
    )
    excerpt = module.extract_log_excerpt(raw)
    assert "abc123" not in excerpt
    assert "secret-token" not in excerpt
    assert "hunter2" not in excerpt
    assert "Authorization: Bearer [REDACTED]" in excerpt
    assert "token=[REDACTED]" in excerpt
    assert "password: [REDACTED]" in excerpt
    assert "AssertionError" in excerpt


def test_extract_log_excerpt_accepts_github_actions_premasked_secret():
    module = _load()
    raw = (
        "Authorization: ***\n"
        "token=secret-token\n"
        "password: hunter2\n"
        "AssertionError: protected invariant failed"
    )
    excerpt = module.extract_log_excerpt(raw)
    assert "Authorization: ***" in excerpt
    assert "secret-token" not in excerpt
    assert "hunter2" not in excerpt
    assert "token=[REDACTED]" in excerpt
    assert "password: [REDACTED]" in excerpt
    assert "AssertionError" in excerpt


def test_extract_log_excerpt_is_bounded():
    module = _load()
    raw = "\n".join(f"ERROR line {index} " + ("x" * 200) for index in range(500))
    excerpt = module.extract_log_excerpt(raw, max_chars=2000)
    assert len(excerpt) <= 2000
    assert "ERROR line 499" in excerpt


def test_extract_log_excerpt_uses_tail_when_no_known_signal_exists():
    module = _load()
    raw = "\n".join(f"plain line {index}" for index in range(200))
    excerpt = module.extract_log_excerpt(raw)
    assert "plain line 199" in excerpt
    assert "plain line 0" not in excerpt
