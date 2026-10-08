from __future__ import annotations

import os


def test_step4_closeout_executor_has_github_app_authority() -> None:
    required = ("GITHUB_APP_ID", "GITHUB_APP_INSTALLATION_ID", "GITHUB_APP_PRIVATE_KEY")
    present = {key: bool(os.environ.get(key)) for key in required}
    print("STEP4_CLOSEOUT_AUTH_KEYS_PRESENT=" + ",".join(key for key, ok in present.items() if ok), flush=True)
    assert all(present.values()), "STEP4_CLOSEOUT_GITHUB_APP_AUTH_NOT_AVAILABLE"
