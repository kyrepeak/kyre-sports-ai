from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "supabase" / "migrations" / "20261013_runless_v2_search_path_hardening.sql"


def test_runless_v2_legal_transition_has_immutable_search_path():
    assert PATCH.exists(), "live hardening migration must exist"
    text = PATCH.read_text().lower()
    assert "function runless_v2.is_legal_transition" in text
    assert "set search_path = pg_catalog" in text
