from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "devsystem" / "kyre_deploy_v1_contract.py"
STREAMLIT_DOCKERFILE = ROOT / "deploy" / "kyre-deploy" / "streamlit.Dockerfile"
STREAMLIT_HEALTHCHECK = ROOT / "deploy" / "kyre-deploy" / "streamlit-healthcheck.py"
COMPOSE_PATH = ROOT / "deploy" / "kyre-deploy" / "compose.yaml"
README_PATH = ROOT / "deploy" / "kyre-deploy" / "README.md"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "kyre-deploy-v1-zero-cost-ci.yml"
API_DOCKERFILE = ROOT / "sports_api" / "Dockerfile"


def _text(path: Path) -> str:
    assert path.exists(), f"required KYRE DEPLOY file missing: {path.relative_to(ROOT)}"
    return path.read_text(encoding="utf-8")


def _load_contract_module():
    assert CONTRACT_PATH.exists(), "provider-neutral deployment contract module is missing"
    spec = importlib.util.spec_from_file_location("kyre_deploy_v1_contract", CONTRACT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_contract_validator_reports_provider_neutral_topology() -> None:
    module = _load_contract_module()
    result = module.validate_kyre_deploy_v1(ROOT)
    assert result["status"] == "GREEN"
    assert result["frontend"] == "streamlit"
    assert result["api"] == "sports_api"
    assert result["live_cutover"] is False
    assert result["vercel_runtime_required"] is False


def test_streamlit_container_is_non_root_and_health_checked() -> None:
    dockerfile = _text(STREAMLIT_DOCKERFILE)
    healthcheck = _text(STREAMLIT_HEALTHCHECK)
    assert "FROM python:3.13-slim" in dockerfile
    assert "USER kyre" in dockerfile
    assert "EXPOSE 8501" in dockerfile
    assert "streamlit run app.py" in dockerfile
    assert "--server.address=0.0.0.0" in dockerfile
    assert "streamlit-healthcheck.py" in dockerfile
    assert "/_stcore/health" in healthcheck


def test_compose_wires_streamlit_to_existing_api_without_secrets() -> None:
    compose = _text(COMPOSE_PATH)
    readme = _text(README_PATH)
    assert "kyre-streamlit:" in compose
    assert "kyre-sports-api:" in compose
    assert "dockerfile: deploy/kyre-deploy/streamlit.Dockerfile" in compose
    assert "dockerfile: sports_api/Dockerfile" in compose
    assert "KYRE_SPORTS_API_BASE_URL: ${KYRE_SPORTS_API_BASE_URL:-http://kyre-sports-api:8000}" in compose
    assert "8501:8501" in compose
    assert "8000:8000" in compose
    forbidden = ("api_key:", "password:", "token:", "secret:")
    lowered = compose.lower()
    assert not any(item in lowered for item in forbidden)
    assert "No credentials are committed" in readme


def test_existing_api_container_contract_is_preserved() -> None:
    api_dockerfile = _text(API_DOCKERFILE)
    assert "uvicorn sports_api.main:app" in api_dockerfile
    assert "EXPOSE 8000" in api_dockerfile
    assert "'/health'" in api_dockerfile


def test_zero_cost_ci_uses_hosted_runner_builds_both_images_and_never_pushes() -> None:
    workflow = _text(WORKFLOW_PATH)
    assert "ubuntu-latest" in workflow
    assert "python -m pytest -q tests/test_kyre_deploy_v1_contract.py" in workflow
    assert "docker build -f deploy/kyre-deploy/streamlit.Dockerfile" in workflow
    assert "docker build -f sports_api/Dockerfile" in workflow
    assert "cancel-in-progress: true" in workflow
    assert "docker push" not in workflow
    assert "build-push-action" not in workflow
    assert "packages: write" not in workflow


def test_zero_cost_ci_does_not_rebuild_images_for_every_sports_api_edit() -> None:
    workflow = _text(WORKFLOW_PATH)
    assert '- "sports_api/**"' not in workflow
    assert '- "sports_api/Dockerfile"' in workflow
    assert '- "sports_api/requirements.txt"' in workflow
    assert '- "sports_api/requirements-mlb-step14b-persistence.txt"' in workflow
    assert "workflow_dispatch:" in workflow
