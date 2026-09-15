"""Regression contract for Monster A8 Streamlit production telemetry activation."""

from __future__ import annotations

from pathlib import Path

import sports_api.posthog_error_radar_v1 as radar
from sports_api.posthog_error_radar_v1 import run_streamlit_activation_probe


def test_streamlit_activation_probe_emits_runtime_and_posthog_proof(monkeypatch) -> None:
    monkeypatch.setattr(radar, "_STREAMLIT_PROBE_RAN", False, raising=False)
    ping_markers: list[str] = []
    captures: list[tuple[BaseException, dict[str, object]]] = []
    flushes: list[bool] = []

    def ping_fn(marker: str) -> bool:
        ping_markers.append(marker)
        return True

    def capture_fn(exc: BaseException, **kwargs: object) -> bool:
        captures.append((exc, kwargs))
        return True

    def flush_fn() -> bool:
        flushes.append(True)
        return True

    result = run_streamlit_activation_probe(
        argv=["streamlit", "run", "app.py"],
        environ={},
        ping_fn=ping_fn,
        capture_fn=capture_fn,
        flush_fn=flush_fn,
        marker_factory=lambda: "monster-a8-test-marker",
    )

    assert result == {
        "status": "flushed",
        "eligible": True,
        "runtime_pinged": True,
        "accepted": True,
        "flushed": True,
        "marker": "monster-a8-test-marker",
        "fingerprint": "MONSTER-A8-STREAMLIT-PROBE-V1",
    }
    assert ping_markers == ["monster-a8-test-marker"]
    assert len(captures) == 1
    exc, kwargs = captures[0]
    assert isinstance(exc, RuntimeError)
    assert str(exc) == "Monster Streamlit certification synthetic exception probe"
    assert kwargs["error_fingerprint"] == "MONSTER-A8-STREAMLIT-PROBE-V1"
    assert kwargs["surface"] == "streamlit"
    assert kwargs["path"] == "app.py"
    assert kwargs["properties"] == {
        "monster_streamlit_certification_probe": "monster-a8-test-marker",
        "synthetic_certification_probe": True,
        "probe_version": "MONSTER_STREAMLIT_TELEMETRY_PROBE_V1",
    }
    assert flushes == [True]


def test_streamlit_activation_probe_is_one_shot_per_process(monkeypatch) -> None:
    monkeypatch.setattr(radar, "_STREAMLIT_PROBE_RAN", False, raising=False)
    calls = {"ping": 0, "capture": 0, "flush": 0}

    def ping_fn(marker: str) -> bool:
        calls["ping"] += 1
        return True

    def capture_fn(exc: BaseException, **kwargs: object) -> bool:
        calls["capture"] += 1
        return True

    def flush_fn() -> bool:
        calls["flush"] += 1
        return True

    first = run_streamlit_activation_probe(
        argv=["streamlit", "run", "app.py"],
        environ={},
        ping_fn=ping_fn,
        capture_fn=capture_fn,
        flush_fn=flush_fn,
        marker_factory=lambda: "monster-a8-first",
    )
    second = run_streamlit_activation_probe(
        argv=["streamlit", "run", "app.py"],
        environ={},
        ping_fn=ping_fn,
        capture_fn=capture_fn,
        flush_fn=flush_fn,
        marker_factory=lambda: "monster-a8-second",
    )

    assert first["status"] == "flushed"
    assert second == {
        "status": "already_ran",
        "eligible": True,
        "runtime_pinged": False,
        "accepted": False,
        "flushed": False,
        "marker": None,
        "fingerprint": "MONSTER-A8-STREAMLIT-PROBE-V1",
    }
    assert calls == {"ping": 1, "capture": 1, "flush": 1}


def test_streamlit_activation_probe_has_safe_no_arg_defaults(monkeypatch) -> None:
    monkeypatch.setattr(radar, "_STREAMLIT_PROBE_RAN", False, raising=False)
    result = run_streamlit_activation_probe()
    assert result["eligible"] is False
    assert result["status"] == "ineligible"


def test_streamlit_entrypoint_invokes_probe_before_render() -> None:
    app_source = Path("app.py").read_text(encoding="utf-8")
    assert "run_streamlit_activation_probe" in app_source
    assert app_source.index("run_streamlit_activation_probe()") < app_source.index("render_app()")
