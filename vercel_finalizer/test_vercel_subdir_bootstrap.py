from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def test_vercel_subdirectory_root_can_import_app(tmp_path: Path) -> None:
    """Reproduce Vercel packaging only vercel_finalizer/ as /var/task."""
    source_root = Path(__file__).resolve().parent
    project_root = tmp_path / "vercel_finalizer"
    shutil.copytree(source_root, project_root, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))

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
