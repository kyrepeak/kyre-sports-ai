import pytest

from devsystem.monster_speed_v3_step2_redeploy_guard_v1 import (
    COMMENT_ONLY_FAILURE,
    RedeployGuardFailure,
    check_repository,
    dependency_lines,
    validate_requirements_change,
)


def test_repository_has_cache_safe_redeploy_contract():
    result = check_repository()
    assert result["status"] == "GREEN"
    assert result["canonical_redeploy_marker"] == "deploy/streamlit-redeploy.txt"
    assert result["marker_in_cache_keys"] is False
    assert result["requirements_cache_key_references"] >= 4


def test_dependency_parser_ignores_comments_and_blank_lines():
    text = "streamlit\n\n# redeploy marker\npandas>=2\n"
    assert dependency_lines(text) == ("streamlit", "pandas>=2")


def test_comment_only_requirements_change_is_blocked():
    base = "streamlit\npandas\n"
    head = "streamlit\npandas\n# force redeploy\n"
    with pytest.raises(RedeployGuardFailure, match=COMMENT_ONLY_FAILURE):
        validate_requirements_change(base, head)


def test_real_dependency_change_is_allowed():
    base = "streamlit\npandas\n"
    head = "streamlit\npandas>=2.2\n# dependency rationale\n"
    result = validate_requirements_change(base, head)
    assert result["requirements_changed"] is True
    assert result["dependency_change"] is True


def test_unchanged_requirements_is_cache_safe():
    text = "streamlit\npandas\n"
    result = validate_requirements_change(text, text)
    assert result == {
        "requirements_changed": False,
        "dependency_change": False,
    }
