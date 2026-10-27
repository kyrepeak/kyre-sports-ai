"""Runless V2 durable proof authority."""

VERSION = "RUNLESS_V2"
__version__ = "2.0.0"

# Server-side compatibility composition: keep the existing Kyre Sports API
# player-context route stable while enriching its response with verified NBA
# Stats usage metadata. Application clients still have one Kyre gateway.
from . import nba_pra_player_context_enrichment_v2 as _nba_pra_player_context_enrichment_v2  # noqa: E402,F401

# Live-acceptance normalization repair: preserve verified opponent metadata in
# history rows without changing the public Kyre Sports API route or fabricating
# missing source fields.
from . import nba_pra_live_acceptance_repair_v1 as _nba_pra_live_acceptance_repair_v1  # noqa: E402,F401

# Page-2 role completeness successor: NBA Stats stays primary; only players still
# missing verified usage are enriched from Basketball-Reference Advanced through
# the same Kyre Sports API player-context route.
from . import nba_pra_usage_fallback_v2 as _nba_pra_usage_fallback_v2  # noqa: E402,F401

# WNBA PRA Page 1 final-polish successor: preserve the frozen one-read route
# while enriching display identity only from already-verified WNBA projection IDs.
from . import wnba_pra_page1_final_polish_runtime_v1 as _wnba_pra_page1_final_polish_runtime_v1  # noqa: E402,F401

# Existing shared-service compatibility adapter. MONSTER proof publishers below
# do not consume that adapter's control state, receipts, leases, or evidence.
from . import api2_authority_isolation_v1 as _api2_authority_isolation_v1  # noqa: E402,F401


def _monster_step2g_maybe_auto_prove() -> None:
    """Publish PR #1853 proof only from its exact Vercel preview head."""
    import asyncio
    import os
    if os.environ.get("VERCEL_ENV", "").strip() != "preview": return
    branch = os.environ.get("VERCEL_GIT_COMMIT_REF", "").strip()
    preview_sha = os.environ.get("VERCEL_GIT_COMMIT_SHA", "").strip().lower()
    authorized_branch = "monster-step2g-production-identity-promotion-v1"
    if branch != authorized_branch or len(preview_sha) != 40: return
    try:
        from .config import Settings
        from .github_authority import GithubAuthority
        from .monster_step2g_proof_v1 import BRANCH, prove_production_promotion
        from .sandbox_executor import SandboxExecutor
        if BRANCH != authorized_branch: raise RuntimeError("MONSTER_STEP2G_PREVIEW_BRANCH_CONTRACT_DRIFT")
        settings = Settings.from_env()
        if not settings.authority_enabled: raise RuntimeError("MONSTER_STEP2G_PREVIEW_AUTHORITY_DISABLED")
        result = asyncio.run(prove_production_promotion(github=GithubAuthority(settings), sandbox=SandboxExecutor(), expected_preview_sha=preview_sha))
        print("MONSTER_STEP2G_AUTO_PROOF_GREEN:" + str(result.get("receipt_digest") or ""))
    except Exception as exc:
        detail = str(exc); safe_detail = detail if detail.startswith("MONSTER_") else type(exc).__name__
        print("MONSTER_STEP2G_AUTO_PROOF_BLOCKED:" + type(exc).__name__ + ":" + safe_detail[:200])


def _monster_step2g_prerender_maybe_auto_prove() -> None:
    """Publish PR #1857 proof only from its exact Vercel preview head."""
    import asyncio
    import os
    if os.environ.get("VERCEL_ENV", "").strip() != "preview": return
    branch = os.environ.get("VERCEL_GIT_COMMIT_REF", "").strip()
    preview_sha = os.environ.get("VERCEL_GIT_COMMIT_SHA", "").strip().lower()
    authorized_branch = "monster-step2g-prerender-runtime-identity-r1"
    if branch != authorized_branch or len(preview_sha) != 40: return
    try:
        from .config import Settings
        from .github_authority import GithubAuthority
        from .monster_step2g_prerender_proof_r1 import BRANCH, prove_prerender_runtime_identity
        from .sandbox_executor import SandboxExecutor
        if BRANCH != authorized_branch: raise RuntimeError("MONSTER_STEP2G_PRERENDER_PREVIEW_BRANCH_CONTRACT_DRIFT")
        settings = Settings.from_env()
        if not settings.authority_enabled: raise RuntimeError("MONSTER_STEP2G_PRERENDER_PREVIEW_AUTHORITY_DISABLED")
        result = asyncio.run(prove_prerender_runtime_identity(github=GithubAuthority(settings), sandbox=SandboxExecutor(), expected_preview_sha=preview_sha))
        print("MONSTER_STEP2G_PRERENDER_AUTO_PROOF_GREEN:" + str(result.get("receipt_digest") or ""))
    except Exception as exc:
        detail = str(exc); safe_detail = detail if detail.startswith("MONSTER_") else type(exc).__name__
        print("MONSTER_STEP2G_PRERENDER_AUTO_PROOF_BLOCKED:" + type(exc).__name__ + ":" + safe_detail[:200])


