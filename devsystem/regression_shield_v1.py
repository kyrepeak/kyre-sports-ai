"""DevSystem Step 3 regression shield.

Fast, dependency-light protection for invariants that should never drift silently.
It intentionally complements the sport-specific pytest jobs rather than replacing them.
"""
from __future__ import annotations

import hashlib
import json
import math
import py_compile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

FROZEN_MANIFESTS = (
    "cfb_over_under_pre_odds_freeze_manifest_v1.json",
    "cfb_over_under_live_odds_freeze_manifest_v1.json",
    "mlb_moneyline_freeze_manifest_v13.json",
    "mlb_hits_freeze_manifest_v7.json",
)

CRITICAL_FILES = (
    # Shared / active Streamlit
    "app.py",
    "streamlit_memory_lazy_router_v58.py",
    # DevSystem browser QA
    "devsystem/browser_qa_v1.py",
    # DevSystem production verification
    "devsystem/production_verify_v1.py",
    "devsystem/production_targets_v1.json",
    # Permanent DevSystem operating contract
    "devsystem/devsystem_manifest_v1.json",
    "devsystem/change_classifier_v1.py",
    "devsystem/permanent_gate_v1.py",
    "devsystem/final_gate_v1.py",
    # CFB active Step 4 path
    "cfb_schedule_v6_runtime_snapshot.py",
    "cfb_over_under_market_adapter_v1.py",
    "cfb_over_under_clean_page_v18.py",
    "data/cfb_runtime_snapshot_v2.json",
    # MLB current certified path
    "sports_api/mlb_step20a_end_to_end_certification_v1.py",
    "sports_api/mlb_step20b_production_release_certification_v1.py",
    "sports_api/mlb_step8d_player_hits_integration_v1.py",
    # WNBA current acceleration path
    "sports_api/wnba_step20b_runtime_acceleration.py",
    "sports_api/wnba_step20b_monte_carlo_acceleration.py",
)

CRITICAL_TESTS = (
    # CFB
    "tests/test_cfb_schedule_v6_runtime_snapshot.py",
    "tests/test_cfb_over_under_market_adapter_v1.py",
    "tests/test_cfb_over_under_clean_page_v18.py",
    "tests/test_cfb_over_under_router_v58.py",
    # MLB
    "tests/test_mlb_step20a_end_to_end_certification_v1.py",
    "tests/test_mlb_step20b_production_release_certification_v1.py",
    "tests/test_mlb_step8d_player_hits_integration_v1.py",
    # WNBA
    "tests/test_wnba_step20b_runtime_acceleration.py",
    "tests/test_wnba_step20b_monte_carlo_acceleration.py",
    "tests/test_wnba_step20b_step2_exact_reuse_timing.py",
    # DevSystem browser QA
    "tests/test_devsystem_browser_qa_v1.py",
    # DevSystem production verification
    "tests/test_devsystem_production_verify_v1.py",
    # Permanent DevSystem operating contract
    "tests/test_devsystem_change_classifier_v1.py",
    "tests/test_devsystem_permanent_gate_v1.py",
)

PYTHON_COMPILE_TARGETS = tuple(
    path
    for path in CRITICAL_FILES
    if path.endswith(".py")
)

# DevSystem Step 2 intentionally changed only workflow trigger metadata to stop
# unrelated PR fan-out. Frozen sports/runtime/model blobs remain hash-protected.
INFRASTRUCTURE_EXEMPT_PREFIXES = (".github/workflows/",)


class ShieldFailure(RuntimeError):
    pass


def _git_blob_sha(path: Path) -> str:
    raw = path.read_bytes()
    return hashlib.sha1(
        f"blob {len(raw)}\0".encode("utf-8") + raw
    ).hexdigest()


def _require_paths(paths: tuple[str, ...], label: str) -> None:
    missing = [path for path in paths if not (ROOT / path).is_file()]
    if missing:
        raise ShieldFailure(f"{label} missing: {missing}")


def _verify_frozen_manifest(path: str) -> tuple[int, int]:
    manifest_path = ROOT / path
    if not manifest_path.is_file():
        raise ShieldFailure(f"frozen manifest missing: {path}")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    exact = payload.get("exact_blobs")
    if not isinstance(exact, dict) or not exact:
        raise ShieldFailure(f"{path} has no exact_blobs contract")

    failures: list[str] = []
    verified = 0
    infrastructure_exemptions = 0
    for rel, expected in sorted(exact.items()):
        if rel.startswith(INFRASTRUCTURE_EXEMPT_PREFIXES):
            infrastructure_exemptions += 1
            continue
        candidate = ROOT / rel
        if not candidate.is_file():
            failures.append(f"{rel}: missing")
            continue
        actual = _git_blob_sha(candidate)
        if actual != expected:
            failures.append(f"{rel}: expected {expected} got {actual}")
        else:
            verified += 1

    if failures:
        raise ShieldFailure(
            f"{path} frozen blob drift:\n" + "\n".join(failures)
        )
    return verified, infrastructure_exemptions


