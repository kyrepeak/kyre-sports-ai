from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "supabase" / "source_parity_ledger" / "archive-v1"
INDEX = json.loads((ARCHIVE / "index.json").read_text())
MANIFEST = json.loads((ROOT / "devsystem" / "guardian_source_of_truth_configuration_parity_v1.json").read_text())


def _archive_b64() -> str:
    return "".join((ARCHIVE / name).read_text() for name in INDEX["chunks"])


def test_archive_transport_is_byte_exact() -> None:
    payload = _archive_b64()
    assert len(payload) == 59788 == INDEX["base64_chars"]
    assert hashlib.sha256(payload.encode()).hexdigest() == INDEX["base64_sha256"]
    decoded = base64.b64decode(payload, validate=True)
    assert len(decoded) == 44840 == INDEX["decoded_bytes"]


def test_archive_index_covers_all_39_live_migrations() -> None:
    assert INDEX["base_archive_migration_count"] == 38
    assert INDEX["supplemental_migration_count"] == 1
    assert INDEX["source_parity_migration_count"] == 39
    assert INDEX["migration_count"] == 39
    assert INDEX["supplemental_migrations"] == ["supplemental-39.json"]
    supplemental = json.loads((ARCHIVE / "supplemental-39.json").read_text())
    assert supplemental["version"] == "20261027183826"
    assert supplemental["name"] == "guardian_source_parity_archive_temp_cleanup_v1"
    assert supplemental["statements"] == ["drop table if exists kyre_runtime.guardian_source_parity_archive_temp;"]
    assert supplemental["content_md5"] == "91084b96cc600dae4245172812babb58"


def test_manifest_marks_archive_complete_and_freeze_candidate() -> None:
    supabase = MANIFEST["supabase"]
    archive = supabase["migration_payload_archive"]
    assert supabase["migration_payload_archive_state"] == "COMPLETE"
    assert archive["base64_sha256"] == INDEX["base64_sha256"]
    assert archive["verified_migration_count"] == 39
    assert archive["verified_md5_mismatches"] == 0
    assert archive["verification_state"] == "GREEN"
    assert MANIFEST["vercel"]["stale_preview_env_count"] == 0
    assert MANIFEST["freeze"]["state"] == "FROZEN"
