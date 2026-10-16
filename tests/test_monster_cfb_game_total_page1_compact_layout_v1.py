from importlib import util
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "cfb_game_total_page1_compact_layout_v1.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page1_unified_repair_v1.py"
PAGE2 = ROOT / "cfb_game_total_page2_same_page_shell_repair_v1.py"


def _load_wrapper():
    assert WRAPPER.is_file(), "RED: compact Page-1 presentation wrapper is not implemented yet"
    spec = util.spec_from_file_location("cfb_page1_compact_test_target", WRAPPER)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_compact_wrapper_exists_and_is_presentation_only():
    module = _load_wrapper()
    assert module.MAY_MODIFY_MODEL is False
    assert module.MAY_MODIFY_PROJECTION is False
    assert module.MAY_MODIFY_PROBABILITY is False
    assert module.MAY_MODIFY_RANKING is False
    assert module.MAY_MODIFY_SELECTION is False
    assert module.MAY_MODIFY_PAGE2 is False
    assert module.MAY_MODIFY_OTHER_SPORTS is False
    assert module.NETWORK_CALLS_ADDED == 0
    assert module.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0


def test_analysis_steps_become_one_compact_exclusive_accordion():
    module = _load_wrapper()
    html = '<details class="gt159-step x" data-testid="gt157-step-2" data-x="1" open><summary>Team Profile</summary><div>body</div></details>'
    compact = module.compact_step_html(html)
    opening = compact.split(">", 1)[0] + ">"
    assert " open" not in opening
    assert 'name="gt-page1-analysis"' in opening
    assert 'data-testid="gt157-step-2"' in opening
    assert "Team Profile" in compact


def test_non_analysis_html_is_byte_preserved():
    module = _load_wrapper()
    html = '<div class="other">keep me exactly</div>'
    assert module.compact_step_html(html) == html


def test_mobile_css_prevents_identity_and_team_evidence_single_column_towers():
    source = WRAPPER.read_text(encoding="utf-8")
    assert "PAGE1_COMPACT_LAYOUT_CSS" in source
    assert ".gt165-team-pair" in source
    assert ".gt227-grid" in source
    assert "grid-template-columns:minmax(0,1fr) 24px minmax(0,1fr)!important" in source
    assert ".gt227-vs" in source and "display:grid!important" in source
    assert ".gt165-vs" in source and "display:grid!important" in source


def test_page1_router_activates_compact_wrapper_while_page2_stays_on_frozen_v45():
    router = ROUTER.read_text(encoding="utf-8")
    page2 = PAGE2.read_text(encoding="utf-8")
    assert 'PAGE1_REPAIR_ROUTE = "cfb_game_total_page1_compact_layout_v1"' in router
    assert "import cfb_game_total_clean_page_v45 as page1" in page2
    assert "cfb_game_total_page1_compact_layout_v1" not in page2


def test_wrapper_does_not_introduce_provider_or_model_code():
    source = WRAPPER.read_text(encoding="utf-8")
    forbidden = ["requests.", "httpx.", "urllib.request", "sportsbook", "recompute_probability", "project_total("]
    for token in forbidden:
        assert token not in source
