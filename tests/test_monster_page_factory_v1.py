from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from sports_api.monster_dependency_map_v1 import build_dependency_map
from sports_api.monster_page_factory_v1 import (
    MAY_MODIFY_PROJECTION,
    MAY_MODIFY_SOURCE_DATA,
    PROJECTION_WEIGHT,
    ComponentKind,
    ComponentSpec,
    PageFactoryError,
    compile_page,
    moneyline_page,
    page_from_preset,
    player_prop_page,
    render_page,
    totals_page,
    with_component,
)

ROOT = Path(__file__).resolve().parents[1]


def _required_totals_payload():
    return {
        "matchup": {"away": "Dallas", "home": "Arizona"},
        "team_comparison": {"away": {}, "home": {}},
        "projection": {"total": 47.5},
    }


def test_nfl_totals_shell_is_one_call_and_reuses_page_bones():
    page = totals_page("NFL")

    assert page.title == "NFL Over/Under"
    assert page.market == "Game Total"
    assert page.sport == "NFL"
    assert [component.key for component in page.components] == [
        "matchup",
        "team-comparison",
        "injuries",
        "environment",
        "market",
        "projection",
        "simulation",
        "confidence",
        "sources",
        "diagnostics",
    ]
    assert page.components[0].required is True
    assert page.components[5].required is True


def test_same_totals_factory_works_across_sports_without_model_logic():
    cfb = totals_page("CFB")
    nfl = totals_page("NFL")
    nba = totals_page("NBA")

    assert cfb.sport == "College Football"
    assert nfl.sport == "NFL"
    assert nba.sport == "NBA"
    assert [c.kind for c in cfb.components] == [c.kind for c in nfl.components]
    assert [c.kind for c in nfl.components] == [c.kind for c in nba.components]


def test_compile_fails_closed_on_missing_required_but_skips_optional():
    page = totals_page("NFL")
    payload = {"matchup": {"away": "A", "home": "B"}}

    plan = compile_page(page, payload)

    assert plan.ready is False
    assert plan.missing_required == ("team_comparison", "projection")
    assert "injuries" in plan.skipped_optional
    assert "environment" in plan.skipped_optional


def test_optional_components_degrade_gracefully():
    page = totals_page("NFL")
    plan = compile_page(page, _required_totals_payload())

    assert plan.ready is True
    assert plan.ready_keys == ("matchup", "team-comparison", "projection")
    assert "market" in plan.skipped_optional
    assert "sources" in plan.skipped_optional


def test_render_dispatches_in_spec_order_without_mutating_payload():
    page = totals_page("NFL")
    payload = _required_totals_payload()
    payload["market"] = {"book": "context only"}
    before = deepcopy(payload)
    calls = []

    def renderer(spec, value, context):
        calls.append((spec.key, value, context.page.page_id))

    renderers = {kind: renderer for kind in ComponentKind}
    result = render_page(page, payload, renderers)

    assert [call[0] for call in calls] == [
        "matchup",
        "team-comparison",
        "market",
        "projection",
    ]
    assert result.rendered == (
        "matchup",
        "team-comparison",
        "market",
        "projection",
    )
    assert payload == before


def test_render_refuses_missing_required_payload():
    page = totals_page("NFL")

    with pytest.raises(PageFactoryError, match="missing required payload"):
        render_page(page, {"matchup": {"away": "A", "home": "B"}}, {})


def test_renderer_registry_is_explicit_and_fails_if_component_renderer_missing():
    page = totals_page("NFL")
    payload = _required_totals_payload()

    with pytest.raises(PageFactoryError, match="no renderer registered"):
        render_page(page, payload, {})


def test_moneyline_and_player_prop_presets_share_factory_contract():
    moneyline = moneyline_page("MLB")
    prop = player_prop_page("NFL", "Passing Yards")

    assert moneyline.market == "Moneyline"
    assert any(c.kind is ComponentKind.PROJECTION for c in moneyline.components)
    assert prop.market == "Passing Yards"
    assert prop.components[0].kind is ComponentKind.PLAYER_HEADER
    assert page_from_preset("ml", "MLB") == moneyline
    assert page_from_preset("player-prop", "NFL", prop="Passing Yards") == prop


def test_page_specs_are_immutable_and_extension_is_additive():
    page = totals_page("NFL")
    custom = ComponentSpec(
        key="custom-note",
        title="Custom Note",
        kind=ComponentKind.DIAGNOSTICS,
        data_key="custom_note",
    )

    extended = with_component(page, custom, after="confidence")

    assert "custom-note" not in [component.key for component in page.components]
    keys = [component.key for component in extended.components]
    assert keys[keys.index("confidence") + 1] == "custom-note"


def test_factory_has_zero_projection_and_source_data_authority():
    assert PROJECTION_WEIGHT == 0.0
    assert MAY_MODIFY_PROJECTION is False
    assert MAY_MODIFY_SOURCE_DATA is False


def test_factory_has_no_streamlit_runtime_dependency():
    source = (ROOT / "sports_api" / "monster_page_factory_v1.py").read_text(encoding="utf-8")
    assert "import streamlit" not in source
    assert "from streamlit" not in source


def test_dependency_map_proves_factory_is_not_wired_into_production_entrypoints():
    dependency_map = build_dependency_map(ROOT)
    report = dependency_map.impact_report("sports_api/monster_page_factory_v1.py")

    assert report["status"] == "OK"
    assert report["impacted_entrypoints"] == []
    assert "app.py" not in report["transitive_dependents"]
    assert "sports_api/main.py" not in report["transitive_dependents"]
