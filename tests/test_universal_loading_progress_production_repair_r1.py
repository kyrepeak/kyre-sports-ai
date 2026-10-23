from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_V4 = ROOT / "universal_page_experience_runtime_v4.py"


def test_server_loader_must_not_be_cleared_before_destination_load_finishes() -> None:
    """Regression for iPad/Safari blank-body loading gap seen on 2026-10-22.

    Inserting a zero-height client component is not proof that its parent-DOM
    script mounted. The server loader must stay authoritative while the expensive
    destination load is still in progress.
    """
    source = RUNTIME_V4.read_text(encoding="utf-8")
    load_pos = source.index("loaded = core.load_destination(adapter)")
    early_clear_pos = source.find("transition_slot.empty()")
    assert early_clear_pos == -1 or early_clear_pos > load_pos


def test_progress_runtime_does_not_gate_server_loader_on_client_component_mount() -> None:
    source = RUNTIME_V4.read_text(encoding="utf-8")
    assert "if is_transition and client_controller:" not in source
