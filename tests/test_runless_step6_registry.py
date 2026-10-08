"""Temporary compatibility shim for the legacy Runless Step-6 executor service.

The service start command still names this historical test path. Completed
one-shot proof bridges must be retired back to this inert shim so a future
executor deploy cannot resubmit an old proof request.
"""


def test_legacy_runless_executor_path_is_available() -> None:
    assert True
