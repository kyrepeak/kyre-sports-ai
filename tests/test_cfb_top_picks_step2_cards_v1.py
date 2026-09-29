from __future__ import annotations

from pathlib import Path
import ast


PAGE_PATH = Path("cfb_top_picks_page_v2.py")
ROUTER_PATH = Path("streamlit_memory_lazy_router_v242.py")
APP_PATH = Path("app.py")

PAGE = PAGE_PATH.read_text(encoding="utf-8")
ROUTER = ROUTER_PATH.read_text(encoding="utf-8")
APP = APP_PATH.read_text(encoding="utf-8")


def _sample_rows():
    tree = ast.parse(PAGE)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "SAMPLE_LAYOUT_ROWS":
                    return ast.literal_eval(node.value)
    raise AssertionError("SAMPLE_LAYOUT_ROWS missing")


def test_step2_has_exactly_ten_compact_cards():
    rows = _sample_rows()
    assert len(rows) == 10
    assert [row["rank"] for row in rows] == list(range(1, 11))
    assert 'data-testid="cfb-top-picks-card-{rank}"' in PAGE
    assert 'data-testid="cfb-top-picks-card-board"' in PAGE


def test_step2_preserves_approved_card_fields():
    rows = _sample_rows()
    required = {"rank","away","home","time","network","market","pick","odds","probability","toughness","toughness_label"}
    assert all(required <= set(row) for row in rows)
    assert {row["market"] for row in rows} == {"MONEYLINE","SPREAD","OVER/UNDER"}
    assert {row["toughness_label"] for row in rows} == {"Easy","Medium","Tough"}


def test_step2_rows_are_collapsed_and_do_not_implement_step4_details():
    assert 'data-expanded="false"' in PAGE
    forbidden = ("Why This Pick","Actual Matchup History","Key Benefits / Edge","st.expander(")
    assert all(token not in PAGE for token in forbidden)


def test_step2_is_explicit_layout_preview_not_real_ranking_engine():
    assert "LAYOUT_PREVIEW = True" in PAGE
    assert "live daily rankings connect in Step 3" in PAGE
    forbidden = ("rank_top_picks(","calculate_probability(","toughness_score(","sportsbook_probability")
    assert all(token not in PAGE for token in forbidden)


def test_v242_adds_only_top_picks_page_v2_over_frozen_v241():
    assert "import streamlit_memory_lazy_router_v241 as prior" in ROUTER
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v241"' in ROUTER
    assert 'TOP_PICKS_PAGE = "cfb_top_picks_page_v2"' in ROUTER
    assert "return prior.render_app()" in ROUTER
    assert "MAY_MODIFY_EXISTING_CFB_PRODUCTS = False" in ROUTER
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in ROUTER


def test_app_activates_v242_and_retains_v241_compatibility():
    assert "from streamlit_memory_lazy_router_v242 import record_bootstrap_import_ms, render_app" in APP
    assert "Frozen V241 compatibility" in APP
