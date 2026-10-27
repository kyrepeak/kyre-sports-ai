from __future__ import annotations

from pathlib import Path
from typing import Final


STREAMLIT_DOCKERFILE: Final = Path("deploy/kyre-deploy/streamlit.Dockerfile")
STREAMLIT_HEALTHCHECK: Final = Path("deploy/kyre-deploy/streamlit-healthcheck.py")
COMPOSE_FILE: Final = Path("deploy/kyre-deploy/compose.yaml")
README_FILE: Final = Path("deploy/kyre-deploy/README.md")
API_DOCKERFILE: Final = Path("sports_api/Dockerfile")
WORKFLOW_FILE: Final = Path(".github/workflows/kyre-deploy-v1-zero-cost-ci.yml")


class KyreDeployContractError(RuntimeError):
    """Raised when the provider-neutral deployment contract is incomplete."""


def _read(root: Path, relative: Path) -> str:
    path = root / relative
    if not path.is_file():
        raise KyreDeployContractError(f"missing required deployment file: {relative}")
    return path.read_text(encoding="utf-8")


def _require(text: str, marker: str, *, source: Path) -> None:
    if marker not in text:
        raise KyreDeployContractError(f"{source} missing required marker: {marker}")


def _forbid(text: str, marker: str, *, source: Path) -> None:
    if marker in text:
        raise KyreDeployContractError(f"{source} contains forbidden runtime dependency: {marker}")


def validate_kyre_deploy_v1(repo_root: Path) -> dict[str, object]:
    """Validate the Phase-1 deployment topology without network access.

    This is intentionally static: it proves packaging and CI ownership only.
    Live host, DNS, alias, and Step 2F/2G convergence remain Phase-2 evidence.
    """

    root = Path(repo_root).resolve()
    streamlit = _read(root, STREAMLIT_DOCKERFILE)
    healthcheck = _read(root, STREAMLIT_HEALTHCHECK)
    compose = _read(root, COMPOSE_FILE)
    readme = _read(root, README_FILE)
    api = _read(root, API_DOCKERFILE)
    workflow = _read(root, WORKFLOW_FILE)

    required = {
        STREAMLIT_DOCKERFILE: (
            "FROM python:3.13-slim",
            "USER kyre",
            "EXPOSE 8501",
            "streamlit run app.py",
            "--server.address=0.0.0.0",
            "streamlit-healthcheck.py",
        ),
        STREAMLIT_HEALTHCHECK: ("/_stcore/health",),
        COMPOSE_FILE: (
            "kyre-streamlit:",
            "kyre-sports-api:",
            "dockerfile: deploy/kyre-deploy/streamlit.Dockerfile",
            "dockerfile: sports_api/Dockerfile",
            "KYRE_SPORTS_API_BASE_URL: ${KYRE_SPORTS_API_BASE_URL:-http://kyre-sports-api:8000}",
        ),
        API_DOCKERFILE: (
            "uvicorn sports_api.main:app",
            "EXPOSE 8000",
            "'/health'",
        ),
        WORKFLOW_FILE: (
            "ubuntu-latest",
            "python -m pytest -q tests/test_kyre_deploy_v1_contract.py",
            "docker build -f deploy/kyre-deploy/streamlit.Dockerfile",
            "docker build -f sports_api/Dockerfile",
            "cancel-in-progress: true",
        ),
        README_FILE: ("No credentials are committed",),
    }
    texts = {
        STREAMLIT_DOCKERFILE: streamlit,
        STREAMLIT_HEALTHCHECK: healthcheck,
        COMPOSE_FILE: compose,
        README_FILE: readme,
        API_DOCKERFILE: api,
        WORKFLOW_FILE: workflow,
    }
    for source, markers in required.items():
        for marker in markers:
            _require(texts[source], marker, source=source)

    for source in (STREAMLIT_DOCKERFILE, STREAMLIT_HEALTHCHECK, COMPOSE_FILE):
        for marker in ("VERCEL_ENV", "VERCEL_URL", "VERCEL_PROJECT_ID"):
            _forbid(texts[source], marker, source=source)

    lowered_compose = compose.lower()
    for marker in ("api_key:", "password:", "token:", "secret:"):
        _forbid(lowered_compose, marker, source=COMPOSE_FILE)

    for marker in ("docker push", "build-push-action", "packages: write"):
        _forbid(workflow, marker, source=WORKFLOW_FILE)

    return {
        "status": "GREEN",
        "frontend": "streamlit",
        "api": "sports_api",
        "build_runner": "github-hosted",
        "live_cutover": False,
        "vercel_runtime_required": False,
    }
