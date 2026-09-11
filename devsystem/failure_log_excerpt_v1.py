"""Create compact, sanitized failure evidence from GitHub Actions job logs."""
from __future__ import annotations

import re

MAX_EXCERPT_CHARS = 12000
MAX_EXCERPT_LINES = 120
_CONTEXT_LINES = 2
_SIGNAL = re.compile(
    r"(?i)(error|failed|failure|traceback|exception|timeout|timed out|assert|"
    r"modulenotfound|importerror|syntaxerror|indentationerror|taberror|"
    r"playwright|locator|combobox|cache miss|cache restore|pip .*failed|"
    r"no matching distribution|could not find a version|429|502|503|rate limit)"
)
_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s]+"),
    re.compile(r"(?i)\b(token|password|passwd|secret|api[_-]?key)\b(\s*[:=]\s*)[^\s]+"),
)


def sanitize_log_text(text: str) -> str:
    cleaned = _ANSI.sub("", text or "")
    cleaned = cleaned.replace("\x00", "")
    for pattern in _SECRET_PATTERNS:
        if pattern.pattern.startswith("(?i)(authorization"):
            cleaned = pattern.sub(r"\1[REDACTED]", cleaned)
        else:
            cleaned = pattern.sub(r"\1\2[REDACTED]", cleaned)
    return cleaned


def extract_log_excerpt(text: str, *, max_chars: int = MAX_EXCERPT_CHARS) -> str:
    """Return deterministic signal-rich context, bounded for packet safety."""
    cleaned = sanitize_log_text(text)
    lines = cleaned.splitlines()
    if not lines:
        return ""

    signal_indexes = [index for index, line in enumerate(lines) if _SIGNAL.search(line)]
    if signal_indexes:
        selected: set[int] = set()
        for index in signal_indexes:
            start = max(0, index - _CONTEXT_LINES)
            end = min(len(lines), index + _CONTEXT_LINES + 1)
            selected.update(range(start, end))
        ordered = [lines[index] for index in sorted(selected)]
    else:
        ordered = lines[-MAX_EXCERPT_LINES:]

    ordered = ordered[-MAX_EXCERPT_LINES:]
    excerpt = "\n".join(ordered).strip()
    if len(excerpt) > max_chars:
        excerpt = excerpt[-max_chars:]
    return excerpt
