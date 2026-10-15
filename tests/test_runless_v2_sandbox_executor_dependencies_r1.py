from runless_v2.sandbox_executor import _MIN_BOOTSTRAP_PACKAGES


def test_runless_v2_bootstrap_includes_runtime_dependencies_needed_by_proof_plans():
    required = {"pandas", "numpy", "streamlit"}
    assert required.issubset(set(_MIN_BOOTSTRAP_PACKAGES))
