from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def pytest_collection_modifyitems(session, config, items):
    """Keep the permanent CFB lane aware of the active V150 Game Total route."""
    if not any(item.path.name.startswith("test_cfb_") for item in items):
        return

    required = (
        ROOT / "cfb_game_total_clean_page_v1.py",
        ROOT / "streamlit_memory_lazy_router_v150.py",
    )
    missing = [path.name for path in required if not path.exists()]
    assert not missing, "missing active CFB V150 contract files: " + ", ".join(missing)
