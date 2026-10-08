"""Temporary compatibility shim for the legacy Runless Step-6 executor service.

The service start command still names this historical test path. The real CFB
Step-4 Runless request is supplied by PYTEST_ADDOPTS and a separate temporary
bridge test. This shim grants no proof or product authority.
"""


def test_legacy_runless_executor_path_is_available() -> None:
    assert True
