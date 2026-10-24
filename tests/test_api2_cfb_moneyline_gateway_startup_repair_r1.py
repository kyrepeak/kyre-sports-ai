from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_fastapi_runtime_does_not_declare_streamlit_dependency() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = project["project"]["dependencies"]
    assert not any(str(dep).split("[", 1)[0].lower().startswith("streamlit") for dep in dependencies)


def test_api_entrypoint_and_health_work_without_external_streamlit() -> None:
    script = r'''
import builtins
import sys

real_import = builtins.__import__

def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    if (name == "streamlit" or name.startswith("streamlit.")) and "streamlit" not in sys.modules:
        raise ModuleNotFoundError("external Streamlit intentionally unavailable in API runtime test")
    return real_import(name, globals, locals, fromlist, level)

builtins.__import__ = guarded_import
import kyre_sports_api_vercel_v1 as api
assert getattr(sys.modules.get("streamlit"), "__kyre_api_compat__", False) is True
from fastapi.testclient import TestClient
response = TestClient(api.app).get("/health")
assert response.status_code == 200, response.text
payload = response.json()
assert payload["service"] == "Kyre Sports API"
assert payload["direct_app_provider_fallback"] is False
'''
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_fastapi_dependencies_are_unique_and_frontend_keeps_streamlit() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = [str(dep).lower() for dep in project["project"]["dependencies"]]
    assert len(dependencies) == len(set(dependencies))
    frontend_requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "streamlit" in frontend_requirements
