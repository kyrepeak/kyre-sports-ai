import json
import re
from copy import deepcopy

import pytest

from devsystem.monster_coding_intelligence_case_contract_v1 import (
    AUTO_MUTATE,
    GITHUB_ACTIONS_FALLBACK,
    MAY_MODIFY_PRODUCT_RUNTIME,
    MUTATION_AUTHORITY_GRANTED,
    NETWORK_CALLS,
    IntelligenceCaseValidationFailure,
    normalize_intelligence_case,
    render_intelligence_case,
    serialize_intelligence_case,
)


BASE_CASE = {
    "workstream_id": "CFB-CARDS-DEBUG",
    "goal": "CFB cards appear normally.",
    "visible_symptom": "Expected games / cards are absent.",
    "success_condition": "Expected slate appears with verified underlying data.",
    "solved_when": "Expected cards are visibly present with verified data.",
    "constraints": ["Use existing multi-source architecture"],
    "do_not_change": ["Visual design", "Navigation"],
    "required_changes": None,
    "affected_systems": ["Schedule", "Rendering"],
    "environment": None,
    "current_known_state": None,
    "suspected_subsystems": ["rendering", "schedule"],
}


def test_valid_case_normalizes_required_fields_and_controls():
    out = normalize_intelligence_case(BASE_CASE)
    assert out["schema_version"] == 1
    assert out["workstream_id"] == "cfb-cards-debug"
    assert out["goal"] == "cfb cards appear normally"
    assert out["visible_symptom"] == "expected games / cards are absent"
    assert out["success_condition"] == "expected slate appears with verified underlying data"
    assert out["solved_when"] == "expected cards are visibly present with verified data"
    assert out["network_calls"] is False
    assert out["auto_mutate"] is False
    assert out["may_modify_product_runtime"] is False
    assert out["mutation_authority_granted"] is False
    assert out["github_actions_fallback"] == 0


def test_input_mapping_is_not_mutated():
    source = deepcopy(BASE_CASE)
    before = deepcopy(source)
    normalize_intelligence_case(source)
    assert source == before


def test_missing_optional_context_remains_explicitly_unknown():
    packet = {key: BASE_CASE[key] for key in (
        "workstream_id", "goal", "visible_symptom", "success_condition", "solved_when"
    )}
    out = normalize_intelligence_case(packet)
    for field in (
        "constraints", "do_not_change", "required_changes", "affected_systems",
        "environment", "current_known_state", "suspected_subsystems",
    ):
        assert out[field] is None


def test_explicit_empty_collections_remain_known_empty():
    packet = {**BASE_CASE, "constraints": [], "do_not_change": [], "affected_systems": []}
    out = normalize_intelligence_case(packet)
    assert out["constraints"] == []
    assert out["do_not_change"] == []
    assert out["affected_systems"] == []


def test_collection_values_are_normalized_deduplicated_and_sorted():
    packet = {
        **BASE_CASE,
        "affected_systems": [" Rendering. ", "schedule", "SCHEDULE", "Identity"],
    }
    assert normalize_intelligence_case(packet)["affected_systems"] == [
        "identity", "rendering", "schedule"
    ]


def test_materially_equivalent_structured_case_normalizes_identically():
    equivalent = {
        "suspected_subsystems": [" SCHEDULE. ", "RENDERING"],
        "current_known_state": None,
        "environment": None,
        "affected_systems": ["rendering", "ＳＣＨＥＤＵＬＥ"],
        "required_changes": None,
        "do_not_change": [" navigation. ", "VISUAL DESIGN"],
        "constraints": ["  USE   EXISTING MULTI-SOURCE ARCHITECTURE.  "],
        "solved_when": " EXPECTED CARDS ARE VISIBLY PRESENT WITH VERIFIED DATA. ",
        "success_condition": "EXPECTED SLATE APPEARS WITH VERIFIED UNDERLYING DATA.",
        "visible_symptom": " EXPECTED GAMES / CARDS ARE ABSENT. ",
        "goal": " cfb CARDS APPEAR NORMALLY. ",
        "workstream_id": "cfb-cards-debug",
    }
    left = normalize_intelligence_case(BASE_CASE)
    right = normalize_intelligence_case(equivalent)
    semantic_fields = (
        "workstream_id", "goal", "visible_symptom", "success_condition", "solved_when",
        "constraints", "do_not_change", "required_changes", "affected_systems",
        "environment", "current_known_state", "suspected_subsystems",
    )
    assert {key: left[key] for key in semantic_fields} == {
        key: right[key] for key in semantic_fields
    }
    assert left["case_id"] == right["case_id"]


