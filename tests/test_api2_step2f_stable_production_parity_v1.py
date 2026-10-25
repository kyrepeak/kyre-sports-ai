from __future__ import annotations

from pathlib import Path

import pytest

from api2_step2f_stable_production_parity_v1 import (
    MLB_STABLE_SERVICE,
    STABLE_VERCEL_ALIAS,
    build_page_receipts,
    evaluate_vercel_receipt,
    validate_static_contract,
    visible_page_keys,
)
from sports_api.api.step2f_deployment_receipt_v1 import deployment_receipt_from_env


EXPECTED_COUNTS = {"nfl": 11, "cfb": 5, "nba": 2, "mlb": 12, "wnba": 9}


def test_step2f_surface_is_all_39_visible_pages() -> None:
    keys = visible_page_keys()
    assert len(keys) == 39
    assert {sport for sport, _ in keys} == set(EXPECTED_COUNTS)
    for sport, count in EXPECTED_COUNTS.items():
        assert len([key for key in keys if key[0] == sport]) == count
    assert validate_static_contract() == ()


def test_step2f_page_receipts_reuse_step2e_and_preserve_mlb_stable_service() -> None:
    receipts = build_page_receipts()
    assert len(receipts) == 39
    assert sum(1 for item in receipts if item["step2e_owned"]) == 27
    assert sum(1 for item in receipts if item["sport"] == "mlb") == 12
    assert all(item["stable_service"] == MLB_STABLE_SERVICE for item in receipts if item["sport"] == "mlb")
    assert all(item["stable_service"] == STABLE_VERCEL_ALIAS for item in receipts if item["sport"] != "mlb")
    assert all(item["canonical_target"] for item in receipts if item["step2e_owned"])


def test_step2f_rejects_preview_even_when_sha_matches() -> None:
    sha = "a" * 40
    receipt = {
        "environment": "preview",
        "target_environment": "preview",
        "git_commit_sha": sha,
        "git_commit_ref": "api2-main",
        "production_url": "kyre-sports-api.vercel.app",
    }
    errors = evaluate_vercel_receipt(receipt, expected_sha=sha)
    assert any("production" in error.lower() for error in errors)


def test_step2f_rejects_stale_sha() -> None:
    receipt = {
        "environment": "production",
        "target_environment": "production",
        "git_commit_sha": "b" * 40,
        "git_commit_ref": "api2-main",
        "production_url": "kyre-sports-api.vercel.app",
    }
    errors = evaluate_vercel_receipt(receipt, expected_sha="a" * 40)
    assert any("sha" in error.lower() for error in errors)


def test_step2f_accepts_exact_production_receipt() -> None:
    sha = "c" * 40
    receipt = {
        "environment": "production",
        "target_environment": "production",
        "git_commit_sha": sha,
        "git_commit_ref": "api2-main",
        "production_url": "kyre-sports-api.vercel.app",
    }
    assert evaluate_vercel_receipt(receipt, expected_sha=sha) == ()


def test_deployment_receipt_exposes_only_non_secret_parity_fields() -> None:
    sha = "d" * 40
    receipt = deployment_receipt_from_env(
        {
            "VERCEL_ENV": "production",
            "VERCEL_TARGET_ENV": "production",
            "VERCEL_GIT_COMMIT_SHA": sha,
            "VERCEL_GIT_COMMIT_REF": "api2-main",
            "VERCEL_URL": "kyre-sports-abc.vercel.app",
            "VERCEL_PROJECT_PRODUCTION_URL": "kyre-sports-api.vercel.app",
            "DATABASE_URL": "must-not-leak",
            "TOKEN": "must-not-leak",
        }
    )
    assert receipt["git_commit_sha"] == sha
    assert receipt["environment"] == "production"
    assert receipt["target_environment"] == "production"
    assert receipt["git_commit_ref"] == "api2-main"
    assert receipt["production_url"] == "kyre-sports-api.vercel.app"
    assert "DATABASE_URL" not in receipt
    assert "TOKEN" not in receipt
    assert "must-not-leak" not in repr(receipt)


def test_vercel_entrypoint_mounts_step2f_receipt_router() -> None:
    source = Path("kyre_sports_api_vercel_v1.py").read_text()
    assert "step2f_deployment_receipt_v1" in source
    assert "app.include_router(step2f_deployment_receipt_router)" in source
    assert '"/api/v1/system/deployment-receipt"' in Path(
        "sports_api/api/step2f_deployment_receipt_v1.py"
    ).read_text()
