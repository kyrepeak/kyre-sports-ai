from __future__ import annotations

REQUIRED_PROJECTS = ("kyre-sports-api", "kyre-runless-proof", "kyre-sports-finalizer")


def evaluate_convergence(snapshot: dict) -> dict:
    failures: list[str] = []
    main_sha = snapshot.get("main_sha")
    if not isinstance(main_sha, str) or len(main_sha) != 40:
        failures.append("github main SHA is missing or invalid")

    supabase = snapshot.get("supabase", {})
    if supabase.get("status") != "ACTIVE_HEALTHY":
        failures.append("Supabase project is not ACTIVE_HEALTHY")
    if supabase.get("security_errors") != 0:
        failures.append("Supabase has actionable security errors")
    if supabase.get("security_warnings") != 0:
        failures.append("Supabase has actionable security warnings")

    vercel = snapshot.get("vercel", {})
    if vercel.get("stale_preview_env_count") != 0:
        failures.append("Vercel still has stale preview environment configuration")
    projects = vercel.get("projects", {})
    for name in REQUIRED_PROJECTS:
        project = projects.get(name)
        if not isinstance(project, dict):
            failures.append(f"{name}: deployment evidence missing")
            continue
        if project.get("ready_state") != "READY":
            failures.append(f"{name}: production deployment is not READY")
        if project.get("git_sha") != main_sha:
            failures.append(f"{name}: production SHA does not equal GitHub main")
        if project.get("runtime_error_count") != 0:
            failures.append(f"{name}: runtime error count is nonzero")
        if project.get("runtime_fatal_count") != 0:
            failures.append(f"{name}: runtime fatal count is nonzero")

    return {"green": not failures, "failures": failures}


def freeze_eligible(
    convergence_report: dict,
    *,
    stale_preview_env_count: int,
    migration_payload_archive_complete: bool,
) -> bool:
    return (
        bool(convergence_report.get("green"))
        and not convergence_report.get("failures")
        and stale_preview_env_count == 0
        and migration_payload_archive_complete
    )
