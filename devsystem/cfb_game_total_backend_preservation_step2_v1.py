from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

BACKEND_FREEZE_TOKEN = "CFB_GAME_TOTAL_NATIVE_WEBSITE_REBUILD_STEP2_BACKEND_PRESERVATION_V1_FROZEN"

PROTECTED_BACKEND_BLOBS = {
    "cfb_freeze_manifest_v12.json": "3ff2a727967e80dddbe03f747d9f32090cc39539",
    "cfb_game_total_model_v1.py": "88e98c2b78c689e48f81f049cb1a64c0e958e964",
    "cfb_game_total_final_v1.py": "78fbeaeb77e3101cc83c579b15f9cd6d485df952",
    "cfb_game_total_slate_v1.py": "777beb82b1dc3dd7df76f8f4d8d37f87eeb9b872",
    "cfb_game_total_model_input_v1.py": "0d270126b6265ec22c29ea0a73faaf57235f4b8e",
    "cfb_game_total_slate_v2.py": "1acc2859bc1666b968e8ea54fb7fadc905781d81",
    "cfb_game_total_step3_form_v1.py": "ea7bad697064625588ec31971fe642446d2f8b34",
}

MANIFEST_NATIVE_BLOBS = {
    "cfb_game_total_model_v1.py": PROTECTED_BACKEND_BLOBS["cfb_game_total_model_v1.py"],
    "cfb_game_total_final_v1.py": PROTECTED_BACKEND_BLOBS["cfb_game_total_final_v1.py"],
    "cfb_game_total_slate_v1.py": PROTECTED_BACKEND_BLOBS["cfb_game_total_slate_v1.py"],
}


class BackendPreservationFailure(RuntimeError):
    pass


def _git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("utf-8")
    return hashlib.sha1(header + data).hexdigest()


def _require(condition: bool, token: str) -> None:
    if not condition:
        raise BackendPreservationFailure(token)


def _read_text(root: Path, relative_path: str) -> str:
    path = root / relative_path
    _require(path.is_file(), f"BACKEND_ARTIFACT_MISSING:{relative_path}")
    return path.read_text(encoding="utf-8")


def _read_manifest(root: Path) -> dict[str, Any]:
    path = root / "cfb_freeze_manifest_v12.json"
    _require(path.is_file(), "BACKEND_MANIFEST_MISSING")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise BackendPreservationFailure("BACKEND_MANIFEST_INVALID") from exc
    _require(isinstance(payload, dict), "BACKEND_MANIFEST_INVALID")
    return payload


