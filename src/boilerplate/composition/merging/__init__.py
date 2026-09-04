"""Merging strategies and helpers for combining template data.

This package provides deterministic, conflict-aware merging of copier
configuration fragments, questions, and metadata produced during
composition.

- CopierConfigMerger: High-level entry point for merging structures.
- strategies: `override`, `accumulate`, `merge_questions`,
    `intersect_versions`, `union`.

Exceptions:
- MergeConflictError: Raised when a conflict cannot be resolved
    under the selected strategy.

Example:
        >>> from boilerplate.composition.merging import union
        >>> union([["a", "b"], ["b", "c"]], "extensions")
        ['a', 'b', 'c']
"""

from boilerplate.composition.merging.exceptions import MergeConflictError
from boilerplate.composition.merging.merger import CopierConfigMerger
from boilerplate.composition.merging.strategies import (
    accumulate,
    intersect_versions,
    merge_questions,
    override,
    union,
)

__all__ = [
    "CopierConfigMerger",
    "MergeConflictError",
    "accumulate",
    "intersect_versions",
    "merge_questions",
    "override",
    "union",
]
