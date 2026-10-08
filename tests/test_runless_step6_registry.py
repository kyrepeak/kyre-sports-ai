"""Compatibility shim for the legacy Runless Step-6 executor service.

The executor service still names this historical test path. Product proof and
closeout authority are not embedded here; task-specific one-shot bridges must
be installed explicitly under Step 2A and removed after use.
"""


def test_legacy_runless_executor_path_is_available() -> None:
    assert True
