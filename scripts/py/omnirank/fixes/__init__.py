"""Fix generators for the MECHANICAL tier.

This release PREVIEWS fixes: every generator returns a unified diff and nothing
in this package opens a file for writing. Actual modification arrives in
v0.4.0, and the split is deliberate -- the locator is the riskiest component in
the product, so it ships and gets proven before anything gains write access.
"""
from __future__ import annotations

from .base import FixOutcome, outcome, unified_diff

__all__ = ["FixOutcome", "outcome", "unified_diff"]
