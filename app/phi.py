"""Application-layer PHI minimization helpers (demo-level patterns)."""

from __future__ import annotations

import re

# Demo patterns only — not a compliance substitute.
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN_REDACTED]"),
    (re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"), "[PHONE_REDACTED]"),
    (re.compile(r"\bMRN[:\s-]?\w+\b", re.IGNORECASE), "[MRN_REDACTED]"),
    (re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE), "[EMAIL_REDACTED]"),
]


def mask_phi(text: str) -> tuple[str, int]:
    """Return masked text and count of replacements applied."""
    masked = text
    hits = 0
    for pattern, replacement in _PATTERNS:
        masked, n = pattern.subn(replacement, masked)
        hits += n
    return masked, hits
