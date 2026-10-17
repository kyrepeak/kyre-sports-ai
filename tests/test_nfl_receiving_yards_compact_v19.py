from importlib.util import find_spec
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v19_compact_owner_exists_over_frozen_v18():
    assert find_spec("nfl_receiving_yards_hub_v19") is not None, "V19 compact owner must exist"
    source = (ROOT / "nfl_receiving_yards_hub_v19.py").read_text(encoding="utf-8")
    assert 'FROZEN_PRIOR = "nfl_receiving_yards_hub_v18"' in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "prior.render_nfl_receiving_yards_hub()" in source


def test_v19_removes_redundant_deep_identity_card_and_caps_images():
    source = (ROOT / "nfl_receiving_yards_hub_v19.py").read_text(encoding="utf-8")
    assert ".krecv19-compact .krecv2-card{display:none!important}" in source
    assert ".krecv19-compact img{max-width:64px!important;max-height:64px!important" in source
    assert ".krecv19-compact .krecv14-player" in source
    assert ".krecv19-compact .krecv15-history" in source
    assert ".krecv19-compact .krecv6-wrap" in source
    assert ".krecv19-compact .krecv7-wrap" in source


def test_v19_wraps_frozen_v15_player_stack_without_changing_payload():
    source = (ROOT / "nfl_receiving_yards_hub_v19.py").read_text(encoding="utf-8")
    assert "_ORIGINAL_PLAYER_CARD_V15" in source
    assert "return f'<div class=\"krecv19-compact\">{stack}</div>'" in source
    assert "prior.render_nfl_receiving_yards_hub()" in source


def test_v19_style_only_markdown_does_not_create_dead_vertical_blocks():
    source = (ROOT / "nfl_receiving_yards_hub_v19.py").read_text(encoding="utf-8")
    assert "_compact_markdown_v19" in source
    assert 'if stripped.startswith("<style>") and stripped.endswith("</style>"):' in source
    assert "return st.html(body)" in source
    assert "st.markdown = _compact_markdown_v19" in source
    assert "st.markdown = original_markdown" in source
    assert "st.html(_COMPACT_CSS)" in source


def test_universal_router_activates_receiving_v19():
    source = (ROOT / "streamlit_memory_lazy_router_universal_nav_v2.py").read_text(encoding="utf-8")
    assert 'RECEIVING_V19_MODULE = "nfl_receiving_yards_hub_v19"' in source
    assert "module_name = RECEIVING_V19_MODULE" in source


def test_v18_and_projection_engine_remain_untouched_by_compact_successor():
    v19 = (ROOT / "nfl_receiving_yards_hub_v19.py").read_text(encoding="utf-8")
    assert "build_player_projection" not in v19
    assert "projection_yards" not in v19
    assert "probability" not in v19.lower()
    assert "sportsbook" in v19.lower()
