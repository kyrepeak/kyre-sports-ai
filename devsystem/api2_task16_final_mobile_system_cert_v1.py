"""API 2 Task 16 — verification-only final mobile/system certification."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

CERTIFICATION_MARKER = "API2_TASK16_FINAL_MOBILE_SYSTEM_CERT_GREEN"
EXPECTED_PRODUCTION_URL = "https://pickvault.streamlit.app"
EXPECTED_FALLBACK_WORKFLOW_COUNT = 30
EXPECTED_BLOBS = {
    "sports_api/nfl_game_totals_total_projection_v1.py": "0738d4f9e995c9d1423118b8fc9a95a799c8c55d",
    "nfl_hub_v18.py": "dfcf29636a10c798de037378624188f245f657e2",
    "nfl_game_totals_hub_v8_1.py": "686cbe7eac7b35398dc754a04f8cdec218f76c6a",
    "nfl_game_totals_hub_v9.py": "0f9e48384daf8b4f79f2edabdf9d234f90d19076",
    "nfl_game_totals_hub_v10.py": "c22485c186e2f53c3b0a6b1302375dd9bb25468a",
    "nfl_game_totals_market_read_v1.py": "ca86561ffbb329f686df752afdfc95da1f210ba3",
    "nfl_hub_v36.py": "97bd832a46cf5bdab1b8a1e6162a8c9282dfeb01",
    "streamlit_memory_lazy_router_v97.py": "e5fffd68c08365a1abd7c449c1aa1a98aef177a6",
}


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    payload = f"blob {len(data)}\0".encode("utf-8") + data
    return hashlib.sha1(payload).hexdigest()


def _read(root: Path, rel: str) -> str:
    return (root / rel).read_text(encoding="utf-8")


def audit(
    root: Path = Path("."),
    *,
    blob_resolver: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    root = Path(root)
    failures: list[str] = []
    checks: dict[str, bool] = {}

    for rel, expected in EXPECTED_BLOBS.items():
        try:
            actual = blob_resolver(rel) if blob_resolver is not None else git_blob_sha(root / rel)
        except Exception as exc:
            actual = ""
            failures.append(f"blob:{rel}:unreadable:{type(exc).__name__}")
        ok = actual == expected
        checks[f"blob:{rel}"] = ok
        if not ok and not any(item.startswith(f"blob:{rel}:unreadable") for item in failures):
            failures.append(f"blob:{rel}:expected={expected}:actual={actual}")

    required_markers: dict[str, tuple[str, ...]] = {
        "nfl_game_totals_hub_v8_1.py": (
            "AUTO_ADVANCE_EMPTY_TODAY = True",
            "NEXT_SLATE_LOOKAHEAD_DAYS = 14",
            "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0",
            "STAKE_SIZING_ENABLED = False",
            "WAGER_ACTIONS_ENABLED = False",
            "clear_router_caches()",
            "➡️ Next Game Day",
            "🔄 Reload Data",
            "use_container_width=True",
        ),
        "nfl_game_totals_hub_v9.py": (
            "PAGE_BUILD_STEP = 9",
            "PAGE_BUILD_TOTAL = 10",
            "MARKET_COMPARISON_ENABLED = True",
            "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0",
            "STAKE_SIZING_ENABLED = False",
            "WAGER_ACTIONS_ENABLED = False",
            "@media(max-width:760px){.kgt-read-grid{grid-template-columns:1fr 1fr}}",
            "build_market_final_read(",
        ),
        "nfl_game_totals_hub_v10.py": (
            "PAGE_BUILD_STEP = 10",
            "PAGE_BUILD_TOTAL = 10",
            "FINAL_CERTIFICATION_ENABLED = True",
            "MARKET_COMPARISON_ENABLED = True",
            "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0",
            "STAKE_SIZING_ENABLED = False",
            "WAGER_ACTIONS_ENABLED = False",
            '("10", "FINAL CERTIFICATION", True)',
        ),
        "nfl_game_totals_market_read_v1.py": (
            "SPORTSBOOK_PROJECTION_WEIGHT = 0.0",
            "STAKE_SIZING_ENABLED = False",
            "WAGER_ACTIONS_ENABLED = False",
            '"comparison_only": True',
        ),
        "nfl_hub_v36.py": (
            "import nfl_hub_v35 as base",
            'if market == "Game Total":',
            "from nfl_game_totals_hub_v10 import render_nfl_game_totals_hub",
            "return base.render_nfl_hub(market)",
        ),
        "streamlit_memory_lazy_router_v97.py": (
            'ACTIVE_NFL_HUB = "nfl_hub_v36"',
            'PASSING_YARDS_MARKET = "Passing Yards"',
            'GAME_TOTAL_MARKET = "Game Total"',
            "if market not in {PASSING_YARDS_MARKET, GAME_TOTAL_MARKET}:",
        ),
    }

    for rel, markers in required_markers.items():
        try:
            source = _read(root, rel)
        except Exception as exc:
            failures.append(f"source:{rel}:unreadable:{type(exc).__name__}")
            continue
        for marker in markers:
            key = f"marker:{rel}:{marker}"
            ok = marker in source
            checks[key] = ok
            if not ok:
                failures.append(f"marker:{rel}:missing:{marker}")

    forbidden_markers = {
        "nfl_game_totals_hub_v8_1.py": (
            "NEXT_SLATE_LOOKAHEAD_DAYS = 0",
            "STAKE_SIZING_ENABLED = True",
            "WAGER_ACTIONS_ENABLED = True",
            "st.cache_data.clear()",
            "st.cache_resource.clear()",
        ),
        "nfl_game_totals_hub_v9.py": (
            "STAKE_SIZING_ENABLED = True",
            "WAGER_ACTIONS_ENABLED = True",
        ),
        "nfl_game_totals_hub_v10.py": (
            "STAKE_SIZING_ENABLED = True",
            "WAGER_ACTIONS_ENABLED = True",
        ),
        "nfl_game_totals_market_read_v1.py": (
            "STAKE_SIZING_ENABLED = True",
            "WAGER_ACTIONS_ENABLED = True",
        ),
    }
    for rel, markers in forbidden_markers.items():
        try:
            source = _read(root, rel)
        except Exception:
            continue
        for marker in markers:
            if marker in source:
                failures.append(f"forbidden:{rel}:{marker}")

    manifest_path = root / "devsystem/runless_legacy_proof_workflows_v1.txt"
    try:
        manifest_lines = [
            line.strip()
            for line in manifest_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
    except Exception as exc:
        manifest_lines = []
        failures.append(f"manifest:unreadable:{type(exc).__name__}")
    fallback_count = len(manifest_lines)
    if fallback_count != EXPECTED_FALLBACK_WORKFLOW_COUNT:
        failures.append(f"fallback_workflow_count:expected={EXPECTED_FALLBACK_WORKFLOW_COUNT}:actual={fallback_count}")
    if len(set(manifest_lines)) != fallback_count:
        failures.append("fallback_manifest:duplicates")
    required_fallback = ".github/workflows/nfl-passing-yards-live-source-cert-v1.yml"
    if required_fallback not in manifest_lines:
        failures.append(f"fallback_manifest:missing:{required_fallback}")

    production_url = ""
    targets_path = root / "devsystem/production_targets_v1.json"
    try:
        payload = json.loads(targets_path.read_text(encoding="utf-8"))
        production_url = str(payload.get("streamlit", {}).get("url") or "")
    except Exception as exc:
        failures.append(f"production_targets:unreadable:{type(exc).__name__}")
    if production_url != EXPECTED_PRODUCTION_URL:
        failures.append(f"production_url:expected={EXPECTED_PRODUCTION_URL}:actual={production_url}")

    return {
        "ready": not failures,
        "checks": checks,
        "failures": failures,
        "sportsbook_projection_influence": 0.0,
        "stake_sizing_enabled": False,
        "wager_actions_enabled": False,
        "fallback_workflow_count": fallback_count,
        "production_url": production_url,
        "certification_marker": CERTIFICATION_MARKER if not failures else "",
    }


def main() -> int:
    report = audit()
    print(json.dumps(report, sort_keys=True))
    if not report["ready"]:
        return 1
    print(CERTIFICATION_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