def _assert_finite(value: Any, path: str = "root") -> None:
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ShieldFailure(f"non-finite numeric value at {path}: {value!r}")
        return
    if isinstance(value, dict):
        for key, child in value.items():
            _assert_finite(child, f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _assert_finite(child, f"{path}[{index}]")


def _verify_cfb_snapshot_v2() -> dict[str, int]:
    path = ROOT / "data/cfb_runtime_snapshot_v2.json"
    payload = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=lambda token: (_ for _ in ()).throw(
            ShieldFailure(f"non-standard JSON numeric token: {token}")
        ),
    )
    _assert_finite(payload)

    if payload.get("version") != 2:
        raise ShieldFailure("CFB runtime snapshot must remain version 2")
    games = payload.get("games")
    if not isinstance(games, list) or not games:
        raise ShieldFailure("CFB runtime snapshot V2 games must be non-empty")

    ids: set[str] = set()
    duplicate_ids: list[str] = []
    missing_identity: list[int] = []
    missing_team_ids: list[int] = []

    for index, game in enumerate(games):
        if not isinstance(game, dict):
            raise ShieldFailure(f"CFB snapshot game {index} is not an object")
        required = (
            str(game.get("event_id") or "").strip(),
            str(game.get("game_date") or "").strip(),
            str(game.get("away_team") or "").strip(),
            str(game.get("home_team") or "").strip(),
        )
        if not all(required):
            missing_identity.append(index)
            continue

        event_id = required[0]
        if event_id in ids:
            duplicate_ids.append(event_id)
        ids.add(event_id)

        away = game.get("away") if isinstance(game.get("away"), dict) else {}
        home = game.get("home") if isinstance(game.get("home"), dict) else {}
        if not str(away.get("team_id") or "").strip() or not str(home.get("team_id") or "").strip():
            missing_team_ids.append(index)

    if missing_identity:
        raise ShieldFailure(
            f"CFB snapshot games missing official identity fields: {missing_identity[:20]}"
        )
    if duplicate_ids:
        raise ShieldFailure(
            f"CFB snapshot duplicate official event IDs: {sorted(set(duplicate_ids))[:20]}"
        )
    if missing_team_ids:
        raise ShieldFailure(
            f"CFB snapshot games missing ESPN team IDs: {missing_team_ids[:20]}"
        )

    return {
        "games": len(games),
        "unique_event_ids": len(ids),
    }


def _verify_cfb_market_contract_text() -> None:
    text = (ROOT / "cfb_over_under_market_adapter_v1.py").read_text(
        encoding="utf-8"
    )
    required = (
        'float(semantics.get("projection_weight")) != 0.0',
        '"projection_weight": 0.0',
        '"market_context_only": True',
        '"may_modify_projection": False',
        '"matching_method": "official ESPN event_id only"',
        '"fuzzy_matching": False',
        '"synthetic_ids": False',
    )
    missing = [item for item in required if item not in text]
    if missing:
        raise ShieldFailure(
            "CFB market safety contract drift: " + " | ".join(missing)
        )


def _verify_active_router() -> None:
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    if "streamlit_memory_lazy_router_v58" not in app:
        raise ShieldFailure(
            "active Streamlit entrypoint no longer references router V58; "
            "update the regression shield deliberately if this is intentional"
        )


def _compile_critical_python() -> int:
    compiled = 0
    for rel in PYTHON_COMPILE_TARGETS:
        py_compile.compile(
            str(ROOT / rel),
            doraise=True,
        )
        compiled += 1
    return compiled


def run() -> dict[str, Any]:
    _require_paths(CRITICAL_FILES, "critical file")
    _require_paths(CRITICAL_TESTS, "critical test")

    manifest_results = [
        _verify_frozen_manifest(path)
        for path in FROZEN_MANIFESTS
    ]
    frozen_blob_count = sum(item[0] for item in manifest_results)
    infrastructure_exemptions = sum(item[1] for item in manifest_results)
    snapshot = _verify_cfb_snapshot_v2()
    _verify_cfb_market_contract_text()
    _verify_active_router()
    compiled = _compile_critical_python()

    result = {
        "status": "GREEN",
        "frozen_manifests": len(FROZEN_MANIFESTS),
        "frozen_blobs_verified": frozen_blob_count,
        "infrastructure_exemptions": infrastructure_exemptions,
        "critical_files_verified": len(CRITICAL_FILES),
        "critical_tests_verified": len(CRITICAL_TESTS),
        "python_files_compiled": compiled,
        "cfb_snapshot_games": snapshot["games"],
        "cfb_snapshot_unique_event_ids": snapshot["unique_event_ids"],
        "cfb_market_projection_weight": 0.0,
        "cfb_matching_method": "official ESPN event_id only",
        "cfb_fuzzy_matching": False,
        "cfb_synthetic_ids": False,
    }
    print("DEVSYSTEM_REGRESSION_SHIELD_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


if __name__ == "__main__":
    run()
