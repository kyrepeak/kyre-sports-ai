from __future__ import annotations

from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def _dependency_names() -> set[str]:
    payload = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    raw = payload.get("project", {}).get("dependencies", [])
    names: set[str] = set()
    for item in raw:
        name = str(item).split(";", 1)[0]
        for marker in ("==", ">=", "<=", "~=", "!=", ">", "<", "["):
            name = name.split(marker, 1)[0]
        names.add(name.strip().casefold().replace("_", "-"))
    return names


def test_vercel_fastapi_manifest_installs_official_injury_pdf_dependency() -> None:
    injury = (ROOT / "nba_spread_injury_availability_v1.py").read_text(encoding="utf-8")
    assert "from pypdf import PdfReader" in injury
    assert "pypdf" in _dependency_names(), (
        "Vercel builds Kyre Sports API from pyproject.toml; the NBA Official "
        "injury parser imports pypdf at module load, so pyproject must install it."
    )


def test_step2g_runtime_successor_changes_dependency_only() -> None:
    source = (ROOT / "sports_api" / "api" / "nba_pra_injury_v1.py").read_text(encoding="utf-8")
    assert "from nba_spread_injury_availability_v1 import _fetch_official_rows" in source
    command = (ROOT / "nba_pra_page2_command_center_v3.py").read_text(encoding="utf-8")
    assert 'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0' in command
