"""Fail-closed source policy for additive WNBA PRA Page 1 final polish V1."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ACTIVE=(
    "wnba_pra_page1_final_polish_v1.py",
    "wnba_pra_page_model_artifact_final_polish_v1.py",
    "runless_v2/wnba_pra_page1_final_polish_runtime_v1.py",
    "runless_v2/__init__.py",
    "wnba_pra_hub_v3612.py",
)
FORBIDDEN=("sports"+"gameodds","esp"+"n bet","import esp"+"n","render.com")

def main()->int:
    failures=[]
    for rel in ACTIVE:
        text=(ROOT/rel).read_text(encoding="utf-8").casefold()
        for token in FORBIDDEN:
            if token in text: failures.append(f"{rel}:{token}")
    ui=(ROOT/"wnba_pra_page1_final_polish_v1.py").read_text(encoding="utf-8")
    for token in ("KYRE MODEL — TOP PRA PICK","More trends in Player Analysis","Analyze Pick",'loading="lazy"','decoding="async"'):
        if token not in ui: failures.append(f"ui-contract:{token}")
    for token in ("import requests","import httpx","curl_cffi"):
        if token in ui.casefold(): failures.append(f"ui-network:{token}")
    artifact=(ROOT/"wnba_pra_page_model_artifact_final_polish_v1.py").read_text(encoding="utf-8")
    for token in ("PLAYER_ID","TEAM_ID","https://cdn.wnba.com/headshots/wnba/latest/1040x760/","https://cdn.nba.com/logos/wnba/"):
        if token not in artifact: failures.append(f"identity-contract:{token}")
    runtime=(ROOT/"runless_v2/wnba_pra_page1_final_polish_runtime_v1.py").read_text(encoding="utf-8")
    for token in ("wnba_pra_page_model_artifact_final_polish_v1","_safe_model_fields","_artifact_from_exact_sha_sandbox"):
        if token not in runtime: failures.append(f"runtime-contract:{token}")
    compat=(ROOT/"wnba_pra_hub_v3612.py").read_text(encoding="utf-8")
    if "import wnba_pra_hub_v3617 as active" not in compat: failures.append("compat:v3617-boundary")
    if "active.render_page_snapshot = _page1_final_polish.render_page_snapshot" not in compat: failures.append("compat:polish-composition")
    frozen={
        "wnba_pra_page1_stier_v1.py":"8882b1034ee7e05ae3006eaedc0ccd91ab30f51f",
        "wnba_pra_page_model_artifact_v1.py":"63f9bfe947c751a64e528d16b58d90d6179f961f",
        "runless_v2/wnba_pra_page_snapshot_v1.py":"e9159d93a8fb6f6fca754391a5fa52a8d09ef407",
    }
    import subprocess
    for rel,expected in frozen.items():
        actual=subprocess.check_output(["git","hash-object",rel],cwd=ROOT,text=True).strip()
        if actual!=expected: failures.append(f"frozen-byte-drift:{rel}:{actual}")
    if failures: raise SystemExit("WNBA_PRA_PAGE1_FINAL_POLISH_SOURCE_POLICY_FAIL:"+",".join(failures))
    print("WNBA_PRA_PAGE1_FINAL_POLISH_SOURCE_POLICY_GREEN")
    return 0
if __name__=="__main__": raise SystemExit(main())
