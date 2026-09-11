from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "devsystem" / "failure_packet_v1.py"
    spec = importlib.util.spec_from_file_location("failure_packet_v1", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_packet_is_green_when_lanes_are_success_or_skipped(tmp_path):
    module = _load()
    packet = module.build_packet(
        {
            "classify": {"result": "success"},
            "browser-qa": {"result": "skipped"},
        },
        run_id="123",
        sha="abc",
        ref="refs/pull/1/merge",
    )
    assert packet["schema"] == "KYRE_DEVSYSTEM_FAILURE_PACKET_V1"
    assert packet["status"] == "GREEN"
    assert packet["triage"]["primary"] is None

    module.write_packet(packet, tmp_path)
    assert (tmp_path / "failure-packet.json").exists()
    assert "No failed DevSystem lanes" in (tmp_path / "failure-packet.md").read_text()


def test_packet_routes_cfb_failure_to_first_cfb_evidence(tmp_path):
    module = _load()
    packet = module.build_packet(
        {
            "classify": {"result": "success"},
            "cfb-critical": {"result": "failure"},
            "mlb-critical": {"result": "success"},
        }
    )
    primary = packet["triage"]["primary"]
    assert packet["status"] == "FAILURES_FOUND"
    assert primary["job"] == "cfb-critical"
    assert primary["layer"] == "cfb"
    assert "frozen projection math" in primary["inspect_first"]
    assert "official-ID" in primary["inspect_first"]

    module.write_packet(packet, tmp_path)
    markdown = (tmp_path / "failure-packet.md").read_text()
    assert "CFB" in markdown
    assert "cfb-critical" in markdown
    assert "Inspect first" in markdown


def test_packet_captures_all_failed_lanes_in_deterministic_order():
    module = _load()
    packet = module.build_packet(
        {
            "wnba-critical": {"result": "failure"},
            "browser-qa": {"result": "cancelled"},
            "classify": {"result": "success"},
        }
    )
    jobs = [item["job"] for item in packet["triage"]["failures"]]
    assert jobs == ["browser-qa", "wnba-critical"]
    assert packet["triage"]["primary"]["job"] == "browser-qa"