def _monster_wnba_pra_upcoming_only_maybe_auto_prove() -> None:
    """Publish PR #1889 proof only from its exact Vercel preview head."""
    import asyncio
    import os
    if os.environ.get("VERCEL_ENV", "").strip() != "preview": return
    branch = os.environ.get("VERCEL_GIT_COMMIT_REF", "").strip()
    preview_sha = os.environ.get("VERCEL_GIT_COMMIT_SHA", "").strip().lower()
    authorized_branch = "monster-wnba-pra-upcoming-only-r1"
    if branch != authorized_branch or len(preview_sha) != 40: return
    try:
        from .config import Settings
        from .github_authority import GithubAuthority
        from .monster_wnba_pra_upcoming_only_proof_r1 import BRANCH, prove_upcoming_only
        from .sandbox_executor import SandboxExecutor
        if BRANCH != authorized_branch: raise RuntimeError("MONSTER_WNBA_UPCOMING_PREVIEW_BRANCH_CONTRACT_DRIFT")
        settings = Settings.from_env()
        if not settings.authority_enabled: raise RuntimeError("MONSTER_WNBA_UPCOMING_PREVIEW_AUTHORITY_DISABLED")
        result = asyncio.run(prove_upcoming_only(github=GithubAuthority(settings), sandbox=SandboxExecutor(), expected_preview_sha=preview_sha))
        print("MONSTER_WNBA_UPCOMING_AUTO_PROOF_GREEN:" + str(result.get("receipt_digest") or ""))
    except Exception as exc:
        detail = str(exc); safe_detail = detail if detail.startswith("MONSTER_") else type(exc).__name__
        print("MONSTER_WNBA_UPCOMING_AUTO_PROOF_BLOCKED:" + type(exc).__name__ + ":" + safe_detail[:200])


def _monster_wnba_pra_upcoming_r2_maybe_auto_prove() -> None:
    """Publish PR #1890 proof only from its exact Vercel preview head."""
    import asyncio
    import os
    if os.environ.get("VERCEL_ENV", "").strip() != "preview": return
    branch = os.environ.get("VERCEL_GIT_COMMIT_REF", "").strip()
    preview_sha = os.environ.get("VERCEL_GIT_COMMIT_SHA", "").strip().lower()
    authorized_branch = "monster-wnba-pra-upcoming-only-r2-final-card"
    if branch != authorized_branch or len(preview_sha) != 40: return
    try:
        from .config import Settings
        from .github_authority import GithubAuthority
        from .monster_wnba_pra_upcoming_only_r2_final_card_proof import BRANCH, prove
        from .sandbox_executor import SandboxExecutor
        if BRANCH != authorized_branch: raise RuntimeError("MONSTER_WNBA_R2_PREVIEW_BRANCH_CONTRACT_DRIFT")
        settings = Settings.from_env()
        if not settings.authority_enabled: raise RuntimeError("MONSTER_WNBA_R2_PREVIEW_AUTHORITY_DISABLED")
        result = asyncio.run(prove(github=GithubAuthority(settings), sandbox=SandboxExecutor(), expected_preview_sha=preview_sha))
        print("MONSTER_WNBA_R2_AUTO_PROOF_GREEN:" + str(result.get("receipt_digest") or ""))
    except Exception as exc:
        detail = str(exc); safe_detail = detail if detail.startswith("MONSTER_") else type(exc).__name__
        print("MONSTER_WNBA_R2_AUTO_PROOF_BLOCKED:" + type(exc).__name__ + ":" + safe_detail[:200])


_monster_step2g_maybe_auto_prove()
_monster_step2g_prerender_maybe_auto_prove()
_monster_wnba_pra_upcoming_only_maybe_auto_prove()
_monster_wnba_pra_upcoming_r2_maybe_auto_prove()
