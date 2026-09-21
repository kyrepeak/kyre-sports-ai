"""KYRE universal semantic design tokens V2.

Additive semantic layer over the frozen V1 primitive token foundation. This
module centralizes reusable surface, border, control, typography, spacing, and
shadow decisions so page presentation layers consume named tokens instead of
repeating visual constants.
"""
from __future__ import annotations

from kyre_universal_theme_v1 import THEME_VERSION

SEMANTIC_TOKEN_VERSION = "KYRE UNIVERSAL SEMANTIC TOKENS V2"
FOUNDATION_VERSION = THEME_VERSION

SEMANTIC_TOKENS = {
    "surface_control": "#071722",
    "surface_panel": "#081926",
    "surface_panel_alt": "#0A1D2A",
    "surface_column": "rgba(3, 10, 16, 0.58)",
    "border_soft": "rgba(88, 201, 255, 0.16)",
    "border_medium": "rgba(88, 201, 255, 0.22)",
    "border_strong": "rgba(88, 201, 255, 0.32)",
    "accent_wash": "rgba(88, 201, 255, 0.12)",
    "accent_wash_soft": "rgba(88, 201, 255, 0.08)",
    "text_primary": "var(--kyre-text-primary)",
    "text_secondary": "var(--kyre-text-secondary)",
    "text_muted": "var(--kyre-text-muted)",
    "text_accent": "var(--kyre-glacier)",
    "text_accent_soft": "var(--kyre-glacier-soft)",
    "radius_control": "var(--kyre-radius-md)",
    "radius_card": "var(--kyre-radius-xl)",
    "radius_section": "var(--kyre-radius-lg)",
    "shadow_card": "var(--kyre-shadow-card)",
    "shadow_glow": "var(--kyre-glow-soft)",
    "space_compact": "var(--kyre-space-2)",
    "space_control": "var(--kyre-space-3)",
    "space_section": "var(--kyre-space-4)",
}

def semantic_token_contract() -> dict[str, str]:
    return SEMANTIC_TOKENS.copy()

def build_semantic_tokens_css() -> str:
    t = SEMANTIC_TOKENS
    return f"""
<style data-kyre-semantic-tokens="v2">
:root {{
  --kyre-sem-surface-control: {t["surface_control"]};
  --kyre-sem-surface-panel: {t["surface_panel"]};
  --kyre-sem-surface-panel-alt: {t["surface_panel_alt"]};
  --kyre-sem-surface-column: {t["surface_column"]};
  --kyre-sem-border-soft: {t["border_soft"]};
  --kyre-sem-border-medium: {t["border_medium"]};
  --kyre-sem-border-strong: {t["border_strong"]};
  --kyre-sem-accent-wash: {t["accent_wash"]};
  --kyre-sem-accent-wash-soft: {t["accent_wash_soft"]};
  --kyre-sem-text-primary: {t["text_primary"]};
  --kyre-sem-text-secondary: {t["text_secondary"]};
  --kyre-sem-text-muted: {t["text_muted"]};
  --kyre-sem-text-accent: {t["text_accent"]};
  --kyre-sem-text-accent-soft: {t["text_accent_soft"]};
  --kyre-sem-radius-control: {t["radius_control"]};
  --kyre-sem-radius-card: {t["radius_card"]};
  --kyre-sem-radius-section: {t["radius_section"]};
  --kyre-sem-shadow-card: {t["shadow_card"]};
  --kyre-sem-shadow-glow: {t["shadow_glow"]};
  --kyre-sem-space-compact: {t["space_compact"]};
  --kyre-sem-space-control: {t["space_control"]};
  --kyre-sem-space-section: {t["space_section"]};
}}
</style>
"""

__all__ = [
    "FOUNDATION_VERSION",
    "SEMANTIC_TOKENS",
    "SEMANTIC_TOKEN_VERSION",
    "build_semantic_tokens_css",
    "semantic_token_contract",
]
