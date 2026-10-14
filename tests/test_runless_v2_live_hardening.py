from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEARCH_PATH_PATCH = ROOT / "supabase" / "migrations" / "20261013_runless_v2_search_path_hardening.sql"
FK_INDEX_PATCH = ROOT / "supabase" / "migrations" / "20261013_runless_v2_fk_index_hardening.sql"


def test_runless_v2_legal_transition_has_immutable_search_path():
    assert SEARCH_PATH_PATCH.exists(), "live hardening migration must exist"
    text = SEARCH_PATH_PATCH.read_text().lower()
    assert "function runless_v2.is_legal_transition" in text
    assert "set search_path = pg_catalog" in text


def test_runless_v2_fk_columns_have_covering_indexes():
    assert FK_INDEX_PATCH.exists(), "FK index hardening migration must exist"
    text = FK_INDEX_PATCH.read_text().lower()
    assert "on runless_v2.failed_fingerprints (proof_id)" in text
    assert "on runless_v2.workstream_leases (owner_proof_id)" in text
