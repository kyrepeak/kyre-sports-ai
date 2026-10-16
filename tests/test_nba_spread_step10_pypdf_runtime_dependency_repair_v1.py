from pathlib import Path


def _normalized_requirement_names() -> set[str]:
    root = Path(__file__).resolve().parents[1]
    names: set[str] = set()
    for raw in (root / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        name = line
        for marker in ("==", ">=", "<=", "~=", "!=", ">", "<"):
            if marker in name:
                name = name.split(marker, 1)[0]
                break
        names.add(name.strip().lower())
    return names


def test_streamlit_root_declares_pypdf_for_nba_injury_runtime() -> None:
    root = Path(__file__).resolve().parents[1]
    injury_source = (root / "nba_spread_injury_availability_v1.py").read_text(encoding="utf-8")

    assert "from pypdf import PdfReader" in injury_source
    assert "pypdf" in _normalized_requirement_names(), (
        "nba_spread_injury_availability_v1 imports pypdf at module load, so the "
        "root Streamlit requirements must install pypdf."
    )
