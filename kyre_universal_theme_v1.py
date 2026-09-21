"""KYRE Sports AI universal theme foundation V1.

Standalone design-token layer for the approved black + glacier-blue website
direction. This module does not mount itself into production. Later steps may
consume its tokens/CSS after their own acceptance criteria are approved.
"""
from __future__ import annotations

THEME_VERSION = "KYRE UNIVERSAL THEME V1 • BLACK + GLACIER BLUE"

COLORS = {
    "bg_0": "#03060A",
    "bg_1": "#07111A",
    "bg_2": "#0B1722",
    "surface": "#0B1520",
    "surface_raised": "#0F1C28",
    "surface_soft": "#122331",
    "glacier": "#58C9FF",
    "glacier_strong": "#1FAEFF",
    "glacier_soft": "#BCEBFF",
    "glacier_dim": "#245A78",
    "border": "#19384D",
    "border_strong": "#2B95C9",
    "text_primary": "#F6FBFF",
    "text_secondary": "#B7C7D6",
    "text_muted": "#7F95A8",
    "success": "#3DE0A1",
    "warning": "#F2C66D",
    "danger": "#FF667A",
}

SPACING = {
    "1": "4px",
    "2": "8px",
    "3": "12px",
    "4": "16px",
    "5": "24px",
    "6": "32px",
    "7": "48px",
}

RADII = {
    "sm": "8px",
    "md": "12px",
    "lg": "16px",
    "xl": "20px",
    "2xl": "28px",
    "pill": "999px",
}

TYPOGRAPHY = {
    "xs": "0.72rem",
    "sm": "0.84rem",
    "md": "1rem",
    "lg": "1.22rem",
    "xl": "1.7rem",
    "display": "clamp(2rem, 4vw, 3.35rem)",
    "weight_regular": "500",
    "weight_semibold": "700",
    "weight_bold": "850",
    "weight_black": "950",
}

EFFECTS = {
    "shadow_card": "0 16px 44px rgba(0, 0, 0, 0.28)",
    "shadow_float": "0 24px 70px rgba(0, 0, 0, 0.38)",
    "glow_soft": "0 0 28px rgba(88, 201, 255, 0.14)",
    "glow_active": "0 0 34px rgba(31, 174, 255, 0.24)",
    "border_soft": "1px solid rgba(88, 201, 255, 0.18)",
    "border_active": "1px solid rgba(88, 201, 255, 0.62)",
}

def theme_contract() -> dict[str, dict[str, str] | str]:
    return {
        "version": THEME_VERSION,
        "colors": COLORS.copy(),
        "spacing": SPACING.copy(),
        "radii": RADII.copy(),
        "typography": TYPOGRAPHY.copy(),
        "effects": EFFECTS.copy(),
    }

def build_universal_theme_css() -> str:
    """Return the reusable token CSS without attaching it to Streamlit."""
    return f"""
<style data-kyre-universal-theme="v1">
:root {{
  --kyre-bg-0: {COLORS["bg_0"]};
  --kyre-bg-1: {COLORS["bg_1"]};
  --kyre-bg-2: {COLORS["bg_2"]};
  --kyre-surface: {COLORS["surface"]};
  --kyre-surface-raised: {COLORS["surface_raised"]};
  --kyre-surface-soft: {COLORS["surface_soft"]};

  --kyre-glacier: {COLORS["glacier"]};
  --kyre-glacier-strong: {COLORS["glacier_strong"]};
  --kyre-glacier-soft: {COLORS["glacier_soft"]};
  --kyre-glacier-dim: {COLORS["glacier_dim"]};

  --kyre-border: {COLORS["border"]};
  --kyre-border-strong: {COLORS["border_strong"]};
  --kyre-text-primary: {COLORS["text_primary"]};
  --kyre-text-secondary: {COLORS["text_secondary"]};
  --kyre-text-muted: {COLORS["text_muted"]};

  --kyre-success: {COLORS["success"]};
  --kyre-warning: {COLORS["warning"]};
  --kyre-danger: {COLORS["danger"]};

  --kyre-space-1: {SPACING["1"]};
  --kyre-space-2: {SPACING["2"]};
  --kyre-space-3: {SPACING["3"]};
  --kyre-space-4: {SPACING["4"]};
  --kyre-space-5: {SPACING["5"]};
  --kyre-space-6: {SPACING["6"]};
  --kyre-space-7: {SPACING["7"]};

  --kyre-radius-sm: {RADII["sm"]};
  --kyre-radius-md: {RADII["md"]};
  --kyre-radius-lg: {RADII["lg"]};
  --kyre-radius-xl: {RADII["xl"]};
  --kyre-radius-2xl: {RADII["2xl"]};
  --kyre-radius-pill: {RADII["pill"]};

  --kyre-font-xs: {TYPOGRAPHY["xs"]};
  --kyre-font-sm: {TYPOGRAPHY["sm"]};
  --kyre-font-md: {TYPOGRAPHY["md"]};
  --kyre-font-lg: {TYPOGRAPHY["lg"]};
  --kyre-font-xl: {TYPOGRAPHY["xl"]};
  --kyre-font-display: {TYPOGRAPHY["display"]};

  --kyre-shadow-card: {EFFECTS["shadow_card"]};
  --kyre-shadow-float: {EFFECTS["shadow_float"]};
  --kyre-glow-soft: {EFFECTS["glow_soft"]};
  --kyre-glow-active: {EFFECTS["glow_active"]};
}}

.kyre-theme-surface {{
  background: linear-gradient(145deg, var(--kyre-surface-raised), var(--kyre-surface));
  border: {EFFECTS["border_soft"]};
  border-radius: var(--kyre-radius-xl);
  box-shadow: var(--kyre-shadow-card), var(--kyre-glow-soft);
  color: var(--kyre-text-primary);
}}

.kyre-theme-focus {{
  outline: none;
  border: {EFFECTS["border_active"]};
  box-shadow: var(--kyre-glow-active);
}}
</style>
"""

__all__ = [
    "COLORS",
    "EFFECTS",
    "RADII",
    "SPACING",
    "THEME_VERSION",
    "TYPOGRAPHY",
    "build_universal_theme_css",
    "theme_contract",
]
