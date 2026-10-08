"""Temporary compatibility shim for the legacy Runless Step-6 executor service.

The service start command still names this historical test path. This shim
grants no proof, product, merge, freeze, or mutation authority.
"""


def test_legacy_runless_executor_path_is_available() -> None:
    assert True
