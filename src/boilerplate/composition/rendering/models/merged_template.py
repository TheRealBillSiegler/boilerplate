"""Merged Copier Template that exposes a consolidated question schema.

This helper allows the renderer to inject a merged questionnaire and augment
the template configuration (for example, to add ``tasks``) without altering
files on disk.
"""

from functools import cached_property
from typing import Any

from boilerplate.integrations.copier_types import Template


class MergedTemplate(Template):
    """Template subclass that overrides questions and augments config."""

    def __init__(
        self,
        url: str,
        merged_questions: dict[str, Any],
        extra_config: dict[str, Any] | None = None,
        ref: str | None = None,
    ) -> None:
        """Initialize a merged template wrapper.

        Args:
            url: Copier template URL/path to initialize.
            merged_questions: Consolidated questionnaire schema to expose.
            extra_config: Optional configuration overrides (e.g., ``{"tasks": ...}``).
            ref: Git reference to resolve the template content at, or ``None``
                for Copier's own default — the latest PEP440 tag when the
                template directory is a git repository root, a plain copy
                otherwise. ``None`` is what composition uses: it is the only
                setting that records a ``_commit`` resolvable outside Copier's
                throwaway clone, per
                docs/design/adr-015-idiomatic-artifacts.md. The parameter
                exists for an explicit author-loop opt-in.
        """
        super().__init__(url=url, ref=ref)
        self._merged_questions = merged_questions
        self._extra_config = extra_config or {}

    @cached_property
    def questions_data(self) -> dict[str, Any]:
        """Returns the consolidated question schema for this template."""
        return self._merged_questions

    @cached_property
    def config_data(self) -> dict[str, Any]:
        """Returns base config merged with any extra config provided.

        This ensures fields like ``tasks`` are visible to Copier Worker during
        rendering without modifying the on-disk template files.

        ``jinja_extensions`` merges additively — the layer's own declarations
        keep their order (loader-before-spec ordering is load-bearing for
        ``copier_template_extensions``) and injected entries are appended —
        because replacing the list would strip a layer's filepath-style local
        extensions, which never travel through the injected union.
        """
        base = dict(super().config_data or {})
        if self._extra_config:
            extra = dict(self._extra_config)
            injected = extra.pop("jinja_extensions", None)
            base.update(extra)
            if injected:
                own = list(base.get("jinja_extensions", []))
                base["jinja_extensions"] = own + [e for e in injected if e not in own]
        return base


__all__ = ["MergedTemplate"]
