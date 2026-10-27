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


def test_manifest_marks_archive_complete_but_does_not_false_freeze() -> None:
    supabase = MANIFEST["supabase"]
    archive = supabase["migration_payload_archive"]
    assert supabase["migration_payload_archive_state"] == "COMPLETE"
    assert archive["base64_sha256"] == INDEX["base64_sha256"]
    assert archive["verified_migration_count"] == 38
    assert archive["verified_md5_mismatches"] == 0
    assert archive["verification_state"] == "GREEN"
    assert MANIFEST["vercel"]["stale_preview_env_count"] == 9
    assert MANIFEST["freeze"]["state"] == "OPEN"
