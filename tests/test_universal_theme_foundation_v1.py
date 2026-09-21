from kyre_universal_theme_v1 import (
    COLORS,
    EFFECTS,
    RADII,
    SPACING,
    THEME_VERSION,
    TYPOGRAPHY,
    build_universal_theme_css,
    theme_contract,
)

assert "BLACK + GLACIER BLUE" in THEME_VERSION

required_colors = {
    "bg_0", "bg_1", "bg_2", "surface", "surface_raised",
    "glacier", "glacier_strong", "glacier_soft",
    "text_primary", "text_secondary", "text_muted",
    "success", "warning", "danger", "border", "border_strong",
}
assert required_colors <= set(COLORS)
assert COLORS["bg_0"] == "#03060A"
assert COLORS["glacier"] == "#58C9FF"
assert COLORS["glacier_strong"] == "#1FAEFF"

assert list(SPACING.values()) == ["4px", "8px", "12px", "16px", "24px", "32px", "48px"]
assert RADII["pill"] == "999px"
assert {"sm", "md", "lg", "xl", "display"} <= set(TYPOGRAPHY)
assert {"shadow_card", "shadow_float", "glow_soft", "glow_active", "border_soft", "border_active"} <= set(EFFECTS)

contract = theme_contract()
assert contract["version"] == THEME_VERSION
assert contract["colors"] == COLORS

css = build_universal_theme_css()
assert 'data-kyre-universal-theme="v1"' in css
for token in (
    "--kyre-bg-0",
    "--kyre-surface",
    "--kyre-glacier",
    "--kyre-glacier-strong",
    "--kyre-text-primary",
    "--kyre-text-secondary",
    "--kyre-text-muted",
    "--kyre-success",
    "--kyre-warning",
    "--kyre-danger",
    "--kyre-space-7",
    "--kyre-radius-2xl",
    "--kyre-font-display",
    "--kyre-shadow-card",
    "--kyre-glow-active",
):
    assert token in css

assert ".kyre-theme-surface" in css
assert ".kyre-theme-focus" in css

print("UNIVERSAL_THEME_STEP1_FOUNDATION_GREEN")