def validate_backend_preservation(root: str | Path) -> dict[str, Any]:
    base = Path(root)

    observed: dict[str, str] = {}
    for relative_path, expected_blob in PROTECTED_BACKEND_BLOBS.items():
        path = base / relative_path
        _require(path.is_file(), f"BACKEND_ARTIFACT_MISSING:{relative_path}")
        observed_blob = _git_blob_sha(path)
        observed[relative_path] = observed_blob
        _require(
            observed_blob == expected_blob,
            f"BACKEND_BLOB_DRIFT:{relative_path}:{expected_blob}:{observed_blob}",
        )

    manifest = _read_manifest(base)
    _require(manifest.get("completed_sections", {}).get("game_total") is True, "GAME_TOTAL_NOT_COMPLETE")
    _require(manifest.get("cfb_build_complete") is True, "CFB_BUILD_NOT_COMPLETE")

    exact_blobs = manifest.get("exact_blobs") or {}
    for relative_path, expected_blob in MANIFEST_NATIVE_BLOBS.items():
        _require(
            exact_blobs.get(relative_path) == expected_blob,
            f"MANIFEST_BACKEND_BLOB_DRIFT:{relative_path}",
        )

    step11 = manifest.get("step11_contract") or {}
    _require(step11.get("market") == "Game Total", "STEP11_MARKET_DRIFT")
    _require(step11.get("projected_combined_total_active") is True, "STEP11_PROJECTION_DISABLED")
    _require(step11.get("exact_total_probability_active") is True, "STEP11_EXACT_PROBABILITY_DISABLED")
    _require(step11.get("total_band_probability_active") is True, "STEP11_BAND_PROBABILITY_DISABLED")
    _require(step11.get("sportsbook_total_input") is False, "STEP11_SPORTSBOOK_TOTAL_DRIFT")
    _require(step11.get("sportsbook_price_input") is False, "STEP11_SPORTSBOOK_PRICE_DRIFT")
    _require(step11.get("market_implied_probability_input") is False, "STEP11_MARKET_PROBABILITY_DRIFT")
    _require(step11.get("monte_carlo_active") is False, "STEP11_MONTE_CARLO_DRIFT")
    _require(step11.get("pregame_only") is True, "STEP11_PREGAME_CONTRACT_DRIFT")

    step12 = manifest.get("step12_contract") or {}
    _require(step12.get("market") == "Game Total", "STEP12_MARKET_DRIFT")
    _require(step12.get("section_complete") is True, "STEP12_SECTION_NOT_COMPLETE")
    _require(step12.get("final_forecast_active") is True, "STEP12_FINAL_FORECAST_DISABLED")
    _require(step12.get("betting_pick_active") is False, "STEP12_BETTING_PICK_DRIFT")
    _require(step12.get("sportsbook_total_input") is False, "STEP12_SPORTSBOOK_TOTAL_DRIFT")
    _require(step12.get("sportsbook_price_input") is False, "STEP12_SPORTSBOOK_PRICE_DRIFT")
    _require(step12.get("market_implied_probability_input") is False, "STEP12_MARKET_PROBABILITY_DRIFT")
    _require(step12.get("edge_or_ev_active") is False, "STEP12_EDGE_EV_DRIFT")
    _require(step12.get("monte_carlo_active") is False, "STEP12_MONTE_CARLO_DRIFT")
    _require(step12.get("pregame_only") is True, "STEP12_PREGAME_CONTRACT_DRIFT")

    model_input_source = _read_text(base, "cfb_game_total_model_input_v1.py")
    _require("SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in model_input_source, "MODEL_INPUT_SPORTSBOOK_INFLUENCE_DRIFT")
    _require("MAY_MODIFY_PROJECTION = False" in model_input_source, "MODEL_INPUT_PROJECTION_GUARD_DRIFT")

    slate_v2_source = _read_text(base, "cfb_game_total_slate_v2.py")
    for token in (
        "raw_model = frozen.raw_model",
        "final_model = frozen.final_model",
        "team_data = frozen.team_data",
        '"sportsbook_input_used": False',
        '"market_price_used": False',
        '"market_probability_used": False',
        '"monte_carlo_used": False',
    ):
        _require(token in slate_v2_source, f"SLATE_V2_FROZEN_BOUNDARY_DRIFT:{token}")

    step3_source = _read_text(base, "cfb_game_total_step3_form_v1.py")
    _require("MAY_MODIFY_PROJECTION = False" in step3_source, "STEP3_PRESENTATION_GUARD_DRIFT")
    _require("SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in step3_source, "STEP3_SPORTSBOOK_INFLUENCE_DRIFT")

    return {
        "status": "GREEN",
        "freeze_token": BACKEND_FREEZE_TOKEN,
        "protected_artifact_count": len(PROTECTED_BACKEND_BLOBS),
        "protected_backend_blobs": observed,
        "step11_model_version": str(step11.get("model_version") or ""),
        "step12_model_version": str(step12.get("final_model_version") or ""),
        "step12_final_forecast_active": bool(step12.get("final_forecast_active")),
        "step12_betting_pick_active": bool(step12.get("betting_pick_active")),
        "sportsbook_projection_influence": 0.0,
        "sportsbook_input_used": False,
        "market_price_used": False,
        "market_probability_used": False,
        "monte_carlo_used": False,
        "product_runtime_mutated": False,
    }


__all__ = [
    "BACKEND_FREEZE_TOKEN",
    "PROTECTED_BACKEND_BLOBS",
    "BackendPreservationFailure",
    "validate_backend_preservation",
]
