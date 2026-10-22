"""Static certification for CFB Moneyline Streamlit -> Kyre Sports API binding."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    failures: list[str] = []
    source = (ROOT / "universal_runtime_v5_loader_v17.py").read_text()
    test = (ROOT / "tests/test_monster_cfb_moneyline_streamlit_gateway_binding_v1.py").read_text()

    required_source = [
        'DEFAULT_CFB_MONEYLINE_GATEWAY = "https://kyre-sports-api.vercel.app"',
        '_MISSING_GATEWAY_ERROR = "Kyre Sports API gateway is not configured."',
        'def _install_cfb_moneyline_gateway_binding(page):',
        'return original_api_base()',
        'if str(exc) != _MISSING_GATEWAY_ERROR:',
        'return DEFAULT_CFB_MONEYLINE_GATEWAY',
        'page = importlib.import_module("cfb_moneyline_clean_page_v7")',
        'original_api_base = _install_cfb_moneyline_gateway_binding(page)',
        'page._api_base = original_api_base',
    ]
    for token in required_source:
        if token not in source:
            failures.append("missing_source_contract:" + token)

    if "kyre-sports-api.onrender.com" in source:
        failures.append("render_gateway_forbidden")
    if "sports_api.collectors" in source or "build_page1_payload" in source:
        failures.append("direct_provider_or_builder_fallback_forbidden")

    required_test = [
        "test_loader_binds_verified_kyre_sports_api_default_only_when_v7_configuration_is_missing",
        "test_loader_preserves_existing_v7_env_or_streamlit_secret_resolution",
        "test_loader_does_not_swallow_unrelated_v7_runtime_errors",
        'https://kyre-sports-api.vercel.app',
    ]
    for token in required_test:
        if token not in test:
            failures.append("missing_regression_contract:" + token)

    if failures:
        print("CFB_MONEYLINE_STREAMLIT_GATEWAY_BINDING_SOURCE_POLICY_V1_RED")
        for failure in failures:
            print("-", failure)
        return 1
    print("CFB_MONEYLINE_STREAMLIT_GATEWAY_BINDING_SOURCE_POLICY_V1_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
