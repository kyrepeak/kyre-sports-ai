from types import SimpleNamespace

import pytest

import universal_runtime_v5_loader_v17 as loader


MISSING = "Kyre Sports API gateway is not configured."


def _raise_missing():
    raise RuntimeError(MISSING)


def test_loader_binds_verified_kyre_sports_api_default_only_when_v7_configuration_is_missing():
    page = SimpleNamespace(_api_base=_raise_missing)

    original = loader._install_cfb_moneyline_gateway_binding(page)

    assert page._api_base() == "https://kyre-sports-api.vercel.app"
    assert original is _raise_missing


def test_loader_preserves_existing_v7_env_or_streamlit_secret_resolution():
    configured = lambda: "https://configured.example/api"
    page = SimpleNamespace(_api_base=configured)

    original = loader._install_cfb_moneyline_gateway_binding(page)

    assert page._api_base() == "https://configured.example/api"
    assert original is configured


def test_loader_does_not_swallow_unrelated_v7_runtime_errors():
    def broken():
        raise RuntimeError("unexpected gateway parser failure")

    page = SimpleNamespace(_api_base=broken)
    loader._install_cfb_moneyline_gateway_binding(page)

    with pytest.raises(RuntimeError, match="unexpected gateway parser failure"):
        page._api_base()
