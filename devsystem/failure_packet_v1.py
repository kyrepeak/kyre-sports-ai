"""Build a compact, deterministic DevSystem failure evidence packet."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _load_triage():
    path = ROOT / "devsystem" / "failure_triage_v1.py"
    spec = importlib.util.spec_from_file_location("failure_triage_v1", path)
    if not spec or not spec.loader:
        raise RuntimeError("Unable to load failure_triage_v1")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_fingerprint():
    path = ROOT / "devsystem" / "failure_fingerprint_v1.py"
    spec = importlib.util.spec_from_file_location("failure_fingerprint_v1", path)
    if not spec or not spec.loader:
        raise RuntimeError("Unable to load failure_fingerprint_v1")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _needs_with_failed_step_evidence(
    needs: dict[str, Any],
    failed_steps: dict[str, list[str]] | None,
) -> dict[str, Any]:
    """Attach captured failed-step text to its lane without mutating caller input."""
    enriched: dict[str, Any] = {}
    captured = failed_steps or {}
    for name, raw_payload in sorted(needs.items()):
        payload = dict(raw_payload or {})
        steps = captured.get(name) or []
        if steps and not (payload.get("evidence") or payload.get("log_excerpt")):
            payload["evidence"] = "\n".join(str(step) for step in steps if str(step).strip())
        enriched[name] = payload
    return enriched


def build_packet(
    needs: dict[str, Any],
    *,
    run_id: str = "",
    sha: str = "",
    ref: str = "",
    failed_steps: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    triage_module = _load_triage()
    fingerprint_module = _load_fingerprint()
    enriched_needs = _needs_with_failed_step_evidence(needs, failed_steps)
    report = triage_module.triage(enriched_needs)
    fingerprint_module.attach_fingerprints(report)
    lane_results = {
        name: str((payload or {}).get("result") or "unknown")
        for name, payload in sorted(needs.items())
    }
    return {
        "schema": "KYRE_DEVSYSTEM_FAILURE_PACKET_V1",
        "status": report["status"],
        "run_id": run_id,
        "sha": sha,
        "ref": ref,
        "lane_results": lane_results,
        "failed_steps": failed_steps or {},
        "triage": report,
    }


def render_markdown(packet: dict[str, Any]) -> str:
    triage = packet["triage"]
    lines = [
        "# DevSystem Failure Packet",
        "",
        f"- **Status:** {packet['status']}",
        f"- **Run ID:** {packet.get('run_id') or 'unknown'}",
        f"- **Commit:** {packet.get('sha') or 'unknown'}",
        f"- **Ref:** {packet.get('ref') or 'unknown'}",
        "",
        "## Lane Results",
        "",
        "| Lane | Result |",
        "| --- | --- |",
    ]
    for name, result in packet["lane_results"].items():
        lines.append(f"| {name} | {result} |")

    primary = triage.get("primary")
    lines.extend(["", "## Primary Diagnosis", ""])
    if not primary:
        lines.append("No failed DevSystem lanes were detected.")
    else:
        lines.extend([
            f"- **Lane:** {primary['job']}",
            f"- **Failure fingerprint:** {primary.get('failure_fingerprint', 'unavailable')}",
            f"- **Layer:** {primary['layer']}",
            f"- **Failure class:** {primary['failure_class']}",
            f"- **Evidence signal:** {primary.get('evidence_signal', 'none')}",
            f"- **Confidence:** {primary.get('confidence', 'lane-only')}",
            f"- **Diagnosis:** {primary.get('diagnosis', primary['failure_class'])}",
            f"- **Remediation class:** {primary.get('remediation_class', 'unknown')}",
            f"- **Retry policy:** {primary.get('retry_policy', 'investigate-first')}",
            f"- **Retry reason:** {primary.get('retry_reason', 'insufficient evidence for retry guidance')}",
            f"- **Inspect first:** {primary['inspect_first']}",
        ])

    failures = triage.get("failures") or []
    lines.extend(["", "## All Failed Lanes", ""])
    if not failures:
        lines.append("None.")
    else:
        for item in failures:
            lines.append(
                f"- `{item['job']}` → fingerprint={item.get('failure_fingerprint', 'unavailable')} → "
                f"{item['layer']} → signal={item.get('evidence_signal', 'none')} → "
                f"confidence={item.get('confidence', 'lane-only')} → "
                f"remediation={item.get('remediation_class', 'unknown')} → "
                f"retry={item.get('retry_policy', 'investigate-first')} → "
                f"{item.get('diagnosis', item['failure_class'])} → inspect: {item['inspect_first']}"
            )

    lines.extend(["", "## Failed Steps", ""])
    failed_steps = packet.get("failed_steps") or {}
    if not failed_steps:
        lines.append("None captured.")
    else:
        for job, steps in sorted(failed_steps.items()):
            lines.append(f"- **{job}:** {', '.join(steps) if steps else 'job failed without a failed step'}")
    lines.append("")
    return "\n".join(lines)


def write_packet(packet: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "failure-packet.json").write_text(
        json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "failure-packet.md").write_text(render_markdown(packet), encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--needs-json")
    parser.add_argument("--failed-steps-json")
    parser.add_argument("--output-dir", default="artifacts/devsystem-failure-packet")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    raw = args.needs_json or os.environ.get("DEVSYSTEM_NEEDS_JSON") or "{}"
    steps_raw = args.failed_steps_json or os.environ.get("DEVSYSTEM_FAILED_STEPS_JSON") or "{}"
    packet = build_packet(
        json.loads(raw),
        run_id=os.environ.get("DEVSYSTEM_SOURCE_RUN_ID") or os.environ.get("GITHUB_RUN_ID", ""),
        sha=os.environ.get("DEVSYSTEM_SOURCE_SHA") or os.environ.get("GITHUB_SHA", ""),
        ref=os.environ.get("DEVSYSTEM_SOURCE_REF") or os.environ.get("GITHUB_REF", ""),
        failed_steps=json.loads(steps_raw),
    )
    write_packet(packet, Path(args.output_dir))
    print("DEVSYSTEM_FAILURE_PACKET_WRITTEN")
    print(render_markdown(packet))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())