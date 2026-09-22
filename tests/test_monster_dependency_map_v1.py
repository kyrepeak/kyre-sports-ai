from __future__ import annotations

from pathlib import Path

from sports_api.monster_dependency_map_v1 import (
    MAY_MODIFY_PROJECTION,
    PROJECTION_WEIGHT,
    build_dependency_map,
)

ROOT = Path(__file__).resolve().parents[1]


def test_map_resolves_static_relative_and_dynamic_imports(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "pkg" / "leaf.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "pkg" / "middle.py").write_text(
        "from . import leaf\n",
        encoding="utf-8",
    )
    (tmp_path / "router.py").write_text(
        "import importlib\n"
        "ACTIVE_PAGE = 'pkg.middle'\n"
        "def load():\n"
        "    return importlib.import_module(ACTIVE_PAGE)\n",
        encoding="utf-8",
    )
    (tmp_path / "app.py").write_text("import router\n", encoding="utf-8")

    graph = build_dependency_map(tmp_path)

    assert "pkg.leaf" in graph.dependencies()["pkg.middle"]
    assert "pkg.middle" in graph.dependencies()["router"]
    assert "router" in graph.dependencies()["app"]
    assert graph.transitive_dependents("pkg.leaf") == ["app", "pkg.middle", "router"]


def test_impact_report_explains_downstream_blast_radius(tmp_path):
    (tmp_path / "shared.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "feature.py").write_text("import shared\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("import feature\n", encoding="utf-8")

    graph = build_dependency_map(tmp_path)
    report = graph.impact_report("shared.py")

    assert report["status"] == "OK"
    assert report["module"] == "shared"
    assert report["direct_dependents"] == ["feature"]
    assert report["transitive_dependents"] == ["app", "feature"]
    assert report["blast_radius"] == 2
    assert report["impacted_entrypoints"] == ["app.py"]
    assert report["risk"] == "HIGH"


def test_not_found_is_explicit_and_never_guesses(tmp_path):
    (tmp_path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    graph = build_dependency_map(tmp_path)

    report = graph.impact_report("does_not_exist.py")

    assert report["status"] == "NOT_FOUND"
    assert report["query"] == "does_not_exist.py"


def test_repo_map_understands_active_streamlit_dynamic_router_chain():
    graph = build_dependency_map(ROOT)
    dependencies = graph.dependencies()

    assert "streamlit_memory_lazy_router_v77" in dependencies["app"]
    assert "cfb_over_under_clean_page_v35" in dependencies["streamlit_memory_lazy_router_v77"]

    report = graph.impact_report("cfb_over_under_clean_page_v35.py")
    assert report["status"] == "OK"
    assert "streamlit_memory_lazy_router_v77" in report["transitive_dependents"]
    assert "app" in report["transitive_dependents"]
    assert "app.py" in report["impacted_entrypoints"]


def test_shared_observability_reports_api_and_streamlit_entrypoint_impact():
    graph = build_dependency_map(ROOT)
    report = graph.impact_report("sports_api/observability_v1.py")

    assert report["status"] == "OK"
    assert "app.py" in report["impacted_entrypoints"]
    assert "sports_api/main.py" in report["impacted_entrypoints"]
    assert report["blast_radius"] >= 2


def test_dependency_map_is_measurement_only():
    assert PROJECTION_WEIGHT == 0.0
    assert MAY_MODIFY_PROJECTION is False
