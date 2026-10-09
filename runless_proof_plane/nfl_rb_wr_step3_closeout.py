from __future__ import annotations

from . import cfb_game_total_page1_visual_cleanup_step5_cert as cert_core

MERGED_MAIN_SHA = "337e9f2429aee703e821b226cc46ea3b52567986"
LEASE_ID = "SCOPE-LEASE-1363371DFE615B06589A63D4"


def install_startup(app):
    """Run only the terminal CFB Game Total Step-5 live certificate."""
    cert_core.MERGED_MAIN_SHA = MERGED_MAIN_SHA
    cert_core.LEASE_ID = LEASE_ID
    driver = cert_core.DRIVER.replace(
        'EXPECTED_DEPLOYMENT_SHA = "443bd71d4ee956a0b26539a900771b30b90a77fe"',
        f'EXPECTED_DEPLOYMENT_SHA = "{MERGED_MAIN_SHA}"',
    )
    if "cert.EXPECTED_MAIN_SHA = EXPECTED_DEPLOYMENT_SHA" not in driver:
        driver = driver.replace(
            "cert._prime_route = canonical_prime",
            "cert.EXPECTED_MAIN_SHA = EXPECTED_DEPLOYMENT_SHA\ncert._prime_route = canonical_prime",
            1,
        )
    cert_core.DRIVER = driver
    cert_core.install_startup(app)
    return app
