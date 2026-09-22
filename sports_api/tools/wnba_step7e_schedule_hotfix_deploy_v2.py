#!/usr/bin/env python3
"""Step 7E hotfix deploy v2: normalize the stored Supabase project origin.

Render may preserve the configured Supabase URL with a trailing slash. The
underlying Step 6R backend already normalizes this safely. This wrapper keeps the
same strict project identity check while accepting only the canonical HTTPS
origin with an optional root slash.
"""
from __future__ import annotations

import json
from typing import Any, Mapping
from urllib.parse import urlsplit

import sports_api.tools.wnba_step7e_schedule_hotfix_deploy as base

MODEL_VERSION = "wnba_step_7e_schedule_hotfix_deploy_v2"


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def validate_render_environment(values: Mapping[str, str]) -> None:
    if values.get("WNBA_KYRE_DURABLE_STORAGE_BACKEND") != "supabase":
        raise base.Step7EHotfixDeployError("Render is no longer configured for the Supabase durable backend.")

    raw_url = _clean(values.get("WNBA_KYRE_SUPABASE_URL"))
    parsed = urlsplit(raw_url or "")
    if (
        parsed.scheme.casefold() != "https"
        or parsed.hostname != base.EXPECTED_SUPABASE_HOST
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise base.Step7EHotfixDeployError("Render Supabase project origin drifted.")

    secret = _clean(values.get("WNBA_KYRE_SUPABASE_SECRET_KEY"))
    if not secret or len(secret) < 20:
        raise base.Step7EHotfixDeployError("Render Supabase server secret is missing.")
    for name in base.OFF_SWITCHES:
        if base._truthy(values.get(name)):
            raise base.Step7EHotfixDeployError(f"Step 7E refuses deployment while {name} is enabled.")


def deploy_schedule_hotfix(*, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    original = base._validate_render_environment
    base._validate_render_environment = validate_render_environment
    try:
        evidence = base.deploy_schedule_hotfix(env=env)
    finally:
        base._validate_render_environment = original
    evidence["model_version"] = MODEL_VERSION
    evidence["compatibility"] = {
        "supabase_origin_normalized": True,
        "supabase_project_host_exact": base.EXPECTED_SUPABASE_HOST,
        "trailing_root_slash_allowed": True,
    }
    return evidence


def main() -> int:
    print(json.dumps(deploy_schedule_hotfix(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
