from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_vercel_subdirectory_root_can_import_app() -> None:
    """Reproduce Vercel loading vercel_finalizer/app.py as top-level app."""
    project_root = Path(__file__).resolve().parent
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [sys.executable, "-c", "import app; print(app.app.title)"],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "Kyre Sports Finalizer"
