"""Monster Speed V3 Step 1 — permanent app.py workflow fanout guard."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "devsystem/monster_speed_v3_step1_app_fanout_quarantine.txt"
FORBIDDEN = "app.py"


class QuarantineFailure(RuntimeError):
    pass


def _listed_paths() -> list[str]:
    items = [
        line.strip()
        for line in MANIFEST.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if len(items) != 51:
        raise QuarantineFailure(f"expected 51 quarantined workflows, found {len(items)}")
    if len(set(items)) != len(items):
        raise QuarantineFailure("duplicate workflow in quarantine manifest")
    return items


def _on_block(text: str) -> list[str]:
    lines = text.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if line == "on:"),
        None,
    )
    if start is None:
        raise QuarantineFailure("workflow has no top-level on block")
    block = [lines[start]]
    for line in lines[start + 1 :]:
        if line.strip() and not line.startswith(" "):
            break
        block.append(line)
    return block


def _automatic_trigger_lines(text: str) -> list[str]:
    """Return only pull_request/push trigger blocks from top-level on."""
    block = _on_block(text)
    out: list[str] = []
    active = False
    for line in block[1:]:
        if line.startswith("  ") and not line.startswith("    ") and line.strip().endswith(":"):
            event = line.strip()[:-1]
            active = event in {"pull_request", "push"}
            if active:
                out.append(line)
            continue
        if active:
            out.append(line)
    return out


def check_repository() -> dict[str, object]:
    failures: list[str] = []
    checked = 0
    for rel in _listed_paths():
        path = ROOT / rel
        if not path.is_file():
            failures.append(f"{rel}: missing")
            continue
        checked += 1
        trigger = "\n".join(_automatic_trigger_lines(path.read_text(encoding="utf-8")))
        if FORBIDDEN in trigger:
            failures.append(f"{rel}: automatic trigger still owns {FORBIDDEN}")
    if failures:
        raise QuarantineFailure(" | ".join(failures))
    return {
        "status": "GREEN",
        "checked": checked,
        "quarantined_workflows": 51,
        "baseline_runs": 56,
        "unrelated_app_runs_removed": 51,
        "expected_max_runs_from_same_app_only_shape": 5,
    }


def main() -> int:
    result = check_repository()
    print("MONSTER_SPEED_V3_STEP1_APP_FANOUT_QUARANTINE_GREEN")
    print("MONSTER_SPEED_V3_STEP1_51_LEGACY_APP_TRIGGERS_REMOVED")
    print("MONSTER_SPEED_V3_STEP1_FROZEN_GREEN")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