def test_case_id_has_stable_contract_shape():
    assert re.fullmatch(r"CASE-[0-9A-F]{24}", normalize_intelligence_case(BASE_CASE)["case_id"])


def test_symptom_is_not_silently_promoted_to_root_cause():
    out = normalize_intelligence_case(BASE_CASE)
    assert "visible_symptom" in out
    assert "root_cause" not in out
    assert "diagnosis" not in out


def test_invalid_workstream_id_fails_closed():
    with pytest.raises(IntelligenceCaseValidationFailure):
        normalize_intelligence_case({**BASE_CASE, "workstream_id": "bad workstream id"})


@pytest.mark.parametrize(
    "field",
    ["workstream_id", "goal", "visible_symptom", "success_condition", "solved_when"],
)
def test_missing_required_core_field_fails_closed(field):
    packet = dict(BASE_CASE)
    packet.pop(field)
    with pytest.raises(IntelligenceCaseValidationFailure):
        normalize_intelligence_case(packet)


def test_non_string_collection_item_fails_closed():
    with pytest.raises(IntelligenceCaseValidationFailure):
        normalize_intelligence_case({**BASE_CASE, "constraints": ["keep fast", 7]})


def test_unknown_extra_field_fails_closed():
    with pytest.raises(IntelligenceCaseValidationFailure):
        normalize_intelligence_case({**BASE_CASE, "mystery": "value"})


@pytest.mark.parametrize("field", ["root_cause", "diagnosis", "hypotheses", "evidence", "confidence"])
def test_later_step_reasoning_fields_are_rejected(field):
    with pytest.raises(IntelligenceCaseValidationFailure):
        normalize_intelligence_case({**BASE_CASE, field: "premature reasoning"})


def test_required_change_cannot_also_be_do_not_change():
    packet = {
        **BASE_CASE,
        "required_changes": ["Navigation"],
        "do_not_change": [" navigation. "],
    }
    with pytest.raises(IntelligenceCaseValidationFailure):
        normalize_intelligence_case(packet)


@pytest.mark.parametrize("field", ["success_condition", "solved_when"])
def test_implementation_only_terminal_success_fails_closed(field):
    with pytest.raises(IntelligenceCaseValidationFailure):
        normalize_intelligence_case({**BASE_CASE, field: "Merge PR."})


def test_serialization_is_deterministic_across_input_key_order():
    a = serialize_intelligence_case(BASE_CASE)
    b = serialize_intelligence_case(dict(reversed(list(BASE_CASE.items()))))
    assert a == b
    assert json.loads(a) == normalize_intelligence_case(BASE_CASE)


def test_serialized_json_uses_sorted_top_level_keys():
    parsed_pairs = json.loads(serialize_intelligence_case(BASE_CASE), object_pairs_hook=list)
    keys = [key for key, _value in parsed_pairs]
    assert keys == sorted(keys)


def test_renderer_has_fixed_fields_and_explicit_unknown_vs_none():
    packet = {
        **BASE_CASE,
        "constraints": None,
        "required_changes": [],
        "environment": None,
    }
    text = render_intelligence_case(packet)
    labels = [
        "Case ID:", "Workstream:", "Goal:", "Visible Symptom:", "Success Condition:",
        "Solved When:", "Constraints:", "Do Not Change:", "Required Changes:",
        "Affected Systems:", "Environment:", "Current Known State:",
        "Suspected Subsystems:", "Mutation Authority:", "GitHub Actions Fallback:",
    ]
    positions = [text.index(label) for label in labels]
    assert positions == sorted(positions)
    assert "Constraints: unknown" in text
    assert "Required Changes: none" in text
    assert "Environment: unknown" in text


def test_renderer_does_not_invent_causal_sections():
    text = render_intelligence_case(BASE_CASE).lower()
    assert "root cause:" not in text
    assert "diagnosis:" not in text
    assert "hypotheses:" not in text


def test_module_control_constants_deny_mutation_authority():
    assert NETWORK_CALLS is False
    assert AUTO_MUTATE is False
    assert MAY_MODIFY_PRODUCT_RUNTIME is False
    assert MUTATION_AUTHORITY_GRANTED is False
    assert GITHUB_ACTIONS_FALLBACK == 0
