from __future__ import annotations

from sports_api.posthog_error_radar_v1 import run_streamlit_activation_probe


def test_streamlit_activation_probe_emits_runtime_and_posthog_proof() -> None:
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
